#!/usr/bin/env python3
"""Generate publication-quality infographic on Avalanche Inflation Profiles.

Covers:
1. Staking Commitment Duration vs Annualized Reward Rate (ARR) [Pre vs Post ACP-285]
2. Supply-Decay Dynamic: Gross Inflation vs Circulating Supply
3. 20-Year Macro Trajectory: Circulating Supply & Annual Issuance (Half-life decay)
4. Net Inflation Phase Space: Staking Ratio vs Fee Burn Deflation Boundary
"""

import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import matplotlib.ticker as ticker

# Style configuration
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 8.5,
    "figure.titlesize": 14,
    "axes.edgecolor": "#CBD5E1",
    "axes.linewidth": 1.2,
    "grid.color": "#E2E8F0",
    "grid.linestyle": "--",
    "grid.alpha": 0.7,
})

# Avalanche & Cryptoeconomic Color Palette
AVAX_RED = "#E84142"
NAVY_DARK = "#0F172A"
NAVY_MID = "#1E293B"
SLATE_MUTED = "#64748B"
TEAL_GREEN = "#0D9488"
AMBER_GOLD = "#D97706"
INDIGO_PURPLE = "#6366F1"
CARD_BG = "#F8FAFC"
WHITE = "#FFFFFF"

# Avalanche Protocol Constants
C = 720.0  # Supply Cap in Millions of AVAX
S0 = 360.0  # Genesis Supply in Millions of AVAX
S_CURR = 470.134  # Current Supply in Millions of AVAX (Helicon Era)
P = 365.0  # Minting Period in Days

# Consumption Rates
R_MIN_PRE = 0.100  # Pre-ACP-285 (10.0%)
R_MAX = 0.120      # Maximum (12.0%)
R_MIN_POST = 0.075 # Post-ACP-285 (7.5%)

def arr(d, s, r_min, r_max):
    """Annualized Reward Rate given duration d (days), supply s (M AVAX), and consumption rates."""
    f_s = (C - s) / s
    r_d = r_min + (r_max - r_min) * (d / P)
    return f_s * r_d * 100.0  # In percent

