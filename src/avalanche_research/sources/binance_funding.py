"""The AVAX perpetual funding rate on Binance, every funding event since the AVAXUSDT contract listed on 2020-09-22.

Binance's USDⓈ-M futures API, ``/fapi/v1/fundingRate``, serves the full history of AVAXUSDT funding rates, 1,000 a
call, to the latest event. Binance's public data archive also publishes the rates once a month, one zip file per
closed month beside a CHECKSUM file carrying its SHA-256. A capture takes both: the API rows to the window's end, and
every monthly file with its CHECKSUM, refused when the hash differs. The monthly files are the record each API rate
must equal. A build refuses a capture in which any archived rate is missing from the API or differs from it, in which
the API holds a rate the archive's months omit, or in which two consecutive events are not 8 hours apart. The newest
closed month may not be published yet in the first days of a month; its rates are then kept unconfirmed and marked so.

A funding rate is the fraction of position value that longs pay shorts at each event, every 8 hours; a negative rate
is paid by shorts to longs. The table gives one row per event with the rate per 8 hours and the same rate in percent
of position value a year. Each row also carries its UTC day's figures: the number of events, the day's mean rate in
percent a year (the day's summed rates times 365 when the day holds all three events), and the mean of the 30 daily
figures ending that day.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from ..core.catalog import DataError, canonical_bytes, load_catalog, sha256, source
from . import public_market
from .binance import _published
from .binance_btc import end_day

DATASET_ID = "binance.avax-usdt-perp-funding"
SOURCE_ID = "binance-market-data"
API_ID = "avax-usdt-funding-rate-api"
MONTHLY_ID = "avax-usdt-funding-rate-monthly"
TABLE = "avax-usdt-perp-funding"
SCHEMA = "binance-avax-usdt-perp-funding-capture/v1"
BUILD_SCHEMA = "binance-avax-usdt-perp-funding-build/v1"
SYMBOL = "AVAXUSDT"
FIRST_DAY = date(2020, 9, 22)
API_LIMIT = 1000
MAX_PAGES = 50
API_PAUSE_SECONDS = 1.0
ARCHIVE_PAUSE_SECONDS = 0.3
ARCHIVE_HEADER = ["calc_time", "funding_interval_hours", "last_funding_rate"]
INTERVAL_HOURS = 8
EVENTS_PER_DAY = 24 // INTERVAL_HOURS
DAYS_PER_YEAR = 365
MEAN_WINDOW_DAYS = 30
FUNDING_COLUMNS = {
    "funding_time": "TIMESTAMP",
    "observation_date": "DATE",
    "funding_rate_per_8h": "DOUBLE",
    "annualised_pct_per_year": "DOUBLE",
    "day_events": "INTEGER",
    "day_annualised_pct_per_year": "DOUBLE",
    "mean_30d_annualised_pct_per_year": "DOUBLE",
}
COLUMNS = {**FUNDING_COLUMNS, "in_archive": "BOOLEAN"}


def millis(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)


def instant(stamp: int) -> datetime:
    """A naive UTC datetime at millisecond precision, as DuckDB stores a TIMESTAMP."""
    return datetime(1970, 1, 1) + timedelta(milliseconds=stamp)


def funding_rows(events: dict[int, float]) -> list[tuple[Any, ...]]:
    """One row per event, oldest first, with the event's and its UTC day's annualised rates.

    Refused unless every pair of consecutive events is 8 hours apart, to the nearest minute, so the rate is always a
    rate per 8 hours and every UTC day between the first and the last holds events."""
    stamps = sorted(events)
    if not stamps:
        raise DataError("no funding events")
    irregular = [(instant(a), round((b - a) / 60_000)) for a, b in zip(stamps, stamps[1:]) if round((b - a) / 60_000) != INTERVAL_HOURS * 60]
    if irregular:
        raise DataError(f"{len(irregular)} intervals are not {INTERVAL_HOURS} hours, first after {irregular[0][0]}: {irregular[0][1]} minutes")
    by_day: dict[date, list[float]] = {}
    for stamp in stamps:
        by_day.setdefault(instant(stamp).date(), []).append(events[stamp])
    days = sorted(by_day)
    daily = [sum(by_day[day]) / len(by_day[day]) * EVENTS_PER_DAY * DAYS_PER_YEAR * 100 for day in days]
    figures = {}
    for index, day in enumerate(days):
        window = daily[index + 1 - MEAN_WINDOW_DAYS:index + 1] if index + 1 >= MEAN_WINDOW_DAYS else None
        figures[day] = (len(by_day[day]), daily[index], sum(window) / MEAN_WINDOW_DAYS if window else None)
    rows = []
    for stamp in stamps:
        moment = instant(stamp)
        rate = events[stamp]
        rows.append((moment, moment.date(), rate, rate * EVENTS_PER_DAY * DAYS_PER_YEAR * 100, *figures[moment.date()]))
    return rows


def funding_summary(rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    days = {row[1]: row for row in rows}
    return {"rows": len(rows), "first_event": rows[0][0].isoformat(), "last_event": rows[-1][0].isoformat(),
            "first_day": rows[0][1].isoformat(), "last_day": rows[-1][1].isoformat(), "days": len(days),
            "mean_annualised_pct_per_year": round(sum(row[5] for row in days.values()) / len(days), 4)}


def next_month(month: date) -> date:
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)


def months(end: date) -> list[date]:
    """The first day of every month from the listing month to the last month closed before end's month."""
    listed, month = [], date(FIRST_DAY.year, FIRST_DAY.month, 1)
    while month < date(end.year, end.month, 1):
        listed.append(month)
        month = next_month(month)
    return listed


