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
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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
DELEGATION = ("delegation_stakes", "delegation_days_left", "delegation_days", "delegation_validator", "delegation_benqi", "delegation_rewards")
SCHEDULED = ("scheduled_stakes", "scheduled_start_day", "scheduled_days", "scheduled_validator", "scheduled_benqi")


@dataclass(frozen=True, eq=False)
class DelegationSetup:
    """What the delegations stage reads besides the state and the day: the three blocks, every validator's fee in
    millionths, the delegation multiplier, the node keys of BENQI's validators, the terms new delegations draw from,
    BENQI's and the others', and the placement batch size."""

    flow: DelegationFlow
    choice: DelegatorChoice
    allocation: BenqiAllocation
    fee_shares: int
    multiplier: int
    benqi_keys: np.ndarray
    terms: Mapping[bool, tuple[np.ndarray, np.ndarray]]
    batch: int


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
    for kind in (False, True):
        mine = is_benqi == kind
        if mine.any():
            term_stakes, term_days = setup.terms[kind]
            pick = np.minimum((u_terms[mine] * len(term_stakes)).astype(np.int64), len(term_stakes) - 1)
            new_stakes[mine], new_days[mine] = term_stakes[pick], term_days[pick]
    order, chosen = place(new_stakes, is_benqi, draw.uniforms("delegator_choice", t, index), draw.uniforms("benqi_allocation", t, index),
                          room, validator_days >= MIN_DELEGATION_DAYS, np.isin(keys, setup.benqi_keys), setup)
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
    }
    out = {name: np.concatenate([kept[name], starting[name], new[name]]) for name in DELEGATION}
    return {
        **validators, **out, **waiting,
        "validator_issued_navax": validator_issued,
        "delegator_issued_navax": supply - opening,
        "issued_navax": validator_issued + supply - opening,
        "unplaced_delegations": int((chosen < 0).sum()),
    }
