"""Policy functions for the Avalanche admission frontier simulation."""

from __future__ import annotations

import math
import numpy as np
from typing import Dict, Any, Tuple


# Exact ACP-285 ARR Lookup (Helicon Post-Ramp at Current Supply 470M AVAX)
ACP285_ARR_SCHEDULE = {
    14: 0.04078,
    30: 0.04183,
    42: 0.04261,
    56: 0.04353,
    70: 0.04445,
    84: 0.04536,
    119: 0.04759,
    180: 0.05166,
    365: 0.06378,
}


def solve_harmonic_exponent(d_target_days: float, s_short: float, target_stake: float = 2000.0) -> float:
    """Solves for exponent p given target duration and S_short.
    
    Formula:
        p = ln( (target_stake - 500) / (S_short - 500) ) / ln( (1/d_target - 1/365) / (1/2 - 1/365) )
    """
    d_clamped = max(2.0, min(364.0, float(d_target_days)))
    denom = (1.0 / d_clamped - 1.0 / 365.0) / (0.5 - 1.0 / 365.0)
    numer = (target_stake - 500.0) / (s_short - 500.0)
    if denom <= 0 or numer <= 0:
        return 0.642
    return float(np.log(numer) / np.log(denom))


def s_min_harmonic(d_days: float, s_short: float, p: float) -> float:
    """Calculates S_min(d) using the Harmonic Bounded Decay formula."""
    d_clamped = max(2.0, min(365.0, float(d_days)))
    inv_term = (1.0 / d_clamped - 1.0 / 365.0) / (0.5 - 1.0 / 365.0)
    inv_term = max(0.0, inv_term)
    return 500.0 + (s_short - 500.0) * (inv_term ** p)


def s_min_piecewise_benqi(d_days: float, s_short: float, d_target_days: float) -> float:
    """Piecewise frontier pinning (2d, s_short), (14d, 6000), (d_target, 2000), (365d, 500)."""
    d = float(d_days)
    if d <= 2.0:
        return s_short
    if d >= 365.0:
        return 500.0

    knots = [
        (2.0, float(s_short)),
        (14.0, 6000.0),
        (float(d_target_days), 2000.0),
        (365.0, 500.0),
    ]
    knots = sorted(knots, key=lambda k: k[0])

    for i in range(len(knots) - 1):
        d0, s0 = knots[i]
        d1, s1 = knots[i+1]
        if d0 <= d <= d1:
            if d0 == d1:
                return s0
            t = (1.0 / d - 1.0 / d1) / (1.0 / d0 - 1.0 / d1)
            return s1 + (s0 - s1) * max(0.0, min(1.0, t))

    return 500.0


def p_admission_filter(params: Dict[str, Any], step: int, sH: list, s: Dict[str, Any]) -> Dict[str, Any]:
    """Policy: Computes current S_min boundary values and verifies admission criteria."""
    s_short = params.get("s_short", 20_000.0)
    d_target_days = params.get("d_target_days", 84.0)
    frontier_mode = params.get("frontier_mode", "harmonic")
    
    if frontier_mode == "piecewise_benqi":
        s_min_fn = lambda d: s_min_piecewise_benqi(d, s_short, d_target_days)
        p = 0.0
    else:
        p = params.get("p")
        if p is None:
            p = solve_harmonic_exponent(d_target_days, s_short, 2000.0)
        s_min_fn = lambda d: s_min_harmonic(d, s_short, p)

    return {
        "s_short": s_short,
        "p": p,
        "d_target_days": d_target_days,
        "frontier_mode": frontier_mode,
        "s_min_2d": s_min_fn(2.0),
        "s_min_14d": s_min_fn(14.0),
        "s_min_dtarget": s_min_fn(d_target_days),
        "s_min_365d": s_min_fn(365.0),
    }


