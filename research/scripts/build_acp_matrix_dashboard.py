#!/usr/bin/env python3
"""
Build interactive ACP Policy Matrix and Foundation Cryptoeconomics Dashboard.
Output: research/plots/acp_policy_matrix_dashboard.html
"""
import os
import shutil

OUTPUT_DIR = "/home/hash/Hub/Projects/avalanche-phase-ii-research/research/plots"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "acp_policy_matrix_dashboard.html")
BRAIN_ARTIFACT_DIR = "/home/hash/.gemini/antigravity-cli/brain/0e0d7bfb-f4a6-49f6-89fd-7f5ff88ccd8c/plots"

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Avalanche ACP Policy Matrix & Foundation Cryptoeconomics</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0d14;
            --bg-secondary: #121824;
            --bg-card: #182234;
            --bg-hover: #223048;
            --border-color: #273750;
            --border-highlight: #3b82f6;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-red: #e84142;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-amber: #f59e0b;
            --accent-purple: #8b5cf6;
            --accent-cyan: #06b6d4;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 30px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        header {
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 24px;
            margin-bottom: 32px;
        }

        .header-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 16px;
        }

        .title-area h1 {
            font-size: 28px;
            font-weight: 800;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .title-area h1 span.badge {
            font-size: 13px;
            font-weight: 600;
            background: rgba(232, 65, 66, 0.15);
            color: var(--accent-red);
            padding: 4px 10px;
            border-radius: 9999px;
            border: 1px solid rgba(232, 65, 66, 0.3);
        }

        .subtitle {
            font-size: 15px;
            color: var(--text-secondary);
            margin-top: 6px;
            max-width: 900px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-bottom: 36px;
        }

        .stat-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            position: relative;
            overflow: hidden;
        }

        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: var(--accent-blue);
        }

        .stat-card.red::before { background: var(--accent-red); }
        .stat-card.green::before { background: var(--accent-green); }
        .stat-card.amber::before { background: var(--accent-amber); }
        .stat-card.purple::before { background: var(--accent-purple); }

        .stat-label {
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
        }

        .stat-val {
            font-size: 26px;
            font-weight: 700;
            margin: 6px 0;
            font-family: 'JetBrains Mono', monospace;
        }

        .stat-target {
            font-size: 12px;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .section-title {
            font-size: 20px;
            font-weight: 700;
            margin: 36px 0 18px 0;
            display: flex;
            align-items: center;
            gap: 10px;
            border-left: 4px solid var(--accent-red);
            padding-left: 12px;
        }

        /* Foundation Paradigm Box */
        .doctrine-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }

        .doctrine-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 22px;
        }

        .doctrine-card h3 {
            font-size: 16px;
            font-weight: 700;
            color: var(--accent-cyan);
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .doctrine-card p {
            font-size: 13.5px;
            color: var(--text-secondary);
            margin-bottom: 12px;
            line-height: 1.5;
        }

        .doctrine-card ul {
            list-style: none;
            font-size: 13px;
        }

        .doctrine-card li {
            padding: 6px 0;
            border-top: 1px solid rgba(255,255,255,0.05);
            color: var(--text-primary);
        }

        .doctrine-card li strong {
            color: #38bdf8;
            font-weight: 600;
        }

        /* Filter Controls */
        .controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            background: var(--bg-secondary);
            padding: 14px 18px;
            border-radius: 10px;
            border: 1px solid var(--border-color);
            margin-bottom: 24px;
        }

        .filter-buttons {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .btn-filter {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 7px 14px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .btn-filter:hover, .btn-filter.active {
            background: var(--accent-blue);
            color: #fff;
            border-color: var(--accent-blue);
        }

        .search-box {
            position: relative;
            min-width: 260px;
        }

        .search-box input {
            width: 100%;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 13px;
            outline: none;
            transition: border 0.2s;
        }

        .search-box input:focus {
            border-color: var(--border-highlight);
        }

        /* ACP Table */
        .table-wrap {
            overflow-x: auto;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            background: var(--bg-secondary);
            margin-bottom: 40px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 13.5px;
        }

        th {
            background: var(--bg-card);
            color: var(--text-muted);
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding: 14px 16px;
            border-bottom: 1px solid var(--border-color);
        }

        td {
            padding: 16px;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            vertical-align: top;
        }

        tr:hover td {
            background: var(--bg-hover);
        }

        .acp-badge {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 13px;
            color: #fff;
            background: rgba(59, 130, 246, 0.15);
            border: 1px solid rgba(59, 130, 246, 0.3);
            padding: 4px 8px;
            border-radius: 6px;
            display: inline-block;
            white-space: nowrap;
        }

        .status-badge {
            font-size: 11px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 9999px;
            text-transform: uppercase;
            display: inline-block;
            white-space: nowrap;
        }

        .status-active { background: rgba(16, 185, 129, 0.15); color: var(--accent-green); border: 1px solid rgba(16, 185, 129, 0.3); }
        .status-merged { background: rgba(59, 130, 246, 0.15); color: var(--accent-blue); border: 1px solid rgba(59, 130, 246, 0.3); }
        .status-proposed { background: rgba(245, 158, 11, 0.15); color: var(--accent-amber); border: 1px solid rgba(245, 158, 11, 0.3); }
        .status-historical { background: rgba(100, 116, 139, 0.15); color: var(--text-muted); border: 1px solid rgba(100, 116, 139, 0.3); }

        .category-tag {
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 4px;
            display: block;
        }

        .mechanism-text {
            color: var(--text-primary);
            font-weight: 500;
            margin-bottom: 4px;
        }

        .impact-box {
            font-size: 12.5px;
            color: var(--text-secondary);
            line-height: 1.45;
            background: rgba(0, 0, 0, 0.2);
            padding: 8px 12px;
            border-radius: 6px;
            border-left: 3px solid var(--accent-amber);
            margin-top: 6px;
        }

        .impact-box.danger { border-left-color: var(--accent-red); }
        .impact-box.success { border-left-color: var(--accent-green); }
        .impact-box.info { border-left-color: var(--accent-blue); }

        /* Cross-Mechanism Deep Dive */
        .callout-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }

        .callout-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 22px;
            position: relative;
        }

        .callout-card h4 {
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .callout-card.red h4 { color: var(--accent-red); }
        .callout-card.amber h4 { color: var(--accent-amber); }
        .callout-card.purple h4 { color: var(--accent-purple); }

        .callout-card p {
            font-size: 13.5px;
            color: var(--text-secondary);
            line-height: 1.5;
            margin-bottom: 12px;
        }

        .code-snippet {
            font-family: 'JetBrains Mono', monospace;
            background: #06090e;
            padding: 10px 14px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            font-size: 12.5px;
            color: #38bdf8;
            overflow-x: auto;
        }

        footer {
            border-top: 1px solid var(--border-color);
            padding-top: 24px;
            font-size: 12.5px;
            color: var(--text-muted);
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
        }
    </style>
</head>
<body>

<div class="container">
    <header>
        <div class="header-top">
            <div class="title-area">
                <h1>Avalanche Policy Matrix & Foundation Cryptoeconomics <span class="badge">Canonical Synthesis</span></h1>
                <div class="subtitle">
                    Systemic evaluation of the 36-ACP portfolio, Foundation macroeconomic doctrine (Matias Antonio & Dr. Eric Lu), and equilibrium mechanism design for the post-Helicon Primary Network.
                </div>
            </div>
            <div style="text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-muted);">
                Revision: Post-Granite / Helicon<br>
                Source: BCRG Systems Engineering
            </div>
        </div>
    </header>

    <!-- Key Macro Indicators -->
    <div class="stats-grid">
        <div class="stat-card amber">
            <div class="stat-label">Staking Ratio (&sigma;)</div>
            <div class="stat-val" style="color: var(--accent-amber);">35.19%</div>
            <div class="stat-target">Target Corridor: <strong>50.0% – 60.0%</strong> (Erosion from 64% Genesis)</div>
        </div>
        <div class="stat-card purple">
            <div class="stat-label">Stake-Weighted Duration</div>
            <div class="stat-val" style="color: var(--accent-purple);">3.97 wks</div>
            <div class="stat-target">Target Horizon: <strong>&ge; 16.9 wks</strong> (Dr. Eric Lu Benchmark)</div>
        </div>
        <div class="stat-card green">
            <div class="stat-label">Active Validator Set</div>
            <div class="stat-val" style="color: var(--accent-green);">604 Nodes</div>
            <div class="stat-target">Decentralization Floor: <strong>&ge; 600 Nodes</strong></div>
        </div>
        <div class="stat-card red">
            <div class="stat-label">Median Validator Self-Stake</div>
            <div class="stat-val" style="color: var(--accent-red);">14,585 AVAX</div>
            <div class="stat-target">Granite Shift: <strong>41% Nodes 100% Fee</strong> (Subnet Decoupled)</div>
        </div>
    </div>

    <!-- Foundation Cryptoeconomic Doctrine -->
    <div class="section-title">Foundation Cryptoeconomic Doctrine: "From Static Constants to Dynamic Variables"</div>
    <div class="doctrine-container">
        <div class="doctrine-card">
            <h3>1. Measure: Gross Chain Product (GCP)</h3>
            <p>Traditional metrics like TVL and Market Cap reflect idle speculation. Dr. Eric Lu introduced <strong>GCP</strong> using the national income framework to isolate real output from price volatility.</p>
            <ul>
                <li><strong>Onchain Value Added:</strong> Protocol Profit + Gas Fees Generated.</li>
                <li><strong>Fisher Chain-Weighting:</strong> Aggregates ~700 tokens to separate real activity from dollar price swings.</li>
                <li><strong>Empirical Discovery:</strong> Between Jan 2025 and Mar 2026, while nominal output fell 60%, <em>Real GCP dropped only 25%</em>.</li>
            </ul>
        </div>
        <div class="doctrine-card">
            <h3>2. Capture: Expanding Protocol Revenue</h3>
            <p>Matias Antonio established that no network funds its security indefinitely without real revenue. The finite 720M AVAX emission budget is a decaying bridge.</p>
            <ul>
                <li><strong>Primary Network Gas Burns:</strong> Deliberate management of the fee floor via ACP-283 validator voting.</li>
                <li><strong>Continuous L1 Revenue (ACP-77):</strong> Sovereign L1s burn AVAX per validator/second, transforming Subnets into revenue drivers.</li>
                <li><strong>P-Chain Dynamic Base Fees (ACP-103):</strong> Market pricing for validator churn and state creation.</li>
            </ul>
        </div>
        <div class="doctrine-card">
            <h3>3. Distribute: Sustainable Security Subsidy</h3>
            <p>Security is a continuous cash bill an attacker must pay. The economic weight behind AVAX <em>is</em> the network security.</p>
            <ul>
                <li><strong>Annualized APY Thinking:</strong> Validators optimize for annualized yield, not period total (MRS &approx; 0.82 pp/yr per week).</li>
                <li><strong>Yield Gradient (ACP-285):</strong> Steepens the reward curve to nudge duration out by ~2 months while cutting inflation by ~20%.</li>
                <li><strong>Admission Frontier S<sub>min</sub>(d):</strong> Mathematical Sybil shield coupling short liquidity with long commitment.</li>
            </ul>
        </div>
    </div>

    <!-- Critical Interaction Deep Dives -->
    <div class="section-title">Critical Cross-Mechanism Friction Points & Systemic Risks</div>
    <div class="callout-grid">
        <div class="callout-card red">
            <h4>The Decoupled Sybil Trap (ACP-49 &times; ACP-273)</h4>
            <p>If ACP-49 (500 AVAX floor) and ACP-273 (48h duration) are enacted independently without duration conditioning, the required capital commitment collapses from 28,000 AVAX-days to 1,000 AVAX-days (<strong>96.4% collapse in skin-in-the-game</strong>).</p>
            <div class="code-snippet">S_min(d) = S_floor + (S_short - S_floor) * (d_min / d)^p</div>
            <p style="margin-top: 10px; font-size: 12px; color: var(--text-muted);">The Continuous Harmonic Frontier ensures that 48h validators must post &ge; 14k–18k AVAX, preserving Sybil resilience.</p>
        </div>

        <div class="callout-card amber">
            <h4>The 14-Day Delegator Firewall (PlatformVM Rule)</h4>
            <p>ACP-273 lowered validator duration to 48 hours, but delegator minimum remains <strong>hardcoded to 14 days (336h)</strong>. PlatformVM rules dictate delegator end times must not exceed validator end times.</p>
            <div class="code-snippet">delegator.duration &gt;= 14d  AND  delegator.endTime &lt;= validator.endTime</div>
            <p style="margin-top: 10px; font-size: 12px; color: var(--text-muted);"><strong>Consequence:</strong> Any validator staking for &lt;14 days cannot receive delegations. LSTs (BENQI: 18.1M AVAX) and commercial pools are locked out of 48h stints.</p>
        </div>

        <div class="callout-card purple">
            <h4>The Granite Shift: Post-ACP-77 Structural Decoupling</h4>
            <p>ACP-77 (Etna) removed the 2,000 AVAX Primary Network bond for Subnets. Over 200 Subnet nodes exited, dropping the macro staking ratio to 35.19% and lifting median self-stake to 14.5k AVAX.</p>
            <div class="code-snippet">41% of 2026 new entrants set fee = 100% (Closed Institutional Float)</div>
            <p style="margin-top: 10px; font-size: 12px; color: var(--text-muted);">New validators are proprietary institutional treasuries running private infrastructure, not public pools competing for delegators.</p>
        </div>
    </div>

    <!-- ACP Portfolio Table -->
    <div class="section-title">The Complete ACP Policy Matrix</div>
    
    <div class="controls">
        <div class="filter-buttons">
            <button class="btn-filter active" onclick="filterTable('all')">All Proposals</button>
            <button class="btn-filter" onclick="filterTable('staking')">Primary Staking & Yield</button>
            <button class="btn-filter" onclick="filterTable('l1')">L1s & Subnet Scaling</button>
            <button class="btn-filter" onclick="filterTable('fee')">Fee Markets & Burns</button>
            <button class="btn-filter" onclick="filterTable('interop')">Interop & Cryptography</button>
        </div>
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Search ACP number, title, mechanism..." onkeyup="searchTable()">
        </div>
    </div>

    <div class="table-wrap">
        <table id="acpTable">
            <thead>
                <tr>
                    <th style="width: 110px;">ACP</th>
                    <th style="width: 130px;">Status / Domain</th>
                    <th style="width: 280px;">Core Mechanism</th>
                    <th style="width: 260px;">Primary Goal</th>
                    <th>Network Health Impact & Systemic Risk</th>
                </tr>
            </thead>
            <tbody>
                <!-- Staking Tier -->
                <tr data-category="staking">
                    <td><span class="acp-badge">ACP-273</span></td>
                    <td>
                        <span class="status-badge status-merged">Merged (Helicon)</span>
                        <span class="category-tag">Staking Duration</span>
                    </td>
                    <td><div class="mechanism-text">Lowers minimum validator self-stake duration from 14 days (336h) to 48 hours.</div>Delegator minimum remains 14 days.</td>
                    <td>Institutional staker liquidity, market maker agility, and ETF 24-hour cash redemption compliance.</td>
                    <td>
                        <div class="impact-box danger">
                            <strong>State Churn & Churn Risk:</strong> If untamed, security capital rotates daily. <strong>Delegator Firewall:</strong> Blocks all delegation pools (BENQI) from &lt;14d stints.
                        </div>
                    </td>
                </tr>

                <tr data-category="staking">
                    <td><span class="acp-badge">ACP-285</span></td>
                    <td>
                        <span class="status-badge status-proposed">Proposed</span>
                        <span class="category-tag">Reward Curve</span>
                    </td>
                    <td><div class="mechanism-text">Asymmetric reduction of reward floor parameter r<sub>min</sub> from 10.0% to 7.5%.</div>r<sub>max</sub> stays 12.0%. Phased over 30 days.</td>
                    <td>Counterbalance ACP-273 short-term churn; slow down 720M emission exhaustion by 20%; double duration premium.</td>
                    <td>
                        <div class="impact-box success">
                            <strong>Duration Extension:</strong> Exploits validator APY-thinking to extend macro duration by ~2 months (&rarr; 16.9w). Cuts annual inflation by 0.5%–1.0%.
                        </div>
                    </td>
                </tr>

                <tr data-category="staking">
                    <td><span class="acp-badge">ACP-236</span></td>
                    <td>
                        <span class="status-badge status-proposed">Proposed</span>
                        <span class="category-tag">Staker Lifecycle</span>
                    </td>
                    <td><div class="mechanism-text">In-protocol auto-renewal for validators and delegators upon period expiry.</div>Allows compounding accrued rewards if uptime &ge; threshold.</td>
                    <td>Eliminate operational friction of manual restaking; smooth P-Chain transaction volume.</td>
                    <td>
                        <div class="impact-box danger">
                            <strong>Runaway 48h Churn Loop:</strong> Rational validators pair ACP-273 + ACP-236 to achieve instant liquidity with continuous compounding unless penalized by ACP-285.
                        </div>
                    </td>
                </tr>

                <tr data-category="staking">
                    <td><span class="acp-badge">ACP-267</span></td>
                    <td>
                        <span class="status-badge status-merged">Merged (Helicon)</span>
                        <span class="category-tag">Uptime Verification</span>
                    </td>
                    <td><div class="mechanism-text">Raises minimum uptime required for reward payout from 80% to 90%.</div>Measured across validator stint.</td>
                    <td>Enforce high availability; eliminate flapping nodes; optimize Snow consensus DAG finality.</td>
                    <td>
                        <div class="impact-box danger">
                            <strong>Centralization Threat:</strong> 40 of 604 active nodes (6.6%) fail the 90% floor today. Increases penalty severity on home stakers with residential internet.
                        </div>
                    </td>
                </tr>

                <tr data-category="staking">
                    <td><span class="acp-badge">ACP-247</span></td>
                    <td>
                        <span class="status-badge status-proposed">Implementable</span>
                        <span class="category-tag">Delegation Cap</span>
                    </td>
                    <td><div class="mechanism-text">Expands delegation multiplier from 4x to 24x self-stake.</div>Retains 3M AVAX total validator weight ceiling.</td>
                    <td>Improve economic viability of small nodes by multiplying potential delegation fee income by up to 6x.</td>
                    <td>
                        <div class="impact-box danger">
                            <strong>Consensus Dilution:</strong> An operator controls 25x weight with only 4% own capital at risk. 52.8% of nodes have 0 delegations today, so capacity is not the true bottleneck.
                        </div>
                    </td>
                </tr>

                <tr data-category="staking">
                    <td><span class="acp-badge">ACP-49</span></td>
                    <td>
                        <span class="status-badge status-historical">Historical</span>
                        <span class="category-tag">Entry Threshold</span>
                    </td>
                    <td><div class="mechanism-text">Lowers minimum validator self-stake from 2,000 AVAX to 500 AVAX.</div>Flat threshold proposal.</td>
                    <td>Democratize node validation; lower entry barrier for home operators and developing regions.</td>
                    <td>
                        <div class="impact-box danger">
                            <strong>The Decoupled Trap:</strong> 500 AVAX &times; 2d = 1,000 AVAX-days (96.4% collapse in skin-in-the-game). Must be conditioned via the BCRG Admission Frontier.
                        </div>
                    </td>
                </tr>

                <!-- L1 & Subnet Scaling Tier -->
                <tr data-category="l1">
                    <td><span class="acp-badge">ACP-77</span></td>
                    <td>
                        <span class="status-badge status-active">Activated (Etna)</span>
                        <span class="category-tag">Avalanche L1s</span>
                    </td>
                    <td><div class="mechanism-text">Decoupled Subnet validation from Primary Network staking.</div>Replaced 2,000 AVAX lock with continuous P-Chain fee burn per validator/sec.</td>
                    <td>Radically reduce capital cost of launching sovereign application chains; turn Subnets into continuous token burners.</td>
                    <td>
                        <div class="impact-box info">
                            <strong>Primary Float Shock:</strong> Led to the Granite staking ratio drop to 35.19% as Subnet nodes vacated the Primary Network, shifting median stake to 14.5k AVAX.
                        </div>
                    </td>
                </tr>

                <tr data-category="l1">
                    <td><span class="acp-badge">ACP-99</span></td>
                    <td>
                        <span class="status-badge status-proposed">Implementable</span>
                        <span class="category-tag">Validator Management</span>
                    </td>
                    <td><div class="mechanism-text">Standardizes EVM Solidity contracts on P-Chain for managing L1 validator sets.</div>Supports onchain staking and slashing logic.</td>
                    <td>Enable programmable L1 validator governance, cross-chain staking pools, and dynamic membership.</td>
                    <td>
                        <div class="impact-box info">
                            Transitions validator management from manual coordination to automated smart contracts, increasing churn velocity.
                        </div>
                    </td>
                </tr>

                <tr data-category="l1">
                    <td><span class="acp-badge">ACP-191</span></td>
                    <td>
                        <span class="status-badge status-proposed">Proposed</span>
                        <span class="category-tag">L1 Creation</span>
                    </td>
                    <td><div class="mechanism-text">Streamlines transaction sequence for instantiating and registering sovereign L1s.</div>Reduces multi-step P-Chain setup.</td>
                    <td>Frictionless enterprise onboarding for new institutional blockchain deployments.</td>
                    <td>
                        <div class="impact-box success">
                            Directly accelerates the velocity of L1 creation, driving cumulative ACP-77 continuous burn demand.
                        </div>
                    </td>
                </tr>

                <tr data-category="l1">
                    <td><span class="acp-badge">ACP-224</span></td>
                    <td>
                        <span class="status-badge status-proposed">Implementable</span>
                        <span class="category-tag">L1 Fee Markets</span>
                    </td>
                    <td><div class="mechanism-text">Extends dynamic gas limits and fee managers to Subnet-EVM execution engines.</div>Standardizes L1 gas algorithms.</td>
                    <td>Bring modern algorithmic fee discovery to all Avalanche sovereign L1s.</td>
                    <td>
                        <div class="impact-box success">
                            Prevents transaction spam on L1s while isolating L1 congestion from impacting the Primary Network.
                        </div>
                    </td>
                </tr>

                <tr data-category="l1">
                    <td><span class="acp-badge">ACP-256</span></td>
                    <td>
                        <span class="status-badge status-active">Active Spec</span>
                        <span class="category-tag">Hardware Standards</span>
                    </td>
                    <td><div class="mechanism-text">Updates official recommended specs for Primary Network validator hardware.</div>Higher CPU, RAM, NVMe IOPS.</td>
                    <td>Ensure node infrastructure supports high-throughput continuous EVM execution and state growth.</td>
                    <td>
                        <div class="impact-box danger">
                            <strong>Operator Cost Drag:</strong> Pushes node running costs above $150–$250/mo, deepening retail operator reliance on delegations to reach break-even.
                        </div>
                    </td>
                </tr>

                <!-- Fee Markets & Burn Tier -->
                <tr data-category="fee">
                    <td><span class="acp-badge">ACP-283</span></td>
                    <td>
                        <span class="status-badge status-merged">Merged (Helicon)</span>
                        <span class="category-tag">Dynamic Gas Floor</span>
                    </td>
                    <td><div class="mechanism-text">Makes C-Chain minimum base fee adjustable via validator preference voting.</div>Replaces hardcoded constant with dynamic voting.</td>
                    <td>Deliberate management of token supply burn; prevent blockspace compute from clearing at near-zero.</td>
                    <td>
                        <div class="impact-box success">
                            <strong>Burn Accrual:</strong> Provides a tool to sustainably capture economic activity. Risk: setting floor too high drives volume to competing L1/L2s.
                        </div>
                    </td>
                </tr>

                <tr data-category="fee">
                    <td><span class="acp-badge">ACP-103</span></td>
                    <td>
                        <span class="status-badge status-proposed">Implementable</span>
                        <span class="category-tag">P-Chain Fees</span>
                    </td>
                    <td><div class="mechanism-text">Applies EIP-1559 style dynamic base fees to P-Chain staking transactions.</div>Market-based pricing for state changes.</td>
                    <td>Prevent P-Chain DDoS spam and state explosion during high-frequency validator churn.</td>
                    <td>
                        <div class="impact-box success">
                            <strong>Essential Defense:</strong> Absolute prerequisite for safe ACP-273 operation, ensuring 48h rotating stakers pay market-clearing fees.
                        </div>
                    </td>
                </tr>

                <tr data-category="fee">
                    <td><span class="acp-badge">ACP-176</span></td>
                    <td>
                        <span class="status-badge status-active">Activated (Durango)</span>
                        <span class="category-tag">Gas Target Voting</span>
                    </td>
                    <td><div class="mechanism-text">Enables validator preference voting on C-Chain gas targets.</div>Dynamically scales block capacity with demand.</td>
                    <td>Maximize transaction throughput while preventing consensus propagation latency and node desync.</td>
                    <td>
                        <div class="impact-box info">
                            Successfully increased C-Chain capacity, but depressed average fee levels, accelerating the drop in transaction burn.
                        </div>
                    </td>
                </tr>

                <tr data-category="fee">
                    <td><span class="acp-badge">ACP-226</span></td>
                    <td>
                        <span class="status-badge status-merged">Merged</span>
                        <span class="category-tag">Block Time Tuning</span>
                    </td>
                    <td><div class="mechanism-text">Allows validators to tune minimum inter-block delay (100ms – 2000ms) via voting.</div>Dynamic block cadence.</td>
                    <td>Eliminate empty block waste, reduce gossip network bandwidth overhead, and optimize latency.</td>
                    <td>
                        <div class="impact-box success">
                            Significantly reduces bandwidth consumption for global validator nodes.
                        </div>
                    </td>
                </tr>

                <tr data-category="fee">
                    <td><span class="acp-badge">ACP-194</span></td>
                    <td>
                        <span class="status-badge status-proposed">Implementable</span>
                        <span class="category-tag">Continuous Exec</span>
                    </td>
                    <td><div class="mechanism-text">Decouples EVM state execution from block building and consensus propagation.</div>Pipelined consensus engine.</td>
                    <td>Drastically accelerate transaction finality and execution throughput on C-Chain.</td>
                    <td>
                        <div class="impact-box success">
                            Separates execution hardware bottlenecks from consensus voting, improving Snow responsiveness.
                        </div>
                    </td>
                </tr>

                <!-- Interop & Crypto Tier -->
                <tr data-category="interop">
                    <td><span class="acp-badge">ACP-30</span></td>
                    <td>
                        <span class="status-badge status-active">Activated</span>
                        <span class="category-tag">Warp Messaging</span>
                    </td>
                    <td><div class="mechanism-text">Integrates Avalanche Warp Messaging (AWM) primitives directly into the EVM.</div>Native cross-subnet calls.</td>
                    <td>Bridge-less native cross-chain asset transfers and state verification across the entire ecosystem.</td>
                    <td>
                        <div class="impact-box success">
                            Eliminates multi-billion dollar bridge exploit vectors; establishes Avalanche cluster interoperability.
                        </div>
                    </td>
                </tr>

                <tr data-category="interop">
                    <td><span class="acp-badge">ACP-118</span></td>
                    <td>
                        <span class="status-badge status-active">Activated</span>
                        <span class="category-tag">Warp Signatures</span>
                    </td>
                    <td><div class="mechanism-text">Standardizes BLS aggregate signature verification interface for cross-chain messages.</div>Canonical encoding spec.</td>
                    <td>Interoperability security standard for seamless multi-L1 composition.</td>
                    <td>
                        <div class="impact-box info">
                            Foundational cryptographic standard underpinning the Avalanche multi-chain cluster.
                        </div>
                    </td>
                </tr>

                <tr data-category="interop">
                    <td><span class="acp-badge">ACP-204</span></td>
                    <td>
                        <span class="status-badge status-proposed">Proposed</span>
                        <span class="category-tag">secp256r1 Curve</span>
                    </td>
                    <td><div class="mechanism-text">Adds EVM precompile for verifying secp256r1 signatures.</div>Hardware secure enclave support.</td>
                    <td>Enable Apple FaceID / TouchID and Android Passkey authentication for web3 wallets.</td>
                    <td>
                        <div class="impact-box success">
                            Major catalyst for mainstream retail and consumer application adoption.
                        </div>
                    </td>
                </tr>

                <tr data-category="interop">
                    <td><span class="acp-badge">ACP-209</span></td>
                    <td>
                        <span class="status-badge status-proposed">Proposed</span>
                        <span class="category-tag">Account Abstraction</span>
                    </td>
                    <td><div class="mechanism-text">EIP-7702 style temporary code execution for Externally Owned Accounts (EOAs).</div>Smart account superpowers.</td>
                    <td>Allow standard wallets to batch transactions, sponsor gas, and delegate execution without contract migration.</td>
                    <td>
                        <div class="impact-box success">
                            Dramatically simplifies user experience for DeFi, gaming, and payments.
                        </div>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Governance Policy Alignment Architecture -->
    <div class="section-title">Tinbergen Policy Alignment: 1 Instrument Per Macro Target</div>
    <div class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th>Macro Strategic Target</th>
                    <th>Target Metric</th>
                    <th>Primary Policy Instrument</th>
                    <th>Operational Mechanism</th>
                    <th>Coordinated ACPs</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>1. Sybil Resilience & Churn Control</strong></td>
                    <td>Skin-in-the-Game &ge; 28k AVAX-d</td>
                    <td>Admission Frontier S<sub>min</sub>(d)</td>
                    <td>Hyperbolic capital curve demanding &ge; 18k AVAX at 48h</td>
                    <td>ACP-273 &times; ACP-49</td>
                </tr>
                <tr>
                    <td><strong>2. Macro Security Duration</strong></td>
                    <td>Duration &ge; 16.9 weeks</td>
                    <td>ACP-285 Yield Steepening</td>
                    <td>Asymmetric floor reduction (r<sub>min</sub> &rarr; 7.5%)</td>
                    <td>ACP-285</td>
                </tr>
                <tr>
                    <td><strong>3. Institutional Liquidity & Products</strong></td>
                    <td>Fast ETF Redemptions</td>
                    <td>ACP-273 48h Window</td>
                    <td>Restricted to proprietary capital via Delegator Firewall</td>
                    <td>ACP-273</td>
                </tr>
                <tr>
                    <td><strong>4. Transaction Burn Accrual</strong></td>
                    <td>Permanent Supply Deflation</td>
                    <td>ACP-283 Gas Price Voting</td>
                    <td>Validator governance of minimum base fee floor</td>
                    <td>ACP-283 &times; ACP-77</td>
                </tr>
                <tr>
                    <td><strong>5. PlatformVM DoS Mitigation</strong></td>
                    <td>Stable P-Chain Throughput</td>
                    <td>ACP-103 Dynamic P-Chain Fees</td>
                    <td>EIP-1559 multidimensional base fees for staker txs</td>
                    <td>ACP-103</td>
                </tr>
                <tr>
                    <td><strong>6. Broad Decentralized Entry</strong></td>
                    <td>&ge; 600 Independent Nodes</td>
                    <td>Asymptotic Stake Floor (500 AVAX)</td>
                    <td>Accessible to community stakers committing for 1 year</td>
                    <td>ACP-49 Floor via Frontier</td>
                </tr>
            </tbody>
        </table>
    </div>

    <footer>
        <div>Avalanche Foundation Economic Research Alignment Matrix &bull; BCRG Milestone 2 Report</div>
        <div>Generated for Antigravity Session 0e0d7bfb-f4a6-49f6-89fd-7f5ff88ccd8c</div>
    </footer>
</div>

<script>
    function filterTable(category) {
        const buttons = document.querySelectorAll('.btn-filter');
        buttons.forEach(btn => btn.classList.remove('active'));
        event.target.classList.add('active');

        const rows = document.querySelectorAll('#acpTable tbody tr');
        rows.forEach(row => {
            if (category === 'all' || row.getAttribute('data-category') === category) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }

    function searchTable() {
        const input = document.getElementById('searchInput');
        const filter = input.value.toLowerCase();
        const rows = document.querySelectorAll('#acpTable tbody tr');

        rows.forEach(row => {
            const text = row.innerText.toLowerCase();
            if (text.includes(filter)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }
</script>

</body>
</html>
"""

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(BRAIN_ARTIFACT_DIR, exist_ok=True)
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT)
    print(f"Generated dashboard: {OUTPUT_FILE}")
    
    # Mirror to brain artifact directory
    brain_file = os.path.join(BRAIN_ARTIFACT_DIR, "acp_policy_matrix_dashboard.html")
    shutil.copy(OUTPUT_FILE, brain_file)
    print(f"Mirrored to brain artifacts: {brain_file}")

if __name__ == "__main__":
    main()
