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
RAW_COLUMNS = (
    "transaction_hash", "accepted_at", "block_height", "tx_type", "node_id", "start_time", "end_time",
    "stake_navax", "delegation_fee_shares", "potential_reward_navax", "rewarded",
    "staked_utxo_count", "utxo_stake_navax",
)
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


def read_capture(
    capture_dir: Path,
    catalog: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
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
    try:
        lines = gzip.decompress(body).decode("utf-8").splitlines()
        rows = [json.loads(line) for line in lines]
    except (OSError, ValueError) as error:
        raise DataError(f"captured result is not compressed JSON lines: {error}") from error
    if len(rows) != record.get("rows") or tuple(record.get("columns", ())) != RAW_COLUMNS:
        raise DataError("captured result rows or columns differ from the receipt")
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or tuple(sorted(row)) != tuple(sorted(RAW_COLUMNS)):
            raise DataError(f"captured row {index} has unexpected fields")
    return receipt, rows


def _text(row: dict[str, Any], field: str) -> str:
    value = row[field]
    if not isinstance(value, str) or not value:
        raise DataError(f"{field} must be a non-empty string")
    return value


def _integer(row: dict[str, Any], field: str, nullable: bool = False, minimum: int | None = 0) -> int | None:
    value = row[field]
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise DataError(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        raise DataError(f"{field} has an invalid value: {value}")
    return value


def _timestamp(row: dict[str, Any], field: str) -> str:
    value = row[field]
    try:
        if not isinstance(value, str) or not value.endswith("Z"):
            raise ValueError(value)
        datetime.fromisoformat(value[:-1])
    except ValueError as error:
        raise DataError(f"{field} must be an ISO 8601 UTC timestamp") from error
    return value


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1]).replace(tzinfo=timezone.utc)


def transform_row(raw: dict[str, Any]) -> dict[str, Any]:
    tx_type = _text(raw, "tx_type")
    if tx_type not in VALIDATOR_TYPES:
        raise DataError(f"tx_type is not a validator transaction: {tx_type}")
    rewarded = raw["rewarded"]
    if rewarded is not None and not isinstance(rewarded, bool):
        raise DataError("rewarded must be a boolean or null")
    start_time = _timestamp(raw, "start_time")
    end_time = _timestamp(raw, "end_time")
    stake_navax = _integer(raw, "stake_navax")
    delegation_fee_shares = _integer(raw, "delegation_fee_shares")
    potential_reward_navax = _integer(raw, "potential_reward_navax", nullable=True)
    return {
        "transaction_hash": _text(raw, "transaction_hash"),
        "accepted_at": _timestamp(raw, "accepted_at"),
        "block_height": _integer(raw, "block_height", minimum=None),
        "tx_type": tx_type,
        "node_id": _text(raw, "node_id"),
        "start_time": start_time,
        "end_time": end_time,
        "duration_days": (_instant(end_time) - _instant(start_time)).total_seconds() / 86_400,
        "stake_navax": stake_navax,
        "stake_avax": stake_navax / NAVAX_PER_AVAX,
        "delegation_fee_shares": delegation_fee_shares,
        "delegation_fee_rate": delegation_fee_shares / FEE_SHARES_PER_UNIT,
        "potential_reward_navax": potential_reward_navax,
        "potential_reward_avax": None if potential_reward_navax is None else potential_reward_navax / NAVAX_PER_AVAX,
        "rewarded": rewarded,
        "staked_utxo_count": _integer(raw, "staked_utxo_count"),
        "utxo_stake_navax": _integer(raw, "utxo_stake_navax", nullable=True),
    }


