"""The node table: one row per validator node, built from the fixture runs the derived test also uses."""

from pathlib import Path

import duckdb
import pytest

from avalanche_research import derived, nodes
from avalanche_research.catalog import DataError, load_catalog
from tests.test_derived import root as derived_root  # noqa: F401  the fixture with the four Snowflake runs


@pytest.fixture
def root(derived_root: Path) -> Path:  # noqa: F811
    derived.derive(derived.DATASET_ID, derived_root / "staking-periods", None, derived_root)
    return derived_root


def test_catalog_declares_the_node_table():
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == nodes.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(nodes.TABLE_COLUMNS)
    assert definition["input_ids"] == [*nodes.INPUTS, *nodes.OPTIONAL_INPUTS]


def test_derive_one_row_per_node_with_the_three_clocks(root):
    output = root / "node-table"
    result = nodes.derive(nodes.DATASET_ID, output, None, root)
    summary = result["build"]["summary"]
    assert (summary["rows"], summary["distinct_nodes"], summary["periods"]) == (2, 2, 2)
    assert summary["nodes_without_reward_address"] == 0 and summary["clock_order_violations"] == 0
    table = duckdb.connect().execute(
        "SELECT node_id, active, periods, streaks, round(span_days, 2), round(tenure_days, 2), round(current_streak_days, 2), delegations, operator_group FROM read_parquet(?) ORDER BY node_id",
        [str(output / "dataset" / "node-table.parquet")],
    ).fetchall()
    # Both nodes finished before the validator capture time of 2026-09-19, so neither is censored: the three clocks agree.
    assert table[0][:7] == ("NodeID-1", False, 1, 1, 364.0, 364.0, 364.0)
    assert table[1][:8] == ("NodeID-2", False, 1, 1, 365.0, 365.0, 365.0, 2)
    assert table[0][8] == "P-avax1owner"
    validation = nodes.check(output / "capture", output / "dataset", None, root)
    assert validation["status"] == "pass", validation["findings"]
    assert "period and reward reconciliation" in validation["checked"]


def test_check_fails_when_an_input_run_changes(root):
    output = root / "node-table"
    nodes.derive(nodes.DATASET_ID, output, None, root)
    parquet = root / "staking-periods" / "dataset" / "staking-periods.parquet"
    parquet.write_bytes(parquet.read_bytes() + b"\n")
    validation = nodes.check(output / "capture", output / "dataset", None, root)
    assert validation["status"] == "attention"
    assert any("input run differs" in item for item in validation["findings"])


def test_rejects_fetch_and_build(tmp_path):
    with pytest.raises(DataError):
        nodes.capture(nodes.DATASET_ID, tmp_path / "x")
    with pytest.raises(DataError):
        nodes.build(nodes.DATASET_ID, tmp_path / "c", tmp_path / "d")
