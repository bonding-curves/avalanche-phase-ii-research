"""Scoring a probabilistic forecast against the realized value, for the Helicon forecasts of the validation protocol.

v0, unreviewed. Beside the measures: a forecast of a registered measure is an ensemble of draws, and its score is the
continuous ranked probability score (Gneiting and Raftery, 2007) against the value the measure realizes. A point
forecast is one draw, whose score is its absolute error. Skill is one minus the model's score over a benchmark's.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .catalog import DataError


def crps(draws: Sequence[float], realized: float) -> float:
    """The ensemble CRPS, E|X - y| - E|X - X'| / 2 over the draws, computed from the sorted draws in O(n log n)."""
    values = sorted(float(value) for value in draws)
    if not values or any(math.isnan(value) or math.isinf(value) for value in values) or math.isnan(realized):
        raise DataError("a forecast needs at least one finite draw and a realized value")
    count = len(values)
    spread = sum(value * (2 * rank - count + 1) for rank, value in enumerate(values)) / (count * count)
    return sum(abs(value - realized) for value in values) / count - spread


def skill(model_score: float, benchmark_score: float) -> float:
    """One minus the model's score over the benchmark's. Above zero means the model beats the benchmark."""
    if benchmark_score == 0:
        raise DataError("a benchmark with zero error leaves skill undefined")
    return 1 - model_score / benchmark_score