def transform(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [transform_row(row) for row in rows]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [row["accepted_at"] for row in rows]
    return {
        "rows": len(rows),
        "accepted_from": min(accepted) if accepted else None,
        "accepted_to": max(accepted) if accepted else None,
        "rows_by_tx_type": {kind: sum(row["tx_type"] == kind for row in rows) for kind in VALIDATOR_TYPES},
        "distinct_node_ids": len({row["node_id"] for row in rows}),
        "rows_without_staked_utxo": sum(row["staked_utxo_count"] == 0 for row in rows),
        "rows_without_reward_status": sum(row["rewarded"] is None for row in rows),
        "rows_without_potential_reward": sum(row["potential_reward_navax"] is None for row in rows),
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
    receipt, raw_rows = read_capture(capture_dir, catalog)
    if receipt["dataset_id"] != dataset_id:
        raise DataError(f"capture belongs to {receipt['dataset_id']}, not {dataset_id}")
    rows = transform(raw_rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet_path = temporary / f"{QUERY_ID}.parquet"
        write_parquet(rows, parquet_path)
        build_receipt = {
            "schema_version": "snowflake-build/v1",
            "dataset_id": dataset_id,
            "dataset_schema": definition["fields"],
            "source_capture_id": receipt["capture_id"],
            "completed_at": now(),
            "tool": f"avalanche-research@{__version__}",
            "summary": summarize(rows),
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


def write_parquet(rows: list[dict[str, Any]], path: Path) -> None:
    """Write typed rows to Parquet by loading a temporary JSON lines file into DuckDB in one statement."""
    timestamps = {name for name, kind in TABLE_COLUMNS.items() if kind == "TIMESTAMP"}
    staging = path.with_suffix(".jsonl")
    with staging.open("w", encoding="utf-8") as handle:
        for row in rows:
            record = {name: (row[name][:-1] if name in timestamps and row[name] is not None else row[name]) for name in TABLE_COLUMNS}
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    declared = ", ".join(f"{name}: '{kind}'" for name, kind in TABLE_COLUMNS.items())
    connection = duckdb.connect()
    try:
        connection.execute(
            f"CREATE TABLE validator_stakes AS SELECT * FROM read_json(?, columns={{{declared}}}, format='newline_delimited')",
            [str(staging)],
        )
        connection.execute("COPY validator_stakes TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(path)])
    finally:
        connection.close()
        staging.unlink(missing_ok=True)


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
    receipt, raw_rows = read_capture(capture_dir, catalog)
    rows = transform(raw_rows)
    window = receipt["queries"][0]["parameters"]
    findings: list[str] = []
    checked = [
        "capture hashes", "query text", "field types", "unique transaction hashes", "acceptance window",
        "time ordering", "duration bounds", "stake bounds", "delegation fee bounds", "staked-UTXO reconciliation",
    ]

    def count(label: str, failed: int) -> None:
        if failed:
            findings.append(f"{failed} rows {label}")

    hashes = [row["transaction_hash"] for row in rows]
    count("repeat a transaction hash", len(hashes) - len(set(hashes)))
    count("were accepted outside the requested window", sum(
        not (window["start"] <= row["accepted_at"][:10] < window["end"]) for row in rows
    ))
    count("start before acceptance or end before start", sum(
        row["start_time"] < row["accepted_at"] or row["end_time"] <= row["start_time"] for row in rows
    ))
    count("have a duration outside 14 to 365 days", sum(
        not DURATION_DAYS[0] <= row["duration_days"] <= DURATION_DAYS[1] for row in rows
    ))
    count("have a stake outside 2,000 to 3,000,000 AVAX", sum(
        not STAKE_NAVAX[0] <= row["stake_navax"] <= STAKE_NAVAX[1] for row in rows
    ))
    count("have a delegation fee outside 2% to 100%", sum(
        not FEE_SHARES[0] <= row["delegation_fee_shares"] <= FEE_SHARES[1] for row in rows
    ))
    count("have staked UTXOs that do not sum to the declared stake", sum(
        row["utxo_stake_navax"] is not None and row["utxo_stake_navax"] != row["stake_navax"] for row in rows
    ))
    if dataset_dir is not None:
        checked.extend(["build hashes", "Parquet rows"])
        try:
            build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
            for item in build_receipt["outputs"]:
                body = (dataset_dir / item["path"]).read_bytes()
                if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                    findings.append(f"output hash or size differs: {item['path']}")
            expected = sorted(rows, key=lambda row: (row["accepted_at"], row["transaction_hash"]))
            if read_parquet(dataset_dir / f"{QUERY_ID}.parquet") != expected:
                findings.append("Parquet rows differ from the captured inputs")
        except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid dataset output: {error}")
    return {
        "dataset_id": receipt["dataset_id"],
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summarize(rows),
        "findings": findings,
    }
