"""The structure of a cadCAD model, traced from its code and drawn with Graphviz.

``trace`` runs each policy and each state update of a model once on its own initial state, with the state
and the policy signal wrapped in dictionaries that record every key read. The result says exactly which
state each policy reads, which signal keys it returns, and which state and signal keys each update reads
and which variable it writes. ``lifecycle_dot`` draws that trace for ``ValidatorLifecycle``, adding the
behaviour blocks and the reward mechanism the policy calls, the inputs measured before the origin, and the
invariants checked each day. Nothing in the drawing is typed by hand except the labels of the input groups.

``trace_stages`` and ``fitted_lifecycle_dot`` do the same for the released v0.8.0 model, whose daily policy runs an
ordered list of stages: each stage is called once inside that policy with every read recorded, and the drawing takes
the stage order, what each stage reads, and which stage each state update comes from from that record. Only the plain
words of the labels are typed, and a stage, block, setting or state variable without them stops the drawing.
"""

from __future__ import annotations

import inspect
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from avalanche_research.model.blocks import Renewal
from avalanche_research.model.engine import SimulationModel
from avalanche_research.model.lifecycle import Entry, ValidatorLifecycle
from avalanche_research.model.parts.stages import Day
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
    """Write ``.dot``, ``.svg`` and ``.png`` beside ``out_stem`` with the system ``dot`` command. Each suffix is
    appended to the stem's whole name, so a stem with a dot in it, such as ``v0.8-structure``, keeps it."""
    if shutil.which("dot") is None:
        raise RuntimeError("Graphviz `dot` is not installed")
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    source = out_stem.parent / f"{out_stem.name}.dot"
    source.write_text(dot_source)
    paths = [source]
    for fmt, extra in (("svg", []), ("png", ["-Gdpi=170"])):
        target = out_stem.parent / f"{out_stem.name}.{fmt}"
        subprocess.run(["dot", f"-T{fmt}", *extra, str(source), "-o", str(target)], check=True)
        paths.append(target)
    return paths


# The released v0.8.0 model: StakeLifecycle on FittedLifecycle, its daily step an ordered list of stages.


class _AttributeRecorder:
    """A read-only view of ``target`` that records each attribute read, in order."""

    def __init__(self, target: Any):
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "read", [])

    def __getattr__(self, name: str):
        value = getattr(object.__getattribute__(self, "_target"), name)
        read = object.__getattribute__(self, "read")
        if name not in read:
            read.append(name)
        return value


@dataclass
class StageTrace:
    """What one stage of the daily step read and returned, from one recorded call."""

    name: str
    function: str
    reads_state: list[str]
    reads_earlier: list[str]
    reads_day: list[str]
    reads_blocks: list[str]
    reads_settings: list[str]
    reads_model: list[str]
    returns: list[str]
    values: dict[str, Any] = field(default_factory=dict, repr=False)


def trace_stages(model: Any) -> list[StageTrace]:
    """Each stage of ``model.stages``, in run order, called once inside the model's own daily policy with the state,
    the day, its blocks and settings, the earlier stages' outputs, and the model itself (for a stage that is one of its
    methods) wrapped so every read is recorded. A block, setting or model attribute read as None is left out."""
    traces: list[StageTrace] = []
    model_stages = model.stages
    had_own = "stages" in vars(model)

    def recorded(name, stage):
        def run(state, day, earlier):
            state_rec, earlier_rec = _Recorder(state), _Recorder(earlier)
            blocks, settings = _AttributeRecorder(day.blocks), _AttributeRecorder(day.settings)
            day_rec = _AttributeRecorder(Day(t=day.t, start=day.start, draw=day.draw, blocks=blocks, renewal_gap=day.renewal_gap,
                                             entry_gap=day.entry_gap, settings=settings))
            bound = inspect.ismethod(stage) and stage.__self__ is model
            model_rec = _AttributeRecorder(model)
            out = stage.__func__(model_rec, state_rec, day_rec, earlier_rec) if bound else stage(state_rec, day_rec, earlier_rec)
            traces.append(StageTrace(
                name=name, function=getattr(stage, "__name__", name),
                reads_state=[k for k in state_rec.read if k not in META_KEYS],
                reads_earlier=list(earlier_rec.read),
                reads_day=[k for k in day_rec.read if k not in ("blocks", "settings")],
                reads_blocks=[k for k in blocks.read if getattr(day.blocks, k) is not None],
                reads_settings=[k for k in settings.read if getattr(day.settings, k) is not None],
                reads_model=[k for k in model_rec.read if getattr(model, k) is not None] if bound else [],
                returns=list(out), values=dict(out),
            ))
            return out
        return run

    model.stages = tuple((name, recorded(name, stage)) for name, stage in model_stages)
    try:
        state = {**model.initial_state(), "run": 1, "timestep": 0, "substep": 1, "simulation": 0}
        model.blocks()[0]["policies"]["lifecycle"]({}, 1, [], state)
    finally:
        if had_own:
            model.stages = model_stages
        else:
            del model.stages
    return traces


