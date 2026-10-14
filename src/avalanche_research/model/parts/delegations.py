"""Delegations: the stage that ages, starts and places delegations on the day's validators, and mints their rewards.

The stage runs last, after the assembly stage, because it reads the next state's validators: the commitments that
continue, those started today and the scheduled ones due today, each with its days left after today.

Each day, open delegations age and those at their end leave. Delegations accepted by the origin that start today
become open. Then the flow block draws the day's new delegations and which of them are BENQI's. Each takes a stake
and a requested duration from the delegations of the year before the origin, and goes to one eligible validator,
chosen by the delegator choice block or, for BENQI, by the BENQI allocation block among BENQI's own validators.

A validator is eligible for a delegation of stake ``s`` when it has at least 14 days left and its reserved room is at
least ``s``. The reserved room is the validator's weight limit, less its own stake, less its open delegations, less
the delegations accepted by the origin that have not yet started. A delegation lasts the requested days or its
validator's days left, if fewer. One with no eligible validator is not made and is counted as unplaced.

Placement runs in batches of ``batch`` delegations in draw order. Within a batch, each delegation chooses on the room
at the batch's start: the eligible validators are those with room for its stake, and it inverts its uniform over
their choice probabilities, renormalised. Then each validator accepts its choosers in draw order while their stakes
fit its room, and the rest choose again in the next batch on the room left. With a batch of one, every placement reads
the room left by the one before. Each new delegation mints its potential reward on the supply left by the one before
it, in the order they were accepted, after the day's validator rewards.

Under the containment rule (``setup.rule == "containment"``), the choice set of a delegation of stake ``s`` for ``d``
days is instead every active validator whose period contains the delegation's whole interval, ``days_left >= d``, and
whose room covers ``s`` after the largest load of every earlier-accepted delegation on any day of that interval, the
open ones, the scheduled ones and those accepted earlier today. Placement runs in batches of ``batch``: every
delegation of a batch counts every other delegation of the batch against the room, whichever validator it chooses, so
each choice is feasible however the batch falls. A batch of one places each delegation on the room left by the one
before it. The delegation runs its requested days, never cut to the validator's. The ordinary choice goes by
``setup.choice`` on each candidate's own stake plus its open delegated stake on the delegation's first day. BENQI's
choice goes by ``setup.allocation`` over its prior-use set, the validator periods it held open or scheduled in the 365
days before the decision, carried in the state as ``benqi_use_key``, ``benqi_use_navax`` (BENQI's total delegated stake
on each) and ``benqi_use_until`` (the last day one of its delegations there was open), and grown by each BENQI
placement.

Each delegation carries the row of the named operator that owns it, or -1. A new delegation drawn as BENQI's is owned by
BENQI's row. One drawn as another delegator's is owned by the named operator, other than BENQI, that owned the
delegation of the year before whose terms it takes, or by none. From a named operator's closing day, the new
delegations it would own are not made: they are not placed, not counted as unplaced, and move no other draw, since
every draw is keyed by its own index.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from avalanche_research.domain.protocol import (
    MAINNET,
    SECONDS_PER_DAY,
    delegation_weight_limit_navax,
)

if TYPE_CHECKING:
    from datetime import datetime

    from avalanche_research.model.delegation_blocks import (
        BenqiAllocation,
        DelegationFlow,
        DelegatorChoice,
    )
    from avalanche_research.model.parts.stages import Day

MIN_DELEGATION_DAYS = MAINNET.min_stake_duration_seconds // SECONDS_PER_DAY
MIN_DELEGATOR_STAKE = MAINNET.min_delegator_stake_navax
BENQI_USE = ("benqi_use_key", "benqi_use_navax", "benqi_use_until")
WINDOW_DAYS = 365
DELEGATION = ("delegation_stakes", "delegation_days_left", "delegation_days", "delegation_validator", "delegation_benqi", "delegation_rewards",
              "delegation_operator")
SCHEDULED = ("scheduled_stakes", "scheduled_start_day", "scheduled_days", "scheduled_validator", "scheduled_benqi", "scheduled_operator")


@dataclass(frozen=True, eq=False)
class DelegationSetup:
    """What the delegations stage reads besides the state and the day: the three blocks, every validator's fee in
    millionths, the delegation multiplier, the node keys of BENQI's validators, the terms new delegations draw from,
    BENQI's and the others', each as stakes, days and the named operator row that owns the delegation, the placement
    batch size, BENQI's row among the named operators, -1 when it is not named, and for each named operator row the day
    counted from the origin from which it makes no new delegation, infinite when it does not close."""

    flow: DelegationFlow
    choice: DelegatorChoice
    allocation: BenqiAllocation
    fee_shares: int
    multiplier: int
    benqi_keys: np.ndarray
    terms: Mapping[bool, tuple[np.ndarray, np.ndarray]]
    batch: int
    benqi_operator: int = -1
    closes_days: np.ndarray = field(default_factory=lambda: np.zeros(0))
    rule: str = "reserved room"


def limits(stakes: np.ndarray, chain_time: datetime, multiplier: int) -> np.ndarray:
    """Each validator's weight limit at ``chain_time``."""
    return np.array([delegation_weight_limit_navax(int(s), chain_time, multiplier) for s in stakes], dtype=np.int64)


