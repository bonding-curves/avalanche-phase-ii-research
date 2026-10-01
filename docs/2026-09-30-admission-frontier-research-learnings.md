# Research Learning Record: Duration-Dependent PoS Admission Frontier Review Cycle

**Subsystem:** Avalanche Primary Network Consensus & PlatformVM  
**Document Type:** Durable Project Learning Record (`/learn`)  
**Context:** Synthesis of Teamwork Adversarial Review, Boost Adjudication, and Goal Acceptance Criteria  
**Status:** Canonical Project Memory (September 30, 2026)  

---

## 1. Purpose of the Research

Determine whether a duration-dependent minimum self-stake schedule $S_{\min}(d)$ is an economically defensible and computationally sound admission mechanism for the Avalanche Primary Network, and identify the admissible parameter envelope $(S_{\mathrm{floor}}, S_{\mathrm{short}}, p)$ that balances validator decentralization against network security and operational capacity.

The candidate mechanism is the bounded harmonic power formulation:

$$S_{\min}(d) = S_{\mathrm{floor}} + (S_{\mathrm{short}} - S_{\mathrm{floor}}) \cdot \eta(d)^p, \qquad \eta(d) = \frac{\frac{1}{d} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}}$$

---

## 2. Research Workflow Separation: Teamwork vs. Boost vs. Goal

To maintain engineering discipline and prevent cognitive drift, the project separates research verification into distinct operational phases:

1. **Teamwork (`/teamwork-preview`): Adversarial Attack Phase**
   - *Role:* Red-team stress testing.
   - *Objective:* Attempt to break the mechanism, identify unstated assumptions, uncover edge-case singularities, and probe failure modes.
   - *Epistemic Status:* Adversarial claims are hypotheses of vulnerability, **not established ground truth**. They intentionally include extreme stress scenarios and aggressive interpretations.
2. **Boost (`/boost`): First-Principles Adjudication Phase**
   - *Role:* Impartial judicial filter.
   - *Objective:* Evaluate every adversarial claim against first-principles mathematics, protocol state rules, and empirical evidence.
   - *Epistemic Status:* Categorizes findings strictly into Valid Defects, Valid Concerns, Overstated Claims, and Rejected Findings. Discards false theorems, strips invented thresholds, and identifies the minimal required correction set.
3. **Goal (`/goal`): Research Acceptance Criteria Phase**
   - *Role:* Gatekeeper and roadmap definition.
   - *Objective:* Define explicit, falsifiable criteria that must be satisfied before transitioning from research to production recommendation.
   - *Epistemic Status:* Formulates verification gates, separates blocking criteria from deferred questions, and prevents premature parameter lock-in.

---

## 3. Major Findings That Survived Adjudication

The Boost adjudication established the following core findings:

- **M1 (Pivot Inversion Singularity — Valid Defect):** If target stake satisfies $S_{\mathrm{pivot}} > S_{\mathrm{floor}} + \Delta S \cdot \eta(d_{\mathrm{pivot}})$, the logarithmic inversion formula mathematically forces $p < 1$. For $p < 1$, an interior inflection point occurs at $d^* = \frac{p+1}{2}d_{\max}$, rendering the curve strictly concave on $(d^*, d_{\max})$ and generating an infinite terminal derivative cliff ($\lim_{d\to d_{\max}^-} |S'| = \infty$). An explicit precondition $S_{\mathrm{pivot}} \le S_{\mathrm{floor}} + \Delta S \cdot \eta(d_{\mathrm{pivot}})$ and constraint $p \ge 1.0$ are required.
- **M3 (Continuous Derivative Bound Inconsistency — Valid Defect):** For all $p > 1$, terminal slope is asymptotically flat ($\lim_{d\to d_{\max}^-} S'(d) = 0$). Imposing a continuous lower bound $|S'(d)| \ge \kappa_{\min}$ on an interval extending toward $d_{\max}$ is mathematically impossible. Intermediate differentiation must be specified via discrete finite differences $S(d_a) - S(d_b) \ge \Gamma_{\min}$.
- **P1 (Consensus Floating-Point Divergence — Valid Defect):** PlatformVM consensus state verification must be 100% bitwise deterministic across x86_64 and ARM64 nodes. IEEE 754 floating-point operations in transaction admission checks risk consensus chain splits. Integer-only fixed-point arithmetic or lookup tables are mandatory.
- **NC1 (Fictitious Latency Transfer Function — Valid Defect):** Avalanche Snowman consensus latency is governed by repeated subsampling with constant sample size $k = 20$, making consensus round latency invariant to validator set size $N$. The analytical function $L(N, \lambda_{\mathrm{churn}}) \le L_{\mathrm{budget}}$ is unsupported in consensus theory. Network capacity gating must rely on empirical node telemetry ceilings from Ava Labs.
- **MD2 (Retail Delegation Quarantine — Valid Concern):** With $d_{\min} = 2\text{d}$ and $d_{\mathrm{del,\min}} = 14\text{d}$, validators on $[2\text{d}, 14\text{d})$ cannot legally accept delegations. This band serves non-delegated operations (Subnets/L1s, market makers, test infrastructure).
- **EB2 (Calendar Clustering Bias — Valid Concern):** Historical stint durations cluster heavily (>70%) at calendar milestones (14d, 30d, 90d, 365d). Histogram mode searches identify calendar heuristics rather than structural economic indifference points.
- **EC1 (Multi-Profile Solvency Divergence — Valid Concern):** Validator viability at $S_{\mathrm{floor}} = 500$ AVAX depends on business models. Standalone solo staking, delegator-facing commercial nodes, and multi-purpose ecosystem nodes exhibit different solvency thresholds.
- **EC2 (Hyperbolic Anchor Status — Valid Concern):** The 28,000 AVAX-days quantity is a legacy empirical reference anchor ($2{,}000\text{ AVAX} \times 14\text{ days}$), not an inviolable security invariant.
- **P3 (In-Flight Validator Migration — Valid Concern):** Hard fork activation requires explicit grandfathering rules for existing validator registrations.
- **DT2 (Endogenous Yield Feedback — Valid Concern):** Staking APR dilutes as aggregate active stake increases. Modeling validator entry requires dynamic APR feedback loops in radCAD.

---

## 4. Major Teamwork Overclaims That Were Rejected

1. **Universal Upper Bound $p \le 2.5$ (Overstated):** Derived from a single numerical tenure evaluation ($d = 84\text{d}$ under $14\text{d}/365\text{d}$). Intermediate flattening depends on the specific duration domain and policy intervals. It is not an absolute mathematical theorem.
2. **Failure Against Capital-Abundant Churners (Overstated):** $S_{\min}(d)$ is an upfront capital admission gate at registration, not an ongoing flow fee. Under mechanism instrument separation $M(S, d) = (G(S, d), R(d))$, anti-churn deterrence for capital-abundant entities is the explicit role of the duration reward premium $\Delta R = R(d_{\max}) - R(d_{\min})$ and transaction fees, not $S_{\min}(d)$ alone.
3. **Mandatory Non-Linear Delegation Power Model $A_{\mathrm{del}}^\gamma$ with $\gamma > 1$ (Rejected):** $A_{\mathrm{del}}(d) = \max\left(0, \frac{d - d_{\mathrm{del,\min}}}{d}\right)$ is strictly a geometric temporal eligibility index. Imposing an arbitrary power parameter without empirical data introduces unjustified complexity.
4. **256-Bit Arithmetic Uniquely Required (Overstated):** Intermediate overflow during fixed-point scaling can be completely prevented in 64-bit or 128-bit registers by normalizing tenure units to integer hours or days.
5. **Uniform Residual Life Inherently Invalid (Overstated):** $\tau_{\mathrm{rem}, i} \sim U(0, d_i)$ is the mathematically standard renewal baseline for stationary Poisson arrivals. It should be augmented with empirical active-set snapshots, not discarded.
6. **Premature Mechanism Lock-in to $p = 1$ (Overstated):** While $p = 1$ provides a parsimonious baseline, curvature flexibility ($p \neq 1$) should remain an evaluative candidate in simulation sweeps to determine whether non-linear decay yields material welfare gains.
7. **Treating Data Recency as Permanent Identification Failure (Overstated):** The lack of post-policy duration-choice data today is due to the 48-hour regime being active for only one week. This is temporary data immaturity, not a permanent impossibility of empirical identification.

---

## 5. Status of the Three Decision Gates

- **Gate D1 (Curve Exponent $p$):** `LEFT OPEN AS COMPARATIVE SCENARIO`. Setting $p = 1$ is adopted as the **Canonical Baseline Mechanism** due to parameter parsimony, non-zero terminal slope, and integer simplicity. Generalized curvature ($p \neq 1$) is retained as an evaluative scenario in Stage 3 and Stage 4 simulation sweeps.
- **Gate D2 (Solvency Target $S_{\mathrm{floor}}$):** `MAPPED AS SCENARIO ENVELOPE`. Evaluated across multi-parameter grids ($P_{\mathrm{AVAX}} \in [\$15, \$50]$, staking $\mathrm{APR} \in [6\%, 10\%]$, infrastructure cost $\in [\$600, \$3{,}600]/\text{year}$) across solo, commercial, and multi-purpose operator profiles. Final calibration awaits Ava Labs policy input on the target operator solvency class.
- **Gate D3 (Behavioral Econometric Framing):** `DEFERRED EMPIRICAL CALIBRATION`. The new regime is too recent (~1 week old) for stable causal estimation. The empirical measurement framework is instrumented now; causal estimation of duration-choice elasticity is deferred until the network stabilizes across multiple renewal cycles (8 to 12 weeks).

---

## 6. What Is Established Now

1. **Mathematical Foundations:** Exact Dirichlet endpoint compliance holds identically for all $p > 0$. Strict monotonic decrease holds everywhere on $[d_{\min}, d_{\max})$. Strict convexity holds everywhere on $(d_{\min}, d_{\max})$ for all $p \ge 1.0$. The curve requires $p \ge 1.0$ to eliminate interior concavity and infinite derivative cliffs.
2. **Mechanism Scope Separation:** $S_{\min}(d)$ governs registration capital access; $R(d)$ governs ongoing tenure incentives. $A_{\mathrm{del}}(d)$ defines legal delegation windows.
3. **Consensus Engineering:** PlatformVM state verification must execute bitwise deterministic integer arithmetic. Standard float operations are strictly prohibited.
4. **Historical Empirical Limits:** Historical renewal data establishes baseline tenure preferences and calendar clustering under $S_{\min} \equiv 2{,}000$ AVAX, but cannot identify causal elasticity to duration-dependent hurdles.

---

## 7. What Remains Open & External Inputs Required

### Simulation Tasks (Stage 4 radCAD Work)
- Macro stability of validator set size $N(t)$ and churn $\lambda(t)$ under price shocks.
- Comparative welfare evaluation of linear harmonic ($p = 1$) vs power-decay ($p > 1$) schedules under heterogeneous validator capital.
- Sensitivity comparisons between stationary uniform residual life and empirical active-set snapshot initializations.

### Deferred Questions (Awaiting Stabilization)
- Revealed duration-choice elasticity ($\beta_{\mathrm{dur}}$) under duration-dependent capital hurdles.
- Empirical delegation matching dynamics across validator tenure tiers.

### External Inputs Required
- **Ava Labs Policy (Class B):** Definition of target validator solvency class (solo self-staking vs commercial delegator-facing).
- **Ava Labs Engineering (Class B):** Node infrastructure telemetry benchmarks establishing safe operational capacity limits for $N_{\max}$ and weekly churn $\lambda_{\max}$.
- **Core Client Release Planning (Class C):** PlatformVM hard fork migration and grandfathering clauses for in-flight validator registrations.

---

## 8. Current Research Sequence

```text
Stage 1: Analytical Scenarios (Solvency & Boundary Grids)
Stage 3: Baseline Curve Formalization (p = 1 Baseline & Integer Specs)
Stage 4: radCAD Digital Twin Infrastructure (Multi-Agent & Dynamic APR)
       │
       ▼
Observe New Duration Regime (Track Cohort Shares & Churn Variance)
       │
       ▼ [Stabilization Gate: 4 consecutive cohorts within ±5%, 8-12 weeks]
Stage 2: Deferred Empirical Calibration (Structural Elasticity Estimation)
       │
       ▼
Final Parameter Recommendation & Governance ACP Submission
```
