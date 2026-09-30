"""Replay recorded staking periods through the cadCAD engine and compare with the monetary ledger.

The replay has no behaviour. Each day's validator and delegation starts, ends, and reward payments are
exogenous inputs taken from ``derived.staking-periods``. The model's state is the active stake and counts
and the rewards paid that day, in integer nAVAX. It must equal ``derived.avax-monetary-daily`` on every
complete day, to the wei. That proves the engine, the state layout, and the day convention before any
behaviour is added.

The ledger observes stake at the last second of each UTC day: a period counts on day D when it starts at
or before D 23:59:59 and ends after it. Rewards paid on D are those whose reward transaction was accepted
on D. By default the replay stops before the validation lockbox, which starts 2025-11-19 16:00 UTC.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import param

from avalanche_research.model.engine import SimulationModel

WEI_PER_NAVAX = 10**9
US_PER_DAY = 86_400_000_000
INSTANT_US = 86_399_000_000
LOCKBOX_FIRST_DAY = date(2025, 11, 19)
ROLES = ("validator", "delegator")
STOCKS = ("active_validator_stake_navax", "active_delegated_stake_navax", "active_validators", "active_delegations")

EVENTS_SQL = f"""
WITH p AS (
    SELECT role, stake_navax,
           (epoch_us(start_time) - {INSTANT_US} + {US_PER_DAY} - 1) // {US_PER_DAY} AS enter_day,
           (epoch_us(greatest(end_time, coalesce(last_cycle_end_time, end_time))) - {INSTANT_US} + {US_PER_DAY} - 1) // {US_PER_DAY} AS leave_day
    FROM read_parquet(?)
    WHERE start_time IS NOT NULL AND end_time IS NOT NULL AND stake_navax IS NOT NULL
),
e AS (
    SELECT role, enter_day AS day, stake_navax AS stake, 1 AS n FROM p WHERE leave_day > enter_day
    UNION ALL
    SELECT role, leave_day AS day, -stake_navax AS stake, -1 AS n FROM p WHERE leave_day > enter_day
)
SELECT day, role, sum(stake)::BIGINT AS stake_navax, sum(n)::BIGINT AS n FROM e GROUP BY 1, 2 ORDER BY 1, 2
"""

REWARDS_SQL = f"""
SELECT epoch_us(rewarded_at) // {US_PER_DAY} AS day, sum(realized_reward_navax)::BIGINT AS rewards_navax
FROM read_parquet(?) WHERE rewarded_at IS NOT NULL GROUP BY 1 ORDER BY 1
"""

LEDGER_SQL = """
SELECT date_utc, complete, active_validator_stake_wei::VARCHAR AS validator_wei,
       active_delegated_stake_wei::VARCHAR AS delegated_wei, issued_rewards_wei::VARCHAR AS issued_wei,
       active_validators, active_delegations
