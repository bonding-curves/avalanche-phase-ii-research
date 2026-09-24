"""The AVAX monetary daily ledger: one row per UTC date with issuance, burns by chain, realized supply, and active stake.

Every amount is an integer number of wei replayed from built runs of the source datasets. Supply is the genesis
360,000,000 AVAX plus every reward paid out minus every burn on the P-, X-, and C-Chains, and it is written for a
day only when that day and every day before it are complete. A component that a source cannot settle leaves the
day incomplete; nothing is imputed. The capture receipt names every input run and its hash, so a run is
reproducible from those runs alone.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from . import __version__, datasets
from .catalog import DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256

DATASET_ID = "derived.avax-monetary-daily"
DATASET_IDS = (DATASET_ID,)
SOURCE_ID = "derived"
TABLE = "avax-monetary-daily"
GENESIS_DATE = date(2020, 9, 10)
C_CHAIN_FIRST_DATE = date(2020, 9, 23)
GENESIS_SUPPLY_WEI = 360_000_000 * 10**18
WEI_PER_NAVAX = 10**9
# The daily stake observation instant: the last second of the UTC day, as in the 2026-09-21 one-day proof.
STAKE_INSTANT = "23:59:59"
# A Data API supply checkpoint is taken at an instant inside a day, so each cumulative total must lie between the
# ledger's totals through the day before and through that day, with this allowance in AVAX for the L1 validator
# fees that accrue continuously and the burns the share settles that the API omits.
CHECKPOINT_TOLERANCE_AVAX = 1.0
# The P-Chain supply counter reserves a period's potential reward at acceptance and releases it if the period fails,
# so it should equal genesis plus rewards paid plus potential rewards of periods still open, within this share.
COUNTER_TOLERANCE = 0.0005

# One built run each, the newest or the one pinned with --input.
SINGLE_INPUTS = {
    "burn-daily": "snowflake.primary-burn-daily",
    "staking-rewards": "snowflake.primary-staking-rewards",
    "staking-periods": "derived.staking-periods",
    "staking-supply": "snowflake.primary-staking-supply",
}
# Every built run whose capture carries the current contract, unioned; the newest capture wins where two overlap.
MANY_INPUTS = {
    "p-transactions": "p-chain-rpc.transactions",
    "c-evm-daily": "snowflake.c-chain-evm-burn-daily",
    "c-block-gaps": "snowflake.c-chain-block-gaps",
    "c-block-fees": "data-api.c-chain-block-fees",
    "c-block-receipt-fees": "c-chain-rpc.block-receipt-fees",
    "c-receipt-repairs": "c-chain-rpc.receipt-gap-repairs",
    "c-atomic": "data-api.c-chain-atomic-burn",
    "c-atomic-transactions": "c-chain-rpc.atomic-transactions",
    "supply-checkpoints": "data-api.avax-supply",
}
REQUIRED_MANY = {"c-evm-daily", "c-atomic"}

TABLE_COLUMNS = {
    "date_utc": "DATE",
    "issued_rewards_wei": "DECIMAL(38,0)",
    "burned_p_wei": "DECIMAL(38,0)",
    "burned_p_transactions_wei": "DECIMAL(38,0)",
    "burned_p_l1_validator_fees_wei": "DECIMAL(38,0)",
    "burned_x_wei": "DECIMAL(38,0)",
    "burned_c_evm_wei": "DECIMAL(38,0)",
    "burned_c_evm_gap_wei": "DECIMAL(38,0)",
    "burned_c_atomic_wei": "DECIMAL(38,0)",
    "burned_wei": "DECIMAL(38,0)",
    "total_supply_open_wei": "DECIMAL(38,0)",
    "total_supply_close_wei": "DECIMAL(38,0)",
    "active_validator_stake_wei": "DECIMAL(38,0)",
    "active_delegated_stake_wei": "DECIMAL(38,0)",
    "active_validators": "BIGINT",
    "active_delegations": "BIGINT",
    "rewards_coverage": "VARCHAR",
    "p_coverage": "VARCHAR",
    "x_coverage": "VARCHAR",
    "c_evm_coverage": "VARCHAR",
    "c_atomic_coverage": "VARCHAR",
    "stake_coverage": "VARCHAR",
    "complete": "BOOLEAN",
}
COVERAGE = ("complete", "repaired", "incomplete", "missing")


def _reject(dataset_id: str) -> None:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    _reject(dataset_id)
    raise DataError(f"{dataset_id} is derived from built runs; use `avalanche data derive`")


def capture(dataset_id: str, output: Path, timeout: float = 20, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    return capture_preview(dataset_id, output, parameters)


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    return capture_preview(dataset_id, output)


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    return capture_preview(dataset_id, output)


def _describe(input_id: str, dataset_id: str, run: str, root: Path | None) -> dict[str, Any]:
    record = datasets.receipt(dataset_id, run, root)
    parquet = datasets.parquet_path(dataset_id, run, root)
    body = parquet.read_bytes()
    return {
        "input_id": input_id, "dataset_id": dataset_id, "run": record["run"],
        "capture_id": record["capture"]["capture_id"], "contract_sha256": record["capture"].get("contract_sha256"),
        "captured_at": record["capture"].get("completed_at"), "rows": record["build"].get("summary", {}).get("rows"),
        "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet, "capture": record["capture"],
    }


def select_inputs(pinned: dict[str, str] | None, root: Path | None, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """The input runs: one per single input, every current run per many-input."""
    pinned = pinned or {}
    unknown = sorted(set(pinned) - set(SINGLE_INPUTS.values()))
    if unknown:
        raise DataError(f"not a pinnable input of {DATASET_ID}: {', '.join(unknown)}")
    selected = [_describe(input_id, dataset_id, pinned.get(dataset_id), root) for input_id, dataset_id in SINGLE_INPUTS.items()]
    for input_id, dataset_id in MANY_INPUTS.items():
        current = contract_hash(catalog, dataset_id)
        runs = [item for item in datasets.runs(dataset_id, root)]
        described = []
        for item in runs:
            record = _describe(input_id, dataset_id, item["run"], root)
            if record["contract_sha256"] == current:
                described.append(record)
        if not described and input_id in REQUIRED_MANY:
            raise DataError(f"no built run of {dataset_id} carries the current contract")
        selected.extend(sorted(described, key=lambda item: (item["captured_at"] or "", item["run"])))
    return selected


def _window(capture: dict[str, Any]) -> tuple[str, str]:
    """The [start, end) UTC dates a Snowflake capture's query was bound with."""
    parameters = capture["queries"][0]["parameters"]
    return parameters["start"], parameters["end"]


