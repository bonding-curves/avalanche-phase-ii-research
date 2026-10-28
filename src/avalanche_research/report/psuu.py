"""PSuU results for a reward-design sweep: goal utilities, forests, response curves and regions.

PSuU, parameter selection under uncertainty, scores every run of a sweep against declared goals and asks which settings
of each reward design keep the goals met across scenarios. `run` reads a sweep's wide table (one row per run and
horizon), its manifest and a goal and utility specification, and writes, for every mechanism family and scenario:

1. each run's metric values, metric utilities, goal utilities and combined utility (`tables/trajectory-utilities.parquet`);
2. summary tables of each goal's utility and pass rate (`tables/summary-goals.csv`, `tables/summary-metrics.csv`);
3. random forests from the inputs to each goal utility and the combined utility, with out-of-bag and held-out fit and
   permutation importances (`tables/forest-fit.csv`, `tables/forest-importance.csv`);
4. response curves: the mean and the 10th to 90th percentile of runs in bins of each input, beside the forest's partial
   dependence and the spread of its individual curves (`tables/response-curves.csv`);
5. the setting region with the highest combined utility and the region where every goal passes (`tables/regions.csv`,
   `tables/region-cells.csv`);
6. PNG and SVG figures of the above (`figures/`), and `run-config.json` with the layout read from the manifest.

The manifest (`report.manifest`) declares which columns are settings, scenarios, behaviour inputs and KPIs, which
rows are the paired baselines and which blocks to analyse. When a sweep has Saltelli blocks A and B, the manifest
names only those, because the hybrid AB and BA rows reuse their noise keys and would leak between the forests' training
and test runs.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import textwrap
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import GroupShuffleSplit

from . import manifest as manifest_io
from . import style
from .style import (GRID, INK, INK2, MODEL_BLUE, MUTED, PAPER, SEQUENTIAL, colour_values, family_colour, family_label,
                    feature_label, feature_value, fmt_horizon, headline, save, scenario_text, setting_phrase)

import matplotlib.pyplot as plt  # noqa: E402  (style selects the Agg backend first)

# Specification -------------------------------------------------------------------------------------------------------

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
FUNCTIONS = {"abs", "log", "exp", "sqrt", "where"}


def load_spec(path):
    spec = json.loads(Path(path).expanduser().read_text())
    if not spec.get("goals"):
        raise SystemExit("the specification has no goals")
    for g in spec["goals"]:
        if not g.get("metrics"):
            raise SystemExit(f"goal {g['id']} has no metrics")
        for m in g["metrics"]:
            for key in ("id", "expr", "threshold", "utility"):
                if key not in m:
                    raise SystemExit(f"metric {m.get('id', '?')} of goal {g['id']} has no {key}")
            if m["threshold"]["op"] not in (">=", ">", "<=", "<", "between"):
                raise SystemExit(f"metric {m['id']}: unknown threshold op {m['threshold']['op']}")
            if m["utility"]["type"] not in ("linear", "step", "band"):
                raise SystemExit(f"metric {m['id']}: unknown utility type {m['utility']['type']}")
    method = spec.get("combine", {}).get("method", "weighted_mean")
    if method != "weighted_mean":
        raise SystemExit(f"unknown combine method {method}")
    regions = {"utility_tolerance": 0.01, "pass_share": 0.9, "min_runs_per_cell": 30}
    regions.update(spec.get("regions", {}))
    spec["regions"] = regions
    return spec


def spec_columns(spec):
    """Base columns and baseline columns that the metric expressions read."""
    base, paired = set(), set()
    for g in spec["goals"]:
        for m in g["metrics"]:
            for name in IDENT.findall(m["expr"]):
                if name.startswith("baseline__"):
                    paired.add(name[len("baseline__"):])
                else:
                    base.add(name)
    return base - FUNCTIONS, paired


def metrics_of(spec):
    """Every metric of the specification, with the goal it belongs to."""
    return [(g, m) for g in spec["goals"] for m in g["metrics"]]


def passes(values, threshold):
    op, v = threshold["op"], threshold["value"]
    if op == ">=":
        return values >= v
    if op == ">":
        return values > v
    if op == "<=":
        return values <= v
    if op == "<":
        return values < v
    lo, hi = v
    return (values >= lo) & (values <= hi)


def utility(values, rule, passed):
    kind = rule["type"]
    if kind == "step":
        return passed.astype(float)
    if kind == "linear":
        floor, target = float(rule["floor"]), float(rule["target"])
        return np.clip((values - floor) / (target - floor), 0.0, 1.0)
    lo, hi, lo_f, hi_f = (float(rule[k]) for k in ("low", "high", "low_floor", "high_floor"))
    below = np.clip((values - lo_f) / (lo - lo_f), 0.0, 1.0)
    above = np.clip((hi_f - values) / (hi_f - hi), 0.0, 1.0)
    return np.where(values < lo, below, np.where(values > hi, above, 1.0))


def score(frame, spec):
    """Add each metric's value, pass and utility, each goal's utility and pass, the combined utility and the
    all-goal pass to the frame."""
    out = {}
    goal_w = []
    for g in spec["goals"]:
        mu, mw, mp = [], [], []
        for m in g["metrics"]:
            col = f"metric__{m['id']}"
            values = frame.eval(m["expr"], engine="python").astype(float).to_numpy()
            if not np.isfinite(values).all():
                bad = int((~np.isfinite(values)).sum())
                raise SystemExit(f"metric {m['id']} is not finite in {bad} runs: check its expression")
            ok = passes(values, m["threshold"])
            out[col] = values
            out[f"pass__{m['id']}"] = ok
            out[f"util__{m['id']}"] = utility(values, m["utility"], ok)
            mu.append(out[f"util__{m['id']}"])
            mw.append(float(m.get("weight", 1)))
            mp.append(ok)
        mw = np.asarray(mw) / sum(mw)
        u = np.sum([w * x for w, x in zip(mw, mu)], axis=0)
        out[f"goal__{g['id']}"] = u
        if g.get("pass_rule", "all_metrics") == "utility_at_least":
            out[f"goalpass__{g['id']}"] = u >= float(g["pass_utility"])
        else:
            out[f"goalpass__{g['id']}"] = np.logical_and.reduce(mp)
        goal_w.append(float(g.get("weight", 1)))
    goal_w = np.asarray(goal_w) / sum(goal_w)
    out["goal__combined"] = np.sum([w * out[f"goal__{g['id']}"] for w, g in zip(goal_w, spec["goals"])], axis=0)
    out["goalpass__combined"] = np.logical_and.reduce([out[f"goalpass__{g['id']}"] for g in spec["goals"]])
    return pd.concat([frame, pd.DataFrame(out, index=frame.index)], axis=1)


# Reading the sweep ---------------------------------------------------------------------------------------------------


def quoted(values):
    return ",".join("'" + str(v).replace("'", "''") + "'" for v in values)


def layout_from_manifest(con, wide, spec, manifest, blocks=None):
    """The analysis layout the manifest declares: families, blocks, scenarios, settings, behaviour and pairing."""
    schema = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [wide]).df()
    types = dict(zip(schema.column_name, schema.column_type))
    manifest_io.check_table(manifest, list(types))
    family = manifest["family_column"]
    block = manifest.get("block_column")
    base, paired = spec_columns(spec)
    kpis = set(manifest_io.names(manifest, "kpi"))
    not_kpi = sorted((base | paired) - kpis)
    if not_kpi:
        raise SystemExit(f"the specification reads columns the manifest does not declare as KPIs: {not_kpi}")
    pair = manifest.get("pair") or {}
    if paired and not (pair.get("row") and pair.get("baseline_row")):
        raise SystemExit("the specification reads baseline__ columns but the manifest declares no pair")
    baseline = manifest.get("baseline") or {}
    clauses = []
    if baseline.get("families"):
        clauses.append(f'"{family}" IN ({quoted(baseline["families"])})')
    if block and baseline.get("blocks"):
        clauses.append(f'"{block}" IN ({quoted(baseline["blocks"])})')
    baseline_where = f"({' OR '.join(clauses)})" if clauses else "FALSE"
    blocks = blocks or manifest.get("analysis_blocks")
    design_where = f"NOT {baseline_where}"
    if blocks:
        if not block:
            raise SystemExit("the manifest lists analysis blocks but no block column")
        design_where += f' AND "{block}" IN ({quoted(blocks)})'
    horizon = manifest.get("horizon_column")
    return {
        "types": types, "family": family, "block": block, "blocks": blocks, "design_where": design_where,
        "baseline_where": baseline_where, "scenarios": manifest_io.names(manifest, "scenario"),
        "parameters": manifest_io.names(manifest, "setting"), "behaviour": manifest_io.names(manifest, "behaviour"),
        "horizon": horizon, "base": sorted(base), "paired": sorted(paired), "group": manifest.get("split_group"),
        "row": pair.get("row"), "baseline_row": pair.get("baseline_row"),
    }


def read_runs(con, wide, layout):
    fam = layout["family"]
    keep = [fam] + layout["scenarios"] + layout["parameters"] + layout["behaviour"] + layout["base"]
    for extra in (layout["horizon"], layout["group"], layout["row"], layout["baseline_row"], layout["block"]):
        if extra and extra in layout["types"]:
            keep.append(extra)
    keep = list(dict.fromkeys(keep))
    sel = ", ".join(f'"{c}"' for c in keep)
    runs = con.execute(f"SELECT {sel} FROM read_parquet(?) WHERE {layout['design_where']}", [wide]).df()
    if runs.empty:
        raise SystemExit("no design runs: check the manifest's baseline and analysis blocks")
    if layout["paired"]:
        row, base_row = layout["row"], layout["baseline_row"]
        on = [row] + ([layout["horizon"]] if layout["horizon"] else [])
        bsel = ", ".join(f'"{c}"' for c in on + layout["paired"])
        base = con.execute(f"SELECT {bsel} FROM read_parquet(?) WHERE {layout['baseline_where']}", [wide]).df()
        base = base.rename(columns={c: f"baseline__{c}" for c in layout["paired"]})
        base = base.rename(columns={row: base_row})
        n = len(runs)
        runs = runs.merge(base, on=[base_row] + on[1:], how="left", validate="many_to_one")
        lost = runs[[f"baseline__{c}" for c in layout["paired"]]].isna().any(axis=1).sum()
        if len(runs) != n or lost:
            raise SystemExit(f"{lost} runs have no paired baseline row")
    if layout["horizon"] is None:
        runs["horizon_days"] = "all"
        layout["horizon"] = "horizon_days"
    return runs


# Strata --------------------------------------------------------------------------------------------------------------


def strata(runs, layout):
    """Yield (keys, frame): every family and horizon, at each scenario and pooled over the scenarios."""
    h, axes = layout["horizon"], layout["scenarios"]
    for (hv, fam), frame in runs.groupby([h, layout["family"]], sort=True):
        if axes:
            for values, sub in frame.groupby(axes, sort=True):
                values = values if isinstance(values, tuple) else (values,)
                yield {"horizon": hv, "mechanism": fam, "scenario": scenario_key(axes, values),
                       **dict(zip(axes, values))}, sub
        yield {"horizon": hv, "mechanism": fam, "scenario": "all", **{a: np.nan for a in axes}}, frame


def scenario_key(axes, values):
    return "; ".join(f"{a}={v:g}" if isinstance(v, (float, int, np.floating, np.integer)) else f"{a}={v}"
                     for a, v in zip(axes, values)).replace("; ", " & ")


def settings_of(frame, layout):
    """The design settings that vary within a family's runs."""
    return [c for c in layout["parameters"] if frame[c].notna().all() and frame[c].nunique() > 1]


