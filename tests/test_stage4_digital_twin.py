"""Unit tests for Stage 4 Empirical Validator Digital Twin and Admission Mechanism."""

import math
import pytest
import numpy as np

from avalanche_research.simulation.population import (
    load_empirical_priors,
    load_current_regime_population,
    classify_validator_profile,
    ValidatorRecord,
)
from avalanche_research.simulation.mechanism import (
    s_min_admission,
    s_min_integer_navax,
    eta_harmonic,
    AdmissionFrontierConfig,
)
from avalanche_research.simulation.moe import (
    compute_snapshot_metrics,
    evaluate_moes,
)
from avalanche_research.simulation.behavior import (
    run_baseline_behavior,
    run_mechanism_behavior,
)
from avalanche_research.simulation.runner import (
    run_digital_twin_simulation,
)


def test_empirical_population_loading():
    """Verify empirical population loads exactly 602 live nodes and priors."""
    priors = load_empirical_priors()
    assert priors.historical_node_count >= 7600
    assert priors.total_completed_periods >= 56000
    assert 0.70 <= priors.renewal_rates_by_profile["Profile A (Solo / Capital-Constrained)"] <= 0.95
    assert 0.80 <= priors.renewal_rates_by_profile["Profile B (Commercial Delegator-Facing)"] <= 0.99

    state = load_current_regime_population()
    assert len(state["validators"]) == 602
    assert state["staked_supply_avax"] > 300_000_000.0
    assert 0.40 <= state["staking_ratio"] <= 0.90


def test_validator_profile_classification():
    """Verify classification into Profile A, B, and C."""
    assert classify_validator_profile(2000.0, 0.0, "typical_mid") == "Profile A (Solo / Capital-Constrained)"
    assert classify_validator_profile(5000.0, 50000.0, "lst_magnet") == "Profile B (Commercial Delegator-Facing)"
    assert classify_validator_profile(500000.0, 0.0, "institutional") == "Profile C (Institutional / Ecosystem)"


def test_mechanism_mathematical_invariants():
    """Verify boundary conditions, monotonicity, and integer/float agreement."""
    s_short = 14000.0
    s_floor = 500.0
    p = 1.0

    # Boundaries
    assert math.isclose(s_min_admission(2.0, s_short, s_floor, p), s_short)
    assert math.isclose(s_min_admission(365.0, s_short, s_floor, p), s_floor)

    # Monotonicity
    durations = [2.0, 14.0, 30.0, 60.0, 90.0, 180.0, 365.0]
    stakes = [s_min_admission(d, s_short, s_floor, p) for d in durations]
    for i in range(len(stakes) - 1):
        assert stakes[i] > stakes[i + 1]

    # Integer nAVAX agreement
    d_sec = 14 * 86400
    float_stake = s_min_admission(14.0, s_short, s_floor, p)
    int_stake_navax = s_min_integer_navax(d_sec, int(s_short * 1e9), int(s_floor * 1e9), p)
    assert math.isclose(float_stake, int_stake_navax / 1e9, rel_tol=1e-4)


def test_moe_calculations_and_operator_clustering():
    """Verify MOE calculations including operator clustering concentration."""
    state = load_current_regime_population()
    snap = compute_snapshot_metrics(0, state["validators"])

    assert snap.active_node_count == 602
    assert snap.hhi_node > 0.0
    # Operator HHI must be strictly greater than node HHI due to multi-node clustering
    assert snap.hhi_operator > snap.hhi_node
    assert snap.c10_operator > snap.c10_node
    assert snap.viability_profile_a == 1.0

    moes = evaluate_moes([snap])
    assert 0.0 <= moes.moe5_capacity_headroom_hcap <= 1.0


def test_baseline_and_mechanism_simulation_execution():
    """Verify simulation runner executes cleanly for both baseline and mechanism modes."""
    # Short 4-step run for quick testing
    base_res = run_digital_twin_simulation(mode="baseline", timesteps=4, seed=123)
    assert len(base_res.trajectory_df) == 5
    assert base_res.moes.moe1_set_stability_sn >= 0.0

    mech_res = run_digital_twin_simulation(
        mode="mechanism",
        s_floor=500.0,
        s_short=14000.0,
        p=1.0,
        yield_scenario="Y2",
        timesteps=4,
        seed=123,
    )
    assert len(mech_res.trajectory_df) == 5
    assert mech_res.moes.moe5_capacity_headroom_hcap > 0.0


