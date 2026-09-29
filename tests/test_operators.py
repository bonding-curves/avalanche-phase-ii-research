"""Operators and fleets, built from a small node table."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from avalanche_research import operators
from avalanche_research.catalog import DataError, canonical_bytes, load_catalog, sha256

GOGOPOOL = "avax10f8305248c0wsfsdempdtpx7lpkc30vwzl9y9q"
# node, reward address, first start, last end, fee, active, periods
NODES = [
    ("NodeID-G1", GOGOPOOL, "2025-01-06 10:00:00", "2025-08-12 10:00:00", 0.02, False, 15),
    ("NodeID-G2", GOGOPOOL, "2025-01-07 11:00:00", "2025-08-13 11:00:00", 0.02, False, 15),
    ("NodeID-X", "avax1other", "2025-01-08 12:00:00", "2025-08-14 12:00:00", 0.02, False, 3),  # same fleet, other operator
    ("NodeID-Y", "avax1other", "2025-01-15 12:00:00", "2026-10-01 00:00:00", 0.05, True, 1),
]


def make_node_table(root: Path, nodes: list[tuple]) -> None:
    capture_dir, dataset_dir = root / "node-table" / "capture", root / "node-table" / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    values = ", ".join(
        f"('{n}', '{a}', TIMESTAMP '{s}', TIMESTAMP '{e}', {f}, {str(act).lower()}, {p})" for n, a, s, e, f, act, p in nodes
    )
    sql = f"SELECT * FROM (VALUES {values}) AS t(node_id, reward_address, first_start, last_end, latest_fee_rate, active, periods)"
    parquet = dataset_dir / "node-table.parquet"
    duckdb.connect().execute(f"COPY ({sql}) TO '{parquet}' (FORMAT PARQUET)")
    capture_id = "capture:test:node-table"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({
        "schema_version": "test-capture/v1", "capture_id": capture_id, "dataset_id": "derived.node-table",
        "completed_at": "2026-09-29T00:00:00Z", "contract_sha256": "0" * 64,
    }))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({
        "schema_version": "test-build/v1", "dataset_id": "derived.node-table", "source_capture_id": capture_id,
        "completed_at": "2026-09-29T00:00:00Z", "summary": {"rows": len(nodes)},
        "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}],
    }))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    make_node_table(tmp_path, NODES)
    return tmp_path


def rows(output: Path) -> dict[str, dict]:
    frame = duckdb.connect().execute(
        "SELECT * FROM read_parquet(?)", [str(output / "dataset" / f"{operators.TABLE}.parquet")]).fetchdf()
    return {row.node_id: row._asdict() for row in frame.itertuples(index=False)}


def test_catalog_declares_the_table():
    fields = next(item for item in load_catalog()["datasets"] if item["id"] == operators.DATASET_ID)["fields"]
    assert [field["name"] for field in fields] == list(operators.TABLE_COLUMNS)


def test_every_node_once_with_operator_fleet_and_named_agent(root):
    output = root / "out"
    result = operators.derive(operators.DATASET_ID, output, root=root)
    table = rows(output)
    assert set(table) == {"NodeID-G1", "NodeID-G2", "NodeID-X", "NodeID-Y"}
    g1, x, y = table["NodeID-G1"], table["NodeID-X"], table["NodeID-Y"]
    assert g1["operator_id"] == GOGOPOOL and g1["operator_nodes"] == 2 and g1["named_agent"] == "GoGoPool"
    # G1, G2, and X entered in the week of 2025-01-06, left in the week of 2025-08-11, at a 2% fee: one fleet, two operators.
    assert g1["fleet_id"] == table["NodeID-G2"]["fleet_id"] == x["fleet_id"]
    assert g1["fleet_nodes"] == 3 and g1["fleet_operators"] == 2
    assert y["fleet_nodes"] == 1 and y["named_agent"] is None
    summary = result["build"]["summary"]
    assert (summary["nodes"], summary["operators"], summary["fleets"], summary["fleets_spanning_operators"]) == (4, 2, 2, 1)
    assert summary["named_agents"] == {"GoGoPool avax10f83": {"nodes": 2, "active": 0}}
    checked = operators.check(output / "capture", output / "dataset", root=root)
    assert checked["status"] == "pass", checked["findings"]


def test_fleet_stability_counts_nodes_whose_fleet_changes_under_two_week_buckets(root):
    output = root / "out"
    summary = operators.derive(operators.DATASET_ID, output, root=root)["build"]["summary"]["fleet_stability"]
    # Y entered in the week after the others; two-week buckets from 2020-09-07 put 2025-01-06 and 2025-01-13 together, but
    # Y also differs in exit week and fee, so no fleet changes size.
    assert summary["fleets"] == 2 and summary["nodes_whose_fleet_size_changes"] == 0


def test_check_flags_a_changed_input_and_rejects_other_datasets(root):
    output = root / "out"
    operators.derive(operators.DATASET_ID, output, root=root)
    parquet = root / "node-table" / "dataset" / "node-table.parquet"
    parquet.write_bytes(parquet.read_bytes() + b"x")
    findings = operators.check(output / "capture", output / "dataset", root=root)["findings"]
    assert any("input run differs" in item for item in findings)
    with pytest.raises(DataError):
        operators.derive("derived.node-table", root / "other", root=root)
