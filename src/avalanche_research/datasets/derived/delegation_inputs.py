"""Delegation inputs at a model origin: the delegations open at the origin instant, each open validator's room for more
delegation, and the year of delegation flows before it, by day and one row per started delegation. A model with delegations starts from this state, and its
delegation blocks are fitted on these flows.

Open follows the replay's rule: a period started by 23:59:59 UTC on the origin day whose end, counting its last cycle, is
after that instant. The open delegations' count and stake therefore equal the replay's ``active_delegations`` and
``active_delegated_stake_navax`` on the origin day, and ``check`` confirms it. A delegation is BENQI's when BENQI's key
(attribution OA9) funds it and it was accepted on or after that key's evidence date (operator event NE6), so no row is
set apart before public evidence existed. A validator's room is its weight limit (``weeks.max_weight_sql``: five times
its stake, at most 3M AVAX from Apricot Phase 3) less its own stake and its open delegations.

A commitment accepted by the origin instant but starting after it is scheduled: the chain already holds it, and it will
add load. Before Durango a stake could be accepted up to two weeks before its start. ``scheduled`` lists those
validator and delegation periods, and each open validator's ``room_reserved_navax`` also subtracts its scheduled
delegations over their whole interval, a conservative bound on the room left for new delegations. A negative bound does
not show the chain over its limit: scheduled delegations that start after open ones end can fit. ``check`` counts these
validators as ``negative_reserved_room``. A consumer refuses new placements on them and keeps their commitments.

A consumer that places delegations from this state takes these tables as follows. It keeps a ledger per validator
period, keyed by its transaction hash, never per node. It starts each open validator with ``delegated_navax`` and each
scheduled validator period, from ``scheduled``, with none. Each scheduled delegation is reserved on its own validator
period from the origin and moves from reserved to open once, at its start. A delegation's load is released only at its
end. A new placement is reserved before the next placement reads the room. The weight limit is recomputed at each
placement from the period's own stake on that day, since the room here is the limit at the origin.

``build`` refuses inputs this reading would get wrong: a period row missing a time or stake, accepted after its
start, ending at or before its start, with negative stake, an unknown role or a repeated hash, or without a node. It
also refuses a delegation with two funding rows, and a delegation accepted by the origin and not yet ended that names no
validator period, names one of another node, names one accepted after the origin, or runs outside it.

Origins must fall before the validation lockbox's first day, as in the replay. Inputs are the staking-period log, for
start, end, stake and fee, and the seamed delegator stakes, for the funding address.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import duckdb
import pandas as pd

from ...core.catalog import DataError
from ...core.clock import LOCKBOX_FIRST_DAY
from .weeks import max_weight_sql

BENQI_FUNDING = "avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy"
BENQI_EVIDENCE = "2022-01-26 12:22:21"
FLOW_DAYS = 365

PERIODS_SQL = """
CREATE OR REPLACE TEMP VIEW p AS
SELECT transaction_hash, role, node_id, validator_transaction_hash, accepted_at, start_time, stake_navax, delegation_fee_rate,
       end_time AS committed_end_time, greatest(end_time, coalesce(last_cycle_end_time, end_time)) AS leave_time
FROM read_parquet('{periods}') WHERE start_time IS NOT NULL AND end_time IS NOT NULL AND stake_navax IS NOT NULL
"""
SOURCE_SQL = """
SELECT count(*) FILTER (WHERE transaction_hash IS NULL OR node_id IS NULL OR accepted_at IS NULL OR start_time IS NULL
                         OR end_time IS NULL OR stake_navax IS NULL) AS missing_fields,
       count(*) FILTER (WHERE accepted_at > start_time) AS accepted_after_start,
       count(*) FILTER (WHERE start_time >= end_time) AS empty_interval,
       count(*) FILTER (WHERE stake_navax < 0) AS negative_stake,
       count(*) FILTER (WHERE role IS NULL OR role NOT IN ('validator', 'delegator')) AS unknown_role,
       count(transaction_hash) - count(DISTINCT transaction_hash) AS repeated_hash
FROM read_parquet('{periods}')
"""
ASSOCIATION_SQL = """
WITH r AS (SELECT * FROM d WHERE accepted_at <= ?::TIMESTAMP AND end_time > ?::TIMESTAMP)
SELECT (SELECT count(*) FROM (SELECT transaction_hash FROM f GROUP BY 1 HAVING count(*) > 1)) AS repeated_funding,
       count(*) FILTER (WHERE v.transaction_hash IS NULL) AS no_validator_period,
       count(*) FILTER (WHERE v.transaction_hash IS NOT NULL AND v.node_id IS DISTINCT FROM r.node_id) AS other_node,
       count(*) FILTER (WHERE v.accepted_at > ?::TIMESTAMP) AS validator_accepted_after_origin,
       count(*) FILTER (WHERE r.start_time < v.start_time OR r.end_time > v.leave_time) AS outside_validator_period
