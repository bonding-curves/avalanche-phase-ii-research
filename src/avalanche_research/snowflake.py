"""Avalanche Snowflake share capture, transformation, and validation."""

from __future__ import annotations

import gzip
import json
import os
import shutil
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

import duckdb

from . import __version__
from .catalog import (
    DATA_DIR, DataError, canonical_bytes, catalog_hash, dataset, load_catalog, now, sha256, source,
)


SOURCE_ID = "avalanche-snowflake"
DATASET_ID = "snowflake.primary-validator-stakes"
QUERY_ID = "primary-validator-stakes"
CONNECTION_VARIABLE = "AVALANCHE_SNOWFLAKE_CONNECTION"
DEFAULT_CONNECTION = "avalanche"
QUERY_TAG = "avalanche-phase-ii-research"
GENESIS_DATE = "2020-09-10"
NAVAX_PER_AVAX = 1_000_000_000
FEE_SHARES_PER_UNIT = 1_000_000
VALIDATOR_TYPES = ("AddValidatorTx", "AddPermissionlessValidatorTx")
DURATION_DAYS = (14, 365)
STAKE_NAVAX = (2_000 * NAVAX_PER_AVAX, 3_000_000 * NAVAX_PER_AVAX)
FEE_SHARES = (20_000, FEE_SHARES_PER_UNIT)
RAW_COLUMNS_TYPES = {
    "transaction_hash": "VARCHAR",
    "accepted_at": "TIMESTAMP",
    "block_height": "BIGINT",
    "tx_type": "VARCHAR",
    "node_id": "VARCHAR",
    "start_time": "TIMESTAMP",
    "end_time": "TIMESTAMP",
    "stake_navax": "BIGINT",
    "delegation_fee_shares": "INTEGER",
    "potential_reward_navax": "BIGINT",
    "rewarded": "BOOLEAN",
    "staked_utxo_count": "INTEGER",
    "utxo_stake_navax": "BIGINT",
}
RAW_COLUMNS = tuple(RAW_COLUMNS_TYPES)
TABLE_COLUMNS = {
    "transaction_hash": "VARCHAR",
    "accepted_at": "TIMESTAMP",
    "block_height": "BIGINT",
    "tx_type": "VARCHAR",
    "node_id": "VARCHAR",
    "start_time": "TIMESTAMP",
    "end_time": "TIMESTAMP",
    "duration_days": "DOUBLE",
    "stake_navax": "BIGINT",
    "stake_avax": "DOUBLE",
    "delegation_fee_shares": "INTEGER",
    "delegation_fee_rate": "DOUBLE",
    "potential_reward_navax": "BIGINT",
    "potential_reward_avax": "DOUBLE",
    "rewarded": "BOOLEAN",
    "staked_utxo_count": "INTEGER",
    "utxo_stake_navax": "BIGINT",
}
SESSION_SQL = "SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_VERSION()"
FETCH_SIZE = 10_000


def connection_name() -> str:
    return os.environ.get(CONNECTION_VARIABLE, DEFAULT_CONNECTION)


def connect(name: str, timeout: float) -> Any:
    """Open a Snowflake connection through the connector's named-connection configuration."""
    try:
        import snowflake.connector
    except ImportError as error:
        raise DataError(
            "snowflake-connector-python is not installed; run: uv sync --locked --extra snowflake"
        ) from error
    try:
        return snowflake.connector.connect(
            connection_name=name,
            login_timeout=int(timeout),
            network_timeout=int(timeout),
            session_parameters={"QUERY_TAG": QUERY_TAG, "STATEMENT_TIMEOUT_IN_SECONDS": int(timeout)},
        )
    except snowflake.connector.errors.Error as error:
        raise DataError(f"Snowflake connection {name!r} failed: {error}") from error


def _connector_error(error: BaseException) -> bool:
    return type(error).__module__.startswith("snowflake.")


def query_definition(catalog: dict[str, Any], dataset_id: str) -> dict[str, Any]:
    definition = dataset(catalog, dataset_id)
    provider = source(catalog, definition["source_id"])
    if "queries" not in provider or definition.get("query_ids") != [QUERY_ID]:
        raise DataError(f"dataset is not a Snowflake query dataset: {dataset_id}")
    return next(item for item in provider["queries"] if item["id"] == QUERY_ID)


def read_sql(query: dict[str, Any]) -> str:
    try:
        return (DATA_DIR / query["sql"]).read_text(encoding="utf-8")
    except OSError as error:
        raise DataError(f"missing query text: {query['sql']}") from error


