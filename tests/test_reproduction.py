from __future__ import annotations

import pytest

from avalanche_research.model.protocol import MAINNET_REWARD
from avalanche_research.model.types import ModelError, NAVAX_PER_AVAX, RewardConfig, SECONDS_PER_DAY
from avalanche_research.reproduction import figure7_frame


STAKE = 1_000_000 * NAVAX_PER_AVAX
SUPPLY = 360_000_000 * NAVAX_PER_AVAX


def test_figure7_matches_source_formula_and_protocol_rounding():
    scenarios = {
        f"minimum {minimum / 10_000:g}%": RewardConfig(
            MAINNET_REWARD.max_consumption_rate,
            minimum,
            MAINNET_REWARD.minting_period_seconds,
            MAINNET_REWARD.supply_cap_navax,
        )
        for minimum in (100_000, 90_000, 80_000, 70_000)
    }
    durations = {"2 days": 2 * SECONDS_PER_DAY, "14 days": 14 * SECONDS_PER_DAY,
                 "half year": 365 * SECONDS_PER_DAY // 2, "full year": 365 * SECONDS_PER_DAY}

    frame = figure7_frame(scenarios, durations, stake_navax=STAKE, supply_navax=SUPPLY)

    assert len(frame) == len(scenarios) * len(durations)
    assert frame.loc[frame.scenario.eq("minimum 10%") & frame.duration.eq("14 days"),
                     "source_implied_return_pct"].item() == pytest.approx(0.3865040345, abs=1e-9)
    assert frame.loc[frame.scenario.eq("minimum 8%") & frame.duration.eq("14 days"),
                     "source_implied_return_pct"].item() == pytest.approx(0.3127340965, abs=1e-9)
    assert set(frame.loc[frame.duration.eq("full year"), "source_implied_return_pct"]) == {12.0}
    assert frame.rounding_gap_navax.ge(0).all()
    assert frame.rounding_gap_navax.lt(1).all()


def test_figure7_rejects_invalid_fixture():
    with pytest.raises(ModelError):
        figure7_frame({"baseline": MAINNET_REWARD}, {"one day": SECONDS_PER_DAY},
                      stake_navax=SUPPLY + 1, supply_navax=SUPPLY)
