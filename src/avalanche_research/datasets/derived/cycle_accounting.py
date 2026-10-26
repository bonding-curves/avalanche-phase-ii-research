"""Cycle-recognised rewards and effective validator weights, preserving transaction grain.

Ordinary net reward outputs retain their existing timing. At an auto-renewed
cycle event, recognise its current eligible self reward and pending commission
once, whether withdrawn or restaked. Prior restakes released on exit are a
liquidity transfer, not new issuance. Chain proposal/option support is required.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, time
from typing import Any

from ...core.catalog import DataError
from ...domain import protocol
from ...domain.protocol.types import ModelError

EVENT_COLUMNS = {
    "validator_transaction_hash": "VARCHAR", "node_id": "VARCHAR", "cycle": "INTEGER",
    "reward_transaction_hash": "VARCHAR", "rewarded_at": "TIMESTAMP", "rewarded": "BOOLEAN",
    "proposal_block_id": "VARCHAR", "proposal_height": "BIGINT", "option_block_id": "VARCHAR", "option_height": "BIGINT",
    "current_validation_navax": "BIGINT", "current_delegatee_navax": "BIGINT", "recognised_reward_navax": "DECIMAL(38,0)",
    "restaked_validation_navax": "BIGINT", "restaked_delegatee_navax": "BIGINT",
    "current_liquid_validation_navax": "BIGINT", "current_liquid_delegatee_navax": "BIGINT",
    "prior_validation_release_navax": "BIGINT", "prior_delegatee_release_navax": "BIGINT",
    "liquid_total_navax": "DECIMAL(38,0)", "renews": "BOOLEAN",
}
COMPONENTS = ("restaked_validation_navax", "restaked_delegatee_navax", "withdrawn_validation_navax", "withdrawn_delegatee_navax")


def columns(connection: Any, table: str) -> set[str]:
    return {row[0] for row in connection.execute(f"DESCRIBE {table}").fetchall()}


def exists(connection: Any, table: str) -> bool:
    return connection.execute("SELECT count(*) FROM information_schema.tables WHERE table_name=?", [table]).fetchone()[0] > 0


def records(connection: Any, sql: str) -> list[dict[str, Any]]:
    cur = connection.execute(sql)
    return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]


def prepare(connection: Any, complete_through: str) -> dict[str, Any]:
    """Create cycle_events, monetary_reward_events and effective_stake_intervals.

    Inputs: staking_periods, staking_rewards, optional staking_cycles/cycle_blocks.
    Every closed cycle must have the chain's proposal and matching option.
    Complete history is required before replacing a parent or releasing accrual.
    """
    pcols = columns(connection, "staking_periods")
    auto = "tx_type='AddAutoRenewedValidatorTx'" if "tx_type" in pcols else (
        "last_cycle_end_time IS NOT NULL" if "last_cycle_end_time" in pcols else "FALSE")
    parents = records(connection, f"SELECT * FROM staking_periods WHERE {auto}")
    if len({p["transaction_hash"] for p in parents}) != len(parents):
        raise DataError("duplicate auto-renewed parent")
    parent_map = {p["transaction_hash"]: p for p in parents}
    cycles = records(connection, "SELECT * FROM staking_cycles ORDER BY validator_transaction_hash,cycle") if exists(connection, "staking_cycles") else []
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in cycles:
        groups.setdefault(row["validator_transaction_hash"], []).append(row)
    if set(groups) != set(parent_map):
        raise DataError("auto-renewed parents need exact matching complete cycle histories")
    connection.execute("CREATE OR REPLACE TABLE cycle_events(" + ",".join(f"{k} {v}" for k, v in EVENT_COLUMNS.items()) + ")")
    connection.execute("CREATE OR REPLACE TABLE cycle_stock(role VARCHAR,start_time TIMESTAMP,end_time TIMESTAMP,stake_navax BIGINT)")
    connection.execute("CREATE OR REPLACE TABLE cycle_parents(transaction_hash VARCHAR)")
    if parents:
        connection.executemany("INSERT INTO cycle_parents VALUES (?)", [(p["transaction_hash"],) for p in parents])
    closed = [c for c in cycles if c["rewarded"] is not None]
    if len({c["reward_transaction_hash"] for c in closed}) != len(closed) or any(c["reward_transaction_hash"] is None for c in closed):
        raise DataError("closed cycles need unique reward transaction identities")
    supported: dict[tuple[str, int], list[dict[str, Any]]] = {}
    if closed:
        if not exists(connection, "cycle_blocks"):
            raise DataError("closed cycles need their pinned proposal/option blocks")
        sql = """WITH options AS (
          SELECT DISTINCT block_height,block_id,parent_id,block_time,block_type FROM cycle_blocks WHERE block_type IN ('commit','abort'))
          SELECT c.validator_transaction_hash,c.cycle,p.block_height AS proposal_height,p.block_id AS proposal_block_id,
                 p.block_time AS proposal_time,p.block_type AS proposal_type,p.tx_type,p.unsigned_tx,o.block_height AS option_height,o.block_id AS option_block_id,
                 o.block_time AS option_time,o.block_type AS option_type
          FROM staking_cycles c JOIN cycle_blocks p ON p.transaction_hash=c.reward_transaction_hash
          LEFT JOIN options o ON o.parent_id=p.block_id
          WHERE c.rewarded IS NOT NULL"""
        for row in records(connection, sql):
            supported.setdefault((row["validator_transaction_hash"], row["cycle"]), []).append(row)
    event_rows, stock_rows = [], []
    horizon = datetime.combine(datetime.fromisoformat(complete_through).date(), time(23, 59, 59))
    for tx, history in groups.items():
        parent = parent_map[tx]
        if parent.get("role") != "validator" or not parent.get("node_id"):
            raise DataError("auto parent lacks validator identity")
        if history[0]["end_time"] != parent["end_time"]:
            raise DataError("first cycle differs from the transaction's original period")
        if "cycles" in parent and parent["cycles"] != len(history):
            raise DataError("cycle history count differs from parent source")
        if parent.get("last_cycle_end_time") is not None and parent["last_cycle_end_time"] != history[-1]["end_time"]:
            raise DataError("cycle history extent differs from parent source")
        if parent.get("stake_navax") is None or parent["stake_navax"] <= 0:
            raise DataError("auto parent needs positive stake")
        weight, accrued_v, accrued_d = int(parent["stake_navax"]), 0, 0
        previous_end = parent["start_time"]
        next_duration = None
        previous_renews = True
        for index, c in enumerate(history, 1):
            if (c["cycle"] != index or not previous_renews or c["start_time"] != previous_end
                    or c["weight_navax"] != weight or c["node_id"] != parent["node_id"] or c["end_time"] <= c["start_time"]):
                raise DataError("noncontiguous or inconsistent cycle identity, times or weight")
            if next_duration is not None and (c["end_time"] - c["start_time"]).total_seconds() != next_duration:
                raise DataError("cycle duration differs from the prior renewal period")
            if c["potential_reward_navax"] is None or c["potential_reward_navax"] < 0:
                raise DataError("cycle lacks a non-negative recorded potential reward")
            stock_rows.append(("validator", c["start_time"], c["end_time"], weight))
            previous_end = c["end_time"]
            if c["rewarded"] is None:
                if (index != len(history) or c["end_time"] <= horizon or c["reward_transaction_hash"] is not None
                        or any(c[k] is not None for k in (*COMPONENTS, "delegatee_reward_navax", "next_period_seconds"))):
                    raise DataError("unresolved cycle cannot certify a completed daily stock/outcome")
                continue
            support = supported.get((tx, index), [])
            if len(support) != 1:
                raise DataError("closed cycle needs one unique proposal/option support")
            b = support[0]
            try:
                unsigned = json.loads(b["unsigned_tx"])
                if (unsigned.get("txID") != tx or type(unsigned.get("timestamp")) is not int
                        or unsigned["timestamp"] != int(c["end_time"].replace(tzinfo=UTC).timestamp())):
                    raise ValueError("parent or end differs")
            except (TypeError, ValueError, AttributeError) as error:
                raise DataError("reward transaction does not name this cycle parent and end") from error
            if (b["proposal_type"] != "proposal" or not b["proposal_block_id"] or not b["option_block_id"]
                    or b["proposal_height"] is None or b["option_height"] is None
                    or b["tx_type"] != "RewardAutoRenewedValidatorTx" or b["option_type"] != ("commit" if c["rewarded"] else "abort")
                    or b["option_height"] != b["proposal_height"] + 1
                    or b["proposal_time"] != c["end_time"] or b["option_time"] != c["end_time"]):
                raise DataError("cycle proposal/option branch or chain timestamp disagrees")
            try:
                potential, delegatee = int(c["potential_reward_navax"]), int(c["delegatee_reward_navax"])
                actual = tuple(int(c[k]) for k in COMPONENTS)
                period = int(c["next_period_seconds"])
                if min(potential, delegatee, period, *actual) < 0:
                    raise ValueError("negative amount")
            except (TypeError, ValueError) as error:
                raise DataError("closed cycle has missing or invalid amounts") from error
            renews = bool(c["rewarded"] and period > 0)
            next_duration = period if renews else None
            try:
                expected = protocol.auto_renew_restake(potential, delegatee, int(c["auto_compound_shares"]), weight) if renews else (
                    0, 0, potential if c["rewarded"] else 0, delegatee)
            except (TypeError, ValueError, ModelError) as error:
                raise DataError("cycle configuration is inconsistent with protocol rules") from error
            if actual != expected:
                raise DataError("cycle reward components disagree with pinned protocol rules")
            rv, rd, pv, pd = actual
            prior_v, prior_d = (0, 0) if renews else (accrued_v, accrued_d)
            new_v = potential if c["rewarded"] else 0
            event_rows.append((tx, c["node_id"], index, c["reward_transaction_hash"], b["proposal_time"], c["rewarded"],
                               b["proposal_block_id"], b["proposal_height"], b["option_block_id"], b["option_height"],
                               new_v, delegatee, new_v + delegatee, rv, rd, pv, pd, prior_v, prior_d,
                               pv + pd + prior_v + prior_d, renews))
            accrued_v += rv
            accrued_d += rd
            weight += rv + rd
            previous_renews = renews
            if renews and index == len(history):
                raise DataError("renewed cycle lacks its next running period")
    if event_rows:
        connection.executemany("INSERT INTO cycle_events VALUES (" + ",".join("?" for _ in EVENT_COLUMNS) + ")", event_rows)
    if stock_rows:
        connection.executemany("INSERT INTO cycle_stock VALUES (?,?,?,?)", stock_rows)
    connection.execute(f"CREATE OR REPLACE VIEW effective_stake_intervals AS SELECT role,start_time,end_time,stake_navax "
                       f"FROM staking_periods WHERE NOT coalesce({auto},FALSE) UNION ALL SELECT * FROM cycle_stock")
    rcols = columns(connection, "staking_rewards")
    if "staking_tx_type" in rcols and "staking_transaction_hash" in rcols:
        unknown = connection.execute("SELECT count(*) FROM staking_rewards r WHERE staking_tx_type='AddAutoRenewedValidatorTx' "
                                     "AND NOT EXISTS(SELECT 1 FROM cycle_parents c WHERE c.transaction_hash=r.staking_transaction_hash)").fetchone()[0]
        if unknown:
            raise DataError("ordinary auto payout lacks its complete parent cycle history")
    if parents and "staking_transaction_hash" not in rcols:
        raise DataError("ordinary reward source lacks its staking identity")
    exclusion = ("WHERE NOT EXISTS(SELECT 1 FROM cycle_parents c WHERE c.transaction_hash=r.staking_transaction_hash)"
                 if "staking_transaction_hash" in rcols else "")
    connection.execute("CREATE OR REPLACE VIEW monetary_reward_events AS "
                       "SELECT rewarded_at,realized_reward_navax::DECIMAL(38,0) AS recognised_reward_navax "
                       f"FROM staking_rewards r {exclusion} UNION ALL SELECT rewarded_at,recognised_reward_navax FROM cycle_events")
    return {"basis": "ordinary-net-payout-plus-cycle-current-recognition/v1", "parents": len(parents),
            "cycles": len(cycles), "closed_events": len(event_rows),
            "cycle_recognised_navax": sum(r[12] for r in event_rows),
            "prior_accrual_released_navax": sum(r[17] + r[18] for r in event_rows)}