def _endpoints(catalog: dict[str, Any] | None = None) -> dict[str, str]:
    return {item["id"]: item["url"] for item in source(catalog or load_catalog(), SOURCE_ID)["endpoints"]}


def archive_files(end: date, catalog: dict[str, Any] | None = None) -> list[dict[str, str]]:
    base = _endpoints(catalog)[MONTHLY_ID]
    return [{"endpoint_id": MONTHLY_ID, "name": f"{SYMBOL}-fundingRate-{month:%Y-%m}.zip",
             "url": f"{base}{SYMBOL}-fundingRate-{month:%Y-%m}.zip"} for month in months(end)]


def api_url(start: int, end: date, catalog: dict[str, Any] | None = None) -> str:
    return f"{_endpoints(catalog)[API_ID]}&startTime={start}&endTime={millis(end) - 1}"


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    end = end_day(parameters, FIRST_DAY)
    return {"dataset_id": DATASET_ID, "source_id": SOURCE_ID, "output": str(output), "first_day": FIRST_DAY.isoformat(),
            "end": end.isoformat(), "first_request": api_url(millis(FIRST_DAY), end), "archive_files": len(archive_files(end)),
            "writes": ["raw/api/page-*.json", "raw/archive/*.zip", "raw/archive/*.zip.CHECKSUM", "capture.json"], "overwrite": False}


def _api_download(url: str, timeout: float) -> bytes:
    return public_market.download(url, timeout, pause=API_PAUSE_SECONDS)


def _archive_download(url: str, timeout: float) -> bytes:
    return public_market.download(url, timeout, pause=ARCHIVE_PAUSE_SECONDS)


def capture(dataset_id: str, output: Path, timeout: float = 30, parameters: dict[str, str] | None = None,
            download: public_market.Download | None = None) -> dict[str, Any]:
    preview = capture_preview(dataset_id, output, parameters)
    end = date.fromisoformat(preview["end"])
    get_api = download or _api_download
    get_archive = download or _archive_download
    with public_market.new_folder(output) as folder:
        records: list[dict[str, Any]] = []
        start = millis(FIRST_DAY)
        for page_number in range(MAX_PAGES + 1):
            if page_number == MAX_PAGES:
                raise DataError(f"more than {MAX_PAGES} API pages")
            url = api_url(start, end)
            body = get_api(url, timeout)
            try:
                page = json.loads(body)
            except json.JSONDecodeError as error:
                raise DataError(f"API page {page_number} is not JSON: {error}") from error
            if not isinstance(page, list):
                raise DataError(f"API page {page_number} is not a list of rates: {body[:200]!r}")
            records.append(public_market.record(folder, f"raw/api/page-{page_number:02d}.json", body, endpoint_id=API_ID, url=url))
            if len(page) < API_LIMIT:
                break
            start = int(page[-1]["fundingTime"]) + 1
        listed = archive_files(end)
        unpublished = []
        for position, item in enumerate(listed):
            try:
                body = get_archive(item["url"], timeout)
            except public_market.NotPublished:
                if position != len(listed) - 1:
                    raise
                unpublished.append(item["name"])
                continue
            checksum = get_archive(item["url"] + ".CHECKSUM", timeout)
            if sha256(body) != _published(checksum, item["name"]):
                raise DataError(f"{item['name']} does not match its published SHA-256")
            records.append(public_market.record(folder, f"raw/archive/{item['name']}", body, **item))
            records.append(public_market.record(folder, f"raw/archive/{item['name']}.CHECKSUM", checksum, checksum_of=item["name"]))
        value = public_market.receipt(SCHEMA, DATASET_ID, SOURCE_ID, records, first_day=preview["first_day"], end=preview["end"],
                                      unpublished_archive_files=unpublished)
        (folder / "capture.json").write_bytes(canonical_bytes(value))
    return value


def _archive_time(value: str) -> int:
    """Milliseconds, also when a file writes microseconds as the spot archive does from 2025."""
    stamp = int(value)
    return stamp // 1000 if stamp > 10**14 else stamp


