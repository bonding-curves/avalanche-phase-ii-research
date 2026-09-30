"""A first validator lifecycle model: commitments end on schedule, renew or leave, and new ones enter.

From an origin day, the validator commitments open at that day's end are the initial state. Each day,
commitments that end either renew on the same node, drawing a new duration, or leave. New commitments
enter at a daily rate, each with a stake and a duration drawn from the year before the origin. Every
input comes from data before the origin, so the days after it are a holdout.

This is v0: renewal is one observed probability, entry one observed rate, and duration and stake are
empirical draws. Fitted blocks replace them through the same interface.
"""

from __future__ import annotations

from datetime import date, timedelta

import duckdb
import numpy as np
import pandas as pd
import param

from avalanche_research.model.blocks import BehaviourBlock, Renewal, behavioural
from avalanche_research.model.engine import SimulationModel

US_PER_DAY = 86_400_000_000
INSTANT_US = 86_399_000_000
RENEWAL_DAYS = 7


class Entry(BehaviourBlock):
    """How many validator commitments that are not renewals start each day."""

    reads = ()
    writes = ("entered_commitments",)
    decision = "enter"

    rate_per_day = behavioural(
        5.0, (0.0, 100.0), "observed moment",
        "Mean daily count of validator commitments that are not seven-day renewals",
        "Counted in the 365 days before the origin by origin_inputs",
    )

    def sample(self, inputs, rng):
        return rng.poisson(self.rate_per_day)

    def log_prob(self, inputs, decisions):
        counts = np.asarray(decisions)
        lam = max(self.rate_per_day, 1e-12)
        from math import lgamma

        return float(sum(k * np.log(lam) - lam - lgamma(k + 1) for k in counts))


class ValidatorLifecycle(SimulationModel):
    """Validator commitments from an origin, stepped one UTC day at a time."""

    origin = param.CalendarDate(default=date(2024, 3, 6), doc="Last observed day. The run starts at its end")
    renewal_probability = param.Number(default=Renewal().probability, bounds=(0.0, 1.0), doc="Renewal block probability")
    entry_rate_per_day = param.Number(default=5.0, bounds=(0.0, 100.0), doc="Entry block daily rate")
    seed = param.Integer(default=0, bounds=(0, None), doc="Base seed. Run r on day t draws from default_rng([seed, r, t])")
    dt = param.Number(default=1.0, bounds=(0, None), inclusive_bounds=(False, True), doc="Days per timestep")
    timesteps = param.Integer(default=90, bounds=(1, 3650), doc="Days after the origin")
    runs = param.Integer(default=20, bounds=(1, None), doc="Monte Carlo runs")
    initial_stakes = param.Array(default=None, allow_None=True, precedence=-1, doc="Stake of each open commitment, nAVAX")
    initial_days_left = param.Array(default=None, allow_None=True, precedence=-1, doc="Days until each open commitment ends")
    draw_durations = param.Array(default=None, allow_None=True, precedence=-1, doc="Durations, whole days, of commitments started in the year before the origin")
    draw_stakes = param.Array(default=None, allow_None=True, precedence=-1, doc="Stakes, nAVAX, of non-renewal commitments started in the year before the origin")
    inputs_source = param.String(default="", doc="The staking-periods run the inputs came from")

    def state_variables(self):
        return ["active_validators", "active_validator_stake_navax"]

    def initial_state(self):
        stakes = np.asarray(self.initial_stakes, dtype=np.int64)
        return {
            "stakes": stakes,
            "days_left": np.asarray(self.initial_days_left, dtype=np.int64),
            "active_validators": len(stakes),
            "active_validator_stake_navax": int(stakes.sum()),
        }

    def blocks(self):
        renewal = Renewal(probability=self.renewal_probability)
        entry = Entry(rate_per_day=self.entry_rate_per_day)
        durations = np.asarray(self.draw_durations, dtype=np.int64)
        entry_stakes = np.asarray(self.draw_stakes, dtype=np.int64)
        seed = self.seed

        def p_lifecycle(params, substep, history, state):
            rng = np.random.default_rng([seed, state["run"], state["timestep"]])
            days_left = state["days_left"] - 1
            stakes = state["stakes"]
            ending = days_left <= 0
            renews = renewal.sample({"ending_commitments": stakes[ending]}, rng)
            kept_stakes = np.concatenate([stakes[~ending], stakes[ending][renews]])
            kept_days = np.concatenate([days_left[~ending], rng.choice(durations, size=int(renews.sum()))])
            n_new = int(entry.sample({}, rng))
            new_stakes = rng.choice(entry_stakes, size=n_new)
            new_days = rng.choice(durations, size=n_new)
            return {"stakes": np.concatenate([kept_stakes, new_stakes]), "days_left": np.concatenate([kept_days, new_days])}

        def s_copy(name):
            return lambda params, substep, history, state, signal: (name, signal[name])

        def s_count(params, substep, history, state, signal):
            return "active_validators", len(signal["stakes"])

        def s_stake(params, substep, history, state, signal):
            return "active_validator_stake_navax", int(signal["stakes"].sum())

        return [{
            "policies": {"lifecycle": p_lifecycle},
            "variables": {
                "stakes": s_copy("stakes"),
                "days_left": s_copy("days_left"),
                "active_validators": s_count,
                "active_validator_stake_navax": s_stake,
            },
        }]

    def invariants(self):
        return [
            ("stakes non-negative", lambda state: bool((state["stakes"] >= 0).all())),
            ("stake total matches the commitments", lambda state: state["active_validator_stake_navax"] == int(state["stakes"].sum())),
        ]


