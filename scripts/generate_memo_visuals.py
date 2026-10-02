"""Generate publication-quality figures for the Technical Mechanism Design Memo.
Visualizes:
1. Decoupled Parameter Dilemma (figures/decoupled_parameter_dilemma.png)
2. Validator Refusal Flowchart (figures/validator_refusal_flowchart.png)
3. Candidate Curve Families (figures/candidate_curve_families.png)
"""

import os
import shutil
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ArrowStyle
import numpy as np

# Set font and style
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']
plt.rcParams['axes.edgecolor'] = '#CBD5E1'
plt.rcParams['axes.linewidth'] = 1.0

OUTPUT_DIRS = [
    Path("content/Phase II/Milestone 2/2-8 Collaborative Mechanism Design/figures"),
    Path("/home/hash/Hub/Projects/avalanche-phase-ii-resources/docs/figures"),
]


def plot_decoupled_parameter_dilemma(output_dirs):
    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=300)
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#FAFAFA')

    # Domain: duration d from 2 to 365 days
    d = np.linspace(2, 365, 500)

    # Conceptual duration-dependent frontier S_min(d)
    # Using bounded harmonic curve as a representative conceptual frontier
    d_max = 365.0
    S_floor = 500.0
    S_anchor = 14000.0  # conceptual anchor at d_min=2
    delta_S = S_anchor - S_floor
    k = 3.5
    p = 1.2
    
    # Normalized harmonic factor
    eta = ((1.0 - d / d_max) / (1.0 + k * (d / d_max))) ** p
    S_frontier = S_floor + delta_S * eta

    # Baseline: Historical status quo (2,000 AVAX flat from 14d to 365d)
    ax.hlines(y=2000, xmin=14, xmax=365, color='#64748B', linestyle='--', linewidth=2.0,
              label='Historical Baseline (S = 2,000 AVAX, d ≥ 14d)')
    ax.plot(14, 2000, marker='o', markersize=8, color='#334155', zorder=5)
    ax.annotate('Historical Status Quo\n(14 days, 2,000 AVAX)',
                xy=(14, 2000), xytext=(35, 3400),
                arrowprops=dict(arrowstyle='->', color='#334155', lw=1.5),
                fontsize=10, fontweight='bold', color='#1E293B',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#F1F5F9', edgecolor='#94A3B8'))

    # Plot Frontier Curve
    ax.plot(d, S_frontier, color='#2563EB', linewidth=2.8, label=r'Duration-Dependent Frontier Concept $S_{\min}(d)$')

    # Shaded Admissible Region (Above frontier)
    ax.fill_between(d, S_frontier, 16000, color='#10B981', alpha=0.08, label='Admissible Consensus Region ($S \geq S_{\min}(d)$)')

    # Hazard Zone: Decoupled Parameter Dilemma
    # Area of low duration (2-30d) and low stake (<2000 AVAX)
    hazard_d = np.linspace(2, 45, 100)
    ax.fill_between(hazard_d, 0, 2000, color='#EF4444', alpha=0.15, hatch='//',
                    edgecolor='#F87171', label='Decoupled Dilemma Zone (Low Stake + Short Lockup)')

    # Annotate Decoupled Reduction Vectors
    ax.annotate('', xy=(14, 600), xytext=(14, 1900),
                arrowprops=dict(arrowstyle='->', color='#DC2626', lw=2.2))
    ax.text(17, 1200, 'Independent Stake\nReduction (e.g. 500 AVAX)',
            fontsize=9.5, fontweight='semibold', color='#B91C1C')

    ax.annotate('', xy=(4, 2000), xytext=(13, 2000),
                arrowprops=dict(arrowstyle='->', color='#D97706', lw=2.2))
    ax.text(3, 2250, 'Independent Duration\nReduction (e.g. 2 days)',
            fontsize=9.5, fontweight='semibold', color='#B45309')

    # Explanatory callouts
    # 1. Short-End Anti-Churn
    ax.annotate('Anti-Churn & Sybil Defense:\nHigh capital barrier for transient slots',
                xy=(10, S_frontier[10]), xytext=(55, 12500),
                arrowprops=dict(arrowstyle='->', color='#2563EB', lw=1.5),
                fontsize=10, fontweight='semibold', color='#1D4ED8',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#EFF6FF', edgecolor='#93C5FD'))

    # 2. Long-End Earned Decentralization
    ax.annotate('Earned Decentralization:\nSovereign operators qualify via duration',
                xy=(340, S_frontier[-20]), xytext=(160, 4800),
                arrowprops=dict(arrowstyle='->', color='#059669', lw=1.5),
                fontsize=10, fontweight='semibold', color='#047857',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#ECFDF5', edgecolor='#6EE7B7'))

    # Axis properties
    ax.set_xlim(0, 370)
    ax.set_ylim(0, 16000)
    ax.set_xlabel('Staking Duration $d$ (Days)', fontsize=12, fontweight='bold', color='#1E293B', labelpad=8)
    ax.set_ylabel('Minimum Self-Stake $S_{\min}$ (AVAX)', fontsize=12, fontweight='bold', color='#1E293B', labelpad=8)
    ax.set_title('The Decoupled Parameter Dilemma & The Duration-Dependent Admission Geometry',
                 fontsize=13.5, fontweight='bold', color='#0F172A', pad=14)

    ax.set_xticks([2, 14, 30, 60, 90, 180, 270, 365])
    ax.set_yticks([0, 500, 2000, 5000, 8000, 11000, 14000])
    ax.grid(True, linestyle=':', alpha=0.6, color='#94A3B8')

    # Legend
    ax.legend(loc='upper right', frameon=True, facecolor='#FFFFFF', edgecolor='#CBD5E1', fontsize=9.5)

    plt.tight_layout()
    for d_path in output_dirs:
        d_path.mkdir(parents=True, exist_ok=True)
        target = d_path / "decoupled_parameter_dilemma.png"
        fig.savefig(target, dpi=300)
        print(f"Saved: {target}")
    plt.close(fig)


def plot_validator_refusal_flowchart(output_dirs):
    fig, ax = plt.subplots(figsize=(11, 7.5), dpi=300)
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#FFFFFF')
    ax.axis('off')

    def draw_box(x, y, w, h, title, subtitle, bg_color, border_color, title_color='#0F172A', text_color='#334155'):
        bbox = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.04",
                              facecolor=bg_color, edgecolor=border_color, linewidth=1.5, zorder=3)
        ax.add_patch(bbox)
        ax.text(x + w / 2, y + h * 0.65, title, ha='center', va='center',
                fontsize=11, fontweight='bold', color=title_color, zorder=4)
        ax.text(x + w / 2, y + h * 0.32, subtitle, ha='center', va='center',
                fontsize=9.0, color=text_color, zorder=4)

    def draw_arrow(x1, y1, x2, y2, color='#64748B', lw=1.8, label='', label_pos=(0.5, 0.5), label_color='#475569'):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color=color, lw=lw, shrinkA=4, shrinkB=4), zorder=2)
        if label:
            lx = x1 + (x2 - x1) * label_pos[0]
            ly = y1 + (y2 - y1) * label_pos[1]
            ax.text(lx, ly, label, ha='center', va='center', fontsize=9.5, fontweight='bold',
                    color=label_color, bbox=dict(boxstyle='square,pad=0.2', facecolor='#FFFFFF', edgecolor='none'), zorder=5)

    # 1. Candidate Stint
    draw_box(0.35, 0.84, 0.30, 0.12,
             "Candidate Validator Stint",
             "Operator specifies self-stake $S_i$ and lockup duration $d_i$",
             "#F8FAFC", "#94A3B8", title_color="#0F172A")

    # Arrow down to protocol check
    draw_arrow(0.50, 0.84, 0.50, 0.69)

    # 2. Admission Gate
    draw_box(0.32, 0.57, 0.36, 0.12,
             "PlatformVM Admission Evaluation",
             r"Evaluates admission condition: Is $S_i \geq S_{\min}(d_i)$?",
             "#EFF6FF", "#3B82F6", title_color="#1D4ED8")

    # Branch YES (Right and Up/Level)
    draw_arrow(0.68, 0.63, 0.77, 0.63, color='#10B981', lw=2.2, label='YES\n(Valid)', label_pos=(0.45, 0.0), label_color='#047857')
    draw_box(0.77, 0.55, 0.21, 0.16,
             "Consensus Admission",
             "Enters active validator set\nConsensus sampling active\nAccrues staking rewards",
             "#ECFDF5", "#10B981", title_color="#065F46", text_color="#047857")

    # Branch NO (Down to Refusal Gate)
    draw_arrow(0.50, 0.57, 0.50, 0.42, color='#EF4444', lw=2.2, label='NO (Binding Constraint)', label_pos=(0.5, 0.5), label_color='#B91C1C')

    # 3. Refusal Rule Node
    draw_box(0.30, 0.31, 0.40, 0.11,
             "Validator Refusal Rule Triggered",
             "Stint rejected: Insufficient capital for requested duration commitment",
             "#FEF2F2", "#EF4444", title_color="#991B1B")

    # Branch down to 3 options
    draw_arrow(0.38, 0.31, 0.16, 0.20, color='#64748B', lw=1.5)
    draw_arrow(0.50, 0.31, 0.50, 0.20, color='#64748B', lw=1.5)
    draw_arrow(0.62, 0.31, 0.84, 0.20, color='#64748B', lw=1.5)

    # Option A: Duration Extension
    draw_box(0.04, 0.05, 0.27, 0.15,
             "Option A: Extend Duration",
             "Increase duration $d' > d_i$\nsuch that $S_i \geq S_{\min}(d')$\nTrades liquidity for admission",
             "#F0FDF4", "#22C55E", title_color="#15803D")

    # Option B: Capital Injection
    draw_box(0.365, 0.05, 0.27, 0.15,
             "Option B: Inject Capital",
             "Increase self-stake $S' > S_i$\nsuch that $S' \geq S_{\min}(d_i)$\nRetains short duration preference",
             "#F5F3FF", "#8B5CF6", title_color="#6D28D9")

    # Option C: Delegation / Exit
    draw_box(0.69, 0.05, 0.27, 0.15,
             "Option C: Delegate or Exit",
             "Delegate stake to active node\nor exit consensus pool\nAvoids high-churn validator slot",
             "#F8FAFC", "#64748B", title_color="#334155")

    # Title
    ax.text(0.50, 0.98, "Consensus Admission Gate & Validator Behavioral Response Flowchart",
            ha='center', va='top', fontsize=14, fontweight='bold', color='#0F172A')
    ax.text(0.50, 0.94, "Structural mechanism filtering validator commitments and preserving consensus stability",
            ha='center', va='top', fontsize=10, color='#475569')

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    plt.tight_layout()
    for d_path in output_dirs:
        d_path.mkdir(parents=True, exist_ok=True)
        target = d_path / "validator_refusal_flowchart.png"
        fig.savefig(target, dpi=300)
        print(f"Saved: {target}")
    plt.close(fig)


