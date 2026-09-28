"""State updates on the engine's ring buffers. Each function changes the ring in place and returns what moved.

The ring holds the horizon arrays of ``state.State`` addressed by absolute day: the cohort that expires on day
``t`` sits in slot ``t % horizon``. A cohort starting on day ``t`` with duration ``d`` goes to slot
``(t + d) % horizon``, so it is active at the close of days t to t + d - 1 and pays on day t + d.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .state import State, menu_index


@dataclass
class Ring:
    menu_days: np.ndarray
    validator_stake: np.ndarray
    validator_count: np.ndarray
    validator_reward_due: np.ndarray
    validator_accrual: np.ndarray
    delegated_stake: np.ndarray
    delegated_reward_due: np.ndarray
    delegated_accrual: np.ndarray

    @property
    def horizon(self) -> int:
        return int(self.validator_reward_due.shape[0])


@dataclass
class Expired:
    validator_stake: np.ndarray
    validator_count: np.ndarray
    validator_reward_due: float
    delegated_stake: float
    delegated_reward_due: float
    validator_accrual: float
    delegated_accrual: float


def ring_from_state(state: State, menu_days: np.ndarray, horizon: int) -> Ring:
    """Copy a state into a ring of at least ``horizon`` slots, mapping its duration buckets to the nearest menu entry."""
    size = max(horizon, state.horizon)
    k = len(menu_days)
    ring = Ring(
        np.asarray(menu_days, dtype=np.int64), np.zeros((size, k)), np.zeros((size, k)), np.zeros(size), np.zeros(size),
        np.zeros(size), np.zeros(size), np.zeros(size),
    )
    n = state.horizon
    targets = menu_index(state.menu_days, menu_days)
    for source, target in enumerate(targets):
        ring.validator_stake[:n, target] += state.validator_stake[:, source]
        ring.validator_count[:n, target] += state.validator_count[:, source]
    for name in ("validator_reward_due", "validator_accrual", "delegated_stake", "delegated_reward_due", "delegated_accrual"):
        getattr(ring, name)[:n] = getattr(state, name)
    return ring


def expire(ring: Ring, slot: int) -> Expired:
    """Remove the cohorts that expire in ``slot`` and return them."""
    out = Expired(
        ring.validator_stake[slot].copy(), ring.validator_count[slot].copy(), float(ring.validator_reward_due[slot]),
        float(ring.delegated_stake[slot]), float(ring.delegated_reward_due[slot]),
        float(ring.validator_accrual[slot]), float(ring.delegated_accrual[slot]),
    )
    ring.validator_stake[slot] = 0.0
    ring.validator_count[slot] = 0.0
    ring.validator_reward_due[slot] = ring.delegated_stake[slot] = ring.delegated_reward_due[slot] = 0.0
    ring.validator_accrual[slot] = ring.delegated_accrual[slot] = 0.0
    return out


def start_validators(ring: Ring, day: int, stake: np.ndarray, count: np.ndarray, reward: np.ndarray) -> float:
    """Add one cohort per menu entry starting on ``day``; returns the day's added accrual (reward per day)."""
    slots = (day + ring.menu_days) % ring.horizon
    columns = np.arange(len(ring.menu_days))
    ring.validator_stake[slots, columns] += stake
    ring.validator_count[slots, columns] += count
    # Menu entries are distinct and shorter than the horizon, so the slots are distinct and += is safe.
    ring.validator_reward_due[slots] += reward
    accrual = reward / ring.menu_days
    ring.validator_accrual[slots] += accrual
    return float(accrual.sum())


def start_delegation(ring: Ring, day: int, stake: float, reward: float, duration: int) -> float:
    slot = (day + duration) % ring.horizon
    ring.delegated_stake[slot] += stake
    ring.delegated_reward_due[slot] += reward
    ring.delegated_accrual[slot] += reward / duration
    return reward / duration


def cell_capacity(ring: Ring, weight_factor: float, max_weight: float) -> np.ndarray:
    """Delegation room of each cohort: n * min(f * s / n, W) - s for n validators of mean self stake s / n."""
    return np.maximum(np.minimum(weight_factor * ring.validator_stake, max_weight * ring.validator_count) - ring.validator_stake, 0.0)


def shrink_delegations(ring: Ring, keep: float) -> tuple[float, float, float]:
    """Scale every open delegation by ``keep`` (capacity fell below committed delegated stake).

    In the protocol a delegation cannot outlast its validator, so these delegations end with the validators that
    left. Returns the stake removed, the reward due released for payment now, and the accrual removed.
    """
    removed_stake = float(ring.delegated_stake.sum()) * (1 - keep)
    removed_reward = float(ring.delegated_reward_due.sum()) * (1 - keep)
    removed_accrual = float(ring.delegated_accrual.sum()) * (1 - keep)
    ring.delegated_stake *= keep
    ring.delegated_reward_due *= keep
    ring.delegated_accrual *= keep
    return removed_stake, removed_reward, removed_accrual


def hhi(ring: Ring, delegated: float, capacity_cells: np.ndarray) -> float:
    """Herfindahl index of validator weight, with validators equal within a cohort and delegated stake allocated
    to cohorts in proportion to their delegation room. Understates concentration within cohorts."""
    capacity = capacity_cells.sum()
    weight = ring.validator_stake + (delegated * capacity_cells / capacity if capacity > 0 else 0.0)
    total = weight.sum()
    count = ring.validator_count
    mask = count > 0
    if total <= 0 or not mask.any():
        return 0.0
    return float((weight[mask] ** 2 / count[mask]).sum() / total**2)
