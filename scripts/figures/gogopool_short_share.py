#!/usr/bin/env python3
"""Share of new validator commitments under 16 days, by upgrade from Banff to Granite: GoGoPool, all other operators, and
the whole network.

    uv run --group notebook python scripts/figures/gogopool_short_share.py <output folder>

Reads `notebooks/results/gogopool-durations.json` for Banff to Fortuna, built from `staking-periods-2026-09-30` and
`operators-2026-09-30`, and computes Granite (accepted 2025-11-19 16:00 UTC to Helicon) from the same runs with the same
rules. Granite is the held-back window, shown on Shawn's decision of 2026-10-02 and recorded as a known exposure in the
lockbox contamination register. Era is the upgrade in force at acceptance. GoGoPool is the latest reward-address grouping, which is retrospective.
Writes `gogopool-short-share.csv`, `.html` and `.png`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import holoviews as hv
import pandas as pd

from avalanche_research import datasets

sys.path.insert(0, str(Path(__file__).resolve().parent))
from png import save_png

RESULTS = Path(__file__).resolve().parents[2] / "notebooks" / "results" / "gogopool-durations.json"
ERAS = ("banff", "cortina", "durango", "etna", "fortuna", "granite")
RUNS = {"derived.staking-periods": "staking-periods-2026-09-30", "derived.operators": "operators-2026-09-30"}
GROUPS = {"GoGoPool": "GoGoPool", "Other": "All other operators", "All": "Whole network"}
AS_OF = "2026-09-30 02:28 UTC"


def granite_rows() -> list[dict]:
    """Granite by the rules of `gogopool-durations.json`: validator commitments, under 16 days, GoGoPool by named agent."""
    connection = duckdb.connect()
    for name, key in [("periods", "derived.staking-periods"), ("operators", "derived.operators")]:
        connection.read_parquet(str(datasets.parquet_path(key, RUNS[key]))).create_view(name)
    frame = connection.sql("""
        SELECT p.duration_days, coalesce(o.named_agent = 'GoGoPool (Hypha)', false) AS gogopool
        FROM periods p LEFT JOIN operators o USING (node_id)
        WHERE p.role = 'validator' AND p.regime = 'granite'
    """).df()
    connection.close()
    rows = []
    for group, selected in [("All", frame), ("GoGoPool", frame[frame.gogopool]), ("Other", frame[~frame.gogopool])]:
        if len(selected):
            short = int((selected.duration_days < 16).sum())
            rows.append({"era": "granite", "group": group, "commitments": len(selected), "under_16_days": short,
                         "under_16_days_share": short / len(selected)})
    return rows


def table() -> pd.DataFrame:
    rows = [row for row in json.loads(RESULTS.read_text())["by_era"] if row["era"] in ERAS] + granite_rows()
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
        xlabel=f"Upgrade in force at acceptance, Banff to Granite. Granite is the held-back period. Data as of {AS_OF}",
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
