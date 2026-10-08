"""The market layer: what a validator could know when it made each commitment, one row per validator period.

The decision instant is the period's acceptance. Every market series is read as of the last UTC day before the decision
day, never the same day, so no row uses information from after its decision:

- the protocol's annual reward rate for each menu duration, at the decision's stake, start and supply counter;
- AVAX price and its trailing 30-day realized volatility;
- the 3-month Treasury bill rate;
- the staking ratio, active validator and delegated stake over total supply, from the monetary ledger.

Each row also carries what the chain already showed about the decision: the upgrade regime at acceptance, the first
upgrade the period's span crosses, the node's previous validator period with the delegated stake open on it at the
decision and its room under the weight limit, and whether the stake equals the previous stake plus its realized reward,
the sign of compounding. ``held_back`` marks decisions from the lockbox boundary on, which no fit may use before the
unseal.
"""

from __future__ import annotations

from datetime import UTC

import duckdb
import pandas as pd

from ...core.clock import LOCKBOX_START
from ...domain.protocol import MAINNET_UPGRADES, annualized_reward_rate
from .weeks import max_weight_sql

MENU_DAYS = (14, 30, 60, 90, 180, 365)
SECONDS_PER_DAY = 86_400


def _quoted(path: str) -> str:
    return path.replace("'", "''")


def decisions(periods_parquet: str) -> pd.DataFrame:
    """Validator periods with the node's previous period, the delegations open on it at the decision, and its room."""
    path = _quoted(periods_parquet)
    limit = max_weight_sql("v.accepted_at", "prev.stake_navax")
    return duckdb.sql(f"""
        WITH v AS (SELECT *, lag(transaction_hash) OVER w AS prev_hash FROM read_parquet('{path}') WHERE role = 'validator'
                   WINDOW w AS (PARTITION BY node_id ORDER BY start_time, transaction_hash)),
             d AS (SELECT validator_transaction_hash, start_time, greatest(end_time, coalesce(last_cycle_end_time, end_time)) AS leave_time,
                          stake_navax FROM read_parquet('{path}') WHERE role = 'delegator'),
             o AS (SELECT v.transaction_hash, sum(d.stake_navax) AS open_navax FROM v JOIN d ON d.validator_transaction_hash = v.prev_hash
                   AND d.start_time <= v.accepted_at AND d.leave_time > v.accepted_at GROUP BY 1)
        SELECT v.transaction_hash, v.node_id, v.accepted_at, v.start_time, v.end_time, v.duration_days, v.stake_navax, v.regime,
               v.supply_before_navax, v.prev_hash AS prev_transaction_hash, prev.stake_navax AS prev_stake_navax,
               prev.realized_reward_navax AS prev_reward_navax,
               coalesce(o.open_navax, 0)::BIGINT AS prev_delegated_open_navax,
               CASE WHEN prev.stake_navax IS NULL THEN NULL ELSE ({limit})::BIGINT - prev.stake_navax END AS prev_delegation_limit_navax
        FROM v LEFT JOIN v AS prev ON prev.transaction_hash = v.prev_hash LEFT JOIN o ON o.transaction_hash = v.transaction_hash
        ORDER BY v.accepted_at, v.transaction_hash
        """).df()


def menu_rates(frame: pd.DataFrame) -> pd.DataFrame:
    """The protocol's annual rate for each menu duration, at each decision's stake, start and supply counter."""
    rates = {days: [] for days in MENU_DAYS}
    for start, stake, supply in zip(frame["start_time"], frame["stake_navax"], frame["supply_before_navax"], strict=True):
        for days in MENU_DAYS:
            if pd.isna(supply) or pd.isna(stake):
                rates[days].append(None)
            else:
                moment = pd.Timestamp(start).tz_localize(UTC).to_pydatetime()
                rates[days].append(annualized_reward_rate(moment, days * SECONDS_PER_DAY, int(stake), int(supply)))
    return pd.DataFrame({f"rate_{days}d": values for days, values in rates.items()}, index=frame.index)


def upgrade_crossed(frame: pd.DataFrame) -> pd.Series:
    """The first upgrade activated after a period's start and before its end, or None."""
    crossed = []
    for start, end in zip(frame["start_time"], frame["end_time"], strict=True):
        begin, finish = pd.Timestamp(start).tz_localize(UTC), pd.Timestamp(end).tz_localize(UTC)
        crossed.append(next((u.name for u in MAINNET_UPGRADES.upgrades if begin < u.activated_at < finish), None))
    return pd.Series(crossed, index=frame.index, dtype="object")


def as_of(frame: pd.DataFrame, price_parquet: str, tbill_parquet: str, ledger_parquet: str) -> pd.DataFrame:
    """Each series' last recorded value on a UTC day before the decision day. Days with no value, such as market
    holidays in the Treasury series, are skipped rather than read as missing. The price series repeats some dates, and
    the last observation of a day is taken."""
    keys = frame[["transaction_hash", "accepted_at"]].assign(decision_day=frame["accepted_at"].dt.normalize())
    connection = duckdb.connect()
    try:
        connection.register("k", keys)
        return connection.execute(f"""
            WITH p AS (SELECT observation_date::TIMESTAMP AS day, arg_max(price_usd, observed_at) AS price_usd,
                              arg_max(realized_volatility_30d, observed_at) AS realized_volatility_30d
                       FROM read_parquet('{_quoted(price_parquet)}') WHERE price_usd IS NOT NULL GROUP BY 1),
                 t AS (SELECT date_utc::TIMESTAMP AS day, discount_rate_pct FROM read_parquet('{_quoted(tbill_parquet)}')
                       WHERE discount_rate_pct IS NOT NULL),
                 l AS (SELECT date_utc::TIMESTAMP AS day,
                              (active_validator_stake_wei + active_delegated_stake_wei)::DOUBLE / total_supply_close_wei::DOUBLE AS staking_ratio
                       FROM read_parquet('{_quoted(ledger_parquet)}') WHERE complete)
            SELECT k.transaction_hash, p.day AS price_day, p.price_usd, p.realized_volatility_30d AS volatility_30d,
                   t.day AS tbill_day, t.discount_rate_pct AS tbill_3m_pct, l.day AS ledger_day, l.staking_ratio
            FROM k
            ASOF LEFT JOIN p ON k.decision_day > p.day
            ASOF LEFT JOIN t ON k.decision_day > t.day
            ASOF LEFT JOIN l ON k.decision_day > l.day
            """).df()
    finally:
        connection.close()


def build(periods_parquet: str, price_parquet: str, tbill_parquet: str, ledger_parquet: str) -> pd.DataFrame:
    frame = decisions(periods_parquet)
    frame = pd.concat([frame, menu_rates(frame)], axis=1)
    frame["upgrade_crossed"] = upgrade_crossed(frame)
    frame["compounding"] = (frame["prev_stake_navax"].notna() & frame["prev_reward_navax"].notna()
                            & (frame["stake_navax"] == frame["prev_stake_navax"] + frame["prev_reward_navax"]))
    frame["held_back"] = frame["accepted_at"] >= LOCKBOX_START.replace(tzinfo=None)
    return frame.merge(as_of(frame, price_parquet, tbill_parquet, ledger_parquet), on="transaction_hash", how="left")
