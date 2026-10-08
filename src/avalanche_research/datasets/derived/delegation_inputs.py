"""Delegation inputs at a model origin: the delegations open at the origin instant, each open validator's room for more
delegation, and the year of delegation flows before it. A model with delegations starts from this state, and its
delegation blocks are fitted on these flows.

Open follows the replay's rule: a period started by 23:59:59 UTC on the origin day whose end, counting its last cycle, is
after that instant. The open delegations' count and stake therefore equal the replay's ``active_delegations`` and
``active_delegated_stake_navax`` on the origin day, and ``check`` confirms it. A delegation is BENQI's when BENQI's key
(attribution OA9) funds it and it was accepted on or after that key's evidence date (operator event NE6), so no row is
set apart before public evidence existed. A validator's room is its weight limit (``weeks.max_weight_sql``: five times
its stake, at most 3M AVAX from Apricot Phase 3) less its own stake and its open delegations.

Origins must fall before the validation lockbox's first day, as in the replay. Inputs are the staking-period log, for
start, end, stake and fee, and the seamed delegator stakes, for the funding address.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import duckdb
import pandas as pd

from ...core.clock import LOCKBOX_FIRST_DAY
from .weeks import max_weight_sql

BENQI_FUNDING = "avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy"
BENQI_EVIDENCE = "2022-01-26 12:22:21"
FLOW_DAYS = 365

PERIODS_SQL = """
CREATE OR REPLACE TEMP VIEW p AS
SELECT transaction_hash, role, node_id, validator_transaction_hash, accepted_at, start_time, stake_navax, delegation_fee_rate,
       greatest(end_time, coalesce(last_cycle_end_time, end_time)) AS leave_time
FROM read_parquet('{periods}') WHERE start_time IS NOT NULL AND end_time IS NOT NULL AND stake_navax IS NOT NULL
"""
FUNDING_SQL = "CREATE OR REPLACE TEMP VIEW f AS SELECT transaction_hash, delegator_address FROM read_parquet('{delegators}')"
DELEGATIONS_SQL = f"""
SELECT p.transaction_hash, p.node_id, p.validator_transaction_hash, f.delegator_address,
       coalesce(f.delegator_address = '{BENQI_FUNDING}' AND p.accepted_at >= TIMESTAMP '{BENQI_EVIDENCE}', false) AS benqi,
       p.accepted_at, p.start_time, p.leave_time AS end_time, p.stake_navax
FROM p LEFT JOIN f USING (transaction_hash) WHERE p.role = 'delegator'
"""


def origin_instant(origin: date) -> datetime:
    if origin >= LOCKBOX_FIRST_DAY:
        raise ValueError(f"origin {origin} is on or after the validation lockbox's first day, {LOCKBOX_FIRST_DAY}")
    return datetime.combine(origin, datetime.min.time()) + timedelta(days=1, seconds=-1)


def _connect(periods_parquet: str, delegators_parquet: str) -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect()
    connection.execute(PERIODS_SQL.format(periods=periods_parquet.replace("'", "''")))
    connection.execute(FUNDING_SQL.format(delegators=delegators_parquet.replace("'", "''")))
    connection.execute(f"CREATE OR REPLACE TEMP VIEW d AS {DELEGATIONS_SQL}")
    return connection


def open_delegations(connection: duckdb.DuckDBPyConnection, origin: date) -> pd.DataFrame:
    """Every delegation open at the origin instant, with days left to its end and its validator's fee rate."""
    instant = origin_instant(origin)
    return connection.execute("""
        SELECT d.*, ceil(epoch(d.end_time - ?::TIMESTAMP) / 86400)::INTEGER AS days_left, v.delegation_fee_rate
        FROM d LEFT JOIN p v ON v.transaction_hash = d.validator_transaction_hash AND v.role = 'validator'
        WHERE d.start_time <= ?::TIMESTAMP AND d.end_time > ?::TIMESTAMP ORDER BY d.start_time, d.transaction_hash
        """, [instant, instant, instant]).df()


