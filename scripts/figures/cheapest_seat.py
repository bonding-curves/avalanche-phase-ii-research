#!/usr/bin/env python3
"""AVAX-days locked by the cheapest allowed validator seat, before Helicon, after it, and under the frontier.

    uv run --group notebook --group model python scripts/figures/cheapest_seat.py <output folder>

The cheapest seat is the smallest stake at the shortest allowed duration. Before Helicon it was 2,000 AVAX for 14
days. Helicon's ACP-273 allows 2,000 AVAX for 2 days. Under Hash's bounded harmonic frontier, at the setting that
keeps at least 28,000 AVAX-days at every duration (500 AVAX at a year, 2,000 at 14 days, curvature 1.282), the
minimum stake at 2 days is computed by the class. Writes `cheapest-seat.html` and `cheapest-seat.csv`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import holoviews as hv
import pandas as pd

from avalanche_research.mechanisms import BoundedHarmonicFrontier
from avalanche_research.palette import QUANTITY_COLORS

INK, GRAY = "#333333", "#9aa0a8"
FLOOR_AVAX, AT_14_DAYS_AVAX, CURVATURE = 500.0, 2_000.0, 1.282


def frontier() -> BoundedHarmonicFrontier:
    return BoundedHarmonicFrontier.through(AT_14_DAYS_AVAX, 14, label="Duration-dependent minimum", s_floor_avax=FLOOR_AVAX, p=CURVATURE)


def seats() -> pd.DataFrame:
    stake_at_2 = frontier().min_stake_avax(2)
    rows = [
        ("Before Helicon: 2,000 AVAX for 14 days", 2_000 * 14, GRAY),
        ("After Helicon: 2,000 AVAX for 2 days", 2_000 * 2, QUANTITY_COLORS["rewards"]),
        (f"Duration-dependent minimum: {stake_at_2:,.0f} AVAX for 2 days", round(stake_at_2 * 2), QUANTITY_COLORS["stake"]),
    ]
    return pd.DataFrame(rows, columns=["seat", "avax_days", "color"])


def chart(frame: pd.DataFrame) -> hv.Overlay:
    frame = frame.iloc[::-1]
    bars = hv.Bars(frame, "seat", ["avax_days", "color"]).opts(
        color="color", invert_axes=True, width=1000, height=320, fontscale=1.2, toolbar=None, show_grid=False,
        xlabel="", ylabel="AVAX-days locked", ylim=(0, frame.avax_days.max() * 1.18),
        title="AVAX-days locked by the cheapest allowed validator seat", tools=[], line_color=None, bar_width=0.6)
    placed = frame.assign(text=[f"{v:,}" for v in frame.avax_days], at=frame.avax_days + frame.avax_days.max() * 0.015)
    labels = hv.Labels(placed, ["seat", "at"], "text").opts(invert_axes=True, text_align="left", text_color=INK, text_font_size="13pt")
    return (bars * labels).opts(hooks=[_axes], toolbar=None)


def _axes(plot, element):
    from bokeh.models import NumeralTickFormatter
    plot.state.xaxis.formatter = NumeralTickFormatter(format="0,0")
    plot.state.outline_line_color = None
    plot.state.title.text_color = INK


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    hv.extension("bokeh")
    frame = seats()
    frame.drop(columns="color").to_csv(out / "cheapest-seat.csv", index=False)
    hv.save(chart(frame), out / "cheapest-seat.html")
    print(frame.drop(columns="color").to_string(index=False))


if __name__ == "__main__":
    main()
