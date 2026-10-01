#!/usr/bin/env python3
"""Generates the revised Avalanche Phase II Research Workflow Infographic.

Renders an HTML/SVG visualization capturing the full research history,
iterative false starts, feedback loops, empirical discoveries, and current
Stage 4 status, then renders it to a high-resolution PNG using Playwright.
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: #f8fafc;
    color: #0f172a;
    width: 1720px;
    height: 1180px;
    padding: 24px 32px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: hidden;
  }

  /* Header */
  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding-bottom: 12px;
    border-bottom: 2px solid #e2e8f0;
  }
  .title-group h1 {
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #0f172a;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .title-group h1 span.tag {
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    background: #e0e7ff;
    color: #3730a3;
    padding: 4px 10px;
    border-radius: 6px;
    letter-spacing: 0.5px;
  }
  .title-group p {
    font-size: 14px;
    color: #475569;
    margin-top: 4px;
    font-weight: 500;
  }
  .legend {
    display: flex;
    gap: 18px;
    background: #ffffff;
    padding: 8px 16px;
    border-radius: 8px;
    border: 1px solid #cbd5e1;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }
  .legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 600;
    color: #334155;
  }
  .legend-line {
    width: 22px;
    height: 3px;
    border-radius: 2px;
  }
  .legend-fwd { background: #16a34a; }
  .legend-loop { background: #dc2626; border-top: 2px dashed #dc2626; height: 0; }
  .legend-amber { background: #d97706; }
  .legend-curr { background: #7c3aed; }

  /* Upper Feedback Loop Overlays Banner */
  .feedback-banner {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin: 10px 0 6px 0;
  }
  .feedback-pill {
    background: #fef2f2;
    border: 1.5px solid #f87171;
    border-radius: 8px;
    padding: 8px 12px;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    box-shadow: 0 1px 2px rgba(220, 38, 38, 0.05);
  }
  .feedback-pill .icon {
    font-size: 14px;
    line-height: 1;
    background: #fee2e2;
    color: #dc2626;
    padding: 4px 6px;
    border-radius: 4px;
    font-weight: 800;
  }
  .feedback-pill .text {
    font-size: 11px;
    line-height: 1.35;
    color: #991b1b;
  }
  .feedback-pill .text strong {
    color: #7f1d1d;
    font-size: 11.5px;
  }

  /* 6 Columns Stage Grid */
  .stages-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 14px;
    margin-top: 4px;
    flex-grow: 1;
  }
  .stage-col {
    background: #ffffff;
    border-radius: 12px;
    border: 1.5px solid #e2e8f0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    position: relative;
  }

  /* Col Header */
  .col-header {
    padding: 10px 12px;
    border-bottom: 1.5px solid;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .col-badge {
    font-size: 10.5px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.6px;
  }
  .col-title {
    font-size: 14px;
    font-weight: 800;
    line-height: 1.2;
  }

  /* Stage Color Themes */
  .s0 { border-color: #93c5fd; }
  .s0 .col-header { background: #eff6ff; border-color: #bfdbfe; color: #1e40af; }
  .s0 .col-badge { color: #2563eb; }

  .s1 { border-color: #67e8f9; }
  .s1 .col-header { background: #ecfeff; border-color: #a5f3fc; color: #0e7490; }
  .s1 .col-badge { color: #0891b2; }

  .s2 { border-color: #fde047; }
  .s2 .col-header { background: #fefce8; border-color: #fef08a; color: #854d0e; }
  .s2 .col-badge { color: #ca8a04; }

  .s3 { border-color: #86efac; }
  .s3 .col-header { background: #f0fdf4; border-color: #bbf7d0; color: #166534; }
  .s3 .col-badge { color: #16a34a; }

  .s4 { border-color: #d8b4fe; }
  .s4 .col-header { background: #faf5ff; border-color: #e9d5ff; color: #6b21a8; }
  .s4 .col-badge { color: #9333ea; }

  .s5 { border-color: #fca5a5; }
  .s5 .col-header { background: #fff1f2; border-color: #fecdd3; color: #9f1239; }
  .s5 .col-badge { color: #e11d48; }

  /* Body Content */
  .col-body {
    padding: 10px 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex-grow: 1;
    background: #fafaf9;
  }

  .card-box {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 8px 10px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
  }
  .card-box.alert-amber {
    background: #fffbeb;
    border-color: #fde68a;
  }
  .card-box.alert-purple {
    background: #fbf7ff;
    border-color: #e9d5ff;
  }

  .card-label {
    font-size: 10px;
    font-weight: 800;
    text-transform: uppercase;
    color: #64748b;
    margin-bottom: 4px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .card-label span.pill {
    background: #f1f5f9;
    color: #475569;
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 9px;
  }
  .card-list {
    list-style: none;
    font-size: 11px;
    color: #334155;
    line-height: 1.35;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .card-list li {
    position: relative;
    padding-left: 12px;
  }
  .card-list li::before {
    content: "•";
    position: absolute;
    left: 0;
    color: #64748b;
    font-weight: 800;
  }
  .card-list li strong {
    color: #0f172a;
    font-weight: 700;
  }

  /* Output Footer of Column */
  .col-footer {
    padding: 8px 10px;
    background: #ffffff;
    border-top: 1px solid #e2e8f0;
    font-size: 10.5px;
    line-height: 1.3;
  }
  .col-footer .f-title {
    font-size: 9.5px;
    font-weight: 800;
    text-transform: uppercase;
    color: #475569;
    margin-bottom: 3px;
  }
  .col-footer ul {
    list-style: none;
    color: #334155;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .col-footer ul li::before {
    content: "→ ";
    color: #0284c7;
    font-weight: 700;
  }

  /* Bottom False Starts & Audits Banner */
  .pivot-banner {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin: 8px 0;
  }
  .pivot-card {
    background: #fff;
    border-radius: 8px;
    border: 1px solid #cbd5e1;
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    position: relative;
  }
  .pivot-card.amber { border-left: 4px solid #f59e0b; }
  .pivot-card.red { border-left: 4px solid #ef4444; }
  .pivot-card.purple { border-left: 4px solid #8b5cf6; }

  .pivot-badge {
    font-size: 9.5px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: flex;
    justify-content: space-between;
  }
  .pivot-card.red .pivot-badge { color: #dc2626; }
  .pivot-card.amber .pivot-badge { color: #d97706; }
  .pivot-card.purple .pivot-badge { color: #7c3aed; }
  .pivot-desc {
    font-size: 11px;
    color: #334155;
    line-height: 1.35;
  }
  .pivot-desc strong { color: #0f172a; }

  /* Timeline */
  .timeline-container {
    background: #ffffff;
    border: 1.5px solid #cbd5e1;
    border-radius: 10px;
    padding: 10px 14px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.04);
  }
  .timeline-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }
  .timeline-header h3 {
    font-size: 13px;
    font-weight: 800;
    color: #1e293b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .timeline-header span {
    font-size: 11px;
    color: #64748b;
    font-weight: 600;
  }
  .timeline-track {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
    position: relative;
  }
  .step-node {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    flex: 1;
    position: relative;
  }
  .step-bubble {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: #e2e8f0;
    color: #475569;
    font-size: 11px;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid #cbd5e1;
    margin-bottom: 4px;
    z-index: 2;
  }
  .step-node.completed .step-bubble {
    background: #dcfce7;
    color: #15803d;
    border-color: #86efac;
  }
  .step-node.active .step-bubble {
    background: #7c3aed;
    color: #ffffff;
    border-color: #6d28d9;
    box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.25);
  }
  .step-node.next .step-bubble {
    background: #f1f5f9;
    color: #94a3b8;
    border-color: #cbd5e1;
    border-style: dashed;
  }
  .step-label {
    font-size: 10.5px;
    font-weight: 700;
    color: #334155;
    line-height: 1.2;
    margin-bottom: 2px;
  }
  .step-sub {
    font-size: 9px;
    color: #64748b;
    line-height: 1.15;
  }
  .step-node.active .step-label { color: #7c3aed; }
  .step-node.active .step-sub { color: #6d28d9; font-weight: 600; }

  .track-line {
    position: absolute;
    top: 13px;
    left: 4%;
    right: 4%;
    height: 2px;
    background: #cbd5e1;
    z-index: 1;
  }
</style>
</head>
<body>

  <!-- 1. Header -->
  <div class="header">
    <div class="title-group">
      <h1>
        Avalanche Admission Frontier Research
        <span class="tag">Actual Iterative Systems Engineering Workflow</span>
      </h1>
      <p>The Non-Linear Evolution: How Empirical Surprises, False Starts, and Forensic Audits Grounded the Consensus Digital Twin</p>
    </div>
    <div class="legend">
      <div class="legend-item"><div class="legend-line legend-fwd"></div> Forward Progression</div>
      <div class="legend-item"><div class="legend-line legend-loop"></div> Empirical Feedback Loop</div>
      <div class="legend-item"><div class="legend-line legend-amber"></div> Flawed Assumption / Overhaul</div>
      <div class="legend-item"><div class="legend-line legend-curr"></div> Current Milestone (Stage 4)</div>
    </div>
  </div>

  <!-- 2. Upper Feedback Banners (How findings challenged assumptions) -->
  <div class="feedback-banner">
    <div class="feedback-pill">
      <div class="icon">LOOP 1</div>
      <div class="text">
        <strong>Macro Population Explosion → August 2025 Contraction Autopsy:</strong><br>
        Early simulations blew up to 1,451 nodes due to Poisson(21.25/wk). Autopsy of the August 2025 collapse revealed 4 operators ran 538 nodes. Decoupled NodeID from operator and reset steady arrival to λ = 8.24/wk.
      </div>
    </div>
    <div class="feedback-pill">
      <div class="icon">LOOP 2</div>
      <div class="text">
        <strong>The 14-Day Fallacy → Provider Firewalls & Demand Gradient:</strong><br>
        Assumed 14d was the economic anchor (Hypothesis P). Historical data revealed 14–21d nodes capture only 3.9% capacity, and BENQI requires 6,000 AVAX. Inverted curve to strict convexity (p ≥ 1) under Hypothesis E.
      </div>
    </div>
    <div class="feedback-pill">
      <div class="icon">LOOP 3</div>
      <div class="text">
        <strong>Profile A Absorbing Trap → Forensic Audit Amber Verdict:</strong><br>
        Hardcoding zero delegation on solo stakers ignored that 20.6% historically transitioned to delegation upon renewal. Independent audit flagged this as a conservative distortion and required sensitivity sweeps.
      </div>
    </div>
  </div>

  <!-- 3. Main 6 Stage Columns -->
  <div class="stages-grid">

    <!-- Stage 0 -->
    <div class="stage-col s0">
      <div class="col-header">
        <div class="col-badge">Stage 0</div>
        <div class="col-title">Objectives & Scope</div>
      </div>
      <div class="col-body">
        <div class="card-box">
          <div class="card-label">Core Research Problem</div>
          <ul class="card-list">
            <li>Is a duration-dependent frontier <strong>S_min(d)</strong> defensible for Primary Network validators?</li>
            <li>Enforce over cycle <strong>D_cycle</strong> under Helicon ACP-236.</li>
          </ul>
        </div>
        <div class="card-box">
          <div class="card-label">Helicon Protocol Context</div>
          <ul class="card-list">
            <li><strong>ACP-236:</strong> Auto-renewing cycles</li>
            <li><strong>ACP-267:</strong> 90% uptime rule</li>
            <li><strong>ACP-273:</strong> 48h minimum duration</li>
            <li><strong>ACP-285:</strong> ARR yield schedule</li>
          </ul>
        </div>
        <div class="card-box">
          <div class="card-label">Candidate Family</div>
          <ul class="card-list">
            <li>Harmonic power family:</li>
            <li><strong>S_min(d) = S_floor + (S_short - S_floor)η(d)^p</strong></li>
            <li>Curvature restriction: <strong>p ≥ 1</strong></li>
          </ul>
        </div>
      </div>
      <div class="col-footer">
        <div class="f-title">Key Artifacts</div>
        <ul>
          <li>Technical Work Plan</li>
          <li>KPI Specification</li>
          <li>Epistemic Boundaries</li>
        </ul>
      </div>
    </div>

    <!-- Stage 1 -->
    <div class="stage-col s1">
      <div class="col-header">
        <div class="col-badge">Stage 1</div>
        <div class="col-title">Boundary Identification</div>
      </div>
      <div class="col-body">
        <div class="card-box">
          <div class="card-label">Canonical Ingestion</div>
          <ul class="card-list">
            <li><strong>7,635</strong> unique NodeIDs</li>
            <li><strong>3,504</strong> distinct operators</li>
            <li><strong>57,067</strong> completed staking periods</li>
            <li><strong>602</strong> live active nodes</li>
          </ul>
        </div>
        <div class="card-box">
          <div class="card-label">S_floor Bound: [500, 2,000]</div>
          <ul class="card-list">
            <li>Solo hardware break-even ($480–$1,440/yr cost).</li>
            <li>500 AVAX labeled stress-case lower bound at low prices.</li>
          </ul>
        </div>
        <div class="card-box">
          <div class="card-label">S_short Bound: [10k, 20k]</div>
          <ul class="card-list">
            <li>Anti-sybil swarm defense.</li>
            <li>Deters ephemeral 48h farming nodes by raising attack capital 5–10x.</li>
          </ul>
        </div>
      </div>
      <div class="col-footer">
        <div class="f-title">Key Artifacts</div>
        <ul>
          <li>Boundary Identification Memo</li>
          <li>Break-even Cost Models</li>
          <li>Anti-Sybil Capital Lower Bounds</li>
        </ul>
      </div>
    </div>

    <!-- Stage 2 -->
    <div class="stage-col s2">
      <div class="col-header">
        <div class="col-badge">Stage 2</div>
        <div class="col-title">Empirical Insights</div>
      </div>
      <div class="col-body">
        <div class="card-box">
          <div class="card-label">Capital-Duration Scaling</div>
          <ul class="card-list">
            <li><strong>Corr(log S, log d) ≈ +0.25</strong></li>
            <li>Small (≤2.5k): median 15d, 82.8% ≤ 35d (liquidity friction).</li>
            <li>Whale (>100k): mean 73d, P90 180d.</li>
          </ul>
        </div>
        <div class="card-box">
          <div class="card-label">Delegation Demand Gradient</div>
          <ul class="card-list">
            <li><strong>14–21d:</strong> 3.9% 4x cap (27% prob)</li>
            <li><strong>22–35d:</strong> 21.1% 4x cap (66% prob)</li>
            <li><strong>96–185d:</strong> 110.8% cap (72% prob)</li>
            <li><strong>186–365d:</strong> 221.0% cap (84% prob)</li>
          </ul>
        </div>
        <div class="card-box alert-amber">
          <div class="card-label">BENQI Provider Firewall</div>
          <ul class="card-list">
            <li>Open Pool (65%): <strong>S ≥ 6,000 AVAX</strong>, fee ≤ 2%. Excludes 2k nodes!</li>
            <li>Miles Pool (35%): S ≥ 2,000 conditioned on governance votes.</li>
          </ul>
        </div>
      </div>
      <div class="col-footer">
        <div class="f-title">Key Artifacts</div>
        <ul>
          <li>Renewal Panel Matrix</li>
          <li>Delegation Gradient Table</li>
          <li>Provider Underwriting Map</li>
        </ul>
      </div>
    </div>

    <!-- Stage 3 -->
    <div class="stage-col s3">
      <div class="col-header">
        <div class="col-badge">Stage 3</div>
        <div class="col-title">Mechanism Curvature</div>
      </div>
      <div class="col-body">
        <div class="card-box alert-amber">
          <div class="card-label">Hypothesis P Busted</div>
          <ul class="card-list">
            <li>14d protocol delegation rule is <strong>not</strong> an economic pivot.</li>
            <li>Protocol permission ≠ economic delegation received!</li>
          </ul>
        </div>
        <div class="card-box">
          <div class="card-label">The Mechanism Dilemma</div>
          <ul class="card-list">
            <li>High S_short penalizes solo stakers who cannot lock for 365d.</li>
            <li>Low S_floor enables whales to multiply multi-node seats.</li>
          </ul>
        </div>
        <div class="card-box">
          <div class="card-label">Convex Curvature (p ≥ 1)</div>
          <ul class="card-list">
            <li>Inverted to <strong>Hypothesis E:</strong></li>
            <li><strong>p ∈ [1.11, 1.49]</strong> lowers admission stake rapidly by 30–90d.</li>
            <li>Protects capital-constrained intermediate validators.</li>
          </ul>
        </div>
      </div>
      <div class="col-footer">
        <div class="f-title">Key Artifacts</div>
        <ul>
          <li>Pivot Curvature Memo</li>
          <li>Convex Inversion Proofs</li>
          <li>NanoAVAX Integer Spec</li>
        </ul>
      </div>
    </div>

    <!-- Stage 4 -->
    <div class="stage-col s4">
      <div class="col-header">
        <div class="col-badge">Stage 4 (CURRENT)</div>
        <div class="col-title">Digital Twin Simulation</div>
      </div>
      <div class="col-body">
        <div class="card-box">
          <div class="card-label">Macro Equilibrium Fixed</div>
          <ul class="card-list">
            <li>Arrival calibrated: <strong>λ = 8.24/wk</strong> (3.37 new ops, 4.87 replacements).</li>
            <li>Maintains <strong>598.8 nodes</strong> (S_N = 0.0127). Fixed 1,451 node explosion!</li>
          </ul>
        </div>
        <div class="card-box">
          <div class="card-label">Conditional Behavior Engine</div>
          <ul class="card-list">
            <li><strong>P(d_t+1 | d_t, S):</strong> Capital transitions</li>
            <li><strong>A_eff_del(d, S):</strong> Multi-layer access</li>
            <li>Yield scenarios: <strong>Y1, Y2, Y3</strong></li>
          </ul>
        </div>
        <div class="card-box alert-purple">
          <div class="card-label">Forensic Audit: AMBER</div>
          <ul class="card-list">
            <li>Caught: Profile A absorbing trap (20.6% empirical mobility).</li>
            <li>Caught: In-sample circularity in 48w replay (-1.6% error). Ready with bounds.</li>
          </ul>
        </div>
      </div>
      <div class="col-footer">
        <div class="f-title">Key Artifacts</div>
        <ul>
          <li>Digital Twin Python Suite</li>
          <li>Behavioral Revision Memo</li>
          <li>Independent Audit Memo</li>
        </ul>
      </div>
    </div>

    <!-- Stage 5 -->
    <div class="stage-col s5">
      <div class="col-header">
        <div class="col-badge">Stage 5 (NEXT)</div>
        <div class="col-title">Policy Recommendations</div>
      </div>
      <div class="col-body">
        <div class="card-box">
          <div class="card-label">Counterfactual Policy Sweeps</div>
          <ul class="card-list">
            <li>Sweep: <strong>S_floor ∈ [500, 2,000]</strong></li>
            <li>Sweep: <strong>S_short ∈ [10k, 20k]</strong></li>
            <li>Sweep: <strong>p ∈ [1.0, 1.5, 2.0]</strong></li>
            <li>Stress: AVAX at $25 and $15</li>
          </ul>
        </div>
        <div class="card-box">
          <div class="card-label">Consensus MOE Evaluation</div>
          <ul class="card-list">
            <li><strong>S_N:</strong> Validator set stability</li>
            <li><strong>T_N:</strong> System churn rate</li>
            <li><strong>HHI & C10:</strong> Operator concentration</li>
            <li><strong>Viability_A:</strong> Solo survival rate</li>
            <li><strong>H_cap:</strong> Peer-to-peer headroom</li>
          </ul>
        </div>
        <div class="card-box">
          <div class="card-label">Final Deliverable</div>
          <ul class="card-list">
            <li>Defensible parameter package for Avalanche Primary Network ACP.</li>
          </ul>
        </div>
      </div>
      <div class="col-footer">
        <div class="f-title">Target Artifacts</div>
        <ul>
          <li>PSUU Simulation Report</li>
          <li>Sensitivity Analysis</li>
          <li>Production ACP Draft</li>
        </ul>
      </div>
    </div>

  </div>

  <!-- 4. Real "False Starts, Red Flags & Pivots" Callout Cards -->
  <div class="pivot-banner">
    <div class="pivot-card red">
      <div class="pivot-badge">False Start 1: Macro Population Explosion (Stage 4A) <span>HALTED & REBUILT</span></div>
      <div class="pivot-desc">
        <strong>What went wrong:</strong> Conflating NodeIDs with new economic entrants generated Poisson(21.25/wk), causing simulated nodes to explode to 1,451. <strong>The Fix:</strong> Autopsy of the August 2025 contraction (-506 nodes) proved 4 farming operators ran 538 nodes of 2k AVAX. Decoupled NodeIDs from operators and calibrated arrival to 8.24/wk.
      </div>
    </div>
    <div class="pivot-card amber">
      <div class="pivot-badge">False Start 2: The 14-Day Pivot Fallacy (Stage 2–3) <span>INVERTED & FIXED</span></div>
      <div class="pivot-desc">
        <strong>What went wrong:</strong> Hypothesis P assumed 14d was the economic anchor because protocol allows delegation at 14d. <strong>The Fix:</strong> On-chain data revealed 14–21d nodes capture only 3.9% capacity, and BENQI requires 6,000 AVAX. Pivoted to Hypothesis E with endogenous curvature p ∈ [1.11, 1.49] to protect intermediate stakers.
      </div>
    </div>
    <div class="pivot-card purple">
      <div class="pivot-badge">False Start 3: Profile A Absorbing Trap (Stage 4B Audit) <span>AUDITED: AMBER</span></div>
      <div class="pivot-desc">
        <strong>What went wrong:</strong> Model hardcoded Profile A to 0 delegation permanently, ignoring that 20.6% of historical small zero-delegation validators transitioned to delegation upon renewal. <strong>The Fix:</strong> Independent forensic audit flagged this conservative distortion and mandated friction sensitivity sweeps.
      </div>
    </div>
  </div>

  <!-- 5. Bottom Timeline (The 9 Real Evolutionary Milestones) -->
  <div class="timeline-container">
    <div class="timeline-header">
      <h3>Chronological Research Trajectory (How We Reached Stage 4)</h3>
      <span>138 Unit Tests Passing • 56,465 Staking Periods Audited • Epistemically Bounded</span>
    </div>
    <div class="timeline-track">
      <div class="track-line"></div>

      <div class="step-node completed">
        <div class="step-bubble">1</div>
        <div class="step-label">Initial Scoping</div>
        <div class="step-sub">ACP matrix & questions</div>
      </div>

      <div class="step-node completed">
        <div class="step-bubble">2</div>
        <div class="step-label">Data Ingestion</div>
        <div class="step-sub">7.6k nodes, 57k periods</div>
      </div>

      <div class="step-node completed">
        <div class="step-bubble">3</div>
        <div class="step-label">Aug 2025 Autopsy</div>
        <div class="step-sub">4 farms = 538 nodes (λ=8.24)</div>
      </div>

      <div class="step-node completed">
        <div class="step-bubble">4</div>
        <div class="step-label">Stage 1 Bounds</div>
        <div class="step-sub">S_floor & S_short ranges</div>
      </div>

      <div class="step-node completed">
        <div class="step-bubble">5</div>
        <div class="step-label">14d Pivot Busted</div>
        <div class="step-sub">BENQI 6k & 3.9% gradient</div>
      </div>

      <div class="step-node completed">
        <div class="step-bubble">6</div>
        <div class="step-label">Curvature Inversion</div>
        <div class="step-sub">p ≥ 1 (Hypothesis E)</div>
      </div>

      <div class="step-node completed">
        <div class="step-bubble">7</div>
        <div class="step-label">Twin Rebuild</div>
        <div class="step-sub">Capital transitions P(d|S)</div>
      </div>

      <div class="step-node active">
        <div class="step-bubble">8</div>
        <div class="step-label">Forensic Audit</div>
        <div class="step-sub">AMBER Gate (CURRENT)</div>
      </div>

      <div class="step-node next">
        <div class="step-bubble">9</div>
        <div class="step-label">Policy Sweeps</div>
        <div class="step-sub">Y1, Y2, Y3 (NEXT)</div>
      </div>

    </div>
  </div>

</body>
</html>
"""

async def render():
    out_html = Path("research/plots/research_workflow_infographic.html")
    out_png_downloads = Path("/home/hash/Downloads/Iterative_Research_Workflow_Infographic_Revised.png")
    out_png_plots = Path("research/plots/Iterative_Research_Workflow_Infographic_Revised.png")
    out_png_docs = Path("docs/Iterative_Research_Workflow_Infographic_Revised.png")

    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(HTML_CONTENT, encoding="utf-8")
    print(f"Wrote HTML source to: {out_html}")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # High resolution viewport (1720x1180 with 2x DPR for ultra crisp typography)
        page = await browser.new_page(
            viewport={"width": 1720, "height": 1180},
            device_scale_factor=2,
        )
        await page.goto(f"file://{out_html.resolve()}")
        await page.wait_for_timeout(500)  # Ensure all styles and fonts settle

        # Render PNGs
        await page.screenshot(path=str(out_png_downloads), full_page=True)
        print(f"Rendered PNG to: {out_png_downloads}")

        await page.screenshot(path=str(out_png_plots), full_page=True)
        print(f"Rendered PNG to: {out_png_plots}")

        await page.screenshot(path=str(out_png_docs), full_page=True)
        print(f"Rendered PNG to: {out_png_docs}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(render())