def tiny_stake_lifecycle() -> Any:
    """The released variant's model class on a small synthetic state, with its stake hurdle and logit return hazard,
    enough to trace its structure. Every stage has something to act on: commitments that end on the first day, a node
    out of the set, arrivals and a scheduled commitment."""
    import hashlib

    import pandas as pd

    from avalanche_research.model.fitted_blocks import Arrivals, RenewalLogit
    from avalanche_research.model.parts.return_hazard import ReturnLogitHazard
    from avalanche_research.model.stake_lifecycle import fitted_stake_settings
    from avalanche_research.model.variants import VARIANTS

    nav, origin = 10**9, date(2024, 3, 6)
    tables = {}
    for context in ("renewal", "return", "entry"):
        table = pd.DataFrame({
            "previous_stake_navax": np.full(60, 0 if context == "entry" else 2_000 * nav, dtype=np.int64),
            "next_days": np.full(60, 30, dtype=np.int64),
            "next_stake_navax": np.repeat(np.array([2_000, 4_000], dtype=np.int64) * nav, 30),
            "decided_us": np.full(60, 1_709_164_800_000_000, dtype=np.int64),
        })
        sha = hashlib.sha256(table.to_csv(index=False).encode()).hexdigest()
        table.attrs = {"context": context, "run": "synthetic", "origin": origin.isoformat(), "window": "365 days",
                       "sha256": sha, "source": f"synthetic; origin {origin}; 365 days; sha256 {sha}"}
        tables[context] = table
    initial = pd.DataFrame({"stakes": np.full(4, 2_000 * nav), "days_left": np.array([1, 1, 5, 9]),
                            "done": np.array([0, 2, 1, 0]), "after_return": np.zeros(4, bool), "days": np.full(4, 30),
                            "handed_on": np.zeros(4, bool), "returns": np.zeros(4, dtype=np.int64)})
    out = pd.DataFrame({"out_stakes": [2_000 * nav], "out_days": [8], "out_done": [1], "out_last_days": [30], "out_returns": [0]})
    scheduled = pd.DataFrame({"start_day": [1], "stakes": [5_000 * nav], "days": [60], "done": [3], "after_return": [False], "returns": [1]})
    moves = pd.DataFrame({"previous_days": [30], "next_days": [30], "previous_stake_navax": [2_000 * nav], "next_stake_navax": [2_000 * nav]})
    first = pd.DataFrame({"days": [30], "stake_navax": [2_000 * nav]})
    model_class = VARIANTS[RELEASED].model
    return model_class(
        origin=origin, inputs_source="synthetic", initial=initial, out_of_set=out, scheduled=scheduled, moves=moves,
        first_commitments=first, renewal=RenewalLogit(intercept=0.0), returns=ReturnLogitHazard(intercept=-1.0),
        arrivals=Arrivals(mean_per_day=2), move_stake_bands="three", move_stake_weighted=False, timesteps=2, runs=1,
        **fitted_stake_settings(tables, origin, "synthetic"),
    )


RELEASED = "v0.8.0"

# Plain words for each stage of the daily step, by stage name. A stage the model adds without words here stops the
# drawing, so the diagram cannot silently fall behind the code.
STAGE_WORDS = {
    "renewal": "each commitment ending today renews on the same node or leaves the set",
    "returns": "each node out of the set for up to 365 days may come back",
    "arrivals": "how many nodes make their first-ever commitment today",
    "continuation": "each renewed, returned or new commitment draws its duration, then its stake",
    "rewards": "the reward mechanism prices each commitment started today at today's supply",
    "assembly": "open commitments that go on, then today's new ones, then the scheduled ones due today",
}

