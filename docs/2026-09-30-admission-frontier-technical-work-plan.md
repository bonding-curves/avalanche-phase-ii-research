# Duration-Dependent PoS Admission Frontier: Technical Work Plan

**Repository:** `avalanche-phase-ii-research`
**Subsystem:** Avalanche Primary Network Consensus & PlatformVM
**Document Type:** Formal Systems Engineering & Mechanism Design Work Plan
**Source Specification:** `docs/2026-09-30-duration-dependent-admission-frontier-specification.md`
**Status:** Revised Working Plan (Planning Mode Only)

---

## 1. Goal Description

Determine whether a duration-dependent minimum self-stake curve is a defensible mechanism for the Avalanche Primary Network and, if so, determine the range of parameters that should be considered.

The candidate mechanism is the bounded harmonic power family:

$$
S_{\min}(d)
=
S_{\mathrm{floor}}
+
\Delta S\cdot\eta(d)^p,
\qquad
\Delta S=S_{\mathrm{short}}-S_{\mathrm{floor}}
$$

where:

$$
\eta(d)
=
\frac{\frac{1}{d}-\frac{1}{d_{\max}}}
{\frac{1}{d_{\min}}-\frac{1}{d_{\max}}}
=
\frac{d_{\min}(d_{\max}-d)}
{d(d_{\max}-d_{\min})}.
$$

This work plan provides:

1. A review of the working specification.
2. A streamlined four-stage research pipeline organized around four direct questions.
3. Explicit treatment of unresolved Foundation/Ava Labs inputs as parallel scenarios rather than blockers.

---

## 2. Specification Sufficiency Finding

> **Is the current specification sufficient to proceed to numerical calibration?**
>
> **Final parameter selection is not possible until certain external inputs are resolved, but analytical and scenario-based calibration can proceed in parallel.**

The main unresolved inputs are:

1. **Target Operator Solvency Definition:** The economic floor condition

   $$
   V_i(S_{\mathrm{floor}},d_{\max})\ge0
   $$

   requires a defined target validator class and corresponding cost structure.

2. **Empirical Grounding of Duration Response:** The pivot duration \(d_{\mathrm{pivot}}\) should not be chosen geometrically or visually. It requires analysis of historical duration choice, renewal, and exit behavior.

3. **Consensus Implementation of \(p\):** First determine what the mechanism mathematically and behaviorally requires for \(p\). Then determine how that requirement can be implemented deterministically in PlatformVM.

These questions do not prevent the research from proceeding. Where the final external answer is unavailable, the relevant scenarios should be analyzed in parallel.

---

## 3. Ten-Point Specification Audit

### 3.1 What is Already Established in the Document

* **Policy Instrument Separation:** The admission gate \(G(S,d)\in\{0,1\}\) and reward curve \(R(d)\) are separate mechanisms in execution, but linked in validator utility.
* **Compact Domain and Boundaries:** Staking duration is bounded:

  $$
  d\in[d_{\min},d_{\max}]
  $$

  with:

  $$
  S_{\min}(d_{\min})=S_{\mathrm{short}},
  \qquad
  S_{\min}(d_{\max})=S_{\mathrm{floor}}.
  $$
* **Retail Delegation Quarantine:** Under the validator/delegator duration ordering, validators below the minimum delegation duration cannot receive ordinary delegations.
* **Delegation-Access Friction Ratio:** For durations above the delegation minimum:

  $$
  A_{\mathrm{del}}(d)
  =
  \max\left(0,\frac{d-d_{\mathrm{del,min}}}{d}\right).
  $$
* **Candidate Functional Form:** The bounded harmonic power family provides exact interpolation between the two boundary values.
* **Alternative Families:** Pure iso-commitment, standard hyperbolic, and shifted power-law families are not selected as the preferred form because of boundary or shape limitations.

### 3.2 What is Mathematically Established