def make_figure(output_path: Path):
    fig = plt.figure(figsize=(15, 10.5), facecolor=WHITE, dpi=300)
    
    # Title & Subtitle banner
    fig.text(0.06, 0.955, "AVALANCHE TOKENOMICS: STRUCTURAL INFLATION PROFILES",
             fontsize=17, fontweight="bold", color=NAVY_DARK)
    fig.text(0.06, 0.932,
             "Mathematical Mechanics of Supply-Capped Minting, ACP-285 Consumption Rate Ramp, and the Deflationary Horizon",
             fontsize=10.5, color=SLATE_MUTED)

    # 2x2 Grid with generous spacing
    gs = GridSpec(2, 2, figure=fig, left=0.06, right=0.95, top=0.90, bottom=0.07,
                  wspace=0.22, hspace=0.30)
    
    # -------------------------------------------------------------
    # PANEL 1: Duration Yield Curve (ARR) Pre vs Post ACP-285
    # -------------------------------------------------------------
    ax1 = fig.add_subplot(gs[0, 0])
    durations = np.linspace(2, 365, 400)
    arr_pre = [arr(d, S_CURR, R_MIN_PRE, R_MAX) for d in durations]
    arr_post = [arr(d, S_CURR, R_MIN_POST, R_MAX) for d in durations]

    ax1.plot(durations, arr_pre, label="Pre-ACP-285 Baseline ($r_{min} = 10\\%, r_{max} = 12\\%$)",
             color=SLATE_MUTED, linestyle="--", linewidth=2.0)
    ax1.plot(durations, arr_post, label="Post-ACP-285 / Helicon ($r_{min} = 7.5\\%, r_{max} = 12\\%$)",
             color=AVAX_RED, linewidth=2.5)

    # Fill spread area
    ax1.fill_between(durations, arr_pre, arr_post, color=AVAX_RED, alpha=0.08,
                     label="Issuance Savings Buffer")

    # Critical duration pins
    pin_durations = [2, 14, 90, 182, 365]
    for d in pin_durations:
        y_post = arr(d, S_CURR, R_MIN_POST, R_MAX)
        ax1.scatter(d, y_post, color=AVAX_RED, s=35, zorder=5)
        if d == 2:
            ax1.annotate(f"2d: {y_post:.2f}%\n(ACP-273 Min)", (d, y_post),
                         xytext=(d + 8, y_post - 0.55), fontsize=8,
                         arrowprops=dict(arrowstyle="->", color=AVAX_RED, lw=0.8))
        elif d == 14:
            ax1.annotate(f"14d: {y_post:.2f}%\n(Liquid Staking)", (d, y_post),
                         xytext=(d + 12, y_post - 0.50), fontsize=8,
                         arrowprops=dict(arrowstyle="->", color=AVAX_RED, lw=0.8))
        elif d == 365:
            ax1.annotate(f"365d: {y_post:.2f}%\n(Full 1-Yr)", (d, y_post),
                         xytext=(d - 75, y_post + 0.15), fontsize=8,
                         arrowprops=dict(arrowstyle="->", color=AVAX_RED, lw=0.8))

    # Spread annotation
    y_14_pre = arr(14, S_CURR, R_MIN_PRE, R_MAX)
    y_14_post = arr(14, S_CURR, R_MIN_POST, R_MAX)
    ax1.annotate("", xy=(14, y_14_pre), xytext=(14, y_14_post),
                 arrowprops=dict(arrowstyle="<->", color=NAVY_DARK, lw=1.2))
    ax1.text(20, (y_14_pre + y_14_post) / 2 - 0.05,
             f"Spread Widened\n1.02% → 2.30%\n(Disincentivizes short loops)",
             fontsize=7.8, color=NAVY_DARK, fontweight="bold")

    ax1.set_title("1. Staking Yield Profile by Commitment Duration\n"
                  f"Evaluated at Current Circulating Supply $S = {S_CURR:.1f}$M AVAX ($F(S) = 0.531$)",
                  loc="left", pad=8, fontweight="bold", color=NAVY_MID)
    ax1.set_xlabel("Commitment Duration $D$ (Days)")
    ax1.set_ylabel("Annualized Reward Rate ARR (%)")
    ax1.set_xlim(0, 375)
    ax1.set_ylim(3.2, 6.8)
    ax1.grid(True)
    ax1.legend(loc="lower right", frameon=True, facecolor=CARD_BG, edgecolor="#E2E8F0")

    # -------------------------------------------------------------
    # PANEL 2: Gross Inflation vs Circulating Supply (Supply-Decay)
    # -------------------------------------------------------------
    ax2 = fig.add_subplot(gs[0, 1])
    s_vals = np.linspace(360, 715, 300)
    f_vals = (C - s_vals) / s_vals  # Remaining supply factor

    # Inflation curves for different staking ratios sigma (at duration-weighted avg r = 10.5%)
    r_avg = 0.105
    for sigma, color, ls in [(0.40, TEAL_GREEN, ":"), (0.55, AVAX_RED, "-"), (0.70, INDIGO_PURPLE, "--")]:
        gross_inf = sigma * f_vals * r_avg * 100.0
        ax2.plot(s_vals, gross_inf, label=f"Staking Ratio $\\sigma = {int(sigma*100)}\\%$",
                 color=color, linestyle=ls, linewidth=2.2 if sigma == 0.55 else 1.8)

    # Current supply vertical line
    ax2.axvline(S_CURR, color=NAVY_DARK, linestyle=":", linewidth=1.5, alpha=0.8)
    ax2.text(S_CURR + 5, 5.8, f"Current Supply\n$S = {S_CURR:.1f}$M\n($F(S) \\approx 0.53$)",
             fontsize=8, color=NAVY_DARK, fontweight="bold")

    # Genesis marker
    inf_genesis_55 = 0.55 * ((720 - 360)/360) * r_avg * 100.0
    ax2.scatter(360, inf_genesis_55, color=NAVY_DARK, s=40, zorder=5)
    ax2.text(365, inf_genesis_55 + 0.15, f"Genesis (2020)\n$S_0=360$M ($I \\approx 5.8\\%$)",
             fontsize=7.8, color=NAVY_DARK)

    # Current marker
    inf_curr_55 = 0.55 * ((720 - S_CURR)/S_CURR) * r_avg * 100.0
    ax2.scatter(S_CURR, inf_curr_55, color=AVAX_RED, s=50, zorder=5)
    ax2.text(S_CURR + 8, inf_curr_55 - 0.45, f"Today (2026)\n$I_{{gross}} \\approx {inf_curr_55:.2f}\\%$",
             fontsize=8.5, color=AVAX_RED, fontweight="bold")

    # Supply cap asymptote
    ax2.axvline(720, color=SLATE_MUTED, linestyle="-", linewidth=1.2)
    ax2.text(712, 1.2, "Supply Cap $C = 720$M\n($I_{gross} \\to 0\\%$)",
             fontsize=8, color=SLATE_MUTED, rotation=90, va="bottom")

    ax2.set_title("2. Gross Inflation Decay Curve: $I_{gross}(S) = \\sigma \\cdot \\left(\\frac{C-S}{S}\\right) \\cdot \\bar{r}$\n"
                  "Structural Asymptotic Decay Governed by Remaining Supply Factor $F(S)$",
                  loc="left", pad=8, fontweight="bold", color=NAVY_MID)
    ax2.set_xlabel("Total Circulating Supply $S$ (Millions of AVAX)")
    ax2.set_ylabel("Annual Gross Inflation Rate (%)")
    ax2.set_xlim(350, 730)
    ax2.set_ylim(0, 8.0)
    ax2.grid(True)
    ax2.legend(loc="upper right", frameon=True, facecolor=CARD_BG, edgecolor="#E2E8F0")

    # -------------------------------------------------------------
    # PANEL 3: 20-Year Macro Trajectory (2020 - 2040)
    # -------------------------------------------------------------
    ax3 = fig.add_subplot(gs[1, 0])
    
    # Time steps in years
    years = np.linspace(0, 20, 200)
    calendar_years = 2020 + years

    # Analytical solution for S(t): dS/dt = sigma * r_bar * (C - S)
    # C - S(t) = (C - S0) * exp(-k * t), where k = sigma * r_bar
    k_baseline = 0.55 * 0.106  # Pre-ACP-285 (k ≈ 0.0583, half-life ≈ 11.9 yrs)
    k_post = 0.55 * 0.095      # Post-ACP-285 (k ≈ 0.0522, half-life ≈ 13.3 yrs)

    # Helicon activates at t ≈ 6 (Late 2026)
    t_helicon = 6.0
    s_baseline = C - (C - S0) * np.exp(-k_baseline * years)
    
    # Post-ACP-285 trajectory branching at t_helicon
    s_helicon_start = C - (C - S0) * np.exp(-k_baseline * t_helicon)
    s_post = np.where(
        years < t_helicon,
        s_baseline,
        C - (C - s_helicon_start) * np.exp(-k_post * (years - t_helicon))
    )

    # Annual gross issuance: dS/dt = k * (C - S)
    issuance_baseline = k_baseline * (C - s_baseline)
    issuance_post = np.where(
        years < t_helicon,
        issuance_baseline,
        k_post * (C - s_post)
    )

    # Plot on dual axis
    color_s = NAVY_DARK
    color_iss = AVAX_RED

    line1 = ax3.plot(calendar_years, s_baseline, color=SLATE_MUTED, linestyle="--", linewidth=1.8,
                     label="Supply $S(t)$ Baseline (Pre-ACP)")
    line2 = ax3.plot(calendar_years, s_post, color=color_s, linewidth=2.4,
                     label="Supply $S(t)$ Managed (Post-ACP-285)")
    ax3.axhline(C, color=SLATE_MUTED, linestyle=":", linewidth=1.0)
    ax3.text(2021, C - 15, "Hard Supply Cap: 720M AVAX", fontsize=8, color=SLATE_MUTED, fontstyle="italic")

    ax3.set_xlabel("Year")
    ax3.set_ylabel("Circulating Supply $S(t)$ (M AVAX)", color=color_s)
    ax3.tick_params(axis="y", labelcolor=color_s)
    ax3.set_ylim(340, 750)
    ax3.set_xlim(2020, 2040)
    ax3.grid(True)

    # Twin axis for issuance
    ax3_twin = ax3.twinx()
    line3 = ax3_twin.plot(calendar_years, issuance_baseline, color=AMBER_GOLD, linestyle="--", linewidth=1.6,
                          label="Annual Issuance Baseline")
    line4 = ax3_twin.plot(calendar_years, issuance_post, color=color_iss, linewidth=2.2,
                          label="Annual Issuance Post-ACP-285")
    ax3_twin.fill_between(calendar_years, issuance_baseline, issuance_post,
                          where=(calendar_years >= 2026), color=AVAX_RED, alpha=0.15,
                          label="Cumulative Minting Reductions")
    
    ax3_twin.set_ylabel("Annual Minted Issuance (M AVAX / Year)", color=color_iss)
    ax3_twin.tick_params(axis="y", labelcolor=color_iss)
    ax3_twin.set_ylim(0, 26)

    # Combine legends
    lines = line2 + line4
    labels = [l.get_label() for l in lines]
    ax3.legend(lines, labels, loc="center right", frameon=True, facecolor=CARD_BG, edgecolor="#E2E8F0")

    # Helicon marker
    ax3.axvline(2026, color=AVAX_RED, linestyle=":", linewidth=1.3)
    ax3.text(2026.3, 380, "Helicon Activation\n(ACP-285 Ramp)", fontsize=7.8, color=AVAX_RED, fontweight="bold")

    ax3.set_title("3. Macro Issuance & Supply Trajectory (2020–2040)\n"
                  "Half-Life Decay: $t_{1/2} = \\frac{\\ln 2}{\\sigma \\cdot \\bar{r}} \\approx 12-13$ Years",
                  loc="left", pad=8, fontweight="bold", color=NAVY_MID)

    # -------------------------------------------------------------
    # PANEL 4: Net Inflation Phase Space (Staking Ratio vs Burn Rate)
    # -------------------------------------------------------------
    ax4 = fig.add_subplot(gs[1, 1])

    # Grid of Staking Ratio (30% to 75%) and Annual Burn Rate (0% to 4%)
    sigma_grid = np.linspace(0.30, 0.75, 100)
    burn_grid = np.linspace(0.0, 4.0, 100)
    SIGMA, BURN = np.meshgrid(sigma_grid, burn_grid)

    # Current supply factor F(S) = (720 - 470.134) / 470.134 ≈ 0.5315
    # Duration weighted avg consumption rate Post-ACP-285 ≈ 9.5%
    f_curr = (C - S_CURR) / S_CURR
    r_post_avg = 0.095

    # Gross inflation rate (%) = sigma * f_curr * r_post_avg * 100
    # Net inflation (%) = Gross - Burn
    GROSS_INF = SIGMA * f_curr * r_post_avg * 100.0
    NET_INF = GROSS_INF - BURN

    # Contour plot
    levels = np.linspace(-1.5, 3.5, 11)
    cp = ax4.contourf(BURN, SIGMA * 100, NET_INF, levels=levels, cmap="RdYlGn_r", alpha=0.85)
    cbar = fig.colorbar(cp, ax=ax4, orientation="vertical", pad=0.03, aspect=20)
    cbar.set_label("Net Annual Inflation Rate $I_{net}$ (%)", fontsize=8.5)
    cbar.ax.tick_params(labelsize=8)

    # Deflation Boundary line (Net Inflation = 0%)
    cs = ax4.contour(BURN, SIGMA * 100, NET_INF, levels=[0.0], colors=[TEAL_GREEN], linewidths=2.5, linestyles="-")
    ax4.clabel(cs, fmt={0.0: "Deflation Tipping Line ($I_{net} = 0\\%$)"}, inline=True, fontsize=8.5, use_clabeltext=True)

    # Current Operating Point
    # Staking ratio ≈ 55%, Burn rate ≈ 0.25% - 0.50%
    curr_sigma = 55.0
    curr_burn = 0.30
    curr_net_inf = (curr_sigma/100.0) * f_curr * r_post_avg * 100.0 - curr_burn
    ax4.scatter(curr_burn, curr_sigma, color=NAVY_DARK, s=80, edgecolors=WHITE, linewidth=1.5, zorder=6)
    ax4.annotate(f"Current Operating Regime\n$\\sigma \\approx 55\\%, \\text{{Burn}} \\approx 0.3\\%$\n$I_{{net}} \\approx {curr_net_inf:.2f}\\%$",
                 xy=(curr_burn, curr_sigma), xytext=(curr_burn + 0.35, curr_sigma - 7),
                 fontsize=8.2, fontweight="bold", color=NAVY_DARK,
                 bbox=dict(boxstyle="round,pad=0.3", facecolor=WHITE, edgecolor="#CBD5E1", alpha=0.95),
                 arrowprops=dict(arrowstyle="->", color=NAVY_DARK, lw=1.2))

    # High network activity scenario (Deflationary flip)
    ax4.scatter(2.9, 52.0, color=TEAL_GREEN, s=70, edgecolors=WHITE, linewidth=1.5, zorder=6)
    ax4.annotate("Subnet / ACP-77 Surge\n$I_{net} < 0\\%$ (Net Deflation)",
                 xy=(2.9, 52.0), xytext=(1.8, 40.0),
                 fontsize=8, fontweight="bold", color=TEAL_GREEN,
                 arrowprops=dict(arrowstyle="->", color=TEAL_GREEN, lw=1.0))

    ax4.set_title("4. Net Inflation Phase Space & Deflation Horizon\n"
                  "$I_{net} = I_{gross} - \\text{Burn Rate}$ (evaluated at $S = 470.1$M AVAX)",
                  loc="left", pad=8, fontweight="bold", color=NAVY_MID)
    ax4.set_xlabel("Annual Fee Burn Rate (% of Circulating Supply)")
    ax4.set_ylabel("Staking Participation Ratio $\\sigma$ (%)")
    ax4.set_xlim(0.0, 4.0)
    ax4.set_ylim(30, 75)
    ax4.grid(True, linestyle=":", alpha=0.6)

    # Save outputs
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, facecolor=WHITE, bbox_inches="tight")
    print(f"Figure successfully written to {output_path}")

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results/figures/avalanche_inflation_profiles.png")
    make_figure(out)
