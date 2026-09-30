"""A first validator lifecycle model: commitments end on schedule, renew or leave, and new ones enter.

From an origin day, the validator commitments open at that day's end are the initial state. Each day,
commitments that end either renew on the same node, drawing a new duration, or leave. New commitments
enter at a daily rate, each with a stake and a duration drawn from the year before the origin. Every
input comes from data before the origin, so the days after it are a holdout.

This is v0: renewal is one observed probability, entry one observed rate, and duration and stake are
empirical draws. Fitted blocks replace them through the same interface.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import duckdb
import numpy as np
import pandas as pd
import param

from avalanche_research.mechanisms import ChainReward, RewardMechanism
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
    initial_periods_done = param.Array(default=None, allow_None=True, precedence=-1, doc="Completed commitments on each open commitment's node before it")
    inputs_source = param.String(default="", doc="The staking-periods run the inputs came from")
    mechanism = param.ClassSelector(class_=RewardMechanism, default=ChainReward(), doc="The reward rule that prices each new commitment")
    renewal_response = param.Number(
        default=0.0, bounds=(-2.0, 2.0), metadata={"source": "assumed", "evidence": "Not identified from history, swept (path forward section 4.2)"},
        doc="Shift in the log-odds of renewal per percentage point of annual rate above the chain's, for a 30-day stake halfway through the run",
    )
    entry_response = param.Number(
        default=0.0, bounds=(-2.0, 2.0), metadata={"source": "assumed", "evidence": "Not identified from history, swept (path forward section 4.2)"},
        doc="Change in the log of the entry rate per percentage point of annual rate above the chain's, for a 30-day stake halfway through the run",
    )
    supply0_navax = param.Integer(default=450_000_000 * 10**9, bounds=(1, 720_000_000 * 10**9), doc="Current supply at the origin, nAVAX")

    def state_variables(self):
        return ["active_validators", "active_validator_stake_navax", "supply_navax", "issued_navax"]

    def initial_state(self):
        stakes = np.asarray(self.initial_stakes, dtype=np.int64)
        done = self.initial_periods_done
        return {
            "stakes": stakes,
            "days_left": np.asarray(self.initial_days_left, dtype=np.int64),
            "periods_done": np.zeros(len(stakes), dtype=np.int64) if done is None else np.asarray(done, dtype=np.int64),
            "active_validators": len(stakes),
            "active_validator_stake_navax": int(stakes.sum()),
            "supply_navax": int(self.supply0_navax),
            "issued_navax": 0,
        }

    def yield_gap_pp(self) -> float:
        """The mechanism's annual rate minus the chain's, in percentage points, for a 30-day stake started halfway through the run.

        v0 holds one gap for the whole run. Halfway represents a mechanism that changes over time, such as a ramp.
        """
        start = datetime.combine(self.origin + timedelta(days=max(1, self.timesteps // 2)), time(12), tzinfo=UTC)
        ours = self.mechanism.annual_rate(30, self.supply0_navax, start, completed_periods=4)
        chain = ChainReward().annual_rate(30, self.supply0_navax, start, completed_periods=4)
        return (ours - chain) * 100

    def blocks(self):
        gap = self.yield_gap_pp()
        base = min(max(self.renewal_probability, 1e-9), 1 - 1e-9)
        shifted = 1 / (1 + np.exp(-(np.log(base / (1 - base)) + self.renewal_response * gap)))
        renewal = Renewal(probability=float(shifted))
        entry = Entry(rate_per_day=min(100.0, self.entry_rate_per_day * float(np.exp(self.entry_response * gap))))
        durations = np.asarray(self.draw_durations, dtype=np.int64)
        entry_stakes = np.asarray(self.draw_stakes, dtype=np.int64)
        seed = self.seed
        mechanism = self.mechanism
        origin = self.origin

        def p_lifecycle(params, substep, history, state):
            rng = np.random.default_rng([seed, state["run"], state["timestep"]])
            day = origin + timedelta(days=state["timestep"] + 1)
            start = datetime.combine(day, time(12), tzinfo=UTC)
            days_left = state["days_left"] - 1
            stakes, done = state["stakes"], state["periods_done"]
            ending = days_left <= 0
            renews = renewal.sample({"ending_commitments": stakes[ending]}, rng)
            renewed_stakes = stakes[ending][renews]
            renewed_days = rng.choice(durations, size=len(renewed_stakes))
            renewed_done = done[ending][renews] + 1
            n_new = int(entry.sample({}, rng))
            new_stakes = rng.choice(entry_stakes, size=n_new)
            new_days = rng.choice(durations, size=n_new)
            started = zip(np.concatenate([renewed_stakes, new_stakes]), np.concatenate([renewed_days, new_days]),
                          np.concatenate([renewed_done, np.zeros(n_new, dtype=np.int64)]))
            issued = sum(
                mechanism.potential_reward_navax(int(stake), int(days) * 86_400, state["supply_navax"], start, int(periods))
                for stake, days, periods in started
            )
            return {
                "stakes": np.concatenate([stakes[~ending], renewed_stakes, new_stakes]),
                "days_left": np.concatenate([days_left[~ending], renewed_days, new_days]),
                "periods_done": np.concatenate([done[~ending], renewed_done, np.zeros(n_new, dtype=np.int64)]),
                "issued_navax": int(issued),
            }

        def s_copy(name):
            return lambda params, substep, history, state, signal: (name, signal[name])

        def s_count(params, substep, history, state, signal):
            return "active_validators", len(signal["stakes"])

        def s_stake(params, substep, history, state, signal):
            return "active_validator_stake_navax", int(signal["stakes"].sum())

        def s_supply(params, substep, history, state, signal):
            return "supply_navax", state["supply_navax"] + signal["issued_navax"]

        return [{
            "policies": {"lifecycle": p_lifecycle},
            "variables": {
                "stakes": s_copy("stakes"),
                "days_left": s_copy("days_left"),
                "periods_done": s_copy("periods_done"),
                "issued_navax": s_copy("issued_navax"),
                "supply_navax": s_supply,
                "active_validators": s_count,
                "active_validator_stake_navax": s_stake,
            },
        }]

    def invariants(self):
        return [
            ("stakes non-negative", lambda state: bool((state["stakes"] >= 0).all())),
            ("stake total matches the commitments", lambda state: state["active_validator_stake_navax"] == int(state["stakes"].sum())),
            ("supply within the cap", lambda state: state["supply_navax"] <= 720_000_000 * 10**9),
            ("stake within supply", lambda state: state["active_validator_stake_navax"] <= state["supply_navax"]),
        ]


def _day(value: date) -> int:
    return (pd.Timestamp(value) - pd.Timestamp(0)).days


def origin_inputs(periods_parquet: str, origin: date, ledger_parquet: str | None = None) -> dict:
    """Inputs for a run from ``origin``, read only from commitments started at or before the origin's end.

    With ``ledger_parquet``, the supply at the origin is the ledger's closing supply on that day.
    """
    day = _day(origin)
    cutoff_us = day * US_PER_DAY + INSTANT_US
    query = f"""
        WITH v AS (
            SELECT node_id, stake_navax,
                   epoch_us(start_time) AS s, epoch_us(end_time) AS e,
                   lag(epoch_us(end_time)) OVER (PARTITION BY node_id ORDER BY start_time) AS prev_e,
                   row_number() OVER (PARTITION BY node_id ORDER BY start_time) - 1 AS done
            FROM read_parquet(?) WHERE role = 'validator' AND stake_navax IS NOT NULL
        )
        SELECT node_id, stake_navax, s, e, prev_e, done FROM v WHERE s <= {cutoff_us} ORDER BY s, e, node_id, stake_navax
    """
    rows = duckdb.execute(query, [periods_parquet]).df()
    open_now = rows[rows["e"] > cutoff_us]
    enter_day = (rows["s"] - INSTANT_US + US_PER_DAY - 1) // US_PER_DAY
    leave_day = (rows["e"] - INSTANT_US + US_PER_DAY - 1) // US_PER_DAY
    open_leave = leave_day[open_now.index]
    year = rows[(enter_day > day - 365) & (enter_day <= day)]
    renewal = year["prev_e"].notna() & (year["s"] >= year["prev_e"]) & (year["s"] <= year["prev_e"] + RENEWAL_DAYS * US_PER_DAY)
    durations = ((year["e"] - year["s"]) / US_PER_DAY).round().clip(lower=1).astype(np.int64)
    inputs = {
        "initial_stakes": open_now["stake_navax"].to_numpy(dtype=np.int64),
        "initial_days_left": (open_leave - day).to_numpy(dtype=np.int64),
        "draw_durations": durations.to_numpy(),
        "draw_stakes": year.loc[~renewal, "stake_navax"].to_numpy(dtype=np.int64),
        "entry_rate_per_day": float((~renewal).sum()) / 365.0,
        "initial_periods_done": open_now["done"].to_numpy(dtype=np.int64),
    }
    if ledger_parquet is not None:
        wei = duckdb.execute(
            "SELECT total_supply_close_wei::VARCHAR FROM read_parquet(?) WHERE date_utc = ?", [ledger_parquet, origin]
        ).fetchone()[0]
        inputs["supply0_navax"] = int(wei) // 10**9
    return inputs


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


def actual_path(events: pd.DataFrame) -> pd.DataFrame:
    """Active validators and validator stake by day, accumulated from the replay's daily events."""
    return pd.DataFrame({
        "date_utc": events["date_utc"],
        "active_validators": events["d_validators"].cumsum(),
        "active_validator_stake_navax": events["d_validator_stake"].cumsum(),
    })
