"""Identity v0: dated identity edges and the operator groups they give at any instant, using only evidence before it.

An edge links a validator node to a reward address its stake names, dated by the stake's acceptance time, when the chain
first showed the link. At an instant, each node takes the addresses of its latest stake accepted by then, which may be a
stake that starts later, and nodes that share one of those addresses form one group (tier AS5, our own clustering: a
shared address links nodes but does not prove one decision maker). At tier AS1, nodes join only through an address an
AS1 attribution names by then, and every other node is a group of its own. Only current addresses join nodes. Chaining through every address a node was ever paid to
merges different operators: on real data a few node IDs that moved between operators joined GoGoPool's 1,885 nodes and
the genesis holder's 327 into one group. A group is
named when one of its addresses carries an AS1 attribution whose public evidence date, from the operator events, is on
or before the instant. An attribution without an evidence date names nothing. Because every edge and name is filtered by
its date, the groups at an instant are the same whether history is cut there or not, which the truncation test checks.
That holds because ``replaces`` in the attribution registry means a correction of an annotation, never a dated change of
owner: ``dated_names`` refuses a replaced AS1 reward-address name that differs from its replacement's. A change of owner
is a new row with its own evidence date.

An evidence time with a clock reading is an exact UTC instant. A date alone means public at some moment that UTC day, so
its name applies only from the end of that day, and nothing is named before its evidence was surely public. An address
takes the name whose evidence time is the latest by the instant, so a later row is a change of owner from its time. Two
names whose evidence times cannot be ordered, the same instant or a date alone on the day of another time, are both
kept as a conflict. Two clock times on one day are ordered, and the later name applies from its instant.

``edges`` refuses a node with two stakes accepted at the same instant, since its latest addresses would be ambiguous. A
group with two dated names gets no ``name`` and lists both in ``names``. Group sizes count every node with an edge by
then, not the active fleet. A consumer that needs the owner of one commitment joins that commitment's own reward
addresses by its transaction hash, not a node's group, because a node's latest stake can be a later one.

The existing ``derived.operators`` groups by each node's latest reward address, which reads the future at any past
origin. These groups are the ones a model or fit at an origin may use.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from ...core.catalog import DataError

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
    ties = frame.groupby(["node_id", "evidence_at"])["transaction_hash"].nunique()
    if (ties > 1).any():
        node, at = ties[ties > 1].index[0]
        raise DataError(f"node {node} has {int((ties > 1).sum())} acceptance instants with two stakes, first at {at}: its addresses are ambiguous")
    return frame.sort_values(["evidence_at", "transaction_hash", "address"], kind="stable").reset_index(drop=True)


def evidence_window(value: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """When evidence became public, as naive UTC: one instant for a time of day, the whole UTC day for a date alone."""
    stamp = pd.Timestamp(value)
    stamp = (stamp.tz_convert("UTC").tz_localize(None) if stamp.tzinfo else stamp).as_unit("us")
    if len(value.strip()) == 10:
        return stamp, stamp + pd.to_timedelta(86_400_000_000 - 1, unit="us")
    return stamp, stamp


def dated_names(attributions_path: Path = ATTRIBUTIONS, events_path: Path = EVENTS) -> pd.DataFrame:
    """AS1 evidence attributions of reward addresses not replaced by a later row, each dated by the earliest identity
    event that names it: ``named_from`` is the end of its evidence window, from which the name applies, and
    ``evidence_from`` its start."""
    attributions = json.loads(attributions_path.read_text())["attributions"]
    events = json.loads(events_path.read_text())["events"]
    dated: dict[str, tuple[pd.Timestamp, pd.Timestamp]] = {}
    for event in events:
        if event["kind"] == "identity" and event["evidence_public_at"]:
            window = evidence_window(event["evidence_public_at"])
            for code in event["attributions"]:
                if code not in dated or window[1] < dated[code][1]:
                    dated[code] = window
    replaced = {row["replaces"] for row in attributions if row["replaces"]}
    by_id = {row["attribution_id"]: row for row in attributions}
    for row in attributions:
        old = by_id.get(row["replaces"]) if row["replaces"] else None
        if old and old["subject_kind"] == "reward-address" and old["tier"] == "AS1" and old["class"] == "EVIDENCE" and old["name"] != row["name"]:
            raise DataError(f"{row['attribution_id']} replaces {old['attribution_id']} with another name: a change of owner needs its own row")
    rows = [{"attribution_id": row["attribution_id"], "address": row["subject"], "name": row["name"],
             "named_from": dated[row["attribution_id"]][1] if row["attribution_id"] in dated else None,
             "evidence_from": dated[row["attribution_id"]][0] if row["attribution_id"] in dated else None}
            for row in attributions
            if row["subject_kind"] == "reward-address" and row["tier"] == "AS1" and row["class"] == "EVIDENCE"
            and row["attribution_id"] not in replaced]
    return pd.DataFrame(rows, columns=["attribution_id", "address", "name", "named_from", "evidence_from"])


def utc_naive(at: datetime | str) -> pd.Timestamp:
    """The stake log's times are naive UTC. An aware instant is converted to UTC first."""
    stamp = pd.Timestamp(at)
    return stamp.tz_convert("UTC").tz_localize(None) if stamp.tzinfo else stamp


