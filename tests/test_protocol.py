from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pytest

from avalanche_research.model import protocol
from avalanche_research.model.backtest import backtest
from avalanche_research.model.types import ModelError, RewardConfig, Upgrade, UpgradeSchedule, ValidatorFeeConfig


DAY = 86_400
MEGA = 1_000_000 * protocol.NAVAX_PER_AVAX
KILO = 1_000 * protocol.NAVAX_PER_AVAX
EPOCH = datetime(1, 1, 1, tzinfo=timezone.utc)


# vms/platformvm/reward/calculator_test.go TestRewards (before Helicon)
@pytest.mark.parametrize("duration, stake, supply, expected", [
    (365 * DAY, MEGA, 360 * MEGA, 120 * KILO),
    (365 * DAY, MEGA, 400 * MEGA, 96 * KILO),
    (365 * DAY, 2 * MEGA, 400 * MEGA, 192 * KILO),
    (365 * DAY, MEGA, 720 * MEGA, 0),
    (DAY, MEGA, 360 * MEGA, 274_122_724_713),
    (DAY, 5_000_000, 360 * MEGA, 1_370),
    (DAY, MEGA, 400 * MEGA, 219_298_179_771),
    (DAY, 2 * MEGA, 400 * MEGA, 438_596_359_542),
    (DAY, MEGA, 720 * MEGA, 0),
])
def test_rewards_match_avalanchego_vectors(duration, stake, supply, expected):
    assert protocol.potential_reward(stake, duration, supply) == expected
    assert protocol.primary_network_reward(EPOCH, duration, stake, supply) == expected


# calculator_test.go TestPrimaryNetworkCalculatorHeliconRewards
HELICON = datetime.fromtimestamp(1_000_000, tz=timezone.utc)
RAMP = timedelta(days=90)


@pytest.mark.parametrize("min_rate, max_rate, start, expected", [
    (100_000, None, HELICON, 274_122_724_713),
    (100_000, None, HELICON + RAMP / 3, 251_355_136_048),
    (100_000, None, HELICON + RAMP, 205_817_226_496),
    (80_000, None, HELICON + RAMP / 2, 212_647_776_318),
    (10_000, None, HELICON + RAMP / 2, 117_020_078_814),
    (74_999, None, HELICON, 205_814_494_276),
    (74_999, None, HELICON + RAMP / 2, 205_814_494_276),
    (74_999, None, HELICON + RAMP, 205_817_226_496),
    (75_000, None, HELICON + RAMP / 2, 205_817_226_496),
    (75_001, None, HELICON, 205_819_958_716),
    (75_001, None, HELICON + RAMP / 2, 205_819_958_716),
    (75_001, None, HELICON + RAMP, 205_817_226_496),
    (10_000, 20_000, HELICON + RAMP, 27_472_321_261),
])
def test_helicon_ramp_matches_avalanchego_vectors(min_rate, max_rate, start, expected):
    config = RewardConfig(max_rate or 120_000, min_rate, 365 * DAY, 720 * MEGA)
    upgrades = UpgradeSchedule((Upgrade("helicon", HELICON),))
    assert protocol.primary_network_reward(start, DAY, MEGA, 360 * MEGA, config, upgrades) == expected


def test_reward_overflow_returns_remaining_supply():
    config = RewardConfig(1_000_000, 1_000_000, DAY, 2**64 - 1)
    assert protocol.potential_reward(2**64 - 1, DAY, 1, config) == 2**64 - 2


def test_reward_rejects_domain_errors():
    with pytest.raises(ModelError):
        protocol.potential_reward(KILO, DAY, 0)
    with pytest.raises(ModelError):
        protocol.potential_reward(KILO, DAY, 721 * MEGA)
    with pytest.raises(ModelError):
        RewardConfig(100_000, 120_000, DAY, 1)


# ACP-285 README reward schedule, supply 470,134,316 AVAX, cap 720,000,000 AVAX
ACP285_SUPPLY = 470_134_316 * protocol.NAVAX_PER_AVAX
BEFORE = datetime(2026, 9, 1, tzinfo=timezone.utc)
AFTER_RAMP = protocol.MAINNET_UPGRADES.time("helicon") + timedelta(days=90)


@pytest.mark.parametrize("days, current, reduced", [
    (2, None, 4.00), (14, 5.36, 4.08), (90, 5.58, 4.58), (182, 5.85, 5.18), (365, 6.38, 6.38),
])
def test_acp285_reward_schedule(days, current, reduced):
    if current is not None:
        assert protocol.annualized_reward_rate(BEFORE, days * DAY, KILO, ACP285_SUPPLY) * 100 == pytest.approx(current, abs=0.01)
    assert protocol.annualized_reward_rate(AFTER_RAMP, days * DAY, KILO, ACP285_SUPPLY) * 100 == pytest.approx(reduced, abs=0.01)


def test_mainnet_helicon_mechanisms_key_on_the_right_time():
    helicon = protocol.MAINNET_UPGRADES.time("helicon")
    second = timedelta(seconds=1)
    assert protocol.reward_config_for_stake_start(helicon - second) == protocol.MAINNET_REWARD
    assert protocol.reward_config_for_stake_start(helicon).min_consumption_rate == 100_000
    assert protocol.reward_config_for_stake_start(helicon + timedelta(days=45)).min_consumption_rate == 87_500
    assert protocol.reward_config_for_stake_start(helicon + timedelta(days=90)).min_consumption_rate == 75_000
    assert protocol.reward_config_for_stake_start(helicon + timedelta(days=400)).min_consumption_rate == 75_000
    assert protocol.min_stake_duration_seconds(helicon - second) == 14 * DAY
    assert protocol.min_stake_duration_seconds(helicon) == 48 * 3_600
    assert protocol.uptime_requirement(helicon - second) == 0.8
    assert protocol.uptime_requirement(helicon) == 0.9
    assert protocol.MAINNET_UPGRADES.regime(datetime(2024, 6, 1, tzinfo=timezone.utc)) == "durango"
    assert protocol.MAINNET_UPGRADES.regime(datetime(2020, 10, 1, tzinfo=timezone.utc)) == "genesis"


