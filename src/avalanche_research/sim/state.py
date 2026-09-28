"""Model state: validator stake cohorts by days to expiry and duration, delegated stake by days to expiry, supply.

Index ``r`` of every horizon array is the number of days until the cohort expires: a cohort at ``r = 0`` leaves
during day 0, so it is not active at day 0's close. Amounts are AVAX as floats in the simulation. The observed
state of a date is the state at 00:00 UTC of that date, which is the ledger's 23:59:59 observation of the day
before, so a run started from it reproduces the ledger's stake at the close of its first day when nothing moves.

Two supplies are kept. ``supply_avax`` is realized supply: genesis plus rewards paid minus burns, as the ledger
defines it. ``counter_avax`` is the P-Chain supply counter that the reward kernel reads (AvalancheGo
``vms/platformvm/state`` CurrentSupply): it adds a period's potential reward when the period starts, drops it
again if the period is not rewarded, and never subtracts burns.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from ..model.types import NAVAX_PER_AVAX

MENU_DAYS = (14, 30, 90, 180, 365)
HORIZON_DAYS = 366
GENESIS_SUPPLY_AVAX = 360_000_000.0
WEI_PER_AVAX = 10**18


@dataclass
class State:
    """One trajectory's state at the opening of ``date``.

    validator_stake, validator_count: (horizon, len(menu_days)) self stake and validator count of the cohort that
    expires in ``r`` days and chose menu duration ``k``.
    validator_reward_due, delegated_reward_due: (horizon,) potential rewards of the cohorts expiring in ``r`` days,
    reserved in the counter and paid at expiry.
    validator_accrual, delegated_accrual: (horizon,) reward per day earned by the cohorts expiring in ``r`` days.
    delegated_stake: (horizon,) delegated stake expiring in ``r`` days.
    """

    date: str
    menu_days: np.ndarray
    supply_avax: float
    counter_avax: float
    validator_stake: np.ndarray
    validator_count: np.ndarray
    validator_reward_due: np.ndarray
    validator_accrual: np.ndarray
    delegated_stake: np.ndarray
    delegated_reward_due: np.ndarray
    delegated_accrual: np.ndarray

    @property
    def horizon(self) -> int:
        return int(self.validator_stake.shape[0])

    def copy(self) -> State:
        return replace(self, **{key: np.array(value, copy=True) for key, value in self.__dict__.items() if isinstance(value, np.ndarray)})

    def totals(self) -> dict[str, float]:
        return {
            "supply_avax": self.supply_avax,
            "counter_avax": self.counter_avax,
            "validator_stake_avax": float(self.validator_stake.sum()),
            "validator_count": float(self.validator_count.sum()),
            "delegated_stake_avax": float(self.delegated_stake.sum()),
            "reserved_rewards_avax": float(self.validator_reward_due.sum() + self.delegated_reward_due.sum()),
        }


def menu_index(duration_days: np.ndarray, menu_days: np.ndarray) -> np.ndarray:
    """Nearest menu entry of each duration, with boundaries at the midpoints between entries."""
    menu = np.asarray(menu_days, dtype=float)
    edges = (menu[1:] + menu[:-1]) / 2
    return np.searchsorted(edges, np.asarray(duration_days, dtype=float), side="left")


def empty(date: str, menu_days: tuple[int, ...] = MENU_DAYS, horizon: int = HORIZON_DAYS) -> State:
    k = len(menu_days)
    return State(
        date=date, menu_days=np.asarray(menu_days, dtype=np.int64), supply_avax=0.0, counter_avax=0.0,
        validator_stake=np.zeros((horizon, k)), validator_count=np.zeros((horizon, k)),
        validator_reward_due=np.zeros(horizon), validator_accrual=np.zeros(horizon),
        delegated_stake=np.zeros(horizon), delegated_reward_due=np.zeros(horizon), delegated_accrual=np.zeros(horizon),
    )


OBSERVED_SQL = """
SELECT role,
       (epoch(end_time) - epoch(TIMESTAMP '{date}'))::BIGINT // 86400 AS r,
       epoch(end_time - start_time) / 86400 AS duration_days,
       stake_navax, potential_reward_navax
FROM staking_periods
WHERE start_time < TIMESTAMP '{date}' AND end_time >= TIMESTAMP '{date}'
"""

AGGREGATE_SQL = """
SELECT role, r, {bucket} AS k, count(*) AS n, sum(stake_navax)::BIGINT AS stake_navax,
       sum(potential_reward_navax)::BIGINT AS reward_navax, sum(potential_reward_navax / duration_days) AS accrual_navax
FROM ({observed}) GROUP BY 1, 2, 3
"""

COUNTER_SQL = """
SELECT (SELECT coalesce(sum(realized_reward_navax), 0) FROM staking_periods WHERE rewarded_at < TIMESTAMP '{date}')::BIGINT,
       (SELECT coalesce(sum(potential_reward_navax), 0) FROM staking_periods
        WHERE accepted_at < TIMESTAMP '{date}' AND (rewarded_at IS NULL OR rewarded_at >= TIMESTAMP '{date}'))::BIGINT
