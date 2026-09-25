"""
Generate a unified, standalone HTML report with interactive 3D and 2D Plotly visuals,
MathJax-rendered equations, and full systems engineering analysis for the Avalanche Admission Frontier.
"""

import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DATA_PATH = "/home/hash/Hub/Projects/avalanche-phase-ii-research/research/data/psuu_utility_tensor.csv"
OUTPUT_HTML = "/home/hash/Hub/Projects/avalanche-phase-ii-research/research/plots/admission_frontier_tensor_report.html"

def generate_report():
    df = pd.read_csv(DATA_PATH)
    
    # Separate admissible vs rejected
    safe_df = df[df["utility"] == 1]
    reject_df = df[df["utility"] == 0]

    # --- FIGURE 1: 3D Parameter State Space Tensor ---
    fig_3d = go.Figure()

    # Rejected points
    fig_3d.add_trace(go.Scatter3d(
        x=reject_df["s_short"],
        y=reject_df["d_target_days"],
        z=reject_df["macro_duration_w"],
        mode="markers",
        name="Rejected (U=0)",
        marker=dict(
            size=6,
            color="#ef4444",
            opacity=0.35,
            symbol="circle"
        ),
        hovertemplate=(
            "<b>Rejected Configuration (U=0)</b><br>"
            "Mode: %{customdata[0]}<br>"
            "S_short: %{x:,.0f} AVAX<br>"
            "d_target: %{y:.0f} days<br>"
            "Macro Duration: %{z:.2f} wks<br>"
            "Retail Retention: %{customdata[1]:.1%}<br>"
            "Retail Lift: +%{customdata[2]:.1f}%<extra></extra>"
        ),
        customdata=reject_df[["frontier_mode", "retail_retention", "retail_lift_pct"]].values
    ))

    # Safe points - piecewise_benqi
    safe_benqi = safe_df[safe_df["frontier_mode"] == "piecewise_benqi"]
    fig_3d.add_trace(go.Scatter3d(
        x=safe_benqi["s_short"],
        y=safe_benqi["d_target_days"],
        z=safe_benqi["macro_duration_w"],
        mode="markers",
        name="Admissible: Piecewise-BENQI (U=1)",
        marker=dict(
            size=10,
            color="#10b981",
            symbol="circle",
            line=dict(color="#ffffff", width=1.5)
        ),
        hovertemplate=(
            "<b>✓ Safe Admissible: Piecewise-BENQI</b><br>"
            "S_short: %{x:,.0f} AVAX<br>"
            "d_target: %{y:.0f} days (%{customdata[0]:.1f} wks)<br>"
            "Macro Duration: %{z:.2f} wks<br>"
            "Retail Retention: %{customdata[1]:.1%}<br>"
            "Retail Lift: +%{customdata[2]:.1f}%<extra></extra>"
        ),
        customdata=np.column_stack([
            safe_benqi["d_target_days"] / 7.0,
            safe_benqi["retail_retention"],
            safe_benqi["retail_lift_pct"]
        ])
    ))

    # Safe points - harmonic
    safe_harmonic = safe_df[safe_df["frontier_mode"] == "harmonic"]
    fig_3d.add_trace(go.Scatter3d(
        x=safe_harmonic["s_short"],
        y=safe_harmonic["d_target_days"],
        z=safe_harmonic["macro_duration_w"],
        mode="markers",
        name="Admissible: Harmonic (U=1)",
        marker=dict(
            size=10,
            color="#38bdf8",
            symbol="diamond",
            line=dict(color="#ffffff", width=1.5)
        ),
        hovertemplate=(
            "<b>✓ Safe Admissible: Harmonic</b><br>"
            "S_short: %{x:,.0f} AVAX<br>"
            "d_target: %{y:.0f} days (%{customdata[0]:.1f} wks)<br>"
            "Macro Duration: %{z:.2f} wks<br>"
            "Retail Retention: %{customdata[1]:.1%}<br>"
            "Retail Lift: +%{customdata[2]:.1f}%<extra></extra>"
        ),
        customdata=np.column_stack([
            safe_harmonic["d_target_days"] / 7.0,
            safe_harmonic["retail_retention"],
            safe_harmonic["retail_lift_pct"]
        ])
    ))

    fig_3d.update_layout(
        title="<b>Figure 1: 3D Admission Frontier State Space Tensor U(θ)</b>",
        scene=dict(
            xaxis=dict(title="S_short (AVAX)", backgroundcolor="#0b0f19", gridcolor="#1e293b", color="#9ca3af"),
            yaxis=dict(title="d_target (Days)", backgroundcolor="#0b0f19", gridcolor="#1e293b", color="#9ca3af"),
            zaxis=dict(title="Macro Duration (Weeks)", backgroundcolor="#0b0f19", gridcolor="#1e293b", color="#9ca3af"),
            bgcolor="#030712"
        ),
        paper_bgcolor="#030712",
        font=dict(color="#f3f4f6", family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto"),
        legend=dict(
            bgcolor="rgba(17, 24, 39, 0.8)",
            bordercolor="#374151",
            borderwidth=1,
            x=0.02,
            y=0.98
        ),
        margin=dict(l=0, r=0, b=0, t=50),
        height=620
    )

    # --- FIGURE 2: 2D Trade-off Plane & Frontier Boundaries ---
    fig_2d = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            "<b>Retention vs. Macro Security Horizon</b>",
            "<b>Frontier Envelope by Mode & Duration Pivot</b>"
        ),
        horizontal_spacing=0.12
    )

    # Subplot 1: Retention vs Macro Duration
    fig_2d.add_trace(
        go.Scatter(
            x=reject_df["retail_retention"] * 100,
            y=reject_df["macro_duration_w"],
            mode="markers",
            name="Rejected",
            marker=dict(color="#ef4444", size=7, opacity=0.4),
            hoverinfo="skip"
        ),
        row=1, col=1
    )

    fig_2d.add_trace(
        go.Scatter(
            x=safe_df["retail_retention"] * 100,
            y=safe_df["macro_duration_w"],
            mode="markers",
            name="Admissible Envelope",
            marker=dict(
                color=np.where(safe_df["frontier_mode"] == "piecewise_benqi", "#10b981", "#38bdf8"),
                size=11,
                line=dict(color="#ffffff", width=1.5)
            ),
            hovertemplate=(
                "Mode: %{customdata[0]}<br>"
                "S_short: %{customdata[1]:,.0f} AVAX<br>"
                "d_target: %{customdata[2]:.0f}d<br>"
                "Retention: %{x:.1f}%<br>"
                "Macro Duration: %{y:.2f} wks<extra></extra>"
            ),
            customdata=safe_df[["frontier_mode", "s_short", "d_target_days"]].values
        ),
        row=1, col=1
    )

    # Verification Gate Threshold Lines
    fig_2d.add_vline(x=50.0, line_dash="dash", line_color="#f59e0b", row=1, col=1,
                     annotation_text="Min Retention (50%)", annotation_position="top left", annotation_font_color="#f59e0b")
    fig_2d.add_hline(y=20.0, line_dash="dash", line_color="#f59e0b", row=1, col=1,
                     annotation_text="Min Macro Horizon (20w)", annotation_position="bottom right", annotation_font_color="#f59e0b")

    # Subplot 2: S_short vs d_target with Success Heat/Contour Mask
    pivot_benqi = df[df["frontier_mode"] == "piecewise_benqi"].pivot(index="d_target_days", columns="s_short", values="utility")
    pivot_harmonic = df[df["frontier_mode"] == "harmonic"].pivot(index="d_target_days", columns="s_short", values="utility")

    fig_2d.add_trace(
        go.Scatter(
            x=df[df["frontier_mode"] == "piecewise_benqi"]["s_short"],
            y=df[df["frontier_mode"] == "piecewise_benqi"]["d_target_days"] / 7.0,
            mode="markers",
            name="Piecewise (U)",
            marker=dict(
                size=12,
                symbol="square",
                color=df[df["frontier_mode"] == "piecewise_benqi"]["utility"],
                colorscale=[[0, "#1f2937"], [1, "#10b981"]],
                showscale=False,
                line=dict(color="#374151", width=1)
            ),
            hovertemplate="Piecewise-BENQI<br>S_short: %{x:,.0f} AVAX<br>d_target: %{y:.1f} wks<br>Utility: %{marker.color}<extra></extra>"
        ),
        row=1, col=2
    )

    fig_2d.add_trace(
        go.Scatter(
            x=df[df["frontier_mode"] == "harmonic"]["s_short"],
            y=df[df["frontier_mode"] == "harmonic"]["d_target_days"] / 7.0,
            mode="markers",
            name="Harmonic (U)",
            marker=dict(
                size=12,
                symbol="diamond",
                color=df[df["frontier_mode"] == "harmonic"]["utility"],
                colorscale=[[0, "#1f2937"], [1, "#38bdf8"]],
                showscale=False,
                line=dict(color="#374151", width=1)
            ),
            hovertemplate="Harmonic<br>S_short: %{x:,.0f} AVAX<br>d_target: %{y:.1f} wks<br>Utility: %{marker.color}<extra></extra>"
        ),
        row=1, col=2
    )

    fig_2d.update_xaxes(title_text="Retail Retention (% of 6,440 nodes)", row=1, col=1, gridcolor="#1e293b", zerolinecolor="#334155")
    fig_2d.update_yaxes(title_text="Macro Duration (Weeks)", row=1, col=1, gridcolor="#1e293b", zerolinecolor="#334155")
    fig_2d.update_xaxes(title_text="Anchor Stake S_short (AVAX)", row=1, col=2, gridcolor="#1e293b", zerolinecolor="#334155")
    fig_2d.update_yaxes(title_text="Target Duration d_target (Weeks)", row=1, col=2, gridcolor="#1e293b", zerolinecolor="#334155")

    fig_2d.update_layout(
        paper_bgcolor="#030712",
        plot_bgcolor="#0b0f19",
        font=dict(color="#f3f4f6", family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto"),
        height=500,
        margin=dict(l=50, r=40, b=50, t=60),
        showlegend=True,
        legend=dict(bgcolor="rgba(17, 24, 39, 0.8)", bordercolor="#374151", borderwidth=1)
    )

    div_3d = fig_3d.to_html(full_html=False, include_plotlyjs="cdn")
    div_2d = fig_2d.to_html(full_html=False, include_plotlyjs=False)

    # Build Admissible Table HTML
    table_rows = ""
    for _, r in safe_df.sort_values(by=["frontier_mode", "d_target_days", "s_short"]).iterrows():
        mode_badge = f"<span class='tag-mode tag-{r['frontier_mode']}'>{r['frontier_mode']}</span>"
        table_rows += f"""
        <tr>
            <td>{mode_badge}</td>
            <td><b>{r['s_short']:,.0f} AVAX</b></td>
            <td><b>{r['d_target_days']:.0f} days ({r['d_target_days']/7.0:.1f}w)</b></td>
            <td><span class='val-good'>{r['retail_retention']*100:.1f}%</span> ({int(r['retail_retention']*6440):,} nodes)</td>
            <td><b style='color:#38bdf8;'>{r['macro_duration_w']:.2f} weeks</b></td>
            <td><b style='color:#34d399;'>+{r['retail_lift_pct']:.1f}%</b></td>
            <td><span class='badge-pass'>PASS (U=1)</span></td>
        </tr>
        """

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Avalanche Admission Frontier: N-Dimensional PSuU Tensor Report</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script>
    window.MathJax = {{
      tex: {{
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
        processEscapes: true
      }},
      options: {{
        skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
      }},
      startup: {{
        pageReady: () => {{
          return MathJax.startup.defaultPageReady();
        }}
      }}
    }};
  </script>
  <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
  <style>
    body {{
      background-color: #030712;
      color: #f3f4f6;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 32px 24px;
      line-height: 1.6;
    }}
    .container {{
      max-width: 1440px;
      margin: 0 auto;
    }}
    .header-bar {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 16px;
      border-bottom: 1px solid #1f2937;
      padding-bottom: 24px;
      margin-bottom: 28px;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 12px;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.3);
      margin-bottom: 8px;
    }}
    h1 {{
      font-size: 2.1rem;
      font-weight: 800;
      color: #f9fafb;
      margin: 0 0 8px 0;
      letter-spacing: -0.02em;
    }}
    .lead {{
      color: #9ca3af;
      font-size: 1.1rem;
      margin: 0;
      max-width: 950px;
    }}
    .actions-nav {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 0.85rem;
      font-weight: 600;
      text-decoration: none;
      transition: all 0.15s ease;
      cursor: pointer;
    }}
    .btn-primary {{
      background: #0284c7;
      color: #ffffff;
      border: 1px solid #0369a1;
    }}
    .btn-primary:hover {{
      background: #0369a1;
    }}
    .btn-secondary {{
      background: #1f2937;
      color: #e5e7eb;
      border: 1px solid #374151;
    }}
    .btn-secondary:hover {{
      background: #374151;
    }}

    .grid-kpis {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 18px;
      margin-bottom: 32px;
    }}
    .kpi-card {{
      background: #0b0f19;
      border: 1px solid #1e293b;
      border-radius: 10px;
      padding: 20px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }}
    .kpi-label {{
      font-size: 0.75rem;
      color: #9ca3af;
      text-transform: uppercase;
      font-weight: 600;
      letter-spacing: 0.05em;
    }}
    .kpi-val {{
      font-size: 1.85rem;
      font-weight: 800;
      color: #f9fafb;
      margin: 6px 0 2px 0;
    }}
    .kpi-sub {{
      font-size: 0.85rem;
      color: #10b981;
      font-weight: 500;
    }}

    .section-card {{
      background: #0b0f19;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 32px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
    }}
    .section-title {{
      font-size: 1.3rem;
      font-weight: 700;
      color: #38bdf8;
      margin-top: 0;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    
    .rules-banner {{
      background: rgba(56, 189, 248, 0.08);
      border: 1px solid rgba(56, 189, 248, 0.25);
      border-radius: 8px;
      padding: 18px 24px;
      margin-bottom: 24px;
    }}
    .rules-banner h3 {{
      margin: 0 0 10px 0;
      color: #38bdf8;
      font-size: 1.1rem;
    }}
    .rules-list {{
      margin: 0;
      padding-left: 20px;
      font-size: 1.05rem;
    }}
    .rules-list li {{
      margin-bottom: 6px;
    }}

    .memo-text {{
      color: #d1d5db;
      font-size: 1rem;
      line-height: 1.7;
    }}
    .memo-text h2 {{
      color: #f3f4f6;
      font-size: 1.25rem;
      border-bottom: 1px solid #1f2937;
      padding-bottom: 8px;
      margin-top: 24px;
    }}
    .memo-text p {{
      margin-bottom: 16px;
    }}
    .memo-text ul {{
      padding-left: 24px;
      margin-bottom: 16px;
    }}
    .memo-text li {{
      margin-bottom: 8px;
    }}
    .memo-text code {{
      background: #1e293b;
      color: #38bdf8;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.9em;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
      margin-top: 12px;
    }}
    th, td {{
      padding: 12px 14px;
      text-align: left;
      border-bottom: 1px solid #1f2937;
    }}
    th {{
      color: #9ca3af;
      font-weight: 600;
      text-transform: uppercase;
      font-size: 0.75rem;
      letter-spacing: 0.05em;
      background: #111827;
    }}
    tr:hover {{
      background: #111827;
    }}
    .tag-mode {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.75rem;
      font-family: monospace;
      font-weight: 600;
    }}
    .tag-piecewise_benqi {{
      background: rgba(16, 185, 129, 0.2);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.3);
    }}
    .tag-harmonic {{
      background: rgba(56, 189, 248, 0.2);
      color: #38bdf8;
      border: 1px solid rgba(56, 189, 248, 0.3);
    }}
    .badge-pass {{
      background: rgba(16, 185, 129, 0.2);
      color: #34d399;
      padding: 3px 8px;
      border-radius: 9999px;
      font-weight: 700;
      font-size: 0.75rem;
    }}
    .val-good {{
      color: #34d399;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header-bar">
      <div>
        <span class="badge">BlockScience GDS &bull; Subspace Reference Architecture</span>
        <h1>Avalanche Admission Frontier: N-Dimensional PSuU Tensor Engine</h1>
        <p class="lead">
          Replacing subjective 2D visual heatmaps with algorithmic utility tensors $U(\\theta) \\in \\{{0, 1\\}}$ to isolate 
          the exact parameter envelope balancing node decentralization against universal duration extension.
        </p>
      </div>
      <div class="actions-nav">
        <a href="frontier_calculator.html" class="btn btn-primary" target="_blank">
          🧮 Interactive Frontier Calculator
        </a>
        <a href="simulation_results.html" class="btn btn-secondary" target="_blank">
          📊 52-Week Trajectory Dashboard
        </a>
      </div>
    </div>

    <!-- KPI SUMMARY CARDS -->
    <div class="grid-kpis">
      <div class="kpi-card">
        <div class="kpi-label">Total Trajectories Swept</div>
        <div class="kpi-val">84 Runs</div>
        <div class="kpi-sub">7 Durations &times; 6 Stakes &times; 2 Curves</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Admissible Safe Envelope</div>
        <div class="kpi-val">23 Sets (27.4%)</div>
        <div class="kpi-sub">&check; Cleared All 3 Verification Gates</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Algorithmic Duration Floor</div>
        <div class="kpi-val">&ge; 56.0 Days</div>
        <div class="kpi-sub">&uarr; Exactly 8.0 Weeks for 2,000 AVAX</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Anchor Stake Floor</div>
        <div class="kpi-val">&ge; 10,000 AVAX</div>
        <div class="kpi-sub">&check; Enforces Global Sybil Parity</div>
      </div>
    </div>

    <!-- DERIVED ALGORITHMIC RULES -->
    <div class="rules-banner">
      <h3>⚡ Algorithmic Verification Gate Extraction (Subspace P6 Invariant)</h3>
      <ul class="rules-list">
        <li><b>Rule 1 (Universal Duration Floor):</b> $d_{{\\text{{target}}}} \\ge 56.0\\text{{ days}}$ ($8\\text{{ weeks}}$). Below 56 days, retail stakers facing $-0.96\\%$ VPS drag rationally exit into frictionless sAVAX liquid staking ($4.15\\% - 4.50\\%$) upon stint expiration.</li>
        <li><b>Rule 2 (Sybil Parity Anchor Stake Floor):</b> $S_{{\\text{{short}}}} \\ge 10{{,}}000\\text{{ AVAX}}$ at $d=2\\text{{ days}}$. Lower values fail to penalize short-term churn, collapsing macro network security below the 20-week threshold.</li>
        <li><b>Rule 3 (Mechanism Separation):</b> <code>piecewise_benqi</code> achieves admissibility at lower lockups ($d=56\\text{{d}}, S=10\\text{{k}}$) due to flat duration tiers, whereas <code>harmonic</code> requires higher commitments ($d \\ge 84\\text{{d}}$ for $S \\ge 14\\text{{k}}$) but achieves up to $59.0\\%$ retention.</li>
      </ul>
    </div>

    <!-- FIGURE 1: 3D INTERACTIVE TENSOR PLOT -->
    <div class="section-card">
      <div class="section-title">🌐 Figure 1: 3D Interactive Utility Tensor State Space</div>
      <p style="color: #9ca3af; margin-top: 0;">
        Explore the 84-point state space across $S_{{\\text{{short}}}}$ (x-axis), $d_{{\\text{{target}}}}$ (y-axis), and 
        Stake-Weighted Macro Security Horizon (z-axis). Green/Cyan markers indicate configurations that satisfy all protocol safety constraints ($U=1$). Red markers failed one or more verification gates ($U=0$).
      </p>
      {div_3d}
    </div>

    <!-- FIGURE 2: 2D PROJECTION & SAFE ENVELOPE -->
    <div class="section-card">
      <div class="section-title">⚖️ Figure 2: Bivariate Safe Envelope & Verification Gates</div>
      {div_2d}
    </div>

    <!-- TABLE: FULL 23 ADMISSIBLE SETS -->
    <div class="section-card">
      <div class="section-title">📋 Complete Admissible Parameter Matrix (The 23 Passing Configurations)</div>
      <p style="color: #9ca3af; margin-top: 0;">
        Every configuration in this table satisfies $U(\\theta) = 1$: Retail Retention $\\ge 50\\%$, Stake-Weighted Macro Duration $\\ge 20\\text{{ weeks}}$, and Retail Duration Lift $\\ge +30\\%$.
      </p>
      <div style="overflow-x: auto;">
        <table>
          <thead>
            <tr>
              <th>Frontier Mode</th>
              <th>Anchor Stake S_short</th>
              <th>Target Lockup d_target</th>
              <th>Retail Retention (52w)</th>
              <th>Macro Security Horizon</th>
              <th>Retail Duration Lift</th>
              <th>Utility Gate</th>
            </tr>
          </thead>
          <tbody>
            {table_rows}
          </tbody>
        </table>
      </div>
    </div>

    <!-- FULL DETAILED MEMO PROSE -->
    <div class="section-card">
      <div class="section-title">📄 Formal Engineering Memo & Theoretical Mechanics</div>
      <div class="memo-text">
        <h2>1. The Problem with 2D Heatmaps in Parameter Selection</h2>
        <p>
          Bivariate heatmaps ($S_{{\\text{{short}}}}$ vs. $d_{{\\text{{target}}}}$) force an arbitrary 2D slice through a complex dynamic system. In reality, the admission frontier operates in a high-dimensional space spanned by:
        </p>
        <ul>
          <li><b>Outside Yield Invariant:</b> Frictionless liquid staking returns on sAVAX ($4.15\\% - 4.50\\%$ APR).</li>
          <li><b>VPS Operational Drag:</b> Fixed hardware costs ($\sim \\$40/\\text{{month}}$ VPS overhead imposes a $-0.96\\%$ yield drag on a $2{{,}}000\\text{{ AVAX}}$ validator).</li>
          <li><b>Asynchronous Rollover Arrivals:</b> Stakers enter and mature continuously over time ($U(1, d_{{\\text{{choice}}}})$), preventing artificial synchronized rollover shockwaves.</li>
        </ul>
        <p>
          By adopting the Subspace Network trajectory/utility tensor methodology, we eliminate visual guesswork. We simulate the entire combinatorial grid, project the trajectories into objective KPI vectors, and apply a binary utility function $U(\\theta) \\in \\{{0, 1\\}}$ to isolate the safe envelope.
        </p>

        <h2>2. Mechanism Comparison: Piecewise-BENQI vs. Harmonic Hyperbolic</h2>
        <p>
          The tensor sweep revealed a clear operational divergence between the two candidate curves:
        </p>
        <ul>
          <li>
            <b>Piecewise-BENQI (Flat Tiered Admission):</b> By isolating retail validators ($2{{,}}000\\text{{ AVAX}}$) at a flat step of $8\\text{{ to }}10\\text{{ weeks}}$, small operators are shielded from steep marginal derivative penalties. This yields early admissibility starting at $d=56\\text{{d}}$ ($8\\text{{w}}$) and $S_{{\\text{{short}}}}=10{{,}}000\\text{{ AVAX}}$, achieving $51.8\\%$ node retention.
          </li>
          <li>
            <b>Harmonic Hyperbolic Curve ($S_{{\\min}}(d) = S_{{\\text{{base}}}} \\cdot (d_{{\\max}} / d)^\\alpha$):</b> Because the hyperbolic curve continuously penalizes shorter horizons, retail validators must be pushed to $84\\text{{d}}$ ($12\\text{{w}}$) before the retention gate passes ($52.7\\%$). However, when operators commit to longer horizons ($d=118\\text{{d}}$), the harmonic curve produces the highest overall node retention ($59.0\\%$) and maximum network duration ($23.87\\text{{ weeks}}$) because high yields completely dominate VPS hosting drag.
          </li>
        </ul>

        <h2>3. Final Recommendation for Dr. Eric Lu & Avalanche Foundation</h2>
        <p>
          If the Foundation seeks to <b>minimize friction on existing retail validator operators</b> while guaranteeing protocol security, <b>Package B with Piecewise-BENQI ($S_{{\\text{{short}}}} = 10{{,}}000 - 14{{,}}000\\text{{ AVAX}}, d_{{\\text{{target}}}} = 8\\text{{ to }}10\\text{{ weeks}}$)</b> is the mathematically optimal choice. It retains over $3{{,}}230$ physical nodes and doubles Mainnet's empirical security horizon from $11.6$ to $>20.2$ weeks.
        </p>
      </div>
    </div>
  </div>

  <script>
    document.addEventListener("DOMContentLoaded", function() {{
      if (window.MathJax && window.MathJax.typesetPromise) {{
        window.MathJax.typesetPromise();
      }}
    }});
  </script>
</body>
</html>
"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"Report generated successfully at: {OUTPUT_HTML}")

if __name__ == "__main__":
    generate_report()
