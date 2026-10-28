"""Utility heat maps: each goal's mean utility and the combined utility over cells of a design's settings.

Three kinds of map are drawn for each horizon.

1. A sorted map of setting cells by goal. Each row is one cell of one design's settings, pooled over scenarios, and the
   rows are sorted by the combined utility, best first. A design with no setting to choose is one row.
2. For each setting of each design, the setting's bins against each scenario value, one panel per goal and one for
   the combined utility.
3. For each pair of a design's settings, one setting's bins against the other's, pooled over scenarios.

Cells with fewer runs than the specification's `min_runs_per_cell` are left blank.
"""

from __future__ import annotations

import itertools
import textwrap

import numpy as np
import pandas as pd

from . import style
from .psuu import bin_index, bins_for, cell_bins, settings_of, targets
from .style import (INK, PAPER, SEQUENTIAL, family_label, feature_label, feature_value, fmt_horizon, headline, save,
                    scenario_text)

import matplotlib.pyplot as plt  # noqa: E402

PAIR_BINS = 6
SCENARIO_BINS = 10


def column_names(spec):
    return [g["id"] for g in spec["goals"]] + ["Combined"]


def goal_titles(spec):
    return {**{f"goal__{g['id']}": f"{g['id']} {g['name']}" for g in spec["goals"]}, "goal__combined": "Combined"}


def bin_labels(frame, p, n_bins, ranges):
    """Each run's bin of setting p as (index, low, high), with the bin edges."""
    edges, _ = bins_for(frame[p], n_bins, ranges)
    if edges is None:
        values = np.sort(frame[p].dropna().unique())
        index = pd.Series(np.searchsorted(values, frame[p].to_numpy()), index=frame.index)
        return index, list(zip(values, values))
    index = pd.Series(bin_index(frame[p].to_numpy(), edges), index=frame.index)
    return index, list(zip(edges[:-1], edges[1:]))


def span_text(p, lo, hi):
    if isinstance(lo, str) or lo == hi:
        return feature_value(p, lo)
    return f"{feature_value(p, lo)} to {feature_value(p, hi)}"


def sorted_cells(runs, spec, layout, ranges, horizon):
    """One row per setting cell of each design at one horizon, pooled over scenarios, best combined utility first."""
    fam_col, tl = layout["family"], targets(spec)
    min_runs = spec["regions"]["min_runs_per_cell"]
    data = runs[runs[layout["horizon"]] == horizon]
    rows = []
    for fam, frame in data.groupby(fam_col, sort=True):
        params = settings_of(frame, layout)
        if not params:
            rows.append({"family": fam, "cell": "fixed design", "runs": len(frame),
                         **{t: frame[t].mean() for t in tl}})
            continue
        n_bins = cell_bins(len(params))
        keys, spans = [], {}
        for p in params:
            idx, spans[p] = bin_labels(frame, p, n_bins, ranges)
            keys.append(idx.rename(p))
        for cell, sub in frame.groupby(keys, sort=True):
            cell = cell if isinstance(cell, tuple) else (cell,)
            if len(sub) < min_runs:
                continue
            text = ", ".join(f"{feature_label(p, False).lower()} {span_text(p, *spans[p][k])}"
                             for p, k in zip(params, cell))
            rows.append({"family": fam, "cell": text, "runs": len(sub), **{t: sub[t].mean() for t in tl}})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("goal__combined", ascending=False, kind="stable").reset_index(drop=True)


def draw_matrix(ax, M, row_labels, col_labels, fontsize=6.8, annotate=True):
    ax.imshow(np.ma.masked_invalid(M), cmap=SEQUENTIAL, vmin=0, vmax=1, aspect="auto")
    if annotate:
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                if np.isfinite(M[i, j]):
                    ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=fontsize,
                            color=PAPER if M[i, j] > 0.55 else INK)
    ax.set_xticks(range(len(col_labels)), col_labels)
    ax.set_yticks(range(len(row_labels)), row_labels)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)


