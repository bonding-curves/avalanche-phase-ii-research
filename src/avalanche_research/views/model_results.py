"""Model v0.7 results as HoloViews figures: mechanism curves and issuance, the response sweep, the scorecard,
and the version roadmap.

Each figure has a compute function, which returns a table, and a plot function, which draws that table.
A notebook cell calls both. A memo image is a saved state of the same plot, so the two cannot drift apart.
Titles name what is plotted and its unit. The finding belongs in the text around the figure.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import holoviews as hv
import numpy as np
import pandas as pd

from avalanche_research.mechanisms import (
    ACP285Ramp,
    ChainReward,
    QuadraticReward,
    RewardMechanism,
    TenureBoost,
)
from avalanche_research.model.engine import run, sweep
from avalanche_research.model.lifecycle import (
    ValidatorLifecycle,
    actual_path,
    origin_inputs,
    score,
)
from avalanche_research.model.replay import daily_events
from avalanche_research.model.versions import EVENTS, VERSIONS, Version
from avalanche_research.palette import MECHANISM_COLORS, QUANTITY_COLORS
from avalanche_research.views.mechanism_explorer import issuance_table

INK = "#1b1b1b"
MUTED = "#7a7f87"
MEMO = {"fontscale": 1.15, "toolbar": None, "show_grid": True}
ORIGINS = {"Banff": date(2022, 10, 18), "Cortina": date(2023, 4, 25), "Durango": date(2024, 3, 6),
           "Etna": date(2024, 12, 16), "Fortuna": date(2025, 4, 8)}
RESPONSES = (0.0, 0.1, 0.3)


# Mechanisms ------------------------------------------------------------------------------------------------

def reference_mechanisms(cohort: pd.DataFrame, supply_navax: int, priced_at: datetime) -> list[RewardMechanism]:
    """The five reward designs of v0.7, labelled as in ``MECHANISM_COLORS``."""
    quadratic = QuadraticReward()
    held = quadratic.at_equal_issuance(cohort.assign(start=priced_at), supply_navax)
    held.label = "Quadratic curve, today's issuance"
    return [ChainReward(), ACP285Ramp(target_min_rate=0.05), TenureBoost(), quadratic, held]


def mechanism_table(mechanisms: list[RewardMechanism], supply_navax: int, priced_at: datetime,
                    completed_periods: int = 8) -> pd.DataFrame:
    """Annual reward rate by committed duration, 2 to 52 weeks, for each mechanism."""
    days = [14 if d == 14 else d for d in range(14, 365, 7)] + [365]
    frames = []
    for mechanism in mechanisms:
        curve = mechanism.curve(supply_navax, priced_at, days, completed_periods=completed_periods)
        frames.append(curve.assign(mechanism=mechanism.label, weeks=curve.duration_days / 7, annual_rate_pct=curve.annual_rate * 100))
    return pd.concat(frames, ignore_index=True)[["mechanism", "duration_days", "weeks", "annual_rate_pct"]]


def mechanism_plot(curves: pd.DataFrame, issuance: pd.DataFrame) -> hv.Layout:
    """Left: annual reward rate by committed duration. Right: AVAX each design mints for the reference cohort."""
    lines = []
    for label in curves.mechanism.unique():
        part = curves[curves.mechanism == label]
        chain = label == "Chain today"
        lines.append(hv.Curve(part, "weeks", ["annual_rate_pct", "mechanism"], label=label).opts(
            color=MECHANISM_COLORS.get(label, MUTED), line_width=4 if chain else 3, line_dash="solid" if chain else "dashed",
            tools=["hover"]))
    left = hv.Overlay(lines).opts(
        width=560, height=460, title="Annual reward rate by committed duration (%)", xlabel="Committed duration (weeks)",
        ylabel="Annual reward rate (%)", legend_position="bottom_right", xlim=(2, 52), **MEMO)
    bars = issuance.assign(issuance_million_avax=issuance.issuance_avax / 1e6,
                           change=["today" if m == "Chain today" else ("same" if abs(v) < 5e-4 else f"{v * 100:+.1f}%") for m, v in zip(issuance.mechanism, issuance.change_vs_chain)])
    order = list(curves.mechanism.unique())[::-1]
    bars["mechanism"] = pd.Categorical(bars.mechanism, categories=order, ordered=True)
    bars = bars.sort_values("mechanism")
    right = hv.Bars(bars, "mechanism", ["issuance_million_avax", "change"]).opts(
        invert_axes=True, width=470, height=460, color="mechanism",
        cmap={k: v for k, v in MECHANISM_COLORS.items()}, show_legend=False, line_color=None,
        title="AVAX minted (million)", xlabel="", ylabel="Million AVAX", tools=["hover"], **MEMO)
    labels = hv.Labels(bars.assign(x=bars.mechanism.astype(str), y=bars.issuance_million_avax * 0.5), ["x", "y"], "change").opts(
        invert_axes=True, text_color="white", text_font_size="11pt", text_font_style="bold")
    return (left + right * labels).opts(toolbar=None)


# The response sweep -------------------------------------------------------------------------------------------

def response_sweep(periods_path: str, origin: date = ORIGINS["Fortuna"], timesteps: int = 180, runs: int = 20,
                   responses: tuple[float, ...] = RESPONSES) -> pd.DataFrame:
    """Validators after ``timesteps`` days and AVAX issued, by mechanism and response strength, from ``origin``."""
    inputs = origin_inputs(periods_path, origin)
    start = datetime.combine(origin + timedelta(days=1), datetime.min.time(), tzinfo=UTC).replace(hour=12)
    stakes = pd.DataFrame({"stake_navax": inputs["initial_stakes"], "start": start, "completed_periods": inputs["initial_periods_done"],
                           "duration_seconds": np.clip(inputs["initial_days_left"], 1, 365) * 86_400})
    held = QuadraticReward().at_equal_issuance(stakes, inputs["supply0_navax"])
    held.label = "Quadratic curve, today's issuance"
    mechanisms = [ChainReward(label="Chain today"),
                  ACP285Ramp(activation=datetime.combine(origin, datetime.min.time(), tzinfo=UTC).replace(hour=16), label="ACP-285 settings"),
                  TenureBoost(label="Tenure boost"), QuadraticReward(label="Quadratic curve"), held]
    model = ValidatorLifecycle(origin=origin, timesteps=timesteps, runs=runs, **inputs)
    rows = []
    for response in responses:
        table = sweep(model, {"mechanism": mechanisms, "renewal_response": [response], "entry_response": [response]})
        last = table[(table.timestep == timesteps) & (table.variable == "active_validators")]
        issued = table[table.variable == "issued_navax"].groupby(["mechanism", "run"]).value.sum() / 1e15
        for mechanism, group in last.groupby("mechanism"):
            rows.append({"response": response, "mechanism": mechanism, "validators_mean": group.value.mean(),
                         "validators_p10": group.value.quantile(0.1), "validators_p90": group.value.quantile(0.9),
                         "issuance_million_avax": issued.loc[mechanism].mean()})
    return pd.DataFrame(rows)


def sweep_plot(frame: pd.DataFrame) -> hv.Layout:
    """Validators after 180 days against AVAX issued, one panel per response strength, 10 to 90 percent bars."""
    panels = []
    responses = sorted(frame.response.unique())
    for response in responses:
        part = frame[frame.response == response]
        layers = []
        for label in [m for m in MECHANISM_COLORS if m in set(part.mechanism)]:
            row = part[part.mechanism == label]
            color = MECHANISM_COLORS[label]
            layers.append(hv.ErrorBars((row.issuance_million_avax, row.validators_mean, row.validators_mean - row.validators_p10,
                                        row.validators_p90 - row.validators_mean), vdims=["y", "yerrneg", "yerrpos"]).opts(color=color, line_width=2))
            layers.append(hv.Scatter(row, "issuance_million_avax", ["validators_mean", "mechanism"], label=label).opts(
                color=color, size=13, line_color="white", tools=["hover"]))
        title = f"Response to reward: {response:g}"
        panels.append(hv.Overlay(layers).opts(
            width=360, height=460, title=title, show_legend=bool(response == responses[0]), legend_position="bottom_left",
            xlabel="AVAX issued in 180 days (million)", ylabel="Active validators after 180 days", **MEMO))
    return hv.Layout(panels).cols(len(panels)).opts(shared_axes=True, toolbar=None)


# The scorecard ----------------------------------------------------------------------------------------------

def lifecycle_scores(periods_path: str, origins: dict[str, date] = ORIGINS, runs: int = 20) -> pd.DataFrame:
    """The lifecycle model scored at 30 and 90 days after each origin against holding the origin value."""
    actual = actual_path(daily_events(periods_path))
    frames = []
    for name, origin in origins.items():
        table = run(ValidatorLifecycle(origin=origin, runs=runs, **origin_inputs(periods_path, origin)))
        frames.append(score(table, actual, origin).assign(origin=name, origin_date=origin))
    return pd.concat(frames, ignore_index=True)


def score_plot(scores: pd.DataFrame) -> hv.Layout:
    """Absolute error as a percent of the actual value: the model's mean of 20 runs against holding the origin value."""
    panels = []
    for variable, title, color in (("active_validators", "Active validators", QUANTITY_COLORS["nodes"]),
                                   ("active_validator_stake_navax", "Validator stake", QUANTITY_COLORS["stake"])):
        part = scores[scores.variable == variable].sort_values(["origin_date", "horizon_days"]).copy()
        part["row"] = part.origin + ", " + part.horizon_days.astype(str) + " days"
        part["model_pct"] = 100 * part.model_abs_error / part.actual
        part["hold_pct"] = 100 * part.persistence_abs_error / part.actual
        part["covered"] = (part.model_p10 <= part.actual) & (part.actual <= part.model_p90)
        rows = list(part.row)[::-1]
        y = {r: i for i, r in enumerate(rows)}
        part["y"] = part.row.map(y)
        segments = hv.Segments((part.hold_pct, part.y, part.model_pct, part.y)).opts(color="#c9ccd1", line_width=3)
        hold = hv.Scatter(part, "hold_pct", ["y", "row"], label="Holding the origin value").opts(
            color="white", line_color=MUTED, line_width=2, size=13)
        model = hv.Scatter(part, "model_pct", ["y", "row"], label="Model, mean of 20 runs").opts(
            color=color, line_color="white", size=14, tools=["hover"])
        xmax = float(max(part.model_pct.max(), part.hold_pct.max())) * 1.15 + 0.5
        marked = part.assign(x=xmax)
        covers = hv.Scatter(marked[marked.covered], "x", ["y"], label="Band covers actual").opts(
            marker="square", size=10, color=INK, line_color=INK)
        spans = hv.Scatter(marked[~marked.covered], "x", ["y"], label="Band misses actual").opts(
            marker="square", size=10, color="white", line_color=INK)
        panels.append((segments * hold * model * covers * spans).opts(
            width=540, height=520, title=f"{title}: absolute error, % of actual", xlabel="Absolute error (% of the actual value)",
            ylabel="", yticks=[(v, k) for k, v in y.items()], xlim=(0, xmax * 1.08), legend_position="bottom",
            legend_cols=2, show_legend=True, **MEMO))
    return hv.Layout(panels).cols(2).opts(toolbar=None)


