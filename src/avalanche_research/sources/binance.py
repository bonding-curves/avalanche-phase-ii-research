"""AVAX daily candles from Binance's public data archive, the full history since AVAX began trading.

CoinGecko's public API serves one year of daily prices. The Binance archive at data.binance.vision publishes every
day's AVAX/USDT candle since the first on 2020-09-22, one zip file per month and, for the month not yet closed, one
per day, each beside a file carrying its SHA-256. A capture downloads the files, refuses any whose hash differs from
the published one, and keeps both. The quote currency is USDT, not USD: the check compares the open of each day with
CoinGecko's USD price at the same midnight wherever both exist.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from .. import __version__
from ..core.catalog import DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256, source

DATASET_ID = "binance.avax-usdt-daily"
SOURCE_ID = "binance-public-data"
MONTHLY_ID = "avax-usdt-1d-monthly"
DAILY_ID = "avax-usdt-1d-daily"
TABLE = "avax-usdt-daily"
SCHEMA = "binance-public-data-capture/v1"
FIRST_DAY = date(2020, 9, 22)
VOLATILITY_WINDOW = 30
DAYS_PER_YEAR = 365
CROSS_CHECK_TOLERANCE = 0.02
COLUMNS = {
    "observation_date": "DATE",
    "open_usdt": "DOUBLE",
    "high_usdt": "DOUBLE",
    "low_usdt": "DOUBLE",
    "close_usdt": "DOUBLE",
    "volume_avax": "DOUBLE",
    "quote_volume_usdt": "DOUBLE",
    "trades": "BIGINT",
    "log_return": "DOUBLE",
    "realized_volatility_30d": "DOUBLE",
}


def _end(parameters: dict[str, str] | None) -> date:
    values = parameters or {}
    if set(values) - {"end"}:
        raise DataError("the only parameter is end=<YYYY-MM-DD>, the first day not captured")
    try:
        end = date.fromisoformat(values["end"]) if "end" in values else datetime.now(UTC).date()
    except ValueError as error:
        raise DataError("end must be a date, YYYY-MM-DD") from error
    if end <= FIRST_DAY:
        raise DataError(f"end must be after {FIRST_DAY}, the first day AVAX traded on Binance")
    return end


def _bases(catalog: dict[str, Any]) -> dict[str, str]:
    provider = source(catalog, SOURCE_ID)
    return {item["id"]: item["url"] for item in provider["endpoints"]}


def files(end: date, catalog: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """One monthly file for every month closed before end's month, then one daily file for each earlier day of that month."""
    bases = _bases(catalog or load_catalog())
    listed, month = [], date(FIRST_DAY.year, FIRST_DAY.month, 1)
    while month < date(end.year, end.month, 1):
        name = f"AVAXUSDT-1d-{month:%Y-%m}.zip"
        listed.append({"endpoint_id": MONTHLY_ID, "name": name, "url": bases[MONTHLY_ID] + name})
        month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    day = max(month, FIRST_DAY)
    while day < end:
        name = f"AVAXUSDT-1d-{day:%Y-%m-%d}.zip"
        listed.append({"endpoint_id": DAILY_ID, "name": name, "url": bases[DAILY_ID] + name})
        day += timedelta(days=1)
    return listed


def _download(url: str, timeout: float) -> bytes:
    import urllib.error
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": "avalanche-phase-ii-research/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except (OSError, urllib.error.URLError) as error:
        raise DataError(f"request failed for {url}: {error}") from error


def _published(body: bytes, name: str) -> str:
    """The hash in a CHECKSUM file, which reads '<sha256>  <file name>'."""
    parts = body.decode("utf-8", "replace").split()
    if len(parts) != 2 or parts[1] != name or len(parts[0]) != 64:
        raise DataError(f"unreadable checksum file for {name}")
    return parts[0]


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    end = _end(parameters)
    listed = files(end)
    return {"dataset_id": DATASET_ID, "source_id": SOURCE_ID, "output": str(output), "first_day": FIRST_DAY.isoformat(),
            "end": end.isoformat(), "files": len(listed), "writes": ["raw/*.zip", "raw/*.zip.CHECKSUM", "capture.json"], "overwrite": False}


