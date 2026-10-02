#!/usr/bin/env python3
"""A minimum validator stake that falls with committed duration: the two charts and the numbers of the memo.

    uv run --group notebook --group model python scripts/figures/em2_minimum_stake.py <memo folder>

The admission rule is the bounded harmonic curve in avalanche_research.mechanisms, the frontier Hash designed:

    S_min(d) = S_floor + (S_short - S_floor) * eta(d) ** p,   eta(d) = (1/d - 1/365) / (1/2 - 1/365)

Three settings are drawn: today's flat 2,000 AVAX, Hash's recommended package (18,000 AVAX at 48 hours, 500 AVAX at a
year, curvature 0.615), and the setting that holds 28,000 AVAX-days at every duration with 2,000 AVAX at 14 days
(19,400 AVAX at 48 hours, 500 at a year, curvature 1.28). It reads the pinned run `staking-periods-2026-09-30` through
avalanche_research.datasets, judging each validator commitment accepted from 2024-11-19 to 2025-11-19 16:00 UTC at
its own stake and duration. Writes `minimum-stake-by-duration.{csv,html}` and `capital-by-duration.html`, and prints
the numbers the memo quotes.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import holoviews as hv
import numpy as np
import pandas as pd

from avalanche_research import datasets
from avalanche_research.mechanisms import BoundedHarmonicFrontier, ChainAdmission
from avalanche_research.mechanisms.cohort import load_periods, validator_periods
from avalanche_research.palette import QUANTITY_COLORS
from avalanche_research.views.mechanism_explorer import admission_table

RUN = "staking-periods-2026-09-30"
JUDGED_AT = datetime(2026, 9, 30, tzinfo=UTC)
PARITY_AVAX_DAYS = 2_000 * 14
TICKS = [2, 7, 14, 30, 90, 182, 365]
RULES = {
    "Today: 2,000 AVAX at any duration": (ChainAdmission(label="Today"), QUANTITY_COLORS["commitments"], "dashed"),
    "Hash's recommended package: 18,000 to 500 AVAX": (
        BoundedHarmonicFrontier(label="Recommended package", s_short_avax=18_000, s_floor_avax=500, p=0.615),
        QUANTITY_COLORS["nodes"], "solid"),
    "2,000 AVAX at 14 days: 19,400 to 500 AVAX": (
        BoundedHarmonicFrontier(label="2,000 AVAX at 14 days", s_short_avax=19_400, s_floor_avax=500, p=1.28),
        QUANTITY_COLORS["stake"], "solid"),
}


def curves() -> pd.DataFrame:
    days = np.geomspace(2, 365, 300)
    rows = [{"setting": name, "duration_days": d, "min_stake_avax": rule.min_stake_avax(d)}
            for name, (rule, _, _) in RULES.items() for d in days]
    frame = pd.DataFrame(rows)
    frame["avax_days"] = frame.min_stake_avax * frame.duration_days
    return frame


def chart(frame: pd.DataFrame, value: str, title: str, ylabel: str, yticks: list[int], legend: str,
          reference: float | None = None) -> hv.Overlay:
    lines = []
    for name, (_, color, dash) in RULES.items():
        part = frame[frame.setting == name]
        lines.append(hv.Curve(part, "duration_days", [value, "setting"], label=name).opts(
            color=color, line_dash=dash, line_width=3, tools=["hover"]))
    if reference is not None:
        lines.append(hv.HLine(reference).opts(color="#999999", line_width=1.5, line_dash="dotted"))
        lines.append(hv.Text(16, reference * 0.86, "2,000 AVAX for 14 days", halign="left").opts(
            text_font_size="11pt", text_color="#555555"))
    return hv.Overlay(lines).opts(
        width=1000, height=520, fontscale=1.2, toolbar=None, show_grid=True, logx=True, logy=True,
        xticks=[(t, str(t)) for t in TICKS], yticks=[(t, f"{t:,}") for t in yticks], xlim=(1.85, 395),
        legend_position=legend, title=title,
        xlabel="Committed duration (days)", ylabel=ylabel)


def numbers() -> pd.DataFrame:
    validators = validator_periods(load_periods(str(datasets.parquet_path("derived.staking-periods", RUN))))
    shares = admission_table([rule for rule, _, _ in RULES.values()], validators, JUDGED_AT)
    grid = np.linspace(2, 365, 36_301)
    rows = []
    for (name, (rule, _, _)), share in zip(RULES.items(), shares.itertuples(index=False)):
        rows.append({"setting": name, **{f"{d}d": round(rule.min_stake_avax(d)) for d in (2, 7, 14, 30, 90, 365)},
                     "least_avax_days": round(min(rule.min_stake_avax(d) * d for d in grid)),
                     "commitments_meeting_it_pct": round(100 * share.periods_admitted, 1),
                     "stake_meeting_it_pct": round(100 * share.avax_admitted, 1)})
    print(f"validator commitments judged: {len(validators)}")
    return pd.DataFrame(rows)


def main() -> None:
    out = Path(sys.argv[1])
    hv.extension("bokeh")
    frame = curves()
    frame.to_csv(out / "minimum-stake-by-duration.csv", index=False)
    hv.save(chart(frame, "min_stake_avax", "A minimum that falls with duration can keep 2,000 AVAX at 14 days and reach 500 at a year",
                  "Minimum validator stake (AVAX)", [500, 1_000, 2_000, 5_000, 10_000, 20_000], "top_right"), out / "minimum-stake-by-duration.html")
    hv.save(chart(frame, "avax_days", "The 2,000-at-14-days setting keeps at least 28,000 AVAX-days at every duration",
                  "Minimum stake times duration (AVAX-days)", [4_000, 10_000, 28_000, 100_000, 300_000, 730_000], "top_left",
                  PARITY_AVAX_DAYS), out / "capital-by-duration.html")
    print(numbers().to_string(index=False))


if __name__ == "__main__":
    main()
