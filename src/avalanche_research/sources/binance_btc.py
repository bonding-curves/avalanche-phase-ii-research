"""Bitcoin daily candles from Binance's public data archive, the reference the Coin Metrics Bitcoin price is checked against.

The archive at data.binance.vision publishes every day's BTC/USDT candle since 2017-08-17, one zip file per closed month
and one per day of the open month, each beside a CHECKSUM file carrying its SHA-256. A capture downloads the files,
refuses any whose hash differs from the published one, and keeps both. A day's close is the last trade before 24:00
UTC, the instant Coin Metrics values its daily price. The quote currency is USDT, not USD.
"""

from __future__ import annotations

import csv
import io
import math
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from ..core.catalog import DataError, canonical_bytes, load_catalog, sha256, source
from . import public_market
from .binance import _candle_time, _published

DATASET_ID = "binance.btc-usdt-daily"
SOURCE_ID = "binance-market-data"
MONTHLY_ID = "btc-usdt-1d-monthly"
DAILY_ID = "btc-usdt-1d-daily"
TABLE = "btc-usdt-daily"
SCHEMA = "binance-btc-usdt-daily-capture/v1"
BUILD_SCHEMA = "binance-btc-usdt-daily-build/v1"
FIRST_DAY = date(2017, 8, 17)
COLUMNS = {
    "observation_date": "DATE",
    "open_usdt": "DOUBLE",
    "high_usdt": "DOUBLE",
    "low_usdt": "DOUBLE",
    "close_usdt": "DOUBLE",
    "volume_btc": "DOUBLE",
    "quote_volume_usdt": "DOUBLE",
    "trades": "BIGINT",
    "log_return": "DOUBLE",
}


def end_day(parameters: dict[str, str] | None, first_day: date) -> date:
    """The ``end`` parameter: the first UTC day not captured, today by default."""
    values = parameters or {}
    if set(values) - {"end"}:
        raise DataError("the only parameter is end=<YYYY-MM-DD>, the first day not captured")
    try:
        end = date.fromisoformat(values["end"]) if "end" in values else datetime.now(UTC).date()
    except ValueError as error:
        raise DataError("end must be a date, YYYY-MM-DD") from error
    if end <= first_day:
        raise DataError(f"end must be after {first_day}, the first day of the series")
    return end


def files(end: date, catalog: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """One monthly file for every month closed before end's month, then one daily file for each earlier day of that month."""
    bases = {item["id"]: item["url"] for item in source(catalog or load_catalog(), SOURCE_ID)["endpoints"]}
    listed, month = [], date(FIRST_DAY.year, FIRST_DAY.month, 1)
    while month < date(end.year, end.month, 1):
        name = f"BTCUSDT-1d-{month:%Y-%m}.zip"
        listed.append({"endpoint_id": MONTHLY_ID, "name": name, "url": bases[MONTHLY_ID] + name})
        month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    day = max(month, FIRST_DAY)
    while day < end:
        name = f"BTCUSDT-1d-{day:%Y-%m-%d}.zip"
        listed.append({"endpoint_id": DAILY_ID, "name": name, "url": bases[DAILY_ID] + name})
        day += timedelta(days=1)
    return listed


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    end = end_day(parameters, FIRST_DAY)
    return {"dataset_id": DATASET_ID, "source_id": SOURCE_ID, "output": str(output), "first_day": FIRST_DAY.isoformat(),
            "end": end.isoformat(), "files": len(files(end)), "writes": ["raw/*.zip", "raw/*.zip.CHECKSUM", "capture.json"],
            "overwrite": False}


def capture(dataset_id: str, output: Path, timeout: float = 30, parameters: dict[str, str] | None = None,
            download: public_market.Download = public_market.download) -> dict[str, Any]:
    preview = capture_preview(dataset_id, output, parameters)
    with public_market.new_folder(output) as folder:
        records = []
        for item in files(date.fromisoformat(preview["end"])):
            body = download(item["url"], timeout)
            checksum = download(item["url"] + ".CHECKSUM", timeout)
            if sha256(body) != _published(checksum, item["name"]):
                raise DataError(f"{item['name']} does not match its published SHA-256")
            records.append(public_market.record(folder, f"raw/{item['name']}", body, **item))
            records.append(public_market.record(folder, f"raw/{item['name']}.CHECKSUM", checksum, checksum_of=item["name"]))
        value = public_market.receipt(SCHEMA, DATASET_ID, SOURCE_ID, records, first_day=preview["first_day"], end=preview["end"])
        (folder / "capture.json").write_bytes(canonical_bytes(value))
    return value


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    value = public_market.read_receipt(capture_dir, SCHEMA, DATASET_ID)
    end = date.fromisoformat(value["end"])
    archives = [item for item in value["files"] if "checksum_of" not in item]
    if [(item["name"], item["url"]) for item in archives] != [(item["name"], item["url"]) for item in files(end)]:
        raise DataError("the captured files are not the ones the archive lists for this window")
    candles: dict[date, tuple[Any, ...]] = {}
    for item in archives:
        body = (capture_dir / item["path"]).read_bytes()
        if _published((capture_dir / f"{item['path']}.CHECKSUM").read_bytes(), item["name"]) != item["sha256"]:
            raise DataError(f"{item['name']} differs from its published SHA-256")
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            names = archive.namelist()
            if len(names) != 1:
                raise DataError(f"{item['name']} holds {len(names)} files, expected one")
            text = archive.read(names[0]).decode("utf-8")
        for fields in csv.reader(io.StringIO(text)):
            if not fields or not fields[0].isdigit():
                continue
            day = _candle_time(fields[0])
            if day in candles:
                raise DataError(f"two candles for {day}")
            candles[day] = (day, float(fields[1]), float(fields[2]), float(fields[3]), float(fields[4]),
                            float(fields[5]), float(fields[7]), int(fields[8]))
    expected = [FIRST_DAY + timedelta(days=offset) for offset in range((end - FIRST_DAY).days)]
    if sorted(candles) != expected:
        missing = sorted(set(expected) - set(candles))
        raise DataError(f"the candles do not cover every day from {FIRST_DAY} to {end}: {len(missing)} missing, first {missing[:3]}")
    rows: list[tuple[Any, ...]] = []
    for day in expected:
        candle = candles[day]
        previous = rows[-1][4] if rows else None
        rows.append((*candle, math.log(candle[4] / previous) if previous else None))
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


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    """Archive integrity and the built rows. This dataset is itself the reference, so it takes no ``--against``."""
    if against is not None:
        raise DataError(f"{DATASET_ID} takes no --against reference")
    value, rows = read_rows(capture_dir)
    checked = ["published SHA-256 of every file", "one candle for every day", "log returns"]
    findings: list[str] = []
    if dataset_dir is not None:
        checked.extend(["build hashes", "Parquet rows"])
        findings.extend(public_market.built_findings(dataset_dir, TABLE, "observation_date", value, rows))
    return {"dataset_id": DATASET_ID, "capture_id": value["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": _summary(rows), "findings": findings}
