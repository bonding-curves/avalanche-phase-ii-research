"""Validation cycles after Helicon, built from a small staking-period log and three validator snapshots."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from avalanche_research import helicon
from avalanche_research.catalog import (
    DataError,
    canonical_bytes,
    contract_hash,
    load_catalog,
    sha256,
)

# The staking-period log before Helicon: a node that will lower its duration, one that will raise it, and a delegator
# row that must not count as validator history.
PERIODS = [
    # hash, role, node, start, end
    ("r1-old", "validator", "NodeID-R1", "2026-08-01 00:00:00", "2026-09-01 00:00:00"),
    ("r2-old", "validator", "NodeID-R2", "2026-09-01 00:00:00", "2026-09-15 00:00:00"),
    ("d-old", "delegator", "NodeID-N", "2026-09-01 00:00:00", "2026-09-15 00:00:00"),
]
# node, hash, start, end, stake
FIRST = [
    ("NodeID-N", "n1", "2026-09-22 16:00:00", "2026-09-29 16:00:00", 2_000.0),   # new node, 7 days
    ("NodeID-R1", "r1", "2026-09-22 18:00:00", "2026-09-24 18:00:00", 3_000.0),  # returning, 31 days to 2: lowered
    ("NodeID-R2", "r2", "2026-09-22 20:00:00", "2026-10-22 20:00:00", 4_000.0),  # returning, 14 days to 30: raised
    ("NodeID-A", "a1", "2026-09-22 17:00:00", "2026-09-24 17:00:00", 2_000.0),   # new node, auto-renewed below
    ("NodeID-X", "old", "2026-09-20 00:00:00", "2026-10-04 00:00:00", 5_000.0),  # started before activation: excluded
]
# The auto-renewed transaction a1 under the same hash with a new start, its stake grown by a restaked reward.
SECOND = [row for row in FIRST if row[1] in {"n1", "r2", "old"}] + [
    ("NodeID-A", "a1", "2026-09-24 17:00:00", "2026-09-26 17:00:00", 2_000.5),
]
# A snapshot under an outdated contract: its rows must not be read.
STALE = [("NodeID-S", "s1", "2026-09-23 00:00:00", "2026-09-25 00:00:00", 2_000.0)]


def literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, str):
        return f"'{value}'"
    return repr(value)


def make_run(root: Path, name: str, dataset_id: str, table: str, sql: str, captured_at: str, contract: str) -> None:
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
        "schema_version": "test-capture/v1", "capture_id": capture_id, "dataset_id": dataset_id, "completed_at": captured_at, "contract_sha256": contract,
    }))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({
        "schema_version": "test-build/v1", "dataset_id": dataset_id, "source_capture_id": capture_id, "completed_at": captured_at,
        "summary": {"rows": rows}, "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}],
    }))


def snapshot_sql(observed_at: str, rows: list[tuple]) -> str:
    values = ", ".join(
        f"(TIMESTAMP '{observed_at}', {literal(node)}, {literal(tx)}, TIMESTAMP '{start}', TIMESTAMP '{end}', {stake}, 0.02)"
        for node, tx, start, end, stake in rows
    )
    return (
        "SELECT * FROM (VALUES " + values + ") AS t(observed_at, node_id, transaction_hash, start_time, end_time, stake_avax, delegation_fee_rate)"
    )


@pytest.fixture
def root(tmp_path: Path) -> Path:
    values = ", ".join(f"({literal(tx)}, {literal(role)}, {literal(node)}, TIMESTAMP '{start}', TIMESTAMP '{end}')" for tx, role, node, start, end in PERIODS)
    periods = f"SELECT * FROM (VALUES {values}) AS t(transaction_hash, role, node_id, start_time, end_time)"
    make_run(tmp_path, "staking-periods", "derived.staking-periods", "staking-periods", periods, "2026-09-22T16:00:00Z", "0" * 64)
    current = contract_hash(load_catalog(), "p-chain-rpc.current-validators")
    make_run(tmp_path, "snap-1", "p-chain-rpc.current-validators", "current-validators", snapshot_sql("2026-09-23 00:00:00", FIRST), "2026-09-23T00:00:00Z", current)
    make_run(tmp_path, "snap-2", "p-chain-rpc.current-validators", "current-validators", snapshot_sql("2026-09-25 00:00:00", SECOND), "2026-09-25T00:00:00Z", current)
    make_run(tmp_path, "snap-stale", "p-chain-rpc.current-validators", "current-validators", snapshot_sql("2026-09-24 00:00:00", STALE), "2026-09-24T00:00:00Z", "0" * 64)
    return tmp_path


def rows(output: Path) -> dict[tuple[str, str], tuple]:
    table = duckdb.connect().execute(
        "SELECT transaction_hash, strftime(cycle_start, '%m-%d'), node_id, round(duration_days, 3), stake_avax, cycle_number, auto_renewed,"
        " node_status, round(previous_duration_days, 3), round(duration_change_days, 3), lowered, duration_bin, strftime(first_seen_at, '%m-%d')"
        " FROM read_parquet(?)",
        [str(output / "dataset" / f"{helicon.TABLE}.parquet")],
    ).fetchall()
    return {(row[0], row[1]): row[2:] for row in table}


def test_catalog_declares_the_commitment_table():
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == helicon.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(helicon.TABLE_COLUMNS)
    assert definition["input_ids"] == [*helicon.INPUTS, *helicon.MANY_INPUTS]


def test_derive_one_row_per_cycle_after_activation(root):
    output = root / "helicon-commitments"
    result = helicon.derive(helicon.DATASET_ID, output, None, root)
    table = rows(output)
    # The cycle that started before activation is excluded; the auto-renewed transaction has two rows.
    assert sorted(table) == [("a1", "09-22"), ("a1", "09-24"), ("n1", "09-22"), ("r1", "09-22"), ("r2", "09-22")]
    # New node: no earlier period, so no comparison. The delegator row in the log is not validator history.
    assert table[("n1", "09-22")] == ("NodeID-N", 7.0, 2_000.0, 1, False, "new", None, None, None, "7d to 14d", "09-23")
    # Returning node that lowers from 31 days to the 48-hour minimum.
    assert table[("r1", "09-22")] == ("NodeID-R1", 2.0, 3_000.0, 1, False, "returning", 31.0, -29.0, True, "48h to 7d", "09-23")
    # Returning node that raises from 14 days to 30.
    assert table[("r2", "09-22")] == ("NodeID-R2", 30.0, 4_000.0, 1, False, "returning", 14.0, 16.0, False, "30d to 90d", "09-23")
    # Auto-renewal: same hash, two start times; the second cycle compares with the first and carries its own stake.
    assert table[("a1", "09-22")] == ("NodeID-A", 2.0, 2_000.0, 1, True, "new", None, None, None, "48h to 7d", "09-23")
    assert table[("a1", "09-24")] == ("NodeID-A", 2.0, 2_000.5, 2, True, "new", 2.0, 0.0, False, "48h to 7d", "09-25")
    summary = result["build"]["summary"]
    assert (summary["rows"], summary["transactions"], summary["nodes"], summary["new_nodes"], summary["returning_nodes"]) == (5, 4, 4, 2, 2)
    assert (summary["lowered_cycles"], summary["raised_cycles"], summary["auto_renewed_transactions"], summary["renewal_cycles"]) == (1, 1, 1, 1)
    assert summary["cycles_by_bin"] == {"48h to 7d": 3, "7d to 14d": 1, "14d to 30d": 0, "30d to 90d": 1, "90d to 180d": 0, "180d to 365d": 0, "over 365d": 0}
    assert summary["transactions_by_bin"]["48h to 7d"] == 2
    # The stale-contract snapshot is not an input; the two current ones are, oldest first.
    assert [item["run"] for item in result["capture"]["inputs"]] == ["staking-periods", "snap-1", "snap-2"]
    assert summary["snapshots"] == 2 and summary["max_snapshot_gap_hours"] == 48.0
    # Before Helicon: r2-old from the log and the snapshot-only cycle "old", both 14 days, fall in the 30-day window.
    assert summary["before_helicon"]["periods"] == 2
    assert summary["before_helicon"]["periods_by_bin"]["14d to 30d"] == 2
    validation = helicon.check(output / "capture", output / "dataset", None, root)
    assert validation["status"] == "pass", validation["findings"]
    assert validation["summary"]["rebuilt_rows"] == 5


def test_check_flags_a_changed_input_and_a_changed_output(root):
    output = root / "helicon-commitments"
    helicon.derive(helicon.DATASET_ID, output, None, root)
    snapshot = root / "snap-2" / "dataset" / "current-validators.parquet"
    snapshot.write_bytes(snapshot.read_bytes() + b"\n")
    validation = helicon.check(output / "capture", output / "dataset", None, root)
    assert validation["status"] == "attention"
    assert any("input run differs" in item for item in validation["findings"])
    table = output / "dataset" / f"{helicon.TABLE}.parquet"
    table.write_bytes(table.read_bytes() + b"\n")
    validation = helicon.check(output / "capture", output / "dataset", None, root)
    assert any("output hash or size differs" in item for item in validation["findings"])


def test_snapshots_cannot_be_pinned_and_other_datasets_are_rejected(root, tmp_path):
    with pytest.raises(DataError, match="cannot be pinned"):
        helicon.derive(helicon.DATASET_ID, root / "x", {"p-chain-rpc.current-validators": "snap-1"}, root)
    with pytest.raises(DataError, match="not an input"):
        helicon.derive(helicon.DATASET_ID, root / "x", {"derived.node-table": "y"}, root)
    result = helicon.derive(helicon.DATASET_ID, root / "pinned", {"derived.staking-periods": "staking-periods"}, root)
    assert result["capture"]["inputs"][0]["run"] == "staking-periods"
    with pytest.raises(DataError):
        helicon.capture(helicon.DATASET_ID, tmp_path / "c")
    with pytest.raises(DataError):
        helicon.build(helicon.DATASET_ID, tmp_path / "c", tmp_path / "d")


# Frozen 2026-09-29 (W215): the modeling lead's Helicon forecast and its naive benchmarks are scored on these bins and
# this node_status rule. Changing either invalidates the forecast, so the change must be a new, dated rule, not an edit.
FROZEN_BINS = (
    ("48h to 7d", 2.0, 7),
    ("7d to 14d", 7, 14),
    ("14d to 30d", 14, 30),
    ("30d to 90d", 30, 90),
    ("90d to 180d", 90, 180),
    ("180d to 365d", 180, 365),
)


def test_bins_and_node_status_rule_are_frozen():
    assert helicon.ACTIVATION.isoformat() == "2026-09-22T15:00:00"
    assert helicon.MIN_DURATION_DAYS == 2.0
    assert helicon.LOWERED_THRESHOLD_DAYS == 1
    assert helicon.BINS == FROZEN_BINS
    assert (helicon.UNDER_BIN, helicon.OVER_BIN) == ("under 48h", "over 365d")
    cases = {1.99: "under 48h", 2.0: "48h to 7d", 6.99: "48h to 7d", 7.0: "7d to 14d", 14.0: "14d to 30d",
             29.99: "14d to 30d", 30.0: "30d to 90d", 180.0: "180d to 365d", 365.0: "180d to 365d", 365.01: "over 365d"}
    for days, label in cases.items():
        assert duckdb.sql(f"SELECT {helicon.bin_case(str(days))}").fetchone()[0] == label, days
    # node_status: 'returning' when the node has any validator period that started before activation, in the staking
    # log or in an earlier snapshot, and 'new' otherwise.
    sql = " ".join(helicon.COMMITMENTS_SQL.split())
    assert "SELECT DISTINCT node_id FROM history WHERE start_time < TIMESTAMP '2026-09-22 15:00:00'" in sql
    assert "CASE WHEN was_validator THEN 'returning' ELSE 'new' END AS node_status" in sql
    assert "duration_days - previous_duration_days < -1 AS lowered" in sql
