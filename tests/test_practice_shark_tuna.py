"""Shark and tuna: the lecture's Euler step, and the conserved quantity's drift shrinking with the step."""

import pytest

pytest.importorskip("cadCAD")

from avalanche_research.model.engine import run
from avalanche_research.practice.shark_tuna import SharkTuna


def final(table, variable):
    return table[table["variable"] == variable].sort_values("timestep")["value"].iloc[-1]


def test_one_euler_step_from_two_sharks_and_three_tuna_is_the_lecture_value():
    table = run(SharkTuna(timesteps=1))
    assert final(table, "sharks") == pytest.approx(2.4)
    assert final(table, "tuna") == pytest.approx(2.7)


def test_the_conserved_quantity_drifts_less_as_the_step_shrinks():
    drifts = {}
    for dt in (0.01, 0.001):
        model = SharkTuna(dt=dt, timesteps=round(50 / dt))
        table = run(model)
        drifts[dt] = model.conserved(final(table, "sharks"), final(table, "tuna")) - model.conserved(2.0, 3.0)
    assert drifts[0.01] > drifts[0.001] > 0
    assert drifts[0.01] == pytest.approx(0.70, abs=0.02)
    assert drifts[0.001] == pytest.approx(0.056, abs=0.002)


def test_a_coarse_step_spirals_out_until_the_positivity_invariant_stops_it():
    from avalanche_research.model.engine import InvariantError

    with pytest.raises(InvariantError, match="populations positive"):
        run(SharkTuna(dt=0.1, timesteps=500))
