"""Deterministic numeric peeling/pasting PRIM with A discovery and B confirmation.

This is an original, mean-objective numerical PRIM implementation, not EMA
Workbench. One greedy trajectory is searched, without CART or B-guided tuning.
"""
import math

import numpy as np
import pandas as pd

PEEL_ALPHA, PASTE_ALPHA, MIN_MASS = .05, .05, .05
MIN_COVERAGE, MIN_DENSITY = .7, .7


class Refused(ValueError):
    """Incomplete or misaligned caller input cannot be analysed."""


def _masked(value):
    if np.ma.isMaskedArray(value):
        return bool(np.ma.getmaskarray(value).any())
    return isinstance(value, (tuple, list)) and any(_masked(item) for item in value)


def _input(X, failed, names, ids, label):
    if _masked(X) or _masked(failed):
        raise Refused("masked observations cannot be coerced or dropped")
    if isinstance(X, pd.DataFrame):
        if list(X.columns) != names or not X.columns.is_unique or not X.index.is_unique:
            raise Refused("DataFrame feature names/order/index differ")
        if isinstance(failed, pd.Series) and not X.index.equals(failed.index):
            raise Refused("labels are not aligned with feature index/order")
    X, failed = np.asarray(X), np.asarray(failed)
    if X.ndim != 2 or X.shape[1] != len(names) or X.dtype.kind not in "iuf":
        raise Refused("complete numeric feature matrix required")
    if failed.ndim != 1 or failed.dtype.kind != "b" or len(failed) != len(X):
        raise Refused("failure labels must be complete Boolean observations")
    if not np.isfinite(X).all():
        raise Refused("nonfinite feature observations are not dropped")
    if isinstance(ids, (str, bytes)):
        raise Refused("sample IDs must be a unique sequence")
    ids = list(ids)
    if len(ids) != len(X) or len(set(ids)) != len(ids) or any(not isinstance(v, str) or not v for v in ids):
        raise Refused(label+" IDs must be complete unique strings")
    # IDs and corresponding whole rows move together. Numeric quantiles and
    # canonical tie breaks do not depend on caller row order.
    order = np.argsort(np.asarray(ids), kind="stable")
    return X[order].astype(float, copy=True), failed[order].copy(), [ids[i] for i in order]


def _inside(X, bounds):
    return ((X >= bounds[0]) & (X <= bounds[1])).all(axis=1)


def _stats(X, y, bounds):
    mask = _inside(X, bounds); n = int(mask.sum()); cases = int(y[mask].sum()); total = int(y.sum())
    return {"runs_in_box": n, "failing_in_box": cases, "failures": total,
            "coverage": cases/total if total else None, "density": cases/n if n else None,
            "mass": n/len(X) if len(X) else None}


def _candidate(X, y, bounds, original, names, operation):
    stats = _stats(X, y, bounds)
    restricted = np.any(bounds != original, axis=0)
    return {"bounds": [{"feature": name, "lower": float(bounds[0, j]), "upper": float(bounds[1, j]),
                         "restricted": bool(restricted[j])} for j, name in enumerate(names)],
            "discovery": stats, "restricted_dimensions": int(restricted.sum()), "operation": operation}


def _canonical(candidate):
    return tuple((r["feature"], r["lower"], r["upper"]) for r in candidate["bounds"])


def _selection_key(candidate):
    s = candidate["discovery"]
    return (-s["coverage"], -s["density"], candidate["restricted_dimensions"], _canonical(candidate))


def _search(X, y, names):
    original = np.stack([X.min(axis=0), X.max(axis=0)])
    bounds = original.copy(); path = [_candidate(X, y, bounds, original, names, "initial")]
    path[0]["path_index"] = 0
    if y.all():
        return path
    minimum = math.ceil(MIN_MASS*len(X))
    while True:
        current = _inside(X, bounds); n = int(current.sum()); options = []
        for j in range(X.shape[1]):
            values = np.unique(X[current, j])
            if len(values) < 2:
                continue
            for side in (0, 1):
                q = float(np.quantile(X[current, j], PEEL_ALPHA if side == 0 else 1-PEEL_ALPHA))
                q = max(q, values[1]) if side == 0 else min(q, values[-2])
                new = bounds.copy(); new[side, j] = q
                result = _candidate(X, y, new, original, names, "peel")
                size = result["discovery"]["runs_in_box"]
                if minimum <= size < n:
                    options.append((result, new))
        if not options:
            break
        result, new = min(options, key=lambda pair: (-pair[0]["discovery"]["density"], *_selection_key(pair[0])))
        if result["discovery"]["density"] < path[-1]["discovery"]["density"]:
            break
        path.append(result); bounds = new
    # Paste the nearest five percent of current box mass on one face. Each
    # accepted paste strictly adds rows without reducing mean, so it terminates.
    while True:
        current = _inside(X, bounds); n = int(current.sum()); options = []
        add = max(1, math.ceil(PASTE_ALPHA*n))
        for j in range(X.shape[1]):
            other = np.ones(len(X), dtype=bool)
            for axis in range(X.shape[1]):
                if axis != j:
                    other &= (X[:, axis] >= bounds[0, axis]) & (X[:, axis] <= bounds[1, axis])
            for side in (0, 1):
                outside = np.sort(X[other & (X[:, j] < bounds[0, j] if side == 0 else X[:, j] > bounds[1, j]), j])
                if len(outside) == 0:
                    continue
                new = bounds.copy()
                new[side, j] = outside[-min(add, len(outside))] if side == 0 else outside[min(add, len(outside))-1]
                result = _candidate(X, y, new, original, names, "paste")
                if result["discovery"]["runs_in_box"] > n and result["discovery"]["density"] >= path[-1]["discovery"]["density"]:
                    options.append((result, new))
        if not options:
            break
        result, bounds = min(options, key=lambda pair: (-pair[0]["discovery"]["density"], *_selection_key(pair[0])))
        path.append(result)
    for index, candidate in enumerate(path):
        candidate["path_index"] = index
    return path