# The roadmap ------------------------------------------------------------------------------------------------

def roadmap_plot(versions: tuple[Version, ...] = VERSIONS, events=EVENTS, today: date | None = None) -> hv.Overlay:
    """Each model version on the date of the call that shows it, with the events that frame the plan."""
    rows = list(versions)
    previous = [date(2026, 8, 1)] + [v.call for v in rows[:-1]]
    frame = pd.DataFrame({
        "version": [v.name for v in rows], "call": pd.to_datetime([v.call for v in rows]),
        "start": pd.to_datetime(previous), "capability": [v.capability for v in rows],
        "released": [v.released for v in rows], "y": list(range(len(rows)))[::-1],
    })
    bars = hv.Segments((frame.start, frame.y, frame.call, frame.y)).opts(color="#d7dade", line_width=10)
    done = hv.Scatter(frame[frame.released], "call", ["y", "version", "capability"]).opts(
        marker="diamond", size=20, color=INK, tools=["hover"])
    planned = hv.Scatter(frame[~frame.released], "call", ["y", "version", "capability"]).opts(
        marker="diamond", size=20, color="white", line_color=INK, line_width=2, tools=["hover"])
    names = hv.Labels(frame.assign(x=frame.call + pd.Timedelta(days=3), text=frame.version + "  " + frame.capability),
                      ["x", "y"], "text").opts(text_align="left", text_font_size="10.5pt", text_color=INK)
    marks = []
    for i, (when, name) in enumerate(events):
        marks.append(hv.VLine(pd.Timestamp(when)).opts(color=MUTED, line_dash="dotted", line_width=1.5))
        marks.append(hv.Text(pd.Timestamp(when) + pd.Timedelta(days=2), len(rows) - 0.3 - 0.32 * (i % 2), name).opts(
            text_font_size="9.5pt", text_color=MUTED, text_align="left"))
    if today is not None:
        marks.append(hv.VLine(pd.Timestamp(today)).opts(color=QUANTITY_COLORS["rewards"], line_width=1.5))
    return hv.Overlay([bars, *marks, done, planned, names]).opts(
        width=1060, height=440, title="Model versions by the call at which each is shown", xlabel="", ylabel="",
        yaxis=None, xlim=(pd.Timestamp("2026-08-01"), pd.Timestamp("2027-03-20")), ylim=(-0.7, len(rows) + 0.05),
        show_grid=False, toolbar=None, fontscale=1.15)


def reference_issuance(mechanisms: list[RewardMechanism], cohort: pd.DataFrame, supply_navax: int, priced_at: datetime) -> pd.DataFrame:
    """AVAX each mechanism mints for the reference cohort, as ``issuance_table``."""
    return issuance_table(mechanisms, cohort, supply_navax, priced_at)
