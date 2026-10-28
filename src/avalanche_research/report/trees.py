"""Readable decision trees from a design's settings to the pass or fail of each goal and each KPI.

For each horizon, each design with a setting to choose and each target, a classification tree of depth three is fitted
from the design's settings and the scenario axes to whether a run passes. Targets are every goal, every goal at once
and every KPI of the utility specification, each against its declared threshold.

The trees are for reading. They describe where in the swept settings runs pass, and they make no causal claim. Their
accuracy is measured out of fold: runs are split into five folds by the column that groups runs sharing random draws,
each fold is predicted by a tree fitted on the other four, and the accuracy of those predictions is set beside the
accuracy of always predicting the larger class. Permutation importance is measured on the same held-out folds.
"""

from __future__ import annotations

import textwrap

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeClassifier

from . import style
from .psuu import design_matrix, metrics_of, settings_of
from .style import (INK, INK2, MUTED, PAPER, PASS_FAIL, family_label, feature_label, feature_value, fmt_horizon,
                    headline, save)

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

DEPTH = 3
FOLDS = 5


def tree_targets(spec):
    """(column, kind, label) for each goal pass, the all-goal pass and each KPI pass."""
    out = [(f"goalpass__{g['id']}", "goal", f"{g['id']} {g['name']}") for g in spec["goals"]]
    out.append(("goalpass__combined", "goal", "Every goal"))
    out += [(f"pass__{m['id']}", "kpi", m.get("label", m["id"])) for _, m in metrics_of(spec)]
    return out


def min_leaf(n):
    return max(20, int(0.02 * n))


def out_of_fold(X, y, groups, seed):
    """Out-of-fold predictions of a depth-three tree, the majority-class predictions and permutation importances."""
    n_groups = len(np.unique(groups))
    folds = min(FOLDS, n_groups)
    pred = np.zeros(len(y), dtype=bool)
    majority = np.zeros(len(y), dtype=bool)
    drops = np.zeros(X.shape[1])
    rng = np.random.default_rng(seed)
    for train, test in GroupKFold(n_splits=folds).split(X, y, groups):
        model = DecisionTreeClassifier(max_depth=DEPTH, min_samples_leaf=min_leaf(len(train)), random_state=seed)
        model.fit(X.iloc[train], y[train])
        pred[test] = model.predict(X.iloc[test])
        majority[test] = y[train].mean() >= 0.5
        base = (pred[test] == y[test]).mean()
        for k in range(X.shape[1]):
            Z = X.iloc[test].copy()
            Z.iloc[:, k] = rng.permutation(Z.iloc[:, k].to_numpy())
            drops[k] += (base - (model.predict(Z) == y[test]).mean()) * len(test) / len(y)
    return pred, majority, drops


def balanced_accuracy(y, pred):
    parts = [(pred[y == c] == c).mean() for c in (True, False) if (y == c).any()]
    return float(np.mean(parts))


def path_rules(model, names):
    """For each leaf: its conditions as {feature: [low, high]}, its runs and its pass share."""
    t = model.tree_
    out = []

    def walk(node, bounds):
        if t.children_left[node] == -1:
            out.append((node, dict(bounds), int(t.n_node_samples[node]), node_share(model, node)))
            return
        f, thr = names[t.feature[node]], t.threshold[node]
        lo, hi = bounds.get(f, (-np.inf, np.inf))
        walk(t.children_left[node], {**bounds, f: (lo, min(hi, thr))})
        walk(t.children_right[node], {**bounds, f: (max(lo, thr), hi)})

    walk(0, {})
    return out


def condition_text(bounds, codes):
    parts = []
    for f, (lo, hi) in bounds.items():
        name = feature_label(f, False).lower()
        if f in codes:
            cats = [c for k, c in enumerate(codes[f]) if lo < k <= hi]
            parts.append(f"{name} {', '.join(map(str, cats))}")
        elif np.isfinite(lo) and np.isfinite(hi):
            parts.append(f"{name} from {feature_value(f, lo)} to {feature_value(f, hi)}")
        elif np.isfinite(hi):
            parts.append(f"{name} at most {feature_value(f, hi)}")
        else:
            parts.append(f"{name} above {feature_value(f, lo)}")
    return " and ".join(parts) if parts else "every run"