def test_capital_dependent_duration_transitions():
    """Verify capital scale modulates duration persistence and transitions."""
    from avalanche_research.simulation.behavior import sample_conditional_duration
    priors = load_empirical_priors()
    rng = np.random.RandomState(42)

    # 100 draws for small validator starting at 15d
    small_draws = [
        sample_conditional_duration(15, 2000.0, "Profile A (Solo / Capital-Constrained)", priors, rng)
        for _ in range(100)
    ]
    # Small stakers should predominantly choose <= 21 days (> 80%)
    assert sum(1 for d in small_draws if d <= 21) >= 80

    # 100 draws for whale validator starting at 90d
    whale_draws = [
        sample_conditional_duration(90, 500000.0, "Profile C (Institutional / Ecosystem)", priors, rng)
        for _ in range(100)
    ]
    # Whale stakers should predominantly choose >= 60 days (> 70%)
    assert sum(1 for d in whale_draws if d >= 60) >= 70


def test_effective_delegation_access_model():
    """Verify multi-layer delegation model: protocol firewall, Profile A exclusion, and provider scaling."""
    from avalanche_research.simulation.behavior import compute_effective_delegation
    priors = load_empirical_priors()
    rng = np.random.RandomState(42)

    # 1. Protocol firewall: sub-14d receives 0.0 delegation
    assert compute_effective_delegation(10000.0, 7, "typical_mid", "Profile B (Commercial)", 0.02, priors, rng) == 0.0
    assert compute_effective_delegation(10000.0, 2, "typical_mid", "Profile B (Commercial)", 0.02, priors, rng) == 0.0

    # 2. Profile A receives 0.0 delegation
    assert compute_effective_delegation(2000.0, 30, "typical_mid", "Profile A (Solo / Capital-Constrained)", 0.02, priors, rng) == 0.0

    # 3. Provider scaling: bond < 6000 AVAX excluded from BENQI Open Pool
    del_small = [
        compute_effective_delegation(3000.0, 30, "typical_mid", "Profile B (Commercial)", 0.02, priors, rng)
        for _ in range(100)
    ]
    del_large = [
        compute_effective_delegation(10000.0, 30, "typical_mid", "Profile B (Commercial)", 0.02, priors, rng)
        for _ in range(100)
    ]
    # Mean capacity utilization of large validator should exceed small validator due to Open Pool access
    util_small = np.mean(del_small) / 3000.0
    util_large = np.mean(del_large) / 10000.0
    assert util_large >= util_small

    # 4. Long durations receive higher utilization than short durations (gradient)
    del_15d = [
        compute_effective_delegation(10000.0, 15, "typical_mid", "Profile B (Commercial)", 0.02, priors, rng)
        for _ in range(200)
    ]
    del_365d = [
        compute_effective_delegation(10000.0, 365, "typical_mid", "Profile B (Commercial)", 0.02, priors, rng)
        for _ in range(200)
    ]
    assert np.mean(del_365d) > np.mean(del_15d) * 5.0


def test_capital_duration_and_delegation_diagnostics():
    """Verify enriched snapshot metrics and MOEResults report composition and diagnostics."""
    state = load_current_regime_population()
    snap = compute_snapshot_metrics(0, state["validators"])

    assert snap.profile_a_count >= 50
    assert 0.05 <= snap.profile_a_share <= 0.25
    assert snap.eligible_zero_delegation_pct >= 0.20
    assert snap.mean_nodes_per_operator >= 1.0

    res = run_digital_twin_simulation(mode="baseline", timesteps=2, seed=42)
    assert res.moes.final_profile_a_count > 0
    assert res.moes.final_profile_a_share > 0.0
    assert res.moes.mean_eligible_zero_delegation_pct > 0.0

