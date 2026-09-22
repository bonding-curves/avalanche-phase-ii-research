"""Unit tests for the Avalanche Duration-Dependent Admission Simulation."""

import pytest
import math
from avalanche_research.simulation.policies import (
    s_min_harmonic,
    solve_harmonic_exponent,
    s_min_piecewise_benqi,
)
from avalanche_research.simulation.state import get_initial_pchain_state, ValidatorRecord
from avalanche_research.simulation.model import build_avalanche_model
from gds_sim import Simulation


def test_harmonic_boundary_invariants():
    """Verify S_min(365) == 500 and S_min(2) == s_short for arbitrary parameters."""
    for s_short in [10_000.0, 20_000.0, 50_000.0]:
        for p in [0.45, 0.642, 0.85]:
            val_365 = s_min_harmonic(365.0, s_short, p)
            assert math.isclose(val_365, 500.0, abs_tol=1e-5), f"Failed at 365d: {val_365}"

            val_2 = s_min_harmonic(2.0, s_short, p)
            assert math.isclose(val_2, s_short, abs_tol=1e-5), f"Failed at 2d: {val_2}"


def test_global_sybil_constraint():
    """Verify S(d)*d >= 28,000 AVAX-days globally for all d in [2, 365] when S_short >= 14,000."""
    for s_short in [14_000.0, 20_000.0]:
        for d_w in [6, 8, 10, 12, 16.9]:
            d_target = d_w * 7
            p = solve_harmonic_exponent(d_target, s_short, 2000.0)
            for d in [2, 7, 14, 30, 60, 84, 119, 180, 365]:
                stake = s_min_harmonic(d, s_short, p)
                commitment = stake * d
                assert commitment >= 27_999.0, f"Sybil violation at d={d}: commitment={commitment}"


def test_piecewise_benqi_invariants():
    """Verify piecewise BENQI frontier pins 2d, 14d (6000), d_target (2000), and 365d (500)."""
    s_short = 20_000.0
    d_target = 84.0
    assert math.isclose(s_min_piecewise_benqi(2.0, s_short, d_target), 20_000.0)
    assert math.isclose(s_min_piecewise_benqi(14.0, s_short, d_target), 6_000.0)
    assert math.isclose(s_min_piecewise_benqi(84.0, s_short, d_target), 2_000.0)
    assert math.isclose(s_min_piecewise_benqi(365.0, s_short, d_target), 500.0)


def test_initial_state_generation():
    """Verify default initial state contains expected cohorts and non-zero aggregates."""
    state = get_initial_pchain_state()
    assert "validators" in state
    assert len(state["validators"]) == 775
    assert state["staked_supply_avax"] > 0
    assert 0.0 < state["staking_ratio"] < 1.0


def test_simulation_execution():
    """Verify a small multi-step simulation executes cleanly without state corruption."""
    model = build_avalanche_model()
    sim = Simulation(model=model, timesteps=4)
    results = sim.run()
    df = results.to_dataframe()
    # Initial state (substep 0) + 4 timesteps * 3 substeps = 13 rows
    assert len(df) == 13
    
    # Invariant: Staking ratio remains within healthy bounds
    for ratio in df["staking_ratio"]:
        assert 0.45 <= ratio <= 0.65, f"Staking ratio out of bounds: {ratio}"
    for avg_w in df["average_duration_weeks"]:
        assert avg_w > 0.0
