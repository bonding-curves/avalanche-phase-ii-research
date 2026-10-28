"""Recommendation tables and the sign-and-confidence matrix, computed from the scored sweep.

Recommendation tables. For each horizon, design and scenario, and pooled over scenarios, the settings are split into
the same cells as the regions of `psuu.regions`, and three recommendations are read from the cells that hold at least
`min_runs_per_cell` runs:

1. the point estimate, the cell with the highest mean combined utility. Its confidence is the share of resamples of
   the runs, drawn by the group of shared draws, in which the same cell stays best: high at 80% or more, medium at 50%
   or more, low below;
2. a range per goal, the cells where at least `pass_share` of runs pass that goal;
3. the global range, the cells where at least `pass_share` of runs pass every goal.

A range's confidence is high when the 95% Wilson lower bound of every one of its cells' pass rates is at or above
`pass_share`, medium when the range holds cells but some lower bound falls below it, and none when no cell qualifies.
With two or more settings, a range is given as each setting's span over the qualifying cells, which can be wider than
the set of cells itself.

Sign-and-confidence matrix. For each horizon and design, the rank correlation of every input (setting, validator
response, scenario) with every KPI and every goal utility, with a 95% interval from the same resamples. The sign is
shown when the interval excludes zero: ++ or -- when the correlation is at least 0.3 in size, + or - from 0.1, and (+)
or (-) below 0.1. A 0 means the interval includes zero.
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from .psuu import cell_keys, describe_ranges, metrics_of, region_cells, settings_of, strata
from .style import family_label, feature_label, feature_value, fmt_horizon, scenario_text

RESAMPLES = 200
Z95 = 1.959964


def wilson_lower(rate, n, z=Z95):
    if n == 0:
        return 0.0
    centre = rate + z * z / (2 * n)
    spread = z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n))
    return (centre - spread) / (1 + z * z / n)


def group_resamples(groups, n_resamples, seed):
    """Row weights for each resample: how many times each row's group was drawn."""
    codes, uniq_n = pd.factorize(groups)[0], len(np.unique(groups))
    rng = np.random.default_rng(seed)
    for _ in range(n_resamples):
        drawn = np.bincount(rng.integers(0, uniq_n, uniq_n), minlength=uniq_n)
        yield drawn[codes]


def point_stability(frame, params, ranges, eligible, best_key, groups, seed):
    """Share of group resamples in which the best eligible cell is the same cell."""
    idx, _ = cell_keys(frame, params, ranges)
    cell_ids, cells = pd.factorize(idx[params].astype(str).agg("|".join, axis=1))
    cells = list(cells)
    ok = np.array([c in eligible for c in cells])
    target = cells.index(best_key)
    u = frame.goal__combined.to_numpy()
    same = 0
    for w in group_resamples(groups, RESAMPLES, seed):
        total = np.bincount(cell_ids, weights=w * u, minlength=len(cells))
        count = np.bincount(cell_ids, weights=w, minlength=len(cells))
        mean = np.where((count > 0) & ok, total / np.maximum(count, 1e-12), -np.inf)
        same += int(np.argmax(mean) == target)
    return same / RESAMPLES


def cell_name(cell):
    return "|".join(map(str, cell))


def level(share):
    return "high" if share >= 0.8 else "medium" if share >= 0.5 else "low"


def range_entry(cells, params, rate_col, pass_share):
    chosen = cells[cells[rate_col] >= pass_share]
    if chosen.empty:
        best = cells[rate_col].max()
        return {"range": "none", "cells": 0, "confidence": "none", "weakest_rate": np.nan,
                "weakest_lower_bound": np.nan, "best_rate_outside": best}
    lows = [wilson_lower(r, n) for r, n in zip(chosen[rate_col], chosen.runs)]
    text = "; ".join(f"{feature_label(p, False).lower()} {describe_ranges(p, chosen)}" for p in params)
    return {"range": text, "cells": len(chosen), "confidence": "high" if min(lows) >= pass_share else "medium",
            "weakest_rate": float(chosen[rate_col].min()), "weakest_lower_bound": float(min(lows)),
            "best_rate_outside": np.nan}


def cell_text(params, best):
    return "; ".join(f"{feature_label(p, False).lower()} " + (
        best[f"{p}_lo"] if isinstance(best[f"{p}_lo"], str)
        else f"{feature_value(p, best[f'{p}_lo'])} to {feature_value(p, best[f'{p}_hi'])}") for p in params)


