"""Real paired reproduction and integrity failures of the delivered small example."""

from __future__ import annotations

import csv
import io
import json
import shutil
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import first_experiment as subject


@pytest.fixture(scope="module")
def completed(tmp_path_factory):
    output = tmp_path_factory.mktemp("first-experiment") / "result"
    summary = subject.run(output, subject.EXAMPLE / "config.json")
    return output, summary


@pytest.fixture
def copied_example(tmp_path, monkeypatch):
    example = tmp_path / "example"
    shutil.copytree(subject.EXAMPLE, example)
    monkeypatch.setattr(subject, "EXAMPLE", example)
    return example


def test_released_model_reproduces_frozen_paired_result(completed):
    output, summary = completed
    expected = subject.read_json(subject.EXAMPLE / "expected.json")
    assert summary["model"]["variant"] == "v0.8.0"
    assert summary["pair_count"] == 4
    assert summary["metrics"] == pytest.approx(expected["metrics"], rel=subject.REL_TOL, abs=subject.ABS_TOL)
    assert summary["controls"]["neutral_response_stake_paths_equal"]
    assert summary["controls"]["protocol_counter_conservation"]
    assert len(subject.read_daily((output / "daily.csv").read_bytes(), summary["design"])) == 372
    figure = (output / "figure.html").read_text()
    assert "Cumulative validator reward promises" in figure
    assert "bokeh" in figure.lower()


def test_check_reads_complete_results_without_fitting_or_simulating(completed, monkeypatch):
    from avalanche_research.model import engine
    from avalanche_research.model.variants import Variant

    def forbidden(*args, **kwargs):
        raise AssertionError("check mode attempted computation")
    monkeypatch.setattr(Variant, "prepare", forbidden)
    monkeypatch.setattr(engine, "run", forbidden)
    assert subject.check(completed[0])["status"] == "complete"


def test_altered_input_is_rejected_before_model_or_output(copied_example, tmp_path, monkeypatch):
    path = copied_example / "inputs/validators.parquet"
    path.write_bytes(path.read_bytes() + b"altered")
    def forbidden(*args):
        raise AssertionError("changed input reached model")
    monkeypatch.setattr(subject, "execute", forbidden)
    output = tmp_path / "result"
    with pytest.raises(ValueError, match="changed input"):
        subject.run(output, copied_example / "config.json")
    assert not output.exists()


@pytest.mark.parametrize("mutation", ["future_acceptance", "duplicate_key"])
def test_semantic_snapshot_checks_refuse_even_rehashed_bad_data(copied_example, tmp_path, monkeypatch, mutation):
    path = copied_example / "inputs/validators.parquet"
    with duckdb.connect() as db:
        frame = db.execute("SELECT * FROM read_parquet(?)", [str(path)]).df()
        if mutation == "future_acceptance":
            frame.loc[0, "accepted_at"] = "2025-11-19 16:00:00"
        else:
            frame.loc[0, "transaction_hash"] = frame.loc[1, "transaction_hash"]
        changed = tmp_path / "changed.parquet"
        db.register("changed_frame", frame)
        db.execute("COPY changed_frame TO '" + str(changed).replace("'", "''") + "' (FORMAT PARQUET)")
    path.write_bytes(changed.read_bytes())
    monkeypatch.setitem(subject.INPUTS, "validators.parquet", subject.sha(path.read_bytes()))
    with pytest.raises(ValueError, match="row, key or information-cut"):
        subject.authenticate_inputs()


@pytest.mark.parametrize("damage", ["changed", "missing", "extra"])
def test_result_check_detects_incomplete_or_changed_artifacts(completed, tmp_path, damage):
    output = tmp_path / "result"
    shutil.copytree(completed[0], output)
    if damage == "changed":
        (output / "figure.html").write_text("changed figure")
    elif damage == "missing":
        (output / "comparison.csv").unlink()
    else:
        (output / "unexpected.csv").write_text("extra")
    with pytest.raises(ValueError, match="changed result artifact|missing files|unexpected entries"):
        subject.check(output)


