"""Governance parameters of the staking reward system, one frozen value object per parameter set.

Defaults are the Avalanche mainnet values (``model.protocol.MAINNET``, from AvalancheGo v1.15.0
``genesis/genesis_mainnet.go`` StakingConfig and ``vms/platformvm/reward/config.go``). The proposal's symbols map as
``t_min`` = min_stake_days, ``t_max`` = max_stake_days, ``Y_min`` = min_consumption_rate, ``Y_max`` =
max_consumption_rate, ``alpha_v`` = max_weight_factor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..model.protocol import MAINNET
from ..model.types import NAVAX_PER_AVAX, PERCENT_DENOMINATOR, SECONDS_PER_DAY
from .behaviour import BehaviourParams


@dataclass(frozen=True)
class Params:
    min_consumption_rate: float = MAINNET.reward.min_consumption_rate / PERCENT_DENOMINATOR  # 0.10
    max_consumption_rate: float = MAINNET.reward.max_consumption_rate / PERCENT_DENOMINATOR  # 0.12
    min_stake_days: int = MAINNET.min_stake_duration_seconds // SECONDS_PER_DAY  # 14
    max_stake_days: int = MAINNET.max_stake_duration_seconds // SECONDS_PER_DAY  # 365
    supply_cap_avax: float = MAINNET.reward.supply_cap_navax / NAVAX_PER_AVAX  # 720,000,000
    min_validator_stake_avax: float = MAINNET.min_validator_stake_navax / NAVAX_PER_AVAX  # 2,000
    min_delegation_fee: float = MAINNET.min_delegation_fee_shares / PERCENT_DENOMINATOR  # 0.02
    max_weight_factor: int = 5  # self stake plus delegations up to 5x self stake (DelegationMultiplier 4 plus 1)
    max_validator_stake_avax: float = MAINNET.max_validator_stake_navax / NAVAX_PER_AVAX  # 3,000,000 weight cap
    mechanism: str = "linear"
    mechanism_args: tuple = ()
    operating_cost_usd_month: float = 0.0
    behaviour: BehaviourParams = field(default_factory=BehaviourParams)

    def __post_init__(self) -> None:
        if not 0 <= self.min_consumption_rate <= self.max_consumption_rate <= 1:
            raise ValueError("consumption rates must satisfy 0 <= min <= max <= 1")
        if not 1 <= self.min_stake_days <= self.max_stake_days:
            raise ValueError("stake durations must satisfy 1 <= min <= max")
        if self.supply_cap_avax <= 0 or self.min_validator_stake_avax <= 0 or self.max_validator_stake_avax < self.min_validator_stake_avax:
            raise ValueError("supply cap and validator stake bounds must be positive and ordered")
        if self.max_weight_factor < 1 or not 0 <= self.min_delegation_fee <= 1 or self.operating_cost_usd_month < 0:
            raise ValueError("weight factor must be at least 1, the fee in [0, 1], and operating cost non-negative")
