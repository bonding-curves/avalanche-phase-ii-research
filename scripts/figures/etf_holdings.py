#!/usr/bin/env python3
"""AVAX held by each exchange-traded fund, daily from September 2026, with the large 21Shares steps marked.

    uv run --group notebook python scripts/figures/etf_holdings.py <output folder>

Two sources, drawn apart. The 21Shares Avalanche Staking ETP publishes AVAX held every valuation day, read from the
issuer history run `etf-history-2026-10-06` (pinned in `data/pins/p3-helicon-etf.json`); it is a solid line. Bitwise's
BAVA and VanEck's VAVX publish no AVAX history, so their points are our own daily snapshot runs from
`etf-snapshot-2026-09-28` to `etf-snapshot-2026-10-06`, dashed. A pin holds one run per dataset, so only the newest
snapshot is pinned; `etf-holdings-runs.json` names every run read with its Parquet sha256. A change in holdings is a
flow inferred from holdings, not a reported flow. Grayscale's GAVA reports quarterly, and two small baskets hold under
100,000 AVAX, so they are not drawn. Writes `etf-holdings.csv`, `etf-holdings-runs.json`, `etf-holdings.html` and
`etf-holdings.png`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import holoviews as hv
import pandas as pd
from bokeh.models import NumeralTickFormatter

from avalanche_research import datasets
from avalanche_research.catalog import sha256

sys.path.insert(0, str(Path(__file__).resolve().parent))
from png import save_png

HISTORY_RUN = "etf-history-2026-10-06"
SNAPSHOT_RUNS = tuple(f"etf-snapshot-2026-{day}" for day in ("09-28", "09-29", "09-30", "10-01", "10-02", "10-03", "10-04", "10-05",
                                                            "10-06"))
DATA_AS_OF = "2026-10-05"
SOURCE = {"AVAX": "issuer history", "BAVA": "our daily snapshots", "VAVX": "our daily snapshots"}
START = pd.Timestamp("2026-09-01")
NAMES = {"AVAX": "21Shares Avalanche Staking ETP", "BAVA": "Bitwise BAVA", "VAVX": "VanEck VAVX"}
COLOURS = {"AVAX": "#1f5fa8", "BAVA": "#d95f02", "VAVX": "#1b9e77"}
SHORT = {"AVAX": "21Shares ETP", "BAVA": "Bitwise BAVA", "VAVX": "VanEck VAVX"}


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
    curves = [hv.Curve(group, "valuation_date", "avax_held").opts(color=COLOURS[ticker], line_width=3, interpolation="steps-post",
                                                                 line_dash="solid" if ticker == "AVAX" else "dashed")
              * hv.Scatter(group, "valuation_date", "avax_held").opts(color=COLOURS[ticker], size=7)
              for ticker, group in frame.groupby("ticker")]
    marks = []
    for ticker, group in frame.groupby("ticker"):
        last = group.iloc[-1]
        marks.append(hv.Text(last.valuation_date + pd.Timedelta(hours=14), last.avax_held,
                             f"{SHORT[ticker]}  {last.avax_held / 1e6:.2f}M", halign="left", fontsize=12).opts(color=COLOURS[ticker]))
    first_us = frame[frame.ticker == "BAVA"].iloc[0]
    marks.append(hv.Text(first_us.valuation_date - pd.Timedelta(hours=14), first_us.avax_held,
                         "US funds: daily capture starts 25 Sep", halign="right", fontsize=11).opts(color="#666666"))
    steps = frame[(frame.ticker == "AVAX") & (frame.change_avax.abs() > 100_000)]
    for _, row in steps.iterrows():
        before = row.avax_held - row.change_avax
        rising = row.change_avax > 0
        x = row.valuation_date + pd.Timedelta(hours=-10 if rising else 14)
        y = (before + row.avax_held) / 2 if rising else row.avax_held - 200_000
        marks.append(hv.Text(x, y, f"{row.change_avax:+,.0f} AVAX on {row.valuation_date:%d %b}, inferred from holdings",
                             halign="right" if rising else "left", fontsize=12).opts(color=COLOURS["AVAX"]))
    return hv.Overlay(curves + marks).opts(
        width=1000, height=520, fontscale=1.2, toolbar=None, show_grid=True, show_legend=False,
        ylim=(0, 3_200_000), xlim=(START, pd.Timestamp("2026-10-20")), yformatter=NumeralTickFormatter(format="0.[0]a"),
        xlabel=f"Valuation date. Solid: issuer history. Dashed: our daily snapshots. Data as of {DATA_AS_OF}",
        ylabel="AVAX held",
        title="AVAX held by each fund, daily, September and October 2026")


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    hv.extension("bokeh")
    frame = table()
    frame.assign(source=frame.ticker.map(SOURCE)).to_csv(out / "etf-holdings.csv", index=False)
    runs = {"etf-issuers.avax-fund-history": [HISTORY_RUN], "etf-issuers.avax-fund-snapshot": list(SNAPSHOT_RUNS)}
    receipt = {dataset_id: [{"run": run, "parquet_sha256": sha256(datasets.parquet_path(dataset_id, run).read_bytes())} for run in names]
               for dataset_id, names in runs.items()}
    (out / "etf-holdings-runs.json").write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n")
    hv.save(chart(frame), out / "etf-holdings.html")
    save_png(out / "etf-holdings.html", out / "etf-holdings.png", 1040, 580)
    print(frame.round(0).to_string(index=False))


if __name__ == "__main__":
    main()
