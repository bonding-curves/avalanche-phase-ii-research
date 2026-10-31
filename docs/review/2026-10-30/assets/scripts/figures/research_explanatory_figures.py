#!/usr/bin/env python3
"""Draw four report figures from explicit inputs and frozen aggregate counts."""

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

INK = "#23354d"
MUTED = "#536176"
BLUE = "#3566a3"
TEAL = "#087f8c"
ORANGE = "#b85c00"
OUTPUTS = []


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(fig, assets, name):
    for extension in ("png", "svg"):
        path = assets / f"{name}.{extension}"
        kwargs = {"metadata": {"Date": None}} if extension == "svg" else {"dpi": 240}
        fig.savefig(path, facecolor="white", **kwargs)
        OUTPUTS.append({"file": path.name, "sha256": digest(path)})
    plt.close(fig)


def heading(fig, title, subtitle):
    fig.text(0.04, 0.95, title, fontsize=19, weight="bold", color=INK, va="top")
    fig.text(0.04, 0.875, subtitle, fontsize=12, color=MUTED, va="top")


def criteria(assets, inputs):
    fig = plt.figure(figsize=(10.6, 5.5))
    heading(
        fig,
        "From objectives to evaluation",
        "Decisions for Workshop 1 · Foundation priorities guide the criteria",
    )
    ax = fig.add_axes([0.04, 0.065, 0.92, 0.72])
    ax.set(xlim=(0, 10), ylim=(0, 4.12))
    ax.axis("off")
    for i, row in enumerate(inputs["criteria"]):
        y = 3.18 - i * 1.03
        ax.add_patch(
            FancyBboxPatch(
                (0.08, y),
                9.80,
                0.81,
                boxstyle="round,pad=0.04",
                linewidth=1.4,
                edgecolor=BLUE,
                facecolor="#f0f5fa",
            )
        )
        ax.text(
            0.30,
            y + 0.405,
            f"{i + 1}.",
            fontsize=17,
            weight="bold",
            color=BLUE,
            va="center",
        )
        ax.text(
            0.92,
            y + 0.405,
            row["title"],
            fontsize=14,
            weight="bold",
            color=INK,
            va="center",
        )
        ax.text(
            3.52,
            y + 0.405,
            row["body"],
            fontsize=12.5,
            color=INK,
            va="center",
            linespacing=1.45,
        )
        if i < 3:
            ax.add_patch(
                FancyArrowPatch(
                    (5, y - 0.025),
                    (5, y - 0.21),
                    arrowstyle="-|>",
                    mutation_scale=14,
                    linewidth=1.4,
                    color=MUTED,
                )
            )
    save(fig, assets, "evaluation-criteria")


