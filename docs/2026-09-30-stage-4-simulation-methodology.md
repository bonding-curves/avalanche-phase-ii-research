# Stage 4 Simulation Methodology: Empirical Validator Digital Twin & PSuU Architecture

**Repository:** `avalanche-phase-ii-research`  
**Subsystem:** Avalanche Primary Network Consensus & PlatformVM  
**Document Type:** Systems Engineering & Simulation Methodology Specification  
**Source Work Plan:** `docs/2026-09-30-admission-frontier-technical-work-plan.md`  
**Data Foundations:** `derived.node-table` (7,644 historical nodes), `derived.staking-periods`, Data API validator captures  
**Status:** Methodological Baseline (September 30, 2026)  

---

## 1. Objective & Empirical Foundation

Stage 4 of the Duration-Dependent PoS Admission Frontier research evaluates how candidate admission frontiers $S_{\min}(d)$ perform under uncertainty when replayed across empirically grounded validator populations.

Rather than treating validator behavior as an uncalibrated theoretical abstraction, Stage 4 is grounded directly in the **full historical Primary Network validator dataset**:

$$\boxed{\text{Historical Validator Data}} \longrightarrow \boxed{\text{Empirical Profiles \& Population}} \longrightarrow \boxed{\text{Replay Baseline Behavior}} \longrightarrow \boxed{\text{Introduce } S_{\min}(d)} \longrightarrow \boxed{\text{Sweep Yield Scenarios (PSuU)}}$$

### Core Methodological Invariants
1. **Grounded in Observed History:** We observe the complete historical record of validator entry, exit, renewal behavior, staking duration choices, self-stake magnitudes, delegation capacity fill, active tenure, streak continuity, and stake distribution. Validator behavior is not unknown overall.
2. **Isolate the True Identification Limitation:** The primary unobserved behavioral relationship is **how sensitive validators are to yield/reward changes**. Historically, the protocol staking yield was effectively stable, providing insufficient cross-sectional or longitudinal variation to identify a causal yield-response function. ACP-285 / Helicon creates the first duration-dependent yield variation.
3. **Bounded Digital Twin & PSuU:** We structure a low-dimensional Generalized Dynamical System (GDS) in radCAD, model unresolved yield sensitivity across bounded behavioral scenarios, and execute Parameter Selection under Uncertainty (PSuU) across policy and macroeconomic grids.
4. **Neutral Stress Testing:** The digital twin is designed to evaluate both favorable and unfavorable outcomes without assuming in advance that the mechanism will stabilize the validator set.

---

## 2. Historical Validator Population & Profile Construction

### 2.1 Population Replay from `derived.node-table`
The digital twin's baseline validator population is reconstructed directly from `derived.node-table` (7,644 historical Primary Network validator nodes) and `derived.staking-periods`:
- **Observed Tenure & Streaks:** Captures empirical distributions of validator span (`span_days`), active tenure (`tenure_days`), gap frequencies (`gap_days`, `gap_count`), and continuous validation streaks (`streaks`, `current_streak_days`).
- **Observed Staking Sizing:** Reflects the empirical distribution of minimum, maximum, and latest self-stake (`min_stake_avax`, `max_stake_avax`, `latest_stake_avax`).
- **Observed Delegation Utilization:** Reconstructs historical delegator counts (`delegator_addresses`), cumulative delegated stake (`delegated_avax`), and delegation fill ratios (median 74% among active nodes with delegation).
- **Observed Duration Choices:** Preserves empirical stint duration distributions and calendar milestone clustering (14d, 30d, 60d, 90d, 180d, 365d).

### 2.2 Profile Generation from Observed Heterogeneity
Representative validator agent classes are generated from the empirical distributions rather than invented archetypes:

- **Profile A (Capital-Constrained Solo Validators):**
  - *Data Mapping:* Nodes operating with self-stake near the legacy minimum ($S_i \approx 2{,}000$ AVAX), zero delegation ($D_i = 0$), and absorbing 100% of server costs.
  - *Behavioral Driver:* High sensitivity to $S_{\mathrm{floor}}$ and cash-flow break-even:
    $$\text{Net\_Operating\_Margin}_i(t) = S_i \cdot R_{\mathrm{macro}}(t) \cdot P_{\mathrm{AVAX}}(t) - C_{\mathrm{infra}, i}$$