def inputs_for(frame, layout, pooled):
    """The stratum's varying inputs: design settings, then behaviour, then scenario axes in a pooled model."""
    names = [c for c in layout["parameters"] + layout["behaviour"] if frame[c].notna().all() and frame[c].nunique() > 1]
    if pooled:
        names += [c for c in layout["scenarios"] if frame[c].nunique() > 1]
    return names


def design_matrix(frame, names):
    X = pd.DataFrame(index=frame.index)
    for c in names:
        col = frame[c]
        X[c] = col.astype("category").cat.codes.astype(float) if col.dtype == object else col.astype(float)
    return X


def targets(spec):
    return [f"goal__{g['id']}" for g in spec["goals"]] + ["goal__combined"]


def target_label(spec, t):
    if t == "goal__combined":
        return "Combined"
    g = next(g for g in spec["goals"] if f"goal__{g['id']}" == t)
    return f"{g['id']} {g['name']}"


# Summaries -----------------------------------------------------------------------------------------------------------


def summaries(runs, spec, layout):
    goal_rows, metric_rows = [], []
    for keys, frame in strata(runs, layout):
        for g in spec["goals"] + [{"id": "combined", "name": "Combined"}]:
            u = frame[f"goal__{g['id']}"]
            goal_rows.append({**keys, "goal": g["id"], "goal_name": g["name"], "runs": len(frame),
                              "utility_mean": u.mean(), "utility_p10": u.quantile(0.1),
                              "utility_p50": u.quantile(0.5), "utility_p90": u.quantile(0.9),
                              "pass_rate": frame[f"goalpass__{g['id']}"].mean()})
            for m in g.get("metrics", []):
                v = frame[f"metric__{m['id']}"]
                metric_rows.append({**keys, "goal": g["id"], "metric": m["id"], "label": m.get("label", ""),
                                    "expr": m["expr"], "runs": len(frame), "value_mean": v.mean(),
                                    "value_p10": v.quantile(0.1), "value_p50": v.quantile(0.5),
                                    "value_p90": v.quantile(0.9),
                                    "utility_mean": frame[f"util__{m['id']}"].mean(),
                                    "pass_rate": frame[f"pass__{m['id']}"].mean()})
    return pd.DataFrame(goal_rows), pd.DataFrame(metric_rows)


