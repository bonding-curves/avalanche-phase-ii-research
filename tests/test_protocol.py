from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pytest

from avalanche_research.model import protocol
from avalanche_research.model.backtest import backtest
from avalanche_research.model.types import ModelError, RewardConfig, Upgrade, UpgradeSchedule


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
