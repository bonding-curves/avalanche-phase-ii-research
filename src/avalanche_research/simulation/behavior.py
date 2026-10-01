"""Modular Behavioral Policies for Avalanche Validator Digital Twin.

Includes:
1. Baseline Empirical Replay Policy:
   - Replays observed historical renewal rates, capital-dependent duration transitions,
     and effective delegation access.
2. Candidate Mechanism Policy under Bounded Yield Scenarios:
   - Admissibility filter based on S_min(d).
   - Capital-dependent duration choice and liquidity friction.
   - Effective delegation access incorporating provider rules and utilization gradients.
   - Scenario Y1: Low yield sensitivity (habitual persistence).
   - Scenario Y2: Moderate yield sensitivity (proportional utility tradeoff).
   - Scenario Y3: High yield sensitivity (aggressive yield optimization).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Any, Tuple
import numpy as np

from avalanche_research.simulation.population import (
    ValidatorRecord,
    EmpiricalPriors,
    classify_capital_tier,
    get_duration_bucket,
)
from avalanche_research.simulation.mechanism import s_min_admission


# ACP-285 ARR Schedule (Helicon post-ramp at ~470M AVAX supply)
ACP285_YIELD_SCHEDULE = {
    2: 0.03950,
    14: 0.04078,
    30: 0.04183,
    60: 0.04353,
    90: 0.04536,
    180: 0.05166,
    365: 0.06378,
}
STANDARD_DURATIONS = [2, 14, 30, 60, 90, 180, 365]

# Empirical Transition Distributions by Capital Tier and Previous Duration Bucket
# Rows: Previous duration bucket. Columns: Next duration bucket
# Order: ['14-21d', '22-35d', '36-65d', '66-95d', '96-185d', '186-365d']
TIER_TRANSITIONS = {
    "Tier 1: Small (<=2.5k)": {
        "14-21d": [0.930, 0.055, 0.007, 0.005, 0.002, 0.001],
        "22-35d": [0.112, 0.740, 0.090, 0.035, 0.015, 0.008],
        "36-65d": [0.088, 0.350, 0.400, 0.110, 0.035, 0.017],
        "66-95d": [0.049, 0.120, 0.110, 0.570, 0.115, 0.036],
        "96-185d": [0.046, 0.080, 0.070, 0.250, 0.410, 0.144],
        "186-365d": [0.089, 0.070, 0.040, 0.130, 0.160, 0.511],
        "<14d": [0.600, 0.250, 0.080, 0.040, 0.020, 0.010],
    },
    "Tier 5: Whale (>100k)": {
        "14-21d": [0.844, 0.085, 0.025, 0.020, 0.012, 0.014],
        "22-35d": [0.151, 0.650, 0.110, 0.050, 0.020, 0.019],
        "36-65d": [0.057, 0.200, 0.420, 0.180, 0.085, 0.058],
        "66-95d": [0.017, 0.080, 0.080, 0.622, 0.140, 0.061],
        "96-185d": [0.047, 0.060, 0.050, 0.180, 0.480, 0.183],
        "186-365d": [0.068, 0.040, 0.020, 0.080, 0.120, 0.672],
        "<14d": [0.200, 0.200, 0.100, 0.200, 0.150, 0.150],
    },
    "Mid": {
        "14-21d": [0.762, 0.150, 0.045, 0.025, 0.010, 0.008],
        "22-35d": [0.113, 0.720, 0.105, 0.038, 0.014, 0.010],
        "36-65d": [0.089, 0.280, 0.440, 0.120, 0.045, 0.026],
        "66-95d": [0.062, 0.100, 0.100, 0.507, 0.165, 0.066],
        "96-185d": [0.047, 0.080, 0.065, 0.220, 0.430, 0.158],
        "186-365d": [0.067, 0.060, 0.035, 0.120, 0.170, 0.548],
        "<14d": [0.350, 0.250, 0.150, 0.100, 0.080, 0.070],
    },
}

BUCKETS_ORDER = ["14-21d", "22-35d", "36-65d", "66-95d", "96-185d", "186-365d"]


def sample_conditional_duration(
    prev_d: int,
    bond_avax: float,
    profile: str,
    priors: EmpiricalPriors | None = None,
    rng: np.random.RandomState | None = None,
) -> int:
    """Samples next duration conditioned on previous duration, capital tier, and profile."""
    if rng is None:
        rng = np.random.RandomState()

    tier = classify_capital_tier(bond_avax)
    prev_b = get_duration_bucket(prev_d)

    # Determine transition lookup tier
    if tier == "Tier 1: Small (<=2.5k)":
        tier_key = "Tier 1: Small (<=2.5k)"
    elif tier == "Tier 5: Whale (>100k)":
        tier_key = "Tier 5: Whale (>100k)"
    else:
        tier_key = "Mid"

    trans_dict = TIER_TRANSITIONS[tier_key]
    b_probs = trans_dict.get(prev_b, trans_dict["14-21d"])
    b_probs = np.array(b_probs, dtype=float)
    b_probs = b_probs / np.sum(b_probs)

    chosen_b = rng.choice(BUCKETS_ORDER, p=b_probs)

    # Sample discrete days within chosen bucket
    if chosen_b == "14-21d":
        return int(rng.choice([14, 15, 21], p=[0.40, 0.50, 0.10]))
    elif chosen_b == "22-35d":
        return int(rng.choice([28, 30, 31], p=[0.15, 0.45, 0.40]))
    elif chosen_b == "36-65d":
        return int(rng.choice([60, 61, 62], p=[0.30, 0.40, 0.30]))
    elif chosen_b == "66-95d":
        return int(rng.choice([90, 91, 92], p=[0.30, 0.40, 0.30]))
    elif chosen_b == "96-185d":
        return int(rng.choice([120, 180], p=[0.40, 0.60]))
    else:
        return 365


def compute_effective_delegation(
    bond_avax: float,
    duration_days: int,
    archetype: str,
    profile: str,
    commission_fee: float = 0.02,
    priors: EmpiricalPriors | None = None,
    rng: np.random.RandomState | None = None,
) -> float:
    """Computes effective delegation received based on protocol and provider constraints.

    Multi-layer model:
    1. Protocol rule: d >= 14 days required. Sub-14d receives strictly 0.0.
    2. Profile rule: Profile A (Solo) receives strictly 0.0 (100% self-funded).
    3. Provider rules (BENQI):
       - Open Pool (65% share) requires S >= 6,000 AVAX, fee <= 2%.
       - Miles Pool (35% share) requires S >= 2,000 AVAX, fee <= 5%, conditioned on votes.
       - If fee > 5%, excluded from BENQI entirely.
    4. Duration gradient: retail and institutional demand scales from 3.9% (14-21d) to 221% (186-365d).
    5. Capacity cap: maximum delegation is 4x self-bond.
    """
    if rng is None:
        rng = np.random.RandomState()

    # 1. Profile A solo stakers earn zero delegation
    if "Profile A" in profile:
        return 0.0

    # 2. Protocol firewall: sub-14d staking cannot receive delegation
    if duration_days < 14:
        return 0.0

    bucket = get_duration_bucket(duration_days)

    # Base probability and capacity utilization from priors or canonical gradients
    if priors and priors.delegation_prob_by_bucket:
        base_prob = priors.delegation_prob_by_bucket.get(bucket, 0.50)
        base_util = priors.delegation_util_by_bucket.get(bucket, 0.50)
    else:
        prob_map = {
            "<14d": 0.0, "14-21d": 0.274, "22-35d": 0.658, "36-65d": 0.732,
            "66-95d": 0.701, "96-185d": 0.716, "186-365d": 0.841,
        }
        util_map = {
            "<14d": 0.0, "14-21d": 0.039, "22-35d": 0.211, "36-65d": 0.408,
            "66-95d": 0.607, "96-185d": 1.108, "186-365d": 2.210,
        }
        base_prob = prob_map.get(bucket, 0.50)
        base_util = util_map.get(bucket, 0.50)

    # 3. Provider constraints
    if commission_fee > 0.05:
        # Excluded from BENQI entirely; retail P2P channel only
        provider_scale = 0.20
    elif bond_avax < 6000.0:
        # Excluded from BENQI Open Pool (65%); eligible only for Miles Pool (35%) + retail
        provider_scale = 0.55
    else:
        # Eligible for Open Pool (65%) + Miles Pool (35%) + retail
        provider_scale = 1.00

    # LST magnet boost
    if archetype == "lst_magnet":
        base_prob = min(0.95, base_prob * 1.25)
        base_util = base_util * 1.30

    eff_prob = base_prob * provider_scale
    if rng.rand() > eff_prob:
        return 0.0

    # Draw realized utilization with lognormal dispersion around conditional mean
    mean_target = max(1e-4, base_util * provider_scale)
    util_draw = float(rng.lognormal(mean=np.log(mean_target), sigma=0.4))
    util_draw = min(4.0, max(0.01, util_draw))

    realized_deleg = float(round(bond_avax * util_draw, 1))
    # Cap at protocol max (4x self-bond)
    return min(4.0 * bond_avax, realized_deleg)


@dataclass
class PolicyDecisions:
    """Validator renewal, exit, and arrival decisions at a timestep."""
    renewals: Dict[str, Dict[str, Any]]
    exits: List[str]
    new_entrants: List[ValidatorRecord]
    short_arrivals: int
    short_exits: int


def run_baseline_behavior(
    validators: Dict[str, ValidatorRecord],
    priors: EmpiricalPriors,
    dt_days: int = 7,
    rng: np.random.RandomState | None = None,
) -> PolicyDecisions:
    """Executes baseline behavioral decisions replaying empirical conditional rates."""
    if rng is None:
        rng = np.random.RandomState()

    renewals: Dict[str, Dict[str, Any]] = {}
    exits: List[str] = []
    short_arrivals = 0
    short_exits = 0

    for nid, val in validators.items():
        if not val.is_active:
            continue
        if val.remaining_days <= dt_days:
            # Expiring validator: evaluate renewal probability from empirical priors
            ren_prob = priors.renewal_rates_by_profile.get(val.profile, 0.85)
            if rng.rand() < ren_prob:
                # Renewing: sample next duration conditioned on (d_t, S, Profile)
                chosen_d = sample_conditional_duration(
                    prev_d=val.total_duration_days,
                    bond_avax=val.self_bond_avax,
                    profile=val.profile,
                    priors=priors,
                    rng=rng,
                )

                # Recompute effective delegation upon renewal
                new_deleg = compute_effective_delegation(
                    bond_avax=val.self_bond_avax,
                    duration_days=chosen_d,
                    archetype=val.archetype,
                    profile=val.profile,
                    commission_fee=val.commission_fee,
                    priors=priors,
                    rng=rng,
                )

                renewals[nid] = {
                    "action": "renew",
                    "duration_days": chosen_d,
                    "bond_avax": val.self_bond_avax,
                    "delegations_received_avax": new_deleg,
                }
                if chosen_d < 14:
                    short_arrivals += 1
            else:
                exits.append(nid)
                if val.total_duration_days < 14:
                    short_exits += 1

    # Incoming new entrants (Poisson arrival around empirical calibrated mean)
    n_new = rng.poisson(priors.mean_weekly_entries * (dt_days / 7.0))
    new_entrants: List[ValidatorRecord] = []
    existing_ops = [v.operator_address for v in validators.values() if v.operator_address]

    for i in range(n_new):
        new_id = f"Entrant-{rng.randint(1_000_000, 9_999_999)}"
        # Post-contraction empirical profile proportions: ~25% solo, ~50% commercial, ~25% institutional
        prof_roll = rng.rand()
        if prof_roll < 0.25:
            prof = "Profile A (Solo / Capital-Constrained)"
            bond = float(rng.uniform(2000.0, 2200.0))
            d = sample_conditional_duration(15, bond, prof, priors, rng)
            deleg = 0.0
            commission = 0.05
        elif prof_roll < 0.75:
            prof = "Profile B (Commercial Delegator-Facing)"
            bond = float(rng.uniform(2500.0, 20000.0))
            d = sample_conditional_duration(30, bond, prof, priors, rng)
            commission = 0.02
            deleg = compute_effective_delegation(bond, d, "typical_mid", prof, commission, priors, rng)
        else:
            prof = "Profile C (Institutional / Ecosystem)"
            bond = float(rng.uniform(100000.0, 1000000.0))
            d = sample_conditional_duration(90, bond, prof, priors, rng)
            commission = 0.02
            deleg = compute_effective_delegation(bond, d, "institutional", prof, commission, priors, rng)

        # 59% replacement from existing operator, 41% genuinely new operator entity
        if existing_ops and rng.rand() < 0.59:
            op_addr = str(rng.choice(existing_ops))
        else:
            op_addr = f"op-{new_id}"

        new_entrants.append(
            ValidatorRecord(
                node_id=new_id,
                self_bond_avax=bond,
                total_duration_days=d,
                remaining_days=d,
                commission_fee=commission,
                delegations_received_avax=deleg,
                uptime_days=0,
                is_active=True,
                operator_address=op_addr,
                archetype="entrant",
                profile=prof,
                tenure_days=0.0,
                streak_count=1,
            )
        )
        if d < 14:
            short_arrivals += 1

    return PolicyDecisions(
        renewals=renewals,
        exits=exits,
        new_entrants=new_entrants,
        short_arrivals=short_arrivals,
        short_exits=short_exits,
    )



def run_mechanism_behavior(
    validators: Dict[str, ValidatorRecord],
    priors: EmpiricalPriors,
    s_floor: float = 500.0,
    s_short: float = 14_000.0,
    p: float = 1.0,
    yield_scenario: str = "Y2",  # 'Y1', 'Y2', or 'Y3'
    dt_days: int = 7,
    rng: np.random.RandomState | None = None,
) -> PolicyDecisions:
    """Executes behavioral decisions under candidate mechanism S_min(d) and yield sensitivity scenario."""
    if rng is None:
        rng = np.random.RandomState()

    renewals: Dict[str, Dict[str, Any]] = {}
    exits: List[str] = []
    short_arrivals = 0
    short_exits = 0

    # Sensitivity multipliers across bounded scenarios
    if yield_scenario == "Y1":
        beta_yield = 0.0     # Habitual lockup, zero yield sensitivity
        base_lockup = 1.5
    elif yield_scenario == "Y3":
        beta_yield = 30.0    # Highly aggressive yield chasing
        base_lockup = 0.5
    else:  # Y2 (Moderate)
        beta_yield = 12.0    # Proportional substitution with friction
        base_lockup = 1.0

    for nid, val in validators.items():
        if not val.is_active:
            continue

        if val.remaining_days <= dt_days:
            # Check feasibility across candidate standard durations under S_min(d)
            feasible_d = [
                d for d in STANDARD_DURATIONS
                if s_min_admission(d, s_short, s_floor, p) <= val.self_bond_avax
            ]

            if not feasible_d:
                # Capital cannot meet S_min for ANY admissible duration (e.g. bond < S_floor)
                exits.append(nid)
                if val.total_duration_days < 14:
                    short_exits += 1
                continue

            # Base renewal probability from empirical prior
            base_ren_prob = priors.renewal_rates_by_profile.get(val.profile, 0.85)

            # Sample preferred conditional duration P(d | d_t, S, Profile)
            preferred_d = sample_conditional_duration(
                prev_d=val.total_duration_days,
                bond_avax=val.self_bond_avax,
                profile=val.profile,
                priors=priors,
                rng=rng,
            )

            is_blocked = preferred_d not in feasible_d

            if is_blocked:
                # Forced duration extension: illiquidity friction penalty
                shortest_feasible = min(feasible_d)
                lockup_increase_ratio = shortest_feasible / max(2, preferred_d)
                if "Profile A" in val.profile:
                    # Solo validators have tighter liquidity constraints
                    adjusted_ren_prob = max(0.40, base_ren_prob - 0.08 * math.log(lockup_increase_ratio))
                else:
                    adjusted_ren_prob = max(0.60, base_ren_prob - 0.03 * math.log(lockup_increase_ratio))
            else:
                adjusted_ren_prob = base_ren_prob

            # Renewal decision
            if rng.rand() < adjusted_ren_prob:
                tier = classify_capital_tier(val.self_bond_avax)
                tier_lockup_multiplier = 2.0 if "Small" in tier else (0.5 if "Whale" in tier else 1.0)
                effective_beta_lockup = base_lockup * tier_lockup_multiplier

                if yield_scenario == "Y1":
                    # Y1: Habitual persistence. Pick shortest feasible duration >= preferred_d
                    eligible = [d for d in feasible_d if d >= preferred_d]
                    chosen_d = min(eligible) if eligible else min(feasible_d)
                else:
                    # Y2 / Y3: Utility-based discrete choice over feasible durations
                    utilities = []
                    for d in feasible_d:
                        arr = ACP285_YIELD_SCHEDULE.get(d, 0.04078 + 0.023 * (d / 365.0))
                        lockup_cost = effective_beta_lockup * ((d - 2.0) / 365.0)
                        u = beta_yield * (arr - 0.03950) - lockup_cost
                        utilities.append(u)

                    max_u = max(utilities)
                    exp_u = np.exp([u - max_u for u in utilities])
                    probs = exp_u / np.sum(exp_u)
                    chosen_d = int(rng.choice(feasible_d, p=probs))

                # Recompute effective delegation for chosen duration
                new_deleg = compute_effective_delegation(
                    bond_avax=val.self_bond_avax,
                    duration_days=chosen_d,
                    archetype=val.archetype,
                    profile=val.profile,
                    commission_fee=val.commission_fee,
                    priors=priors,
                    rng=rng,
                )

                renewals[nid] = {
                    "action": "renew",
                    "duration_days": chosen_d,
                    "bond_avax": val.self_bond_avax,
                    "delegations_received_avax": new_deleg,
                }
                if chosen_d < 14:
                    short_arrivals += 1
            else:
                exits.append(nid)
                if val.total_duration_days < 14:
                    short_exits += 1

    # Incoming new entrants (Poisson arrival)
    n_new = rng.poisson(priors.mean_weekly_entries * (dt_days / 7.0))
    new_entrants: List[ValidatorRecord] = []
    existing_ops = [v.operator_address for v in validators.values() if v.operator_address]

    for i in range(n_new):
        new_id = f"Entrant-{rng.randint(1_000_000, 9_999_999)}"
        prof_roll = rng.rand()
        if prof_roll < 0.25:
            prof = "Profile A (Solo / Capital-Constrained)"
            bond = float(rng.uniform(max(s_floor, 1000.0), 2200.0))
            commission = 0.05
            arch = "entrant"
        elif prof_roll < 0.75:
            prof = "Profile B (Commercial Delegator-Facing)"
            bond = float(rng.uniform(max(s_floor, 2500.0), 20000.0))
            commission = 0.02
            arch = "typical_mid"
        else:
            prof = "Profile C (Institutional / Ecosystem)"
            bond = float(rng.uniform(100000.0, 1000000.0))
            commission = 0.02
            arch = "institutional"

        # Check admission feasibility
        feasible_d = [
            d for d in STANDARD_DURATIONS
            if s_min_admission(d, s_short, s_floor, p) <= bond
        ]
        if not feasible_d:
            continue

        # Sample preferred duration
        pref_d = sample_conditional_duration(30, bond, prof, priors, rng)
        if pref_d in feasible_d:
            chosen_d = pref_d
        else:
            chosen_d = min(feasible_d)

        deleg = compute_effective_delegation(bond, chosen_d, arch, prof, commission, priors, rng)

        if existing_ops and rng.rand() < 0.59:
            op_addr = str(rng.choice(existing_ops))
        else:
            op_addr = f"op-{new_id}"

        new_entrants.append(
            ValidatorRecord(
                node_id=new_id,
                self_bond_avax=bond,
                total_duration_days=chosen_d,
                remaining_days=chosen_d,
                commission_fee=commission,
                delegations_received_avax=deleg,
                uptime_days=0,
                is_active=True,
                operator_address=op_addr,
                archetype=arch,
                profile=prof,
                tenure_days=0.0,
                streak_count=1,
            )
        )
        if chosen_d < 14:
            short_arrivals += 1

    return PolicyDecisions(
        renewals=renewals,
        exits=exits,
        new_entrants=new_entrants,
        short_arrivals=short_arrivals,
        short_exits=short_exits,
    )