def on_validators(validator_keys: np.ndarray, delegation_keys: np.ndarray) -> np.ndarray:
    """Each delegation's row among the validators, or -1 when its validator is not active."""
    if not len(delegation_keys):
        return np.zeros(0, dtype=np.int64)
    if not len(validator_keys):
        return np.full(len(delegation_keys), -1, dtype=np.int64)
    order = np.argsort(validator_keys, kind="stable")
    at = np.minimum(np.searchsorted(validator_keys, delegation_keys, sorter=order), len(order) - 1)
    rows = order[at]
    return np.where(validator_keys[rows] == delegation_keys, rows, -1)


def stake_on(n_validators: int, rows: np.ndarray, stakes: np.ndarray) -> np.ndarray:
    """Stake per validator row, leaving out delegations whose row is -1."""
    on = rows >= 0
    total = np.zeros(n_validators, dtype=np.int64)
    np.add.at(total, rows[on], stakes[on])
    return total


def _choose(stakes: np.ndarray, u: np.ndarray, room: np.ndarray, candidates: np.ndarray, probabilities) -> np.ndarray:
    """The validator row each delegation chooses on ``room``, or -1 when none of ``candidates`` has room for it.

    The candidates are sorted by room, largest first, so each delegation's eligible set is a prefix. Its uniform is
    inverted over the cumulative choice probabilities of that prefix."""
    rows = np.flatnonzero(candidates)
    chosen = np.full(len(stakes), -1, dtype=np.int64)
    if not len(rows) or not len(stakes):
        return chosen
    rows = rows[np.argsort(-room[rows], kind="stable")]
    cumulative = np.cumsum(probabilities(rows))
    eligible = np.searchsorted(-room[rows], -stakes, side="right")
    some = eligible > 0
    last = eligible[some] - 1
    pick = np.minimum(np.searchsorted(cumulative, u[some] * cumulative[last], side="right"), last)
    chosen[some] = rows[pick]
    return chosen


def place(stakes: np.ndarray, is_benqi: np.ndarray, u_choice: np.ndarray, u_benqi: np.ndarray, room: np.ndarray,
          open_long: np.ndarray, in_benqi: np.ndarray, setup: DelegationSetup) -> tuple[np.ndarray, np.ndarray]:
    """Place the day's delegations in batches of ``setup.batch``. Returns the order in which they were accepted and
    each one's validator row, -1 when unplaced. ``room`` is reduced in place by every accepted stake."""
    fee = setup.fee_shares

    def others(rows):
        return setup.choice.probabilities({"fee_shares": np.full(len(rows), fee), "remaining_navax": room[rows]})

    def benqi(rows):
        return setup.allocation.probabilities({"remaining_navax": room[rows]})

    validator = np.full(len(stakes), -1, dtype=np.int64)
    accepted: list[np.ndarray] = []
    pending = np.arange(len(stakes))
    while len(pending):
        batch, pending = pending[:setup.batch], pending[setup.batch:]
        candidates = open_long & (room >= MIN_DELEGATOR_STAKE)
        chosen = np.full(len(batch), -1, dtype=np.int64)
        kind = is_benqi[batch]
        chosen[~kind] = _choose(stakes[batch[~kind]], u_choice[batch[~kind]], room, candidates, others)
        chosen[kind] = _choose(stakes[batch[kind]], u_benqi[batch[kind]], room, candidates & in_benqi, benqi)
        # Each validator accepts its choosers in draw order while their stakes fit its room.
        tried = chosen >= 0
        order = np.argsort(chosen[tried], kind="stable")
        rows, want = chosen[tried][order], stakes[batch[tried]][order]
        running = np.cumsum(want)
        starts = np.r_[0, np.flatnonzero(np.diff(rows)) + 1] if len(rows) else np.zeros(0, dtype=np.int64)
        before = np.repeat(running[starts] - want[starts], np.diff(np.r_[starts, len(rows)]))
        fits = np.zeros(len(rows), dtype=bool)
        fits[order] = running - before <= room[rows]
        took = np.zeros(len(batch), dtype=bool)
        took[np.flatnonzero(tried)] = fits
        np.subtract.at(room, chosen[took], stakes[batch[took]])
        validator[batch[took]] = chosen[took]
        accepted.append(batch[took])
        pending = np.concatenate([batch[tried & ~took], pending])
    return (np.concatenate(accepted) if accepted else np.zeros(0, dtype=np.int64)), validator


