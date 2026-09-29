"""Derived datasets: deterministic transformations of built runs of other catalog datasets.

The staking-period log joins the four Snowflake staking datasets into one row per staking period, validators and
delegators together, and adds two columns no provider publishes: the network upgrade regime at acceptance and the
reward the protocol kernel computes for the row from its supply reading. A derived run carries a capture receipt
that names the exact input runs and their hashes, so it is reproducible from those runs alone.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from . import __version__, datasets, seam
from .catalog import DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256
from .model.protocol import MAINNET_UPGRADES, primary_network_reward
from .model.types import ModelError


DATASET_ID = "derived.staking-periods"
DATASET_IDS = (DATASET_ID,)
SOURCE_ID = "derived"
TABLE = "staking-periods"
INPUTS = {
    "validator-stakes": "snowflake.primary-validator-stakes",
    "delegator-stakes": "snowflake.primary-delegator-stakes",
    "staking-rewards": "snowflake.primary-staking-rewards",
    "staking-supply": "snowflake.primary-staking-supply",
}
TABLE_COLUMNS = {
    "transaction_hash": "VARCHAR", "role": "VARCHAR", "tx_type": "VARCHAR", "node_id": "VARCHAR",
    "validator_transaction_hash": "VARCHAR", "accepted_at": "TIMESTAMP", "block_height": "BIGINT",
    "start_time": "TIMESTAMP", "end_time": "TIMESTAMP", "duration_days": "DOUBLE",
    "stake_navax": "BIGINT", "stake_avax": "DOUBLE", "potential_reward_navax": "BIGINT", "potential_reward_avax": "DOUBLE",
    "rewarded": "BOOLEAN", "delegation_fee_rate": "DOUBLE", "regime": "VARCHAR", "start_kind": "VARCHAR",
    "rewarded_at": "TIMESTAMP", "realized_reward_navax": "BIGINT", "realized_reward_avax": "DOUBLE",
    "fee_transfer_navax": "BIGINT", "supply_before_navax": "BIGINT", "kernel_reward_navax": "BIGINT",
    "kernel_gap_navax": "BIGINT", "reproduced": "BOOLEAN", "cycles": "BIGINT", "last_cycle_end_time": "TIMESTAMP",
}
# From Helicon one AddAutoRenewedValidatorTx holds many cycles (glossary G9, decision DC3). The row keeps the transaction's
# own first period; cycles counts the cycles it has started and last_cycle_end_time ends the latest. History has none, so
# the cycle table is optional.
OPTIONAL_INPUTS = {"p-staking-cycles": "derived.p-chain-staking-cycles"}
IMMEDIATE_REPRODUCTION_FLOOR = 0.999
# From Cortina, a delegator's fee is withheld from its reward and paid to the validator at the validator's own period end,
# so a rewarded delegation's fee_transfer equals -(potential reward x the validator's fee rate) to the nAVAX. Before
# Cortina the delegation's reward UTXOs included the validator's share, and the field reads zero. This floor is the
# share of rewarded delegations to post-Cortina validators that must reconcile.
FEE_RECONCILIATION_FLOOR = 0.999
FEE_RECONCILIATION_SQL = """
    WITH d AS (
        SELECT d.fee_transfer_navax, d.potential_reward_navax, v.delegation_fee_rate
        FROM periods d JOIN periods v ON v.transaction_hash = d.validator_transaction_hash AND v.role = 'validator'
        WHERE d.role = 'delegator' AND d.rewarded_at IS NOT NULL AND d.realized_reward_navax > 0 AND v.regime NOT IN ({pre_cortina})
    )
    SELECT count(*), count(*) FILTER (WHERE abs(-fee_transfer_navax - round(potential_reward_navax * delegation_fee_rate)) <= 1) FROM d"""
PRE_CORTINA = ("genesis", "apricot_phase_1", "apricot_phase_2", "apricot_phase_3", "apricot_phase_4", "apricot_phase_5", "apricot_phase_pre_6", "apricot_phase_6", "apricot_phase_post_6", "banff")
FETCH_SIZE = 200_000

STAKES_SQL = """
CREATE OR REPLACE TABLE stakes AS
WITH unioned AS (
    SELECT transaction_hash, 'validator' AS role, tx_type, node_id, NULL::VARCHAR AS validator_transaction_hash,
           accepted_at, block_height, start_time, end_time, duration_days, stake_navax, stake_avax,
           potential_reward_navax, potential_reward_avax, rewarded, delegation_fee_rate
    FROM validators
    UNION ALL
    SELECT transaction_hash, 'delegator', tx_type, node_id, validator_transaction_hash,
           accepted_at, block_height, start_time, end_time, duration_days, stake_navax, stake_avax,
           potential_reward_navax, potential_reward_avax, rewarded, NULL::DOUBLE
    FROM delegators
)
SELECT s.*,
       coalesce(g.regime, 'genesis') AS regime,
       CASE WHEN s.start_time > s.accepted_at THEN 'pending' ELSE 'immediate' END AS start_kind,
       r.rewarded_at, r.realized_reward_navax, r.realized_reward_avax, r.fee_transfer_navax,
       u.supply_before_navax,
       NULL::BIGINT AS kernel_reward_navax,
       coalesce(c.cycles, 1) AS cycles, c.last_cycle_end_time
