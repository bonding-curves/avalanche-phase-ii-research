"""Mass action: conservation checked every step, and the equilibrium ratio kf / kb."""

import pytest

pytest.importorskip("cadCAD")

from avalanche_research.model.engine import run
from avalanche_research.practice.mass_action import MassAction


def finals(table):
    last = table[table["timestep"] == table["timestep"].max()]
    return dict(zip(last["variable"], last["value"]))


def test_equilibrium_ratio_is_kf_over_kb():
    values = finals(run(MassAction()))
    assert values["z"] / (values["x"] * values["y"]) == pytest.approx(2.0 / 0.5, rel=1e-4)


def test_totals_are_conserved_at_the_end():
    values = finals(run(MassAction()))
    assert values["x"] + values["z"] == pytest.approx(0.6)
    assert values["y"] + values["z"] == pytest.approx(0.4)


def test_the_equilibrium_does_not_depend_on_the_rate_scale():
    fast, slow = finals(run(MassAction(kf=4.0, kb=1.0))), finals(run(MassAction(kf=2.0, kb=0.5, timesteps=6000)))
    assert fast["z"] == pytest.approx(slow["z"], rel=1e-4)