* **Exact Boundary Interpolation:**

  $$
  \eta(d_{\min})=1,
  \qquad
  \eta(d_{\max})=0.
  $$

  Therefore:

  $$
  S_{\min}(d_{\min})=S_{\mathrm{short}},
  \qquad
  S_{\min}(d_{\max})=S_{\mathrm{floor}}.
  $$

* **Strict Monotonic Decrease:** For \(p\ge1\):

  $$
  S'_{\min}(d)<0
  $$

  on the interior up to the terminal boundary.

* **Strict Interior Convexity:** For \(p\ge1\):

  $$
  S''_{\min}(d)>0
  $$

  on:

  $$
  d\in(d_{\min},d_{\max}).
  $$

* **Analytical Inversion for \(p\):** Given a target pivot point:

  $$
  p=
  \frac{
  \ln\left(
  \frac{S_{\mathrm{pivot}}-S_{\mathrm{floor}}}
  {S_{\mathrm{short}}-S_{\mathrm{floor}}}
  \right)
  }{
  \ln\eta(d_{\mathrm{pivot}})
  }.
  $$

* **Finite Terminal First-Derivative:** For \(p\ge1\),

  $$
  \lim_{d\to d_{\max}^{-}}
  |S'_{\min}(d)|
  <\infty.
  $$

  For \(p>1\), this limit is zero.

These are mathematical properties of the candidate curve. They do not by themselves establish economic viability, anti-splitting behavior, churn reduction, or consensus safety.

### 3.3 What is Currently Only a Design Choice or Assumption

* **Choice of Coordinate \(\eta(d)\):** Selection of the normalized harmonic coordinate over other two-point interpolators.
* **Single-Point Pivot Inversion:** Using a single pivot condition to determine \(p\), rather than fitting the curve directly across multiple duration observations.
* **Linear Delegation Friction Form:** Modeling delegation access using:

  $$
  A_{\mathrm{del}}(d)
  =
  \max\left(0,\frac{d-d_{\mathrm{del,min}}}{d}\right).
  $$
* **Additive Random Utility Structure:** Assuming validator renewal choices can be represented using a discrete-choice utility model.
* **Stationary Arrival Assumption:** Assuming phase-randomized residual duration initialization produces a suitable stationary approximation for the simulation.

### 3.4 What Requires Empirical Estimation

* **Validator Operating Costs:** Annualized infrastructure costs across relevant validator operating classes.
* **Opportunity Cost of Capital:** Expected return forgone by committing self-stake rather than using available outside options.
* **Duration Preference Parameters:** Empirical estimation of validator duration sensitivity from the historical renewal panel.
* **Delegation Capture Function:** Empirical relationship between validator duration, self-stake, and realized delegation inflow.
* **Candidate Pivot Region:** Duration range where greater commitment appears to improve persistence without excessive participation loss.

The empirical analysis must also distinguish between:

* effects directly observable in the historical data;
* effects that are statistically estimable;
* effects that are causally identifiable;
* effects that require assumptions or counterfactual simulation.

In particular, historical data may not contain enough variation in rewards or admission requirements to identify how validators would respond to a new policy. Such effects must not be presented as directly estimated causal relationships.

### 3.5 What Requires Simulation

* **Dynamic Intertemporal Anti-Splitting:** Testing whether validators can economically circumvent the capital schedule through repeated short-duration renewals.
* **Active Set Stability:** Evaluating validator population trajectories under different market and macroeconomic conditions.
* **Consensus Churn Dynamics:** Measuring entry and exit behavior relative to the relevant baseline.
* **Stake Concentration:** Measuring changes in concentration across validator classes.
* **Network Latency Headroom:** Evaluating whether simulated population and churn remain within validated network-capacity limits.

### 3.6 What Requires PlatformVM / Consensus Implementation Verification

* **Cleared-Fraction Arithmetic:**

  $$
  \eta(d)=
  \frac{
  d_{\min}(d_{\max}-d)
  }{
  d(d_{\max}-d_{\min})
  }.
  $$