FROM read_parquet(?) ORDER BY date_utc
"""


def daily_events(periods_parquet: str, through: date = LOCKBOX_FIRST_DAY) -> pd.DataFrame:
    """One row per UTC day before ``through``: stake and count changes by role, and rewards paid.

    ``through`` may not pass the first day of the validation lockbox.
    """
    if through > LOCKBOX_FIRST_DAY:
        raise ValueError(f"through {through} reaches into the validation lockbox, which starts 2025-11-19 16:00 UTC")
    events = duckdb.execute(EVENTS_SQL, [periods_parquet]).fetchall()
    rewards = duckdb.execute(REWARDS_SQL, [periods_parquet]).fetchall()
    first = min(min(row[0] for row in events), min(row[0] for row in rewards))
    last = (pd.Timestamp(through) - pd.Timestamp(0)).days - 1
    size = last - first + 1
    columns = {name: np.zeros(size, dtype=np.int64) for name in ("d_validator_stake", "d_delegated_stake", "d_validators", "d_delegations", "rewards_paid")}
    for day, role, stake, n in events:
        if first <= day <= last:
            prefix = "validator" if role == "validator" else "delegated"
            columns[f"d_{prefix}_stake"][day - first] += stake
            columns["d_validators" if role == "validator" else "d_delegations"][day - first] += n
    for day, amount in rewards:
        if first <= day <= last:
            columns["rewards_paid"][day - first] += amount
    dates = pd.to_datetime(np.arange(first, last + 1) * US_PER_DAY, unit="us").date
    return pd.DataFrame({"date_utc": dates, **columns})


class Replay(SimulationModel):
    """Recorded stake starts, ends, and rewards, stepped one UTC day at a time."""

    events = param.DataFrame(default=None, allow_None=True, precedence=-1, doc="Daily events from daily_events")
    events_source = param.String(default="", doc="The staking-periods run the events came from")
    dt = param.Number(default=1.0, bounds=(0, None), inclusive_bounds=(False, True), doc="Days per timestep")

    def __init__(self, **params: Any):
        super().__init__(**params)
        if self.events is not None:
            self.timesteps = len(self.events)

    def initial_state(self):
        return {name: 0 for name in STOCKS} | {"rewards_paid_navax": 0}

    def blocks(self):
        table = self.events
        arrays = {name: table[name].to_numpy() for name in table.columns if name != "date_utc"}

        def p_day(params, substep, history, state):
            i = state["timestep"]
            return {name: int(values[i]) for name, values in arrays.items()}

        def add(variable, change):
            return lambda params, substep, history, state, signal: (variable, state[variable] + signal[change])

        return [{
            "policies": {"day": p_day},
            "variables": {
                "active_validator_stake_navax": add("active_validator_stake_navax", "d_validator_stake"),
                "active_delegated_stake_navax": add("active_delegated_stake_navax", "d_delegated_stake"),
                "active_validators": add("active_validators", "d_validators"),
                "active_delegations": add("active_delegations", "d_delegations"),
                "rewards_paid_navax": lambda params, substep, history, state, signal: ("rewards_paid_navax", signal["rewards_paid"]),
            },
        }]

    def invariants(self):
        return [(name, lambda state, name=name: state[name] >= 0) for name in STOCKS]


def compare(table: pd.DataFrame, events: pd.DataFrame, ledger_parquet: str) -> dict[str, Any]:
    """The replayed long table against the ledger on every complete day, exactly, in wei and counts."""
    wide = table.pivot_table(index="timestep", columns="variable", values="value", aggfunc="first")
    wide = wide[wide.index >= 1]
    wide.index = events["date_utc"].iloc[: len(wide)].to_numpy()
    ledger = duckdb.execute(LEDGER_SQL, [ledger_parquet]).df()
    ledger["date_utc"] = pd.to_datetime(ledger["date_utc"]).dt.date
    ledger = ledger[ledger["complete"] & ledger["date_utc"].isin(set(wide.index))]
    pairs = {
        "active_validator_stake": ("validator_wei", "active_validator_stake_navax", WEI_PER_NAVAX),
        "active_delegated_stake": ("delegated_wei", "active_delegated_stake_navax", WEI_PER_NAVAX),
        "issued_rewards": ("issued_wei", "rewards_paid_navax", WEI_PER_NAVAX),
        "active_validators": ("active_validators", "active_validators", 1),
        "active_delegations": ("active_delegations", "active_delegations", 1),
    }
    result: dict[str, Any] = {"complete_days": len(ledger), "first_date": str(ledger["date_utc"].min()), "last_date": str(ledger["date_utc"].max())}
    for name, (ledger_column, state_column, scale) in pairs.items():
        observed = ledger[ledger_column].map(int).to_numpy(dtype=object)
        replayed = np.array([int(v) * scale for v in wide.loc[ledger["date_utc"], state_column]], dtype=object)
        differ = [(str(d), int(o - r)) for d, o, r in zip(ledger["date_utc"], observed, replayed) if o != r]
        result[name] = {"days_differ": len(differ), "first_differences": differ[:5]}
    result["exact"] = all(result[name]["days_differ"] == 0 for name in pairs)
    return result
