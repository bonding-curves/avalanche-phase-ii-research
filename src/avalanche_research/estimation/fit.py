"""Goodness-of-fit measures for comparing a simulated series with an observed one, day by day.

All functions take two equal-length sequences, drop positions where either value is missing, and return a float.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def _pair(observed: Sequence[float], simulated: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    a = np.asarray(observed, dtype=float)
    b = np.asarray(simulated, dtype=float)
    if a.shape != b.shape:
        raise ValueError("observed and simulated series must have the same length")
    keep = np.isfinite(a) & np.isfinite(b)
    return a[keep], b[keep]


def pearson_r(observed: Sequence[float], simulated: Sequence[float]) -> float:
    """Pearson correlation. NaN when either series is constant or fewer than two pairs remain."""
    a, b = _pair(observed, simulated)
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def rmse(observed: Sequence[float], simulated: Sequence[float]) -> float:
    """Root mean squared error, in the units of the series."""
    a, b = _pair(observed, simulated)
    if len(a) == 0:
        return float("nan")
    return float(np.sqrt(np.mean((a - b) ** 2)))


def direction_accuracy(observed: Sequence[float], simulated: Sequence[float]) -> float:
    """Share of day-over-day changes where the signs of the two changes match (a zero matches only a zero).

    Changes are taken on the full series first, so a missing value removes the two changes it touches.
    """
    a = np.diff(np.asarray(observed, dtype=float))
    b = np.diff(np.asarray(simulated, dtype=float))
    if a.shape != b.shape:
        raise ValueError("observed and simulated series must have the same length")
    keep = np.isfinite(a) & np.isfinite(b)
    if not keep.any():
        return float("nan")
    return float(np.mean(np.sign(a[keep]) == np.sign(b[keep])))


def cross_correlation(observed: Sequence[float], simulated: Sequence[float], lag: int) -> float:
    """Correlation of observed[t] with simulated[t + lag] over the overlapping days."""
    a = np.asarray(observed, dtype=float)
    b = np.asarray(simulated, dtype=float)
    if lag >= 0:
        return pearson_r(a[: len(a) - lag], b[lag:])
    return pearson_r(a[-lag:], b[: len(b) + lag])


def phase_alignment_days(observed: Sequence[float], simulated: Sequence[float], max_lag: int = 30) -> int:
    """The lag in [-max_lag, max_lag] that maximizes the cross-correlation.

    A positive lag means the simulated series trails the observed one by that many days: simulated[t + lag]
    best matches observed[t]. Ties go to the smallest absolute lag.
    """
    if len(observed) != len(simulated):
        raise ValueError("observed and simulated series must have the same length")
    best_lag, best_value = 0, -np.inf
    for lag in sorted(range(-max_lag, max_lag + 1), key=lambda v: (abs(v), v)):
        if abs(lag) >= len(observed) - 1:
            continue
        value = cross_correlation(observed, simulated, lag)
        if np.isfinite(value) and value > best_value + 1e-12:
            best_lag, best_value = lag, value
    return int(best_lag)
