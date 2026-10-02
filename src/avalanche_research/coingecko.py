"""CoinGecko AVAX market data: typed daily table with log returns and 30-day realized volatility."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from . import __version__
from .catalog import DataError, canonical_bytes, dataset, load_catalog, now, sha256
from .rest import capture, capture_preview, read_capture  # noqa: F401  shared REST capture path


DATASET_ID = "coingecko.avax-market-daily"
ENDPOINT_ID = "avax-market-chart"
TABLE = "avax-market-daily"
VOLATILITY_WINDOW = 30
DAYS_PER_YEAR = 365
TABLE_COLUMNS = {
    "observed_at": "TIMESTAMP",
    "observation_date": "DATE",
    "partial_day": "BOOLEAN",
    "price_usd": "DOUBLE",
    "market_cap_usd": "DOUBLE",
    "volume_usd": "DOUBLE",
    "log_return": "DOUBLE",
    "realized_volatility_30d": "DOUBLE",
}
TRANSFORM_SQL = f"""
WITH series AS (
  SELECT p.ts, p.value AS price_usd, m.value AS market_cap_usd, v.value AS volume_usd
  FROM (SELECT unnest(prices)[1] AS ts, unnest(prices)[2] AS value FROM capture) p
  JOIN (SELECT unnest(market_caps)[1] AS ts, unnest(market_caps)[2] AS value FROM capture) m USING (ts)
  JOIN (SELECT unnest(total_volumes)[1] AS ts, unnest(total_volumes)[2] AS value FROM capture) v USING (ts)
),
typed AS (
  SELECT make_timestamp((ts * 1000)::BIGINT) AS observed_at, price_usd, market_cap_usd, volume_usd FROM series
),
derived AS (
  SELECT observed_at, observed_at::DATE AS observation_date,
         observed_at <> date_trunc('day', observed_at) AS partial_day,
         price_usd, market_cap_usd, volume_usd,
         ln(price_usd / lag(price_usd) OVER (ORDER BY observed_at)) AS log_return
  FROM typed
)
SELECT observed_at, observation_date, partial_day, price_usd, market_cap_usd, volume_usd, log_return,
       CASE WHEN COUNT(log_return) OVER w = {VOLATILITY_WINDOW}
            THEN stddev_samp(log_return) OVER w * sqrt({DAYS_PER_YEAR}) END AS realized_volatility_30d
