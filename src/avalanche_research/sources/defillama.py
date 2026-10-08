"""DefiLlama datasets: the AVAX daily price history with CoinGecko lineage."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from .. import __version__
from ..core.catalog import DataError, canonical_bytes, dataset, load_catalog, now, sha256
from .capture.rest import capture, capture_preview, read_capture  # noqa: F401  shared REST capture path


DATASET_ID = "defillama.avax-price-daily"
COIN = "coingecko:avalanche-2"
TABLE = "avax-price-daily"
VOLATILITY_WINDOW = 30
DAYS_PER_YEAR = 365
TABLE_COLUMNS = {
    "observed_at": "TIMESTAMP",
    "observation_date": "DATE",
    "price_usd": "DOUBLE",
    "confidence": "DOUBLE",
    "lineage": "VARCHAR",
    "log_return": "DOUBLE",
    "realized_volatility_30d": "DOUBLE",
}


def _transform_sql(paths: list[str]) -> str:
    files = ", ".join("'" + path.replace("'", "''") + "'" for path in paths)
    return f"""
WITH windows AS (
  SELECT json_extract(content, '$.coins."{COIN}"') AS coin FROM read_text([{files}])
),
points AS (
  SELECT unnest(json_transform(json_extract(coin, '$.prices'), '[{{"timestamp":"BIGINT","price":"DOUBLE"}}]')) AS point,
         json_extract(coin, '$.confidence')::DOUBLE AS confidence
  FROM windows
),
typed AS (
  SELECT DISTINCT ON (point.timestamp) make_timestamp(point.timestamp * 1000000) AS observed_at, point.price AS price_usd, confidence
  FROM points
  ORDER BY point.timestamp
),
derived AS (
  -- DefiLlama stamps each daily point near midnight UTC, at about 00:20 or about 23:30. A point is dated by its nearest
  -- midnight, so a 23:30 point is the next day's: dating it by its calendar day repeated 343 dates and skipped 346.
  SELECT observed_at, (observed_at + INTERVAL 12 HOUR)::DATE AS observation_date, price_usd, confidence, '{COIN}' AS lineage,
         ln(price_usd / lag(price_usd) OVER (ORDER BY observed_at)) AS log_return
  FROM typed
)
SELECT observed_at, observation_date, price_usd, confidence, lineage, log_return,
       CASE WHEN COUNT(log_return) OVER w = {VOLATILITY_WINDOW}
            THEN stddev_samp(log_return) OVER w * sqrt({DAYS_PER_YEAR}) END AS realized_volatility_30d
