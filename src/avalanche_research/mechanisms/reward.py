"""Reward mechanisms as Param classes.

The chain pays a stake its potential reward, AvalancheGo's ``Calculate``:

    reward = remaining supply * (stake / current supply) * rate(d) * (d / T)

where ``d`` is the staking duration, ``T`` the one-year minting period, and ``rate(d)`` the consumption rate,
linear in ``d`` from the minimum to the maximum rate. ACP-285 lowers the minimum rate over a 90-day ramp
from Helicon, keyed to each stake's start time.

Every mechanism here keeps that formula and its integer operation order, and changes one thing: the rate
configuration at a stake's start, the shape of ``rate(d)``, or a multiplier on the result. Each offers:

- ``potential_reward_navax``: the rule for one stake, in nAVAX.
- ``curve``: annual rate by duration, a table ready to plot.
- ``issuance_navax``: what the rule mints for a set of stakes, the cost every comparison scores.
- ``check``: the properties the rule must keep, returned as a list of failures.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

import pandas as pd
import param

from avalanche_research.model.protocol import (
    ACP285_RAMP_SECONDS,
    ACP285_TARGET_MIN_CONSUMPTION_RATE,
    MAINNET_REWARD,
    MAINNET_UPGRADES,
    reward_config_for_stake_start,
)
from avalanche_research.model.types import (
    NANOSECONDS_PER_SECOND,
    PERCENT_DENOMINATOR,
    SECONDS_PER_DAY,
    RewardConfig,
    as_utc,
)

AVAX = 10**9
CURVE_STAKE_NAVAX = 10**6 * AVAX
DEFAULT_DURATIONS_DAYS = (2, 7, 14, 21, 30, 60, 90, 120, 180, 270, 365)
STAKE_COLUMNS = ("stake_navax", "duration_seconds", "start")


class RewardMechanism(param.Parameterized):
    """The potential reward of one stake. The base class is the chain's rule."""

    label = param.String(default="Chain today", doc="Name shown in tables and legends")

    def config(self, start: datetime) -> RewardConfig:
        """The rate configuration a stake starting at ``start`` is priced with."""
        return reward_config_for_stake_start(start, MAINNET_REWARD, MAINNET_UPGRADES)

    def numerator(self, config: RewardConfig, duration_ns: int) -> int:
        """rate(d) * T in millionths times nanoseconds, the chain's linear rate."""
        return (config.max_consumption_rate - config.min_consumption_rate) * duration_ns + (
            config.min_consumption_rate * config.minting_period_nanoseconds
        )

    def multiplier(self, completed_periods: int) -> float:
        """A factor applied to the reward. One for the chain."""
        return 1.0

    def potential_reward_navax(
        self, stake_navax: int, duration_seconds: int, supply_navax: int, start: datetime, completed_periods: int = 0
    ) -> int:
        config = self.config(start)
        if supply_navax <= 0 or supply_navax > config.supply_cap_navax or stake_navax < 0 or duration_seconds < 0:
            raise ValueError("stake and duration must be non-negative and supply within (0, cap]")
        duration_ns = duration_seconds * NANOSECONDS_PER_SECOND
        period_ns = config.minting_period_nanoseconds
        remaining = config.supply_cap_navax - supply_navax
        reward = remaining * self.numerator(config, duration_ns) * stake_navax * duration_ns
        reward //= period_ns * PERCENT_DENOMINATOR
        reward //= supply_navax
        reward //= period_ns
        if reward >= 2**64:
            reward = remaining
        factor = self.multiplier(completed_periods)
        if factor != 1.0:
            reward = int(reward * factor)
        return min(remaining, reward)

    def annual_rate(self, duration_days: float, supply_navax: int, start: datetime, completed_periods: int = 0) -> float:
        """Reward per AVAX staked, annualized over the duration."""
        seconds = int(duration_days * SECONDS_PER_DAY)
        reward = self.potential_reward_navax(CURVE_STAKE_NAVAX, seconds, supply_navax, start, completed_periods)
        return reward / CURVE_STAKE_NAVAX * (365 * SECONDS_PER_DAY) / seconds

    def curve(
        self,
        supply_navax: int,
        start: datetime,
        durations_days: Iterable[float] = DEFAULT_DURATIONS_DAYS,
        completed_periods: int = 0,
    ) -> pd.DataFrame:
        """Annual rate by staking duration, for one supply and start time."""
        rows = [
            {"mechanism": self.label, "duration_days": days, "annual_rate": self.annual_rate(days, supply_navax, start, completed_periods)}
            for days in durations_days
        ]
        return pd.DataFrame(rows)

    def issuance_navax(self, stakes: pd.DataFrame, supply_navax: int) -> int:
        """What the rule mints for a set of stakes at one supply.

        ``stakes`` needs ``stake_navax``, ``duration_seconds``, and ``start``, and may carry ``completed_periods``.
        """
        missing = set(STAKE_COLUMNS) - set(stakes.columns)
        if missing:
            raise ValueError(f"stakes table lacks {sorted(missing)}")
        periods = stakes["completed_periods"] if "completed_periods" in stakes else pd.Series(0, index=stakes.index)
        return sum(
            self.potential_reward_navax(int(row.stake_navax), int(row.duration_seconds), supply_navax, row.start, int(n))
            for row, n in zip(stakes.itertuples(index=False), periods)
        )

    def check(self, supply_navax: int, start: datetime) -> list[str]:
        """Failures of the properties every reward rule must keep."""
        failures = []
        rates = self.curve(supply_navax, start)["annual_rate"].tolist()
        if any(later < earlier - 1e-12 for earlier, later in zip(rates, rates[1:])):
            failures.append("annual rate falls as duration rises")
        if any(rate < 0 for rate in rates):
            failures.append("negative rate")
        remaining = self.config(start).supply_cap_navax - supply_navax
        if self.potential_reward_navax(remaining * 10, 365 * SECONDS_PER_DAY, supply_navax, start) > remaining:
            failures.append("reward exceeds the remaining supply")
        return failures


