"""Grouped nested CART on complete caller-declared labels and design blocks.

The reviewed calculation has no I/O, inferred thresholds or outcome filtering.
"""
import itertools
import json
import math

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor


class Refused(ValueError):
    """The complete declared design cannot be assessed under this contract."""


CCP_ALPHAS = (0., .0001, .001, .01, .05, .1, .25, .5)
OUTER_SPLITS, INNER_SPLITS = 10, 5


def _aligned(X, outcomes, names):
    if np.ndim(outcomes) != 1:
        raise Refused("outcomes must be a one-dimensional complete vector")
    if isinstance(X, pd.DataFrame):
        if not X.columns.is_unique or not X.index.is_unique or list(X.columns) != list(names):
            raise Refused("DataFrame feature names/order/index differ")
        if isinstance(outcomes, pd.Series) and not X.index.equals(outcomes.index):
            raise Refused("outcomes are not aligned with feature index/order")


def _scope(scope):
    """One frozen family/yield/horizon; row provenance remains caller-owned."""
    if not isinstance(scope, dict):
        raise Refused("scope must declare family, competing_yield_pp and horizon_days")
    _text(scope.get("family"), "scope.family")
    value = scope.get("competing_yield_pp")
    if type(value) not in (int, float) or not math.isfinite(value):
        raise Refused("scope.competing_yield_pp must be finite")
    if type(scope.get("horizon_days")) is not int or scope["horizon_days"] not in (180, 365):
        raise Refused("scope.horizon_days must be 180 or 365")
    return dict(scope)


def _bootstrap(correct, reference, block_ids, indices):
    """Resample complete units using the caller's fixed joint index matrix."""
    if _has_explicit_mask(indices):
        raise Refused("bootstrap indices contain missing values")
    order = sorted(set(block_ids))
    if not order:
        raise Refused("bootstrap needs nonempty complete blocks")
    draw = np.asarray(indices)
    if draw.shape != (1000, len(order)) or draw.dtype.kind not in "iu":
        raise Refused("bootstrap_indices must be native integer shape (1000, distinct blocks)")
    if (draw < 0).any() or (draw >= len(order)).any():
        raise Refused("bootstrap index outside sorted distinct block order")
    position = {name: i for i, name in enumerate(order)}
    code = np.array([position[name] for name in block_ids])
    count = np.bincount(code, minlength=len(order))
    value = np.bincount(code, weights=correct, minlength=len(order))
    difference = np.bincount(code, weights=correct-reference, minlength=len(order))
    denominator = count[draw].sum(axis=1)
    raw = value[draw].sum(axis=1)/denominator
    paired = difference[draw].sum(axis=1)/denominator
    return {"unit_order": order, "replicates": 1000, "confidence": .95,
            "raw_interval95": np.quantile(raw, [.025, .975]).tolist(),
            "paired_interval95": np.quantile(paired, [.025, .975]).tolist()}