# Bins ----------------------------------------------------------------------------------------------------------------


def nice_range(values):
    lo, hi = float(np.nanmin(values)), float(np.nanmax(values))
    if hi <= lo:
        return lo, hi
    step = 10 ** (math.floor(math.log10(hi - lo)) - 1)
    return math.floor(lo / step + 1e-9) * step, math.ceil(hi / step - 1e-9) * step


def input_ranges(runs, layout):
    """Each numeric input's swept range rounded outward, so bins have readable edges in every subset."""
    out = {}
    for c in layout["parameters"] + layout["behaviour"] + layout["scenarios"]:
        if runs[c].dtype != object and runs[c].notna().any():
            out[c] = nice_range(runs[c])
    return out


def bins_for(values, n_bins, ranges):
    values = pd.Series(values)
    uniq = np.sort(values.dropna().unique())
    if values.dtype == object or len(uniq) <= n_bins:
        return None, uniq
    lo, hi = ranges.get(values.name, (uniq[0], uniq[-1]))
    edges = np.linspace(lo, hi, n_bins + 1)
    return edges, (edges[:-1] + edges[1:]) / 2


def bin_index(values, edges):
    n_bins = len(edges) - 1
    return np.clip(np.searchsorted(edges, np.asarray(values, dtype=float), side="right") - 1, 0, n_bins - 1)


def binned(frame, feature, target, ranges, n_bins=12):
    """Mean and 10th to 90th percentile of runs in equal-width bins of one input."""
    edges, centres = bins_for(frame[feature], n_bins, ranges)
    if edges is None:
        groups = frame.groupby(feature)[target]
        rows = [(c, c, c, s) for c, s in groups]
    else:
        idx = bin_index(frame[feature].to_numpy(), edges)
        groups = frame[target].groupby(idx)
        rows = [(edges[k], edges[k + 1], centres[k], s) for k, s in groups]
    return pd.DataFrame([{"bin_lo": lo, "bin_hi": hi, "x": x, "n": len(s), "run_mean": s.mean(),
                          "run_p10": s.quantile(0.1), "run_p50": s.quantile(0.5), "run_p90": s.quantile(0.9)}
                         for lo, hi, x, s in rows])


# Forests and response curves -----------------------------------------------------------------------------------------


def partial_dependence(model, X, feature, grid, sample=2000, seed=0):
    """Average and 10th and 90th percentile of the individual curves at each grid value."""
    Xs = X.sample(n=min(sample, len(X)), random_state=seed) if len(X) > sample else X
    out = []
    for v in grid:
        Z = Xs.copy()
        Z[feature] = v
        p = model.predict(Z)
        out.append((p.mean(), np.quantile(p, 0.1), np.quantile(p, 0.9)))
    return np.asarray(out)


