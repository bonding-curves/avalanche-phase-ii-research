"""Reward mechanisms as Param classes.

The chain pays a stake its potential reward, AvalancheGo's ``Calculate``:

    reward = remaining supply * (stake / current supply) * rate(d) * (d / T)

where ``d`` is the staking duration, ``T`` the one-year minting period, and ``rate(d)`` the consumption rate,
linear in ``d`` from the minimum to the maximum rate. ACP-285 lowers the minimum rate over a 90-day ramp
from Helicon, keyed to each stake's start time.

Every mechanism here keeps that formula and changes one thing: the rate configuration at a stake's start,
the shape of ``rate(d)``, or a multiplier on the result. The chain and ACP-285 rules keep the chain's
integer operation order exactly. The quadratic shape and the multipliers are computed in floating point
and rounded down to the nAVAX. Each offers:

- ``potential_reward_navax``: the rule for one stake, in nAVAX.
- ``curve``: annual rate by duration, a table ready to plot.
- ``issuance_navax``: what the rule mints for a set of stakes, the cost every comparison scores.
- ``check``: the properties the rule must keep, returned as a list of failures.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from itertools import pairwise

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

    def duration_bounds(self) -> tuple[int, int] | None:
        """The shortest and longest commitment, in whole days, that the rule admits, or None for the durations a model
        draws as they are. Only :class:`GovernanceReward` sets bounds."""
        return None

    def share_multiplier(self, staked_share: float | None) -> float:
        """A factor on the reward from the share of supply staked when the stake starts. One for the chain, whose rate
        does not read participation, and one for every rule when no share is given. Only
        :class:`StakeDependentReward` reads the share."""
        return 1.0

    def potential_reward_navax(
        self, stake_navax: int, duration_seconds: int, supply_navax: int, start: datetime, completed_periods: int = 0,
        staked_share: float | None = None,
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
        factor = self.multiplier(completed_periods) * self.share_multiplier(staked_share)
        if factor != 1.0:
            reward = int(reward * factor)
        return min(remaining, reward)

    def annual_rate(self, duration_days: float, supply_navax: int, start: datetime, completed_periods: int = 0,
                    staked_share: float | None = None) -> float:
        """Reward per AVAX staked, annualized over the duration."""
        seconds = int(duration_days * SECONDS_PER_DAY)
        reward = self.potential_reward_navax(CURVE_STAKE_NAVAX, seconds, supply_navax, start, completed_periods, staked_share)
        return reward / CURVE_STAKE_NAVAX * (365 * SECONDS_PER_DAY) / seconds

    def curve(
        self,
        supply_navax: int,
        start: datetime,
        durations_days: Iterable[float] = DEFAULT_DURATIONS_DAYS,
        completed_periods: int = 0,
        staked_share: float | None = None,
    ) -> pd.DataFrame:
        """Annual rate by staking duration, for one supply, start time and, for a rule that reads it, staked share."""
        rows = [
            {"mechanism": self.label, "duration_days": days,
             "annual_rate": self.annual_rate(days, supply_navax, start, completed_periods, staked_share)}
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
        """Failures of the properties every reward rule must keep: a rate that does not fall as duration
        rises, and is never negative. The cap on the remaining supply is enforced by the formula itself."""
        failures = []
        rates = self.curve(supply_navax, start)["annual_rate"].tolist()
        if any(later < earlier - 1e-12 for earlier, later in pairwise(rates)):
            failures.append("annual rate falls as duration rises")
        if any(rate < 0 for rate in rates):
            failures.append("negative rate")
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
    ramp_days = param.Integer(default=ACP285_RAMP_SECONDS // SECONDS_PER_DAY, bounds=(1, 730), doc="Days from activation to the target. Mainnet: 90")
    activation = param.Date(
        default=MAINNET_UPGRADES.time("helicon"),
        doc="When the ramp starts. Mainnet: Helicon, 2026-09-22 15:00 UTC. A scenario can start it at any origin",
    )

    def config(self, start: datetime) -> RewardConfig:
        base = MAINNET_REWARD
        target = round(self.target_min_rate * PERCENT_DENOMINATOR)
        at = as_utc(start)
        activation = self.activation
        if not isinstance(activation, datetime):
            activation = datetime.combine(activation, datetime.min.time())
        activation = as_utc(activation)
        if at < activation or base.min_consumption_rate == target:
            return base
        full = abs(base.min_consumption_rate - target)
        elapsed_ns = int((at - activation).total_seconds()) * NANOSECONDS_PER_SECOND
        ramp_ns = self.ramp_days * SECONDS_PER_DAY * NANOSECONDS_PER_SECOND
        change = full * elapsed_ns // ramp_ns if elapsed_ns < ramp_ns else full
        minimum = base.min_consumption_rate + change if base.min_consumption_rate < target else base.min_consumption_rate - change
        return RewardConfig(base.max_consumption_rate, minimum, base.minting_period_seconds, base.supply_cap_navax)


class TenureBoost(RewardMechanism):
    """A reward that rises with a validator's tenure, the Foundation's written research question of 2026-05-07.

    Tenure is counted as the node's completed validation periods before this one. The Foundation has not yet said
    whether tenure means span, days staked, or the current streak, so the count is a declared choice.
    """

    label = param.String(default="Tenure boost")
    boost_max = param.Number(default=0.10, bounds=(0.0, 1.0), step=0.01, doc="Extra reward at full tenure, as a fraction of the chain's reward")
    full_boost_periods = param.Integer(default=8, bounds=(1, 100), doc="Completed periods at which the boost is full")

    acp285 = param.Boolean(
        default=True,
        doc="Price stakes from Helicon with ACP-285's ramp, as the chain does. False holds the rule before ACP-285 for every stake",
    )

    def config(self, start: datetime) -> RewardConfig:
        return super().config(start) if self.acp285 else MAINNET_REWARD

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

    acp285 = param.Boolean(
        default=True,
        doc="Price stakes from Helicon with ACP-285's ramp, as the chain does. False holds the rule before ACP-285 for every stake",
    )

    def config(self, start: datetime) -> RewardConfig:
        return super().config(start) if self.acp285 else MAINNET_REWARD

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
        """A copy scaled so these stakes mint what the chain's linear rate mints for them under the same rule, keeping
        this curve's choice of ACP-285."""
        # The chain's linear rate under the same rule: exponent 1 with this curve's choice of ACP-285.
        chain = QuadraticReward(exponent=1.0, acp285=self.acp285).issuance_navax(stakes, supply_navax)
        designed = QuadraticReward(exponent=self.exponent, acp285=self.acp285).issuance_navax(stakes, supply_navax)
        return QuadraticReward(exponent=self.exponent, scale=chain / designed if designed else 1.0, acp285=self.acp285,
                               label=f"{self.label}, equal issuance")


