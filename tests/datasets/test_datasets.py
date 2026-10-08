from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pytest

from avalanche_research import cli, datasets
from avalanche_research.core.catalog import DataError, canonical_bytes, sha256


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
    assert set(datasets.views(root=root)) == {"validator_stakes", "delegator_stakes", "snowflake_primary_validator_stakes",
                                              "snowflake_primary_delegator_stakes"}
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


def test_a_bad_receipt_of_another_dataset_does_not_stop_a_listing(root):
    (root / "delegators" / "dataset" / "build.json").write_text("{not json")
    assert [item["run"] for item in datasets.runs("snowflake.primary-validator-stakes", root)] == ["validators-new", "validators-old"]
    with pytest.raises(DataError, match="unreadable receipt"):
        datasets.runs("snowflake.primary-delegator-stakes", root)


def test_a_run_built_from_another_capture_is_refused_not_skipped(root):
    capture = root / "validators-new" / "capture" / "capture.json"
    capture.write_bytes(canonical_bytes({"capture_id": "capture:other", "dataset_id": "snowflake.primary-validator-stakes",
                                         "completed_at": "2026-09-14T00:00:00Z"}))
    with pytest.raises(DataError, match="run validators-new: its build names capture"):
        datasets.load("snowflake.primary-validator-stakes", root=root)


def test_connect_closes_its_connection_when_a_run_fails(root, monkeypatch):
    opened = []
    real = duckdb.connect

    def tracking(*args, **kwargs):
        opened.append(real(*args, **kwargs))
        return opened[-1]

    monkeypatch.setattr(datasets.duckdb, "connect", tracking)
    parquet = root / "validators-new" / "dataset" / "primary-validator-stakes.parquet"
    parquet.write_bytes(parquet.read_bytes() + b" ")
    with pytest.raises(DataError):
        datasets.connect(root=root)
    with pytest.raises(duckdb.Error):
        opened[0].execute("SELECT 1")


def test_a_receipt_that_is_not_utf8_or_not_an_object_is_refused_with_its_path(root):
    build = root / "validators-new" / "dataset" / "build.json"
    for body in (b"\xff\xfe\x00", b"[1, 2]"):
        build.write_bytes(body)
        with pytest.raises(DataError, match="unreadable receipt: .*validators-new"):
            datasets.runs("snowflake.primary-validator-stakes", root)
        assert [item["run"] for item in datasets.runs("snowflake.primary-delegator-stakes", root)] == ["delegators"]


def test_a_run_whose_build_and_capture_name_different_datasets_is_refused(root):
    for receipt in ("capture/capture.json", "dataset/build.json"):
        path = root / "validators-new" / receipt
        kept = path.read_bytes()
        value = json.loads(kept)
        value["dataset_id"] = "snowflake.primary-delegator-stakes"
        path.write_bytes(canonical_bytes(value))
        with pytest.raises(DataError, match="run validators-new: its build names"):
            datasets.load("snowflake.primary-validator-stakes", root=root)
        path.write_bytes(kept)