def forests(runs, spec, layout, ranges, trees=300, repeats=10, jobs=8, seed=20261027, log=print):
    fit_rows, imp_rows, curve_rows = [], [], []
    tlist = targets(spec)
    for keys, frame in strata(runs, layout):
        pooled = keys["scenario"] == "all"
        names = inputs_for(frame, layout, pooled)
        if not names:
            continue
        X = design_matrix(frame, names)
        groups = frame[layout["group"]].to_numpy() if layout["group"] else np.arange(len(frame))
        split = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed)
        train, test = next(split.split(X, groups=groups))
        for t in tlist:
            y = frame[t].to_numpy()
            row = {**keys, "target": t, "target_name": target_label(spec, t), "inputs": ",".join(names),
                   "runs": len(frame), "train_runs": len(train), "test_runs": len(test), "target_sd": y.std()}
            if y.std() < 0.005:
                fit_rows.append({**row, "status": "utility spread below 0.005, no forest"})
                continue
            model = RandomForestRegressor(n_estimators=trees, min_samples_leaf=5, max_features=1.0,
                                          oob_score=True, n_jobs=jobs, random_state=seed)
            model.fit(X.iloc[train], y[train])
            model.set_params(n_jobs=1)  # threaded prediction sums trees in thread order, which changes the last bits
            test_r2 = model.score(X.iloc[test], y[test])
            fit_rows.append({**row, "status": "fitted", "oob_r2": model.oob_score_, "test_r2": test_r2})
            pi = permutation_importance(model, X.iloc[test], y[test], n_repeats=repeats, scoring="r2",
                                        random_state=seed, n_jobs=1)
            for k, name in enumerate(names):
                imp_rows.append({**keys, "target": t, "target_name": target_label(spec, t), "input": name,
                                 "importance_r2_drop": pi.importances_mean[k], "importance_sd": pi.importances_std[k],
                                 "test_r2": test_r2})
            for name in names:
                curve = binned(frame, name, t, ranges)
                if frame[name].dtype == object:
                    grid = frame[name].astype("category").cat.categories.get_indexer(curve.x).astype(float)
                else:
                    grid = curve.x.to_numpy(dtype=float)
                pd_vals = partial_dependence(model, X, name, grid, seed=seed)
                curve["pd_mean"], curve["ice_p10"], curve["ice_p90"] = pd_vals.T
                for r in curve.to_dict("records"):
                    curve_rows.append({**keys, "target": t, "target_name": target_label(spec, t), "input": name, **r})
        log(f"  forests {keys['horizon']} {keys['mechanism']} {keys['scenario']}: {len(frame)} runs")
    return pd.DataFrame(fit_rows), pd.DataFrame(imp_rows), pd.DataFrame(curve_rows)


# Regions -------------------------------------------------------------------------------------------------------------


def cell_bins(n_params):
    """Bins per setting in the region cells: finer for one setting, coarser as settings multiply."""
    return {1: 10, 2: 5, 3: 4}.get(n_params, 3)


def cell_keys(frame, params, ranges):
    """Each run's region cell, one column per setting, and each setting's bin edges (None for a text setting)."""
    n_bins = cell_bins(len(params))
    idx = pd.DataFrame(index=frame.index)
    edges = {}
    for p in params:
        e, _ = bins_for(frame[p], n_bins, ranges)
        if e is None:
            idx[p] = frame[p].astype(str)
            edges[p] = None
        else:
            idx[p] = bin_index(frame[p].to_numpy(), e)
            edges[p] = e
    return idx, edges


def region_cells(frame, params, spec, ranges):
    idx, edges = cell_keys(frame, params, ranges)
    rows = []
    for cell, sub in frame.groupby([idx[p] for p in params]):
        cell = cell if isinstance(cell, tuple) else (cell,)
        r = {"runs": len(sub), "combined_mean": sub.goal__combined.mean(),
             "combined_se": sub.goal__combined.std(ddof=1) / math.sqrt(len(sub)) if len(sub) > 1 else np.nan,
             "combined_p10": sub.goal__combined.quantile(0.1), "combined_p90": sub.goal__combined.quantile(0.9),
             "all_goals_pass_rate": sub.goalpass__combined.mean()}
        ids = [g["id"] for g in spec["goals"]]
        for g in ids:
            r[f"{g}_utility"] = sub[f"goal__{g}"].mean()
            r[f"{g}_pass_rate"] = sub[f"goalpass__{g}"].mean()
        for g in ids:  # the share that would pass if this one goal were dropped
            others = [f"goalpass__{o}" for o in ids if o != g]
            r[f"all_but_{g}_pass_rate"] = sub[others].all(axis=1).mean() if others else 1.0
        for p, c in zip(params, cell):
            if edges[p] is None:
                r[f"{p}_lo"] = r[f"{p}_hi"] = c
            else:
                r[f"{p}_lo"], r[f"{p}_hi"] = edges[p][c], edges[p][c + 1]
        r["_cell"] = cell
        rows.append(r)
    return pd.DataFrame(rows)


