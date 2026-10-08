"""The evidence receipt of a model run, v0: it stands on intact pins and checks, and is refused otherwise."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from avalanche_research.core.catalog import DataError, canonical_bytes, sha256
from avalanche_research.datasets import pins
from avalanche_research.experiments import receipt

LEDGER = "derived.avax-monetary-daily"
CODE = {"commit": "0" * 40, "dirty": False, "package_version": "test"}
SPECIFICATION = {"model": "avalanche_research.model.example.Supply", "dt": 1.0, "timesteps": 2, "runs": 1, "rate": 0.1}


def make_run(root: Path, run: str, dataset_id: str) -> None:
    capture_dir, dataset_dir = root / run / "capture", root / run / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / "table.parquet"
    duckdb.connect().execute(f"COPY (SELECT '{run}' AS run) TO ? (FORMAT PARQUET)", [str(parquet)])
    capture_id = f"capture:test:{run}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({"capture_id": capture_id, "dataset_id": dataset_id, "completed_at": "2026-09-30T00:00:00Z"}))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({"dataset_id": dataset_id, "source_capture_id": capture_id, "completed_at": "2026-09-30T00:00:00Z",
                                                              "summary": {"rows": 1}, "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}]}))
    (dataset_dir / "check.json").write_bytes(canonical_bytes({"status": "pass"}))


@pytest.fixture
def pinned(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "runs"
    make_run(root, "ledger", LEDGER)
    pins.pin("m2", [LEDGER], root=root, directory=tmp_path / "pins")
    return root, tmp_path / "pins" / "m2.json"


def table(digest: str) -> pd.DataFrame:
    rows = [(0, 1, step, step * 1.0, variable, value, 0.1, digest) for step in (1, 2) for variable, value in (("supply", 100.0 + step), ("staked", 40.0))]
    return pd.DataFrame(rows, columns=["simulation", "run", "timestep", "time", "variable", "value", "rate", "specification"])


def made(pin_file: Path, frame: pd.DataFrame, conservation: list | None = None, code: dict | None = None) -> dict:
    checks = conservation if conservation is not None else [{"name": "supply identity", "passed": True, "worst_error": 0.0, "tolerance": 1e-9}]
    return receipt.build(frame, [SPECIFICATION], pin_file, [7], checks, "2026-09-30T00:00:00Z", "2026-09-30T00:00:01Z", 1.0, code or CODE, "run.parquet")


def test_the_specification_hash_is_the_engines():
    expected = hashlib.sha256(json.dumps(SPECIFICATION, sort_keys=True, default=str).encode()).hexdigest()[:16]
    assert receipt.specification_hash(SPECIFICATION) == expected


def test_a_receipt_on_intact_pins_is_written_and_checks_clean(pinned, tmp_path):
    root, pin_file = pinned
    frame = table(receipt.specification_hash(SPECIFICATION))
    value = made(pin_file, frame)
    assert value["inputs"]["runs"] == [{"dataset_id": LEDGER, "run": "ledger", "sha256": pins.read(pin_file)["runs"][0]["sha256"]}]
    assert value["output"]["rows"] == 4 and value["output"]["rows_by_variable"] == {"staked": 2, "supply": 2}
    # The table's hash does not depend on row order.
    assert receipt.table_sha256(frame.iloc[::-1]) == value["output"]["sha256"]
    path = receipt.write(value, tmp_path / "receipt.json", frame, root)
    assert json.loads(path.read_text())["receipt_id"] == value["receipt_id"]
    assert receipt.check(value, frame, root) == []


def test_a_receipt_whose_pins_fail_is_refused(pinned, tmp_path):
    root, pin_file = pinned
    frame = table(receipt.specification_hash(SPECIFICATION))
    value = made(pin_file, frame)
    parquet = root / "ledger" / "dataset" / "table.parquet"
    parquet.write_bytes(parquet.read_bytes() + b"\n")
    with pytest.raises(DataError, match=f"pin: {LEDGER} run ledger differs from its pin"):
        receipt.write(value, tmp_path / "receipt.json", frame, root)
    assert not (tmp_path / "receipt.json").exists()


def test_each_defect_is_named(pinned):
    root, pin_file = pinned
    frame = table(receipt.specification_hash(SPECIFICATION))
    failed = made(pin_file, frame, conservation=[{"name": "supply identity", "passed": False, "worst_error": 2.0, "tolerance": 1e-9}],
                  code={**CODE, "dirty": True})
    changed = frame.assign(value=frame["value"] + 1)
    assert receipt.check(failed, changed, root) == [
        "conservation check supply identity failed", "the code differed from commit 000000000000",
        "the table differs from the one the receipt describes"]
    edited = {**made(pin_file, frame), "seeds": [8]}
    assert receipt.check(edited, frame, root) == ["the receipt was edited after it was written"]
    with pytest.raises(DataError, match="specification column does not match"):
        made(pin_file, table("f" * 16))