def analyze_cart(X, labels, *, sample_ids, block_ids, feature_names, scope,
                 bootstrap_indices, label_definition, independence_statement,
                 seed=20261005):
    """Frozen MM2 classification with paired-unit OOF uncertainty.

    Bootstrap columns index sorted distinct block IDs. The caller freezes the
    1000 draws jointly across measures, costs and contexts before reading outcomes.
    Every row must already be an eligible A or B row of the declared scope.
    """
    scope = _scope(scope)
    _aligned(X, labels, feature_names)
    # Validate caller draws even when no class contrast can be fitted.
    groups = _strings(block_ids, len(labels), "block_ids")
    _bootstrap(np.zeros(len(groups)), np.zeros(len(groups)), groups, bootstrap_indices)
    try:
        result = analyze_mm2(X, labels, sample_ids=sample_ids, block_ids=groups,
            feature_names=feature_names, stratum_id=json.dumps(scope, sort_keys=True),
            target_id=scope.get("measure", "caller-declared threshold"),
            label_definition=label_definition, independence_statement=independence_statement,
            ccp_alphas=CCP_ALPHAS, outer_splits=OUTER_SPLITS, inner_splits=INNER_SPLITS, seed=seed)
    except Refused as error:
        if any(term in str(error) for term in ("one-class", "both classes required", "insufficient distinct blocks")):
            return {"status": "unassessable", "reason": str(error), "scope": scope,
                    "target_type": "classification", "informative": None, "margin": None,
                    "accuracy_interval95": None, "paired_difference_interval95": None,
                    "outer_splits": OUTER_SPLITS, "inner_splits": INNER_SPLITS,
                    "ccp_alphas": list(CCP_ALPHAS)}
        raise
    rows = result["held_out_predictions"]
    correct = np.array([r["predicted_met"] == r["met"] for r in rows], dtype=float)
    majority = np.array([r["majority_baseline_met"] == r["met"] for r in rows], dtype=float)
    interval = _bootstrap(correct, majority, groups, bootstrap_indices)
    result.update(status="ok", scope=scope, target_type="classification",
        accuracy_interval95=interval["raw_interval95"],
        paired_difference_interval95=interval["paired_interval95"],
        margin=interval["paired_interval95"][0], informative=interval["paired_interval95"][0] > 0,
        raw_accuracy_low_minus_majority_display=interval["raw_interval95"][0]-float(majority.mean()),
        interval_basis="Paired OOF correctness minus its training-fold majority correctness; whole Saltelli units",
        bootstrap=interval)
    return result


def _reg_splits(indices, y, groups, ids, count, seed, stage):
    if len(set(groups[indices])) < count:
        raise Refused(f"{stage}: insufficient distinct blocks for {count} folds")
    result = []
    for fold, (tr, va) in enumerate(GroupKFold(n_splits=count, shuffle=True, random_state=seed).split(indices, y[indices], groups[indices])):
        train, valid = indices[tr], indices[va]
        def support(ix):
            return {"n": len(ix), "groups": sorted(set(groups[ix].tolist())),
                    "sample_ids": [ids[i] for i in ix], "mean": float(y[ix].mean())}
        result.append((train, valid, {"fold": fold, "train": support(train), "held_out": support(valid)}))
    return result


def _reg_fit(X, y, indices, alpha, seed, stage):
    return DecisionTreeRegressor(criterion="squared_error", splitter="best", ccp_alpha=alpha,
        random_state=seed).fit(X[indices], y[indices])


def _reg_select(X, y, indices, groups, ids, seed, stage):
    splits = _reg_splits(indices, y, groups, ids, INNER_SPLITS, seed, stage)
    scores = []
    for alpha in CCP_ALPHAS:
        losses = []
        for train, valid, receipt in splits:
            model = _reg_fit(X, y, train, alpha, seed, stage+f"/fold{receipt['fold']}")
            losses.append(float(np.mean((model.predict(X[valid])-y[valid])**2)))
        scores.append({"ccp_alpha": alpha, "fold_mse": losses, "mean_negative_mse": -float(np.mean(losses))})
    alpha = max(scores, key=lambda value: (value["mean_negative_mse"], value["ccp_alpha"]))["ccp_alpha"]
    return alpha, {"folds": [r for _, _, r in splits], "scores": scores, "selected_ccp_alpha": alpha}


