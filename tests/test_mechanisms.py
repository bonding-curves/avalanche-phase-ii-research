"""Each reward mechanism reproduces the chain at its neutral settings and keeps the required properties."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from avalanche_research.mechanisms import (
    ACP285Ramp,
    ChainReward,
    QuadraticReward,
    TenureBoost,
)
from avalanche_research.model.protocol import primary_network_reward
from avalanche_research.model.types import SECONDS_PER_DAY

AVAX = 10**9
SUPPLY = 470_000_000 * AVAX
HELICON = datetime(2026, 9, 22, 15, tzinfo=UTC)
STARTS = [
    datetime(2025, 6, 1, tzinfo=UTC),
    HELICON,
    HELICON + timedelta(days=45),
    HELICON + timedelta(days=120),
]
DURATIONS_DAYS = [2, 14, 30, 90, 180, 365]
STAKES_NAVAX = [2_000 * AVAX, 123_456_789_012, 3_000_000 * AVAX]


def stakes_table():
    rows = [
        {"stake_navax": stake, "duration_seconds": days * SECONDS_PER_DAY, "start": start}
        for stake in STAKES_NAVAX for days in DURATIONS_DAYS for start in STARTS
    ]
    return pd.DataFrame(rows)


@pytest.mark.parametrize("start", STARTS)
def test_chain_reward_equals_the_kernel_to_the_navax(start):
    chain = ChainReward()
    for stake in STAKES_NAVAX:
        for days in DURATIONS_DAYS:
            seconds = days * SECONDS_PER_DAY
            assert chain.potential_reward_navax(stake, seconds, SUPPLY, start) == primary_network_reward(start, seconds, stake, SUPPLY)


def test_acp285_defaults_are_the_chain_and_other_settings_differ_after_helicon():
    table = stakes_table()
    assert ACP285Ramp().issuance_navax(table, SUPPLY) == ChainReward().issuance_navax(table, SUPPLY)
    slower = ACP285Ramp(ramp_days=180)
    mid_ramp = HELICON + timedelta(days=45)
    assert slower.potential_reward_navax(2_000 * AVAX, 14 * SECONDS_PER_DAY, SUPPLY, mid_ramp) > ChainReward().potential_reward_navax(
        2_000 * AVAX, 14 * SECONDS_PER_DAY, SUPPLY, mid_ramp
    )
    before = datetime(2025, 6, 1, tzinfo=UTC)
    assert ACP285Ramp(target_min_rate=0.05).potential_reward_navax(2_000 * AVAX, 14 * SECONDS_PER_DAY, SUPPLY, before) == ChainReward().potential_reward_navax(
        2_000 * AVAX, 14 * SECONDS_PER_DAY, SUPPLY, before
    )


def test_tenure_boost_is_the_chain_at_zero_and_full_at_its_tenure():
    table = stakes_table()
    assert TenureBoost(boost_max=0.0).issuance_navax(table, SUPPLY) == ChainReward().issuance_navax(table, SUPPLY)
    boost = TenureBoost(boost_max=0.10, full_boost_periods=8)
    base = ChainReward().potential_reward_navax(2_000 * AVAX, 90 * SECONDS_PER_DAY, SUPPLY, HELICON)
    for periods, factor in [(0, 1.0), (4, 1.05), (8, 1.10), (20, 1.10)]:
        boosted = boost.potential_reward_navax(2_000 * AVAX, 90 * SECONDS_PER_DAY, SUPPLY, HELICON, periods)
        assert boosted == pytest.approx(base * factor, abs=1)


def test_quadratic_with_exponent_one_is_the_chain():
    table = stakes_table()
    assert QuadraticReward(exponent=1.0).issuance_navax(table, SUPPLY) == ChainReward().issuance_navax(table, SUPPLY)


def test_quadratic_pays_less_short_and_the_same_at_one_year():
    quadratic, chain = QuadraticReward(), ChainReward()
    for start in STARTS:
        assert quadratic.annual_rate(14, SUPPLY, start) < chain.annual_rate(14, SUPPLY, start)
        assert quadratic.annual_rate(365, SUPPLY, start) == pytest.approx(chain.annual_rate(365, SUPPLY, start), rel=1e-9)


def test_quadratic_at_equal_issuance_mints_what_the_chain_mints():
    table = stakes_table()
    matched = QuadraticReward().at_equal_issuance(table, SUPPLY)
    assert matched.scale > 1.0
    assert matched.issuance_navax(table, SUPPLY) == pytest.approx(ChainReward().issuance_navax(table, SUPPLY), rel=1e-6)


@pytest.mark.parametrize("mechanism", [ChainReward(), ACP285Ramp(), TenureBoost(), QuadraticReward()])
@pytest.mark.parametrize("start", STARTS)
def test_every_default_mechanism_keeps_the_required_properties(mechanism, start):
    assert mechanism.check(SUPPLY, start) == []


def test_curves_share_one_shape_for_plotting():
    curves = pd.concat([m.curve(SUPPLY, HELICON) for m in (ChainReward(), QuadraticReward())])
    assert list(curves.columns) == ["mechanism", "duration_days", "annual_rate"]
    assert set(curves["mechanism"]) == {"Chain today", "Quadratic curve"}


def test_settings_outside_bounds_raise():
    with pytest.raises(ValueError):
        ACP285Ramp(target_min_rate=0.5)
    with pytest.raises(ValueError):
        QuadraticReward(exponent=0.5)
    with pytest.raises(ValueError):
        TenureBoost(boost_max=-0.1)


def test_acp285_can_activate_at_any_scenario_date():
    origin = datetime(2025, 4, 8, tzinfo=UTC)
    early = ACP285Ramp(activation=origin)
    halfway = origin + timedelta(days=45)
    before = origin - timedelta(days=1)
    chain = ChainReward()
    assert early.config(before).min_consumption_rate == 100_000
    assert early.config(halfway).min_consumption_rate == 87_500
    assert early.config(origin + timedelta(days=200)).min_consumption_rate == 75_000
    assert early.potential_reward_navax(2_000 * AVAX, 14 * SECONDS_PER_DAY, SUPPLY, halfway) < chain.potential_reward_navax(2_000 * AVAX, 14 * SECONDS_PER_DAY, SUPPLY, halfway)
