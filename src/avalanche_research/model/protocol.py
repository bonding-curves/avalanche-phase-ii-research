"""Source-linked Avalanche Primary Network staking and reward rules.

Every rule cites the pinned ACP text (avalanche-foundation/ACPs at b80ea34682b419603f0241f114560dea5d61e03a)
and the AvalancheGo v1.15.0 code path (ava-labs/avalanchego at 70bd6d063b7343fd2cd8217200aaf77b57f19f68).
Integer arithmetic reproduces the Go big-integer operation order exactly, so results are consensus values,
not floating-point approximations.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

from .types import (
    NANOSECONDS_PER_SECOND, NAVAX_PER_AVAX, PERCENT_DENOMINATOR, SECONDS_PER_DAY, Mechanism, ModelError,
    RewardConfig, StakingConfig, Upgrade, UpgradeSchedule, as_utc,
)


ACPS = "https://github.com/avalanche-foundation/ACPs/blob/b80ea34682b419603f0241f114560dea5d61e03a/ACPs"
AVALANCHEGO = "https://github.com/ava-labs/avalanchego/blob/70bd6d063b7343fd2cd8217200aaf77b57f19f68"

# genesis/genesis_mainnet.go MainnetParams.StakingConfig
MAINNET_REWARD = RewardConfig(
    max_consumption_rate=120_000,
    min_consumption_rate=100_000,
    minting_period_seconds=365 * SECONDS_PER_DAY,
    supply_cap_navax=720_000_000 * NAVAX_PER_AVAX,
)
MAINNET = StakingConfig(
    uptime_requirement=0.8,
    min_validator_stake_navax=2_000 * NAVAX_PER_AVAX,
    max_validator_stake_navax=3_000_000 * NAVAX_PER_AVAX,
    min_delegator_stake_navax=25 * NAVAX_PER_AVAX,
    min_delegation_fee_shares=20_000,
    min_stake_duration_seconds=14 * SECONDS_PER_DAY,
    max_stake_duration_seconds=365 * SECONDS_PER_DAY,
    helicon_min_stake_duration_seconds=48 * 3_600,
    reward=MAINNET_REWARD,
)

# upgrade/upgrade.go Mainnet
MAINNET_UPGRADES = UpgradeSchedule((
    Upgrade("apricot_phase_1", datetime(2021, 3, 31, 14, tzinfo=timezone.utc)),
    Upgrade("apricot_phase_2", datetime(2021, 5, 10, 11, tzinfo=timezone.utc)),
    Upgrade("apricot_phase_3", datetime(2021, 8, 24, 14, tzinfo=timezone.utc)),
    Upgrade("apricot_phase_4", datetime(2021, 9, 22, 21, tzinfo=timezone.utc)),
    Upgrade("apricot_phase_5", datetime(2021, 12, 2, 18, tzinfo=timezone.utc)),
    Upgrade("apricot_phase_pre_6", datetime(2022, 9, 5, 1, 30, tzinfo=timezone.utc)),
    Upgrade("apricot_phase_6", datetime(2022, 9, 6, 20, tzinfo=timezone.utc)),
    Upgrade("apricot_phase_post_6", datetime(2022, 9, 7, 3, tzinfo=timezone.utc)),
    Upgrade("banff", datetime(2022, 10, 18, 16, tzinfo=timezone.utc)),
    Upgrade("cortina", datetime(2023, 4, 25, 15, tzinfo=timezone.utc)),
    Upgrade("durango", datetime(2024, 3, 6, 16, tzinfo=timezone.utc)),
    Upgrade("etna", datetime(2024, 12, 16, 17, tzinfo=timezone.utc)),
    Upgrade("fortuna", datetime(2025, 4, 8, 15, tzinfo=timezone.utc)),
    Upgrade("granite", datetime(2025, 11, 19, 16, tzinfo=timezone.utc)),
    Upgrade("helicon", datetime(2026, 9, 22, 15, tzinfo=timezone.utc)),
))

# ACP-285 and vms/platformvm/reward/calculator.go configForStakeStart
ACP285_TARGET_MIN_CONSUMPTION_RATE = 75_000
ACP285_RAMP_SECONDS = 90 * SECONDS_PER_DAY
# genesis/params.go ACP267UptimeRequirement
ACP267_UPTIME_REQUIREMENT = 0.9
# ACP-247 README: current DelegationMultiplier = 4, proposed 24 (not part of Helicon)
ACP247_CURRENT_DELEGATION_MULTIPLIER = 4
ACP247_PROPOSED_DELEGATION_MULTIPLIER = 24

MECHANISMS = (
    Mechanism(
        "protocol", "Primary Network staking reward", None, "stake duration, amount, and current supply",
        (f"{AVALANCHEGO}/vms/platformvm/reward/calculator.go", f"{AVALANCHEGO}/genesis/genesis_mainnet.go"),
    ),
    Mechanism(
        "ACP-285", "Minimum consumption rate 10% to 7.5% over a 90-day ramp", "helicon", "stake start time",
        (f"{ACPS}/285-reduce-minimum-consumption-rate/README.md", f"{AVALANCHEGO}/vms/platformvm/reward/calculator.go"),
    ),
    Mechanism(
        "ACP-273", "Minimum validator duration 14 days to 48 hours", "helicon", "chain time when the validator is added",
        (f"{ACPS}/273-reduce-minimum-staking-duration/README.md", f"{AVALANCHEGO}/genesis/genesis_mainnet.go",
         f"{AVALANCHEGO}/vms/platformvm/txs/executor/staker_tx_verification_helpers.go"),
    ),
    Mechanism(
        "ACP-267", "Uptime requirement 80% to 90%", "helicon", "validator start time",
        (f"{ACPS}/267-uptime-requirement-increase/README.md", f"{AVALANCHEGO}/genesis/params.go",
         f"{AVALANCHEGO}/vms/platformvm/block/executor/options.go"),
    ),
    Mechanism(
        "ACP-247", "Delegation multiplier 4 to 24", None, "not scheduled; proposal text only",
        (f"{ACPS}/247-delegation-multiplier-increase/README.md",),
    ),
)


def reward_config_for_stake_start(
    stake_start: datetime,
    config: RewardConfig = MAINNET_REWARD,
    upgrades: UpgradeSchedule = MAINNET_UPGRADES,
) -> RewardConfig:
    """ACP-285 ramp: vms/platformvm/reward/calculator.go configForStakeStart.

    Stakes starting before Helicon keep the genesis configuration. From activation the minimum consumption rate
    moves linearly toward 75,000 millionths over 90 days, evaluated once at the stake's start time, with the
    change truncated to an integer. Networks whose maximum is below the target keep their configuration.
    """
    start = as_utc(stake_start)
    if not upgrades.activated("helicon", start) or config.min_consumption_rate == ACP285_TARGET_MIN_CONSUMPTION_RATE:
        return config
    if config.max_consumption_rate < ACP285_TARGET_MIN_CONSUMPTION_RATE:
        return config
    full_change = abs(config.min_consumption_rate - ACP285_TARGET_MIN_CONSUMPTION_RATE)
    change = full_change
    elapsed_ns = int((start - upgrades.time("helicon")).total_seconds()) * NANOSECONDS_PER_SECOND
    ramp_ns = ACP285_RAMP_SECONDS * NANOSECONDS_PER_SECOND
    if elapsed_ns < ramp_ns:
        change = full_change * elapsed_ns // ramp_ns
    if config.min_consumption_rate < ACP285_TARGET_MIN_CONSUMPTION_RATE:
        minimum = config.min_consumption_rate + change
    else:
        minimum = config.min_consumption_rate - change
    return RewardConfig(config.max_consumption_rate, minimum, config.minting_period_seconds, config.supply_cap_navax)


def potential_reward(
    stake_navax: int,
    duration_seconds: int,
    current_supply_navax: int,
    config: RewardConfig = MAINNET_REWARD,
) -> int:
    """vms/platformvm/reward/calculator.go Calculate, with the Go big-integer operation order.

    Reward = RemainingSupply * (StakedAmount / CurrentSupply) * MintingRate * (Duration / MintingPeriod), where
    MintingRate = MinRate + (MaxRate - MinRate) * Duration / MintingPeriod. Durations are nanoseconds in Go, so
    the seconds given here are scaled before the arithmetic. The result is capped at the remaining supply.
    """
    if stake_navax < 0 or duration_seconds < 0 or current_supply_navax <= 0:
        raise ModelError("stake and duration must be non-negative and current supply positive")
    if current_supply_navax > config.supply_cap_navax:
        raise ModelError("current supply exceeds the supply cap")
    duration_ns = duration_seconds * NANOSECONDS_PER_SECOND
    minting_period_ns = config.minting_period_nanoseconds
    numerator = (config.max_consumption_rate - config.min_consumption_rate) * duration_ns
    numerator += config.min_consumption_rate * minting_period_ns
    denominator = minting_period_ns * PERCENT_DENOMINATOR
    remaining = config.supply_cap_navax - current_supply_navax
    reward = remaining * numerator * stake_navax * duration_ns
    reward //= denominator
    reward //= current_supply_navax
    reward //= minting_period_ns
    if reward >= 2**64:
        return remaining
    return min(remaining, reward)


def primary_network_reward(
    stake_start: datetime,
    duration_seconds: int,
    stake_navax: int,
    current_supply_navax: int,
    config: RewardConfig = MAINNET_REWARD,
    upgrades: UpgradeSchedule = MAINNET_UPGRADES,
) -> int:
    """vms/platformvm/reward/calculator.go primaryNetworkCalculator.Calculate: ACP-285 applied per stake start."""
    return potential_reward(stake_navax, duration_seconds, current_supply_navax, reward_config_for_stake_start(stake_start, config, upgrades))


def annualized_reward_rate(
    stake_start: datetime,
    duration_seconds: int,
    stake_navax: int,
    current_supply_navax: int,
    config: RewardConfig = MAINNET_REWARD,
    upgrades: UpgradeSchedule = MAINNET_UPGRADES,
) -> float:
    """Reward per unit staked, scaled to the minting period. Matches the ARR tables in ACP-285."""
    if stake_navax <= 0 or duration_seconds <= 0:
        raise ModelError("annualized rate needs a positive stake and duration")
    reward = primary_network_reward(stake_start, duration_seconds, stake_navax, current_supply_navax, config, upgrades)
    return reward / stake_navax * config.minting_period_seconds / duration_seconds


def split_reward(total_navax: int, shares: int) -> tuple[int, int]:
    """vms/platformvm/reward/calculator.go Split: (amount from shares, remainder).

    For a delegation reward, the first value is the validator's fee and the second the delegator's payout.
    """
    if not 0 <= shares <= PERCENT_DENOMINATOR or total_navax < 0:
        raise ModelError("shares must lie in [0, PercentDenominator] and the amount must be non-negative")
    remainder_shares = PERCENT_DENOMINATOR - shares
    remainder = remainder_shares * (total_navax // PERCENT_DENOMINATOR)
    optimistic = remainder_shares * total_navax
    if optimistic < 2**64:
        remainder = optimistic // PERCENT_DENOMINATOR
    return total_navax - remainder, remainder


def supply_after_stake_start(
    current_supply_navax: int,
    potential_reward_navax: int,
    config: RewardConfig = MAINNET_REWARD,
) -> int:
    """Current supply after a stake starts: the potential reward is added before it is earned.

    AvalancheGo 70bd6d0 adds it at every Primary Network stake start: vms/platformvm/txs/executor/
    standard_tx_executor.go L1533 (putStaker, from Durango) and L1382-L1409 (AddAutoRenewedValidatorTx),
    state_changes.go L196 (pending staker promotion before Durango), and proposal_tx_executor.go L915-L920 (each
    ACP-236 renewal). Calculate caps the reward at the remaining supply, so the counter never passes the cap.
    """
    if current_supply_navax <= 0 or potential_reward_navax < 0:
        raise ModelError("current supply must be positive and the potential reward non-negative")
    supply = current_supply_navax + potential_reward_navax
    if supply > config.supply_cap_navax:
        raise ModelError("current supply would exceed the supply cap")
    return supply


def supply_after_stake_end(current_supply_navax: int, potential_reward_navax: int, rewarded: bool) -> int:
    """Current supply after a stake ends: unchanged when rewarded, minus the potential reward when not.

    AvalancheGo 70bd6d0 vms/platformvm/txs/executor/proposal_tx_executor.go L505-L520 undoSupplyMintOnAbort, called
    for validators and delegators (L394) and for auto-renewed cycles (L454). The commit branch keeps the reward
    minted at the start. No other path lowers the counter: burned fees never reach it.
    """
    if current_supply_navax <= 0 or potential_reward_navax < 0:
        raise ModelError("current supply must be positive and the potential reward non-negative")
    if rewarded:
        return current_supply_navax
    if potential_reward_navax > current_supply_navax:
        raise ModelError("potential reward exceeds the current supply")
    return current_supply_navax - potential_reward_navax


def start_stake(
    stake_start: datetime,
    duration_seconds: int,
    stake_navax: int,
    current_supply_navax: int,
    config: RewardConfig = MAINNET_REWARD,
    upgrades: UpgradeSchedule = MAINNET_UPGRADES,
) -> tuple[int, int]:
    """(potential reward, current supply after the start) for one Primary Network stake.

    AvalancheGo 70bd6d0 vms/platformvm/txs/executor/standard_tx_executor.go L1508-L1533 putStaker: the reward is
    computed from the supply before the start and then added to it.
    """
    reward = primary_network_reward(stake_start, duration_seconds, stake_navax, current_supply_navax, config, upgrades)
    return reward, supply_after_stake_start(current_supply_navax, reward, config)


def start_stakes_in_order(
    stakes: Iterable[tuple[datetime, int, int]],
    current_supply_navax: int,
    config: RewardConfig = MAINNET_REWARD,
    upgrades: UpgradeSchedule = MAINNET_UPGRADES,
) -> tuple[tuple[int, ...], int]:
    """Potential rewards and the final current supply for stakes (start, duration seconds, amount) in event order.

    Each start reads the supply left by the previous one, so order changes every reward after the first
    (AvalancheGo 70bd6d0 vms/platformvm/txs/executor/state_changes_test.go L453-L530
    TestAdvanceTimeTo_PromotePendingDelegatorAndValidator_PreservesRewardOrder). The caller supplies the order.
    """
    rewards = []
    supply = current_supply_navax
    for stake_start, duration_seconds, stake_navax in stakes:
        reward, supply = start_stake(stake_start, duration_seconds, stake_navax, supply, config, upgrades)
        rewards.append(reward)
    return tuple(rewards), supply


STAKER_ROLES = ("validator", "delegator")


def min_stake_duration_seconds(
    at: datetime,
    config: StakingConfig = MAINNET,
    upgrades: UpgradeSchedule = MAINNET_UPGRADES,
    role: str = "validator",
) -> int:
    """Minimum Primary Network stake duration for a stake verified at chain time ``at``, by role.

    Validators follow ACP-273: 48 hours from Helicon, AvalancheGo 70bd6d0 vms/platformvm/txs/executor/
    staker_tx_verification_helpers.go L27-L32 primaryNetworkValidatorMinStakeDuration, also used for every
    ACP-236 period (staker_tx_verification.go L918-L920 and L1011). Delegators keep MinStakeDuration, 14 days,
    after Helicon: getDelegatorRules L79-L87.
    """
    if role not in STAKER_ROLES:
        raise ModelError(f"role must be one of {STAKER_ROLES}")
    if role == "validator" and upgrades.activated("helicon", at):
        return config.helicon_min_stake_duration_seconds
    return config.min_stake_duration_seconds


def delegation_within_validator_period(
    delegation_start: datetime,
    delegation_end: datetime,
    validator_start: datetime,
    validator_end: datetime,
) -> bool:
    """A delegation must lie inside its validator's current period, bounds included.

    AvalancheGo 70bd6d0 vms/platformvm/txs/validator.go L60-L62 BoundedBy, applied at staker_tx_verification.go
    L736-L743 (AddPermissionlessDelegatorTx) and L470-L477 (AddDelegatorTx). For an ACP-236 validator the period is
    the current cycle, so a delegation cannot span a renewal.
    """
    start, end = as_utc(delegation_start), as_utc(delegation_end)
    return start >= as_utc(validator_start) and end <= as_utc(validator_end) and end >= start


def delegation_window_open(
    delegation_start: datetime,
    validator_start: datetime,
    validator_end: datetime,
    config: StakingConfig = MAINNET,
    upgrades: UpgradeSchedule = MAINNET_UPGRADES,
) -> bool:
    """Whether a delegation of the minimum delegator duration starting at ``delegation_start`` fits the validator.

    Combines the delegator minimum (min_stake_duration_seconds, role ``delegator``) with BoundedBy. A validator
    with less than 14 days left, and any period or ACP-236 cycle shorter than 14 days, cannot take a new delegation.
    From Durango the delegation starts at the chain time of verification (staker_tx_verification.go L675-L681).
    """
    minimum = min_stake_duration_seconds(delegation_start, config, upgrades, role="delegator")
    earliest_end = as_utc(delegation_start) + timedelta(seconds=minimum)
    return delegation_within_validator_period(delegation_start, earliest_end, validator_start, validator_end)


def uptime_requirement(
    validator_start: datetime,
    config: StakingConfig = MAINNET,
    upgrades: UpgradeSchedule = MAINNET_UPGRADES,
) -> float:
    """ACP-267: 90% for validation periods starting at or after Helicon, else the genesis 80%."""
    if upgrades.activated("helicon", validator_start):
        return ACP267_UPTIME_REQUIREMENT
    return config.uptime_requirement


def uptime_fraction(up_seconds: int, since_validator_start_seconds: int) -> float:
    """Uptime as the node's up time over the time since its validator period started, 1 for an empty window.

    AvalancheGo 70bd6d0 snow/uptime/manager.go L176-L187 CalculateUptimePercentFrom, which divides the two
    durations as float64 nanosecond counts. The protocol keeps only the pass or fail result.
    """
    if up_seconds < 0 or since_validator_start_seconds < 0:
        raise ModelError("up time and window must be non-negative")
    if since_validator_start_seconds == 0:
        return 1.0
    return float(up_seconds * NANOSECONDS_PER_SECOND) / float(since_validator_start_seconds * NANOSECONDS_PER_SECOND)


def uptime_passes(
    uptime: float,
    validator_start: datetime,
    config: StakingConfig = MAINNET,
    upgrades: UpgradeSchedule = MAINNET_UPGRADES,
) -> bool:
    """Whether a stake ending now is rewarded: uptime at or above the requirement for the validator's start.

    AvalancheGo 70bd6d0 vms/platformvm/block/executor/options.go L146-L194 prefersCommit. A delegation is judged
    on its node's Primary Network validator: the validator's start time sets the threshold (80%, or 90% from
    Helicon under ACP-267) and its uptime from that start decides, whenever the delegation itself started.
    """
    return uptime >= uptime_requirement(validator_start, config, upgrades)


def validator_rewards_at_end(potential_reward_navax: int, delegatee_reward_navax: int, passed: bool) -> tuple[int, int]:
    """(validation reward paid, delegation fees paid) when a non-renewing validator ends.

    AvalancheGo 70bd6d0 vms/platformvm/txs/executor/proposal_tx_executor.go L522-L603 rewardValidatorTx. A failed
    uptime check forfeits the potential reward (and undoes its supply mint, supply_after_stake_end), but the
    deferred delegation fees in ``delegatee_reward_navax`` are paid on both branches because they were earned by
    delegations that already succeeded. The stake itself is returned on both branches.
    """
    if potential_reward_navax < 0 or delegatee_reward_navax < 0:
        raise ModelError("rewards must be non-negative")
    return (potential_reward_navax if passed else 0), delegatee_reward_navax


def delegator_rewards_at_end(potential_reward_navax: int, delegation_fee_shares: int, passed: bool) -> tuple[int, int]:
    """(delegator reward, validator fee) when a delegation ends, judged on its validator's uptime.

    AvalancheGo 70bd6d0 vms/platformvm/txs/executor/proposal_tx_executor.go L605-L661 rewardDelegatorTx: the
    commit branch splits the potential reward by the validator's delegation shares (split_reward). The abort branch
    pays neither, and the potential reward leaves the supply (L394). The fee is paid now or deferred (L667-L708).
    """
    if not passed:
        if potential_reward_navax < 0:
            raise ModelError("rewards must be non-negative")
        return 0, 0
    fee, delegator = split_reward(potential_reward_navax, delegation_fee_shares)
    return delegator, fee


def auto_renew_continues(passed: bool, next_period_seconds: int) -> bool:
    """Whether an ACP-236 validator starts another cycle at its cycle end.

    AvalancheGo 70bd6d0 vms/platformvm/txs/executor/proposal_tx_executor.go L414-L503 RewardAutoRenewedValidatorTx:
    a failed uptime check (abort) always removes the validator, and a next period of 0 is a graceful exit on commit.
    """
    if next_period_seconds < 0:
        raise ModelError("next period must be non-negative")
    return passed and next_period_seconds > 0


def auto_renew_exit_rewards(
    potential_reward_navax: int,
    delegatee_reward_navax: int,
    accrued_validation_rewards_navax: int,
    accrued_delegatee_rewards_navax: int,
    passed: bool,
) -> tuple[int, int]:
    """(validation rewards paid, delegatee rewards paid) when an ACP-236 validator leaves at a cycle end.

    AvalancheGo 70bd6d0 vms/platformvm/txs/executor/proposal_tx_executor.go L459-L503 and L712-L733. Rewards
    restaked in earlier cycles are paid out on either branch. A failed uptime check (forced exit) forfeits only the
    current cycle's potential reward. The original stake is returned on both branches.
    """
    values = (potential_reward_navax, delegatee_reward_navax, accrued_validation_rewards_navax, accrued_delegatee_rewards_navax)
    if min(values) < 0:
        raise ModelError("rewards must be non-negative")
    validation = accrued_validation_rewards_navax + (potential_reward_navax if passed else 0)
    return validation, delegatee_reward_navax + accrued_delegatee_rewards_navax


def auto_renew_restake(
    potential_reward_navax: int,
    delegatee_reward_navax: int,
    auto_compound_shares: int,
    weight_navax: int,
    config: StakingConfig = MAINNET,
) -> tuple[int, int, int, int]:
    """(restaked validation, restaked delegatee, withdrawn validation, withdrawn delegatee) at a renewal.

    AvalancheGo 70bd6d0 vms/platformvm/txs/executor/proposal_tx_executor.go L786-L888
    restakeAutoRenewedValidatorOnCommit. Each reward is split by the auto-compound shares (split_reward). If the
    restaked total would lift the weight above MaxValidatorStake, only the remaining capacity is restaked: the
    validation part is floor(V * C / T) (intmath.MulDiv) and the delegatee part takes the rest of the capacity.
    Everything not restaked is paid out. The new weight is the old weight plus both restaked parts.
    """
    if weight_navax > config.max_validator_stake_navax:
        raise ModelError("weight exceeds the maximum validator stake")
    validation, _ = split_reward(potential_reward_navax, auto_compound_shares)
    delegatee, _ = split_reward(delegatee_reward_navax, auto_compound_shares)
    capacity = config.max_validator_stake_navax - weight_navax
    total = validation + delegatee
    if total > capacity:
        validation = validation * capacity // total
        delegatee = capacity - validation
    return validation, delegatee, potential_reward_navax - validation, delegatee_reward_navax - delegatee


def auto_renew_next_cycle(
    previous_end: datetime,
    next_period_seconds: int,
    weight_navax: int,
    current_supply_navax: int,
    config: RewardConfig = MAINNET_REWARD,
    upgrades: UpgradeSchedule = MAINNET_UPGRADES,
) -> tuple[datetime, int, int]:
    """(cycle end, potential reward, current supply after) for the next ACP-236 cycle.

    AvalancheGo 70bd6d0 vms/platformvm/txs/executor/proposal_tx_executor.go L890-L930: the next cycle starts at
    the previous cycle's end, and its reward is recomputed from the post-restake weight, the current supply at
    that instant, and the reward configuration for that start, so the ACP-285 ramp applies cycle by cycle.
    """
    if next_period_seconds <= 0:
        raise ModelError("a renewed cycle needs a positive period")
    start = as_utc(previous_end)
    reward, supply = start_stake(start, next_period_seconds, weight_navax, current_supply_navax, config, upgrades)
    return start + timedelta(seconds=next_period_seconds), reward, supply


def max_validator_weight_navax(
    self_stake_navax: int,
    delegation_multiplier: int = ACP247_CURRENT_DELEGATION_MULTIPLIER,
    config: StakingConfig = MAINNET,
) -> int:
    """Total weight a validator may carry: self stake plus delegations up to the multiplier, capped by the maximum stake.

    ACP-247 README: MaxDelegatorStake = Min(ValidatorStake * multiplier, MaxValidatorWeight - ValidatorStake).
    """
    if self_stake_navax < 0 or delegation_multiplier < 0:
        raise ModelError("self stake and multiplier must be non-negative")
    return min(self_stake_navax * (1 + delegation_multiplier), config.max_validator_stake_navax)


def delegation_weight_limit_navax(
    validator_weight_navax: int,
    chain_time: datetime,
    delegation_multiplier: int = ACP247_CURRENT_DELEGATION_MULTIPLIER,
    config: StakingConfig = MAINNET,
    upgrades: UpgradeSchedule = MAINNET_UPGRADES,
) -> int:
    """Total weight a delegation may not push its validator above, at the chain time of verification.

    AvalancheGo 70bd6d0 vms/platformvm/txs/executor/staker_tx_verification.go L461-L468 (AddDelegatorTx) and
    L727-L734 (AddPermissionlessDelegatorTx): MaxValidatorWeightFactor (5, proposal_tx_executor.go L32) times the
    validator's weight, capped at MaxValidatorStake from Apricot Phase 3. For an ACP-236 validator the weight is the
    current cycle's weight after restaking.
    """
    if upgrades.activated("apricot_phase_3", chain_time):
        return max_validator_weight_navax(validator_weight_navax, delegation_multiplier, config)
    if validator_weight_navax < 0 or delegation_multiplier < 0:
        raise ModelError("validator weight and multiplier must be non-negative")
    return validator_weight_navax * (1 + delegation_multiplier)


def peak_validator_weight_navax(
    validator_weight_navax: int,
    delegations: Iterable[tuple[datetime, datetime, int]],
    start: datetime,
    end: datetime,
) -> int:
    """Largest total weight on a validator between ``start`` and ``end`` given its delegations (start, end, weight).

    AvalancheGo 70bd6d0 vms/platformvm/txs/executor/staker_tx_verification_helpers.go L143-L226 GetMaxWeight.
    Delegation starts and ends are applied in time order, a start before an end at the same instant
    (vms/platformvm/state/staker_diff_iterator.go L69-L78). The weight is sampled before each change inside
    [start, end] and once after the last change at or before ``end``, so a delegation that ends at ``start`` or
    begins at ``end`` still counts. Pass every current and pending delegation on the validator.
    """
    if as_utc(end) <= as_utc(start):
        raise ModelError("the interval must have start < end")
    changes = []
    for delegation_start, delegation_end, weight in delegations:
        if weight < 0 or as_utc(delegation_end) < as_utc(delegation_start):
            raise ModelError("delegations need a non-negative weight and start <= end")
        changes.append((as_utc(delegation_start), 0, weight))
        changes.append((as_utc(delegation_end), 1, -weight))
    changes.sort(key=lambda change: (change[0], change[1]))
    current, peak = validator_weight_navax, 0
    for instant, _, delta in changes:
        if instant > as_utc(end):
            break
        if instant >= as_utc(start):
            peak = max(peak, current)
        current += delta
    return max(peak, current)


def over_delegated(
    validator_weight_navax: int,
    delegations: Iterable[tuple[datetime, datetime, int]],
    delegation_weight_navax: int,
    start: datetime,
    end: datetime,
    weight_limit_navax: int,
) -> bool:
    """AvalancheGo 70bd6d0 staker_tx_verification_helpers.go L120-L141 overDelegated: peak weight plus the new
    delegation above the limit (delegation_weight_limit_navax) rejects the delegation."""
    peak = peak_validator_weight_navax(validator_weight_navax, delegations, start, end)
    return peak + delegation_weight_navax > weight_limit_navax


def describe(config: StakingConfig = MAINNET, upgrades: UpgradeSchedule = MAINNET_UPGRADES) -> dict[str, Any]:
    return {
        "staking": {
            "uptime_requirement": config.uptime_requirement,
            "min_validator_stake_avax": config.min_validator_stake_navax // NAVAX_PER_AVAX,
            "max_validator_stake_avax": config.max_validator_stake_navax // NAVAX_PER_AVAX,
            "min_delegator_stake_avax": config.min_delegator_stake_navax // NAVAX_PER_AVAX,
            "min_delegation_fee_shares": config.min_delegation_fee_shares,
            "min_stake_duration_days": config.min_stake_duration_seconds / SECONDS_PER_DAY,
            "helicon_min_stake_duration_days": config.helicon_min_stake_duration_seconds / SECONDS_PER_DAY,
            "max_stake_duration_days": config.max_stake_duration_seconds / SECONDS_PER_DAY,
        },
        "reward": {
            "max_consumption_rate": config.reward.max_consumption_rate,
            "min_consumption_rate": config.reward.min_consumption_rate,
            "acp285_target_min_consumption_rate": ACP285_TARGET_MIN_CONSUMPTION_RATE,
            "acp285_ramp_days": ACP285_RAMP_SECONDS / SECONDS_PER_DAY,
            "minting_period_days": config.reward.minting_period_seconds / SECONDS_PER_DAY,
            "supply_cap_avax": config.reward.supply_cap_navax // NAVAX_PER_AVAX,
            "percent_denominator": PERCENT_DENOMINATOR,
        },
        "upgrades": [{"name": item.name, "activated_at": item.activated_at.isoformat().replace("+00:00", "Z")} for item in upgrades.upgrades],
        "mechanisms": [
            {"acp": item.acp, "name": item.name, "upgrade": item.upgrade, "keyed_by": item.keyed_by, "sources": list(item.sources)}
            for item in MECHANISMS
        ],
    }