FROM r LEFT JOIN p v ON v.transaction_hash = r.validator_transaction_hash AND v.role = 'validator'
"""
FUNDING_SQL = "CREATE OR REPLACE TEMP VIEW f AS SELECT transaction_hash, delegator_address FROM read_parquet('{delegators}')"
DELEGATIONS_SQL = f"""
SELECT p.transaction_hash, p.node_id, p.validator_transaction_hash, f.delegator_address,
       coalesce(f.delegator_address = '{BENQI_FUNDING}' AND p.accepted_at >= TIMESTAMP '{BENQI_EVIDENCE}', false) AS benqi,
       p.accepted_at, p.start_time, p.leave_time AS end_time, p.committed_end_time, p.stake_navax
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
                   FROM d WHERE start_time <= ?::TIMESTAMP AND end_time > ?::TIMESTAMP GROUP BY 1),
             s AS (SELECT validator_transaction_hash, count(*) AS scheduled, sum(stake_navax) AS scheduled_navax
                   FROM d WHERE accepted_at <= ?::TIMESTAMP AND start_time > ?::TIMESTAMP GROUP BY 1)
        SELECT v.transaction_hash, v.node_id, v.stake_navax, v.delegation_fee_rate, v.leave_time AS end_time,
               coalesce(o.delegations, 0)::INTEGER AS delegations, coalesce(o.delegated_navax, 0)::BIGINT AS delegated_navax,
               ({limit})::BIGINT AS max_weight_navax,
               (({limit}) - v.stake_navax - coalesce(o.delegated_navax, 0))::BIGINT AS room_navax,
               coalesce(s.scheduled, 0)::INTEGER AS scheduled_delegations, coalesce(s.scheduled_navax, 0)::BIGINT AS scheduled_delegated_navax,
               (({limit}) - v.stake_navax - coalesce(o.delegated_navax, 0) - coalesce(s.scheduled_navax, 0))::BIGINT AS room_reserved_navax
        FROM v LEFT JOIN o ON o.validator_transaction_hash = v.transaction_hash
               LEFT JOIN s ON s.validator_transaction_hash = v.transaction_hash ORDER BY v.node_id, v.transaction_hash
        """, [instant] * 9).df()


def scheduled(connection: duckdb.DuckDBPyConnection, origin: date) -> pd.DataFrame:
    """Validator and delegation periods accepted by the origin instant that start after it."""
    instant = origin_instant(origin)
    return connection.execute("""
        SELECT p.role, p.transaction_hash, p.node_id, p.validator_transaction_hash, p.accepted_at, p.start_time, p.leave_time AS end_time,
               p.stake_navax, d.delegator_address, coalesce(d.benqi, false) AS benqi
        FROM p LEFT JOIN d USING (transaction_hash)
        WHERE p.accepted_at <= ?::TIMESTAMP AND p.start_time > ?::TIMESTAMP ORDER BY p.start_time, p.transaction_hash
        """, [instant, instant]).df()


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


def refusals(connection: duckdb.DuckDBPyConnection, periods_parquet: str, origin: date) -> dict[str, int]:
    """Counts of the source conditions ``build`` refuses, each zero for valid inputs."""
    instant = origin_instant(origin)
    source = connection.execute(SOURCE_SQL.format(periods=periods_parquet.replace("'", "''"))).df().iloc[0]
    association = connection.execute(ASSOCIATION_SQL, [instant, instant, instant]).df().iloc[0]
    return {name: int(value) for name, value in {**source.to_dict(), **association.to_dict()}.items()}


def starts(connection: duckdb.DuckDBPyConnection, origin: date, days: int = FLOW_DAYS) -> pd.DataFrame:
    """Every delegation started in the ``days`` UTC days up to the origin instant, one row each: its stake, its committed
    days from start to its stated end, BENQI's flag by the rule above, and its acceptance time. The daily flows' starts
    are these rows counted by day."""
    instant = origin_instant(origin)
    return connection.execute("""
        SELECT transaction_hash, node_id, validator_transaction_hash, delegator_address, benqi, accepted_at, start_time,
               committed_end_time, epoch(committed_end_time - start_time) / 86400.0 AS days, stake_navax
        FROM d WHERE start_time > ?::TIMESTAMP AND start_time <= ?::TIMESTAMP ORDER BY start_time, transaction_hash
        """, [instant - timedelta(days=days), instant]).df()


def build(periods_parquet: str, delegators_parquet: str, origin: date) -> dict[str, pd.DataFrame]:
    connection = _connect(periods_parquet, delegators_parquet)
    try:
        found = {name: count for name, count in refusals(connection, periods_parquet, origin).items() if count}
        if found:
            raise DataError(f"delegation inputs at {origin} refused: " + ", ".join(f"{name} {count}" for name, count in found.items()))
        return {"open": open_delegations(connection, origin), "validators": validator_room(connection, origin),
                "scheduled": scheduled(connection, origin), "flows": flows(connection, origin), "starts": starts(connection, origin)}
    finally:
        connection.close()


def check(inputs: dict[str, pd.DataFrame], replay_day: pd.Series) -> dict:
    """The open delegations against the replay's stocks on the origin day, and room never below zero after Apricot 3."""
    opened = inputs["open"]
    result = {"delegations": len(opened), "replay_delegations": int(replay_day["active_delegations"]),
              "delegated_navax": int(opened["stake_navax"].sum()), "replay_delegated_navax": int(replay_day["active_delegated_stake_navax"]),
              "unfunded": int(opened["delegator_address"].isna().sum()), "benqi": int(opened["benqi"].sum()),
              "validators": len(inputs["validators"]), "over_limit": int((inputs["validators"]["room_navax"] < 0).sum()),
              "scheduled": len(inputs["scheduled"]), "negative_reserved_room": int((inputs["validators"]["room_reserved_navax"] < 0).sum())}
    result["equal"] = (result["delegations"] == result["replay_delegations"]
                       and result["delegated_navax"] == result["replay_delegated_navax"])
    return result
