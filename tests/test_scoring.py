"""The ensemble CRPS: exact on small cases, and close to the normal distribution's closed form."""

from __future__ import annotations

import math
from statistics import NormalDist

import pytest

from avalanche_research.catalog import DataError
from avalanche_research.scoring import crps, skill


def normal_crps(mean: float, sd: float, realized: float) -> float:
    """Gneiting and Raftery (2007): sd * (z (2 Phi(z) - 1) + 2 phi(z) - 1 / sqrt(pi)), z = (y - mean) / sd."""
    z = (realized - mean) / sd
    return sd * (z * (2 * NormalDist().cdf(z) - 1) + 2 * NormalDist().pdf(z) - 1 / math.sqrt(math.pi))


def test_one_draw_scores_its_absolute_error_and_two_draws_are_exact():
    assert crps([0.3], 0.1) == pytest.approx(0.2)
    # E|X - y| = (1 + 1) / 2 = 1, E|X - X'| = (0 + 2 + 2 + 0) / 4 = 1, so 1 - 0.5.
    assert crps([-1.0, 1.0], 0.0) == pytest.approx(0.5)
    assert crps([1.0, -1.0], 0.0) == crps([-1.0, 1.0], 0.0)


@pytest.mark.parametrize("realized", [0.44, 0.40, 0.52])
def test_many_draws_approach_the_normal_closed_form(realized):
    # 20,000 evenly spaced quantiles of N(0.44, 0.02), a staking ratio forecast.
    draws = [NormalDist(0.44, 0.02).inv_cdf((rank + 0.5) / 20_000) for rank in range(20_000)]
    assert crps(draws, realized) == pytest.approx(normal_crps(0.44, 0.02, realized), rel=1e-3)


def test_skill_and_refusals():
    assert skill(0.01, 0.02) == pytest.approx(0.5)
    with pytest.raises(DataError):
        skill(0.01, 0.0)
    with pytest.raises(DataError):
        crps([], 1.0)
    with pytest.raises(DataError):
        crps([float("nan")], 1.0)
