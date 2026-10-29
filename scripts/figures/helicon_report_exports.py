#!/usr/bin/env python3
"""Export the four Helicon panels as two matched pairs at 170 mm report width.

Run with the figure's input directory. Writes SVG, 300 dpi PNG and a two-page PDF
under report-exports/. Reads the delivered extract and its verified hash only.
"""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from helicon_commitment_comparison import COLOURS, bubble_weight
from helicon_density import density, marginals
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import ListedColormap, LogNorm
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FuncFormatter

MM = 1 / 25.4
PRINT_MAX_AREA = 60.0
CONTOUR_BANDS = 16
DISPLAY_MIN_DAYS = {"Before Helicon": 14.0, "After Helicon": 2.0}
PRINT_BANDWIDTH = (1.5, 0.12)


def draw(frame, grids, histograms, mode):
    fig = plt.figure(figsize=(170 * MM, 115 * MM))
    outer = fig.add_gridspec(
        1, 2, left=0.06, right=0.94, bottom=0.28, top=0.74, wspace=0.40
    )
    max_weight = bubble_weight(frame.stake_avax, frame.duration_days).max()
    max_density = max(np.max(grid[2]) for grid in grids)
    levels = np.r_[0, np.geomspace(max_density * 1e-5, max_density, CONTOUR_BANDS)]
    duration_max = max(max(h[0]["share"]) for h in histograms) * 1.1
    stake_max = max(max(h[1]["share"]) for h in histograms) * 1.1
    fig.text(
        0.04, 0.96, "Validator commitments around Helicon", fontsize=11, weight="bold"
    )
    fig.text(
        0.04,
        0.915,
        "Individual commitments"
        if mode == "scatter"
        else "Where scheduled AVAX-days concentrate",
        fontsize=9,
    )
    for column, ((cohort, colour), grid, hist) in enumerate(
        zip(COLOURS.items(), grids, histograms)
    ):
        g = frame[frame.cohort.eq(cohort)]
        x_header = 0.07 if column == 0 else 0.58
        fig.text(x_header, 0.865, cohort, color=colour, fontsize=10, weight="bold")
        fig.text(
            x_header,
            0.827,
            f"{g.stake_avax.sum() / 1e6:.2f}M AVAX · {g.avax_days.sum() / 1e9:.3f}B AVAX-days",
            fontsize=7.8,
        )
        fig.text(
            x_header,
            0.792,
            f"{len(g)} commitments · {g.node_id.nunique()} nodes · 34.375 days",
            fontsize=7.8,
        )
        sub = outer[column].subgridspec(
            2,
            2,
            width_ratios=[0.19, 0.81],
            height_ratios=[0.20, 0.80],
            hspace=0.12,
            wspace=0.10,
        )
        ax = fig.add_subplot(sub[1, 1])
        top = fig.add_subplot(sub[0, 1], sharex=ax)
        side = fig.add_subplot(sub[1, 0], sharey=ax)
        if mode == "scatter":
            area = (
                PRINT_MAX_AREA
                * bubble_weight(g.stake_avax, g.duration_days)
                / max_weight
            )
            ax.scatter(
                g.duration_days,
                g.stake_avax,
                s=4 / np.pi * area,
                color=colour,
                alpha=0.55,
                linewidths=0.2,
                edgecolors="white",
            )
        else:
            rgb = np.array([int(colour[i : i + 2], 16) for i in (1, 3, 5)])
            palette = [
                tuple((255 + (rgb - 255) * t) / 255)
                for t in np.linspace(0.04, 1, CONTOUR_BANDS)
            ]
            positive = grid[0] >= DISPLAY_MIN_DAYS[cohort]
            ax.contourf(
                grid[0][positive],
                grid[1],
                grid[2][:, positive],
                levels=levels,
                colors=palette,
            )
            ax.axvline(
                DISPLAY_MIN_DAYS[cohort], color=colour, linewidth=0.6, linestyle=":"
            )
            if cohort == "Before Helicon":
                ax.text(
                    5.0,
                    2e5,
                    "None below\n14 days",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color=colour,
                )
            cax = fig.add_axes([0.08 if column == 0 else 0.59, 0.13, 0.30, 0.014])
            bar = fig.colorbar(
                matplotlib.cm.ScalarMappable(
                    norm=LogNorm(levels[1], max_density), cmap=ListedColormap(palette)
                ),
                cax=cax,
                orientation="horizontal",
            )
            bar.set_ticks(
                [levels[1], max_density],
                labels=[f"{levels[1]:.2g}", f"{max_density:.2f}"],
            )
            bar.ax.tick_params(labelsize=7, length=2)
            bar.ax.minorticks_off()
        hd, hs = hist
        take = hd["count"] > 0
        top.bar(
            hd["lo"][take],
            hd["share"][take],
            width=(hd["hi"] - hd["lo"])[take],
            align="edge",
            color=colour,
            alpha=0.65,
            edgecolor=colour,
            linewidth=0.45,
        )
        take = hs["count"] > 0
        side.barh(
            hs["lo"][take],
            hs["share"][take],
            height=(hs["hi"] - hs["lo"])[take],
            align="edge",
            color=colour,
            alpha=0.65,
            edgecolor=colour,
            linewidth=0.45,
        )
        ax.set(
            xlim=(1.8, 410),
            ylim=(1600, 7e6),
            xscale="log",
            yscale="log",
            xlabel="Duration (days, log)",
        )
        ax.yaxis.tick_right()
        ax.xaxis.set_major_locator(FixedLocator([2, 7, 14, 30, 90, 180, 365]))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}"))
        ax.yaxis.set_major_locator(
            FixedLocator([2000, 10000, 100000, 1000000, 5000000])
        )
        ax.yaxis.set_major_formatter(
            FuncFormatter(lambda x, _: f"{x / 1e6:g}M" if x >= 1e6 else f"{x / 1e3:g}k")
        )
        side.set(xlim=(stake_max, 0), ylabel="Stake (AVAX, log)", xlabel="%")
        top.set_ylim(0, duration_max)
        top.set_title("AVAX-days by duration (%)", fontsize=7.5, loc="left", pad=3)
        top.set_yticks([0, 20])
        side.set_xticks([0, 30])
        side.tick_params(axis="y", which="both", left=False, labelleft=False)
        top.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
        for axis in [ax, top, side]:
            axis.minorticks_off()
            axis.tick_params(labelsize=7.5, length=2, width=0.4, pad=2)
            axis.grid(color="#e1e5e9", linewidth=0.3)
            axis.set_axisbelow(True)
            for spine in axis.spines.values():
                spine.set_linewidth(0.4)
                spine.set_color("#a0a8b0")
        ax.xaxis.label.set_size(8)
        side.xaxis.label.set_size(7.5)
        side.yaxis.label.set_size(8)
    if mode == "scatter":
        handles = []
        for value in [1e4, 1e6, 1e8]:
            area = PRINT_MAX_AREA * np.sqrt(value) / max_weight
            handles.append(
                Line2D(
                    [],
                    [],
                    linestyle="",
                    marker="o",
                    markersize=np.sqrt(4 / np.pi * area),
                    color="#75808e",
                    label=f"10$^{{{int(np.log10(value))}}}$",
                )
            )
        fig.legend(
            handles=handles,
            title="AVAX-days · bubble area ∝ √(AVAX-days)",
            title_fontsize=8,
            fontsize=8,
            loc="lower left",
            bbox_to_anchor=(0.04, 0.085),
            frameon=False,
            ncols=3,
            handletextpad=0.5,
        )
    else:
        fig.text(
            0.04,
            0.18,
            "AVAX-day weighted density · 16 bands · smoothing: 1.5 days / 0.12 stake dex",
            fontsize=7.5,
        )
        fig.text(
            0.04,
            0.065,
            "Density: % of era AVAX-days per day × log₁₀-AVAX. Tails below 14 days before / 2 days after hidden.",
            fontsize=7,
        )
    fig.text(
        0.04,
        0.043,
        "Equal 34-day, 9-hour windows around 22 Sep 2026, 15:00 UTC, through 26 Oct.",
        fontsize=7,
    )
    fig.text(
        0.04,
        0.019,
        "Source: frozen 27 Oct P-Chain records. New validator transactions; later renewal cycles excluded.",
        fontsize=6.8,
    )
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    metadata = json.loads((args.input / "provenance.json").read_text())
    body = (args.input / "commitments.csv").read_bytes()
    if hashlib.sha256(body).hexdigest() != metadata["extract_sha256"]:
        raise ValueError("Extract hash mismatch")
    frame = pd.read_csv(args.input / "commitments.csv")
    groups = [frame[frame.cohort.eq(c)] for c in COLOURS]
    grids = [density(g, bandwidth=PRINT_BANDWIDTH) for g in groups]
    histograms = [marginals(g) for g in groups]
    out = args.input / "report-exports"
    out.mkdir(exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "svg.fonttype": "none",
            "svg.hashsalt": "helicon-report",
            "pdf.fonttype": 42,
        }
    )
    with PdfPages(
        out / "helicon-report-figures.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    ) as pdf:
        for mode in ["scatter", "kde"]:
            fig = draw(frame, grids, histograms, mode)
            fig.savefig(out / f"helicon-{mode}.png", dpi=300)
            fig.savefig(out / f"helicon-{mode}.svg", metadata={"Date": None})
            pdf.savefig(fig)
            plt.close(fig)
    for path in out.glob("*.svg"):
        path.write_text(
            "\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n"
        )
    (out / "export-spec.json").write_text(
        json.dumps(
            {
                "source_extract_sha256": metadata["extract_sha256"],
                "width_mm": 170,
                "height_mm": 115,
                "png_dpi": 300,
                "duration_scale": "log",
                "panels": "Before/after scatter pair and before/after KDE pair",
                "density": {
                    **{
                        key: metadata["density"][key]
                        for key in [
                            "weights",
                            "coordinates",
                            "normalization",
                            "boundary",
                            "duration_bin_edges_days",
                            "stake_bin_edges_avax",
                        ]
                    },
                    "bandwidth": {
                        "days": PRINT_BANDWIDTH[0],
                        "log10_avax": PRINT_BANDWIDTH[1],
                    },
                    "grid_integrals_percent": [grid[3] for grid in grids],
                    "display_domain": {
                        "duration_days": [1.8, 410],
                        "stake_avax": [1600, 7000000],
                    },
                    "contour_levels": np.r_[
                        0,
                        np.geomspace(
                            max(np.max(grid[2]) for grid in grids) * 1e-5,
                            max(np.max(grid[2]) for grid in grids),
                            CONTOUR_BANDS,
                        ),
                    ].tolist(),
                    "contour_spacing": "16 bands from zero plus log-spaced positive levels spanning 1e-5 of common maximum to maximum",
                    "display_min_duration_days": DISPLAY_MIN_DAYS,
                    "display_note": "Log positioning; density per linear day and log10 AVAX. Smoothing below 14 days before Helicon and 2 days after is hidden, not redistributed. The full unmasked KDE integrates to 100% per era.",
                    "marginal_visibility": "Nonempty bins outlined at 0.45 points; exact heights unchanged; empty bins omitted",
                    "era_colours": COLOURS,
                    "colour_interpolation": "16 common bands, white blended with era colour at fractions 0.04 to 1",
                },
                "print_max_bubble_area_pt2": PRINT_MAX_AREA,
            },
            indent=2,
        )
        + "\n"
    )
    print(out)


if __name__ == "__main__":
    main()
