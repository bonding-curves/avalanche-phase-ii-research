#!/usr/bin/env python3
"""Build F1 from frozen records, or replay from the delivered 954-row extract.

From a checkout with the two named data runs installed::

    uv run --group notebook --with matplotlib==3.10.8 python \
        scripts/figures/helicon_commitment_comparison.py OUTPUT --extract

Without those runs, rebuild from OUTPUT/commitments.csv and provenance.json by
omitting --extract. Writes PNG, SVG, standalone HTML and summary.json to OUTPUT.
No network request, model fit or automatic run selection is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ACTIVATION = pd.Timestamp("2026-09-22 15:00:00")
END = pd.Timestamp("2026-10-27 00:00:00")
START = ACTIVATION - (END - ACTIVATION)
COLOURS = {"Before Helicon": "#3566a3", "After Helicon": "#b85c00"}
AREA_MAX_PT2 = 420.0
SIZE_EXAMPLES = [1e4, 1e6, 1e8]
EXPECTED = {
    "derived.staking-periods": (
        "staking-periods-2026-10-27",
        "1dd095cec9465c4b55438d710ac8b8ab6323cf2704c5feddfeaa8244c80517f8",
    ),
    "derived.helicon-commitments": (
        "helicon-commitments-2026-10-27",
        "5e38203a836c146fde468faef1d2d9e2fd584b32ec08b4a2963712bf77babc20",
    ),
}


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def bubble_weight(stake_avax, duration_days):
    """Square root of scheduled AVAX-days."""
    return np.sqrt(stake_avax * duration_days)


def bubble_area(stake_avax, duration_days, maximum_weight):
    """True circle area proportional to square-root AVAX-days, without a floor."""
    return AREA_MAX_PT2 * bubble_weight(stake_avax, duration_days) / maximum_weight


def write_size_metadata(folder, frame):
    path = folder / "provenance.json"
    metadata = json.loads(path.read_text())
    weights = bubble_weight(frame.stake_avax, frame.duration_days)
    metadata["size"] = {
        "mapping": "area_pt2 = 420 * sqrt(stake_avax * duration_days) / maximum_weight",
        "maximum_weight": float(weights.max()),
        "area_range_pt2": [
            float(AREA_MAX_PT2 * weights.min() / weights.max()),
            AREA_MAX_PT2,
        ],
        "additive_floor": 0,
        "shared_across": "Both cohorts, the static figure and the interactive figure",
    }
    path.write_text(json.dumps(metadata, indent=2) + "\n")


def extract(folder):
    import duckdb

    from avalanche_research import datasets

    records, paths = [], {}
    for dataset, (run, expected) in EXPECTED.items():
        selected = datasets.select_run(dataset, run=run)
        path = selected["parquet"]
        digest = sha256(path)
        if digest != expected:
            raise ValueError(f"Frozen source hash mismatch: {run}")
        receipt = datasets.receipt(dataset, run)
        records.append(
            {
                "dataset_id": dataset,
                "run": run,
                "sha256": digest,
                "bytes": path.stat().st_size,
                "capture_id": selected["capture_id"],
                "captured_at": selected["captured_at"],
                "coverage": receipt["build"].get("summary", {}),
            }
        )
        paths[dataset] = str(path)
    with duckdb.connect() as con:
        frame = con.execute(
            """SELECT transaction_hash, node_id, accepted_at,
            start_time, end_time, duration_days, stake_avax FROM read_parquet(?)
            WHERE role='validator' AND start_time>=? AND start_time<?
            ORDER BY start_time, transaction_hash""",
            [paths["derived.staking-periods"], START, END],
        ).df()
        first = con.execute(
            """SELECT transaction_hash, node_id, cycle_start, cycle_end,
            duration_days, stake_avax FROM read_parquet(?)
            WHERE cycle_number=1 AND cycle_start>=? AND cycle_start<?""",
            [paths["derived.helicon-commitments"], ACTIVATION, END],
        ).df()
    post = frame[frame.start_time >= ACTIVATION]
    check = post.merge(
        first,
        on="transaction_hash",
        how="outer",
        validate="one_to_one",
        suffixes=("_tx", "_cycle"),
        indicator=True,
    )
    if not check._merge.eq("both").all():
        raise ValueError("Post-Helicon transaction/first-cycle membership mismatch")
    if not check.node_id_tx.eq(check.node_id_cycle).all():
        raise ValueError("Post-Helicon node mismatch")
    for name in ("duration_days", "stake_avax"):
        if not np.allclose(
            check[name + "_tx"], check[name + "_cycle"], rtol=0, atol=1e-8
        ):
            raise ValueError(f"Post-Helicon {name} mismatch")
    if not (
        (check.start_time == check.cycle_start) & (check.end_time == check.cycle_end)
    ).all():
        raise ValueError("Post-Helicon cycle date mismatch")
    frame["cohort"] = np.where(
        frame.start_time < ACTIVATION, "Before Helicon", "After Helicon"
    )
    frame["avax_days"] = frame.stake_avax * frame.duration_days
    frame.to_csv(
        folder / "commitments.csv", index=False, date_format="%Y-%m-%dT%H:%M:%S"
    )
    provenance = {
        "inputs": records,
        "extract_sha256": sha256(folder / "commitments.csv"),
        "activation_utc": ACTIVATION.isoformat() + "Z",
        "start_utc": START.isoformat() + "Z",
        "end_exclusive_utc": END.isoformat() + "Z",
        "seconds_per_window": int((END - ACTIVATION).total_seconds()),
        "unit": "One new validator staking transaction, at its first cycle. Delegations and later automatic renewal cycles excluded.",
        "assignment": "Commitment start time, not transaction acceptance time. Half-open windows.",
        "reconciliation": {
            "post_transaction_count": len(post),
            "post_first_cycle_count": len(first),
            "membership_stake_duration_and_dates_match": True,
        },
        "interpretation": "Gross scheduled AVAX-days include future time and repeat capital across transactions. This is not realized exposure or a causal effect.",
    }
    (folder / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")


def read_and_summarise(folder):
    metadata = json.loads((folder / "provenance.json").read_text())
    if sha256(folder / "commitments.csv") != metadata["extract_sha256"]:
        raise ValueError("Extract hash mismatch")
    f = pd.read_csv(
        folder / "commitments.csv",
        parse_dates=["accepted_at", "start_time", "end_time"],
    )
    if f.transaction_hash.duplicated().any() or f.isna().any().any():
        raise ValueError("Duplicate transaction or missing value")
    if not f.start_time.between(START, END, inclusive="left").all():
        raise ValueError("Commitment outside equal windows")
    if not np.array_equal(f.cohort.eq("After Helicon"), f.start_time.ge(ACTIVATION)):
        raise ValueError("Cohort mismatch")
    if not ((f.stake_avax > 0) & (f.duration_days > 0)).all():
        raise ValueError("Nonpositive stake or duration")
    if not np.allclose(
        (f.end_time - f.start_time).dt.total_seconds() / 86400,
        f.duration_days,
        rtol=0,
        atol=1e-8,
    ):
        raise ValueError("Duration mismatch")
    if not np.allclose(f.avax_days, f.stake_avax * f.duration_days, rtol=1e-14):
        raise ValueError("AVAX-days mismatch")
    summary = {}
    for cohort in COLOURS:
        g = f[f.cohort.eq(cohort)]
        short = g[g.duration_days < 7]
        summary[cohort] = {
            "commitments": len(g),
            "nodes": int(g.node_id.nunique()),
            "gross_committed_avax": float(g.stake_avax.sum()),
            "scheduled_avax_days": float(g.avax_days.sum()),
            "median_duration_days": float(g.duration_days.median()),
            "stake_weighted_duration_days": float(
                g.avax_days.sum() / g.stake_avax.sum()
            ),
            "under_7d_commitments": len(short),
            "under_7d_count_share": len(short) / len(g),
            "under_7d_stake_share": float(short.stake_avax.sum() / g.stake_avax.sum()),
            "under_7d_avax_days_share": float(
                short.avax_days.sum() / g.avax_days.sum()
            ),
            "exact_coordinate_duplicates": int(
                g.duplicated(["duration_days", "stake_avax"]).sum()
            ),
        }
    (folder / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return f, summary


def static_plot(f, folder):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FixedLocator, FuncFormatter

    plt.rcParams.update(
        {"font.family": "DejaVu Sans", "font.size": 11, "svg.hashsalt": "helicon-f1"}
    )
    fig, ax = plt.subplots(figsize=(12, 7.5))
    fig.subplots_adjust(left=0.11, right=0.97, bottom=0.24, top=0.78)
    # Interleave cohorts deterministically so neither entire cohort sits on top.
    shown = f.sample(frac=1, random_state=42)
    maximum_weight = bubble_weight(f.stake_avax, f.duration_days).max()
    ax.scatter(
        shown.duration_days,
        shown.stake_avax,
        # Matplotlib s is squared diameter, so convert true circle area.
        s=4
        / np.pi
        * bubble_area(shown.stake_avax, shown.duration_days, maximum_weight),
        c=shown.cohort.map(COLOURS),
        alpha=0.42,
        linewidths=0.5,
        edgecolors="white",
    )
    ax.set(
        xscale="log",
        yscale="log",
        xlim=(1.8, 410),
        ylim=(1600, 7e6),
        xlabel="Commitment duration (days, log scale)",
        ylabel="Stake amount (AVAX, log scale)",
    )
    ax.xaxis.set_major_locator(FixedLocator([2, 7, 14, 30, 90, 180, 365]))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}"))
    ax.yaxis.set_major_locator(FixedLocator([2000, 10000, 100000, 1000000, 5000000]))
    ax.yaxis.set_major_formatter(
        FuncFormatter(lambda x, _: f"{x / 1e6:g}M" if x >= 1e6 else f"{x / 1e3:g}k")
    )
    ax.minorticks_off()
    ax.grid(color="#dce1e6", lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for cohort, colour in COLOURS.items():
        ax.scatter(
            [],
            [],
            s=65,
            color=colour,
            alpha=0.75,
            label=f"{cohort} · {sum(f.cohort.eq(cohort))} commitments",
        )
    ax.legend(loc="upper left", bbox_to_anchor=(0, 1.18), frameon=False, ncols=2)
    fig.text(
        0.06,
        0.94,
        "F1   Validator commitments before and after Helicon",
        fontsize=18,
        weight="bold",
        color="#202b39",
    )
    fig.text(
        0.06,
        0.892,
        "Equal windows of 34 days, 9 hours · activation: 22 September 2026, 15:00 UTC",
        fontsize=11,
        color="#566271",
    )
    for value, x in zip(SIZE_EXAMPLES, [0.145, 0.36, 0.575]):
        ax.scatter(
            [x],
            [-0.23],
            transform=ax.transAxes,
            clip_on=False,
            s=4 / np.pi * bubble_area(value, 1, maximum_weight),
            color="#75808e",
            alpha=0.65,
        )
        ax.text(
            x + 0.025,
            -0.23,
            f"10$^{{{int(np.log10(value))}}}$",
            transform=ax.transAxes,
            va="center",
            fontsize=10,
        )
    fig.text(0.06, 0.116, "AVAX-days", fontsize=10, color="#566271")
    fig.text(
        0.06,
        0.075,
        "Bubble area ∝ √(AVAX-days). One point per new validator transaction. Exact overlaps retained.",
        fontsize=10,
        color="#566271",
    )
    fig.text(
        0.06,
        0.045,
        "Starts: 19 Aug 06:00–22 Sep 15:00 and 22 Sep 15:00–27 Oct 00:00 UTC. Window ends excluded.",
        fontsize=9,
        color="#566271",
    )
    fig.text(
        0.06,
        0.015,
        "Source: P-Chain staking records, frozen 27 Oct 2026 runs. Later automatic renewal cycles and delegations excluded.",
        fontsize=9,
        color="#566271",
    )
    for suffix in ("png", "svg"):
        fig.savefig(
            folder / f"f1.{suffix}",
            dpi=180,
            metadata={"Date": None} if suffix == "svg" else None,
        )
    plt.close(fig)
    svg = folder / "f1.svg"
    svg.write_text(
        "\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n"
    )


def interactive_plot(f, folder):
    from bokeh.embed import file_html
    from bokeh.layouts import column
    from bokeh.models import (
        ColumnDataSource,
        Div,
        FixedTicker,
        HoverTool,
        NumeralTickFormatter,
    )
    from bokeh.plotting import figure
    from bokeh.resources import INLINE

    maximum_weight = bubble_weight(f.stake_avax, f.duration_days).max()
    plot = figure(
        title="F1 · Validator commitments before and after Helicon",
        height=590,
        sizing_mode="stretch_width",
        x_axis_type="log",
        y_axis_type="log",
        x_range=(1.8, 410),
        y_range=(1600, 7e6),
        tools="pan,wheel_zoom,box_zoom,reset,save",
        x_axis_label="Commitment duration (days, log scale)",
        y_axis_label="Stake amount (AVAX, log scale)",
    )
    for cohort, colour in COLOURS.items():
        g = f[f.cohort.eq(cohort)].copy()
        # Bokeh size is diameter in CSS px. Convert the same circle area to diameter.
        g["diameter"] = (
            2
            * np.sqrt(
                bubble_area(g.stake_avax, g.duration_days, maximum_weight) / np.pi
            )
            * 96
            / 72
        )
        g["start_label"] = g.start_time.dt.strftime("%d %b %Y %H:%M:%S UTC")
        g["overlapping_points"] = g.groupby(
            ["duration_days", "stake_avax"]
        ).transaction_hash.transform("size")
        renderer = plot.scatter(
            "duration_days",
            "stake_avax",
            source=ColumnDataSource(g),
            size="diameter",
            color=colour,
            fill_alpha=0.42,
            line_color=colour,
            line_alpha=0.65,
            legend_label=f"{cohort} ({len(g)})",
        )
        plot.add_tools(
            HoverTool(
                renderers=[renderer],
                tooltips=[
                    ("Cohort", "@cohort"),
                    ("Start", "@start_label"),
                    ("Duration", "@duration_days{0.0000} days"),
                    ("Stake", "@stake_avax{0,0.000} AVAX"),
                    ("AVAX-days", "@avax_days{0,0}"),
                    ("Node", "@node_id"),
                    ("Transaction", "@transaction_hash"),
                    ("Points here in cohort", "@overlapping_points"),
                ],
            )
        )
    plot.xaxis.ticker = FixedTicker(ticks=[2, 7, 14, 30, 90, 180, 365])
    plot.yaxis.ticker = FixedTicker(ticks=[2000, 10000, 100000, 1000000, 5000000])
    plot.yaxis.formatter = NumeralTickFormatter(format="0.[0]a")
    plot.legend.click_policy = "hide"
    plot.legend.location = "top_left"
    plot.grid.grid_line_alpha = 0.3
    intro = Div(
        text="<p>Equal windows of <b>34 days, 9 hours</b> around 22 September 2026, 15:00 UTC. "
        "Hover for records. Click a legend entry to hide its cohort. Drag or scroll to zoom.</p>"
    )
    legend = []
    for value in SIZE_EXAMPLES:
        diameter = 2 * np.sqrt(bubble_area(value, 1, maximum_weight) / np.pi) * 96 / 72
        legend.append(
            f'<span style="display:inline-flex;align-items:center;gap:9px;margin-right:32px">'
            f'<span style="display:inline-block;width:{diameter:.3f}px;height:{diameter:.3f}px;'
            'border-radius:50%;background:#75808e;opacity:.65"></span>'
            f"<span>10<sup>{int(np.log10(value))}</sup></span></span>"
        )
    size_legend = Div(
        text='<div style="display:flex;align-items:center;gap:18px;min-height:42px">'
        "<span>AVAX-days</span>" + "".join(legend) + "</div>"
    )
    note = Div(
        text="<p>One point per new validator transaction. Bubble area ∝ √(stake in AVAX × duration in days). "
        "The same size scale applies to both cohorts. Four times the AVAX-days gives twice the bubble area. "
        "Both axes use logarithmic scales. Exact overlaps are retained, without jitter.</p>"
        "<p>Before: 19 Aug 06:00–22 Sep 15:00 UTC. After: 22 Sep 15:00–27 Oct 00:00 UTC. "
        "Each interval includes its start and excludes its end. Delegations and later automatic renewal cycles are excluded. "
        "AVAX-days are scheduled commitments, including future days, rather than realized exposure. "
        "This descriptive comparison does not establish a causal effect.</p>"
    )
    html = file_html(
        column(intro, plot, size_legend, note, sizing_mode="stretch_width"),
        INLINE,
        "Helicon commitment comparison",
    )
    (folder / "interactive.html").write_text(
        "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Read and verify the two frozen data runs",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.extract:
        extract(args.output)
    frame, summary = read_and_summarise(args.output)
    write_size_metadata(args.output, frame)
    static_plot(frame, args.output)
    interactive_plot(frame, args.output)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
