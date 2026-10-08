"""The fitted lifecycle's daily step as an ordered list of stages, without changing any result.

The expected hashes were recorded on the code before the daily step was split. A small lifecycle that uses every part
and reads a small table of parameter draws, with a renewal shift and a continuation resample in each row, must give
the same specification hash and the same simulated table. The draws are rounded to ten decimals and then to six
significant digits before the lifecycle reads them, and a negative zero becomes zero, since the fits' last digits
differ between processors.

The specification hash and table are compared as in test_parts_split, after the three settings added since the
recording.
"""

import pandas as pd
import pytest

pytest.importorskip("cadCAD")
pytest.importorskip("scipy")

from test_parameter_draws import synthetic_events
from test_parts_split import as_recorded, small_lifecycle, table_sha256

from avalanche_research.model.engine import run
from avalanche_research.model.fitted_lifecycle import FittedLifecycle, parameter_draws
from avalanche_research.model.variants import VARIANTS, Prepared

EXPECTED_SPECIFICATION_HASH = "5f4a4626852e1e5a"
RECORDED_SPECIFICATION_HASH = "76edf0402231e521"
EXPECTED_TABLE_SHA256 = "f31aa8731da06f569db1c4506287cd8517be6070303d5df2e3add5c0fc2a2b43"


def rounded_draws() -> pd.DataFrame:
    draws = parameter_draws(synthetic_events(), n=3, seed=4, tau=0.3, large_above_avax=1_000_000)
    floats = [c for c in draws.columns if draws[c].dtype.kind == "f"]
    return draws.assign(**{c: [float(f"{round(x, 10):.6g}") + 0.0 for x in draws[c]] for c in floats})


def drawn_lifecycle():
    base = small_lifecycle()
    return base.with_settings(
        runs=3, draws=rounded_draws(),
        moves=base.moves.assign(node_code=[0, 0, 1, 2, 2, 3, 4]),
        first_commitments=base.first_commitments.assign(node_code=[5, 6, 7]),
    )


def test_the_specification_hash_with_draws_is_unchanged():
    assert drawn_lifecycle().specification_hash() == EXPECTED_SPECIFICATION_HASH


def test_the_simulated_table_with_draws_is_unchanged():
    assert table_sha256(as_recorded(run(drawn_lifecycle()), RECORDED_SPECIFICATION_HASH)) == EXPECTED_TABLE_SHA256


def test_the_daily_step_runs_its_stages_in_order():
    names = [name for name, _ in FittedLifecycle.stages]
    assert names == ["renewal", "returns", "arrivals", "continuation", "rewards", "assembly"]


def test_the_stage_list_is_not_a_setting():
    assert "stages" not in FittedLifecycle.param.objects()
    assert "stages" not in small_lifecycle().specification()


def test_the_registry_names_the_variants_the_development_scores_run():
    assert list(VARIANTS) == ["v0.7", "v0.8", "v0.8 separate", "v0.8 u"]


def test_a_variant_builds_the_model_its_inputs_describe():
    base = drawn_lifecycle()
    inputs = {k: v for k, v in base.param.values().items() if k not in ("name", "timesteps", "runs", "seed", "draws")}
    prepared = Prepared(inputs, base.draws)
    built = VARIANTS["v0.8 u"].simulation(prepared, seed=base.seed, timesteps=base.timesteps, runs=base.runs, draws=base.draws)
    assert built.specification_hash() == EXPECTED_SPECIFICATION_HASH