def analyze_regression_cart(X, values, *, sample_ids, block_ids, feature_names,
                            scope, bootstrap_indices, independence_statement, seed=20261005):
    """Continuous-KPI descriptive trees and honest grouped OOF MSE/R2.

    No pass/fail threshold or classification acceptance rule is inferred. The
    regression tree's negative-MSE tuning uses the same fixed groups and grid.
    """
    scope = _scope(scope)
    _aligned(X, values, feature_names)
    _text(independence_statement, "independence_statement")
    _integer(seed, "seed", 0, 2**32-1)
    if _has_explicit_mask(X) or _has_explicit_mask(values):
        raise Refused("explicitly masked entries are missing")
    X, y = np.asarray(X), np.asarray(values)
    if X.ndim != 2 or min(X.shape, default=0) < 1 or X.dtype.kind not in "iuf" or y.ndim != 1 or y.dtype.kind not in "iuf" or len(y) != len(X):
        raise Refused("complete numeric feature matrix and continuous vector required")
    X, y = X.astype(float, copy=True), y.astype(float, copy=True)
    with np.errstate(over="ignore"):
        if not np.isfinite(X.astype(np.float32)).all() or not np.isfinite(y).all():
            raise Refused("finite float32-range features and finite outcomes required")
    ids = _strings(sample_ids, len(y), "sample_ids", unique=True)
    groups = np.asarray(_strings(block_ids, len(y), "block_ids"))
    names = _strings(feature_names, X.shape[1], "feature_names", unique=True)
    _bootstrap(np.zeros(len(y)), np.zeros(len(y)), groups, bootstrap_indices)
    indices = np.arange(len(y))
    try:
        outer = _reg_splits(indices, y, groups, ids, OUTER_SPLITS, seed, "outer")
        for fold, (train, _, _) in enumerate(outer):
            _reg_splits(train, y, groups, ids, INNER_SPLITS, (seed+fold+1) % 2**32, "inner")
    except Refused as error:
        return {"status": "unassessable", "reason": str(error), "scope": scope,
                "target_type": "regression", "informative": None, "informative_reason": "policy_not_prescribed"}
    predictions, baseline = np.empty(len(y)), np.empty(len(y))
    receipts = []
    for fold, (train, test, receipt) in enumerate(outer):
        alpha, selection = _reg_select(X, y, train, groups, ids, (seed+fold+1) % 2**32, f"outer{fold}/inner")
        model = _reg_fit(X, y, train, alpha, seed, f"outer{fold}/fit")
        predictions[test] = model.predict(X[test]); baseline[test] = y[train].mean()
        receipt.update(selection=selection, training_mean=float(y[train].mean()),
                       held_out_mse=float(np.mean((predictions[test]-y[test])**2)))
        receipts.append(receipt)
    alpha, selection = _reg_select(X, y, indices, groups, ids, seed, "final/inner")
    model = _reg_fit(X, y, indices, alpha, seed, "final/descriptive")
    tree = model.tree_; paths = model.decision_path(X).tocsc(); nodes = []; lines = ["digraph CART {"]
    for node in range(tree.node_count):
        members = paths.indices[paths.indptr[node]:paths.indptr[node+1]]
        leaf = bool(tree.children_left[node] == -1)
        record = {"node": node, "n": len(members), "mean": float(y[members].mean()), "leaf": leaf}
        label = f"n={len(members)}, mean={record['mean']:.9g}"
        if not leaf:
            feature = int(tree.feature[node]); threshold = float(tree.threshold[node])
            record.update(feature=names[feature], feature_index=feature, threshold=threshold,
                          left=int(tree.children_left[node]), right=int(tree.children_right[node]))
            label = f"{names[feature]} <= {threshold:.17g}\n"+label
            lines.extend([f'{node} -> {record["left"]} [label="yes"];', f'{node} -> {record["right"]} [label="no"];'])
        nodes.append(record); lines.append(f"{node} [label={json.dumps(label)}];")
    lines.append("}")
    error, reference = (predictions-y)**2, (baseline-y)**2
    variance = float(np.mean((y-y.mean())**2))
    uncertainty = _bootstrap(error, reference, groups, bootstrap_indices)
    return {"status": "ok", "target_type": "regression", "scope": scope, "seed": seed,
        "outer_splits": OUTER_SPLITS, "inner_splits": INNER_SPLITS, "ccp_alphas": list(CCP_ALPHAS),
        "selection_metric": "unweighted mean inner-fold negative MSE; exact ties choose largest alpha",
        "outer_folds": receipts, "held_out_mse": float(error.mean()), "training_mean_baseline_mse": float(reference.mean()),
        "held_out_r2": 1-float(error.mean())/variance if variance > 0 else None,
        "r2_reason": None if variance > 0 else "constant_target",
        "mse_interval95": uncertainty["raw_interval95"], "mse_minus_mean_baseline_interval95": uncertainty["paired_interval95"],
        "informative": None, "informative_reason": "policy_not_prescribed", "margin": None,
        "accuracy_interval95": None, "independence_statement": independence_statement,
        "held_out_predictions": [{"sample_id": ids[i], "block_id": str(groups[i]), "value": float(y[i]),
            "prediction": float(predictions[i]), "training_mean_baseline": float(baseline[i])} for i in indices],
        "final_tree": {"nodes": nodes, "depth": int(model.get_depth()), "leaves": int(model.get_n_leaves()),
            "selected_ccp_alpha": alpha, "selection": selection, "dot": "\n".join(lines),
            "impurity_importance": dict(zip(names, model.feature_importances_.tolist())),
            "role": "descriptive all-data regression fit; independent accuracy is OOF only"}}


