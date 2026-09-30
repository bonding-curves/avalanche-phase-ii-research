# Duration-Dependent PoS Admission Frontier: Technical Work Plan

**Repository:** `avalanche-phase-ii-research`  
**Subsystem:** Avalanche Primary Network Consensus & PlatformVM  
**Document Type:** Formal Systems Engineering & Mechanism Design Work Plan  
**Source Specification:** [docs/2026-09-30-duration-dependent-admission-frontier-specification.md](file:///home/hash/Hub/Projects/avalanche-phase-ii-research/docs/2026-09-30-duration-dependent-admission-frontier-specification.md)  
**Status:** Revised Working Plan (Planning Mode Only)  

---

## 1. Goal Description

Determine whether a duration-dependent minimum self-stake curve is a defensible mechanism for the Avalanche Primary Network and, if so, determine the range of parameters that should be considered.

The candidate mechanism is the bounded harmonic power family:

$$S_{\min}(d) = S_{\mathrm{floor}} + \Delta S \cdot \eta(d)^p, \quad \Delta S = S_{\mathrm{short}} - S_{\mathrm{floor}}$$

where:

$$\eta(d) = \frac{\frac{1}{d} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}} = \frac{d_{\min}(d_{\max} - d)}{d(d_{\max} - d_{\min})}$$

This work plan provides:
1. A forensic audit of the working specification across 10 evaluation categories.
2. A streamlined, four-stage research pipeline organized around four direct questions.
3. Explicit treatment of unresolved Foundation/Ava Labs inputs as parallel scenarios rather than blockers.

---

## 2. Specification Sufficiency Finding

> [!IMPORTANT]
> **Is the current specification sufficient to proceed to numerical calibration?**
>
> **No.** Foundational prerequisites must be resolved before numerical parameters can be calibrated:
> 1. **Target Operator Solvency Definition:** The economic floor condition $V_i(S_{\mathrm{floor}}, d_{\max}) \ge 0$ requires defining the representative cost structure ($C_{\mathrm{op}}, c_i$) of the target viable validator class.
> 2. **Empirical Grounding of Duration Response:** The pivot duration $d_{\mathrm{pivot}}$ cannot be chosen geometrically or visually. It requires empirical estimation of duration sensitivity and renewal/exit probabilities from historical P-Chain telemetry.
> 3. **Consensus Exponent Admissibility:** The allowable numerical representation for exponent $p$ (restricted integer vs. rational $a/b$ vs. fixed-point lookup) must be verified against PlatformVM consensus execution constraints before calibrating continuous values.

---

## 3. Ten-Point Specification Audit

### 3.1 What is Already Established in the Document
* **Policy Instrument Separation:** The admission gate $G(S, d) \in \{0, 1\}$ and reward curve $R(d)$ are separate mechanisms in execution, but linked in validator utility $M(S, d) = (G(S, d), R(d))$.
* **Compact Domain and Boundaries:** Staking duration is strictly bounded $d \in [d_{\min}, d_{\max}]$, with exact boundary requirements $S_{\min}(d_{\min}) = S_{\mathrm{short}}$ and $S_{\min}(d_{\max}) = S_{\mathrm{floor}}$.
* **Retail Delegation Quarantine:** Under PlatformVM duration ordering ($d_{\mathrm{del},\min} \le d_{\mathrm{del}} \le d_{\mathrm{val}}$), validators with $d < d_{\mathrm{del},\min} = 14\text{ days}$ are physically barred from receiving retail delegations.
* **Delegation-Access Friction Ratio:** For $d \ge d_{\mathrm{del},\min}$, retail entry window friction is captured by $A_{\mathrm{del}}(d) = \max(0, (d - d_{\mathrm{del},\min})/d)$.
* **Rejection of Alternative Families:** Rejection of pure iso-commitment ($C/d$), unshifted hyperbola ($S_{\mathrm{floor}} + K/d$), and shifted power laws based on boundary drift or interior derivative collapse.