class GovernanceReward(RewardMechanism):
    """The chain's linear rate with the four governance settings of the grant proposal: the minimum and maximum
    consumption rates (Y_min and Y_max as the protocol holds them) and the shortest and longest commitment (t_min and
    t_max).

    The rate is ``min + (max - min) * min(d, t_max) / t_max``, so it reaches the maximum at ``t_max``, as the proposal's
    C(t) does. With ``t_max`` at one year it is the chain's integer formula exactly, and at 10%, 12%, 14 and 365 days it
    is the rule before ACP-285. Every stake is priced with these rates whatever its start, so ACP-285 does not apply.
    A model that reads :meth:`duration_bounds` moves each new commitment's duration to the nearer bound before its stake
    is drawn.
    """

    label = param.String(default="Governance settings")
    min_rate = param.Number(default=0.10, bounds=(0.0, 1.0), doc="Minimum consumption rate, as a fraction. Before ACP-285: 0.10")
    max_rate = param.Number(default=0.12, bounds=(0.0, 1.0), doc="Maximum consumption rate, as a fraction. Mainnet: 0.12")
    min_days = param.Integer(default=14, bounds=(1, 365), doc="Shortest commitment, days. Mainnet: 14")
    max_days = param.Integer(default=365, bounds=(1, 365), doc="Longest commitment and the duration at which the rate is the maximum, days. Mainnet: 365")

    def __init__(self, **params):
        super().__init__(**params)
        if self.max_rate < self.min_rate:
            raise ValueError(f"the maximum rate {self.max_rate} is below the minimum {self.min_rate}")
        if self.max_days < self.min_days:
            raise ValueError(f"the longest commitment {self.max_days} days is shorter than the shortest {self.min_days}")

    def config(self, start: datetime) -> RewardConfig:
        base = MAINNET_REWARD
        return RewardConfig(round(self.max_rate * PERCENT_DENOMINATOR), round(self.min_rate * PERCENT_DENOMINATOR),
                            base.minting_period_seconds, base.supply_cap_navax)

    def numerator(self, config: RewardConfig, duration_ns: int) -> int:
        period_ns = config.minting_period_nanoseconds
        top_ns = self.max_days * SECONDS_PER_DAY * NANOSECONDS_PER_SECOND
        if top_ns == period_ns:
            return super().numerator(config, duration_ns)
        span = config.max_consumption_rate - config.min_consumption_rate
        return span * min(duration_ns, top_ns) * period_ns // top_ns + config.min_consumption_rate * period_ns

    def duration_bounds(self) -> tuple[int, int]:
        return self.min_days, self.max_days


