"""Inputs for the Gross Chain Income study, and one checked monthly table built from them.

Eric Lu's Gross Chain Income article (2026-08-12) nests three layers: on-chain production (NGCP), yield paid to
Avalanche holders by real-world-asset products, and the reserve income that stablecoin issuers earn on the float
resident on Avalanche. Its monthly table is not public. These datasets rebuild what public data allows:

| Dataset | What |
| --- | --- |
| ``c-chain-rpc.token-supply-monthly`` | Each tracked token's supply at the last C-Chain block of each UTC month, and each ERC-4626 vault's assets |
| ``fred.tbill-3m-daily`` | The 3-month Treasury bill secondary-market discount rate, FRED ``DTB3``, the article's bill rate |
| ``defillama.avalanche-fees-daily`` | DefiLlama's Avalanche fees and revenue, context for NGCP and never NGCP |
| ``derived.gci-monthly`` | One row per month: issuer float and income, holder-product float and income where the chain shows it, fees, and the C-Chain burn |

Issuer income is the resident float times the month's mean ``DTB3`` over 12, on native USDT and USDC as the article
counts them; bridged ``.e`` float is kept apart. A vault's holder income is the rise in its assets per share over the
month times the shares at the month's start. BUIDL and JAAA pay their yield off-chain or by new tokens, so only their
float is shown.
"""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
import time
import urllib.error
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb

from .. import __version__
from ..core.catalog import (
    DataError,
    canonical_bytes,
    contract_hash,
    dataset,
    load_catalog,
    now,
    sha256,
    source,
)
from .capture.rest import _request

SUPPLY_ID = "c-chain-rpc.token-supply-monthly"
RATE_ID = "fred.tbill-3m-daily"
FEES_ID = "defillama.avalanche-fees-daily"
DATASET_IDS = (SUPPLY_ID, RATE_ID, FEES_ID)
# Each token with the public page that confirms its Avalanche contract; name, symbol, and decimals were read on-chain
# on 2026-09-29 and match. Vaults are ERC-4626: their assets are read with totalAssets.
TOKENS = {
    "USDT": ("0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7", "issuer", "Tether", False, "https://tether.to/en/supported-protocols/"),
    "USDC": ("0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E", "issuer", "Circle", False, "https://developers.circle.com/stablecoins/usdc-contract-addresses"),
    "USDT.e": ("0xc7198437980c041c805A1EDcbA50c1Ce5db95118", "bridged", "Tether", False, "https://snowtrace.io/token/0xc7198437980c041c805A1EDcbA50c1Ce5db95118"),
    "USDC.e": ("0xA7D7079b0FEaD91F3e65f86E8915Cb59c1a4C664", "bridged", "Circle", False, "https://snowtrace.io/token/0xA7D7079b0FEaD91F3e65f86E8915Cb59c1a4C664"),
    "BUIDL": ("0x53fc82f14f009009b440a706e31c9021e1196a2f", "holder", "BlackRock", False, "https://www.coingecko.com/en/coins/blackrock-usd-institutional-digital-liquidity-fund"),
    "JAAA": ("0x58f93d6b1ef2f44ec379cb975657c132cbed3b6b", "holder", "Janus Henderson", False, "https://www.coingecko.com/en/coins/janus-henderson-anemoy-aaa-clo-fund"),
    "savUSD": ("0x06d47F3fb376649c3A9Dafe069B3D6E35572219E", "holder", "Avant", True, "https://docs.avantprotocol.com/security/contract-addresses"),
    "savBTC": ("0x649342c6bff544d82DF1B2bA3C93e0C22cDeBa84", "holder", "Avant", True, "https://docs.avantprotocol.com/security/contract-addresses"),
}
SELECTORS = {"totalSupply": "0x18160ddd", "decimals": "0x313ce567", "totalAssets": "0x01e1d114"}
FIRST_MONTH = "2024-01"
ATTEMPTS = 8
RETRY_SECONDS = 2.0
PAUSE_SECONDS = 0.2
FRED_SERIES = ("DTB3", "TB3MS")
FEE_TYPES = ("dailyFees", "dailyRevenue")
COLUMNS = {
    SUPPLY_ID: {
        "month": "DATE", "block_number": "BIGINT", "block_time": "TIMESTAMP", "token": "VARCHAR", "contract": "VARCHAR", "role": "VARCHAR",
        "issuer": "VARCHAR", "deployed": "BOOLEAN", "decimals": "INTEGER", "total_supply_raw": "DECIMAL(38,0)", "total_supply": "DOUBLE",
        "total_assets_raw": "DECIMAL(38,0)", "total_assets": "DOUBLE", "assets_per_share": "DOUBLE",
    },
    RATE_ID: {"date_utc": "DATE", "discount_rate_pct": "DOUBLE"},
    FEES_ID: {"date_utc": "DATE", "fees_usd": "DOUBLE", "revenue_usd": "DOUBLE"},
}
TABLES = {SUPPLY_ID: "token-supply-monthly", RATE_ID: "tbill-3m-daily", FEES_ID: "avalanche-fees-daily"}
SOURCES = {SUPPLY_ID: "tenderly-c-chain-rpc", RATE_ID: "fred", FEES_ID: "defillama"}
ENDPOINTS = {SUPPLY_ID: "eth-call", RATE_ID: "fredgraph-csv", FEES_ID: "avalanche-fees-overview"}


