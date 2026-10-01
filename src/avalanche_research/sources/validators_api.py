"""Avalanche Data API validator datasets: the active set with uptime and capacity, and the completed history with rewards.

Both come from one paginated endpoint, ``/v1/networks/mainnet/validators``, filtered by ``validationStatus``. The active
snapshot is a second observer of uptime beside the P-Chain RPC snapshot, and adds delegation capacity, health, version,
geolocation, and staking type. The completed history carries every finished validation's reward addresses and reward
amounts, which cross-check the Snowflake captures.
"""

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

ACTIVE_ID = "data-api.validators-active"
COMPLETED_ID = "data-api.validators-completed"
RECENT_ID = "data-api.validators-completed-recent"
DATASET_IDS = (ACTIVE_ID, COMPLETED_ID, RECENT_ID)
ENDPOINTS = {ACTIVE_ID: "validators-active", COMPLETED_ID: "validators-completed", RECENT_ID: "validators-completed-recent"}
TABLES = {ACTIVE_ID: "validators-active", COMPLETED_ID: "validators-completed", RECENT_ID: "validators-completed-recent"}
SWEEP_DAYS = 30
NAVAX = 1_000_000_000
# MaxValidatorWeightFactor in avalanchego is five, so capacity is four times own stake (glossary G24). The API reports
# the remaining capacity, and fill is derived from it.
CAPACITY_MULTIPLE = 4

COMMON_COLUMNS = {
    "observed_at": "TIMESTAMP", "transaction_hash": "VARCHAR", "node_id": "VARCHAR", "validation_status": "VARCHAR", "staking_type": "VARCHAR",
    "start_time": "TIMESTAMP", "end_time": "TIMESTAMP", "stake_navax": "BIGINT", "stake_avax": "DOUBLE",
    "delegation_fee_rate": "DOUBLE", "delegator_count": "INTEGER", "delegated_navax": "BIGINT", "delegated_avax": "DOUBLE",
}
ACTIVE_COLUMNS = {
    **COMMON_COLUMNS,
    "uptime_performance_pct": "DOUBLE", "reachability_pct": "DOUBLE", "benched_p_chain_pct": "DOUBLE", "benched_x_chain_pct": "DOUBLE", "benched_c_chain_pct": "DOUBLE",
    "delegation_capacity_navax": "BIGINT", "delegation_fill": "DOUBLE", "stake_percentage": "DOUBLE",
    "potential_validation_reward_navax": "BIGINT", "potential_delegation_reward_navax": "BIGINT",
    "node_version": "VARCHAR", "country": "VARCHAR", "city": "VARCHAR", "latitude": "DOUBLE", "longitude": "DOUBLE",
}
COMPLETED_COLUMNS = {
    **COMMON_COLUMNS,
    "validation_reward_navax": "BIGINT", "delegation_reward_navax": "BIGINT", "reward_address": "VARCHAR", "reward_address_count": "INTEGER", "reward_transaction_hash": "VARCHAR",
}
TABLE_COLUMNS = {ACTIVE_ID: ACTIVE_COLUMNS, COMPLETED_ID: COMPLETED_COLUMNS, RECENT_ID: COMPLETED_COLUMNS}

VALIDATOR_STRUCT = """STRUCT(
    txHash VARCHAR, nodeId VARCHAR, subnetId VARCHAR, validationStatus VARCHAR, stakingType VARCHAR,
    startTimestamp BIGINT, endTimestamp BIGINT, amountStaked VARCHAR, delegationFee VARCHAR, delegatorCount BIGINT, amountDelegated VARCHAR,
    uptimePerformance DOUBLE, delegationCapacity VARCHAR, stakePercentage DOUBLE, avalancheGoVersion VARCHAR,
    validatorHealth STRUCT(reachabilityPercent DOUBLE, benchedPChainRequestsPercent DOUBLE, benchedXChainRequestsPercent DOUBLE, benchedCChainRequestsPercent DOUBLE),
    geolocation STRUCT(city VARCHAR, country VARCHAR, latitude DOUBLE, longitude DOUBLE),
    potentialRewards STRUCT(validationRewardAmount VARCHAR, delegationRewardAmount VARCHAR),
    rewards STRUCT(validationRewardAmount VARCHAR, delegationRewardAmount VARCHAR, rewardAddresses VARCHAR[], rewardTxHash VARCHAR)
)"""

