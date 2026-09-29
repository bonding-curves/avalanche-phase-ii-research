"""Operator attributions: the attribution standard's rules on the curated file, and the join to the operator table."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest
from test_operators import NODES, make_node_table

from avalanche_research import attributions, operators
from avalanche_research.catalog import DataError, load_catalog


def test_catalog_declares_the_columns():
    fields = next(item for item in load_catalog()["datasets"] if item["id"] == attributions.DATASET_ID)["fields"]
    assert [field["name"] for field in fields] == list(attributions.TABLE_COLUMNS)


def test_the_curated_file_follows_the_standard_and_names_every_operator_agent():
    rows, _ = attributions.load_attributions()
    assert all(row["class"] != "EVIDENCE" or row["tier"] in ("AS1", "AS2", "AS3") for row in rows)
    assert set(operators.NAMED_AGENTS) == {row["subject"] for row in rows if row["subject_kind"] == "reward-address"}
    assert operators.NAMED_AGENTS["avax19zfygxaf59stehzedhxjesads0p5jdvfeedal0"][1].startswith("OA3 AS4 INFERENCE")


def write(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "attributions.json"
    path.write_text(json.dumps({"schema_version": "operator-attributions/v1", "attributions": rows}))
    return path


def row(**changes) -> dict:
    base = {"attribution_id": "X1", "subject_kind": "reward-address", "subject": "avax1x", "name": "Somebody", "statement": "s",
            "tier": "AS1", "class": "EVIDENCE", "source": "https://example.org", "supporting_sources": [], "captured_on": "2026-09-29",
            "data_run": None, "agent": "data-engineer", "replaces": None}
    return {**base, **changes}


@pytest.mark.parametrize("bad, message", [
    ([row(tier="AS4")], "EVIDENCE on an AS4 source alone"),
    ([row(tier="AS5")], "EVIDENCE on an AS5 source alone"),
    ([row(replaces="X9")], "replaces an unknown row"),
    ([row(source="sources/data/private-note.md")], "cites no public source"),
    ([row(name=None, **{"class": "INFERENCE"})], "attributes no name"),
    ([row(), row()], "ID repeats"),
])
def test_the_standard_refuses(tmp_path, bad, message):
    with pytest.raises(DataError, match=message):
        attributions.load_attributions(write(tmp_path, bad))


def test_a_correction_replaces_the_row_it_names(tmp_path):
    path = write(tmp_path, [row(), row(attribution_id="X2", name="Somebody else", replaces="X1")])
    assert attributions.named_agents(path)["avax1x"][0] == "Somebody else"


def test_derive_joins_operators_and_fleets(tmp_path):
    runs = tmp_path / "runs"
    make_node_table(runs, NODES)
    operators.derive(operators.DATASET_ID, runs / "operators", root=runs)
    output = runs / "attributions"
    attributions.derive(attributions.DATASET_ID, output, root=runs)
    table = {r[0]: r for r in duckdb.connect().execute(
        "SELECT attribution_id, operator_id, operator_nodes, active_nodes, fleets, fleets_shared_with_other_operators FROM read_parquet(?)",
        [str(output / "dataset" / f"{attributions.TABLE}.parquet")]).fetchall()}
    # GoGoPool's two nodes share their fleet with another operator's node.
    assert table["OA1"][1:] == ("avax10f8305248c0wsfsdempdtpx7lpkc30vwzl9y9q", 2, 0, 1, 1)
    checked = attributions.check(output / "capture", output / "dataset", root=runs)
    # The fixture holds only GoGoPool's nodes, so the other attributed reward addresses are reported as no operator.
    assert any("no operator" in item for item in checked["findings"]) and checked["summary"]["named_agents"] == 1