def test_split_and_weight_rules():
    assert protocol.split_reward(1_000_000, 20_000) == (20_000, 980_000)
    assert protocol.split_reward(1_000_000, 1_000_000) == (1_000_000, 0)
    assert protocol.split_reward(7, 20_000) == (7 - 6, 6)
    assert protocol.max_validator_weight_navax(2 * KILO) == 10 * KILO
    assert protocol.max_validator_weight_navax(2 * KILO, protocol.ACP247_PROPOSED_DELEGATION_MULTIPLIER) == 50 * KILO
    assert protocol.max_validator_weight_navax(1_000 * KILO) == 3_000 * KILO
    with pytest.raises(ModelError):
        protocol.split_reward(10, 1_000_001)


def test_describe_lists_sources_for_every_mechanism():
    description = protocol.describe()
    assert description["reward"]["supply_cap_avax"] == 720_000_000
    assert [item["name"] for item in description["upgrades"]][-1] == "helicon"
    assert all(item["sources"] for item in description["mechanisms"])


def write_parquet(path: Path, sql: str) -> None:
    connection = duckdb.connect()
    try:
        connection.execute(f"COPY ({sql}) TO '{path}' (FORMAT PARQUET)")
    finally:
        connection.close()


def test_backtest_reports_matches_and_regime_mismatches(tmp_path):
    start = datetime(2025, 6, 30, 23, 57, 1)
    supply = 470_000_000 * protocol.NAVAX_PER_AVAX
    stake = 374_179_173_106
    duration = 14 * DAY + 3_600
    expected = protocol.primary_network_reward(start.replace(tzinfo=timezone.utc), duration, stake, supply)
    validators, delegators, supplies = tmp_path / "v", tmp_path / "d", tmp_path / "s"
    for directory in (validators, delegators, supplies):
        directory.mkdir()
    write_parquet(validators / "primary-validator-stakes.parquet", f"""
        SELECT 'v1' AS transaction_hash, TIMESTAMP '2025-06-30 23:57:01' AS accepted_at, 'AddPermissionlessValidatorTx' AS tx_type,
               TIMESTAMP '{start}' AS start_time, TIMESTAMP '{start + timedelta(seconds=duration)}' AS end_time,
               {stake}::BIGINT AS stake_navax, {expected}::BIGINT AS potential_reward_navax""")
    write_parquet(delegators / "primary-delegator-stakes.parquet", f"""
        SELECT 'd1' AS transaction_hash, TIMESTAMP '2021-01-01 00:00:00' AS accepted_at, 'AddDelegatorTx' AS tx_type,
               TIMESTAMP '2021-01-01 00:05:00' AS start_time, TIMESTAMP '2021-01-15 00:05:00' AS end_time,
               {25 * protocol.NAVAX_PER_AVAX}::BIGINT AS stake_navax, 1::BIGINT AS potential_reward_navax
        UNION ALL
        SELECT 'd2', TIMESTAMP '2020-09-10 00:00:00', 'AddDelegatorTx', TIMESTAMP '2020-09-10 00:00:00', TIMESTAMP '2020-12-10 00:00:00',
               {25 * protocol.NAVAX_PER_AVAX}::BIGINT, 5::BIGINT""")
    write_parquet(supplies / "primary-staking-supply.parquet", f"""
        SELECT 'v1' AS transaction_hash, {supply - 10**15}::BIGINT AS previous_block_supply_navax, {supply + expected}::BIGINT AS block_supply_navax,
               {10**15}::BIGINT AS in_block_prior_delta_navax, {10**15 + expected}::BIGINT AS in_block_total_delta_navax
        UNION ALL SELECT 'd1', {supply}::BIGINT, {supply}::BIGINT, 0::BIGINT, 0::BIGINT
        UNION ALL SELECT 'd2', NULL, NULL, 0::BIGINT, 0::BIGINT""")
    result = backtest(validators, delegators, supplies)
    assert result["summary"] == {
        "rows": 3, "without_supply_context": 1, "without_potential_reward": 0,
        "immediate_rows": 1, "immediate_matched": 1, "immediate_mismatched": 0,
        "pending_rows": 1, "pending_matched": 0, "pending_mismatched": 1, "unmatched_supply_rows": 0,
    }
    assert result["regimes"]["fortuna"]["candidate_matches"] == {"supply_before": 1, "previous_block": 0, "block_before_later": 1, "block_after": 0}
    assert result["regimes"]["fortuna"]["best_candidate"] == "supply_before"
    assert result["findings"] == [
        "1 of 1 rows starting after acceptance are not reproducible from the acceptance-block supply because the protocol computed their reward at the start time"
    ]
    assert list(result["regimes"]) == ["genesis", "fortuna"]
    assert result["regimes"]["genesis"]["pending_mismatched"] == 1


# KG1 current-supply counter
GENESISTEST_SUPPLY = 360 * MEGA  # genesis/genesistest/genesis.go InitialSupply
PRE_HELICON = protocol.MAINNET_UPGRADES.time("helicon") - timedelta(days=30)


def test_supply_counter_preserves_reward_order():
    # state_changes_test.go TestAdvanceTimeTo_PromotePendingDelegatorAndValidator_PreservesRewardOrder: the delegator
    # is promoted first, so the validator's reward reads the supply that already includes the delegator's reward.
    duration = 14 * DAY
    delegator, validator = KILO, 2 * MEGA
    want_delegator = protocol.potential_reward(delegator, duration, GENESISTEST_SUPPLY)
    want_validator = protocol.potential_reward(validator, duration, GENESISTEST_SUPPLY + want_delegator)
    rewards, supply = protocol.start_stakes_in_order(
        [(PRE_HELICON, duration, delegator), (PRE_HELICON, duration, validator)], GENESISTEST_SUPPLY)
    assert rewards == (want_delegator, want_validator)
    assert supply == GENESISTEST_SUPPLY + want_delegator + want_validator
    reversed_rewards, reversed_supply = protocol.start_stakes_in_order(
        [(PRE_HELICON, duration, validator), (PRE_HELICON, duration, delegator)], GENESISTEST_SUPPLY)
    assert reversed_rewards[1] != want_delegator
    assert reversed_supply != supply


def test_supply_counter_undoes_forfeited_rewards():
    reward, supply = protocol.start_stake(PRE_HELICON, 14 * DAY, 2 * KILO, GENESISTEST_SUPPLY)
    assert supply == GENESISTEST_SUPPLY + reward
    # reward_validator_test.go TestRewardDelegatorTxExecuteOnAbort and assertRewardAutoRenewedValidator:
    # abort removes the potential reward, commit keeps the counter.
    assert protocol.supply_after_stake_end(supply, reward, rewarded=False) == GENESISTEST_SUPPLY
    assert protocol.supply_after_stake_end(supply, reward, rewarded=True) == supply
    assert protocol.supply_after_stake_end(supply, 0, rewarded=False) == supply


