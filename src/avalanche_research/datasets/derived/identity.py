"""Identity v0: dated identity edges and the operator groups they give at any instant, using only evidence before it.

An edge links a validator node to a reward address its stake names, dated by the stake's acceptance time, when the chain
first showed the link. At an instant, each node is paid to the addresses of its latest stake accepted by then, and nodes
that share one of those addresses form one group (tier AS5, our own clustering: a shared address links nodes but does
not prove one decision maker). Only current addresses join nodes. Chaining through every address a node was ever paid to
merges different operators: on real data a few node IDs that moved between operators joined GoGoPool's 1,885 nodes and
the genesis holder's 327 into one group. A group is
named when one of its addresses carries an AS1 attribution whose public evidence date, from the operator events, is on
or before the instant. An attribution without an evidence date names nothing. Because every edge and name is filtered by
its date, the groups at an instant are the same whether history is cut there or not, which the truncation test checks.

The existing ``derived.operators`` groups by each node's latest reward address, which reads the future at any past
origin. These groups are the ones a model or fit at an origin may use.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
ATTRIBUTIONS = ROOT / "data" / "operator-attributions.json"
EVENTS = ROOT / "data" / "operator-events.json"

EDGES_SQL = """
SELECT DISTINCT node_id, unnest(from_json(reward_addresses, '["VARCHAR"]')) AS address, accepted_at AS evidence_at, transaction_hash
FROM read_parquet('{validators}') WHERE reward_addresses IS NOT NULL AND accepted_at IS NOT NULL
"""


def edges(validators_parquet: str) -> pd.DataFrame:
    """One row per validator stake and reward address it names, earliest first."""
    sql = EDGES_SQL.format(validators=validators_parquet.replace("'", "''"))
    frame = duckdb.sql(sql).df()
    return frame.sort_values(["evidence_at", "transaction_hash", "address"], kind="stable").reset_index(drop=True)


def dated_names(attributions_path: Path = ATTRIBUTIONS, events_path: Path = EVENTS) -> pd.DataFrame:
    """AS1 evidence attributions of reward addresses not replaced by a later row, each dated by the earliest identity
    event that names it."""
    attributions = json.loads(attributions_path.read_text())["attributions"]
    events = json.loads(events_path.read_text())["events"]
    dated: dict[str, str] = {}
    for event in events:
        if event["kind"] == "identity" and event["evidence_public_at"]:
            for code in event["attributions"]:
                dated[code] = min(dated.get(code, event["evidence_public_at"]), event["evidence_public_at"])
    replaced = {row["replaces"] for row in attributions if row["replaces"]}
    rows = [{"attribution_id": row["attribution_id"], "address": row["subject"], "name": row["name"],
             "named_from": pd.Timestamp(dated[row["attribution_id"]]).tz_localize(None) if row["attribution_id"] in dated else None}
            for row in attributions
            if row["subject_kind"] == "reward-address" and row["tier"] == "AS1" and row["class"] == "EVIDENCE"
            and row["attribution_id"] not in replaced]
    return pd.DataFrame(rows, columns=["attribution_id", "address", "name", "named_from"])


def utc_naive(at: datetime | str) -> pd.Timestamp:
    """The stake log's times are naive UTC. An aware instant is converted to UTC first."""
    stamp = pd.Timestamp(at)
    return stamp.tz_convert("UTC").tz_localize(None) if stamp.tzinfo else stamp


def groups(edge_table: pd.DataFrame, at: datetime | str, names: pd.DataFrame | None = None) -> pd.DataFrame:
    """Every node with an edge dated on or before ``at``: its group by the addresses of its latest stake by then, the
    group's size, and its name if dated by then."""
    at = utc_naive(at)
    known = edge_table[edge_table["evidence_at"] <= at]
    latest = known.groupby("node_id")["evidence_at"].transform("max")
    known = known[known["evidence_at"] == latest]
    parent: dict[str, str] = {}

    def find(key: str) -> str:
        while parent.setdefault(key, key) != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for node, address in zip(known["node_id"], known["address"], strict=True):
        a, b = find("node:" + node), find("address:" + address)
        if a != b:
            parent[max(a, b)] = min(a, b)
    members: dict[str, list[str]] = {}
    for key in parent:
        members.setdefault(find(key), []).append(key)
    named: dict[str, str] = {}
    if names is not None:
        for row in names.itertuples():
            if row.named_from is not None and pd.notna(row.named_from) and row.named_from <= at and "address:" + row.address in parent:
                named.setdefault(find("address:" + row.address), row.name)
    rows = []
    for root, keys in members.items():
        nodes = sorted(key[5:] for key in keys if key.startswith("node:"))
        group_id = "group:" + nodes[0] if nodes else "group:" + root
        for node in nodes:
            rows.append({"node_id": node, "group_id": group_id, "group_nodes": len(nodes), "name": named.get(root)})
    return pd.DataFrame(rows, columns=["node_id", "group_id", "group_nodes", "name"]).sort_values("node_id").reset_index(drop=True)


def resolve(edge_table: pd.DataFrame, node_id: str, at: datetime | str, names: pd.DataFrame | None = None) -> dict:
    """The group of one node at ``at``: its id, members and name, or None when the node has no edge yet."""
    table = groups(edge_table, at, names)
    row = table[table["node_id"] == node_id]
    if row.empty:
        return {"node_id": node_id, "group_id": None, "members": [], "name": None}
    group_id = row["group_id"].iloc[0]
    return {"node_id": node_id, "group_id": group_id, "members": table[table["group_id"] == group_id]["node_id"].tolist(),
            "name": row["name"].iloc[0]}
