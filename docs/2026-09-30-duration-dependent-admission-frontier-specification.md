# Duration-Dependent PoS Admission Frontier

## Revised Mechanism Design Specification

**Repository:** `avalanche-phase-ii-research`
**Subsystem:** Avalanche Primary Network Consensus & PlatformVM
**Document Type:** Formal Mechanism Design Specification
**Status:** Revised Working Draft
**Purpose:** Define a duration-dependent self-stake admission frontier and the empirical/simulation procedure used to calibrate and validate it.

---

## Executive Summary

The protocol must choose a minimum self-stake requirement as a function of staking duration:

$$
S_{\min}(d).
$$

The design has three distinct jobs.

1. **Economic floor:** determine the minimum self-stake that remains economically viable for a relevant validator class at long duration.
2. **Duration steering:** make shorter commitments require more self-stake, while longer commitments can access the lower floor.
3. **Network validation:** test whether the resulting validator population and renewal pattern remain within the network's operational limits.

These jobs should not be collapsed into one equation. The admission rule and reward rule remain separate execution mechanisms, but their parameters must be economically consistent. The reward curve determines the reward premium for duration; the admission frontier determines the capital requirement for duration.

The candidate frontier proposed in this specification is the bounded harmonic power family:

$$
S_{\min}(d)=S_{\mathrm{floor}}+\Delta S\,\eta(d)^p,
$$

where

$$
\Delta S=S_{\mathrm{short}}-S_{\mathrm{floor}},
$$

and

$$
\eta(d)=
\frac{\frac1d-\frac1{d_{\max}}}
{\frac1{d_{\min}}-\frac1{d_{\max}}}.
$$

This family is not claimed to be mathematically unique. It is selected because it satisfies the required endpoint conditions exactly and provides one interpretable shape parameter, \(p\), that can be calibrated and stress-tested.

No final numerical values for \(S_{\mathrm{short}}\), \(S_{\mathrm{floor}}\), or \(p\) are claimed by this document. Those values are outputs of subsequent empirical and simulation stages.

---

# 1. Protocol Context

## 1.1 Admission Action

A validator candidate chooses:

$$
a_i=(S_i,d_i),
$$

where \(S_i\) is self-stake and \(d_i\) is commitment duration.

The admission gate is:

$$
G(S_i,d_i)=
\begin{cases}
1,&S_i\ge S_{\min}(d_i),\\
0,&S_i<S_{\min}(d_i).
\end{cases}
$$

The gate answers one question only:

> Is this validator's proposed stake-duration pair admissible?

The reward system answers a different question:

> Given an admissible duration, what reward does the validator receive?

These mechanisms remain separate in execution.

## 1.2 Economic Co-Consistency

Execution separation does not imply economic independence.

The combined mechanism is:

$$
M(S,d)=\big(G(S,d),R(d)\big).
$$

A duration can be technically admissible but economically unattractive to all relevant validator types. That would create an unused region of the mechanism even though the state transition rule accepts it.

Therefore parameter calibration must check both sides:

$$
\text{Admission requirement }S_{\min}(d)
$$

and

$$
\text{Reward incentive }R(d).
$$

The design does **not** require every admissible duration to be chosen. It requires that policy-supported duration regions are not made economically empty by the interaction of the two schedules.

---

# 2. Hard Protocol Constraints

## 2.1 Duration Domain

$$
d\in[d_{\min},d_{\max}],
\qquad d_{\max}>d_{\min}>0.
$$

The actual protocol values used for implementation must be taken from the verified PlatformVM specification for the target network version.

## 2.2 Delegator Firewall

Delegation is subject to the validator/delegator duration ordering:

$$
d_{\mathrm{del,min}}\le d_{\mathrm{del}}\le d_{\mathrm{val}}.
$$

Thus validators with

$$
d<d_{\mathrm{del,min}}
$$

cannot receive ordinary delegations.

The important effect does not end exactly at the delegation minimum. For a validator of duration \(d\ge d_{\mathrm{del,min}}\), a new delegator can only enter while at least \(d_{\mathrm{del,min}}\) time remains.

Define the delegation-access ratio:

$$
A_{\mathrm{del}}(d)=
\max\left(0,\frac{d-d_{\mathrm{del,min}}}{d}\right).
$$

Examples:

$$
A_{\mathrm{del}}(d_{\mathrm{del,min}})=0,
$$

$$
A_{\mathrm{del}}(d_{\mathrm{del,min}}+1\text{ day})
\approx \text{very small},
$$

and

$$
A_{\mathrm{del}}(2d_{\mathrm{del,min}})=\frac12.
$$

The interval immediately above the delegation minimum is therefore a **delegation-friction region**, not a clean transition from “no delegation” to “full delegation.”

This effect enters validator behavior through the value of receiving delegation. It is not imposed as a hard exclusion from the admission curve.

---

# 3. Design Requirements for the Admission Frontier

The admission curve must satisfy five practical requirements.

## Requirement 1: Exact Endpoints

The policy specifies:

$$
S_{\min}(d_{\min})=S_{\mathrm{short}},
$$

$$
S_{\min}(d_{\max})=S_{\mathrm{floor}}.
$$

The curve must hit both values exactly.

## Requirement 2: Monotone Decrease

For interior durations:

$$
S'_{\min}(d)<0,
\qquad d\in[d_{\min},d_{\max}).
$$

Longer commitment must never require more minimum self-stake under this mechanism.

## Requirement 3: Interior Convexity

The desired shape is convex over the interior:

$$
S''_{\min}(d)>0,
\qquad d\in(d_{\min},d_{\max}).
$$

The interpretation is simple: reducing duration near the short end should incur a larger incremental capital requirement than reducing duration near the long end.

This is a **shape requirement**, not by itself a proof of intertemporal anti-splitting behavior. That behavioral property must be tested separately.

## Requirement 4: No Interior Collapse

The curve must retain economically meaningful differentiation across the intermediate duration range.

For a chosen validation interval \(I\subset(d_{\min},d_{\max})\), define a minimum acceptable marginal effect \(\kappa_{\min}\). Require either a derivative condition such as

$$
|S'_{\min}(d)|\geq\kappa_{\min},
\qquad d\in I,
$$

or, preferably for implementation, a discrete finite-difference condition such as

$$
S_{\min}(d_a)-S_{\min}(d_b)\geq\Gamma_{\min}
$$

for selected intermediate duration pairs \(d_a<d_b\).

This requirement is what prevents a hockey-stick curve in which nearly all of the stake change occurs close to the shortest duration.

## Requirement 5: Finite Terminal Sensitivity

The curve must approach the long-duration floor without a derivative cliff:

$$
\lim_{d\to d_{\max}^{-}}|S'_{\min}(d)|<\infty.
$$

No stronger terminal-curvature claim is required by the mechanism. In particular, the endpoint is not required to have strictly positive second derivative.

---

# 4. Economic Determination of the Floor

The long-duration floor should be economically grounded rather than treated as an arbitrary curve parameter.

Let a validator type be:

$$
\theta_i=(w_i,c_i,\tau_i),
$$

where:

* \(w_i\): liquid capital available for staking;
* \(c_i\): opportunity cost of capital;
* \(\tau_i\): preferred operating horizon.

For a validator using self-stake \(S\) for duration \(d\), define expected net economic value relative to the validator's outside option as

$$
V_i(S,d)=
PV\big(R_i(S,d)\big)
-C_{\mathrm{op},i}(d)
-C_{\mathrm{cap},i}(S,d)
-U_{\mathrm{outside},i}.
$$

The capital cost term can be represented as an opportunity cost of keeping \(S\) unavailable for the commitment period. The exact functional form and empirical inputs are to be estimated from validator telemetry and operating-cost data.

The floor is then constrained by an individual-rationality condition for the target validator class:

$$
V_i(S_{\mathrm{floor}},d_{\mathrm{max}})\ge0
$$

for at least the intended viable operator class.

This produces an **economic lower bound** for \(S_{\mathrm{floor}}\). It does not mean every validator must be profitable at that floor, nor does it make the floor a universal equilibrium stake.

---

# 5. Behavioral Determination of the Duration Pivot

