"""Measures of Effectiveness (MOEs) for the Avalanche Consensus Digital Twin.

Evaluates system outcomes strictly using consensus, economic, and network metrics
without governance or voting terminology.

MOEs:
1. Validator-Set Stability (S_N = sigma(N) / mean(N))
2. Validator Churn & Renewal Dynamics (lambda_turnover, lambda_short)
3. Stake Concentration / Decentralization across Nodes and Clustered Operators:
   - Node-level HHI and C_10, C_20
   - Operator-level HHI and C_10, C_20 (aggregating multi-node operators)
4. Economic Viability Across Validator Profiles (V_profile for A, B, C)
5. Network-Capacity Pressure (Headroom H_cap relative to N_max, lambda_max)
6. Capital-Duration and Delegation Diagnostics:
   - Duration distribution across capital tiers (Small vs Whale)
   - Profile A count and share
   - Effective delegation access and capacity utilization across durations
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Any, Tuple
import numpy as np
import pandas as pd

from avalanche_research.simulation.population import (
    ValidatorRecord,
    classify_capital_tier,
    get_duration_bucket,
)


@dataclass
class SnapshotMetrics:
    """Quantitative snapshot of consensus, stake, and network state at one timestep."""
    timestep: int
    active_node_count: int
    total_staked_avax: float
    total_self_bond_avax: float
    total_delegations_avax: float
    arrivals_count: int
    exits_count: int
    short_arrivals_count: int  # d < 14d
    short_exits_count: int     # d < 14d
    turnover_rate: float
    hhi_node: float
    hhi_operator: float
    c10_node: float
    c20_node: float
    c10_operator: float
    c20_operator: float
    viability_profile_a: float
    viability_profile_b: float
    viability_profile_c: float
    mean_duration_days: float
    stake_weighted_duration_days: float
    # Enriched composition and diagnostic metrics
    profile_a_count: int = 0
    profile_b_count: int = 0
    profile_c_count: int = 0
    profile_a_share: float = 0.0
    tier1_small_count: int = 0
    tier2_midsmall_count: int = 0
    tier3_medium_count: int = 0
    tier4_large_count: int = 0
    tier5_whale_count: int = 0
    small_duration_share_le_21d: float = 0.0
    small_duration_share_ge_90d: float = 0.0
    whale_duration_share_ge_90d: float = 0.0
    mean_delegation_utilization_14_21d: float = 0.0
    mean_delegation_utilization_ge_30d: float = 0.0
    eligible_zero_delegation_pct: float = 0.0
    max_nodes_single_operator: int = 0
    mean_nodes_per_operator: float = 0.0


@dataclass
class MOEResults:
    """Full trajectory evaluation across all 5 MOEs and diagnostics."""
    moe1_set_stability_sn: float
    moe2_mean_turnover_rate: float
    moe2_mean_short_churn_rate: float
    moe3_terminal_hhi_node: float
    moe3_terminal_hhi_operator: float
    moe3_terminal_c10_operator: float
    moe3_terminal_c20_operator: float
    moe4_viability_profile_a: float
    moe4_viability_profile_b: float
    moe4_viability_profile_c: float
    moe5_capacity_headroom_hcap: float
    n_max_headroom: float
    churn_headroom: float
    # Enriched summary diagnostics
    final_profile_a_count: int = 0
    final_profile_a_share: float = 0.0
    small_validators_le_21d_pct: float = 0.0
    small_validators_ge_90d_pct: float = 0.0
    whale_validators_ge_90d_pct: float = 0.0
    mean_eligible_zero_delegation_pct: float = 0.0
    terminal_max_operator_nodes: int = 0


def compute_snapshot_metrics(
    timestep: int,
    validators: Dict[str, ValidatorRecord],
    arrivals: int = 0,
    exits: int = 0,
    short_arrivals: int = 0,
    short_exits: int = 0,
    avax_price_usd: float = 25.0,
    annual_staking_yield: float = 0.055,
) -> SnapshotMetrics:
    """Calculates all instantaneous metrics for active validators at a timestep."""
    active_vals = [v for v in validators.values() if v.is_active]
    n_active = len(active_vals)

    if n_active == 0:
        return SnapshotMetrics(
            timestep=timestep,
            active_node_count=0,
            total_staked_avax=0.0,
            total_self_bond_avax=0.0,
            total_delegations_avax=0.0,
            arrivals_count=arrivals,
            exits_count=exits,
            short_arrivals_count=short_arrivals,
            short_exits_count=short_exits,
            turnover_rate=0.0,
            hhi_node=0.0,
            hhi_operator=0.0,
            c10_node=0.0,
            c20_node=0.0,
            c10_operator=0.0,
            c20_operator=0.0,
            viability_profile_a=0.0,
            viability_profile_b=0.0,
            viability_profile_c=0.0,
            mean_duration_days=0.0,
            stake_weighted_duration_days=0.0,
        )

    total_self = sum(v.self_bond_avax for v in active_vals)
    total_deleg = sum(v.delegations_received_avax for v in active_vals)
    total_staked = total_self + total_deleg

    # Node-level stake shares
    node_weights = np.array([v.total_weight_avax for v in active_vals], dtype=float)
    node_shares = node_weights / total_staked if total_staked > 0 else np.zeros(n_active)

    # Node-level concentration
    hhi_node = float(np.sum(node_shares ** 2) * 10_000.0)
    sorted_node_shares = np.sort(node_shares)[::-1]
    c10_node = float(np.sum(sorted_node_shares[:10]))
    c20_node = float(np.sum(sorted_node_shares[:20]))

    # Operator-level concentration (aggregating multi-node clusters)
    op_weights: Dict[str, float] = {}
    op_node_counts: Dict[str, int] = {}
    for v in active_vals:
        op = v.operator_address if v.operator_address else v.node_id
        op_weights[op] = op_weights.get(op, 0.0) + v.total_weight_avax
        op_node_counts[op] = op_node_counts.get(op, 0) + 1

    op_shares = np.array(list(op_weights.values()), dtype=float) / total_staked if total_staked > 0 else np.zeros(1)
    hhi_operator = float(np.sum(op_shares ** 2) * 10_000.0)
    sorted_op_shares = np.sort(op_shares)[::-1]
    c10_operator = float(np.sum(sorted_op_shares[:10]))
    c20_operator = float(np.sum(sorted_op_shares[:20]))

    max_op_nodes = max(op_node_counts.values()) if op_node_counts else 0
    mean_op_nodes = float(np.mean(list(op_node_counts.values()))) if op_node_counts else 0.0

    # Turnover rate
    turnover_rate = float((arrivals + exits) / (2.0 * n_active))

    # Economic viability by profile (Annual Revenue - Annual Hardware/VPS Costs > 0)
    cost_a_avax = 480.0 / avax_price_usd if avax_price_usd > 0 else 20.0
    cost_b_avax = 1440.0 / avax_price_usd if avax_price_usd > 0 else 60.0
    cost_c_avax = 4200.0 / avax_price_usd if avax_price_usd > 0 else 180.0

    vals_a = [v for v in active_vals if "Profile A" in v.profile]
    vals_b = [v for v in active_vals if "Profile B" in v.profile]
    vals_c = [v for v in active_vals if "Profile C" in v.profile]
    cnt_a = len(vals_a)
    cnt_b = len(vals_b)
    cnt_c = len(vals_c)
    share_a = float(cnt_a / n_active) if n_active > 0 else 0.0

    def calc_viability(vals: List[ValidatorRecord], cost_avax: float) -> float:
        if not vals:
            return 1.0
        solvent_count = 0
        for v in vals:
            self_rev = v.self_bond_avax * annual_staking_yield
            deleg_rev = v.delegations_received_avax * annual_staking_yield * v.commission_fee
            net_operating_margin = (self_rev + deleg_rev) - cost_avax
            if net_operating_margin > 0:
                solvent_count += 1
        return float(solvent_count / len(vals))

    viability_a = calc_viability(vals_a, cost_a_avax)
    viability_b = calc_viability(vals_b, cost_b_avax)
    viability_c = calc_viability(vals_c, cost_c_avax)

    durations = np.array([v.total_duration_days for v in active_vals], dtype=float)
    mean_dur = float(np.mean(durations))
    stake_weighted_dur = float(np.sum(durations * node_weights) / total_staked) if total_staked > 0 else mean_dur

    # Capital tier counts
    cnt_t1 = sum(1 for v in active_vals if v.self_bond_avax <= 2500.0)
    cnt_t2 = sum(1 for v in active_vals if 2500.0 < v.self_bond_avax <= 6000.0)
    cnt_t3 = sum(1 for v in active_vals if 6000.0 < v.self_bond_avax <= 20000.0)
    cnt_t4 = sum(1 for v in active_vals if 20000.0 < v.self_bond_avax <= 100000.0)
    cnt_t5 = sum(1 for v in active_vals if v.self_bond_avax > 100000.0)

    # Capital-duration joint metrics
    small_vals = [v for v in active_vals if v.self_bond_avax <= 2500.0]
    small_le_21 = float(sum(1 for v in small_vals if v.total_duration_days <= 21) / len(small_vals)) if small_vals else 0.0
    small_ge_90 = float(sum(1 for v in small_vals if v.total_duration_days >= 90) / len(small_vals)) if small_vals else 0.0

    whale_vals = [v for v in active_vals if v.self_bond_avax > 100000.0]
    whale_ge_90 = float(sum(1 for v in whale_vals if v.total_duration_days >= 90) / len(whale_vals)) if whale_vals else 0.0

    # Delegation diagnostics
    short_del_vals = [v for v in active_vals if 14 <= v.total_duration_days <= 21 and v.self_bond_avax > 0]
    util_14_21 = float(np.mean([v.delegations_received_avax / (4.0 * v.self_bond_avax) for v in short_del_vals])) if short_del_vals else 0.0

    ge30_del_vals = [v for v in active_vals if v.total_duration_days >= 30 and v.self_bond_avax > 0]
    util_ge_30 = float(np.mean([v.delegations_received_avax / (4.0 * v.self_bond_avax) for v in ge30_del_vals])) if ge30_del_vals else 0.0

    eligible_vals = [v for v in active_vals if v.total_duration_days >= 14]
    eligible_zero_cnt = sum(1 for v in eligible_vals if v.delegations_received_avax == 0.0)
    eligible_zero_pct = float(eligible_zero_cnt / len(eligible_vals)) if eligible_vals else 0.0

    return SnapshotMetrics(
        timestep=timestep,
        active_node_count=n_active,
        total_staked_avax=total_staked,
        total_self_bond_avax=total_self,
        total_delegations_avax=total_deleg,
        arrivals_count=arrivals,
        exits_count=exits,
        short_arrivals_count=short_arrivals,
        short_exits_count=short_exits,
        turnover_rate=turnover_rate,
        hhi_node=hhi_node,
        hhi_operator=hhi_operator,
        c10_node=c10_node,
        c20_node=c20_node,
        c10_operator=c10_operator,
        c20_operator=c20_operator,
        viability_profile_a=viability_a,
        viability_profile_b=viability_b,
        viability_profile_c=viability_c,
        mean_duration_days=mean_dur,
        stake_weighted_duration_days=stake_weighted_dur,
        profile_a_count=cnt_a,
        profile_b_count=cnt_b,
        profile_c_count=cnt_c,
        profile_a_share=share_a,
        tier1_small_count=cnt_t1,
        tier2_midsmall_count=cnt_t2,
        tier3_medium_count=cnt_t3,
        tier4_large_count=cnt_t4,
        tier5_whale_count=cnt_t5,
        small_duration_share_le_21d=small_le_21,
        small_duration_share_ge_90d=small_ge_90,
        whale_duration_share_ge_90d=whale_ge_90,
        mean_delegation_utilization_14_21d=util_14_21,
        mean_delegation_utilization_ge_30d=util_ge_30,
        eligible_zero_delegation_pct=eligible_zero_pct,
        max_nodes_single_operator=max_op_nodes,
        mean_nodes_per_operator=mean_op_nodes,
    )


def evaluate_moes(
    snapshots: List[SnapshotMetrics],
    n_max: float = 2000.0,
    lambda_max: float = 0.50,
) -> MOEResults:
    """Evaluates the 5 MOEs and diagnostics from a completed simulation trajectory."""
    node_counts = [s.active_node_count for s in snapshots]
    turnovers = [s.turnover_rate for s in snapshots[1:]] if len(snapshots) > 1 else [0.0]
    
    # MOE 1: Validator-Set Stability
    mean_n = float(np.mean(node_counts))
    std_n = float(np.std(node_counts))
    s_n = float(std_n / mean_n) if mean_n > 0 else 0.0

    # MOE 2: Validator Churn & Renewal Dynamics
    mean_turnover = float(np.mean(turnovers))
    total_short_events = sum(s.short_arrivals_count + s.short_exits_count for s in snapshots)
    mean_short_churn = float(total_short_events / (2.0 * mean_n * len(snapshots))) if mean_n > 0 else 0.0

    # MOE 3: Stake Concentration across Nodes and Operators (terminal snapshot)
    last_snap = snapshots[-1]
    term_hhi_node = last_snap.hhi_node
    term_hhi_op = last_snap.hhi_operator
    term_c10_op = last_snap.c10_operator
    term_c20_op = last_snap.c20_operator

    # MOE 4: Economic Viability Across Validator Profiles (trajectory means)
    mean_viab_a = float(np.mean([s.viability_profile_a for s in snapshots]))
    mean_viab_b = float(np.mean([s.viability_profile_b for s in snapshots]))
    mean_viab_c = float(np.mean([s.viability_profile_c for s in snapshots]))

    # MOE 5: Network-Capacity Pressure (Safety Headroom)
    max_n = float(np.max(node_counts))
    max_turnover = float(np.max(turnovers))
    headroom_n = float(1.0 - (max_n / n_max))
    headroom_turnover = float(1.0 - (max_turnover / lambda_max))
    h_cap = float(min(headroom_n, headroom_turnover))

    # Diagnostics
    final_cnt_a = last_snap.profile_a_count
    final_share_a = last_snap.profile_a_share
    small_le21 = float(np.mean([s.small_duration_share_le_21d for s in snapshots]))
    small_ge90 = float(np.mean([s.small_duration_share_ge_90d for s in snapshots]))
    whale_ge90 = float(np.mean([s.whale_duration_share_ge_90d for s in snapshots]))
    mean_elig_zero = float(np.mean([s.eligible_zero_delegation_pct for s in snapshots]))
    term_max_op_nodes = last_snap.max_nodes_single_operator

    return MOEResults(
        moe1_set_stability_sn=s_n,
        moe2_mean_turnover_rate=mean_turnover,
        moe2_mean_short_churn_rate=mean_short_churn,
        moe3_terminal_hhi_node=term_hhi_node,
        moe3_terminal_hhi_operator=term_hhi_op,
        moe3_terminal_c10_operator=term_c10_op,
        moe3_terminal_c20_operator=term_c20_op,
        moe4_viability_profile_a=mean_viab_a,
        moe4_viability_profile_b=mean_viab_b,
        moe4_viability_profile_c=mean_viab_c,
        moe5_capacity_headroom_hcap=h_cap,
        n_max_headroom=headroom_n,
        churn_headroom=headroom_turnover,
        final_profile_a_count=final_cnt_a,
        final_profile_a_share=final_share_a,
        small_validators_le_21d_pct=small_le21,
        small_validators_ge_90d_pct=small_ge90,
        whale_validators_ge_90d_pct=whale_ge90,
        mean_eligible_zero_delegation_pct=mean_elig_zero,
        terminal_max_operator_nodes=term_max_op_nodes,
    )