def node_share(model, node):
    t = model.tree_
    v = t.value[node][0]
    classes = list(model.classes_)
    return float(v[classes.index(True)] / v.sum()) if True in classes else 0.0


def draw_tree(ax, model, names, codes):
    """Draw the fitted tree: split nodes state their rule, every node its runs and pass share, coloured by share."""
    t = model.tree_
    positions, leaf_x = {}, [0]

    def place(node, depth):
        if t.children_left[node] == -1:
            positions[node] = (leaf_x[0], depth)
            leaf_x[0] += 1
            return
        place(t.children_left[node], depth + 1)
        place(t.children_right[node], depth + 1)
        positions[node] = ((positions[t.children_left[node]][0] + positions[t.children_right[node]][0]) / 2, depth)

    place(0, 0)
    n_leaves = max(1, leaf_x[0])
    depth = max(d for _, d in positions.values())
    w, h = 0.9, 0.56
    for node, (x, d) in positions.items():
        for child, word in ((t.children_left[node], "yes"), (t.children_right[node], "no")):
            if child == -1:
                continue
            cx, cd = positions[child]
            ax.plot([x, cx], [-d - h / 2, -cd + h / 2], color=MUTED, lw=0.8, zorder=1)
            ax.text((x + cx) / 2, -(d + cd) / 2, word, fontsize=6.5, color=INK2, ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc=PAPER, ec="none"), zorder=2)
    for node, (x, d) in positions.items():
        share = node_share(model, node)
        colour = PASS_FAIL(share)
        ax.add_patch(FancyBboxPatch((x - w / 2, -d - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                    fc=colour, ec=MUTED, lw=0.6, zorder=3))
        ink = PAPER if share > 0.85 or share < 0.15 else INK
        lines = []
        if t.children_left[node] != -1:
            f, thr = names[t.feature[node]], t.threshold[node]
            if f in codes:
                left = [str(c) for k, c in enumerate(codes[f]) if k <= thr]
                rule = f"{feature_label(f, False)} is {', '.join(left)}"
            else:
                rule = f"{feature_label(f, False)} ≤ {feature_value(f, thr)}"
            lines.append(textwrap.fill(rule, 24))
        if t.children_left[node] != -1:
            lines.append(f"{share:.0%} pass of {int(t.n_node_samples[node]):,}")
        else:
            lines += [f"{share:.0%} pass", f"{int(t.n_node_samples[node]):,} runs"]
        ax.text(x, -d, "\n".join(lines), ha="center", va="center", fontsize=6.3, color=ink, zorder=4,
                weight="bold" if t.children_left[node] == -1 else "normal", linespacing=1.15)
    ax.set_xlim(-0.6, n_leaves - 0.4)
    ax.set_ylim(-depth - 0.6, 0.6)
    ax.axis("off")


def fit_one(frame, names, target, groups, seed):
    X = design_matrix(frame, names)
    y = frame[target].to_numpy(dtype=bool)
    pred, majority, drops = out_of_fold(X, y, groups, seed)
    model = DecisionTreeClassifier(max_depth=DEPTH, min_samples_leaf=min_leaf(len(y)), random_state=seed)
    model.fit(X, y)
    return model, {
        "oof_accuracy": float((pred == y).mean()), "oof_balanced_accuracy": balanced_accuracy(y, pred),
        "majority_accuracy": float((majority == y).mean()), "leaves": int(model.get_n_leaves()),
        "depth": int(model.get_depth()),
    }, drops


def figure_tree(model, names, codes, stats, drops, label, fam, horizon, n, pass_rate, folder, name):
    rules = path_rules(model, names)
    n_leaves = len(rules)
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(max(5.5, 1.1 * n_leaves + 2.6), 4.2),
                                 gridspec_kw={"width_ratios": [max(3.0, 1.05 * n_leaves), 1.6]},
                                 constrained_layout=True)
    draw_tree(ax, model, names, codes)
    order = np.argsort(drops)
    bx.barh(range(len(names)), np.maximum(drops[order], 0) * 100, color=style.MODEL_BLUE, height=0.4)
    bx.set_ylim(-0.7, len(names) - 0.3)
    bx.set_yticks(range(len(names)), [textwrap.fill(feature_label(names[k], False), 16) for k in order], fontsize=7)
    bx.set_xlabel("Accuracy lost when shuffled, points", fontsize=7)
    bx.set_title("Importance, held out", fontsize=8)
    bx.grid(axis="x", color=style.GRID, lw=0.6)
    bx.set_axisbelow(True)
    best = max(rules, key=lambda r: (r[3], r[2]))
    worst = min(rules, key=lambda r: (r[3], -r[2]))
    if best[3] - worst[3] < 0.05:
        title = f"{label}: {family_label(fam, True)} passes in {pass_rate:.0%} of runs wherever its settings sit"
    else:
        title = (f"{label}: {family_label(fam, True)} passes in {best[3]:.0%} of runs with "
                 f"{condition_text(best[1], codes)}, and in {worst[3]:.0%} with {condition_text(worst[1], codes)}")
    sub = (f"Depth-three tree for reading, fitted on {n:,} runs, {fmt_horizon(horizon)}. Out-of-fold accuracy "
           f"{stats['oof_accuracy']:.0%} against {stats['majority_accuracy']:.0%} for always predicting the larger "
           f"class, balanced accuracy {stats['oof_balanced_accuracy']:.0%}, {FOLDS} folds grouped by shared draws. "
           f"Box colour: share of runs that pass, red fails, blue passes.")
    headline(fig, title, sub)
    leaf_rows = pd.DataFrame([{"leaf": k, "conditions": condition_text(b, codes), "runs": r, "pass_share": s}
                              for k, (_, b, r, s) in enumerate(rules)])
    save(fig, folder, name, leaf_rows)
    return title, leaf_rows


