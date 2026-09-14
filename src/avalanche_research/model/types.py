"""Typed units, parameters, upgrades, and mechanism descriptions for the Avalanche staking subsystem.

Units follow AvalancheGo: amounts in nAVAX integers, rates in millionths (PercentDenominator), durations in
seconds here and nanoseconds inside the reward arithmetic. Nothing in this module reads data or performs I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


NAVAX_PER_AVAX = 1_000_000_000
NANOSECONDS_PER_SECOND = 1_000_000_000
SECONDS_PER_DAY = 86_400
# vms/platformvm/reward/config.go: PercentDenominator = 1_000_000
PERCENT_DENOMINATOR = 1_000_000


class ModelError(ValueError):
    """A protocol rule was asked to evaluate an input outside its domain."""


@dataclass(frozen=True)
class RewardConfig:
    """Mirror of vms/platformvm/reward/config.go Config."""

    max_consumption_rate: int
    min_consumption_rate: int
    minting_period_seconds: int
    supply_cap_navax: int

    def __post_init__(self) -> None:
        if not 0 <= self.min_consumption_rate <= self.max_consumption_rate <= PERCENT_DENOMINATOR:
            raise ModelError("consumption rates must satisfy 0 <= min <= max <= PercentDenominator")
        if self.minting_period_seconds <= 0 or self.supply_cap_navax <= 0:
            raise ModelError("minting period and supply cap must be positive")

    @property
    def minting_period_nanoseconds(self) -> int:
        return self.minting_period_seconds * NANOSECONDS_PER_SECOND


@dataclass(frozen=True)
class StakingConfig:
    """Mirror of genesis/params.go StakingConfig."""

    uptime_requirement: float
    min_validator_stake_navax: int
    max_validator_stake_navax: int
    min_delegator_stake_navax: int
    min_delegation_fee_shares: int
    min_stake_duration_seconds: int
    max_stake_duration_seconds: int
    helicon_min_stake_duration_seconds: int
    reward: RewardConfig


@dataclass(frozen=True)
class Upgrade:
    name: str
    activated_at: datetime

    def __post_init__(self) -> None:
        if self.activated_at.tzinfo is None:
            raise ModelError(f"upgrade {self.name} needs a timezone-aware activation time")


@dataclass(frozen=True)
class UpgradeSchedule:
    """Ordered network upgrades. Activation is inclusive: an event at the activation instant is activated."""

    upgrades: tuple[Upgrade, ...]

    def __post_init__(self) -> None:
        times = [item.activated_at for item in self.upgrades]
        if times != sorted(times) or len({item.name for item in self.upgrades}) != len(self.upgrades):
            raise ModelError("upgrades must be unique and in activation order")

    def time(self, name: str) -> datetime:
        for item in self.upgrades:
            if item.name == name:
                return item.activated_at
        raise ModelError(f"unknown upgrade: {name}")

    def activated(self, name: str, at: datetime) -> bool:
        return as_utc(at) >= self.time(name)

    def regime(self, at: datetime) -> str:
        """Name of the latest activated upgrade at the instant, or ``genesis`` before the first."""
        current = "genesis"
        instant = as_utc(at)
        for item in self.upgrades:
            if instant >= item.activated_at:
                current = item.name
        return current


@dataclass(frozen=True)
class Mechanism:
    """One protocol rule, the upgrade that changes it, what its activation is keyed by, and its sources."""

    acp: str
    name: str
    upgrade: str | None
    keyed_by: str
    sources: tuple[str, ...]


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
