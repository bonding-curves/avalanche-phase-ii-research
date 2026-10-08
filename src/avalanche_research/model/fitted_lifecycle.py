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

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

import duckdb
import numpy as np
import pandas as pd
import param
from scipy import special

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
from avalanche_research.model.parts.arrivals import arrivals_stage
from avalanche_research.model.parts.continuation import continuation_stage
from avalanche_research.model.parts.renewal import renewal_stage
from avalanche_research.model.parts.returns import returns_stage
from avalanche_research.model.parts.stages import (
    Day,
    RunBlocks,
    RunSettings,
    assembly_stage,
    rewards_stage,
    run_stages,
)
from avalanche_research.model.replay import LOCKBOX_FIRST_DAY
from avalanche_research.model.response import FittedMenu, response_gap_pp
from avalanche_research.model.streams import (
    KIND_OPEN,
    KIND_OUT,
    KIND_SCHEDULED,
    Streams,
    node_keys,
)

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
    seed = param.Integer(default=0, bounds=(0, None), doc="Base seed. Draws are keyed by seed, run, purpose and node (model.streams)")
    random_streams = param.String(default="keyed-v1", constant=True, doc="The random-number scheme. Keyed streams from 2026-10, so no run made before shares a specification hash with one made after")
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
    fitted_menu = param.ClassSelector(
        class_=RewardMechanism, default=FittedMenu(),
        doc="The reward rule in force while the blocks were fitted, the point the responses count from. The default "
            "holds the chain's rule at the lockbox start, 2025-11-19 16:00 UTC. fitted_inputs sets the menu of the "
            "origin's fitting window",
    )
    outside_yield_pp = param.Number(
        default=None, allow_None=True,
        doc="An outside yield over the run, such as a Treasury bill rate, in percent a year. Given with "
            "fitted_outside_yield_pp or not at all. None leaves it out of the gap",
    )
    fitted_outside_yield_pp = param.Number(
        default=None, allow_None=True,
        doc="The outside yield's level over the fitting window, in percent a year, which the fitted blocks already carry",
    )
    renewal_response = param.Number(
        default=0.0, bounds=(-2.0, 2.0), metadata={"source": "assumed", "evidence": "Not identified from history, swept (RD3)"},
        doc="Shift in the log-odds of renewal per percentage point of annual rate above the fitted menu's rate, less "
            "the outside yield's change from its fitting-window level, for a 30-day stake at the renewal tenure",
    )
    entry_response = param.Number(
        default=0.0, bounds=(-2.0, 2.0), metadata={"source": "assumed", "evidence": "Not identified from history, swept (RD3)"},
        doc="Change in the log of the arrival rate per percentage point of annual rate above the fitted menu's rate, "
            "less the outside yield's change from its fitting-window level, for a 30-day stake with no tenure",
    )
    renewal_tenure = param.Integer(default=4, bounds=(0, 100), doc="Completed commitments at which the renewal response prices the yield gap")
    draws = param.DataFrame(
        default=None, allow_None=True, precedence=-1,
        doc="One row per run of drawn block parameters: renewal.<name>, renewal_large.<name>, returns.<name>, "
            "arrivals.<name> and renewal_shift. Run r reads row r - 1, and a block parameter without a column keeps "
            "its fitted value",
    )
    supply0_navax = param.Integer(default=450_000_000 * 10**9, bounds=(1, 720_000_000 * 10**9), doc="The P-Chain reward counter at the origin, nAVAX. The reward formula reads it")

    # The daily step, run in this order (model.parts.stages). A plain class attribute, not a setting, so the
    # specification and its hash do not record it.
    stages = (
        ("renewal", renewal_stage),
        ("returns", returns_stage),
        ("arrivals", arrivals_stage),
        ("continuation", continuation_stage),
        ("rewards", rewards_stage),
        ("assembly", assembly_stage),
    )

    def state_variables(self):
        return ["active_validators", "active_validator_stake_navax", "returning_nodes", "supply_navax", "issued_navax"]

    def float_variables(self):
        return ["yield_gap_pp"]

    def __init__(self, **params):
        super().__init__(**params)
        if self.dt != 1:
            raise ValueError(f"the lifecycle clock is one UTC day per step, so dt must be 1, not {self.dt}")
        if (self.outside_yield_pp is None) != (self.fitted_outside_yield_pp is None):
            raise ValueError("give the outside yield and its level over the fitting window together, or neither")

    def initial_state(self):
        initial = self.initial if self.initial is not None else pd.DataFrame(columns=COMMITMENT)
        out = self.out_of_set if self.out_of_set is not None else pd.DataFrame(columns=OUT)
        state = {name: _column(initial, name, bool if name in ("after_return", "handed_on") else np.int64) for name in COMMITMENT}
        state |= {name: _column(out, name) for name in OUT}
        state["node_key"] = node_keys(KIND_OPEN, 0, np.arange(len(state["stakes"])))
        state["out_node_key"] = node_keys(KIND_OUT, 0, np.arange(len(state["out_stakes"])))
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
        """The mechanism's annual rate above the fitted menu's rate, less the outside yield's change from its
        fitting-window level, in percentage points, for a 30-day stake started on ``day`` (model.response).

        Before Helicon the fitted menu is the chain's rule, so with no outside yield this is the mechanism's rate minus
        the chain's. From Helicon the chain's own rule carries ACP-285's change in the rate.
        """
        return response_gap_pp(self.mechanism, self.fitted_menu, day, self.supply0_navax, completed_periods,
                               self.outside_yield_pp, self.fitted_outside_yield_pp)

    def _blocks_by_run(self):
        """A function from run number to that run's :class:`RunBlocks`: its renewal, large-holder renewal, arrival and
        return blocks, its renewal shift, its continuation table and its first-ever durations and stakes. Without
        ``draws`` every run gets the fitted blocks, no shift and the full tables. With them, run r's are built from row
        r - 1 on first use and kept. A ``resample_seed`` column resamples the tables by node, so it needs a
        ``node_code`` column in both."""
        fixed = {"renewal": self.renewal, "renewal_large": self.renewal_large, "arrivals": self.arrivals, "returns": self.returns}
        moves, first = self.moves, self.first_commitments
        tables = _continuation_tables(moves, first)
        if self.draws is None:
            same = RunBlocks(*fixed.values(), 0.0, *tables)
            return lambda run: same
        draws = self.draws
        if len(draws) < self.runs:
            raise ValueError(f"the draw table has {len(draws)} rows for {self.runs} runs")
        if "resample_seed" in draws.columns and not ("node_code" in moves.columns and "node_code" in first.columns):
            raise ValueError("a resample_seed column needs a node_code column in moves and first_commitments")
        known = {"renewal_shift", "resample_seed"} | {
            f"{prefix}.{name}" for prefix, block in fixed.items() if block is not None
            for name, parameter in block.param.objects().items() if "source" in (getattr(parameter, "metadata", None) or {})
        }
        unknown = sorted(set(draws.columns) - known)
        if unknown:
            raise ValueError(f"the draw table has columns no block of this model reads: {unknown}")
        built = {}

        def blocks_for(run: int):
            if run not in built:
                row = draws.iloc[run - 1]
                drawn = {prefix: _drawn(block, prefix, row, run) for prefix, block in fixed.items()}
                shift = float(row["renewal_shift"]) if "renewal_shift" in row.index else 0.0
                own = tables
                if "resample_seed" in row.index:
                    own = _continuation_tables(*resampled_tables(moves, first, int(row["resample_seed"]), run))
                built[run] = RunBlocks(*drawn.values(), shift, *own)
            return built[run]

        return blocks_for

    def blocks(self):
        days = [self.origin + timedelta(days=t + 1) for t in range(self.timesteps)]
        gaps = [(self.yield_gap_pp(day, self.renewal_tenure), self.yield_gap_pp(day, 0)) for day in days]
        blocks_for = self._blocks_by_run()
        large_navax = None if self.renewal_large is None or self.large_above_avax is None else int(self.large_above_avax * 10**9)
        seed, origin, stages = self.seed, self.origin, self.stages
        sched = self.scheduled if self.scheduled is not None else pd.DataFrame(columns=["start_day", "stakes", "days", "done", "after_return", "returns"])
        sched_day = _array(sched["start_day"])
        settings = RunSettings(
            large_navax=large_navax, renewal_response=self.renewal_response, entry_response=self.entry_response,
            mechanism=self.mechanism,
            scheduled={
                "start_day": sched_day, "stakes": _array(sched["stakes"]), "days": _array(sched["days"]),
                "done": _array(sched["done"]), "after_return": _array(sched["after_return"], bool),
                "returns": _column(sched, "returns"), "node_key": node_keys(KIND_SCHEDULED, 0, np.arange(len(sched_day))),
            },
        )

        def p_lifecycle(params, substep, history, state):
            t = state["timestep"]
            run = int(state["run"])
            renewal_gap, entry_gap = gaps[t]
            day = Day(
                t=t, start=datetime.combine(origin + timedelta(days=t + 1), time(12), tzinfo=UTC), draw=Streams(seed, run),
                blocks=blocks_for(run), renewal_gap=renewal_gap, entry_gap=entry_gap, settings=settings,
            )
            return run_stages(stages, state, day)

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

        copied = (*COMMITMENT, *OUT, "node_key", "out_node_key", "issued_navax", "yield_gap_pp")
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


