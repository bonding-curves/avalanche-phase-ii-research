"""The fitted lifecycle's daily step as an ordered list of stages.

A stage is a function ``stage(state, day, earlier) -> dict``. It reads the state at the start of the day, the
:class:`Day` (the day, its keyed draws, the run's blocks and the run's settings) and ``earlier``, the outputs of the
stages before it by stage name, and returns its own outputs. The last stage's output is the day's policy signal.

Each behaviour stage lives in the module of its part: :func:`~avalanche_research.model.parts.renewal.renewal_stage`,
:func:`~avalanche_research.model.parts.returns.returns_stage`,
:func:`~avalanche_research.model.parts.arrivals.arrivals_stage` and
:func:`~avalanche_research.model.parts.continuation.continuation_stage`. The rewards and assembly stages, which
belong to no behaviour part, live here.

Every draw is a uniform keyed by its purpose, node and decision count, so the order the stages run in changes no draw.
The order of the commitments in the next state does matter, and the assembly stage keeps it: the open commitments that
continue, then those started today (renewed, returned, arrived), then the scheduled ones due today.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, NamedTuple

import numpy as np

from avalanche_research.model.parts.base import RETURN_DAYS

if TYPE_CHECKING:
    from avalanche_research.mechanisms import RewardMechanism
    from avalanche_research.model.parts.arrivals import Arrivals
    from avalanche_research.model.parts.continuation import Continuation
    from avalanche_research.model.parts.duration_transition import DurationTransition
    from avalanche_research.model.parts.renewal import RenewalLogit
    from avalanche_research.model.parts.return_hazard import ReturnLogitHazard
    from avalanche_research.model.parts.returns import ReturnHazard
    from avalanche_research.model.streams import Streams

Stage = Callable[[Mapping[str, Any], "Day", Mapping[str, dict]], dict]


class RunBlocks(NamedTuple):
    """One run's blocks: fitted, or built from the run's row of parameter draws."""

    renewal: RenewalLogit
    renewal_large: RenewalLogit | None
    arrivals: Arrivals
    returns: ReturnHazard | ReturnLogitHazard
    renewal_shift: float
    continuation: Continuation
    first_days: np.ndarray
    first_stakes: np.ndarray
    durations: DurationTransition | None = None


@dataclass(frozen=True, eq=False)
class RunSettings:
    """What every day of every run reads: the large-holder line, the yield-gap responses, the reward rule, and the
    commitments accepted by the origin that start after it, one array per column."""

    large_navax: int | None
    renewal_response: float
    entry_response: float
    mechanism: RewardMechanism
    scheduled: dict[str, np.ndarray]
    market_renewal_shift: float = 0.0
    market_entry_shift: float = 0.0
    # The participation feedback (parts.participation): the arrival rate's elasticity to the unstaked share of supply,
    # and that share at the origin, which the scale is one at.
    participation_elasticity: float = 0.0
    unstaked_share0: float = 1.0


@dataclass(frozen=True, eq=False)
class Day:
    """What a stage reads besides the state: timestep ``t``, noon UTC of the day it steps to, the run's keyed draws,
    the run's blocks, the day's yield gaps for renewal and entry, and the run's settings."""

    t: int
    start: datetime
    draw: Streams
    blocks: RunBlocks
    renewal_gap: float
    entry_gap: float
    settings: RunSettings


def run_stages(stages: tuple[tuple[str, Stage], ...], state: Mapping[str, Any], day: Day) -> dict:
    """Run ``stages`` in order on one day and return the last stage's output."""
    outputs: dict[str, dict] = {}
    for name, stage in stages:
        outputs[name] = stage(state, day, outputs)
    return outputs[stages[-1][0]]


OFFERED_RATE_DAYS = 30
"""The duration whose annual rate the run writes each day as ``offered_rate_30d``."""


