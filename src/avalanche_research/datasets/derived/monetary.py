"""The AVAX monetary daily ledger: one row per UTC date with issuance, burns by chain, realized supply, and active stake.

Every amount is an integer number of wei replayed from built runs of the source datasets. Supply uses ordinary net
reward payouts plus current cycle recognition, including restakes but excluding releases of earlier accrual. It is the
genesis 360,000,000 AVAX plus those recognised rewards minus burns on the P-, X-, and C-Chains, and is written for a
day only when that day and every day before it are complete. A component that a source cannot settle leaves the
day incomplete; nothing is imputed. The capture receipt names every input run and its hash, so a run is
reproducible from those runs alone.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from ... import __version__, datasets
from ...core.catalog import (
    DataError,
    canonical_bytes,
    contract_hash,
    dataset,
    load_catalog,
    now,
    sha256,
)
from . import cycle_accounting as ca
from . import seam
from .staking_periods import PRE_CORTINA

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
# The API's burn totals can also sit below the ledger's total through the day before, which a capture early in a UTC day
# brackets narrowly. At the six 02:15 UTC captures from 2026-10-01 to 2026-10-07, measured against that total, the
# C-Chain figure sat 131 to 252 AVAX below it at five and 226 AVAX above at one, and the P-Chain figure 1.24 to 1.34 AVAX
# below at all six. These measurements do not identify a cause. The two allowances below hold them: 0.01% of the C-Chain
# total, about 509 AVAX at 5.09M, and 2 AVAX for P-Chain. A missing earlier day lowers both ends of the ledger's range,
# so this comparison detects it only when the API value then lies outside the widened bracket. The ledger's coverage
# checks are what detect a missing day.
CHECKPOINT_ALLOWANCE_AVAX = {"p_burned": 2.0}
CHECKPOINT_ALLOWANCE_SHARE = {"c_burned": 0.0001}
# The P-Chain supply counter reserves a period's potential reward at acceptance and releases it if the period fails,
# so it should equal genesis plus rewards paid plus potential rewards of periods still open, within this share.
COUNTER_TOLERANCE = 0.0005
# The Data API's totalRewards counts rewards as they are earned, the ledger when the chain pays them. At a snapshot
# instant it reconciles as rewards paid, plus delegation fees earned but held until the validator's period ends (from
# Cortina), plus each open period's potential reward times the share of its duration elapsed (data/monetary-source-audit.md,
# F5). The fit was 0.0014% on 2026-09-19 and 0.014% on 2026-09-21, so a snapshot fails beyond this share of totalRewards.
REWARDS_RECONCILIATION_TOLERANCE = 0.0002
# From about this instant the API's totalRewards grows some 11,000 AVAX a day slower than the reconciliation, while its
# totalStaked still equals the chain's and the P-Chain supply counter confirms the ledger's periods and rewards
# (data/monetary-source-audit.md, F5). The provider has not said why, so from here a gap is reported, not a finding.
REWARDS_API_DRIFT_FROM = "2026-09-20"  # UTC, compared with the snapshot's ISO time

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
CYCLE_INPUTS = {"staking-cycles": "derived.p-chain-staking-cycles", "cycle-blocks": "p-chain-rpc.blocks"}
REWARD_ACCOUNTING_BASIS = "ordinary-net-payout-plus-cycle-current-recognition/v1"
CYCLE_EVENTS_FILE = "cycle-accounting-events.parquet"
# Natural keys and authority are part of the recorded selection policy, not file iteration order.
MANY_KEYS = {
    "p-transactions": "transaction_hash", "c-evm-daily": "date_utc", "c-block-gaps": "block_height",
    "c-block-fees": "block_height", "c-block-receipt-fees": "block_height", "c-receipt-repairs": "transaction_hash",
    "c-atomic": "transaction_hash", "c-atomic-transactions": "transaction_hash", "supply-checkpoints": "observed_at",
}
INPUT_SELECTION_POLICY = {
    "version": "monetary-whole-row/v1",
    "automatic": "seamed source before raw source, then newest UTC capture",
    "ties": "conflicting equal-authority/equal-time rows refuse; identical rows use descending run name",
    "pins": "an explicit raw or seamed pin selects only that run for its input family",
    "nulls": "preserve the selected whole row, including nulls",
    "gap_fee_sources": ["c-block-fees", "c-block-receipt-fees", "c-receipt-repairs"],
}

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


@contextmanager
def accounting_connection() -> Iterator[Any]:
    """A bounded connection with private spill storage, closed before its scratch directory is removed."""
    with tempfile.TemporaryDirectory(prefix="avalanche-accounting-") as scratch:
        connection = duckdb.connect(config={"threads": "2", "memory_limit": "4GB", "temp_directory": scratch})
        try:
            yield connection
        finally:
            connection.close()


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
        "capture_sha256": sha256((parquet.parent.parent / "capture" / "capture.json").read_bytes()),
    }


def _cycle_reference(input_id: str, reference: dict[str, Any], pinned: dict[str, str], root: Path | None) -> dict[str, Any]:
    """Resolve the parent's exact recorded dependency, never a newest-run lookup."""
    dataset_id = CYCLE_INPUTS[input_id]
    required = ("run", "dataset_id", "capture_id", "parquet", "bytes", "sha256")
    if any(key not in reference for key in required) or reference["dataset_id"] != dataset_id:
        raise DataError(f"{input_id} reference lacks its exact source identity")
    if dataset_id in pinned and pinned[dataset_id] != reference["run"]:
        raise DataError(f"{input_id} pin differs from the selected parent's recorded dependency")
    selected = _describe(input_id, dataset_id, reference["run"], root)
    if "capture_sha256" in reference:
        required += ("capture_sha256",)
    if any(selected[key] != reference[key] for key in required):
        raise DataError(f"{input_id} source differs from the selected parent's recorded dependency")
    return selected