def test_rehashed_false_comparison_is_not_accepted(completed, tmp_path):
    output = tmp_path / "result"
    shutil.copytree(completed[0], output)
    path = output / "comparison.csv"
    rows = list(csv.DictReader(io.StringIO(path.read_text())))
    rows[0]["baseline_promised_rewards_avax"] = float(rows[0]["baseline_promised_rewards_avax"]) + 100
    body = subject.csv_bytes(rows)
    path.write_bytes(body)
    summary = subject.read_json(output / "summary.json")
    summary["artifacts"]["comparison.csv"] = {"bytes": len(body), "sha256": subject.sha(body)}
    (output / "summary.json").write_bytes(subject.canonical(summary))
    with pytest.raises(ValueError, match="comparison does not follow daily"):
        subject.check(output)


@pytest.mark.parametrize("damage", ["malformed", "missing_column", "duplicate_column", "missing_run",
                                  "nonfinite", "fractional_seed", "negative_seed", "extra_cell"])
def test_rehashed_malformed_parameter_draws_are_refused(completed, tmp_path, damage):
    output = tmp_path / "result"
    shutil.copytree(completed[0], output)
    path = output / "parameter-draws.csv"
    table = list(csv.reader(io.StringIO(path.read_text())))
    if damage == "missing_column":
        table = [row[:-1] for row in table]
    elif damage == "duplicate_column":
        table[0][-1] = table[0][0]
    elif damage == "missing_run":
        table.pop()
    elif damage == "nonfinite":
        table[1][0] = "nan"
    elif damage == "fractional_seed":
        table[1][-1] = "1.5"
    elif damage == "negative_seed":
        table[1][-1] = "-1"
    elif damage == "extra_cell":
        table[1].append("unexpected")
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerows(table)
    body = b"not_a_draw_table\n" if damage == "malformed" else stream.getvalue().encode()
    path.write_bytes(body)
    summary = subject.read_json(output / "summary.json")
    summary["artifacts"]["parameter-draws.csv"] = {"bytes": len(body), "sha256": subject.sha(body)}
    (output / "summary.json").write_bytes(subject.canonical(summary))
    with pytest.raises(ValueError, match="parameter draw"):
        subject.check(output)


def test_relabelled_model_and_control_metadata_are_refused(completed, tmp_path):
    output = tmp_path / "result"
    shutil.copytree(completed[0], output)
    summary = subject.read_json(output / "summary.json")
    summary["model"]["variant"] = "v0.8.1"
    (output / "summary.json").write_bytes(subject.canonical(summary))
    with pytest.raises(ValueError, match="model identity"):
        subject.check(output)
    summary["model"]["variant"] = "v0.8.0"
    summary["controls"]["neutral_response_stake_paths_equal"] = False
    (output / "summary.json").write_bytes(subject.canonical(summary))
    with pytest.raises(ValueError, match="controls or declared tolerance"):
        subject.check(output)


def test_existing_output_refused_and_failed_run_has_no_complete_summary(completed, tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="new directory"):
        subject.run(completed[0], subject.EXAMPLE / "config.json")
    def failure(*args):
        raise ValueError("injected model failure")
    monkeypatch.setattr(subject, "execute", failure)
    output = tmp_path / "failed"
    with pytest.raises(ValueError, match="injected model failure"):
        subject.run(output, subject.EXAMPLE / "config.json")
    assert not (output / "summary.json").exists()
    with pytest.raises(ValueError, match="missing complete result"):
        subject.check(output)


def test_protected_origin_and_resource_expansion_are_refused(copied_example):
    path = copied_example / "custom.json"
    base = subject.read_json(copied_example / "config.json")
    for key, value in (("origin", "2025-11-19"), ("runs", 100), ("timesteps", 365), ("entry_response", float("inf"))):
        path.write_text(json.dumps({**base, key: value}))
        with pytest.raises(ValueError):
            subject.configuration(path)


def test_changed_frozen_expected_result_is_detected(completed, copied_example):
    path = copied_example / "expected.json"
    expected = subject.read_json(path)
    expected["metrics"]["rewards_saved_avax"] += 100
    path.write_bytes(subject.canonical(expected))
    with pytest.raises(ValueError, match="expected numerical result differs"):
        subject.check(completed[0])
