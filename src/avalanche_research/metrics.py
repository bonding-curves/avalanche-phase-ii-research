"""Avalanche Metrics API daily series: Primary Network staking totals and C-Chain activity."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from . import __version__
from .catalog import DataError, canonical_bytes, dataset, load_catalog, now, sha256
from .rest import capture, capture_preview, read_capture  # noqa: F401  shared REST capture path


NAVAX_PER_AVAX = 1_000_000_000
RECONCILIATION_TOLERANCE = 0.02
RECONCILIATION_DAY_SHARE = 0.10


@dataclass(frozen=True)
class SeriesSpec:
    dataset_id: str
    table: str
    endpoint_prefix: str
    metrics: dict[str, str]          # metric name -> column
    integer_columns: tuple[str, ...]
    table_columns: dict[str, str]
    derived_sql: str                 # extra select expressions after the pivoted columns


STAKING = SeriesSpec(
    dataset_id="metrics-api.primary-staking-daily",
    table="primary-staking-daily",
    endpoint_prefix="staking-",
    metrics={"validator-count": "validator_count", "delegator-count": "delegator_count", "validator-weight": "validator_weight_navax", "delegator-weight": "delegator_weight_navax"},
    integer_columns=("validator_count", "delegator_count", "validator_weight_navax", "delegator_weight_navax"),
    table_columns={
        "observation_date": "DATE", "validator_count": "BIGINT", "delegator_count": "BIGINT",
        "validator_weight_navax": "BIGINT", "delegator_weight_navax": "BIGINT",
        "validator_weight_avax": "DOUBLE", "delegator_weight_avax": "DOUBLE",
    },
    derived_sql=", validator_weight_navax::DOUBLE / 1e9, delegator_weight_navax::DOUBLE / 1e9",
)
ACTIVITY = SeriesSpec(
    dataset_id="metrics-api.c-chain-activity-daily",
    table="c-chain-activity-daily",
    endpoint_prefix="chain-",
    metrics={"active-addresses": "active_addresses", "tx-count": "tx_count", "gas-used": "gas_used", "fees-paid": "fees_paid", "avg-gas-price": "avg_gas_price"},
    integer_columns=("active_addresses", "tx_count", "gas_used"),
    table_columns={
        "observation_date": "DATE", "active_addresses": "BIGINT", "tx_count": "BIGINT", "gas_used": "BIGINT",
        "fees_paid": "DOUBLE", "avg_gas_price": "DOUBLE",
    },
    derived_sql="",
)
SPECS = {spec.dataset_id: spec for spec in (STAKING, ACTIVITY)}
DATASET_IDS = tuple(SPECS)


def spec_for(dataset_id: str) -> SeriesSpec:
    try:
        return SPECS[dataset_id]
    except KeyError:
        raise DataError(f"unknown Metrics API dataset: {dataset_id}") from None


def _metric_of(endpoint_id: str, spec: SeriesSpec) -> str:
    body = endpoint_id[len(spec.endpoint_prefix):]
    for slug in spec.metrics:
        if body.startswith(slug + "-"):
            return spec.metrics[slug]
    raise DataError(f"endpoint does not belong to the dataset: {endpoint_id}")


def load_capture(connection: Any, spec: SeriesSpec, capture_dir: Path, receipt: dict[str, Any]) -> None:
    """Read every captured window, refuse incomplete pages, and pivot the series into one row per day."""
    selects = []
    for record in receipt["responses"]:
        column = _metric_of(record["endpoint_id"], spec)
        path = str(capture_dir / record["path"]).replace("'", "''")
        selects.append(
            f"SELECT '{column}' AS metric, unnest(results) AS point, nextPageToken FROM read_json('{path}', "
            "columns={results: 'STRUCT(value DOUBLE, timestamp BIGINT)[]', nextPageToken: 'VARCHAR'})"
        )
    pivots = []
    for column in spec.metrics.values():
        cast = "::BIGINT" if column in spec.integer_columns else ""
        pivots.append(f"MAX(CASE WHEN metric = '{column}' THEN point.value END){cast} AS {column}")
    typed = ", ".join(f"{name} {kind}" for name, kind in spec.table_columns.items())
    try:
        connection.execute(f"CREATE VIEW capture AS {' UNION ALL '.join(selects)}")
        incomplete = connection.execute("SELECT COUNT(DISTINCT metric) FROM capture WHERE nextPageToken IS NOT NULL AND nextPageToken <> ''").fetchone()[0]
        if incomplete:
            raise DataError(f"{incomplete} captured windows are incomplete pages; narrow the window contract")
        connection.execute(f"CREATE TABLE rows({typed})")
        connection.execute(
            f"""
            INSERT INTO rows
            SELECT observation_date, {', '.join(spec.metrics.values())}{spec.derived_sql}
            FROM (SELECT make_timestamp(point.timestamp * 1000000)::DATE AS observation_date, {', '.join(pivots)} FROM capture GROUP BY 1)
            ORDER BY observation_date
            """
        )
        counts = connection.execute(
            f"SELECT COUNT(*), COUNT_IF({' OR '.join(f'{c} IS NULL' for c in spec.metrics.values())}), COUNT_IF({' OR '.join(f'{c} < 0' for c in spec.metrics.values())}) FROM rows"
        ).fetchone()
    except duckdb.Error as error:
        raise DataError(f"captured response does not match the declared shape: {error}") from error
    if counts[0] == 0:
        raise DataError("captured windows hold no observations")
    if counts[2]:
        raise DataError(f"{counts[2]} days carry a negative value")


def summarize(connection: Any, spec: SeriesSpec) -> dict[str, Any]:
    columns = list(spec.metrics.values())
    record = connection.execute(
        f"""
        WITH ordered AS (SELECT observation_date, lag(observation_date) OVER (ORDER BY observation_date) AS previous_date FROM rows)
        SELECT (SELECT COUNT(*) FROM rows), (SELECT MIN(observation_date) FROM rows), (SELECT MAX(observation_date) FROM rows),
               (SELECT COUNT_IF(observation_date - previous_date > 1) FROM ordered),
               (SELECT COUNT_IF({' OR '.join(f'{c} IS NULL' for c in columns)}) FROM rows),
               {', '.join(f'(SELECT {c} FROM rows ORDER BY observation_date DESC LIMIT 1)' for c in columns)}
        """
    ).fetchone()
    summary = {
        "rows": record[0],
        "observed_from": record[1].isoformat(),
        "observed_to": record[2].isoformat(),
        "skipped_dates": record[3],
        "days_with_a_missing_series": record[4],
    }
    summary.update({f"latest_{column}": value for column, value in zip(columns, record[5:])})
    return summary


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    spec = spec_for(dataset_id)
    load_catalog()
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{spec.table}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    spec = spec_for(dataset_id)
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
        parquet_path = temporary / f"{spec.table}.parquet"
        connection = duckdb.connect()
        try:
            load_capture(connection, spec, capture_dir, receipt)
            connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection, spec)
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "metrics-api-build/v1",
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


def reconcile(connection: Any, references: tuple[Path, ...]) -> tuple[dict[str, Any], list[str]]:
    """Compare the staking series with daily active counts and weights rebuilt from the Snowflake stake datasets.

    A period is active on a day when it started on or before that day's end and ends after it. The Snowflake side
    is reconstructed from start and end events with cumulative sums, so the comparison is exact in its own terms;
    remaining differences reflect the Metrics API's aggregation instant, which it does not document.
    """
    sides = {}
    for directory in references:
        for name, kind in (("primary-validator-stakes.parquet", "validator"), ("primary-delegator-stakes.parquet", "delegator")):
            if (directory / name).is_file():
                sides[kind] = str(directory / name).replace("'", "''")
    if not sides:
        raise DataError("no Snowflake validator or delegator dataset found in the reference directories")
    summary: dict[str, Any] = {}
    findings: list[str] = []
    for kind, parquet in sides.items():
        record = connection.execute(
            f"""
            WITH events AS (
              SELECT start_time::DATE AS d, 1 AS n, stake_navax AS w FROM read_parquet('{parquet}')
              UNION ALL
              SELECT (end_time - INTERVAL 1 SECOND)::DATE + 1 AS d, -1, -stake_navax FROM read_parquet('{parquet}')
            ),
            daily AS (SELECT d, SUM(n) AS n, SUM(w) AS w FROM events GROUP BY d),
            spine AS (SELECT observation_date AS d FROM rows),
            rebuilt AS (
              SELECT s.d, SUM(daily.n) OVER (ORDER BY s.d) AS active_count, SUM(daily.w) OVER (ORDER BY s.d) AS active_weight
              FROM (SELECT DISTINCT d FROM (SELECT d FROM spine UNION ALL SELECT d FROM daily)) s LEFT JOIN daily USING (d)
            ),
            paired AS (
              SELECT r.observation_date,
                     abs(r.{kind}_count / NULLIF(b.active_count, 0) - 1) AS count_difference,
                     abs(r.{kind}_weight_navax / NULLIF(b.active_weight, 0) - 1) AS weight_difference
              FROM rows r JOIN rebuilt b ON b.d = r.observation_date
              WHERE b.active_count > 0
            )
            SELECT COUNT(*), median(count_difference), COUNT_IF(count_difference > {RECONCILIATION_TOLERANCE}),
                   median(weight_difference), COUNT_IF(weight_difference > {RECONCILIATION_TOLERANCE})
            FROM paired
            """
        ).fetchone()
        by_year = connection.execute(
            f"""
            WITH events AS (
              SELECT start_time::DATE AS d, 1 AS n FROM read_parquet('{parquet}')
              UNION ALL SELECT (end_time - INTERVAL 1 SECOND)::DATE + 1, -1 FROM read_parquet('{parquet}')
            ),
            daily AS (SELECT d, SUM(n) AS n FROM events GROUP BY d),
            rebuilt AS (SELECT s.d, SUM(daily.n) OVER (ORDER BY s.d) AS active_count
                        FROM (SELECT DISTINCT d FROM (SELECT observation_date AS d FROM rows UNION ALL SELECT d FROM daily)) s LEFT JOIN daily USING (d))
            SELECT year(r.observation_date), median(abs(r.{kind}_count / NULLIF(b.active_count, 0) - 1))
            FROM rows r JOIN rebuilt b ON b.d = r.observation_date WHERE b.active_count > 0 GROUP BY 1 ORDER BY 1
            """
        ).fetchall()
        summary.update({
            f"{kind}_days_compared": record[0],
            f"{kind}_count_median_relative_difference": record[1],
            f"{kind}_count_days_beyond_tolerance": record[2],
            f"{kind}_weight_median_relative_difference": record[3],
            f"{kind}_weight_days_beyond_tolerance": record[4],
            f"{kind}_count_median_relative_difference_by_year": {str(year): value for year, value in by_year},
        })
        if record[0] == 0:
            findings.append(f"no overlapping days with the Snowflake {kind} dataset")
            continue
        for measure, beyond in (("count", record[2]), ("weight", record[4])):
            if beyond > RECONCILIATION_DAY_SHARE * record[0]:
                findings.append(f"{beyond} of {record[0]} days differ from the Snowflake {kind} {measure} by more than {RECONCILIATION_TOLERANCE:.0%}")
    return summary, findings


def check(capture_dir: Path, dataset_dir: Path | None = None, against: tuple[Path, ...] | Path | None = None) -> dict[str, Any]:
    catalog = load_catalog()
    receipt, _ = read_capture(capture_dir, catalog)
    spec = spec_for(receipt["dataset_id"])
    references = tuple(against) if isinstance(against, (tuple, list)) else ((against,) if against else ())
    findings: list[str] = []
    checked = ["capture hashes", "required endpoints", "complete pages", "response shape", "unique days", "daily spacing", "series completeness"]
    # Trailing days that lack a series are provider publication lag and are counted in the summary, not reported.
    connection = duckdb.connect()
    try:
        load_capture(connection, spec, capture_dir, receipt)
        counts = connection.execute(
            f"""
            WITH ordered AS (SELECT observation_date, lag(observation_date) OVER (ORDER BY observation_date) AS previous_date,
                                    {' OR '.join(f'{c} IS NULL' for c in spec.metrics.values())} AS incomplete FROM rows),
                 last_complete AS (SELECT MAX(observation_date) AS d FROM ordered WHERE NOT incomplete)
            SELECT (SELECT COUNT(*) - COUNT(DISTINCT observation_date) FROM rows),
                   (SELECT COUNT_IF(observation_date - previous_date > 1) FROM ordered),
                   (SELECT COUNT_IF(incomplete AND observation_date < (SELECT d FROM last_complete)) FROM ordered)
            """
        ).fetchone()
        labels = ("repeat a day", "follow a gap of more than one day", "lack one of the series before the last complete day")
        findings.extend(f"{failed} rows {label}" for failed, label in zip(counts, labels) if failed)
        summary = summarize(connection, spec)
        if dataset_dir is not None:
            checked.extend(["build hashes", "Parquet rows"])
            try:
                build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
                for item in build_receipt["outputs"]:
                    body = (dataset_dir / item["path"]).read_bytes()
                    if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                        findings.append(f"output hash or size differs: {item['path']}")
                parquet = str(dataset_dir / f"{spec.table}.parquet")
                columns = ", ".join(spec.table_columns)
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
        if references:
            if spec is not STAKING:
                raise DataError("only the staking series reconciles against the Snowflake datasets")
            checked.append("Snowflake staking reconciliation")
            reconciliation, reconciliation_findings = reconcile(connection, references)
            summary.update(reconciliation)
            findings.extend(reconciliation_findings)
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