def load_profile(n_validators: int, horizon: int, rows: np.ndarray, starts: np.ndarray, ends: np.ndarray, stakes: np.ndarray) -> np.ndarray:
    """``load[r, k]``: the delegated stake on validator row ``r`` on day ``k`` ahead, 0 being the first day of a new
    delegation, from delegations covering the day offsets ``[start, end)``. A row of -1 is on no active validator."""
    diff = np.zeros((n_validators, horizon + 1), dtype=np.int64)
    on = (rows >= 0) & (starts < horizon) & (ends > starts)
    first, last = np.clip(starts[on], 0, horizon), np.clip(ends[on], 0, horizon)
    np.add.at(diff, (rows[on], first), stakes[on])
    np.add.at(diff, (rows[on], last), -stakes[on])
    return np.cumsum(diff, axis=1)[:, :horizon]


def place_contained(stakes: np.ndarray, days: np.ndarray, is_benqi: np.ndarray, u_choice: np.ndarray, u_benqi: np.ndarray,
                    load: np.ndarray, room_limit: np.ndarray, validator_days: np.ndarray, own: np.ndarray,
                    prior_use: np.ndarray, prior_stakes: np.ndarray, setup: DelegationSetup) -> np.ndarray:
    """Place the day's delegations under the containment rule, in batches of ``setup.batch`` in draw order. Returns
    each one's validator row, -1 when no validator is feasible. ``load`` (validators by days ahead), ``prior_use`` and
    ``prior_stakes`` are updated in place by every accepted delegation."""
    chosen = np.full(len(stakes), -1, dtype=np.int64)
    if not len(stakes):
        return chosen
    peak = np.maximum.accumulate(load, axis=1)
    for start in range(0, len(stakes), setup.batch):
        batch = np.arange(start, min(start + setup.batch, len(stakes)))
        d, s = days[batch], stakes[batch]
        peers = s.sum() - s
        room = room_limit[None, :] - peak[:, d - 1].T - peers[:, None]
        eligible = (validator_days[None, :] >= d[:, None]) & (room >= s[:, None])
        open_now = load[:, 0]
        for j, i in enumerate(batch):
            rows = np.flatnonzero(eligible[j])
            if not len(rows):
                continue
            inputs = {"own_stake_navax": own[rows], "open_delegated_navax": open_now[rows]}
            if is_benqi[i]:
                inputs |= {"prior_use": prior_use[rows], "benqi_stake_navax": prior_stakes[rows]}
                chosen[i] = rows[setup.allocation.choose_from_uniform(inputs, float(u_benqi[i]))]
            else:
                chosen[i] = rows[setup.choice.choose_from_uniform(inputs, float(u_choice[i]))]
        for i in batch[chosen[batch] >= 0]:
            row = chosen[i]
            load[row, :days[i]] += stakes[i]
            peak[row] = np.maximum.accumulate(load[row])
            if is_benqi[i]:
                prior_use[row] = True
                prior_stakes[row] += stakes[i]
    return chosen