def _has_explicit_mask(value):
    if np.ma.isMaskedArray(value):
        return bool(np.any(np.ma.getmaskarray(value)))
    # np.asarray also strips masks from masked rows inside ordinary sequences.
    if isinstance(value, (list, tuple)):
        return any(_has_explicit_mask(item) for item in value)
    return False


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise Refused(f"{name}: nonempty string required")
    return value


def _strings(values, size, name, unique=False):
    if isinstance(values, (str, bytes)):
        raise Refused(f"{name}: sequence required")
    try:
        values = list(values)
    except TypeError as exc:
        raise Refused(f"{name}: sequence required") from exc
    if len(values) != size:
        raise Refused(f"{name}: wrong length")
    for value in values:
        _text(value, name)
    if unique and len(set(values)) != size:
        raise Refused(f"{name}: identifiers must be unique")
    return values


def _integer(value, name, low, high=None):
    if type(value) is not int or value < low or (high is not None and value > high):
        raise Refused(f"{name}: native integer in declared range required")
    return value


def _support(indices, y, groups, ids):
    return {"n": len(indices), "not_met": int(np.sum(~y[indices])),
            "met": int(np.sum(y[indices])),
            "groups": sorted(set(groups[indices].tolist())),
            "sample_ids": [ids[i] for i in indices]}


def _splits(indices, y, groups, ids, count, seed, stage):
    if len(set(groups[indices])) < count:
        raise Refused(f"{stage}: insufficient distinct blocks for {count} folds")
    splitter = GroupKFold(n_splits=count, shuffle=True, random_state=seed)
    result = []
    for fold, (tr, va) in enumerate(splitter.split(indices, y[indices], groups[indices])):
        train, valid = indices[tr], indices[va]
        if len(np.unique(y[train])) != 2 or len(np.unique(y[valid])) != 2:
            raise Refused(f"{stage}/fold{fold}: both classes required in train and held-out support")
        result.append((train, valid, {"fold": fold,
            "train": _support(train, y, groups, ids),
            "held_out": _support(valid, y, groups, ids)}))
    return result


def _fit(X, y, indices, alpha, seed, stage):
    # stage is an audit hook for synthetic isolation tests, not a data-dependent choice.
    return DecisionTreeClassifier(criterion="gini", splitter="best", class_weight=None,
        ccp_alpha=alpha, random_state=seed).fit(X[indices], y[indices])


def _metrics(y, pred):
    # Both labels are required before this function is called.
    return {"raw_accuracy": float(np.mean(y == pred)),
            "balanced_accuracy": float((np.mean(pred[y]) + np.mean(~pred[~y])) / 2)}


def _select(X, y, indices, groups, ids, grid, count, seed, stage):
    splits = _splits(indices, y, groups, ids, count, seed, stage)
    scores = []
    for alpha in grid:
        metrics = []
        for train, valid, receipt in splits:
            model = _fit(X, y, train, alpha, seed, stage + f"/fold{receipt['fold']}")
            metrics.append(_metrics(y[valid], model.predict(X[valid])))
        scores.append({"ccp_alpha": alpha, "fold_metrics": metrics,
            "mean_balanced_accuracy": float(np.mean([m["balanced_accuracy"] for m in metrics]))})
    # Exact ties prefer the largest declared alpha. No tolerance or test labels used.
    selected = max(scores, key=lambda s: (s["mean_balanced_accuracy"], s["ccp_alpha"]))["ccp_alpha"]
    return selected, {"folds": [r for _, _, r in splits], "scores": scores,
                      "selected_ccp_alpha": selected}


