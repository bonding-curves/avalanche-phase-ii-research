"""
Script to build the canonical post-Helicon engineering-grade HTML memo.
Reflects live Helicon Mainnet activation (Sept 22, 2026), post-Etna empirical ground truth,
and the Pure Harmonic Policy Envelopes.
"""

import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DATA_PATH = "/home/hash/Hub/Projects/avalanche-phase-ii-research/research/data/psuu_utility_tensor_helicon.csv"
OUTPUT_HTML = "/home/hash/Hub/Projects/avalanche-phase-ii-research/research/plots/canonical_helicon_admission_frontier_memo.html"
ARTIFACT_HTML = "/home/hash/.gemini/antigravity-cli/brain/0e0d7bfb-f4a6-49f6-89fd-7f5ff88ccd8c/plots/canonical_helicon_admission_frontier_memo.html"

def solve_exponent(d_target, s_short, s_floor=500.0):
    denom = (1.0 / d_target - 1.0 / 365.0) / (0.5 - 1.0 / 365.0)
    numer = (2000.0 - s_floor) / (s_short - s_floor)
    if denom <= 0 or numer <= 0:
        return 0.642
    return np.log(numer) / np.log(denom)

def s_min_harmonic(d, s_short, p, s_floor=500.0):
    d = np.asarray(d, dtype=float)
    inv_term = (1.0 / np.maximum(d, 2.0) - 1.0 / 365.0) / (0.5 - 1.0 / 365.0)
    return np.where(d <= 2.0, s_short, np.where(d >= 365.0, s_floor, s_floor + (s_short - s_floor) * np.power(np.maximum(0.0, inv_term), p)))

