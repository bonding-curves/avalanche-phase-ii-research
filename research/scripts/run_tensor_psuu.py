"""
Backend engine for the Avalanche Admission Frontier PSUU Parameter Sweep.
Uses the N-Dimensional Tensor and Decision Tree approach to isolate the admission frontier.
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd



from gds_analysis.psuu import (
    Discrete,
    ParameterSpace,
    KPI,
    Sweep,
    GridSearchOptimizer,
)
from avalanche_research.simulation.model import build_avalanche_model


def run_tensor_psuu():
    print("=" * 80)
    print("🚀 INITIALIZING N-DIMENSIONAL PSuU TENSOR SWEEP")
    print("Approach: Subspace Reference Model (Utility Tensor + Decision Analysis)")
    print("=" * 80)

    model = build_avalanche_model()

    # 1. Define the Parameter Space (The Governance & Environment Dimensions)
    d_targets_days = [28.0, 42.0, 56.0, 70.0, 84.0, 98.0, 118.0]
    s_shorts = [10_000.0, 12_000.0, 14_000.0, 16_000.0, 18_000.0, 20_000.0]
    modes = ["harmonic", "piecewise_benqi"]

    space = ParameterSpace(
        params={
            "d_target_days": Discrete(values=d_targets_days),
            "s_short": Discrete(values=s_shorts),
            "frontier_mode": Discrete(values=modes),
        }
    )

    # 2. Define KPIs (Metrics to reduce timestep trajectories into single values)
    def kpi_retail_retention(results) -> float:
        df = results.to_dataframe()
        last_validators = df["validators"].iloc[-1]
        retail_active = sum(1 for nid, v in last_validators.items() if nid.startswith("Retail") and v.is_active)
        return float(retail_active / 229.0)

    def kpi_stake_weighted_duration_weeks(results) -> float:
        df = results.to_dataframe()
        return float(df["average_duration_weeks"].iloc[-1])

    def kpi_retail_mean_duration_days(results) -> float:
        df = results.to_dataframe()
        last_validators = df["validators"].iloc[-1]
        retail_nodes = [v for nid, v in last_validators.items() if nid.startswith("Retail") and v.is_active]
        return float(np.mean([v.total_duration_days for v in retail_nodes])) if retail_nodes else 0.0

    kpis = [
        KPI(name="retail_retention", fn=kpi_retail_retention),
        KPI(name="stake_weighted_duration_weeks", fn=kpi_stake_weighted_duration_weeks),
        KPI(name="retail_mean_duration_days", fn=kpi_retail_mean_duration_days),
    ]

    sweep = Sweep(
        model=model,
        space=space,
        kpis=kpis,
        optimizer=GridSearchOptimizer(),
        timesteps=52,
        runs=1,
    )

    # 3. Execute the Sweep to build the Trajectory Tensor
    total_evals = len(d_targets_days) * len(s_shorts) * len(modes)
    print(f"Sweeping {total_evals} coordinate combinations on post-Etna calibrated network...")
    results = sweep.run()
    print("Sweep complete. Generating Utility Tensor...")

    records = []
    # Post-Etna empirical ground truth median is 15.0 days
    baseline_retail_days = 15.0

    for ev in results.evaluations:
        d_target_d = ev.params["d_target_days"]
        s_short = ev.params["s_short"]
        mode = ev.params["frontier_mode"]
        
        retention = ev.scores["retail_retention"]
        macro_dur = ev.scores["stake_weighted_duration_weeks"]
        retail_dur = ev.scores["retail_mean_duration_days"]
        lift_pct = ((retail_dur - baseline_retail_days) / baseline_retail_days) * 100.0

        # UTILITY FUNCTION (Verification Gate)
        # Success criteria calibrated to Helicon & Foundation goals: 
        # 1. Retail Retention >= 50% (preserves >= 115 out of 229 active nodes)
        # 2. Macro duration >= 16.9 weeks (Dr. Eric Lu's target, lifted from 8.9w post-Etna baseline)
        # 3. Retail Lift >= 50% above post-Etna 15-day median
        is_successful = (retention >= 0.50) and (macro_dur >= 16.9) and (lift_pct >= 50.0)
        
        records.append({
            "d_target_days": d_target_d,
            "s_short": s_short,
            "frontier_mode": mode,
            "retail_retention": retention,
            "macro_duration_w": macro_dur,
            "retail_lift_pct": lift_pct,
            "utility": 1 if is_successful else 0
        })

    df = pd.DataFrame(records)

    # 4. Decision Analysis: Isolate the Algorithmic Frontier
    print("-" * 80)
    print("DECISION ANALYSIS: EXTRACTING ADMISSION FRONTIER RULES (POST-HELICON CALIBRATION)")
    print("-" * 80)
    
    # Filter to successful parameter sets
    success_df = df[df['utility'] == 1]
    
    if success_df.empty:
        print("Boundary warning: No coordinates resulted in success (utility = 1).")
    elif len(success_df) == len(df):
        print("Boundary warning: All coordinates resulted in success (utility = 1).")
    else:
        print("ALGORITHMIC ADMISSION FRONTIER (utility = 1):")
        # Find minimum boundaries for success
        min_d_target = success_df['d_target_days'].min()
        min_s_short = success_df['s_short'].min()
        
        print(f"Rule 1: d_target_days MUST be >= {min_d_target}")
        print(f"Rule 2: s_short MUST be >= {min_s_short:,.0f} AVAX")
        print("\nSafe Envelope (Valid Configurations):")
        print(success_df[['frontier_mode', 's_short', 'd_target_days', 'retail_retention', 'macro_duration_w']].to_string(index=False))

    # 5. Export multi-dimensional tensor for reproducibility
    tensor_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'psuu_utility_tensor.csv'))
    helicon_tensor_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'psuu_utility_tensor_helicon.csv'))
    os.makedirs(os.path.dirname(tensor_path), exist_ok=True)
    
    df.to_csv(tensor_path, index=False)
    df.to_csv(helicon_tensor_path, index=False)
    print(f"\n[!] Trajectory/Utility Tensor explicitly saved to: {tensor_path} and {helicon_tensor_path}")
    print("=" * 80)

if __name__ == "__main__":
    run_tensor_psuu()

