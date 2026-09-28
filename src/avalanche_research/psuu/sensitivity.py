"""Which controllable parameters decide whether goals pass, and the recommended parameter tiers.

- ``trees``: per KPI and per goal group, a depth-4 decision tree classifying pass or fail from the controllable
  parameters, with held-out accuracy, the majority-class accuracy it must beat, and feature importances.
- ``spearman``: rank correlation of each numeric controllable parameter with each KPI.
- ``recommendations``: the point estimate (the parameter set passing all goals in the largest share of
  trajectories), per-goal ranges, and the global range. A parameter set qualifies for a goal when that goal passes
  in at least 80% of its trajectories (scenarios x seeds). A range is the minimum to maximum of each parameter over
  the qualifying sets. It bounds them and does not guarantee that every point inside it qualifies.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

from .design import MECHANISMS, PARAMETER_RANGES
from .goals import GROUPS, KPI_NAMES, pass_shares
from .kpis import KPI_COLUMNS

NUMERIC = tuple(PARAMETER_RANGES)
QUALIFY_SHARE = 0.80
TREE_DEPTH = 4
TARGETS = (*KPI_NAMES, *GROUPS, "all")


def features(results: pd.DataFrame) -> pd.DataFrame:
    """Numeric controllable parameters plus one indicator per mechanism."""
    frame = results[list(NUMERIC)].astype(float).copy()
    for name in MECHANISMS:
        frame[f"mechanism={name}"] = (results["mechanism"] == name).astype(float)
    return frame


def _parameter_of(feature: str) -> str:
    return "mechanism" if feature.startswith("mechanism=") else feature


def trees(evaluated: pd.DataFrame, seed: int = 0, test_size: float = 0.3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(summary, importances). Summary: one row per target with accuracy on the held-out split. Importances: one
    row per target and controllable parameter, mechanism indicators summed into ``mechanism``."""
    x = features(evaluated)
    summary, importances = [], []
    for target in TARGETS:
        y = evaluated[f"pass_{target}"].to_numpy(dtype=bool)
        row: dict[str, Any] = {"target": target, "pass_share": float(y.mean()), "rows": len(y)}
        if y.all() or not y.any():
            summary.append({**row, "status": "constant", "test_accuracy": np.nan, "majority_accuracy": 1.0})
            continue
        stratify = y if min(y.sum(), (~y).sum()) >= 2 else None
        x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=test_size, random_state=seed, stratify=stratify)
        model = DecisionTreeClassifier(max_depth=TREE_DEPTH, random_state=seed).fit(x_train, y_train)
        majority = max(y_test.mean(), 1 - y_test.mean())
        summary.append({**row, "status": "fitted", "test_accuracy": float(model.score(x_test, y_test)),
                        "majority_accuracy": float(majority)})
        by_parameter = pd.Series(model.feature_importances_, index=x.columns).groupby(_parameter_of).sum()
        importances.extend({"target": target, "parameter": name, "importance": float(value)} for name, value in by_parameter.items())
    return pd.DataFrame(summary), pd.DataFrame(importances, columns=["target", "parameter", "importance"])


def spearman(results: pd.DataFrame, kpi_columns: tuple[str, ...] = KPI_COLUMNS) -> pd.DataFrame:
    """Spearman rank correlation, rows = numeric controllable parameters, columns = KPIs."""
    ranks = results[list(NUMERIC) + list(kpi_columns)].astype(float).rank()
    return ranks.corr(method="pearson").loc[list(NUMERIC), list(kpi_columns)]


def _range(parameters: pd.DataFrame, param_ids: pd.Index) -> dict[str, Any]:
    chosen = parameters.set_index("param_id").loc[param_ids]
    if chosen.empty:
        return {"qualifying_sets": 0}
    out: dict[str, Any] = {"qualifying_sets": len(chosen)}
    for name in NUMERIC:
        out[name] = [float(chosen[name].min()), float(chosen[name].max())]
    out["mechanism"] = sorted(chosen["mechanism"].unique())
    return out


def recommendations(evaluated: pd.DataFrame, qualify_share: float = QUALIFY_SHARE) -> dict[str, Any]:
    shares = pass_shares(evaluated)
    parameters = evaluated.drop_duplicates("param_id")[["param_id", *NUMERIC, "mechanism"]]
    best_share = shares["share_all"].max()
    best = shares.index[shares["share_all"] == best_share].min()
    point = parameters.set_index("param_id").loc[best]
    per_goal = {group: _range(parameters, shares.index[shares[f"share_{group}"] >= qualify_share]) for group in GROUPS}
    global_ids = shares.index[(shares[[f"share_{group}" for group in GROUPS]] >= qualify_share).all(axis=1)]
    return {
        "qualify_share": qualify_share,
        "point_estimate": {
            "param_id": int(best), "share_all": float(best_share),
            **{name: float(point[name]) for name in NUMERIC}, "mechanism": point["mechanism"],
        },
        "per_goal": per_goal,
        "global": _range(parameters, global_ids),
    }