def test_supply_counter_stops_at_the_cap():
    small = RewardConfig(1_000_000, 1_000_000, 365 * DAY, 1_000 * protocol.NAVAX_PER_AVAX)
    remaining = 900 * protocol.NAVAX_PER_AVAX
    reward, supply = protocol.start_stake(PRE_HELICON, 365 * DAY, 10_000 * protocol.NAVAX_PER_AVAX, 100 * protocol.NAVAX_PER_AVAX, small)
    assert (reward, supply) == (remaining, small.supply_cap_navax)
    cap = protocol.MAINNET_REWARD.supply_cap_navax
    assert protocol.start_stake(PRE_HELICON, 365 * DAY, 3 * MEGA, cap) == (0, cap)
    with pytest.raises(ModelError):
        protocol.supply_after_stake_start(cap, 1)
    with pytest.raises(ModelError):
        protocol.supply_after_stake_end(10, 11, rewarded=False)


# KG4 delegator minimum duration and delegation containment
HELICON_MAINNET = protocol.MAINNET_UPGRADES.time("helicon")


@pytest.mark.parametrize("fork_offset, role, expected", [
    # staker_tx_verification_test.go TestGetValidatorRules and TestGetDelegatorRules: MinStakeDuration 2s,
    # HeliconMinStakeDuration 1s, before (Granite) and after Helicon.
    (-1, "validator", 2), (0, "validator", 1), (-1, "delegator", 2), (0, "delegator", 2),
])
def test_min_stake_duration_by_role_matches_avalanchego_rules(fork_offset, role, expected):
    config = replace(protocol.MAINNET, min_stake_duration_seconds=2, helicon_min_stake_duration_seconds=1)
    at = HELICON_MAINNET + timedelta(seconds=fork_offset)
    assert protocol.min_stake_duration_seconds(at, config, role=role) == expected


def test_mainnet_delegators_keep_fourteen_days_after_helicon():
    assert protocol.min_stake_duration_seconds(HELICON_MAINNET, role="delegator") == 14 * DAY
    assert protocol.min_stake_duration_seconds(HELICON_MAINNET, role="validator") == 48 * 3_600
    assert protocol.min_stake_duration_seconds(HELICON_MAINNET) == 48 * 3_600
    with pytest.raises(ModelError):
        protocol.min_stake_duration_seconds(HELICON_MAINNET, role="subnet")


def at_second(value: int) -> datetime:
    return EPOCH + timedelta(seconds=value)


@pytest.mark.parametrize("a, b, a_in_b, b_in_a", [
    # txs/validator_test.go TestBoundedBy, cases 1 to 6 and the equal-interval case
    ((0, 1), (2, 3), False, False),
    ((0, 2), (1, 3), False, False),
    ((0, 3), (1, 2), False, True),
    ((1, 2), (0, 3), True, False),
    ((2, 3), (0, 1), False, False),
    ((1, 3), (0, 2), False, False),
    ((0, 1), (0, 1), True, True),
])
def test_delegation_containment_matches_bounded_by(a, b, a_in_b, b_in_a):
    a_start, a_end, b_start, b_end = (at_second(value) for value in (*a, *b))
    assert protocol.delegation_within_validator_period(a_start, a_end, b_start, b_end) is a_in_b
    assert protocol.delegation_within_validator_period(b_start, b_end, a_start, a_end) is b_in_a


def test_delegation_containment_matches_add_delegator_cases():
    # standard_tx_executor_test.go TestStandardTxExecutorAddDelegator: validator period [start, end]
    start, end = at_second(5), at_second(360 * DAY - 5)
    second = timedelta(seconds=1)
    assert not protocol.delegation_within_validator_period(start - second, end, start, end)  # starts before validator
    assert not protocol.delegation_within_validator_period(start, end + second, start, end)  # stops after validator
    assert protocol.delegation_within_validator_period(start, end, start, end)  # valid


def test_delegation_window_closes_fourteen_days_before_validator_end():
    start = HELICON_MAINNET + timedelta(days=1)
    end = start + timedelta(days=30)
    last = end - timedelta(days=14)
    assert protocol.delegation_window_open(last, start, end)
    assert not protocol.delegation_window_open(last + timedelta(seconds=1), start, end)
    assert not protocol.delegation_window_open(start - timedelta(seconds=1), start, end)
    # a 48-hour validator and a 13-day cycle can never hold a delegation
    assert not protocol.delegation_window_open(start, start, start + timedelta(hours=48))
    assert not protocol.delegation_window_open(start, start, start + timedelta(days=13))
    assert protocol.delegation_window_open(start, start, start + timedelta(days=14))


# KG5 peak-weight delegation check
MILLI = protocol.NAVAX_PER_AVAX // 1_000


def test_peak_weight_without_delegations_is_the_validator_weight():
    # vm_test.go TestMaxStakeAmount: every window inside the validator period
    start, end = at_second(0), at_second(360 * DAY)
    minute = timedelta(minutes=1)
    for window in ((start, end), (start + minute, end), (start, end - minute), (start + minute, end - minute)):
        assert protocol.peak_validator_weight_navax(5 * MILLI, [], *window) == 5 * MILLI


def test_over_delegated_regression():
    # vm_regression_test.go TestAddDelegatorTxOverDelegatedRegression: validator 5 mAVAX, limit 25 mAVAX,
    # MinStakeDuration 48 hours in vm_test.go
    minimum = timedelta(hours=48)
    validator = 5 * MILLI
    limit = protocol.delegation_weight_limit_navax(validator, HELICON_MAINNET)
    assert limit == 25 * MILLI
    first_start = at_second(100)
    first = (first_start, first_start + minimum, 4 * validator)
    second_start = first[1] + timedelta(seconds=2)
    second = (second_start, second_start + minimum, MILLI)
    assert not protocol.over_delegated(validator, [first], MILLI, second_start, second_start + minimum, limit)
    third_start = first[1] - timedelta(seconds=1)
    assert protocol.over_delegated(validator, [first, second], MILLI, third_start, third_start + minimum, limit)