### 3.2 What is Mathematically Established
* **Exact Dirichlet Boundary Interpolation:** $\eta(d_{\min}) = 1 \implies S_{\min}(d_{\min}) = S_{\mathrm{short}}$, and $\eta(d_{\max}) = 0 \implies S_{\min}(d_{\max}) = S_{\mathrm{floor}}$, with identically zero residual error for all $p > 0$.
* **Strict Monotonic Decrease:** For all $p \ge 1$ and $d \in [d_{\min}, d_{\max})$, $S'_{\min}(d) < 0$.
* **Strict Interior Convexity:** For all $p \ge 1$ and $d \in (d_{\min}, d_{\max})$, $S''_{\min}(d) > 0$.
* **Analytical Invertibility for $p$:** Given a target pivot point $(d_{\mathrm{pivot}}, S_{\mathrm{pivot}})$, the exponent is uniquely determined by:
  $$p = \frac{\ln\left( \frac{S_{\mathrm{pivot}} - S_{\mathrm{floor}}}{S_{\mathrm{short}} - S_{\mathrm{floor}}} \right)}{\ln \eta(d_{\mathrm{pivot}})}$$
* **Finite Terminal Sensitivity:** $\lim_{d \to d_{\max}^-} |S'_{\min}(d)| < \infty$ for all $p \ge 1$ (identically zero for $p > 1$).

### 3.3 What is Currently Only a Design Choice or Assumption
* **Choice of Coordinate $\eta(d)$:** Selection of the normalized harmonic coordinate over other two-point interpolators (e.g., splines or piecewise functions).
* **Single-Point Pivot Inversion:** Using a single point $(d_{\mathrm{pivot}}, S_{\mathrm{pivot}})$ to pin down $p$, rather than a multi-point regression fit across duration buckets.
* **Linear Delegation Friction Form:** Modeling delegation exposure via the linear ratio $A_{\mathrm{del}}(d) = (d - d_{\mathrm{del},\min})/d$.
* **Additive Random Utility Structure:** Assuming validator renewal choices follow an additive discrete-choice utility model with Gumbel/Weibull errors.
* **Stationary Arrival Assumption:** Assuming phase-randomized initialization $\tau_{\mathrm{rem}, i} \sim U(0, d_i)$ produces a stationary continuous arrival process in simulation.

### 3.4 What Requires Empirical Estimation
* **Validator Operating Costs ($C_{\mathrm{op}}$):** Annualized infrastructure costs across bare-metal, budget VPS, and standard commercial cloud nodes.
* **Opportunity Cost of Capital ($c_i$):** Expected shadow yield on capital relative to liquid staking tokens (sAVAX / ggAVAX) and DeFi outside options.
* **Duration Preference Parameters ($\beta_{\mathrm{dur}}$):** Econometric estimation of validator duration sensitivity from the historical renewal panel (`01-renewal-panel.parquet`, $N = 57{,}067$ stints across $7{,}635$ nodes).
* **Delegation Capture Function ($B_i(A_{\mathrm{del}}(d))$):** Empirical relationship between validator duration, self-stake, and actual delegation inflow.
* **Candidate Pivot Region ($d_{\mathrm{pivot}}$):** Duration range where tenure extension is achieved without excessive validator exit.

### 3.5 What Requires Simulation
* **Dynamic Intertemporal Anti-Splitting:** Testing whether validators can profitably exploit repeated short-duration rolls under dynamic fee, reward, and price conditions.
* **Active Set Stability ($N^*(t)$):** Evaluating validator population trajectories under market stress and macroeconomic shocks.
* **Consensus Churn Dynamics ($N_{\mathrm{churn}}(t)$):** Measuring daily entry/exit volume compared against historical baseline turnover.
* **Stake Concentration:** Measuring evolution of stake concentration (HHI, Gini coefficient, top-tier share) over multi-year simulation runs.
* **Network Latency Headroom:** Evaluating whether simulated active set and churn rates remain within consensus latency capacity limits.

### 3.6 What Requires PlatformVM / Consensus Implementation Verification
* **Cleared-Fraction Arithmetic:** Verifying that $\eta(d) = \frac{d_{\min}(d_{\max} - d)}{d(d_{\max} - d_{\min})}$ evaluates deterministically without floating-point arithmetic.
* **Exponent Evaluation in Consensus:** Determining whether PlatformVM requires restricted integer exponents ($p \in \{1, 2, 3\}$), rational power approximations ($p = a/b$), or fixed-point lookup tables.
* **Rounding and Ordering Proofs:** Demonstrating that integer division with ceiling rounding preserves strict monotonic ordering and guarantees $S_{\min}(d_{\max}) \equiv S_{\mathrm{floor}}$.
* **Execution Placement and Overhead:** Benchmarking computational overhead inside `vms/platformvm/txs/executor/staker_tx_verification_helpers.go`.

