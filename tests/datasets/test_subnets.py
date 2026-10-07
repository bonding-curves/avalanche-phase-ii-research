"""Subnet and L1 validation by node, built from a small transaction log and staking-period log."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from avalanche_research.core.catalog import (
    DataError,
    canonical_bytes,
    load_catalog,
    sha256,
)
from avalanche_research.datasets.derived import subnets

# node, start, end: Primary Network validator periods
PERIODS = [
    ("NodeID-A", "2024-06-01 00:00:00", "2025-06-01 00:00:00"),
    ("NodeID-B", "2024-01-01 00:00:00", "2026-06-01 00:00:00"),
    ("NodeID-C", "2024-07-01 00:00:00", "2024-09-01 00:00:00"),
]
# type, hash, accepted, node, subnet, start, end, removal, weight
TRANSACTIONS = [
    # A validates S1 inside its Primary period, removed early. S1 converts on 2025-01-10 with A as an initial L1 validator.
    ("AddSubnetValidatorTx", "add-a", "2024-07-01 00:00:00", "NodeID-A", "S1", "2024-07-02 00:00:00", "2024-12-01 00:00:00", "2024-11-01 00:00:00", None),
    ("RemoveSubnetValidatorTx", "rm-a", "2024-11-01 00:00:00", None, "S1", None, None, None, None),
    ("ConvertSubnetToL1Tx", "conv-1", "2025-01-10 00:00:00", "NodeID-A", "S1", None, None, None, 100),
    ("ConvertSubnetToL1Tx", "conv-1", "2025-01-10 00:00:00", "NodeID-D", "S1", None, None, None, 100),
    ("DisableL1ValidatorTx", "dis-a", "2025-03-01 00:00:00", "NodeID-A", "S1", None, None, None, 100),
    # B validates S2 twice, S2 never converts.
    ("AddSubnetValidatorTx", "add-b1", "2024-02-01 00:00:00", "NodeID-B", "S2", "2024-02-02 00:00:00", "2024-05-01 00:00:00", None, None),
    ("AddSubnetValidatorTx", "add-b2", "2024-06-01 00:00:00", "NodeID-B", "S2", "2024-06-02 00:00:00", "2024-12-01 00:00:00", None, None),
    # E registers as an L1 validator of S1 without ever validating the Primary Network.
    ("RegisterL1ValidatorTx", "reg-e", "2025-02-01 00:00:00", "NodeID-E", "S1", None, None, None, 50),
]


def literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, str):
        return f"'{value}'"
    return repr(value)


def stamp(value):
    return "NULL::TIMESTAMP" if value is None else f"TIMESTAMP '{value}'"


def make_run(root: Path, name: str, dataset_id: str, table: str, sql: str, captured_at: str) -> None:
    capture_dir, dataset_dir = root / name / "capture", root / name / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / f"{table}.parquet"
    connection = duckdb.connect()
    try:
        connection.execute(f"COPY ({sql}) TO '{parquet}' (FORMAT PARQUET)")
        rows = connection.execute(f"SELECT count(*) FROM ({sql})").fetchone()[0]
    finally:
        connection.close()
    capture_id = f"capture:test:{captured_at}:{name}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({
        "schema_version": "test-capture/v1", "capture_id": capture_id, "dataset_id": dataset_id, "completed_at": captured_at, "contract_sha256": "0" * 64,
    }))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({
        "schema_version": "test-build/v1", "dataset_id": dataset_id, "source_capture_id": capture_id, "completed_at": captured_at,
        "summary": {"rows": rows}, "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}],
    }))


def build_root(root: Path, transactions: list[tuple], periods: list[tuple]) -> Path:
    values = ", ".join(f"('p-{i}', 'validator', {literal(node)}, TIMESTAMP '{start}', TIMESTAMP '{end}')" for i, (node, start, end) in enumerate(periods))
    make_run(root, "staking-periods", "derived.staking-periods", "staking-periods",
             f"SELECT * FROM (VALUES {values}) AS t(transaction_hash, role, node_id, start_time, end_time)", "2026-09-22T00:00:00Z")
    values = ", ".join(
        f"({literal(t)}, {literal(h)}, TIMESTAMP '{a}', 1, {literal(n)}, {literal(s)}, {stamp(st)}, {stamp(en)}, {stamp(rm)}, {literal(w)}::BIGINT)"
        for t, h, a, n, s, st, en, rm, w in transactions
    )
    make_run(root, "subnet-transactions", "snowflake.subnet-validator-transactions", "subnet-validator-transactions",
             f"SELECT * FROM (VALUES {values}) AS t(tx_type, transaction_hash, accepted_at, block_height, node_id, subnet_id,"
             " start_time, end_time, removal_time, l1_validator_weight)", "2026-09-29T00:00:00Z")
    return root


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return build_root(tmp_path, TRANSACTIONS, PERIODS)


def table(output: Path) -> dict[tuple[str, str], dict]:
    connection = duckdb.connect()
    frame = connection.execute("SELECT * FROM read_parquet(?)", [str(output / "dataset" / f"{subnets.TABLE}.parquet")]).fetchdf()
    return {(row.node_id, row.subnet_id): row._asdict() for row in frame.itertuples(index=False)}


def test_catalog_declares_the_table():
    catalog = load_catalog()
    fields = next(item for item in catalog["datasets"] if item["id"] == subnets.DATASET_ID)["fields"]
    assert [field["name"] for field in fields] == list(subnets.TABLE_COLUMNS)


def test_one_row_per_node_and_subnet_with_conversion_and_primary_span(root):
    output = root / "out"
    result = subnets.derive(subnets.DATASET_ID, output, root=root)
    rows = table(output)
    assert set(rows) == {("NodeID-A", "S1"), ("NodeID-B", "S2"), ("NodeID-D", "S1"), ("NodeID-E", "S1")}
    a = rows[("NodeID-A", "S1")]
    assert a["subnet_periods"] == 1 and a["removed_early"] == 1
    assert str(a["last_subnet_end"]) == "2024-11-01 00:00:00"  # the removal, not the scheduled end
    assert str(a["l1_converted_at"]) == "2025-01-10 00:00:00" and a["initial_l1_validator"]
    assert str(a["l1_registered_at"]) == "2025-01-10 00:00:00" and str(a["l1_disabled_at"]) == "2025-03-01 00:00:00"
    assert a["subnet_periods_after_conversion"] == 0 and a["subnet_periods_outside_primary"] == 0
    b = rows[("NodeID-B", "S2")]
    assert b["subnet_periods"] == 2 and str(b["l1_converted_at"]) == "NaT"
    e = rows[("NodeID-E", "S1")]
    assert e["subnet_periods"] == 0 and not e["initial_l1_validator"] and str(e["l1_registered_at"]) == "2025-02-01 00:00:00"
    assert str(e["primary_first_start"]) == "NaT"
    summary = result["build"]["summary"]
    assert (summary["rows"], summary["converted_subnets"], summary["subnet_validator_rows"], summary["l1_validator_rows"]) == (4, 1, 2, 3)
    assert summary["catalog_reproduction"]["active_2024_12_15_noon"] == 2  # A and B span 2024-12-15 12:00
    checked = subnets.check(output / "capture", output / "dataset", root=root)
    assert checked["status"] == "pass", checked["findings"]


def test_check_flags_protocol_violations(tmp_path):
    # C's Subnet period runs past its Primary Network period, and a period of A starts after S1 converted.
    transactions = TRANSACTIONS + [
        ("AddSubnetValidatorTx", "add-c", "2024-07-01 00:00:00", "NodeID-C", "S3", "2024-07-02 00:00:00", "2024-10-01 00:00:00", None, None),
        ("AddSubnetValidatorTx", "add-a2", "2025-02-01 00:00:00", "NodeID-A", "S1", "2025-02-02 00:00:00", "2025-05-01 00:00:00", None, None),
    ]
    root = build_root(tmp_path, transactions, PERIODS)
    output = root / "out"
    subnets.derive(subnets.DATASET_ID, output, root=root)
    findings = subnets.check(output / "capture", output / "dataset", root=root)["findings"]
    assert "1 Subnet periods start after their Subnet converted to an L1" in findings
    assert "1 Subnet periods are not inside a Primary Network period of the same node" in findings


def test_check_flags_a_changed_input_and_rejects_other_datasets(root):
    output = root / "out"
    subnets.derive(subnets.DATASET_ID, output, root=root)
    parquet = root / "staking-periods" / "dataset" / "staking-periods.parquet"
    parquet.write_bytes(parquet.read_bytes() + b"x")
    findings = subnets.check(output / "capture", output / "dataset", root=root)["findings"]
    assert any("input run differs" in item for item in findings)
    with pytest.raises(DataError):
        subnets.derive("derived.node-table", root / "other", root=root)