COMMON_SELECT = """
    TIMESTAMP '{observed_at}', v.txHash, v.nodeId, v.validationStatus, v.stakingType,
    make_timestamp(v.startTimestamp * 1000000), make_timestamp(v.endTimestamp * 1000000),
    v.amountStaked::BIGINT, v.amountStaked::BIGINT::DOUBLE / 1e9,
    v.delegationFee::DOUBLE / 100, v.delegatorCount::INTEGER, v.amountDelegated::BIGINT, v.amountDelegated::BIGINT::DOUBLE / 1e9"""
ACTIVE_SELECT = COMMON_SELECT + f""",
    v.uptimePerformance, v.validatorHealth.reachabilityPercent, v.validatorHealth.benchedPChainRequestsPercent, v.validatorHealth.benchedXChainRequestsPercent, v.validatorHealth.benchedCChainRequestsPercent,
    v.delegationCapacity::BIGINT,
    CASE WHEN v.amountStaked::BIGINT > 0 THEN v.amountDelegated::BIGINT::DOUBLE / (v.amountStaked::BIGINT * {CAPACITY_MULTIPLE}) END,
    v.stakePercentage,
    v.potentialRewards.validationRewardAmount::BIGINT, v.potentialRewards.delegationRewardAmount::BIGINT,
    v.avalancheGoVersion, v.geolocation.country, v.geolocation.city, v.geolocation.latitude, v.geolocation.longitude"""
COMPLETED_SELECT = COMMON_SELECT + """,
    v.rewards.validationRewardAmount::BIGINT, v.rewards.delegationRewardAmount::BIGINT,
    v.rewards.rewardAddresses[1], coalesce(len(v.rewards.rewardAddresses), 0), v.rewards.rewardTxHash"""
SELECTS = {ACTIVE_ID: ACTIVE_SELECT, COMPLETED_ID: COMPLETED_SELECT, RECENT_ID: COMPLETED_SELECT}
REQUIRED = "transaction_hash IS NULL OR node_id IS NULL OR start_time IS NULL OR end_time IS NULL OR stake_navax IS NULL OR delegation_fee_rate IS NULL"
REQUIRED_EXTRA = {ACTIVE_ID: " OR uptime_performance_pct IS NULL", COMPLETED_ID: " OR validation_reward_navax IS NULL", RECENT_ID: " OR validation_reward_navax IS NULL"}


def _reject(dataset_id: str) -> None:
    if dataset_id not in DATASET_IDS:
        raise DataError(f"unknown dataset: {dataset_id}")


def load_capture(connection: Any, capture_dir: Path, receipt: dict[str, Any]) -> None:
    """Read the captured pages and build the typed validator table in DuckDB. One page per JSON line."""
    dataset_id = receipt["dataset_id"]
    _reject(dataset_id)
    record = next(item for item in receipt["responses"] if item["endpoint_id"] == ENDPOINTS[dataset_id])
    path = str(capture_dir / record["path"]).replace("'", "''")
    typed = ", ".join(f"{name} {kind}" for name, kind in TABLE_COLUMNS[dataset_id].items())
    observed_at = receipt["completed_at"].replace("Z", "")
    try:
        connection.execute(
            f"CREATE VIEW capture AS SELECT unnest(validators) AS v FROM read_json('{path}', columns={{validators: '{VALIDATOR_STRUCT}[]', nextPageToken: 'VARCHAR'}}, format='newline_delimited')"
        )
        connection.execute(f"CREATE TABLE rows({typed})")
        connection.execute(f"INSERT INTO rows SELECT {SELECTS[dataset_id].format(observed_at=observed_at)} FROM capture ORDER BY v.startTimestamp, v.txHash")
        counts = connection.execute(f"SELECT COUNT(*), COUNT_IF({REQUIRED}{REQUIRED_EXTRA[dataset_id]}), COUNT(*) - COUNT(DISTINCT transaction_hash) FROM rows").fetchone()
    except duckdb.Error as error:
        raise DataError(f"captured response does not match the declared shape: {error}") from error
    if counts[0] == 0:
        raise DataError("captured pages hold no validators")
    if counts[1]:
        raise DataError(f"{counts[1]} validators miss a required field")
    if counts[2]:
        raise DataError(f"{counts[2]} validations repeat a transaction hash across pages")


