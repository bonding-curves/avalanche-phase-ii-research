"""Design rows and the streaming sweep runner, on the lifecycle model with synthetic inputs."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cadCAD")

from avalanche_research.model import designs, runner
from avalanche_research.model.lifecycle import ValidatorLifecycle

VARIABLES = ("active_validators", "active_validator_stake_navax")
BIG = 2**53 + 1


def base(**overrides):
    values = {"initial_stakes": np.array([BIG, 20, 30, 40]), "initial_days_left": np.array([1, 2, 3, 100]),
              "draw_durations": np.array([5, 9]), "draw_stakes": np.array([7, 11]), "entry_rate_per_day": 1.5,
              "renewal_probability": 0.5, "timesteps": 6, "runs": 3, "inputs_source": "synthetic"}
    return ValidatorLifecycle(**{**values, **overrides})


def comparable(frame):
    return frame.drop(columns="worker_peak_mib").sort_values(["row_id", "run", "timestep", "variable"]).reset_index(drop=True)


def test_a_sobol_design_extends_and_resumes_to_the_same_rows():
    bounds = {"renewal_probability": (0.5, 0.9), "entry_rate_per_day": (1.0, 9.0)}
    eight, sixteen = list(designs.sobol(bounds, 3, 7)), list(designs.sobol(bounds, 4, 7))
    assert [designs.settings(r) for r in eight] == [designs.settings(r) for r in sixteen[:8]]
    assert list(designs.sobol(bounds, 4, 7, start=8)) == sixteen[8:]
    assert list(designs.sobol(bounds, 3, 7, start=0)) == eight


def test_cardinality_and_row_ids_are_checked_before_launch():
    rows = list(designs.cartesian({"renewal_probability": [0.2, 0.8], "seed": [0, 1]}))
    designs.check_cardinality(rows, 4)
    with pytest.raises(ValueError, match="not 5"):
        designs.check_cardinality(rows, 5)
    with pytest.raises(ValueError, match="repeats"):
        designs.check_cardinality(rows + [{**rows[0], "index": 9}], 5)
    assert designs.row_id(rows[0], "aa") == designs.row_id(dict(rows[0]), "aa") != designs.row_id(rows[0], "bb")
    assert designs.design_hash(rows, "aa") != designs.design_hash(rows[::-1], "aa")


def test_an_interrupted_and_resumed_sweep_equals_a_clean_one(tmp_path):
    rows = list(designs.cartesian({"renewal_probability": [0.2, 0.8], "seed": [0, 1, 2]}))
    clean = runner.run_sweep(base(), rows, tmp_path / "clean", VARIABLES, workers=2)
    assert clean["written"] == 6 and not clean["stopped"]
    first = runner.run_sweep(base(), rows, tmp_path / "resumed", VARIABLES, workers=2, in_flight=1, stop_after=2)
    assert first["stopped"] and 2 <= first["written"] < 6
    (tmp_path / "resumed" / ".stale.parquet.tmp").write_bytes(b"partial")
    second = runner.run_sweep(base(), rows, tmp_path / "resumed", VARIABLES, workers=2)
    assert second["skipped"] == first["written"] and second["written"] == 6 - first["written"]
    assert not list((tmp_path / "resumed").glob(".*.tmp"))
    pd.testing.assert_frame_equal(comparable(runner.read_sweep(tmp_path / "clean")), comparable(runner.read_sweep(tmp_path / "resumed")))


def test_whole_navax_above_two_to_the_53_stay_exact(tmp_path):
    rows = list(designs.cartesian({"renewal_probability": [1.0]}))
    runner.run_sweep(base(entry_rate_per_day=0.0, initial_days_left=np.array([10, 10, 10, 10])), rows, tmp_path, VARIABLES, workers=1)
    paths = runner.read_sweep(tmp_path)
    stake = paths[(paths.variable == "active_validator_stake_navax") & (paths.timestep == 1)].value
    assert str(paths.value.dtype) == "int64" and set(stake.map(int)) == {BIG + 90}


def test_a_swept_setting_that_moves_nothing_is_named(tmp_path):
    # Under the chain's own reward rule the yield gap is zero, so the response multiplies nothing.
    rows = list(designs.cartesian({"renewal_response": [0.0, 0.3], "renewal_probability": [0.3, 0.7]}))
    runner.run_sweep(base(), rows, tmp_path, VARIABLES, workers=2)
    assert designs.no_effect(runner.read_sweep(tmp_path), ["renewal_response", "renewal_probability"]) == ["renewal_response"]