@pytest.mark.parametrize("ap3_offset", [timedelta(days=-400), timedelta(days=400)])
def test_heap_corruption_regression_accepts_all_four(ap3_offset):
    # vm_regression_test.go TestAddDelegatorTxHeapCorruption, min stake 5 mAVAX, max 500 mAVAX, min duration 48 hours
    minimum = timedelta(hours=48)
    config = replace(protocol.MAINNET, min_validator_stake_navax=5 * MILLI, max_validator_stake_navax=500 * MILLI)
    validator = config.max_validator_stake_navax // 5
    start = HELICON_MAINNET
    upgrades = UpgradeSchedule((Upgrade("apricot_phase_3", start + ap3_offset),))
    delegations = [
        (start, start + 3 * minimum, 5 * MILLI),
        (start + minimum, start + 6 * minimum, 5 * MILLI),
        (start + 2 * minimum, start + 4 * minimum, config.max_validator_stake_navax - validator - 10 * MILLI),
        (start + 5 * minimum, start + 7 * minimum, config.max_validator_stake_navax - validator - 5 * MILLI),
    ]
    limit = protocol.delegation_weight_limit_navax(validator, start, config=config, upgrades=upgrades)
    for index, (delegation_start, delegation_end, weight) in enumerate(delegations):
        assert not protocol.over_delegated(validator, delegations[:index], weight, delegation_start, delegation_end, limit)


def test_add_before_remove_regression():
    # vm_regression_test.go TestAddDelegatorTxAddBeforeRemove: the second delegation starts when the first ends
    minimum = timedelta(hours=48)
    maximum = 500 * MILLI
    validator = maximum // 5
    start = at_second(0)
    first = (start, start + 3 * minimum, maximum - validator)
    limit = min(5 * validator, maximum)
    assert protocol.over_delegated(validator, [first], maximum - validator, first[1], first[1] + 3 * minimum, limit)


def test_weight_limit_is_capped_from_apricot_phase_3():
    # standard_tx_executor_test.go TestStandardTxExecutorAddDelegator, over delegation before and after AP3:
    # validator at MaxValidatorStake 500 mAVAX, delegation of MinDelegatorStake 1 mAVAX
    config = replace(protocol.MAINNET, max_validator_stake_navax=500 * MILLI)
    start, end = at_second(5), at_second(360 * DAY - 5)
    for ap3, expected in ((end, False), (start, True)):
        upgrades = UpgradeSchedule((Upgrade("apricot_phase_3", ap3),))
        limit = protocol.delegation_weight_limit_navax(500 * MILLI, start, config=config, upgrades=upgrades)
        assert protocol.over_delegated(500 * MILLI, [], MILLI, start, end, limit) is expected


def test_peak_weight_counts_changes_at_both_interval_bounds():
    start, end = at_second(10), at_second(20)
    ends_at_start = (at_second(0), start, 7)
    starts_at_end = (end, at_second(30), 11)
    outside = (at_second(21), at_second(30), 13)
    assert protocol.peak_validator_weight_navax(100, [ends_at_start], start, end) == 107
    assert protocol.peak_validator_weight_navax(100, [starts_at_end], start, end) == 111
    assert protocol.peak_validator_weight_navax(100, [outside], start, end) == 100
    assert protocol.peak_validator_weight_navax(100, [(at_second(0), at_second(5), 50)], start, end) == 100
    with pytest.raises(ModelError):
        protocol.peak_validator_weight_navax(100, [], end, start)


# KG3 uptime pass or fail and forfeiture
ACP267_TEST_HELICON = datetime(2026, 4, 1, tzinfo=HELICON_MAINNET.tzinfo)


@pytest.mark.parametrize("helicon_scheduled, start_offset, uptime, prefers_commit", [
    # block/executor/block_test.go TestBlockOptionsACP267UptimeRequirement
    (True, timedelta(seconds=-1), 0.85, True),  # pre_helicon
    (True, timedelta(0), 0.85, False),  # at_helicon
    (True, timedelta(hours=1), 0.9, True),  # post_helicon
    (False, timedelta(hours=1), 0.85, True),  # without_helicon
])
def test_uptime_outcome_matches_acp267_block_options(helicon_scheduled, start_offset, uptime, prefers_commit):
    helicon = ACP267_TEST_HELICON if helicon_scheduled else datetime(9999, 1, 1, tzinfo=HELICON_MAINNET.tzinfo)
    upgrades = UpgradeSchedule((Upgrade("helicon", helicon),))
    assert protocol.uptime_passes(uptime, ACP267_TEST_HELICON + start_offset, upgrades=upgrades) is prefers_commit


def test_uptime_fraction_matches_uptime_manager():
    # snow/uptime/manager_test.go TestCalculateUptimePercentageDivBy0 and TestCalculateUptimePercentage
    assert protocol.uptime_fraction(0, 0) == 1.0
    assert protocol.uptime_fraction(0, 1) == 0.0
    # ACP-267 leaves 4.8 hours of downtime on a 48-hour cycle
    window = 48 * 3_600
    assert protocol.uptime_passes(protocol.uptime_fraction(window - 17_280, window), HELICON_MAINNET)
    assert not protocol.uptime_passes(protocol.uptime_fraction(window - 17_281, window), HELICON_MAINNET)
    with pytest.raises(ModelError):
        protocol.uptime_fraction(-1, 10)


def test_failed_uptime_forfeits_reward_but_pays_deferred_fees():
    # reward_validator_test.go TestRewardValidatorTxExecuteOnCommit and OnAbort; rewardValidatorTx pays the
    # accrued delegatee reward on abort too.
    assert protocol.validator_rewards_at_end(1_000, 50, passed=True) == (1_000, 50)
    assert protocol.validator_rewards_at_end(1_000, 50, passed=False) == (0, 50)


