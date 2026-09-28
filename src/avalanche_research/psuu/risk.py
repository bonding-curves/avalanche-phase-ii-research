"""The risk surface: for each pair of controllable parameters, the share of trajectories where a goal fails.

Numeric parameters are cut into equal-width bins over their sweep range. The mechanism is its own axis, one cell per
mechanism. By default a trajectory fails when any goal group fails (``pass_all`` is false).
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from .design import CONTROLLABLE, MECHANISMS, PARAMETER_RANGES

N_BINS = 5
FAILURE_THRESHOLD = 0.50


def _axis(evaluated: pd.DataFrame, name: str, n_bins: int) -> pd.DataFrame:
    """Per row: bin index, lower edge, upper edge, and label for one parameter."""
    if name == "mechanism":
        index = evaluated["mechanism"].map({value: position for position, value in enumerate(MECHANISMS)})
        return pd.DataFrame({"bin": index, "low": np.nan, "high": np.nan, "label": evaluated["mechanism"]}, index=evaluated.index)
    low, high = PARAMETER_RANGES[name]
    edges = np.linspace(low, high, n_bins + 1)
    index = np.clip(np.searchsorted(edges, evaluated[name].to_numpy(dtype=float), side="right") - 1, 0, n_bins - 1)
    labels = [f"[{edges[i]:.4g}, {edges[i + 1]:.4g}{']' if i == n_bins - 1 else ')'}" for i in range(n_bins)]
    return pd.DataFrame({"bin": index, "low": edges[index], "high": edges[index + 1],
                         "label": [labels[i] for i in index]}, index=evaluated.index)


def surface(evaluated: pd.DataFrame, target: str = "all", n_bins: int = N_BINS) -> pd.DataFrame:
    """Tidy frame, one row per (parameter pair, x cell, y cell): trajectories and the failure share."""
    failed = ~evaluated[f"pass_{target}"].to_numpy(dtype=bool)
    axes = {name: _axis(evaluated, name, n_bins) for name in CONTROLLABLE}
    frames = []
    for x_name, y_name in combinations(CONTROLLABLE, 2):
        x, y = axes[x_name].add_prefix("x_"), axes[y_name].add_prefix("y_")
        cells = pd.concat([x, y], axis=1).assign(failed=failed)
        grouped = cells.groupby(["x_bin", "y_bin", "x_label", "y_label"], dropna=False).agg(
            x_low=("x_low", "first"), x_high=("x_high", "first"), y_low=("y_low", "first"), y_high=("y_high", "first"),
            trajectories=("failed", "size"), fail_share=("failed", "mean"),
        ).reset_index()
        frames.append(grouped.assign(param_x=x_name, param_y=y_name, target=target))
    columns = ["target", "param_x", "x_bin", "x_label", "x_low", "x_high", "param_y", "y_bin", "y_label", "y_low", "y_high",
               "trajectories", "fail_share"]
    return pd.concat(frames, ignore_index=True)[columns]


def failure_regions(risk_surface: pd.DataFrame, threshold: float = FAILURE_THRESHOLD) -> pd.DataFrame:
    """Cells whose failure share exceeds ``threshold``, worst first."""
    return risk_surface[risk_surface["fail_share"] > threshold].sort_values("fail_share", ascending=False, ignore_index=True)
