"""The node table: one row per Primary Network validator node, every attribute computed once from the staking-period log.

Each column realises one glossary term, named in the catalog's field descriptions. Clocks are clipped at ``as_of``, the
validator capture time, so a node still validating then is right-censored and ``active`` says so. Rewrite the SQL and
the catalog together: the check compares the Parquet columns with the declared fields.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from . import __version__, datasets, seam
from .catalog import DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256

DATASET_ID = "derived.node-table"
DATASET_IDS = (DATASET_ID,)
SOURCE_ID = "derived"
TABLE = "node-table"
INPUTS = {
    "staking-periods": "derived.staking-periods",
    "validator-stakes": "snowflake.primary-validator-stakes",
    "delegator-stakes": "snowflake.primary-delegator-stakes",
}
# Two observers of today's uptime, joined when their runs exist. Neither is the protocol's own view, which is a majority
# vote at period end, so both are kept (node table plan UC1, UC4). Their absence is not an error: history has none.
OPTIONAL_INPUTS = {
    "current-validators": "p-chain-rpc.current-validators",
    "validators-active": "data-api.validators-active",
}
# A gap longer than this between one period's end and the next period's start ends a streak (glossary G8).
STREAK_GAP_DAYS = 1
# MaxValidatorWeightFactor in avalanchego: a validator's total weight may reach five times its own stake, so the
# delegation capacity of one period is four times its stake (glossary G24, node table plan NC3).
DELEGATION_CAPACITY_MULTIPLE = 4

TABLE_COLUMNS = {
    "node_id": "VARCHAR", "as_of": "TIMESTAMP", "first_start": "TIMESTAMP", "last_end": "TIMESTAMP", "active": "BOOLEAN",
    "periods": "BIGINT", "closed_periods": "BIGINT", "failed_periods": "BIGINT",
    "streaks": "BIGINT", "gap_count": "BIGINT", "gap_days": "DOUBLE",
    "span_days": "DOUBLE", "tenure_days": "DOUBLE", "current_streak_days": "DOUBLE",
    "stake_days_avax": "DOUBLE", "stake_weighted_period_days": "DOUBLE",
    "min_stake_avax": "DOUBLE", "max_stake_avax": "DOUBLE", "latest_stake_avax": "DOUBLE",
    "latest_fee_rate": "DOUBLE", "fee_settings": "BIGINT",
    "delegations": "BIGINT", "delegated_avax": "DOUBLE", "delegator_addresses": "BIGINT", "max_period_delegation_ratio": "DOUBLE",
    "rewards_avax": "DOUBLE", "delegatee_fees_avax": "DOUBLE",
    "first_regime": "VARCHAR", "last_regime": "VARCHAR",
    "reward_address": "VARCHAR", "reward_addresses_used": "BIGINT", "operator_group": "VARCHAR",
    "uptime_rpc_pct": "DOUBLE", "uptime_api_pct": "DOUBLE", "uptime_observed_at": "TIMESTAMP",
    "delegation_fill_api": "DOUBLE", "node_version": "VARCHAR", "country": "VARCHAR",
}

# Every interval is clipped at as_of. Streaks are built by numbering the periods whose start lies more than
# STREAK_GAP_DAYS after every earlier period's end. Overlapping periods on one node are merged before tenure is summed.
NODES_SQL = f"""
CREATE OR REPLACE TABLE nodes AS
WITH v AS (
    SELECT p.*, least(p.end_time, ?::TIMESTAMP) AS end_clipped
    FROM periods p WHERE p.role = 'validator' AND p.start_time < ?::TIMESTAMP
),
ordered AS (
    SELECT *, max(end_time) OVER (PARTITION BY node_id ORDER BY start_time, transaction_hash ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prior_end
    FROM v
),
numbered AS (
    SELECT *, sum(CASE WHEN prior_end IS NULL OR start_time > prior_end + INTERVAL {STREAK_GAP_DAYS} DAY THEN 1 ELSE 0 END)
                  OVER (PARTITION BY node_id ORDER BY start_time, transaction_hash) AS streak_no
    FROM ordered
),
streaks AS (
    SELECT node_id, streak_no, min(start_time) AS streak_start, max(end_clipped) AS streak_end,
           lead(min(start_time)) OVER (PARTITION BY node_id ORDER BY streak_no) AS next_start
    FROM numbered GROUP BY node_id, streak_no
),
streak_stats AS (
    SELECT node_id, count(*) AS streaks,
           count(next_start) AS gap_count,
           coalesce(sum(date_diff('second', streak_end, next_start)) / 86400.0, 0) AS gap_days,
           sum(date_diff('second', streak_start, streak_end)) / 86400.0 AS tenure_days,
           arg_max(date_diff('second', streak_start, streak_end), streak_no) / 86400.0 AS current_streak_days
    FROM streaks GROUP BY node_id
),
delegations AS (
    SELECT d.validator_transaction_hash AS vtx, count(*) AS delegations, sum(d.stake_avax) AS delegated_avax,
           count(DISTINCT ds.delegator_address) AS delegator_addresses,
           sum(CASE WHEN d.realized_reward_navax > 0 THEN round(d.potential_reward_navax * v.delegation_fee_rate) ELSE 0 END) / 1e9 AS delegatee_fees_avax
    FROM periods d
    JOIN periods v ON v.transaction_hash = d.validator_transaction_hash AND v.role = 'validator'
    LEFT JOIN delegators ds ON ds.transaction_hash = d.transaction_hash
    WHERE d.role = 'delegator'
    GROUP BY 1
),
per_period AS (
    SELECT n.*, coalesce(dl.delegations, 0) AS delegations, coalesce(dl.delegated_avax, 0) AS delegated_avax,
           coalesce(dl.delegator_addresses, 0) AS delegator_addresses, coalesce(dl.delegatee_fees_avax, 0) AS delegatee_fees_avax,
           vs.reward_address
    FROM numbered n
    LEFT JOIN delegations dl ON dl.vtx = n.transaction_hash
    LEFT JOIN validators vs ON vs.transaction_hash = n.transaction_hash
)
SELECT p.node_id,
       ?::TIMESTAMP AS as_of,
       min(p.start_time) AS first_start,
       max(p.end_time) AS last_end,
       max(p.end_time) > ?::TIMESTAMP AS active,
       sum(p.cycles)::BIGINT AS periods,
       count(*) FILTER (WHERE p.rewarded_at IS NOT NULL) AS closed_periods,
       count(*) FILTER (WHERE p.rewarded_at IS NOT NULL AND p.realized_reward_navax = 0) AS failed_periods,
       any_value(s.streaks) AS streaks,
       any_value(s.gap_count) AS gap_count,
       any_value(s.gap_days) AS gap_days,
       date_diff('second', min(p.start_time), least(max(p.end_time), ?::TIMESTAMP)) / 86400.0 AS span_days,
       any_value(s.tenure_days) AS tenure_days,
       any_value(s.current_streak_days) AS current_streak_days,
       sum(p.stake_avax * date_diff('second', p.start_time, p.end_clipped) / 86400.0) AS stake_days_avax,
       sum(p.stake_avax * date_diff('second', p.start_time, p.end_clipped) / 86400.0) / sum(p.stake_avax) AS stake_weighted_period_days,
       min(p.stake_avax) AS min_stake_avax,
       max(p.stake_avax) AS max_stake_avax,
       arg_max(p.stake_avax, p.start_time) AS latest_stake_avax,
       arg_max(p.delegation_fee_rate, p.start_time) AS latest_fee_rate,
       count(DISTINCT p.delegation_fee_rate) AS fee_settings,
       sum(p.delegations) AS delegations,
       sum(p.delegated_avax) AS delegated_avax,
       sum(p.delegator_addresses) AS delegator_addresses,
       max(p.delegated_avax / (p.stake_avax * {DELEGATION_CAPACITY_MULTIPLE})) AS max_period_delegation_ratio,
       coalesce(sum(p.realized_reward_navax), 0) / 1e9 AS rewards_avax,
       sum(p.delegatee_fees_avax) AS delegatee_fees_avax,
       arg_min(p.regime, p.start_time) AS first_regime,
       arg_max(p.regime, p.start_time) AS last_regime,
       arg_max(p.reward_address, p.start_time) AS reward_address,
       count(DISTINCT p.reward_address) AS reward_addresses_used,
       arg_max(p.reward_address, p.start_time) AS operator_group,
       any_value(o.uptime_rpc_pct) AS uptime_rpc_pct,
       any_value(o.uptime_api_pct) AS uptime_api_pct,
       any_value(o.uptime_observed_at) AS uptime_observed_at,
       any_value(o.delegation_fill_api) AS delegation_fill_api,
       any_value(o.node_version) AS node_version,
       any_value(o.country) AS country
FROM per_period p
JOIN streak_stats s USING (node_id)
LEFT JOIN observers o USING (node_id)
GROUP BY p.node_id
ORDER BY p.node_id
"""

# One row per node from whichever observer runs exist; an empty table when neither does.
OBSERVERS_SQL = {
    "none": "CREATE OR REPLACE TABLE observers(node_id VARCHAR, uptime_rpc_pct DOUBLE, uptime_api_pct DOUBLE, uptime_observed_at TIMESTAMP, delegation_fill_api DOUBLE, node_version VARCHAR, country VARCHAR)",
    "rpc": """CREATE OR REPLACE TABLE observers AS
        SELECT node_id, max(uptime) * 100 AS uptime_rpc_pct, NULL::DOUBLE AS uptime_api_pct, max(observed_at) AS uptime_observed_at,
               NULL::DOUBLE AS delegation_fill_api, NULL::VARCHAR AS node_version, NULL::VARCHAR AS country
        FROM rpc_snapshot GROUP BY node_id""",
    "api": """CREATE OR REPLACE TABLE observers AS
        SELECT node_id, NULL::DOUBLE AS uptime_rpc_pct, max(uptime_performance_pct) AS uptime_api_pct, max(observed_at) AS uptime_observed_at,
               max(delegation_fill) AS delegation_fill_api, any_value(node_version) AS node_version, any_value(country) AS country
        FROM api_snapshot GROUP BY node_id""",
    "both": """CREATE OR REPLACE TABLE observers AS
        WITH r AS (SELECT node_id, max(uptime) * 100 AS uptime_rpc_pct, max(observed_at) AS observed_at FROM rpc_snapshot GROUP BY node_id),
             a AS (SELECT node_id, max(uptime_performance_pct) AS uptime_api_pct, max(observed_at) AS observed_at, max(delegation_fill) AS delegation_fill_api,
                          any_value(node_version) AS node_version, any_value(country) AS country FROM api_snapshot GROUP BY node_id)
        SELECT coalesce(r.node_id, a.node_id) AS node_id, r.uptime_rpc_pct, a.uptime_api_pct, greatest(r.observed_at, a.observed_at) AS uptime_observed_at,
               a.delegation_fill_api, a.node_version, a.country
        FROM r FULL OUTER JOIN a USING (node_id)""",
}

SUMMARY_SQL = """
SELECT count(*), count(DISTINCT node_id), count(*) FILTER (WHERE active), sum(periods), sum(failed_periods),
       count(*) FILTER (WHERE reward_address IS NULL), count(DISTINCT operator_group),
       count(*) FILTER (WHERE tenure_days > span_days + 1e-6 OR current_streak_days > tenure_days + 1e-6),
       round(sum(rewards_avax), 6), round(median(span_days), 2), round(median(tenure_days), 2), round(median(current_streak_days), 2)
FROM nodes
"""
SUMMARY_KEYS = (
    "rows", "distinct_nodes", "active_nodes", "periods", "failed_periods", "nodes_without_reward_address", "operator_groups",
    "clock_order_violations", "rewards_avax", "median_span_days", "median_tenure_days", "median_current_streak_days",
)


def _reject(dataset_id: str) -> None:
    if dataset_id != DATASET_ID:
        raise DataError(f"{dataset_id} is not a derived dataset of this module")


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    _reject(dataset_id)
    raise DataError(f"{DATASET_ID} is built with `avalanche data derive`, not fetched")


def capture(dataset_id: str, output: Path, timeout: float = 20, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    return capture_preview(dataset_id, output, parameters)


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    _reject(dataset_id)
    raise DataError(f"{DATASET_ID} is built with `avalanche data derive`, which writes capture and dataset together")


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    return build_preview(dataset_id, capture_dir, output)


def select_inputs(pinned: dict[str, str] | None, root: Path | None) -> list[dict[str, Any]]:
    """The input runs: pinned by ``dataset_id=run`` or the newest built run of each input."""
    pinned = pinned or {}
    unknown = sorted(set(pinned) - set(INPUTS.values()) - set(OPTIONAL_INPUTS.values()) - set(seam.SEAMED.values()))
    if unknown:
        raise DataError(f"not an input of {DATASET_ID}: {', '.join(unknown)}")
    selected = []
    for input_id, share_id in {**INPUTS, **OPTIONAL_INPUTS}.items():
        dataset_id, run = seam.resolve(share_id, pinned, root)
        try:
            record = datasets.receipt(dataset_id, run, root)
            parquet = datasets.parquet_path(dataset_id, run, root)
        except DataError:
            if input_id in OPTIONAL_INPUTS and run is None:
                continue
            raise
        body = parquet.read_bytes()
        selected.append({
            "input_id": input_id, "dataset_id": dataset_id, "run": record["run"],
            "capture_id": record["capture"]["capture_id"], "contract_sha256": record["capture"].get("contract_sha256"),
            "captured_at": record["capture"].get("completed_at"), "rows": record["build"].get("summary", {}).get("rows"),
            "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet,
        })
    return selected


def as_of_time(inputs: list[dict[str, Any]]) -> str:
    """The validator capture time: the instant the clocks are clipped at."""
    return next(item["captured_at"] for item in inputs if item["input_id"] == "validator-stakes")


def cycles_of(path: str) -> str:
    """Nothing for a log with the Helicon cycle columns, else one cycle per period."""
    columns = {row[0] for row in duckdb.connect().execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()}
    return "" if "cycles" in columns else ", 1 AS cycles"


def load_inputs(connection: Any, inputs: list[dict[str, Any]]) -> None:
    names = {"staking-periods": "periods", "validator-stakes": "validators", "delegator-stakes": "delegators", "current-validators": "rpc_snapshot", "validators-active": "api_snapshot"}
    present = set()
    for item in inputs:
        path = str(item["path"]).replace("'", "''")
        connection.execute(f"CREATE OR REPLACE VIEW {names[item['input_id']]} AS SELECT * FROM read_parquet('{path}')")
        present.add(item["input_id"])
    periods = str(next(item["path"] for item in inputs if item["input_id"] == "staking-periods")).replace("'", "''")
    columns = {row[0] for row in connection.execute(f"DESCRIBE SELECT * FROM read_parquet('{periods}')").fetchall()}
    # An auto-renewed validator runs to the end of its latest cycle, and each of its cycles is a period (NC6). A log built
    # before the Helicon grain has neither column, and every period in it is one cycle.
    cycles = "" if "cycles" in columns else ", 1 AS cycles, NULL::TIMESTAMP AS last_cycle_end_time"
    connection.execute(f"CREATE OR REPLACE VIEW periods AS SELECT * REPLACE (coalesce(last_cycle_end_time, end_time) AS end_time) FROM"
                       f" (SELECT *{cycles} FROM read_parquet('{periods}'))")
    key = {frozenset(): "none", frozenset({"current-validators"}): "rpc", frozenset({"validators-active"}): "api", frozenset({"current-validators", "validators-active"}): "both"}
    connection.execute(OBSERVERS_SQL[key[frozenset(present & set(OPTIONAL_INPUTS))]])


def compute(connection: Any, as_of: str) -> None:
    stamp = as_of.replace("Z", "")
    try:
        connection.execute(NODES_SQL, [stamp, stamp, stamp, stamp, stamp])
    except duckdb.Error as error:
        raise DataError(f"node table computation failed: {error}") from error


def summarize(connection: Any) -> dict[str, Any]:
    row = connection.execute(SUMMARY_SQL).fetchone()
    return dict(zip(SUMMARY_KEYS, row))


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    """Build the node table into a new run directory holding ``capture/`` and ``dataset/``."""
    _reject(dataset_id)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    inputs = select_inputs(pinned, root)
    completed_at = now()
    as_of = as_of_time(inputs)
    records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records, "as_of": as_of}))
    capture_receipt = {
        "schema_version": "derived-capture/v1",
        "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
        "dataset_id": dataset_id,
        "source_id": SOURCE_ID,
        "completed_at": completed_at,
        "contract_sha256": contract_hash(catalog, dataset_id),
        "tool": f"avalanche-research@{__version__}",
        "inputs": records,
        "as_of": as_of,
        "parameters": {"streak_gap_days": STREAK_GAP_DAYS, "delegation_capacity_multiple": DELEGATION_CAPACITY_MULTIPLE},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "capture").mkdir()
        (temporary / "dataset").mkdir()
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet_path = temporary / "dataset" / f"{TABLE}.parquet"
        connection = duckdb.connect()
        try:
            load_inputs(connection, inputs)
            compute(connection, as_of)
            connection.execute("COPY nodes TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection)
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "derived-build/v1",
            "dataset_id": dataset_id,
            "dataset_schema": definition["fields"],
            "source_capture_id": capture_receipt["capture_id"],
            "completed_at": now(),
            "tool": f"avalanche-research@{__version__}",
            "summary": summary,
            "outputs": [{"path": parquet_path.name, "bytes": parquet_path.stat().st_size, "sha256": sha256(parquet_path.read_bytes())}],
        }
        (temporary / "dataset" / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"capture": capture_receipt, "build": build_receipt}


def read_capture(capture_dir: Path) -> dict[str, Any]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"unreadable capture receipt: {error}") from error
    if receipt.get("schema_version") != "derived-capture/v1" or receipt.get("dataset_id") != DATASET_ID:
        raise DataError(f"not a {DATASET_ID} capture: {capture_dir}")
    return receipt


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """Verify the input runs still hash as recorded, the contract is unchanged, and the build holds: one row per node,
    every node has a reward address, the clocks are ordered, and the periods and rewards reconcile to the period log."""
    if against is not None:
        raise DataError(f"{DATASET_ID} takes no --against directory")
    catalog = load_catalog()
    receipt = read_capture(capture_dir)
    findings: list[str] = []
    checked = ["input run hashes", "catalog contract"]
    if receipt.get("contract_sha256") != contract_hash(catalog, DATASET_ID):
        findings.append("catalog contract changed since the capture")
    root_dir = datasets.RUNS if root is None else root
    inputs: dict[str, Path] = {}
    for item in receipt.get("inputs", []):
        parquet = root_dir / item["run"] / "dataset" / item["parquet"]
        if not parquet.is_file():
            findings.append(f"input run missing: {item['run']}")
            continue
        body = parquet.read_bytes()
        if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
            findings.append(f"input run differs from the capture receipt: {item['run']}")
        inputs[item["input_id"]] = parquet
    summary: dict[str, Any] = {"inputs": len(receipt.get("inputs", []))}
    if dataset_dir is not None:
        checked.extend(["build hashes", "one row per node", "reward address coverage", "clock order", "period and reward reconciliation"])
        try:
            build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
            if build_receipt.get("source_capture_id") != receipt.get("capture_id"):
                findings.append("build does not belong to this capture")
            for item in build_receipt["outputs"]:
                body = (dataset_dir / item["path"]).read_bytes()
                if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                    findings.append(f"output hash or size differs: {item['path']}")
            connection = duckdb.connect()
            try:
                parquet = str(dataset_dir / f"{TABLE}.parquet").replace("'", "''")
                connection.execute(f"CREATE VIEW nodes AS SELECT * FROM read_parquet('{parquet}')")
                columns = [row[0] for row in connection.execute("DESCRIBE nodes").fetchall()]
                if columns != list(TABLE_COLUMNS):
                    findings.append("Parquet columns differ from the declared fields")
                summary.update(summarize(connection))
                if "staking-periods" in inputs:
                    path = str(inputs["staking-periods"]).replace("'", "''")
                    stamp = receipt["as_of"].replace("Z", "")
                    nodes, periods, rewards = connection.execute(
                        f"SELECT count(DISTINCT node_id), sum(cycles)::BIGINT, round(coalesce(sum(realized_reward_navax), 0) / 1e9, 6) FROM (SELECT *{cycles_of(path)} FROM read_parquet('{path}')) WHERE role = 'validator' AND start_time < ?::TIMESTAMP", [stamp]
                    ).fetchone()
                    summary.update({"log_validator_nodes": nodes, "log_validator_periods": periods, "log_validator_rewards_avax": rewards})
                    if nodes != summary["rows"]:
                        findings.append(f"{summary['rows']} rows against {nodes} validator nodes in the period log")
                    if periods != summary["periods"]:
                        findings.append(f"{summary['periods']} periods against {periods} validator periods in the period log")
                    if abs(float(rewards) - float(summary["rewards_avax"])) > 1e-3:
                        findings.append("validator rewards do not reconcile to the period log")
            finally:
                connection.close()
            if summary["rows"] != summary["distinct_nodes"]:
                findings.append(f"{summary['rows'] - summary['distinct_nodes']} nodes appear more than once")
            if summary["nodes_without_reward_address"]:
                findings.append(f"{summary['nodes_without_reward_address']} nodes have no reward address")
            if summary["clock_order_violations"]:
                findings.append(f"{summary['clock_order_violations']} nodes have tenure above span or streak above tenure")
        except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid dataset output: {error}")
    return {
        "dataset_id": DATASET_ID,
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summary,
        "findings": findings,
    }
