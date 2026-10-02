#!/usr/bin/env python3
"""AVAX held by each exchange-traded fund, daily in September 2026, with the two 21Shares steps marked.

    uv run --group notebook python scripts/figures/etf_holdings.py <output folder>

Reads `etf-history-2026-10-01` for the 21Shares Avalanche Staking ETP, which publishes AVAX held every valuation day, and
the daily snapshot runs `etf-snapshot-2026-09-28` to `etf-snapshot-2026-10-01` for Bitwise's BAVA and VanEck's VAVX, whose
histories carry no AVAX figure. Grayscale's GAVA reports quarterly, and two small baskets hold under 100,000 AVAX, so
they are listed in the caption, not drawn. Writes `etf-holdings.csv`, `etf-holdings.html` and `etf-holdings.png`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import holoviews as hv
import pandas as pd
from bokeh.models import NumeralTickFormatter

from avalanche_research import datasets

sys.path.insert(0, str(Path(__file__).resolve().parent))
from png import save_png

HISTORY_RUN = "etf-history-2026-10-01"
SNAPSHOT_RUNS = ("etf-snapshot-2026-09-28", "etf-snapshot-2026-09-29", "etf-snapshot-2026-09-30", "etf-snapshot-2026-10-01")
START = pd.Timestamp("2026-09-01")
NAMES = {"AVAX": "21Shares Avalanche Staking ETP", "BAVA": "Bitwise BAVA", "VAVX": "VanEck VAVX"}
COLOURS = {"AVAX": "#1f5fa8", "BAVA": "#d95f02", "VAVX": "#1b9e77"}


def table() -> pd.DataFrame:
    history = datasets.load("etf-issuers.avax-fund-history", run=HISTORY_RUN)
    shares21 = history[(history.ticker == "AVAX") & (history.valuation_date >= START)][["ticker", "valuation_date", "avax_held"]]
    snapshots = pd.concat([datasets.load("etf-issuers.avax-fund-snapshot", run=run) for run in SNAPSHOT_RUNS])
    us = snapshots[snapshots.ticker.isin(["BAVA", "VAVX"])].rename(columns={"as_of": "valuation_date"})
    us = us[["ticker", "valuation_date", "avax_held"]].drop_duplicates(["ticker", "valuation_date"])
    frame = pd.concat([shares21, us], ignore_index=True).sort_values(["ticker", "valuation_date"])
    frame["fund"] = frame.ticker.map(NAMES)
    frame["change_avax"] = frame.groupby("ticker").avax_held.diff()
    return frame.reset_index(drop=True)


def chart(frame: pd.DataFrame) -> hv.Overlay:
    curves = [hv.Curve(group, "valuation_date", "avax_held", label=NAMES[ticker]).opts(color=COLOURS[ticker], line_width=3,
                                                                                    interpolation="steps-post")
              * hv.Scatter(group, "valuation_date", "avax_held").opts(color=COLOURS[ticker], size=7)
              for ticker, group in frame.groupby("ticker")]
    steps = frame[(frame.ticker == "AVAX") & (frame.change_avax.abs() > 100_000)]
    marks = []
    for _, row in steps.iterrows():
        marks.append(hv.VLine(row.valuation_date).opts(color="#888888", line_dash="dashed"))
        marks.append(hv.Text(row.valuation_date - pd.Timedelta(hours=12), row.avax_held + (280_000 if row.change_avax > 0 else -220_000),
                             f"{row.change_avax:+,.0f} AVAX on {row.valuation_date:%d %b}", halign="right", fontsize=12))
    return hv.Overlay(curves + marks).opts(
        width=1000, height=520, fontscale=1.2, toolbar=None, show_grid=True, legend_position="bottom_left",
        ylim=(0, 3_200_000), xlim=(START, pd.Timestamp("2026-10-02")), yformatter=NumeralTickFormatter(format="0.0a"),
        xlabel="Valuation date. BAVA and VAVX from their daily snapshots, which start 25 Sep", ylabel="AVAX held",
        title="AVAX held by each fund, daily, September 2026")


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    hv.extension("bokeh")
    frame = table()
    frame.to_csv(out / "etf-holdings.csv", index=False)
    hv.save(chart(frame), out / "etf-holdings.html")
    save_png(out / "etf-holdings.html", out / "etf-holdings.png", 1040, 580)
    print(frame.round(0).to_string(index=False))


if __name__ == "__main__":
    main()