def capture(
    dataset_id: str,
    output: Path,
    timeout: float = 30,
    parameters: dict[str, str] | None = None,
    download: Callable[[str, float], bytes] = _download,
) -> dict[str, Any]:
    preview = capture_preview(dataset_id, output, parameters)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    records = []
    try:
        (temporary / "raw").mkdir()
        for item in files(date.fromisoformat(preview["end"])):
            body = download(item["url"], timeout)
            checksum = download(item["url"] + ".CHECKSUM", timeout)
            published = _published(checksum, item["name"])
            if sha256(body) != published:
                raise DataError(f"{item['name']} does not match its published SHA-256")
            (temporary / "raw" / item["name"]).write_bytes(body)
            (temporary / "raw" / f"{item['name']}.CHECKSUM").write_bytes(checksum)
            records.append({**item, "path": f"raw/{item['name']}", "bytes": len(body), "sha256": published,
                            "checksum_path": f"raw/{item['name']}.CHECKSUM", "checksum_sha256": sha256(checksum)})
        completed_at = now()
        identity = sha256(canonical_bytes({"completed_at": completed_at, "files": records}))
        receipt = {
            "schema_version": SCHEMA, "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
            "dataset_id": DATASET_ID, "source_id": SOURCE_ID, "completed_at": completed_at,
            "contract_sha256": contract_hash(load_catalog(), DATASET_ID), "tool": f"avalanche-research@{__version__}",
            "first_day": preview["first_day"], "end": preview["end"], "files": records,
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        os.replace(temporary, output)
        return receipt
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _candle_time(value: str) -> date:
    """Open time in milliseconds before 2025 and in microseconds from 2025 on."""
    stamp = int(value)
    seconds = stamp / 1_000_000 if stamp > 10**14 else stamp / 1_000
    return datetime.fromtimestamp(seconds, UTC).date()


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid Binance capture: {error}") from error
    if receipt.get("schema_version") != SCHEMA or receipt.get("dataset_id") != DATASET_ID:
        raise DataError("unsupported Binance capture")
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), DATASET_ID):
        raise DataError("Binance capture contract hash differs")
    end = date.fromisoformat(receipt["end"])
    if [(item["name"], item["url"]) for item in receipt["files"]] != [(item["name"], item["url"]) for item in files(end)]:
        raise DataError("the captured files are not the ones the archive lists for this window")
    candles: dict[date, tuple[Any, ...]] = {}
    for item in receipt["files"]:
        body = (capture_dir / item["path"]).read_bytes()
        checksum = (capture_dir / item["checksum_path"]).read_bytes()
        if sha256(body) != item["sha256"] or _published(checksum, item["name"]) != item["sha256"] or sha256(checksum) != item["checksum_sha256"]:
            raise DataError(f"{item['name']} differs from its receipt or its published SHA-256")
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
    rows, returns = [], []
    for day in expected:
        candle = candles[day]
        previous = rows[-1][4] if rows else None
        log_return = math.log(candle[4] / previous) if previous else None
        if log_return is not None:
            returns.append(log_return)
        window = returns[-VOLATILITY_WINDOW:]
        volatility = None
        if log_return is not None and len(window) == VOLATILITY_WINDOW:
            mean = sum(window) / VOLATILITY_WINDOW
            volatility = math.sqrt(sum((value - mean) ** 2 for value in window) / (VOLATILITY_WINDOW - 1)) * math.sqrt(DAYS_PER_YEAR)
        rows.append((*candle, log_return, volatility))
    return receipt, rows


