"""AVAX exchange-traded products: net asset value, shares, and AVAX held, as each issuer publishes them.

Two datasets share one source. ``etf-issuers.avax-fund-snapshot`` holds one row per fund per capture from each
issuer's current figures: Bitwise's BAVA page, VanEck's VAVX blocks, 21Shares' product details for its Avalanche
product and two baskets that hold AVAX, and Grayscale GAVA's latest quarterly SEC filing. Most of these figures are
current only, so the daily capture is what turns them into a series. ``etf-issuers.avax-fund-history`` holds one row
per fund per valuation date from the histories issuers do publish: 21Shares' daily valuations, BAVA's daily NAV, and
GAVA's quarter-end filings.

Issuers serve these figures in different forms (an HTML page with embedded JSON, JSON blocks that expect a browser,
gzipped JSON, and an SEC API that requires a named contact), so this module fetches them itself rather than through
the shared JSON capture path. Each response is stored exactly as served, after gzip decoding, with its hash in the
receipt. The BAVA page is kept whole, so its wallet list stays in the raw capture.
"""

from __future__ import annotations

import gzip
import http.cookiejar
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb

from . import __version__
from .catalog import (
    DataError,
    canonical_bytes,
    contract_hash,
    dataset,
    load_catalog,
    now,
    sha256,
    source,
)

SOURCE_ID = "etf-issuers"
SNAPSHOT_ID = "etf-issuers.avax-fund-snapshot"
HISTORY_ID = "etf-issuers.avax-fund-history"
DATASET_IDS = (SNAPSHOT_ID, HISTORY_ID)
TABLES = {SNAPSHOT_ID: "avax-fund-snapshot", HISTORY_ID: "avax-fund-history"}
USER_AGENT = "avalanche-phase-ii-research/0.1"
# VanEck's blocks answer a browser. SEC EDGAR asks for a User-Agent naming a contact: set AVALANCHE_SEC_CONTACT to add
# one. No personal contact is kept in code or receipts.
BROWSER_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def sec_user_agent() -> str:
    contact = os.environ.get("AVALANCHE_SEC_CONTACT", "").strip()
    return f"{USER_AGENT} {contact}" if contact else USER_AGENT
ATTEMPTS = 3
RETRY_SECONDS = 5.0
TOLERANCE = 0.005
NEXT_DATA = re.compile(rb'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)

BAVA = "bava-page"
VAVX_NAV, VAVX_STAKING, VAVX_PRICES = "vaneck-vavx-nav", "vaneck-vavx-staking", "vaneck-vavx-prices"
SEC_GAVA = "sec-gava-facts"
TS_PREFIX = "twentyone-shares-"
TS_TICKERS = ("AVAX", "MOON", "KEYS")
# The valuation histories carry no product name; these are the names product_details reported on 2026-09-28.
TS_FUNDS = {"AVAX": "21shares Avalanche Staking ETP", "MOON": "Sygnum Platform Winners Index ETP", "KEYS": "21shares Bitwise Select 10 ETP"}

SNAPSHOT_COLUMNS = {
    "captured_at": "TIMESTAMP",
    "issuer": "VARCHAR",
    "fund": "VARCHAR",
    "ticker": "VARCHAR",
    "endpoint_id": "VARCHAR",
    "as_of": "DATE",
    "nav_usd": "DOUBLE",
    "net_assets_usd": "DOUBLE",
    "shares_outstanding": "DOUBLE",
    "avax_held": "DOUBLE",
    "avax_per_share": "DOUBLE",
    "avax_weight": "DOUBLE",
    "avax_held_derived": "BOOLEAN",
    "staked_share": "DOUBLE",
}
HISTORY_COLUMNS = {
    "captured_at": "TIMESTAMP",
    "issuer": "VARCHAR",
    "fund": "VARCHAR",
    "ticker": "VARCHAR",
    "endpoint_id": "VARCHAR",
    "valuation_date": "DATE",
    "nav_usd": "DOUBLE",
    "net_assets_usd": "DOUBLE",
    "shares_outstanding": "DOUBLE",
    "avax_price_usd": "DOUBLE",
    "avax_held": "DOUBLE",
    "avax_per_share": "DOUBLE",
    "avax_held_derived": "BOOLEAN",
}
COLUMNS = {SNAPSHOT_ID: SNAPSHOT_COLUMNS, HISTORY_ID: HISTORY_COLUMNS}


def _check_dataset(dataset_id: str) -> None:
    if dataset_id not in DATASET_IDS:
        raise DataError(f"unknown dataset: {dataset_id}")


def _headers(url: str) -> dict[str, str]:
    host = urllib.parse.urlsplit(url).hostname or ""
    agent = sec_user_agent() if host == "data.sec.gov" else BROWSER_USER_AGENT if host.endswith("vaneck.com") else USER_AGENT
    return {"User-Agent": agent, "Accept": "application/json, text/html;q=0.9", "Accept-Encoding": "gzip"}


def _default_opener() -> Callable[..., Any]:
    """One cookie jar per capture: VanEck sets session cookies on the first block and expects them on the next."""
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())).open


