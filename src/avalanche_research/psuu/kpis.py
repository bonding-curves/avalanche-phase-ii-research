"""The proposal's seven KPIs per trajectory, from a daily frame with the engine's columns.

``observed_daily`` builds the same daily frame from the ledger so a replay and the observed record are scored by
the same ``kpis`` function.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import numpy as np
import pandas as pd

from ..model.protocol import annualized_reward_rate
from ..model.types import NAVAX_PER_AVAX, SECONDS_PER_DAY

FRAME_COLUMNS = (
    "day", "date", "supply_avax", "validator_stake_avax", "delegated_stake_avax", "staking_ratio", "validator_count",
    "rewards_paid_avax", "reward_apr", "hhi", "net_inflation_annual", "validator_profit_usd_month",
)
KPI_COLUMNS = (
    "staking_ratio_final", "staking_ratio_mean", "validator_count_final", "decentralization_mean",
    "net_inflation_mean", "net_inflation_slope", "net_inflation_decreasing", "val_profitability_mean",
    "apr_volatility", "staking_volatility",
)
DAYS_PER_MONTH = 365 / 12
WEI_PER_AVAX = 10**18


def kpis(frame: pd.DataFrame) -> dict[str, float | bool]:
    """KPIs of one trajectory.

    - STAKING_RATIO: final and mean daily staking ratio.
    - VALIDATOR_COUNT: final validator count.
    - DECENTRALIZATION: mean of 1 - HHI.
    - NET_INFLATION: mean annualized net inflation, its least-squares slope per year, and whether that slope is
      negative (decreasing).
    - VAL_PROFITABILITY: mean monthly USD profit per validator.
    - APR_VOLATILITY: standard deviation of the daily reward APR.
    - STAKING_VOLATILITY: standard deviation of the daily change in staking ratio.
    """
    missing = [column for column in FRAME_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"daily frame lacks columns: {missing}")
    if len(frame) < 2:
        raise ValueError("KPIs need at least two days")
    ratio = frame["staking_ratio"].to_numpy(dtype=float)
    inflation = frame["net_inflation_annual"].to_numpy(dtype=float)
    years = frame["day"].to_numpy(dtype=float) / 365
    slope = float(np.polyfit(years, inflation, 1)[0])
    return {
        "staking_ratio_final": float(ratio[-1]),
        "staking_ratio_mean": float(ratio.mean()),
        "validator_count_final": float(frame["validator_count"].iloc[-1]),
        "decentralization_mean": float((1 - frame["hhi"].to_numpy(dtype=float)).mean()),
        "net_inflation_mean": float(inflation.mean()),
        "net_inflation_slope": slope,
        "net_inflation_decreasing": bool(slope < 0),
        "val_profitability_mean": float(frame["validator_profit_usd_month"].to_numpy(dtype=float).mean()),
        "apr_volatility": float(frame["reward_apr"].to_numpy(dtype=float).std(ddof=1)),
        "staking_volatility": float(np.diff(ratio).std(ddof=1)),
    }


def _epoch_day(value: str) -> int:
    return (date.fromisoformat(value) - date(1970, 1, 1)).days


def observed_daily(con: Any, start: str, end: str, operating_cost_usd_month: float = 0.0) -> pd.DataFrame:
    """The engine's daily columns from the ledger for ``start`` to ``end`` inclusive.

    - supply_avax, stakes, validator_count, rewards_paid_avax: ``avax_monetary_daily`` (close supply, active stake,
      active validators, issued rewards). Sums stay in wei inside SQL.
    - net_inflation_annual: (issued - burned) / opening supply x 365.
    - reward_apr: the protocol's annualized rate for a 365-day stake at the day's opening supply
      (``model.protocol.annualized_reward_rate``), the quoted maximum-duration rate.
    - hhi: Herfindahl index of node weight (validator plus delegated stake) active at 00:00 UTC, from
      ``staking_periods``.
    - validator_profit_usd_month: validator-role rewards paid that day (``realized_reward_navax`` on validator rows,
      which includes delegation fees since Cortina) x the day's AVAXUSDT close x 365/12 / active validators, minus
      the operating cost.
    """
    first, last = _epoch_day(start), _epoch_day(end)
    ledger = con.execute(
        """
        SELECT m.date_utc,
               CAST(m.total_supply_open_wei AS HUGEINT) AS supply_open_wei,
               CAST(m.total_supply_close_wei AS HUGEINT) AS supply_close_wei,
               CAST(m.active_validator_stake_wei AS HUGEINT) AS validator_stake_wei,
               CAST(m.active_delegated_stake_wei AS HUGEINT) AS delegated_stake_wei,
               m.active_validators,
               CAST(m.issued_rewards_wei AS HUGEINT) AS issued_wei,
               CAST(m.issued_rewards_wei AS HUGEINT) - CAST(m.burned_wei AS HUGEINT) AS net_issued_wei,
               m.complete,
               p.close_usdt
        FROM avax_monetary_daily m
        LEFT JOIN avax_usdt_daily p ON p.observation_date = m.date_utc
        WHERE m.date_utc BETWEEN ?::DATE AND ?::DATE
        ORDER BY m.date_utc
        """,
        [start, end],
    ).fetchall()
    if len(ledger) != last - first + 1:
        raise ValueError(f"avax_monetary_daily has {len(ledger)} of {last - first + 1} days in {start} to {end}")
    incomplete = [row[0].isoformat() for row in ledger if not row[8]]
    if incomplete:
        raise ValueError(f"incomplete ledger days: {incomplete[:5]}")
    concentration = dict(con.execute(
        """
        WITH p AS (
            SELECT node_id, stake_navax,
                   greatest(CAST(ceil(epoch(start_time) / 86400) AS BIGINT), $first) AS start_day,
                   CAST(ceil(epoch(end_time) / 86400) AS BIGINT) AS end_day
            FROM staking_periods
            WHERE epoch(start_time) <= $last * 86400 AND epoch(end_time) > $first * 86400
        ),
        events AS (
            SELECT node_id, start_day AS d, stake_navax AS delta FROM p
            UNION ALL
            SELECT node_id, end_day AS d, -stake_navax AS delta FROM p WHERE end_day <= $last
        ),
        daily AS (SELECT node_id, d, sum(delta) AS delta FROM events GROUP BY ALL),
        grid AS (
            SELECT n.node_id, r.range AS d
            FROM (SELECT DISTINCT node_id FROM p) n CROSS JOIN range($first, $last + 1) r
        ),
        weights AS (
            SELECT g.d, sum(coalesce(e.delta, 0)) OVER (PARTITION BY g.node_id ORDER BY g.d) AS weight
            FROM grid g LEFT JOIN daily e USING (node_id, d)
        )
        SELECT d, sum(CAST(weight AS DOUBLE) ^ 2) / sum(CAST(weight AS DOUBLE)) ^ 2
        FROM weights WHERE weight > 0 GROUP BY d ORDER BY d
        """,
        {"first": first, "last": last},
    ).fetchall())
    income = dict(con.execute(
        """
        SELECT CAST(rewarded_at AS DATE), sum(CAST(realized_reward_navax AS HUGEINT))
        FROM staking_periods
        WHERE role = 'validator' AND rewarded AND rewarded_at >= ?::DATE AND rewarded_at < ?::DATE + INTERVAL 1 DAY
        GROUP BY 1
        """,
        [start, end],
    ).fetchall())
    rows = []
    for index, (day, supply_open, supply_close, validator_stake, delegated_stake, validators, issued, net_issued, _, price) in enumerate(ledger):
        if price is None:
            raise ValueError(f"no AVAXUSDT close on {day}")
        epoch_day = first + index
        at = datetime(day.year, day.month, day.day, tzinfo=UTC)
        apr = annualized_reward_rate(at, 365 * SECONDS_PER_DAY, 2_000 * NAVAX_PER_AVAX, int(supply_open) // (WEI_PER_AVAX // NAVAX_PER_AVAX))
        income_avax = int(income.get(day, 0)) / NAVAX_PER_AVAX
        supply = int(supply_close) / WEI_PER_AVAX
        staked = (int(validator_stake) + int(delegated_stake)) / WEI_PER_AVAX
        rows.append((
            index, day, supply, int(validator_stake) / WEI_PER_AVAX, int(delegated_stake) / WEI_PER_AVAX,
            staked / supply, int(validators), int(issued) / WEI_PER_AVAX, apr, concentration[epoch_day],
            int(net_issued) / int(supply_open) * 365,
            income_avax * float(price) * DAYS_PER_MONTH / int(validators) - operating_cost_usd_month,
        ))
    return pd.DataFrame(rows, columns=list(FRAME_COLUMNS))


def observed_kpis(con: Any, start: str, end: str, operating_cost_usd_month: float = 0.0) -> dict[str, float | bool]:
    return kpis(observed_daily(con, start, end, operating_cost_usd_month))