def _summary(rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    return {"rows": len(rows), "first_day": rows[0][0].isoformat(), "last_day": rows[-1][0].isoformat(),
            "volatility_days": sum(row[9] is not None for row in rows)}


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{TABLE}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    build_preview(dataset_id, capture_dir, output)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    receipt, rows = read_rows(capture_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet = temporary / f"{TABLE}.parquet"
        connection = duckdb.connect()
        try:
            connection.execute(f"CREATE TABLE rows({', '.join(f'{name} {kind}' for name, kind in COLUMNS.items())})")
            connection.executemany(f"INSERT INTO rows VALUES ({', '.join('?' for _ in COLUMNS)})", rows)
            connection.execute("COPY (SELECT * FROM rows ORDER BY observation_date) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
        finally:
            connection.close()
        result = {
            "schema_version": "binance-public-data-build/v1", "dataset_id": DATASET_ID,
            "dataset_schema": dataset(load_catalog(), DATASET_ID)["fields"], "source_capture_id": receipt["capture_id"],
            "completed_at": now(), "tool": f"avalanche-research@{__version__}", "summary": _summary(rows),
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(result))
        os.replace(temporary, output)
        return result
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def cross_check(rows: list[tuple[Any, ...]], reference_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Each day's USDT open against CoinGecko's USD price at the same midnight.

    CoinGecko's midnight point is an aggregate taken near, not at, the open, so on a fast-moving night it can sit
    several percent from the open while inside the day's range. A day is a finding only when the reference is both
    beyond the tolerance from the open and outside the day's low to high widened by the tolerance."""
    parquet = next(reference_dir.glob("*.parquet"), None)
    if parquet is None:
        raise DataError(f"no reference Parquet in {reference_dir}")
    connection = duckdb.connect()
    try:
        reference = {day: float(price) for day, price in connection.execute("SELECT observation_date, price_usd FROM read_parquet(?) WHERE NOT partial_day", [str(parquet)]).fetchall()}
    finally:
        connection.close()
    shared = [(row, reference[row[0]]) for row in rows if row[0] in reference]
    if not shared:
        return {"cross_check_days": 0}, ["no overlapping days with the reference price dataset"]
    differences = sorted(abs(row[1] / price - 1) for row, price in shared)
    beyond = sum(abs(row[1] / price - 1) > CROSS_CHECK_TOLERANCE
                 and not row[3] * (1 - CROSS_CHECK_TOLERANCE) <= price <= row[2] * (1 + CROSS_CHECK_TOLERANCE) for row, price in shared)
    summary = {"cross_check_days": len(differences), "cross_check_median_difference": round(differences[len(differences) // 2], 6),
               "cross_check_max_difference": round(differences[-1], 6), "cross_check_days_beyond_tolerance": beyond}
    return summary, ([f"{beyond} days differ from the reference price by more than {CROSS_CHECK_TOLERANCE:.0%}"] if beyond else [])


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    """With ``--against`` a built coingecko.avax-market-daily dataset directory: the USDT open against the USD price."""
    receipt, rows = read_rows(capture_dir)
    findings: list[str] = []
    checked = ["published SHA-256 of every file", "one candle for every day", "log returns and 30-day volatility"]
    summary = _summary(rows)
    if against is not None:
        checked.append("CoinGecko USD price at the same midnight")
        extra, found = cross_check(rows, against)
        summary.update(extra)
        findings.extend(found)
    if dataset_dir is not None:
        checked.extend(["build hashes", "Parquet rows"])
        try:
            built = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
            parquet = dataset_dir / f"{TABLE}.parquet"
            data = parquet.read_bytes()
            if built["source_capture_id"] != receipt["capture_id"] or len(data) != built["outputs"][0]["bytes"] or sha256(data) != built["outputs"][0]["sha256"]:
                findings.append("build receipt or Parquet hash differs")
            connection = duckdb.connect()
            try:
                actual = connection.execute("SELECT * FROM read_parquet(?) ORDER BY observation_date", [str(parquet)]).fetchall()
            finally:
                connection.close()
            if actual != rows:
                findings.append("Parquet rows differ from the captured candles")
        except (OSError, KeyError, ValueError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid Binance dataset output: {error}")
    return {"dataset_id": DATASET_ID, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}