def plot_candidate_curve_families(output_dirs):
    fig, ax = plt.subplots(figsize=(10.5, 6.8), dpi=300)
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#FAFAFA')

    d = np.linspace(14, 365, 600)
    d_max = 365.0
    S_floor = 500.0

    # 1. Fixed Baseline: S = 2,000 flat
    S_fixed = np.full_like(d, 2000.0)

    # 2. Iso-Commitment: S * d = constant (normalized through pivot at 14d, 2000 AVAX)
    C_iso = 2000.0 * 14.0
    S_iso = C_iso / d

    # 3. Power-law Decay: S(d) = S_floor + (S_anchor - S_floor) * (14 / d)^0.8
    S_power = S_floor + (14000.0 - S_floor) * (14.0 / d) ** 0.8

    # 4. Piecewise Step Function: 5 discrete tiers
    def step_function(durations):
        res = []
        for val in durations:
            if val < 30:
                res.append(14000)
            elif val < 60:
                res.append(8000)
            elif val < 120:
                res.append(4000)
            elif val < 240:
                res.append(1500)
            else:
                res.append(500)
        return np.array(res)
    S_step = step_function(d)

    # 5. Bounded Harmonic Family: S_min(d) with p=1.2, k=3.0
    k_harm = 3.0
    p_harm = 1.2
    S_anchor_harm = 14000.0
    delta_S = S_anchor_harm - S_floor
    eta_harm = ((1.0 - d / d_max) / (1.0 + k_harm * (d / d_max))) ** p_harm
    S_harm = S_floor + delta_S * eta_harm

    # Plot curves
    ax.plot(d, S_fixed, label='1. Fixed Baseline (Status Quo: $S = 2,000$ AVAX)',
            color='#64748B', linestyle='--', linewidth=2.0)
    ax.plot(d, S_iso, label='2. Iso-Commitment ($S \cdot d = C$)',
            color='#D97706', linestyle=':', linewidth=2.2)
    ax.plot(d, S_power, label='3. Power-Law Decay ($S \propto d^{-\\alpha}$)',
            color='#9333EA', linestyle='-.', linewidth=2.0)
    ax.plot(d, S_step, label='4. Piecewise Step Schedule (Cliffs)',
            color='#EF4444', linestyle='-', linewidth=1.8, alpha=0.85, drawstyle='steps-post')
    ax.plot(d, S_harm, label='5. Bounded Harmonic Family ($p \geq 1, k > 0$)',
            color='#2563EB', linestyle='-', linewidth=2.8)

    # Annotations highlighting axiom violations and features
    # Iso-commitment collapse at long end
    ax.annotate('Collapses below viable floor\n($S(365) \\approx 77$ AVAX)',
                xy=(350, S_iso[-15]), xytext=(220, 2200),
                arrowprops=dict(arrowstyle='->', color='#D97706', lw=1.3),
                fontsize=9.0, color='#92400E',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#FEF3C7', edgecolor='#FCD34D'))

    # Step function cliff edges
    ax.annotate('Arbitrary cliff edges\ninduce boundary gaming',
                xy=(120, 4000), xytext=(145, 6200),
                arrowprops=dict(arrowstyle='->', color='#EF4444', lw=1.3),
                fontsize=9.0, color='#991B1B',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#FEF2F2', edgecolor='#FCA5A5'))

    # Bounded Harmonic properties
    ax.annotate('Strict convexity ($p \geq 1$), smooth marginal\nrelief, exact boundary convergence ($S_{\\mathrm{floor}}$)',
                xy=(180, S_harm[len(S_harm)//2]), xytext=(195, 10500),
                arrowprops=dict(arrowstyle='->', color='#2563EB', lw=1.5),
                fontsize=9.5, fontweight='semibold', color='#1D4ED8',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#EFF6FF', edgecolor='#93C5FD'))

    # Axis properties
    ax.set_xlim(10, 370)
    ax.set_ylim(0, 16000)
    ax.set_xlabel('Staking Duration $d$ (Days)', fontsize=12, fontweight='bold', color='#1E293B', labelpad=8)
    ax.set_ylabel('Required Self-Stake $S$ (AVAX)', fontsize=12, fontweight='bold', color='#1E293B', labelpad=8)
    ax.set_title('Comparative Geometry of Evaluated Admission Frontier Functional Forms',
                 fontsize=13.5, fontweight='bold', color='#0F172A', pad=14)

    ax.set_xticks([14, 30, 60, 90, 180, 270, 365])
    ax.set_yticks([0, 500, 2000, 4000, 8000, 11000, 14000])
    ax.grid(True, linestyle=':', alpha=0.6, color='#94A3B8')

    # Legend
    ax.legend(loc='upper right', frameon=True, facecolor='#FFFFFF', edgecolor='#CBD5E1', fontsize=9.5)

    plt.tight_layout()
    for d_path in output_dirs:
        d_path.mkdir(parents=True, exist_ok=True)
        target = d_path / "candidate_curve_families.png"
        fig.savefig(target, dpi=300)
        print(f"Saved: {target}")
    plt.close(fig)


if __name__ == '__main__':
    print("Generating visual assets...")
    plot_decoupled_parameter_dilemma(OUTPUT_DIRS)
    plot_validator_refusal_flowchart(OUTPUT_DIRS)
    plot_candidate_curve_families(OUTPUT_DIRS)
    print("All visual assets successfully generated.")