FROM derived
WINDOW w AS (ORDER BY observed_at ROWS BETWEEN {VOLATILITY_WINDOW - 1} PRECEDING AND CURRENT ROW)
ORDER BY observed_at
"""


def load_capture(connection: Any, capture_dir: Path, receipt: dict[str, Any]) -> None:
    """Read every captured window and build the typed price table in DuckDB."""
    paths = [str(capture_dir / item["path"]) for item in receipt["responses"]]
    typed = ", ".join(f"{name} {kind}" for name, kind in TABLE_COLUMNS.items())
    try:
        connection.execute(f"CREATE TABLE rows({typed})")
        connection.execute(f"INSERT INTO rows {_transform_sql(paths)}")
        counts = connection.execute(
            "SELECT COUNT(*), COUNT_IF(observed_at IS NULL OR price_usd IS NULL OR confidence IS NULL), COUNT_IF(price_usd <= 0) FROM rows"
        ).fetchone()
    except duckdb.Error as error:
        raise DataError(f"captured response does not match the declared shape: {error}") from error
    if counts[0] == 0:
        raise DataError("captured windows hold no observations")
    if counts[1]:
        raise DataError(f"{counts[1]} observations miss a value")
    if counts[2]:
        raise DataError(f"{counts[2]} observations carry a non-positive price")


def summarize(connection: Any) -> dict[str, Any]:
    record = connection.execute(
        """
        WITH ordered AS (SELECT observation_date, lag(observation_date) OVER (ORDER BY observed_at) AS previous_date FROM rows)
        SELECT (SELECT COUNT(*) FROM rows), (SELECT MIN(observation_date) FROM rows), (SELECT MAX(observation_date) FROM rows),
               (SELECT COUNT(*) - COUNT(DISTINCT observation_date) FROM rows),
               (SELECT COUNT_IF(observation_date - previous_date > 1) FROM ordered),
               (SELECT MIN(confidence) FROM rows), (SELECT MIN(price_usd) FROM rows), (SELECT MAX(price_usd) FROM rows),
               (SELECT COUNT_IF(realized_volatility_30d IS NULL) FROM rows)
        """
    ).fetchone()
    return {
        "rows": record[0],
        "observed_from": record[1].isoformat(),
        "observed_to": record[2].isoformat(),
        "dates_with_two_observations": record[3],
        "skipped_dates": record[4],
        "confidence_min": record[5],
        "price_usd_min": record[6],
        "price_usd_max": record[7],
        "rows_without_volatility": record[8],
    }


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    load_catalog()
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{TABLE}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    receipt, _ = read_capture(capture_dir, catalog)
    if receipt["dataset_id"] != dataset_id:
        raise DataError(f"capture belongs to {receipt['dataset_id']}, not {dataset_id}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet_path = temporary / f"{TABLE}.parquet"
        connection = duckdb.connect()
        try:
            load_capture(connection, capture_dir, receipt)
            connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection)
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "defillama-build/v1",
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


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    catalog = load_catalog()
    receipt, _ = read_capture(capture_dir, catalog)
    findings: list[str] = []
    checked = ["capture hashes", "required endpoints", "response shape", "positive prices", "unique observations", "coverage gaps", "volatility window"]
    connection = duckdb.connect()
    try:
        load_capture(connection, capture_dir, receipt)
        counts = connection.execute(
            f"""
            WITH ordered AS (
              SELECT observed_at, observation_date, realized_volatility_30d, COUNT(*) OVER () AS total,
                     lag(observation_date) OVER (ORDER BY observed_at) AS previous_date
              FROM rows
            )
            SELECT COUNT(*) - COUNT(DISTINCT observed_at),
                   COUNT_IF(observation_date - previous_date > 3),
                   COUNT_IF(realized_volatility_30d IS NULL) - LEAST({VOLATILITY_WINDOW}, MAX(total))
            FROM ordered
            """
        ).fetchone()
        labels = ("repeat an observation time", "follow a gap of more than three days", "lack a volatility value beyond the first 30 observations")
        findings.extend(f"{failed} rows {label}" for failed, label in zip(counts, labels) if failed)
        summary = summarize(connection)
        if dataset_dir is not None:
            checked.extend(["build hashes", "Parquet rows"])
            try:
                build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
                for item in build_receipt["outputs"]:
                    body = (dataset_dir / item["path"]).read_bytes()
                    if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                        findings.append(f"output hash or size differs: {item['path']}")
                parquet = str(dataset_dir / f"{TABLE}.parquet")
                columns = ", ".join(TABLE_COLUMNS)
                differing = connection.execute(
                    f"""
                    SELECT (SELECT COUNT(*) FROM (SELECT {columns} FROM rows EXCEPT ALL SELECT {columns} FROM read_parquet(?)))
                         + (SELECT COUNT(*) FROM (SELECT {columns} FROM read_parquet(?) EXCEPT ALL SELECT {columns} FROM rows))
                    """,
                    [parquet, parquet],
                ).fetchone()[0]
                if differing:
                    findings.append("Parquet rows differ from the captured inputs")
            except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
                findings.append(f"invalid dataset output: {error}")
        if against is not None:
            raise DataError("the DefiLlama price dataset is the reference series; run the cross-check from the CoinGecko dataset")
    finally:
        connection.close()
    return {
        "dataset_id": receipt["dataset_id"],
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summary,
        "findings": findings,
    }
