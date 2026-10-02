from __future__ import annotations

import pytest
import pandas as pd

from avalanche_research.model.protocol import MAINNET_REWARD
from avalanche_research.model.types import ModelError, NAVAX_PER_AVAX, RewardConfig, SECONDS_PER_DAY
from avalanche_research.reproduction import figure7_frame, figure8_observed_bins


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


def test_figure8_observed_bins_keep_count_and_stake_weights_separate():
    commitments = pd.DataFrame({
        "duration_weeks": [2.0, 2.5, 3.0],
        "stake_avax": [1_000.0, 1_000.0, 8_000.0],
    })

    bins = figure8_observed_bins(commitments)

    assert bins.commitments.sum() == len(commitments)
    assert bins.self_stake_avax.sum() == commitments.stake_avax.sum()
    assert bins.commitment_share_pct.sum() == pytest.approx(100)
    assert bins.self_stake_share_pct.sum() == pytest.approx(100)
    two_weeks = bins.loc[bins.duration_interval.eq("[2, 3)")].iloc[0]
    three_weeks = bins.loc[bins.duration_interval.eq("[3, 4)")].iloc[0]
    assert two_weeks.commitments == 2
    assert two_weeks.self_stake_share_pct == pytest.approx(20)
    assert three_weeks.commitments == 1
    assert three_weeks.self_stake_share_pct == pytest.approx(80)


@pytest.mark.parametrize("bad", [
    pd.DataFrame(columns=["duration_weeks", "stake_avax"]),
    pd.DataFrame({"duration_weeks": [0], "stake_avax": [1]}),
    pd.DataFrame({"duration_weeks": [2], "stake_avax": [float("nan")]}),
])
def test_figure8_rejects_invalid_population(bad):
    with pytest.raises(ModelError):
        figure8_observed_bins(bad)
