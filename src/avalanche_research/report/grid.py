"""A grid of each input against each KPI, one figure per design and horizon.

Rows are the KPIs of the utility specification, each the measured value its goal reads, such as stake retained
against the chain's rule. Columns are the design's settings, then the validator responses and the scenario axes. Each
panel shows a seeded sample of runs as points, the mean of all runs in equal bins of the input as a line, the 10th to
90th percentile of runs in each bin as a band, and the KPI's pass line dashed.
"""

from __future__ import annotations

import textwrap

import numpy as np
import pandas as pd

from . import style
from .psuu import binned, metrics_of, settings_of
from .style import (GRID, INK2, MODEL_BLUE, MUTED, REWARD, family_label, feature_label, feature_scale, fmt_horizon,
                    headline, save)

import matplotlib.pyplot as plt  # noqa: E402

SAMPLE = 600
BINS = 12
MIN_BIN_RUNS = 10  # a bin with fewer runs, or under 1% of the design's runs, draws no mean


def grid_inputs(frame, layout):
    params = settings_of(frame, layout)
    others = [c for c in layout["behaviour"] + layout["scenarios"] if frame[c].notna().all() and frame[c].nunique() > 1]
    return params, others


def rank_correlation(x, y):
    rx, ry = pd.Series(x).rank().to_numpy(), pd.Series(y).rank().to_numpy()
    if rx.std() == 0 or ry.std() == 0:
        return np.nan
    return float(np.corrcoef(rx, ry)[0, 1])


def figure_grid(runs, spec, layout, ranges, horizon, fam, folder, sample=SAMPLE, seed=20261027):
    frame = runs[(runs[layout["horizon"]] == horizon) & (runs[layout["family"]] == fam)]
    params, others = grid_inputs(frame, layout)
    inputs = params + others
    if not inputs:
        return None
    kpis = metrics_of(spec)
    points = frame.sample(n=min(sample, len(frame)), random_state=seed)
    min_n = max(MIN_BIN_RUNS, int(0.01 * len(frame)))
    fig, axes = plt.subplots(len(kpis), len(inputs), figsize=(2.05 * len(inputs) + 1.3, 1.32 * len(kpis) + 0.8),
                             squeeze=False, sharex="col", sharey="row", constrained_layout=True)
    bins, strongest = [], None
    for r, (g, m) in enumerate(kpis):
        col = f"metric__{m['id']}"
        thr = m["threshold"]
        for c, name in enumerate(inputs):
            ax = axes[r, c]
            scale = feature_scale(name)
            x = points[name].astype(float) * scale if points[name].dtype != object else points[name]
            ax.scatter(x, points[col], s=2.5, color=MUTED, alpha=0.35, lw=0, rasterized=True)
            b = binned(frame, name, col, ranges, BINS)
            b = b[b.n >= min_n]
            ax.fill_between(b.x * scale, b.run_p10, b.run_p90, color=MODEL_BLUE, alpha=0.16, lw=0)
            ax.plot(b.x * scale, b.run_mean, color=MODEL_BLUE, lw=1.5)
            for v in (thr["value"] if thr["op"] == "between" else [thr["value"]]):
                ax.axhline(v, color=REWARD, lw=0.8, ls=(0, (3, 2)))
            ax.grid(axis="y", color=GRID, lw=0.5)
            ax.set_axisbelow(True)
            if c == 0:
                ax.set_ylabel(textwrap.fill(m.get("label", m["id"]), 24), fontsize=6.6)
            if r == len(kpis) - 1:
                ax.set_xlabel(textwrap.fill(feature_label(name), 26), fontsize=7)
            if r == 0:
                ax.set_title("Setting" if name in params else "Scenario" if name in layout["scenarios"]
                             else "Validator response", fontsize=7.5, color=INK2)
            rho = rank_correlation(frame[name], frame[col])
            for row in b.to_dict("records"):
                bins.append({"kpi": m["id"], "input": name, **row, "rank_correlation": rho})
            if name in params and np.isfinite(rho) and (strongest is None or abs(rho) > abs(strongest[0])):
                strongest = (rho, name, m.get("label", m["id"]))
    if strongest:
        rho, name, label = strongest
        way = "rises" if rho > 0 else "falls"
        title = (f"{family_label(fam)}: {label[0].lower()}{label[1:]} {way} most with a higher "
                 f"{feature_label(name, False).lower()}, rank correlation {rho:.2f}")
    else:
        title = f"{family_label(fam)}: the validators' response and the scenario move the KPIs, with no setting to choose"
    sub = (f"Grey points: a seeded sample of {len(points):,} of {len(frame):,} runs. Blue line: mean of all runs in "
           f"{BINS} equal bins of the input, band 10th to 90th percentile, bins of under {min_n} runs left out. "
           f"Red dashed: the KPI's pass line. {fmt_horizon(horizon)}.")
    headline(fig, title, sub)
    save(fig, folder, f"grid-{fam}-{horizon}", pd.DataFrame(bins))
    return title


def draw_all(scored, folder, sample=SAMPLE, seed=20261027, log=print):
    runs, spec, layout, ranges = scored.runs, scored.spec, scored.layout, scored.ranges
    style.apply()
    titles = {}
    for h in sorted(runs[layout["horizon"]].unique()):
        for fam in sorted(runs[layout["family"]].unique()):
            titles[f"grid-{fam}-{h}"] = figure_grid(runs, spec, layout, ranges, h, fam, folder, sample, seed)
    titles = {k: v for k, v in titles.items() if v}
    log(f"  parameter grids: {len(titles)} figures")
    return titles
