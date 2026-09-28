"""Source-comparable calculations for published Avalanche economic research."""

from __future__ import annotations

from fractions import Fraction
from typing import Mapping

import numpy as np
import pandas as pd

from .model.protocol import potential_reward
from .model.types import ModelError, PERCENT_DENOMINATOR, RewardConfig, SECONDS_PER_DAY


def figure7_frame(
    scenarios: Mapping[str, RewardConfig],
    durations_seconds: Mapping[str, int],
    *,
    stake_navax: int,
    supply_navax: int,
) -> pd.DataFrame:
    """Compare Eric Lu's Figure 7 period-return formula with the integer protocol kernel.

    The published figure is an equation, not a numeric series. Every returned
    value is source-implied for the caller's declared fixture, not an observed
    staking return or a reproduction of the article's behavioral estimates.
    """
    if stake_navax <= 0 or supply_navax < stake_navax:
        raise ModelError("fixture needs positive stake no greater than current supply")

    rows = []
    for scenario, config in scenarios.items():
        if supply_navax > config.supply_cap_navax:
            raise ModelError("current supply exceeds the scenario supply cap")
        scarcity = Fraction(config.supply_cap_navax - supply_navax, supply_navax)
        minimum = Fraction(config.min_consumption_rate, PERCENT_DENOMINATOR)
        maximum = Fraction(config.max_consumption_rate, PERCENT_DENOMINATOR)
        for duration, seconds in durations_seconds.items():
            if not 0 < seconds <= config.minting_period_seconds:
                raise ModelError("duration must be within the minting period")
            duration_fraction = Fraction(seconds, config.minting_period_seconds)
            source_return = scarcity * (
                minimum * duration_fraction
                + (maximum - minimum) * duration_fraction**2
            )
            protocol_reward = potential_reward(stake_navax, seconds, supply_navax, config)
            rows.append({
                "scenario": scenario,
                "duration": duration,
                "minimum_rate_pct": float(minimum * 100),
                "duration_days": seconds / SECONDS_PER_DAY,
                "source_implied_return_pct": float(source_return * 100),
                "protocol_return_pct": protocol_reward / stake_navax * 100,
                "rounding_gap_navax": float(source_return * stake_navax - protocol_reward),
            })
    return pd.DataFrame.from_records(rows)


def figure8_observed_bins(
    commitments: pd.DataFrame, *, weeks_per_bin: int = 1
) -> pd.DataFrame:
    """Bin observed commitment durations by count and cumulative self-stake.

    The caller selects and validates the population. This is an empirical
    comparator for Figure 8, not the article's simulated distribution.
    Cumulative self-stake sums entries and is not concurrent network stake.
    """
    if weeks_per_bin <= 0:
        raise ModelError("weeks_per_bin must be positive")
    required = {"duration_weeks", "stake_avax"}
    if not required <= set(commitments):
        raise ModelError("commitments need duration_weeks and stake_avax")
    if commitments.empty:
        raise ModelError("commitments must not be empty")

    rows = commitments[["duration_weeks", "stake_avax"]].copy()
    if not np.isfinite(rows.to_numpy(dtype=float)).all() or rows.le(0).any().any():
        raise ModelError("durations and self-stakes must be finite and positive")

    last_edge = (int(rows.duration_weeks.max() // weeks_per_bin) + 1) * weeks_per_bin
    edges = range(0, last_edge + 1, weeks_per_bin)
    rows["duration_interval"] = pd.cut(rows.duration_weeks, edges, right=False)
    bins = rows.groupby("duration_interval", observed=False).agg(
        commitments=("stake_avax", "size"), self_stake_avax=("stake_avax", "sum")
    ).reset_index()
    bins["duration_week"] = bins.duration_interval.map(lambda interval: interval.mid).astype(float)
    bins["commitment_share_pct"] = 100 * bins.commitments / len(rows)
    bins["self_stake_share_pct"] = 100 * bins.self_stake_avax / rows.stake_avax.sum()
    bins["duration_interval"] = bins.duration_interval.astype(str)
    return bins
