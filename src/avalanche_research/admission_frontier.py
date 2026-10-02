"""Mathematical models and protocol-level invariants for duration-dependent entry stake frontiers.

This module formalizes the mechanism design of duration-dependent admission barriers S_min(d)
for the Avalanche Primary Network, resolving the multi-policy tension between:
- Community proposals: Lowering minimum self-stake threshold from 2,000 AVAX to 500 AVAX.
- ACP-273 / ACP-275: Lowering minimum staking duration from 14 days to 2 days (or 1 day).

Key design principle:
This is a pure protocol-level state transition gate / admission rule.
It does not depend on unobservable validator behavioral response priors or interview data.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd


class CurveFamily(str, Enum):
    """Mathematical functional form for the duration-stake admission frontier."""
    HYPERBOLIC = "hyperbolic"
    ISO_COMMITMENT = "iso_commitment"
    POWER_LAW = "power_law"
    BOUNDED_HARMONIC = "bounded_harmonic"


@dataclass(frozen=True)
class AdmissionConfig:
    """Parameter specification for the duration-dependent admission frontier."""
    s_floor: float = 500.0          # Target asymptotic stake floor at 365 days (community proposals)
    s_short: float = 20000.0        # Minimum stake required at shortest duration d_min (AVAX)
    d_min: float = 2.0              # Minimum protocol lockup duration in days (ACP-273)
    d_max: float = 365.0            # Maximum protocol lockup duration in days
    alpha: float = 1.0              # Curvature parameter for hyperbolic decay
    power_p: float = 3.5            # Curvature exponent for power law decay
    k_iso: float = 28000.0          # Capital-time commitment invariant (2000 AVAX * 14 days)


def s_min_hyperbolic(d: np.ndarray, config: AdmissionConfig) -> np.ndarray:
    r"""Compute minimum stake requirement using hyperbolic decay:
    
    $$S_{\min}(d) = S_{\text{floor}} + \frac{S_{\text{short}} - S_{\text{floor}}}{1 + \alpha (d - d_{\min})}$$
    
    Guarantees:
    - S_min(d_min) == S_short exactly.
    - S_min(14) == 2000 AVAX exactly when S_short=20000, S_floor=500, d_min=2, alpha=1.0.
    - S_min(d) -> S_floor as d -> infinity.
    - Strictly monotonic: dS/dd < 0 everywhere.
    - Strictly convex: d^2S/dd^2 > 0 everywhere.
    """
    delta_d = np.maximum(0.0, d - config.d_min)
    return config.s_floor + (config.s_short - config.s_floor) / (1.0 + config.alpha * delta_d)


def s_min_iso_commitment(d: np.ndarray, config: AdmissionConfig) -> np.ndarray:
    r"""Compute minimum stake requirement under constant Capital-Time invariant:
    
    $$\text{Commitment} = S \cdot d \ge K_{\text{iso}}$$
    $$S_{\min}(d) = \max(S_{\text{floor}}, \min(S_{\text{short}}, \frac{K_{\text{iso}}}{d}))$$
    
    Guarantees:
    - Perfectly constant sybil attack cost (AVAX-days) across all durations d in [K/S_short, K/S_floor].
    - S_min(14) == 2000 AVAX exactly when K_iso = 28,000 AVAX-days.
    - Clamped at S_short at the short end and S_floor at the long end.
    """
    unbounded = config.k_iso / np.maximum(1e-6, d)
    return np.clip(unbounded, config.s_floor, config.s_short)


def s_min_power_law(d: np.ndarray, config: AdmissionConfig) -> np.ndarray:
    r"""Compute minimum stake requirement using generalized power-law decay:
    
    $$S_{\min}(d) = S_{\text{floor}} + (S_{\text{short}} - S_{\text{floor}}) \cdot \left(\frac{d_{\max} - d}{d_{\max} - d_{\min}}\right)^p$$
    
    Guarantees:
    - S_min(d_min) == S_short.
    - S_min(d_max) == S_floor exactly at 365 days.
    """
    norm_dist = np.clip((config.d_max - d) / (config.d_max - config.d_min), 0.0, 1.0)
    return config.s_floor + (config.s_short - config.s_floor) * (norm_dist ** config.power_p)


def s_min_bounded_harmonic(d: np.ndarray, config: AdmissionConfig) -> np.ndarray:
    r"""Compute minimum stake requirement using canonical Bounded Harmonic P-Decay:
    
    $$S_{\min}(d) = S_{\text{floor}} + (S_{\text{short}} - S_{\text{floor}}) \cdot \left[ \frac{\frac{1}{d} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}} \right]^p$$
    
    Guarantees:
    - S_min(d_min) == S_short exactly.
    - S_min(d_max) == S_floor exactly at d_max with zero boundary residue (Axiom 3).
    - Strictly monotonic (dS/dd < 0) and strictly convex (d^2S/dd^2 > 0) for all p >= 1.
    - Asymptotically smooth C^1 continuity at d_max.
    """
    d_clamped = np.clip(d, config.d_min, config.d_max)
    denom = (1.0 / config.d_min) - (1.0 / config.d_max)
    numer = (1.0 / d_clamped) - (1.0 / config.d_max)
    ratio = np.maximum(0.0, numer / denom)
    return config.s_floor + (config.s_short - config.s_floor) * (ratio ** config.power_p)


def evaluate_admission_frontier(
    durations: np.ndarray,
    config: AdmissionConfig,
    family: CurveFamily = CurveFamily.BOUNDED_HARMONIC,
) -> pd.DataFrame:
    """Generate comprehensive evaluation metrics for a duration-dependent admission schedule."""
    d = np.asarray(durations, dtype=float)
    
    if family == CurveFamily.HYPERBOLIC:
        s_min = s_min_hyperbolic(d, config)
    elif family == CurveFamily.ISO_COMMITMENT:
        s_min = s_min_iso_commitment(d, config)
    elif family == CurveFamily.POWER_LAW:
        s_min = s_min_power_law(d, config)
    elif family == CurveFamily.BOUNDED_HARMONIC:
        s_min = s_min_bounded_harmonic(d, config)
    else:
        raise ValueError(f"Unknown curve family: {family}")
        
    capital_time = s_min * d
    annual_turnover = 365.0 / d
    mainnet_flat = np.full_like(d, 2000.0)
    flat_500 = np.full_like(d, config.s_floor)
    
    # Sybil cost ratio relative to current Mainnet (2,000 AVAX * 14 days = 28,000 AVAX-days)
    baseline_commitment = 2000.0 * 14.0
    sybil_parity_ratio = capital_time / baseline_commitment
    
    # Capital discount relative to current 2,000 AVAX barrier
    barrier_relief_pct = (1.0 - s_min / 2000.0) * 100.0
    
    return pd.DataFrame({
        "duration_days": d,
        "min_stake_avax": np.round(s_min, 2),
        "capital_time_avax_days": np.round(capital_time, 1),
        "annual_rollover_txs": np.round(annual_turnover, 1),
        "sybil_parity_ratio": np.round(sybil_parity_ratio, 3),
        "barrier_relief_pct": np.round(barrier_relief_pct, 1),
        "mainnet_baseline_stake": mainnet_flat,
        "naive_flat_500_stake": flat_500,
    })


def evaluate_historical_eligibility(
    df_bonds: pd.DataFrame,
    config: AdmissionConfig,
    family: CurveFamily = CurveFamily.BOUNDED_HARMONIC,
) -> Dict[str, float]:
    """Calculate the share of historical validator self-bonds that would qualify under S_min(d).
    
    This provides an empirical feasibility audit across 57,067 historical validator self-bonds.
    """
    bonds = df_bonds["bond_avax"].values
    durations = df_bonds["duration_days"].values
    
    if family == CurveFamily.HYPERBOLIC:
        s_req = s_min_hyperbolic(durations, config)
    elif family == CurveFamily.ISO_COMMITMENT:
        s_req = s_min_iso_commitment(durations, config)
    elif family == CurveFamily.POWER_LAW:
        s_req = s_min_power_law(durations, config)
    elif family == CurveFamily.BOUNDED_HARMONIC:
        s_req = s_min_bounded_harmonic(durations, config)
    else:
        raise ValueError(f"Unknown curve family: {family}")
        
    qualified = bonds >= s_req
    total = len(bonds)
    
    return {
        "total_records": float(total),
        "qualified_count": float(np.sum(qualified)),
        "qualified_pct": float(np.mean(qualified) * 100.0),
        "disqualified_count": float(total - np.sum(qualified)),
        "disqualified_pct": float((1.0 - np.mean(qualified)) * 100.0),
    }
