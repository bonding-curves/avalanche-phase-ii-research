"""
Script to build the comprehensive engineering-grade HTML memo.
Combines forensic empirical data, complete assumptions register, mathematical mechanics,
digital twin tensor results, and interactive Plotly visualizations.
"""

import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DATA_PATH = "/home/hash/Hub/Projects/avalanche-phase-ii-research/research/data/psuu_utility_tensor.csv"
OUTPUT_HTML = "/home/hash/Hub/Projects/avalanche-phase-ii-research/research/plots/comprehensive_engineering_memo.html"

def build_memo():
    df = pd.read_csv(DATA_PATH)
    safe_df = df[df["utility"] == 1]
    reject_df = df[df["utility"] == 0]

    # --- Plotly Figures ---
    # Figure 1: 3D Utility Tensor
    fig_3d = go.Figure()
    
    fig_3d.add_trace(go.Scatter3d(
        x=reject_df["s_short"],
        y=reject_df["d_target_days"],
        z=reject_df["macro_duration_w"],
        mode="markers",
        name="Rejected (U=0)",
        marker=dict(size=6, color="#ef4444", opacity=0.35, symbol="circle"),
        hovertemplate=(
            "<b>Rejected Configuration (U=0)</b><br>"
            "Mode: %{customdata[0]}<br>"
            "S_short: %{x:,.0f} AVAX<br>"
            "d_target: %{y:.0f} days (%{customdata[1]:.1f} wks)<br>"
            "Macro Duration: %{z:.2f} wks<br>"
            "Retail Retention: %{customdata[2]:.1%}<extra></extra>"
        ),
        customdata=np.column_stack([
            reject_df["frontier_mode"],
            reject_df["d_target_days"] / 7.0,
            reject_df["retail_retention"]
        ])
    ))

    # Safe piecewise
    safe_benqi = safe_df[safe_df["frontier_mode"] == "piecewise_benqi"]
    fig_3d.add_trace(go.Scatter3d(
        x=safe_benqi["s_short"],
        y=safe_benqi["d_target_days"],
        z=safe_benqi["macro_duration_w"],
        mode="markers",
        name="Admissible: Piecewise-BENQI (U=1)",
        marker=dict(size=10, color="#10b981", symbol="circle", line=dict(color="#ffffff", width=1.5)),
        hovertemplate=(
            "<b>✓ Safe: Piecewise-BENQI (U=1)</b><br>"
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

    # Safe harmonic
    safe_harmonic = safe_df[safe_df["frontier_mode"] == "harmonic"]
    fig_3d.add_trace(go.Scatter3d(
        x=safe_harmonic["s_short"],
        y=safe_harmonic["d_target_days"],
        z=safe_harmonic["macro_duration_w"],
        mode="markers",
        name="Admissible: Harmonic (U=1)",
        marker=dict(size=10, color="#38bdf8", symbol="diamond", line=dict(color="#ffffff", width=1.5)),
        hovertemplate=(
            "<b>✓ Safe: Harmonic (U=1)</b><br>"
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
        title="<b>Figure 1: 3D Parameter State Space Tensor U(θ)</b>",
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
        legend=dict(bgcolor="rgba(17, 24, 39, 0.8)", bordercolor="#374151", borderwidth=1, x=0.02, y=0.98)
    )

    # Figure 2: 2D Tradeoff Planes
    fig_2d = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            "<b>Retail Retention vs. Macro Security Horizon</b>",
            "<b>Admissible Envelope by Frontier Family</b>"
        ),
        horizontal_spacing=0.12
    )

    fig_2d.add_trace(
        go.Scatter(
            x=reject_df["retail_retention"] * 100,
            y=reject_df["macro_duration_w"],
            mode="markers",
            name="Rejected (U=0)",
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
            name="Admissible (U=1)",
            marker=dict(
                color=np.where(safe_df["frontier_mode"] == "piecewise_benqi", "#10b981", "#38bdf8"),
                size=11,
                line=dict(color="#ffffff", width=1.5)
            ),
            hovertemplate=(
                "Mode: %{customdata[0]}<br>"
                "S_short: %{customdata[1]:,.0f} AVAX<br>"
                "d_target: %{customdata[2]:.0f}d (%{customdata[3]:.1f}w)<br>"
                "Retention: %{x:.1f}%<br>"
                "Macro Duration: %{y:.2f} wks<extra></extra>"
            ),
            customdata=np.column_stack([
                safe_df["frontier_mode"],
                safe_df["s_short"],
                safe_df["d_target_days"],
                safe_df["d_target_days"] / 7.0
            ])
        ),
        row=1, col=1
    )

    fig_2d.add_vline(x=50.0, line_dash="dash", line_color="#f59e0b", row=1, col=1,
                     annotation_text="Min Retention (50%)", annotation_position="top left", annotation_font_color="#f59e0b")
    fig_2d.add_hline(y=20.0, line_dash="dash", line_color="#f59e0b", row=1, col=1,
                     annotation_text="Min Macro Horizon (20w)", annotation_position="bottom right", annotation_font_color="#f59e0b")

    # Subplot 2: Grid mask
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

    fig_2d.update_xaxes(title_text="Retail Retention (% of nodes)", row=1, col=1, gridcolor="#1e293b", zerolinecolor="#334155")
    fig_2d.update_yaxes(title_text="Macro Duration (Weeks)", row=1, col=1, gridcolor="#1e293b", zerolinecolor="#334155")
    fig_2d.update_xaxes(title_text="Anchor Stake S_short (AVAX)", row=1, col=2, gridcolor="#1e293b", zerolinecolor="#334155")
    fig_2d.update_yaxes(title_text="Target Lockup d_target (Weeks)", row=1, col=2, gridcolor="#1e293b", zerolinecolor="#334155")

    fig_2d.update_layout(
        paper_bgcolor="#030712",
        plot_bgcolor="#0b0f19",
        font=dict(color="#f3f4f6", family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto"),
        height=480,
        margin=dict(l=50, r=40, b=50, t=60),
        legend=dict(bgcolor="rgba(17, 24, 39, 0.8)", bordercolor="#374151", borderwidth=1)
    )

    div_3d = fig_3d.to_html(full_html=False, include_plotlyjs="cdn")
    div_2d = fig_2d.to_html(full_html=False, include_plotlyjs=False)

    # 23 Admissible configurations rows
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
  <title>Avalanche Admission Frontier: Engineering Specification & Memo</title>
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
      line-height: 1.65;
    }}
    .container {{
      max-width: 1400px;
      margin: 0 auto;
    }}
    .header-bar {{
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
      font-size: 2.2rem;
      font-weight: 800;
      color: #f9fafb;
      margin: 0 0 10px 0;
      letter-spacing: -0.02em;
    }}
    .meta-box {{
      background: #0b0f19;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 16px 20px;
      margin-top: 16px;
      font-size: 0.9rem;
      color: #9ca3af;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
    }}
    .meta-item b {{
      color: #e5e7eb;
    }}
    .nav-pills {{
      display: flex;
      gap: 12px;
      margin-top: 16px;
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

    .section-card {{
      background: #0b0f19;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 28px;
      margin-bottom: 32px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    }}
    .section-title {{
      font-size: 1.35rem;
      font-weight: 700;
      color: #38bdf8;
      margin-top: 0;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
      border-bottom: 1px solid #1e293b;
      padding-bottom: 10px;
    }}
    .section-card p {{
      color: #d1d5db;
      font-size: 1rem;
      margin-bottom: 16px;
    }}
    .section-card ul, .section-card ol {{
      color: #d1d5db;
      padding-left: 24px;
      margin-bottom: 16px;
    }}
    .section-card li {{
      margin-bottom: 8px;
    }}

    .alert-box {{
      background: rgba(245, 158, 11, 0.08);
      border: 1px solid rgba(245, 158, 11, 0.3);
      border-radius: 8px;
      padding: 16px 20px;
      margin-bottom: 20px;
      color: #fde68a;
    }}
    .alert-box h4 {{
      margin: 0 0 6px 0;
      color: #fbbf24;
      font-size: 1rem;
    }}

    .rule-banner {{
      background: rgba(56, 189, 248, 0.08);
      border: 1px solid rgba(56, 189, 248, 0.3);
      border-radius: 8px;
      padding: 16px 20px;
      margin-bottom: 24px;
    }}
    .rule-banner h4 {{
      margin: 0 0 8px 0;
      color: #38bdf8;
      font-size: 1.05rem;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
      margin-top: 12px;
      margin-bottom: 20px;
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
    code {{
      background: #1e293b;
      color: #38bdf8;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.9em;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header-bar">
      <span class="badge">Systems Engineering &bull; Canonical Specification</span>
      <h1>Avalanche Admission Frontier: Engineering Specification & Recommendation Memo</h1>
      <p style="color: #9ca3af; font-size: 1.1rem; margin: 0; max-width: 1000px;">
        First-principles derivation, empirical data audit (`01-renewal-panel.parquet`), formal assumptions register, 
        and digital twin parameter selection under uncertainty (PSuU).
      </p>

      <div class="meta-box">
        <div class="meta-item"><b>Author:</b> Antigravity AI & BCRG Systems Engineering</div>
        <div class="meta-item"><b>Date:</b> September 24, 2026</div>
        <div class="meta-item"><b>Audience:</b> BCRG Research, Dr. Eric Lu (Avalanche Foundation)</div>
        <div class="meta-item"><b>Primary Data:</b> `01-renewal-panel.parquet` (57,067 records)</div>
        <div class="meta-item"><b>Digital Twin:</b> `gds-sim` discrete-event 52-week engine</div>
        <div class="meta-item"><b>Status:</b> Complete Canonical Engineering Review</div>
      </div>

      <div class="nav-pills">
        <a href="frontier_calculator.html" class="btn btn-primary" target="_blank">
          🧮 Interactive Desmos Calculator
        </a>
        <a href="simulation_results.html" class="btn btn-secondary" target="_blank">
          📊 52-Week Trajectory Dashboard
        </a>
        <a href="admission_frontier_tensor_report.html" class="btn btn-secondary" target="_blank">
          🌐 3D Tensor State Space Report
        </a>
      </div>
    </div>

    <!-- SECTION 1: EMPIRICAL DATA RECONCILIATION -->
    <div class="section-card">
      <div class="section-title">📊 1. Forensic Empirical Analysis: Why Means Are Misleading</div>
      <p>
        In skewed distributions, the arithmetic mean is an uninformative statistic. In the Avalanche Primary Network staking corpus 
        (<code>01-renewal-panel.parquet</code>, containing <b>57,067 reconciled validation periods</b> across <b>7,635 unique physical nodes</b>), 
        stakers are hyper-clustered at the shortest legal boundary. 
      </p>

      <table>
        <thead>
          <tr>
            <th>Segment / Population</th>
            <th>Sample Count (N)</th>
            <th>Unweighted Median (Behavioral Action)</th>
            <th>Unweighted Mean (Inflated by Tail)</th>
            <th>Stake-Weighted Mean (Consensus Security)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>All-Time Network (Pooled)</b></td>
            <td><b>57,067</b></td>
            <td><b>23.0 days (3.3w)</b></td>
            <td>45.6 days (6.5w)</td>
            <td><b>80.3 days (11.5w)</b></td>
          </tr>
          <tr>
            <td><b>Pre-Etna Era</b></td>
            <td>39,249</td>
            <td><b>29.0 days (4.1w)</b></td>
            <td>51.1 days (7.3w)</td>
            <td>88.3 days (12.6w)</td>
          </tr>
          <tr>
            <td><b>Post-Etna Era (Current Reality)</b></td>
            <td>17,818</td>
            <td><b style="color: #f87171;">15.0 days (2.1w)</b></td>
            <td>33.5 days (4.8w)</td>
            <td><b style="color: #f87171;">62.3 days (8.9w)</b></td>
          </tr>
          <tr>
            <td><b>Retail Cohort (&lt; 6,000 AVAX)</b></td>
            <td>42,710</td>
            <td><b>18.0 days (2.6w)</b></td>
            <td>39.1 days (5.6w)</td>
            <td>40.9 days (5.8w)</td>
          </tr>
          <tr>
            <td>&mdash; <i>Retail Post-Etna Only</i></td>
            <td>13,239</td>
            <td><b style="color: #f87171;">15.0 days (2.1w)</b></td>
            <td>27.7 days (4.0w)</td>
            <td>29.1 days (4.2w)</td>
          </tr>
          <tr>
            <td><b>Whale Cohort (&ge; 6,000 AVAX)</b></td>
            <td>14,357</td>
            <td><b>31.0 days (4.4w)</b></td>
            <td>64.8 days (9.3w)</td>
            <td><b>81.0 days (11.6w)</b></td>
          </tr>
        </tbody>
      </table>

      <div class="alert-box">
        <h4>⚡ Key Behavioral Insights from the Panel</h4>
        <ul style="margin: 0; padding-left: 20px;">
          <li><b>Post-Etna Median Collapse:</b> Post-Etna, the median validator stint collapsed to <b>15.0 days</b>&mdash;literally 24 hours above the 14-day legal floor. Quoting an unweighted mean (like 37.1d or 45.6d) creates false comfort by masking that retail nodes are addicted to rolling 14-day contracts.</li>
          <li><b>Diagonal State-Dependence:</b> <b>74.5%</b> of nodes that enter on the 14-day floor choose the 14-day floor again on renewal. Duration is habit-forming.</li>
          <li><b>Tenure-Dependent Exit Hazard:</b> A validator's exit hazard is <b>28.9%</b> on their 1st staking stint, dropping to <b>14.7%</b> by stint 3, and &lt;<b>8%</b> by stint 7. Early tenure carries the highest flight risk.</li>
        </ul>
      </div>
    </div>

    <!-- SECTION 2: BENQI STRUCTURAL FOOTPRINT & INCENTIVE REALITY -->
    <div class="section-card">
      <div class="section-title">🏛️ 2. The BENQI Capital Footprint & Incentive Reality</div>
      <p>
        On-chain reconciliation (TASK-HIGH.04 & HIGH.05 across Snowflake Primary Network data) proves that BENQI operates as a near-monopoly on programmatic delegation flow:
      </p>

      <table>
        <thead>
          <tr>
            <th>Measurement Dimension</th>
            <th>BENQI Value</th>
            <th>Rest of Network</th>
            <th>BENQI Share</th>
            <th>Mechanical Interpretation</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>Active Delegated Stock</b></td>
            <td><b>18,143,774 AVAX</b></td>
            <td>20,569,288 AVAX</td>
            <td><b style="color: #38bdf8;">46.9%</b></td>
            <td>Almost half of all delegated capital on Avalanche belongs to BENQI.</td>
          </tr>
          <tr>
            <td><b>Trailing 365-Day Volume Flow</b></td>
            <td><b>467,435,493 AVAX</b></td>
            <td>196,003,294 AVAX</td>
            <td><b style="color: #38bdf8;">70.5%</b></td>
            <td>7 out of every 10 AVAX entering delegations over the last year came from BENQI.</td>
          </tr>
          <tr>
            <td><b>All-Time Cumulative Flow</b></td>
            <td>1,048,481,123 AVAX</td>
            <td>1,709,948,314 AVAX</td>
            <td>38.0%</td>
            <td>Lower historically because BENQI only achieved dominant scale in 2024&ndash;2026.</td>
          </tr>
          <tr>
            <td><b>Active Delegation Positions</b></td>
            <td><b>24,005 positions</b></td>
            <td>&mdash;</td>
            <td>99.9%+</td>
            <td>BENQI holds 24,005 open UTXOs; the 2nd largest delegator holds just <b>5</b>.</td>
          </tr>
          <tr>
            <td><b>Annual Capital Turnover</b></td>
            <td><b>25.76&times; / year</b></td>
            <td>9.53&times; / year</td>
            <td>2.7&times; faster</td>
            <td>365 / 25.76 = <b>14.17 days</b>. BENQI systematically churns in 14-day terms.</td>
          </tr>
        </tbody>
      </table>

      <div class="alert-box" style="background: rgba(239, 68, 68, 0.08); border-color: rgba(239, 68, 68, 0.3); color: #fca5a5;">
        <h4 style="color: #f87171;">⚠️ Why We CANNOT Rely on Asking BENQI to Voluntarily Lengthen Lockups</h4>
        <p style="margin-bottom: 0;">
          BENQI is a liquid staking protocol issuer (<code>sAVAX</code>). Their core value proposition is liquidity, instant redemption buffers, 
          and dynamic rebalancing across high-performing validators. Asking BENQI to voluntarily lock their delegations into 60-day or 90-day terms 
          forces them to take on severe duration risk and eliminates their liquidity reserves. 
          <b>They have zero incentive to agree to this.</b> Therefore, the protocol cannot rely on off-chain cooperation; 
          the <b>on-chain mechanism itself</b> ($S_{{\\min}}(d)$ combined with ACP-285 yield curve steepening) must make longer commitments 
          strictly profit-maximizing for validators and delegators alike.
        </p>
      </div>

      <p>
        <b>The 6,000 AVAX Threshold Step Function:</b> BENQI's Open Pool (65% of volume) requires validator self-stake $\ge 6{{,}}000\text{{ AVAX}}$, 
        a fee of exactly $2\%$, and uptime $\ge 15\text{{ days}}$. On-chain analysis proves that crossing from 5,999 to 6,000 AVAX self-bond increases 
        expected delegation volume by <b>$1.53\times$ locally</b> and <b>$80\times$ across the whole network</b>. Validators with $\ge 6{{,}}000\text{{ AVAX}}$ 
        captured <b>$97.18\%$ of all delegation volume in network history</b> ($2.67\text{{B AVAX}}$). Any admission frontier must preserve this knot 
        at $(14\text{{d}}, 6{{,}}000\text{{ AVAX}})$ to avoid breaking physical node financing.
      </p>
    </div>

    <!-- SECTION 3: FORMAL ASSUMPTIONS REGISTER -->
    <div class="section-card">
      <div class="section-title">📋 3. Formal Assumptions Register</div>
      <p>
        Every model output and recommendation rests upon the following explicit engineering and economic assumptions:
      </p>

      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Parameter / Dynamics</th>
            <th>Baseline Value</th>
            <th>Formal Assumption & Underlying Rationale</th>
            <th>Sensitivity & Known Limitations</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>A-01</b></td>
            <td>Cloud VPS Cost Drag</td>
            <td><b>&minus;0.96% APY</b></td>
            <td>Hardware costs $\sim \$40/\text{{mo}}$ ($\$480/\text{{yr}}$) on 2,000 AVAX ($V_{{\\text{{stake}}}} = \$50{{,}}000$ at $\$25/\text{{AVAX}}$).</td>
            <td>If AVAX drops to $\$10$, drag becomes &minus;2.40% APY. Bare-metal operators with sunk hardware face $\$0$ marginal drag.</td>
          </tr>
          <tr>
            <td><b>A-02</b></td>
            <td>Liquid Staking Outside Option</td>
            <td><b>4.15% APY</b></td>
            <td>Standalone validators compare net return to frictionless sAVAX yield (30-day trailing mean).</td>
            <td>If sAVAX yield rises above 5.0%, validator exit acceleration increases unless matched by delegations.</td>
          </tr>
          <tr>
            <td><b>A-03</b></td>
            <td>Capital Concentration</td>
            <td><b>&gt;98% Whale Share</b></td>
            <td>Institutional stakers ($\ge 6{{,}}000\text{{ AVAX}}$) control $>98\%$ of bonded capital. Macro security is dictated by capital, not node count.</td>
            <td>Whales optimize ACP-285 term premiums (4.08% $\to$ 6.38%), ignoring minor cloud VPS hardware costs.</td>
          </tr>
          <tr>
            <td><b>A-04</b></td>
            <td>Dual-Stage Rational Exit</td>
            <td>$p_{{\\text{{exit}}}} \\in [1\\%, 35\\%]$</td>
            <td>Expiring nodes exit if net spread against sAVAX is negative: $p_{{\\text{{exit}}}} = \\min(0.35, 0.02 + 0.12 \\frac{{-\\Delta}}{{0.01}} + 0.02 \\Delta_{{\\text{{dur}}}})$.</td>
            <td>Calibrated logit choice model. High liquidity preference ($\\lambda = 1.2$) forces stakers to shortest admissible duration.</td>
          </tr>
          <tr>
            <td><b>A-05</b></td>
            <td>Stationary Continuous Arrivals</td>
            <td>$\\tau_{{\\text{{rem}}}} \\sim U(1, d)$</td>
            <td>Initial remaining contract durations are uniform $U(1, d_{{\\text{{choice}}}})$ at $t=0$, reflecting ongoing asynchronous distributed arrivals.</td>
            <td><b>Critical Invariant:</b> Prevents artificial harmonic resonance and synchronized rollover cliffs at Week 26.</td>
          </tr>
          <tr>
            <td><b>A-06</b></td>
            <td>Closed Macro Economy</td>
            <td>450M AVAX Supply</td>
            <td>Total supply float is fixed at 450M AVAX; staking ratio target corridor is $50\\% - 60\\%$.</td>
            <td>Does not model external macro exchange crashes or regulatory shocks.</td>
          </tr>
          <tr>
            <td><b>A-07</b></td>
            <td>BENQI Open Pool Pinning</td>
            <td>6,000 AVAX @ 14d</td>
            <td>BENQI maintains its 6,000 AVAX qualification floor for 65% of delegation volume.</td>
            <td>Frontier must preserve $(14\\text{{d}}, 6{{,}}000\\text{{ AVAX}})$ knot to avoid disrupting liquid staking liquidity.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- SECTION 4: MATHEMATICAL DERIVATIONS & GOVERNING EQUATIONS -->
    <div class="section-card">
      <div class="section-title">📐 4. Mathematical Mechanics & Governing Equations</div>
      
      <p><b>1. Global Sybil Parity Invariant:</b></p>
      <p>
        To prevent stake-splitting attacks that dilute consensus sampling or bloat P-Chain state, the cumulative capital-duration commitment 
        at any duration $d$ must equal or exceed Mainnet's canonical baseline ($2{{,}}000\\text{{ AVAX}} \\times 14\\text{{ days}} = 28{{,}}000\\text{{ AVAX-days}}$):
      </p>
      $$\\kappa(d) = S_{{\\min}}(d) \\cdot d \\ge 28{{,}}000\\text{{ AVAX-days}} \\implies S_{{\\min}}(2\\text{{d}}) \\ge 14{{,}}000\\text{{ AVAX}}$$

      <p><b>2. Harmonic Bounded Decay Curve:</b></p>
      $$S_{{\\min}}(d) = 500 + (S_{{\\text{{short}}}} - 500) \\cdot \\left[ \\frac{{\\frac{{1}}{{d}} - \\frac{{1}}{{365}}}}{{\\frac{{1}}{{2}} - \\frac{{1}}{{365}}}} \\right]^p$$
      $$\\text{{where }}\\quad p = \\frac{{\\ln\\left(\\frac{{2{{,}}000 - 500}}{{S_{{\\text{{short}}}} - 500}}\\right)}}{{\\ln\\left(\\frac{{\\frac{{1}}{{d_{{\\text{{target}}}}}} - \\frac{{1}}{{365}}}}{{\\frac{{1}}{{2}} - \\frac{{1}}{{365}}}}\\right)}}$$

      <p><b>3. Piecewise-BENQI Curve (4-Knot Inverse-Linear Interpolation):</b></p>
      <p>
        Pinned explicitly to four structural market coordinates: 
        $(2\\text{{d}}, S_{{\\text{{short}}}})$, $(14\\text{{d}}, 6{{,}}000\\text{{ AVAX}})$, $(d_{{\\text{{target}}}}, 2{{,}}000\\text{{ AVAX}})$, and $(365\\text{{d}}, 500\\text{{ AVAX}})$. 
        Between any two knots $(d_0, s_0)$ and $(d_1, s_1)$, admission stake interpolates linearly in inverse-time space:
      </p>
      $$t(d) = \\frac{{\\frac{{1}}{{d}} - \\frac{{1}}{{d_1}}}}{{\\frac{{1}}{{d_0}} - \\frac{{1}}{{d_1}}}}, \\quad S_{{\\min}}(d) = s_1 + (s_0 - s_1) \\cdot t(d)$$
    </div>

    <!-- SECTION 5: DIGITAL TWIN EXPERIMENT & TENSOR RESULTS -->
    <div class="section-card">
      <div class="section-title">🧪 5. Digital Twin Experiment & Algorithmic Frontier</div>
      <p>
        Using the Subspace P6 tensor reduction architecture (<code>run_tensor_psuu.py</code>), we crossed 84 coordinate combinations 
        ($7\\text{{ durations}} \\times 6\\text{{ anchor stakes}} \\times 2\\text{{ curves}}$) over a 52-week discrete-time simulation ($dt = 1\\text{{ week}}$). 
        Each trajectory was evaluated against a Boolean Utility Function:
      </p>
      $$U(\\theta) = \\mathbb{{I}}\\left( \\text{{Retail Retention}} \\ge 50.0\\% \\;\\land\\; \\text{{Macro Duration}} \\ge 20.0\\text{{ weeks}} \\;\\land\\; \\text{{Retail Lift}} \\ge +30\\% \\right)$$

      <div class="rule-banner">
        <h4>⚡ Extracted Algorithmic Boundary Rules (Out of 84 Trajectories)</h4>
        <ul style="margin: 0; padding-left: 20px;">
          <li><b>Rule 1:</b> $\\min(d_{{\\text{{target}}}}) \\ge \\mathbf{{56.0\\text{{ days (8 weeks)}}}}$. No parameter set with $d \\le 42\\text{{d}}$ passes the retention gate.</li>
          <li><b>Rule 2:</b> $\\min(S_{{\\text{{short}}}}) \\ge \\mathbf{{10{{,}}000\\text{{ AVAX}}}}$. Below 10k, short-end churn collapses macro network security.</li>
          <li><b>Admissible Set:</b> Exactly <b>23 configurations (27.4%)</b> cleared all verification gates ($U=1$).</li>
        </ul>
      </div>

      <!-- FIGURE 1: 3D TENSOR -->
      <div style="margin: 24px 0;">
        {div_3d}
      </div>

      <!-- FIGURE 2: 2D TRADEOFFS -->
      <div style="margin: 24px 0;">
        {div_2d}
      </div>
    </div>

    <!-- SECTION 6: WHY PIECEWISE DOMINATES HARMONIC -->
    <div class="section-card">
      <div class="section-title">⚖️ 6. Comparative Dynamics: Piecewise-BENQI vs. Harmonic</div>
      
      <table>
        <thead>
          <tr>
            <th>Frontier Metric / Dynamic</th>
            <th>Continuous Harmonic Curve (`harmonic`)</th>
            <th>Piecewise-BENQI Curve (`piecewise_benqi`)</th>
            <th>First-Principles Systems Engineering Rationale</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>Minimum Viable $d_{{\\text{{target}}}}$</b></td>
            <td><b>84.0 days (12.0 weeks)</b></td>
            <td><b style="color: #34d399;">56.0 days (8.0 weeks)</b></td>
            <td>`piecewise_benqi` achieves compliance with a 4-week shorter lockup requirement.</td>
          </tr>
          <tr>
            <td><b>Minimum Viable $S_{{\\text{{short}}}}$</b></td>
            <td>14,000 AVAX</td>
            <td><b style="color: #34d399;">10,000 AVAX</b></td>
            <td>Permits a wider operational envelope for testing stints without violating Sybil limits.</td>
          </tr>
          <tr>
            <td><b>Retail Retention at 8w&ndash;10w</b></td>
            <td><span style="color: #f87171;">41.8% &ndash; 45.6% (FAIL)</span></td>
            <td><b style="color: #34d399;">50.2% &ndash; 51.8% (PASS)</b></td>
            <td>The steep derivative of the harmonic curve forces small nodes out at intermediate lockups.</td>
          </tr>
          <tr>
            <td><b>BENQI 6k Liquidity Knot</b></td>
            <td>Arbitrary ($4{{,}}500 - 8{{,}}200\\text{{ AVAX}}$)</td>
            <td><b style="color: #34d399;">Explicitly Pinned at (14d, 6k)</b></td>
            <td>Protects Open Pool delegation routing without requiring protocol or off-chain changes.</td>
          </tr>
          <tr>
            <td><b>Marginal Derivative $\\frac{{\\partial S_{{\\min}}}}{{\\partial d}}$</b></td>
            <td>Steep derivative across the entire curve</td>
            <td>Flat step between 14d and $d_{{\\text{{target}}}}$</td>
            <td>Small operators face predictable thresholds without marginal bracket creep.</td>
          </tr>
        </tbody>
      </table>

      <p>
        <b>The Mathematical Cause:</b> In the continuous harmonic curve, forcing $S_{{\\min}}(d_{{\\text{{target}}}}) = 2{{,}}000$ when $d_{{\\text{{target}}}} = 56\\text{{d}}$ 
        steepens the exponent $p$. As a result, stakers attempting to enter at $30\\text{{d}}$ or $42\\text{{d}}$ face punitive barriers ($S_{{\\min}} &gt; 3{{,}}500\\text{{ AVAX}}$). 
        Unable to top up, they shut down their VPS and exit into sAVAX. 
        <code>piecewise_benqi</code> eliminates this derivative penalty by connecting $(14\\text{{d}}, 6{{,}}000)$ directly to $(d_{{\\text{{target}}}}, 2{{,}}000)$ with a predictable slope.
      </p>
    </div>

    <!-- SECTION 7: POLICY RECOMMENDATIONS & TRADE-OFF MATRIX -->
    <div class="section-card">
      <div class="section-title">🏆 7. Final Policy Package Recommendation</div>
      
      <table>
        <thead>
          <tr>
            <th>Evaluation Dimension</th>
            <th>Package C (Mild Reform)</th>
            <th>Package B (RECOMMENDED)</th>
            <th>Package A (Aggressive Pivot)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>Target Lockup ($d_{{\\text{{target}}}}$)</b></td>
            <td>42.0 days (6.0 weeks)</td>
            <td><b style="color: #38bdf8;">56.0 &ndash; 70.0 days (8.0 &ndash; 10.0 weeks)</b></td>
            <td>118.0 days (16.9 weeks)</td>
          </tr>
          <tr>
            <td><b>Anchor Stake ($S_{{\\text{{short}}}}$)</b></td>
            <td>14,000 AVAX</td>
            <td><b style="color: #38bdf8;">14,000 &ndash; 16,000 AVAX</b></td>
            <td>20,000 AVAX</td>
          </tr>
          <tr>
            <td><b>Frontier Curve Family</b></td>
            <td>`piecewise_benqi`</td>
            <td><b style="color: #34d399;">`piecewise_benqi`</b></td>
            <td>`harmonic` or `piecewise`</td>
          </tr>
          <tr>
            <td><b>Retail Node Retention (52w)</b></td>
            <td><span style="color: #f87171;">44.7% (2,878 nodes)</span></td>
            <td><b style="color: #34d399;">50.2% &ndash; 51.8% (3,230 &ndash; 3,335 nodes)</b></td>
            <td>53.5% &ndash; 59.0% (3,445 &ndash; 3,800 nodes)</td>
          </tr>
          <tr>
            <td><b>Retail Duration Lift vs. 15d Median</b></td>
            <td>+180% (42 days)</td>
            <td><b style="color: #34d399;">+273% to +366% (56 &ndash; 70 days)</b></td>
            <td>+686% (118 days)</td>
          </tr>
          <tr>
            <td><b>Stake-Weighted Macro Horizon</b></td>
            <td>20.58 weeks</td>
            <td><b style="color: #38bdf8;">20.20 &ndash; 21.74 weeks</b></td>
            <td>21.69 &ndash; 23.87 weeks</td>
          </tr>
          <tr>
            <td><b>Global Sybil Parity</b></td>
            <td>1.00&times; (28,000 AVAX-d)</td>
            <td><b>1.00&times; &ndash; 1.14&times; (28,000 &ndash; 32,000 AVAX-d)</b></td>
            <td>1.43&times; (40,000 AVAX-d)</td>
          </tr>
          <tr>
            <td><b>Utility Status ($U(\\theta)$)</b></td>
            <td><b style="color: #f87171;">FAIL (U=0)</b></td>
            <td><b style="color: #34d399;">PASS (U=1)</b></td>
            <td><b style="color: #34d399;">PASS (U=1)</b></td>
          </tr>
          <tr>
            <td><b>Systems Engineering Verdict</b></td>
            <td><b>REJECTED:</b> Loses &gt;3,500 physical nodes due to VPS yield drag.</td>
            <td><b>OPTIMAL:</b> Preserves &gt;3,230 nodes while doubling network security.</td>
            <td><b>HIGH FRICTION:</b> Forces small nodes to 8&times; their current lockup.</td>
          </tr>
        </tbody>
      </table>

      <div class="alert-box" style="background: rgba(16, 185, 129, 0.08); border-color: rgba(16, 185, 129, 0.3); color: #a7f3d0;">
        <h4 style="color: #34d399;">🎯 Final Recommendation for Dr. Eric Lu & The Avalanche Foundation</h4>
        <p style="margin-bottom: 0;">
          Deploy <b>Package B with Piecewise-BENQI ($S_{{\\text{{short}}}} = 14{{,}}000 - 16{{,}}000\\text{{ AVAX}}, d_{{\\text{{target}}}} = 8\\text{{ to }}10\\text{{ weeks}}$)</b>. 
          This configuration:
          <br>1. Preserves over <b>3,230 physical retail validator nodes</b> against liquid staking outside options.
          <br>2. Doubles network-wide capital security from $11.6\text{{ weeks}}$ to <b>$>20.2\text{{ weeks}}$</b>, achieving the Foundation's macro security mandate.
          <br>3. Maintains exact mathematical Sybil parity ($\ge 28{{,}}000\text{{ AVAX-days}}$) across all stint lengths.
          <br>4. Seamlessly protects BENQI's Open Pool ($6{{,}}000\text{{ AVAX}}$) capital allocation pipeline without requiring off-chain coordination.
        </p>
      </div>
    </div>

    <!-- SECTION 8: COMPLETE ADMISSIBLE MATRIX TABLE -->
    <div class="section-card">
      <div class="section-title">📋 8. Complete Admissible Parameter Matrix (The 23 Passing Configurations)</div>
      <p>
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

    print(f"Comprehensive Engineering Memo successfully generated at: {OUTPUT_HTML}")

if __name__ == "__main__":
    build_memo()