def read_events(capture_dir: Path) -> tuple[dict[str, Any], dict[int, float], dict[int, float], dict[str, Any]]:
    """The receipt, the API rates and the archived rates by event time in milliseconds, and the comparison of the two."""
    value = public_market.read_receipt(capture_dir, SCHEMA, DATASET_ID)
    end = date.fromisoformat(value["end"])
    pages = [item for item in value["files"] if item.get("endpoint_id") == API_ID]
    if not pages or pages[0]["url"] != api_url(millis(FIRST_DAY), end):
        raise DataError("the first API page is not the request the catalog declares for this window")
    api: dict[int, float] = {}
    for item in pages:
        for row in json.loads((capture_dir / item["path"]).read_bytes()):
            if row.get("symbol") != SYMBOL:
                raise DataError(f"unexpected API row: {row}")
            stamp, rate = int(row["fundingTime"]), float(row["fundingRate"])
            if not millis(FIRST_DAY) <= stamp < millis(end):
                raise DataError(f"API rate at {instant(stamp)} lies outside the window")
            if api.get(stamp, rate) != rate:
                raise DataError(f"two API rates at {instant(stamp)}")
            api[stamp] = rate
    listed = archive_files(end)
    unpublished = value.get("unpublished_archive_files", [])
    if unpublished not in ([], [listed[-1]["name"]] if listed else []):
        raise DataError(f"only the newest monthly file may be unpublished, not {unpublished}")
    archives = [item for item in value["files"] if item.get("endpoint_id") == MONTHLY_ID]
    expected = [item for item in listed if item["name"] not in unpublished]
    if [(item["name"], item["url"]) for item in archives] != [(item["name"], item["url"]) for item in expected]:
        raise DataError("the captured monthly files are not the ones the archive lists for this window")
    archived: dict[int, float] = {}
    for item in archives:
        checksum = (capture_dir / f"{item['path']}.CHECKSUM").read_bytes()
        if _published(checksum, item["name"]) != item["sha256"]:
            raise DataError(f"{item['name']} differs from its published SHA-256")
        with zipfile.ZipFile(io.BytesIO((capture_dir / item["path"]).read_bytes())) as archive:
            names = archive.namelist()
            if len(names) != 1:
                raise DataError(f"{item['name']} holds {len(names)} files, expected one")
            lines = list(csv.reader(io.StringIO(archive.read(names[0]).decode("utf-8"))))
        if not lines or lines[0] != ARCHIVE_HEADER:
            raise DataError(f"{item['name']} does not start with the header {','.join(ARCHIVE_HEADER)}")
        for fields in lines[1:]:
            if not fields:
                continue
            stamp = _archive_time(fields[0])
            if int(fields[1]) != INTERVAL_HOURS:
                raise DataError(f"{item['name']} gives a {fields[1]}-hour interval at {instant(stamp)}")
            if stamp in archived:
                raise DataError(f"two archived rates at {instant(stamp)}")
            archived[stamp] = float(fields[2])
    last_month = date.fromisoformat(f"{archives[-1]['name'][-11:-4]}-01") if archives else None
    covered_to = millis(next_month(last_month)) if last_month else 0
    missing = sorted(stamp for stamp in archived if stamp not in api)
    differ = sorted(stamp for stamp in archived if stamp in api and api[stamp] != archived[stamp])
    omitted = sorted(stamp for stamp in api if stamp < covered_to and stamp not in archived)
    if missing:
        raise DataError(f"{len(missing)} archived rates are missing from the API, first at {instant(missing[0])}")
    if differ:
        raise DataError(f"{len(differ)} API rates differ from the archive, first at {instant(differ[0])}")
    if omitted:
        raise DataError(f"{len(omitted)} API rates fall in archived months the archive omits, first at {instant(omitted[0])}")
    comparison = {"archive_files": len(archives), "archive_rows": len(archived), "archive_rows_equal_to_api": len(archived),
                  "api_rows": len(api), "api_rows_after_archive": sum(stamp >= covered_to for stamp in api),
                  "archive_last_month": f"{last_month:%Y-%m}" if last_month else None,
                  "unpublished_archive_files": unpublished}
    return value, api, archived, comparison


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]], dict[str, Any]]:
    value, api, archived, comparison = read_events(capture_dir)
    rows = [(*row, millis_of(row[0]) in archived) for row in funding_rows(api)]
    return value, rows, comparison


def millis_of(moment: datetime) -> int:
    return round((moment - datetime(1970, 1, 1)).total_seconds() * 1000)


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output),
            "writes": [f"{TABLE}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    build_preview(dataset_id, capture_dir, output)
    value, rows, comparison = read_rows(capture_dir)
    return public_market.build_table(DATASET_ID, TABLE, COLUMNS, "funding_time", value, rows,
                                     {**funding_summary(rows), **comparison}, output, BUILD_SCHEMA)


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    """Archive integrity, every archived rate equal to the API's, 8-hour spacing, and the built rows."""
    if against is not None:
        raise DataError(f"{DATASET_ID} takes no --against reference; check Bybit against it instead")
    value, rows, comparison = read_rows(capture_dir)
    checked = ["published SHA-256 of every monthly file", "every archived rate equal to the API rate at the same instant",
               "no API rate missing from an archived month", "8 hours between consecutive events", "daily and 30-day figures"]
    findings: list[str] = []
    if dataset_dir is not None:
        checked.extend(["build hashes", "Parquet rows"])
        findings.extend(public_market.built_findings(dataset_dir, TABLE, "funding_time", value, rows))
    return {"dataset_id": DATASET_ID, "capture_id": value["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": {**funding_summary(rows), **comparison}, "findings": findings}