def _benqi_use(state: Mapping[str, Any], keys: np.ndarray, t: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """BENQI's prior-use set on the day's active validators: for each validator row, whether BENQI held a delegation
    on it open or scheduled in the 365 days before the decision, and its total delegated stake there; and the rows of
    the state's use records among the active validators."""
    rows = on_validators(keys, state["benqi_use_key"])
    in_window = state["benqi_use_until"] > t + 1 - WINDOW_DAYS
    prior_use = np.zeros(len(keys), dtype=bool)
    prior_stakes = np.zeros(len(keys), dtype=np.int64)
    on = (rows >= 0) & in_window
    prior_use[rows[on]] = True
    np.add.at(prior_stakes, rows[on], state["benqi_use_navax"][on])
    return prior_use, prior_stakes, rows


def _next_benqi_use(state: Mapping[str, Any], keys: np.ndarray, rows: np.ndarray, t: int, placed_keys: np.ndarray,
                    placed_stakes: np.ndarray, placed_days: np.ndarray, placed_benqi: np.ndarray, scheduled_keys: np.ndarray) -> dict:
    """The use records carried to the next state: those on a validator still active or scheduled, plus today's BENQI
    placements, one record per validator key."""
    keep = (rows >= 0) | np.isin(state["benqi_use_key"], scheduled_keys)
    all_keys = np.concatenate([state["benqi_use_key"][keep], placed_keys[placed_benqi]])
    all_navax = np.concatenate([state["benqi_use_navax"][keep], placed_stakes[placed_benqi]])
    all_until = np.concatenate([state["benqi_use_until"][keep], t + placed_days[placed_benqi]])
    unique, inverse = np.unique(all_keys, return_inverse=True)
    navax = np.zeros(len(unique), dtype=np.int64)
    np.add.at(navax, inverse, all_navax)
    until = np.full(len(unique), np.iinfo(np.int64).min, dtype=np.int64)
    np.maximum.at(until, inverse, all_until)
    return {"benqi_use_key": unique, "benqi_use_navax": navax, "benqi_use_until": until}


def delegations_stage(state: Mapping[str, Any], day: Day, earlier: Mapping[str, dict], *, setup: DelegationSetup) -> dict:
    """The daily delegations stage. Returns the assembly's next state with the delegations added, and issuance as the
    day's validator rewards plus its delegator rewards."""
    validators = earlier["assembly"]
    t, draw, flow = day.t, day.draw, setup.flow

    # Open delegations age. One that reaches its end leaves before today's new ones are placed.
    days_left = state["delegation_days_left"] - 1
    stay = days_left > 0
    kept = {name: state[name][stay] for name in DELEGATION} | {"delegation_days_left": days_left[stay]}
    # Delegations accepted by the origin that start today become open.
    due = state["scheduled_start_day"] == t + 1
    starting = {
        "delegation_stakes": state["scheduled_stakes"][due], "delegation_days_left": state["scheduled_days"][due],
        "delegation_days": state["scheduled_days"][due], "delegation_validator": state["scheduled_validator"][due],
        "delegation_benqi": state["scheduled_benqi"][due], "delegation_rewards": np.zeros(int(due.sum()), dtype=np.int64),
        "delegation_operator": state["scheduled_operator"][due],
    }
    waiting = {name: state[name][~due] for name in SCHEDULED}

    keys, stakes, validator_days = validators["node_key"], validators["stakes"], validators["days_left"]
    n_validators = len(keys)
    room = (limits(stakes, day.start, setup.multiplier) - stakes
            - stake_on(n_validators, on_validators(keys, kept["delegation_validator"]), kept["delegation_stakes"])
            - stake_on(n_validators, on_validators(keys, starting["delegation_validator"]), starting["delegation_stakes"])
            - stake_on(n_validators, on_validators(keys, waiting["scheduled_validator"]), waiting["scheduled_stakes"]))

    n = flow.count_from_uniform(float(draw.uniforms("delegations", t)[0]))
    index = np.arange(n)
    is_benqi = flow.benqi_from_uniforms(draw.uniforms("delegation_benqi", t, index))
    u_terms = draw.uniforms("delegation_terms", t, index)
    new_stakes = np.zeros(n, dtype=np.int64)
    new_days = np.zeros(n, dtype=np.int64)
    owner = np.full(n, -1, dtype=np.int64)
    for kind in (False, True):
        mine = is_benqi == kind
        if mine.any():
            term_stakes, term_days, term_owners = setup.terms[kind]
            pick = np.minimum((u_terms[mine] * len(term_stakes)).astype(np.int64), len(term_stakes) - 1)
            new_stakes[mine], new_days[mine] = term_stakes[pick], term_days[pick]
            drawn = term_owners[pick]
            owner[mine] = setup.benqi_operator if kind else np.where(drawn == setup.benqi_operator, -1, drawn)
    # From its closing day, a named operator makes none of the new delegations it would own.
    if len(setup.closes_days) and (owner >= 0).any():
        made = ~((owner >= 0) & (setup.closes_days[np.maximum(owner, 0)] <= t + 1))
        index, is_benqi, new_stakes, new_days, owner = index[made], is_benqi[made], new_stakes[made], new_days[made], owner[made]
    u_choice, u_benqi = draw.uniforms("delegator_choice", t, index), draw.uniforms("benqi_allocation", t, index)
    use = {name: state[name] for name in BENQI_USE}
    if setup.rule == "containment":
        horizon = int(max(1, validator_days.max(initial=0), new_days.max(initial=0), state["scheduled_start_day"].max(initial=0) - t)) + 1
        covering = (
            (on_validators(keys, kept["delegation_validator"]), np.zeros(len(kept["delegation_stakes"]), dtype=np.int64),
             kept["delegation_days_left"], kept["delegation_stakes"]),
            (on_validators(keys, starting["delegation_validator"]), np.zeros(len(starting["delegation_stakes"]), dtype=np.int64),
             starting["delegation_days_left"], starting["delegation_stakes"]),
            (on_validators(keys, waiting["scheduled_validator"]), waiting["scheduled_start_day"] - (t + 1),
             waiting["scheduled_start_day"] - (t + 1) + waiting["scheduled_days"], waiting["scheduled_stakes"]),
        )
        load = sum(load_profile(n_validators, horizon, *part) for part in covering)
        prior_use, prior_stakes, use_rows = _benqi_use(state, keys, t)
        chosen = place_contained(new_stakes, new_days, is_benqi, u_choice, u_benqi, load, limits(stakes, day.start, setup.multiplier) - stakes,
                                 validator_days, stakes, prior_use, prior_stakes, setup)
        order = np.flatnonzero(chosen >= 0)
        rows = chosen[order]
        placed_stakes, placed_days = new_stakes[order], new_days[order]
        use = _next_benqi_use(state, keys, use_rows, t, keys[rows], placed_stakes, placed_days, is_benqi[order],
                              day.settings.scheduled["node_key"][day.settings.scheduled["start_day"] > t + 1])
    else:
        order, chosen = place(new_stakes, is_benqi, u_choice, u_benqi, room, validator_days >= MIN_DELEGATION_DAYS,
                              np.isin(keys, setup.benqi_keys), setup)
        rows = chosen[order]
        placed_stakes = new_stakes[order]
        placed_days = np.minimum(new_days[order], validator_days[rows])

    validator_issued = int(validators["issued_navax"])
    opening = int(state["supply_navax"]) + validator_issued
    supply = opening
    mechanism = day.settings.mechanism
    rewards = np.zeros(len(order), dtype=np.int64)
    for i, (stake, d) in enumerate(zip(placed_stakes.tolist(), placed_days.tolist())):
        rewards[i] = mechanism.potential_reward_navax(stake, d * SECONDS_PER_DAY, supply, day.start, 0)
        supply += int(rewards[i])

    new = {
        "delegation_stakes": placed_stakes, "delegation_days_left": placed_days, "delegation_days": placed_days,
        "delegation_validator": keys[rows], "delegation_benqi": is_benqi[order], "delegation_rewards": rewards,
        "delegation_operator": owner[order],
    }
    out = {name: np.concatenate([kept[name], starting[name], new[name]]) for name in DELEGATION}
    return {
        **validators, **out, **waiting, **use,
        "validator_issued_navax": validator_issued,
        "delegator_issued_navax": supply - opening,
        "issued_navax": validator_issued + supply - opening,
        "unplaced_delegations": int((chosen < 0).sum()),
    }