class StakeDependentReward(RewardMechanism):
    """A rate that falls as the staked share of supply rises, on the chain's linear rate in duration.

    The reward is the chain's times ``(reference_share / staked_share) ** elasticity``, with the factor held within
    ``min_multiplier`` and ``max_multiplier``. At the reference share the rule pays the chain's rate whatever the
    elasticity, and at an elasticity of zero it is the chain's rule exactly at every share. An elasticity of 0.5 is
    the shape of Ethereum's issuance, which pays each unit of stake in proportion to one over the square root of the
    total stake. Polkadot's ideal staking rate pays the full rate up to an ideal share and a rate that falls past it,
    which this rule approximates with the reference share as the ideal and the elasticity as the fall. The staked
    share is the validator and delegated stake over the supply counter at the stake's start, as the model reads it
    each day. A rule asked for a reward without a share prices at its reference share.

    The rule reads the share only through the multiplier, so the chain's integer operation order holds up to it, and
    the product is rounded down to the nAVAX as the other multipliers are.
    """

    label = param.String(default="Stake-dependent rate")
    elasticity = param.Number(
        default=0.0, bounds=(0.0, 2.0), step=0.05,
        doc="How fast the rate falls as the staked share rises: the reward is scaled by (reference_share / staked_share) "
            "** elasticity. 0 is the chain's rule. 0.5 is Ethereum's one over the square root of stake",
    )
    reference_share = param.Number(
        default=0.44, bounds=(0.01, 1.0), step=0.01,
        doc="The staked share of supply at which the rule pays the chain's rate. About 0.44 on the chain in 2025",
    )
    min_multiplier = param.Number(default=0.25, bounds=(0.0, 1.0), doc="The lowest factor on the chain's reward, reached when much is staked")
    max_multiplier = param.Number(default=4.0, bounds=(1.0, 10.0), doc="The highest factor on the chain's reward, reached when little is staked")

    acp285 = param.Boolean(
        default=True,
        doc="Price stakes from Helicon with ACP-285's ramp, as the chain does. False holds the rule before ACP-285 for every stake",
    )

    def __init__(self, **params):
        super().__init__(**params)
        if self.max_multiplier < self.min_multiplier:
            raise ValueError(f"the highest factor {self.max_multiplier} is below the lowest {self.min_multiplier}")

    def config(self, start: datetime) -> RewardConfig:
        return super().config(start) if self.acp285 else MAINNET_REWARD

    def share_multiplier(self, staked_share: float | None) -> float:
        if self.elasticity == 0.0 or staked_share is None:
            return 1.0
        share = float(staked_share)
        if share != share or share < 0.0 or share > 1.0:
            raise ValueError(f"the staked share must be within [0, 1], not {staked_share}")
        if share == 0.0:
            return float(self.max_multiplier)
        return float(min(self.max_multiplier, max(self.min_multiplier, (self.reference_share / share) ** self.elasticity)))
