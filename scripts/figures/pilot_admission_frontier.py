#!/usr/bin/env python3
"""A minimum validator stake that falls with committed duration, drawn over six years of real commitments.

    uv run --group notebook --group model python scripts/figures/pilot_admission_frontier.py <output folder>

The admission rule is Hash's bounded harmonic frontier in avalanche_research.mechanisms:

    S_min(d) = S_floor + (S_short - S_floor) * eta(d) ** p,   eta(d) = (1/d - 1/365) / (1/2 - 1/365)

The setting drawn asks 2,000 AVAX at 14 days and 500 AVAX at a year. Its curvature is the smallest that keeps
stake times days at or above 28,000 AVAX-days, the capital of a 2,000 AVAX validator for 14 days, at every
duration. The script solves for it with the class.

The top panel is the density of validator commitments accepted before Granite (2025-11-19 16:00 UTC) in the pinned
run `staking-periods-2026-09-30`, by duration and stake, with the frontier and today's flat 2,000 AVAX rule on top.
The commitments shorter than 14 days begun since Helicon (run `helicon-commitments-2026-10-01`, first cycles) are
marked by whether they clear the frontier. The bottom panel is the capital behind the minimum seat, in AVAX-days.

Writes `admission-frontier.html`, `admission-frontier.csv` (the curves), `helicon-short-commitments.csv`, and
`numbers.json`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import holoviews as hv
import numpy as np
import pandas as pd

from avalanche_research import datasets
from avalanche_research.mechanisms import BoundedHarmonicFrontier
from avalanche_research.palette import QUANTITY_COLORS

PERIODS_RUN = "staking-periods-2026-09-30"
HELICON_RUN = "helicon-commitments-2026-10-01"
GRANITE = pd.Timestamp("2025-11-19 16:00:00")
HELICON = pd.Timestamp("2026-09-22 15:00:00")
PARITY_AVAX_DAYS = 2_000 * 14
FLOOR_AVAX, AT_14_DAYS_AVAX = 500.0, 2_000.0
DAY_TICKS = [2, 7, 14, 30, 90, 180, 365]
STAKE_TICKS = [500, 2_000, 10_000, 100_000, 1_000_000]
WIDTH, TOP_HEIGHT, BOTTOM_HEIGHT = 1040, 520, 300
INK, MUTED, DENSITY = "#333333", "#7a7f87", ["#eef0f3", "#c3c9d2", "#8a94a3", "#56606f"]
FRONTIER_COLOR, CLEARS_COLOR, SHORT_COLOR = QUANTITY_COLORS["stake"], QUANTITY_COLORS["stake"], QUANTITY_COLORS["rewards"]


def frontier() -> BoundedHarmonicFrontier:
    """The smallest curvature at 2,000 AVAX for 14 days that keeps 28,000 AVAX-days at every duration."""
    rule = BoundedHarmonicFrontier(label="Admission frontier", s_short_avax=10_000, s_floor_avax=FLOOR_AVAX, p=1.0)
    short_days = np.geomspace(rule.d_min_days, 14, 600)
    for p in np.arange(1.0, 4.0, 0.001):
        s_short = FLOOR_AVAX + (AT_14_DAYS_AVAX - FLOOR_AVAX) / rule.eta(14) ** p
        candidate = BoundedHarmonicFrontier(label=rule.label, s_short_avax=float(s_short), s_floor_avax=FLOOR_AVAX, p=float(round(p, 3)))
        if all(candidate.min_stake_avax(d) * d >= PARITY_AVAX_DAYS - 1e-6 for d in short_days):
            return candidate
    raise ValueError("no curvature below 4 keeps 28,000 AVAX-days at every duration")


def commitments() -> pd.DataFrame:
    periods = datasets.load("derived.staking-periods", run=PERIODS_RUN)
    rows = periods[(periods.role == "validator") & (periods.start_time < GRANITE)
                   & periods.duration_days.between(1, 366) & (periods.stake_avax > 0)]
    return rows[["duration_days", "stake_avax"]]


def helicon_short(rule: BoundedHarmonicFrontier) -> pd.DataFrame:
    cycles = datasets.load("derived.helicon-commitments", run=HELICON_RUN)
    first = cycles[(cycles.cycle_number == 1) & (cycles.duration_days < 14)].copy()
    first["frontier_min_avax"] = [rule.min_stake_avax(d) for d in first.duration_days]
    first["clears"] = first.stake_avax >= first.frontier_min_avax
    return first[["node_id", "cycle_start", "duration_days", "stake_avax", "frontier_min_avax", "clears", "auto_renewed"]]


def curves(rule: BoundedHarmonicFrontier) -> pd.DataFrame:
    days = np.geomspace(2, 365, 400)
    frame = pd.DataFrame({"duration_days": days})
    frame["frontier_min_avax"] = [rule.min_stake_avax(d) for d in days]
    frame["today_min_avax"] = 2_000.0
    frame["frontier_avax_days"] = frame.frontier_min_avax * frame.duration_days
    frame["today_avax_days"] = frame.today_min_avax * frame.duration_days
    return frame


def density(rows: pd.DataFrame) -> hv.QuadMesh:
    x_edges = np.geomspace(1, 366, 70)
    y_edges = np.geomspace(max(rows.stake_avax.min(), 100), rows.stake_avax.max() * 1.01, 60)
    counts, _, _ = np.histogram2d(rows.duration_days, rows.stake_avax, bins=[x_edges, y_edges])
    counts = np.where(counts > 0, np.log10(counts + 1), np.nan)
    return hv.QuadMesh((x_edges, y_edges, counts.T), ["Commitment duration (days)", "Stake (AVAX)"], "log10 commitments").opts(
        cmap=DENSITY, colorbar=False, tools=[], alpha=0.9, clipping_colors={"NaN": "white"})


def hook_axes(plot, element):
    from bokeh.models import FixedTicker, NumeralTickFormatter
    plot.state.xaxis.ticker = FixedTicker(ticks=DAY_TICKS)
    plot.state.xaxis.formatter = NumeralTickFormatter(format="0,0")
    plot.state.yaxis.formatter = NumeralTickFormatter(format="0,0")
    plot.state.title.text_font_size = "17px"
    plot.state.title.text_color = INK
    plot.state.outline_line_color = None


def chart(rule, rows, short, frame) -> hv.Layout:
    base = density(rows)
    today = hv.Curve(frame, "duration_days", "today_min_avax", label="Today: 2,000 AVAX at any duration").opts(
        color=MUTED, line_dash="dashed", line_width=2.5)
    curve = hv.Curve(frame, "duration_days", "frontier_min_avax", label="Frontier: 19,500 at 2 days, 2,000 at 14, 500 at a year").opts(
        color=FRONTIER_COLOR, line_width=4)
    clears = hv.Scatter(short[short.clears], "duration_days", "stake_avax", label="Since Helicon, under 14 days, clears the frontier").opts(
        color=CLEARS_COLOR, size=13, marker="circle", line_color="white", line_width=2)
    below = hv.Scatter(short[~short.clears], "duration_days", "stake_avax", label="Since Helicon, under 14 days, below the frontier").opts(
        color=SHORT_COLOR, size=13, marker="circle", line_color="white", line_width=2)
    top = (base * today * curve * below * clears).opts(
        width=WIDTH, height=TOP_HEIGHT, logx=True, logy=True, fontscale=1.2, toolbar=None, show_grid=False,
        xlim=(1.8, 380), ylim=(300, 30_000_000), yticks=STAKE_TICKS, legend_position="top_left", hooks=[hook_axes],
        title="A minimum stake that falls with duration binds only on seats shorter than two weeks",
        xlabel="", ylabel="Stake (AVAX)")
    parity = hv.HLine(PARITY_AVAX_DAYS).opts(color=INK, line_dash="dotted", line_width=2)
    parity_label = hv.Text(360, PARITY_AVAX_DAYS * 0.62, "28,000 AVAX-days: 2,000 AVAX for 14 days").opts(
        text_color=INK, text_font_size="12pt", text_align="right")
    today_days = hv.Curve(frame, "duration_days", "today_avax_days", label="Today").opts(color=MUTED, line_dash="dashed", line_width=2.5)
    frontier_days = hv.Curve(frame, "duration_days", "frontier_avax_days", label="Frontier").opts(color=FRONTIER_COLOR, line_width=4)
    bottom = (today_days * frontier_days * parity * parity_label).opts(
        width=WIDTH, height=BOTTOM_HEIGHT, logx=True, logy=True, fontscale=1.2, toolbar=None, show_grid=False,
        xlim=(1.8, 380), ylim=(2_000, 1_000_000), yticks=[4_000, 28_000, 100_000, 730_000], legend_position="top_left",
        hooks=[hook_axes], title="Capital behind the smallest seat, in AVAX-days", xlabel="Commitment duration (days)",
        ylabel="AVAX-days")
    return (top + bottom).cols(1).opts(shared_axes=True, toolbar=None)


def numbers(rule, rows, short, delegations) -> dict:
    return {
        "frontier": {"s_short_avax": round(rule.s_short_avax, 2), "s_floor_avax": rule.s_floor_avax, "p": rule.p,
                     "d_min_days": rule.d_min_days, "d_max_days": rule.d_max_days,
                     "min_stake_at_days": {str(d): round(rule.min_stake_avax(d)) for d in (2, 3, 7, 14, 30, 90, 180, 365)},
                     "min_avax_days": round(min(rule.min_stake_avax(d) * d for d in np.geomspace(2, 365, 2000))),
                     "check_failures": rule.check(None)},
        "avax_days_at_48h": {"today": 2_000 * 2, "frontier": round(rule.min_stake_avax(2) * 2)},
        "pre_granite_validator_commitments": {"run": PERIODS_RUN, "count": len(rows), "first_start": "2020-09", "cut": str(GRANITE)},
        "helicon_short_commitments": {"run": HELICON_RUN, "count": len(short), "clear": int(short.clears.sum()),
                                      "stake_avax": round(short.stake_avax.sum()),
                                      "stake_avax_clear": round(short.loc[short.clears, "stake_avax"].sum())},
        "delegations_since_helicon": delegations,
    }


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    hv.extension("bokeh")
    rule = frontier()
    rows = commitments()
    short = helicon_short(rule)
    frame = curves(rule)
    periods = datasets.load("derived.staking-periods", run=PERIODS_RUN)
    started = periods[(periods.role == "delegator") & (periods.start_time >= HELICON)]
    delegations = {"run": PERIODS_RUN, "count": len(started), "min_duration_days": round(float(started.duration_days.min()), 3)}
    frame.to_csv(out / "admission-frontier.csv", index=False)
    short.to_csv(out / "helicon-short-commitments.csv", index=False)
    hv.save(chart(rule, rows, short, frame), out / "admission-frontier.html")
    result = numbers(rule, rows, short, delegations)
    (out / "numbers.json").write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
