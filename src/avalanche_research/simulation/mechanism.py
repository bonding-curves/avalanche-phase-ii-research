"""Canonical Duration-Dependent Admission Frontier Mechanism.

Mathematical Specification:
    S_min(d) = S_floor + (S_short - S_floor) * [eta(d)]^p

where:
    eta(d) = max(0.0, min(1.0, (1/d - 1/d_max) / (1/d_min - 1/d_max)))

Boundary Invariants:
    S_min(d_min) == S_short
    S_min(d_max) == S_floor

Monotonicity:
    d_1 < d_2  =>  S_min(d_1) >= S_min(d_2)

Curvature:
    p = 1.0: Canonical harmonic baseline
    p > 1.0: Candidate nonlinear alternatives (convex decay)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class AdmissionFrontierConfig:
    """Configuration parameters for the admission frontier mechanism."""
    s_floor_avax: float = 500.0
    s_short_avax: float = 14_000.0
    d_min_days: float = 2.0
    d_max_days: float = 365.0
    p: float = 1.0

    def __post_init__(self):
        if self.s_floor_avax <= 0:
            raise ValueError(f"S_floor must be positive: {self.s_floor_avax}")
        if self.s_short_avax < self.s_floor_avax:
            raise ValueError(f"S_short ({self.s_short_avax}) cannot be less than S_floor ({self.s_floor_avax})")
        if self.d_min_days <= 0 or self.d_max_days <= self.d_min_days:
            raise ValueError(f"Invalid duration bounds: [{self.d_min_days}, {self.d_max_days}]")
        if self.p <= 0:
            raise ValueError(f"Exponent p must be positive: {self.p}")


def eta_harmonic(d_days: float, d_min: float = 2.0, d_max: float = 365.0) -> float:
    """Computes normalized harmonic distance eta(d) in [0, 1]."""
    if d_days <= d_min:
        return 1.0
    if d_days >= d_max:
        return 0.0
    denom = (1.0 / d_min) - (1.0 / d_max)
    numer = (1.0 / d_days) - (1.0 / d_max)
    return max(0.0, min(1.0, numer / denom))


def s_min_admission(
    d_days: float,
    s_short_avax: float = 14_000.0,
    s_floor_avax: float = 500.0,
    p: float = 1.0,
    d_min: float = 2.0,
    d_max: float = 365.0,
) -> float:
    """Calculates continuous S_min(d) in AVAX."""
    eta = eta_harmonic(d_days, d_min, d_max)
    return s_floor_avax + (s_short_avax - s_floor_avax) * (eta ** p)


def s_min_integer_navax(
    d_seconds: int,
    s_short_navax: int = 14_000_000_000_000,
    s_floor_navax: int = 500_000_000_000,
    p_float: float = 1.0,
    d_min_seconds: int = 2 * 86400,
    d_max_seconds: int = 365 * 86400,
) -> int:
    """Calculates deterministic protocol-compatible S_min(d) in integer nAVAX.

    Safe integer bounds and fixed-precision representation for PlatformVM execution.
    """
    if d_seconds <= d_min_seconds:
        return s_short_navax
    if d_seconds >= d_max_seconds:
        return s_floor_navax

    # Scaled harmonic computation (scale factor 10^12 for fixed point)
    SCALE = 1_000_000_000_000
    inv_d = SCALE // d_seconds
    inv_max = SCALE // d_max_seconds
    inv_min = SCALE // d_min_seconds

    denom = inv_min - inv_max
    numer = inv_d - inv_max

    if denom <= 0:
        return s_floor_navax

    eta = max(0.0, min(1.0, numer / denom))
    if p_float == 1.0:
        # Exact integer linear arithmetic
        spread = s_short_navax - s_floor_navax
        hurdle_increment = (spread * numer) // denom
        return s_floor_navax + hurdle_increment
    else:
        # Exponentiation via standard mathematical library
        spread = float(s_short_navax - s_floor_navax)
        hurdle = float(s_floor_navax) + spread * (eta ** p_float)
        return int(math.floor(hurdle))
