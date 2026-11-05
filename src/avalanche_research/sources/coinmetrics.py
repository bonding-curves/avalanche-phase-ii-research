"""The daily Bitcoin price from Coin Metrics' community API, from its first observation in July 2010.

Coin Metrics publishes ``PriceUSD``, its reference rate for Bitcoin in US dollars, once per UTC day. The value dated d
is the price at 24:00 UTC of d, the end of that day, the same instant as an exchange's daily close. The keyless
community API serves the full history in pages of up to 10,000 rows; a capture follows each page's
``next_page_url`` and keeps every page's bytes. The build gives one row per UTC day with the daily log return.

The check reads a built ``binance.btc-usdt-daily`` run with ``--against``. On the days both cover from 1 September 2020,
the start of the AVAX record, at least 99% of prices must lie within 1% of Binance's BTC/USDT close and the daily log
returns must correlate at 0.99 or more. The level band alone would let a one-day shift pass in calm months; the return
correlation catches it. Before 2020 Binance's USDT market sat further from the dollar price: over every shared day from
2017-08-17 the share within 1% is about 95%. The check reports that full overlap beside the tested window.
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..core.catalog import DataError, canonical_bytes, load_catalog, source
from . import public_market
from .binance_btc import DATASET_ID as BINANCE_BTC_ID
from .binance_btc import end_day

DATASET_ID = "coinmetrics.btc-usd-daily"
SOURCE_ID = "coinmetrics-community"
ENDPOINT_ID = "btc-priceusd-daily"
TABLE = "btc-usd-daily"
SCHEMA = "coinmetrics-community-capture/v1"
BUILD_SCHEMA = "coinmetrics-community-build/v1"
SERIES_START = date(2010, 7, 18)
PAGE_PREFIX = "https://community-api.coinmetrics.io/v4/"
MAX_PAGES = 20
PAUSE_SECONDS = 1.0
LEVEL_TOLERANCE = 0.01
LEVEL_SHARE = 0.99
RETURN_CORRELATION = 0.99
CROSS_CHECK_START = date(2020, 9, 1)
COLUMNS = {
    "observation_date": "DATE",
    "price_usd": "DOUBLE",
    "log_return": "DOUBLE",
}


def _url(end: date, catalog: dict[str, Any] | None = None) -> str:
    endpoint = next(item for item in source(catalog or load_catalog(), SOURCE_ID)["endpoints"] if item["id"] == ENDPOINT_ID)
    return f"{endpoint['url']}&end_time={end - timedelta(days=1):%Y-%m-%d}"


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    end = end_day(parameters, SERIES_START)
    return {"dataset_id": DATASET_ID, "source_id": SOURCE_ID, "output": str(output), "end": end.isoformat(),
            "first_request": _url(end), "writes": ["raw/page-*.json", "capture.json"], "overwrite": False}


def _polite(url: str, timeout: float) -> bytes:
    return public_market.download(url, timeout, pause=PAUSE_SECONDS)


def capture(dataset_id: str, output: Path, timeout: float = 30, parameters: dict[str, str] | None = None,
            download: public_market.Download = _polite) -> dict[str, Any]:
    preview = capture_preview(dataset_id, output, parameters)
    with public_market.new_folder(output) as folder:
        records, url = [], preview["first_request"]
        while url:
            if len(records) == MAX_PAGES:
                raise DataError(f"more than {MAX_PAGES} pages; the series is longer than expected")
            if not url.startswith(PAGE_PREFIX):
                raise DataError(f"next page is outside the community API: {url}")
            body = download(url, timeout)
            try:
                page = json.loads(body)
            except json.JSONDecodeError as error:
                raise DataError(f"page {len(records)} is not JSON: {error}") from error
            if "data" not in page:
                raise DataError(f"page {len(records)} holds no data: {body[:200]!r}")
            records.append(public_market.record(folder, f"raw/page-{len(records):02d}.json", body, endpoint_id=ENDPOINT_ID, url=url))
            url = page.get("next_page_url")
        value = public_market.receipt(SCHEMA, DATASET_ID, SOURCE_ID, records, end=preview["end"])
        (folder / "capture.json").write_bytes(canonical_bytes(value))
    return value


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    value = public_market.read_receipt(capture_dir, SCHEMA, DATASET_ID)
    end = date.fromisoformat(value["end"])
    if not value["files"] or value["files"][0]["url"] != _url(end):
        raise DataError("the first captured page is not the request the catalog declares for this window")
    prices: dict[date, float] = {}
    for item in value["files"]:
        for point in json.loads((capture_dir / item["path"]).read_bytes())["data"]:
            stamp = point.get("time", "")
            if point.get("asset") != "btc" or not stamp.endswith("T00:00:00.000000000Z"):
                raise DataError(f"unexpected point: {point}")
            day = date.fromisoformat(stamp[:10])
            if day in prices:
                raise DataError(f"two prices for {day}")
            price = float(point["PriceUSD"])
            if not price > 0:
                raise DataError(f"non-positive price on {day}")
            prices[day] = price
    if not prices:
        raise DataError("the capture holds no prices")
    first = min(prices)
    expected = [first + timedelta(days=offset) for offset in range((end - first).days)]
    if sorted(prices) != expected:
        missing = sorted(set(expected) - set(prices))
        raise DataError(f"the prices do not cover every day from {first} to {end}: {len(missing)} missing, first {missing[:3]}")
    rows: list[tuple[Any, ...]] = []
    for day in expected:
        previous = rows[-1][1] if rows else None
        rows.append((day, prices[day], math.log(prices[day] / previous) if previous else None))
    return value, rows


def _summary(rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    return {"rows": len(rows), "first_day": rows[0][0].isoformat(), "last_day": rows[-1][0].isoformat()}


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output),
            "writes": [f"{TABLE}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    build_preview(dataset_id, capture_dir, output)
    value, rows = read_rows(capture_dir)
    return public_market.build_table(DATASET_ID, TABLE, COLUMNS, "observation_date", value, rows, _summary(rows), output,
                                     BUILD_SCHEMA)


def _agreement(shared: list[tuple[tuple[Any, ...], tuple[float, float | None]]]) -> dict[str, Any]:
    gaps = [abs(row[1] / close - 1) for row, (close, _) in shared]
    returns = [(row[2], other) for row, (_, other) in shared if row[2] is not None and other is not None]
    correlation = public_market.correlation(returns)
    worst = max(range(len(shared)), key=lambda index: gaps[index])
    return {"days": len(shared), "first_day": shared[0][0][0].isoformat(), "last_day": shared[-1][0][0].isoformat(),
            "share_within_1pct": round(sum(gap <= LEVEL_TOLERANCE for gap in gaps) / len(gaps), 6),
            "median_level_difference": round(sorted(gaps)[len(gaps) // 2], 6), "max_level_difference": round(gaps[worst], 6),
            "max_level_difference_day": shared[worst][0][0].isoformat(), "return_days": len(returns),
            "return_correlation": None if correlation is None else round(correlation, 6)}


def cross_check(rows: list[tuple[Any, ...]], reference_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Each day's price against Binance's BTC/USDT close of the same UTC day, in level and in daily log return, tested
    from 1 September 2020 and reported over the full overlap."""
    reference = {day: (close, log_return) for day, close, log_return in public_market.reference_rows(
        reference_dir, BINANCE_BTC_ID, "SELECT observation_date, close_usdt, log_return FROM {parquet}")}
    shared = [(row, reference[row[0]]) for row in rows if row[0] in reference]
    tested = [(row, other) for row, other in shared if row[0] >= CROSS_CHECK_START]
    if not tested:
        return {"cross_check_days": 0}, [f"no overlapping days with the Binance BTC/USDT reference from {CROSS_CHECK_START}"]
    measured = _agreement(tested)
    summary = {f"cross_check_{key}": value for key, value in measured.items()}
    summary.update({f"full_overlap_{key}": value for key, value in _agreement(shared).items()})
    findings = []
    if measured["share_within_1pct"] < LEVEL_SHARE:
        findings.append(f"{measured['share_within_1pct']:.2%} of {measured['days']} days from {CROSS_CHECK_START} lie within "
                        f"{LEVEL_TOLERANCE:.0%} of Binance's BTC/USDT close; at least {LEVEL_SHARE:.0%} must")
    correlation = measured["return_correlation"]
    if correlation is None or correlation < RETURN_CORRELATION:
        findings.append(f"the daily log returns from {CROSS_CHECK_START} correlate at {correlation} with Binance's; "
                        f"at least {RETURN_CORRELATION} is required")
    return summary, findings


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    """With ``--against`` a built binance.btc-usdt-daily run: the level and return agreement with Binance's close."""
    value, rows = read_rows(capture_dir)
    checked = ["page hashes", "one price for every day", "log returns"]
    findings: list[str] = []
    summary = _summary(rows)
    if against is not None:
        checked.append("Binance BTC/USDT close from 2020-09-01: 99% of days within 1%, return correlation at least 0.99")
        extra, found = cross_check(rows, against)
        summary.update(extra)
        findings.extend(found)
    if dataset_dir is not None:
        checked.extend(["build hashes", "Parquet rows"])
        findings.extend(public_market.built_findings(dataset_dir, TABLE, "observation_date", value, rows))
    return {"dataset_id": DATASET_ID, "capture_id": value["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}
