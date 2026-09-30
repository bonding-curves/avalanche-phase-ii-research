"""Stage 1: Economic and Protocol Boundary Calibration for the Admission Frontier.

Computes the viable economic floor S_floor across operator cost structures,
opportunity cost benchmarks, and AVAX price scenarios, establishing the
formal boundary parameter table for Stage 1.
"""

from __future__ import annotations

import pandas as pd


def compute_economic_floor_grid() -> pd.DataFrame:
    """Computes minimum viable self-stake S_floor (in AVAX) across cost, spread, and price regimes."""
    arr_365 = 0.06383  # 365d annualized reward rate under ACP-285 at current supply (~470M AVAX)

    scenarios = [
        ("Base Case (sAVAX 4.15%)", 0.0415),
        ("Conservative (DeFi 5.00%)", 0.0500),
        ("Favorable (LST 3.50%)", 0.0350),
        ("Cash Break-Even (r=0%)", 0.0000),
    ]

    operators = [
        ("Home Bare-Metal ($380/yr)", 380.0),
        ("Budget Cloud VPS ($540/yr)", 540.0),
        ("Standard Cloud VPS ($720/yr)", 720.0),
        ("Enterprise Cloud ($1200/yr)", 1200.0),
    ]

    prices = [15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 60.0]

    rows = []
    for op_name, c_op in operators:
        for scen_name, r_out in scenarios:
            spread = arr_365 - r_out
            if spread <= 0:
                continue
            for p in prices:
                # S * spread * P >= C_op  =>  S >= C_op / (spread * P)
                s_viable = c_op / (spread * p)
                rows.append({
                    "operator_class": op_name,
                    "annual_cost_usd": c_op,
                    "outside_option": scen_name,
                    "yield_spread_pct": spread * 100.0,
                    "avax_price_usd": p,
                    "s_floor_viable_avax": round(s_viable, 1),
                })

    return pd.DataFrame(rows)


def print_summary():
    df = compute_economic_floor_grid()

    print("=" * 80)
    print("STAGE 1: ECONOMIC VIABILITY FLOOR S_floor (AVAX) AT d_max = 365 DAYS")
    print("Formula: S_floor >= C_op / ((ARR_365 - r_outside) * P_AVAX)")
    print("=" * 80)

    # Filter to base case (sAVAX 4.15%, spread = 2.233%)
    base_df = df[df["outside_option"] == "Base Case (sAVAX 4.15%)"]
    pivot_base = base_df.pivot(index="operator_class", columns="avax_price_usd", values="s_floor_viable_avax")
    print("\n--- BASE CASE: Liquid Staking Outside Option (r_outside = 4.15%, Spread = 2.23%) ---")
    print(pivot_base.to_string())

    # Filter to Cash break-even (r=0, ignoring capital opportunity cost)
    cash_df = df[df["outside_option"] == "Cash Break-Even (r=0%)"]
    pivot_cash = cash_df.pivot(index="operator_class", columns="avax_price_usd", values="s_floor_viable_avax")
    print("\n--- CASH BREAK-EVEN (r_outside = 0%, Spread = 6.38%, pure dollar accounting) ---")
    print(pivot_cash.to_string())


if __name__ == "__main__":
    print_summary()
