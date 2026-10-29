#!/usr/bin/env python3
"""Draw the report's goal matrix from its included frozen aggregate CSV."""

import argparse
import hashlib
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    assets = args.report / "assets"
    source = assets / "goal-utilities.csv"
    receipt = json.loads((assets / "figure-sources.json").read_text())
    if (
        hashlib.sha256(source.read_bytes()).hexdigest()
        != receipt["goal_utilities"]["sha256"]
    ):
        raise ValueError("Goal utility extract hash mismatch")
    frame = pd.read_csv(source)
    families = {"before": 0, "ramp": 1, "quadratic": 2, "tenure": 3}
    frame["family_order"] = frame.family.map(families)
    frame["setting_order"] = frame.cell.map(
        lambda label: (
            float(re.search(r"\d+(?:\.\d+)?", label)[0])
            if re.search(r"\d+(?:\.\d+)?", label)
            else 0
        )
    )
    frame = frame.sort_values(["family_order", "setting_order"])
    prefixes = {
        "before": "Pre-ACP-285 rule",
        "ramp": "Ramp minimum consumption rate",
        "quadratic": "Duration exponent",
        "tenure": "Full-tenure boost",
    }
    labels = []
    for row in frame.itertuples():
        setting = re.sub(
            r"^(floor of the reward rate|duration exponent|full-tenure boost)\s*",
            "",
            row.cell,
        )
        labels.append(
            prefixes[row.family]
            if row.family == "before"
            else f"{prefixes[row.family]} {setting}"
        )
    values = frame[
        [*[f"utility_G{i}" for i in range(1, 6)], "utility_combined"]
    ].to_numpy()
    if not np.isfinite(values).all() or not ((values >= 0) & (values <= 1)).all():
        raise ValueError("Utilities must be finite and between zero and one")
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "svg.fonttype": "none",
            "svg.hashsalt": "reward-goals",
        }
    )
    fig, ax = plt.subplots(figsize=(12.5, 13.8))
    fig.subplots_adjust(left=0.43, right=0.91, bottom=0.09, top=0.88)
    image = ax.imshow(values, vmin=0, vmax=1, cmap="Blues", aspect="auto")
    ax.set_xticks(
        range(6),
        labels=[
            "G1\nStake",
            "G2\nValidators",
            "G3\nIssuance",
            "G4\nStake per\nAVAX issued",
            "G5\nDuration",
            "Combined",
        ],
    )
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(frame)), labels=labels)
    ax.tick_params(axis="both", length=0, labelsize=11, pad=9)
    for i, row in enumerate(values):
        for j, value in enumerate(row):
            ax.text(
                j,
                i,
                f"{value:.2f}",
                ha="center",
                va="center",
                fontsize=12,
                color="white" if value > 0.58 else "#233248",
            )
        ax.text(
            5.72,
            i,
            f"{int(frame.iloc[i].runs):,}",
            va="center",
            fontsize=10,
            color="#536176",
            clip_on=False,
        )
    ax.text(5.72, -1.05, "Runs", ha="left", fontsize=11, color="#536176", clip_on=False)
    changes = (
        np.flatnonzero(frame.family.to_numpy()[1:] != frame.family.to_numpy()[:-1])
        + 0.5
    )
    for boundary in changes:
        ax.axhline(boundary, color="white", linewidth=3)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(
        0.04,
        0.97,
        "Reward mechanisms across five working goals",
        fontsize=18,
        weight="bold",
    )
    fig.text(
        0.04,
        0.935,
        "One year · 16,384 design runs · mean utility by setting · BCRG working preferences",
        fontsize=12,
        color="#536176",
    )
    bar = fig.colorbar(
        image, cax=fig.add_axes([0.44, 0.045, 0.40, 0.012]), orientation="horizontal"
    )
    bar.set_ticks([0, 0.5, 1], labels=["0", "0.5", "1"])
    bar.ax.tick_params(labelsize=10)
    bar.set_label("Utility score, not a probability", fontsize=11)
    fig.savefig(assets / "goal-utilities.png", dpi=160)
    fig.savefig(assets / "goal-utilities.svg", metadata={"Date": None})
    plt.close(fig)


if __name__ == "__main__":
    main()