def pin_file(root: Path, tmp_path: Path, dataset_id: str, run: str) -> Path:
    parquet = next((root / run / "dataset").glob("*.parquet"))
    body = parquet.read_bytes()
    capture = json.loads((root / run / "capture" / "capture.json").read_text())
    (root / run / "dataset" / "check.json").write_bytes(canonical_bytes({"status": "pass"}))
    path = tmp_path / "pin.json"
    path.write_bytes(canonical_bytes({"schema_version": "avalanche-pins/v1", "name": "pin", "pinned_at": "2026-10-08T00:00:00Z", "runs": [
        {"dataset_id": dataset_id, "run": run, "capture_id": capture["capture_id"], "captured_at": capture["completed_at"], "check": "pass",
         "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body)}]}))
    return path


def set_times(root: Path, run: str, captured_at: str | None = None, built_at: str | None = None) -> None:
    for receipt, field, value in (("capture/capture.json", "completed_at", captured_at), ("dataset/build.json", "completed_at", built_at)):
        if value is not None:
            path = root / run / receipt
            record = json.loads(path.read_text())
            record[field] = value
            path.write_bytes(canonical_bytes(record))


def test_colliding_short_names_keep_canonical_views_and_the_ambiguous_alias_is_refused(root, monkeypatch):
    make_run(root, "x-blocks", "x-chain-rpc.blocks", "blocks", "SELECT 1 AS x", "2026-09-14T00:00:00Z")
    make_run(root, "p-blocks", "p-chain-rpc.blocks", "blocks", "SELECT 2 AS x", "2026-09-14T00:00:00Z")
    names = datasets.views(root=root)
    assert "x_chain_rpc_blocks" in names and "p_chain_rpc_blocks" in names and "blocks" not in names
    connection = datasets.connect(root=root)
    try:
        assert connection.execute("SELECT x FROM p_chain_rpc_blocks").fetchone() == (2,)
        with pytest.raises(duckdb.CatalogException):
            connection.execute("SELECT * FROM blocks")
        provenance = dict(connection.execute("SELECT view_name, run FROM _provenance").fetchall())
        assert provenance["x_chain_rpc_blocks"] == "x-blocks" and provenance["validator_stakes"] == "validators-new"
    finally:
        connection.close()


def test_a_pinned_read_ignores_a_newer_run(root, tmp_path):
    pin = pin_file(root, tmp_path, "snowflake.primary-validator-stakes", "validators-old")
    make_run(root, "validators-newest", "snowflake.primary-validator-stakes", "primary-validator-stakes", "SELECT 'v9' AS transaction_hash",
             "2026-09-20T00:00:00Z")
    chosen = datasets.select_run("snowflake.primary-validator-stakes", pin=pin, root=root)
    assert chosen["run"] == "validators-old" and chosen["rule"] == "pin" and chosen["capture_id"].endswith("validators-old")


def test_a_later_rebuild_of_an_older_capture_does_not_outrank_a_newer_capture(root):
    set_times(root, "validators-old", built_at="2026-10-01T00:00:00Z")
    assert datasets.runs("snowflake.primary-validator-stakes", root)[0]["run"] == "validators-new"
    assert datasets.select_run("snowflake.primary-validator-stakes", newest=True, root=root)["run"] == "validators-new"


def test_capture_times_compare_in_utc_across_offsets(root):
    set_times(root, "validators-old", captured_at="2026-09-14T06:00:00+08:00")
    set_times(root, "validators-new", captured_at="2026-09-13T23:00:00-02:00")
    assert datasets.select_run("snowflake.primary-validator-stakes", newest=True, root=root)["run"] == "validators-new"


@pytest.mark.parametrize("value", [None, "not a time", "2026-09-14T00:00:00"])
def test_a_missing_or_unreadable_capture_time_requires_an_exact_run(root, value):
    path = root / "validators-old" / "capture" / "capture.json"
    record = json.loads(path.read_text())
    record["completed_at"] = value
    path.write_bytes(canonical_bytes(record))
    with pytest.raises(DataError, match="name the run exactly"):
        datasets.select_run("snowflake.primary-validator-stakes", newest=True, root=root)
    assert datasets.select_run("snowflake.primary-validator-stakes", run="validators-old", root=root)["rule"] == "run"


def test_a_tied_latest_capture_time_requires_an_exact_run(root):
    set_times(root, "validators-old", captured_at="2026-09-14T00:00:00Z")
    with pytest.raises(DataError, match="share the latest capture time"):
        datasets.select_run("snowflake.primary-validator-stakes", newest=True, root=root)


def test_a_corrupted_newest_run_raises_with_its_identity_and_never_falls_back(root):
    parquet = root / "validators-new" / "dataset" / "primary-validator-stakes.parquet"
    parquet.write_bytes(parquet.read_bytes() + b" ")
    with pytest.raises(DataError, match="validators-new"):
        datasets.select_run("snowflake.primary-validator-stakes", newest=True, root=root)
    with pytest.raises(DataError, match="exactly one"):
        datasets.select_run("snowflake.primary-validator-stakes", root=root)


def test_a_pinned_read_refuses_when_the_code_the_pin_names_does_not_resolve(root, tmp_path):
    pin = pin_file(root, tmp_path, "snowflake.primary-validator-stakes", "validators-old")
    record = json.loads(pin.read_text())
    record["code"] = {"client_commit": "0" * 40}
    pin.write_bytes(canonical_bytes(record))
    with pytest.raises(DataError, match="does not resolve"):
        datasets.select_run("snowflake.primary-validator-stakes", pin=pin, root=root)


def test_an_automatic_reading_takes_the_newest_capture_in_utc_across_offsets(root):
    set_times(root, "validators-old", captured_at="2026-09-14T06:00:00+08:00")
    set_times(root, "validators-new", captured_at="2026-09-13T23:00:00-02:00")
    found = datasets.readings({"previous": "snowflake.primary-validator-stakes"}, {"previous": "auto"}, root)
    assert found["previous"]["run"] == "validators-new"


def test_a_read_without_a_run_keeps_the_newest_build_route(root):
    set_times(root, "validators-old", built_at="2026-10-08T00:00:00Z")
    assert datasets.receipt("snowflake.primary-validator-stakes", root=root)["run"] == "validators-old"
    assert datasets.select_run("snowflake.primary-validator-stakes", newest=True, root=root)["run"] == "validators-new"
