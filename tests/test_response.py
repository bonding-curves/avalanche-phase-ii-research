"""The behaviour responses act on a design's change from the reward menu the blocks were fitted under.

Before Helicon the fitted menu is the chain's own rule, so the gap is the one the lifecycle models compute today, to
the bit. After Helicon the chain's rule has moved away from the fitted menu, so even the chain's own rule carries a
gap: ACP-285's change in the 30-day rate.
"""

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from avalanche_research.domain.protocol import MAINNET_REWARD
from avalanche_research.mechanisms import (
    ACP285Ramp,
    ChainReward,
    QuadraticReward,
    TenureBoost,
)
from avalanche_research.model.fitted_lifecycle import FittedLifecycle
from avalanche_research.model.lifecycle import ValidatorLifecycle
from avalanche_research.model.response import FittedMenu, response_gap_pp

AVAX = 10**9
SUPPLIES = [440_000_000 * AVAX, 470_000_000 * AVAX]
HELICON = datetime(2026, 9, 22, 15, tzinfo=UTC)
LOCKBOX = datetime(2025, 11, 19, 16, tzinfo=UTC)
YEAR_BEFORE_GRANITE = (datetime(2024, 11, 19, tzinfo=UTC), LOCKBOX)
PRE_HELICON_DAYS = [date(2021, 1, 4), date(2023, 6, 1), date(2024, 3, 7), date(2025, 4, 8), date(2025, 11, 18), date(2026, 9, 22)]
POST_HELICON_DAYS = [date(2026, 9, 23), date(2026, 10, 8), date(2026, 11, 6), date(2026, 12, 22), date(2027, 3, 1)]
TENURES = [0, 4]


def designs():
    return [
        ChainReward(),
        TenureBoost(boost_max=0.5),
        QuadraticReward(exponent=2.0),
        ACP285Ramp(activation=datetime(2025, 4, 8, 16, tzinfo=UTC)),
    ]


def menu():
    return FittedMenu.for_window(*YEAR_BEFORE_GRANITE)


@pytest.mark.parametrize("supply", SUPPLIES)
@pytest.mark.parametrize("day", PRE_HELICON_DAYS)
def test_before_helicon_the_gap_is_todays_gap_to_the_bit(day, supply):
    fitted = menu()
    for design in designs():
        lifecycle = ValidatorLifecycle(mechanism=design, supply0_navax=supply)
        fitted_lifecycle = FittedLifecycle(mechanism=design, supply0_navax=supply)
        for tenure in TENURES:
            gap = response_gap_pp(design, fitted, day, supply, tenure)
            assert gap.hex() == lifecycle.yield_gap_pp(day, tenure).hex()
            assert gap.hex() == fitted_lifecycle.yield_gap_pp(day, tenure).hex()


@pytest.mark.parametrize("supply", SUPPLIES)
@pytest.mark.parametrize("day", POST_HELICON_DAYS)
def test_after_helicon_the_chains_own_rule_carries_the_change_acp_285_made(day, supply):
    start = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
    before = datetime(2026, 9, 21, 12, tzinfo=UTC)
    change = (ChainReward().annual_rate(30, supply, start) - ChainReward().annual_rate(30, supply, before)) * 100
    for tenure in TENURES:
        gap = response_gap_pp(ChainReward(), menu(), day, supply, tenure)
        assert gap != 0.0
        assert gap < 0.0
        assert gap == change
        assert ValidatorLifecycle(supply0_navax=supply).yield_gap_pp(day, tenure) == 0.0


def test_the_gap_grows_along_the_ramp_and_holds_once_it_is_done():
    gaps = [response_gap_pp(ChainReward(), menu(), day, SUPPLIES[0], 0) for day in POST_HELICON_DAYS]
    assert gaps[0] > gaps[1] > gaps[2] > gaps[3]
    assert gaps[3] == gaps[4]
    full_ramp_pp = -2.5 * (1 - 30 / 365)
    assert gaps[4] == pytest.approx(full_ramp_pp * (720_000_000 * AVAX - SUPPLIES[0]) / SUPPLIES[0], rel=1e-6)


@pytest.mark.parametrize("day", PRE_HELICON_DAYS + POST_HELICON_DAYS)
def test_a_response_of_zero_changes_nothing(day):
    renewal_log_odds, entry_rate = np.log(0.8 / 0.2), 5.0
    for design in [*designs(), ACP285Ramp()]:
        for tenure in TENURES:
            gap = response_gap_pp(design, menu(), day, SUPPLIES[0], tenure)
            assert np.isfinite(gap)
            shift = 0.0 * gap
            assert shift == 0
            assert (renewal_log_odds + shift).hex() == renewal_log_odds.hex()
            assert (entry_rate * float(np.exp(shift))).hex() == entry_rate.hex()


def test_the_menu_is_the_rule_in_force_at_the_end_of_the_fitting_window():
    fitted = menu()
    assert fitted.fitted_at == LOCKBOX
    assert fitted.config(HELICON + timedelta(days=120)) == MAINNET_REWARD
    assert fitted.config(datetime(2021, 1, 1, tzinfo=UTC)) == MAINNET_REWARD
    early = FittedMenu.for_window(datetime(2021, 1, 1, tzinfo=UTC), datetime(2022, 1, 1, tzinfo=UTC))
    assert early.fitted_at == datetime(2022, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize("end", [LOCKBOX + timedelta(seconds=1), datetime(2026, 10, 1, tzinfo=UTC), HELICON + timedelta(days=1)])
def test_a_fitting_window_that_reaches_into_the_lockbox_is_refused(end):
    with pytest.raises(ValueError, match="lockbox"):
        FittedMenu.for_window(datetime(2024, 11, 19, tzinfo=UTC), end)


def test_an_empty_fitting_window_is_refused():
    with pytest.raises(ValueError, match="before its end"):
        FittedMenu.for_window(LOCKBOX, LOCKBOX)


def test_an_outside_yield_acts_on_its_change_from_the_fitting_window():
    """An outside yield enters as its change from its level over the fitting window, in points, subtracted from the
    gap. At the fitted level, or when no outside yield is given, the gap is the menu gap exactly."""
    menu = FittedMenu.for_window(*YEAR_BEFORE_GRANITE)
    day, supply = date(2025, 4, 8), SUPPLIES[0]
    plain = response_gap_pp(ChainReward(), menu, day, supply, 0)
    assert response_gap_pp(ChainReward(), menu, day, supply, 0, outside_yield_pp=4.2, fitted_outside_yield_pp=4.2) == plain
    assert response_gap_pp(ChainReward(), menu, day, supply, 0, outside_yield_pp=7.0, fitted_outside_yield_pp=4.2) == pytest.approx(plain - 2.8)
    assert response_gap_pp(ChainReward(), menu, day, supply, 0, outside_yield_pp=3.0, fitted_outside_yield_pp=4.2) == pytest.approx(plain + 1.2)
    with pytest.raises(ValueError):
        response_gap_pp(ChainReward(), menu, day, supply, 0, outside_yield_pp=7.0)
    with pytest.raises(ValueError):
        response_gap_pp(ChainReward(), menu, day, supply, 0, outside_yield_pp=float("nan"), fitted_outside_yield_pp=4.2)
