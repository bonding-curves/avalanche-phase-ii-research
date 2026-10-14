"""Report consumer regressions, independent of simulations and fitting."""

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from avalanche_research.analysis.report_summaries import (
    correction_summary_rows,
    found_label,
    paired_margin_fields,
    recommendation_reversal_fields,
    tree_top_input,
)


def test_margin_alias_uses_paired_bound_and_refuses_inconsistent_source():
    result = {"margin": .03, "accuracy_interval95": [.7, .9],
              "held_out_majority_baseline": {"raw_accuracy": .75},
              "paired_difference_interval95": [.03, .16]}
    assert paired_margin_fields(result)["Margin low (95%)"] == .03
    assert .7 - .75 != .03
    with pytest.raises(ValueError, match="paired lower bound"):
        paired_margin_fields(result | {"margin": -.05})
    assert paired_margin_fields({"margin": None})["Margin low (95%)"] is None


@pytest.mark.parametrize("status,flag,label", [("found", True, "found"),
    ("not_found", False, "not found"), ("unassessable", False, "unassessable")])
def test_found_labels_preserve_three_states(status, flag, label):
    assert found_label({"status": status, "found": flag}) == label


def test_found_label_refuses_contradictory_saved_result():
    with pytest.raises(ValueError, match="disagree"):
        found_label({"status": "found", "found": False})
    with pytest.raises(ValueError, match="unsupported"):
        found_label({"status": "missing", "found": False})


def test_descriptive_top_input_retains_ties_and_nonfits():
    result = {"status": "ok", "final_tree": {"impurity_importance": {"z": .4, "a": .4, "b": .2}}}
    assert tree_top_input(result)["Descriptive top input"] == "a; z"
    assert tree_top_input(result)["Top input status"] == "descriptive"
    assert tree_top_input({"status": "unassessable"})["Top input status"] == "unassessable"
    leaf = result | {"final_tree": {"impurity_importance": {"a": 0}}}
    assert tree_top_input(leaf)["Top input status"] == "no split"


def frames():
    accuracy = pd.DataFrame([{"Design family": "ramp", "Competing yield (%)": 5.,
        "Horizon (days)": 365, "Target type": "classification", "Measure": "issuance_saved",
        "Threshold alternative": "primary", "Cost level": "zero",
        "Descriptive top input": "entry_response", "Descriptive top input importance": .7,
        "Top input status": "descriptive", "Top input basis": "descriptive final fit"}])
    points = pd.DataFrame([{"family": "ramp", "yield_pp": 5., "horizon_days": 365,
        "population": "grid", "renewal_band": band, "entry_band": "middle",
        "input": "target_min_rate", "status": status} for band, status in
        [("low", "assessable"), ("middle", "assessable"), ("high", "unassessable")]])
    ranking = pd.DataFrame([{"Design": "ramp", "Competing yield (%)": 5.,
        "Horizon (days)": 365, "Renewal response": "middle", "Entry response": "middle",
        "Measure": "issuance_saved", "Order same at every yield": False}])
    return accuracy, points, ranking


def test_summary_cells_have_point_counts_tree_basis_and_pending_verdicts():
    rows = pd.DataFrame(correction_summary_rows(*frames())).set_index("Summary key")
    assert rows.loc["tiers.point-estimate.assessable.ramp.5.0.365", "Value"] == 2
    assert rows.loc["tiers.point-estimate.unassessable.ramp.5.0.365", "Value"] == 1
    assert rows.loc["tiers.point-estimate.not_applicable.ramp.5.0.365", "Value"] == 0
    for code in ["2.5", "2.6", "2.8"]:
        assert rows.loc["contract." + code, "Value"] == "pending owner verdict"
    top = rows[rows.index.str.startswith("MM2.top-input.")].iloc[0]
    assert top.Value == "entry_response"
    assert top.Status == "descriptive"
    assert json.loads(top["Source selector"])["Target type"] == "classification"
    rank = rows[rows.index.str.startswith("ranking.")].iloc[0]
    assert rank.Value == "no"
    assert rank["Source artifact"] == "figure-6-designs.csv"


@pytest.mark.parametrize("index", [0, 1, 2])
def test_summary_refuses_duplicate_scientific_identities(index):
    inputs = list(frames())
    inputs[index] = pd.concat([inputs[index], inputs[index].iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="repeated"):
        correction_summary_rows(*inputs)


def test_reversal_is_not_inferred_from_association_and_rows_are_traceable():
    base = {"family": "ramp", "yield_pp": 5., "horizon_days": 365,
            "population": "grid", "renewal_band": "low", "entry_band": "middle",
            "input": "target_min_rate", "source_index": 32}
    first = recommendation_reversal_fields(base, point=True)
    other = recommendation_reversal_fields(base | {"source_index": 99}, point=True)
    assert first["Response value that reverses it"] == "not determined"
    assert first["Recommendation source selector"] != other["Recommendation source selector"]
    assert json.loads(first["Recommendation source selector"])["source_index"] == 32
    assert "sign changes" in first["Reversal reason"]
    assert first["Recommendation source artifact"] == "point-estimates.csv"


def exporter():
    spec = importlib.util.spec_from_file_location("m2_report_exporter", Path(__file__).parents[1] / "scripts/m2_report_analysis.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_actual_exporter_refuses_nonempty_output_before_reading_inputs(tmp_path, monkeypatch):
    marker = tmp_path / "original.csv"
    marker.write_text("preserve these original bytes\n")
    argv = ["exporter"]
    for key in ["inputs", "numerics", "cart-prim", "decisions", "chrome"]:
        argv += ["--" + key, str(tmp_path / "not-read")]
    argv += ["--output", str(tmp_path)]
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(ValueError, match="new empty"):
        exporter().main()
    assert marker.read_text() == "preserve these original bytes\n"