def select_inputs(pinned: dict[str, str] | None, root: Path | None, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """The input runs: one per single input, every current run per many-input."""
    pinned = pinned or {}
    base_ids = set(SINGLE_INPUTS.values()) | set(MANY_INPUTS.values())
    allowed = base_ids | set(CYCLE_INPUTS.values()) | {seam.SEAMED[value] for value in base_ids if value in seam.SEAMED}
    unknown = sorted(set(pinned) - allowed)
    if unknown:
        raise DataError(f"not a pinnable input of {DATASET_ID}: {', '.join(unknown)}")
    selected = [_describe(input_id, *seam.resolve(dataset_id, pinned, root), root) for input_id, dataset_id in SINGLE_INPUTS.items()]
    periods = next(item for item in selected if item["input_id"] == "staking-periods")
    references = [item for item in periods["capture"].get("inputs", []) if item.get("input_id") == "p-staking-cycles"]
    if len(references) > 1:
        raise DataError("staking-periods has ambiguous cycle dependencies")
    if references:
        cycles = _cycle_reference("staking-cycles", references[0], pinned, root)
        blocks = [item for item in cycles["capture"].get("inputs", []) if item.get("input_id") == "blocks"]
        if len(blocks) != 1:
            raise DataError("cycle input needs its exact recorded block walk")
        selected.extend([cycles, _cycle_reference("cycle-blocks", blocks[0], pinned, root)])
    elif set(pinned) & set(CYCLE_INPUTS.values()):
        raise DataError("cycle pins have no matching dependency in the selected staking-periods source")
    for input_id, dataset_id in MANY_INPUTS.items():
        seamed = seam.SEAMED.get(dataset_id)
        explicit = [value for value in (dataset_id, seamed) if value in pinned]
        if len(explicit) > 1:
            raise DataError(f"pin only one source for {input_id}: {', '.join(explicit)}")
        if explicit:
            # An archival pin is explicit even if today's catalog contract has changed.
            source_id = explicit[0]
            selected.append(_describe(input_id, source_id, pinned[source_id], root))
            continue
        current = contract_hash(catalog, dataset_id)
        runs = [item for item in datasets.runs(dataset_id, root)]
        described = []
        for item in runs:
            record = _describe(input_id, dataset_id, item["run"], root)
            if record["contract_sha256"] == current:
                described.append(record)
        described.sort(key=lambda item: (item["captured_at"] or "", item["run"]))
        if seamed:
            # Admit all current-contract seamed candidates too, so equal-time conflicts cannot hide in a latest lookup.
            for item in datasets.runs(seamed, root):
                record = _describe(input_id, seamed, item["run"], root)
                if record["contract_sha256"] == contract_hash(catalog, seamed):
                    described.append(record)
        if not described and input_id in REQUIRED_MANY:
            raise DataError(f"no built run of {dataset_id} carries the current contract")
        selected.extend(described)
    return selected


def _window(capture: dict[str, Any]) -> tuple[str, str]:
    """The [start, end) UTC dates a Snowflake capture's query was bound with, or a seamed table is complete for."""
    if "window" in capture:
        return capture["window"]["start"], capture["window"]["end"]
    parameters = capture["queries"][0]["parameters"]
    return parameters["start"], parameters["end"]


def _input_order(item: dict[str, Any]) -> tuple[int, datetime, str]:
    try:
        captured = datetime.fromisoformat(item["captured_at"])
        if captured.tzinfo is None:
            raise ValueError("missing UTC offset")
    except (KeyError, AttributeError, TypeError, ValueError) as error:
        raise DataError(f"input {item['run']} has no unambiguous capture time") from error
    preferred = item["dataset_id"] == seam.SEAMED.get(MANY_INPUTS[item["input_id"]])
    return int(preferred), captured.astimezone(UTC), item["run"]


def load_inputs(connection: Any, inputs: list[dict[str, Any]]) -> dict[str, Any]:
    """Whole-row winners with their source runs; refuse conflicting equal-time/equal-authority rows."""
    by_input: dict[str, list[dict[str, Any]]] = {}
    for item in inputs:
        by_input.setdefault(item["input_id"], []).append(item)
    for parent_id, reference_id, child_id in (("staking-periods", "p-staking-cycles", "staking-cycles"),
                                               ("staking-cycles", "blocks", "cycle-blocks")):
        parents = by_input.get(parent_id, [])
        refs = [r for parent in parents for r in parent["capture"].get("inputs", []) if r.get("input_id") == reference_id]
        children = by_input.get(child_id, [])
        if not refs and not children:
            continue
        if len(refs) != 1 or len(children) != 1:
            raise DataError(f"{child_id} input does not match its parent's exact recorded dependency")
        keys = ["run", "dataset_id", "capture_id", "parquet", "bytes", "sha256"]
        if "capture_sha256" in refs[0]:
            keys.append("capture_sha256")
        if any(refs[0].get(key) != children[0].get(key) for key in keys):
            raise DataError(f"{child_id} input does not match its parent's exact recorded dependency")
    meta: dict[str, Any] = {"selected_input_rows": {}}
    for input_id, items in by_input.items():
        name = input_id.replace("-", "_")
        parts = []
        many = input_id in MANY_INPUTS
        ordered = sorted(items, key=_input_order) if many else items
        for rank, item in enumerate(ordered):
            path = str(item["path"]).replace("'", "''")
            run = item["run"].replace("'", "''")
            priority = ""
            if many:
                authority, captured, _ = _input_order(item)
                priority = f", {authority} AS source_authority, TIMESTAMPTZ '{captured.isoformat()}' AS source_captured_at"
            parts.append(f"SELECT {rank} AS run_rank, '{run}' AS run{priority}, * FROM read_parquet('{path}')")
        raw = f"{name}_all_runs" if many else name
        connection.execute(f"CREATE OR REPLACE VIEW {raw} AS {' UNION ALL BY NAME '.join(parts)}")
        if many:
            key = MANY_KEYS[input_id]
            columns = [row[0] for row in connection.execute(f"DESCRIBE {raw}").fetchall()
                       if row[0] not in ("run_rank", "run", "source_authority", "source_captured_at")]
            payload = ", ".join('"' + column.replace('"', '""') + '"' for column in columns)
            conflict = connection.execute(
                f"SELECT {key} FROM {raw} GROUP BY {key}, source_authority, source_captured_at "
                f"HAVING count(DISTINCT row({payload})) > 1 LIMIT 1"
            ).fetchone()
            if conflict is not None:
                raise DataError(f"conflicting equal-priority input rows for {input_id} at {key}={conflict[0]}; select an explicit run")
            connection.execute(
                f"CREATE OR REPLACE VIEW {name} AS SELECT * EXCLUDE (source_authority, source_captured_at) FROM {raw} "
                f"QUALIFY row_number() OVER (PARTITION BY {key} ORDER BY run_rank DESC) = 1"
            )
            meta["selected_input_rows"][input_id] = [
                {"run": run, "rows": count} for run, count in connection.execute(
                    f"SELECT run, count(*) FROM {name} GROUP BY run ORDER BY run"
                ).fetchall()
            ]
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
    SELECT rewarded_at::DATE AS date_utc, sum(recognised_reward_navax)::DECIMAL(38,0) * {navax} AS issued_wei
    FROM monetary_reward_events GROUP BY 1
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
    SELECT u.date_utc, u.chain, count(*) AS listed, count(t.transaction_hash) FILTER (WHERE t.burned_navax IS NOT NULL) AS settled,
           coalesce(sum(t.burned_navax), 0)::DECIMAL(38,0) * {navax} AS settled_wei
    FROM unresolved u LEFT JOIN p_transactions t USING (transaction_hash)
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
    SELECT date_utc, burned_wei, absent_blocks + short_blocks AS gap_blocks FROM c_evm_daily
),
gap_heights AS (
    SELECT block_height, date_utc FROM c_block_gaps
),
fee_records AS (
    SELECT 0 AS source_priority, block_height, date_utc, fees_wei FROM c_block_fees
    UNION ALL BY NAME
    SELECT 1 AS source_priority, block_height, date_utc, fees_wei FROM c_block_receipt_fees
    UNION ALL BY NAME
    SELECT 2 AS source_priority, block_height, min(block_timestamp)::DATE AS date_utc,
           CASE WHEN count(*) FILTER (WHERE burned_wei IS NULL) > 0 THEN NULL ELSE sum(burned_wei)::DECIMAL(38,0) END AS fees_wei
    FROM c_receipt_repairs GROUP BY block_height
),
gap_fees AS (
    SELECT block_height, date_utc, fees_wei FROM fee_records
    WHERE block_height IN (SELECT block_height FROM gap_heights)
    QUALIFY row_number() OVER (PARTITION BY block_height ORDER BY source_priority) = 1
),
gap_status AS (
    -- Gap dates can be the preceding present block's date. Settlement follows height identity,
    -- while gap_amounts assigns the actual fees to the fee record's chain date.
    SELECT g.date_utc, count(*) AS listed,
           count(f.block_height) FILTER (WHERE f.fees_wei IS NOT NULL AND f.date_utc IS NOT NULL) AS settled
    FROM gap_heights g LEFT JOIN gap_fees f USING (block_height) GROUP BY 1
),
gap_amounts AS (
    SELECT date_utc, sum(fees_wei)::DECIMAL(38,0) AS gap_wei FROM gap_fees GROUP BY 1
),
evm_days AS (
    SELECT c.date_utc,
           CASE WHEN e.date_utc IS NOT NULL THEN e.burned_wei ELSE 0 END::DECIMAL(38,0) AS complete_wei,
           coalesce(a.gap_wei, 0)::DECIMAL(38,0) AS gap_wei,
           CASE WHEN c.date_utc < DATE '{c_first}' THEN 'complete'
                WHEN NOT EXISTS (SELECT 1 FROM windows w WHERE w.component = 'c_evm_daily' AND c.date_utc >= w.start_date AND c.date_utc < w.end_date) THEN 'missing'
                -- This query is sparse: a covered date without a row has no present blocks, not a null-valued row.
                WHEN e.date_utc IS NOT NULL AND (e.burned_wei IS NULL OR e.gap_blocks IS NULL) THEN 'incomplete'
                WHEN coalesce(e.gap_blocks, 0) = 0 AND coalesce(s.listed, 0) = 0 THEN 'complete'
                WHEN coalesce(s.settled, 0) = coalesce(s.listed, 0) AND coalesce(e.gap_blocks, 0) <= coalesce(s.listed, 0) THEN 'repaired'
                ELSE 'incomplete' END AS coverage
    FROM calendar c
    LEFT JOIN evm e USING (date_utc)
    LEFT JOIN gap_status s USING (date_utc)
    LEFT JOIN gap_amounts a USING (date_utc)
),
atomic_rows AS (
    SELECT transaction_hash, accepted_at, burned_navax FROM c_atomic
),
atomic AS (
    -- An import the Data API leaves unsettled (null burn) takes the node's burn from its signed transaction.
    SELECT a.accepted_at::DATE AS date_utc, sum(coalesce(a.burned_navax, t.burned_navax))::DECIMAL(38,0) * {navax} AS burned_wei,
           count(*) FILTER (WHERE a.burned_navax IS NULL) AS unsettled,
           count(*) FILTER (WHERE a.burned_navax IS NULL AND t.burned_navax IS NOT NULL) AS settled
    FROM atomic_rows a LEFT JOIN c_atomic_transactions t USING (transaction_hash)
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
    LEFT JOIN effective_stake_intervals p ON p.start_time <= c.date_utc + INTERVAL '{instant}'
         AND p.end_time > c.date_utc + INTERVAL '{instant}'
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
    _start, end = meta["windows"]["burn_daily"]
    last = (date.fromisoformat(end) - timedelta(days=1)).isoformat()
    meta["complete_through"] = last
    meta["cycle_accounting"] = ca.prepare(connection, last)
    if meta["cycle_accounting"]["basis"] != REWARD_ACCOUNTING_BASIS:
        raise DataError("cycle accounting helper has an unsupported recognition basis")
    if "staking_transaction_hash" in ca.columns(connection, "staking_rewards"):
        count, amount = connection.execute("""
            SELECT count(*), coalesce(sum(r.realized_reward_navax),0)::VARCHAR FROM staking_rewards r
            JOIN cycle_parents p ON p.transaction_hash=r.staking_transaction_hash
        """).fetchone()
    else:
        count, amount = 0, "0"
    meta["cycle_accounting"].update(excluded_ordinary_auto_payout_rows=count, excluded_ordinary_auto_payout_navax=amount)
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


def burn_component_findings(connection: Any, *, p_detail: bool = False) -> list[str]:
    """Integer identities on the ledger. Gap repairs are an included subset of C-EVM, not another chain."""
    total, gap = connection.execute("""
        SELECT count(*) FILTER (WHERE burned_wei IS DISTINCT FROM
                   burned_p_wei + burned_x_wei + burned_c_evm_wei + burned_c_atomic_wei),
               count(*) FILTER (WHERE burned_c_evm_gap_wei < 0 OR burned_c_evm_gap_wei > burned_c_evm_wei)
        FROM ledger
    """).fetchone()
    findings = []
    if total:
        findings.append(f"{total} days have burn components that do not sum to total burn")
    if gap:
        findings.append(f"{gap} days have gap burn outside the inclusive C-EVM amount")
    if p_detail:
        p = connection.execute("""
            SELECT count(*) FILTER (WHERE burned_p_wei IS DISTINCT FROM
                       burned_p_transactions_wei + burned_p_l1_validator_fees_wei) FROM ledger
        """).fetchone()[0]
        if p:
            findings.append(f"{p} days have P-Chain burn subcomponents that do not sum to P burn")
    return findings


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
        SELECT count(*), count(*) FILTER (WHERE a.fees_wei IS DISTINCT FROM b.fees_wei OR a.date_utc IS DISTINCT FROM b.date_utc)
        FROM c_block_fees a JOIN c_block_receipt_fees b USING (block_height)
    """).fetchone()
    return {"shared_blocks": int(shared), "differing_blocks": int(differing)}


def checkpoints(connection: Any) -> list[dict[str, Any]]:
    """Each Data API supply snapshot against the ledger's cumulative totals through the day before and through its day.

    The API's totalCBurned counts C-Chain EVM fees only, so it is compared with the ledger's EVM burns; the ledger's
    import and export burns are real and stay in its supply, but have no counterpart in the API's figure."""
    rows = connection.execute(
        """
        WITH cumulative AS (
            SELECT date_utc,
                   sum(issued_rewards_wei) OVER w AS rewards, sum(burned_p_wei) OVER w AS p, sum(burned_x_wei) OVER w AS x,
                   sum(burned_c_evm_wei) OVER w AS c, total_supply_close_wei AS supply, complete
            FROM ledger WINDOW w AS (ORDER BY date_utc ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        ),
        snapshots AS (
            SELECT observed_at, observed_at::DATE AS date_utc, total_rewards_avax, total_p_burned_avax, total_x_burned_avax, total_c_burned_avax, total_supply_avax
            FROM supply_checkpoints
        )
        SELECT s.observed_at, s.total_rewards_avax, s.total_p_burned_avax, s.total_x_burned_avax, s.total_c_burned_avax, s.total_supply_avax,
               b.rewards, a.rewards, b.p, a.p, b.x, a.x, b.c, a.c, b.supply, a.supply,
               (SELECT bool_and(complete) FROM cumulative WHERE date_utc <= s.date_utc) AS ledger_complete,
               s.date_utc > (SELECT max(date_utc) FROM cumulative WHERE supply IS NOT NULL) AS after_ledger_supply
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
            "after_ledger_supply": row[17],
            "rewards_reconciliation": rewards_reconciliation(connection, observed_at, api_rewards),
            **{name: _bracket(api, before if ledger_complete else None, after if ledger_complete else None, name) for name, api, before, after in (
                ("rewards", api_rewards, row[6], row[7]), ("p_burned", api_p, row[8], row[9]), ("x_burned", api_x, row[10], row[11]),
                ("c_burned", api_c, row[12], row[13]), ("total_supply", api_supply, row[14], row[15]),
            )},
        })
    return results


def _cycle_diagnostic_amounts(connection: Any, instant: Any, height: int | None = None) -> dict[str, Any] | None:
    """Time/height-bounded recognition, held fees and current reservations. None retains the ordinary-only path."""
    if not ca.exists(connection, "cycle_parents") or not connection.execute("SELECT count(*) FROM cycle_parents").fetchone()[0]:
        return None
    required = {"staking_transaction_hash", "block_height", "rewarded_at"}
    if not required <= ca.columns(connection, "staking_rewards") or not {"accepted_at", "block_height"} <= ca.columns(connection, "staking_periods"):
        return {"limit": "cycle-aware diagnostic lacks ordinary reward or acceptance block identity"}
    params = {"t": instant, "h": height}
    row = connection.execute(f"""
        WITH r AS (SELECT * FROM staking_rewards WHERE rewarded_at <= $t AND ($h IS NULL OR block_height <= $h)),
        e AS (SELECT * FROM cycle_events WHERE rewarded_at <= $t AND ($h IS NULL OR option_height <= $h)),
        ordinary_open AS (
            SELECT p.* FROM staking_periods p WHERE p.accepted_at <= $t AND ($h IS NULL OR p.block_height <= $h)
            AND NOT EXISTS (SELECT 1 FROM cycle_parents cp WHERE cp.transaction_hash=p.transaction_hash)
            AND NOT EXISTS (SELECT 1 FROM r WHERE r.staking_transaction_hash=p.transaction_hash)),
        cycle_open AS (
            SELECT c.* FROM staking_cycles c JOIN staking_periods p ON p.transaction_hash=c.validator_transaction_hash
            WHERE p.accepted_at <= $t AND ($h IS NULL OR p.block_height <= $h) AND c.start_time <= $t
            AND (c.cycle=1 OR EXISTS (SELECT 1 FROM e WHERE e.validator_transaction_hash=c.validator_transaction_hash AND e.cycle=c.cycle-1))
            AND NOT EXISTS (SELECT 1 FROM e WHERE e.validator_transaction_hash=c.validator_transaction_hash AND e.cycle=c.cycle)),
        held AS (
            SELECT d.fee_transfer_navax FROM staking_periods d
            JOIN staking_periods v ON v.transaction_hash=d.validator_transaction_hash AND v.role='validator'
            JOIN r ON r.staking_transaction_hash=d.transaction_hash
            WHERE d.role='delegator' AND d.rewarded
              AND v.regime NOT IN ({', '.join(f"'{name}'" for name in PRE_CORTINA)})
              AND ((EXISTS (SELECT 1 FROM cycle_parents cp WHERE cp.transaction_hash=v.transaction_hash)
                    AND NOT EXISTS (SELECT 1 FROM e WHERE e.validator_transaction_hash=v.transaction_hash AND e.proposal_height>=r.block_height))
                   OR (NOT EXISTS (SELECT 1 FROM cycle_parents cp WHERE cp.transaction_hash=v.transaction_hash)
                       AND NOT EXISTS (SELECT 1 FROM r vr WHERE vr.staking_transaction_hash=v.transaction_hash))))
        SELECT
          (SELECT coalesce(sum(realized_reward_navax),0) FROM r WHERE NOT EXISTS
             (SELECT 1 FROM cycle_parents cp WHERE cp.transaction_hash=r.staking_transaction_hash))
             + (SELECT coalesce(sum(recognised_reward_navax),0) FROM e),
          (SELECT coalesce(sum(-fee_transfer_navax),0) FROM held),
          (SELECT coalesce(sum(potential_reward_navax),0) FROM ordinary_open)
             + (SELECT coalesce(sum(potential_reward_navax),0) FROM cycle_open),
          (SELECT coalesce(sum(potential_reward_navax * least(1.0, epoch($t-start_time)/epoch(end_time-start_time))),0)
             FROM ordinary_open WHERE start_time<=$t AND end_time>start_time)
             + (SELECT coalesce(sum(potential_reward_navax * least(1.0, epoch($t-start_time)/epoch(end_time-start_time))),0)
                FROM cycle_open),
          (SELECT max(rewarded_at)>=$t FROM monetary_reward_events)
             AND (SELECT max(block_time)>=$t FROM cycle_blocks)
    """, params).fetchone()
    return dict(zip(("recognised", "held", "pending", "earned", "covered"), row))


def rewards_reconciliation(connection: Any, instant: Any, api_rewards: Any) -> dict[str, Any]:
    """The API against recognised rewards, held delegation fees and earned current open shares.

    On the ordinary-only path recognised rewards are payouts. The cycle-aware diagnostic is not a cash-payment
    reconstruction, so its former paid_avax field is null rather than relabeling restaked recognition as payment.
    Not compared when the reward input ends before the instant: the periods come from the same walk and end with it."""
    cycle = _cycle_diagnostic_amounts(connection, instant)
    if cycle is not None and cycle.get("limit"):
        return {"basis": REWARD_ACCOUNTING_BASIS, "limit": cycle["limit"], "covered": False, "within": None}
    if cycle is not None:
        paid, held, earned, covered = cycle["recognised"], cycle["held"], cycle["earned"], cycle["covered"]
    else:
        covered = connection.execute("SELECT max(rewarded_at) >= ? FROM staking_rewards", [instant]).fetchone()[0]
        paid, held, earned = connection.execute(
        f"""
        SELECT (SELECT coalesce(sum(realized_reward_navax), 0) FROM staking_rewards WHERE rewarded_at <= $t),
               (SELECT coalesce(sum(-d.fee_transfer_navax), 0) FROM staking_periods d
                JOIN staking_periods v ON v.transaction_hash = d.validator_transaction_hash AND v.role = 'validator'
                WHERE d.role = 'delegator' AND d.rewarded AND d.rewarded_at <= $t AND coalesce(v.rewarded_at > $t, TRUE)
                  AND v.regime NOT IN ({", ".join(f"'{name}'" for name in PRE_CORTINA)})),
               (SELECT coalesce(sum(potential_reward_navax * least(1.0, epoch($t - start_time) / epoch(end_time - start_time))), 0)
                FROM staking_periods WHERE start_time <= $t AND end_time > start_time AND coalesce(rewarded_at > $t, TRUE))
        """, {"t": instant}).fetchone()
    model = (int(paid) + int(held) + float(earned)) / 1e9
    api = float(api_rewards)
    gap = api - model
    return {"basis": REWARD_ACCOUNTING_BASIS if cycle is not None else "ordinary-payout-held-fees-earned-open/v1",
            "paid_avax": int(paid) / 1e9 if cycle is None else None,
            "recognised_avax": int(paid) / 1e9, "held_fees_avax": int(held) / 1e9, "earned_open_avax": float(earned) / 1e9, "model_avax": model,
            "api_avax": api, "gap_avax": round(gap, 3), "gap_share": gap / api if api else None, "covered": bool(covered),
            "within": abs(gap) <= REWARDS_RECONCILIATION_TOLERANCE * api if covered else None}


def checkpoint_allowance(name: str, before_avax: float) -> float:
    """The AVAX a Data API total may sit outside the ledger's bracket for that day."""
    return max(CHECKPOINT_TOLERANCE_AVAX, CHECKPOINT_ALLOWANCE_AVAX.get(name, 0.0),
               CHECKPOINT_ALLOWANCE_SHARE.get(name, 0.0) * abs(before_avax))


def judge_checkpoint(name: str, result: dict[str, Any]) -> dict[str, Any]:
    """``result`` with its gap and verdict under the current allowance, from the API value and the ledger's bracket it
    stores. The check judges from these values, so a run built under an earlier allowance is judged under this one."""
    before, after = result.get("ledger_before_avax"), result.get("ledger_after_avax")
    if before is None or after is None:
        return {**result, "gap_avax": None, "within": None}
    allowance = checkpoint_allowance(name, before)
    low, high = min(before, after) - allowance, max(before, after) + allowance
    api = result["api_avax"]
    gap = 0.0 if low <= api <= high else (api - high if api > high else api - low)
    return {**result, "allowance_avax": round(allowance, 6), "gap_avax": round(gap, 6), "within": low <= api <= high}


def _bracket(api_avax: Any, before_wei: Any, after_wei: Any, name: str = "") -> dict[str, Any]:
    api_avax = float(api_avax)
    if before_wei is None or after_wei is None:
        return {"api_avax": api_avax, "ledger_before_avax": None, "ledger_after_avax": None, "gap_avax": None, "within": None}
    before, after = int(before_wei) / 1e18, int(after_wei) / 1e18
    return judge_checkpoint(name, {"api_avax": api_avax, "ledger_before_avax": before, "ledger_after_avax": after})


def counter_check(connection: Any) -> dict[str, Any]:
    """The last counter against genesis, recognised rewards, held fees and current reward reservations."""
    row = connection.execute(
        """
        SELECT accepted_at, block_supply_navax, block_height FROM staking_supply
        WHERE block_supply_navax IS NOT NULL ORDER BY accepted_at DESC, block_height DESC LIMIT 1
        """
    ).fetchone()
    if row is None:
        return {"counter_read_at": None}
    read_at, counter, height = row
    cycle = _cycle_diagnostic_amounts(connection, read_at, height)
    if cycle is not None and cycle.get("limit"):
        return {"counter_read_at": _plain(read_at), "basis": REWARD_ACCOUNTING_BASIS, "limit": cycle["limit"], "gap_share": None}
    held = 0
    if cycle is not None:
        realized, pending, held = cycle["recognised"], cycle["pending"], cycle["held"]
    else:
        realized, pending = connection.execute("""
            SELECT (SELECT sum(realized_reward_navax) FROM staking_rewards WHERE rewarded_at <= $t),
                   (SELECT sum(potential_reward_navax) FROM staking_periods WHERE accepted_at <= $t AND (rewarded_at IS NULL OR rewarded_at > $t))
        """, {"t": read_at}).fetchone()
    expected = 360_000_000 * WEI_PER_NAVAX + int(realized or 0) + int(pending or 0) + int(held or 0)
    return {"counter_read_at": _plain(read_at), "counter_avax": int(counter) / 1e9, "genesis_rewards_open_potential_avax": expected / 1e9,
            "basis": REWARD_ACCOUNTING_BASIS if cycle is not None else "ordinary-payout-plus-open-potential/v1",
            "recognised_navax": str(realized or 0), "pending_navax": str(pending or 0), "held_fees_navax": str(held or 0),
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
        "input_selection_policy": INPUT_SELECTION_POLICY,
        "inputs": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "capture").mkdir()
        (temporary / "dataset").mkdir()
        parquet_path = temporary / "dataset" / f"{TABLE}.parquet"
        events_path = temporary / "dataset" / CYCLE_EVENTS_FILE
        with accounting_connection() as connection:
            meta = load_inputs(connection, inputs)
            compute(connection, meta)
            connection.execute("COPY (SELECT * FROM ledger ORDER BY date_utc) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            connection.execute("COPY (SELECT * FROM cycle_events ORDER BY validator_transaction_hash,cycle) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(events_path)])
            summary = summarize(connection)
            summary["checkpoints"] = checkpoints(connection)
            summary["counter"] = counter_check(connection)
            summary["gap_fee_sources"] = gap_fee_agreement(connection)
            summary["selected_input_rows"] = meta["selected_input_rows"]
            summary["cycle_accounting"] = meta["cycle_accounting"]
        capture_receipt["reward_accounting_basis"] = meta["cycle_accounting"]["basis"]
        capture_receipt["accounting_projection"] = {
            "complete_through": meta["complete_through"], "cycle_events": CYCLE_EVENTS_FILE,
            "event_time": "verified equal proposal/option chain timestamp",
            "stock": "ordinary intervals plus effective cycle weights, half-open intervals",
            "cycle_output_window": "complete selected source history, filtered by ledger UTC dates on consumption",
        }
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        build_receipt = {
            "schema_version": "derived-build/v1",
            "dataset_id": dataset_id,
            "dataset_schema": definition["fields"],
            "source_capture_id": capture_receipt["capture_id"],
            "completed_at": now(),
            "tool": f"avalanche-research@{__version__}",
            "summary": summary,
            "outputs": [{"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path.read_bytes())} for path in (parquet_path, events_path)],
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


def _check_cycle_projection(receipt: dict[str, Any], build: dict[str, Any], dataset_dir: Path, root: Path) -> list[str]:
    """Replay only recorded inputs and compare both published projections, without any newest-run resolution."""
    basis = receipt.get("reward_accounting_basis")
    if basis is None:
        return []  # An archived payout-only ledger retains its original producer contract.
    if basis != REWARD_ACCOUNTING_BASIS:
        return ["unsupported reward accounting basis"]
    if sum(item["path"] == CYCLE_EVENTS_FILE for item in build["outputs"]) != 1:
        return ["cycle accounting companion is missing from the build outputs"]
    inputs = []
    for item in receipt["inputs"]:
        capture = json.loads((root / item["run"] / "capture" / "capture.json").read_text())
        inputs.append({**item, "path": root / item["run"] / "dataset" / item["parquet"], "capture": capture})
    with accounting_connection() as proof:
        meta = load_inputs(proof, inputs)
        compute(proof, meta)
        findings = []
        for table, path in (("ledger", dataset_dir / f"{TABLE}.parquet"), ("cycle_events", dataset_dir / CYCLE_EVENTS_FILE)):
            differences = proof.execute(
                f"SELECT (SELECT count(*) FROM (SELECT * FROM {table} EXCEPT ALL SELECT * FROM read_parquet(?))) "
                f"+ (SELECT count(*) FROM (SELECT * FROM read_parquet(?) EXCEPT ALL SELECT * FROM {table}))",
                [str(path), str(path)],
            ).fetchone()[0]
            if differences:
                findings.append(f"{table} differs from the recorded accounting projection")
        if build.get("summary", {}).get("cycle_accounting") != meta["cycle_accounting"]:
            findings.append("cycle accounting summary differs from the recorded inputs")
        return findings


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
        if "capture_sha256" in item:
            capture_path = root_dir / item["run"] / "capture" / "capture.json"
            if not capture_path.is_file() or sha256(capture_path.read_bytes()) != item["capture_sha256"]:
                findings.append(f"input capture differs from the recorded lineage: {item['run']}")
    summary: dict[str, Any] = {"inputs": len(receipt.get("inputs", []))}
    if dataset_dir is not None:
        checked.extend(["build hashes", "columns", "daily conservation", "burn component conservation", "supply continuity", "coverage values", "Data API checkpoints", "P-Chain supply counter"])
        try:
            build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
            if build_receipt.get("source_capture_id") != receipt.get("capture_id"):
                findings.append("build does not belong to this capture")
            for item in build_receipt["outputs"]:
                body = (dataset_dir / item["path"]).read_bytes()
                if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                    findings.append(f"output hash or size differs: {item['path']}")
            if not findings:
                findings.extend(_check_cycle_projection(receipt, build_receipt, dataset_dir, root_dir))
            with accounting_connection() as connection:
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
                findings.extend(burn_component_findings(connection, p_detail=True))
                summary.update({key: value for key, value in build_receipt.get("summary", {}).items()})
                for point in summary.get("checkpoints", []):
                    reconciled = point.get("rewards_reconciliation")
                    if reconciled and reconciled.get("limit"):
                        findings.append(reconciled["limit"])
                    # With the reconciliation, rewards and total supply are compared on the API's earned basis, not bracketed.
                    for name in ("p_burned", "x_burned", "c_burned") + (() if reconciled else ("rewards", "total_supply")):
                        result = point[name] = judge_checkpoint(name, point[name])
                        if result["within"] is False:
                            findings.append(f"Data API {name} at {point['observed_at']} differs from the ledger by {result['gap_avax']:,.3f} AVAX "
                                            f"beyond the {result['allowance_avax']:,.3f} AVAX allowance")
                        elif result["within"] is None and point["ledger_complete_through_that_day"] is not False and not point.get("after_ledger_supply"):
                            findings.append(f"Data API {name} at {point['observed_at']} cannot be bracketed: the ledger has no supply through that day")
                    if reconciled and reconciled["within"] is False and point["observed_at"] >= REWARDS_API_DRIFT_FROM:
                        summary.setdefault("reported", []).append(
                            f"Data API rewards at {point['observed_at']} differ from the reconciliation by {reconciled['gap_avax']:,.0f} AVAX "
                            f"({reconciled['gap_share']:.4%}); reported, not a finding, from {REWARDS_API_DRIFT_FROM}")
                    elif reconciled and reconciled["within"] is False:
                        findings.append(f"Data API rewards at {point['observed_at']} differ from rewards paid plus held fees plus earned open shares by "
                                        f"{reconciled['gap_avax']:,.0f} AVAX ({reconciled['gap_share']:.4%}), beyond {REWARDS_RECONCILIATION_TOLERANCE:.2%}")
                sources = summary.get("gap_fee_sources", {})
                if sources.get("differing_blocks"):
                    findings.append(f"{sources['differing_blocks']} of {sources['shared_blocks']} gap blocks carry different fees from the Data API and the node's receipts")
                counter = summary.get("counter", {})
                if counter.get("limit"):
                    findings.append(counter["limit"])
                if counter.get("gap_share") is not None and abs(counter["gap_share"]) > COUNTER_TOLERANCE:
                    findings.append(f"the P-Chain supply counter differs from genesis plus rewards paid plus open potential rewards by {counter['gap_avax']:,.0f} AVAX")
        except (OSError, KeyError, TypeError, ValueError, DataError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid dataset output: {error}")
    return {
        "dataset_id": DATASET_ID,
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summary,
        "findings": findings,
    }
