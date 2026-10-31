"""Rebuild the reported central case's three trajectory panels from checked output.

Run after scripts/reproduce_report.py has completed. This figure uses only the
pre-origin record and the reproduced simulations, with no forecast scoring.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

PROJECT = Path(__file__).resolve().parents[2]
ORIGIN = pd.Timestamp("2025-11-18")
END = pd.Timestamp("2026-11-18")
CELLS = ("chain-central", "ramp-7.5-central")
MEASURES = {
    "validator_stake_avax": "Validator own stake (AVAX)",
    "active_validators": "Active validators",
    "total_supply_avax": "Supply (AVAX)",
}
COLORS = {"chain-central": "#6b7079", "ramp-7.5-central": "#0e7c86"}
LABELS = {"chain-central": "Historical schedule", "ramp-7.5-central": "Earlier ACP-285 ramp"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trajectory_quantiles(daily: pd.DataFrame) -> pd.DataFrame:
    """Use the original P1-a scaling and linear trajectory percentiles."""
    expected = pd.MultiIndex.from_product([CELLS, range(50), range(366)], names=["cell", "key", "day"])
    actual = pd.MultiIndex.from_frame(daily[["cell", "key", "day"]])
    if len(actual) != len(expected) or actual.has_duplicates or set(actual) != set(expected):
        raise ValueError("figure requires all 100 original paths and 366 daily states per path")
    dates = ORIGIN + pd.to_timedelta(daily["day"], unit="D")
    if not dates.equals(pd.to_datetime(daily["date"])):
        raise ValueError("figure dates differ from the original origin and daily clock")
    frame = daily[["cell", "key", "date", "active_validators"]].copy()
    frame["date"] = dates
    frame["validator_stake_avax"] = daily["validator_stake_navax"].to_numpy(float) / 1e9
    frame["total_supply_avax"] = daily["realized_supply_navax"].to_numpy(float) / 1e9
    if not np.isfinite(frame[list(MEASURES)].to_numpy(float)).all():
        raise ValueError("figure inputs must be finite")
    parts = []
    for name in MEASURES:
        grouped = frame.groupby(["cell", "date"])[name]
        values = grouped.quantile([0.1, 0.5, 0.9], interpolation="linear").unstack()
        values.columns = ["p10", "median", "p90"]
        values["paths"] = grouped.count()
        values["measure"] = name
        parts.append(values.reset_index())
    return pd.concat(parts, ignore_index=True)[["cell", "date", "measure", "paths", "p10", "median", "p90"]]


def read_record(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["date"])
    if list(frame) != ["date", *MEASURES]:
        raise ValueError("pre-origin record columns differ")
    expected = pd.date_range("2020-09-22", ORIGIN)
    if not pd.DatetimeIndex(frame["date"]).equals(expected):
        raise ValueError("record must contain each day through the origin, with no later observations")
    if not np.isfinite(frame[list(MEASURES)].to_numpy(float)).all():
        raise ValueError("pre-origin record contains nonfinite observations")
    return frame


def render(inputs: Path, result: Path, output: Path) -> dict:
    # The runtime checker authenticates the full inputs and original-path comparison.
    sys.path.insert(0, str(PROJECT / "scripts"))
    from reproduce_report import check_result

    check_result(inputs, result)
    record_path = inputs / "figure-record-before-origin.csv"
    record = read_record(record_path)
    daily = trajectory_quantiles(pd.read_csv(result / "daily.csv"))
    output.mkdir(parents=True, exist_ok=False)
    table = output / "figure-data.csv"
    daily.to_csv(table, index=False, date_format="%Y-%m-%d", float_format="%.17g", lineterminator="\n")
    style = {"font.family": "DejaVu Sans", "font.size": 12, "axes.spines.top": False,
             "axes.spines.right": False, "axes.labelcolor": "#374151", "xtick.color": "#4b5563",
             "ytick.color": "#4b5563", "svg.hashsalt": "central-case-reproduction-v1"}
    with plt.rc_context(style):
        fig, axes = plt.subplots(3, 1, figsize=(11, 10.5), sharex=True)
        fig.subplots_adjust(left=0.12, right=0.97, top=0.85, bottom=0.16, hspace=0.22)
        fig.text(0.04, 0.965, "Staking under the historical schedule and an earlier ramp", fontsize=17,
                 weight="bold", va="top", color="#1f2937")
        fig.text(0.04, 0.923,
                 "Model v0.8.0 · 50 paired one-year runs from 18 November 2025\n"
                 "Lines: medians. Bands: 10th–90th percentiles across simulated paths.",
                 fontsize=12, va="top", color="#4b5563", linespacing=1.5)
        for axis, (name, label), color in zip(axes, MEASURES.items(), ["#3566a3", "#202020", "#c13a5b"]):
            axis.axvspan(ORIGIN, END, color="#f7f4ef", zorder=0)
            axis.grid(axis="y", color="#e5e7eb", linewidth=0.6)
            axis.plot(record["date"], record[name], color=color, linewidth=1.4, label="Recorded before origin")
            for cell in CELLS:
                q = daily[(daily["measure"] == name) & (daily["cell"] == cell)]
                axis.fill_between(q["date"], q["p10"], q["p90"], color=COLORS[cell], alpha=0.18, linewidth=0)
                axis.plot(q["date"], q["median"], color=COLORS[cell], linewidth=1.7, label=LABELS[cell])
            axis.axvline(ORIGIN, color="#202020", linewidth=0.9)
            axis.axvline(pd.Timestamp("2026-09-22"), color="#9ca3af", linewidth=0.7, linestyle="--")
            axis.set_ylabel(label)
            axis.tick_params(labelsize=11)
            if name != "active_validators":
                axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value / 1e6:,.0f}M"))
        axes[0].set_ylim(0, 290e6)
        axes[1].set_ylim(0, 2150)
        axes[2].set_ylim(300e6, 760e6)
        axes[0].annotate("Runs start", (ORIGIN, 280e6), xytext=(-6, 0), textcoords="offset points",
                         ha="right", va="top", fontsize=10.5, color="#4b5563")
        axes[1].text(pd.Timestamp("2026-09-22"), 2020, "Helicon", ha="right", va="top",
                     fontsize=10.5, color="#6b7079")
        axes[2].axhline(720e6, color="#202020", linestyle="--", linewidth=0.9)
        axes[2].text(record["date"].iloc[25], 725e6, "Supply cap: 720M AVAX", fontsize=11, va="bottom")
        axes[0].legend(loc="lower left", fontsize=10.5, frameon=True, framealpha=0.95)
        axes[-1].set_xlim(record["date"].iloc[0], END)
        axes[-1].xaxis.set_major_locator(mdates.YearLocator())
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        axes[-1].set_xlabel("Calendar year")
        fig.text(0.04, 0.085,
                 "Early ramp to 7.5% over 90 days. Renewal response: 0.025, entry: 0.04, outside yield: 5%.\n"
                 "Reference: historical schedule, with ACP-285 from Helicon (22 September 2026, 15:00 UTC).\n"
                 "Supply adds validator reward promises and subtracts fixed burn. Delegated issuance omitted.\n"
                 "Bands describe variation across simulated paths. No forecast evaluation is performed.",
                 fontsize=10.5, va="top", color="#4b5563", linespacing=1.5)
        fig.savefig(output / "figure.png", dpi=126, facecolor="white")
        fig.savefig(output / "figure.svg", facecolor="white", metadata={"Date": None})
        plt.close(fig)
    sources = {"daily.csv": digest(result / "daily.csv"), "summary.json": digest(result / "summary.json"),
               "figure-record-before-origin.csv": digest(record_path),
               "producer": digest(Path(__file__)), "uv.lock": digest(PROJECT / "uv.lock")}
    receipt = {"schema": "central-case-reproduction-figure/v1", "model": "v0.8.0",
               "sources_sha256": sources, "original_figure": "central-trajectories.png",
               "original_figure_sha256": "b87d5d8d30cd0dd15750851a8e4c612e04bde7cd5067d2175243fa80579b53d1",
               "original_panels": ["validator own stake", "active validators", "supply"],
               "presentation": "Rebuilt panels with explicit reproduction caption and formula terminology.",
               "quantiles": "Linear 10th, 50th and 90th percentiles of absolute trajectories; 50 paths per cell/day.",
               "forecast_evaluation": False,
               "artifacts": {name: {"sha256": digest(output / name), "bytes": (output / name).stat().st_size}
                             for name in ("figure-data.csv", "figure.png", "figure.svg")}}
    (output / "figure-provenance.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    render(args.inputs.resolve(), args.result.resolve(), args.output.resolve())
    print(json.dumps({"status": "pass", "figure": str(args.output / "figure.png")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