def load_inputs(connection: Any, inputs: list[dict[str, Any]]) -> dict[str, Any]:
    """One view per input; many-inputs are unioned with a run rank so the newest capture wins where runs overlap."""
    by_input: dict[str, list[dict[str, Any]]] = {}
    for item in inputs:
        by_input.setdefault(item["input_id"], []).append(item)
    meta: dict[str, Any] = {}
    for input_id, items in by_input.items():
        name = input_id.replace("-", "_")
        parts = []
        for rank, item in enumerate(items):
            path = str(item["path"]).replace("'", "''")
            parts.append(f"SELECT {rank} AS run_rank, '{item['run']}' AS run, * FROM read_parquet('{path}')")
        connection.execute(f"CREATE OR REPLACE VIEW {name} AS {' UNION ALL BY NAME '.join(parts)}")
    windows = {"c_evm_daily": [], "c_atomic": [], "burn_daily": None, "staking_rewards": None}
    for item in by_input.get("c-evm-daily", []):
        windows["c_evm_daily"].append(_window(item["capture"]))
    for item in by_input.get("c-atomic", []):
        capture = item["capture"]
        windows["c_atomic"].append((_epoch_date(capture["start_timestamp"]), _epoch_date(capture["end_timestamp"])))
    windows["burn_daily"] = _window(by_input["burn-daily"][0]["capture"])
    windows["staking_rewards"] = _window(by_input["staking-rewards"][0]["capture"])
    meta["windows"] = windows
    meta["rewards_captured"] = by_input["staking-rewards"][0]["captured_at"][:10]
    periods_capture = by_input["staking-periods"][0]["capture"]
    meta["stake_captured"] = min(item["captured_at"] for item in periods_capture.get("inputs", []))[:10]
    meta["has"] = {key: key in by_input for key in MANY_INPUTS}
    connection.execute("CREATE OR REPLACE TABLE windows(component VARCHAR, start_date DATE, end_date DATE)")
    for component in ("c_evm_daily", "c_atomic"):
        for start, end in windows[component]:
            connection.execute("INSERT INTO windows VALUES (?, ?, ?)", [component, start, end])
    return meta


def _epoch_date(seconds: int) -> str:
    return datetime.fromtimestamp(int(seconds), UTC).date().isoformat()