def contiguous_ranges(lo, hi):
    """Merge touching or overlapping intervals into ranges. Cells of two or more settings repeat each bin."""
    spans = sorted(set(zip(lo, hi)))
    out = []
    for a, b in spans:
        if out and a <= out[-1][1] + 1e-12:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def describe_ranges(p, cells):
    if cells.empty:
        return "none"
    if isinstance(cells[f"{p}_lo"].iloc[0], str):
        return ", ".join(sorted(set(cells[f"{p}_lo"])))
    return ", ".join(f"{feature_value(p, a)} to {feature_value(p, b)}"
                     for a, b in contiguous_ranges(cells[f"{p}_lo"], cells[f"{p}_hi"]))


def regions(runs, spec, layout, ranges):
    cfg = spec["regions"]
    summary_rows, cell_rows = [], []
    for keys, frame in strata(runs, layout):
        params = settings_of(frame, layout)
        conditions = [("all runs", frame)]
        for b in layout["behaviour"]:
            if frame[b].nunique() > 3:
                lo, hi = frame[b].min(), frame[b].max()
                third = np.minimum(((frame[b] - lo) / (hi - lo) * 3).astype(int), 2)
                for k, name in enumerate(("low", "middle", "high")):
                    conditions.append((f"{feature_label(b, False).lower()} {name} third", frame[third == k]))
        for cond, sub in conditions:
            base = {**keys, "condition": cond, "parameters": ",".join(params), "runs": len(sub),
                    "combined_mean": sub.goal__combined.mean(), "all_goals_pass_rate": sub.goalpass__combined.mean()}
            if not params:
                summary_rows.append({**base, "region": "no setting to choose"})
                continue
            cells = region_cells(sub, params, spec, ranges)
            for r in cells.drop(columns="_cell").to_dict("records"):
                cell_rows.append({**keys, "condition": cond, **r})
            ok = cells[cells.runs >= cfg["min_runs_per_cell"]]
            if ok.empty:
                summary_rows.append({**base, "region": "too few runs per cell"})
                continue
            best = ok.loc[ok.combined_mean.idxmax()]
            top = ok[ok.combined_mean >= best.combined_mean - cfg["utility_tolerance"]]
            passing = ok[ok.all_goals_pass_rate >= cfg["pass_share"]]
            best_pass = ok.loc[ok.all_goals_pass_rate.idxmax()]
            no_pass = best_pass.all_goals_pass_rate == 0
            ids = [g["id"] for g in spec["goals"]]
            binding = max(ids, key=lambda g: best_pass[f"all_but_{g}_pass_rate"])
            row = {**base, "region": "found", "best_cell_combined_mean": best.combined_mean,
                   "best_cell_combined_se": best.combined_se, "best_cell_combined_p10": best.combined_p10,
                   "best_cell_combined_p90": best.combined_p90, "best_cell_all_goals_pass_rate": best.all_goals_pass_rate,
                   "binding_goal_in_highest_pass_cell": binding,
                   "highest_pass_cell_rate_without_binding_goal": best_pass[f"all_but_{binding}_pass_rate"],
                   "top_cells": len(top), "top_cells_mean_low": top.combined_mean.min(),
                   "all_goal_cells": len(passing), "highest_cell_all_goals_pass_rate": best_pass.all_goals_pass_rate}
            for p in params:
                row[f"best_cell[{p}]"] = f"{feature_value(p, best[f'{p}_lo'])} to {feature_value(p, best[f'{p}_hi'])}" \
                    if not isinstance(best[f"{p}_lo"], str) else best[f"{p}_lo"]
                row[f"highest_utility_region[{p}]"] = describe_ranges(p, top)
                row[f"all_goal_region[{p}]"] = describe_ranges(p, passing)
                row[f"highest_pass_cell[{p}]"] = "none" if no_pass else describe_ranges(p, best_pass.to_frame().T)
            summary_rows.append(row)
    return pd.DataFrame(summary_rows), pd.DataFrame(cell_rows)


# Figures -------------------------------------------------------------------------------------------------------------