* **Deterministic Exponent Implementation:** First determine the continuous behavioral requirement for \(p\), then determine whether PlatformVM should use an integer exponent, rational fixed-point approximation, lookup table, or another deterministic representation.

* **Rounding and Ordering:** Demonstrate that integer implementation preserves the intended floor and duration ordering.

* **Execution Placement and Overhead:** Verify where the rule should execute in PlatformVM and what computational cost it introduces.

### 3.7 Claims that Must be Weakened, Removed, or Explicitly Qualified

* **Convexity as Anti-Splitting Proof:** Convexity is a mathematical shape property. It does not prove that repeated short-duration rolling is economically inferior. That requires behavioral and dynamic analysis.

* **Sybil Protection from \(S_{\mathrm{short}}\) Alone:** A short-duration capital barrier raises the cost of obtaining short-term consensus seats, but overall consensus security depends on voting-weight distribution and Snow sampling dynamics.

* **Delegation Accessibility vs. Actual Flow:** \(A_{\mathrm{del}}(d)\) measures temporal eligibility, not realized delegation volume.

* **Zero Terminal Derivative:** For \(p>1\):

  $$
  \lim_{d\to d_{\max}^{-}}S'_{\min}(d)=0.
  $$

  The mechanism should therefore examine whether the resulting flatness near the upper boundary materially reduces differentiation between long durations.

* **Unwarranted Quantitative Thresholds:** Numerical acceptance thresholds should not be introduced unless they are established by protocol requirements, empirical evidence, or explicit research assumptions.

### 3.8 Dependencies Between the Workstreams

The core research follows:

$$
\boxed{\text{Stage 1: Economics}}
\rightarrow
\boxed{\text{Stage 2: Behavior}}
\rightarrow
\boxed{\text{Stage 3: Curve}}
\rightarrow
\boxed{\text{Stage 4: Stress Test}}.
$$

* **Stage 1:** Establishes the economic and protocol boundaries.
* **Stage 2:** Establishes how validators respond to duration.
* **Stage 3:** Converts those findings into an admissible curve.
* **Stage 4:** Tests the mechanism in a multi-agent environment.

External inputs can be carried as scenarios wherever possible.

### 3.9 Questions Addressed in Analytical Calibration

* **Q1 (Activation Regime):** What is the target lower bound on duration, such as the 2-day or 14-day regime? Carry both as scenarios until the final regime is confirmed.
* **Q2 (Target Viability Class):** Which validator operating class should define the economic viability boundary at \(S_{\mathrm{floor}}\)?
* **Q3 (Short-End Constraint):** How should the short-duration boundary be jointly informed by the legacy capital-time benchmark and the required security/churn behavior?

### 3.10 Questions Required Before Ava Labs Architectural Review

* **Q4 (Deterministic Implementation):** How can PlatformVM deterministically implement the candidate curve produced by Stage 3?
* **Q5 (State Verification Placement):** Where should \(S_{\min}(d)\) be enforced in PlatformVM?
* **Q6 (Migration Policy):** How are in-flight validators handled when the new rule becomes active?
* **Q7 (Reward Coordination):** How should the admission frontier and duration rewards be coordinated at activation?
* **Q8 (Validated Latency Budget):** What validated relationship should be used to assess the effect of validator population and churn on consensus/network capacity?

---

# 4. Four-Stage Research Work Plan

## Stage 1: Establish the Economic and Protocol Boundaries

**Core Question:** What should the two ends of the curve mean?

**Scope:**

1. Confirm the relevant protocol regime:

   $$
   d_{\min},\quad d_{\max},\quad d_{\mathrm{del,min}}.
   $$

   Carry the relevant 2-day and 14-day regimes as parallel scenarios if necessary.

2. Estimate \(S_{\mathrm{floor}}\) from validator solvency:

   $$
   \text{Rewards}
   -
   \text{Operating Cost}
   -
   \text{Capital Opportunity Cost}
   \ge0.
   $$

   Establish a plausible range across relevant validator operating classes and market conditions.

