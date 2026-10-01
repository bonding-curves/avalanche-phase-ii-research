"""Stage 4 Simulation Runner Script.

Executes:
1. Baseline Empirical Replay
2. Mechanism Evaluation under Y1, Y2, Y3
3. Exploratory Parameter Sweep over S_floor, S_short, p, Yield scenarios, and Stress Prices
4. Exports results to research/data/stage4_exploratory_sweep_results.csv
"""

import sys
import time
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from avalanche_research.simulation.population import load_empirical_priors, load_current_regime_population
from avalanche_research.simulation.runner import run_digital_twin_simulation, run_exploratory_parameter_sweep


def main():
    print("=" * 80)
    print("AVALANCHE ADMISSION FRONTIER — STAGE 4 SIMULATION EXECUTION")
    print("=" * 80)

    start_time = time.time()
    
    # 1. Load data and verify
    print("[1/4] Loading canonical historical datasets and calibrating priors...")
    priors = load_empirical_priors()
    init_state = load_current_regime_population()
    print(f"  - Historical completed periods: {priors.total_completed_periods:,}")
    print(f"  - Historical unique nodes: {priors.historical_node_count:,}")
    print(f"  - Current-regime active nodes: {len(init_state['validators']):,}")
    print(f"  - Profile renewal rates: {priors.renewal_rates_by_profile}")

    # 2. Run Baseline Empirical Replay
    print("\n[2/4] Running Baseline Empirical Replay (Model Validation)...")
    base_res = run_digital_twin_simulation(
        mode="baseline",
        timesteps=52,
        seed=42,
        initial_validators=init_state["validators"],
        priors=priors,
    )
    print(f"  - Baseline Initial Nodes: {base_res.trajectory_df['active_node_count'].iloc[0]}")
    print(f"  - Baseline Final Nodes: {base_res.trajectory_df['active_node_count'].iloc[-1]}")
    print(f"  - Baseline Mean Nodes: {base_res.trajectory_df['active_node_count'].mean():.1f}")
    print(f"  - MOE 1 Set Stability (S_N): {base_res.moes.moe1_set_stability_sn:.4f}")
    print(f"  - MOE 2 Mean Turnover Rate: {base_res.moes.moe2_mean_turnover_rate:.4f}")
    print(f"  - MOE 3 Terminal HHI (Node): {base_res.moes.moe3_terminal_hhi_node:.2f}")
    print(f"  - MOE 3 Terminal HHI (Operator): {base_res.moes.moe3_terminal_hhi_operator:.2f}")
    print(f"  - MOE 3 Terminal C10 (Operator): {base_res.moes.moe3_terminal_c10_operator:.2%}")
    print(f"  - MOE 4 Profile A Viability: {base_res.moes.moe4_viability_profile_a:.2%}")
    print(f"  - MOE 5 Capacity Headroom (H_cap): {base_res.moes.moe5_capacity_headroom_hcap:.2%}")

    # 3. Run Exploratory Parameter Sweep
    print("\n[3/4] Running Exploratory Parameter Sweep...")
    s_floors = [500.0, 2000.0]
    s_shorts = [10_000.0, 14_000.0, 20_000.0]
    powers = [1.0, 1.5, 2.0]
    yield_scenarios = ["Y1", "Y2", "Y3"]
    stress_prices = [25.0, 15.0]

    df_sweep = run_exploratory_parameter_sweep(
        s_floors=s_floors,
        s_shorts=s_shorts,
        powers=powers,
        yield_scenarios=yield_scenarios,
        stress_prices=stress_prices,
        timesteps=52,
        seed=42,
    )

    out_csv = Path(__file__).resolve().parents[1] / "data" / "stage4_exploratory_sweep_results.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df_sweep.to_csv(out_csv, index=False)
    print(f"\n[4/4] Sweep complete! Exported {len(df_sweep)} evaluations to: {out_csv}")
    print(f"Total execution elapsed time: {time.time() - start_time:.2f} seconds")

    # Display comparison between canonical baseline p=1 and p>1
    print("\n" + "=" * 80)
    print("COMPARATIVE OUTCOME ANALYSIS: CANONICAL BASELINE (p=1.0) VS NONLINEAR (p>1.0)")
    print("=" * 80)
    p_comp = df_sweep[df_sweep["mode"] == "mechanism"].groupby("p")[
        ["final_node_count", "moe1_stability_sn", "moe2_turnover_rate", "moe3_hhi_operator", "moe5_headroom_hcap", "terminal_stake_weighted_dur"]
    ].mean()
    print(p_comp.to_string())

    print("\n" + "=" * 80)
    print("MOE OUTCOMES ACROSS YIELD SENSITIVITY SCENARIOS (Y1 vs Y2 vs Y3)")
    print("=" * 80)
    y_comp = df_sweep[df_sweep["mode"] == "mechanism"].groupby("yield_scenario")[
        ["final_node_count", "moe1_stability_sn", "moe2_turnover_rate", "moe3_hhi_operator", "moe5_headroom_hcap", "terminal_stake_weighted_dur"]
    ].mean()
    print(y_comp.to_string())

    print("\n" + "=" * 80)
    print("S_FLOOR COMPARISON: S_FLOOR = 500 AVAX VS 2,000 AVAX")
    print("=" * 80)
    floor_comp = df_sweep[df_sweep["mode"] == "mechanism"].groupby("s_floor")[
        ["final_node_count", "moe1_stability_sn", "moe2_turnover_rate", "moe3_hhi_operator", "moe4_viab_a", "moe5_headroom_hcap"]
    ].mean()
    print(floor_comp.to_string())


if __name__ == "__main__":
    main()