def _table(dataset_id: str) -> str:
    if dataset_id not in TABLES:
        raise DataError(f"unknown dataset: {dataset_id}")
    return TABLES[dataset_id]


def _endpoint(catalog: dict[str, Any], dataset_id: str) -> str:
    return next(item["url"] for item in source(catalog, SOURCES[dataset_id])["endpoints"] if item["id"] == ENDPOINTS[dataset_id])


def _months(first: str, last: str) -> list[date]:
    start, end = date.fromisoformat(first + "-01"), date.fromisoformat(last + "-01")
    months = []
    while start <= end:
        months.append(start)
        start = date(start.year + start.month // 12, start.month % 12 + 1, 1)
    return months


def _next_month(month: date) -> date:
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)


def _last_complete_month() -> str:
    today = datetime.now(UTC).date()
    previous = date(today.year - (today.month == 1), (today.month - 2) % 12 + 1, 1)
    return previous.isoformat()[:7]


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    _table(dataset_id)
    values = dict(parameters or {})
    allowed = {"from_month", "to_month", "resume"} if dataset_id == SUPPLY_ID else set()
    if set(values) - allowed:
        raise DataError(f"unknown parameters: {', '.join(sorted(set(values) - allowed))}")
    preview: dict[str, Any] = {"dataset_id": dataset_id, "source_id": SOURCES[dataset_id], "output": str(output),
                               "endpoint": _endpoint(load_catalog(), dataset_id), "writes": ["raw/", "capture.json"], "overwrite": False}
    if dataset_id == SUPPLY_ID:
        first, last = values.get("from_month", FIRST_MONTH), values.get("to_month", _last_complete_month())
        try:
            months = _months(first, last)
        except ValueError as error:
            raise DataError("from_month and to_month are YYYY-MM") from error
        if not months:
            raise DataError("to_month precedes from_month")
        preview.update(from_month=first, to_month=last, months=len(months), tokens=list(TOKENS), **({"resume": values["resume"]} if values.get("resume") else {}))
    return preview