LEDGER_SQL = """
CREATE OR REPLACE TABLE ledger AS
WITH calendar AS (
    SELECT unnest(generate_series(DATE '{genesis}', DATE '{last}', INTERVAL 1 DAY))::DATE AS date_utc
),
rewards AS (
    SELECT rewarded_at::DATE AS date_utc, sum(realized_reward_navax)::DECIMAL(38,0) * {navax} AS issued_wei
    FROM staking_rewards GROUP BY 1
),
px AS (
    SELECT date_utc, chain, burned_navax, l1_validator_fees_navax, unresolved_transactions, unresolved_hashes
    FROM burn_daily
),
unresolved AS (
    SELECT date_utc, chain, unnest(string_split(unresolved_hashes, ',')) AS transaction_hash
    FROM px WHERE unresolved_hashes IS NOT NULL
),
resolutions AS (
    SELECT u.date_utc, u.chain, count(*) AS listed, count(t.transaction_hash) AS settled,
           coalesce(sum(t.burned_navax), 0)::DECIMAL(38,0) * {navax} AS settled_wei
    FROM unresolved u LEFT JOIN (SELECT transaction_hash, arg_min(burned_navax, run_rank) AS burned_navax FROM p_transactions GROUP BY 1) t USING (transaction_hash)
    GROUP BY 1, 2
),
p AS (
    SELECT px.date_utc,
           (px.burned_navax::DECIMAL(38,0) * {navax} + coalesce(r.settled_wei, 0)) AS transactions_wei,
           px.l1_validator_fees_navax::DECIMAL(38,0) * {navax} AS l1_wei,
           CASE WHEN px.unresolved_transactions = 0 THEN 'complete' WHEN r.settled = r.listed THEN 'repaired' ELSE 'incomplete' END AS coverage
    FROM px LEFT JOIN resolutions r ON r.date_utc = px.date_utc AND r.chain = px.chain
    WHERE px.chain = 'P'
),
x AS (
    SELECT px.date_utc,
           (px.burned_navax::DECIMAL(38,0) * {navax} + coalesce(r.settled_wei, 0)) AS burned_wei,
           CASE WHEN px.unresolved_transactions = 0 THEN 'complete' WHEN r.settled = r.listed THEN 'repaired' ELSE 'incomplete' END AS coverage
    FROM px LEFT JOIN resolutions r ON r.date_utc = px.date_utc AND r.chain = px.chain
    WHERE px.chain = 'X'
),
evm AS (
    SELECT date_utc, arg_min(burned_wei, run_rank) AS burned_wei, arg_min(absent_blocks + short_blocks, run_rank) AS gap_blocks
    FROM c_evm_daily GROUP BY 1
),
gap_heights AS (
    SELECT block_height, arg_min(date_utc, run_rank) AS date_utc FROM c_block_gaps GROUP BY 1
),
fee_records AS (
    SELECT block_height, arg_min(date_utc, run_rank) AS date_utc, arg_min(fees_wei, run_rank) AS fees_wei FROM c_block_fees GROUP BY 1
    UNION ALL BY NAME
    SELECT block_height, arg_min(date_utc, run_rank) AS date_utc, arg_min(fees_wei, run_rank) AS fees_wei FROM c_block_receipt_fees GROUP BY 1
    UNION ALL BY NAME
    SELECT block_height, min(block_timestamp)::DATE AS date_utc, sum(burned_wei)::DECIMAL(38,0) AS fees_wei FROM c_receipt_repairs GROUP BY 1
),
gap_fees AS (
    SELECT block_height, arg_min(date_utc, ordinal) AS date_utc, arg_min(fees_wei, ordinal) AS fees_wei
    FROM (SELECT *, row_number() OVER () AS ordinal FROM fee_records)
    WHERE block_height IN (SELECT block_height FROM gap_heights)
    GROUP BY 1
),
gap_status AS (
    SELECT g.date_utc, count(*) AS listed, count(f.block_height) AS settled
    FROM gap_heights g LEFT JOIN gap_fees f USING (block_height) GROUP BY 1
),
gap_amounts AS (
    SELECT date_utc, sum(fees_wei)::DECIMAL(38,0) AS gap_wei FROM gap_fees GROUP BY 1
),
evm_days AS (
    SELECT c.date_utc,
           coalesce(e.burned_wei, 0)::DECIMAL(38,0) AS complete_wei,
           coalesce(a.gap_wei, 0)::DECIMAL(38,0) AS gap_wei,
           CASE WHEN c.date_utc < DATE '{c_first}' THEN 'complete'
                WHEN NOT EXISTS (SELECT 1 FROM windows w WHERE w.component = 'c_evm_daily' AND c.date_utc >= w.start_date AND c.date_utc < w.end_date) THEN 'missing'
                WHEN coalesce(e.gap_blocks, 0) = 0 AND coalesce(s.listed, 0) = 0 THEN 'complete'
                WHEN coalesce(s.settled, 0) = coalesce(s.listed, 0) AND coalesce(e.gap_blocks, 0) <= coalesce(s.listed, 0) THEN 'repaired'
                ELSE 'incomplete' END AS coverage
    FROM calendar c
    LEFT JOIN evm e USING (date_utc)
    LEFT JOIN gap_status s USING (date_utc)
    LEFT JOIN gap_amounts a USING (date_utc)
),
atomic_rows AS (
    SELECT transaction_hash, arg_min(accepted_at, run_rank) AS accepted_at, arg_min(burned_navax, run_rank) AS burned_navax FROM c_atomic GROUP BY 1
),
atomic AS (
    -- An import the Data API leaves unsettled (null burn) takes the node's burn from its signed transaction.
    SELECT a.accepted_at::DATE AS date_utc, sum(coalesce(a.burned_navax, t.burned_navax))::DECIMAL(38,0) * {navax} AS burned_wei,
           count(*) FILTER (WHERE a.burned_navax IS NULL) AS unsettled,
           count(*) FILTER (WHERE a.burned_navax IS NULL AND t.burned_navax IS NOT NULL) AS settled
    FROM atomic_rows a LEFT JOIN (SELECT transaction_hash, arg_min(burned_navax, run_rank) AS burned_navax FROM c_atomic_transactions GROUP BY 1) t USING (transaction_hash)
    GROUP BY 1
),
atomic_days AS (
    SELECT c.date_utc, coalesce(a.burned_wei, 0)::DECIMAL(38,0) AS burned_wei,
           CASE WHEN c.date_utc < DATE '{c_first}' THEN 'complete'
                WHEN NOT EXISTS (SELECT 1 FROM windows w WHERE w.component = 'c_atomic' AND c.date_utc >= w.start_date AND c.date_utc < w.end_date) THEN 'missing'
                WHEN coalesce(a.unsettled, 0) = 0 THEN 'complete'
                WHEN a.settled = a.unsettled THEN 'repaired'
                ELSE 'incomplete' END AS coverage
    FROM calendar c LEFT JOIN atomic a USING (date_utc)
),
stake AS (
    SELECT c.date_utc,
           coalesce(sum(p.stake_navax) FILTER (WHERE p.role = 'validator'), 0)::DECIMAL(38,0) * {navax} AS validator_wei,
           coalesce(sum(p.stake_navax) FILTER (WHERE p.role = 'delegator'), 0)::DECIMAL(38,0) * {navax} AS delegated_wei,
           count(*) FILTER (WHERE p.role = 'validator') AS validators,
           count(*) FILTER (WHERE p.role = 'delegator') AS delegations
    FROM calendar c
    LEFT JOIN staking_periods p ON p.start_time <= c.date_utc + INTERVAL '{instant}' AND p.end_time > c.date_utc + INTERVAL '{instant}'
    GROUP BY 1
),
days AS (
    SELECT c.date_utc,
           coalesce(r.issued_wei, 0)::DECIMAL(38,0) AS issued_rewards_wei,
           (p.transactions_wei + p.l1_wei)::DECIMAL(38,0) AS burned_p_wei,
           p.transactions_wei::DECIMAL(38,0) AS burned_p_transactions_wei,
           p.l1_wei::DECIMAL(38,0) AS burned_p_l1_validator_fees_wei,
           x.burned_wei::DECIMAL(38,0) AS burned_x_wei,
           (e.complete_wei + e.gap_wei)::DECIMAL(38,0) AS burned_c_evm_wei,
           e.gap_wei AS burned_c_evm_gap_wei,
           am.burned_wei AS burned_c_atomic_wei,
           s.validator_wei AS active_validator_stake_wei, s.delegated_wei AS active_delegated_stake_wei,
           s.validators AS active_validators, s.delegations AS active_delegations,
           CASE WHEN c.date_utc >= DATE '{rewards_start}' AND c.date_utc < least(DATE '{rewards_end}', DATE '{rewards_captured}') THEN 'complete' ELSE 'missing' END AS rewards_coverage,
           coalesce(p.coverage, 'missing') AS p_coverage,
           coalesce(x.coverage, 'missing') AS x_coverage,
           e.coverage AS c_evm_coverage,
           am.coverage AS c_atomic_coverage,
           CASE WHEN c.date_utc < DATE '{stake_captured}' THEN 'complete' ELSE 'missing' END AS stake_coverage
    FROM calendar c
    LEFT JOIN rewards r USING (date_utc)
    LEFT JOIN p USING (date_utc)
    LEFT JOIN x USING (date_utc)
    LEFT JOIN evm_days e USING (date_utc)
    LEFT JOIN atomic_days am USING (date_utc)
    LEFT JOIN stake s USING (date_utc)
),
flagged AS (
    SELECT *,
           burned_p_wei + burned_x_wei + burned_c_evm_wei + burned_c_atomic_wei AS burned_wei,
           rewards_coverage IN ('complete', 'repaired') AND p_coverage IN ('complete', 'repaired') AND x_coverage IN ('complete', 'repaired')
               AND c_evm_coverage IN ('complete', 'repaired') AND c_atomic_coverage IN ('complete', 'repaired') AND stake_coverage = 'complete' AS complete
    FROM days
),
cut AS (
    SELECT coalesce(min(date_utc), DATE '9999-12-31') AS first_incomplete FROM flagged WHERE NOT complete
),
replay AS (
    SELECT f.*,
           CASE WHEN f.date_utc < cut.first_incomplete
                THEN {genesis_wei}::DECIMAL(38,0) + sum(f.issued_rewards_wei - f.burned_wei) OVER (ORDER BY f.date_utc ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                ELSE NULL END AS total_supply_close_wei
    FROM flagged f, cut
)
SELECT date_utc, issued_rewards_wei, burned_p_wei, burned_p_transactions_wei, burned_p_l1_validator_fees_wei, burned_x_wei,
       burned_c_evm_wei, burned_c_evm_gap_wei, burned_c_atomic_wei, burned_wei,
       lag(total_supply_close_wei, 1, {genesis_wei}::DECIMAL(38,0)) OVER (ORDER BY date_utc) AS total_supply_open_wei,
       total_supply_close_wei,
       active_validator_stake_wei, active_delegated_stake_wei, active_validators, active_delegations,
       rewards_coverage, p_coverage, x_coverage, c_evm_coverage, c_atomic_coverage, stake_coverage, complete
FROM replay
ORDER BY date_utc
"""


