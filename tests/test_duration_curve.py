"""The duration curve reproduces the chain's lines at its defaults and holds the bump curve's known shape."""

from datetime import UTC, datetime

import pytest

from avalanche_research.mechanisms import ACP285Ramp, ChainReward, DurationCurve, QuadraticReward
from avalanche_research.model.types import SECONDS_PER_DAY
from test_mechanisms import SUPPLY, stakes_table

ORIGIN = datetime(2025, 11, 18, 16, tzinfo=UTC)
BUMP = dict(bump_scale=1.274, bump_power=25.0)


def test_defaults_are_acp285s_target_line_from_the_first_day():
    table = stakes_table()
    line = DurationCurve().issuance_navax(table, SUPPLY)
    target = ACP285Ramp(activation=datetime(2020, 1, 1, tzinfo=UTC), ramp_days=1).issuance_navax(table, SUPPLY)
    assert abs(line - target) <= len(table)  # one nAVAX of rounding per stake at most


def test_min_rate_ten_percent_is_the_rule_before_helicon():
    table = stakes_table()
    before = DurationCurve(min_rate=0.10).issuance_navax(table, SUPPLY)
    chain = QuadraticReward(exponent=1.0, acp285=False).issuance_navax(table, SUPPLY)
    assert abs(before - chain) <= len(table)
    assert DurationCurve(min_rate=0.10).check(SUPPLY, ORIGIN) == []


def test_bump_curve_peaks_near_14_days_dips_near_60_and_rejoins_the_line():
    bump = DurationCurve(**BUMP)
    assert bump.rate(14) == pytest.approx(0.0951, abs=1e-4)
    assert bump.rate(30) == pytest.approx(0.0910, abs=1e-4)
    assert bump.rate(60) == pytest.approx(0.0848, abs=1e-4)
    assert bump.rate(60) < bump.rate(14)
    assert bump.rate(180) == pytest.approx(DurationCurve().rate(180), abs=1e-4)
    assert bump.rate(365) == pytest.approx(0.12, abs=1e-9)
    assert "annual rate falls as duration rises" in bump.check(SUPPLY, ORIGIN)


def test_flat_minimum_pays_the_floor_short_and_the_line_long_and_never_falls():
    flat = DurationCurve(floor=0.095)
    assert flat.rate(2) == pytest.approx(0.095)
    assert flat.rate(14) == pytest.approx(0.095)
    assert flat.rate(60) == pytest.approx(0.095)
    assert flat.rate(365) == pytest.approx(0.12)
    assert flat.rate(200) == pytest.approx(DurationCurve().rate(200))
    assert flat.check(SUPPLY, ORIGIN) == []


def test_the_run_prices_a_30_day_stake_with_the_curve():
    chain = ChainReward().annual_rate(30, SUPPLY, ORIGIN)
    acp = DurationCurve().annual_rate(30, SUPPLY, ORIGIN)
    bump = DurationCurve(**BUMP).annual_rate(30, SUPPLY, ORIGIN)
    flat = DurationCurve(floor=0.095).annual_rate(30, SUPPLY, ORIGIN)
    assert acp < bump < flat < chain
    seconds = 30 * SECONDS_PER_DAY
    reward = DurationCurve(**BUMP).potential_reward_navax(10**6 * 10**9, seconds, SUPPLY, ORIGIN)
    assert reward > 0


def test_settings_outside_bounds_raise():
    with pytest.raises(ValueError):
        DurationCurve(bump_scale=-1.0)
    with pytest.raises(ValueError):
        DurationCurve(floor=0.5)