def figure_sorted(runs, spec, layout, ranges, horizon, folder):
    table = sorted_cells(runs, spec, layout, ranges, horizon)
    if table.empty:
        return None
    tl = targets(spec)
    M = table[tl].to_numpy(dtype=float)
    labels = [f"{family_label(f)}: {c}" for f, c in zip(table.family, table.cell)]
    fig, ax = plt.subplots(figsize=(0.75 * len(tl) + 3.6, 0.24 * len(table) + 1.1), constrained_layout=True)
    draw_matrix(ax, M, labels, column_names(spec), fontsize=6.5)
    ax.xaxis.tick_top()
    ax.set_yticklabels(labels, fontsize=6.8)
    ax.axvline(len(tl) - 1.5, color=PAPER, lw=3)
    best, worst = table.iloc[0], table.iloc[-1]
    title = (f"{family_label(best.family)} with {best.cell} has the highest combined utility, "
             f"{best.goal__combined:.2f}, against {worst.goal__combined:.2f} for the lowest cell")
    goals = ", ".join(f"{g['id']} {g['name']}" for g in spec["goals"])
    sub = (f"Mean utility of runs in each setting cell, 0 to 1, pooled over scenarios, sorted by the combined utility. "
           f"{fmt_horizon(horizon)}. Cells with fewer than {spec['regions']['min_runs_per_cell']} runs are left out."
           f"\nGoals: {goals}.")
    headline(fig, title, sub)
    data = table.rename(columns={t: t.replace("goal__", "utility_") for t in tl})
    save(fig, folder, f"heatmap-sorted-{horizon}", data)
    return title


def grid_means(frame, rows, cols, tl, min_runs):
    """Mean of each target in each (row key, column key) cell, NaN where a cell has too few runs."""
    out = {}
    for t in tl:
        g = frame.groupby([rows, cols])[t]
        mean, n = g.mean(), g.size()
        out[t] = mean.where(n >= min_runs)
    count = frame.groupby([rows, cols]).size()
    return out, count


def panels(fig_cols, n):
    return int(np.ceil(n / fig_cols))