def compute(connection: Any, meta: dict[str, Any]) -> None:
    """Build ``ledger`` from the input views: one row per UTC date from genesis to the burn-daily run's last day."""
    for name in ("p_transactions", "c_block_gaps", "c_block_fees", "c_block_receipt_fees", "c_receipt_repairs", "c_atomic_transactions", "supply_checkpoints"):
        if not meta["has"][name.replace("_", "-")]:
            empty = {
                "p_transactions": "SELECT 0 AS run_rank, '' AS run, ''::VARCHAR AS transaction_hash, 0::BIGINT AS burned_navax WHERE FALSE",
                "c_block_gaps": "SELECT 0 AS run_rank, '' AS run, 0::BIGINT AS block_height, DATE '2020-01-01' AS date_utc WHERE FALSE",
                "c_block_fees": "SELECT 0 AS run_rank, '' AS run, 0::BIGINT AS block_height, DATE '2020-01-01' AS date_utc, 0::DECIMAL(38,0) AS fees_wei WHERE FALSE",
                "c_block_receipt_fees": "SELECT 0 AS run_rank, '' AS run, 0::BIGINT AS block_height, DATE '2020-01-01' AS date_utc, 0::DECIMAL(38,0) AS fees_wei WHERE FALSE",
                "c_receipt_repairs": "SELECT 0 AS run_rank, '' AS run, 0::BIGINT AS block_height, TIMESTAMP '2020-01-01' AS block_timestamp, 0::DECIMAL(38,0) AS burned_wei WHERE FALSE",
                "c_atomic_transactions": "SELECT 0 AS run_rank, '' AS run, ''::VARCHAR AS transaction_hash, 0::BIGINT AS burned_navax WHERE FALSE",
                "supply_checkpoints": "SELECT 0 AS run_rank, '' AS run, TIMESTAMP '2020-01-01' AS observed_at WHERE FALSE",
            }[name]
            connection.execute(f"CREATE OR REPLACE VIEW {name} AS {empty}")
    start, end = meta["windows"]["burn_daily"]
    last = (date.fromisoformat(end) - timedelta(days=1)).isoformat()
    rewards_start, rewards_end = meta["windows"]["staking_rewards"]
    sql = LEDGER_SQL.format(
        genesis=GENESIS_DATE.isoformat(), last=last, navax=WEI_PER_NAVAX, c_first=C_CHAIN_FIRST_DATE.isoformat(),
        rewards_start=rewards_start, rewards_end=rewards_end, rewards_captured=meta["rewards_captured"],
        stake_captured=meta["stake_captured"], instant=STAKE_INSTANT, genesis_wei=GENESIS_SUPPLY_WEI,
    )
    try:
        connection.execute(sql)
    except duckdb.Error as error:
        raise DataError(f"input datasets do not match the declared shape: {error}") from error


