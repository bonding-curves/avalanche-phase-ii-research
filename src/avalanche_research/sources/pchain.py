"""Avalanche P-Chain RPC datasets: the current Primary Network validator snapshot."""

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


DATASET_ID = "p-chain-rpc.current-validators"
ENDPOINT_ID = "current-validators"
TABLE = "current-validators"
TABLE_COLUMNS = {
    "observed_at": "TIMESTAMP",
    "node_id": "VARCHAR",
    "transaction_hash": "VARCHAR",
    "start_time": "TIMESTAMP",
    "end_time": "TIMESTAMP",
    "stake_navax": "BIGINT",
    "stake_avax": "DOUBLE",
    "delegation_fee_rate": "DOUBLE",
    "uptime": "DOUBLE",
    "connected": "BOOLEAN",
    "delegator_count": "INTEGER",
    "delegator_weight_navax": "BIGINT",
    "potential_reward_navax": "BIGINT",
    "accrued_delegatee_reward_navax": "BIGINT",
    "validation_reward_address": "VARCHAR",
    "delegation_reward_address": "VARCHAR",
}
VALIDATOR_STRUCT = (
    "STRUCT(txID VARCHAR, startTime VARCHAR, endTime VARCHAR, weight VARCHAR, nodeID VARCHAR, "
    "validationRewardOwner STRUCT(addresses VARCHAR[]), delegationRewardOwner STRUCT(addresses VARCHAR[]), "
    "potentialReward VARCHAR, accruedDelegateeReward VARCHAR, delegationFee VARCHAR, uptime VARCHAR, connected BOOLEAN, "
    "delegatorCount VARCHAR, delegatorWeight VARCHAR)[]"
)


def load_capture(connection: Any, capture_dir: Path, receipt: dict[str, Any]) -> None:
    """Read the captured JSON-RPC response and build the typed validator table in DuckDB."""
    record = next(item for item in receipt["responses"] if item["endpoint_id"] == ENDPOINT_ID)
    path = str(capture_dir / record["path"]).replace("'", "''")
    typed = ", ".join(f"{name} {kind}" for name, kind in TABLE_COLUMNS.items())
    observed_at = receipt["completed_at"].replace("Z", "")
    try:
        connection.execute(
            f"CREATE VIEW capture AS SELECT unnest(result.validators) AS v "
            f"FROM read_json('{path}', columns={{result: 'STRUCT(validators {VALIDATOR_STRUCT})'}})"
        )
        connection.execute(f"CREATE TABLE rows({typed})")
        connection.execute(
            f"""
            INSERT INTO rows
            SELECT TIMESTAMP '{observed_at}', v.nodeID, v.txID,
                   make_timestamp(v.startTime::BIGINT * 1000000), make_timestamp(v.endTime::BIGINT * 1000000),
                   v.weight::BIGINT, v.weight::BIGINT::DOUBLE / 1e9,
                   v.delegationFee::DOUBLE / 100, v.uptime::DOUBLE / 100, v.connected,
                   v.delegatorCount::INTEGER, v.delegatorWeight::BIGINT, v.potentialReward::BIGINT, v.accruedDelegateeReward::BIGINT,
                   v.validationRewardOwner.addresses[1], v.delegationRewardOwner.addresses[1]
            FROM capture
            ORDER BY v.startTime::BIGINT, v.nodeID
            """
        )
        counts = connection.execute(
            "SELECT COUNT(*), COUNT_IF(node_id IS NULL OR transaction_hash IS NULL OR start_time IS NULL OR end_time IS NULL OR stake_navax IS NULL OR uptime IS NULL OR delegation_fee_rate IS NULL) FROM rows"
        ).fetchone()
    except duckdb.Error as error:
        raise DataError(f"captured response does not match the declared shape: {error}") from error
    if counts[0] == 0:
        raise DataError("captured response holds no validators")
    if counts[1]:
        raise DataError(f"{counts[1]} validators miss a required field")