### 3.7 Claims that Must be Weakened, Removed, or Explicitly Qualified
* **Convexity as Anti-Splitting Proof:** Static convexity ($S''_{\min}(d) > 0$) is purely a curve shape property. It does not prove dynamic intertemporal anti-splitting across repeated stints. That property must be confirmed through simulation.
* **Sybil Protection from $S_{\mathrm{short}}$ Alone:** $S_{\mathrm{short}}$ sets an admission hurdle, but Snow consensus security depends on sub-sampled voting weight distributions ($\alpha, k$), not validator seat counts in isolation.
* **Delegation Accessibility vs. Flow:** $A_{\mathrm{del}}(d)$ measures temporal eligibility, not realized delegation volume. Realized flow is endogenous and concentrates on validators with $\ge 6{,}000\text{ AVAX}$ self-stake.
* **Zero Terminal Derivative for $p > 1$:** When $p > 1$, $\lim_{d \to d_{\max}^-} S'_{\min}(d) = 0$. The specification must explicitly analyze whether this flat terminal slope weakens incentives to lock for 365 days versus 300 days.
* **Unwarranted Quantitative Thresholds:** Remove premature acceptance thresholds (such as "$\ge 40\%$ churn reduction," "$N \ge 500$," "$L/L_{\mathrm{budget}} \le 0.75$," or "$< 1\text{ nAVAX}$ error") from research criteria until established by formal protocol requirements.

### 3.8 Dependencies Between the Workstreams
The work follows a direct, sequential four-stage pipeline:
$$\boxed{\text{Stage 1: Economics}} \longrightarrow \boxed{\text{Stage 2: Behavior}} \longrightarrow \boxed{\text{Stage 3: Curve}} \longrightarrow \boxed{\text{Stage 4: Stress Test}}$$

* **Stage 1 (Economics)** establishes $(d_{\min}, d_{\max}, S_{\mathrm{floor}}, S_{\mathrm{short}})$.
* **Stage 2 (Behavior)** estimates validator duration response and identifies candidate $d_{\mathrm{pivot}}$ ranges.
* **Stage 3 (Curve)** solves for exponent $p$, tests interior differentiation, and specifies consensus integer arithmetic.
* **Stage 4 (Stress Test)** evaluates multi-agent dynamics in radCAD against network capacity constraints.

### 3.9 Questions Required Before Numerical Calibration
* **Q1 (Activation Regime):** What is the target activation lower bound ($d_{\min} = 2\text{ days}$ under ACP-273 vs. legacy $14\text{ days}$)?
* **Q2 (Target Viability Class):** Which operator persona must break even at $S_{\mathrm{floor}}$ (home bare-metal vs. budget cloud VPS)?
* **Q3 (Short-End Constraint):** Is $S_{\mathrm{short}}$ anchored strictly to legacy capital-time commitment ($28{,}000\text{ AVAX-days}$) or an elevated churn hurdle?
* **Q4 (Consensus Arithmetic Form):** Does PlatformVM consensus mandate integer exponents ($p \in \{1, 2, 3\}$), or are rational fixed-point powers supported?

### 3.10 Questions Required Before Ava Labs Architectural Review
* **Q5 (State Verification Placement):** Where is $S_{\min}(d)$ enforced in PlatformVM (state transition verification vs. mempool filtering)?
* **Q6 (Migration Policy):** How are in-flight validators handled upon hard fork activation (grandfathered until expiry vs. mandatory renewal rule)?
* **Q7 (Reward Coordination):** Are the admission frontier and ACP-285 duration rewards activated concurrently in the same hard fork?
* **Q8 (Validated Latency Budget):** Has the consensus latency model $L(N, \lambda_{\text{churn}})$ been validated against testnet churn telemetry?

---

## 4. Four-Stage Research Work Plan

### Stage 1: Establish the Economic and Protocol Boundaries
* **Core Question:** What should the two ends of the curve mean?
* **Scope:**
  1. Confirm protocol regime ($d_{\min}, d_{\max}, d_{\mathrm{del},\min}$). Carry ACP-273 ($2\text{d}$) and legacy ($14\text{d}$) as parallel scenarios.
  2. Estimate $S_{\mathrm{floor}}$ from validator solvency:
     $$\text{Rewards} - \text{Operating Cost} - \text{Capital Opportunity Cost} \ge 0$$
     Establish a plausible range across operator classes and AVAX price levels.
  3. Constrain $S_{\mathrm{short}}$ using the legacy capital-time invariant ($K = 28{,}000\text{ AVAX-days}$) as a baseline and evaluate required security cushions.
* **Output:** Boundary parameter table $(d_{\min}, d_{\max}, S_{\mathrm{floor}}, S_{\mathrm{short}})$ labeled by epistemic status.