FROM unioned s
ASOF LEFT JOIN upgrades g ON s.accepted_at >= g.activated_at
LEFT JOIN rewards r ON r.staking_transaction_hash = s.transaction_hash
LEFT JOIN supply u USING (transaction_hash)
LEFT JOIN (SELECT validator_transaction_hash, count(*) AS cycles, max(end_time) AS last_cycle_end_time FROM cycles GROUP BY 1) c
       ON c.validator_transaction_hash = s.transaction_hash
"""

_COMPUTED = {"kernel_gap_navax": "kernel_reward_navax - potential_reward_navax AS kernel_gap_navax",
             "reproduced": "kernel_reward_navax = potential_reward_navax AS reproduced"}
PERIODS_SQL = f"""
SELECT {', '.join(_COMPUTED.get(name, name) for name in TABLE_COLUMNS)}
FROM stakes
ORDER BY accepted_at, transaction_hash
"""

SUMMARY_SQL = """
SELECT count(*) AS rows,
       count(*) FILTER (WHERE role = 'validator') AS validators,
       count(*) FILTER (WHERE role = 'delegator') AS delegators,
       count(*) FILTER (WHERE start_kind = 'immediate' AND kernel_reward_navax IS NOT NULL) AS immediate_rows,
       count(*) FILTER (WHERE start_kind = 'immediate' AND reproduced) AS immediate_reproduced,
       count(*) FILTER (WHERE start_kind = 'pending' AND kernel_reward_navax IS NOT NULL) AS pending_rows,
       count(*) FILTER (WHERE start_kind = 'pending' AND reproduced) AS pending_reproduced,
       count(*) FILTER (WHERE supply_before_navax IS NULL) AS gap_without_supply_row,
       count(*) FILTER (WHERE supply_before_navax IS NOT NULL AND kernel_reward_navax IS NULL) AS kernel_failed,
       count(*) FILTER (WHERE rewarded_at IS NOT NULL) AS with_reward_row,
       count(*) FILTER (WHERE rewarded_at IS NULL AND end_time < ?::TIMESTAMP AND tx_type <> 'AddAutoRenewedValidatorTx') AS gap_ended_without_reward_row,
       count(*) FILTER (WHERE rewarded_at IS NULL AND end_time >= ?::TIMESTAMP) AS open_periods,
       count(*) FILTER (WHERE realized_reward_navax = 0) AS zero_realized,
       count(DISTINCT transaction_hash) AS distinct_hashes,
       min(accepted_at) AS accepted_from, max(accepted_at) AS accepted_to