def figure_overview(runs, spec, layout, ranges, horizon, axis, folder):
    """Combined utility and all-goal pass share across each design's settings, one line per scenario value."""
    fam_col = layout["family"]
    data = runs[runs[layout["horizon"]] == horizon]
    fams = sorted(data[fam_col].unique())
    panels = [(f, p) for f in fams for p in layout["parameters"]
              if data.loc[data[fam_col] == f, p].notna().all() and data.loc[data[fam_col] == f, p].nunique() > 1]
    fixed = [f for f in fams if not any(f == q for q, _ in panels)]
    if not panels:
        return None
    vals, colours = colour_values(data, axis) if axis else ([None], {None: MODEL_BLUE})
    fig, axes = plt.subplots(2, len(panels), figsize=(2.55 * len(panels) + 0.6, 4.9), squeeze=False,
                             sharey="row", constrained_layout=True)
    best = None
    for c, (f, p) in enumerate(panels):
        sub = data[data[fam_col] == f]
        scale = style.feature_scale(p)
        band = binned(sub, p, "goal__combined", ranges, 10)
        axes[0, c].fill_between(band.x * scale, band.run_p10, band.run_p90, color=GRID, lw=0,
                                label="10th to 90th percentile of runs")
        for v in vals:
            s = sub if v is None else sub[sub[axis] == v]
            if s.empty:
                continue
            u = binned(s, p, "goal__combined", ranges, 10)
            a = binned(s.assign(_p=s.goalpass__combined.astype(float)), p, "_p", ranges, 10)
            x = u.x * scale
            colour = colours[v]
            lab = scenario_text(axis, v) if v is not None else "all runs"
            axes[0, c].plot(x, u.run_mean, color=colour, lw=1.8, label=lab)
            axes[1, c].plot(x, a.run_mean * 100, color=colour, lw=1.8, label=lab)
        pooled = binned(sub, p, "goal__combined", ranges, 10)
        k = pooled.run_mean.idxmax()
        if best is None or pooled.run_mean[k] > best[0]:
            best = (pooled.run_mean[k], f, p, pooled.bin_lo[k], pooled.bin_hi[k])
        for f2 in fixed:
            m = data.loc[data[fam_col] == f2, "goal__combined"].mean()
            axes[0, c].axhline(m, color=family_colour(f2, fams), lw=1.1, ls=(0, (4, 3)))
            if c == len(panels) - 1:
                axes[0, c].text(axes[0, c].get_xlim()[1], m, f"{family_label(f2)}, mean ", fontsize=7, color=INK2,
                                va="bottom", ha="right")
        axes[1, c].axhline(spec["regions"]["pass_share"] * 100, color=MUTED, lw=0.8, ls=":")
        axes[0, c].set_title(family_label(f), color=family_colour(f, fams))
        axes[1, c].set_xlabel(feature_label(p))
        for r in (0, 1):
            axes[r, c].grid(axis="y", color=GRID, lw=0.6)
            axes[r, c].set_axisbelow(True)
    axes[0, 0].set_ylabel("Combined utility, 0 to 1")
    axes[1, 0].set_ylabel("Runs passing every goal, %")
    axes[1, 0].set_ylim(-2, 102)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=min(len(labels), 6))
    title = (f"{family_label(best[1])} reaches the highest combined utility of {best[0]:.2f} at "
             f"{setting_phrase(best[2])} {feature_value(best[2], best[3])} to {feature_value(best[2], best[4])}")
    sub = (f"Top: mean combined utility of runs in each setting bin, grey band 10th to 90th percentile of runs. Bottom: "
           f"share of runs passing every goal, dotted line at {spec['regions']['pass_share']:.0%}. {fmt_horizon(horizon)}.")
    headline(fig, title, sub)
    save(fig, folder, f"overview-{axis or 'pooled'}-{horizon}")
    return title


def figure_family(runs, spec, layout, ranges, horizon, fam, curves, folder):
    """Each goal's utility and the combined utility across each input, one line per primary scenario value."""
    data = runs[(runs[layout["horizon"]] == horizon) & (runs[layout["family"]] == fam)]
    names = inputs_for(data, layout, pooled=False)
    if not names:
        return None
    axis = layout["scenarios"][0] if layout["scenarios"] else None
    vals, colours = colour_values(data, axis) if axis else ([None], {None: MODEL_BLUE})
    tl = targets(spec)
    fig, axes = plt.subplots(len(tl), len(names), figsize=(2.5 * len(names) + 0.8, 1.55 * len(tl) + 0.6),
                             squeeze=False, sharey="row", sharex="col", constrained_layout=True)
    pooled_pd = curves[(curves.horizon == horizon) & (curves.mechanism == fam) & (curves.scenario == "all")] \
        if not curves.empty else curves
    swing = []
    for c, name in enumerate(names):
        scale = style.feature_scale(name)
        for r, t in enumerate(tl):
            ax = axes[r, c]
            allb = binned(data, name, t, ranges, 10)
            ax.fill_between(allb.x * scale, allb.run_p10, allb.run_p90, color=GRID, lw=0,
                            label="10th to 90th percentile of runs")
            for v in vals:
                s = data if v is None else data[data[axis] == v]
                b = binned(s, name, t, ranges, 10)
                ax.plot(b.x * scale, b.run_mean, color=colours[v], lw=1.6,
                        label=scenario_text(axis, v) if v is not None else "all runs")
            pdc = pooled_pd[(pooled_pd.input == name) & (pooled_pd.target == t)] if not pooled_pd.empty else pooled_pd
            if not pdc.empty:
                ax.plot(pdc.x * scale, pdc.pd_mean, color=INK, lw=1.1, ls=(0, (4, 2)), label="Forest, partial dependence")
                if t == "goal__combined":
                    swing.append((pdc.pd_mean.max() - pdc.pd_mean.min(), name))
            ax.grid(axis="y", color=GRID, lw=0.6)
            ax.set_axisbelow(True)
            ax.set_ylim(-0.03, 1.03)
            if c == 0:
                ax.set_ylabel(textwrap.fill(target_label(spec, t), 18), fontsize=7.5)
            if r == len(tl) - 1:
                ax.set_xlabel(feature_label(name))
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=3 if len(labels) > 4 else len(labels))
    if swing and max(swing)[0] >= 0.02:
        d, name = max(swing)
        title = (f"{feature_label(name, False)} moves {family_label(fam, True)}'s combined utility most "
                 f"with a swing of {d:.2f}")
    else:
        d = max(swing)[0] if swing else 0.0
        title = f"No input moves {family_label(fam, True)}'s combined utility by more than {max(d, 0.01):.2f}"
    sub = (f"Utility 0 to 1. Lines: mean of runs in each bin, one per "
           f"{feature_label(axis, False).lower() if axis else 'run'}. Grey band: 10th to 90th percentile of runs. "
           f"Dashed: forest partial dependence over all scenarios. {fmt_horizon(horizon)}.")
    headline(fig, title, sub)
    save(fig, folder, f"response-{fam}-{horizon}")
    return title