SUMMARY_SQL = """
SELECT count(*) AS rows, min(date_utc) AS first_date, max(date_utc) AS last_date,
       count(*) FILTER (WHERE complete) AS complete_days,
       min(date_utc) FILTER (WHERE NOT complete) AS first_incomplete_date,
       max(date_utc) FILTER (WHERE total_supply_close_wei IS NOT NULL) AS supply_through,
       max(total_supply_close_wei) FILTER (WHERE date_utc = (SELECT max(date_utc) FROM ledger WHERE total_supply_close_wei IS NOT NULL)) AS supply_close_wei,
       count(*) FILTER (WHERE p_coverage = 'repaired') AS p_repaired_days,
       count(*) FILTER (WHERE c_evm_coverage = 'repaired') AS c_evm_repaired_days,
       count(*) FILTER (WHERE c_evm_coverage = 'incomplete') AS c_evm_incomplete_days,
       count(*) FILTER (WHERE c_evm_coverage = 'missing') AS c_evm_missing_days,
       count(*) FILTER (WHERE c_atomic_coverage = 'missing') AS c_atomic_missing_days,
       count(*) FILTER (WHERE rewards_coverage = 'missing') AS rewards_missing_days,
       count(*) FILTER (WHERE stake_coverage = 'missing') AS stake_missing_days,
       sum(issued_rewards_wei) AS issued_rewards_wei, sum(burned_p_wei) AS burned_p_wei, sum(burned_x_wei) AS burned_x_wei,
       sum(burned_c_evm_wei) AS burned_c_evm_wei, sum(burned_c_atomic_wei) AS burned_c_atomic_wei
FROM ledger
"""


