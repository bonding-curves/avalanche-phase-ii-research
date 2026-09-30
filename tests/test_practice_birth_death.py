"""Birth and death: the lecture's change vectors, the doubling time, and the Euler iteration exactly."""

import math

import pytest

pytest.importorskip("cadCAD")

from avalanche_research.model.engine import run
from avalanche_research.practice.birth_death import BirthDeath


def test_change_vectors_are_the_lecture_values():
    growth_only = BirthDeath(birth_rate=0.2, death_rate=0.0)
    assert growth_only.change(10) == pytest.approx(2.0)
    assert growth_only.change(100) == pytest.approx(20.0)


def test_doubling_time_with_net_rate_one_tenth():
    assert BirthDeath().doubling_time() == pytest.approx(6.93, abs=0.005)


def test_simulation_equals_the_euler_iteration_and_approaches_the_exact_curve():
    model = BirthDeath()
    table = run(model)
    values = table.sort_values("timestep")["value"].tolist()
    assert values[-1] == pytest.approx(model.euler(1000), rel=1e-12)
    assert values[-1] == pytest.approx(10 * math.exp(0.1 * 10), rel=1e-3)


def test_deaths_above_births_decay_toward_zero():
    table = run(BirthDeath(birth_rate=0.1, death_rate=0.3, timesteps=5000))
    assert table.sort_values("timestep")["value"].iloc[-1] == pytest.approx(10 * math.exp(-0.2 * 50), rel=1e-2)