def figure_importance(imp, spec, layout, horizon, folder):
    """Permutation importance from the pooled forest and, beside it, the mean over the single-scenario forests."""
    if imp.empty:
        return None
    d = imp[imp.horizon == horizon]
    pooled = d[d.scenario == "all"]
    within = d[d.scenario != "all"].groupby(["mechanism", "input", "target"]).importance_r2_drop.mean()
    if pooled.empty:
        return None
    fams = sorted(pooled.mechanism.unique())
    tl = targets(spec)
    rows = [(f, i) for f in fams for i in dict.fromkeys(pooled[pooled.mechanism == f].input)]
    P = np.full((len(rows), len(tl)), np.nan)
    W = np.full((len(rows), len(tl)), np.nan)
    for k, (f, i) in enumerate(rows):
        for j, t in enumerate(tl):
            v = pooled[(pooled.mechanism == f) & (pooled.input == i) & (pooled.target == t)].importance_r2_drop
            if len(v):
                P[k, j] = max(v.iloc[0], 0)
            if (f, i, t) in within.index:
                W[k, j] = max(within[(f, i, t)], 0)
    fig, axes = plt.subplots(1, 2, figsize=(2 * (0.62 * len(tl) + 0.4) + 3.0, 0.3 * len(rows) + 1.3),
                             constrained_layout=True, sharey=True)
    for ax, M, name in ((axes[0], P, "One forest over all scenarios"),
                        (axes[1], W, "Forests within one scenario, mean")):
        ax.imshow(np.nan_to_num(M, nan=0), cmap=SEQUENTIAL, vmin=0, vmax=1, aspect="auto")
        for k in range(len(rows)):
            for j in range(len(tl)):
                if np.isfinite(M[k, j]):
                    ax.text(j, k, f"{M[k, j]:.2f}", ha="center", va="center", fontsize=6.8,
                            color=PAPER if M[k, j] > 0.55 else INK)
                else:
                    ax.text(j, k, "n/a", ha="center", va="center", fontsize=6.5, color=MUTED)
        ax.set_xticks(range(len(tl)), [target_label(spec, t).split(" ")[0] for t in tl], fontsize=7.5)
        ax.xaxis.tick_top()
        ax.tick_params(length=0)
        ax.set_title(name, fontsize=8, pad=18)
        for sp in ax.spines.values():
            sp.set_visible(False)
        for k in range(1, len(rows)):
            if rows[k][0] != rows[k - 1][0]:
                ax.axhline(k - 0.5, color=PAPER, lw=3)
    axes[0].set_yticks(range(len(rows)), [f"{family_label(f)}: {feature_label(i, False).lower()}" for f, i in rows])
    comb = pooled[(pooled.target == "goal__combined") & (pooled.test_r2 >= 0.1)]
    if comb.empty:
        title = "No forest predicts the combined utility from the inputs"
    else:
        top = comb.loc[comb.groupby("mechanism").importance_r2_drop.idxmax()]
        kind = top.input.map(lambda i: "setting" if i in layout["parameters"] else
                             "scenario" if i in layout["scenarios"] else "behaviour")
        lead = kind.value_counts().index[0]
        n = int((kind == lead).sum())
        what = {"setting": "The design's own setting", "scenario": "The scenario",
                "behaviour": "The validators' response"}[lead]
        title = (f"{what} is the strongest input to the combined utility in {n} of {len(top)} designs "
                 f"whose forest predicts it")
    names = ", ".join(f"{g['id']} {g['name']}" for g in spec["goals"])
    sub = (f"Fall in held-out R² when one input is shuffled, {fmt_horizon(horizon)}. A fall above 1 means the forest "
           f"then predicts worse than the mean. n/a: the input does not vary, or the utility spread is below 0.005."
           f"\nGoals: {names}.")
    headline(fig, title, sub)
    save(fig, folder, f"importance-{horizon}")
    return title


def figure_pass_rates(goals, spec, layout, horizon, folder):
    d = goals[(goals.horizon == horizon)]
    fams = sorted(d.mechanism.unique())
    scen = [s for s in dict.fromkeys(d.scenario) if s != "all"] + ["all"]
    cols = [g["id"] for g in spec["goals"]] + ["combined"]
    rows = [(f, s) for f in fams for s in scen if not d[(d.mechanism == f) & (d.scenario == s)].empty]
    M = np.array([[d[(d.mechanism == f) & (d.scenario == s) & (d.goal == g)].pass_rate.iloc[0] for g in cols]
                  for f, s in rows]) * 100
    fig, ax = plt.subplots(figsize=(0.95 * len(cols) + 3.3, 0.26 * len(rows) + 1.0), constrained_layout=True)
    ax.imshow(M, cmap=SEQUENTIAL, vmin=0, vmax=100, aspect="auto")
    for k in range(len(rows)):
        for j in range(len(cols)):
            ax.text(j, k, f"{M[k, j]:.0f}", ha="center", va="center", fontsize=7, color=PAPER if M[k, j] > 55 else INK)
    names = {g["id"]: f"{g['id']} {g['name']}" for g in spec["goals"]} | {"combined": "Every goal"}
    ax.set_xticks(range(len(cols)), [textwrap.fill(names[c], 16) for c in cols], fontsize=7.5)

    def row_name(f, s):
        if s == "all":
            return f"{family_label(f)}: all scenarios"
        r = d[(d.mechanism == f) & (d.scenario == s)].iloc[0]
        return f"{family_label(f)}: " + ", ".join(scenario_text(a, r[a]) for a in layout["scenarios"]).lower()

    ax.set_yticks(range(len(rows)), [row_name(f, s) for f, s in rows], fontsize=7)
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    for k in range(1, len(rows)):
        if rows[k][0] != rows[k - 1][0]:
            ax.axhline(k - 0.5, color=PAPER, lw=3)
    alls = d[(d.goal == "combined") & (d.scenario != "all")]
    if alls.empty:
        alls = d[d.goal == "combined"]
    best = alls.loc[alls.pass_rate.idxmax()]
    where = " and ".join(scenario_text(a, best[a]) for a in layout["scenarios"]).lower() or "all scenarios"
    title = (f"No design passes every goal in more than {best.pass_rate:.0%} of runs in any scenario"
             if best.pass_rate < spec["regions"]["pass_share"] else
             f"{family_label(best.mechanism)} passes every goal in {best.pass_rate:.0%} of runs at {where}")
    sub = f"Share of runs passing each goal's thresholds, %, {fmt_horizon(horizon)}."
    headline(fig, title, sub)
    save(fig, folder, f"pass-rates-{horizon}")
    return title


