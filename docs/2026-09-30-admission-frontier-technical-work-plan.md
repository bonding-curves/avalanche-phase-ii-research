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

## Stage 4: Stress-Test the Mechanism

**Core Question:** Does the mechanism behave acceptably when heterogeneous validators interact?

**Scope:**

1. Implement the candidate frontier in radCAD with validator renewal decisions driven by the Stage 2 behavioral model.

2. Compare:

   $$
   \text{Baseline mechanism}
   $$

   against:

   $$
   \text{Duration-dependent frontier}.
   $$

3. Track:

   $$
   N(t),
   \quad
   N_{\mathrm{churn}}(t),
   \quad
   S_{\mathrm{total}}(t),
   \quad
   HHI(t).
   $$

4. Test the mechanism under relevant stress scenarios.

5. Where validated consensus/network capacity information is available, compare simulated validator population and churn against that capacity.

**Output:** Stress-test report resulting in one of:

1. **Candidate region supported for external review.**
2. **Candidate supported only within a defined parameter range.**
3. **Mechanism fails and requires redesign.**

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