def summarize(connection: Any) -> dict[str, Any]:
    record = connection.execute(
        """
        SELECT COUNT(*), MAX(observed_at), SUM(stake_navax), SUM(delegator_weight_navax), SUM(delegator_count),
               COUNT_IF(connected), median(uptime), MIN(uptime), COUNT_IF(uptime < 0.8), COUNT_IF(uptime < 0.9),
               median(delegation_fee_rate), COUNT_IF(delegator_count = 0)
        FROM rows
        """
    ).fetchone()
    return {
        "rows": record[0],
        "observed_at": record[1].isoformat(timespec="seconds") + "Z",
        "validator_stake_navax_total": record[2],
        "delegator_weight_navax_total": record[3],
        "delegations_total": record[4],
        "connected_validators": record[5],
        "uptime_median": record[6],
        "uptime_min": record[7],
        "validators_below_80_percent_uptime": record[8],
        "validators_below_90_percent_uptime": record[9],
        "delegation_fee_rate_median": record[10],
        "validators_without_delegations": record[11],
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
            "schema_version": "p-chain-rpc-build/v1",
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


def reconcile(connection: Any, reference_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Reconcile the snapshot against the Snowflake validator dataset by staking transaction hash."""
    parquet = reference_dir / "primary-validator-stakes.parquet"
    if not parquet.is_file():
        raise DataError(f"missing reference validator dataset: {parquet}")
    record = connection.execute(
        f"""
        WITH reference AS (SELECT transaction_hash, node_id, start_time, end_time, stake_navax, delegation_fee_rate, MAX(accepted_at) OVER () AS latest
                           FROM read_parquet('{str(parquet).replace("'", "''")}'))
        SELECT COUNT(*),
               COUNT(x.transaction_hash),
               COUNT_IF(x.transaction_hash IS NULL AND r.start_time <= (SELECT MAX(latest) FROM reference)),
               COUNT_IF(x.transaction_hash IS NOT NULL AND (x.node_id <> r.node_id OR x.start_time <> r.start_time OR x.end_time <> r.end_time OR x.stake_navax <> r.stake_navax)),
               COUNT_IF(x.transaction_hash IS NOT NULL AND abs(x.delegation_fee_rate - r.delegation_fee_rate) > 1e-9)
        FROM rows r LEFT JOIN reference x USING (transaction_hash)
        """
    ).fetchone()
    summary = {
        "reconciled_validators": record[0],
        "matched_in_reference": record[1],
        "missing_from_reference_before_its_last_row": record[2],
        "matched_with_different_period_or_stake": record[3],
        "matched_with_different_fee": record[4],
    }
    findings = []
    if record[2]:
        findings.append(f"{record[2]} validators started before the reference dataset's last row but are absent from it")
    if record[3]:
        findings.append(f"{record[3]} validators disagree with the reference on node, period, or stake")
    if record[4]:
        findings.append(f"{record[4]} validators disagree with the reference on delegation fee")
    return summary, findings


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    catalog = load_catalog()
    receipt, _ = read_capture(capture_dir, catalog)
    findings: list[str] = []
    checked = ["capture hashes", "required endpoints", "response shape", "unique validators", "period ordering", "stake bounds", "fee bounds", "uptime bounds"]
    connection = duckdb.connect()
    try:
        load_capture(connection, capture_dir, receipt)
        counts = connection.execute(
            """
            SELECT (COUNT(*) - COUNT(DISTINCT node_id)) + (COUNT(*) - COUNT(DISTINCT transaction_hash)),
                   COUNT_IF(end_time <= start_time OR start_time > observed_at OR end_time < observed_at),
                   COUNT_IF(stake_navax < 2000000000000 OR stake_navax > 3000000000000000),
                   COUNT_IF(delegation_fee_rate < 0.02 OR delegation_fee_rate > 1),
                   COUNT_IF(uptime < 0 OR uptime > 1)
            FROM rows
            """
        ).fetchone()
        labels = (
            "repeat a node or transaction",
            "have a period that does not contain the observation time",
            "have a stake outside 2,000 to 3,000,000 AVAX",
            "have a delegation fee outside 2% to 100%",
            "have an uptime outside 0 to 1",
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
            checked.append("Snowflake validator reconciliation")
            reconciliation, reconciliation_findings = reconcile(connection, against)
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
