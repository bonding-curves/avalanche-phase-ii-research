"""Identity v0: dated edges, groups at an instant from earlier edges only, names from their evidence date, truncation."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from avalanche_research.core.catalog import DataError
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


def test_two_stakes_of_one_node_at_one_instant_are_refused(tmp_path):
    stakes = [*STAKES, ("S6", "A", "2022-01-01 00:00", ["addr9"])]
    with pytest.raises(DataError, match="two stakes"):
        identity.edges(write(tmp_path, stakes))


def test_a_group_with_two_dated_names_gets_no_name_and_lists_both(tmp_path):
    edges = identity.edges(write(tmp_path))
    named = pd.DataFrame([{"attribution_id": "X1", "address": "addr3", "name": "Fleet", "named_from": pd.Timestamp("2022-12-01")},
                          {"attribution_id": "X4", "address": "addr4", "name": "Other", "named_from": pd.Timestamp("2022-12-01")}])
    for order in (named, named.iloc[::-1]):
        row = identity.groups(edges, "2023-06-01", order).set_index("node_id").loc["C"]
        assert pd.isna(row["name"]) and row["names"] == "Fleet; Other"


def test_a_replacement_that_changes_an_as1_name_is_refused(tmp_path):
    rows = [{"attribution_id": "X1", "subject_kind": "reward-address", "subject": "addr4", "name": "Fleet", "tier": "AS1", "class": "EVIDENCE",
             "replaces": None},
            {"attribution_id": "X2", "subject_kind": "reward-address", "subject": "addr4", "name": "Buyer", "tier": "AS1", "class": "EVIDENCE",
             "replaces": "X1"}]
    (tmp_path / "a.json").write_text(json.dumps({"attributions": rows}))
    (tmp_path / "e.json").write_text(json.dumps({"events": []}))
    with pytest.raises(DataError, match="change of owner"):
        identity.dated_names(tmp_path / "a.json", tmp_path / "e.json")


def test_at_as1_only_named_addresses_join_nodes(tmp_path):
    edges, named = identity.edges(write(tmp_path)), names(tmp_path)
    as1 = identity.groups(edges, "2023-06-01", named, tier="AS1").set_index("node_id")
    assert as1.loc["C", "group_id"] == as1.loc["D", "group_id"] == "group:C"
    assert as1.loc["B", "group_id"] == "group:B" and as1.loc["A", "group_nodes"] == 1
    with pytest.raises(ValueError, match="tier"):
        identity.groups(edges, "2023-06-01", named, tier="AS3")


def test_an_address_takes_its_latest_dated_name_and_a_same_day_pair_is_a_conflict_in_any_order(tmp_path):
    edges = identity.edges(write(tmp_path))

    def table(*rows):
        return pd.DataFrame([{"attribution_id": f"X{i}", "address": "addr4", "name": name, "named_from": pd.Timestamp(day)}
                             for i, (name, day) in enumerate(rows)])

    for order in ((("Fleet", "2022-12-01"), ("Buyer", "2023-03-01")), (("Buyer", "2023-03-01"), ("Fleet", "2022-12-01"))):
        named = table(*order)
        assert identity.groups(edges, "2023-01-01", named).set_index("node_id").loc["D", "name"] == "Fleet"
        assert identity.groups(edges, "2023-06-01", named).set_index("node_id").loc["D", "name"] == "Buyer"
    for order in ((("Fleet", "2022-12-01"), ("Other", "2022-12-01")), (("Other", "2022-12-01"), ("Fleet", "2022-12-01"))):
        row = identity.groups(edges, "2023-06-01", table(*order)).set_index("node_id").loc["D"]
        assert pd.isna(row["name"]) and row["names"] == "Fleet; Other"


def test_a_date_alone_names_from_the_end_of_its_day_and_cannot_be_ordered_against_a_time_that_day(tmp_path):
    attributions = {"attributions": [
        {"attribution_id": f"X{i}", "subject_kind": "reward-address", "subject": "addr4", "name": name, "tier": "AS1",
         "class": "EVIDENCE", "replaces": None} for i, name in ((1, "Fleet"), (2, "Buyer"))]}
    events = {"events": [{"kind": "identity", "attributions": ["X1"], "evidence_public_at": "2022-12-01"},
                         {"kind": "identity", "attributions": ["X2"], "evidence_public_at": "2022-12-01T17:00:00Z"}]}
    (tmp_path / "a.json").write_text(json.dumps(attributions))
    (tmp_path / "e.json").write_text(json.dumps(events))
    named = identity.dated_names(tmp_path / "a.json", tmp_path / "e.json")
    edges = identity.edges(write(tmp_path))
    at = {when: identity.groups(edges, when, named).set_index("node_id").loc["C"] for when in
          ("2022-12-01 16:00", "2022-12-01 18:00", "2022-12-02 00:00")}
    assert pd.isna(at["2022-12-01 16:00"]["name"]) and pd.isna(at["2022-12-01 16:00"]["names"])
    assert at["2022-12-01 18:00"]["name"] == "Buyer"
    assert pd.isna(at["2022-12-02 00:00"]["name"]) and at["2022-12-02 00:00"]["names"] == "Buyer; Fleet"


def test_two_times_on_one_day_are_ordered_by_instant_in_any_order(tmp_path):
    edges = identity.edges(write(tmp_path))
    rows = [("X", "2022-12-01 09:00"), ("Y", "2022-12-01 17:00")]
    for order in (rows, rows[::-1]):
        named = pd.DataFrame([{"attribution_id": name, "address": "addr4", "name": name, "named_from": pd.Timestamp(at),
                               "evidence_from": pd.Timestamp(at)} for name, at in order])
        assert identity.groups(edges, "2022-12-01 12:00", named).set_index("node_id").loc["C", "name"] == "X"
        assert identity.groups(edges, "2022-12-01 18:00", named).set_index("node_id").loc["C", "name"] == "Y"
