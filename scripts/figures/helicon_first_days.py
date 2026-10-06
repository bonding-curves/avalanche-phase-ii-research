#!/usr/bin/env python3
"""Validator commitments by duration, in the 30 days before Helicon and since its activation: the memo's chart.

    uv run --group notebook python scripts/figures/helicon_first_days.py <memo folder>

Reads two pinned runs through avalanche_research.datasets: `helicon-commitments-2026-10-02`, every validator cycle
started from Helicon's activation on 2026-09-22 15:00 UTC through the snapshot of 2026-10-02 00:15 UTC, and
`staking-periods-2026-09-30`, for the validator periods started in the 30 days before activation. A new commitment is a
transaction's first cycle, so an auto-renewal is not counted twice. Writes `helicon-first-days.csv`,
`helicon-first-days.html` and `helicon-first-days.png`, and prints the table.
"""

from __future__ import annotations

import sys
from pathlib import Path

import holoviews as hv
import pandas as pd

from avalanche_research import datasets

sys.path.insert(0, str(Path(__file__).resolve().parent))
from png import save_png

HELICON_RUN = "helicon-commitments-2026-10-06"
PERIODS_RUN = "staking-periods-2026-10-06"
ACTIVATION = pd.Timestamp("2026-09-22 15:00:00")
BINS = [("48h to 7d", 0, 7), ("7d to 14d", 7, 14), ("14d to 30d", 14, 30), ("30d to 90d", 30, 90), ("90d to 180d", 90, 180),
        ("180d to 365d", 180, 365.0001)]


def binned(frame: pd.DataFrame, window: str) -> pd.DataFrame:
    rows = []
    for name, low, high in BINS:
        part = frame[(frame.duration_days >= low) & (frame.duration_days < high)]
        rows.append({"window": window, "duration": name, "commitments": len(part), "stake_avax": part.stake_avax.sum(),
                     "avax_days": (part.stake_avax * part.duration_days).sum()})
    table = pd.DataFrame(rows)
    for column in ("commitments", "stake_avax", "avax_days"):
        table[f"{column}_share_pct"] = 100 * table[column] / table[column].sum()
    return table


def table() -> pd.DataFrame:
    cycles = datasets.load("derived.helicon-commitments", run=HELICON_RUN)
    after = cycles[cycles.cycle_number == 1]
    periods = datasets.load("derived.staking-periods", run=PERIODS_RUN)
    before = periods[(periods.role == "validator") & (periods.start_time >= ACTIVATION - pd.Timedelta(days=30)) & (periods.start_time < ACTIVATION)]
    return pd.concat([binned(before, "30 days before activation"), binned(after, "Since activation")], ignore_index=True)


def chart(frame: pd.DataFrame) -> hv.Bars:
    def hook(plot, element):
        # The legend names the two bars of each pair, so the axis shows only the duration.
        plot.state.xaxis.major_label_text_font_size = "0pt"
        plot.state.xaxis.group_text_font_size = "14px"
        plot.state.xaxis.group_text_color = "#333333"

    bars = hv.Bars(frame, ["duration", "window"], "commitments_share_pct").opts(
        width=1000, height=520, fontscale=1.2, toolbar=None, show_grid=True, ylim=(0, 85), cmap=["#9aa5b1", "#1f5fa8"], hooks=[hook],
        color="window", show_legend=True, legend_position="top_right", multi_level=True,
        title="New validator commitments by duration: 30 days before Helicon and since its activation",
        xlabel="Commitment duration. Data as of 2026-10-02 00:15 UTC",
        ylabel="Share of new validator commitments (%)")
    return bars


def main() -> None:
    out = Path(sys.argv[1])
    hv.extension("bokeh")
    frame = table()
    frame.to_csv(out / "helicon-first-days.csv", index=False)
    hv.save(chart(frame), out / "helicon-first-days.html")
    save_png(out / "helicon-first-days.html", out / "helicon-first-days.png", 1040, 580)
    print(frame.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