def rewards_stage(state: Mapping[str, Any], day: Day, earlier: Mapping[str, dict]) -> dict:
    """The rewards minted for every commitment started today, priced by the reward rule at the day's supply and, for a
    rule that reads it, the share of supply staked at the start of the day, with the started commitments' stake and
    stake-days and the annual rate the rule offers a 30-day stake with no tenure at that supply. The scheduled
    commitments due today are not started here, so none of these counts them."""
    from avalanche_research.model.parts.participation import unstaked_share

    started = earlier["continuation"]["started"]
    mechanism = day.settings.mechanism
    share = 1.0 - unstaked_share(state) if "supply_navax" in state else None
    issued = sum(
        mechanism.potential_reward_navax(int(stake), int(d) * 86_400, state["supply_navax"], day.start, int(periods), share)
        for stake, d, periods in zip(started["stakes"], started["days"], started["done"])
    )
    return {
        "issued_navax": int(issued),
        "started_stake_navax": int(sum(int(stake) for stake in started["stakes"])),
        "started_stake_days_navax": float(sum(int(stake) * int(d) for stake, d in zip(started["stakes"], started["days"]))),
        "offered_rate_30d": float(mechanism.annual_rate(OFFERED_RATE_DAYS, int(state["supply_navax"]), day.start, staked_share=share)),
    }


def assembly_stage(state: Mapping[str, Any], day: Day, earlier: Mapping[str, dict]) -> dict:
    """The next state's commitments and nodes out of the set. Open commitments that do not end today stay, followed by
    those started today and the scheduled ones due today. A node out of the set stays out until it returns or its 365
    days pass, followed by the nodes whose commitment ended today without renewal, or whose renewal the supply limit
    did not fund. The rewards stage's outputs pass through."""
    renewal, returns, continuation = earlier["renewal"], earlier["returns"], earlier["continuation"]
    started = continuation["started"]
    days_left, ending, ended = renewal["days_left"], renewal["ending"], renewal["ended"]
    # The supply limit can turn a renewal into a leave and a return into a stay (parts.participation).
    renews = continuation.get("renews", renewal["renews"])
    out_days, comes_back = returns["out_days"], continuation.get("comes_back", returns["comes_back"])
    sched = day.settings.scheduled
    stay_out = ~comes_back & (out_days <= RETURN_DAYS)
    left = ~renews
    due = sched["start_day"] == day.t + 1
    keep = ~ending
    return {
        "stakes": np.concatenate([state["stakes"][keep], started["stakes"], sched["stakes"][due]]),
        "days_left": np.concatenate([days_left[keep], started["days"], sched["days"][due]]),
        "done": np.concatenate([state["done"][keep], started["done"], sched["done"][due]]),
        "after_return": np.concatenate([state["after_return"][keep], started["after_return"], sched["after_return"][due]]),
        "days": np.concatenate([state["days"][keep], started["days"], sched["days"][due]]),
        "handed_on": np.concatenate([state["handed_on"][keep], np.zeros(len(started["stakes"]) + int(due.sum()), bool)]),
        "returns": np.concatenate([state["returns"][keep], started["returns"], sched["returns"][due]]),
        "node_key": np.concatenate([state["node_key"][keep], started["node_key"], sched["node_key"][due]]),
        "out_stakes": np.concatenate([state["out_stakes"][stay_out], ended["stakes"][left]]),
        "out_days": np.concatenate([out_days[stay_out], np.zeros(int(left.sum()), dtype=np.int64)]),
        "out_done": np.concatenate([state["out_done"][stay_out], ended["done"][left] + 1]),
        "out_last_days": np.concatenate([state["out_last_days"][stay_out], ended["days"][left]]),
        "out_returns": np.concatenate([state["out_returns"][stay_out], ended["returns"][left]]),
        "out_node_key": np.concatenate([state["out_node_key"][stay_out], ended["node_key"][left]]),
        **earlier["rewards"],
        "yield_gap_pp": float(day.renewal_gap),
    }


def bounded_days(days: np.ndarray, mechanism: RewardMechanism | None) -> np.ndarray:
    """Durations moved to the nearer of the mechanism's bounds, or unchanged when it sets none or there is none."""
    bounds = None if mechanism is None else mechanism.duration_bounds()
    if bounds is None:
        return days
    return np.clip(days, bounds[0], bounds[1]).astype(np.int64)
