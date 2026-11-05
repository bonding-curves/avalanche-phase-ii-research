"""Operator clusters, built from small staking-period, validator-stake and minipool-record runs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from avalanche_research.core.catalog import (
    DataError,
    canonical_bytes,
    dataset,
    load_catalog,
    sha256,
)
from avalanche_research.datasets.derived import operator_clusters

POOL = "avax1pool"
OWNER_A, OWNER_B = "0x" + "aa" * 20, "0x" + "bb" * 20
# transaction, node, accepted (and start), end, fee, reward address
PERIODS = [
    ("t1", "NodeID-M1", "2024-12-02 10:00:00", "2024-12-17 10:00:00", 0.02, POOL),  # before M1's record began: carried back
    ("t2", "NodeID-M1", "2025-02-03 10:00:00", "2025-02-18 10:00:00", 0.02, POOL),
    ("t3", "NodeID-M2", "2025-03-03 10:00:00", "2025-03-18 10:00:00", 0.02, POOL),
    ("t4", "NodeID-M3", "2025-04-07 10:00:00", "2025-04-22 10:00:00", 0.02, POOL),  # M3's record began after the cut
    ("t5", "NodeID-M3", "2026-02-02 10:00:00", "2026-02-17 10:00:00", 0.02, POOL),  # held back
    ("t6", "NodeID-P1", "2025-05-05 10:00:00", "2025-05-20 10:00:00", 0.10, POOL),  # pool-funded, no record
    ("t7", "NodeID-X1", "2025-01-06 12:00:00", "2025-07-06 12:00:00", 0.05, "avax1x"),
    ("t8", "NodeID-X1", "2026-01-05 12:00:00", "2026-07-05 12:00:00", 0.10, "avax1y"),  # held back
    ("t9", "NodeID-X2", "2025-06-02 12:00:00", "2025-12-02 12:00:00", 0.03, "avax1y"),
]
# node, owner, creation time, initial start time
RECORDS = [
    ("NodeID-M1", OWNER_A, None, "2025-01-01 00:00:00"),
    ("NodeID-M2", OWNER_A, "2025-02-20 00:00:00", "2025-03-03 10:00:00"),
    ("NodeID-M3", OWNER_B, "2026-01-10 00:00:00", "2026-02-02 10:00:00"),
]


def make_run(root: Path, name: str, dataset_id: str, table: str, sql: str, rows: int) -> None:
    capture_dir, dataset_dir = root / name / "capture", root / name / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / f"{table}.parquet"
    duckdb.connect().execute(f"COPY ({sql}) TO '{parquet}' (FORMAT PARQUET)")
    capture_id = f"capture:test:{name}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({
        "schema_version": "test-capture/v1", "capture_id": capture_id, "dataset_id": dataset_id,
        "completed_at": "2026-11-05T00:00:00Z", "contract_sha256": "0" * 64,
    }))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({
        "schema_version": "test-build/v1", "dataset_id": dataset_id, "source_capture_id": capture_id,
        "completed_at": "2026-11-05T00:00:00Z", "summary": {"rows": rows},
        "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}],
    }))


def time(value: str | None) -> str:
    return "NULL::TIMESTAMP" if value is None else f"TIMESTAMP '{value}'"


def make_inputs(root: Path, periods: list[tuple] = PERIODS) -> None:
    values = ", ".join(f"('{t}', 'validator', '{n}', {time(a)}, {time(a)}, {time(e)}, {f})" for t, n, a, e, f, _ in periods)
    delegation = "('d1', 'delegator', 'NodeID-X1', TIMESTAMP '2025-02-01', TIMESTAMP '2025-02-01', TIMESTAMP '2025-03-01', NULL)"
    make_run(root, "staking-periods", "derived.staking-periods", "staking-periods",
             f"SELECT * FROM (VALUES {values}, {delegation}) AS t(transaction_hash, role, node_id, accepted_at, start_time, end_time, delegation_fee_rate)",
             len(periods) + 1)
    stakes = ", ".join(f"('{t}', '{r}')" for t, *_, r in periods)
    make_run(root, "validator-stakes", "snowflake.primary-validator-stakes", "validator-stakes",
             f"SELECT * FROM (VALUES {stakes}) AS t(transaction_hash, reward_address)", len(periods))
    records = ", ".join(f"('{n}', '{o}', '0xmultisig', NULL::VARCHAR, {time(c)}, {time(s)})" for n, o, c, s in RECORDS)
    make_run(root, "minipool-records", "c-chain-rpc.minipool-records", "minipool-records",
             f"SELECT * FROM (VALUES {records}) AS t(node_id, owner, multisig_address, tx_id, creation_time, initial_start_time)",
             len(RECORDS))


def rows(output: Path) -> dict[str, dict]:
    frame = duckdb.connect().execute(
        "SELECT * FROM read_parquet(?)", [str(output / "dataset" / f"{operator_clusters.TABLE}.parquet")]).fetchdf()
    return {row.transaction_hash: row._asdict() for row in frame.astype(object).where(frame.notna(), None).itertuples(index=False)}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    make_inputs(tmp_path)
    return tmp_path


def test_the_held_back_cut_is_19_november_2025_utc():
    assert operator_clusters.HELD_BACK_CUT == datetime(2025, 11, 19, 0, 0, tzinfo=UTC)
    assert operator_clusters.CUT_SQL == f"TIMESTAMP '{operator_clusters.HELD_BACK_CUT:%Y-%m-%d %H:%M:%S}'"


def test_catalog_declares_the_table():
    fields = dataset(load_catalog(), operator_clusters.DATASET_ID)["fields"]
    assert [field["name"] for field in fields] == list(operator_clusters.TABLE_COLUMNS)


def test_owner_keys_split_the_pool_address_by_minipool_owner(root):
    output = root / "out"
    result = operator_clusters.derive(operator_clusters.DATASET_ID, output, root=root)
    table = rows(output)
    assert set(table) == {f"t{index}" for index in range(1, 10)}
    assert result["build"]["summary"]["pool"]["address"] == POOL
    assert [table[t]["owner_key"] for t in ("t1", "t2", "t3")] == [f"{POOL}/owner/{OWNER_A}"] * 3
    assert [table[t]["owner_basis"] for t in ("t1", "t2", "t3")] == ["minipool-owner-carried-back", "minipool-owner", "minipool-owner"]
    # M3's record began after the cut, so its earlier period cannot use it and joins the pool block; its held-back
    # period may.
    assert table["t4"]["owner_key"] == table["t6"]["owner_key"] == f"{POOL}/pool"
    assert table["t4"]["owner_basis"] == "pool-no-record" and table["t4"]["minipool_owner"] is None
    assert table["t5"]["owner_key"] == f"{POOL}/owner/{OWNER_B}" and table["t5"]["held_back"]
    assert table["t7"]["owner_key"] == "avax1x" and table["t7"]["owner_basis"] == "reward-address" and not table["t7"]["pool_address"]
    pool = result["build"]["summary"]["pool"]
    assert pool["by_basis"]["pool-no-record"] == {"periods": 2, "nodes": 2, "periods_before_cut": 2}
    assert pool["pool_no_record_periods_before_cut_whose_node_has_a_record_from_after_the_cut"] == {"periods": 1, "nodes": 1}
    assert pool["minipool_owners"] == 2 and pool["largest_owner_nodes"] == 2


def test_cohort_comes_from_the_first_period_and_components_only_from_periods_before_the_cut(root):
    output = root / "out"
    summary = operator_clusters.derive(operator_clusters.DATASET_ID, output, root=root)["build"]["summary"]
    table = rows(output)
    assert str(table["t8"]["entry_week"])[:10] == "2025-01-06" and table["t8"]["entry_fee_rate"] == 0.05
    assert table["t8"]["cohort_key"] == "2025-01-06/0.05"
    assert table["t1"]["cohort_key"] == "2024-12-02/0.02" and table["t6"]["cohort_key"] == "2025-05-05/0.1"
    # M1 and M2 share an owner key; M3 and P1 share the pool block. X1 was paid to avax1y only after the cut, so it
    # stays apart from X2.
    assert table["t1"]["component_id"] == table["t3"]["component_id"] == "NodeID-M1" and table["t1"]["component_nodes"] == 2
    assert table["t4"]["component_id"] == table["t6"]["component_id"] == "NodeID-M3"
    assert table["t7"]["component_id"] == "NodeID-X1" and table["t9"]["component_id"] == "NodeID-X2"
    assert table["t7"]["component_nodes"] == 1 and table["t7"]["component_keys"] == 1
    assert table["t5"]["component_id"] is None and table["t8"]["component_id"] is None
    assert summary["keys_before_cut"] == {"reward_address": 3, "owner_key": 4, "cohort_key": 6, "component_id": 4}
    assert summary["held_back_periods"] == 2 and summary["nodes"] == 6
    checked = operator_clusters.check(output / "capture", output / "dataset", root=root)
    assert checked["status"] == "pass", checked["findings"]


def test_records_after_the_cut_never_change_an_earlier_row(tmp_path):
    full, early = tmp_path / "full", tmp_path / "early"
    make_inputs(full)
    # The same history without any period accepted on or after the cut: a later link from X1 to X2 and M3's held-back
    # period disappear, and every earlier row stays as it was.
    make_inputs(early, [item for item in PERIODS if item[2] < "2025-11-19"])
    operator_clusters.derive(operator_clusters.DATASET_ID, full / "out", root=full)
    operator_clusters.derive(operator_clusters.DATASET_ID, early / "out", root=early)
    later, earlier = rows(full / "out"), rows(early / "out")
    assert set(earlier) == {key for key, value in later.items() if not value["held_back"]}
    assert all(later[key] == earlier[key] for key in earlier)


def test_check_flags_a_changed_input_and_rejects_other_datasets(root):
    output = root / "out"
    operator_clusters.derive(operator_clusters.DATASET_ID, output, root=root)
    parquet = root / "minipool-records" / "dataset" / "minipool-records.parquet"
    parquet.write_bytes(parquet.read_bytes() + b"x")
    findings = operator_clusters.check(output / "capture", output / "dataset", root=root)["findings"]
    assert any("input run differs" in item for item in findings)
    with pytest.raises(DataError):
        operator_clusters.derive("derived.operators", root / "other", root=root)
