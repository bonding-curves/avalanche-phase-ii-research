"""Known-answer tests for the practice models and the engine that runs them."""

import math

import pytest

pytest.importorskip("cadCAD")

from avalanche_research.model.engine import run, sweep
from avalanche_research.practice.bathtub import Bathtub
from avalanche_research.practice.logistic import Logistic


def final(table, **where):
    rows = table
    for key, value in where.items():
        rows = rows[rows[key] == value]
    return rows.sort_values("timestep")["value"].iloc[-1]


def test_bathtub_euler_matches_the_catalog_value_at_forty_minutes():
    table = run(Bathtub())
    assert final(table) == pytest.approx(49.9845, abs=5e-5)
    assert Bathtub().exact(40.0) == pytest.approx(49.9832, abs=5e-5)


def test_bathtub_settles_at_inflow_over_k_for_every_swept_drain():
    table = sweep(Bathtub(timesteps=2000), {"k": [0.1, 0.2, 0.5]})
    for k in (0.1, 0.2, 0.5):
        assert final(table, k=k) == pytest.approx(10.0 / k, rel=1e-6)


def test_bathtub_euler_error_shrinks_with_the_step():
    errors = []
    for dt in (0.5, 0.1, 0.02):
        model = Bathtub(dt=dt, timesteps=round(10 / dt))
        errors.append(abs(final(run(model)) - model.exact(10.0)))
    assert errors[0] > errors[1] > errors[2]


def test_logistic_single_euler_step_is_the_lecture_value():
    table = run(Logistic(b=0.02, K=100.0, rabbits0=10.0, dt=0.1, timesteps=1))
    assert final(table) == pytest.approx(10.018, abs=1e-12)


def test_logistic_change_vectors_and_stable_equilibrium():
    model = Logistic()
    assert model.change(15) == pytest.approx(2.955)
    assert model.change(90) == pytest.approx(16.38)
    assert model.change(2000) == pytest.approx(-400)
    assert final(run(Logistic(timesteps=3000))) == pytest.approx(1000.0, rel=1e-6)
    assert model.equilibria() == {0.0: "unstable", 1000.0: "stable"}


def test_a_setting_outside_its_bounds_raises_before_any_run():
    with pytest.raises(ValueError):
        sweep(Bathtub(), {"k": [0.2, -0.1]})


def test_the_long_table_carries_settings_time_and_a_specification_hash():
    table = run(Bathtub(timesteps=10))
    assert {"simulation", "run", "timestep", "time", "variable", "value", "k", "inflow", "specification"} <= set(table.columns)
    assert table["time"].iloc[-1] == pytest.approx(1.0)
    assert table["specification"].nunique() == 1
    assert Bathtub(k=0.3).specification_hash() != Bathtub().specification_hash()
    assert math.isclose(table["value"].iloc[0], 0.0)