def discover_confirm(A, failed_A, B, failed_B, *, feature_names, scope,
                     sample_ids_A, sample_ids_B):
    """Choose an A-qualified box, then confirm its unchanged bounds on B once.

    Closed numeric intervals start at A's observed bounds. No rotation, multiple
    boxes, categorical peels, empirical significance or exhaustive-search claim.
    Inputs already belong to one frozen family/yield/horizon/failure condition.
    """
    if isinstance(feature_names, str):
        raise Refused("feature names must be a nonempty unique sequence")
    names = list(feature_names)
    if not names or len(set(names)) != len(names) or any(not isinstance(v, str) or not v for v in names):
        raise Refused("feature names must be nonempty unique strings")
    if not isinstance(scope, dict) or not isinstance(scope.get("family"), str) or not scope["family"]:
        raise Refused("declare one frozen family/yield/horizon scope")
    if type(scope.get("competing_yield_pp")) not in (int, float) or not math.isfinite(scope["competing_yield_pp"]) or type(scope.get("horizon_days")) is not int or scope["horizon_days"] not in (180, 365):
        raise Refused("declare finite competing_yield_pp and 180/365 horizon_days")
    A, y, ids_A = _input(A, failed_A, names, sample_ids_A, "A")
    B, future, ids_B = _input(B, failed_B, names, sample_ids_B, "B")
    if set(ids_A) & set(ids_B):
        raise Refused("A discovery and B confirmation sample IDs overlap")
    # Canonical feature order fixes face/box ties under aligned column reordering.
    order = np.argsort(names); names = [names[i] for i in order]; A = A[:, order]; B = B[:, order]
    result = {"method": "deterministic numeric mean-objective peeling/pasting PRIM", "scope": dict(scope),
        "settings": {"peel_alpha": PEEL_ALPHA, "paste_alpha": PASTE_ALPHA, "min_mass": MIN_MASS,
                     "min_coverage": MIN_COVERAGE, "min_density": MIN_DENSITY,
                     "selection": "A-qualified candidates: highest coverage, density, fewest restricted dimensions, canonical bounds"},
        "found": False, "selected_box": None, "confirmation": None, "path": [],
        "limitations": ["one greedy numerical PRIM trajectory, not EMA or exhaustive discovery",
                        "initial closed bounds use A only; points outside those observed bounds stay outside",
                        "caller authenticates A/B roles, complete outcomes and frozen scope"]}
    if len(A) == 0:
        return result | {"status": "unassessable", "reason": "empty_discovery"}
    if not y.any():
        return result | {"status": "not_found", "reason": "no_discovery_failures"}
    path = _search(A, y, names); result["path"] = path
    qualified = [c for c in path if c["discovery"]["coverage"] >= MIN_COVERAGE and c["discovery"]["density"] >= MIN_DENSITY]
    if not qualified:
        display = min(path, key=lambda c: (-c["discovery"]["density"], *_selection_key(c)))
        return result | {"status": "not_found", "reason": "no_A_qualified_box", "display_candidate": display}
    selected = min(qualified, key=_selection_key); result["selected_box"] = selected
    bounds = np.array([[r["lower"] for r in selected["bounds"]], [r["upper"] for r in selected["bounds"]]])
    if len(B) == 0:
        return result | {"status": "unassessable", "reason": "empty_confirmation"}
    confirmation = _stats(B, future, bounds); result["confirmation"] = confirmation
    result["confirmation_points"] = [{"sample_id": row, "failed": bool(value), "inside_box": bool(inside)} for row, value, inside in zip(ids_B, future, _inside(B, bounds))]
    if not future.any():
        return result | {"status": "not_found", "reason": "no_confirmation_failures"}
    found = confirmation["coverage"] >= MIN_COVERAGE and confirmation["density"] is not None and confirmation["density"] >= MIN_DENSITY
    return result | {"status": "found" if found else "not_found", "found": found,
                     "reason": "both_B_standards_met" if found else "B_confirmation_failed"}