The duration pivot is not chosen only from curve geometry. It should be anchored in validator behavior.

For each candidate duration \(d\), define validator utility as a function of reward, capital cost, operating cost, delegation access, and duration preference:

$$
U_{i,d}=
R_i(d)
-C_{\mathrm{cap},i}(S_{\min}(d),d)
-C_{\mathrm{op},i}(d)
+B_i\big(A_{\mathrm{del}}(d)\big)
-\beta_{\mathrm{dur}}g(d,\tau_i)
+\varepsilon_{i,d}.
$$

The exact specification of \(g\) is an empirical model choice. The parameter \(\beta_{\mathrm{dur}}\) measures the behavioral penalty associated with commitment duration.

A discrete-choice model can then estimate:

$$
P_i(d)=P(d\mid\theta_i).
$$

The empirical input is the historical renewal panel. The model should use observed transitions between one completed staking period and the validator's next chosen duration.

The pivot is then defined as a duration or transition region where the mechanism obtains a useful increase in commitment persistence without producing an excessive increase in predicted exits among relevant validator types.

The pivot is therefore an empirical output, not an arbitrary point selected to make the curve look attractive.

---

# 6. Candidate Admission Curve

Define the normalized bounded harmonic coordinate:

$$
\eta(d)=
\frac{\frac1d-\frac1{d_{\max}}}
{\frac1{d_{\min}}-\frac1{d_{\max}}}.
$$

Equivalently, for implementation:

$$
\eta(d)=
\frac{d_{\min}(d_{\max}-d)}
{d(d_{\max}-d_{\min})}.
$$

The candidate family is:

$$
\boxed{
S_{\min}(d)=S_{\mathrm{floor}}+
\Delta S\,\eta(d)^p
}
$$

with

$$
\Delta S=S_{\mathrm{short}}-S_{\mathrm{floor}}.
$$

This family has the required exact boundaries:

$$
\eta(d_{\min})=1,
\qquad
\eta(d_{\max})=0.
$$

Therefore:

$$
S_{\min}(d_{\min})=S_{\mathrm{short}},
$$

$$
S_{\min}(d_{\max})=S_{\mathrm{floor}}.
$$

For \(p\ge1\), the function is decreasing and convex on the open interior.

The parameter \(p\) controls how strongly the stake requirement is concentrated toward the short-duration end:

* lower \(p\): the stake reduction is spread more broadly across durations;
* higher \(p\): the stake reduction is concentrated closer to \(d_{\min}\).

Therefore \(p\) is not free. It must pass the intermediate-duration differentiation test in Requirement 4.

---

# 7. Why the Other Families Are Not Selected

## 7.1 Iso-Commitment

$$
S(d)=C/d.
$$

This family can satisfy monotonicity and convexity, but one parameter cannot generally hit both sovereign boundary values:

$$
S(d_{\min})=S_{\mathrm{short}},
\qquad
S(d_{\max})=S_{\mathrm{floor}}.
$$

Calibrating to one endpoint creates a residual at the other. It is therefore not selected.

## 7.2 Standard Hyperbola

$$
S(d)=S_{\mathrm{floor}}+K/d.
$$

Calibrating it at \(d_{\min}\) leaves a positive residual above \(S_{\mathrm{floor}}\) at \(d_{\max}\). It is therefore not selected without additional normalization.

## 7.3 Shifted Power Law

$$
S(d)=S_{\mathrm{floor}}+\Delta S(d_{\min}/d)^\alpha.
$$

This has the correct short endpoint but not the exact long endpoint for finite \(\alpha\). Increasing \(\alpha\) can reduce the terminal residue, but for sufficiently large \(\alpha\) it also concentrates almost all slope near the short end. The family is therefore not rejected because every \(\alpha\) is pathological; it is rejected as the preferred exact two-boundary family because the boundary and interior-shape tradeoff becomes undesirable.

## 7.4 Bounded Harmonic Power

The bounded harmonic power family is selected as the working candidate because it exactly satisfies both endpoints while exposing a single explicit shape parameter for empirical calibration and stress testing.

No uniqueness theorem is asserted.

---

# 8. Calibration Procedure