### Stage 2: Understand Validator Behavior
* **Core Question:** How do validators trade off duration, reward, capital lockup, and delegation access?
* **Scope:**
  1. Analyze historical records (`01-renewal-panel.parquet`) to identify chosen durations, renewal rates, and exit triggers across capital tiers.
  2. Quantify delegation friction for $d < 28\text{ days}$ using $A_{\mathrm{del}}(d) = \max(0, (d - d_{\mathrm{del},\min})/d)$.
  3. Estimate an empirical duration response model ($\text{duration} \to \text{validator renewal/exit response}$).
  4. Identify a candidate pivot region $d_{\mathrm{pivot}}$ where commitment duration increases with acceptable participation loss.
* **Output:** Empirical behavioral report containing estimated duration sensitivity, renewal probabilities, exit response, and candidate $d_{\mathrm{pivot}}$ range.

### Stage 3: Construct and Test the Admission Curve
* **Core Question:** Given the economic boundaries and behavioral pivot, what curve should the protocol use?
* **Scope:**
  1. Invert the bounded harmonic curve at the candidate pivot to solve for $p$:
     $$p = \frac{\ln\left( \frac{S_{\mathrm{pivot}} - S_{\mathrm{floor}}}{S_{\mathrm{short}} - S_{\mathrm{floor}}} \right)}{\ln \eta(d_{\mathrm{pivot}})}$$
  2. Test the candidate curve:
     * Strict monotonic decrease ($S'_{\min} < 0$).
     * Interior convexity ($S''_{\min} > 0$).
     * Intermediate differentiation (reject hockey-stick collapse).
     * Exact endpoint convergence.
  3. Specify deterministic integer / fixed-point implementation for PlatformVM using cleared-fraction coordinates.
* **Output:** Candidate parameter set $(S_{\mathrm{floor}}, S_{\mathrm{short}}, d_{\mathrm{pivot}}, p)$ and consensus integer implementation specification.

### Stage 4: Stress-Test the Mechanism
* **Core Question:** Does the mechanism behave acceptably when many heterogeneous validators interact?
* **Scope:**
  1. Implement the candidate frontier in radCAD with agent renewal decisions driven by the Stage 2 behavioral model.
  2. Run comparative simulations: Baseline mechanism vs. Duration-dependent frontier.
  3. Track validator set size $N(t)$, churn rate $N_{\mathrm{churn}}(t)$, total stake $S_{\mathrm{total}}(t)$, and concentration (HHI).
  4. Evaluate simulated churn and population against available Avalanche consensus capacity data ($L(N, \lambda_{\mathrm{churn}}) \le L_{\mathrm{budget}}$).
* **Output:** Stress-test evaluation report resulting in:
  1. *Candidate accepted for external review*, or
  2. *Candidate accepted only within a defined parameter range*, or
  3. *Mechanism fails and requires redesign.*

---

## 5. External Scenarios Carried in Parallel

Unresolved Foundation and Ava Labs decisions are carried as analytical scenarios rather than blockers:

* **Scenario Set 1 (Duration Lower Bound):**
  * Scenario 1A: $d_{\min} = 2\text{ days}$ (Helicon / ACP-273 activation).
  * Scenario 1B: $d_{\min} = 14\text{ days}$ (Legacy duration baseline).
* **Scenario Set 2 (Short-End Hurdle):**
  * Scenario 2A: $S_{\mathrm{short}} = 14{,}000\text{ AVAX}$ (Iso-commitment parity).
  * Scenario 2B: $S_{\mathrm{short}} = 20{,}000\text{ AVAX}$ (Elevated anti-churn barrier).
* **Scenario Set 3 (Consensus Capacity Model):**
  * Scenario 3A: Formal P2P latency response surface $L(N, \lambda_{\text{churn}})$ provided by Ava Labs.
  * Scenario 3B: Uncalibrated capacity treated as an external protocol dependency.

---

## 6. Verification and Execution Boundaries

* **Planning Mode Discipline:** No production code modifications, exploratory regressions, or simulations proceed until this plan is formally approved.
* **Verification Approach:**
  * Stage 1: Verified against Go constants in `ava-labs/avalanchego` and cash/opportunity cost accounting.
  * Stage 2: Verified against historical renewal panel records (`01-renewal-panel.parquet`).
  * Stage 3: Verified via symbolic calculus and fixed-point integer arithmetic simulation.
  * Stage 4: Verified via radCAD multi-agent simulation runs.
