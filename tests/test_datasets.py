from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pytest

from avalanche_research import cli, datasets
from avalanche_research.catalog import DataError, canonical_bytes, sha256


def make_run(root: Path, name: str, dataset_id: str, table: str, sql: str, captured_at: str) -> Path:
    capture_dir, dataset_dir = root / name / "capture", root / name / "dataset"
    capture_dir.mkdir(parents=True), dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / f"{table}.parquet"
    connection = duckdb.connect()
    try:
        connection.execute(f"COPY ({sql}) TO '{parquet}' (FORMAT PARQUET)")
        rows = connection.execute(f"SELECT COUNT(*) FROM ({sql})").fetchone()[0]
    finally:
        connection.close()
    capture_id = f"capture:test:{captured_at}:{name}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({"schema_version": "test-capture/v1", "capture_id": capture_id, "dataset_id": dataset_id, "completed_at": captured_at}))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({
        "schema_version": "test-build/v1", "dataset_id": dataset_id, "source_capture_id": capture_id, "completed_at": captured_at,
        "summary": {"rows": rows}, "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}],
    }))
    return root / name


@pytest.fixture
def root(tmp_path: Path) -> Path:
    make_run(tmp_path, "validators-old", "snowflake.primary-validator-stakes", "primary-validator-stakes",
             "SELECT 'v1' AS transaction_hash, 'NodeID-A' AS node_id, 1::BIGINT AS potential_reward_navax", "2026-09-13T00:00:00Z")
    make_run(tmp_path, "validators-new", "snowflake.primary-validator-stakes", "primary-validator-stakes",
             "SELECT * FROM (VALUES ('v1', 'NodeID-A', 1::BIGINT), ('v2', 'NodeID-B', NULL::BIGINT)) t(transaction_hash, node_id, potential_reward_navax)", "2026-09-14T00:00:00Z")
    make_run(tmp_path, "delegators", "snowflake.primary-delegator-stakes", "primary-delegator-stakes",
             "SELECT 'd1' AS transaction_hash, 'v2' AS validator_transaction_hash, TIMESTAMP '2021-01-01 00:00:00' AS accepted_at", "2026-09-14T01:00:00Z")
    (tmp_path / "stray").mkdir()
    return tmp_path


def test_runs_lists_newest_first_and_skips_incomplete_directories(root):
    listed = datasets.runs("snowflake.primary-validator-stakes", root)
    assert [item["run"] for item in listed] == ["validators-new", "validators-old"]
    assert listed[0]["rows"] == 2 and listed[0]["captured_at"] == "2026-09-14T00:00:00Z"
    assert {item["dataset_id"] for item in datasets.runs(root=root)} == {"snowflake.primary-validator-stakes", "snowflake.primary-delegator-stakes"}


def test_load_returns_typed_frames_and_pins_runs(root):
    frame = datasets.load("snowflake.primary-validator-stakes", root=root)
    assert list(frame["transaction_hash"]) == ["v1", "v2"] and str(frame["potential_reward_navax"].dtype) == "Int64"
    assert len(datasets.load("snowflake.primary-validator-stakes", run="validators-old", root=root)) == 1
    receipt = datasets.receipt("snowflake.primary-delegator-stakes", root=root)
    assert receipt["run"] == "delegators" and receipt["build"]["source_capture_id"] == receipt["capture"]["capture_id"]
    with pytest.raises(DataError, match="no built run"):
        datasets.load("coingecko.avax-market-daily", root=root)
    with pytest.raises(DataError, match="unknown dataset"):
        datasets.load("nothing.here", root=root)


def test_load_rejects_a_modified_parquet_file(root):
    parquet = root / "validators-new" / "dataset" / "primary-validator-stakes.parquet"
    parquet.write_bytes(parquet.read_bytes() + b" ")
    with pytest.raises(DataError, match="differs from its receipt"):
        datasets.load("snowflake.primary-validator-stakes", root=root)


def test_connect_exposes_one_view_per_built_dataset(root):
    assert set(datasets.views(root=root)) == {"validator_stakes", "delegator_stakes"}
    assert datasets.view_name("coingecko.avax-market-daily") == "avax_market_daily"
    connection = datasets.connect(root=root)
    try:
        joined = connection.execute(
            "SELECT d.transaction_hash, v.node_id FROM delegator_stakes d JOIN validator_stakes v ON v.transaction_hash = d.validator_transaction_hash"
        ).fetchall()
    finally:
        connection.close()
    assert joined == [("d1", "NodeID-B")]
    pinned = datasets.connect(run="validators-old", root=root)
    try:
        assert pinned.execute("SELECT COUNT(*) FROM validator_stakes").fetchone()[0] == 1
        with pytest.raises(duckdb.Error):
            pinned.execute("SELECT COUNT(*) FROM delegator_stakes")
    finally:
        pinned.close()


def test_cli_runs_lists_records(root, monkeypatch, capsys):
    monkeypatch.setattr(datasets, "RUNS", root)
    monkeypatch.setattr(sys, "argv", ["avalanche", "data", "runs", "snowflake.primary-validator-stakes"])
    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "validators-new" in out and "2 runs" in out
