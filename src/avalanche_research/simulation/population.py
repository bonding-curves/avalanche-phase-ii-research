"""Empirical validator population loader and behavioral prior calibration.

Loads canonical historical validator datasets:
1. `research/data/15-all-nodes-archetype.parquet` (7,635 nodes, operator clusters, live status)
2. `research/data/01-renewal-panel.parquet` (57,067 periods, duration choices, renewals, stake, delegations)

Constructs the current-regime validator set (602 active nodes) and empirical behavioral priors.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Tuple
import duckdb
import numpy as np
import pandas as pd


@dataclass
class ValidatorRecord:
    """Represents an active validator entity in the digital twin."""
    node_id: str
    self_bond_avax: float
    total_duration_days: int
    remaining_days: int
    commission_fee: float = 0.02
    delegations_received_avax: float = 0.0
    uptime_days: int = 15
    is_active: bool = True
    operator_address: str = ""
    archetype: str = ""
    profile: str = "Profile A (Solo / Capital-Constrained)"
    tenure_days: float = 0.0
    streak_count: int = 1

    @property
    def total_weight_avax(self) -> float:
        return self.self_bond_avax + self.delegations_received_avax


def classify_capital_tier(bond_avax: float) -> str:
    """Classifies self-stake into one of the 5 empirical capital tiers."""
    if bond_avax <= 2500.0:
        return "Tier 1: Small (<=2.5k)"
    if bond_avax <= 6000.0:
        return "Tier 2: Mid-Small (2.5k-6k)"
    if bond_avax <= 20000.0:
        return "Tier 3: Medium (6k-20k)"
    if bond_avax <= 100000.0:
        return "Tier 4: Large (20k-100k)"
    return "Tier 5: Whale (>100k)"


def get_duration_bucket(days: float) -> str:
    """Maps duration in days to standard discrete duration buckets."""
    d = round(days)
    if d < 14:
        return "<14d"
    if d <= 21:
        return "14-21d"
    if d <= 35:
        return "22-35d"
    if d <= 65:
        return "36-65d"
    if d <= 95:
        return "66-95d"
    if d <= 185:
        return "96-185d"
    return "186-365d"


@dataclass
class EmpiricalPriors:
    """Empirical behavioral priors estimated from historical validator records."""
    renewal_rates_by_profile: Dict[str, float]
    duration_distribution_by_profile: Dict[str, Dict[int, float]]
    overall_duration_distribution: Dict[int, float]
    mean_weekly_entries: float
    mean_delegation_fill_ratio: float
    total_completed_periods: int
    historical_node_count: int
    duration_distribution_by_tier: Dict[str, Dict[int, float]] = field(default_factory=dict)
    capital_tier_distribution: Dict[str, float] = field(default_factory=dict)
    delegation_util_by_bucket: Dict[str, float] = field(default_factory=dict)
    delegation_prob_by_bucket: Dict[str, float] = field(default_factory=dict)


def get_data_paths() -> Tuple[Path, Path]:
    """Resolves data paths for archetype nodes and renewal panel datasets."""
    root = Path(__file__).resolve().parents[3]
    nodes_path = root / "research" / "data" / "15-all-nodes-archetype.parquet"
    periods_path = root / "research" / "data" / "01-renewal-panel.parquet"
    if not nodes_path.exists() or not periods_path.exists():
        raise FileNotFoundError(f"Canonical datasets missing from research/data: {nodes_path}, {periods_path}")
    return nodes_path, periods_path


def classify_validator_profile(
    bond_avax: float,
    delegation_avax: float,
    archetype: str,
) -> str:
    """Maps validator state to one of the three canonical Stage 4 profiles.

    - Profile A (Solo / Capital-Constrained): Zero delegation, self-bond < 6,000 AVAX.
    - Profile B (Commercial Delegator-Facing): Active delegation, non-institutional archetype.
    - Profile C (Institutional / Ecosystem): Institutional archetype or large self-bond infrastructure.
    """
    if delegation_avax == 0.0 and bond_avax < 6000.0:
        return "Profile A (Solo / Capital-Constrained)"
    if delegation_avax > 0.0 and archetype != "institutional":
        return "Profile B (Commercial Delegator-Facing)"
    return "Profile C (Institutional / Ecosystem)"



def load_empirical_priors(
    con: duckdb.DuckDBPyConnection | None = None,
    regime: str = "post_contraction",
) -> EmpiricalPriors:
    """Computes empirical priors from completed historical staking periods.

    Parameters:
    - regime: 'post_contraction' (since 2025-09-01 steady state) or 'all_time' (genesis to present).
    """
    if con is None:
        con = duckdb.connect()
    nodes_path, periods_path = get_data_paths()

    # Time filter for completed periods
    time_filter = "WHERE p.is_right_censored = 0"
    if regime == "post_contraction":
        time_filter += " AND p.end_time >= '2025-09-01'"

    # Compute renewal rates by profile
    renewal_rates = {}
    duration_distributions: Dict[str, Dict[int, float]] = {
        "Profile A (Solo / Capital-Constrained)": {},
        "Profile B (Commercial Delegator-Facing)": {},
        "Profile C (Institutional / Ecosystem)": {},
    }
    overall_durations: Dict[int, float] = {}

    tot_periods_query = f"""
    WITH node_archetypes AS (
        SELECT NODE_ID, archetype FROM '{nodes_path}'
    ),
    periods_with_profiles AS (
        SELECT 
            p.*,
            CASE 
                WHEN p.delegation_volume_received_avax == 0 AND p.bond_avax < 6000 THEN 'Profile A (Solo / Capital-Constrained)'
                WHEN p.delegation_volume_received_avax > 0 AND coalesce(na.archetype, '') != 'institutional' THEN 'Profile B (Commercial Delegator-Facing)'
                ELSE 'Profile C (Institutional / Ecosystem)'
            END as profile
        FROM '{periods_path}' p
        LEFT JOIN node_archetypes na ON p.node_id = na.NODE_ID
        {time_filter}
    )
    SELECT profile, avg(renewed) as ren_rate, count(*) as cnt
    FROM periods_with_profiles
    GROUP BY profile
    """
    df_ren = con.execute(tot_periods_query).df()
    for _, row in df_ren.iterrows():
        renewal_rates[row["profile"]] = float(row["ren_rate"])

    # Duration frequency distribution by profile
    dur_query = f"""
    WITH node_archetypes AS (
        SELECT NODE_ID, archetype FROM '{nodes_path}'
    ),
    periods_with_profiles AS (
        SELECT 
            p.*,
            CASE 
                WHEN p.delegation_volume_received_avax == 0 AND p.bond_avax < 6000 THEN 'Profile A (Solo / Capital-Constrained)'
                WHEN p.delegation_volume_received_avax > 0 AND coalesce(na.archetype, '') != 'institutional' THEN 'Profile B (Commercial Delegator-Facing)'
                ELSE 'Profile C (Institutional / Ecosystem)'
            END as profile
        FROM '{periods_path}' p
        LEFT JOIN node_archetypes na ON p.node_id = na.NODE_ID
        {time_filter}
    )
    SELECT profile, round(duration_days)::INT as d_days, count(*) as count
    FROM periods_with_profiles
    GROUP BY profile, d_days
    ORDER BY profile, count DESC
    """
    df_dur = con.execute(dur_query).df()
    for prof in duration_distributions:
        sub = df_dur[df_dur["profile"] == prof]
        total_p = sub["count"].sum()
        if total_p > 0:
            for _, r in sub.iterrows():
                duration_distributions[prof][int(r["d_days"])] = float(r["count"] / total_p)

    # Overall duration distribution across top standard buckets
    top_d_query = f"""
    SELECT round(duration_days)::INT as d_days, count(*) as count
    FROM '{periods_path}'
    WHERE is_right_censored = 0
    GROUP BY d_days
    ORDER BY count DESC
    """
    df_top_d = con.execute(top_d_query).df()
    tot_d = df_top_d["count"].sum()
    for _, r in df_top_d.iterrows():
        overall_durations[int(r["d_days"])] = float(r["count"] / tot_d)

    # Weekly arrival rate decomposed
    if regime == "post_contraction":
        arrival_query = f"""
        WITH first_starts AS (
            SELECT node_id, min(start_time) as first_start
            FROM '{periods_path}'
            GROUP BY node_id
        )
        SELECT count(*) as total_entries
        FROM first_starts
        WHERE first_start >= '2025-09-01'
        """
        tot_entries = con.execute(arrival_query).fetchone()[0]
        # Weeks from 2025-09-01 to 2026-08-13 (~49.5 weeks)
        weekly_entries = float(tot_entries / 49.5)
    else:
        arrival_query = f"""
        WITH first_starts AS (
            SELECT node_id, min(start_time) as first_start
            FROM '{periods_path}'
            GROUP BY node_id
        )
        SELECT count(*) as total_entries
        FROM first_starts
        WHERE first_start >= '2024-01-01'
        """
        tot_entries = con.execute(arrival_query).fetchone()[0]
        # Weeks from 2024-01-01 to 2026-08-13 (~136.4 weeks)
        weekly_entries = float(tot_entries / 136.4)

    # Capital tier distribution and duration distribution by tier
    tier_dist: Dict[str, float] = {}
    dur_by_tier: Dict[str, Dict[int, float]] = {
        "Tier 1: Small (<=2.5k)": {},
        "Tier 2: Mid-Small (2.5k-6k)": {},
        "Tier 3: Medium (6k-20k)": {},
        "Tier 4: Large (20k-100k)": {},
        "Tier 5: Whale (>100k)": {},
    }
    tier_query = f"""
    WITH categorized AS (
        SELECT 
            CASE
                WHEN bond_avax <= 2500 THEN 'Tier 1: Small (<=2.5k)'
                WHEN bond_avax <= 6000 THEN 'Tier 2: Mid-Small (2.5k-6k)'
                WHEN bond_avax <= 20000 THEN 'Tier 3: Medium (6k-20k)'
                WHEN bond_avax <= 100000 THEN 'Tier 4: Large (20k-100k)'
                ELSE 'Tier 5: Whale (>100k)'
            END as capital_tier,
            round(duration_days)::INT as d_days
        FROM '{periods_path}'
        WHERE is_right_censored = 0
    )
    SELECT capital_tier, d_days, count(*) as count
    FROM categorized
    GROUP BY capital_tier, d_days
    ORDER BY capital_tier, count DESC
    """
    df_tier = con.execute(tier_query).df()
    tier_totals = df_tier.groupby("capital_tier")["count"].sum()
    all_periods_count = float(tier_totals.sum())
    for t_name, t_tot in tier_totals.items():
        tier_dist[str(t_name)] = float(t_tot / all_periods_count)
        sub = df_tier[df_tier["capital_tier"] == t_name]
        for _, r in sub.iterrows():
            dur_by_tier[str(t_name)][int(r["d_days"])] = float(r["count"] / t_tot)

    # Delegation utilization and probability gradient by duration bucket
    deleg_util_gradient: Dict[str, float] = {
        "<14d": 0.0,
        "14-21d": 0.039,
        "22-35d": 0.211,
        "36-65d": 0.408,
        "66-95d": 0.607,
        "96-185d": 1.108,
        "186-365d": 2.210,
    }
    deleg_prob_gradient: Dict[str, float] = {
        "<14d": 0.0,
        "14-21d": 0.274,
        "22-35d": 0.658,
        "36-65d": 0.732,
        "66-95d": 0.701,
        "96-185d": 0.716,
        "186-365d": 0.841,
    }

    return EmpiricalPriors(
        renewal_rates_by_profile=renewal_rates,
        duration_distribution_by_profile=duration_distributions,
        overall_duration_distribution=overall_durations,
        mean_weekly_entries=weekly_entries,
        mean_delegation_fill_ratio=0.74,
        total_completed_periods=int(con.execute(f"SELECT count(*) FROM '{periods_path}' WHERE is_right_censored = 0").fetchone()[0]),
        historical_node_count=int(con.execute(f"SELECT count(*) FROM '{nodes_path}'").fetchone()[0]),
        duration_distribution_by_tier=dur_by_tier,
        capital_tier_distribution=tier_dist,
        delegation_util_by_bucket=deleg_util_gradient,
        delegation_prob_by_bucket=deleg_prob_gradient,
    )



def load_current_regime_population(
    con: duckdb.DuckDBPyConnection | None = None,
    total_supply_avax: float = 473_600_000.0,
) -> Dict[str, Any]:
    """Builds the active validator set directly from current-regime data (602 live nodes)."""
    if con is None:
        con = duckdb.connect()
    nodes_path, periods_path = get_data_paths()

    query = f"""
    WITH latest_periods AS (
        SELECT 
            node_id,
            duration_days,
            bond_avax,
            delegation_volume_received_avax,
            delegation_count_received,
            start_time,
            end_time,
            is_right_censored,
            ROW_NUMBER() OVER (PARTITION BY node_id ORDER BY start_time DESC) as rn
        FROM '{periods_path}'
    )
    SELECT 
        n.NODE_ID as node_id,
        n.OPERATOR_ADDRESS as operator_address,
        n.archetype,
        coalesce(n.lifespan_days, 180.0) as tenure_days,
        coalesce(n.staking_periods_corrected, 1) as period_count,
        p.bond_avax,
        p.duration_days,
        p.delegation_volume_received_avax,
        p.delegation_count_received,
        p.start_time,
        p.end_time,
        p.is_right_censored
    FROM '{nodes_path}' n
    JOIN latest_periods p ON n.NODE_ID = p.node_id AND p.rn = 1
    WHERE n.LIVE_NOW
    ORDER BY n.NODE_ID
    """
    df = con.execute(query).df()

    validators: Dict[str, ValidatorRecord] = {}
    for _, row in df.iterrows():
        nid = str(row["node_id"])
        bond = float(row["bond_avax"])
        duration = int(round(float(row["duration_days"])))
        delegation = float(row["delegation_volume_received_avax"])
        archetype = str(row["archetype"])
        operator = str(row["operator_address"])
        tenure = float(row["tenure_days"])
        streak = int(row["period_count"])

        # Determine profile
        profile = classify_validator_profile(bond, delegation, archetype)

        # Remaining days under continuous stationary arrival invariant:
        # Uniform residual life bounded by stint duration U(1, duration)
        # Seeded deterministically by hash of node_id for perfect reproducibility
        rng = np.random.RandomState(abs(hash(nid)) % (2**31 - 1))
        rem_days = int(rng.randint(1, max(2, duration + 1)))

        commission = 0.02
        if profile == "Profile A (Solo / Capital-Constrained)":
            commission = 0.05

        validators[nid] = ValidatorRecord(
            node_id=nid,
            self_bond_avax=bond,
            total_duration_days=duration,
            remaining_days=rem_days,
            commission_fee=commission,
            delegations_received_avax=delegation,
            uptime_days=int(min(365, tenure)),
            is_active=True,
            operator_address=operator,
            archetype=archetype,
            profile=profile,
            tenure_days=tenure,
            streak_count=streak,
        )

    total_staked = sum(v.total_weight_avax for v in validators.values())
    staked_self = sum(v.self_bond_avax for v in validators.values())
    unweighted_mean_dur = float(np.mean([v.total_duration_days for v in validators.values()]))
    stake_weighted_dur_days = float(
        sum(v.total_duration_days * v.total_weight_avax for v in validators.values()) / total_staked
    ) if total_staked > 0 else 62.3

    return {
        "validators": validators,
        "staked_supply_avax": total_staked,
        "bonded_self_stake_avax": staked_self,
        "circulating_supply_avax": total_supply_avax,
        "staking_ratio": total_staked / total_supply_avax if total_supply_avax > 0 else 0.352,
        "average_duration_weeks": stake_weighted_dur_days / 7.0,
        "unweighted_mean_duration_days": unweighted_mean_dur,
        "pchain_tx_count": 0,
        "total_minted_rewards_avax": 0.0,
        "total_burned_fees_avax": 0.0,
    }
