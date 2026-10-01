"""Capture every C-Chain block from now back to a UTC date from the Data API's block list, and the daily EVM fees from it.

The Data API lists C-Chain blocks newest first, 100 to a page, each with ``feesSpent``: the sum of gas used times effective
gas price over the block's receipts, in wei (checked against the share on complete blocks, and against a node's receipts
to the wei on the gap blocks). It takes no time filter, so the capture pages back from the newest block until a page
reaches before ``from_date``. One page is one JSON line with the token that fetched it, written as it arrives; a stopped
capture continues from its last page with ``resume=<kept directory>``.

``data-api.p-chain-block-list`` pages the P-Chain list the same way. Each P-Chain block carries the supply counter and the
ACP-77 counters: the active L1 validator count and the fee each has accrued since Etna. The continuous L1 validator fee
between two blocks is the earlier count times the rise in accrued fees, as in the share's burn table.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
from collections.abc import Callable
from datetime import UTC, date, datetime
from itertools import pairwise
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

DATASET_ID = "data-api.c-chain-block-list"
P_LIST_ID = "data-api.p-chain-block-list"
DATASET_IDS = (DATASET_ID, P_LIST_ID)
SOURCE_ID = "avalanche-data-api"
ENDPOINT_ID = "c-chain-block-list"
TABLE = "c-chain-block-list"
PROGRESS = "progress.jsonl"
RAW = "raw/pages.jsonl"
PAGE_SIZE = 100
ATTEMPTS = 8
RETRY_SECONDS = 5.0
MAX_PAGES = 50_000
COLUMNS = {
    "block_height": "BIGINT",
    "block_hash": "VARCHAR",
    "block_timestamp": "TIMESTAMP",
    "date_utc": "DATE",
    "transactions": "INTEGER",
    "gas_used": "BIGINT",
    "base_fee_wei": "DECIMAL(38,0)",
    "fees_wei": "DECIMAL(38,0)",
}
P_COLUMNS = {
    "block_height": "BIGINT",
    "block_hash": "VARCHAR",
    "block_timestamp": "TIMESTAMP",
    "date_utc": "DATE",
    "block_type": "VARCHAR",
    "transactions": "INTEGER",
    "current_supply_navax": "BIGINT",
    "active_l1_validators": "BIGINT",
    "l1_validators_accrued_fees_navax": "BIGINT",
}


def _c_row(item: dict[str, Any], stamp: datetime) -> tuple[Any, ...]:
    return (int(item["blockNumber"]), item["blockHash"], stamp, stamp.date(), int(item["txCount"]), int(item["gasUsed"]),
            int(item["baseFee"]), int(item["feesSpent"]))


def _p_row(item: dict[str, Any], stamp: datetime) -> tuple[Any, ...]:
    return (int(item["blockNumber"]), item["blockHash"], stamp, stamp.date(), item["blockType"], int(item["txCount"]),
            int(item["currentSupply"]), int(item["activeL1Validators"]), int(item["l1ValidatorsAccruedFees"]))


LISTS = {
    DATASET_ID: {"endpoint_id": ENDPOINT_ID, "table": TABLE, "columns": COLUMNS, "row": _c_row},
    P_LIST_ID: {"endpoint_id": "p-chain-block-list", "table": "p-chain-block-list", "columns": P_COLUMNS, "row": _p_row},
}


def _endpoint(catalog: dict[str, Any], dataset_id: str = DATASET_ID) -> str:
    return next(item["url"] for item in source(catalog, SOURCE_ID)["endpoints"] if item["id"] == LISTS[dataset_id]["endpoint_id"])


def _parameters(parameters: dict[str, str] | None) -> dict[str, Any]:
    values = dict(parameters or {})
    unknown = set(values) - {"from_date", "resume"}
    if unknown:
        raise DataError(f"unknown parameters: {', '.join(sorted(unknown))}")
    try:
        from_date = date.fromisoformat(values["from_date"])
    except (KeyError, ValueError) as error:
        raise DataError("provide from_date=<YYYY-MM-DD>, the first UTC day to capture") from error
    return {"from_date": from_date.isoformat(), **({"resume": values["resume"]} if values.get("resume") else {})}


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    if dataset_id not in LISTS:
        raise DataError(f"unknown dataset: {dataset_id}")
    return {"dataset_id": dataset_id, "source_id": SOURCE_ID, "output": str(output), "endpoint": _endpoint(load_catalog(), dataset_id),
            **_parameters(parameters), "writes": [RAW, "capture.json"], "overwrite": False}


def _url(endpoint: str, token: str | None) -> str:
    query = {"pageSize": PAGE_SIZE, **({"pageToken": token} if token else {})}
    return f"{endpoint}?{urllib.parse.urlencode(query)}"


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
    floor = int(datetime.fromisoformat(preview["from_date"]).replace(tzinfo=UTC).timestamp())
    header = {"endpoint": preview["endpoint"], "from_date": preview["from_date"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    if "resume" in preview:
        temporary = Path(preview["resume"])
        try:
            lines = (temporary / PROGRESS).read_text(encoding="utf-8").splitlines()
            kept_header, records = json.loads(lines[0]), [json.loads(line) for line in lines[1:]]
            pages = (temporary / RAW).read_bytes().splitlines()
        except (OSError, IndexError, json.JSONDecodeError) as error:
            raise DataError(f"cannot resume from {temporary}: {error}") from error
        if kept_header != header:
            raise DataError("cannot resume: the kept capture starts elsewhere or reads another endpoint")
        kept = 0
        for record, page in zip(records, pages):
            if sha256(page) != record["sha256"] or len(page) != record["bytes"]:
                break
            kept += 1
        records = records[:kept]
        (temporary / RAW).write_bytes(b"".join(page + b"\n" for page in pages[:kept]))
        (temporary / PROGRESS).write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in [header, *records]), encoding="utf-8")
    else:
        temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
        (temporary / "raw").mkdir()
        (temporary / RAW).write_bytes(b"")
        (temporary / PROGRESS).write_text(json.dumps(header, sort_keys=True) + "\n", encoding="utf-8")
        records = []
    token = records[-1]["next_token"] if records else None
    done = bool(records) and (records[-1]["oldest_timestamp"] < floor or not token)
    retries = 0
    try:
        with (temporary / RAW).open("ab") as raw, (temporary / PROGRESS).open("a", encoding="utf-8") as progress:
            while not done:
                if len(records) >= MAX_PAGES:
                    raise DataError(f"more than {MAX_PAGES} pages; start from a later date")
                url = _url(preview["endpoint"], token)
                for attempt in range(1, ATTEMPTS + 1):
                    try:
                        body, _ = request(url, timeout)
                        break
                    except DataError as error:
                        # Keyless, the Data API refuses for minutes after about a thousand requests. Wait, doubling, then keep the pages.
                        if attempt == ATTEMPTS or not isinstance(error.__cause__, (OSError, urllib.error.URLError)):
                            raise DataError(f"{error}; {len(records)} pages kept at {temporary}") from error
                        retries += 1
                        time.sleep(RETRY_SECONDS * 2 ** (attempt - 1))
                value = json.loads(body)
                blocks = value.get("blocks") or []
                if not blocks:
                    raise DataError(f"an empty page; {len(records)} pages kept at {temporary}")
                line = json.dumps({"page_token": token, "response": value}, separators=(",", ":"), sort_keys=True).encode()
                raw.write(line + b"\n")
                oldest = min(int(item["blockTimestamp"]) for item in blocks)
                token = value.get("nextPageToken")
                record = {"page": len(records), "bytes": len(line), "sha256": sha256(line), "blocks": len(blocks),
                          "oldest_timestamp": oldest, "next_token": token}
                records.append(record)
                progress.write(json.dumps(record, sort_keys=True) + "\n")
                raw.flush()
                progress.flush()
                done = oldest < floor or not token
        completed_at = now()
        body_all = (temporary / RAW).read_bytes()
        identity = sha256(canonical_bytes({"completed_at": completed_at, "sha256": sha256(body_all)}))
        receipt = {
            "schema_version": "data-api-block-list-capture/v1",
            "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
            "dataset_id": dataset_id, "source_id": SOURCE_ID, "completed_at": completed_at,
            "contract_sha256": contract_hash(catalog, dataset_id), "tool": f"avalanche-research@{__version__}",
            "endpoint": preview["endpoint"], "from_date": preview["from_date"], "retries": retries,
            "responses": [{"endpoint_id": LISTS[dataset_id]["endpoint_id"], "path": RAW, "pages": len(records), "bytes": len(body_all), "sha256": sha256(body_all)}],
            "pages": [{key: record[key] for key in ("page", "bytes", "sha256", "blocks")} for record in records],
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        (temporary / PROGRESS).unlink()
        os.replace(temporary, output)
        return receipt
    except Exception:
        if not (temporary / RAW).exists() or (temporary / RAW).stat().st_size == 0:
            shutil.rmtree(temporary, ignore_errors=True)
        raise


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    """Every listed block on or after from_date once, from pages that chain by token."""
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid block list capture receipt: {error}") from error
    dataset_id = receipt.get("dataset_id")
    if receipt.get("schema_version") != "data-api-block-list-capture/v1" or dataset_id not in LISTS:
        raise DataError("unsupported block list capture receipt")
    parse = LISTS[dataset_id]["row"]
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), dataset_id):
        raise DataError("block list capture contract hash differs")
    summary = receipt["responses"][0]
    body = (capture_dir / summary["path"]).read_bytes()
    if sha256(body) != summary["sha256"] or len(body) != summary["bytes"]:
        raise DataError("captured pages hash or size differs")
    pages = body.splitlines()
    if len(pages) != len(receipt["pages"]):
        raise DataError("captured pages differ from the receipt")
    floor = datetime.fromisoformat(receipt["from_date"]).date()
    rows: dict[int, tuple[Any, ...]] = {}
    token = None
    for line, record in zip(pages, receipt["pages"]):
        if sha256(line) != record["sha256"]:
            raise DataError(f"page {record['page']} differs from its record")
        page = json.loads(line)
        if page["page_token"] != token:
            raise DataError(f"page {record['page']} was not fetched with the token of the page before it")
        token = page["response"].get("nextPageToken")
        for item in page["response"]["blocks"]:
            stamp = datetime.fromtimestamp(int(item["blockTimestamp"]), UTC).replace(tzinfo=None)
            if stamp.date() < floor:
                continue
            row = parse(item, stamp)
            if rows.setdefault(row[0], row) != row:
                raise DataError(f"block {row[0]} is listed twice with different fields")
    return receipt, [rows[height] for height in sorted(rows)]


def _gaps(rows: list[tuple[Any, ...]]) -> int:
    return sum(later[0] - earlier[0] - 1 for earlier, later in pairwise(rows))


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id not in LISTS:
        raise DataError(f"unknown dataset: {dataset_id}")
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{LISTS[dataset_id]['table']}.parquet", "build.json"], "overwrite": False}


def _write(parquet: Path, columns: dict[str, str], rows: list[tuple[Any, ...]]) -> None:
    connection = duckdb.connect()
    try:
        connection.execute(f"CREATE TABLE rows({', '.join(f'{name} {kind}' for name, kind in columns.items())})")
        casts = ", ".join(f"CAST(? AS {kind})" if kind.startswith("DECIMAL") else "?" for kind in columns.values())
        connection.executemany(f"INSERT INTO rows VALUES ({casts})",
                               [[str(value) if kind.startswith("DECIMAL") and value is not None else value for value, kind in zip(row, columns.values())] for row in rows])
        connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
    finally:
        connection.close()


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    build_preview(dataset_id, capture_dir, output)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    receipt, rows = read_rows(capture_dir)
    if receipt["dataset_id"] != dataset_id:
        raise DataError(f"the capture is of {receipt['dataset_id']}, not {dataset_id}")
    spec = LISTS[dataset_id]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet = temporary / f"{spec['table']}.parquet"
        _write(parquet, spec["columns"], rows)
        result = {
            "schema_version": "data-api-build/v1", "dataset_id": dataset_id, "dataset_schema": dataset(load_catalog(), dataset_id)["fields"],
            "source_capture_id": receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": {"rows": len(rows), "first_block": rows[0][0] if rows else None, "last_block": rows[-1][0] if rows else None,
                        "missing_heights": _gaps(rows), **({"fees_wei": str(sum(row[7] for row in rows))} if dataset_id == DATASET_ID else {})},
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(result))
        os.replace(temporary, output)
        return result
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    """The block list: pages chain by token and each block appears once."""
    receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    findings: list[str] = []
    if receipt.get("dataset_id") in LISTS:
        if against is not None:
            raise DataError(f"{receipt['dataset_id']} takes no --against directory")
        _, rows = read_rows(capture_dir)
        summary: dict[str, Any] = {"rows": len(rows), "missing_heights": _gaps(rows)}
        if summary["missing_heights"]:
            findings.append(f"{summary['missing_heights']} heights are missing between the first and last listed block")
        return {"dataset_id": receipt["dataset_id"], "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
                "checked": ["capture hashes", "page token chain", "every block once", "no missing height"], "summary": summary, "findings": findings}
    raise DataError(f"not a {DATASET_ID} or {P_LIST_ID} capture: {capture_dir}")
