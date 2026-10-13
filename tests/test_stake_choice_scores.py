"""Independent controls for node provenance, paired scoring and calibration."""
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location("stake_choice_scores", Path(__file__).parents[1] / "scripts/stake_choice_scores.py")
SCORES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCORES)


def test_constant_probability_calibration_is_not_lost_by_quantile_binning():
    assert SCORES.expected_calibration_error(np.full(4, .8), np.array([1, 1, 0, 0])) == pytest.approx(.3)


def test_categorical_calibration_retains_bad_atom_even_with_many_empty_cells():
    law = np.zeros((4, 103))
    law[:, 0], law[:, 1] = .8, .2
    receipt = SCORES.calibration(law, np.array([0, 0, 1, 1]))
    assert receipt["atom_ece"] == pytest.approx(.3)
    assert receipt["maximum_cell_ece"] == pytest.approx(.3)
    assert receipt["mean_cell_ece"] == pytest.approx(.6 / 103)


def test_paired_bootstrap_keeps_nodes_grouped_and_direction_explicit():
    events = pd.DataFrame({"origin": ["a"] * 8, "node_id": ["n"] * 8, "delta": [-2.] * 8})
    result = SCORES.paired_bootstrap(events)
    assert result["p_no_better"] == 0
    assert result["delta_nll_interval95"] == [-2., -2.]
    events["delta"] = 2.
    assert SCORES.paired_bootstrap(events)["p_no_better"] == 1


def test_nonfinite_pairs_are_refused():
    with pytest.raises(ValueError):
        SCORES.paired_bootstrap(pd.DataFrame({"origin": ["a"], "node_id": ["n"], "delta": [np.nan]}))


def test_adapter_positions_recover_the_right_nodes_and_refuse_changed_clocks(tmp_path):
    from test_stake_decisions import ORIGIN, write_periods

    path = write_periods(tmp_path)
    tables = SCORES.stake_decisions(path, ORIGIN, "synthetic")
    metadata = SCORES.decision_metadata(path, ORIGIN, tables)
    assert metadata["renewal"].node_id.tolist() == ["A", "B"]
    assert metadata["return"].node_id.tolist() == ["A", "B"]
    tables["renewal"].iloc[0, tables["renewal"].columns.get_loc("decided_us")] += 1
    with pytest.raises(AssertionError):
        SCORES.decision_metadata(path, ORIGIN, tables)


def test_fit_bridge_rechecks_producer_hash_before_separate_consumer_encoding():
    row = (2000 * 10**9, 30, 2000 * 10**9, int(pd.Timestamp("2024-02-01").value // 1000))
    columns = list(SCORES.stake_decisions.__globals__["STAKE_DECISION_COLUMNS"])
    tables = {c: pd.DataFrame([row], columns=columns).astype(np.int64) for c in ("renewal", "return", "entry")}
    tables["entry"]["previous_stake_navax"] = 0
    for t in tables.values():
        t.attrs = {"sha256": hashlib.sha256(t.to_csv(index=False).encode()).hexdigest()}
    original = {c: dict(t.attrs) for c, t in tables.items()}
    SCORES.fit_part(tables, pd.Timestamp("2024-03-01").date(), "synthetic")
    assert {c: t.attrs for c, t in tables.items()} == original
    tables["renewal"].loc[0, "next_stake_navax"] += 1
    with pytest.raises(ValueError, match="changed"):
        SCORES.fit_part(tables, pd.Timestamp("2024-03-01").date(), "synthetic")