def fit_all(scored, figures, seed=20261027, log=print):
    """Fit, score and draw every tree. Returns (fit table, importance table, leaf table, {figure name: title})."""
    runs, spec, layout = scored.runs, scored.spec, scored.layout
    style.apply()
    fit_rows, imp_rows, leaf_rows, titles = [], [], [], {}
    for h in sorted(runs[layout["horizon"]].unique()):
        for fam, frame in runs[runs[layout["horizon"]] == h].groupby(layout["family"], sort=True):
            params = settings_of(frame, layout)
            if not params:
                continue
            names = params + [a for a in layout["scenarios"] if frame[a].nunique() > 1]
            codes = {c: list(frame[c].astype("category").cat.categories) for c in names if frame[c].dtype == object}
            groups = frame[layout["group"]].to_numpy() if layout["group"] else np.arange(len(frame))
            for target, kind, label in tree_targets(spec):
                y = frame[target].astype(bool)
                base = {"horizon": h, "mechanism": fam, "target": target, "kind": kind, "label": label,
                        "inputs": ",".join(names), "runs": len(frame), "pass_rate": float(y.mean())}
                if y.all() or not y.any():
                    fit_rows.append({**base, "status": "every run passes" if y.all() else "no run passes"})
                    continue
                model, stats, drops = fit_one(frame, names, target, groups, seed)
                fit_rows.append({**base, "status": "fitted", **stats})
                for k, name in enumerate(names):
                    imp_rows.append({**base, "input": name, "oof_accuracy_drop": float(drops[k])})
                if stats["leaves"] < 2:
                    continue
                fig_name = f"tree-{fam}-{target.split('__', 1)[1]}-{h}"
                titles[fig_name], leaves = figure_tree(model, names, codes, stats, drops, label, fam, h, len(frame),
                                                       float(y.mean()), figures, fig_name)
                leaf_rows += [{**base, **r} for r in leaves.to_dict("records")]
    log(f"  trees: {len(fit_rows)} targets, {len(titles)} drawn")
    return pd.DataFrame(fit_rows), pd.DataFrame(imp_rows), pd.DataFrame(leaf_rows), titles
