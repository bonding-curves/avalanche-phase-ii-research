"""The Allee effect: three equilibria, their stability, and the threshold separating extinction from growth."""

import pytest

pytest.importorskip("cadCAD")

from avalanche_research.model.engine import run
from avalanche_research.practice.allee import Allee


def final(model):
    return run(model).sort_values("timestep")["value"].iloc[-1]


def test_slopes_at_the_equilibria_are_the_lecture_formulas():
    model = Allee()
    assert model.slope(0) == pytest.approx(-0.1)
    assert model.slope(20) == pytest.approx(0.1 * (1 - 20 / 100))
    assert model.slope(100) == pytest.approx(0.1 * (1 - 100 / 20))


def test_a_start_above_the_threshold_grows_to_capacity_and_below_it_dies_out():
    assert final(Allee(animals0=25)) == pytest.approx(100, abs=1e-3)
    assert final(Allee(animals0=15)) == pytest.approx(0, abs=1e-3)


def test_a_start_at_the_threshold_stays_there():
    assert final(Allee(animals0=20, timesteps=100)) == pytest.approx(20)