def _plain(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if value is not None and not isinstance(value, (bool, int, float, str)):
        return str(value)
    return value


def summarize(connection: Any) -> dict[str, Any]:
    row = connection.execute(SUMMARY_SQL).fetchone()
    keys = [item[0] for item in connection.execute(f"DESCRIBE {SUMMARY_SQL}").fetchall()]
    return {key: _plain(value) for key, value in zip(keys, row)}


def gap_fee_agreement(connection: Any) -> dict[str, int]:
    """Gap blocks whose fees both the Data API record and a node's receipts give, and how many of those differ."""
    shared, differing = connection.execute("""
        SELECT count(*), count(*) FILTER (WHERE a.fees_wei <> b.fees_wei OR a.date_utc <> b.date_utc)
        FROM (SELECT block_height, arg_min(fees_wei, run_rank) AS fees_wei, arg_min(date_utc, run_rank) AS date_utc FROM c_block_fees GROUP BY 1) a
        JOIN (SELECT block_height, arg_min(fees_wei, run_rank) AS fees_wei, arg_min(date_utc, run_rank) AS date_utc FROM c_block_receipt_fees GROUP BY 1) b USING (block_height)
    """).fetchone()
    return {"shared_blocks": int(shared), "differing_blocks": int(differing)}


def checkpoints(connection: Any) -> list[dict[str, Any]]:
    """Each Data API supply snapshot against the ledger's cumulative totals through the day before and through its day."""
    rows = connection.execute(
        """
        WITH cumulative AS (
            SELECT date_utc,
                   sum(issued_rewards_wei) OVER w AS rewards, sum(burned_p_wei) OVER w AS p, sum(burned_x_wei) OVER w AS x,
                   sum(burned_c_evm_wei + burned_c_atomic_wei) OVER w AS c, total_supply_close_wei AS supply, complete
            FROM ledger WINDOW w AS (ORDER BY date_utc ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        ),
        snapshots AS (
            SELECT observed_at, observed_at::DATE AS date_utc, total_rewards_avax, total_p_burned_avax, total_x_burned_avax, total_c_burned_avax, total_supply_avax
            FROM supply_checkpoints
        )
        SELECT s.observed_at, s.total_rewards_avax, s.total_p_burned_avax, s.total_x_burned_avax, s.total_c_burned_avax, s.total_supply_avax,
               b.rewards, a.rewards, b.p, a.p, b.x, a.x, b.c, a.c, b.supply, a.supply,
               (SELECT bool_and(complete) FROM cumulative WHERE date_utc <= s.date_utc) AS ledger_complete
        FROM snapshots s
        LEFT JOIN cumulative b ON b.date_utc = s.date_utc - INTERVAL 1 DAY
        LEFT JOIN cumulative a ON a.date_utc = s.date_utc
        ORDER BY s.observed_at
        """
    ).fetchall()
    results = []
    for row in rows:
        observed_at, api_rewards, api_p, api_x, api_c, api_supply = row[:6]
        ledger_complete = row[16]
        results.append({
            "observed_at": _plain(observed_at),
            "ledger_complete_through_that_day": ledger_complete,
            **{name: _bracket(api, before if ledger_complete else None, after if ledger_complete else None) for name, api, before, after in (
                ("rewards", api_rewards, row[6], row[7]), ("p_burned", api_p, row[8], row[9]), ("x_burned", api_x, row[10], row[11]),
                ("c_burned", api_c, row[12], row[13]), ("total_supply", api_supply, row[14], row[15]),
            )},
        })
    return results


def _bracket(api_avax: Any, before_wei: Any, after_wei: Any) -> dict[str, Any]:
    api_avax = float(api_avax)
    if before_wei is None or after_wei is None:
        return {"api_avax": api_avax, "ledger_before_avax": None, "ledger_after_avax": None, "gap_avax": None, "within": None}
    before, after = int(before_wei) / 1e18, int(after_wei) / 1e18
    low, high = min(before, after) - CHECKPOINT_TOLERANCE_AVAX, max(before, after) + CHECKPOINT_TOLERANCE_AVAX
    gap = 0.0 if low <= api_avax <= high else (api_avax - high if api_avax > high else api_avax - low)
    return {"api_avax": api_avax, "ledger_before_avax": before, "ledger_after_avax": after, "gap_avax": round(gap, 6), "within": low <= api_avax <= high}


def counter_check(connection: Any) -> dict[str, Any]:
    """The P-Chain supply counter at its last reading against genesis plus rewards paid plus open potential rewards."""
    row = connection.execute(
        """
        WITH last AS (SELECT accepted_at, block_supply_navax FROM staking_supply WHERE block_supply_navax IS NOT NULL ORDER BY accepted_at DESC, block_height DESC LIMIT 1)
        SELECT last.accepted_at, last.block_supply_navax,
               (SELECT sum(realized_reward_navax) FROM staking_rewards WHERE rewarded_at <= last.accepted_at),
               (SELECT sum(potential_reward_navax) FROM staking_periods WHERE accepted_at <= last.accepted_at AND (rewarded_at IS NULL OR rewarded_at > last.accepted_at))
        FROM last
        """
    ).fetchone()
    if row is None:
        return {"counter_read_at": None}
    read_at, counter, realized, pending = row
    expected = 360_000_000 * WEI_PER_NAVAX + int(realized or 0) + int(pending or 0)
    return {"counter_read_at": _plain(read_at), "counter_avax": int(counter) / 1e9, "genesis_rewards_open_potential_avax": expected / 1e9,
            "gap_avax": (int(counter) - expected) / 1e9, "gap_share": (int(counter) - expected) / int(counter)}


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    _reject(dataset_id)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    inputs = select_inputs(pinned, root, catalog)
    completed_at = now()
    records = [{key: value for key, value in item.items() if key not in ("path", "capture")} for item in inputs]
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records}))
    capture_receipt = {
        "schema_version": "derived-capture/v1",
        "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
        "dataset_id": dataset_id,
        "source_id": SOURCE_ID,
        "completed_at": completed_at,
        "contract_sha256": contract_hash(catalog, dataset_id),
        "tool": f"avalanche-research@{__version__}",
        "genesis_supply_wei": str(GENESIS_SUPPLY_WEI),
        "stake_instant_utc": STAKE_INSTANT,
        "inputs": records,
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
            meta = load_inputs(connection, inputs)
            compute(connection, meta)
            connection.execute("COPY (SELECT * FROM ledger ORDER BY date_utc) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection)
            summary["checkpoints"] = checkpoints(connection)
            summary["counter"] = counter_check(connection)
            summary["gap_fee_sources"] = gap_fee_agreement(connection)
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
    """Input hashes, the contract, daily conservation, supply continuity, coverage, and the provider checkpoints."""
    if against is not None:
        raise DataError(f"{DATASET_ID} takes no --against directory")
    catalog = load_catalog()
    receipt = read_capture(capture_dir)
    findings: list[str] = []
    checked = ["input run hashes", "catalog contract"]
    if receipt.get("contract_sha256") != contract_hash(catalog, DATASET_ID):
        findings.append("catalog contract changed since the capture")
    root_dir = datasets.RUNS if root is None else root
    for item in receipt.get("inputs", []):
        parquet = root_dir / item["run"] / "dataset" / item["parquet"]
        if not parquet.is_file():
            findings.append(f"input run missing: {item['run']}")
            continue
        body = parquet.read_bytes()
        if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
            findings.append(f"input run differs from the capture receipt: {item['run']}")
    summary: dict[str, Any] = {"inputs": len(receipt.get("inputs", []))}
    if dataset_dir is not None:
        checked.extend(["build hashes", "columns", "daily conservation", "supply continuity", "coverage values", "Data API checkpoints", "P-Chain supply counter"])
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
                connection.execute(f"CREATE VIEW ledger AS SELECT * FROM read_parquet('{parquet}')")
                columns = [row[0] for row in connection.execute("DESCRIBE ledger").fetchall()]
                if columns != list(TABLE_COLUMNS):
                    findings.append("Parquet columns differ from the declared fields")
                broken, discontinuous, bad_coverage, negative = connection.execute(
                    """
                    WITH ordered AS (SELECT *, lag(total_supply_close_wei) OVER (ORDER BY date_utc) AS previous_close FROM ledger)
                    SELECT count(*) FILTER (WHERE total_supply_close_wei IS NOT NULL AND total_supply_close_wei <> total_supply_open_wei + issued_rewards_wei - burned_wei),
                           count(*) FILTER (WHERE previous_close IS NOT NULL AND total_supply_close_wei IS NOT NULL AND total_supply_open_wei <> previous_close),
                           count(*) FILTER (WHERE rewards_coverage NOT IN ('complete', 'repaired', 'incomplete', 'missing') OR p_coverage NOT IN ('complete', 'repaired', 'incomplete', 'missing')
                                            OR x_coverage NOT IN ('complete', 'repaired', 'incomplete', 'missing') OR c_evm_coverage NOT IN ('complete', 'repaired', 'incomplete', 'missing')
                                            OR c_atomic_coverage NOT IN ('complete', 'repaired', 'incomplete', 'missing') OR stake_coverage NOT IN ('complete', 'missing')
                                            OR (complete AND total_supply_close_wei IS NULL AND date_utc < coalesce((SELECT min(date_utc) FROM ledger WHERE NOT complete), DATE '9999-12-31'))),
                           count(*) FILTER (WHERE issued_rewards_wei < 0 OR burned_wei < 0 OR burned_p_wei < 0 OR burned_x_wei < 0 OR burned_c_evm_wei < 0 OR burned_c_atomic_wei < 0)
                    FROM ordered
                    """
                ).fetchone()
                if broken:
                    findings.append(f"{broken} days break the supply identity")
                if discontinuous:
                    findings.append(f"{discontinuous} days open at a supply other than the previous close")
                if bad_coverage:
                    findings.append(f"{bad_coverage} days carry an unknown coverage or lack a supply while complete")
                if negative:
                    findings.append(f"{negative} days carry a negative flow")
                summary.update({key: value for key, value in build_receipt.get("summary", {}).items()})
                for point in summary.get("checkpoints", []):
                    for name in ("p_burned", "x_burned", "c_burned", "rewards", "total_supply"):
                        result = point[name]
                        if result["within"] is False:
                            findings.append(f"Data API {name} at {point['observed_at']} differs from the ledger by {result['gap_avax']:,.3f} AVAX beyond the {CHECKPOINT_TOLERANCE_AVAX} AVAX allowance")
                        elif result["within"] is None and point["ledger_complete_through_that_day"] is not False:
                            findings.append(f"Data API {name} at {point['observed_at']} cannot be bracketed: the ledger has no supply through that day")
                sources = summary.get("gap_fee_sources", {})
                if sources.get("differing_blocks"):
                    findings.append(f"{sources['differing_blocks']} of {sources['shared_blocks']} gap blocks carry different fees from the Data API and the node's receipts")
                counter = summary.get("counter", {})
                if counter.get("gap_share") is not None and abs(counter["gap_share"]) > COUNTER_TOLERANCE:
                    findings.append(f"the P-Chain supply counter differs from genesis plus rewards paid plus open potential rewards by {counter['gap_avax']:,.0f} AVAX")
            finally:
                connection.close()
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid dataset output: {error}")
    return {
        "dataset_id": DATASET_ID,
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summary,
        "findings": findings,
    }