def figure_setting_scenario(runs, spec, layout, ranges, horizon, fam, p, folder):
    """One setting of one design against every scenario value, one panel per goal and one for the combined utility."""
    axes_names = layout["scenarios"]
    if not axes_names:
        return None
    fam_col, tl = layout["family"], targets(spec)
    frame = runs[(runs[layout["horizon"]] == horizon) & (runs[fam_col] == fam)]
    min_runs = spec["regions"]["min_runs_per_cell"]
    xidx, spans = bin_labels(frame, p, SCENARIO_BINS, ranges)
    scen = frame[axes_names].apply(lambda r: " & ".join(scenario_text(a, r[a]) for a in axes_names), axis=1)
    order = frame[axes_names].drop_duplicates().sort_values(axes_names)
    scen_labels = [" & ".join(scenario_text(a, r[a]) for a in axes_names) for _, r in order.iterrows()]
    yidx = scen.map({s: k for k, s in enumerate(scen_labels)})
    means, count = grid_means(frame, yidx.rename("scenario"), xidx.rename("setting"), tl, min_runs)
    nx, ny = len(spans), len(scen_labels)
    ncols = 3
    nrows = panels(ncols, len(tl))
    fig, axs = plt.subplots(nrows, ncols, figsize=(ncols * (0.42 * nx + 1.2) + 1.0, nrows * (0.3 * ny + 1.25)),
                            squeeze=False, constrained_layout=True)
    titles = goal_titles(spec)
    rows = [{"scenario": scen_labels[yi], "setting_lo": spans[xi][0], "setting_hi": spans[xi][1], "runs": int(n),
             **{t.replace("goal__", "utility_"): means[t].get((yi, xi), np.nan) for t in tl}}
            for (yi, xi), n in count.items()]
    for k, t in enumerate(tl):
        ax = axs[k // ncols, k % ncols]
        M = np.full((ny, nx), np.nan)
        for (yi, xi), v in means[t].items():
            M[yi, xi] = v
        draw_matrix(ax, M, scen_labels if k % ncols == 0 else [""] * ny,
                    [span_text(p, *spans[i]).split(" to ")[0] for i in range(nx)], fontsize=5.8, annotate=nx <= 12)
        ax.set_title(textwrap.fill(titles[t], 30), fontsize=8)
        short = max(len(span_text(p, *spans[i]).split(" to ")[0]) for i in range(nx)) <= 5
        ax.tick_params(axis="x", labelrotation=0 if short else 90, labelsize=6.5)
        if k // ncols == nrows - 1 or k + ncols >= len(tl):
            ax.set_xlabel(f"{feature_label(p)}, bin start", fontsize=7.5)
    for k in range(len(tl), nrows * ncols):
        axs[k // ncols, k % ncols].axis("off")
    data = pd.DataFrame(rows)
    comb = data.dropna(subset=["utility_combined"])
    if comb.empty:
        return None
    best = comb.loc[comb.utility_combined.idxmax()]
    title = (f"{family_label(fam)}: the combined utility peaks at {best.utility_combined:.2f} with "
             f"{feature_label(p, False).lower()} {span_text(p, best.setting_lo, best.setting_hi)} "
             f"at {best.scenario.lower()}")
    sub = (f"Mean utility of runs in each cell, 0 to 1, darker is better. Columns: {feature_label(p, False).lower()} "
           f"in {nx} bins. Rows: scenario. Blank: fewer than {min_runs} runs. {fmt_horizon(horizon)}.")
    headline(fig, title, sub)
    save(fig, folder, f"heatmap-scenario-{fam}-{p}-{horizon}", data)
    return title


def figure_pair(runs, spec, layout, ranges, horizon, fam, p, q, folder):
    """Two settings of one design against each other, pooled over scenarios."""
    fam_col, tl = layout["family"], targets(spec)
    frame = runs[(runs[layout["horizon"]] == horizon) & (runs[fam_col] == fam)]
    min_runs = spec["regions"]["min_runs_per_cell"]
    xidx, xs = bin_labels(frame, p, PAIR_BINS, ranges)
    yidx, ys = bin_labels(frame, q, PAIR_BINS, ranges)
    means, count = grid_means(frame, yidx.rename("y"), xidx.rename("x"), tl, min_runs)
    ncols = 3
    nrows = panels(ncols, len(tl))
    fig, axs = plt.subplots(nrows, ncols, figsize=(ncols * (0.45 * len(xs) + 1.3) + 1.0,
                                                   nrows * (0.4 * len(ys) + 1.2)),
                            squeeze=False, constrained_layout=True)
    titles, rows = goal_titles(spec), []
    for (yi, xi), n in count.items():
        rows.append({f"{p}_lo": xs[xi][0], f"{p}_hi": xs[xi][1], f"{q}_lo": ys[yi][0], f"{q}_hi": ys[yi][1],
                     "runs": int(n), **{t.replace("goal__", "utility_"): means[t].get((yi, xi), np.nan) for t in tl}})
    for k, t in enumerate(tl):
        ax = axs[k // ncols, k % ncols]
        M = np.full((len(ys), len(xs)), np.nan)
        for (yi, xi), v in means[t].items():
            M[yi, xi] = v
        draw_matrix(ax, M[::-1], [span_text(q, *ys[i]) for i in range(len(ys))][::-1] if k % ncols == 0
                    else [""] * len(ys), [span_text(p, *xs[i]) for i in range(len(xs))], fontsize=6)
        ax.set_title(textwrap.fill(titles[t], 30), fontsize=8)
        ax.tick_params(axis="x", labelrotation=90, labelsize=6.5)
        if k % ncols == 0:
            ax.set_ylabel(feature_label(q), fontsize=7.5)
        ax.set_xlabel(feature_label(p), fontsize=7.5)
    for k in range(len(tl), nrows * ncols):
        axs[k // ncols, k % ncols].axis("off")
    data = pd.DataFrame(rows)
    comb = data.dropna(subset=["utility_combined"])
    if comb.empty:
        return None
    best = comb.loc[comb.utility_combined.idxmax()]
    title = (f"{family_label(fam)}: the combined utility peaks at {best.utility_combined:.2f} with "
             f"{feature_label(p, False).lower()} {span_text(p, best[f'{p}_lo'], best[f'{p}_hi'])} and "
             f"{feature_label(q, False).lower()} {span_text(q, best[f'{q}_lo'], best[f'{q}_hi'])}")
    sub = (f"Mean utility of runs in each cell, 0 to 1, darker is better, pooled over scenarios. Blank: fewer than "
           f"{min_runs} runs. {fmt_horizon(horizon)}.")
    headline(fig, title, sub)
    save(fig, folder, f"heatmap-pair-{fam}-{p}-{q}-{horizon}", data)
    return title


def draw_all(scored, folder, log=print):
    """Every heat map of a scored sweep. Returns {figure name: title}."""
    runs, spec, layout, ranges = scored.runs, scored.spec, scored.layout, scored.ranges
    style.apply()
    titles = {}
    for h in sorted(runs[layout["horizon"]].unique()):
        titles[f"heatmap-sorted-{h}"] = figure_sorted(runs, spec, layout, ranges, h, folder)
        for fam, frame in runs[runs[layout["horizon"]] == h].groupby(layout["family"], sort=True):
            params = settings_of(frame, layout)
            for p in params:
                titles[f"heatmap-scenario-{fam}-{p}-{h}"] = figure_setting_scenario(
                    runs, spec, layout, ranges, h, fam, p, folder)
            for p, q in itertools.combinations(params, 2):
                titles[f"heatmap-pair-{fam}-{p}-{q}-{h}"] = figure_pair(runs, spec, layout, ranges, h, fam, p, q,
                                                                         folder)
    titles = {k: v for k, v in titles.items() if v}
    log(f"  heat maps: {len(titles)} figures")
    return titles

