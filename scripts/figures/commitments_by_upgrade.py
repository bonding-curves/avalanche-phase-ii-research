#!/usr/bin/env python3
"""Validator commitments by the upgrade period in which they began: the table and the headline chart of the memo.

    uv run --group notebook python scripts/figures/commitments_by_upgrade.py <memo folder>

Reads one pinned run, `staking-periods-2026-09-22`, through avalanche_research.datasets, and writes
`commitments-by-upgrade.csv`, `commitments-by-upgrade.html` (interactive), and prints the table as Markdown.
A commitment is one validator staking transaction's period. "At the minimum" means a duration under 16 days,
which holds the protocol's 14-day minimum and the start delays of up to two days observed before Durango.
"""

from __future__ import annotations

import sys
from pathlib import Path

import holoviews as hv
import pandas as pd
from bokeh.models import Label, Span

from avalanche_research import datasets

RUN = "staking-periods-2026-09-22"
ORDER = ["Genesis", "Apricot", "Banff", "Cortina", "Durango", "Etna", "Fortuna", "Granite"]
AT_MINIMUM_DAYS = 16


def period(regime: str) -> str | None:
    if regime.startswith("apricot"):
        return "Apricot"
    name = regime.title()
    return name if name in ORDER else None


def table() -> pd.DataFrame:
    rows = datasets.load("derived.staking-periods", run=RUN)
    rows = rows.loc[rows.role.eq("validator"), ["node_id", "regime", "duration_days", "stake_avax"]].copy()
    rows["period"] = rows.regime.map(period)
    rows = rows.dropna(subset=["period"])
    rows["weeks"] = rows.duration_days / 7
    rows["avax_days"] = rows.stake_avax * rows.duration_days
    rows["at_min"] = rows.duration_days < AT_MINIMUM_DAYS

    def summary(group: pd.DataFrame) -> pd.Series:
        ordered = group.sort_values("weeks")
        weighted = ordered.loc[ordered.stake_avax.cumsum().ge(ordered.stake_avax.sum() / 2), "weeks"].iloc[0]
        return pd.Series({
            "commitments": len(group),
            "nodes": group.node_id.nunique(),
            "median_weeks": group.weeks.median(),
            "stake_weighted_median_weeks": weighted,
            "median_self_stake_avax": group.stake_avax.median(),
            "share_at_minimum_pct": 100 * group.at_min.mean(),
            "avax_days_share_at_minimum_pct": 100 * group.avax_days[group.at_min].sum() / group.avax_days.sum(),
        })

    return rows.groupby("period").apply(summary, include_groups=False).reindex(ORDER).reset_index()


def chart(frame: pd.DataFrame) -> hv.Overlay:
    blue, grey = "#1f5fa8", "#6b7785"
    count = hv.Curve(frame, "period", "share_at_minimum_pct", label="Share of new commitments at the minimum").opts(color=blue, line_width=4)
    capital = hv.Curve(frame, "period", "avax_days_share_at_minimum_pct", label="Share of committed AVAX-days they hold").opts(color=grey, line_width=4, line_dash="dashed")
    points = hv.Scatter(frame, "period", "share_at_minimum_pct").opts(color=blue, size=9) * hv.Scatter(frame, "period", "avax_days_share_at_minimum_pct").opts(color=grey, size=9)

    def hook(plot, element):
        figure = plot.state
        durango = ORDER.index("Durango")  # the boundary between Cortina and Durango
        figure.add_layout(Span(location=durango, dimension="height", line_color="#c0392b", line_dash="dotted", line_width=2))
        figure.add_layout(Label(x=durango + 0.05, y=90, text="Durango activates, 2024-03-06", text_color="#c0392b", text_font_size="13px"))
        for row in frame.itertuples():
            x = ORDER.index(row.period) + 0.5
            figure.add_layout(Label(x=x, y=row.share_at_minimum_pct + 3, text=f"{row.share_at_minimum_pct:.0f}%", text_align="center", text_color=blue, text_font_size="13px", text_font_style="bold"))
            figure.add_layout(Label(x=x, y=row.avax_days_share_at_minimum_pct + 3, text=f"{row.avax_days_share_at_minimum_pct:.0f}%", text_align="center", text_color=grey, text_font_size="12px"))
        figure.toolbar_location = None
        figure.legend.location = "top_left"
        figure.xaxis.axis_label_text_font_style = figure.yaxis.axis_label_text_font_style = "normal"

    return (count * capital * points).opts(
        width=1000, height=520, ylim=(0, 100), show_grid=True, fontscale=1.2, toolbar=None, hooks=[hook],
        title="Since Durango, most new commitments stop at the minimum, holding 3 to 11% of the capital",
        xlabel="Upgrade period in which the commitment began", ylabel="Share at the minimum duration (%)")


def main() -> None:
    out = Path(sys.argv[1])
    hv.extension("bokeh")
    frame = table()
    frame.to_csv(out / "commitments-by-upgrade.csv", index=False)
    hv.save(chart(frame), out / "commitments-by-upgrade.html")
    print(frame.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