class ChainReward(RewardMechanism):
    """Mainnet as it runs: the linear rate, with ACP-285 applied at each stake's start since Helicon."""


class ACP285Ramp(RewardMechanism):
    """ACP-285's ramp with its target and length as settings. The defaults are the chain since Helicon."""

    label = param.String(default="ACP-285 settings")
    target_min_rate = param.Number(
        default=ACP285_TARGET_MIN_CONSUMPTION_RATE / PERCENT_DENOMINATOR,
        bounds=(0.0, MAINNET_REWARD.max_consumption_rate / PERCENT_DENOMINATOR),
        step=0.0025,
        doc="Minimum consumption rate the ramp reaches, as a fraction. Mainnet: 0.075",
    )
    ramp_days = param.Integer(default=ACP285_RAMP_SECONDS // SECONDS_PER_DAY, bounds=(1, 730), doc="Days from Helicon to the target. Mainnet: 90")

    def config(self, start: datetime) -> RewardConfig:
        base = MAINNET_REWARD
        target = round(self.target_min_rate * PERCENT_DENOMINATOR)
        at = as_utc(start)
        if not MAINNET_UPGRADES.activated("helicon", at) or base.min_consumption_rate == target:
            return base
        full = abs(base.min_consumption_rate - target)
        elapsed_ns = int((at - MAINNET_UPGRADES.time("helicon")).total_seconds()) * NANOSECONDS_PER_SECOND
        ramp_ns = self.ramp_days * SECONDS_PER_DAY * NANOSECONDS_PER_SECOND
        change = full * elapsed_ns // ramp_ns if elapsed_ns < ramp_ns else full
        minimum = base.min_consumption_rate + change if base.min_consumption_rate < target else base.min_consumption_rate - change
        return RewardConfig(base.max_consumption_rate, minimum, base.minting_period_seconds, base.supply_cap_navax)


class TenureBoost(RewardMechanism):
    """A reward that rises with a validator's tenure, Eric's written research question of 2026-05-07.

    Tenure is counted as the node's completed validation periods before this one. Eric has not yet said
    whether tenure means span, days staked, or the current streak, so the count is a declared choice.
    """

    label = param.String(default="Tenure boost")
    boost_max = param.Number(default=0.10, bounds=(0.0, 1.0), step=0.01, doc="Extra reward at full tenure, as a fraction of the chain's reward")
    full_boost_periods = param.Integer(default=8, bounds=(1, 100), doc="Completed periods at which the boost is full")

    def multiplier(self, completed_periods: int) -> float:
        return 1.0 + self.boost_max * min(max(completed_periods, 0), self.full_boost_periods) / self.full_boost_periods


class QuadraticReward(RewardMechanism):
    """A rate convex in duration: rate(d) = min + (max - min) * (d / T) ** exponent.

    Exponent 1 is the chain's linear rate. A larger exponent pays less for short stakes and the same at one
    year. ``scale`` multiplies the result, and ``at_equal_issuance`` sets it so a set of stakes mints what
    the chain mints, which separates the effect of the curve's shape from the effect of paying more.
    """

    label = param.String(default="Quadratic curve")
    exponent = param.Number(default=2.0, bounds=(1.0, 4.0), step=0.25, doc="Curvature of the rate in duration. 1 is the chain")
    scale = param.Number(default=1.0, bounds=(0.0, 10.0), doc="Multiplier on the reward. 1 as designed")

    def numerator(self, config: RewardConfig, duration_ns: int) -> int:
        if self.exponent == 1.0:
            return super().numerator(config, duration_ns)
        period_ns = config.minting_period_nanoseconds
        span = config.max_consumption_rate - config.min_consumption_rate
        shaped = round(span * period_ns * (duration_ns / period_ns) ** self.exponent)
        return shaped + config.min_consumption_rate * period_ns

    def multiplier(self, completed_periods: int) -> float:
        return self.scale

    def at_equal_issuance(self, stakes: pd.DataFrame, supply_navax: int) -> QuadraticReward:
        """A copy scaled so these stakes mint what the chain mints for them."""
        chain = ChainReward().issuance_navax(stakes, supply_navax)
        designed = QuadraticReward(exponent=self.exponent).issuance_navax(stakes, supply_navax)
        return QuadraticReward(exponent=self.exponent, scale=chain / designed if designed else 1.0, label=f"{self.label}, equal issuance")