3. Constrain \(S_{\mathrm{short}}\) using the legacy capital-time relationship as a benchmark:

   $$
   K=28{,}000\text{ AVAX-days}.
   $$

   Under the 2-day scenario this corresponds to the benchmark:

   $$
   S_{\mathrm{short}}^{K}
   =
   \frac{28{,}000}{2}
   =
   14{,}000\text{ AVAX}.
   $$

   This is a benchmark, not the final security requirement. Higher barriers should be evaluated as alternative security scenarios.

**Output:** Boundary parameter table:

$$
(d_{\min},d_{\max},S_{\mathrm{floor}},S_{\mathrm{short}})
$$

with each quantity labeled by epistemic status.

---

## Stage 2: Understand Validator Behavior

**Core Question:** How do validators trade off duration, reward, capital lockup, and delegation access?

**Scope:**

1. Analyze the historical renewal panel to identify chosen durations, renewal rates, exits, and observable conditions associated with renewal or exit across validator capital tiers.

2. Quantify delegation friction around the delegation minimum using:

   $$
   A_{\mathrm{del}}(d)
   =
   \max\left(
   0,
   \frac{d-d_{\mathrm{del,min}}}{d}
   \right).
   $$

3. Estimate an empirical duration-response model describing:

   $$
   \text{duration}
   \rightarrow
   \text{renewal/exit behavior}.
   $$

4. Determine which effects are identified from historical variation and which require assumptions or counterfactual simulation, especially where historical rewards or admission conditions did not vary sufficiently to identify a causal response.

5. Identify a candidate pivot region:

   $$
   d_{\mathrm{pivot}}
   $$

   where longer commitment appears to improve persistence without excessive participation loss.

**Output:** Empirical behavioral report containing duration sensitivity, renewal probabilities, exit behavior, identification limits, and candidate pivot region.

---

## Stage 3: Construct and Test the Admission Curve

**Core Question:** Given the economic boundaries and behavioral findings, what curve should the protocol use?

**Scope:**

1. Evaluate candidate pivot and boundary combinations and solve:

   $$
   p=
   \frac{
   \ln\left(
   \frac{S_{\mathrm{pivot}}-S_{\mathrm{floor}}}
   {S_{\mathrm{short}}-S_{\mathrm{floor}}}
   \right)
   }{
   \ln\eta(d_{\mathrm{pivot}})
   }.
   $$

2. Test the resulting curve for:

   * monotone decrease;
   * interior convexity;
   * meaningful intermediate differentiation;
   * exact endpoint convergence;
   * acceptable behavior across the relevant duration range.

3. Identify the admissible parameter region rather than forcing a single numerical solution.

4. Once the desirable mathematical parameter region is known, determine the deterministic PlatformVM implementation strategy.

**Output:** Candidate parameter region:

$$
(S_{\mathrm{floor}},
S_{\mathrm{short}},
d_{\mathrm{pivot}},
p)
$$

with admissible and rejected regions identified, together with the implementation specification.

---

## Stage 4: Stress-Test the Mechanism (Empirical Validator Digital Twin & PSuU)

**Core Question:** How does the candidate mechanism perform under uncertainty when replayed across empirically grounded validator populations, and how sensitive are system outcomes to unresolved yield-response behaviors?

**Scope:**

1. **Three-Layer Data Architecture for Digital Twin Grounding:**
   The simulation model is grounded directly in real-world validator data structured into three distinct operational layers:
   - *Layer A: Full Historical Data (Genesis to Present):* The complete historical dataset (`derived.node-table` covering 7,644 historical Primary Network nodes, `derived.staking-periods`, and completed validation records) serves as the behavioral foundation. It establishes the empirical distribution of entry timing, exit hazards, renewal habits, accumulated tenure, streak persistence, duration choices, self-stake magnitudes, delegation capacity utilization, stake concentration, and multi-cohort population dynamics.
   - *Layer B: Current-Regime Data:* The most relevant recent and current validator population (active nodes captured via P-Chain RPC snapshots and Data API telemetry) initializes the baseline digital-twin population. Its purpose is to represent the active validator set operating under current protocol parameters without imposing an arbitrary historical lookback window.
   - *Layer C: Post-ACP-285 / Helicon Data:* Observations collected under ACP-285 / Helicon provide the specific empirical foundation to begin identifying how validators respond to duration-dependent yield spreads and reward differentials.