def _day(value: date) -> int:
    return (pd.Timestamp(value) - pd.Timestamp(0)).days


def origin_inputs(periods_parquet: str, origin: date) -> dict:
    """Inputs for a run from ``origin``, read only from commitments started at or before the origin's end."""
    day = _day(origin)
    cutoff_us = day * US_PER_DAY + INSTANT_US
    query = f"""
        WITH v AS (
            SELECT node_id, stake_navax,
                   epoch_us(start_time) AS s, epoch_us(end_time) AS e,
                   lag(epoch_us(end_time)) OVER (PARTITION BY node_id ORDER BY start_time) AS prev_e
            FROM read_parquet(?) WHERE role = 'validator' AND stake_navax IS NOT NULL
        )
        SELECT stake_navax, s, e, prev_e FROM v WHERE s <= {cutoff_us}
    """
    rows = duckdb.execute(query, [periods_parquet]).df()
    open_now = rows[rows["e"] > cutoff_us]
    enter_day = (rows["s"] - INSTANT_US + US_PER_DAY - 1) // US_PER_DAY
    leave_day = (rows["e"] - INSTANT_US + US_PER_DAY - 1) // US_PER_DAY
    open_leave = leave_day[open_now.index]
    year = rows[(enter_day > day - 365) & (enter_day <= day)]
    renewal = year["prev_e"].notna() & (year["s"] >= year["prev_e"]) & (year["s"] <= year["prev_e"] + RENEWAL_DAYS * US_PER_DAY)
    durations = ((year["e"] - year["s"]) / US_PER_DAY).round().clip(lower=1).astype(np.int64)
    return {
        "initial_stakes": open_now["stake_navax"].to_numpy(dtype=np.int64),
        "initial_days_left": (open_leave - day).to_numpy(dtype=np.int64),
        "draw_durations": durations.to_numpy(),
        "draw_stakes": year.loc[~renewal, "stake_navax"].to_numpy(dtype=np.int64),
        "entry_rate_per_day": float((~renewal).sum()) / 365.0,
    }


def score(table: pd.DataFrame, actual: pd.DataFrame, origin: date, horizons=(30, 90)) -> pd.DataFrame:
    """Mean simulated count and stake at each horizon against the actual and against persistence.

    ``actual`` has ``date_utc``, ``active_validators``, and ``active_validator_stake_navax``, as the replay
    produces.
    """
    actual = actual.set_index("date_utc")
    rows = []
    for variable in ("active_validators", "active_validator_stake_navax"):
        start = float(actual.loc[origin, variable])
        for h in horizons:
            realized = float(actual.loc[origin + timedelta(days=h), variable])
            draws = table[(table["variable"] == variable) & (table["timestep"] == h)]["value"].astype(float)
            rows.append({
                "variable": variable, "horizon_days": h, "actual": realized, "model_mean": draws.mean(),
                "model_p10": draws.quantile(0.1), "model_p90": draws.quantile(0.9),
                "model_abs_error": abs(draws.mean() - realized), "persistence_abs_error": abs(start - realized),
            })
    return pd.DataFrame(rows)