def _tree_receipt(model, X, y, names):
    tree = model.tree_
    paths = model.decision_path(X).tocsc()
    nodes, lines = [], ["digraph CART {"]
    for node in range(tree.node_count):
        members = paths.indices[paths.indptr[node]:paths.indptr[node + 1]]
        met, total = int(np.sum(y[members])), len(members)
        leaf = bool(tree.children_left[node] == -1)
        receipt = {"node": node, "n": total, "met": met, "not_met": total-met,
                   "share_met": met/total, "leaf": leaf,
                   "predict_met": bool(met > total-met)}
        label = f"n={total}, met={met}/{total} ({met/total:.6g})"
        if not leaf:
            feature = int(tree.feature[node])
            receipt.update(feature=names[feature], feature_index=feature,
                           threshold=float(tree.threshold[node]),
                           left=int(tree.children_left[node]), right=int(tree.children_right[node]))
            label = f"{names[feature]} <= {tree.threshold[node]:.17g}\n" + label
        nodes.append(receipt)
        lines.append(f"  {node} [label={json.dumps(label)}];")
        if not leaf:
            lines.extend([f'  {node} -> {tree.children_left[node]} [label="yes"];',
                          f'  {node} -> {tree.children_right[node]} [label="no"];'])
    lines.append("}")
    return {"nodes": nodes, "depth": int(model.get_depth()), "leaves": int(model.get_n_leaves()),
            "dot": "\n".join(lines),
            "impurity_importance": dict(zip(names, model.feature_importances_.tolist()))}