def test_delegation_reward_follows_validator_outcome():
    # reward_validator_test.go TestRewardDelegatorTxExecuteOnCommitPreDelegateeDeferral: reward 1,000,000 with a
    # 25% delegation fee; TestRewardDelegatorTxExecuteOnAbort: neither side is paid.
    delegator, fee = protocol.delegator_rewards_at_end(1_000_000, protocol.PERCENT_DENOMINATOR // 4, passed=True)
    assert (delegator, fee) == (750_000, 250_000)
    assert fee < delegator and delegator + fee == 1_000_000
    assert protocol.delegator_rewards_at_end(1_000_000, protocol.PERCENT_DENOMINATOR // 4, passed=False) == (0, 0)
    # a delegation starting after Helicon on a validator that started before it is judged at 80%
    validator_start = HELICON_MAINNET - timedelta(days=10)
    assert protocol.uptime_passes(0.85, validator_start)
    assert not protocol.uptime_passes(0.85, HELICON_MAINNET)


# KG2 ACP-236 auto-renewed staking
# reward_validator_test.go defaultAutoRenewedValidatorConfig with the executor test limits (min 5 mAVAX, max 500 mAVAX).
# The potential reward is the TestRewards vector for 5,000,000 nAVAX staked one day at 360M AVAX supply.
AUTO_RENEW = {"weight": 5 * MILLI, "delegatee": 5_000_000, "accrued_validation": 1_000_000, "accrued_delegatee": 500_000,
              "shares": 4 * protocol.PERCENT_DENOMINATOR // 10}
AUTO_RENEW_CONFIG = replace(protocol.MAINNET, min_validator_stake_navax=5 * MILLI, max_validator_stake_navax=500 * MILLI)
AUTO_RENEW_REWARD = protocol.potential_reward(5_000_000, DAY, 360 * MEGA)


def restaked(amount: int, shares: int) -> int:
    # reward_validator_test.go autoRenewedValidatorConfig.restakedReward
    return amount - (protocol.PERCENT_DENOMINATOR - shares) * amount // protocol.PERCENT_DENOMINATOR


def test_auto_renew_graceful_stop_and_forced_exit():
    # reward_validator_test.go TestRewardAutoRenewedValidatorTx graceful_stop, commit and abort branches
    args = (AUTO_RENEW_REWARD, AUTO_RENEW["delegatee"], AUTO_RENEW["accrued_validation"], AUTO_RENEW["accrued_delegatee"])
    assert AUTO_RENEW_REWARD == 1_370
    assert protocol.auto_renew_exit_rewards(*args, passed=True) == (AUTO_RENEW_REWARD + 1_000_000, 5_500_000)
    assert protocol.auto_renew_exit_rewards(*args, passed=False) == (1_000_000, 5_500_000)
    assert not protocol.auto_renew_continues(True, 0)
    assert not protocol.auto_renew_continues(False, DAY)
    assert protocol.auto_renew_continues(True, DAY)


def test_auto_renew_restake_below_max():
    # reward_validator_test.go TestRewardAutoRenewedValidatorTx restake_below_max
    validation, delegatee = restaked(AUTO_RENEW_REWARD, AUTO_RENEW["shares"]), restaked(AUTO_RENEW["delegatee"], AUTO_RENEW["shares"])
    result = protocol.auto_renew_restake(AUTO_RENEW_REWARD, AUTO_RENEW["delegatee"], AUTO_RENEW["shares"], AUTO_RENEW["weight"], AUTO_RENEW_CONFIG)
    assert result == (validation, delegatee, AUTO_RENEW_REWARD - validation, AUTO_RENEW["delegatee"] - delegatee)
    assert (validation, delegatee) == (548, 2_000_000)


def test_auto_renew_restake_capped_at_max():
    # reward_validator_test.go TestRewardAutoRenewedValidatorTx restake_capped_at_max, restakingCapacity 2,000,000
    capacity = 2_000_000
    weight = AUTO_RENEW_CONFIG.max_validator_stake_navax - capacity
    uncapped_validation = restaked(AUTO_RENEW_REWARD, AUTO_RENEW["shares"])
    uncapped = uncapped_validation + restaked(AUTO_RENEW["delegatee"], AUTO_RENEW["shares"])
    validation = uncapped_validation * capacity // uncapped
    delegatee = capacity - validation
    result = protocol.auto_renew_restake(AUTO_RENEW_REWARD, AUTO_RENEW["delegatee"], AUTO_RENEW["shares"], weight, AUTO_RENEW_CONFIG)
    assert result == (validation, delegatee, AUTO_RENEW_REWARD - validation, AUTO_RENEW["delegatee"] - delegatee)
    assert weight + result[0] + result[1] == AUTO_RENEW_CONFIG.max_validator_stake_navax
    assert protocol.auto_renew_restake(10, 10, protocol.PERCENT_DENOMINATOR, AUTO_RENEW_CONFIG.max_validator_stake_navax, AUTO_RENEW_CONFIG) == (0, 0, 10, 10)
    assert protocol.auto_renew_restake(10, 10, 0, weight, AUTO_RENEW_CONFIG) == (0, 0, 10, 10)


def test_auto_renew_next_cycle_recomputes_reward_on_the_ramp():
    # assertRewardAutoRenewedValidator: commit supply equals the supply plus the renewed cycle's potential reward.
    supply = 460_000_000 * protocol.NAVAX_PER_AVAX
    weight = 2 * KILO
    end, reward, new_supply = protocol.auto_renew_next_cycle(HELICON_MAINNET, 14 * DAY, weight, supply)
    assert end == HELICON_MAINNET + timedelta(days=14)
    assert reward == protocol.primary_network_reward(HELICON_MAINNET, 14 * DAY, weight, supply)
    assert new_supply == supply + reward
    # MI2: the same cycle 45 days into the ACP-285 ramp earns less
    _, later_reward, _ = protocol.auto_renew_next_cycle(HELICON_MAINNET + timedelta(days=45), 14 * DAY, weight, supply)
    assert later_reward < reward
    with pytest.raises(ModelError):
        protocol.auto_renew_next_cycle(HELICON_MAINNET, 0, weight, supply)


# KG6 admission checks
# staker_tx_verification_test.go TestVerifyAddPermissionlessValidatorTx rules: stake 1 to 2, duration 3s to 4s, fee 5
TRANSFORM_RULES = replace(protocol.MAINNET, min_validator_stake_navax=1, max_validator_stake_navax=2,
                          min_stake_duration_seconds=3, helicon_min_stake_duration_seconds=3,
                          max_stake_duration_seconds=4, min_delegation_fee_shares=5)


@pytest.mark.parametrize("weight, shares, duration, expected", [
    (0, 20_000, 3, protocol.ERR_WEIGHT_TOO_SMALL),  # weight too low
    (3, 20_000, 3, protocol.ERR_WEIGHT_TOO_LARGE),  # weight too high
    (2, 4, 3, protocol.ERR_INSUFFICIENT_DELEGATION_FEE),  # insufficient delegation fee
    (2, 5, 2, protocol.ERR_STAKE_TOO_SHORT),  # duration too short
    (2, 5, 5, protocol.ERR_STAKE_TOO_LONG),  # duration too long
    (1, 20_000, 3, None),  # success
    (2, 5, 4, None),
])
def test_validator_admission_matches_avalanchego_cases(weight, shares, duration, expected):
    start = HELICON_MAINNET + timedelta(days=1)
    end = start + timedelta(seconds=duration)
    assert protocol.validator_admission_error(weight, shares, start, end, TRANSFORM_RULES) == expected


# standard_tx_executor_test.go executor environment: stake 5 mAVAX to 500 mAVAX, fee 2%, 24h, Helicon 12h, 365 days
EXECUTOR_RULES = replace(protocol.MAINNET, min_validator_stake_navax=5 * MILLI, max_validator_stake_navax=500 * MILLI,
                         min_delegator_stake_navax=MILLI, min_stake_duration_seconds=DAY,
                         helicon_min_stake_duration_seconds=12 * 3_600)


@pytest.mark.parametrize("chain_offset, weight, shares, period, expected", [
    # TestStandardExecutorAddAutoRenewedValidatorTxErrors
    (-1, 5 * MILLI, 20_000, DAY, protocol.ERR_HELICON_NOT_ACTIVE),  # invalid_upgrade
    (0, 5 * MILLI - 1, 20_000, DAY, protocol.ERR_WEIGHT_TOO_SMALL),
    (0, 500 * MILLI + 1, 20_000, DAY, protocol.ERR_WEIGHT_TOO_LARGE),
    (0, 5 * MILLI, 19_999, DAY, protocol.ERR_INSUFFICIENT_DELEGATION_FEE),
    (0, 5 * MILLI, 20_000, 12 * 3_600 - 1, protocol.ERR_STAKE_TOO_SHORT),
    (0, 5 * MILLI, 20_000, 365 * DAY + 1, protocol.ERR_STAKE_TOO_LONG),
    (0, 5 * MILLI, 20_000, 12 * 3_600, None),
])
def test_auto_renewed_admission_matches_avalanchego_cases(chain_offset, weight, shares, period, expected):
    chain_time = HELICON_MAINNET + timedelta(seconds=chain_offset)
    assert protocol.auto_renewed_validator_admission_error(weight, shares, period, chain_time, EXECUTOR_RULES) == expected


@pytest.mark.parametrize("chain_offset, period, expected", [
    # TestStandardExecutorSetAutoRenewedValidatorConfigTx and its Errors test
    (-1, 30 * DAY, protocol.ERR_HELICON_NOT_ACTIVE),
    (0, 30 * DAY, None),  # updated period
    (0, 0, None),  # period 0, exit requested
    (0, 12 * 3_600 - 1, protocol.ERR_STAKE_TOO_SHORT),
    (0, 365 * DAY + 1, protocol.ERR_STAKE_TOO_LONG),
])
def test_auto_renewed_config_matches_avalanchego_cases(chain_offset, period, expected):
    chain_time = HELICON_MAINNET + timedelta(seconds=chain_offset)
    assert protocol.auto_renewed_config_error(period, chain_time, EXECUTOR_RULES) == expected


def test_delegator_admission_order_and_rules():
    chain = HELICON_MAINNET + timedelta(days=1)
    validator_start, validator_end = chain - timedelta(days=1), chain + timedelta(days=60)
    fourteen = chain + timedelta(days=14)

    def check(weight, start, end, delegations=(), validator_weight=2 * KILO, at=chain):
        return protocol.delegator_admission_error(weight, start, end, at, validator_start, validator_end,
                                                  validator_weight, list(delegations))

    assert check(25 * protocol.NAVAX_PER_AVAX, chain, fourteen) is None
    assert check(25 * protocol.NAVAX_PER_AVAX - 1, chain, fourteen) == protocol.ERR_WEIGHT_TOO_SMALL
    assert check(25 * protocol.NAVAX_PER_AVAX, chain, fourteen - timedelta(seconds=1)) == protocol.ERR_STAKE_TOO_SHORT
    assert check(25 * protocol.NAVAX_PER_AVAX, chain, chain + timedelta(days=61)) == protocol.ERR_PERIOD_MISMATCH
    assert check(8 * KILO, chain, fourteen) is None
    assert check(8 * KILO + 1, chain, fourteen) == protocol.ERR_OVER_DELEGATED
    assert check(KILO, chain, fourteen, [(chain, fourteen, 7 * KILO + 1)]) == protocol.ERR_OVER_DELEGATED
    # both a small stake and a short duration: Durango reports the stake first, AddDelegatorTx the duration first
    short_small = (25 * protocol.NAVAX_PER_AVAX - 1, chain, chain + timedelta(days=1))
    assert check(*short_small) == protocol.ERR_WEIGHT_TOO_SMALL
    pre_durango = protocol.MAINNET_UPGRADES.time("durango") - timedelta(days=1)
    assert check(short_small[0], pre_durango, pre_durango + timedelta(days=1), at=pre_durango) == protocol.ERR_STAKE_TOO_SHORT


# KG7 delegation fee deferral
CORTINA = protocol.MAINNET_UPGRADES.time("cortina")


def test_delegation_fee_paid_at_delegation_end_before_cortina():
    # reward_validator_test.go TestRewardDelegatorTxExecuteOnCommitPreDelegateeDeferral: 25% of a 1,000,000 reward
    # reaches the validator's delegation owner when the delegation ends.
    delegator, fee = protocol.delegator_rewards_at_end(1_000_000, protocol.PERCENT_DENOMINATOR // 4, passed=True)
    assert protocol.settle_delegation_fee(fee, 0, CORTINA - timedelta(seconds=1)) == (250_000, 0)
    assert delegator == 750_000


def test_delegation_fee_deferred_to_validator_end_from_cortina():
    # reward_validator_test.go TestRewardDelegatorTxExecuteOnCommitPostDelegateeDeferral and
    # TestRewardDelegatorTxAndValidatorTxExecuteOnCommitPostDelegateeDeferral: delegation reward 1,000,000 at 25%,
    # validator reward 2,000,000. Nothing reaches the validator at the delegation's end; at its own end it
    # receives 2,000,000 plus 1,000,000 / 4.
    delegator, fee = protocol.delegator_rewards_at_end(1_000_000, protocol.PERCENT_DENOMINATOR // 4, passed=True)
    paid_now, accrued = protocol.settle_delegation_fee(fee, 0, CORTINA)
    assert (delegator, paid_now, accrued) == (750_000, 0, 250_000)
    assert protocol.validator_rewards_at_end(2_000_000, accrued, passed=True) == (2_000_000, 250_000)
    assert protocol.validator_rewards_at_end(2_000_000, accrued, passed=False) == (0, 250_000)
    # keyed to the validator's start, not the delegation's
    assert not protocol.delegation_fee_deferred(CORTINA - timedelta(seconds=1))
    assert protocol.delegation_fee_deferred(CORTINA)
    assert protocol.settle_delegation_fee(10, 5, CORTINA) == (0, 15)


# KG8 pending stakers before Durango
DURANGO = protocol.MAINNET_UPGRADES.time("durango")


def test_pending_promotion_rewards_follow_iterator_order():
    # state_changes_test.go TestAdvanceTimeTo_PromotePendingDelegatorAndValidator_PreservesRewardOrder: an Apricot
    # delegator and a validator with the same start; the delegator's reward is minted first.
    start = DURANGO - timedelta(days=30)
    end = start + timedelta(days=14)
    stakes = [("AddValidatorTx", start, end, 2 * MEGA), ("AddDelegatorTx", start, end, KILO)]
    want_delegator = protocol.potential_reward(KILO, 14 * DAY, GENESISTEST_SUPPLY)
    want_validator = protocol.potential_reward(2 * MEGA, 14 * DAY, GENESISTEST_SUPPLY + want_delegator)
    rewards, supply = protocol.promote_pending_stakes(stakes, GENESISTEST_SUPPLY)
    assert rewards == (want_validator, want_delegator)
    assert supply == GENESISTEST_SUPPLY + want_delegator + want_validator
    # a Banff (permissionless) delegator at the same start comes after the validator
    banff = [("AddPermissionlessDelegatorTx", start, end, KILO), ("AddPermissionlessValidatorTx", start, end, 2 * MEGA)]
    rewards, _ = protocol.promote_pending_stakes(banff, GENESISTEST_SUPPLY)
    assert rewards[1] == protocol.potential_reward(2 * MEGA, 14 * DAY, GENESISTEST_SUPPLY)
    # an earlier start is promoted first whatever its priority
    early = [("AddPermissionlessDelegatorTx", start - timedelta(seconds=1), end, KILO), ("AddDelegatorTx", start, end, KILO)]
    rewards, _ = protocol.promote_pending_stakes(early, GENESISTEST_SUPPLY)
    assert rewards[0] == protocol.potential_reward(KILO, 14 * DAY + 1, GENESISTEST_SUPPLY)
    with pytest.raises(ModelError):
        protocol.promote_pending_stakes([("AddSubnetValidatorTx", start, end, KILO)], GENESISTEST_SUPPLY)


def test_stake_start_before_and_after_durango():
    # staker_tx_verification_test.go "start time too early" and standard_tx_executor_test.go "starts delegating at
    # current timestamp": before Durango a start equal to the chain time is rejected.
    chain = DURANGO - timedelta(days=1)
    second = timedelta(seconds=1)
    assert protocol.staker_start_time_error(chain, chain) == protocol.ERR_TIMESTAMP_NOT_BEFORE_START_TIME
    assert protocol.staker_start_time_error(chain, chain - second) == protocol.ERR_TIMESTAMP_NOT_BEFORE_START_TIME
    assert protocol.staker_start_time_error(chain, chain + second) is None
    assert protocol.effective_stake_start(chain, chain + timedelta(days=3)) == chain + timedelta(days=3)
    # from Durango the requested start is ignored and the stake starts at acceptance
    assert protocol.staker_start_time_error(DURANGO, DURANGO) is None
    assert protocol.effective_stake_start(DURANGO, DURANGO + timedelta(days=3)) == DURANGO


# KG9 L1 validators: continuous fee and the Subnet validator rules
MAX64 = 2**64 - 1


@pytest.mark.parametrize("min_price, excess, constant, expected", [
    # vms/components/gas/gas_test.go calculatePriceTests
    (1, 0, 1, 1), (1, 1, 1, 2), (1, 2, 1, 6), (1, 10_000, 10_000, 2), (1, 1_000_000, 10_000, MAX64),
    (10, 10_000_000, 1_000_000, 220_264), (MAX64, MAX64, 1, MAX64), (2**32 - 1, 1, 1, 11_674_931_546),
    (6_786_177_901_268_885_274, 1, 1, MAX64 - 11), (6_786_177_901_268_885_274, MAX64, MAX64, MAX64 - 1),
])
def test_gas_price_matches_avalanchego_vectors(min_price, excess, constant, expected):
    assert protocol.gas_price(min_price, excess, constant) == expected


# vms/platformvm/validators/fee/fee_test.go tests: min price 2,048, target 10,000, price doubling each day
FEE_TEST_CONFIG = ValidatorFeeConfig(20_000, 10_000, 2_048, 1_246_488_515)
MINUTE, HOUR, WEEK = 60, 3_600, 7 * DAY
FEE_VECTORS = [
    # (current, excess, target, seconds, cost, excess after)
    (10, 0, 10_000, MINUTE, 122_880, 0),
    (10_000, 0, 10_000, MINUTE, 122_880, 0),
    (10_000, 10_000 * DAY, 10_000, MINUTE, 245_760, 10_000 * DAY),
    (10_000, 1_246_488_515, 10_000, MINUTE, 334_020, 1_246_488_515),
    (15_000, 0, 10_000, MINUTE, 122_880, 5_000 * MINUTE),
    (9_000, 6 * HOUR * 1_000, 10_000, DAY, 177_321_939, 0),
    (10_000, 1_246_488_515, 10_000, DAY, 480_988_800, 1_246_488_515),
    (15_000, 0, 10_000, DAY, 211_438_809, 5_000 * DAY),
    (10_000, 0, 10_000, WEEK, 1_238_630_400, 0),
    (15_000, 0, 10_000, WEEK, 5_265_492_669, 5_000 * WEEK),
    (MAX64, 1, 0, 1, MAX64, MAX64),
    (2**32 - 1, 0, 0, 10, 1_948_429_840_780_833_612, (2**32 - 1) * 10),
]


@pytest.mark.parametrize("current, excess, target, seconds, cost, excess_after", FEE_VECTORS)
def test_l1_validator_fee_matches_avalanchego_vectors(current, excess, target, seconds, cost, excess_after):
    # TestStateAdvanceTime, TestStateCostOf, TestStateSecondsRemaining
    config = replace(FEE_TEST_CONFIG, target=target)
    assert protocol.fee_excess_after(current, excess, target, seconds) == excess_after
    assert protocol.l1_validator_fee_navax(current, excess, seconds, config) == cost
    assert protocol.l1_validator_seconds_remaining(current, excess, cost, WEEK, config) == seconds


@pytest.mark.parametrize("current, excess, seconds", [
    # TestStateCostOfOverflow
    (2**32 - 1, 0, MAX64), (10_000, 0, MAX64), (0, 0, MAX64), (0, 10_001, MAX64 // 2_048 + 1),
])
def test_l1_validator_fee_saturates(current, excess, seconds):
    assert protocol.l1_validator_fee_navax(current, excess, seconds, FEE_TEST_CONFIG) == MAX64


@pytest.mark.parametrize("current, min_price, limit", [
    # TestStateSecondsRemainingLimit
    (2**32 - 1, 0, 0), (10_001, 2_048, MAX64), (10_000, 2_048, 2_048 * (WEEK + 1)), (0, 2_048, 2_048 * (WEEK + 1)),
])
def test_l1_validator_seconds_remaining_limit(current, min_price, limit):
    config = replace(FEE_TEST_CONFIG, min_price_navax=min_price)
    assert protocol.l1_validator_seconds_remaining(current, 0, limit, WEEK, config) == WEEK


def test_mainnet_l1_validator_fee_at_minimum_price():
    # ACP-77: about 1.33 AVAX per validator per 30 days at the 512 nAVAX per second minimum
    month = protocol.l1_validator_fee_navax(0, 0, 30 * DAY)
    assert month == 512 * 30 * DAY
    assert round(month / protocol.NAVAX_PER_AVAX, 2) == 1.33


def test_subnet_validator_rules_around_acp77():
    start = HELICON_MAINNET
    end = start + timedelta(days=14)
    primary = (start - timedelta(days=1), end + timedelta(days=1))
    assert protocol.subnet_validator_admission_error(start, end, primary, subnet_converted=False) is None
    assert protocol.subnet_validator_admission_error(start, end, primary, subnet_converted=True) == protocol.ERR_IS_IMMUTABLE
    assert protocol.subnet_validator_admission_error(start, end, None, subnet_converted=False) == protocol.ERR_NOT_VALIDATOR
    short_primary = (primary[0], end - timedelta(seconds=1))
    assert protocol.subnet_validator_admission_error(start, end, short_primary, False) == protocol.ERR_PERIOD_MISMATCH
    # the 48-hour ACP-273 minimum is for Primary Network validators only
    assert protocol.subnet_validator_admission_error(start, start + timedelta(hours=48), primary, False) == protocol.ERR_STAKE_TOO_SHORT


# KG10 P-Chain transaction fee
TEST_WEIGHTS = (1, 2_000, 20_000, 10)  # txs/fee/calculator_test.go testDynamicWeights, price 1 nAVAX


@pytest.mark.parametrize("complexity, expected", [
    # calculator_test.go txTests: AddPermissionlessValidatorTx and AddPermissionlessDelegatorTx for the primary network
    (protocol.ADD_PERMISSIONLESS_VALIDATOR_TX_COMPLEXITY, 137_191),
    (protocol.ADD_PERMISSIONLESS_DELEGATOR_TX_COMPLEXITY, 106_499),
])
def test_p_chain_fee_matches_reference_transactions(complexity, expected):
    config = replace(protocol.MAINNET_P_CHAIN_FEE, weights=TEST_WEIGHTS)
    etna = protocol.MAINNET_UPGRADES.time("etna")
    assert protocol.p_chain_tx_fee_navax(complexity, 0, etna, config) == expected
    assert protocol.p_chain_tx_fee_navax(complexity, 0, etna - timedelta(seconds=1), config) == 0


def test_p_chain_fee_on_mainnet_parameters():
    etna = protocol.MAINNET_UPGRADES.time("etna")
    gas = 691 + 2 * 1_000 + 6 * 1_000 + 1_250 * 4
    assert protocol.p_chain_tx_fee_navax(protocol.ADD_PERMISSIONLESS_VALIDATOR_TX_COMPLEXITY, 0, etna) == gas
    # at the 1 nAVAX minimum the integer price stays 1 until excess passes K ln 2, then floor(e) = 2 at excess K
    assert protocol.p_chain_tx_fee_navax(protocol.ADD_PERMISSIONLESS_VALIDATOR_TX_COMPLEXITY, 1_500_000, etna) == gas
    assert protocol.p_chain_tx_fee_navax(protocol.ADD_PERMISSIONLESS_VALIDATOR_TX_COMPLEXITY, 2_164_043, etna) == 2 * gas
    with pytest.raises(ModelError):
        protocol.p_chain_gas((MAX64, 0, 0, 0), (2, 0, 0, 0))


@pytest.mark.parametrize("capacity, excess, max_capacity, rate, target, seconds, expected", [
    # vms/components/gas/state_test.go Test_State_AdvanceTime
    (10, 0, 20, 10, 0, 2, (20, 0)),  # cap capacity
    (10, 0, 30, 10, 0, 1, (20, 0)),  # increase capacity
    (10, 10, 20, 10, 10, 2, (20, 0)),  # avoid excess underflow
    (10, 10, 20, 10, 5, 1, (20, 5)),  # reduce excess
])
def test_p_chain_fee_state_matches_avalanchego(capacity, excess, max_capacity, rate, target, seconds, expected):
    config = replace(protocol.MAINNET_P_CHAIN_FEE, max_capacity=max_capacity, max_per_second=rate, target_per_second=target)
    assert protocol.p_chain_fee_state_after(capacity, excess, seconds, config) == expected


def test_p_chain_gas_consumption_matches_avalanchego():
    # vms/components/gas/state_test.go Test_State_ConsumeGas
    assert protocol.p_chain_consume_gas(10, 10, 5) == (5, 15)
    assert protocol.p_chain_consume_gas(10, 10, 10) == (0, 20)
    assert protocol.p_chain_consume_gas(10, MAX64, 1) == (9, MAX64)
    with pytest.raises(ModelError):
        protocol.p_chain_consume_gas(10, 10, 11)


# KG11 provenance for every mechanism
def test_describe_lists_every_catalogued_mechanism_with_pinned_sources():
    mechanisms = protocol.describe()["mechanisms"]
    acps = {item["acp"] for item in mechanisms}
    assert {"ACP-41", "ACP-62", "ACP-77", "ACP-103", "ACP-236", "ACP-247", "ACP-267", "ACP-273", "ACP-285"} <= acps
    names = " ".join(item["name"] for item in mechanisms)
    assert "Current supply" in names and "deferred" in names and "L1 validator fee" in names
    upgrades = {item.name for item in protocol.MAINNET_UPGRADES.upgrades}
    for item in mechanisms:
        assert item["upgrade"] is None or item["upgrade"] in upgrades
        assert all(source.startswith((protocol.AVALANCHEGO, protocol.ACPS)) for source in item["sources"])
