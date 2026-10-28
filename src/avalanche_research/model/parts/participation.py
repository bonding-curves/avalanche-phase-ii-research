"""Participation: the unstaked AVAX that new stake comes from, as a feedback on arrivals and as a hard limit.

The model's supply is the P-Chain reward counter. What is not staked on it is the pool new stake can come from:
the supply less the validator stake and the delegated stake open at the time. Two rules read that pool.

The participation feedback scales the first-ever arrival rate by the unstaked share of supply, relative to its level
at the origin, raised to the elasticity ``participation_elasticity``: ``((1 - r_t) / (1 - r_0)) ** gamma`` with ``r``
the staked share. At the origin the scale is one, so the fitted arrival rate is the rate at the origin's level of
participation. At ``gamma = 1`` every unstaked AVAX carries the same hazard of being staked for the first time, so a
run that stakes half of what was unstaked halves the arrival rate, and arrivals stop as the unstaked pool empties. At
``gamma = 0`` the rate does not read participation, which is model v0.8.0. Across the 17 quarters from July 2021 to
September 2025 the record's first-ever arrivals per day moved in proportion to the unstaked share of supply: a
regression of their logs has a slope of 1.03, over an unstaked share of 0.34 to 0.52. The slope is confounded with the
network's age and the AVAX price, so it bounds the elasticity at one rather than estimating it.

The supply limit is the backstop the invariant ``stake within supply`` relies on. Every commitment that starts on a
day takes its stake from the pool left after the commitments that continue, those scheduled to start that day and the
delegated stake, in the order renewed, returned, arrived. Each takes the smaller of its drawn stake and the room left.
When the room left is below the protocol's minimum validator stake, a renewing node leaves the set, a returning node
stays out and an arrival is not made. A new delegation is placed only while the pool left after the day's validators
covers its stake, and is otherwise counted as unplaced. At the record's levels, about 45% of supply staked, the pool
is hundreds of millions of AVAX against a day's new stake of a few million, so the limit never binds there and the
run is unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from avalanche_research.model.parts.base import AVAX

MIN_STAKE_NAVAX = 2_000 * AVAX
"""The protocol's minimum validator stake, below which no commitment can start."""


def staked_navax(state: Mapping[str, Any]) -> int:
    """The validator stake and, in a model that carries delegations, the delegated stake open in ``state``."""
    delegated = int(state["active_delegated_stake_navax"]) if "active_delegated_stake_navax" in state else 0
    return int(state["active_validator_stake_navax"]) + delegated


def unstaked_share(state: Mapping[str, Any]) -> float:
    """The share of the supply counter not staked in ``state``, at least zero."""
    supply = int(state["supply_navax"])
    return max(0.0, 1.0 - staked_navax(state) / supply) if supply > 0 else 0.0


def participation_scale(share: float, share0: float, elasticity: float) -> float:
    """The arrival rate's scale from the unstaked share ``share`` against the origin's ``share0``: one at the origin,
    one everywhere when the elasticity is zero, and zero once nothing is unstaked."""
    if elasticity == 0.0:
        return 1.0
    if share0 <= 0.0:
        raise ValueError("the participation feedback needs some unstaked supply at the origin")
    return float(max(0.0, share / share0) ** elasticity)


def funded(stakes: np.ndarray, pool: int, minimum: int = MIN_STAKE_NAVAX) -> tuple[np.ndarray, np.ndarray]:
    """Each stake in order takes the smaller of itself and the room left in ``pool``. Returns the funded stakes and
    which of them start: those whose room was at least ``minimum``."""
    stakes = np.asarray(stakes, dtype=np.int64)
    out = stakes.copy()
    made = np.ones(len(stakes), dtype=bool)
    room = int(pool)
    for i, stake in enumerate(stakes.tolist()):
        if room < minimum:
            made[i] = False
            out[i] = 0
            continue
        if stake > room:
            out[i] = room
        room -= int(out[i])
    return out, made


def validator_pool(state: Mapping[str, Any], day, earlier: Mapping[str, dict]) -> int:
    """The AVAX the day's starting commitments can take: the supply less the commitments that continue, those
    scheduled to start today, the delegated stake open at the start of the day and the delegations scheduled to start
    today."""
    keep = ~earlier["renewal"]["ending"]
    sched = day.settings.scheduled
    due = sched["start_day"] == day.t + 1
    delegated = int(state["active_delegated_stake_navax"]) if "active_delegated_stake_navax" in state else 0
    if "scheduled_stakes" in state:
        delegated += int(state["scheduled_stakes"][state["scheduled_start_day"] == day.t + 1].sum())
    return int(state["supply_navax"]) - int(state["stakes"][keep].sum()) - int(sched["stakes"][due].sum()) - delegated


def cap_started(state: Mapping[str, Any], day, earlier: Mapping[str, dict], started: dict, n_renewed: int, n_back: int) -> dict:
    """The continuation stage's output under the supply limit: the started commitments that the pool funds, with the
    renewal and return decisions those drops change. When every commitment fits, the output is the input unchanged."""
    renews, comes_back = earlier["renewal"]["renews"], earlier["returns"]["comes_back"]
    if day.settings is None or "ending" not in earlier["renewal"] or "supply_navax" not in state:
        # The stage called on its own, outside a run, has no pool to read.
        return {"started": started, "renews": renews, "comes_back": comes_back}
    pool = validator_pool(state, day, earlier)
    stakes, made = funded(started["stakes"], pool)
    if made.all() and (stakes == started["stakes"]).all():
        return {"started": started, "renews": renews, "comes_back": comes_back}
    renews, comes_back = renews.copy(), comes_back.copy()
    renews[np.flatnonzero(renews)[~made[:n_renewed]]] = False
    comes_back[np.flatnonzero(comes_back)[~made[n_renewed:n_renewed + n_back]]] = False
    kept = {name: np.asarray(value)[made] for name, value in started.items()}
    kept["stakes"] = stakes[made]
    return {"started": kept, "renews": renews, "comes_back": comes_back}


def delegation_pool(state: Mapping[str, Any], validators: Mapping[str, Any], open_navax: int) -> int:
    """The AVAX the day's new delegations can take: the supply after the day's validator rewards, less the next
    state's validator stake and the delegated stake already open or starting today."""
    return int(state["supply_navax"]) + int(validators["issued_navax"]) - int(validators["stakes"].sum()) - int(open_navax)


def within_pool(order: np.ndarray, stakes: np.ndarray, pool: int) -> np.ndarray:
    """The prefix of ``order`` whose stakes fit in ``pool`` one after another."""
    if not len(order):
        return order
    taken = np.cumsum(stakes[order])
    return order[: int(np.searchsorted(taken, int(pool), side="right"))]
