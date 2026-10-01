#!/usr/bin/env python3
"""The two levers on a validator's choice of duration and stake, and the delegation firewall: a Graphviz diagram.

    uv run python scripts/figures/pilot_levers_diagram.py <output folder>

Each edge states a rule the code holds:

- ACP-285 lowers the minimum consumption rate from 10% to 7.5% over a 90-day ramp, so the reward rate rises
  more steeply with committed duration (avalanche_research.model.protocol). It lowers issuance for short
  commitments rather than raising it for long ones.
- The admission frontier sets the minimum stake by duration (avalanche_research.mechanisms.admission). A gate
  issues nothing.
- Delegations keep a 14-day minimum duration (protocol.min_stake_duration_seconds with role "delegator"), so a
  validator seat shorter than 14 days can receive no delegation.

Writes `levers.dot`, `levers.svg` and `levers.png` with the system `dot` command, in the house colours.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from avalanche_research.palette import QUANTITY_COLORS

INK, MUTED, PAPER = "#333333", "#7a7f87", "#ffffff"
FONT = "Helvetica"


def node(name: str, label: str, color: str, fill: str = PAPER, bold: bool = False) -> str:
    weight = "<B>" + label + "</B>" if bold else label
    return (f'  {name} [label=<{weight}>, shape=box, style="rounded,filled", fillcolor="{fill}", color="{color}", '
            f'penwidth=2.5, fontname="{FONT}", fontsize=15, fontcolor="{INK}", margin="0.25,0.14"];')


def edge(source: str, target: str, label: str, color: str, dashed: bool = False) -> str:
    style = "dashed" if dashed else "solid"
    return (f'  {source} -> {target} [label=<&nbsp;&nbsp;{label}&nbsp;&nbsp;>, color="{color}", fontcolor="{INK}", fontname="{FONT}", '
            f'fontsize=13, penwidth=2.5, style={style}, arrowsize=0.9];')


def dot_source() -> str:
    reward, stake, duration = QUANTITY_COLORS["rewards"], QUANTITY_COLORS["stake"], QUANTITY_COLORS["duration"]
    lines = [
        "digraph levers {",
        f'  graph [rankdir=TB, bgcolor="{PAPER}", nodesep=0.6, ranksep=0.75, pad=0.3, fontname="{FONT}"];',
        node("reward", "ACP-285 reward curve<BR/><FONT POINT-SIZE='12' COLOR='#7a7f87'>lowers the reward rate for short commitments,<BR/>so pay rises faster with duration</FONT>", reward),
        node("frontier", "Admission frontier<BR/><FONT POINT-SIZE='12' COLOR='#7a7f87'>minimum stake falls as duration rises<BR/>cost: none, it is a gate</FONT>", stake),
        node("choice", "A validator chooses<BR/>duration and stake", INK, fill="#f4f5f7", bold=True),
        node("seat", "With the frontier, every validator commitment<BR/>holds at least 28,000 AVAX-days", stake),
        node("firewall", "Delegators: 14-day minimum<BR/><FONT POINT-SIZE='12' COLOR='#7a7f87'>unchanged by Helicon</FONT>", duration),
        node("short", "Validator commitments shorter than 14 days", MUTED),
        "  { rank=same; reward; frontier; firewall; }",
        edge("reward", "choice", "the carrot: reward for duration", reward),
        edge("frontier", "choice", "the stick: stake required by duration", stake),
        edge("choice", "seat", "commitments admitted", INK),
        edge("firewall", "short", "no delegation possible", duration, dashed=True),
        edge("choice", "short", "the new 48-hour tier", MUTED, dashed=True),
        "}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    source = out / "levers.dot"
    source.write_text(dot_source())
    subprocess.run(["dot", "-Tsvg", str(source), "-o", str(out / "levers.svg")], check=True)
    subprocess.run(["dot", "-Tpng", "-Gdpi=200", str(source), "-o", str(out / "levers.png")], check=True)


if __name__ == "__main__":
    main()
