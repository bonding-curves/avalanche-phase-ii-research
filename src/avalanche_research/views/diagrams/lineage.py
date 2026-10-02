"""The data path from the chain to the two tables the model reads, built from the run receipts.

Starting from the staking-period log and the daily monetary ledger, each run's capture receipt is read and its inputs
are followed back to the captured datasets and their providers. A receipt names its inputs in ``inputs`` (a derived
table) or in ``blocks_run`` (a capture that reads a P-Chain block walk). Rows come from each run's build receipt and the
seam from each seamed table's overlap record, so no number on the diagram is typed. The burn branch, every run that
reaches the model only through the ledger's burn inputs, is drawn as one node with its dataset and run counts, because
the staking model does not read it. The Data API supply snapshots stay as their own node: the ledger's check reads them. The model's reads come from its code: the replay reads the
staking-period log and compares with the ledger, and the lifecycle model takes its origin from the staking-period log.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ... import datasets
from ...catalog import load_catalog
from . import Diagram, Node

PERIODS = "derived.staking-periods"
LEDGER = "derived.avax-monetary-daily"
DEFAULT_RUNS = {PERIODS: "staking-periods-2026-09-30", LEDGER: "avax-monetary-daily-2026-09-30"}
# What the model reads, from its code: model.replay.daily_events and model.lifecycle.origin_inputs read the
# staking-period log, and model.replay.compare reads the ledger.
MODEL_READS = (("Replay", PERIODS), ("Replay", LEDGER), ("ValidatorLifecycle", PERIODS))
BURNS = "burn-record"
CHECKPOINTS = "data-api.avax-supply"
# Short provider names for the memo version, as the memo's text names them.
SHORT_NAMES = {"avalanche-snowflake": "Snowflake data share", "avalanche-p-chain-rpc": "P-Chain RPC",
               "avalanche-data-api": "Avalanche Data API", "avalanche-c-chain-rpc": "C-Chain RPC"}
RANKS = {"provider": 0, "capture": 1, "walk": 2, "seamed": 3, "periods": 4, "ledger": 5, "model": 6}


def _role(dataset_id: str) -> str:
    if dataset_id == PERIODS:
        return "periods"
    if dataset_id == LEDGER:
        return "ledger"
    if dataset_id.startswith("derived.seamed-"):
        return "seamed"
    return "walk" if dataset_id.startswith("derived.") else "capture"


def _inputs(capture: dict[str, Any]) -> list[tuple[str, str]]:
    found = [(item["dataset_id"], item["run"]) for item in capture.get("inputs", []) if "dataset_id" in item and "run" in item]
    if capture.get("blocks_run"):
        found.append(("p-chain-rpc.blocks", capture["blocks_run"]))
    return found


def walk(runs: dict[str, str] | None = None, root: Path | None = None) -> dict[tuple[str, str], dict[str, Any]]:
    """Every run the two tables depend on, with its receipts and the runs it reads."""
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    pending = list((runs or DEFAULT_RUNS).items())
    while pending:
        key = pending.pop()
        if key in seen:
            continue
        record = datasets.receipt(*key, root=root)
        seen[key] = {"capture": record["capture"], "build": record["build"], "inputs": _inputs(record["capture"])}
        pending.extend(seen[key]["inputs"])
    return seen


def _rows(build: dict[str, Any]) -> int | None:
    return (build.get("summary") or {}).get("rows")


def _seam_line(build: dict[str, Any]) -> str:
    overlap = (build.get("summary") or {}).get("overlap") or {}
    if not overlap:
        return ""
    differing = sum((overlap.get("differing_by_column") or {}).values()) + int(overlap.get("share_rows_missing_in_backup") or 0)
    return (f"share before {overlap.get('seam')} UTC, our walk from it\n"
            f"{overlap.get('rows_compared', 0):,} rows compared, {differing:,} differ")


def build(runs: dict[str, str] | None = None, root: Path | None = None, catalog: dict[str, Any] | None = None) -> Diagram:
    catalog = catalog or load_catalog()
    sources = {item["id"]: item["name"] for item in catalog["sources"]}
    source_of = {item["id"]: item["source_id"] for item in catalog["datasets"]}
    lineage = walk(runs, root)
    by_dataset: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for (dataset_id, run), record in lineage.items():
        by_dataset.setdefault(dataset_id, []).append((run, record))
    diagram = Diagram(
        title="Every row the model reads traces to a checked capture",
        subtitle=f"From runs {', '.join(sorted((runs or DEFAULT_RUNS).values()))}. Rows and seams are read from each run's receipt")

    # Everything the staking-period log depends on stays drawn. What else feeds the ledger is its burn branch.
    parents: dict[str, set[str]] = {}
    for (dataset_id, _), record in lineage.items():
        parents.setdefault(dataset_id, set()).update(input_id for input_id, _ in record["inputs"])
    kept, stack = set(), [PERIODS]
    while stack:
        current = stack.pop()
        if current not in kept:
            kept.add(current)
            stack.extend(parents.get(current, ()))
    burns = sorted(dataset_id for dataset_id in by_dataset if dataset_id not in kept | {LEDGER, CHECKPOINTS})

    def node_id(dataset_id: str) -> str:
        return BURNS if dataset_id in burns else dataset_id

    if burns:
        count = sum(len(by_dataset[dataset_id]) for dataset_id in burns)
        diagram.add(Node(BURNS, f"Burn record, P-, X- and C-Chain\n{len(burns)} datasets, {count} runs", "walk", RANKS["seamed"],
                         "Collapsed: " + ", ".join(burns)))
    for dataset_id, entries in sorted(by_dataset.items()):
        if dataset_id in burns:
            continue
        role = _role(dataset_id)
        entries.sort(key=lambda entry: entry[0])
        run_text = entries[0][0] if len(entries) == 1 else f"{len(entries)} runs"
        rows = [_rows(record["build"]) for _, record in entries]
        rows_text = f"{sum(rows):,} rows" if all(value is not None for value in rows) else ""
        lines = [dataset_id, run_text] + ([_seam_line(entries[0][1]["build"])] if role == "seamed" else [rows_text])
        tooltip = "; ".join(f"{run}: capture {record['capture'].get('capture_id')}, completed {record['capture'].get('completed_at')}"
                            for run, record in entries)
        diagram.add(Node(dataset_id, "\n".join(line for line in lines if line), role, RANKS[role], tooltip))
    for dataset_id in sorted(by_dataset):
        source_id = source_of.get(dataset_id)
        if source_id and source_id != "derived":
            provider = f"provider:{source_id}"
            diagram.add(Node(provider, sources[source_id], "provider", RANKS["provider"]))
            diagram.link(provider, node_id(dataset_id))
    for (dataset_id, _), record in lineage.items():
        for input_id, _ in record["inputs"]:
            diagram.link(node_id(input_id), node_id(dataset_id))
    for model, dataset_id in MODEL_READS:
        if dataset_id in by_dataset:
            diagram.add(Node(f"model:{model}", model, "model", RANKS["model"]))
            diagram.link(dataset_id, f"model:{model}")
    return diagram


def manifest(runs: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    lineage = walk(runs, root)
    return {"start_runs": runs or DEFAULT_RUNS, "runs": sorted(f"{dataset_id} {run}" for dataset_id, run in lineage)}


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _table(title: str, rows: list[tuple[str, ...]], note: str = "") -> str:
    """An HTML-like Graphviz label: a bold title, an optional note, and one row per dataset."""
    width = max(len(row) for row in rows) if rows else 1
    head = f'<TR><TD COLSPAN="{width}" ALIGN="LEFT"><B>{_escape(title)}</B></TD></TR>'
    if note:
        head += f'<TR><TD COLSPAN="{width}" ALIGN="LEFT"><FONT POINT-SIZE="12">{_escape(note)}</FONT></TD></TR>'
    body = "".join("<TR>" + "".join(f'<TD ALIGN="{"LEFT" if i == 0 else "RIGHT"}"><FONT POINT-SIZE="12">{_escape(cell)}</FONT></TD>'
                                    for i, cell in enumerate(row)) + "</TR>" for row in rows)
    return f'<TABLE BORDER="0" CELLSPACING="0" CELLPADDING="3">{head}{body}</TABLE>'


def build_memo(runs: dict[str, str] | None = None, root: Path | None = None, catalog: dict[str, Any] | None = None) -> Diagram:
    """The same lineage at memo width: one box per provider with its captures, one for our walk, one for the seamed
    tables, the burn branch as one box, the two tables the model reads, and the model. An edge joins two boxes when a
    receipt in one names a run in the other."""
    full = build(runs, root, catalog)
    catalog = catalog or load_catalog()
    sources = {item["id"]: item["name"] for item in catalog["sources"]}
    lineage = walk(runs, root)
    builds: dict[str, list[dict[str, Any]]] = {}
    for (dataset_id, _), record in lineage.items():
        builds.setdefault(dataset_id, []).append(record["build"])

    def group(node_id: str) -> str:
        node = full.nodes[node_id]
        if node.role == "capture":
            source_id = next(edge[0] for edge in full.edges if edge[1] == node_id and edge[0].startswith("provider:"))
            return source_id
        if node.role == "walk" and node_id != BURNS:
            return "walk"
        if node.role == "seamed":
            return "seamed"
        return node_id

    diagram = Diagram(title="Every row the model reads traces to a checked capture",
                      subtitle="Every count is read from a run receipt", rankdir="TB")
    members: dict[str, list[str]] = {}
    for node_id, node in full.nodes.items():
        if node.role not in ("provider", "model"):
            members.setdefault(group(node_id), []).append(node_id)

    def rows_of(dataset_id: str) -> str:
        total = sum((build.get("summary") or {}).get("rows") or 0 for build in builds.get(dataset_id, []))
        return f"{total:,} rows"

    for key, ids in sorted(members.items()):
        ids.sort()
        if key.startswith("provider:"):
            source_id = key.removeprefix("provider:")
            label = _table(SHORT_NAMES.get(source_id, sources[source_id]), [(i.split(".", 1)[1], rows_of(i)) for i in ids])
            diagram.add(Node(key, label, "capture", 0, html=True))
        elif key == "walk":
            diagram.add(Node(key, _table("Our P-Chain walk", [(i.removeprefix("derived."), rows_of(i)) for i in ids]), "walk", 1, html=True))
        elif key == "seamed":
            overlaps = [(builds[i][0].get("summary") or {}).get("overlap") or {} for i in ids]
            seam = sorted({str(o.get("seam")) for o in overlaps if o})
            rows = [(i.removeprefix("derived."), f"{o.get('rows_compared', 0):,} compared", f"{sum((o.get('differing_by_column') or {}).values()):,} differ")
                    for i, o in zip(ids, overlaps)]
            note = f"Share before {', '.join(seam)} UTC, our walk from it"
            diagram.add(Node(key, _table("Seamed tables", rows, note), "seamed", 2, html=True))
        elif key == BURNS:
            diagram.add(Node(key, full.nodes[BURNS].label, "walk", 2, full.nodes[BURNS].tooltip))
        else:
            node = full.nodes[key]
            diagram.add(Node(key, node.label, node.role, {"periods": 3, "ledger": 4}.get(node.role, 2), node.tooltip))
    for node_id, node in full.nodes.items():
        if node.role == "model":
            diagram.add(Node(node_id, node.label, "model", 5))
    for source, target in full.edges:
        if source.startswith("provider:"):
            continue
        a = group(source) if full.nodes[source].role != "model" else source
        b = group(target) if full.nodes[target].role != "model" else target
        if a != b:
            diagram.link(a, b)
    return diagram
