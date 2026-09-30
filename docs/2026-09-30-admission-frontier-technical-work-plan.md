# Duration-Dependent PoS Admission Frontier

## Simple Research Work Plan

### Goal

Determine whether a duration-dependent minimum self-stake curve is a defensible mechanism for the Avalanche Primary Network and, if so, determine the range of parameters that should be considered.

The core mechanism remains:

$$
S_{\min}(d)
=
S_{\mathrm{floor}}
+
\Delta S\,\eta(d)^p
$$

where:

$$
\Delta S=S_{\mathrm{short}}-S_{\mathrm{floor}}.
$$

The research proceeds in four stages.

---

## Stage 1: Establish the Economic and Protocol Boundaries

### Question

What should the two ends of the curve mean?

We need to establish:

$$
d_{\min},\quad d_{\max},\quad
S_{\mathrm{floor}},\quad
S_{\mathrm{short}}.
$$

### Work

First, confirm the protocol regime being studied.

If the final activation regime is not yet confirmed, analyze the relevant alternatives rather than stopping the research.

Second, estimate $S_{\mathrm{floor}}$ from validator economics:

$$
\text{Rewards}
-
\text{Operating Cost}
-
\text{Capital Opportunity Cost}
\geq0.
$$

The purpose is not to find one magical number. It is to establish a plausible economic range.

Third, determine how $S_{\mathrm{short}}$ should be constrained.

Use the legacy capital-time relationship as a benchmark and separately examine whether the resulting short-end barrier is sufficient to address the intended churn/security problem.

### Output

A table of:

$$
d_{\min},\ d_{\max},\
S_{\mathrm{floor}},\
S_{\mathrm{short}}
$$

with each value labelled as:

* confirmed protocol input;
* empirical estimate;
* design assumption;
* unresolved external input.

---

## Stage 2: Understand Validator Behavior

### Question

How do validators trade off duration, reward, capital lockup, and delegation access?

### Work

Use the historical renewal data to study:

* which durations validators actually choose;
* when validators renew or exit;
* how behavior differs across validator capital levels;
* how reward differences relate to duration choice;
* how the 14-day delegation requirement affects shorter-duration validators.

Define the delegation-access ratio:

$$
A_{\mathrm{del}}(d)
=
\max\left(
0,
\frac{d-d_{\mathrm{del,min}}}{d}
\right).
$$

The first goal is not to build the most sophisticated possible econometric model.

The first goal is to obtain a reliable empirical picture of:

$$
\text{duration}
\rightarrow
\text{validator response}.
$$

A structural discrete-choice model can then be used where the data support it.

### Pivot

Use the behavioral results to identify a **candidate pivot region**:

$$
d_{\mathrm{pivot}}.
$$

The pivot represents the point where increasing commitment duration appears to produce a useful behavioral benefit without imposing excessive participation loss.

Do not force one exact pivot if the evidence only supports a range.

### Output

A behavioral report containing:

$$
\hat{\beta}_{\mathrm{dur}},
\quad
\text{renewal probabilities},
\quad
\text{exit response},
\quad
d_{\mathrm{pivot}}\text{ range}.
$$

---

## Stage 3: Construct and Test the Admission Curve

### Question

Given the economic boundaries and behavioral pivot, what curve should the protocol use?

Use the bounded harmonic family:

$$
S_{\min}(d)
=
S_{\mathrm{floor}}
+
\Delta S
\left[
\frac{
\frac1d-\frac1{d_{\max}}
}{
\frac1{d_{\min}}-\frac1{d_{\max}}
}
\right]^p.
$$

The curve must satisfy:

$$
S_{\min}(d_{\min})
=
S_{\mathrm{short}}
$$

and

$$
S_{\min}(d_{\max})
=
S_{\mathrm{floor}}.
$$

Use the pivot to solve for $p$:

$$
p=
\frac{
\ln
\left(
\frac{S_{\mathrm{pivot}}-S_{\mathrm{floor}}}
{S_{\mathrm{short}}-S_{\mathrm{floor}}}
\right)
}{
\ln \eta(d_{\mathrm{pivot}})
}.
$$

Then test the resulting curve.

### The tests are simple

Does it:

1. decrease with duration?
2. remain convex over the intended interior?
3. avoid becoming flat too early?
4. reach the floor exactly?
5. remain sensible across the important duration range?

If a solved $p$ produces a hockey-stick curve, reject that parameter combination and revisit the pivot/boundary assumptions.

### Implementation

Only after the mathematical curve passes the tests, specify the deterministic integer/fixed-point implementation.

The implementation question is:

> Can the mathematical curve be represented safely and deterministically in PlatformVM?

Do not constrain the research model to integer $p$ before knowing whether that is actually necessary.

### Output

A candidate parameter region:

$$
(S_{\mathrm{floor}},
S_{\mathrm{short}},
d_{\mathrm{pivot}},
p)
$$

plus the deterministic implementation specification.

---

## Stage 4: Stress-Test the Mechanism

### Question

Does the mechanism behave acceptably when many heterogeneous validators interact?

Implement the mechanism in radCAD.

Let validators choose duration using the behavioral model from Stage 2.

Compare at least:

$$
\text{Baseline mechanism}
$$

against:

$$
\text{Duration-dependent frontier}.
$$

Track:

$$
N(t)
$$

validator population,

$$
N_{\mathrm{churn}}(t)
$$

validator turnover,

$$
S_{\mathrm{total}}(t)
$$

total stake,

and concentration measures such as HHI.

Then stress the system under different conditions.

The purpose is not to prove that the mechanism is universally safe.

The purpose is to determine:

> Under what conditions does it work, and where does it fail?

Finally, compare the simulated validator population and churn against the actual network capacity information available from Avalanche/Ava Labs.

If a validated P2P/consensus latency model exists, test:

$$
L(N,\lambda_{\mathrm{churn}})
\leq
L_{\mathrm{budget}}.
$$

If it does not yet exist, identify that as an external engineering dependency rather than inventing a threshold.

### Output

A final result of one of three forms:

1. **Candidate accepted for external review**
2. **Candidate accepted only within a defined parameter range**
3. **Current mechanism fails and requires redesign.**

---

# External Questions We Carry in Parallel

Some questions cannot be answered by the research team alone.

Examples include:

* $d_{\min}$ for the final activation regime,
* the intended validator population,
* the final security requirement for the short-duration boundary,
* the PlatformVM implementation constraints,
* the hard-fork migration policy, and
* the validated P2P latency budget.

These should be recorded as **External Inputs**, not treated as blockers.

Where possible, run scenarios around them.

For example:

$$
d_{\min}=2\text{ days}
$$

and

$$
d_{\min}=14\text{ days}.
$$

Then show how the results differ.

When Foundation or Ava Labs provides the authoritative input, substitute it into the existing analysis.

---

# Final Research Pipeline

The entire project can therefore be remembered as:

$$
\boxed{
\text{1. Economics}
\rightarrow
\text{2. Behavior}
\rightarrow
\text{3. Curve}
\rightarrow
\text{4. Stress Test}
}
$$

Or in plain language:

**How much stake is economically viable?**

↓

**How do validators respond to duration?**

↓

**What curve best implements that relationship?**

↓

**Does the resulting system behave safely?**

That is the core work.

Everything else is supporting evidence, implementation detail, or an external dependency.