- **Profile B (Commercial Delegator-Facing Validators):**
  - *Data Mapping:* Nodes with substantial self-stake ($S_i \gg 2{,}000$ AVAX), high delegation fill, and active fee commission revenue ($f_{\mathrm{del}} \in [2\%, 10\%]$).
  - *Behavioral Driver:* Sensitive to the delegation eligibility boundary ($d_i \ge d_{\mathrm{del,\min}}$) and duration reward differentials.
- **Profile C (Multi-Purpose Ecosystem Validators):**
  - *Data Mapping:* Institutional and foundation-backed nodes exhibiting continuous streaks across hard fork regimes, co-funding Subnet/L1 infrastructure, or operating RPC endpoints.
  - *Behavioral Driver:* Participation is governed by ecosystem presence and operational uptime rather than standalone Primary Network staking margins.

---

## 3. Known vs. Unknown Behavioral Dimensions (Three-Tier Identification)

To maintain strict epistemic discipline, validator behavioral dimensions are partitioned into three explicit tiers:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ TIER 1: OBSERVED BEHAVIOR (Estimated / Replayed from History)           │
│ - Entry timing, cadence, and historical arrival volume                 │
│ - Baseline stint duration choices & calendar clustering (14d-365d)     │
│ - Exit hazards and streak persistence across tenures                   │
│ - Historical self-stake sizing and delegation fill ratios              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ TIER 2: PARTIALLY IDENTIFIED BEHAVIOR                                  │
│ - Duration switching under shifting capital constraints                │
│ - Delegation re-routing upon validator exit                            │
│ - Operator address consolidation                                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ TIER 3: CURRENTLY UNIDENTIFIED BEHAVIOR (Yield Sensitivity)            │
│ - Validator elasticity to duration-dependent yield / reward spreads    │
│ - Non-identified due to historical yield stability                     │
│ - Evaluated via bounded behavioral scenarios                           │
└────────────────────────────────────────────────────────────────────────┘
```

The lack of historical yield variation is a limitation on estimating yield sensitivity specifically, not a limitation on reconstructing validator behavior generally.

---

## 4. Bounded Treatment of Yield Sensitivity

Because empirical yield elasticity cannot be identified from historical records, Stage 4 evaluates this dimension using three bounded behavioral scenarios:

1. **Scenario Y1 (Low Yield Sensitivity):**
   - Validator duration choices and renewal decisions are dominated by operational conventions, capital lockup limits, and existing delegation relationships.
   - Minimal migration toward higher-reward tenures when duration reward spreads expand.
2. **Scenario Y2 (Moderate Yield Sensitivity):**
   - Validators exhibit proportional substitution toward longer, higher-reward tenures as duration reward spreads widen, balanced by capital exposure frictions.
3. **Scenario Y3 (High Yield Sensitivity):**
   - Validators actively optimize staking duration to maximize net annual yield, rapidly migrating toward peak-reward tenures and exhibiting high elasticity to outside liquid staking / lending benchmarks.

*Methodological Purpose:* The objective of these scenarios is not to assert an ungrounded elasticity parameter, but to determine how much the admission frontier's conclusions and optimal parameter envelopes $(S_{\mathrm{floor}}, S_{\mathrm{short}}, p)$ depend on this specific unresolved behavioral relationship.

---

## 5. Formal Measures of Effectiveness (MOEs)

Mechanism performance is evaluated against five quantitative, decision-relevant MOEs expressed strictly in consensus, economic, and network terms, without governance or voting terminology:

$$\begin{array}{|l|l|l|l|}
\hline
\textbf{MOE} & \textbf{Metric Name} & \textbf{Mathematical Definition} & \textbf{Decision Relevance} \\
\hline
\text{MOE 1} & \textbf{Validator-Set} & S_N = \frac{\sigma(N)}{\bar{N}} & \text{Measures active population volatility across the simulation} \\
& \textbf{Stability} & & \text{horizon under macro price shocks. Evaluates set resilience.} \\
\hline
\text{MOE 2} & \textbf{Validator Churn \&} & \lambda_{\mathrm{turnover}}(t) = \frac{A(t) + E(t)}{2N(t)} & \text{Measures total network turnover and quantifies short-tenure} \\
& \textbf{Renewal Dynamics} & \lambda_{\mathrm{short}} = \frac{1}{T}\sum_{t=1}^T \frac{A_{\mathrm{short}}(t) + E_{\mathrm{short}}(t)}{2N(t)} & \text{turnover below delegation gate. Informs calibration of } S_{\mathrm{short}}\text{.} \\
\hline
\text{MOE 3} & \textbf{Stake Concentration} & HHI_{\mathrm{node}}(t) = \sum_{i=1}^{N(t)} s_i(t)^2 \times 10^4 & \text{Evaluates dispersion of consensus stake weight } s_i(t)\text{;} \\
& \textbf{Across Nodes \&} & HHI_{\mathrm{operator}}(t) = \sum_{j=1}^{M(t)} \omega_j(t)^2 \times 10^4 & \text{aggregates nodes by operator cluster } \omega_j(t) \text{ so multi-node} \\
& \textbf{Clustered Operators} & C_{K,\mathrm{operator}}(t) = \sum_{j=1}^K \omega_{(j)}(t) \quad (K=10, 20) & \text{entities do not mask true consensus stake concentration.} \\
\hline
\text{MOE 4} & \textbf{Economic Viability} & V_{\mathrm{profile}, k}(t) = \frac{1}{N_k}\sum_{i \in k} \chi(\text{Margin}_i(t) > 0) & \text{Measures fraction of validators within each profile maintaining} \\
& \textbf{Across Profiles} & & \text{positive net margins. Prevents } S_{\mathrm{floor}} \text{ being an unviable ghost tier.} \\
\hline
\text{MOE 5} & \textbf{Network-Capacity} & H_{\mathrm{cap}} = \min\left(1 - \frac{\max N}{N_{\max}}, 1 - \frac{\max \lambda}{\lambda_{\max}}\right) & \text{Measures operational safety headroom against Ava Labs telemetry} \\
& \textbf{Pressure} & & \text{capacity limits } (N_{\max}, \lambda_{\max})\text{. Informs P2P and PlatformVM safety.} \\
\hline
\end{array}$$

---

## 6. Parameter Selection under Uncertainty (PSuU)

PSuU executes high-throughput parameter sweeps across five core exploration dimensions:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ PSuU EXPLORATION GRID                                                  │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Policy Frontier Parameters:                                         │
│    S_floor ∈ [500, 2,000] AVAX                                         │
│    S_short ∈ [5,000, 25,000] AVAX                                      │
│                                                                        │
│ 2. Curve Exponent Candidates:                                          │
│    Canonical Baseline: p = 1.0 (linear harmonic)                       │
│    Alternative Candidates: p ∈ {1.2, 1.5, 2.0, 3.0}                    │
│    (No p range is claimed to be universally valid)                     │
│                                                                        │
│ 3. Yield-Sensitivity Scenarios (Formalized via Algorithmic Rules):     │
│    - Scenario Y1: Low yield sensitivity (habitual persistence)         │
│    - Scenario Y2: Moderate yield sensitivity (proportional trade-off)  │
│    - Scenario Y3: High yield sensitivity (aggressive optimization)     │
│    (Implemented via explicit numerical choice models / elasticities)   │
│                                                                        │
│ 4. Macroeconomic Stress Scenarios (Exploratory Assumptions):           │
│    - Stress Baseline: $25 AVAX price & stable staking yield            │
│    - Depressed Valuation Stress: $15 AVAX price & elevated yields      │
│    - Volatile Swings: Dynamic price shocks testing active-set solvency │
│    (Explicitly exploratory stress assumptions, not empirical limits)   │
│                                                                        │
│ 5. Initial Condition Robustness:                                       │
│    - Replay of empirical active-set snapshot from derived.node-table   │
│    - Comparison against stationary uniform residual life baseline      │
└────────────────────────────────────────────────────────────────────────┘
```

### Analysis & Curve Comparison
- Compute global variance decomposition (Sobol sensitivity indices) across MOE 1–5 to determine parameter dominance.
- Conduct comparative outcome analysis of canonical baseline $p = 1$ versus candidate $p > 1$ curves across all five MOEs to examine structural trade-offs rather than forcing an artificial single-score ranking.

---

## 7. Deferred Empirical Calibration Integration

The simulation methodology enforces strict epistemic separation:
- *Observed from history:* Baseline arrival cadence, duration distributions, tenure persistence, and streak distributions.
- *Calibrated from history:* Profile revenue and operating margin models.
- *Assumed for scenario testing:* Yield-sensitivity behavioral scenarios (Y1–Y3).
- *Not yet identifiable from available data:* Exact causal yield-elasticity function.

### Role of ACP-285 / Helicon
ACP-285 / Helicon introduces the first duration-dependent reward schedule on Avalanche. Post-policy data from ACP-285 / Helicon should therefore be treated as the beginning of the empirical calibration opportunity for yield sensitivity, to be monitored as post-policy observations accumulate over relevant renewal cycles, rather than something that must already be fully identified today.