# The state a stage reads and the daily update writes, grouped as the drawing shows it.
STATE_GROUPS = {
    "open": ("Open commitments", "stake, days left, duration, tenure and record of each",
             ("stakes", "days_left", "done", "after_return", "days", "handed_on", "returns", "node_key")),
    "out": ("Nodes out of the set", "up to 365 days; stake, days out, tenure and record of each",
            ("out_stakes", "out_days", "out_done", "out_last_days", "out_returns", "out_node_key")),
    "supply": ("Reward counter", "supply_navax, which the reward formula reads", ("supply_navax",)),
}

# What each block, setting or model attribute a stage reads is drawn as: (node, title, plain words). A read with no
# entry here stops the drawing.
BLOCK_NODES = {
    "blocks.renewal": "renewal", "blocks.renewal_shift": "renewal", "blocks.renewal_large": "renewal_large",
    "blocks.returns": "returns", "blocks.arrivals": "arrivals",
    "blocks.continuation": "durations", "blocks.first_days": "durations", "blocks.durations": "duration_transition",
    "blocks.first_stakes": "first_stakes", "model.stake_choice": "stake",
    "settings.mechanism": "mechanism", "settings.renewal_response": "responses", "settings.entry_response": "responses",
    "settings.large_navax": "renewal_large", "settings.scheduled": "scheduled",
    # The participation feedback: its elasticity is a setting a run compares, and the origin's unstaked share is read
    # from the initial state before the step, as the gaps are.
    "settings.participation_elasticity": "responses", "settings.unstaked_share0": None,
    # The market condition's shifts in renewal log-odds and in log arrivals, settings a run compares as the responses are.
    "settings.market_renewal_shift": "responses", "settings.market_entry_shift": "responses",
    # The day's yield gaps come from the mechanism and outside_yield_pp before the step; the responses decide what
    # they do, so the drawing joins the responses to the stages that read them and not to the gaps.
    "day.renewal_gap": None, "day.entry_gap": None, "day.t": None, "day.start": None, "day.draw": None,
}
SWEPT = ("renewal_response", "entry_response", "outside_yield_pp", "participation_elasticity", "market_renewal_shift",
         "market_entry_shift")


def _wrapped(items: list[str], per_line: int) -> str:
    return "<BR/>".join(", ".join(items[i:i + per_line]) for i in range(0, len(items), per_line))


def _stage_table(stages: list[StageTrace]) -> str:
    """The daily step as one HTML-like table, a row per stage in run order, each row a port named by its stage."""
    rows = ['<TR><TD BORDER="0"><B>Each day, in this order</B></TD></TR>']
    for i, stage in enumerate(stages, 1):
        words = STAGE_WORDS[stage.name].split(" ")
        half = (len(words) + 1) // 2
        text = " ".join(words[:half]) + "<BR/>" + " ".join(words[half:])
        rows.append(f'<TR><TD PORT="{stage.name}" STYLE="rounded" BGCOLOR="#f4f5f7" COLOR="{INK}" CELLPADDING="7">'
                    f'<B>{i}. {stage.name}</B>{_small(text)}</TD></TR>')
    return '<<TABLE BORDER="0" CELLBORDER="2" CELLSPACING="7">' + "".join(rows) + "</TABLE>>"