2. **Validator Profile Construction from Observed Heterogeneity:**
   Representative validator profiles are derived directly from observed historical distributions to preserve real-world heterogeneity across stake, duration, tenure, renewal propensity, delegation position, and operator scale:
   - *Profile A (Capital-Constrained Solo Validators):* Reconstructed from historical nodes operating near minimum self-stake ($S_i \approx 2{,}000$ AVAX historically), carrying zero delegation ($D_i = 0$), and absorbing 100% of server costs. Evaluated against break-even solvency at $S_{\mathrm{floor}}$.
   - *Profile B (Commercial Delegator-Facing Validators):* Reconstructed from historical nodes with substantial self-stake ($S_i \gg 2{,}000$ AVAX), high delegation fill (median 74% of capacity), and active commission fee capture ($f_{\mathrm{del}} \in [2\%, 10\%]$). Evaluated against the delegation eligibility threshold $d_{\mathrm{del,\min}}$.
   - *Profile C (Multi-Purpose Ecosystem Validators):* Reconstructed from institutional and infrastructure nodes exhibiting continuous streaks, co-funded operations (Subnets/L1s, RPC services), and low sensitivity to standalone Primary Network staking returns.

3. **Clarifying the Identification Limitation (Three Behavioral Dimensions):**
   Validator behavior is not unknown overall. Historical records provide substantial, high-confidence empirical evidence regarding validator behavior:
   - *Observed Behavior:* Entry timing, baseline duration preferences, calendar milestone clustering (14d, 30d, 60d, 90d, 180d, 365d), renewal propensities, streak lengths, exit hazards, self-stake sizing, and delegation capacity utilization are observed and estimated from history.
   - *Partially Identified Behavior:* Duration switching under shifting capital hurdles and delegation re-routing upon node exit, where historical data provides structural boundaries but incomplete counterfactual variation.
   - *Currently Unidentified Behavior (Yield / Reward Sensitivity):* The specific unresolved behavioral relationship is how sensitive validators are to yield and reward changes. Historically, protocol staking yield was effectively stable, providing insufficient variation to identify a reliable yield-elasticity function. Lack of historical yield variation is a limitation on estimating yield sensitivity specifically, not a limitation on reconstructing validator behavior generally.

4. **Immediate Simulation Execution via Bounded Yield Scenarios:**
   The digital twin can and should be built, validated, and run now using the historical behavioral foundation and current-regime population baseline. Simulation does not wait for future data. What awaits additional post-Helicon observations is stronger empirical calibration of the yield-response function. To evaluate the candidate admission mechanism immediately under uncertainty, Stage 4 introduces three bounded yield-sensitivity scenarios:
    - *Scenario Y1 (Low Yield Sensitivity):* Validator duration choices and renewal decisions are dominated by operational conventions, capital lockup limits, and existing delegation relationships, exhibiting low migration in response to duration reward differentials.
    - *Scenario Y2 (Moderate Yield Sensitivity):* Validators exhibit proportional substitution toward longer, higher-reward tenures as duration reward spreads widen, balanced by capital lockup frictions.
    - *Scenario Y3 (High Yield Sensitivity):* Validators actively optimize staking duration to maximize net annual yield, rapidly migrating toward peak-reward tenures and exhibiting high elasticity to outside liquid staking or lending benchmarks.
    - *Algorithmic Implementation & Purpose:* While parameterized at the methodology level as low, moderate, and high, simulation execution translates each scenario into explicit algorithmic transition rules and numerical elasticity parameters. This structure determines how much the mechanism's performance, stability boundaries, and optimal parameter envelopes $(S_{\mathrm{floor}}, S_{\mathrm{short}}, p)$ depend on this specific unresolved behavioral parameter.

