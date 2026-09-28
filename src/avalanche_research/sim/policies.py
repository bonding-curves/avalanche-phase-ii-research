"""Policies: the reward mechanism registry and the behavioural decision rules the engine applies each day.

A reward mechanism maps stakes starting today to their potential rewards. The engine looks it up by
``Params.mechanism``. ``linear`` is the protocol's rule. Other modules (the sweep's ``psuu.mechanisms``) add
alternatives with ``register_mechanism`` and need no engine change.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..model.protocol import MAINNET_REWARD
from ..model.types import SECONDS_PER_DAY
from .behaviour import BehaviourParams

MINTING_PERIOD_DAYS = MAINNET_REWARD.minting_period_seconds / SECONDS_PER_DAY  # 365


@dataclass
class MechanismContext:
    """What a mechanism may read on the day it prices new stakes. The engine updates one instance in place.

    supply_counter_avax is the P-Chain supply counter the kernel reads. staking_ratio and validator_count are the
    opening values of the day. role is ``validator`` or ``delegator``.
    """

    params: Any
    day: int = 0
    supply_counter_avax: float = 0.0
    supply_avax: float = 0.0
    staking_ratio: float = 0.0
    validator_count: float = 0.0
    external_yield: float = 0.0
    price_usd: float = 0.0
    role: str = "validator"


Mechanism = Callable[[np.ndarray, np.ndarray, MechanismContext], np.ndarray]
REWARD_MECHANISMS: dict[str, Mechanism] = {}


def register_mechanism(name: str, function: Mechanism | None = None) -> Any:
    """Register ``function(stake_avax, duration_days, context) -> potential_reward_avax`` under ``name``.

    Usable as a decorator. Arrays are float AVAX and days of equal shape. The engine caps the day's total at the
    remaining supply (cap minus counter), so a mechanism needs no cap of its own.
    """
    def decorate(item: Mechanism) -> Mechanism:
        REWARD_MECHANISMS[name] = item
        return item
    return decorate if function is None else decorate(function)


def get_mechanism(name: str) -> Mechanism:
    try:
        return REWARD_MECHANISMS[name]
    except KeyError:
        raise KeyError(f"unknown reward mechanism {name!r}; registered: {sorted(REWARD_MECHANISMS)}") from None


@register_mechanism("linear")
def linear(stake_avax: np.ndarray, duration_days: np.ndarray, context: MechanismContext) -> np.ndarray:
    """The protocol kernel (``model.protocol.potential_reward``) in floating point.

    reward = (cap - counter) * stake / counter * (Y_min + (Y_max - Y_min) * d / M) * d / M, M = 365 days,
    capped at the remaining supply. AvalancheGo v1.15.0 ``vms/platformvm/reward/calculator.go`` Calculate.
    """
    params = context.params
    remaining = params.supply_cap_avax - context.supply_counter_avax
    if remaining <= 0:
        return np.zeros_like(np.asarray(stake_avax, dtype=float))
    share = np.asarray(duration_days, dtype=float) / MINTING_PERIOD_DAYS
    rate = params.min_consumption_rate + (params.max_consumption_rate - params.min_consumption_rate) * share
    reward = remaining * (np.asarray(stake_avax, dtype=float) / context.supply_counter_avax) * rate * share
    return np.minimum(reward, remaining)


def effective_menu(behaviour: BehaviourParams, min_days: int, max_days: int) -> tuple[np.ndarray, np.ndarray]:
    """The duration menu clipped into [min_days, max_days]; entries that clip to the same day merge their probability."""
    merged: dict[int, float] = {}
    for day, probability in zip(behaviour.duration_menu_days, behaviour.duration_probabilities):
        clipped = int(min(max(day, min_days), max_days))
        merged[clipped] = merged.get(clipped, 0.0) + float(probability)
    menu = np.array(sorted(merged), dtype=np.int64)
    probabilities = np.array([merged[int(day)] for day in menu])
    return menu, probabilities / probabilities.sum()


def entry_rate(behaviour: BehaviourParams, spread: float) -> float:
    """Expected new validators per day: base * exp(elasticity * spread)."""
    return behaviour.entry_base_per_day * math.exp(behaviour.entry_spread_elasticity * spread)


def duration_probabilities(behaviour: BehaviourParams, menu_days: np.ndarray, base: np.ndarray, spread: float) -> np.ndarray:
    """Menu probabilities tilted toward longer durations when the spread is positive: p_k proportional to
    base_k * exp(elasticity * spread * d_k / 365)."""
    if behaviour.duration_spread_elasticity == 0.0:
        return base
    weights = base * np.exp(behaviour.duration_spread_elasticity * spread * menu_days / MINTING_PERIOD_DAYS)
    return weights / weights.sum()


def renewal_probability(behaviour: BehaviourParams, spread: float) -> float:
    """Probability that an expiring validator starts a new period: logit(p) = logit(p0) + elasticity * spread."""
    base = behaviour.renewal_probability
    if behaviour.renewal_spread_elasticity == 0.0 or base in (0.0, 1.0):
        return base
    logit = math.log(base / (1 - base)) + behaviour.renewal_spread_elasticity * spread
    return 1 / (1 + math.exp(-logit))


def delegation_flow(behaviour: BehaviourParams, spread: float, unstaked_avax: float) -> float:
    """Net delegated flow per day: weekly flow / unstaked supply = sensitivity * tanh(spread), divided by 7."""
    if behaviour.delegation_sensitivity == 0.0:
        return 0.0
    return behaviour.delegation_sensitivity * math.tanh(spread) * max(unstaked_avax, 0.0) / 7.0