def fitted_lifecycle_dot(model: Any | None = None) -> str:
    """Graphviz source for the released v0.8.0 model's structure. The stage order, what each stage reads (state, blocks,
    settings), which stage's output each state variable is updated from, the daily outputs, the KPIs and the other
    reward mechanisms are read from the code; only the labels' plain words are typed here."""
    from avalanche_research import mechanisms
    from avalanche_research.model.kpis import KPIS

    model = model or tiny_stake_lifecycle()
    stages = trace_stages(model)
    order = [s.name for s in stages]
    missing = [name for name in order if name not in STAGE_WORDS]
    if missing:
        raise KeyError(f"stages without plain words in STAGE_WORDS: {missing}")
    updates = trace(model).updates
    # The day's signal is the last stage's output. A key is drawn from the first stage that returned the very object
    # the signal holds, so a value passed through unchanged is drawn from the stage that made it.
    signal = stages[-1].values
    produced_by = {key: next(s.name for s in stages if key in s.values and s.values[key] is value) for key, value in signal.items()}
    grouped = {key: group for group, (_t, _w, keys) in STATE_GROUPS.items() for key in keys}

    # Which drawn block, setting or fixed table each stage reads.
    reads: dict[str, list[str]] = {}
    for stage in stages:
        for kind, keys in (("blocks", stage.reads_blocks), ("settings", stage.reads_settings), ("day", stage.reads_day), ("model", stage.reads_model)):
            for key in keys:
                name = f"{kind}.{key}"
                if name not in BLOCK_NODES:
                    raise KeyError(f"stage {stage.name} reads {name}, which BLOCK_NODES does not place")
                node = BLOCK_NODES[name]
                if node is not None and stage.name not in reads.setdefault(node, []):
                    reads[node].append(stage.name)
    daily = [*model.state_variables(), *model.float_variables()]
    # Every state variable, read by a stage or only by a state update, is a drawn group or a column of the daily table.
    ungrouped = sorted(({k for s in stages for k in s.reads_state} | set(model.initial_state()) | set(updates))
                       - set(grouped) - set(daily))
    if ungrouped:
        raise KeyError(f"state that STATE_GROUPS does not place and the daily table does not name: {ungrouped}")
    # Which state group each stage reads, and which stage's output updates each group.
    state_reads = {(grouped[k], s.name) for s in stages for k in s.reads_state if k in grouped}
    state_writes = {(grouped[v], produced_by[k]) for v, u in updates.items() if v in grouped for k in u["reads_signal"]}

    blue, orange, green, red = (QUANTITY_COLORS[k] for k in ("nodes", "duration", "stake", "rewards"))
    font = f'fontname="{FONT}"'
    lines = [
        "digraph fitted_lifecycle {",
        f'  graph [rankdir=LR, bgcolor="{PAPER}", nodesep=0.3, ranksep=0.7, pad=0.3, {font}, fontsize=14, newrank=true, compound=true];',
        f'  edge [{font}, fontsize=11, fontcolor="{MUTED}"];',
        f'  subgraph cluster_inputs {{ label=<<B>Measured before the origin</B>>; {font}; color="{MUTED}"; style="rounded,dashed";',
        _node("in:events", "Staking events before the origin"
              + _small("renewal endings, return spells,<BR/>first-ever commitments, moves<BR/>and stake choices of the year<BR/>derived.staking-periods"), MUTED, dashed=True),
        "  }",
    ]

    renewal, returns, arrivals = model.renewal, model.returns, model.arrivals
    drawn = "redrawn each run"
    fitted_nodes = {
        "renewal": (f"Renewal: {renewal.decision}", f"{type(renewal).__name__} on tenure, after a return,<BR/>duration and stake; {drawn},<BR/>with a renewal shift", blue),
        "renewal_large": ("Large-holder renewal", f"{type(model.renewal_large).__name__} above the line; {drawn}", blue),
        "returns": (f"Return: {returns.decision}", f"{type(returns).__name__} on days out, stake band,<BR/>returned before, first commitment;<BR/>{drawn}", blue),
        "arrivals": (f"Arrivals: first-ever nodes {arrivals.decision}", f"{type(arrivals).__name__}, a negative binomial count;<BR/>{drawn}", blue),
        "durations": ("Next duration", "renewing or returning: the year's moves<BR/>with a like previous duration; new: the<BR/>year's first commitments; resampled each run", orange),
        "duration_transition": ("Duration band transition", f"DurationTransition; {drawn}", orange),
        "first_stakes": ("First stakes", "the year's first commitments", orange),
    }
    if "stake" in reads:
        hurdle = model.stake_choice
        point = "one point estimate, not redrawn" if model.stake_point_estimate else "one point estimate"
        fitted_nodes["stake"] = (f"Stake hurdle: {hurdle.decision}",
                                 f"{type(hurdle).__name__}: keep the stake or change it,<BR/>by renewal, return or entry, stake<BR/>and duration; {point}", green)
    lines.append(f'  subgraph cluster_fitted {{ label=<<B>Fitted on those events</B>>; {font}; color="{blue}"; style=rounded;')
    placed = [node for node in reads if node in fitted_nodes]
    for node in placed:
        title, words, color = fitted_nodes[node]
        lines.append(_node(f"block:{node}", title + _small(words), color))
    lines.append("  }")

    designs = [getattr(mechanisms, name) for name in mechanisms.__all__]
    others = [m().label for m in designs if isinstance(m, type) and issubclass(m, mechanisms.RewardMechanism)
              and m is not mechanisms.RewardMechanism and m().label != model.mechanism.label]
    lines.append(f'  subgraph cluster_settings {{ label=<<B>Settings a run compares</B>>; {font}; color="{red}"; style="rounded,dashed";')
    if "mechanism" in reads:
        lines.append(_node("block:mechanism", f"Reward mechanism: {model.mechanism.label}"
                           + _small("the design input, or<BR/>" + _wrapped(others, 2)), red))
    if "responses" in reads:
        values = [f"{name} {getattr(model, name)}".replace(" None", " none") for name in SWEPT]
        lines.append(_node("block:responses", "Yield-gap responses" + _small("swept, not fitted<BR/>" + _wrapped(values, 1)), red, dashed=True))
    lines.append("  }")

    lines.append(f'  "step" [shape=plain, label={_stage_table(stages)}, {font}, fontsize=13, fontcolor="{INK}"];')

    lines.append(f'  subgraph cluster_state {{ label=<<B>State</B><BR/><FONT POINT-SIZE="10" COLOR="{MUTED}">from the chain at the origin, carried day to day</FONT>>; labelloc=b; {font}; color="{green}"; style=rounded;')
    for group, (title, words, _keys) in STATE_GROUPS.items():
        lines.append(_node(f"state:{group}", title + _small(words), green, shape="cylinder", style="solid"))
    if "scheduled" in reads:
        lines.append(_node("state:scheduled", "Scheduled commitments"
                           + _small("accepted by the origin, start later;<BR/>fixed, add no issuance in the run"), green, shape="cylinder", style="solid", dashed=True))
    lines.append("  }")

    kpis = [kpi.label for kpi in KPIS.values() if kpi.horizon != "chain only"]
    lines.append(f'  subgraph cluster_out {{ label=<<B>Outputs</B>>; {font}; color="{MUTED}"; style=rounded;')
    lines.append(_node("out:daily", "Daily table, a row per run and day" + _small(_wrapped(daily, 2)), INK))
    lines.append(_node("out:kpis", "KPIs at 180 and 365 days" + _small(_wrapped(kpis, 2)), INK))
    lines.append("  }")
    lines.append(_node("in:ledger", "Monetary ledger to the origin" + _small("measured before the origin: realized<BR/>supply, mean daily burn of the year<BR/>derived.avax-monetary-daily"), MUTED, dashed=True))
    lines.append('  { rank=same; "out:daily"; "out:kpis"; }')

    lines.append(f'  "in:events" -> "block:{placed[len(placed) // 2]}" [lhead=cluster_fitted, color="{MUTED}", style=dashed, penwidth=1.6, arrowsize=0.7, label=" fit "];')
    for node, readers in reads.items():
        for reader in readers:
            if node == "scheduled":
                lines.append(f'  "step":"{reader}":e -> "state:scheduled" [color="{green}", penwidth=1.4, arrowsize=0.7, style=dashed, dir=back];')
            else:
                color = red if node in ("mechanism", "responses") else blue
                style = "dashed" if node == "responses" else "solid"
                lines.append(f'  "block:{node}" -> "step":"{reader}":w [color="{color}", penwidth=1.6, arrowsize=0.7, style={style}];')
    for group, stage in sorted(state_reads | state_writes, key=lambda gs: (order.index(gs[1]), gs[0])):
        both = (group, stage) in state_reads and (group, stage) in state_writes
        if (group, stage) in state_writes:
            direction = "both" if both else "forward"
            lines.append(f'  "step":"{stage}":e -> "state:{group}" [color="{green}", penwidth=1.8, arrowsize=0.7, dir={direction}];')
        else:
            lines.append(f'  "step":"{stage}":e -> "state:{group}" [color="{green}", penwidth=1.4, arrowsize=0.7, style=dashed, dir=back];')
    sources = sorted({produced_by[k] for v in daily for k in updates[v]["reads_signal"]}, key=order.index)
    for name in sources:
        lines.append(f'  "step":"{name}":e -> "out:daily" [color="{INK}", penwidth=1.6, arrowsize=0.7];')
    # A flat edge in this layout runs upward, so the arrow is drawn backward to keep the daily table above the KPIs.
    lines.append(f'  "out:kpis" -> "out:daily" [color="{INK}", penwidth=1.6, arrowsize=0.7, dir=back];')
    lines.append(_edge("in:ledger", "out:kpis", color=MUTED, dashed=True))
    lines.append("}")
    return "\n".join(lines) + "\n"
