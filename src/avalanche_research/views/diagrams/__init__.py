"""Structure diagrams as Graphviz `dot`, generated in Python and never written by hand.

A diagram is a list of nodes, each with a role, and a list of edges. The role sets the node's style from one table of
house tokens, so every diagram draws a role the same way, and the legend lists exactly the roles a diagram uses. The DOT
text is sorted, so two builds of the same diagram give the same bytes. ``save`` writes the DOT, the SVG, a PNG at 288 dpi
(three times 96 CSS pixels per inch, the scale of the chart PNGs), and a JSON manifest with the node ids, their roles,
the source commit, and the Graphviz version.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ...palette import QUANTITY_COLORS

# Neutral diagram tokens: ink for text and the model, a grey for borders and edges that no quantity uses.
INK = "#1f2328"
MUTED = "#6b7785"

# One style per role: (shape, fill, border, border width, line style, font colour, extra attributes).
ROLE_STYLES = {
    "provider": ("box", "#f1f2f4", MUTED, 1.2, "dashed,rounded,filled", INK, {}),
    "capture": ("box", "#ffffff", MUTED, 1.2, "rounded,filled", INK, {}),
    "walk": ("box", "#eef1f5", INK, 1.2, "rounded,filled", INK, {}),
    "seamed": ("box", "#ffffff", INK, 1.2, "rounded,filled", INK, {"peripheries": "2"}),
    "periods": ("box", "#ffffff", QUANTITY_COLORS["stake"], 3.0, "rounded,filled", INK, {}),
    "ledger": ("box", "#ffffff", QUANTITY_COLORS["rewards"], 3.0, "rounded,filled", INK, {}),
    "model": ("box", INK, INK, 1.2, "rounded,filled", "#ffffff", {}),
}
ROLE_NAMES = {
    "provider": "Provider",
    "capture": "Captured dataset",
    "walk": "Our P-Chain walk",
    "seamed": "Share before the seam, our walk from it",
    "periods": "Staking-period log",
    "ledger": "Daily monetary ledger",
    "model": "Model",
}


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    role: str
    rank: int
    tooltip: str = ""
    html: bool = False


@dataclass
class Diagram:
    title: str
    subtitle: str
    rankdir: str = "LR"
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: set[tuple[str, str]] = field(default_factory=set)

    def add(self, node: Node) -> None:
        if node.role not in ROLE_STYLES:
            raise ValueError(f"unknown role {node.role!r}")
        self.nodes.setdefault(node.id, node)

    def link(self, source: str, target: str) -> None:
        if source not in self.nodes or target not in self.nodes:
            raise ValueError(f"edge between unknown nodes: {source} -> {target}")
        if source != target:
            self.edges.add((source, target))

    def roles(self) -> list[str]:
        used = {node.role for node in self.nodes.values()}
        return [role for role in ROLE_STYLES if role in used]


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _attributes(values: dict[str, str]) -> str:
    return ", ".join(f"{key}={value if key == 'label' and str(value).startswith('<<') else _quote(str(value))}"
                     for key, value in sorted(values.items()))


def _style(role: str) -> dict[str, str]:
    shape, fill, border, width, style, font, extra = ROLE_STYLES[role]
    return {"shape": shape, "fillcolor": fill, "color": border, "penwidth": f"{width}", "style": style, "fontcolor": font, **extra}


def to_dot(diagram: Diagram) -> str:
    """Sorted DOT text: nodes by rank then id, edges by endpoints, the legend from the roles used."""
    lines = [
        "digraph G {",
        f'  graph [{_attributes({"rankdir": diagram.rankdir, "bgcolor": "white", "fontname": "Arial", "fontsize": "20", "labelloc": "t", "labeljust": "l", "nodesep": "0.25", "ranksep": "0.45", "splines": "spline", "newrank": "true", "concentrate": "true"})}, label={_quote(diagram.title + chr(1) + diagram.subtitle + chr(1)).replace(chr(1), chr(92) + "l")}];',
        f'  node [{_attributes({"fontname": "Arial", "fontsize": "14", "margin": "0.15,0.08"})}];',
        f'  edge [{_attributes({"color": MUTED, "arrowsize": "0.7", "penwidth": "1.1"})}];',
    ]
    last = max(node.rank for node in diagram.nodes.values())
    for rank in sorted({node.rank for node in diagram.nodes.values()}):
        members = sorted((node for node in diagram.nodes.values() if node.rank == rank), key=lambda node: node.id)
        lines.append('  { rank=same; "~legend";' if rank == last else "  { rank=same;")
        for node in members:
            values = {**_style(node.role), "label": f"<{node.label}>" if node.html else node.label}
            if node.tooltip:
                values["tooltip"] = node.tooltip
            lines.append(f"    {_quote(node.id)} [{_attributes(values)}];")
        lines.append("  }")
    for source, target in sorted(diagram.edges):
        lines.append(f"  {_quote(source)} -> {_quote(target)};")
    rows = "".join(
        f'<TR><TD WIDTH="22" HEIGHT="14" BGCOLOR="{ROLE_STYLES[role][1]}" COLOR="{ROLE_STYLES[role][2]}" BORDER="2"></TD>'
        f'<TD ALIGN="LEFT"><FONT POINT-SIZE="13">{ROLE_NAMES[role]}</FONT></TD></TR>' for role in diagram.roles())
    lines.append('  "~legend" [shape=plaintext, label=<<TABLE BORDER="0" CELLSPACING="4">'
                 f'<TR><TD COLSPAN="2" ALIGN="LEFT"><B>Legend</B></TD></TR>{rows}</TABLE>>];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def dot_version() -> str:
    return subprocess.run(["dot", "-V"], check=True, capture_output=True, text=True).stderr.strip()


def save(diagram: Diagram, folder: Path, name: str, manifest: dict | None = None) -> dict[str, Path]:
    """Write NAME.dot, .svg, .png and .json. Refuses a diagram for which Graphviz prints a warning."""
    folder.mkdir(parents=True, exist_ok=True)
    text = to_dot(diagram)
    paths = {kind: folder / f"{name}.{kind}" for kind in ("dot", "svg", "png", "json")}
    paths["dot"].write_text(text, encoding="utf-8")
    for kind, extra in (("svg", []), ("png", ["-Gdpi=288"])):
        done = subprocess.run(["dot", f"-T{kind}", *extra, "-o", str(paths[kind]), str(paths["dot"])], capture_output=True, text=True, check=False)
        if done.returncode or done.stderr.strip():
            raise RuntimeError(f"dot -T{kind} failed or warned: {done.stderr.strip()}")
    record = {"name": name, "graphviz": dot_version(), "nodes": {node.id: node.role for node in sorted(diagram.nodes.values(), key=lambda n: n.id)},
              "edges": [list(edge) for edge in sorted(diagram.edges)], **(manifest or {})}
    paths["json"].write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return paths