def build_memo():
    print(f"Loading data from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    # We only care about Harmonic runs now
    df = df[df["frontier_mode"] == "harmonic"]
    
    top_candidates = df.sort_values(by="retail_retention", ascending=False).head(15)

    # --- FIGURE 1: 3D Parameter State Space Tensor ---
    fig_3d = go.Figure()
    fig_3d.add_trace(go.Scatter3d(
        x=df["s_short"],
        y=df["d_target_days"],
        z=df["macro_duration_w"],
        mode="markers",
        name="Harmonic Trajectories",
        marker=dict(
            size=8,
            color=df["retail_retention"] * 100,
            colorscale="Plasma",
            colorbar=dict(title="Validator Retention %", x=1.05),
            opacity=0.9,
            symbol="circle",
            line=dict(color="#ffffff", width=1)
        ),
        hovertemplate=(
            "<b>Harmonic Configuration</b><br>"
            "S_short: %{x:,.0f} AVAX<br>"
            "d_target: %{y:.0f} days (%{customdata[0]:.1f} wks)<br>"
            "Macro Duration: %{z:.2f} wks<br>"
            "Validator Retention: %{customdata[1]:.1%}<br>"
            "Duration Lift: +%{customdata[2]:.1f}%<extra></extra>"
        ),
        customdata=np.column_stack([
            df["d_target_days"] / 7.0,
            df["retail_retention"],
            df["retail_lift_pct"]
        ])
    ))

    fig_3d.update_layout(
        title="<b>Figure 1: 3D Harmonic Parameter Envelope Trade-offs</b>",
        scene=dict(
            xaxis=dict(title="S_short (AVAX)", backgroundcolor="#0b0f19", gridcolor="#1e293b", color="#9ca3af"),
            yaxis=dict(title="d_target (Days)", backgroundcolor="#0b0f19", gridcolor="#1e293b", color="#9ca3af"),
            zaxis=dict(title="Macro Duration (Weeks)", backgroundcolor="#0b0f19", gridcolor="#1e293b", color="#9ca3af"),
            bgcolor="#030712"
        ),
        paper_bgcolor="#030712",
        font=dict(color="#f3f4f6", family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto"),
        margin=dict(l=0, r=0, b=0, t=50),
        height=580,
    )

    # --- FIGURE 2: Admission Frontier Geometry Comparison ---
    days_range = np.linspace(2, 365, 364)
    p_gentle = solve_exponent(70.0, 14000.0)
    p_strict = solve_exponent(118.0, 18000.0)
    
    s_hm_gentle = s_min_harmonic(days_range, 14000.0, p_gentle)
    s_hm_strict = s_min_harmonic(days_range, 18000.0, p_strict)
    s_sybil = 28000.0 / days_range

    fig_geom = go.Figure()
    fig_geom.add_trace(go.Scatter(
        x=days_range, y=s_sybil,
        name="Iso-Commitment Sybil Parity (28k AVAX-d)",
        line=dict(color="#ef4444", width=2, dash="dash"),
        hovertemplate="Sybil Floor: %{x:.0f}d, %{y:,.0f} AVAX<extra></extra>"
    ))
    fig_geom.add_trace(go.Scatter(
        x=days_range, y=s_hm_gentle,
        name="Gentle Envelope (14k @ 2d, 2k @ 70d)",
        line=dict(color="#10b981", width=3),
        hovertemplate="Gentle Envelope: %{x:.0f}d, %{y:,.0f} AVAX<extra></extra>"
    ))
    fig_geom.add_trace(go.Scatter(
        x=days_range, y=s_hm_strict,
        name="Aggressive Envelope (18k @ 2d, 2k @ 118d)",
        line=dict(color="#38bdf8", width=3),
        hovertemplate="Aggressive Envelope: %{x:.0f}d, %{y:,.0f} AVAX<extra></extra>"
    ))
    fig_geom.add_trace(go.Scatter(
        x=[2, 365], y=[2000, 2000],
        name="Current Flat Baseline (2,000 AVAX)",
        line=dict(color="#64748b", width=1.5, dash="dashdot"),
        hovertemplate="Flat Baseline: 2,000 AVAX<extra></extra>"
    ))

    fig_geom.update_layout(
        title="<b>Figure 2: Harmonic Policy Envelopes vs. Sybil Parity Floor</b>",
        paper_bgcolor="#030712",
        plot_bgcolor="#0b0f19",
        font=dict(color="#f3f4f6", family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto"),
        xaxis=dict(title="Staking Duration d (Days)", range=[2, 180], gridcolor="#1e293b", zerolinecolor="#334155"),
        yaxis=dict(title="Minimum Required Bond S_min(d) (AVAX)", range=[0, 22000], gridcolor="#1e293b", zerolinecolor="#334155"),
        height=480,
        margin=dict(l=60, r=40, b=50, t=60),
        legend=dict(bgcolor="rgba(17, 24, 39, 0.8)", bordercolor="#374151", borderwidth=1, x=0.45, y=0.95)
    )

    div_3d = fig_3d.to_html(full_html=False, include_plotlyjs="cdn")
    div_geom = fig_geom.to_html(full_html=False, include_plotlyjs=False)

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Avalanche Admission Frontier: Ecosystem-First Harmonic Envelopes</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script>
    window.MathJax = {{
      tex: {{
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
        processEscapes: true
      }},
      options: {{ skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'] }},
      startup: {{ pageReady: () => {{ return MathJax.startup.defaultPageReady(); }} }}
    }};
  </script>
  <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
  <style>
    body {{ background-color: #030712; color: #f3f4f6; font-family: -apple-system, sans-serif; margin: 0; padding: 32px 24px; line-height: 1.65; }}
    .container {{ max-width: 1400px; margin: 0 auto; }}
    .header-bar {{ border-bottom: 1px solid #1f2937; padding-bottom: 24px; margin-bottom: 28px; }}
    .badge {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); margin-bottom: 8px; }}
    h1 {{ font-size: 2.2rem; font-weight: 800; color: #f9fafb; margin: 0 0 10px 0; }}
    .meta-box {{ background: #0b0f19; border: 1px solid #1e293b; border-radius: 8px; padding: 16px 20px; margin-top: 16px; font-size: 0.9rem; color: #9ca3af; display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }}
    .meta-item b {{ color: #e5e7eb; }}
    .section-card {{ background: #0b0f19; border: 1px solid #1e293b; border-radius: 12px; padding: 28px; margin-bottom: 32px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4); }}
    .section-title {{ font-size: 1.35rem; font-weight: 700; color: #38bdf8; margin-bottom: 16px; border-bottom: 1px solid #1e293b; padding-bottom: 10px; }}
    .section-card p, .section-card li {{ color: #d1d5db; font-size: 1rem; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; margin-bottom: 20px; }}
    th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid #1f2937; }}
    th {{ color: #9ca3af; font-weight: 600; text-transform: uppercase; font-size: 0.75rem; background: #111827; }}
    tr:hover {{ background: #111827; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header-bar">
      <span class="badge">Canonical Systems Engineering Memo</span>
      <h1>Avalanche Dynamic Admission Frontier $S_{{\\min}}(d)$</h1>
      <p style="color: #9ca3af; font-size: 1.1rem; max-width: 1100px;">
        Ecosystem-First Harmonic Envelopes, Live Pre-Helicon Census Audit, and Validator Profitability Dynamics.
      </p>
      <div class="meta-box">
        <div class="meta-item"><b>Target Recipient:</b> Avalanche Foundation</div>
        <div class="meta-item"><b>Primary Goal:</b> Maximize Validator Health & Macro Duration</div>
        <div class="meta-item"><b>Simulation Baseline:</b> Live Pre-Helicon Census (Sept 2026, 602 nodes)</div>
        <div class="meta-item"><b>Live Upstream Engine:</b> PlatformVM Helicon Protocol Upgrade</div>
      </div>
    </div>

    <!-- SECTION 1: MACRO GOALS -->
    <div class="section-card">
      <div class="section-title">🎯 1. Ecosystem-First Macro Goals</div>
      <p>The mathematical architecture of the Admission Frontier is designed strictly to serve three interconnected ecosystem goals:</p>
      <ul>
        <li><b>1. Prevent 48-Hour Saturation (Sybil Parity):</b> With ACP-273 activating a 2-day minimum staking duration, the network cannot allow historical 14-day churn capital to collapse into 48-hour stints at no cost. The frontier must mathematically guarantee that 2-day staking requires proportionally higher capital commitment.</li>
        <li><b>2. Validator Maximization & Profitability:</b> Decentralization is not strictly defined by the "2,000 AVAX" node, but by maximizing the total number of independent validators. The frontier must gently guide capital toward longer lockups where ACP-285 yields safely outpace sovereign hardware costs (VPS drag), ensuring independent nodes remain profitable.</li>
        <li><b>3. Gradual Macro Duration Expansion:</b> The goal is to lift the network's capital lock duration across the board without causing aggressive liquidity shocks. We provide flexible parameter <i>ranges</i> rather than rigid dictates, allowing capital to adjust organically.</li>
      </ul>
    </div>

    <!-- SECTION 2: CURRENT LIVE STATE -->
    <div class="section-card">
      <div class="section-title">📊 2. Current Live Network State (Sept 2026)</div>
      <p>By auditing the live network state immediately preceding Helicon (<code>01-renewal-panel.parquet</code>), we isolate the true baseline we are lifting from:</p>
      <table>
        <thead>
          <tr>
            <th>Validator Metric</th>
            <th>Current Live State (Sept 2026)</th>
            <th>Systems Engineering Interpretation</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>Active Live Consensus Nodes</b></td>
            <td><b>602 active nodes</b></td>
            <td>True concurrent network consensus active size.</td>
          </tr>
          <tr>
            <td><b>Macro Capital Duration</b></td>
            <td><b>8.90 weeks (62.3 days)</b></td>
            <td>The current capital-weighted locked duration of the network.</td>
          </tr>
          <tr>
            <td><b>Staking Duration Median (Small Nodes)</b></td>
            <td><b>15.0 days</b></td>
            <td>The majority of operators park exactly at the minimum viable boundary.</td>
          </tr>
          <tr>
            <td><b>14-Day Capital Concentration</b></td>
            <td><b>70.5% turnover volume</b></td>
            <td>Heavy concentration of $>6,000$ AVAX nodes churning every 14 days. <b>This is the capital we must gently expand, rather than violently shock.</b></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- SECTION 3: HARMONIC MATH -->
    <div class="section-card">
      <div class="section-title">📐 3. The Continuous Harmonic Frontier</div>
      <p>
        We strongly recommend the <b>Continuous Harmonic Bounded Decay</b> curve. It treats all ecosystem capital fairly, applying a smooth, continuous mathematical function without arbitrary "steps" or accommodations for specific third-party smart contracts.
      </p>
      $$S_{{\\min}}(d) = 500 + (S_{{\\text{{short}}}} - 500) \\cdot \\left[ \\frac{{\\frac{{1}}{{d}} - \\frac{{1}}{{365}}}}{{\\frac{{1}}{{2}} - \\frac{{1}}{{365}}}} \\right]^p, \\quad p = \\frac{{\\ln\\left(\\frac{{2{{,}}000 - 500}}{{S_{{\\text{{short}}}} - 500}}\\right)}}{{\\ln\\left(\\frac{{\\frac{{1}}{{d_{{\\text{{target}}}}}} - \\frac{{1}}{{365}}}}{{\\frac{{1}}{{2}} - \\frac{{1}}{{365}}}}\\right)}}$$
      <p>
        <b>The Genius of the Harmonic Curve for 14-Day Capital:</b> The heavy concentration of capital churning at 14 days currently resides in nodes with $>6,000$ AVAX. Under a moderate Harmonic envelope, a 14-day lockup mathematically requires $\\sim 4,500$ to $7,000$ AVAX. Therefore, this capital is <b>not violently evicted</b>—they already have the stake to maintain their 14-day cadence. The curve simply acts as a wall, preventing them from dropping to 2 days without putting up $14,000+$ AVAX.
      </p>
      <div style="margin: 24px 0;">{div_geom}</div>
    </div>

    <!-- SECTION 4: TENSOR & RANGES -->
    <div class="section-card">
      <div class="section-title">🏆 4. The Recommended Harmonic Policy Envelopes (Ranges)</div>
      <p>Rather than dictating a single harsh configuration, we recommend the Foundation select values within the following safe ranges to gently expand macro duration without triggering liquidity shocks.</p>
      
      <table>
        <thead>
          <tr>
            <th>Parameter</th>
            <th>Recommended Range</th>
            <th>Impact & Rationale</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>Short Boundary ($S_{{\\text{{short}}}}$ at 2d)</b></td>
            <td><b>14,000 to 18,000 AVAX</b></td>
            <td><b>14,000 AVAX guarantees exact mathematical Sybil parity</b> ($14\\text{{k}} \\times 2\\text{{d}} = 28\\text{{k AVAX-d}}$). Anything higher adds a security premium against 48h exploitation.</td>
          </tr>
          <tr>
            <td><b>Target Lockup ($d_{{\\text{{target}}}}$ for 2k)</b></td>
            <td><b>70 days (10w) to 118 days (16.9w)</b></td>
            <td><b>70 Days:</b> The gentle approach. Smoothly guides the 15-day median up to 10 weeks.<br><b>118 Days:</b> The aggressive approach. Maximizes ACP-285 protocol yield ($4.76\\%$) to guarantee independent nodes can comfortably pay their server costs.</td>
          </tr>
        </tbody>
      </table>

      <div style="margin: 24px 0;">{div_3d}</div>
    </div>
  </div>
</body>
</html>
"""

    print(f"Writing updated canonical HTML report to {OUTPUT_HTML}...")
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"Writing copy to artifact destination {ARTIFACT_HTML}...")
    with open(ARTIFACT_HTML, "w", encoding="utf-8") as f:
        f.write(full_html)

    print("Canonical Post-Helicon Memo (Harmonic/Ecosystem version) built successfully!")

if __name__ == "__main__":
    build_memo()
