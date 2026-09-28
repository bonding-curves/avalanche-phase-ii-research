"""Reward curves C(t): the annual consumption rate a stake of a given duration earns.

Contract for engines. A mechanism is a function ``fn(duration_days, params, state) -> rate`` where

- ``duration_days`` is a float or numpy array of stake durations in days,
- ``params`` is any object with the ``sim.params.Params`` fields (``min_consumption_rate``,
  ``max_consumption_rate``, ``max_stake_days``, ``mechanism_args`` ...),
- ``state`` is a mapping of the current system state. Keys used by the built-in curves: ``staking_ratio``
  (staked AVAX over supply, a fraction) and ``node_age_days`` (validator age in days, scalar or array
  broadcastable with ``duration_days``),
- the result is the annual consumption rate as a fraction, broadcast to the shape of ``duration_days``.

The engine looks the function up with ``get(params.mechanism)`` or calls ``consumption_rate`` directly, and turns
the rate into a reward with the protocol's formula (``reward_avax``). Registering a new name with ``register``
needs no engine change.

``sim.policies`` keeps its own registry of reward functions ``fn(stake_avax, duration_days, context)``.
``install_into_sim`` wraps every curve here as such a function and registers it there, so ``sim.engine`` runs any
curve registered here without a change.

``linear`` is the protocol's curve, ``MinRate + (MaxRate - MinRate) * Duration / MintingPeriod``
(vms/platformvm/reward/calculator.go). The sweep identifies the minting period with ``max_stake_days`` so the
rate spans exactly min to max over the allowed durations. With mainnet parameters (365 days) this equals the
protocol, which ``tests/test_psuu.py`` checks against ``model.protocol.potential_reward``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import numpy as np

Mechanism = Callable[[Any, Any, Mapping[str, Any]], Any]
REGISTRY: dict[str, Mechanism] = {}
DAYS_PER_YEAR = 365

# Arguments used when a parameter set leaves mechanism_args empty. The sweep design uses these values.
DEFAULT_ARGS: dict[str, tuple] = {
    "linear": (),
    # (duration share, rate share) breakpoints: 60% of the rate range is reached at a quarter of the duration range.
    "piecewise": ((0.0, 0.0), (0.25, 0.6), (1.0, 1.0)),
    # (slope, lower ratio, upper ratio): the rate rises by slope per unit of staking ratio below the lower bound
    # and falls by slope per unit above the upper bound.
    "state_dependent": (0.5, 0.50, 0.60),
    # (bonus, full age in days): the rate is multiplied by 1 + bonus * min(age / full age, 1).
    "node_age": (0.10, 365.0),
}


class MechanismError(ValueError):
    """A reward curve is unknown, badly specified, or returned an invalid rate."""


def register(name: str, fn: Mechanism | None = None, *, replace: bool = False):
    """Add a reward curve to ``REGISTRY``. Usable as ``register("name", fn)`` or as a decorator."""

    def add(function: Mechanism) -> Mechanism:
        if not replace and name in REGISTRY and REGISTRY[name] is not function:
            raise MechanismError(f"mechanism already registered: {name}")
        REGISTRY[name] = function
        return function

    return add if fn is None else add(fn)


def get(name: str) -> Mechanism:
    try:
        return REGISTRY[name]
    except KeyError as error:
        raise MechanismError(f"unknown mechanism: {name}; registered: {sorted(REGISTRY)}") from error


def args_for(params: Any) -> tuple:
    args = tuple(getattr(params, "mechanism_args", ()) or ())
    return args if args else DEFAULT_ARGS.get(params.mechanism, ())


def consumption_rate(duration_days: Any, params: Any, state: Mapping[str, Any]) -> np.ndarray:
    """The registered curve for ``params.mechanism``, checked to be finite and within [0, 1]."""
    duration = np.asarray(duration_days, dtype=float)
    rate = np.broadcast_to(np.asarray(get(params.mechanism)(duration, params, state), dtype=float), duration.shape)
    if not np.all(np.isfinite(rate)) or np.any(rate < 0) or np.any(rate > 1):
        raise MechanismError(f"mechanism {params.mechanism} returned a rate outside [0, 1]")
    return rate


def reward_avax(stake_avax: Any, duration_days: Any, supply_avax: float, params: Any, state: Mapping[str, Any]) -> np.ndarray:
    """Protocol reward formula with the mechanism's rate, capped at the remaining supply.

    Reward = (SupplyCap - Supply) * (Stake / Supply) * C(t) * (t / 365).
    """
    remaining = params.supply_cap_avax - supply_avax
    if remaining < 0 or supply_avax <= 0:
        raise MechanismError("supply must be positive and not above the cap")
    stake = np.asarray(stake_avax, dtype=float)
    duration = np.asarray(duration_days, dtype=float)
    reward = remaining * stake / supply_avax * consumption_rate(duration, params, state) * duration / DAYS_PER_YEAR
    return np.minimum(reward, remaining)


def _duration_share(duration: np.ndarray, params: Any) -> np.ndarray:
    return np.clip(np.asarray(duration, dtype=float) / params.max_stake_days, 0.0, 1.0)


def linear(duration_days: Any, params: Any, state: Mapping[str, Any]) -> np.ndarray:
    span = params.max_consumption_rate - params.min_consumption_rate
    return params.min_consumption_rate + span * _duration_share(duration_days, params)


def piecewise(duration_days: Any, params: Any, state: Mapping[str, Any]) -> np.ndarray:
    points = args_for(params)
    xs = np.array([float(x) for x, _ in points])
    ys = np.array([float(y) for _, y in points])
    if len(xs) < 2 or np.any(np.diff(xs) <= 0) or xs[0] < 0 or xs[-1] > 1 or np.any((ys < 0) | (ys > 1)):
        raise MechanismError("piecewise needs at least two (duration share, rate share) points, shares in [0, 1], increasing")
    span = params.max_consumption_rate - params.min_consumption_rate
    return params.min_consumption_rate + span * np.interp(_duration_share(duration_days, params), xs, ys)


def state_dependent(duration_days: Any, params: Any, state: Mapping[str, Any]) -> np.ndarray:
    slope, lower, upper = (float(value) for value in args_for(params))
    ratio = float(state["staking_ratio"])
    adjustment = slope * max(lower - ratio, 0.0) - slope * max(ratio - upper, 0.0)
    return np.clip(linear(duration_days, params, state) + adjustment, 0.0, 1.0)


def node_age(duration_days: Any, params: Any, state: Mapping[str, Any]) -> np.ndarray:
    bonus, full_age = (float(value) for value in args_for(params))
    age = np.asarray(state.get("node_age_days", 0.0), dtype=float)
    return np.clip(linear(duration_days, params, state) * (1.0 + bonus * np.clip(age / full_age, 0.0, 1.0)), 0.0, 1.0)


def as_sim_reward(name: str) -> Callable[[Any, Any, Any], np.ndarray]:
    """Wrap curve ``name`` as a ``sim.policies`` reward function reading a ``MechanismContext``.

    The reward uses the context's P-Chain supply counter. The state passed to the curve is the context's
    ``staking_ratio`` and, when present, its ``node_age_days``. Without that attribute the age is zero.
    """

    def reward(stake_avax: Any, duration_days: Any, context: Any) -> np.ndarray:
        params = context.params
        stake = np.asarray(stake_avax, dtype=float)
        if params.supply_cap_avax - context.supply_counter_avax <= 0:
            return np.zeros_like(stake)
        state = {"staking_ratio": context.staking_ratio, "node_age_days": getattr(context, "node_age_days", 0.0)}
        rate = np.asarray(get(name)(np.asarray(duration_days, dtype=float), params, state), dtype=float)
        remaining = params.supply_cap_avax - context.supply_counter_avax
        reward_avax = remaining * stake / context.supply_counter_avax * rate * np.asarray(duration_days, dtype=float) / DAYS_PER_YEAR
        return np.minimum(reward_avax, remaining)

    return reward


def install_into_sim(names: tuple[str, ...] | None = None) -> tuple[str, ...]:
    """Register curves from ``REGISTRY`` (all by default) in ``sim.policies``, replacing same-named entries there."""
    from ..sim.policies import register_mechanism

    chosen = tuple(REGISTRY) if names is None else names
    for name in chosen:
        register_mechanism(name, as_sim_reward(name))
    return chosen


register("linear", linear)
register("piecewise", piecewise)
register("state_dependent", state_dependent)
register("node_age", node_age)
