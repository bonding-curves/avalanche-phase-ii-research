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
from avalanche_research.model.replay import LOCKBOX_FIRST_DAY

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
        """The exact Poisson log-likelihood of daily counts, minus infinity for a count a zero rate rules out."""
        from math import lgamma

        counts = np.asarray(decisions)
        if counts.ndim != 1 or (counts < 0).any() or not np.equal(np.mod(counts, 1), 0).all():
            raise ValueError("decisions must be a one-dimensional array of non-negative whole counts")
        lam = self.rate_per_day
        if lam == 0.0:
            return float("-inf") if counts.any() else 0.0
        return float(sum(k * np.log(lam) - lam - lgamma(int(k) + 1) for k in counts))


class ValidatorLifecycle(SimulationModel):
    """Validator commitments from an origin, stepped one UTC day at a time."""

    origin = param.CalendarDate(default=date(2024, 3, 6), doc="Last observed day. The run starts at its end")
    renewal_probability = param.Number(default=Renewal().probability, bounds=(0.0, 1.0), doc="Renewal block probability")
    entry_rate_per_day = param.Number(default=5.0, bounds=(0.0, 100.0), doc="Entry block daily rate")
    seed = param.Integer(default=0, bounds=(0, None), doc="Base seed. Run r on day t draws from default_rng([seed, r, t])")
    dt = param.Number(default=1.0, bounds=(0, None), inclusive_bounds=(False, True), doc="Days per timestep. The lifecycle clock is one UTC day per step, so only 1 is allowed")
    timesteps = param.Integer(default=90, bounds=(1, 3650), doc="Days after the origin")
    runs = param.Integer(default=20, bounds=(1, None), doc="Monte Carlo runs")
    initial_stakes = param.Array(default=None, allow_None=True, precedence=-1, doc="Stake of each open commitment, nAVAX")
    initial_days_left = param.Array(default=None, allow_None=True, precedence=-1, doc="Days until each open commitment ends")
    draw_durations = param.Array(default=None, allow_None=True, precedence=-1, doc="Durations, whole days, of commitments started in the year before the origin")
    draw_stakes = param.Array(default=None, allow_None=True, precedence=-1, doc="Stakes, nAVAX, of non-renewal commitments started in the year before the origin")
    initial_periods_done = param.Array(default=None, allow_None=True, precedence=-1, doc="Completed commitments on each open commitment's node before it")
    scheduled_start_day = param.Array(default=None, allow_None=True, precedence=-1, doc="Day after the origin on which each commitment accepted by the origin but not yet started begins")
    scheduled_stakes = param.Array(default=None, allow_None=True, precedence=-1, doc="Stake of each scheduled commitment, nAVAX")
    scheduled_days = param.Array(default=None, allow_None=True, precedence=-1, doc="Duration of each scheduled commitment, whole days")
    inputs_source = param.String(default="", doc="The staking-periods run the inputs came from")
    mechanism = param.ClassSelector(class_=RewardMechanism, default=ChainReward(), doc="The reward rule that prices each new commitment")
    renewal_response = param.Number(
        default=0.0, bounds=(-2.0, 2.0), metadata={"source": "assumed", "evidence": "Not identified from history, swept (path forward section 4.2)"},
        doc="Shift in the log-odds of renewal per percentage point of annual rate above the chain's, for a 30-day stake started that day by a node at the typical tenure of renewing validators",
    )
    entry_response = param.Number(
        default=0.0, bounds=(-2.0, 2.0), metadata={"source": "assumed", "evidence": "Not identified from history, swept (path forward section 4.2)"},
        doc="Change in the log of the entry rate per percentage point of annual rate above the chain's, for a 30-day stake started that day by a new validator, with no tenure",
    )
    renewal_tenure = param.Integer(default=4, bounds=(0, 100), doc="Completed commitments at which the renewal response prices the yield gap: the typical tenure of a renewing validator")
    supply0_navax = param.Integer(default=450_000_000 * 10**9, bounds=(1, 720_000_000 * 10**9), doc="The P-Chain reward counter at the origin, nAVAX: genesis plus rewards paid plus open potential rewards, with no burns. The reward formula reads it. It is not the realized supply")

    def state_variables(self):
        return ["active_validators", "active_validator_stake_navax", "supply_navax", "issued_navax"]

    def float_variables(self):
        return ["yield_gap_pp"]

    def __init__(self, **params):
        super().__init__(**params)
        if self.dt != 1:
            raise ValueError(f"the lifecycle clock is one UTC day per step, so dt must be 1, not {self.dt}")

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
            "yield_gap_pp": 0.0,
        }

    def yield_gap_pp(self, day: date | None = None, completed_periods: int | None = None) -> float:
        """The mechanism's annual rate minus the chain's, in percentage points, for a 30-day stake started on ``day``.

        Priced at ``completed_periods`` of tenure, the renewal tenure by default. Without a day, halfway through
        the run. The run uses each day's own gap, at the renewal tenure for renewal and at no tenure for entry,
        so a mechanism that changes over time, such as a ramp, moves behaviour as its rate moves, and a reward
        for tenure does not draw in new validators who would not receive it.
        """
        day = day or self.origin + timedelta(days=max(1, self.timesteps // 2))
        periods = self.renewal_tenure if completed_periods is None else completed_periods
        start = datetime.combine(day, time(12), tzinfo=UTC)
        ours = self.mechanism.annual_rate(30, self.supply0_navax, start, completed_periods=periods)
        chain = ChainReward().annual_rate(30, self.supply0_navax, start, completed_periods=periods)
        return (ours - chain) * 100

    def _blocks_for(self, renewal_gap: float, entry_gap: float) -> tuple[Renewal, Entry]:
        if self.renewal_response * renewal_gap == 0:
            renewal = Renewal().with_value(
                "probability", self.renewal_probability, "observed moment",
                f"renewal_probability {self.renewal_probability}, from {self.inputs_source or 'the given inputs'}",
            )
        else:
            base = min(max(self.renewal_probability, 1e-9), 1 - 1e-9)
            shifted = 1 / (1 + np.exp(-(np.log(base / (1 - base)) + self.renewal_response * renewal_gap)))
            renewal = Renewal().with_value(
                "probability", float(shifted), "assumed",
                f"renewal_probability {self.renewal_probability} shifted by renewal_response {self.renewal_response} times a yield gap of {renewal_gap:.4f} points",
            )
        scaled = self.entry_response * entry_gap != 0
        entry = Entry().with_value(
            "rate_per_day", min(100.0, self.entry_rate_per_day * float(np.exp(self.entry_response * entry_gap))),
            "assumed" if scaled else "observed moment",
            f"{self.inputs_source or 'given'} rate {self.entry_rate_per_day:.4f} a day" + (f", scaled by entry_response {self.entry_response} times a yield gap of {entry_gap:.4f} points" if scaled else ""),
        )
        return renewal, entry

    def blocks(self):
        days = [self.origin + timedelta(days=t + 1) for t in range(self.timesteps)]
        gaps = [(self.yield_gap_pp(day), self.yield_gap_pp(day, completed_periods=0)) for day in days]
        by_gap = {(round(r, 9), round(e, 9)): self._blocks_for(r, e) for r, e in set(gaps)}
        daily = [(r, *by_gap[(round(r, 9), round(e, 9))]) for r, e in gaps]
        durations = np.asarray(self.draw_durations, dtype=np.int64)
        entry_stakes = np.asarray(self.draw_stakes, dtype=np.int64)
        seed = self.seed
        mechanism = self.mechanism
        origin = self.origin
        sched_day = np.asarray(self.scheduled_start_day if self.scheduled_start_day is not None else [], dtype=np.int64)
        sched_stakes = np.asarray(self.scheduled_stakes if self.scheduled_stakes is not None else [], dtype=np.int64)
        sched_days = np.asarray(self.scheduled_days if self.scheduled_days is not None else [], dtype=np.int64)

        def p_lifecycle(params, substep, history, state):
            rng = np.random.default_rng([seed, state["run"], state["timestep"]])
            gap, renewal, entry = daily[state["timestep"]]
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
            due = sched_day == state["timestep"] + 1
            return {
                "stakes": np.concatenate([stakes[~ending], renewed_stakes, new_stakes, sched_stakes[due]]),
                "days_left": np.concatenate([days_left[~ending], renewed_days, new_days, sched_days[due]]),
                "periods_done": np.concatenate([done[~ending], renewed_done, np.zeros(n_new + int(due.sum()), dtype=np.int64)]),
                "issued_navax": int(issued),
                "yield_gap_pp": float(gap),
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
                "yield_gap_pp": s_copy("yield_gap_pp"),
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


def origin_inputs(periods_parquet: str, origin: date) -> dict:
    """Inputs for a run from ``origin``, read only from staking periods started at or before the origin's end.

    Before Durango a stake could be accepted up to 11.7 days before it started. Commitments accepted by the
    origin that start after it enter as scheduled commitments on their start day, already minted. Rows
    without a recorded supply are skipped when the supply is read. The renewal probability is the seven-day
    same-node renewal share of validator commitments that ended in
    the year before the origin with a full seven days of follow-up before it. The supply is the P-Chain
    supply recorded at the last stake start before the origin's end, the supply the reward formula uses.
    An origin inside the validation lockbox is refused.
    """
    if origin >= LOCKBOX_FIRST_DAY:
        raise ValueError(f"origin {origin} is inside the validation lockbox, which starts 2025-11-19 16:00 UTC")
    day = _day(origin)
    cutoff_us = day * US_PER_DAY + INSTANT_US
    query = f"""
        WITH v AS (
            SELECT node_id, stake_navax,
                   epoch_us(start_time) AS s, epoch_us(end_time) AS e,
                   lag(epoch_us(end_time)) OVER (PARTITION BY node_id ORDER BY start_time, transaction_hash) AS prev_e,
                   lead(epoch_us(start_time)) OVER (PARTITION BY node_id ORDER BY start_time, transaction_hash) AS next_s,
                   row_number() OVER (PARTITION BY node_id ORDER BY start_time, transaction_hash) - 1 AS done
            FROM read_parquet(?) WHERE role = 'validator' AND stake_navax IS NOT NULL
              AND start_time <= make_timestamp({cutoff_us})
        )
        SELECT node_id, stake_navax, s, e, prev_e, next_s, done FROM v ORDER BY s, e, node_id, stake_navax
    """
    rows = duckdb.execute(query, [periods_parquet]).df()
    if rows["node_id"].isna().any():
        raise ValueError("a validator period has no node_id, so its renewals and tenure cannot be counted")
    open_now = rows[rows["e"] > cutoff_us]
    pending = duckdb.execute(
        f"""SELECT stake_navax, epoch_us(start_time) AS s, epoch_us(end_time) AS e FROM read_parquet(?)
            WHERE role = 'validator' AND stake_navax IS NOT NULL
              AND accepted_at <= make_timestamp({cutoff_us}) AND start_time > make_timestamp({cutoff_us})
            ORDER BY start_time, transaction_hash""",
        [periods_parquet],
    ).df()
    pending_enter = (pending["s"] - INSTANT_US + US_PER_DAY - 1) // US_PER_DAY
    pending_leave = (pending["e"] - INSTANT_US + US_PER_DAY - 1) // US_PER_DAY
    enter_day = (rows["s"] - INSTANT_US + US_PER_DAY - 1) // US_PER_DAY
    leave_day = (rows["e"] - INSTANT_US + US_PER_DAY - 1) // US_PER_DAY
    open_leave = leave_day[open_now.index]
    year = rows[(enter_day > day - 365) & (enter_day <= day)]
    renewal = year["prev_e"].notna() & (year["s"] >= year["prev_e"]) & (year["s"] <= year["prev_e"] + RENEWAL_DAYS * US_PER_DAY)
    durations = ((year["e"] - year["s"]) / US_PER_DAY).round().clip(lower=1).astype(np.int64)
    follow = RENEWAL_DAYS * US_PER_DAY
    ended = rows[(rows["e"] > cutoff_us - 365 * US_PER_DAY - follow) & (rows["e"] <= cutoff_us - follow)]
    ended = ended[ended["next_s"].isna() | (ended["next_s"] >= ended["e"])]
    renewed = ended["next_s"].notna() & (ended["next_s"] <= ended["e"] + follow)
    supply = duckdb.execute(
        f"SELECT supply_before_navax FROM read_parquet(?) WHERE start_time <= make_timestamp({cutoff_us}) "
        "AND supply_before_navax IS NOT NULL ORDER BY start_time DESC, transaction_hash LIMIT 1",
        [periods_parquet],
    ).fetchone()[0]
    return {
        "initial_stakes": open_now["stake_navax"].to_numpy(dtype=np.int64),
        "initial_days_left": (open_leave - day).to_numpy(dtype=np.int64),
        "initial_periods_done": open_now["done"].to_numpy(dtype=np.int64),
        "draw_durations": durations.to_numpy(),
        "draw_stakes": year.loc[~renewal, "stake_navax"].to_numpy(dtype=np.int64),
        "entry_rate_per_day": float((~renewal).sum()) / 365.0,
        "renewal_probability": float(renewed.mean()),
        "renewal_tenure": int(np.median(ended.loc[renewed, "done"])) + 1 if renewed.any() else 1,
        "supply0_navax": int(supply),
        "scheduled_start_day": (pending_enter - day).to_numpy(dtype=np.int64),
        "scheduled_stakes": pending["stake_navax"].to_numpy(dtype=np.int64),
        "scheduled_days": (pending_leave - pending_enter).to_numpy(dtype=np.int64),
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


def actual_path(events: pd.DataFrame) -> pd.DataFrame:
    """Active validators and validator stake by day, accumulated from the replay's daily events."""
    return pd.DataFrame({
        "date_utc": events["date_utc"],
        "active_validators": events["d_validators"].cumsum(),
        "active_validator_stake_navax": events["d_validator_stake"].cumsum(),
    })