def resolve_parameters(parameters: dict[str, str] | None) -> dict[str, str]:
    values = dict(parameters or {})
    unknown = sorted(set(values) - {"start", "end"})
    if unknown:
        raise DataError(f"unknown parameters: {', '.join(unknown)}; expected start and end dates")
    today = datetime.now(timezone.utc).date()
    resolved = {"start": values.get("start", GENESIS_DATE), "end": values.get("end", (today + timedelta(days=1)).isoformat())}
    bounds: dict[str, date] = {}
    for key, text in resolved.items():
        try:
            bounds[key] = date.fromisoformat(text)
        except ValueError as error:
            raise DataError(f"{key} must be an ISO date (YYYY-MM-DD): {text}") from error
    if bounds["start"] >= bounds["end"]:
        raise DataError(f"start must precede end: {resolved['start']} >= {resolved['end']}")
    return {key: bounds[key].isoformat() for key in ("start", "end")}


def capture_preview(
    dataset_id: str,
    output: Path,
    parameters: dict[str, str] | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    query = query_definition(catalog, dataset_id)
    sql_text = read_sql(query)
    return {
        "dataset_id": dataset_id,
        "source_id": SOURCE_ID,
        "output": str(output),
        "connection": connection_name(),
        "query_id": QUERY_ID,
        "sql": query["sql"],
        "sql_sha256": sha256(sql_text.encode()),
        "parameters": resolve_parameters(parameters),
        "writes": [f"raw/{QUERY_ID}.sql", f"raw/{QUERY_ID}.jsonl.gz", "capture.json"],
        "overwrite": False,
    }


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        spec = "seconds" if value.microsecond == 0 else "microseconds"
        return value.isoformat(timespec=spec) + "Z"
    if isinstance(value, date):
        return value.isoformat()
    raise DataError(f"unsupported value type from Snowflake: {type(value).__name__}")


def _session(connection: Any) -> dict[str, Any]:
    cursor = connection.cursor()
    try:
        cursor.execute(SESSION_SQL)
        role, warehouse, database, schema, version = cursor.fetchall()[0]
    finally:
        cursor.close()
    return {"role": role, "warehouse": warehouse, "database": database, "schema": schema, "server_version": version}


def capture(
    dataset_id: str,
    output: Path,
    timeout: float = 20,
    parameters: dict[str, str] | None = None,
    catalog: dict[str, Any] | None = None,
    connector: Callable[[str, float], Any] = connect,
) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    preview = capture_preview(dataset_id, output, parameters, catalog)
    sql_text = read_sql(query_definition(catalog, dataset_id))
    if output.exists():
        raise DataError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        raw = temporary / "raw"
        raw.mkdir()
        sql_path = raw / f"{QUERY_ID}.sql"
        rows_path = raw / f"{QUERY_ID}.jsonl.gz"
        sql_path.write_text(sql_text, encoding="utf-8")
        started_at = now()
        connection = connector(preview["connection"], timeout)
        try:
            session = _session(connection)
            cursor = connection.cursor()
            try:
                cursor.execute(sql_text, preview["parameters"])
                columns = tuple(item[0].lower() for item in cursor.description)
                if columns != RAW_COLUMNS:
                    raise DataError(f"query returned unexpected columns: {', '.join(columns)}")
                rows = 0
                with rows_path.open("wb") as file, gzip.GzipFile(fileobj=file, mode="wb", mtime=0) as handle:
                    while batch := cursor.fetchmany(FETCH_SIZE):
                        for record in batch:
                            values = dict(zip(columns, (_json_value(value) for value in record)))
                            handle.write((json.dumps(values, ensure_ascii=False, sort_keys=True) + "\n").encode())
                            rows += 1
                snowflake_query_id = cursor.sfqid
            finally:
                cursor.close()
        finally:
            connection.close()
        completed_at = now()
        body = rows_path.read_bytes()
        record = {
            "query_id": QUERY_ID,
            "sql_path": f"raw/{sql_path.name}",
            "sql_sha256": preview["sql_sha256"],
            "parameters": preview["parameters"],
            "snowflake_query_id": snowflake_query_id,
            "started_at": started_at,
            "completed_at": completed_at,
            "columns": list(columns),
            "rows": rows,
            "path": f"raw/{rows_path.name}",
            "bytes": len(body),
            "sha256": sha256(body),
        }
        identity = sha256(canonical_bytes({"completed_at": completed_at, "queries": [record]}))
        receipt = {
            "schema_version": "snowflake-capture/v1",
            "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
            "dataset_id": dataset_id,
            "source_id": SOURCE_ID,
            "completed_at": completed_at,
            "catalog_sha256": catalog_hash(catalog),
            "tool": f"avalanche-research@{__version__}",
            "session": session,
            "queries": [record],
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        os.replace(temporary, output)
    except Exception as error:
        shutil.rmtree(temporary, ignore_errors=True)
        if _connector_error(error):
            raise DataError(f"Snowflake query failed: {error}") from error
        raise
    return receipt


def read_capture(capture_dir: Path, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verify a capture's receipt, query text, and result hash, and return the receipt."""
    catalog = catalog or load_catalog()
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid capture receipt: {error}") from error
    if receipt.get("schema_version") != "snowflake-capture/v1":
        raise DataError("unsupported capture receipt schema")
    if receipt.get("catalog_sha256") != catalog_hash(catalog):
        raise DataError("capture catalog hash differs from the current data contract")
    if len(receipt.get("queries", [])) != 1 or receipt["queries"][0].get("query_id") != QUERY_ID:
        raise DataError("capture does not contain the expected query")
    record = receipt["queries"][0]
    current_sql = read_sql(query_definition(catalog, receipt["dataset_id"]))
    try:
        captured_sql = (capture_dir / record["sql_path"]).read_bytes()
        body = (capture_dir / record["path"]).read_bytes()
    except (OSError, KeyError) as error:
        raise DataError(f"missing captured query output: {error}") from error
    if sha256(captured_sql) != record.get("sql_sha256") or captured_sql != current_sql.encode():
        raise DataError("captured query text differs from the current data contract")
    if sha256(body) != record.get("sha256") or len(body) != record.get("bytes"):
        raise DataError(f"captured result hash or size differs: {record['path']}")
    if tuple(record.get("columns", ())) != RAW_COLUMNS or not isinstance(record.get("rows"), int):
        raise DataError("captured result columns differ from the data contract")
    return receipt


TRANSFORM_SQL = """
SELECT
  transaction_hash,
  accepted_at,
  block_height,
  tx_type,
  node_id,
  start_time,
  end_time,
  date_diff('second', start_time, end_time)::DOUBLE / 86400 AS duration_days,
  stake_navax,
  stake_navax::DOUBLE / 1e9 AS stake_avax,
  delegation_fee_shares,
  delegation_fee_shares::DOUBLE / 1e6 AS delegation_fee_rate,
  potential_reward_navax,
  potential_reward_navax::DOUBLE / 1e9 AS potential_reward_avax,
  rewarded,
  staked_utxo_count,
  utxo_stake_navax
FROM capture
ORDER BY accepted_at, transaction_hash
"""


def load_capture(connection: Any, capture_dir: Path, receipt: dict[str, Any]) -> None:
    """Read the compressed capture into DuckDB with the declared types and build the typed rows table."""
    record = receipt["queries"][0]
    declared = ", ".join(f"{name}: '{kind}'" for name, kind in RAW_COLUMNS_TYPES.items())
    typed = ", ".join(f"{name} {kind}" for name, kind in TABLE_COLUMNS.items())
    path = str(capture_dir / record["path"]).replace("'", "''")
    try:
        connection.execute(
            f"CREATE VIEW capture AS SELECT * FROM read_json('{path}', columns={{{declared}}}, format='newline_delimited')"
        )
        connection.execute(f"CREATE TABLE rows({typed})")
        connection.execute(f"INSERT INTO rows {TRANSFORM_SQL}")
        count = connection.execute("SELECT COUNT(*) FROM rows").fetchone()[0]
    except duckdb.Error as error:
        raise DataError(f"captured rows do not match the declared types: {error}") from error
    if count != record["rows"]:
        raise DataError(f"captured result holds {count} rows, receipt declares {record['rows']}")
    invalid = connection.execute(
        """
        SELECT COUNT_IF(transaction_hash IS NULL OR transaction_hash = '' OR node_id IS NULL OR node_id = ''
                        OR accepted_at IS NULL OR start_time IS NULL OR end_time IS NULL OR block_height IS NULL
                        OR stake_navax IS NULL OR delegation_fee_shares IS NULL OR staked_utxo_count IS NULL),
               COUNT_IF(tx_type IS NULL OR tx_type NOT IN (?, ?)),
               COUNT_IF(stake_navax < 0 OR delegation_fee_shares < 0 OR potential_reward_navax < 0
                        OR staked_utxo_count < 0 OR utxo_stake_navax < 0)
        FROM rows
        """,
        list(VALIDATOR_TYPES),
    ).fetchone()
    for failed, label in zip(invalid, ("miss a required field", "are not validator transactions", "carry a negative amount")):
        if failed:
            raise DataError(f"{failed} captured rows {label}")


def summarize(connection: Any) -> dict[str, Any]:
    record = connection.execute(
        """
        SELECT COUNT(*), MIN(accepted_at), MAX(accepted_at),
               COUNT_IF(tx_type = ?), COUNT_IF(tx_type = ?), COUNT(DISTINCT node_id),
               COUNT_IF(staked_utxo_count = 0), COUNT_IF(rewarded IS NULL), COUNT_IF(potential_reward_navax IS NULL)
        FROM rows
        """,
        list(VALIDATOR_TYPES),
    ).fetchone()
    return {
        "rows": record[0],
        "accepted_from": _json_value(record[1]),
        "accepted_to": _json_value(record[2]),
        "rows_by_tx_type": dict(zip(VALIDATOR_TYPES, record[3:5])),
        "distinct_node_ids": record[5],
        "rows_without_staked_utxo": record[6],
        "rows_without_reward_status": record[7],
        "rows_without_potential_reward": record[8],
    }


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    catalog = load_catalog()
    query_definition(catalog, dataset_id)
    return {
        "dataset_id": dataset_id,
        "capture": str(capture_dir),
        "output": str(output),
        "writes": [f"{QUERY_ID}.parquet", "build.json"],
        "overwrite": False,
    }


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    query_definition(catalog, dataset_id)
    receipt = read_capture(capture_dir, catalog)
    if receipt["dataset_id"] != dataset_id:
        raise DataError(f"capture belongs to {receipt['dataset_id']}, not {dataset_id}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet_path = temporary / f"{QUERY_ID}.parquet"
        connection = duckdb.connect()
        try:
            load_capture(connection, capture_dir, receipt)
            connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection)
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "snowflake-build/v1",
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


def read_parquet(path: Path) -> list[dict[str, Any]]:
    columns = list(TABLE_COLUMNS)
    connection = duckdb.connect()
    try:
        records = connection.execute(
            f"SELECT {', '.join(columns)} FROM read_parquet(?) ORDER BY accepted_at, transaction_hash", [str(path)]
        ).fetchall()
    finally:
        connection.close()
    return [dict(zip(columns, (_json_value(value) for value in record))) for record in records]


def check(capture_dir: Path, dataset_dir: Path | None = None) -> dict[str, Any]:
    catalog = load_catalog()
    receipt = read_capture(capture_dir, catalog)
    window = receipt["queries"][0]["parameters"]
    findings: list[str] = []
    checked = [
        "capture hashes", "query text", "field types", "unique transaction hashes", "acceptance window",
        "time ordering", "duration bounds", "stake bounds", "delegation fee bounds", "staked-UTXO reconciliation",
    ]
    connection = duckdb.connect()
    try:
        load_capture(connection, capture_dir, receipt)
        counts = connection.execute(
            """
            SELECT COUNT(*) - COUNT(DISTINCT transaction_hash),
                   COUNT_IF(accepted_at::DATE < ?::DATE OR accepted_at::DATE >= ?::DATE),
                   COUNT_IF(start_time < accepted_at OR end_time <= start_time),
                   COUNT_IF(duration_days < ? OR duration_days > ?),
                   COUNT_IF(stake_navax < ? OR stake_navax > ?),
                   COUNT_IF(delegation_fee_shares < ? OR delegation_fee_shares > ?),
                   COUNT_IF(utxo_stake_navax IS NOT NULL AND utxo_stake_navax <> stake_navax)
            FROM rows
            """,
            [window["start"], window["end"], *DURATION_DAYS, *STAKE_NAVAX, *FEE_SHARES],
        ).fetchone()
        labels = (
            "repeat a transaction hash",
            "were accepted outside the requested window",
            "start before acceptance or end before start",
            "have a duration outside 14 to 365 days",
            "have a stake outside 2,000 to 3,000,000 AVAX",
            "have a delegation fee outside 2% to 100%",
            "have staked UTXOs that do not sum to the declared stake",
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
                parquet = str(dataset_dir / f"{QUERY_ID}.parquet")
                schema = connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [parquet]).fetchall()
                if [(item[0], item[1]) for item in schema] != list(TABLE_COLUMNS.items()):
                    findings.append("Parquet schema differs from the dataset contract")
                else:
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