FROM derived
WINDOW w AS (ORDER BY observed_at ROWS BETWEEN {VOLATILITY_WINDOW - 1} PRECEDING AND CURRENT ROW)
ORDER BY observed_at
"""


def load_capture(connection: Any, capture_dir: Path, receipt: dict[str, Any]) -> None:
    """Read the captured response and build the typed daily table in DuckDB."""
    record = next(item for item in receipt["responses"] if item["endpoint_id"] == ENDPOINT_ID)
    path = str(capture_dir / record["path"]).replace("'", "''")
    typed = ", ".join(f"{name} {kind}" for name, kind in TABLE_COLUMNS.items())
    try:
        connection.execute(
            f"CREATE VIEW capture AS SELECT * FROM read_json('{path}', "
            "columns={prices: 'DOUBLE[][]', market_caps: 'DOUBLE[][]', total_volumes: 'DOUBLE[][]'})"
        )
        connection.execute(f"CREATE TABLE rows({typed})")
        connection.execute(f"INSERT INTO rows {TRANSFORM_SQL}")
        counts = connection.execute(
            "SELECT COUNT(*), COUNT_IF(observed_at IS NULL OR price_usd IS NULL OR market_cap_usd IS NULL OR volume_usd IS NULL),"
            " COUNT_IF(price_usd <= 0 OR market_cap_usd < 0 OR volume_usd < 0) FROM rows"
        ).fetchone()
    except duckdb.Error as error:
        raise DataError(f"captured response does not match the declared shape: {error}") from error
    if counts[0] == 0:
        raise DataError("captured response holds no observations")
    if counts[1]:
        raise DataError(f"{counts[1]} observations miss a value")
    if counts[2]:
        raise DataError(f"{counts[2]} observations carry a non-positive price or negative amount")


def summarize(connection: Any) -> dict[str, Any]:
    record = connection.execute(
        "SELECT COUNT(*), MIN(observation_date), MAX(observation_date), COUNT_IF(partial_day), MIN(price_usd), MAX(price_usd),"
        " COUNT_IF(realized_volatility_30d IS NULL), MAX(observed_at) FROM rows"
    ).fetchone()
    return {
        "rows": record[0],
        "observed_from": record[1].isoformat(),
        "observed_to": record[2].isoformat(),
        "partial_day_rows": record[3],
        "price_usd_min": record[4],
        "price_usd_max": record[5],
        "rows_without_volatility": record[6],
        "last_observation_at": record[7].isoformat(timespec="seconds") + "Z",
    }


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    load_catalog()
    return {
        "dataset_id": dataset_id,
        "capture": str(capture_dir),
        "output": str(output),
        "writes": [f"{TABLE}.parquet", "build.json"],
        "overwrite": False,
    }


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
            "schema_version": "coingecko-build/v1",
            "dataset_id": dataset_id,
            "dataset_schema": definition["fields"],
            "source_capture_id": receipt["capture_id"],
            "completed_at": now(),
            "tool": f"avalanche-research@{__version__}",
            "summary": summary,
            "outputs": [
                {"path": parquet_path.name, "bytes": parquet_path.stat().st_size, "sha256": sha256(parquet_path.read_bytes())},
            ],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return build_receipt


CROSS_CHECK_TOLERANCE = 0.10
CROSS_CHECK_ALIGNMENT_SECONDS = 3 * 3_600


def cross_check(connection: Any, reference_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Compare midnight prices with the DefiLlama price dataset built in reference_dir.

    DefiLlama observation times drift through the day, so a day is compared only when its nearest reference
    observation lies within three hours of midnight. Days without an aligned reference are counted, not compared.
    """
    parquet = reference_dir / "avax-price-daily.parquet"
    if not parquet.is_file():
        raise DataError(f"missing reference price dataset: {parquet}")
    record = connection.execute(
        f"""
        WITH reference AS (
          SELECT DISTINCT ON (observation_date) observation_date, price_usd,
                 abs(date_diff('second', observation_date::TIMESTAMP, observed_at)) AS offset_seconds
          FROM read_parquet('{str(parquet).replace("'", "''")}')
          ORDER BY observation_date, offset_seconds
        ),
        paired AS (
          SELECT r.observation_date, x.offset_seconds <= {CROSS_CHECK_ALIGNMENT_SECONDS} AS aligned,
                 abs(r.price_usd / x.price_usd - 1) AS relative_difference
          FROM rows r JOIN reference x USING (observation_date)
          WHERE NOT r.partial_day
        )
        SELECT COUNT_IF(aligned), median(relative_difference) FILTER (aligned), MAX(relative_difference) FILTER (aligned),
               COUNT_IF(aligned AND relative_difference > {CROSS_CHECK_TOLERANCE}), COUNT_IF(NOT aligned)
        FROM paired
        """
    ).fetchone()
    summary = {
        "cross_check_days": record[0],
        "cross_check_median_relative_difference": record[1],
        "cross_check_max_relative_difference": record[2],
        "cross_check_days_beyond_tolerance": record[3],
        "cross_check_days_without_aligned_reference": record[4],
    }
    findings = []
    if record[0] == 0:
        findings.append("no overlapping days with the reference price dataset")
    elif record[3]:
        findings.append(f"{record[3]} days differ from the reference price by more than {CROSS_CHECK_TOLERANCE:.0%}")
    return summary, findings


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    catalog = load_catalog()
    receipt, _ = read_capture(capture_dir, catalog)
    findings: list[str] = []
    checked = [
        "capture hashes", "required endpoints", "response shape", "positive values", "unique observations",
        "daily spacing", "partial-day placement", "volatility window",
    ]
    connection = duckdb.connect()
    try:
        load_capture(connection, capture_dir, receipt)
        counts = connection.execute(
            f"""
            WITH ordered AS (
              SELECT observed_at, observation_date, partial_day, realized_volatility_30d,
                     row_number() OVER (ORDER BY observed_at) AS position, COUNT(*) OVER () AS total,
                     lag(observation_date) OVER (ORDER BY observed_at) AS previous_date
              FROM rows
            )
            SELECT COUNT(*) - COUNT(DISTINCT observed_at),
                   COUNT_IF(NOT partial_day AND previous_date IS NOT NULL AND observation_date - previous_date <> 1),
                   COUNT_IF(partial_day AND position <> total),
                   COUNT_IF(realized_volatility_30d IS NULL) - LEAST({VOLATILITY_WINDOW}, MAX(total))
            FROM ordered
            """
        ).fetchone()
        labels = (
            "repeat an observation time",
            "follow a gap of more than one day",
            "are partial days before the final observation",
            "lack a volatility value beyond the first 30 observations",
        )
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
            checked.append("reference price cross-check")
            cross_summary, cross_findings = cross_check(connection, against)
            summary.update(cross_summary)
            findings.extend(cross_findings)
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
