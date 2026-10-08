#!/usr/bin/env python3
"""The coverage chart of deliverable 1.1: staking periods accepted per month, validators and delegations, since 2020.

    uv run --group notebook python scripts/figures/ingestion_coverage.py <page folder> [--run RUN]

Reads one checked run of `derived.staking-periods` through avalanche_research.datasets, the newest by default, and
writes four files with the stem `ingestion-coverage`: a PNG for the page, an HTML for interaction, a CSV holding
exactly the drawn data under readable column names, and a JSON receipt naming the run, its capture and the SHA-256 of
its Parquet file. `scripts/milestone_pages.py build` reads the CSV for the caption and refuses to build when the
receipt names a different run from the one the page reports.

A staking period is one validator or delegation staking transaction, counted in the month its stake was accepted.
The month that holds the run's last acceptance is incomplete and is not drawn. Network upgrades are marked at their
activation times from the run's own upgrade schedule. The green line marks the seam, where the Snowflake share ends
and the P-Chain walk begins.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import holoviews as hv
import pandas as pd
from bokeh.models import Label, Span

from avalanche_research import datasets
from avalanche_research.catalog import sha256

sys.path.insert(0, str(Path(__file__).resolve().parent))
from png import save_png

DATASET = "derived.staking-periods"
SEAMED = "derived.seamed-validator-stakes"
STEM = "ingestion-coverage"
COLUMNS = {"month": "Month accepted", "delegator": "Delegations", "validator": "Validator staking periods"}
BLUE, ORANGE, GREEN, MUTED = "#1f5fa8", "#d95f02", "#1b7f3b", "#7a7f87"
WIDTH, HEIGHT = 820, 440


def newest_run() -> str:
    return datasets.receipt(DATASET)["run"]


def table(run: str) -> tuple[pd.DataFrame, str]:
    """Counts per complete month, and the timestamp of the run's last acceptance."""
    rows = datasets.load(DATASET, run=run)[["role", "accepted_at"]]
    accepted = pd.to_datetime(rows.accepted_at)
    accepted = accepted.dt.tz_localize(None) if accepted.dt.tz is not None else accepted
    last = accepted.max()
    rows = rows.assign(month=accepted.dt.to_period("M").dt.to_timestamp())
    counts = rows.groupby(["month", "role"]).size().unstack("role", fill_value=0).reset_index()
    counts = counts.loc[counts.month < last.to_period("M").to_timestamp()]
    frame = counts[["month", "delegator", "validator"]].rename(columns=COLUMNS)
    frame[COLUMNS["month"]] = frame[COLUMNS["month"]].dt.strftime("%Y-%m")
    return frame.reset_index(drop=True), str(last)


def upgrades(run: str) -> dict[str, pd.Timestamp]:
    """Named upgrades from Banff on, at their activation times, from the run's capture."""
    schedule = datasets.receipt(DATASET, run)["capture"]["upgrades"]
    named = [item for item in schedule if not item["name"].startswith("apricot")]
    return {item["name"].title(): pd.Timestamp(item["activated_at"]).tz_localize(None) for item in named}


def seam(run: str) -> tuple[str, pd.Timestamp]:
    """The seamed validator run this staking-periods run read, and its seam."""
    inputs = datasets.receipt(DATASET, run)["capture"]["inputs"]
    seamed = next(item["run"] for item in inputs if item["dataset_id"] == SEAMED)
    return seamed, pd.Timestamp(datasets.receipt(SEAMED, seamed)["capture"]["seam"])


def chart(frame: pd.DataFrame, marks: dict[str, pd.Timestamp], seam_at: pd.Timestamp) -> hv.Overlay:
    data = frame.assign(month=pd.to_datetime(frame[COLUMNS["month"]]))
    top = data[COLUMNS["delegator"]].max()

    def hook(plot, element):
        figure = plot.state
        for index, (name, at) in enumerate(marks.items()):
            if name == "Helicon":
                continue
            figure.add_layout(Span(location=at, dimension="height", line_color=MUTED, line_dash="dotted", line_width=1))
            figure.add_layout(Label(x=at, y=top * (4.5 if index % 2 else 2.6), text=name, text_color=MUTED,
                                    text_font_size="11px", text_align="left", x_offset=3))
        figure.add_layout(Span(location=seam_at, dimension="height", line_color=GREEN, line_width=2))
        figure.add_layout(Label(x=seam_at, y=top * 2.6, text="Helicon, share ends", text_color=GREEN,
                                text_font_size="11px", text_align="right", x_offset=-4))
        figure.toolbar_location = None
        figure.xaxis.axis_label_text_font_style = figure.yaxis.axis_label_text_font_style = "normal"

    delegations = hv.Curve(data, "month", COLUMNS["delegator"], label="Delegations").opts(color=BLUE, line_width=2.5)
    validators = hv.Curve(data, "month", COLUMNS["validator"], label="Validator staking periods").opts(color=ORANGE, line_width=2.5)
    return (delegations * validators).opts(
        width=WIDTH, height=HEIGHT, logy=True, ylim=(100, top * 8), show_grid=True, fontscale=1.1, toolbar=None,
        xlim=(data.month.min() - pd.Timedelta(days=20), seam_at + pd.Timedelta(days=75)), hooks=[hook], legend_position="top_left",
        title=f"Staking periods accepted per month, {data.month.min():%B %Y} to {data.month.max():%B %Y}",
        xlabel="Month the stake was accepted", ylabel="Staking periods (log scale)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path, help="the page folder")
    parser.add_argument("--run", default=None, help=f"run of {DATASET}; the newest by default")
    args = parser.parse_args()
    run = args.run or newest_run()
    hv.extension("bokeh")
    frame, last = table(run)
    seamed_run, seam_at = seam(run)
    args.out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.out / f"{STEM}.csv", index=False)
    hv.save(chart(frame, upgrades(run), seam_at), args.out / f"{STEM}.html")
    save_png(args.out / f"{STEM}.html", args.out / f"{STEM}.png", WIDTH + 40, HEIGHT + 40)
    receipt = datasets.receipt(DATASET, run)
    record = {
        "chart": STEM, "script": "scripts/figures/ingestion_coverage.py",
        "run": {"dataset_id": DATASET, "run": run, "capture_id": receipt["capture"]["capture_id"],
                "parquet_sha256": sha256(datasets.parquet_path(DATASET, run).read_bytes())},
        "seam": {"dataset_id": SEAMED, "run": seamed_run, "at_utc": str(seam_at)},
        "last_acceptance_utc": last,
        "notes": ["One row per complete month: the month holding the last acceptance is not drawn.",
                  "Counts are staking transactions by the month their stake was accepted, validators and delegations apart."],
    }
    (args.out / f"{STEM}.json").write_text(json.dumps(record, indent=1) + "\n")
    print(frame.tail(3).to_string(index=False))
    print(f"run {run}: months {len(frame)}, validator periods {frame[COLUMNS['validator']].sum()}, delegations {frame[COLUMNS['delegator']].sum()}")


if __name__ == "__main__":
    main()