def validator_room(connection: duckdb.DuckDBPyConnection, origin: date) -> pd.DataFrame:
    """Every validator period open at the origin instant, its delegations open then, its weight limit and its room."""
    instant = origin_instant(origin)
    limit = max_weight_sql("?::TIMESTAMP", "v.stake_navax")
    return connection.execute(f"""
        WITH v AS (SELECT * FROM p WHERE role = 'validator' AND start_time <= ?::TIMESTAMP AND leave_time > ?::TIMESTAMP),
             o AS (SELECT validator_transaction_hash, count(*) AS delegations, sum(stake_navax) AS delegated_navax
                   FROM d WHERE start_time <= ?::TIMESTAMP AND end_time > ?::TIMESTAMP GROUP BY 1)
        SELECT v.transaction_hash, v.node_id, v.stake_navax, v.delegation_fee_rate, v.leave_time AS end_time,
               coalesce(o.delegations, 0)::INTEGER AS delegations, coalesce(o.delegated_navax, 0)::BIGINT AS delegated_navax,
               ({limit})::BIGINT AS max_weight_navax,
               (({limit}) - v.stake_navax - coalesce(o.delegated_navax, 0))::BIGINT AS room_navax
        FROM v LEFT JOIN o ON o.validator_transaction_hash = v.transaction_hash ORDER BY v.node_id, v.transaction_hash
        """, [instant, instant, instant, instant, instant, instant]).df()


def flows(connection: duckdb.DuckDBPyConnection, origin: date, days: int = FLOW_DAYS) -> pd.DataFrame:
    """Daily delegation starts and ends in the ``days`` UTC days up to the origin day, BENQI's apart from the rest."""
    instant = origin_instant(origin)
    first = instant - timedelta(days=days)
    return connection.execute("""
        WITH e AS (
            SELECT CAST(start_time AS DATE) AS date_utc, benqi, 1 AS started, 0 AS ended, stake_navax AS started_navax, 0 AS ended_navax
            FROM d WHERE start_time > ?::TIMESTAMP AND start_time <= ?::TIMESTAMP
            UNION ALL
            SELECT CAST(end_time AS DATE), benqi, 0, 1, 0, stake_navax
            FROM d WHERE end_time > ?::TIMESTAMP AND end_time <= ?::TIMESTAMP
        )
        SELECT date_utc, benqi, sum(started)::INTEGER AS started, sum(ended)::INTEGER AS ended,
               sum(started_navax)::BIGINT AS started_navax, sum(ended_navax)::BIGINT AS ended_navax
        FROM e GROUP BY 1, 2 ORDER BY 1, 2
        """, [first, instant, first, instant]).df()


def build(periods_parquet: str, delegators_parquet: str, origin: date) -> dict[str, pd.DataFrame]:
    connection = _connect(periods_parquet, delegators_parquet)
    try:
        return {"open": open_delegations(connection, origin), "validators": validator_room(connection, origin),
                "flows": flows(connection, origin)}
    finally:
        connection.close()


def check(inputs: dict[str, pd.DataFrame], replay_day: pd.Series) -> dict:
    """The open delegations against the replay's stocks on the origin day, and room never below zero after Apricot 3."""
    opened = inputs["open"]
    result = {"delegations": len(opened), "replay_delegations": int(replay_day["active_delegations"]),
              "delegated_navax": int(opened["stake_navax"].sum()), "replay_delegated_navax": int(replay_day["active_delegated_stake_navax"]),
              "unfunded": int(opened["delegator_address"].isna().sum()), "benqi": int(opened["benqi"].sum()),
              "validators": len(inputs["validators"]), "over_limit": int((inputs["validators"]["room_navax"] < 0).sum())}
    result["equal"] = (result["delegations"] == result["replay_delegations"]
                       and result["delegated_navax"] == result["replay_delegated_navax"])
    return result
