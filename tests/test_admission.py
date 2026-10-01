"""Admission mechanisms: the chain's flat minimum and Hash's bounded harmonic frontier."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from avalanche_research.mechanisms import BoundedHarmonicFrontier, ChainAdmission
from avalanche_research.model.protocol import validator_admission_error
from avalanche_research.model.types import SECONDS_PER_DAY

AVAX = 10**9
BEFORE = datetime(2025, 6, 1, tzinfo=UTC)
AFTER = datetime(2026, 9, 30, tzinfo=UTC)


@pytest.mark.parametrize("start", [BEFORE, AFTER])
@pytest.mark.parametrize("stake_avax", [1_999, 2_000, 50_000, 3_000_001])
@pytest.mark.parametrize("days", [1, 2, 13, 14, 90, 365, 366])
def test_chain_admission_agrees_with_the_kernel(start, stake_avax, days):
    from datetime import timedelta

    kernel = validator_admission_error(stake_avax * AVAX, 20_000, start, start + timedelta(days=days)) is None
    assert ChainAdmission().admits(stake_avax * AVAX, days * SECONDS_PER_DAY, start) == kernel


def test_frontier_interpolates_both_ends_and_keeps_the_axioms_at_p_one_and_above():
    for p in (1.0, 1.5, 3.0):
        frontier = BoundedHarmonicFrontier(p=p)
        assert frontier.min_stake_avax(2) == pytest.approx(7_000)
        assert frontier.min_stake_avax(365) == pytest.approx(1_000)
        assert frontier.check(AFTER) == []


def test_frontier_reports_the_axioms_it_breaks():
    assert "the short-duration stake is not above the floor" in BoundedHarmonicFrontier(s_short_avax=500, s_floor_avax=1_000).check(AFTER)
    with pytest.raises(ValueError):
        BoundedHarmonicFrontier(d_min_days=30, d_max_days=14)


def test_frontier_admits_by_duration():
    frontier = BoundedHarmonicFrontier(p=1.0)
    assert frontier.admits(7_000 * AVAX, 2 * SECONDS_PER_DAY, AFTER)
    assert not frontier.admits(6_000 * AVAX, 2 * SECONDS_PER_DAY, AFTER)
    assert frontier.admits(1_000 * AVAX, 365 * SECONDS_PER_DAY, AFTER)
    assert not ChainAdmission().admits(1_000 * AVAX, 365 * SECONDS_PER_DAY, AFTER)


def test_admitted_marks_a_table_of_stakes():
    stakes = pd.DataFrame(
        {"stake_navax": [2_000 * AVAX, 2_000 * AVAX], "duration_seconds": [2 * SECONDS_PER_DAY, 365 * SECONDS_PER_DAY], "start": [AFTER, AFTER]}
    )
    marked = BoundedHarmonicFrontier().admitted(stakes)
    assert marked["admitted"].tolist() == [False, True]


def test_curve_and_sybil_parity():
    frontier = BoundedHarmonicFrontier()
    curve = frontier.curve()
    assert list(curve.columns) == ["mechanism", "duration_days", "min_stake_avax", "stake_days"]
    assert curve["duration_days"].min() == 2 and curve["duration_days"].max() == 365
    assert frontier.below_sybil_parity() == [d for d in curve["duration_days"] if frontier.min_stake_avax(d) * d < 28_000]


def test_a_flat_frontier_admits_exactly_what_the_chain_admits_after_helicon():
    flat = BoundedHarmonicFrontier(s_short_avax=2_000, s_floor_avax=2_000, d_min_days=2, d_max_days=365)
    for stake_avax in (1_999, 2_000, 2_500):
        for days in (2, 3, 14, 90, 365):
            assert flat.admits(stake_avax * AVAX, days * SECONDS_PER_DAY, AFTER) == ChainAdmission().admits(stake_avax * AVAX, days * SECONDS_PER_DAY, AFTER)
