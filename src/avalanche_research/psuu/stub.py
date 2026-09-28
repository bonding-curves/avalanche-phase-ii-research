"""A stand-in engine with the signature and columns of ``sim.engine.run``, for testing the sweep machinery.

Its dynamics are invented and uncalibrated. They respond to the swept parameters, price, and external yield in the
intended direction so the reductions have signal to find. No result from this engine is a finding.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from .mechanisms import consumption_rate

COLUMNS = (
    "day", "date", "supply_avax", "validator_stake_avax", "delegated_stake_avax", "staking_ratio", "validator_count",
    "rewards_paid_avax", "reward_apr", "hhi", "net_inflation_annual", "validator_profit_usd_month",
)

# Synthetic start near the observed 2025-01-01 ledger (avax_monetary_daily): supply 441.3M, validator stake 159.4M,
# delegated stake 32.4M, 1,422 validators. The HHI is a placeholder.
SYNTHETIC_START = {
    "supply_avax": 441_323_311.7,
    "validator_stake_avax": 159_444_978.7,
    "delegated_stake_avax": 32_356_327.3,
    "validator_count": 1422,
    "hhi": 0.004,
}


@dataclass(frozen=True)
class Params:
    """Stand-in for ``sim.params.Params`` with the same fields and defaults. ``behaviour`` is unused here."""

    min_consumption_rate: float = 0.10
    max_consumption_rate: float = 0.12
    min_stake_days: int = 14
    max_stake_days: int = 365
    supply_cap_avax: float = 720_000_000
    min_validator_stake_avax: float = 2000
    min_delegation_fee: float = 0.02
    max_weight_factor: int = 5
    max_validator_stake_avax: float = 3_000_000
    mechanism: str = "linear"
    mechanism_args: tuple = ()
    operating_cost_usd_month: float = 0.0
    behaviour: Any = None


@dataclass
class Scenario:
    """Stand-in for ``sim.scenario.Scenario``."""

    name: str
    price_usd: np.ndarray
    external_yield: np.ndarray
    start_date: str = "2025-01-01"


def _start(initial_state: Any) -> dict[str, float]:
    if initial_state is None:
        return dict(SYNTHETIC_START)
    get = initial_state.get if isinstance(initial_state, Mapping) else lambda key, default=None: getattr(initial_state, key, default)
    return {key: float(get(key, default)) for key, default in SYNTHETIC_START.items()}


def run(params: Any, scenario: Any, seed: int, days: int, initial_state: Any = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = _start(initial_state)
    supply = start["supply_avax"]
    count = start["validator_count"]
    stake_per_validator = start["validator_stake_avax"] / count
    delegated = start["delegated_stake_avax"]
    hhi0, count0 = start["hhi"], count
    duration = 0.5 * (params.min_stake_days + params.max_stake_days)
    fee = params.min_delegation_fee + 0.03
    first = date.fromisoformat(scenario.start_date)
    rows = []
    for day in range(days):
        validator_stake = count * stake_per_validator
        staked = validator_stake + delegated
        ratio = staked / supply
        rate = float(consumption_rate(duration, params, {"staking_ratio": ratio, "node_age_days": 365.0}))
        apr = (params.supply_cap_avax - supply) / supply * rate
        rewards = apr / 365 * staked
        burn = 0.001 / 365 * supply
        supply = min(supply + rewards - burn, params.supply_cap_avax)
        spread = apr - float(scenario.external_yield[day])
        price = float(scenario.price_usd[day])
        income_avax = (validator_stake + delegated * fee) * apr / 365 * 30 / count
        profit = income_avax * price - params.operating_cost_usd_month
        unstaked = supply - staked
        delegated = max(delegated + 0.02 * np.tanh(10 * spread) * unstaked / 7 + rng.normal(0, 0.001 * delegated), 0.0)
        delegated = min(delegated, validator_stake * (params.max_weight_factor - 1))
        entries = rng.poisson(max(1.0 + 3.0 * np.tanh(profit / 1000.0), 0.0))
        renewal = 0.8 + 0.1 * np.tanh(10 * spread)
        exits = rng.poisson(count / duration * (1 - renewal) * (14 / params.min_stake_days) ** 0.25)
        count = max(count + entries - exits, 1)
        stake_per_validator *= float(np.exp(rng.normal(0, 0.002)))
        hhi = hhi0 * count0 / count * float(np.exp(rng.normal(0, 0.01)))
        rows.append((
            day, first + timedelta(days=day), supply, count * stake_per_validator, delegated,
            (count * stake_per_validator + delegated) / supply, count, rewards, apr, hhi,
            (rewards - burn) / supply * 365, profit,
        ))
    return pd.DataFrame(rows, columns=list(COLUMNS))