def summarize(connection: Any, dataset_id: str) -> dict[str, Any]:
    if dataset_id == ACTIVE_ID:
        record = connection.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT node_id), MAX(observed_at), SUM(stake_navax), SUM(delegated_navax),
                   median(uptime_performance_pct), COUNT_IF(uptime_performance_pct < 80), COUNT_IF(uptime_performance_pct < 90),
                   COUNT_IF(staking_type = 'autoRenewed'), COUNT_IF(country IS NOT NULL), median(delegation_fill)
            FROM rows
            """
        ).fetchone()
        keys = ("rows", "distinct_nodes", "observed_at", "validator_stake_navax_total", "delegated_navax_total", "uptime_median_pct",
                "validators_below_80_percent_uptime", "validators_below_90_percent_uptime", "auto_renewed_validations", "validators_with_geolocation", "delegation_fill_median")
    else:
        record = connection.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT node_id), MAX(observed_at), MIN(start_time), MAX(end_time), SUM(validation_reward_navax), SUM(delegation_reward_navax),
                   COUNT_IF(validation_reward_navax = 0), COUNT(DISTINCT reward_address), COUNT_IF(reward_address IS NULL), COUNT_IF(reward_address_count > 1),
                   COUNT_IF(reward_transaction_hash IS NULL)
            FROM rows
            """
        ).fetchone()
        keys = ("rows", "distinct_nodes", "observed_at", "earliest_start", "latest_end", "validation_reward_navax_total", "delegation_reward_navax_total",
                "validations_with_zero_reward", "distinct_reward_addresses", "validations_without_reward_address", "validations_with_several_reward_addresses",
                "validations_without_reward_transaction")
    summary = dict(zip(keys, record))
    for key in ("observed_at", "earliest_start", "latest_end"):
        if summary.get(key) is not None:
            summary[key] = summary[key].isoformat(timespec="seconds") + "Z"
    return summary


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    _reject(dataset_id)
    load_catalog()
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{TABLES[dataset_id]}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    _reject(dataset_id)
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
        parquet_path = temporary / f"{TABLES[dataset_id]}.parquet"
        connection = duckdb.connect()
        try:
            load_capture(connection, capture_dir, receipt)
            connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection, dataset_id)
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "avalanche-data-api-build/v1",
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


