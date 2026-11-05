import hashlib
import importlib.util
import json
import os
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from avalanche_research import datasets
from avalanche_research.datasets import pins

ROOT = Path(__file__).resolve().parents[1]


def selection():
    spec = importlib.util.spec_from_file_location("model_v090_selection", ROOT / "scripts" / "model_v090_selection.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_origin_price_is_the_last_observed_by_the_origin_and_a_rebuilt_run_is_refused(tmp_path, monkeypatch):
    # RV04's witness: a price run rebuilt under its pinned name with other bytes must not be read.
    s = selection()
    root, run, capture, dataset = tmp_path / "runs", "synthetic-price", "capture:test:rv04-price", s.PRICE_DATASET
    out, cap = root / run / "dataset", root / run / "capture"
    out.mkdir(parents=True)
    cap.mkdir()
    monkeypatch.setattr(datasets, "RUNS", root)
    (cap / "capture.json").write_text(json.dumps({"capture_id": capture, "dataset_id": dataset, "completed_at": "2026-11-05T00:00:00Z"}))
    (out / "check.json").write_text(json.dumps({"status": "pass"}))
    parquet = out / "price.parquet"

    def write(prices, times):
        duckdb.from_df(pd.DataFrame({"observed_at": pd.to_datetime(times), "price_usd": prices})).write_parquet(str(parquet))
        body = parquet.read_bytes()
        (out / "build.json").write_text(json.dumps({"dataset_id": dataset, "source_capture_id": capture,
                                                    "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}]}))

    write([10.0, 2000.0], ["2024-03-01 20:00:00", "2024-03-02 00:00:00"])
    pins.pin("price", [dataset], {dataset: run}, root=root, directory=tmp_path)
    pin = tmp_path / "price.json"
    assert s.origin_price(pin, date(2024, 3, 1)) == 10.0
    write([999.0, 2000.0], ["2024-03-01 20:00:00", "2024-03-02 00:00:00"])
    with pytest.raises(ValueError, match="pins"):
        s.origin_price(pin, date(2024, 3, 1))


def test_each_worker_spills_to_its_own_folder():
    # A shared `.tmp` spill folder corrupted a 3-worker v0.8.1 reselection run on 5 November.
    module = selection()
    setting = "SELECT current_setting('temp_directory')"
    try:
        module.worker_setup()
        first = duckdb.execute(setting).fetchone()[0]
        module.worker_setup()
        second = duckdb.execute(setting).fetchone()[0]
    finally:
        for name in ("temp_directory", "memory_limit", "threads"):
            duckdb.execute(f"RESET {name}")
    assert first != second
    assert all(f"duckdb-spill-{os.getpid()}-" in Path(folder).name and Path(folder).is_dir() for folder in (first, second))