def _continuation_tables(moves: pd.DataFrame, first: pd.DataFrame) -> tuple[Continuation, np.ndarray, np.ndarray]:
    continuation = Continuation(moves["previous_days"], moves["next_days"], moves["previous_stake_navax"], moves["next_stake_navax"])
    return continuation, _array(first["days"]), _array(first["stake_navax"])


def resampled_tables(moves: pd.DataFrame, first: pd.DataFrame, resample_seed: int, run: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """``moves`` and ``first`` resampled by ``node_code``, as many nodes as each holds, from the run's
    ``continuation_resample`` stream under ``resample_seed``."""
    rng = Streams(resample_seed, run).generator("continuation_resample")
    picked_moves = moves.iloc[node_resample(moves["node_code"].to_numpy(), rng)].reset_index(drop=True)
    picked_first = first.iloc[node_resample(first["node_code"].to_numpy(), rng)].reset_index(drop=True)
    return picked_moves, picked_first


def _drawn(block, prefix: str, row: pd.Series, run: int):
    """``block`` with every parameter that ``row`` holds under ``prefix`` replaced, labelled as that run's draw."""
    if block is None:
        return None
    for column, value in row.items():
        if column.startswith(prefix + "."):
            name = column[len(prefix) + 1:]
            evidence = block.sources()[name]["evidence"]
            block = block.with_value(name, float(value), "fitted", f"bootstrap draw {run} of: {evidence}")
    return block


def node_resample(node_codes: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Row indices of a bootstrap by node: as many nodes as there are, drawn with replacement, each with all its rows."""
    codes = np.asarray(node_codes)
    nodes, inverse = np.unique(codes, return_inverse=True)
    rows_of = np.split(np.argsort(inverse, kind="stable"), np.cumsum(np.bincount(inverse))[:-1])
    picked = rng.integers(0, len(nodes), len(nodes))
    return np.concatenate([rows_of[i] for i in picked]) if len(nodes) else np.zeros(0, dtype=np.int64)


def window_tau(observed_share, mean_probability, endings) -> float:
    """The SD of the renewal log-odds shift between quarters, net of binomial noise.

    For each quarter, ``d = logit(observed share) - logit(mean fitted probability)`` and its binomial variance
    ``v = 1 / (n p (1 - p))``. The shift's variance is ``max(0, var(d) - mean(v))``.
    """
    share = np.clip(np.asarray(observed_share, dtype=float), 1e-6, 1 - 1e-6)
    p = np.clip(np.asarray(mean_probability, dtype=float), 1e-6, 1 - 1e-6)
    n = np.asarray(endings, dtype=float)
    d = special.logit(share) - special.logit(p)
    v = 1 / (n * p * (1 - p))
    return float(np.sqrt(max(0.0, d.var(ddof=1) - v.mean())))


ARRIVAL_BLOCK_DAYS = 28
QUARTER_MIN_ENDINGS = 200
QUARTERS_FOR_TAU = 8
ASSUMED_TAU = 0.18


def renewal_quarters(endings: pd.DataFrame, through_us: int, renewal: RenewalLogit) -> pd.DataFrame:
    """Each calendar quarter of renewal endings that ended seven days before ``through_us``, so every ending in it is
    labelled, and that holds at least 200 endings: its count, its observed share renewed, and the mean probability
    ``renewal`` gives the same endings."""
    quarter = pd.to_datetime(endings["e"], unit="us").dt.to_period("Q")
    rows = []
    for period, part in endings.groupby(quarter.to_numpy(), sort=True):
        period = pd.Period(period, freq="Q")
        quarter_end_us = (period + 1).start_time.value // 1_000
        if quarter_end_us + RENEWAL_DAYS * US_PER_DAY > through_us or len(part) < QUARTER_MIN_ENDINGS:
            continue
        rows.append({"quarter": str(period), "endings": len(part), "observed": float(part["renewed"].mean()),
                     "mean_probability": float(renewal.probability(renewal_inputs(part)).mean())})
    return pd.DataFrame(rows, columns=["quarter", "endings", "observed", "mean_probability"])


def window_sd_from_quarters(table: pd.DataFrame) -> tuple[float, str]:
    """τ from a :func:`renewal_quarters` table, and its source. With fewer than eight quarters it is the assumed 0.18,
    the median of earlier in-sample estimates."""
    if len(table) < QUARTERS_FOR_TAU:
        return ASSUMED_TAU, f"assumed: {len(table)} quarters of at least {QUARTER_MIN_ENDINGS} labelled endings, fewer than {QUARTERS_FOR_TAU}"
    tau = window_tau(table["observed"], table["mean_probability"], table["endings"])
    return tau, f"fitted on {len(table)} quarters, {table['quarter'].iloc[0]} to {table['quarter'].iloc[-1]}"


def window_sd(periods_parquet: str, origin: date, renewal: RenewalLogit) -> tuple[float, str]:
    """τ at ``origin``: the drift of the renewal log-odds between quarters, net of binomial noise, measured against the
    origin's fitted ``renewal`` block on every labelled quarter before the origin. An origin in the lockbox is refused."""
    if origin >= LOCKBOX_FIRST_DAY:
        raise ValueError(f"origin {origin} is inside the validation lockbox, which starts 2025-11-19 16:00 UTC")
    cutoff = _day(origin) * US_PER_DAY + INSTANT_US
    rows = validator_periods(periods_parquet, cutoff)
    endings = renewal_endings(rows, -(2**62), cutoff - RENEWAL_DAYS * US_PER_DAY)
    return window_sd_from_quarters(renewal_quarters(endings, cutoff, renewal))


def arrival_block_sample(counts, rng: np.random.Generator, block_days: int = ARRIVAL_BLOCK_DAYS) -> np.ndarray:
    """A moving-block bootstrap of daily counts: whole runs of ``block_days`` consecutive days, drawn with replacement
    and joined, the last cut so the sample is as long as ``counts``. Whole blocks keep the week-to-week correlation that
    resampling single days would break. For 365 days that is 14 blocks, the last cut to one day."""
    counts = np.asarray(counts)
    if len(counts) < block_days:
        raise ValueError(f"at least {block_days} days of counts are needed")
    starts = rng.integers(0, len(counts) - block_days + 1, -(-len(counts) // block_days))
    return np.concatenate([counts[start:start + block_days] for start in starts])[:len(counts)]


def _prefixed(prefix: str, block) -> dict[str, float]:
    return {f"{prefix}.{name}": meta["value"] for name, meta in block.sources().items()}


def parameter_draws(events: TrainingEvents, n: int, seed: int, tau: float, large_above_avax: float | None = None) -> pd.DataFrame:
    """``n`` draws of every fitted block parameter, one row per run, for the ``draws`` input of :class:`FittedLifecycle`.

    Draw i refits each block on a resample of its training events: renewal endings and return spells by node, so a
    node's decisions stay together, and arrivals by 28-day blocks. With ``large_above_avax``, the endings are resampled
    once and then split at the line, so the two renewal blocks share their nodes. Each draw adds a renewal shift from
    Normal(0, ``tau``), the drift of the renewal log-odds between quarters, and the seed of the run's continuation
    resample. Draws come from the ``parameter_draw`` stream, so a seed reproduces its table.
    """
    if events.origin >= LOCKBOX_FIRST_DAY:
        raise ValueError(f"origin {events.origin} is inside the validation lockbox, which starts 2025-11-19 16:00 UTC")
    ended, lapsed = events.endings, events.lapsed
    rows = []
    for i in range(n):
        rng = Streams(seed, 0).generator("parameter_draw", i)
        evidence = f"bootstrap draw {i} of {events.window}"
        picked = ended.iloc[node_resample(ended["node_code"].to_numpy(), rng)]
        row = {}
        if large_above_avax is None:
            row |= _prefixed("renewal", RenewalLogit.fit(renewal_inputs(picked), picked["renewed"].to_numpy(), evidence))
        else:
            big = (picked["stake_navax"] > large_above_avax * 10**9).to_numpy()
            small, large = picked[~big], picked[big]
            row |= _prefixed("renewal", RenewalLogit.fit(renewal_inputs(small), small["renewed"].to_numpy(), evidence))
            row |= _prefixed("renewal_large", RenewalLogit.fit(renewal_inputs(large), large["renewed"].to_numpy(), evidence))
        back = lapsed.iloc[node_resample(lapsed["node_code"].to_numpy(), rng)]
        row |= _prefixed("returns", ReturnHazard.fit(back["stake_navax"].to_numpy(), back["days_out"].to_numpy(),
                                                    back["came_back"].to_numpy(), evidence))
        row |= _prefixed("arrivals", Arrivals.fit(arrival_block_sample(events.first_counts, rng), evidence))
        row["renewal_shift"] = float(rng.normal(0.0, tau))
        row["resample_seed"] = int(rng.integers(0, 2**31 - 1))
        rows.append(row)
    return pd.DataFrame(rows)


RENEWAL_CLIP = 20.0


def clipped_draws(draws: pd.DataFrame) -> int:
    """The number of draws with any renewal log-odds term at the fit's ±20 clip, where a separable cell in a resample
    sends a coefficient to its bound. The node record's prior strength and the renewal shift are not log-odds terms."""
    terms = [c for c in draws.columns if c.split(".")[0] in ("renewal", "renewal_large") and not c.split(".")[-1].startswith("node_prior")]
    return int((draws[terms].abs() >= RENEWAL_CLIP - 1e-9).any(axis=1).sum()) if terms else 0


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


@dataclass(frozen=True)
class TrainingEvents:
    """Everything a v0.8 fit reads from the staking periods at one origin, with each node as an integer ``node_code``
    shared across the tables, so a bootstrap can resample nodes."""

    origin: date
    run: str
    window: str
    endings: pd.DataFrame
    lapsed: pd.DataFrame
    first_counts: np.ndarray
    first_total: int
    moves: pd.DataFrame
    first_commitments: pd.DataFrame
    state: dict


def training_events(periods_parquet: str, origin: date, run: str = "") -> TrainingEvents:
    """The events :func:`fitted_inputs` fits on, read from staking periods that started by the origin's end."""
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

    lapsed = rows[(rows["e"] > cutoff - 730 * US_PER_DAY) & (rows["e"] <= cutoff) & ~overlapped & ~rows["renewed"]]
    came_back = lapsed["next_s"].notna()
    days_out = np.where(came_back, np.ceil((lapsed["next_s"] - lapsed["e"]) / US_PER_DAY), np.floor((cutoff - lapsed["e"]) / US_PER_DAY))

    enter_day = _whole_days(rows["s"])
    year = rows[(enter_day > day - 365) & (enter_day <= day)]
    first = year[year["done"] == 0]
    counts = np.bincount((_whole_days(first["s"]) - (day - 364)).to_numpy(dtype=np.int64), minlength=365)

    moved = rows[rows["next_s"].notna() & ~overlapped & (rows["next_s"] > cutoff - 365 * US_PER_DAY) & (rows["next_s"] <= cutoff)]
    moves = pd.DataFrame({
        "node_id": moved["node_id"].to_numpy(),
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
    codes = {node: i for i, node in enumerate(sorted(set(ended["node_id"]) | set(lapsed["node_id"]) | set(moved["node_id"]) | set(first["node_id"])))}

    def code_of(nodes) -> np.ndarray:
        return np.array([codes[n] for n in nodes], dtype=np.int64)

    return TrainingEvents(
        origin=origin, run=run, window=window,
        endings=ended.assign(node_code=code_of(ended["node_id"])),
        lapsed=pd.DataFrame({"stake_navax": lapsed["stake_navax"].to_numpy(), "days_out": days_out,
                             "came_back": came_back.to_numpy(), "node_code": code_of(lapsed["node_id"])}),
        first_counts=counts, first_total=len(first),
        moves=moves.assign(node_code=code_of(moves.pop("node_id"))),
        first_commitments=pd.DataFrame({"days": first["days"].to_numpy(), "stake_navax": first["stake_navax"].to_numpy(dtype=np.int64),
                                        "node_code": code_of(first["node_id"])}),
        state={"initial": initial, "out_of_set": out_of_set, "scheduled": scheduled, "supply0_navax": int(supply)},
    )


def fit_blocks(events: TrainingEvents, large_above_avax: float | None = None) -> dict:
    """Every input of a v0.8 run, with its blocks fitted on ``events``. See :func:`fitted_inputs`."""
    run, origin, window, ended = events.run, events.origin, events.window, events.endings
    renewal = RenewalLogit.fit(renewal_inputs(ended), ended["renewed"].to_numpy(), f"{window}: {len(ended)} endings, {int(ended['renewed'].sum())} renewed")
    renewal_large = None
    if large_above_avax is not None:
        big = ended["stake_navax"] > large_above_avax * 10**9
        small, large = ended[~big], ended[big]
        renewal = RenewalLogit.fit(renewal_inputs(small), small["renewed"].to_numpy(), f"{window}, at or below {large_above_avax:,.0f} AVAX: {len(small)} endings")
        renewal_large = RenewalLogit.fit(renewal_inputs(large), large["renewed"].to_numpy(), f"{window}, above {large_above_avax:,.0f} AVAX: {len(large)} endings")
    lapsed = events.lapsed
    returns = ReturnHazard.fit(
        lapsed["stake_navax"].to_numpy(), lapsed["days_out"].to_numpy(), lapsed["came_back"].to_numpy(),
        f"{run or 'staking periods'}, {len(lapsed)} endings without renewal in the 730 days before {origin}",
    )
    arrivals = Arrivals.fit(events.first_counts, f"{run or 'staking periods'}, {events.first_total} first-ever commitments in the 365 days to {origin}")
    renewing = ended[ended["renewed"]]
    state = events.state
    # The fitting window ends with the origin's day. Its widest block, returns, reaches back 730 days.
    fitting_end = datetime.combine(origin + timedelta(days=1), time(0), tzinfo=UTC)
    return {
        "origin": origin,
        "renewal": renewal,
        **({"renewal_large": renewal_large, "large_above_avax": large_above_avax} if renewal_large is not None else {}),
        "arrivals": arrivals,
        "returns": returns,
        "initial": state["initial"],
        "out_of_set": state["out_of_set"],
        "scheduled": state["scheduled"],
        "moves": events.moves.drop(columns="node_code"),
        "first_commitments": events.first_commitments.drop(columns="node_code"),
        "renewal_tenure": int(np.median(renewing["done"])) + 1 if len(renewing) else 1,
        "supply0_navax": state["supply0_navax"],
        "inputs_source": run,
        "fitted_menu": FittedMenu.for_window(fitting_end - timedelta(days=730), fitting_end),
    }


def fitted_inputs(periods_parquet: str, origin: date, run: str = "", large_above_avax: float | None = None) -> dict:
    """Every input of a v0.8 run from ``origin``, fitted on staking periods that started by the origin's end.

    * Renewal: endings in the 365 days before the origin with seven days of follow-up before it, as ``AM2`` counts them.
      With ``large_above_avax``, one renewal block is fitted on the endings at or below that stake and another above it.
    * Returns: endings in the 730 days before the origin that did not renew, each followed until it returned or the
      origin came, so a node out at the origin is censored there.
    * Arrivals: daily counts of first-ever commitments in the 365 days before the origin.
    * Continuations: renewals and returns that started in the 365 days before the origin.
    * Fitted menu: the chain's reward rule at the origin's end, the point the behaviour responses count from.

    Commitments accepted by the origin that start after it enter on their start day, already minted. An open
    commitment whose node has one of them is handed on to it, with no renewal draw. A node that ended in the week
    before the origin without a new commitment is out of the set, so its chance to renew in what is left of its
    week is not drawn. An origin inside the validation lockbox is refused.
    """
    return fit_blocks(training_events(periods_parquet, origin, run), large_above_avax)