def reconcile_active(connection: Any, reference_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Two observers of one set: the RPC snapshot's nodes must be present, and uptime and delegated weight must agree."""
    parquet = reference_dir / "current-validators.parquet"
    if not parquet.is_file():
        raise DataError(f"missing reference validator snapshot: {parquet}")
    record = connection.execute(
        """
        WITH api AS (SELECT node_id, max(uptime_performance_pct) AS uptime_pct, sum(delegated_navax) AS delegated FROM rows GROUP BY node_id),
             rpc AS (SELECT node_id, uptime * 100 AS uptime_pct, sum(delegator_weight_navax) AS delegated FROM read_parquet(?) GROUP BY node_id, uptime)
        SELECT (SELECT COUNT(*) FROM rpc), (SELECT COUNT(*) FROM rpc LEFT JOIN api USING (node_id) WHERE api.node_id IS NULL),
               median(abs(api.uptime_pct - rpc.uptime_pct)), max(abs(api.uptime_pct - rpc.uptime_pct)),
               COUNT_IF(api.delegated = rpc.delegated), COUNT(*), sum(api.delegated), sum(rpc.delegated)
        FROM rpc JOIN api USING (node_id)
        """,
        [str(parquet)],
    ).fetchone()
    findings: list[str] = []
    total_api, total_rpc = record[6] or 0, record[7] or 0
    summary = {"rpc_nodes": record[0], "rpc_nodes_missing_from_api": record[1], "uptime_abs_difference_median_pct": record[2], "uptime_abs_difference_max_pct": record[3],
               "delegated_weight_equal": record[4], "nodes_compared": record[5], "delegated_navax_api": total_api, "delegated_navax_rpc": total_rpc}
    if record[1]:
        findings.append(f"{record[1]} RPC validators are absent from the API snapshot")
    if record[2] is not None and record[2] > 1:
        findings.append(f"median uptime disagreement between observers is {record[2]:.2f} points")
    # The two captures are minutes apart and delegations move, so per-node equality is a floor and the total is the check.
    if record[5] and record[4] < 0.85 * record[5]:
        findings.append(f"delegated weight agrees on {record[4]} of {record[5]} nodes, below 85%")
    if total_rpc and abs(total_api - total_rpc) > 0.02 * total_rpc:
        findings.append(f"total delegated weight differs between observers by {abs(total_api - total_rpc) / total_rpc:.2%}")
    return summary, findings


def reconcile_completed(connection: Any, reference_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Every completed validation present in the Snowflake validator capture must name the same first reward address,
    stake, and reward. The API's reward is the potential reward whether or not the validation passed: on 2026-09-22 it
    equalled Snowflake's potential reward on all 56,963 validations, including the 1,397 Snowflake records as unrewarded,
    so pass or fail comes from Snowflake alone. When the delegator capture sits beside the validator capture, the API's
    delegated amount and delegator count must equal the sum and count of every delegation to the validation. When the
    full history's parquet sits there, every validation shared with it must read the same, which is the daily sweep's
    overlap check."""
    parquet = reference_dir / "primary-validator-stakes.parquet"
    history = reference_dir / f"{TABLES[COMPLETED_ID]}.parquet"
    if not parquet.is_file() and not history.is_file():
        raise DataError(f"missing reference validator dataset: {parquet} or {history}")
    findings: list[str] = []
    summary: dict[str, Any] = {}
    if history.is_file():
        # A sweep overlaps the full history. Every shared validation must read the same, apart from the capture time.
        columns = [name for name in COMPLETED_COLUMNS if name != "observed_at"]
        same = " AND ".join(f"r.{name} IS NOT DISTINCT FROM h.{name}" for name in columns)
        record = connection.execute(
            f"SELECT COUNT(*), COUNT_IF({same}), (SELECT COUNT(*) FROM rows WHERE transaction_hash NOT IN (SELECT transaction_hash FROM read_parquet(?)))"
            " FROM rows r JOIN read_parquet(?) h ON h.transaction_hash = r.transaction_hash",
            [str(history), str(history)],
        ).fetchone()
        summary.update({"validations_in_history": record[0], "history_equal": record[1], "validations_new_since_history": record[2]})
        if record[0] and record[1] != record[0]:
            findings.append(f"{record[0] - record[1]} validations read differently from the full history")
    if parquet.is_file():
        record = connection.execute(
            """
            SELECT COUNT(*), COUNT_IF(r.reward_address = s.reward_address), COUNT_IF(r.stake_navax = s.stake_navax),
                   COUNT_IF(r.validation_reward_navax = s.potential_reward_navax), COUNT_IF(NOT s.rewarded)
            FROM rows r JOIN read_parquet(?) s ON s.transaction_hash = r.transaction_hash
            """,
            [str(parquet)],
        ).fetchone()
        summary.update({"validations_in_both": record[0], "reward_address_equal": record[1], "stake_equal": record[2],
                        "reward_equals_potential": record[3], "unrewarded_per_snowflake": record[4]})
        for count, label in zip(record[1:4], ("reward address", "stake", "reward")):
            if record[0] and count != record[0]:
                findings.append(f"{label} differs from the Snowflake capture on {record[0] - count} validations")
    delegators = reference_dir / "primary-delegator-stakes.parquet"
    if delegators.is_file():
        record = connection.execute(
            """
            SELECT COUNT(*), COUNT_IF(r.delegated_navax = d.total AND r.delegator_count = d.n)
            FROM rows r JOIN (SELECT validator_transaction_hash h, SUM(stake_navax) total, COUNT(*) n FROM read_parquet(?) GROUP BY 1) d ON d.h = r.transaction_hash
            """,
            [str(delegators)],
        ).fetchone()
        summary.update({"delegated_validations_in_both": record[0], "delegation_sum_and_count_equal": record[1]})
        if record[0] and record[1] != record[0]:
            findings.append(f"cumulative delegation differs from the Snowflake delegator capture on {record[0] - record[1]} validations")
    return summary, findings


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    catalog = load_catalog()
    receipt, _ = read_capture(capture_dir, catalog)
    dataset_id = receipt["dataset_id"]
    _reject(dataset_id)
    findings: list[str] = []
    checked = ["capture hashes", "required endpoints", "response shape", "unique validations", "period ordering", "stake bounds", "fee bounds"]
    connection = duckdb.connect()
    try:
        load_capture(connection, capture_dir, receipt)
        counts = connection.execute(
            """
            SELECT COUNT_IF(end_time <= start_time),
                   COUNT_IF(stake_navax < 2000000000000 OR stake_navax > 3000000000000000),
                   COUNT_IF(delegation_fee_rate < 0.02 OR delegation_fee_rate > 1)
            FROM rows
            """
        ).fetchone()
        labels = ("end before or at start", "have a stake outside 2,000 to 3,000,000 AVAX", "have a delegation fee outside 2% to 100%")
        for count, label in zip(counts, labels):
            if count:
                findings.append(f"{count} validations {label}")
        if dataset_id == ACTIVE_ID:
            # Only the active row's delegated amount is a concurrent weight. A completed row sums every delegation over the period.
            checked.extend(["capacity bound", "uptime bounds"])
            over, bad = connection.execute(
                "SELECT COUNT_IF(delegated_navax > stake_navax * ?), COUNT_IF(uptime_performance_pct < 0 OR uptime_performance_pct > 100) FROM rows",
                [CAPACITY_MULTIPLE],
            ).fetchone()
            if over:
                findings.append(f"{over} validations carry more delegation than four times their stake")
            if bad:
                findings.append(f"{bad} validations have uptime outside 0 to 100")
        summary = summarize(connection, dataset_id)
        if dataset_id == RECENT_ID:
            checked.append("sweep span")
            days = connection.execute("SELECT date_diff('day', MIN(end_time), MAX(end_time)) FROM rows").fetchone()[0]
            summary["sweep_days"] = days
            if days < SWEEP_DAYS:
                findings.append(f"sweep spans {days} days of end times, fewer than {SWEEP_DAYS}; raise first_pages on the endpoint")
        if dataset_dir is not None:
            checked.append("build hashes")
            try:
                build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
                if build_receipt.get("source_capture_id") != receipt.get("capture_id"):
                    findings.append("build does not belong to this capture")
                for item in build_receipt["outputs"]:
                    body = (dataset_dir / item["path"]).read_bytes()
                    if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                        findings.append(f"output hash or size differs: {item['path']}")
            except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
                findings.append(f"invalid build output: {error}")
        if against is not None:
            checked.append("two-observer reconciliation" if dataset_id == ACTIVE_ID else "completed reconciliation")
            extra, more = (reconcile_active if dataset_id == ACTIVE_ID else reconcile_completed)(connection, against)
            summary.update(extra)
            findings.extend(more)
    finally:
        connection.close()
    return {
        "dataset_id": dataset_id,
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summary,
        "findings": findings,
    }
