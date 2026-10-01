"""Digital Twin Simulation Runner and Parameter Sweep Engine.

Executes:
1. Baseline Empirical Replay (Model Validation against historical properties)
2. Mechanism Simulation across Yield Scenarios (Y1, Y2, Y3)
3. Exploratory Parameter Sweeps (S_floor, S_short, p, Macro Stress)
4. Comprehensive MOE Extraction
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Dict, List, Any, Tuple
import numpy as np
import pandas as pd

from avalanche_research.simulation.population import (
    ValidatorRecord,
    EmpiricalPriors,
    load_empirical_priors,
    load_current_regime_population,
)
from avalanche_research.simulation.mechanism import s_min_admission
from avalanche_research.simulation.behavior import (
    run_baseline_behavior,
    run_mechanism_behavior,
    PolicyDecisions,
)
from avalanche_research.simulation.moe import (
    SnapshotMetrics,
    MOEResults,
    compute_snapshot_metrics,
    evaluate_moes,
)


@dataclass
class SimulationRunResult:
    """Complete result from a single simulation trajectory."""
    mode: str
    s_floor: float
    s_short: float
    p: float
    yield_scenario: str
    avax_price_usd: float
    timesteps: int
    moes: MOEResults
    trajectory_df: pd.DataFrame
    final_validators: Dict[str, ValidatorRecord]


def run_digital_twin_simulation(
    mode: str = "baseline",  # 'baseline' or 'mechanism'
    s_floor: float = 500.0,
    s_short: float = 14_000.0,
    p: float = 1.0,
    yield_scenario: str = "Y2",  # 'Y1', 'Y2', or 'Y3'
    avax_price_usd: float = 25.0,
    annual_staking_yield: float = 0.055,
    timesteps: int = 52,  # 52 weeks = 1 year
    dt_days: int = 7,
    seed: int = 42,
    initial_validators: Dict[str, ValidatorRecord] | None = None,
    priors: EmpiricalPriors | None = None,
) -> SimulationRunResult:
    """Executes a multi-timestep digital twin simulation trajectory."""
    rng = np.random.RandomState(seed)

    if priors is None:
        priors = load_empirical_priors()

    if initial_validators is None:
        init_state = load_current_regime_population()
        validators = {nid: copy.deepcopy(v) for nid, v in init_state["validators"].items()}
    else:
        validators = {nid: copy.deepcopy(v) for nid, v in initial_validators.items()}

    snapshots: List[SnapshotMetrics] = []

    # Initial snapshot at t = 0
    snap_0 = compute_snapshot_metrics(
        timestep=0,
        validators=validators,
        arrivals=0,
        exits=0,
        short_arrivals=0,
        short_exits=0,
        avax_price_usd=avax_price_usd,
        annual_staking_yield=annual_staking_yield,
    )
    snapshots.append(snap_0)

    for t in range(1, timesteps + 1):
        # 1. Behavioral policies
        if mode == "baseline":
            decisions = run_baseline_behavior(
                validators=validators,
                priors=priors,
                dt_days=dt_days,
                rng=rng,
            )
        else:
            decisions = run_mechanism_behavior(
                validators=validators,
                priors=priors,
                s_floor=s_floor,
                s_short=s_short,
                p=p,
                yield_scenario=yield_scenario,
                dt_days=dt_days,
                rng=rng,
            )

        # 2. State updates
        # Process exits
        for nid in decisions.exits:
            if nid in validators:
                validators[nid].is_active = False
                validators[nid].remaining_days = 0
                validators[nid].delegations_received_avax = 0.0

        # Process renewals
        for nid, ren in decisions.renewals.items():
            if nid in validators:
                val = validators[nid]
                val.total_duration_days = ren["duration_days"]
                val.remaining_days = ren["duration_days"]
                val.self_bond_avax = ren.get("bond_avax", val.self_bond_avax)
                val.delegations_received_avax = ren.get("delegations_received_avax", val.delegations_received_avax)
                val.streak_count += 1


        # Process time progression for active validators not expiring
        for nid, val in validators.items():
            if val.is_active and nid not in decisions.renewals:
                val.remaining_days = max(0, val.remaining_days - dt_days)
                val.uptime_days += dt_days
                val.tenure_days += dt_days

        # Process new entrants
        for entrant in decisions.new_entrants:
            validators[entrant.node_id] = entrant

        # 3. Snapshot recording
        snap_t = compute_snapshot_metrics(
            timestep=t,
            validators=validators,
            arrivals=len(decisions.new_entrants),
            exits=len(decisions.exits),
            short_arrivals=decisions.short_arrivals,
            short_exits=decisions.short_exits,
            avax_price_usd=avax_price_usd,
            annual_staking_yield=annual_staking_yield,
        )
        snapshots.append(snap_t)

    # 4. Evaluate MOEs
    moe_results = evaluate_moes(snapshots)

    # 5. Trajectory DataFrame
    traj_records = [
        {
            "timestep": s.timestep,
            "active_node_count": s.active_node_count,
            "total_staked_avax": s.total_staked_avax,
            "total_self_bond_avax": s.total_self_bond_avax,
            "total_delegations_avax": s.total_delegations_avax,
            "turnover_rate": s.turnover_rate,
            "hhi_node": s.hhi_node,
            "hhi_operator": s.hhi_operator,
            "c10_operator": s.c10_operator,
            "c20_operator": s.c20_operator,
            "viability_profile_a": s.viability_profile_a,
            "viability_profile_b": s.viability_profile_b,
            "viability_profile_c": s.viability_profile_c,
            "mean_duration_days": s.mean_duration_days,
            "stake_weighted_duration_days": s.stake_weighted_duration_days,
        }
        for s in snapshots
    ]
    df_traj = pd.DataFrame(traj_records)

    return SimulationRunResult(
        mode=mode,
        s_floor=s_floor,
        s_short=s_short,
        p=p,
        yield_scenario=yield_scenario,
        avax_price_usd=avax_price_usd,
        timesteps=timesteps,
        moes=moe_results,
        trajectory_df=df_traj,
        final_validators=validators,
    )


def run_exploratory_parameter_sweep(
    s_floors: List[float] = [500.0, 1000.0, 2000.0],
    s_shorts: List[float] = [10_000.0, 14_000.0, 20_000.0],
    powers: List[float] = [1.0, 1.5, 2.0],
    yield_scenarios: List[str] = ["Y1", "Y2", "Y3"],
    stress_prices: List[float] = [25.0, 15.0],
    timesteps: int = 52,
    seed: int = 42,
) -> pd.DataFrame:
    """Executes a structured exploratory parameter sweep across policy and behavioral dimensions."""
    priors = load_empirical_priors()
    init_state = load_current_regime_population()
    init_vals = init_state["validators"]

    records = []

    # 1. First run baseline replay
    print("Running baseline empirical replay...")
    base_res = run_digital_twin_simulation(
        mode="baseline",
        timesteps=timesteps,
        seed=seed,
        initial_validators=init_vals,
        priors=priors,
    )
    records.append({
        "mode": "baseline",
        "s_floor": 2000.0,
        "s_short": 2000.0,
        "p": 1.0,
        "yield_scenario": "empirical_baseline",
        "avax_price_usd": 25.0,
        "final_node_count": base_res.trajectory_df["active_node_count"].iloc[-1],
        "moe1_stability_sn": base_res.moes.moe1_set_stability_sn,
        "moe2_turnover_rate": base_res.moes.moe2_mean_turnover_rate,
        "moe2_short_churn": base_res.moes.moe2_mean_short_churn_rate,
        "moe3_hhi_node": base_res.moes.moe3_terminal_hhi_node,
        "moe3_hhi_operator": base_res.moes.moe3_terminal_hhi_operator,
        "moe3_c10_operator": base_res.moes.moe3_terminal_c10_operator,
        "moe4_viab_a": base_res.moes.moe4_viability_profile_a,
        "moe4_viab_b": base_res.moes.moe4_viability_profile_b,
        "moe4_viab_c": base_res.moes.moe4_viability_profile_c,
        "moe5_headroom_hcap": base_res.moes.moe5_capacity_headroom_hcap,
        "terminal_mean_duration": base_res.trajectory_df["mean_duration_days"].iloc[-1],
        "terminal_stake_weighted_dur": base_res.trajectory_df["stake_weighted_duration_days"].iloc[-1],
    })

    # 2. Run mechanism sweeps across S_floor, S_short, p, Yield scenarios, and Stress Prices
    total_runs = len(s_floors) * len(s_shorts) * len(powers) * len(yield_scenarios) * len(stress_prices)
    print(f"Running mechanism exploratory sweep ({total_runs} combinations)...")
    run_idx = 0

    for s_floor in s_floors:
        for s_short in s_shorts:
            for p in powers:
                for y_scen in yield_scenarios:
                    for price in stress_prices:
                        run_idx += 1
                        res = run_digital_twin_simulation(
                            mode="mechanism",
                            s_floor=s_floor,
                            s_short=s_short,
                            p=p,
                            yield_scenario=y_scen,
                            avax_price_usd=price,
                            timesteps=timesteps,
                            seed=seed,
                            initial_validators=init_vals,
                            priors=priors,
                        )
                        records.append({
                            "mode": "mechanism",
                            "s_floor": s_floor,
                            "s_short": s_short,
                            "p": p,
                            "yield_scenario": y_scen,
                            "avax_price_usd": price,
                            "final_node_count": res.trajectory_df["active_node_count"].iloc[-1],
                            "moe1_stability_sn": res.moes.moe1_set_stability_sn,
                            "moe2_turnover_rate": res.moes.moe2_mean_turnover_rate,
                            "moe2_short_churn": res.moes.moe2_mean_short_churn_rate,
                            "moe3_hhi_node": res.moes.moe3_terminal_hhi_node,
                            "moe3_hhi_operator": res.moes.moe3_terminal_hhi_operator,
                            "moe3_c10_operator": res.moes.moe3_terminal_c10_operator,
                            "moe4_viab_a": res.moes.moe4_viability_profile_a,
                            "moe4_viab_b": res.moes.moe4_viability_profile_b,
                            "moe4_viab_c": res.moes.moe4_viability_profile_c,
                            "moe5_headroom_hcap": res.moes.moe5_capacity_headroom_hcap,
                            "terminal_mean_duration": res.trajectory_df["mean_duration_days"].iloc[-1],
                            "terminal_stake_weighted_dur": res.trajectory_df["stake_weighted_duration_days"].iloc[-1],
                        })

    df_sweep = pd.DataFrame(records)
    return df_sweep