5. **Measures of Effectiveness (MOEs):**
   Mechanism performance is evaluated across five quantitative MOEs expressed strictly in consensus, economic, and network terms, without governance or voting terminology:
   - *MOE 1: Validator-Set Stability ($S_N$):*
     $$S_N = \frac{\sigma(N)}{\bar{N}}$$
     Measures active validator population volatility across the simulation horizon under macroeconomic price and return shocks. Informs whether candidate admission hurdles cause destabilizing validator dropouts.
   - *MOE 2: Validator Churn & Renewal Dynamics ($\lambda_{\mathrm{turnover}}, \lambda_{\mathrm{short}}$):*
     $$\lambda_{\mathrm{turnover}}(t) = \frac{A(t) + E(t)}{2N(t)}, \qquad \lambda_{\mathrm{short}} = \frac{1}{T} \sum_{t=1}^T \frac{A_{\mathrm{short}}(t) + E_{\mathrm{short}}(t)}{2N(t)}$$
     where $A_{\mathrm{short}}(t)$ and $E_{\mathrm{short}}(t)$ measure arrivals and exits on tenures below the delegation eligibility minimum ($d < d_{\mathrm{del,\min}}$). Evaluates overall network turnover and quantifies whether $S_{\mathrm{short}}$ successfully dampens transient short-tenure churn.
   - *MOE 3: Stake Concentration / Decentralization Across Nodes and Clustered Operators ($HHI, C_K$):*
     $$HHI_{\mathrm{node}}(t) = \sum_{i=1}^{N(t)} s_i(t)^2 \times 10{,}000, \qquad HHI_{\mathrm{operator}}(t) = \sum_{j=1}^{M(t)} \omega_j(t)^2 \times 10{,}000$$
     $$C_{K,\mathrm{operator}}(t) = \sum_{j=1}^K \omega_{(j)}(t) \quad (K=10, 20)$$
     where $s_i(t) = \frac{S_i(t) + D_i(t)}{S_{\mathrm{total}}(t) + D_{\mathrm{total}}(t)}$ is node $i$'s share of active consensus stake weight, and $\omega_j(t) = \sum_{i \in \text{Operator } j} s_i(t)$ aggregates consensus stake across all nodes belonging to the same identified operator cluster. Evaluates both node-level dispersion and operator-level concentration, ensuring that multi-node operators do not mask true consensus stake concentration.
   - *MOE 4: Economic Viability Across Validator Profiles ($V_{\mathrm{profile}, k}$):*
     $$V_{\mathrm{profile}, k}(t) = \frac{1}{N_k} \sum_{i \in \text{Profile } k} \chi\left( \text{Net\_Operating\_Margin}_i(t) > 0 \right)$$
     Measures the proportion of validators within each empirical profile that maintain positive net operating margins under endogenous staking yields $R_{\mathrm{macro}}(t)$ and market price scenarios. Informs whether $S_{\mathrm{floor}}$ represents a sustainable economic tier for solo operators.
   - *MOE 5: Network-Capacity Pressure ($H_{\mathrm{cap}}$):*
     $$H_{\mathrm{cap}} = \min\left( 1 - \frac{\max_t N(t)}{N_{\max}}, \; 1 - \frac{\max_t \lambda_{\mathrm{turnover}}(t)}{\lambda_{\max}} \right)$$
     Measures operational safety headroom relative to external telemetry capacity limits $(N_{\max}, \lambda_{\max})$ established by Ava Labs engineering benchmarks. Informs whether a parameter configuration breaches P2P gossip or PlatformVM throughput capacity.

