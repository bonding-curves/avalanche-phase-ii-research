#!/usr/bin/env python3
"""Share of new validator commitments under 16 days, by upgrade from Banff to Fortuna: GoGoPool, all other operators, and
the whole network.

    uv run --group notebook python scripts/figures/gogopool_short_share.py <output folder>

Reads `notebooks/results/gogopool-durations.json`, built from `staking-periods-2026-09-30` and `operators-2026-09-30`.
Every commitment counted was accepted before Granite (2025-11-19 16:00 UTC), so nothing from the held-back window is
shown. Era is the upgrade in force at acceptance. GoGoPool is the latest reward-address grouping, which is retrospective.
Writes `gogopool-short-share.csv`, `.html` and `.png`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import holoviews as hv
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from png import save_png

RESULTS = Path(__file__).resolve().parents[2] / "notebooks" / "results" / "gogopool-durations.json"
ERAS = ("banff", "cortina", "durango", "etna", "fortuna")
GROUPS = {"GoGoPool": "GoGoPool", "Other": "All other operators", "All": "Whole network"}
AS_OF = "2026-09-30 02:28 UTC"


def table() -> pd.DataFrame:
    rows = [row for row in json.loads(RESULTS.read_text())["by_era"] if row["era"] in ERAS]
    frame = pd.DataFrame(rows)
    frame["upgrade"] = frame.era.str.title()
    frame["operators"] = frame.group.map(GROUPS)
    frame["share_pct"] = 100 * frame.under_16_days_share
    order = {era.title(): i for i, era in enumerate(ERAS)}
    frame["order"] = frame.upgrade.map(order) * 10 + frame.group.map({"GoGoPool": 0, "Other": 1, "All": 2})
    return frame.sort_values("order")[["upgrade", "operators", "commitments", "under_16_days", "share_pct"]].reset_index(drop=True)


def chart(frame: pd.DataFrame) -> hv.Bars:
    def hook(plot, element):
        plot.state.xaxis.major_label_text_font_size = "0pt"
        plot.state.xaxis.group_text_font_size = "14px"
        plot.state.xaxis.group_text_color = "#333333"

    return hv.Bars(frame, ["upgrade", "operators"], "share_pct").opts(
        width=1000, height=520, fontscale=1.2, toolbar=None, show_grid=True, ylim=(0, 105), multi_level=True,
        color="operators", cmap=["#1f5fa8", "#9aa5b1", "#d95f02"], show_legend=True, legend_position="top_left", hooks=[hook],
        title="Share of new validator commitments under 16 days, by upgrade: GoGoPool against all other operators",
        xlabel=f"Upgrade in force at acceptance, Banff to Fortuna, before November 2025. Data as of {AS_OF}",
        ylabel="Commitments under 16 days (%)")


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    hv.extension("bokeh")
    frame = table()
    frame.to_csv(out / "gogopool-short-share.csv", index=False)
    hv.save(chart(frame), out / "gogopool-short-share.html")
    save_png(out / "gogopool-short-share.html", out / "gogopool-short-share.png", 1040, 580)
    print(frame.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