class _Node:
    """One JSON-RPC call at a time to the gateway, retried with a doubling wait, paced, with block times cached."""

    def __init__(self, endpoint: str, timeout: float, request: Callable[..., tuple[bytes, dict[str, Any]]]):
        self.endpoint, self.timeout, self.request, self.times, self.retries = endpoint, timeout, request, {}, 0

    def call(self, method: str, params: list[Any]) -> Any:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        for attempt in range(1, ATTEMPTS + 1):
            try:
                body, _ = self.request(self.endpoint, self.timeout, body_json=payload)
                value = json.loads(body)
                if value.get("error"):
                    raise DataError(f"{method} answered {value['error']}")
                time.sleep(PAUSE_SECONDS)
                return value.get("result")
            except DataError as error:
                if attempt == ATTEMPTS or not isinstance(error.__cause__, (OSError, urllib.error.URLError)):
                    raise
                self.retries += 1
                time.sleep(RETRY_SECONDS * 2 ** (attempt - 1))
        raise AssertionError("unreachable")

    def block_time(self, height: int) -> int:
        if height not in self.times:
            block = self.call("eth_getBlockByNumber", [hex(height), False])
            self.times[height] = int(block["timestamp"], 16)
        return self.times[height]

    def last_block_before(self, instant: int, low: int, high: int) -> int:
        """The highest block whose time is before ``instant``, by bisection between two known heights."""
        while low < high:
            middle = (low + high + 1) // 2
            if self.block_time(middle) < instant:
                low = middle
            else:
                high = middle - 1
        return low


def _month_record(node: _Node, month: date, low: int, head: int) -> dict[str, Any]:
    instant = int(datetime.combine(_next_month(month), datetime.min.time(), UTC).timestamp())
    block = node.last_block_before(instant, low, head)
    calls: dict[str, dict[str, Any]] = {}
    for token, (contract, _, _, vault, _) in TOKENS.items():
        tag = hex(block)
        calls[token] = {"totalSupply": node.call("eth_call", [{"to": contract, "data": SELECTORS["totalSupply"]}, tag]),
                        "decimals": node.call("eth_call", [{"to": contract, "data": SELECTORS["decimals"]}, tag])}
        if vault:
            calls[token]["totalAssets"] = node.call("eth_call", [{"to": contract, "data": SELECTORS["totalAssets"]}, tag])
    return {"month": month.isoformat()[:7], "block": block, "block_time": node.block_time(block), "next_block_time": node.block_time(block + 1), "calls": calls}


