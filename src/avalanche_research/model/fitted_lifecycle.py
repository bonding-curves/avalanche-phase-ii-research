"""v0.8: the validator lifecycle with behaviour fitted to the chain before an origin.

Each day, commitments that end either renew on the same node, by :class:`RenewalLogit`, or leave the active set.
A node that left can return after more than seven days, by :class:`ReturnHazard`, until 365 days out. Nodes that
never validated before arrive by :class:`Arrivals`. A node that renews or returns draws its next duration and stake
from :class:`Continuation`, so it keeps its habit and can lower or raise its stake. A first-ever node draws both from
the first-ever commitments of the year before the origin.

``fitted_inputs`` fits every block on the events before an origin, so the days after it are a holdout. What v0.8
does not yet have, and v0.7 did not either: named operators as event blocks (RD5), operator types (RD7), and
delegations. The yield-gap responses shift renewal and arrivals as in v0.7. Returns do not respond.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import duckdb
import numpy as np
import pandas as pd
import param

from avalanche_research.mechanisms import ChainReward, RewardMechanism
from avalanche_research.model.engine import SimulationModel
from avalanche_research.model.fitted_blocks import (
    RENEWAL_DAYS,
    RETURN_DAYS,
    Arrivals,
    Continuation,
    RenewalLogit,
    ReturnHazard,
)
from avalanche_research.model.replay import LOCKBOX_FIRST_DAY

US_PER_DAY = 86_400_000_000
INSTANT_US = 86_399_000_000

COMMITMENT = ("stakes", "days_left", "done", "after_return", "days", "handed_on", "returns")
OUT = ("out_stakes", "out_days", "out_done", "out_last_days", "out_returns")


def _array(value, dtype=np.int64) -> np.ndarray:
    return np.asarray(value if value is not None else [], dtype=dtype)


def _column(frame: pd.DataFrame, name: str, dtype=np.int64) -> np.ndarray:
    """A column as an array, or zeros when the frame does not have it, as for a table built before ``returns`` existed."""
    return _array(frame[name], dtype) if name in frame else np.zeros(len(frame), dtype=dtype)


class FittedLifecycle(SimulationModel):
    """Validator commitments and the nodes out of the active set, stepped one UTC day at a time from an origin."""

    origin = param.CalendarDate(default=date(2024, 3, 6), doc="Last observed day. The run starts at its end")
    renewal = param.ClassSelector(class_=RenewalLogit, default=RenewalLogit(), doc="The renewal block")
    renewal_large = param.ClassSelector(class_=RenewalLogit, default=None, allow_None=True, doc="The renewal block for commitments above large_above_avax. None uses the one renewal block for every commitment")
    large_above_avax = param.Number(default=None, allow_None=True, bounds=(0, None), doc="The stake line above which renewal_large decides")
    arrivals = param.ClassSelector(class_=Arrivals, default=Arrivals(), doc="The first-ever arrival block")
    returns = param.ClassSelector(class_=ReturnHazard, default=ReturnHazard(), doc="The return block")
    seed = param.Integer(default=0, bounds=(0, None), doc="Base seed. Run r on day t draws from default_rng([seed, r, t])")
    dt = param.Number(default=1.0, bounds=(0, None), inclusive_bounds=(False, True), doc="Days per timestep. Only 1 is allowed")
    timesteps = param.Integer(default=90, bounds=(1, 3650), doc="Days after the origin")
    runs = param.Integer(default=20, bounds=(1, None), doc="Monte Carlo runs")
    initial = param.DataFrame(default=None, allow_None=True, precedence=-1, doc="Open commitments at the origin, one row each, with the columns of COMMITMENT")
    out_of_set = param.DataFrame(default=None, allow_None=True, precedence=-1, doc="Nodes out of the active set at the origin for at most 365 days, with the columns of OUT")
    scheduled = param.DataFrame(default=None, allow_None=True, precedence=-1, doc="Commitments accepted by the origin that start after it: start_day, stakes, days, done, after_return, returns")
    moves = param.DataFrame(default=None, allow_None=True, precedence=-1, doc="Renewals and returns of the year before the origin: previous_days, next_days, previous_stake_navax, next_stake_navax")
    first_commitments = param.DataFrame(default=None, allow_None=True, precedence=-1, doc="First-ever commitments of the year before the origin: days, stake_navax")
    inputs_source = param.String(default="", doc="The staking-periods run the inputs came from")
    mechanism = param.ClassSelector(class_=RewardMechanism, default=ChainReward(), doc="The reward rule that prices each new commitment")
    renewal_response = param.Number(
        default=0.0, bounds=(-2.0, 2.0), metadata={"source": "assumed", "evidence": "Not identified from history, swept (RD3)"},
        doc="Shift in the log-odds of renewal per percentage point of annual rate above the chain's, for a 30-day stake at the renewal tenure",
    )
    entry_response = param.Number(
        default=0.0, bounds=(-2.0, 2.0), metadata={"source": "assumed", "evidence": "Not identified from history, swept (RD3)"},
        doc="Change in the log of the arrival rate per percentage point of annual rate above the chain's, for a 30-day stake with no tenure",
    )
    renewal_tenure = param.Integer(default=4, bounds=(0, 100), doc="Completed commitments at which the renewal response prices the yield gap")
    supply0_navax = param.Integer(default=450_000_000 * 10**9, bounds=(1, 720_000_000 * 10**9), doc="The P-Chain reward counter at the origin, nAVAX. The reward formula reads it")

    def state_variables(self):
        return ["active_validators", "active_validator_stake_navax", "returning_nodes", "supply_navax", "issued_navax"]

    def float_variables(self):
        return ["yield_gap_pp"]

    def __init__(self, **params):
        super().__init__(**params)
        if self.dt != 1:
            raise ValueError(f"the lifecycle clock is one UTC day per step, so dt must be 1, not {self.dt}")

    def initial_state(self):
        initial = self.initial if self.initial is not None else pd.DataFrame(columns=COMMITMENT)
        out = self.out_of_set if self.out_of_set is not None else pd.DataFrame(columns=OUT)
        state = {name: _column(initial, name, bool if name in ("after_return", "handed_on") else np.int64) for name in COMMITMENT}
        state |= {name: _column(out, name) for name in OUT}
        return {
            **state,
            "active_validators": len(state["stakes"]),
            "active_validator_stake_navax": int(state["stakes"].sum()),
            "returning_nodes": len(state["out_stakes"]),
            "supply_navax": int(self.supply0_navax),
            "issued_navax": 0,
            "yield_gap_pp": 0.0,
        }

    def yield_gap_pp(self, day: date, completed_periods: int) -> float:
        """The mechanism's annual rate minus the chain's, in percentage points, for a 30-day stake started on ``day``."""
        start = datetime.combine(day, time(12), tzinfo=UTC)
        ours = self.mechanism.annual_rate(30, self.supply0_navax, start, completed_periods=completed_periods)
        chain = ChainReward().annual_rate(30, self.supply0_navax, start, completed_periods=completed_periods)
        return (ours - chain) * 100

    def blocks(self):
        days = [self.origin + timedelta(days=t + 1) for t in range(self.timesteps)]
        gaps = [(self.yield_gap_pp(day, self.renewal_tenure), self.yield_gap_pp(day, 0)) for day in days]
        renewal, arrivals, returns, mechanism = self.renewal, self.arrivals, self.returns, self.mechanism
        renewal_large = self.renewal_large
        large_navax = None if renewal_large is None or self.large_above_avax is None else int(self.large_above_avax * 10**9)
        renewal_response, entry_response, seed, origin = self.renewal_response, self.entry_response, self.seed, self.origin
        moves, first = self.moves, self.first_commitments
        continuation = Continuation(moves["previous_days"], moves["next_days"], moves["previous_stake_navax"], moves["next_stake_navax"])
        first_days, first_stakes = _array(first["days"]), _array(first["stake_navax"])
        sched = self.scheduled if self.scheduled is not None else pd.DataFrame(columns=["start_day", "stakes", "days", "done", "after_return", "returns"])
        sched_day = _array(sched["start_day"])

        def p_lifecycle(params, substep, history, state):
            t = state["timestep"]
            rng = np.random.default_rng([seed, state["run"], t])
            renewal_gap, entry_gap = gaps[t]
            start = datetime.combine(origin + timedelta(days=t + 1), time(12), tzinfo=UTC)
            days_left = state["days_left"] - 1
            ending = days_left <= 0
            decide = ending & ~state["handed_on"]
            ended = {name: state[name][decide] for name in ("stakes", "done", "after_return", "days", "returns")}
            decision_inputs = {
                "done": ended["done"], "after_return": ended["after_return"], "days": ended["days"],
                "stake_navax": ended["stakes"], "returns": ended["returns"], "shift": renewal_response * renewal_gap,
            }
            renews = renewal.sample(decision_inputs, rng)
            if large_navax is not None:
                large = ended["stakes"] > large_navax
                renews[large] = renewal_large.sample({k: (v[large] if isinstance(v, np.ndarray) else v) for k, v in decision_inputs.items()}, rng)

            out_days = state["out_days"] + 1
            comes_back = returns.sample({"stake_navax": state["out_stakes"], "days_since_end": out_days}, rng)
            n_new = int(arrivals.sample({"scale": float(np.exp(entry_response * entry_gap))}, rng))

            started = {
                "stakes": np.concatenate([
                    continuation.stakes(ended["stakes"][renews], rng),
                    continuation.stakes(state["out_stakes"][comes_back], rng),
                    rng.choice(first_stakes, size=n_new) if n_new else np.zeros(0, dtype=np.int64),
                ]),
                "days": np.concatenate([
                    continuation.durations(ended["days"][renews], rng),
                    continuation.durations(state["out_last_days"][comes_back], rng),
                    rng.choice(first_days, size=n_new) if n_new else np.zeros(0, dtype=np.int64),
                ]),
                "done": np.concatenate([ended["done"][renews] + 1, state["out_done"][comes_back], np.zeros(n_new, dtype=np.int64)]),
                "after_return": np.concatenate([np.zeros(int(renews.sum()), bool), np.ones(int(comes_back.sum()), bool), np.zeros(n_new, bool)]),
                "returns": np.concatenate([ended["returns"][renews], state["out_returns"][comes_back] + 1, np.zeros(n_new, dtype=np.int64)]),
            }
            issued = sum(
                mechanism.potential_reward_navax(int(stake), int(d) * 86_400, state["supply_navax"], start, int(periods))
                for stake, d, periods in zip(started["stakes"], started["days"], started["done"])
            )

            stay_out = ~comes_back & (out_days <= RETURN_DAYS)
            left = ~renews
            due = sched_day == t + 1
            keep = ~ending
            return {
                "stakes": np.concatenate([state["stakes"][keep], started["stakes"], _array(sched["stakes"])[due]]),
                "days_left": np.concatenate([days_left[keep], started["days"], _array(sched["days"])[due]]),
                "done": np.concatenate([state["done"][keep], started["done"], _array(sched["done"])[due]]),
                "after_return": np.concatenate([state["after_return"][keep], started["after_return"], _array(sched["after_return"], bool)[due]]),
                "days": np.concatenate([state["days"][keep], started["days"], _array(sched["days"])[due]]),
                "handed_on": np.concatenate([state["handed_on"][keep], np.zeros(len(started["stakes"]) + int(due.sum()), bool)]),
                "returns": np.concatenate([state["returns"][keep], started["returns"], _column(sched, "returns")[due]]),
                "out_stakes": np.concatenate([state["out_stakes"][stay_out], ended["stakes"][left]]),
                "out_days": np.concatenate([out_days[stay_out], np.zeros(int(left.sum()), dtype=np.int64)]),
                "out_done": np.concatenate([state["out_done"][stay_out], ended["done"][left] + 1]),
                "out_last_days": np.concatenate([state["out_last_days"][stay_out], ended["days"][left]]),
                "out_returns": np.concatenate([state["out_returns"][stay_out], ended["returns"][left]]),
                "issued_navax": int(issued),
                "yield_gap_pp": float(renewal_gap),
            }

        def s_copy(name):
            return lambda params, substep, history, state, signal: (name, signal[name])

        def s_count(params, substep, history, state, signal):
            return "active_validators", len(signal["stakes"])

        def s_stake(params, substep, history, state, signal):
            return "active_validator_stake_navax", int(signal["stakes"].sum())

        def s_out(params, substep, history, state, signal):
            return "returning_nodes", len(signal["out_stakes"])

        def s_supply(params, substep, history, state, signal):
            return "supply_navax", state["supply_navax"] + signal["issued_navax"]

        copied = (*COMMITMENT, *OUT, "issued_navax", "yield_gap_pp")
        return [{
            "policies": {"lifecycle": p_lifecycle},
            "variables": {
                **{name: s_copy(name) for name in copied},
                "supply_navax": s_supply,
                "active_validators": s_count,
                "active_validator_stake_navax": s_stake,
                "returning_nodes": s_out,
            },
        }]

    def invariants(self):
        return [
            ("stakes within the validator bounds", lambda s: bool(((s["stakes"] >= 2_000 * 10**9) & (s["stakes"] <= 3_000_000 * 10**9)).all())),
            ("stake total matches the commitments", lambda s: s["active_validator_stake_navax"] == int(s["stakes"].sum())),
            ("nodes out of the set at most 365 days", lambda s: bool((s["out_days"] <= RETURN_DAYS).all())),
            ("supply within the cap", lambda s: s["supply_navax"] <= 720_000_000 * 10**9),
            ("stake within supply", lambda s: s["active_validator_stake_navax"] <= s["supply_navax"]),
        ]


def _day(value: date) -> int:
    return (pd.Timestamp(value) - pd.Timestamp(0)).days


def _whole_days(us: pd.Series) -> pd.Series:
    """A timestamp in microseconds as the UTC day whose end is the first at or after it, as the replay counts days."""
    return (us - INSTANT_US + US_PER_DAY - 1) // US_PER_DAY


def validator_periods(periods_parquet: str, through_us: int) -> pd.DataFrame:
    """Validator commitments that started by ``through_us``, each with its node's neighbours and the terms the blocks read.

    ``done`` counts the node's commitments before this one. ``after_return`` marks a commitment that began more than
    seven days after the node's last one ended, and ``returns`` counts the node's commitments to this one that did.
    ``renewed`` marks one followed on the same node within seven days of its end, by a commitment that started by
    ``through_us``.
    """
    rows = duckdb.execute(
        f"""SELECT node_id, stake_navax, s, e, prev_e, next_s, next_e, next_stake, done FROM (
              SELECT node_id, stake_navax, epoch_us(start_time) AS s, epoch_us(end_time) AS e, start_time, transaction_hash,
                     lag(epoch_us(end_time)) OVER w AS prev_e,
                     lead(epoch_us(start_time)) OVER w AS next_s,
                     lead(epoch_us(end_time)) OVER w AS next_e,
                     lead(stake_navax) OVER w AS next_stake,
                     row_number() OVER w - 1 AS done
              FROM read_parquet(?) WHERE role = 'validator' AND stake_navax IS NOT NULL AND start_time <= make_timestamp({through_us})
              WINDOW w AS (PARTITION BY node_id ORDER BY start_time, transaction_hash))
            ORDER BY start_time, transaction_hash""",
        [periods_parquet],
    ).df()
    if rows["node_id"].isna().any():
        raise ValueError("a validator period has no node_id, so its renewals and tenure cannot be counted")
    for column in ("prev_e", "next_s", "next_e", "next_stake"):
        rows[column] = rows[column].astype("float64")
    follow = RENEWAL_DAYS * US_PER_DAY
    rows["days"] = ((rows["e"] - rows["s"]) / US_PER_DAY).round().clip(lower=1).astype(np.int64)
    rows["after_return"] = rows["prev_e"].notna() & (rows["s"] > rows["prev_e"] + follow)
    rows["renewed"] = rows["next_s"].notna() & (rows["next_s"] >= rows["e"]) & (rows["next_s"] <= rows["e"] + follow)
    rows["leave_day"] = _whole_days(rows["e"])
    rows["returns"] = rows.groupby("node_id")["after_return"].cumsum().astype(np.int64)
    return rows


def renewal_endings(rows: pd.DataFrame, after_us: int, through_us: int) -> pd.DataFrame:
    """The renewal decisions of commitments that ended after ``after_us`` and by ``through_us``, as ``AM2`` counts them.

    A commitment overlapped by the node's next one made no decision and is left out. Its label needs seven days of
    follow-up, so ``rows`` must reach seven days past ``through_us``.
    """
    overlapped = rows["next_s"].notna() & (rows["next_s"] < rows["e"])
    return rows[(rows["e"] > after_us) & (rows["e"] <= through_us) & ~overlapped]


def renewal_inputs(endings: pd.DataFrame) -> dict[str, np.ndarray]:
    """The inputs :class:`RenewalLogit` reads, from rows of :func:`renewal_endings`."""
    return {
        "done": endings["done"].to_numpy(), "after_return": endings["after_return"].to_numpy(),
        "days": endings["days"].to_numpy(), "stake_navax": endings["stake_navax"].to_numpy(),
        "returns": endings["returns"].to_numpy(),
    }


def fitted_inputs(periods_parquet: str, origin: date, run: str = "", large_above_avax: float | None = None) -> dict:
    """Every input of a v0.8 run from ``origin``, fitted on staking periods that started by the origin's end.

    * Renewal: endings in the 365 days before the origin with seven days of follow-up before it, as ``AM2`` counts them.
      With ``large_above_avax``, one renewal block is fitted on the endings at or below that stake and another above it.
    * Returns: endings in the 730 days before the origin that did not renew, each followed until it returned or the
      origin came, so a node out at the origin is censored there.
    * Arrivals: daily counts of first-ever commitments in the 365 days before the origin.
    * Continuations: renewals and returns that started in the 365 days before the origin.

    Commitments accepted by the origin that start after it enter on their start day, already minted. An open
    commitment whose node has one of them is handed on to it, with no renewal draw. A node that ended in the week
    before the origin without a new commitment is out of the set, so its chance to renew in what is left of its
    week is not drawn. An origin inside the validation lockbox is refused.
    """
    if origin >= LOCKBOX_FIRST_DAY:
        raise ValueError(f"origin {origin} is inside the validation lockbox, which starts 2025-11-19 16:00 UTC")
    day = _day(origin)
    cutoff = day * US_PER_DAY + INSTANT_US
    rows = validator_periods(periods_parquet, cutoff)
    pending = duckdb.execute(
        f"""SELECT p.node_id, p.stake_navax, epoch_us(p.start_time) AS s, epoch_us(p.end_time) AS e
            FROM read_parquet(?) p WHERE role = 'validator' AND stake_navax IS NOT NULL
              AND accepted_at <= make_timestamp({cutoff}) AND start_time > make_timestamp({cutoff})
            ORDER BY start_time, transaction_hash""",
        [periods_parquet],
    ).df()
    follow = RENEWAL_DAYS * US_PER_DAY
    overlapped = rows["next_s"].notna() & (rows["next_s"] < rows["e"])

    ended = renewal_endings(rows, cutoff - 365 * US_PER_DAY - follow, cutoff - follow)
    window = f"{run or 'staking periods'}, endings from {pd.Timestamp(int(cutoff - 365 * US_PER_DAY - follow), unit='us').date()} to {pd.Timestamp(int(cutoff - follow), unit='us').date()}"
    renewal = RenewalLogit.fit(renewal_inputs(ended), ended["renewed"].to_numpy(), f"{window}: {len(ended)} endings, {int(ended['renewed'].sum())} renewed")
    renewal_large = None
    if large_above_avax is not None:
        big = ended["stake_navax"] > large_above_avax * 10**9
        small, large = ended[~big], ended[big]
        renewal = RenewalLogit.fit(renewal_inputs(small), small["renewed"].to_numpy(), f"{window}, at or below {large_above_avax:,.0f} AVAX: {len(small)} endings")
        renewal_large = RenewalLogit.fit(renewal_inputs(large), large["renewed"].to_numpy(), f"{window}, above {large_above_avax:,.0f} AVAX: {len(large)} endings")

    lapsed = rows[(rows["e"] > cutoff - 730 * US_PER_DAY) & (rows["e"] <= cutoff) & ~overlapped & ~rows["renewed"]]
    came_back = lapsed["next_s"].notna()
    days_out = np.where(came_back, np.ceil((lapsed["next_s"] - lapsed["e"]) / US_PER_DAY), np.floor((cutoff - lapsed["e"]) / US_PER_DAY))
    returns = ReturnHazard.fit(
        lapsed["stake_navax"].to_numpy(), days_out, came_back.to_numpy(),
        f"{run or 'staking periods'}, {len(lapsed)} endings without renewal in the 730 days before {origin}",
    )

    enter_day = _whole_days(rows["s"])
    year = rows[(enter_day > day - 365) & (enter_day <= day)]
    first = year[year["done"] == 0]
    counts = np.bincount((_whole_days(first["s"]) - (day - 364)).to_numpy(dtype=np.int64), minlength=365)
    arrivals = Arrivals.fit(counts, f"{run or 'staking periods'}, {len(first)} first-ever commitments in the 365 days to {origin}")

    moved = rows[rows["next_s"].notna() & ~overlapped & (rows["next_s"] > cutoff - 365 * US_PER_DAY) & (rows["next_s"] <= cutoff)]
    moves = pd.DataFrame({
        "previous_days": moved["days"].to_numpy(),
        "next_days": ((moved["next_e"] - moved["next_s"]) / US_PER_DAY).round().clip(lower=1).astype(np.int64).to_numpy(),
        "previous_stake_navax": moved["stake_navax"].to_numpy(dtype=np.int64),
        "next_stake_navax": moved["next_stake"].to_numpy(dtype=np.int64),
    })

    open_now = rows[rows["e"] > cutoff]
    pending_nodes = set(pending["node_id"])
    initial = pd.DataFrame({
        "stakes": open_now["stake_navax"].to_numpy(dtype=np.int64),
        "days_left": (open_now["leave_day"] - day).to_numpy(dtype=np.int64),
        "done": open_now["done"].to_numpy(dtype=np.int64),
        "after_return": open_now["after_return"].to_numpy(dtype=bool),
        "days": open_now["days"].to_numpy(dtype=np.int64),
        "handed_on": open_now["node_id"].isin(pending_nodes).to_numpy(),
        "returns": open_now["returns"].to_numpy(dtype=np.int64),
    })

    latest = rows.groupby("node_id").tail(1)
    out = latest[(latest["e"] <= cutoff) & (latest["e"] > cutoff - RETURN_DAYS * US_PER_DAY) & ~latest["node_id"].isin(pending_nodes)]
    out_of_set = pd.DataFrame({
        "out_stakes": out["stake_navax"].to_numpy(dtype=np.int64),
        "out_days": (day - out["leave_day"]).to_numpy(dtype=np.int64),
        "out_done": (out["done"] + 1).to_numpy(dtype=np.int64),
        "out_last_days": out["days"].to_numpy(dtype=np.int64),
        "out_returns": out["returns"].to_numpy(dtype=np.int64),
    })

    last = rows.groupby("node_id").agg(last_done=("done", "max"), last_e=("e", "max"), last_returns=("returns", "max"))
    pending = pending.join(last, on="node_id")
    start_day = _whole_days(pending["s"])
    scheduled = pd.DataFrame({
        "start_day": (start_day - day).to_numpy(dtype=np.int64),
        "stakes": pending["stake_navax"].to_numpy(dtype=np.int64),
        "days": (_whole_days(pending["e"]) - start_day).to_numpy(dtype=np.int64),
        "done": (pending["last_done"].fillna(-1) + 1).to_numpy(dtype=np.int64),
        "after_return": (pending["last_e"].notna() & (pending["s"] > pending["last_e"] + follow)).to_numpy(dtype=bool),
    })
    scheduled["returns"] = (pending["last_returns"].fillna(0).to_numpy(dtype=np.int64) + scheduled["after_return"].to_numpy()).astype(np.int64)

    supply = duckdb.execute(
        f"SELECT supply_before_navax FROM read_parquet(?) WHERE start_time <= make_timestamp({cutoff}) "
        "AND supply_before_navax IS NOT NULL ORDER BY start_time DESC, transaction_hash LIMIT 1",
        [periods_parquet],
    ).fetchone()[0]
    renewing = ended[ended["renewed"]]
    return {
        "origin": origin,
        "renewal": renewal,
        **({"renewal_large": renewal_large, "large_above_avax": large_above_avax} if renewal_large is not None else {}),
        "arrivals": arrivals,
        "returns": returns,
        "initial": initial,
        "out_of_set": out_of_set,
        "scheduled": scheduled,
        "moves": moves,
        "first_commitments": pd.DataFrame({"days": first["days"].to_numpy(), "stake_navax": first["stake_navax"].to_numpy(dtype=np.int64)}),
        "renewal_tenure": int(np.median(renewing["done"])) + 1 if len(renewing) else 1,
        "supply0_navax": int(supply),
        "inputs_source": run,
    }