def groups(edge_table: pd.DataFrame, at: datetime | str, names: pd.DataFrame | None = None, tier: str = "AS5") -> pd.DataFrame:
    """Every node with an edge dated on or before ``at``: its group by the addresses of its latest stake by then, the
    group's size, its name when one is dated by then, and every such name. At ``tier="AS1"`` only named addresses join
    nodes."""
    if tier not in ("AS1", "AS5"):
        raise ValueError(f"tier must be AS1 or AS5, not {tier}")
    at = utc_naive(at)
    dated: dict[str, set[str]] = {}
    if names is not None:
        known_names = names[names["named_from"].notna() & (names["named_from"] <= at)]
        starts = known_names["evidence_from"] if "evidence_from" in known_names else known_names["named_from"]
        known_names = known_names.assign(evidence_from=starts.fillna(known_names["named_from"]))
        for address, rows in known_names.groupby("address"):
            latest = rows["named_from"].max()
            start = rows.loc[rows["named_from"] == latest, "evidence_from"].min()
            dated[address] = set(rows.loc[rows["named_from"] >= start, "name"])
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
        if tier == "AS1" and address not in dated:
            find("node:" + node)
            continue
        a, b = find("node:" + node), find("address:" + address)
        if a != b:
            parent[max(a, b)] = min(a, b)
    members: dict[str, list[str]] = {}
    for key in parent:
        members.setdefault(find(key), []).append(key)
    named: dict[str, set[str]] = {}
    for address, found in dated.items():
        if "address:" + address in parent:
            named.setdefault(find("address:" + address), set()).update(found)
    rows = []
    for root, keys in members.items():
        nodes = sorted(key[5:] for key in keys if key.startswith("node:"))
        group_id = "group:" + nodes[0] if nodes else "group:" + root
        for node in nodes:
            found = sorted(named.get(root, ()))
            rows.append({"node_id": node, "group_id": group_id, "group_nodes": len(nodes), "name": found[0] if len(found) == 1 else None,
                         "names": "; ".join(found) or None})
    return pd.DataFrame(rows, columns=["node_id", "group_id", "group_nodes", "name", "names"]).sort_values("node_id").reset_index(drop=True)


def resolve(edge_table: pd.DataFrame, node_id: str, at: datetime | str, names: pd.DataFrame | None = None, tier: str = "AS5") -> dict:
    """The group of one node at ``at``: its id, members and name, or None when the node has no edge yet."""
    table = groups(edge_table, at, names, tier)
    row = table[table["node_id"] == node_id]
    if row.empty:
        return {"node_id": node_id, "group_id": None, "members": [], "name": None}
    group_id = row["group_id"].iloc[0]
    return {"node_id": node_id, "group_id": group_id, "members": table[table["group_id"] == group_id]["node_id"].tolist(),
            "name": row["name"].iloc[0]}