def capture(
    dataset_id: str,
    output: Path,
    timeout: float = 20,
    parameters: dict[str, str] | None = None,
    request: Callable[..., tuple[bytes, dict[str, Any]]] = _request,
) -> dict[str, Any]:
    preview = capture_preview(dataset_id, output, parameters)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    output.parent.mkdir(parents=True, exist_ok=True)
    if dataset_id == SUPPLY_ID and "resume" in preview:
        temporary = Path(preview["resume"])
        lines = (temporary / "raw" / "months.jsonl").read_bytes().splitlines() if (temporary / "raw" / "months.jsonl").exists() else []
    else:
        temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
        (temporary / "raw").mkdir()
        lines = []
    extra: dict[str, Any] = {}
    try:
        if dataset_id == SUPPLY_ID:
            node = _Node(preview["endpoint"], timeout, request)
            head = int(node.call("eth_blockNumber", []), 16)
            done = {json.loads(line)["month"] for line in lines}
            low = max((json.loads(line)["block"] for line in lines), default=0)
            with (temporary / "raw" / "months.jsonl").open("ab") as raw:
                for month in _months(preview["from_month"], preview["to_month"]):
                    if month.isoformat()[:7] in done:
                        continue
                    record = _month_record(node, month, low, head)
                    low = record["block"]
                    raw.write(json.dumps(record, separators=(",", ":"), sort_keys=True).encode() + b"\n")
                    raw.flush()
            extra = {"from_month": preview["from_month"], "to_month": preview["to_month"], "head_block": head, "retries": node.retries,
                     "tokens": {token: {"contract": item[0], "role": item[1], "issuer": item[2], "vault": item[3], "confirmed_by": item[4]}
                                for token, item in TOKENS.items()}}
        elif dataset_id == RATE_ID:
            for series in FRED_SERIES:
                body, _ = request(f"{preview['endpoint']}?id={series}", timeout, content="csv")
                (temporary / "raw" / f"{series}.csv").write_bytes(body)
        else:
            for kind in FEE_TYPES:
                body, _ = request(f"{preview['endpoint']}?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType={kind}", timeout)
                (temporary / "raw" / f"{kind}.json").write_bytes(body)
        files = sorted((temporary / "raw").iterdir())
        records = [{"path": f"raw/{path.name}", "bytes": path.stat().st_size, "sha256": sha256(path.read_bytes())} for path in files]
        completed_at = now()
        identity = sha256(canonical_bytes({"completed_at": completed_at, "responses": records}))
        receipt = {
            "schema_version": "gci-capture/v1", "capture_id": f"capture:{SOURCES[dataset_id]}:{completed_at}:{identity[:12]}",
            "dataset_id": dataset_id, "source_id": SOURCES[dataset_id], "completed_at": completed_at,
            "contract_sha256": contract_hash(catalog, dataset_id), "tool": f"avalanche-research@{__version__}",
            "endpoint": preview["endpoint"], **extra, "responses": records,
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        os.replace(temporary, output)
        return receipt
    except Exception as error:
        if dataset_id == SUPPLY_ID and (temporary / "raw" / "months.jsonl").exists() and (temporary / "raw" / "months.jsonl").stat().st_size:
            raise DataError(f"{error}; months kept at {temporary}") from error
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _hex_int(value: Any) -> int | None:
    if not isinstance(value, str) or value in ("0x", ""):
        return None
    return int(value, 16)


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid capture receipt: {error}") from error
    dataset_id = receipt.get("dataset_id")
    if receipt.get("schema_version") != "gci-capture/v1" or dataset_id not in SOURCES:
        raise DataError("unsupported capture receipt")
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), dataset_id):
        raise DataError(f"{dataset_id} capture contract hash differs")
    bodies = {}
    for record in receipt["responses"]:
        body = (capture_dir / record["path"]).read_bytes()
        if sha256(body) != record["sha256"] or len(body) != record["bytes"]:
            raise DataError(f"{record['path']} differs from its receipt")
        bodies[record["path"]] = body
    rows: list[tuple[Any, ...]] = []
    if dataset_id == SUPPLY_ID:
        for line in bodies["raw/months.jsonl"].splitlines():
            month = json.loads(line)
            if not month["block_time"] < datetime.combine(_next_month(date.fromisoformat(month["month"] + "-01")), datetime.min.time(), UTC).timestamp() <= month["next_block_time"]:
                raise DataError(f"block {month['block']} is not the last block of {month['month']}")
            stamp = datetime.fromtimestamp(month["block_time"], UTC).replace(tzinfo=None)
            for token, calls in month["calls"].items():
                spec = receipt["tokens"][token]
                contract, role, issuer, vault = spec["contract"], spec["role"], spec["issuer"], spec["vault"]
                supply, decimals = _hex_int(calls["totalSupply"]), _hex_int(calls["decimals"])
                assets = _hex_int(calls.get("totalAssets")) if vault else None
                deployed = supply is not None and decimals is not None
                scale = 10 ** decimals if deployed else None
                rows.append((date.fromisoformat(month["month"] + "-01"), month["block"], stamp, token, contract, role, issuer, deployed, decimals,
                             supply, supply / scale if deployed else None, assets, assets / scale if deployed and assets is not None else None,
                             assets / supply if deployed and assets is not None and supply else None))
    elif dataset_id == RATE_ID:
        for row in csv.DictReader(io.StringIO(bodies["raw/DTB3.csv"].decode())):
            value = row.get("DTB3", "").strip()
            rows.append((date.fromisoformat(row["observation_date"]), float(value) if value not in ("", ".") else None))
    else:
        by_day: dict[date, list[float | None]] = {}
        for index, kind in enumerate(FEE_TYPES):
            for stamp, value in json.loads(bodies[f"raw/{kind}.json"])["totalDataChart"]:
                by_day.setdefault(datetime.fromtimestamp(int(stamp), UTC).date(), [None, None])[index] = float(value)
        rows = [(day, *values) for day, values in sorted(by_day.items())]
    return receipt, rows