"""


def observed_state(con: Any, date: str, menu_days: tuple[int, ...] = MENU_DAYS, horizon: int = HORIZON_DAYS) -> State:
    """The observed state at 00:00 UTC of ``date`` from ``staking_periods`` and ``avax_monetary_daily``.

    Active periods are those with start_time before the instant and end_time at or after it, which is the ledger's
    active set at 23:59:59 of the day before. Validator periods go to their nearest menu duration. Reward due is
    each period's potential reward, and the counter is genesis plus realized rewards plus potential rewards of
    periods accepted but not yet rewarded, as ``monetary.counter_check`` defines it. Realized supply is the ledger's
    total_supply_open_wei of the date.
    """
    menu = np.asarray(menu_days, dtype=float)
    edges = (menu[1:] + menu[:-1]) / 2
    bucket = "CASE " + " ".join(f"WHEN duration_days < {edge} THEN {i}" for i, edge in enumerate(edges)) + f" ELSE {len(menu) - 1} END"
    rows = con.execute(AGGREGATE_SQL.format(bucket=bucket, observed=OBSERVED_SQL.format(date=date))).fetchall()
    state = empty(date, menu_days, horizon)
    for role, r, k, n, stake, reward, accrual in rows:
        if r >= horizon:
            raise ValueError(f"a period active on {date} expires beyond the {horizon}-day horizon")
        if role == "validator":
            state.validator_stake[r, k] += stake / NAVAX_PER_AVAX
            state.validator_count[r, k] += n
            state.validator_reward_due[r] += reward / NAVAX_PER_AVAX
            state.validator_accrual[r] += accrual / NAVAX_PER_AVAX
        else:
            state.delegated_stake[r] += stake / NAVAX_PER_AVAX
            state.delegated_reward_due[r] += reward / NAVAX_PER_AVAX
            state.delegated_accrual[r] += accrual / NAVAX_PER_AVAX
    realized, reserved = con.execute(COUNTER_SQL.format(date=date)).fetchone()
    state.counter_avax = GENESIS_SUPPLY_AVAX + (realized + reserved) / NAVAX_PER_AVAX
    supply = con.execute("SELECT total_supply_open_wei::VARCHAR FROM avax_monetary_daily WHERE date_utc = ?::DATE", [date]).fetchone()
    if supply is None or supply[0] is None:
        raise ValueError(f"the ledger has no realized supply for {date}")
    state.supply_avax = int(supply[0]) / WEI_PER_AVAX
    return state


# Observed state at 2025-01-01 00:00 UTC (ledger close of 2024-12-31), from observed_state(con, "2025-01-01") on
# staking-periods-2026-09-22 and monetary-daily-2026-09-26, rounded. The synthetic start keeps these totals and
# spreads each duration bucket evenly over its remaining days.
SYNTHETIC_2025 = {
    "date": "2025-01-01",
    "supply_avax": 440_770_508.92,
    "counter_avax": 452_707_543.20,
    "menu_days": (14, 30, 90, 180, 365),
    "validator_stake_avax": (8_829_178.74, 30_774_601.54, 27_689_185.76, 35_731_982.54, 67_271_283.74),
    "validator_count": (463, 227, 382, 100, 292),
    "delegated_stake_avax": 33_179_793.35,
}


def _spread(total: float, count: int, days: int) -> tuple[np.ndarray, np.ndarray]:
    """Integer counts spread as evenly as possible over ``days`` slots, with stake proportional to counts."""
    edges = np.floor(np.arange(days + 1) * count / days)
    counts = np.diff(edges)
    return counts, counts * (total / count if count else 0.0)


def synthetic_state(menu_days: np.ndarray, delegation_days: int, kernel: Any, horizon: int = HORIZON_DAYS) -> State:
    """A documented synthetic start near the observed 2025-01-01 state.

    Each observed duration bucket goes to the nearest menu entry and is spread evenly over remaining days 0 to d-1.
    Delegated stake is spread evenly over 0 to ``delegation_days``-1. Reward due of each slot is
    ``kernel(stake, duration)`` at the observed counter, which assumes every open period started at today's counter.
    """
    menu_days = np.asarray(menu_days, dtype=np.int64)
    horizon = max(horizon, int(menu_days.max()) + 1, delegation_days + 1)
    state = empty(SYNTHETIC_2025["date"], tuple(int(d) for d in menu_days), horizon)
    state.supply_avax = SYNTHETIC_2025["supply_avax"]
    state.counter_avax = SYNTHETIC_2025["counter_avax"]
    targets = menu_index(np.asarray(SYNTHETIC_2025["menu_days"]), menu_days)
    for k, stake, count in zip(targets, SYNTHETIC_2025["validator_stake_avax"], SYNTHETIC_2025["validator_count"]):
        days = int(menu_days[k])
        counts, stakes = _spread(stake, count, days)
        rewards = kernel(stakes, np.full(days, float(days)))
        state.validator_stake[:days, k] += stakes
        state.validator_count[:days, k] += counts
        state.validator_reward_due[:days] += rewards
        state.validator_accrual[:days] += rewards / days
    per_day = SYNTHETIC_2025["delegated_stake_avax"] / delegation_days
    reward = float(kernel(np.array([per_day]), np.array([float(delegation_days)]))[0])
    state.delegated_stake[:delegation_days] = per_day
    state.delegated_reward_due[:delegation_days] = reward
    state.delegated_accrual[:delegation_days] = reward / delegation_days
    return state
