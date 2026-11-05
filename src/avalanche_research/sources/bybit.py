"""The AVAX perpetual funding rate on Bybit, the second venue beside Binance, since the contract launched on 2021-09-15.

Bybit's public API, ``/v5/market/funding/history``, returns at most 200 rates per call, newest first, up to an
``endTime``. A capture walks back from the window's end, each call ending one millisecond before the oldest rate of the
last, until it reaches the contract's launch time, which it reads with the funding interval from the instrument
record. The table has the same columns and units as ``binance.avax-usdt-perp-funding``: one row per event with the
rate per 8 hours and the same rate in percent of position value a year, and each row's UTC day figures.

The check reads a built ``binance.avax-usdt-perp-funding`` run with ``--against``. Bybit's 30-day mean must lie within
5 percentage points a year of Binance's on at least 80% of the days both venues have one.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from ..core.catalog import DataError, canonical_bytes, load_catalog, source
from . import public_market
from .binance_btc import end_day
from .binance_funding import DATASET_ID as BINANCE_FUNDING_ID
from .binance_funding import FUNDING_COLUMNS, INTERVAL_HOURS, funding_rows, funding_summary, instant, millis

DATASET_ID = "bybit.avax-usdt-perp-funding"
SOURCE_ID = "bybit-public-api"
HISTORY_ID = "avax-usdt-funding-history"
INSTRUMENT_ID = "avax-usdt-instrument"
TABLE = "bybit-avax-usdt-perp-funding"
SCHEMA = "bybit-avax-usdt-perp-funding-capture/v1"
BUILD_SCHEMA = "bybit-avax-usdt-perp-funding-build/v1"
SYMBOL = "AVAXUSDT"
FIRST_DAY = date(2021, 9, 15)
PAGE_LIMIT = 200
MAX_PAGES = 100
PAUSE_SECONDS = 0.6
BAND_POINTS = 5.0
BAND_SHARE = 0.80
COLUMNS = dict(FUNDING_COLUMNS)


def _endpoints(catalog: dict[str, Any] | None = None) -> dict[str, str]:
    return {item["id"]: item["url"] for item in source(catalog or load_catalog(), SOURCE_ID)["endpoints"]}


def history_url(before: int, catalog: dict[str, Any] | None = None) -> str:
    return f"{_endpoints(catalog)[HISTORY_ID]}&endTime={before}"


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    end = end_day(parameters, FIRST_DAY)
    return {"dataset_id": DATASET_ID, "source_id": SOURCE_ID, "output": str(output), "end": end.isoformat(),
            "instrument_request": _endpoints()[INSTRUMENT_ID], "first_request": history_url(millis(end) - 1),
            "writes": ["raw/instrument.json", "raw/history/page-*.json", "capture.json"], "overwrite": False}


def _polite(url: str, timeout: float) -> bytes:
    return public_market.download(url, timeout, pause=PAUSE_SECONDS)


def _result(body: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(body)
    except json.JSONDecodeError as error:
        raise DataError(f"{label} is not JSON: {error}") from error
    if not isinstance(value, dict) or value.get("retCode") != 0 or not isinstance(value.get("result"), dict):
        raise DataError(f"{label} is not a successful answer: {body[:200]!r}")
    return value["result"]


def _instrument(body: bytes) -> dict[str, Any]:
    listed = _result(body, "the instrument record").get("list", [])
    if len(listed) != 1 or listed[0].get("symbol") != SYMBOL:
        raise DataError(f"the instrument record does not describe {SYMBOL}")
    return listed[0]


def capture(dataset_id: str, output: Path, timeout: float = 30, parameters: dict[str, str] | None = None,
            download: public_market.Download = _polite) -> dict[str, Any]:
    preview = capture_preview(dataset_id, output, parameters)
    with public_market.new_folder(output) as folder:
        body = download(preview["instrument_request"], timeout)
        launch = int(_instrument(body)["launchTime"])
        records = [public_market.record(folder, "raw/instrument.json", body, endpoint_id=INSTRUMENT_ID, url=preview["instrument_request"])]
        before = millis(date.fromisoformat(preview["end"])) - 1
        for page_number in range(MAX_PAGES + 1):
            if page_number == MAX_PAGES:
                raise DataError(f"more than {MAX_PAGES} history pages")
            url = history_url(before)
            body = download(url, timeout)
            page = _result(body, f"history page {page_number}").get("list", [])
            if not page:
                break
            records.append(public_market.record(folder, f"raw/history/page-{page_number:03d}.json", body, endpoint_id=HISTORY_ID, url=url))
            oldest = min(int(row["fundingRateTimestamp"]) for row in page)
            if oldest <= launch or len(page) < PAGE_LIMIT:
                break
            before = oldest - 1
        value = public_market.receipt(SCHEMA, DATASET_ID, SOURCE_ID, records, end=preview["end"])
        (folder / "capture.json").write_bytes(canonical_bytes(value))
    return value


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]], dict[str, Any]]:
    value = public_market.read_receipt(capture_dir, SCHEMA, DATASET_ID)
    end = date.fromisoformat(value["end"])
    instruments = [item for item in value["files"] if item.get("endpoint_id") == INSTRUMENT_ID]
    pages = [item for item in value["files"] if item.get("endpoint_id") == HISTORY_ID]
    if len(instruments) != 1 or not pages or pages[0]["url"] != history_url(millis(end) - 1):
        raise DataError("the capture does not start with the instrument record and the history request the catalog declares")
    instrument = _instrument((capture_dir / instruments[0]["path"]).read_bytes())
    if int(instrument.get("fundingInterval", 0)) != INTERVAL_HOURS * 60:
        raise DataError(f"the instrument's funding interval is {instrument.get('fundingInterval')} minutes, not {INTERVAL_HOURS * 60}")
    launch = int(instrument["launchTime"])
    events: dict[int, float] = {}
    for item in pages:
        for row in _result((capture_dir / item["path"]).read_bytes(), item["path"]).get("list", []):
            if row.get("symbol") != SYMBOL:
                raise DataError(f"unexpected history row: {row}")
            stamp, rate = int(row["fundingRateTimestamp"]), float(row["fundingRate"])
            if not launch <= stamp < millis(end):
                raise DataError(f"rate at {instant(stamp)} lies outside the contract's life in this window")
            if events.get(stamp, rate) != rate:
                raise DataError(f"two rates at {instant(stamp)}")
            events[stamp] = rate
    rows = funding_rows(events)
    return value, rows, {"launch_time": instant(launch).isoformat(), "history_pages": len(pages)}


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output),
            "writes": [f"{TABLE}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    build_preview(dataset_id, capture_dir, output)
    value, rows, extra = read_rows(capture_dir)
    return public_market.build_table(DATASET_ID, TABLE, COLUMNS, "funding_time", value, rows,
                                     {**funding_summary(rows), **extra}, output, BUILD_SCHEMA)


def cross_check(rows: list[tuple[Any, ...]], reference_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Bybit's 30-day mean against Binance's on each UTC day both have one, in percentage points a year."""
    reference = {day: (daily, mean) for day, daily, mean in public_market.reference_rows(
        reference_dir, BINANCE_FUNDING_ID,
        "SELECT DISTINCT observation_date, day_annualised_pct_per_year, mean_30d_annualised_pct_per_year FROM {parquet}")}
    own = {row[1]: (row[5], row[6]) for row in rows}
    days = sorted(day for day in own if day in reference and own[day][1] is not None and reference[day][1] is not None)
    if not days:
        return {"cross_check_days": 0}, ["no day on which both venues have a 30-day mean"]
    gaps = [abs(own[day][1] - reference[day][1]) for day in days]
    ordered = sorted(gaps)
    within = sum(gap <= BAND_POINTS for gap in gaps) / len(gaps)
    shared = [day for day in own if day in reference]
    worst = max(range(len(days)), key=lambda index: gaps[index])
    correlation = public_market.correlation([(own[day][1], reference[day][1]) for day in days])
    summary = {
        "cross_check_days": len(days), "cross_check_first_day": days[0].isoformat(), "cross_check_last_day": days[-1].isoformat(),
        "cross_check_share_within_5_points": round(within, 6),
        "cross_check_median_gap_points": round(ordered[len(ordered) // 2], 4),
        "cross_check_p95_gap_points": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 4),
        "cross_check_max_gap_points": round(gaps[worst], 4), "cross_check_max_gap_day": days[worst].isoformat(),
        "cross_check_30d_mean_correlation": None if correlation is None else round(correlation, 4),
        "cross_check_mean_annualised_pct_per_year_bybit": round(sum(own[day][0] for day in shared) / len(shared), 4),
        "cross_check_mean_annualised_pct_per_year_binance": round(sum(reference[day][0] for day in shared) / len(shared), 4),
    }
    findings = []
    if within < BAND_SHARE:
        findings.append(f"Bybit's 30-day mean lies within {BAND_POINTS:g} points a year of Binance's on {within:.2%} of "
                        f"{len(days)} days; at least {BAND_SHARE:.0%} is required")
    return summary, findings


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    """With ``--against`` a built binance.avax-usdt-perp-funding run: the 30-day means within 5 points a year on 80% of days."""
    value, rows, extra = read_rows(capture_dir)
    checked = ["page hashes", "instrument funding interval of 8 hours", "8 hours between consecutive events",
               "daily and 30-day figures"]
    findings: list[str] = []
    summary = {**funding_summary(rows), **extra}
    if against is not None:
        checked.append("Binance 30-day mean: within 5 points a year on at least 80% of days")
        more, found = cross_check(rows, against)
        summary.update(more)
        findings.extend(found)
    if dataset_dir is not None:
        checked.extend(["build hashes", "Parquet rows"])
        findings.extend(public_market.built_findings(dataset_dir, TABLE, "funding_time", value, rows))
    return {"dataset_id": DATASET_ID, "capture_id": value["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}
