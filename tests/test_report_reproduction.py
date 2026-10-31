"""Portable archive boundaries, independent scientific reductions and saved-result mutations."""

from __future__ import annotations

import shutil
import stat
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import reproduce_report as subject


def parquet(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    if "date_utc" in frame:
        frame["date_utc"] = pd.to_datetime(frame["date_utc"]).dt.date
    with duckdb.connect() as db:
        db.register("test_records", frame)
        db.execute("COPY test_records TO '" + str(path).replace("'", "''") + "' (FORMAT PARQUET)")


@pytest.fixture
def completed(tmp_path, monkeypatch):
    example, inputs, output = (tmp_path / name for name in ("example", "inputs", "output"))
    example.mkdir()
    inputs.mkdir()
    output.mkdir()
    design = subject.read_json(subject.EXAMPLE / "config.json")
    design.update(pairs=2, burn_navax_per_day=0.0, realized_supply_at_origin_navax=1e12)
    expected = subject.read_json(subject.EXAMPLE / "expected.json")
    expected.update(pair_count=2, daily_rows=1464)
    daily = []
    for cell in design["cells"]:
        for key in range(2):
            for day in range(366):
                issued = (10 if cell == "chain-central" else 9) if day else 0
                total = day * (10 if cell == "chain-central" else 9)
                daily.append({"cell": cell, "key": key, "seed": key + 1, "draw": key, "day": day,
                              "date": (date(2025, 11, 18) + timedelta(days=day)).isoformat(),
                              "active_validators": 10 if cell == "chain-central" or not day else 9,
                              "validator_stake_navax": 100000 if cell == "chain-central" or not day else 90000,
                              "supply_counter_navax": design["supply0_navax"] + total,
                              "issued_day_navax": issued, "cumulative_issued_navax": total,
                              "realized_supply_navax": 1e12 + total})
    reference = [{key: value for key, value in row.items() if key != "key"} for row in daily]
    parquet(inputs / "central-reference.parquet", reference)
    parquet(inputs / "data/runs/avax-monetary-daily-2026-09-30/dataset/avax-monetary-daily.parquet",
            [{"date_utc": date(2025, 11, 18) - timedelta(days=364 - day), "burned_wei": 0,
              "total_supply_close_wei": str(10**21), "complete": True} for day in range(365)])
    (inputs / "counter.csv").write_text("start_time,accepted_at,supply_before_navax\n"
                                       "2025-11-18 23:56:46,2025-11-18 23:56:46,465370216397635557\n")
    source = inputs / "model-source/src/example.py"
    source.parent.mkdir(parents=True)
    source.write_text("# Authenticated fixture, never executed.\n")
    value = {"schema": "report-reproduction-inputs/v1", "release": subject.RELEASE,
             "archive": {"bytes": 1, "sha256": "0" * 64}, "model_source_commit": subject.MODEL_SOURCE,
             "members": {p.relative_to(inputs).as_posix(): subject.record(p) for p in inputs.rglob("*") if p.is_file()}}
    paired, quantiles = subject.comparison(daily, 2, design)
    expected["comparison"] = quantiles
    for name, data in (("config.json", design), ("expected.json", expected), ("input-manifest.json", value)):
        (example / name).write_bytes(subject.canonical(data))
    monkeypatch.setattr(subject, "EXAMPLE", example)
    monkeypatch.setattr(subject, "INPUT_MANIFEST_SHA256", subject.record(example / "input-manifest.json")["sha256"])
    execution = {"model_source_commit": subject.MODEL_SOURCE,
                 "prepared_specification_sha256": expected["prepared_specification_sha256"],
                 "original_execution_driver_identity": "unresolved", "clocks": subject.clock_inputs(inputs, design),
                 "archived_source_files": {name: item for name, item in value["members"].items()
                                           if name.startswith("model-source/")}}
    for name, body in (("daily.csv", subject.csv_bytes(daily)), ("paired.csv", subject.csv_bytes(paired)),
                       ("comparison.csv", subject.csv_bytes(quantiles)), ("configuration.json", subject.canonical(design)),
                       ("execution.json", subject.canonical(execution))):
        (output / name).write_bytes(body)
    summary = {"schema": "report-reproduction-result/v1", "status": "complete", "mode": "full", "pair_count": 2,
               "design": design, "inputs": value, "producing_files": subject.producing_files(),
               "tolerance": expected["tolerance"], "comparison": quantiles,
               "reference_comparison": subject.verify_reference(daily, daily, design, expected["tolerance"]),
               "artifacts": {name: subject.record(output / name) for name in subject.OUTPUTS}}
    (output / "summary.json").write_bytes(subject.canonical(summary))
    return inputs, output, design


def rebind(output, name):
    path = output / "summary.json"
    summary = subject.read_json(path)
    summary["artifacts"][name] = subject.record(output / name)
    path.write_bytes(subject.canonical(summary))


def test_check_authenticates_without_fitting_or_running_a_model(completed, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("saved readback attempted execution")
    monkeypatch.setattr(subject, "worker", forbidden)
    monkeypatch.setattr(subject.subprocess, "Popen", forbidden)
    assert subject.check_result(*completed[:2])["status"] == "complete"


def test_reduction_uses_per_pair_ratios_not_pooled_totals():
    design = {"cells": ["chain-central", "ramp-7.5-central"], "timesteps": 365}
    daily = [{"cell": cell, "key": key, "day": 365, "cumulative_issued_navax": value,
              "validator_stake_navax": value, "active_validators": value}
             for key, values in enumerate(((10, 9), (100, 50))) for cell, value in zip(design["cells"], values)]
    paired, quantiles = subject.comparison(daily, 2, design)
    assert [row["issuance_saved"] for row in paired] == pytest.approx([0.1, 0.5])
    assert [row["issuance_saved"] for row in quantiles] == pytest.approx([0.14, 0.3, 0.46])
    assert quantiles[1]["issuance_saved"] != pytest.approx(1 - 59 / 110)


@pytest.mark.parametrize("damage", ["missing", "changed", "extra", "symlink"])
def test_changed_input_dependencies_are_rejected(completed, damage):
    inputs, output, _ = completed
    target = inputs / "counter.csv"
    if damage == "missing":
        target.unlink()
    elif damage == "changed":
        target.write_text("different")
    elif damage == "extra":
        (inputs / "extra").write_text("extra")
    else:
        copy = inputs.parent / "counter-copy.csv"
        shutil.copyfile(target, copy)
        target.unlink()
        target.symlink_to(copy)
    with pytest.raises(ValueError, match="input|dependency"):
        subject.check_result(inputs, output)


@pytest.mark.parametrize("damage", ["value", "duplicate", "seed", "date", "columns", "nonfinite", "supply"])
def test_rehashed_daily_corruption_cannot_pass_saved_readback(completed, damage):
    inputs, output, design = completed
    rows = subject.read_daily((output / "daily.csv").read_bytes(), 2, design)
    if damage == "value":
        rows[9]["validator_stake_navax"] += 1
    elif damage == "duplicate":
        rows[9] = dict(rows[8])
    elif damage == "seed":
        rows[9]["seed"] += 1
    elif damage == "date":
        rows[9]["date"] = "2026-01-01"
    elif damage == "columns":
        for row in rows:
            row.pop("draw")
    elif damage == "nonfinite":
        rows[9]["realized_supply_navax"] = float("nan")
    else:
        rows[9]["realized_supply_navax"] += 1e8
    (output / "daily.csv").write_bytes(subject.csv_bytes(rows))
    rebind(output, "daily.csv")
    with pytest.raises(ValueError):
        subject.check_result(inputs, output)


@pytest.mark.parametrize("artifact", ["paired.csv", "comparison.csv", "execution.json"])
def test_rehashed_derived_artifact_corruption_is_rejected(completed, artifact):
    inputs, output, _ = completed
    path = output / artifact
    if artifact == "execution.json":
        value = subject.read_json(path)
        value["prepared_specification_sha256"] = "0" * 64
        path.write_bytes(subject.canonical(value))
    else:
        path.write_text("not_a_scientific_table\n")
    rebind(output, artifact)
    with pytest.raises(ValueError, match="differs|differ"):
        subject.check_result(inputs, output)


def test_execution_failure_has_no_complete_summary(completed, tmp_path, monkeypatch):
    class Failed:
        pid = 12345

        def wait(self, **kwargs):
            return 1
    monkeypatch.setattr(subject.subprocess, "Popen", lambda *a, **kw: Failed())
    monkeypatch.setattr(subject.os, "killpg", lambda *args: None)
    output = tmp_path / "failed"
    with pytest.raises(ValueError, match="worker failed"):
        subject.run_result(completed[0], output)
    assert not (output / "summary.json").exists()


def test_existing_result_is_not_overwritten(completed):
    with pytest.raises(ValueError, match="must be new"):
        subject.run_result(*completed[:2])


def test_failed_final_readback_removes_complete_marker(completed, tmp_path, monkeypatch):
    original = completed[1]

    class CompletedWorker:
        def __init__(self, command, **kwargs):
            output = Path(command[command.index("--output") + 1])
            for name in ("daily.csv", "execution.json"):
                shutil.copyfile(original / name, output / name)

        def wait(self, **kwargs):
            return 0

    def reject(*args):
        raise ValueError("final readback failed")

    monkeypatch.setattr(subject.subprocess, "Popen", CompletedWorker)
    monkeypatch.setattr(subject, "check_result", reject)
    output = tmp_path / "incomplete"
    with pytest.raises(ValueError, match="final readback failed"):
        subject.run_result(completed[0], output)
    assert not (output / "summary.json").exists()


def test_ledger_clock_ignores_every_post_origin_observation(completed):
    inputs, _, design = completed
    path = inputs / "data/runs/avax-monetary-daily-2026-09-30/dataset/avax-monetary-daily.parquet"
    before = subject.clock_inputs(inputs, design)
    rows = duckdb.execute("SELECT * FROM read_parquet(?)", [str(path)]).df().to_dict("records")
    rows.append({"date_utc": date(2025, 11, 19), "burned_wei": 999999999999999999,
                 "total_supply_close_wei": "999999999999999999999999", "complete": True})
    path.unlink()
    parquet(path, rows)
    assert subject.clock_inputs(inputs, design) == before


def test_changed_counter_observation_clock_is_rejected_even_at_same_value(completed):
    inputs, _, design = completed
    path = inputs / "counter.csv"
    path.write_text(path.read_text().replace("23:56:46", "23:59:59"))
    with pytest.raises(ValueError, match="counter observation"):
        subject.clock_inputs(inputs, design)


def test_incomplete_origin_ledger_day_is_rejected(completed):
    inputs, _, design = completed
    path = inputs / "data/runs/avax-monetary-daily-2026-09-30/dataset/avax-monetary-daily.parquet"
    rows = duckdb.execute("SELECT * FROM read_parquet(?)", [str(path)]).df().to_dict("records")
    rows[-1]["complete"] = False
    path.unlink()
    parquet(path, rows)
    with pytest.raises(ValueError, match="origin ledger"):
        subject.clock_inputs(inputs, design)


@pytest.mark.parametrize("name", ["../escape", "/escape", "a/../escape", "a\\escape", "a//escape"])
def test_archive_traversal_is_rejected_before_destination_creation(tmp_path, monkeypatch, name):
    archive = tmp_path / "input.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr(name, b"payload")
    value = {"archive": subject.record(archive), "members": {name: {"bytes": 7, "sha256": "0" * 64}}}
    monkeypatch.setattr(subject, "contract", lambda: value)
    destination = tmp_path / "output"
    with pytest.raises(ValueError, match="unsafe"):
        subject.extract_archive(archive, destination)
    assert not destination.exists()
    assert not (tmp_path / "escape").exists()


def test_archive_symlink_is_rejected_before_destination_creation(tmp_path, monkeypatch):
    archive = tmp_path / "input.zip"
    member = zipfile.ZipInfo("counter.csv")
    member.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr(member, b"outside")
    value = {"archive": subject.record(archive), "members": {"counter.csv": {"bytes": 7, "sha256": "0" * 64}}}
    monkeypatch.setattr(subject, "contract", lambda: value)
    with pytest.raises(ValueError, match="nonregular"):
        subject.extract_archive(archive, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_archive_wrong_hash_is_rejected_before_extraction(tmp_path, monkeypatch):
    archive = tmp_path / "input.zip"
    archive.write_bytes(b"not_the_authenticated_archive")
    monkeypatch.setattr(subject, "contract", lambda: {"archive": {"bytes": 1, "sha256": "0" * 64}})
    with pytest.raises(ValueError, match="archive hash"):
        subject.extract_archive(archive, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_saved_result_detects_current_producing_contract_change(completed):
    inputs, output, _ = completed
    path = subject.EXAMPLE / "expected.json"
    value = subject.read_json(path)
    value["prepared_specification_sha256"] = "0" * 64
    path.write_bytes(subject.canonical(value))
    with pytest.raises(ValueError, match="binding differs"):
        subject.check_result(inputs, output)
