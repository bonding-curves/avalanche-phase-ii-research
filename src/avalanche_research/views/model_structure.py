"""The structure of a cadCAD model, traced from its code and drawn with Graphviz.

``trace`` runs each policy and each state update of a model once on its own initial state, with the state
and the policy signal wrapped in dictionaries that record every key read. The result says exactly which
state each policy reads, which signal keys it returns, and which state and signal keys each update reads
and which variable it writes. ``lifecycle_dot`` draws that trace for ``ValidatorLifecycle``, adding the
behaviour blocks and the reward mechanism the policy calls, the inputs measured before the origin, and the
invariants checked each day. Nothing in the drawing is typed by hand except the labels of the input groups.
"""

from __future__ import annotations

import inspect
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from avalanche_research.model.blocks import Renewal
from avalanche_research.model.engine import SimulationModel
from avalanche_research.model.lifecycle import Entry, ValidatorLifecycle
from avalanche_research.palette import QUANTITY_COLORS

INK = "#2b2b2b"
MUTED = "#7a7f87"
PAPER = "#ffffff"
FONT = "DejaVu Sans"
META_KEYS = ("run", "timestep", "substep", "simulation")


class _Recorder(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.read: list[str] = []

    def __getitem__(self, key):
        if key not in self.read:
            self.read.append(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key not in self.read:
            self.read.append(key)
        return super().get(key, default)


@dataclass
class Trace:
    state: list[str]
    policies: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    updates: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    invariants: list[str] = field(default_factory=list)


def trace(model: SimulationModel) -> Trace:
    """Which keys each policy and update of ``model`` reads and writes, from one recorded call of each."""
    initial = model.initial_state()
    result = Trace(state=list(initial), invariants=[name for name, _check in model.invariants()])
    for block in model.blocks():
        signal: dict[str, Any] = {}
        for name, policy in block["policies"].items():
            state = _Recorder({**initial, "run": 0, "timestep": 0, "substep": 1, "simulation": 0})
            out = policy({}, 1, [], state)
            signal.update(out)
            result.policies[name] = {"reads": [k for k in state.read if k not in META_KEYS], "meta": [k for k in state.read if k in META_KEYS], "returns": list(out)}
        for variable, update in block["variables"].items():
            state = _Recorder({**initial, "run": 0, "timestep": 0, "substep": 1, "simulation": 0})
            recorded_signal = _Recorder(signal)
            written, _value = update({}, 1, [], state, recorded_signal)
            result.updates[variable] = {"writes": [written], "reads_state": [k for k in state.read if k not in META_KEYS], "reads_signal": list(recorded_signal.read)}
    return result


def tiny_lifecycle(**settings: Any) -> ValidatorLifecycle:
    """A lifecycle model on a small synthetic state, enough to trace its structure."""
    nav = 10**9
    return ValidatorLifecycle(
        initial_stakes=np.array([2_000 * nav, 5_000 * nav]), initial_days_left=np.array([1, 10]),
        initial_periods_done=np.array([0, 3]), draw_durations=np.array([14, 30]), draw_stakes=np.array([2_000 * nav]),
        timesteps=2, runs=1, **settings,
    )


def _node(name: str, label: str, color: str, shape: str = "box", style: str = "rounded", fill: str = PAPER, dashed: bool = False) -> str:
    styles = style + (",dashed" if dashed else "") + ",filled"
    return (f'  "{name}" [label=<{label}>, shape={shape}, style="{styles}", color="{color}", fillcolor="{fill}", '
            f'penwidth=2, fontname="{FONT}", fontsize=13, fontcolor="{INK}", margin="0.18,0.08"];')


def _edge(a: str, b: str, label: str = "", color: str = MUTED, dashed: bool = False) -> str:
    style = "dashed" if dashed else "solid"
    text = f', label=" {label} ", fontname="{FONT}", fontsize=10, fontcolor="{MUTED}"' if label else ""
    return f'  "{a}" -> "{b}" [color="{color}", penwidth=1.6, style={style}, arrowsize=0.7{text}];'


def _small(text: str) -> str:
    return f"<BR/><FONT POINT-SIZE='10' COLOR='{MUTED}'>{text}</FONT>"


INPUT_GROUPS = {
    "open commitments at the origin": ("initial_stakes", "initial_days_left", "initial_periods_done"),
    "commitments accepted, not yet started": ("scheduled_start_day", "scheduled_stakes", "scheduled_days"),
    "durations and stakes of the year before": ("draw_durations", "draw_stakes"),
    "renewal share and entry rate of the year before": ("renewal_probability", "entry_rate_per_day"),
    "reward counter at the origin": ("supply0_navax",),
}


def lifecycle_dot(model: ValidatorLifecycle | None = None) -> str:
    """Graphviz source for the lifecycle model's structure, from ``trace``."""
    model = model or tiny_lifecycle()
    t = trace(model)
    policy_name, policy = next(iter(t.policies.items()))
    teal = "#0e7c86"
    lines = [
        "digraph lifecycle {",
        f'  graph [rankdir=LR, bgcolor="{PAPER}", nodesep=0.35, ranksep=0.9, pad=0.3, fontname="{FONT}", newrank=true, compound=true];',
        '  subgraph cluster_inputs { label=<<B>Inputs, measured before the origin</B>>; fontsize=13; fontname="' + FONT + f'"; color="{MUTED}"; style="rounded,dashed";',
    ]
    for group, params in INPUT_GROUPS.items():
        present = [p for p in params if p in model.param]
        if present:
            lines.append(_node(f"in:{group}", group + _small(", ".join(present)), MUTED, dashed=True))
    lines.append("  }")
    lines.append('  subgraph cluster_policy { label=<<B>Each day: the policy</B>>; fontsize=13; fontname="' + FONT + f'"; color="{INK}"; style=rounded;')
    lines.append(_node(f"policy:{policy_name}", f"<B>{policy_name}</B>" + _small("one UTC day per step, reads " + ", ".join(policy["reads"])), INK, shape="box", fill="#f4f5f7"))
    renewal, entry = Renewal(), Entry()
    lines.append(_node("block:renewal", f"Renewal: {renewal.decision}" + _small(f"probability, source {renewal.sources()['probability']['source']}"), QUANTITY_COLORS["nodes"]))
    lines.append(_node("block:entry", f"Entry: {entry.decision}" + _small("Poisson count at a daily rate"), QUANTITY_COLORS["nodes"]))
    lines.append(_node("block:draws", "Duration and stake draws" + _small("from the year before the origin"), QUANTITY_COLORS["duration"]))
    reward_args = [p for p in inspect.signature(model.mechanism.potential_reward_navax).parameters if p != "self"]
    lines.append(_node("block:mechanism", f"Reward mechanism: {model.mechanism.label}" + _small("potential reward from " + ", ".join(reward_args)), QUANTITY_COLORS["rewards"]))
    lines.append("  }")
    lines.append('  subgraph cluster_state { label=<<B>State after the day, read by the policy the next day</B>>; fontsize=13; fontname="' + FONT + f'"; color="{QUANTITY_COLORS["stake"]}"; style=rounded;')
    rules = {}
    for variable, update in t.updates.items():
        signal_keys, state_keys = update["reads_signal"], update["reads_state"]
        if state_keys and signal_keys:
            rules[variable] = f"previous {', '.join(state_keys)} + {', '.join(signal_keys)}"
        elif signal_keys == [variable]:
            rules[variable] = "set by the policy"
        else:
            rules[variable] = "from " + ", ".join(signal_keys)
    for variable in t.state:
        lines.append(_node(f"state:{variable}", variable + _small(rules.get(variable, "")), QUANTITY_COLORS["stake"], shape="cylinder", style="solid"))
    lines.append("  }")
    lines.append('  subgraph cluster_checks { label=<<B>Checked every day</B>>; fontsize=13; fontname="' + FONT + f'"; color="{MUTED}"; style=rounded;')
    lines.append(_node("checks", "<BR/>".join(t.invariants), MUTED))
    lines.append("  }")
    for group in INPUT_GROUPS:
        if f"in:{group}" in "\n".join(lines):
            lines.append(_edge(f"in:{group}", f"policy:{policy_name}", dashed=True))
    for block in ("block:renewal", "block:entry", "block:draws", "block:mechanism"):
        lines.append(_edge(f"policy:{policy_name}", block, color=INK))
    for variable in t.updates:
        lines.append(_edge(f"policy:{policy_name}", f"state:{variable}", color=teal))
    lines.append(f'  "state:{t.state[0]}" -> "checks" [ltail=cluster_state, color="{MUTED}", penwidth=1.6, style=dashed, arrowsize=0.7];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def render(dot_source: str, out_stem: Path) -> list[Path]:
    """Write ``.dot``, ``.svg`` and ``.png`` beside ``out_stem`` with the system ``dot`` command."""
    if shutil.which("dot") is None:
        raise RuntimeError("Graphviz `dot` is not installed")
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    source = out_stem.with_suffix(".dot")
    source.write_text(dot_source)
    paths = [source]
    for fmt, extra in (("svg", []), ("png", ["-Gdpi=170"])):
        target = out_stem.with_suffix(f".{fmt}")
        subprocess.run(["dot", f"-T{fmt}", *extra, str(source), "-o", str(target)], check=True)
        paths.append(target)
    return paths