FROM periods
"""


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


def upgrade_schedule() -> list[dict[str, str]]:
    return [{"name": item.name, "activated_at": item.activated_at.isoformat().replace("+00:00", "Z")} for item in MAINNET_UPGRADES.upgrades]


def select_inputs(pinned: dict[str, str] | None, root: Path | None) -> list[dict[str, Any]]:
    """The input runs: pinned by ``dataset_id=run`` or the newest built run of each input."""
    pinned = pinned or {}
    unknown = sorted(set(pinned) - set(INPUTS.values()) - set(OPTIONAL_INPUTS.values()) - set(seam.SEAMED.values()))
    if unknown:
        raise DataError(f"not an input of {DATASET_ID}: {', '.join(unknown)}")
    selected = []
    for input_id, share_id in {**INPUTS, **OPTIONAL_INPUTS}.items():
        dataset_id, run = seam.resolve(share_id, pinned, root)
        if input_id in OPTIONAL_INPUTS and run is None and not datasets.runs(dataset_id, root):
            continue
        record = datasets.receipt(dataset_id, run, root)
        parquet = datasets.parquet_path(dataset_id, run, root)
        body = parquet.read_bytes()
        selected.append({
            "input_id": input_id, "dataset_id": dataset_id, "run": record["run"],
            "capture_id": record["capture"]["capture_id"], "contract_sha256": record["capture"].get("contract_sha256"),
            "captured_at": record["capture"].get("completed_at"), "rows": record["build"].get("summary", {}).get("rows"),
            "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet,
        })
    return selected


def load_inputs(connection: Any, inputs: list[dict[str, Any]]) -> None:
    names = {"validator-stakes": "validators", "delegator-stakes": "delegators", "staking-rewards": "rewards", "staking-supply": "supply",
             "p-staking-cycles": "cycles"}
    for item in inputs:
        path = str(item["path"]).replace("'", "''")
        connection.execute(f"CREATE OR REPLACE VIEW {names[item['input_id']]} AS SELECT * FROM read_parquet('{path}')")
    if not any(item["input_id"] == "p-staking-cycles" for item in inputs):
        connection.execute("CREATE OR REPLACE TABLE cycles(validator_transaction_hash VARCHAR, cycle INTEGER, end_time TIMESTAMP)")
    connection.execute("CREATE OR REPLACE TABLE upgrades(regime VARCHAR, activated_at TIMESTAMP)")
    for item in MAINNET_UPGRADES.upgrades:
        connection.execute("INSERT INTO upgrades VALUES (?, ?)", [item.name, item.activated_at.replace(tzinfo=None)])


def compute(connection: Any) -> None:
    """Build ``stakes`` from the input views, then fill ``kernel_reward_navax`` row by row from the protocol formula."""
    try:
        connection.execute(STAKES_SQL)
    except duckdb.Error as error:
        raise DataError(f"input datasets do not match the declared shape: {error}") from error
    connection.execute("CREATE OR REPLACE TABLE kernel(transaction_hash VARCHAR, kernel_reward_navax BIGINT)")
    cursor = connection.cursor()
    cursor.execute(
        "SELECT transaction_hash, start_time, date_diff('second', start_time, end_time), stake_navax, supply_before_navax "
        "FROM stakes WHERE supply_before_navax IS NOT NULL"
    )
    while batch := cursor.fetchmany(FETCH_SIZE):
        hashes, rewards = [], []
        for transaction_hash, start, duration, stake, supply in batch:
            try:
                reward = primary_network_reward(start.replace(tzinfo=timezone.utc), duration, stake, supply)
            except ModelError:
                reward = None
            hashes.append(transaction_hash)
            rewards.append(reward)
        frame = pd.DataFrame({"transaction_hash": hashes, "kernel_reward_navax": pd.array(rewards, dtype="Int64")})
        connection.register("kernel_batch", frame)
        connection.execute("INSERT INTO kernel SELECT transaction_hash, kernel_reward_navax FROM kernel_batch")
        connection.unregister("kernel_batch")
    cursor.close()
    connection.execute(
        "UPDATE stakes SET kernel_reward_navax = kernel.kernel_reward_navax FROM kernel WHERE stakes.transaction_hash = kernel.transaction_hash"
    )
    connection.execute(f"CREATE OR REPLACE VIEW periods AS {PERIODS_SQL}")


def reward_horizon(connection: Any) -> str:
    """The latest reward the log holds: a period that ended later cannot have a reward row yet. The capture time is not
    used, because a seamed or lagging input holds data well short of when it was built."""
    latest = connection.execute("SELECT max(rewarded_at) FROM periods").fetchone()[0]
    return latest.isoformat(sep=" ") if latest is not None else "9999-12-31"


def summarize(connection: Any, as_of: str) -> dict[str, Any]:
    """Counts over ``periods``; ``as_of`` is the latest reward the log holds, which separates ended periods from open ones."""
    row = connection.execute(SUMMARY_SQL, [as_of, as_of]).fetchone()
    keys = [
        "rows", "validators", "delegators", "immediate_rows", "immediate_reproduced", "pending_rows", "pending_reproduced",
        "gap_without_supply_row", "kernel_failed", "with_reward_row", "gap_ended_without_reward_row", "open_periods",
        "zero_realized", "distinct_hashes", "accepted_from", "accepted_to",
    ]
    summary = dict(zip(keys, row))
    for key in ("accepted_from", "accepted_to"):
        summary[key] = summary[key].isoformat(timespec="seconds") + "Z" if summary[key] is not None else None
    summary["immediate_reproduced_share"] = summary["immediate_reproduced"] / summary["immediate_rows"] if summary["immediate_rows"] else None
    summary["pending_reproduced_share"] = summary["pending_reproduced"] / summary["pending_rows"] if summary["pending_rows"] else None
    summary["auto_renewed_periods"], summary["auto_renewed_cycles"] = connection.execute(
        "SELECT count(*), coalesce(sum(cycles), 0) FROM periods WHERE tx_type = 'AddAutoRenewedValidatorTx'").fetchone()
    placeholders = ", ".join("?" for _ in PRE_CORTINA)
    fee_rows, fee_matched = connection.execute(FEE_RECONCILIATION_SQL.format(pre_cortina=placeholders), list(PRE_CORTINA)).fetchone()
    summary["fee_reconciled_rows"] = fee_rows
    summary["fee_reconciled"] = fee_matched
    summary["fee_reconciled_share"] = fee_matched / fee_rows if fee_rows else None
    return summary


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    """Build the derived dataset into a new run directory holding ``capture/`` and ``dataset/``."""
    _reject(dataset_id)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    inputs = select_inputs(pinned, root)
    completed_at = now()
    schedule = upgrade_schedule()
    records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records, "upgrades": schedule}))
    capture_receipt = {
        "schema_version": "derived-capture/v1",
        "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
        "dataset_id": dataset_id,
        "source_id": SOURCE_ID,
        "completed_at": completed_at,
        "contract_sha256": contract_hash(catalog, dataset_id),
        "tool": f"avalanche-research@{__version__}",
        "inputs": records,
        "upgrades": schedule,
        "upgrades_sha256": sha256(canonical_bytes(schedule)),
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
            compute(connection)
            connection.execute("COPY periods TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection, reward_horizon(connection))
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
    """Verify the input runs still hash as recorded, the contract and upgrade schedule are unchanged, and the build holds."""
    if against is not None:
        raise DataError(f"{DATASET_ID} takes no --against directory")
    catalog = load_catalog()
    receipt = read_capture(capture_dir)
    findings: list[str] = []
    checked = ["input run hashes", "catalog contract", "upgrade schedule"]
    if receipt.get("contract_sha256") != contract_hash(catalog, DATASET_ID):
        findings.append("catalog contract changed since the capture")
    if receipt.get("upgrades_sha256") != sha256(canonical_bytes(upgrade_schedule())):
        findings.append("upgrade schedule changed since the capture")
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
        checked.extend(["build hashes", "unique periods", "kernel coverage", "immediate reproduction", "fee reconciliation"])
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
                connection.execute(f"CREATE VIEW periods AS SELECT * FROM read_parquet('{parquet}')")
                columns = [row[0] for row in connection.execute("DESCRIBE periods").fetchall()]
                if columns != list(TABLE_COLUMNS):
                    findings.append("Parquet columns differ from the declared fields")
                summary.update(summarize(connection, reward_horizon(connection)))
            finally:
                connection.close()
            if summary["rows"] != summary["distinct_hashes"]:
                findings.append(f"{summary['rows'] - summary['distinct_hashes']} staking transactions appear more than once")
            if summary["rows"] != summary["validators"] + summary["delegators"]:
                findings.append("rows are neither validator nor delegator")
            if summary["kernel_failed"]:
                findings.append(f"{summary['kernel_failed']} rows with a supply reading have no kernel reward")
            share = summary["immediate_reproduced_share"]
            if share is not None and share < IMMEDIATE_REPRODUCTION_FLOOR:
                findings.append(f"kernel reproduces {share:.4%} of immediate starts, below {IMMEDIATE_REPRODUCTION_FLOOR:.1%}")
            fee_share = summary["fee_reconciled_share"]
            if fee_share is not None and fee_share < FEE_RECONCILIATION_FLOOR:
                findings.append(f"delegator fee transfers reconcile to rate x potential on {fee_share:.4%} of post-Cortina rewarded delegations, below {FEE_RECONCILIATION_FLOOR:.1%}")
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