6. **Parameter Selection under Uncertainty (PSuU):**
   Execute structured parameter sweeps across uncertain policy, behavioral, and macroeconomic dimensions:
   - Policy parameters: $S_{\mathrm{floor}} \in [500, 2{,}000]$ AVAX, $S_{\mathrm{short}} \in [5{,}000, 25{,}000]$ AVAX.
   - Exponent sweep: Canonical baseline $p = 1.0$ evaluated against alternative candidates $p \in \{1.2, 1.5, 2.0, 3.0\}$. No $p$ range is claimed to be universally valid; simulation tests whether curvature flexibility produces material value over the linear harmonic baseline.
   - Yield-sensitivity scenarios: Scenarios Y1 (Low), Y2 (Moderate), and Y3 (High).
   - Macroeconomic stress scenarios: Exploratory price assumptions ($25 AVAX and $15 AVAX) and volatile price cycles, explicitly treated as stress assumptions for parameter exploration rather than empirically established economic thresholds.
   - Perform global variance decomposition to determine which parameters dominate MOE outcomes, which have marginal impact, and where parameter combinations are robust.

7. **Deferred Empirical Calibration Questions:**
   - The simulation methodology strictly distinguishes: *Observed from history* vs. *Calibrated from history* vs. *Assumed for scenario testing* vs. *Not yet identifiable from available data*.
   - The lack of historical yield variation is a limitation on estimating yield sensitivity, not a limitation on reconstructing validator behavior generally.
   - ACP-285 / Helicon data is formally treated as the beginning of the empirical calibration opportunity for yield sensitivity, to be monitored as post-policy observations accumulate over relevant renewal cycles, while the simulation framework proceeds immediately.

**Output:** Comprehensive PSuU Stress-Test Report containing:
1. Empirical validator population and profile baseline characteristics.
2. Sensitivity ranking across MOE 1 through MOE 5 under low, moderate, and high yield responsiveness.
3. Robustness heatmaps identifying feasible $(S_{\mathrm{floor}}, S_{\mathrm{short}}, p)$ operational envelopes.
4. Comparative outcome analysis of the canonical baseline $p = 1$ versus candidate $p > 1$ curves across all five MOEs to examine structural trade-offs without forcing an artificial single-score ranking.
5. Network-capacity headroom compliance verification.

---

# 5. External Scenarios Carried in Parallel

Unresolved Foundation and Ava Labs decisions are treated as analytical scenarios rather than research blockers.

### Scenario Set 1: Duration Lower Bound

* **Scenario 1A:** \(d_{\min}=2\) days.
* **Scenario 1B:** \(d_{\min}=14\) days.

### Scenario Set 2: Short-End Hurdle

* **Scenario 2A:** Capital-time benchmark:

  $$
  S_{\mathrm{short}}=14{,}000
  $$

  under \(d_{\min}=2\) days.

* **Scenario 2B:** Higher short-end barriers explored as security scenarios.

* **Generic representation:**

  $$
  S_{\mathrm{short}}
  \in
  [S_{\mathrm{short}}^L,S_{\mathrm{short}}^H].
  $$

The final value remains unresolved until the economic and security analysis is complete.

### Scenario Set 3: Consensus Capacity

* **Scenario 3A:** Use a validated P2P/consensus latency response model.
* **Scenario 3B:** Treat network capacity as an external dependency until such a model is available.

---

# 6. Verification and Execution Boundaries

**Planning Mode Discipline:** No production code modifications or final parameter recommendations are made until the workplan is approved.

**Verification Approach:**

* **Stage 1:** Verify protocol constants and economic accounting.
* **Stage 2:** Verify behavioral findings against the historical renewal panel and clearly document identification limits.
* **Stage 3:** Verify the curve mathematically and specify deterministic implementation requirements.
* **Stage 4:** Verify system behavior through radCAD simulation and compare against available network-capacity evidence.

The work should remain as simple as possible. New mechanisms, variables, or analytical layers should be introduced only when a concrete problem in the existing design requires them.