def recommendations(scored, seed=20261027):
    """One row per horizon, design, scenario and recommendation kind."""
    runs, spec, layout, ranges = scored.runs, scored.spec, scored.layout, scored.ranges
    cfg = spec["regions"]
    rows = []
    for keys, frame in strata(runs, layout):
        params = settings_of(frame, layout)
        base = {"horizon": keys["horizon"], "mechanism": keys["mechanism"], "scenario": keys["scenario"],
                "settings": ",".join(params), "runs": len(frame)}
        if not params:
            rows.append({**base, "kind": "fixed", "goal": "", "range": "no setting to choose",
                         "all_goals_pass_rate": frame.goalpass__combined.mean(),
                         "combined_utility": frame.goal__combined.mean(), "confidence": ""})
            continue
        cells = region_cells(frame, params, spec, ranges)
        ok = cells[cells.runs >= cfg["min_runs_per_cell"]]
        if ok.empty:
            rows.append({**base, "kind": "point", "goal": "", "range": "too few runs per cell", "confidence": "none"})
            continue
        best = ok.loc[ok.combined_mean.idxmax()]
        groups = frame[layout["group"]].to_numpy() if layout["group"] else np.arange(len(frame))
        eligible = {cell_name(c) for c in ok["_cell"]}
        share = point_stability(frame, params, ranges, eligible, cell_name(best["_cell"]), groups, seed)
        rows.append({**base, "kind": "point", "goal": "", "range": cell_text(params, best),
                     "combined_utility": best.combined_mean, "combined_se": best.combined_se,
                     "all_goals_pass_rate": best.all_goals_pass_rate, "cells": 1, "best_share": share,
                     "confidence": level(share)})
        for g in spec["goals"]:
            rows.append({**base, "kind": "goal range", "goal": g["id"],
                         **range_entry(ok, params, f"{g['id']}_pass_rate", cfg["pass_share"])})
        rows.append({**base, "kind": "global range", "goal": "every goal",
                     **range_entry(ok, params, "all_goals_pass_rate", cfg["pass_share"])})
    return pd.DataFrame(rows)


# Sign and confidence -----------------------------------------------------------------------------------------------


def symbol(rho, lo, hi):
    if not np.isfinite(rho):
        return "n/a"
    if lo <= 0 <= hi:
        return "0"
    sign = "+" if rho > 0 else "-"
    size = abs(rho)
    return sign * 2 if size >= 0.3 else sign if size >= 0.1 else f"({sign})"


def rank_corr(X, Y):
    """Spearman correlation of every column of X with every column of Y."""
    rx = X.rank().to_numpy()
    ry = Y.rank().to_numpy()
    rx = (rx - rx.mean(0)) / np.where(rx.std(0) > 0, rx.std(0), np.nan)
    ry = (ry - ry.mean(0)) / np.where(ry.std(0) > 0, ry.std(0), np.nan)
    return rx.T @ ry / len(rx)


def sign_matrix(scored, seed=20261027):
    runs, spec, layout = scored.runs, scored.spec, scored.layout
    target_cols = [(f"metric__{m['id']}", "kpi", m["id"]) for _, m in metrics_of(spec)]
    target_cols += [(f"goal__{g['id']}", "goal utility", g["id"]) for g in spec["goals"]]
    target_cols.append(("goal__combined", "goal utility", "combined"))
    rows = []
    for (h, fam), frame in runs.groupby([layout["horizon"], layout["family"]], sort=True):
        params = settings_of(frame, layout)
        others = [c for c in layout["behaviour"] + layout["scenarios"]
                  if frame[c].notna().all() and frame[c].nunique() > 1]
        inputs = params + others
        if not inputs:
            continue
        X = frame[inputs].apply(lambda c: c.astype("category").cat.codes if c.dtype == object else c)
        Y = frame[[c for c, _, _ in target_cols]].astype(float)
        rho = rank_corr(X, Y)
        groups = frame[layout["group"]].to_numpy() if layout["group"] else np.arange(len(frame))
        codes = pd.factorize(groups)[0]
        members = pd.Series(np.arange(len(frame))).groupby(codes).apply(np.asarray).to_list()
        rng = np.random.default_rng(seed)
        draws = []
        for _ in range(RESAMPLES):
            pick = np.concatenate([members[k] for k in rng.integers(0, len(members), len(members))])
            draws.append(rank_corr(X.iloc[pick], Y.iloc[pick]))
        draws = np.asarray(draws)
        with warnings.catch_warnings():  # a KPI that never varies within a design has no correlation to bound
            warnings.simplefilter("ignore", RuntimeWarning)
            lo, hi = np.nanquantile(draws, 0.025, axis=0), np.nanquantile(draws, 0.975, axis=0)
        for i, name in enumerate(inputs):
            kind = "setting" if name in params else "scenario" if name in layout["scenarios"] else "behaviour"
            for j, (col, tkind, tid) in enumerate(target_cols):
                rows.append({"horizon": h, "mechanism": fam, "input": name, "input_kind": kind, "target": tid,
                             "target_kind": tkind, "rank_correlation": rho[i, j], "ci_low": lo[i, j],
                             "ci_high": hi[i, j], "symbol": symbol(rho[i, j], lo[i, j], hi[i, j]), "runs": len(frame)})
    return pd.DataFrame(rows)


# Markdown ----------------------------------------------------------------------------------------------------------


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out)


def scenario_name(scored, key):
    if key == "all":
        return "All scenarios"
    parts = []
    for part in key.split(" & "):
        axis, _, value = part.partition("=")
        try:
            value = float(value)
        except ValueError:
            pass
        parts.append(scenario_text(axis, value))
    return ", ".join(parts)


