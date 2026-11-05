import importlib.util
from pathlib import Path

import pandas as pd

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
    assert verdict[module.INCUMBENT] == {"required": ["SF4"], "failing": [], "passed": True, "paths": 1}
    # Without renewals the loops model cannot run SF7, which it requires.
    assert verdict[module.CHALLENGER]["failing"] == ["SF7"] and verdict[module.CHALLENGER]["passed"] is False
    back = module.read_paths(files)[module.INCUMBENT][0]
    pd.testing.assert_index_equal(back.index, record.index, check_names=False)
