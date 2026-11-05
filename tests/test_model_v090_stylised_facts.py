import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from test_fitted_lifecycle import model as small_model
from test_stylised_facts import load_record

from avalanche_research.model.engine import run

ROOT = Path(__file__).resolve().parents[1]


def measurement():
    spec = importlib.util.spec_from_file_location("model_v090_stylised_facts", ROOT / "scripts" / "model_v090_stylised_facts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_both_models_carry_the_price_path_and_only_the_loops_model_reads_it():
    module = measurement()
    defaults, loops = module.settings(module.INCUMBENT, 20.0), module.settings(module.CHALLENGER, 20.0)
    for model in (defaults, loops):
        assert model["price0_usd"] == 20.0 and model["record_turnover"] is True
        assert {k: model[k] for k in module.PRICE_PATH} == module.PRICE_PATH
    assert "margin_response" not in defaults and loops["margin_response"] == module.LOOPS["margin_response"]
    assert module.DAYS == 1883 and str(module.ORIGIN) == "2025-10-01"


def test_a_price_path_without_the_margin_changes_no_other_output():
    price = {"price0_usd": 20.0, "price_drift_pa": 0.0, "price_volatility_pa": 0.84}
    plain = run(small_model(timesteps=30))
    priced = run(small_model(timesteps=30, **price))
    columns = ["simulation", "run", "timestep", "variable", "value"]
    pd.testing.assert_frame_equal(plain[columns].sort_values(columns[:4]).reset_index(drop=True),
                                  priced[columns].sort_values(columns[:4]).reset_index(drop=True))
    assert "price_usd" in priced.columns and "price_usd" not in plain.columns


def write_task(folder, module, model, path, batch=0, run_=1):
    files, _ = module.task_files(folder, model, batch)
    files.parent.mkdir(parents=True, exist_ok=True)
    frame = path.rename_axis("day").reset_index().assign(model=model, batch_seed=batch, run=run_, seed=run_ - 1)
    frame.to_csv(files, index=False, compression={"method": "gzip", "mtime": 0})
    return files


def test_the_measurement_reads_task_files_back_as_paths_and_scores_the_required_facts(tmp_path):
    module = measurement()
    record = load_record(labelled=False)
    files = [write_task(tmp_path, module, module.INCUMBENT, record),
             write_task(tmp_path, module, module.CHALLENGER, record.drop(columns=["renewed"]))]
    table, verdict = module.measure(files)
    assert set(table["model"]) == {module.INCUMBENT, module.CHALLENGER}
    # Each required part reports how many paths gave it a finite statistic.
    assert verdict[module.INCUMBENT] == {"required": ["SF4"], "failing": [], "passed": True, "paths": 1,
                                         "support": {"SF4 staked_26w": 1}}
    # Without renewals the loops model cannot run SF7, which it requires.
    assert verdict[module.CHALLENGER]["failing"] == ["SF7"] and verdict[module.CHALLENGER]["passed"] is False
    assert verdict[module.CHALLENGER]["support"]["SF7 renewal_pp_per_log_move"] == 0
    back = module.read_paths(files)[module.INCUMBENT][0]
    pd.testing.assert_index_equal(back.index, record.index, check_names=False)


SOURCES = {"periods_run": "periods", "periods_sha256": "a" * 64, "delegators_run": "delegators",
           "delegators_sha256": "b" * 64, "pin_sha256": "c" * 64, "price_pin_sha256": "d" * 64, "script_sha256": "e" * 64}


class Ran(Exception):
    """Raised by a stand-in variant, to show a task was computed rather than reused."""


class Computes:
    def prepare(self, *args, **kwargs):
        raise Ran


def cached_task(tmp_path, module, days, price0=20.0):
    """A finished task's files, as a run of ``days`` days at ``price0`` leaves them."""
    identity = module.task_identity(module.INCUMBENT, 0, days, price0, SOURCES)
    write_task(tmp_path, module, module.INCUMBENT, load_record(labelled=False))
    module.task_files(tmp_path, module.INCUMBENT, 0)[1].write_text("model\n")
    module.identity_file(tmp_path, module.INCUMBENT, 0).write_text(json.dumps(identity))
    return identity


def task(module, out, days, price0=20.0, sources=SOURCES):
    identity = module.task_identity(module.INCUMBENT, 0, days, price0, sources)
    return (module.INCUMBENT, 0, "periods", "periods.parquet", "delegators.parquet", days, out, price0, identity)


def test_a_full_request_refuses_a_rehearsals_cached_task(tmp_path, monkeypatch):
    module = measurement()
    monkeypatch.setitem(module.VARIANTS, module.VARIANT, Computes())
    cached_task(tmp_path, module, days=120)
    with pytest.raises(RuntimeError, match="days"):
        module.model_paths(task(module, tmp_path, module.DAYS))


def test_changed_inputs_or_price_refuse_a_cached_task(tmp_path, monkeypatch):
    module = measurement()
    monkeypatch.setitem(module.VARIANTS, module.VARIANT, Computes())
    cached_task(tmp_path, module, days=module.DAYS)
    with pytest.raises(RuntimeError, match="price0_usd"):
        module.model_paths(task(module, tmp_path, module.DAYS, price0=777.0))
    with pytest.raises(RuntimeError, match="periods_sha256"):
        module.model_paths(task(module, tmp_path, module.DAYS, sources={**SOURCES, "periods_sha256": "f" * 64}))


def test_a_stopped_run_resumes_from_tasks_of_the_same_request(tmp_path, monkeypatch):
    module = measurement()
    monkeypatch.setitem(module.VARIANTS, module.VARIANT, Computes())
    cached_task(tmp_path, module, days=module.DAYS)
    assert module.model_paths(task(module, tmp_path, module.DAYS)) == module.task_files(tmp_path, module.INCUMBENT, 0)


def test_a_task_without_its_identity_file_runs_again(tmp_path, monkeypatch):
    module = measurement()
    monkeypatch.setitem(module.VARIANTS, module.VARIANT, Computes())
    cached_task(tmp_path, module, days=module.DAYS)
    module.identity_file(tmp_path, module.INCUMBENT, 0).unlink()
    monkeypatch.setattr(module, "candidate_tables", lambda *args: None)
    with pytest.raises(Ran):
        module.model_paths(task(module, tmp_path, module.DAYS))


def test_a_rehearsal_refuses_a_folder_that_holds_a_verdict(tmp_path, monkeypatch):
    module = measurement()
    (tmp_path / "verdict.json").write_text("{}\n")
    monkeypatch.setattr(sys, "argv", ["script", str(tmp_path), "--pin", "pin.json", "--price-pin", "price.json", "--days", "120"])
    with pytest.raises(SystemExit, match="holds a verdict"):
        module.main()