def p_validator_renewal_and_entry(params: Dict[str, Any], step: int, sH: list, s: Dict[str, Any]) -> Dict[str, Any]:
    """Policy: Models expiring validator renewal choices calibrated to empirical behaviors.
    
    Causal Behavioral Dynamics:
    1. Retail Stakers (2,000 AVAX):
       - Strong empirical preference for liquidity (71% currently choose 14d-30d).
       - When 14d is blocked by S_min(14d) > 2,000, they choose the SHORTEST admissible
         duration >= d_target. Probability drops sharply with further lockup (lambda_liq).
       - They top-up only if deficit is small (<25%), otherwise they choose d >= d_target.
    2. Whale Stakers (>=6,000 AVAX):
       - Capital satisfies S_min across all d >= 14d.
       - Under ACP-285's yield steepening (4.08% at 14d -> 6.38% at 1y), whales balance
         higher yield against institutional rebalancing needs, resulting in stake-weighted
         tenure extending from 11.6w toward 16-20w.
    """
    s_short = params.get("s_short", 20_000.0)
    d_target_days = params.get("d_target_days", 84.0)
    frontier_mode = params.get("frontier_mode", "harmonic")
    p = params.get("p")
    if p is None and frontier_mode == "harmonic":
        p = solve_harmonic_exponent(d_target_days, s_short, 2000.0)

    if frontier_mode == "piecewise_benqi":
        s_min_fn = lambda d: s_min_piecewise_benqi(d, s_short, d_target_days)
    else:
        s_min_fn = lambda d: s_min_harmonic(d, s_short, p)

    dt_days = params.get("dt_days", 7)
    candidate_durations = [14, 30, 42, 56, 70, 84, 119, 180, 365]

    validators = s["validators"]
    renewals = {}
    new_entries = {}
    pchain_txs = 0

    for nid, val in validators.items():
        if not val.is_active:
            continue
        
        # Check expiration
        if val.remaining_days <= dt_days:
            is_retail = val.self_bond_avax < 6000.0
            
            if is_retail:
                # ---------------------------------------------------------
                # RETAIL OPERATOR DUAL-STAGE CHOICE MODEL
                # Stage 1: Evaluate Outside Option Spread (Standalone Cloud VPS vs sAVAX)
                # Stage 2: If staying, select shortest admissible duration >= d_target
                # ---------------------------------------------------------
                cloud_drag = 0.0096  # $40/mo cloud VPS on 2,000 AVAX = -0.96% APY
                savax_apy = params.get("savax_apy", 0.0415)  # 4.15% 30-day mean APY
                deleg_ratio = params.get("delegation_subsidy_ratio", 1.0)
                
                # Check candidate feasible durations
                feasible_d = [d for d in candidate_durations if s_min_fn(d) <= val.self_bond_avax * 1.25]
                if not feasible_d:
                    renewals[nid] = {"action": "exit", "chosen_duration": 0, "bond": val.self_bond_avax}
                    continue
                
                # The validator looks at their best entry horizon (typically d_min = feasible_d[0])
                d_entry = feasible_d[0]
                arr_entry = ACP285_ARR_SCHEDULE.get(d_entry, 0.04078 + 0.023 * (d_entry / 365.0))
                fee_bonus = deleg_ratio * arr_entry * val.commission_fee
                net_validator_yield = arr_entry - cloud_drag + fee_bonus
                
                # Economic spread: net standalone yield minus liquid staking outside option
                spread = net_validator_yield - savax_apy
                
                # Illiquidity friction: stakers prefer shorter horizons (baseline 37.1d)
                # Excess commitment beyond 30d adds illiquidity pressure
                excess_lockup_months = max(0.0, (d_entry - 30.0) / 30.0)
                
                # Probability of exit per renewal event:
                # Negative spread + lockup pressure increases probability of shutting down cloud VPS
                if spread < 0:
                    p_exit = min(0.35, 0.02 + 0.12 * (-spread / 0.01) + 0.02 * excess_lockup_months)
                else:
                    # Positive spread: validator earns more than liquid staking!
                    p_exit = max(0.01, 0.02 - 0.015 * (spread / 0.005) + 0.01 * excess_lockup_months)
                
                # Random choice: exit vs renew
                if np.random.rand() < p_exit:
                    renewals[nid] = {"action": "exit", "chosen_duration": 0, "bond": val.self_bond_avax}
                    continue
                
                # Stage 2: Among feasible durations, retail validators strongly favor the shortest admissible
                dur_utilities = []
                dur_bonds = []
                for d in feasible_d:
                    req_stake = s_min_fn(d)
                    bond = max(val.self_bond_avax, req_stake)
                    arr_d = ACP285_ARR_SCHEDULE.get(d, 0.04078 + 0.023 * (d / 365.0))
                    # Penalty for locking beyond minimum necessary:
                    lockup_penalty = 1.2 * ((d - d_entry) / 30.0)
                    u_d = 20.0 * (arr_d - 0.040) - lockup_penalty
                    dur_utilities.append(u_d)
                    dur_bonds.append(bond)
                
                max_u = max(dur_utilities)
                exp_u = np.exp([u - max_u for u in dur_utilities])
                p_d = exp_u / np.sum(exp_u)
                chosen_idx = int(np.random.choice(len(feasible_d), p=p_d))
                chosen_duration = feasible_d[chosen_idx]
                
                renewals[nid] = {
                    "action": "renew",
                    "chosen_duration": chosen_duration,
                    "bond": dur_bonds[chosen_idx],
                }
                pchain_txs += 1
            else:
                # ---------------------------------------------------------
                # WHALE / INSTITUTIONAL OPERATOR CHOICE MODEL (>= 6,000 AVAX)
                # Whales have institutional balance sheets, low VPS drag relative to capital,
                # and optimize ACP-285 ARR term premium vs treasury liquidity needs.
                # ---------------------------------------------------------
                whale_utilities = []
                for d in candidate_durations:
                    arr = ACP285_ARR_SCHEDULE.get(d, 0.04078 + 0.023 * (d / 365.0))
                    liq_cost = (d / 365.0) ** 1.1 * 1.8
                    u = 20.0 * (arr - 0.04078) - liq_cost
                    whale_utilities.append(u)
                
                max_u = max(whale_utilities)
                exp_u = np.exp([u - max_u for u in whale_utilities])
                p_w = exp_u / np.sum(exp_u)
                chosen_idx = int(np.random.choice(len(candidate_durations), p=p_w))
                
                renewals[nid] = {
                    "action": "renew",
                    "chosen_duration": candidate_durations[chosen_idx],
                    "bond": val.self_bond_avax,
                }
                pchain_txs += 1

    return {
        "renewals": renewals,
        "new_entries": new_entries,
        "pchain_tx_count_delta": pchain_txs,
    }


def p_benqi_routing(params: Dict[str, Any], step: int, sH: list, s: Dict[str, Any]) -> Dict[str, Any]:
    """Policy: Allocates BENQI and liquid staking delegation volume."""
    total_delegation_pool = params.get("benqi_pool_avax", 15_000_000.0)
    validators = s["validators"]

    eligible_nodes = []
    for nid, val in validators.items():
        if val.is_active and val.self_bond_avax >= 6000.0 and val.commission_fee <= 0.02:
            eligible_nodes.append(nid)

    allocations: Dict[str, float] = {}
    if eligible_nodes:
        per_node_alloc = total_delegation_pool / len(eligible_nodes)
        for nid in eligible_nodes:
            allocations[nid] = per_node_alloc

    return {
        "benqi_eligible_count": len(eligible_nodes),
        "benqi_allocations": allocations,
    }
