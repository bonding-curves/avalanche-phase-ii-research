"""The released v0.8.0 model's structure diagram: traced from the model's own stages, and valid Graphviz."""

import re
import shutil
import subprocess

import pytest

from avalanche_research.model.parts.return_hazard import ReturnLogitHazard
from avalanche_research.model.variants import VARIANTS
from avalanche_research.views.model_structure import (
    fitted_lifecycle_dot,
    tiny_stake_lifecycle,
    trace_stages,
)


def test_the_diagram_names_every_stage_in_the_model_order():
    model = tiny_stake_lifecycle()
    assert type(model) is VARIANTS["v0.8.0"].model
    order = [name for name, _stage in model.stages]
    dot = fitted_lifecycle_dot(model)
    drawn = re.findall(r'<TD PORT="([a-z_]+)"', dot)
    assert drawn == order
    for i, name in enumerate(order, 1):
        assert f"<B>{i}. {name}</B>" in dot


def test_the_trace_reads_the_released_blocks():
    model = tiny_stake_lifecycle()
    assert isinstance(model.returns, ReturnLogitHazard) and model.fitted_stake
    stages = {s.name: s for s in trace_stages(model)}
    assert [s for s in stages] == [name for name, _stage in model.stages]
    assert stages["continuation"].reads_model == ["stake_choice"]
    assert stages["renewal"].reads_settings == ["renewal_response"]
    assert stages["arrivals"].reads_settings == ["entry_response", "unstaked_share0", "participation_elasticity"]
    assert stages["rewards"].reads_settings == ["mechanism"]
    assert stages["assembly"].reads_settings == ["scheduled"]
    # The model's stages are restored after the trace.
    assert "stake_continuation" in dict(model.stages)["continuation"].__name__


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz is a system package")
def test_the_diagram_parses():
    result = subprocess.run(["dot", "-Tsvg"], input=fitted_lifecycle_dot(), capture_output=True, text=True, check=True)
    assert result.stdout.lstrip().startswith("<?xml") and not result.stderr


def test_the_released_model_has_no_large_holder_renewal_block():
    model = tiny_stake_lifecycle()
    assert model.renewal_large is None and model.large_above_avax is None
    assert "renewal_large" not in fitted_lifecycle_dot(model)


def test_a_state_variable_without_a_place_stops_the_drawing():
    model = tiny_stake_lifecycle()
    initial, blocks = model.initial_state, model.blocks

    def with_stock():
        b = blocks()
        b[0]["variables"]["unplaced_stock"] = lambda p, s, h, state, signal: ("unplaced_stock", state["unplaced_stock"])
        return b

    model.initial_state = lambda: {**initial(), "unplaced_stock": 1}
    model.blocks = with_stock
    with pytest.raises(KeyError, match="unplaced_stock"):
        fitted_lifecycle_dot(model)