def range_text(r):
    if r.confidence == "none":
        best = r.best_rate_outside
        return f"none, best cell {best:.0%}" if np.isfinite(best) else "none"
    return f"{r.range} ({r.confidence})"


def recommendations_md(scored, table):
    spec = scored.spec
    cfg = spec["regions"]
    goals = [g["id"] for g in spec["goals"]]
    lines = ["# Recommendation tables", "",
             f"Computed from the scored sweep with specification `{spec.get('name')}`. A cell is a bin of the design's "
             f"settings and needs at least {cfg['min_runs_per_cell']} runs. A range holds the cells where at least "
             f"{cfg['pass_share']:.0%} of runs pass. Confidence is defined in the notes at the end.", ""]
    names = ", ".join(f"{g['id']} {g['name']}" for g in spec["goals"])
    lines += [f"Goals: {names}.", ""]
    for h in sorted(table.horizon.unique(), key=str):
        lines += [f"## {fmt_horizon(h)}", ""]
        for fam in sorted(table[table.horizon == h].mechanism.unique()):
            t = table[(table.horizon == h) & (table.mechanism == fam)]
            lines += [f"### {family_label(fam)}", ""]
            if (t.kind == "fixed").all():
                rows = [[scenario_name(scored, r.scenario), f"{r.all_goals_pass_rate:.0%}", f"{r.combined_utility:.2f}"]
                        for r in t.itertuples()]
                lines += ["A fixed design with no setting to choose.", "",
                          md_table(["Scenario", "Runs passing every goal", "Combined utility"], rows), ""]
                continue
            rows = []
            for scen in dict.fromkeys(t.scenario):
                s = t[t.scenario == scen].set_index(["kind", "goal"])
                p = s.loc[("point", "")]

                point = (f"{p.range}: utility {p.combined_utility:.2f}, best in {p.best_share:.0%} of resamples "
                         f"({p.confidence}), {p.all_goals_pass_rate:.0%} of its runs pass every goal"
                         if p.confidence != "none" else p.range)
                rows.append([scenario_name(scored, scen), point] + [range_text(s.loc[("goal range", g)]) for g in goals]
                            + [range_text(s.loc[("global range", "every goal")])])
            lines += [md_table(["Scenario", "Point estimate"] + [f"{g} range" for g in goals] + ["Every goal"], rows),
                      ""]
    lines += ["## Notes", "",
              "1. Point estimate: the cell with the highest mean combined utility. Its confidence is the share of "
              f"{RESAMPLES} resamples of the runs, drawn by the group of shared draws, in which the same cell stays "
              "best. High is 80% or more, medium 50% or more, low below 50%. Neighbouring cells with almost equal "
              "utility make a low confidence, so read the point with its range.",
              f"2. Ranges: high when the 95% Wilson lower bound of every cell's pass rate is at least "
              f"{cfg['pass_share']:.0%}, medium when the range holds cells but some lower bound is below it. 'none, "
              "best cell' gives the highest pass rate of any cell when no cell reaches the line.",
              "3. With two or more settings, a range lists each setting's span over its cells, which can be wider "
              "than the cells themselves. The cell table holds the exact cells.", ""]
    return "\n".join(lines)


def sign_md(scored, table):
    spec = scored.spec
    kpis = [m for _, m in metrics_of(spec)]
    lines = ["# Sign and confidence of each input against each KPI and goal", "",
             "Rank correlation across runs of one design, with a 95% interval from "
             f"{RESAMPLES} resamples drawn by the group of shared draws. ++ or --: the interval excludes zero and the "
             "correlation is at least 0.3 in size. + or -: from 0.1 to 0.3. (+) or (-): below 0.1. 0: the interval "
             "includes zero. A + means a higher input goes with a higher value.", "",
             "KPIs: " + "; ".join(f"{m['id']} {m.get('label', '')}" for m in kpis) + ".", ""]
    targets = [m["id"] for m in kpis] + [g["id"] for g in spec["goals"]] + ["combined"]
    for h in sorted(table.horizon.unique(), key=str):
        lines += [f"## {fmt_horizon(h)}", ""]
        for fam in sorted(table[table.horizon == h].mechanism.unique()):
            t = table[(table.horizon == h) & (table.mechanism == fam)]
            rows = []
            for name in dict.fromkeys(t.input):
                r = t[t.input == name].set_index("target")
                rows.append([f"{feature_label(name, False)} ({r.input_kind.iloc[0]})"]
                            + [r.loc[x, "symbol"] for x in targets])
            lines += [f"### {family_label(fam)}", "", md_table(["Input"] + targets, rows), ""]
    return "\n".join(lines)


def write_all(scored, folder: Path, seed=20261027, log=print):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rec = recommendations(scored, seed)
    rec.to_csv(folder / "recommendations.csv", index=False)
    (folder / "recommendations.md").write_text(recommendations_md(scored, rec))
    sig = sign_matrix(scored, seed)
    sig.to_csv(folder / "sign-confidence.csv", index=False)
    (folder / "sign-confidence.md").write_text(sign_md(scored, sig))
    log(f"  recommendations: {len(rec)} rows; sign matrix: {len(sig)} cells")
    return rec, sig