def schedule(assets, inputs):
    fig = plt.figure(figsize=(11.4, 5.2))
    heading(
        fig,
        "Research review and delivery",
        "Repository shared · review and workshop dates proposed · later delivery targets",
    )
    ax = fig.add_axes([0.385, 0.16, 0.56, 0.61])
    labels = []
    for i, item in enumerate(inputs["schedule"]):
        y = 5 - i
        labels.append(item["label"])
        start = mdates.date2num(date.fromisoformat(item["start"]))
        end = mdates.date2num(date.fromisoformat(item.get("end", item["start"])))
        color = (
            ORANGE
            if item["kind"] == "workshop"
            else TEAL
            if item["kind"] == "work"
            else BLUE
        )
        if end > start:
            ax.barh(y, end - start, left=start, height=0.38, color=color, alpha=0.85)
            ax.annotate(
                item["dates"],
                ((start + end) / 2, y),
                xytext=(0, 13),
                textcoords="offset points",
                ha="center",
                fontsize=11,
                color=INK,
            )
        else:
            ax.scatter(
                start,
                y,
                s=65,
                color=color,
                marker="D" if item["kind"] == "workshop" else "o",
                zorder=3,
            )
            ax.annotate(
                item["dates"],
                (start, y),
                xytext=(9, 0),
                textcoords="offset points",
                va="center",
                fontsize=11,
                color=INK,
            )
    ax.set_yticks(range(5, -1, -1), labels=labels, fontsize=12)
    ax.set_xlim(date(2026, 10, 25), date(2027, 1, 29))
    ax.set_ylim(-0.65, 5.65)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.tick_params(axis="both", length=0, pad=10, labelcolor=MUTED)
    ax.grid(axis="x", color="#e0e6ed", zorder=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(
        0.04,
        0.04,
        "30 Oct sent. Review targets 2–6 Nov. Workshop proposed for 27 Nov. Later dates remain planning targets.",
        fontsize=11,
        color=MUTED,
    )
    save(fig, assets, "proposed-schedule")


def reward_duration(assets, inputs):
    config = inputs["reward_formula"]
    scarcity = (config["supply_cap_avax"] - config["supply_counter_avax"]) / config[
        "supply_counter_avax"
    ]
    fig = plt.figure(figsize=(10.6, 5.8))
    heading(
        fig,
        "How duration changes the reward",
        "Annualized reward at a fixed supply counter of 465 million AVAX",
    )
    ax = fig.add_axes([0.11, 0.18, 0.83, 0.60])
    rows = []
    for setting, color in zip(config["configurations"], [BLUE, ORANGE]):
        durations = np.linspace(setting["minimum_duration_days"], 365, 500)
        yields = (
            100
            * scarcity
            * (
                setting["minimum_consumption_rate"]
                + (
                    config["maximum_consumption_rate"]
                    - setting["minimum_consumption_rate"]
                )
                * durations
                / config["minting_period_days"]
            )
        )
        ax.plot(durations, yields, linewidth=2.8, color=color, label=setting["label"])
        for days in sorted(
            set([setting["minimum_duration_days"], 14, 30, 90, 180, 365])
        ):
            if days < setting["minimum_duration_days"]:
                continue
            consumption = (
                setting["minimum_consumption_rate"]
                + (
                    config["maximum_consumption_rate"]
                    - setting["minimum_consumption_rate"]
                )
                * days
                / config["minting_period_days"]
            )
            rows.append(
                {
                    "configuration": setting["label"],
                    "duration_days": days,
                    "consumption_rate": consumption,
                    "annualized_reward_percent_of_stake": 100 * scarcity * consumption,
                }
            )
        first = yields[0]
        ax.scatter(durations[0], first, color=color, s=35, zorder=4)
        ax.annotate(
            f"{setting['minimum_duration_days']} days: {first:.1f}%",
            (durations[0], first),
            xytext=(12, 15 if color == BLUE else -23),
            textcoords="offset points",
            color=color,
            fontsize=12,
        )
    endpoint = 100 * scarcity * config["maximum_consumption_rate"]
    ax.scatter(365, endpoint, s=42, color=INK, zorder=4)
    ax.annotate(
        f"365 days: {endpoint:.1f}%\nSame 12% maximum consumption rate",
        (365, endpoint),
        xytext=(-10, -52),
        textcoords="offset points",
        ha="right",
        color=INK,
        fontsize=11,
        arrowprops={"arrowstyle": "-", "color": MUTED},
    )
    ax.set(
        xlim=(0, 375),
        ylim=(0, 7.2),
        xlabel="Commitment duration (days)",
        ylabel="Annualized reward (% of stake)",
    )
    ax.set_xticks([2, 30, 90, 180, 270, 365])
    ax.grid(color="#e0e6ed", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="lower right", frameon=False, fontsize=11)
    fig.text(
        0.04,
        0.045,
        "Formula illustration before integer rounding. The 7.5% minimum is reached after ACP-285's 90-day ramp.",
        fontsize=11,
        color=MUTED,
    )
    with (assets / "reward-duration.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    save(fig, assets, "reward-duration")


def conditional_pass(assets, evidence):
    data = evidence["conditional_goal_regions"]
    windows = data["windows"]
    values, counts, rows = [], [], []
    for window in windows:
        value_row, count_row = [], []
        for band in window["half_point_bands"]:
            count = band["counts"]["goalpass__combined"]
            numerator, denominator = count["numerator"], count["denominator"]
            if denominator <= 0 or not 0 <= numerator <= denominator:
                raise ValueError("Invalid frozen count")
            fraction = numerator / denominator
            if not np.isclose(fraction, count["fraction"], rtol=0, atol=1e-12):
                raise ValueError("Frozen fraction differs from its integer counts")
            value_row.append(100 * fraction)
            count_row.append(f"{numerator}/{denominator}")
            rows.append(
                {
                    "response_window": window["window"],
                    "minimum_rate_low_percent": 100
                    * band["minimum_consumption_rate_low_inclusive"],
                    "minimum_rate_high_percent": 100
                    * band["minimum_consumption_rate_high_exclusive"],
                    "all_goal_passes": numerator,
                    "runs": denominator,
                    "pass_percent": 100 * fraction,
                }
            )
        values.append(value_row)
        counts.append(count_row)
    if np.shape(values) != (2, 10):
        raise ValueError("Expected two response windows and ten minimum-rate bands")
    fig = plt.figure(figsize=(12, 5.6))
    heading(
        fig,
        "Where all five working goals pass",
        "One-year ramp results · two response samples · four outside yields pooled",
    )
    ax = fig.add_axes([0.22, 0.37, 0.74, 0.39])
    image = ax.imshow(values, vmin=0, vmax=100, cmap="Blues", aspect="auto")
    ax.set_yticks(
        [0, 1],
        labels=[
            "Near central\nRenewal 0.01–0.04\nEntry 0.02–0.06",
            "Wider renewal\nRenewal 0.01–0.06\nEntry 0–0.1",
        ],
        fontsize=11,
    )
    bands = windows[0]["half_point_bands"]
    ax.set_xticks(
        range(10),
        labels=[
            f"{100 * b['minimum_consumption_rate_low_inclusive']:g}–\n{100 * b['minimum_consumption_rate_high_exclusive']:g}"
            for b in bands
        ],
        fontsize=11,
    )
    ax.tick_params(length=0, pad=10)
    ax.set_xlabel("Minimum consumption rate band (%)", fontsize=12, labelpad=12)
    for i in range(2):
        for j in range(10):
            ax.text(
                j,
                i,
                f"{values[i][j]:.1f}%\n{counts[i][j]}",
                ha="center",
                va="center",
                fontsize=11,
                linespacing=1.8,
                color="white" if values[i][j] >= 60 else INK,
            )
    ax.set_xticks(np.arange(-0.5, 10, 1), minor=True)
    ax.set_yticks([-0.5, 0.5, 1.5], minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    bar = fig.colorbar(
        image, cax=fig.add_axes([0.30, 0.16, 0.55, 0.025]), orientation="horizontal"
    )
    bar.set_label("Runs meeting every working threshold (%)", fontsize=11)
    bar.set_ticks([0, 25, 50, 75, 100])
    fig.text(
        0.04,
        0.045,
        "Each cell: pass share and passes/runs. Windows overlap. Shares are conditional on BCRG's working criteria.",
        fontsize=11,
        color=MUTED,
    )
    with (assets / "conditional-goal-pass.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    save(fig, assets, "conditional-goal-pass")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    assets = args.report / "assets"
    input_path = assets / "explanatory-figure-inputs.json"
    evidence_path = assets / "numerical-evidence.json"
    inputs = json.loads(input_path.read_text())
    if digest(evidence_path) != inputs["numerical_evidence_sha256"]:
        raise ValueError("Frozen numerical evidence hash mismatch")
    evidence = json.loads(evidence_path.read_text())
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 12,
            "text.color": INK,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "svg.fonttype": "none",
            "svg.hashsalt": "avalanche-explanatory-figures",
        }
    )
    criteria(assets, inputs)
    schedule(assets, inputs)
    reward_duration(assets, inputs)
    conditional_pass(assets, evidence)
    receipt = {
        "generator": "scripts/figures/research_explanatory_figures.py",
        "generator_sha256": digest(Path(__file__)),
        "inputs_file": input_path.name,
        "inputs_sha256": digest(input_path),
        "numerical_evidence_sha256": digest(evidence_path),
        "model": "v0.8.0",
        "conditional_results_source": evidence["conditional_goal_regions"][
            "source_result"
        ],
        "conditional_results_producing_code_commit": evidence[
            "conditional_goal_regions"
        ]["producing_code_commit"],
        "scope": "Frozen aggregate counts, analytical reward illustration and proposed evaluation/schedule diagrams. No simulation, fitting or rescoring.",
        "outputs": OUTPUTS
        + [
            {"file": name, "sha256": digest(assets / name)}
            for name in ["reward-duration.csv", "conditional-goal-pass.csv"]
        ],
    }
    (assets / "explanatory-figure-sources.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