# Running -------------------------------------------------------------------------------------------------------------


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Scored:
    """A scored sweep: the runs with their utilities, the layout, the specification and the bin ranges."""

    def __init__(self, runs, layout, spec, manifest, ranges, inputs):
        self.runs, self.layout, self.spec, self.manifest, self.ranges, self.inputs = (
            runs, layout, spec, manifest, ranges, inputs)


def load_scored(wide, manifest_path, spec_path, blocks=None, log=print):
    """Read a sweep's design runs by its manifest, join their paired baselines and score them."""
    wide = str(Path(wide).expanduser().resolve())
    spec = load_spec(spec_path)
    manifest = manifest_io.load(manifest_path)
    style.apply()
    style.set_labels(features=manifest_io.labels(manifest), families=manifest.get("families"),
                     phrases=manifest.get("phrases"))
    con = duckdb.connect()
    layout = layout_from_manifest(con, wide, spec, manifest, blocks)
    log(f"blocks {layout['blocks']}, scenarios {layout['scenarios']}, settings {layout['parameters']}, "
        f"behaviour {layout['behaviour']}, horizon {layout['horizon']}")
    runs = score(read_runs(con, wide, layout), spec)
    ranges = input_ranges(runs, layout)
    log(f"scored {len(runs):,} runs")
    inputs = {"wide": wide, "wide_sha256": sha256(wide), "spec": str(Path(spec_path).expanduser().resolve()),
              "spec_sha256": sha256(Path(spec_path).expanduser()), "spec_name": spec.get("name"),
              "manifest": str(Path(manifest_path).expanduser().resolve()),
              "manifest_sha256": sha256(Path(manifest_path).expanduser())}
    return Scored(runs, layout, spec, manifest, ranges, inputs)


def run(scored, out, trees=300, repeats=10, jobs=8, seed=20261027, log=print):
    """Write the PSuU tables, the four figure kinds and run-config.json into `out`, and return the tables."""
    started = time.time()
    out = Path(out).expanduser()
    tables, figures = out / "tables", out / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    runs, layout, spec, ranges = scored.runs, scored.layout, scored.spec, scored.ranges

    keep = [c for c in runs.columns if not c.startswith("baseline__")]
    con = duckdb.connect()
    con.register("scored", runs[keep])
    con.execute(f"COPY scored TO '{tables / 'trajectory-utilities.parquet'}' (FORMAT parquet)")
    goals, metrics = summaries(runs, spec, layout)
    goals.to_csv(tables / "summary-goals.csv", index=False)
    metrics.to_csv(tables / "summary-metrics.csv", index=False)
    reg, cells = regions(runs, spec, layout, ranges)
    reg.to_csv(tables / "regions.csv", index=False)
    cells.to_csv(tables / "region-cells.csv", index=False)
    fit, imp, curves = forests(runs, spec, layout, ranges, trees, repeats, jobs, seed, log)
    fit.to_csv(tables / "forest-fit.csv", index=False)
    imp.to_csv(tables / "forest-importance.csv", index=False)
    curves.to_csv(tables / "response-curves.csv", index=False)

    titles = {}
    fam_col = layout["family"]
    for h in sorted(runs[layout["horizon"]].unique()):
        for axis in (layout["scenarios"] or [None]):
            titles[f"overview-{axis or 'pooled'}-{h}"] = figure_overview(runs, spec, layout, ranges, h, axis, figures)
        for fam in sorted(runs[fam_col].unique()):
            titles[f"response-{fam}-{h}"] = figure_family(runs, spec, layout, ranges, h, fam, curves, figures)
        titles[f"importance-{h}"] = figure_importance(imp, spec, layout, h, figures)
        titles[f"pass-rates-{h}"] = figure_pass_rates(goals, spec, layout, h, figures)
    titles = {k: v for k, v in titles.items() if v}

    config = {
        **scored.inputs, "rows_analysed": len(runs),
        "blocks": layout["blocks"], "scenario_axes": layout["scenarios"], "mechanism_settings": layout["parameters"],
        "behaviour_inputs": layout["behaviour"], "horizon_column": layout["horizon"],
        "baseline_columns": layout["paired"], "split_groups": layout["group"],
        "forest": {"trees": trees, "min_samples_leaf": 5, "max_features": 1.0, "test_share": 0.25,
                   "permutation_repeats": repeats, "seed": seed},
        "figure_titles": titles, "seconds": round(time.time() - started, 1),
    }
    (out / "run-config.json").write_text(json.dumps(config, indent=2, default=str) + "\n")
    log(f"wrote {out} in {config['seconds']} s")
    return {"goals": goals, "metrics": metrics, "regions": reg, "cells": cells, "fit": fit, "importance": imp,
            "curves": curves, "titles": titles, "config": config}