def analyze_mm2(X, labels, *, sample_ids, block_ids, feature_names, stratum_id,
                target_id, label_definition, independence_statement, ccp_alphas,
                outer_splits, inner_splits, seed):
    """Return JSON-compatible nested-CV receipts and a descriptive fitted CART.

    labels must already be complete Boolean indicators of one frozen caller-owned
    KPI threshold. Each block is kept whole. No failed/missing rows are dropped.
    All rows belong to the one caller-declared stratum/target. Caller establishes
    block independence, temporal eligibility and compatible response/design families.
    """
    for name, value in (("stratum_id", stratum_id), ("target_id", target_id),
                        ("label_definition", label_definition),
                        ("independence_statement", independence_statement)):
        _text(value, name)
    outer_splits = _integer(outer_splits, "outer_splits", 2)
    inner_splits = _integer(inner_splits, "inner_splits", 2)
    seed = _integer(seed, "seed", 0, 2**32 - 1)
    # np.asarray strips MaskedArray masks. Refuse missing entries before any
    # coercion can expose their underlying storage. An all-false mask is complete.
    for value, name in ((X, "X"), (labels, "labels")):
        if _has_explicit_mask(value):
            raise Refused(f"{name}: explicitly masked entries are missing; no dropping or imputation")
    try:
        raw, y = np.asarray(X), np.asarray(labels)
    except (TypeError, ValueError) as exc:
        raise Refused("rectangular numeric X and Boolean labels required") from exc
    if raw.ndim != 2 or min(raw.shape, default=0) < 1 or raw.dtype.kind not in "iuf":
        raise Refused("X: nonempty two-dimensional real numeric array required")
    if y.ndim != 1 or y.dtype.kind != "b" or len(y) != len(raw):
        raise Refused("labels: complete one-dimensional Boolean vector required")
    X = raw.astype(np.float64, copy=True)
    y = y.copy()
    if not np.all(np.isfinite(X)):
        raise Refused("X: all values must be finite; no dropping or imputation")
    # sklearn CART evaluates numeric features at float32 precision.
    with np.errstate(over="ignore", invalid="ignore"):
        if not np.all(np.isfinite(X.astype(np.float32))):
            raise Refused("X: outside finite sklearn float32 feature range")
    n, p = X.shape
    ids = _strings(sample_ids, n, "sample_ids", unique=True)
    groups = np.asarray(_strings(block_ids, n, "block_ids"), dtype=str)
    names = _strings(feature_names, p, "feature_names", unique=True)
    if isinstance(ccp_alphas, (str, bytes)):
        raise Refused("ccp_alphas: explicit sequence required")
    try:
        grid = list(ccp_alphas)
    except TypeError as exc:
        raise Refused("ccp_alphas: explicit sequence required") from exc
    if not grid or any(type(a) not in (int, float) for a in grid):
        raise Refused("ccp_alphas: finite nonnegative native real values required")
    try:
        grid = [float(a) for a in grid]
    except (ValueError, OverflowError) as exc:
        raise Refused("ccp_alphas: outside finite real range") from exc
    if any(not math.isfinite(a) or a < 0 for a in grid):
        raise Refused("ccp_alphas: finite nonnegative native real values required")
    if any(a >= b for a, b in itertools.pairwise(grid)):
        raise Refused("ccp_alphas: strictly increasing preregistered grid required")
    if len(np.unique(y)) != 2:
        raise Refused("target: one-class labels are unassessable")
    indices = np.arange(n)
    outer = _splits(indices, y, groups, ids, outer_splits, seed, "outer")
    # Validate all inner support before fitting anything, with no outcome-driven retry.
    for fold, (train, _, _) in enumerate(outer):
        _splits(train, y, groups, ids, inner_splits, (seed+fold+1) % 2**32, f"outer{fold}/inner")
    _splits(indices, y, groups, ids, inner_splits, seed, "final/inner")
    predictions, baseline = np.empty(n, dtype=bool), np.empty(n, dtype=bool)
    receipts = []
    for fold, (train, test, receipt) in enumerate(outer):
        alpha, selection = _select(X, y, train, groups, ids, grid, inner_splits,
                                  (seed+fold+1) % 2**32, f"outer{fold}/inner")
        model = _fit(X, y, train, alpha, seed, f"outer{fold}/fit")
        predictions[test] = model.predict(X[test])
        majority = bool(np.sum(y[train]) > len(train)/2)
        baseline[test] = majority
        receipt.update(selection=selection, selected_ccp_alpha=alpha,
                       held_out_metrics=_metrics(y[test], predictions[test]),
                       training_majority_met=majority,
                       held_out_majority_baseline=_metrics(y[test], baseline[test]))
        receipts.append(receipt)
    alpha, final_selection = _select(X, y, indices, groups, ids, grid, inner_splits, seed, "final/inner")
    model = _fit(X, y, indices, alpha, seed, "final/descriptive")
    final = _tree_receipt(model, X, y, names)
    final.update(selected_ccp_alpha=alpha, selection=final_selection,
                 role="descriptive fit to all supplied rows; no independent accuracy claim")
    return {"method": "MM2 grouped nested-CV CART", "stratum_id": stratum_id,
            "target_id": target_id, "label_definition": label_definition,
            "independence_statement": independence_statement, "seed": seed,
            "outer_splits": outer_splits, "inner_splits": inner_splits, "ccp_alphas": grid,
            "selection_metric": "unweighted mean inner-fold balanced accuracy; exact ties choose largest alpha",
            "support": _support(indices, y, groups, ids), "outer_folds": receipts,
            "held_out_metrics": _metrics(y, predictions),
            "held_out_majority_baseline": _metrics(y, baseline),
            "aggregation": "pooled out-of-fold rows, each row once; raw accuracy weights rows equally; balanced accuracy averages pooled class recalls",
            "held_out_predictions": [{"sample_id": ids[i], "block_id": groups[i],
                "met": bool(y[i]), "predicted_met": bool(predictions[i]),
                "majority_baseline_met": bool(baseline[i])} for i in range(n)],
            "constant_features": [names[j] for j in range(p) if np.all(X[:, j] == X[0, j])],
            "final_tree": final,
            "limitations": ["caller authenticates source bytes and scientific scope; no causal claim",
                "caller owns frozen threshold, complete eligible rows, blocks, chronology and per-response/family separation",
                "group isolation does not prove independence, temporal validity or E2 pairing",
                "raw kernel has no interval; wrapper uses caller-supplied whole-block draws; folds are not independent; no split-stability study",
                "CART internally quantizes features to float32; close values may merge",
                "impurity importance is descriptive and may split correlated feature credit unstably"]}