def _decode(body: bytes) -> bytes:
    return gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body


def _bava_data(body: bytes) -> dict[str, Any]:
    """The fund record embedded in the BAVA page's Next.js data."""
    match = NEXT_DATA.search(body)
    if match is None:
        raise DataError("the BAVA page carries no __NEXT_DATA__ block")
    try:
        return json.loads(match.group(1))["props"]["pageProps"]["fundData"]["data"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise DataError(f"the BAVA page's embedded data has an unexpected shape: {error}") from error


def _validate(endpoint_id: str, body: bytes) -> None:
    if endpoint_id == BAVA:
        _bava_data(body)
        return
    try:
        value = json.loads(body)
    except json.JSONDecodeError as error:
        raise DataError(f"response is not JSON for {endpoint_id}: {error}") from error
    if not isinstance(value, dict):
        raise DataError(f"response is not a JSON object for {endpoint_id}")


def _request(url: str, endpoint_id: str, timeout: float, opener: Callable[..., Any]) -> tuple[bytes, dict[str, Any]]:
    request = urllib.request.Request(url, headers=_headers(url))
    try:
        with opener(request, timeout=timeout) as response:
            body = _decode(response.read())
            status = int(getattr(response, "status", 200))
            content_type = response.headers.get("Content-Type", "")
    except (OSError, urllib.error.URLError) as error:
        raise DataError(f"request failed for {url}: {error}") from error
    if status != 200:
        raise DataError(f"request returned HTTP {status} for {url}")
    _validate(endpoint_id, body)
    return body, {"http_status": status, "content_type": content_type}


def _fetch(url: str, endpoint_id: str, timeout: float, opener: Callable[..., Any], sleep: Callable[[float], None]) -> tuple[bytes, dict[str, Any]]:
    """A request retried with growing waits when the connection fails; a malformed answer fails at once."""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            body, meta = _request(url, endpoint_id, timeout, opener)
            return body, {**meta, "attempts": attempt}
        except DataError as error:
            if attempt == ATTEMPTS or not isinstance(error.__cause__, (OSError, urllib.error.URLError)):
                raise
            sleep(RETRY_SECONDS * attempt)
    raise AssertionError("unreachable")


def _raw_path(endpoint_id: str) -> str:
    return f"raw/{endpoint_id}.{'html' if endpoint_id == BAVA else 'json'}"


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    _check_dataset(dataset_id)
    if parameters:
        raise DataError(f"{dataset_id} accepts no parameters")
    catalog = catalog or load_catalog()
    endpoints = {item["id"]: item for item in source(catalog, SOURCE_ID)["endpoints"]}
    requests = [{"endpoint_id": item, "url": endpoints[item]["url"], "method": "GET", "path": _raw_path(item)} for item in dataset(catalog, dataset_id)["endpoint_ids"]]
    return {"dataset_id": dataset_id, "source_id": SOURCE_ID, "output": str(output), "requests": requests,
            "writes": [item["path"] for item in requests] + ["capture.json"], "overwrite": False}


def capture(
    dataset_id: str,
    output: Path,
    timeout: float = 20,
    parameters: dict[str, str] | None = None,
    catalog: dict[str, Any] | None = None,
    opener: Callable[..., Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    preview = capture_preview(dataset_id, output, parameters, catalog)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    opener = opener or _default_opener()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "raw").mkdir()
        records = []
        for item in preview["requests"]:
            body, meta = _fetch(item["url"], item["endpoint_id"], timeout, opener, sleep)
            (temporary / item["path"]).write_bytes(body)
            records.append({"endpoint_id": item["endpoint_id"], "url": item["url"], "method": "GET", "path": item["path"],
                            "bytes": len(body), "sha256": sha256(body), **meta})
        completed_at = now()
        identity = sha256(canonical_bytes({"completed_at": completed_at, "responses": records}))
        receipt = {
            "schema_version": f"{SOURCE_ID}-capture/v1",
            "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
            "dataset_id": dataset_id,
            "source_id": SOURCE_ID,
            "completed_at": completed_at,
            "contract_sha256": contract_hash(catalog, dataset_id),
            "tool": f"avalanche-research@{__version__}",
            "responses": records,
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return receipt


def read_capture(capture_dir: Path, catalog: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """The receipt and each endpoint's parsed answer, verified against the receipt's hashes and the current contract."""
    catalog = catalog or load_catalog()
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid capture receipt: {error}") from error
    if receipt.get("schema_version") != f"{SOURCE_ID}-capture/v1" or receipt.get("dataset_id") not in DATASET_IDS:
        raise DataError(f"not an {SOURCE_ID} capture: {capture_dir}")
    if receipt.get("contract_sha256") != contract_hash(catalog, receipt["dataset_id"]):
        raise DataError("capture contract hash differs from the current data contract")
    values: dict[str, Any] = {}
    for item in receipt.get("responses", []):
        try:
            body = (capture_dir / item["path"]).read_bytes()
        except OSError as error:
            raise DataError(f"missing captured response: {item.get('path')}") from error
        if len(body) != item.get("bytes") or sha256(body) != item.get("sha256"):
            raise DataError(f"captured response hash or size differs: {item['path']}")
        _validate(item["endpoint_id"], body)
        values[item["endpoint_id"]] = _bava_data(body) if item["endpoint_id"] == BAVA else json.loads(body)
    missing = sorted(set(dataset(catalog, receipt["dataset_id"])["endpoint_ids"]) - values.keys())
    if missing:
        raise DataError(f"capture is missing endpoints: {', '.join(missing)}")
    return receipt, values


def _number(text: Any) -> float | None:
    """VanEck's display strings: ``20,724,615``, ``$21.82``, ``80.00``, ``5.93%``."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    cleaned = str(text).replace(",", "").replace("$", "").replace("%", "").strip()
    return float(cleaned) if cleaned else None


def _us_date(text: str) -> date:
    month, day, year = (int(part) for part in text.split("/"))
    return date(year, month, day)


def _captured_at(receipt: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(receipt["completed_at"]).astimezone(UTC).replace(tzinfo=None)


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    return numerator / denominator if numerator is not None and denominator else None


def _bava_avax(data: dict[str, Any]) -> tuple[float, float]:
    """BAVA's AVAX units and their basket weight."""
    basket = [item for item in data["holdings"]["basket"] if str(item.get("companyName", "")).upper() == "AVALANCHE"]
    if len(basket) != 1:
        raise DataError(f"the BAVA basket holds {len(basket)} Avalanche lines, not one")
    return float(basket[0]["shares"]), float(basket[0]["weight"])


def _bava_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    details = data["fundDetails"]
    avax, weight = _bava_avax(data)
    shares = _number(details["sharesOutstanding"])
    return {
        "issuer": "Bitwise", "fund": "Bitwise Avalanche ETF", "ticker": "BAVA", "endpoint_id": BAVA,
        "as_of": date.fromisoformat(data["holdings"]["asOfDate"]), "nav_usd": _number(data["navAndMarketPrice"]["nav"]),
        "net_assets_usd": _number(details["netAssets"]), "shares_outstanding": shares, "avax_held": avax,
        "avax_per_share": _ratio(avax, shares), "avax_weight": weight, "avax_held_derived": False,
        "staked_share": _number((details.get("stakingMetrics") or {}).get("currentPercentageOfAssetsStaked")),
    }


def _vavx_snapshot(nav: dict[str, Any], staking: dict[str, Any], prices: dict[str, Any]) -> dict[str, Any]:
    figures = {item["Key"]: item["Value"] for item in nav["data"]["Navs"]}
    staked = next((item["Value"] for item in staking["data"]["Values"] if item["Title"] == "Percentage Staked"), None)
    shares, avax = _number(figures["Shares Outstanding"]), _number(figures["AVAX in Trust"])
    return {
        "issuer": "VanEck", "fund": "VanEck Avalanche ETF", "ticker": "VAVX", "endpoint_id": VAVX_NAV,
        "as_of": _us_date(nav["data"]["AsOfDate"]), "nav_usd": _number(prices["data"]["PricesViewModel"]["NavCurrent"]),
        "net_assets_usd": _number(figures["Total Net Assets"]), "shares_outstanding": shares, "avax_held": avax,
        "avax_per_share": _number(figures["AVAX per 1,000 Shares"]) / 1000, "avax_weight": 1.0, "avax_held_derived": False,
        "staked_share": _number(staked) / 100 if staked is not None else None,
    }


def _ts_avax_line(data: dict[str, Any]) -> dict[str, Any]:
    lines = [item for item in data["constituents"] if item.get("ticker") == "AVAX"]
    if len(lines) != 1:
        raise DataError(f"21Shares {data.get('ticker')} lists {len(lines)} AVAX constituents, not one")
    return lines[0]


def _ts_snapshot(endpoint_id: str, value: dict[str, Any]) -> dict[str, Any]:
    data = value["data"]
    line = _ts_avax_line(data)
    units, per_unit = float(data["total_units_outstanding"]), float(line["coin_entitlement_per_share"])
    return {
        "issuer": "21Shares", "fund": data["product_name"], "ticker": data["ticker"], "endpoint_id": endpoint_id,
        "as_of": date.fromisoformat(data["valuation_date"]), "nav_usd": _number(data["nav_per_unit"]),
        "net_assets_usd": _number(data["total_nav"]), "shares_outstanding": units, "avax_held": per_unit * units,
        "avax_per_share": per_unit, "avax_weight": _number(line["weight"]), "avax_held_derived": True, "staked_share": None,
    }


def _sec_instants(facts: dict[str, Any]) -> dict[date, dict[str, Any]]:
    """GAVA's instant facts by period end, keeping the latest filing's value where a later filing restates one."""
    wanted = {"InvestmentOwnedBalanceContracts": "Avax", "SharesOutstanding": "shares", "NetAssetValuePerShare": "USD/shares",
              "AssetsNet": "USD", "InvestmentOwnedPercentOfNetAssets": "pure"}
    periods: dict[date, dict[str, Any]] = {}
    for concept, unit in wanted.items():
        rows = facts["facts"].get("us-gaap", {}).get(concept, {}).get("units", {}).get(unit, [])
        for row in sorted((row for row in rows if "start" not in row), key=lambda row: (row["filed"], row["accn"])):
            period = periods.setdefault(date.fromisoformat(row["end"]), {})
            period[concept] = float(row["val"])
            period["filed"] = max(period.get("filed", ""), row["filed"])
    return {end: period for end, period in periods.items() if "InvestmentOwnedBalanceContracts" in period}


def _sec_row(facts: dict[str, Any], end: date, period: dict[str, Any]) -> dict[str, Any]:
    shares, avax = period.get("SharesOutstanding"), period["InvestmentOwnedBalanceContracts"]
    return {
        "issuer": "Grayscale", "fund": facts.get("entityName", "Grayscale Avalanche Staking ETF"), "ticker": "GAVA", "endpoint_id": SEC_GAVA,
        "nav_usd": period.get("NetAssetValuePerShare"), "net_assets_usd": period.get("AssetsNet"), "shares_outstanding": shares,
        "avax_held": avax, "avax_per_share": _ratio(avax, shares), "avax_held_derived": False,
        "_as_of": end, "_weight": period.get("InvestmentOwnedPercentOfNetAssets"),
    }


def snapshot_rows(receipt: dict[str, Any], values: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [_bava_snapshot(values[BAVA]), _vavx_snapshot(values[VAVX_NAV], values[VAVX_STAKING], values[VAVX_PRICES])]
    rows += [_ts_snapshot(f"{TS_PREFIX}{ticker.lower()}-details", values[f"{TS_PREFIX}{ticker.lower()}-details"]) for ticker in TS_TICKERS]
    instants = _sec_instants(values[SEC_GAVA])
    if not instants:
        raise DataError("the GAVA SEC facts hold no quarter-end AVAX balance")
    end = max(instants)
    row = _sec_row(values[SEC_GAVA], end, instants[end])
    rows.append({**{key: value for key, value in row.items() if not key.startswith("_")}, "as_of": row["_as_of"], "avax_weight": row["_weight"], "staked_share": None})
    captured_at = _captured_at(receipt)
    return [{name: ({**row, "captured_at": captured_at}).get(name) for name in SNAPSHOT_COLUMNS} for row in rows]


def history_rows(receipt: dict[str, Any], values: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticker in TS_TICKERS:
        endpoint_id = f"{TS_PREFIX}{ticker.lower()}-history"
        for point in values[endpoint_id]["data"]:
            underlying = point.get("underlying") or {}
            price = _number(underlying.get("AVAX"))
            # A single-asset product's NAV is all AVAX, so its units are the NAV over the AVAX price. A basket's are not.
            avax = point["total_nav"] / price if set(underlying) == {"AVAX"} and price and point.get("total_nav") is not None else None
            units = _number(point.get("total_units_outstanding"))
            rows.append({"issuer": "21Shares", "fund": TS_FUNDS[ticker], "ticker": ticker, "endpoint_id": endpoint_id,
                         "valuation_date": date.fromisoformat(point["valuation_date"]), "nav_usd": _number(point.get("nav_per_share")),
                         "net_assets_usd": _number(point.get("total_nav")), "shares_outstanding": units, "avax_price_usd": price,
                         "avax_held": avax, "avax_per_share": _ratio(avax, units), "avax_held_derived": True if avax is not None else None})
    bava = values[BAVA]
    held_on = date.fromisoformat(bava["holdings"]["asOfDate"])
    current = _bava_snapshot(bava)
    for stamp, nav in bava["navAndMarketPrice"]["chart"]["nav"]:
        day = datetime.fromtimestamp(stamp / 1000, UTC).date()
        known = day == held_on
        rows.append({"issuer": "Bitwise", "fund": "Bitwise Avalanche ETF", "ticker": "BAVA", "endpoint_id": BAVA, "valuation_date": day,
                     "nav_usd": float(nav), "net_assets_usd": current["net_assets_usd"] if known else None,
                     "shares_outstanding": current["shares_outstanding"] if known else None, "avax_price_usd": None,
                     "avax_held": current["avax_held"] if known else None, "avax_per_share": current["avax_per_share"] if known else None,
                     "avax_held_derived": False if known else None})
    facts = values[SEC_GAVA]
    for end, period in sorted(_sec_instants(facts).items()):
        row = _sec_row(facts, end, period)
        rows.append({**{key: value for key, value in row.items() if not key.startswith("_")}, "valuation_date": end, "avax_price_usd": None})
    captured_at = _captured_at(receipt)
    return [{name: ({**row, "captured_at": captured_at}).get(name) for name in HISTORY_COLUMNS} for row in rows]


ROW_BUILDERS = {SNAPSHOT_ID: snapshot_rows, HISTORY_ID: history_rows}


def _load(connection: Any, dataset_id: str, rows: list[dict[str, Any]], table: str = "rows") -> None:
    columns = COLUMNS[dataset_id]
    connection.execute(f"CREATE TABLE {table}({', '.join(f'{name} {kind}' for name, kind in columns.items())})")
    if rows:
        connection.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' for _ in columns)})", [[row[name] for name in columns] for row in rows])


def summarize(connection: Any, dataset_id: str) -> dict[str, Any]:
    if dataset_id == SNAPSHOT_ID:
        funds = connection.execute(
            "SELECT ticker, issuer, as_of, avax_held, shares_outstanding, net_assets_usd, staked_share FROM rows ORDER BY avax_held DESC NULLS LAST"
        ).fetchall()
        return {
            "rows": len(funds),
            "avax_held_total": sum(item[3] or 0 for item in funds),
            "funds": [{"ticker": item[0], "issuer": item[1], "as_of": item[2].isoformat(), "avax_held": item[3], "shares_outstanding": item[4],
                       "net_assets_usd": item[5], "staked_share": item[6]} for item in funds],
        }
    funds = connection.execute(
        """SELECT ticker, COUNT(*), MIN(valuation_date), MAX(valuation_date), COUNT(avax_held), COALESCE(COUNT_IF(avax_held_derived), 0)
           FROM rows GROUP BY ticker ORDER BY ticker"""
    ).fetchall()
    return {
        "rows": sum(item[1] for item in funds),
        "funds": [{"ticker": item[0], "rows": item[1], "from": item[2].isoformat(), "to": item[3].isoformat(), "rows_with_avax_held": item[4],
                   "rows_with_avax_held_derived": item[5]} for item in funds],
    }


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    _check_dataset(dataset_id)
    load_catalog()
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{TABLES[dataset_id]}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    _check_dataset(dataset_id)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    receipt, values = read_capture(capture_dir, catalog)
    if receipt["dataset_id"] != dataset_id:
        raise DataError(f"capture belongs to {receipt['dataset_id']}, not {dataset_id}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet_path = temporary / f"{TABLES[dataset_id]}.parquet"
        connection = duckdb.connect()
        try:
            _load(connection, dataset_id, ROW_BUILDERS[dataset_id](receipt, values))
            order = "ticker" if dataset_id == SNAPSHOT_ID else "ticker, valuation_date"
            connection.execute(f"COPY (SELECT * FROM rows ORDER BY {order}) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection, dataset_id)
        finally:
            connection.close()
        build_receipt = {
            "schema_version": f"{SOURCE_ID}-build/v1",
            "dataset_id": dataset_id,
            "dataset_schema": definition["fields"],
            "source_capture_id": receipt["capture_id"],
            "completed_at": now(),
            "tool": f"avalanche-research@{__version__}",
            "summary": summary,
            "outputs": [{"path": parquet_path.name, "bytes": parquet_path.stat().st_size, "sha256": sha256(parquet_path.read_bytes())}],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return build_receipt


def _off(value: float | None, reference: float | None) -> bool:
    """True when two amounts differ by more than the tolerance, relative to the reference."""
    return value is not None and reference is not None and abs(value - reference) > TOLERANCE * abs(reference)


def nav_share_gaps(rows: list[dict[str, Any]]) -> list[str]:
    """Fund and date of each row whose NAV per share times shares is off its net assets by more than the tolerance."""
    return [
        f"{row['ticker']} {row.get('as_of') or row.get('valuation_date')}" for row in rows
        if row.get("nav_usd") and row.get("shares_outstanding") and _off(row["nav_usd"] * row["shares_outstanding"], row["net_assets_usd"])
    ]


def _findings(dataset_id: str, rows: list[dict[str, Any]], values: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    required = ("issuer", "fund", "ticker", "as_of", "net_assets_usd", "shares_outstanding", "avax_held") if dataset_id == SNAPSHOT_ID else ("issuer", "fund", "ticker", "valuation_date", "nav_usd")
    missing = [f"{row['ticker']} {name}" for row in rows for name in required if row.get(name) is None]
    if missing:
        findings.append(f"{len(missing)} required values are missing: {', '.join(missing[:5])}")
    negative = [row["ticker"] for row in rows if row.get("avax_held") is not None and row["avax_held"] < 0]
    if negative:
        findings.append(f"{len(negative)} rows hold negative AVAX: {', '.join(sorted(set(negative)))}")
    key = "ticker" if dataset_id == SNAPSHOT_ID else "valuation_date"
    seen = [(row["ticker"], row[key]) for row in rows]
    if len(seen) != len(set(seen)):
        findings.append(f"{len(seen) - len(set(seen))} rows repeat a fund{'' if dataset_id == SNAPSHOT_ID else ' and valuation date'}")
    units, _ = _bava_avax(values[BAVA])
    held_on = date.fromisoformat(values[BAVA]["holdings"]["asOfDate"])
    bava = [row for row in rows if row["ticker"] == "BAVA" and (dataset_id == SNAPSHOT_ID or row["valuation_date"] == held_on)]
    if len(bava) != 1 or bava[0]["avax_held"] != units:
        findings.append(f"BAVA AVAX held does not equal the basket's {units} units")
    if dataset_id == HISTORY_ID:
        # The derivation divides by the AVAX price, which for a single-asset product must be the product's index.
        for ticker in TS_TICKERS:
            for point in values[f"{TS_PREFIX}{ticker.lower()}-history"]["data"]:
                underlying = point.get("underlying") or {}
                if set(underlying) == {"AVAX"} and _off(_number(underlying["AVAX"]), _number(point.get("index"))):
                    findings.append(f"21Shares {ticker} {point['valuation_date']}: the AVAX price is off the index by more than 0.5%")
    if dataset_id == SNAPSHOT_ID:
        findings.extend(f"{label}: NAV times shares is off the net assets by more than 0.5%" for label in nav_share_gaps(rows))
        for ticker in TS_TICKERS:
            data = values[f"{TS_PREFIX}{ticker.lower()}-details"]["data"]
            line = _ts_avax_line(data)
            row = next(row for row in rows if row["ticker"] == data["ticker"])
            # The AVAX line's share of the NAV over the AVAX price: the whole NAV for the single-asset product.
            implied = data["total_nav"] * (1.0 if len(data["constituents"]) == 1 else float(line["weight"])) / float(line["price"])
            if _off(row["avax_held"], implied):
                findings.append(f"21Shares {ticker}: AVAX held {row['avax_held']:.3f} is off total NAV over the AVAX price ({implied:.3f}) by more than 0.5%")
        vavx = next(row for row in rows if row["ticker"] == "VAVX")
        if _off(vavx["avax_per_share"] * vavx["shares_outstanding"], vavx["avax_held"]):
            findings.append("VAVX AVAX per 1,000 shares times shares outstanding is off the AVAX in trust by more than 0.5%")
    return findings


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    if against is not None:
        raise DataError("the ETF datasets take no --against reference")
    catalog = load_catalog()
    receipt, values = read_capture(capture_dir, catalog)
    dataset_id = receipt["dataset_id"]
    checked = ["capture hashes", "required endpoints", "required fields", "non-negative AVAX held", "one row per fund and date", "BAVA basket units"]
    checked += (["NAV times shares against net assets", "21Shares AVAX held against total NAV over the AVAX price", "VAVX AVAX per share"]
                if dataset_id == SNAPSHOT_ID else ["21Shares AVAX price against the index"])
    rows = ROW_BUILDERS[dataset_id](receipt, values)
    findings = _findings(dataset_id, rows, values)
    connection = duckdb.connect()
    try:
        _load(connection, dataset_id, rows)
        summary = summarize(connection, dataset_id)
        if dataset_id == SNAPSHOT_ID:
            wallets = values[BAVA].get("wallets", {}).get("walletBalances", [])
            summary["bava_wallets"] = len(wallets)
            summary["bava_wallet_balance_total"] = sum(float(item.get("balance") or 0) for item in wallets)
        else:
            # Issuers' old records hold a few days whose units and NAV disagree; they are reported, not failed.
            summary["nav_times_shares_off_net_assets"] = nav_share_gaps(rows)
        if dataset_dir is not None:
            checked.extend(["build hashes", "Parquet rows"])
            try:
                build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
                for item in build_receipt["outputs"]:
                    body = (dataset_dir / item["path"]).read_bytes()
                    if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                        findings.append(f"output hash or size differs: {item['path']}")
                if build_receipt.get("source_capture_id") != receipt["capture_id"]:
                    findings.append("the build names a different capture")
                parquet = str(dataset_dir / f"{TABLES[dataset_id]}.parquet")
                columns = ", ".join(COLUMNS[dataset_id])
                differing = connection.execute(
                    f"""SELECT (SELECT COUNT(*) FROM (SELECT {columns} FROM rows EXCEPT ALL SELECT {columns} FROM read_parquet(?)))
                             + (SELECT COUNT(*) FROM (SELECT {columns} FROM read_parquet(?) EXCEPT ALL SELECT {columns} FROM rows))""",
                    [parquet, parquet],
                ).fetchone()[0]
                if differing:
                    findings.append("Parquet rows differ from the captured inputs")
            except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
                findings.append(f"invalid dataset output: {error}")
    finally:
        connection.close()
    return {
        "dataset_id": dataset_id,
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summary,
        "findings": findings,
    }
