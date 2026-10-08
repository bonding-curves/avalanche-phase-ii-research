"""Identity v0: dated edges, groups at an instant from earlier edges only, names from their evidence date, truncation."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

from avalanche_research.datasets.derived import identity

# (hash, node, accepted, reward addresses)
STAKES = [
    ("S1", "A", "2022-01-01 00:00", ["addr1"]),
    ("S2", "B", "2022-02-01 00:00", ["addr2"]),
    ("S3", "B", "2022-06-01 00:00", ["addr1"]),
    ("S4", "C", "2022-07-01 00:00", ["addr3", "addr4"]),
    ("S5", "D", "2023-01-01 00:00", ["addr4"]),
]


def write(tmp_path: Path, stakes=STAKES) -> str:
    frame = pd.DataFrame(stakes, columns=["transaction_hash", "node_id", "accepted_at", "addresses"])
    frame["accepted_at"] = pd.to_datetime(frame["accepted_at"])
    frame["reward_addresses"] = frame.pop("addresses").map(json.dumps)
    path = tmp_path / "validators.parquet"
    duckdb.from_df(frame).write_parquet(str(path))
    return str(path)


def names(tmp_path: Path) -> pd.DataFrame:
    attributions = {"attributions": [
        {"attribution_id": "X1", "subject_kind": "reward-address", "subject": "addr4", "name": "Fleet", "tier": "AS1", "class": "EVIDENCE",
         "replaces": None},
        {"attribution_id": "X2", "subject_kind": "reward-address", "subject": "addr2", "name": "Guess", "tier": "AS4", "class": "INFERENCE",
         "replaces": None},
        {"attribution_id": "X3", "subject_kind": "reward-address", "subject": "addr1", "name": "Undated", "tier": "AS1", "class": "EVIDENCE",
         "replaces": None}]}
    events = {"events": [{"kind": "identity", "attributions": ["X1"], "evidence_public_at": "2022-12-01T00:00:00Z"}]}
    (tmp_path / "a.json").write_text(json.dumps(attributions))
    (tmp_path / "e.json").write_text(json.dumps(events))
    return identity.dated_names(tmp_path / "a.json", tmp_path / "e.json")


def test_groups_join_nodes_only_through_edges_dated_before_the_instant(tmp_path):
    edges = identity.edges(write(tmp_path))
    early = identity.groups(edges, "2022-03-01").set_index("node_id")
    assert early["group_id"].to_dict() == {"A": "group:A", "B": "group:B"}
    later = identity.groups(edges, "2023-06-01").set_index("node_id")
    assert later.loc["B", "group_id"] == "group:A" and later.loc["B", "group_nodes"] == 2
    assert later.loc["D", "group_id"] == "group:C"


def test_a_node_moving_to_a_new_address_leaves_its_old_group(tmp_path):
    stakes = [*STAKES, ("S6", "B", "2023-03-01 00:00", ["addr4"])]
    later = identity.groups(identity.edges(write(tmp_path, stakes)), "2023-06-01").set_index("node_id")
    assert later.loc["A", "group_nodes"] == 1
    assert later.loc["B", "group_id"] == "group:B" and later.loc["B", "group_nodes"] == 3


def test_names_apply_only_from_their_evidence_date_and_only_at_as1(tmp_path):
    edges, named = identity.edges(write(tmp_path)), names(tmp_path)
    assert pd.isna(named.set_index("attribution_id").loc["X3", "named_from"])
    assert identity.groups(edges, "2022-11-01", named).set_index("node_id")["name"].isna().all()
    after = identity.groups(edges, "2023-06-01", named).set_index("node_id")
    assert after.loc["C", "name"] == "Fleet" and after.loc["D", "name"] == "Fleet" and pd.isna(after.loc["A", "name"])


def test_truncating_history_at_an_instant_changes_no_group_there(tmp_path):
    full = identity.edges(write(tmp_path))
    (tmp_path / "cut").mkdir()
    cut = identity.edges(write(tmp_path / "cut", [row for row in STAKES if row[2] <= "2022-06-30"]))
    at = "2022-06-30"
    pd.testing.assert_frame_equal(identity.groups(full, at), identity.groups(cut, at))


def test_resolve_returns_a_node_group_or_none_before_its_first_edge(tmp_path):
    edges = identity.edges(write(tmp_path))
    assert identity.resolve(edges, "D", "2022-08-01")["group_id"] is None
    assert identity.resolve(edges, "D", "2023-02-01")["members"] == ["C", "D"]
