"""Custody failures must refuse before additive export or frozen-source writes."""

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/m2_explainer_exports.py"
spec = importlib.util.spec_from_file_location("m2_explainer_exports", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_json(path, value):
    path.write_text(json.dumps(value))


@pytest.fixture
def bound_sources(tmp_path):
    inputs, decisions, report = [tmp_path / name for name in ("inputs", "decisions", "report")]
    for directory in (inputs, decisions, report):
        directory.mkdir()
    (inputs / "wide.parquet").write_bytes(b"authenticated saved cache")
    manifest = {"wide_sha256": module.sha(inputs / "wide.parquet")}
    write_json(inputs / "inputs-manifest.json", manifest)
    for name in module.DECISION_TABLES:
        (decisions / name).write_text("saved,values\n1,2\n")
    bindings = {name: module.sha(decisions / name) for name in module.DECISION_TABLES}
    write_json(decisions / "decisions-receipt.json", {"outputs": bindings})
    (report / "figure-5-points.csv").write_text("First input,Second input,Role\nr,e,A\nr,e,B\n")
    parent = {"inputs": manifest, "outputs": {"figure-5-points.csv": module.sha(report / "figure-5-points.csv")}, "decisions_receipt_sha256": module.sha(decisions / "decisions-receipt.json"), "decision_inputs": bindings}
    write_json(report / "analysis-receipt.json", parent)
    return inputs, module.sha(inputs / "inputs-manifest.json"), decisions, report, module.sha(report / "analysis-receipt.json")


def test_authenticated_saved_sources_are_accepted(bound_sources):
    manifest, parent, decision = module.authenticate(*bound_sources)
    assert manifest == parent["inputs"]
    assert decision["outputs"] == parent["decision_inputs"]


@pytest.mark.parametrize("directory,name", [
    (0, "inputs-manifest.json"), (0, "wide.parquet"),
    (2, "decisions-receipt.json"), (2, "pass-shares.csv"),
    (3, "analysis-receipt.json"), (3, "figure-5-points.csv"),
])
def test_mutated_source_bytes_refuse(bound_sources, directory, name):
    path = bound_sources[directory] / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        module.authenticate(*bound_sources)


def test_nested_source_paths_refuse(tmp_path):
    with pytest.raises(ValueError, match="flat relative"):
        module.authenticate_outputs(tmp_path, {"../elsewhere.csv": "bad"})


def test_set_alias_preserves_exact_original_cell_text():
    frame = pd.DataFrame({"First input": ["renewal_response"] * 2, "Second input": ["entry_response"] * 2, "Role": ["A", "B"], "Value": ["0.0000000000123", "False"]})
    result = module.points_with_set(frame)
    pd.testing.assert_frame_equal(result[frame.columns], frame)
    assert result.Set.tolist() == ["A", "B"]
    assert "Set" not in frame


@pytest.mark.parametrize("fault", ["missing_names", "empty_name", "wrong_role", "wrong_set"])
def test_invalid_dr5_contract_refuses(fault):
    frame = pd.DataFrame({"First input": ["r", "r"], "Second input": ["e", "e"], "Role": ["A", "B"]})
    if fault == "missing_names":
        frame = frame.drop(columns="First input")
    elif fault == "empty_name":
        frame.loc[0, "First input"] = ""
    elif fault == "wrong_role":
        frame.loc[0, "Role"] = "noise"
    else:
        frame["Set"] = ["B", "A"]
    with pytest.raises(ValueError):
        module.points_with_set(frame)


def test_nonempty_output_refuses_without_touching_sources(bound_sources, tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "keep"
    sentinel.write_text("preserve")
    before = {str(path): module.sha(path) for path in tmp_path.rglob("*") if path.is_file()}
    with pytest.raises(ValueError, match="new empty"):
        module.export(*bound_sources, output)
    assert before == {str(path): module.sha(path) for path in tmp_path.rglob("*") if path.is_file()}


def test_output_inside_saved_sources_refuses(bound_sources):
    with pytest.raises(ValueError, match="separate"):
        module.export(*bound_sources, bound_sources[0] / "new")