The parameterization is calibrated in this order.

### Step 1: Determine \(S_{\mathrm{floor}}\)

Estimate the economically viable long-duration floor from operating-cost and opportunity-cost data.

### Step 2: Determine \(d_{\mathrm{pivot}}\)

Estimate validator duration preferences and renewal responses using the structural discrete-choice model. Include delegation-access friction in the utility model.

### Step 3: Solve for \(p\)

Impose the pivot condition:

$$
S_{\min}(d_{\mathrm{pivot}})=S_{\mathrm{pivot}}.
$$

Then:

$$
p=
\frac{
\ln\left(
\frac{S_{\mathrm{pivot}}-S_{\mathrm{floor}}}
{\Delta S}
\right)
}{
\ln \eta(d_{\mathrm{pivot}})
}.
$$

### Step 4: Reject invalid \(p\)

The solved \(p\) must satisfy the shape tests:

1. exact endpoints;
2. monotone decrease;
3. interior convexity;
4. minimum intermediate-duration differentiation;
5. finite terminal first-derivative behavior;
6. consensus-safe integer implementation.

If the pivot generates an unacceptable \(p\), do not force the curve. Revisit the pivot condition or the underlying behavioral assumptions.

This is important: **the pivot and \(p\) are jointly constrained.** A pivot that produces an extreme \(p\) is evidence that the chosen economic target and curve family are incompatible, not a reason to hide the resulting exponent.

---

# 9. Consensus-Safe Integer Representation

The continuous function is a design specification. PlatformVM requires a deterministic integer implementation.

The implementation therefore uses the cleared-fraction form:

$$
\eta(d)=
\frac{d_{\min}(d_{\max}-d)}
{d(d_{\max}-d_{\min})}.
$$

The final implementation specification must define:

* integer units for duration;
* fixed-point scale factor;
* multiplication order;
* overflow bounds;
* rounding direction;
* exact endpoint handling;
* deterministic evaluation of the power term;
* proof that quantization does not violate the floor or invert the intended duration ordering.

A consensus implementation must be treated as a distinct discrete function, not assumed to be identical to the real-valued design curve.

For non-integer \(p\), the implementation choice must be explicit. Candidate options are a rational approximation \(p=a/b\), a deterministic fixed-point approximation, or a restricted integer exponent. The final choice is an implementation decision and should not be hidden inside the mathematical notation.

---

# 10. Structural Validator Choice Model

The digital twin should not contain an informal instruction such as “the validator selects \(d^*\).” The choice rule must be explicit.

For each validator type \(\theta_i\), evaluate utility over the admissible duration set:

$$
U_{i,d}=U(d;\theta_i,S_{\min},R,A_{\mathrm{del}})+\varepsilon_{i,d}.
$$

The empirical model estimates the relationship between observable validator characteristics and renewal choices.

The main behavioral output is the estimated duration choice distribution:

$$
P_i(d).
$$

The model should report:

* estimated duration penalty parameters;
* predicted renewal probabilities;
* predicted exit probability by validator type;
* sensitivity of renewal behavior to reward differences;
* sensitivity of participation to the admission frontier.

This is the bridge between historical econometrics and simulation.

---

# 11. Digital Twin

The radCAD model represents validators as agents with:

$$
v_i=(S_i,d_i,\tau_{\mathrm{rem},i},\theta_i).
$$

At renewal, an agent evaluates the structural choice model, selects a duration, computes the corresponding minimum stake, and enters only if capital-feasible.

For a validator whose chosen duration is \(d_i\), phase-randomized initialization may use:

$$
\tau_{\mathrm{rem},i}\sim U(0,d_i)
$$

with the appropriate discrete-time implementation.

The simulator tracks at minimum:

$$
N(t),
\quad
S_{\mathrm{total}}(t),
\quad
N_{\mathrm{churn}}(t),
\quad
HHI(t).
$$

Network capacity is represented separately through a calibrated latency model:

$$
L(t)=f\big(N(t),\lambda_{\mathrm{churn}}(t),\text{network conditions},\ldots\big).
$$

The hard operational condition is:

$$
L(t)\le L_{\mathrm{budget}}.
$$

The corresponding \(N_{\max}\) is derived from measured or otherwise validated network capacity rather than assumed.

The objective of the digital twin is therefore not to “prove” the curve is safe. It is to test whether the proposed mechanism remains within the stated operational constraints under defined stress scenarios.

---

# 12. Validation Matrix

The calibrated mechanism should be evaluated under a common set of controlled experiments.

| Test                 | Question                                                               | Output                          |
| -------------------- | ---------------------------------------------------------------------- | ------------------------------- |
| Economic viability   | Can relevant validator types operate at \(S_{\mathrm{floor}}\)?        | IR / solvency margin            |
| Duration choice      | Does the reward-plus-admission schedule shift renewal behavior?        | \(P(d)\), exit rate             |
| Delegation friction  | How does limited delegation access affect near-14-day validators?      | delegation access / utility     |
| Curvature            | Does \(p\) preserve differentiation across intermediate tenures?       | finite differences / elasticity |
| Churn                | Does the frontier reduce high-frequency turnover relative to baseline? | churn distribution              |
| Validator population | Does the mechanism produce a stable active set?                        | \(N^*\) distribution            |
| Concentration        | Does the mechanism materially change stake concentration?              | HHI / quantiles                 |
| Consensus capacity   | Does the resulting population remain inside the P2P latency budget?    | \(L/L_{\mathrm{budget}}\)       |
| Quantization         | Does consensus arithmetic preserve the intended curve properties?      | integer implementation audit    |

KPI results are empirical outputs. They are not treated as identities merely because the admission gate mechanically enforces a minimum stake.

---

# 13. Decision Rules

A candidate parameter set \((S_{\mathrm{short}},S_{\mathrm{floor}},p)\) is admissible only if all mandatory constraints pass.

### Hard constraints

$$
S_{\mathrm{short}}>S_{\mathrm{floor}}>0,
$$

$$
d_{\min}<d_{\max},
$$

$$
S_{\min}(d_{\min})=S_{\mathrm{short}},
$$

$$
S_{\min}(d_{\max})=S_{\mathrm{floor}},
$$

and the integer implementation preserves the ordering and floor.

### Behavioral constraints

The estimated choice model must show that the mechanism does not create an economically empty policy-supported region and must quantify the participation effects of duration changes.

### Network constraints

The digital twin must demonstrate that the resulting validator population and churn process remain within the calibrated consensus/P2P operating envelope for the specified stress scenarios.

A candidate that fails any hard constraint is rejected. A candidate that passes hard constraints but fails behavioral or network validation is not promoted to a protocol recommendation.

---

# 14. What This Specification Claims

This specification establishes a methodology for constructing and testing a duration-dependent admission frontier.

It does claim that the bounded harmonic power family is a useful candidate functional form with exact two-boundary interpolation and a single explicit shape parameter.

It does not claim that the family is mathematically unique.

It does not claim that convexity alone proves anti-Sybil or anti-splitting behavior.

It does not claim that admission and rewards can be calibrated independently without checking their economic interaction.

It does not claim that a simulated equilibrium is automatically safe unless the P2P/consensus capacity model is specified and validated.

The final protocol recommendation is therefore the result of four linked stages:

$$
\boxed{
\text{Economics}
\rightarrow
\text{Behavior}
\rightarrow
\text{Admission Curve}
\rightarrow
\text{Digital-Twin Validation}
}
$$

with consensus implementation as the final engineering gate.

---

# 15. Next Work

1. Calibrate the economic floor \(S_{\mathrm{floor}}\) from cost-of-capital and operating-cost data.
2. Estimate the structural duration-choice model from the historical renewal panel.
3. Quantify the delegation-access effect and identify plausible pivot regions.
4. Solve for \(p\) from the pivot condition and reject values that fail the interior differentiation tests.
5. Implement the curve with deterministic integer/fixed-point arithmetic.
6. Run radCAD stress tests over the accepted parameter region.
7. Compare the resulting validator population and churn dynamics with the relevant baseline.
8. Produce a final parameter recommendation only after the economic, behavioral, and network constraints have all been evaluated.