def _write(parquet: Path, columns: dict[str, str], rows: list[tuple[Any, ...]]) -> None:
    connection = duckdb.connect()
    try:
        connection.execute(f"CREATE TABLE rows({', '.join(f'{name} {kind}' for name, kind in columns.items())})")
        casts = ", ".join("CAST(? AS DECIMAL(38,0))" if kind.startswith("DECIMAL") else "?" for kind in columns.values())
        prepared = [[str(value) if kind.startswith("DECIMAL") and value is not None else value for value, kind in zip(row, columns.values())] for row in rows]
        if prepared:
            connection.executemany(f"INSERT INTO rows VALUES ({casts})", prepared)
        connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
    finally:
        connection.close()


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{_table(dataset_id)}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    build_preview(dataset_id, capture_dir, output)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    receipt, rows = read_rows(capture_dir)
    if receipt["dataset_id"] != dataset_id:
        raise DataError(f"the capture is of {receipt['dataset_id']}, not {dataset_id}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet = temporary / f"{_table(dataset_id)}.parquet"
        _write(parquet, COLUMNS[dataset_id], rows)
        result = {
            "schema_version": "gci-build/v1", "dataset_id": dataset_id, "dataset_schema": dataset(load_catalog(), dataset_id)["fields"],
            "source_capture_id": receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": {"rows": len(rows), "first": str(rows[0][0]) if rows else None, "last": str(rows[-1][0]) if rows else None},
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(result))
        os.replace(temporary, output)
        return result
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _tb3ms_findings(capture_dir: Path, rows: list[tuple[Any, ...]]) -> tuple[int, list[str]]:
    """Monthly means of DTB3 against FRED's own monthly average TB3MS, within 0.01 points."""
    monthly: dict[str, list[float]] = {}
    for day, value in rows:
        if value is not None:
            monthly.setdefault(day.isoformat()[:7], []).append(value)
    compared, differing = 0, []
    for row in csv.DictReader(io.StringIO((capture_dir / "raw" / "TB3MS.csv").read_text())):
        month = row["observation_date"][:7]
        if month in monthly and row["TB3MS"].strip() not in ("", "."):
            compared += 1
            mean = sum(monthly[month]) / len(monthly[month])
            if abs(round(mean, 2) - float(row["TB3MS"])) > 0.01 + 1e-9:
                differing.append(f"{month} {mean:.3f} against {row['TB3MS']}")
    return compared, differing


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    """Captures: hashes, the month-end block rule, and for the bill rate the monthly means against TB3MS."""
    if against is not None:
        raise DataError("the GCI datasets take no --against directory")
    receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    dataset_id = receipt.get("dataset_id")
    findings: list[str] = []
    summary: dict[str, Any] = {}
    receipt, rows = read_rows(capture_dir)
    checked = ["capture hashes"]
    summary = {"rows": len(rows)}
    if dataset_id == SUPPLY_ID:
        checked.append("each block is its month's last")
        negative = sum(1 for row in rows if row[9] is not None and row[9] < 0)
        if negative:
            findings.append(f"{negative} negative supplies")
    if dataset_id == RATE_ID:
        checked.append("monthly means of DTB3 equal TB3MS within 0.01")
        compared, differing = _tb3ms_findings(capture_dir, rows)
        summary.update(months_compared=compared, months_differing=len(differing))
        if differing:
            findings.append(f"{len(differing)} months differ from TB3MS: {', '.join(differing[:5])}")
    if dataset_dir is not None:
        checked.append("build hashes")
        built = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
        body = (dataset_dir / built["outputs"][0]["path"]).read_bytes()
        if built["source_capture_id"] != receipt["capture_id"] or sha256(body) != built["outputs"][0]["sha256"]:
            findings.append("build receipt or Parquet hash differs")
    return {"dataset_id": dataset_id, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}
