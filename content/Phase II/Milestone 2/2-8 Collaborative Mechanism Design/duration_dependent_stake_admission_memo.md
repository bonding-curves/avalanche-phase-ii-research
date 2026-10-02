# Technical Mechanism Design Memo: Duration-Dependent Consensus Admission Frontiers ($S_{\min}(d)$)

| Field | Value |
| :--- | :--- |
| **Author** | Hasher Nabi ([@coad1024-cmd](https://github.com/coad1024-cmd)), Bonding Curves Research Group (BCRG) |
| **Topic** | Duration-Dependent Validator Admission and Consensus Security |
| **Audience** | Avalanche Foundation |
| **Date** | October 2, 2026 |
| **Status** | Research Working Paper / Mechanism Design Investigation |
| **Target Review Gate** | Model v0.7.0 Handoff & Milestone 2 Collaborative Mechanism Review (October 2, 2026) |
| **Artifact Codebase** | `src/avalanche_research/admission_frontier.py` & `BoundedHarmonicFrontier` |

---

## 1. Executive Summary

In proof-of-stake protocols, validator stake and staking duration jointly determine the economic commitment required to participate in consensus sampling. In Avalanche's Primary Network, consensus admission has historically been governed by two static constraints: a minimum self-stake requirement of $2{,}000\text{ AVAX}$ and a minimum staking duration of $14\text{ days}$. 

As the protocol evolves through recent and proposed upgrades—including the Helicon upgrade series, discussions surrounding ACP-273 (shortened staking durations), and community initiatives to broaden validator decentralization—proposals have emerged to adjust these parameters. However, changing minimum duration and minimum stake as independent, uncoupled static scalars creates structural mechanism-design risks:

- `[DERIVED]` **The Decoupled Parameter Dilemma:** Lowering minimum duration (e.g., to 48 hours) and minimum stake (e.g., to 500 AVAX) independently collapses the minimum capital-time commitment from the historical baseline of $28{,}000\text{ AVAX-days}$ down to $1{,}000\text{ AVAX-days}$—a 96.43% reduction in the economic barrier to occupying an active consensus slot.
- `[HYPOTHESIS]` **Operational Vulnerabilities:** Decoupled reductions lower the cost of high-frequency validator churning, elevate Snowman consensus sampling variance, and increase PlatformVM state-transition overhead (frequent BLS key additions and UTXO state churn).
- `[OBSERVED]` **Empirical Concentration:** Analysis of 57,067 completed validator stints across 7,635 nodes reveals heavy clustering at the historical minimum boundaries (74.8% bond between 2,000 and 6,000 AVAX; 58.97% select durations $\le 30\text{ days}$), indicating that validator operators are highly sensitive to protocol entry thresholds.

To resolve these tensions, this research investigates **duration-dependent admission frontiers** ($S_{\min}(d)$), wherein the minimum required self-stake is a decreasing function of commitment duration:

1. **Earned Decentralization:** The mechanism is designed to enable lower-capital sovereign operators to access consensus validation by committing capital over longer time horizons, while the exact stake-duration trajectory remains subject to simulation sweeps and engineering validation.
2. **Anti-Churn & Sybil Defense:** Short-duration commitments require substantially greater economic commitment than long-duration commitments, ensuring that reducing lockup duration does not reduce the economic barrier to consensus participation.
3. **Continuity with Historical Participation:** The research establishes an analytical framework to evaluate how existing validator cohorts are affected under candidate admission geometries, treating continuity as an objective to quantify and calibrate rather than an assumed fixed constraint.
4. **Architectural Feasibility:** Evaluating discrete integer schedules to ensure deterministic consensus validation within PlatformVM without floating-point arithmetic.

This memorandum presents the theoretical foundations, empirical baseline, design axioms, candidate functional forms, behavioral mechanics, and exploratory sensitivity analyses of duration-dependent admission frontiers. It outlines what has been mathematically established versus what requires dynamic simulation in forthcoming digital-twin modeling, culminating in four structured questions for Avalanche Foundation leadership.

---

## 2. Research Question & Protocol Context

### 2.1 The Evolving Consensus Landscape
Avalanche's Primary Network relies on Snowman consensus, a metastable consensus mechanism where validators repeatedly sample random subsets ($k=20$) of the active validator set. The security and performance of this mechanism depend upon validator set stability, representative stake weighting, and bounded churn in network membership.

Recent protocol discussions have highlighted two distinct, competing desires:
1. **Liquidity and Capital Efficiency:** Staking capital locked for long windows incurs substantial liquidity opportunity costs. Reducing minimum lockup durations allows market participants, liquid staking providers, and institutional treasuries to manage liquidity more responsively.
2. **Validator Decentralization:** The historical $2{,}000\text{ AVAX}$ self-stake floor represents a significant capital barrier for solo, home, and sovereign operators. Lowering this threshold aims to expand node counts and geographical distribution.

When evaluated in isolation, each goal appears desirable. However, in an economic engineering system, these parameters cannot be separated from the cost of consensus influence.

### 2.2 Qualification of the Tinbergen Separation Heuristic
A classical concept in economic policy design is the **Tinbergen Separation Principle**, which posits that achieving $N$ independent policy targets requires at least $N$ independent policy instruments. In preliminary mechanism discussions, Tinbergen separation has been cited to argue that admission rules should govern node counts, reward curves should govern duration, and fees should govern state churn:

```
                      [ Dynamic Protocol Feedback ]
        +-------------------------------------------------------+
        |                                                       |
        v                                                       |
[ Admission Rule S_min(d) ] ---> [ Validator Entry / Stint Choice ]
        ^                               |
        |                               v
[ Macro Yield Curve ARR(d) ] <--- [ Aggregate Staked Supply & Churn ]
        |                               |
        +-------------------------------+
```

> [!NOTE]
> **Tinbergen as a Guiding Heuristic, Not a Dynamic Law:**  
> While Tinbergen separation provides a useful first-order organizing heuristic for distinguishing between policy objectives, **it is insufficient as a complete framework for a dynamic protocol system**.

In a decentralized proof-of-stake protocol:
- Policy instruments are dynamically coupled through behavioral feedback loops.
- An adjustment to admission rules ($S_{\min}(d)$) alters the composition and duration distribution of validators.
- Changes in validator duration and count alter aggregate circulating supply, delegation capacity, consensus sampling load, and fee consumption.
- These state changes, in turn, shift the equilibrium yield delivered by reward mechanisms (such as ACP-285 consumption rate curves) and change the operational viability of node operators.

Therefore, this research treats admission rules not as isolated static levers, but as an interactive component of a broader economic-engineering digital twin.

---

## 3. Empirical Baseline (57,067 Staking Periods, 7,635 Nodes)

To ground the mechanism design in verified empirical reality, this investigation examines the primary dataset (`01-renewal-panel.parquet`), which captures 57,067 completed validator stints across 7,635 unique physical node IDs from Genesis through August 13, 2026 (the pre-Helicon baseline).

*(Note: Helicon activated on September 22, 2026. All historical stints in this baseline were executed under the $d \ge 14\text{ days}$ and $S \ge 2{,}000\text{ AVAX}$ constraints. Prospective sub-14-day commitments represent an unobserved regime).*

### 3.1 Distributional Observations
- `[OBSERVED]` **Clustering at the Capital Boundary:** Validator self-stake exhibits extreme clustering at the protocol floor. The historical median self-stake is $2{,}015\text{ AVAX}$ (mean: $97{,}264\text{ AVAX}$). Exactly **74.8% of all validator stints (42,710 stints)** were initiated with self-bonds between $2{,}000\text{ AVAX}$ and $6{,}000\text{ AVAX}$.
- `[OBSERVED]` **Duration Skewness:** The unweighted median staking duration across historical records is $23.0\text{ days}$ (mean: $45.6\text{ days}$). Commitments of exactly $14\text{ days}$ represent **16.38% of all stints (9,347 records)**. Commitments $\le 30\text{ days}$ account for **58.97% (33,654 records)**. Conversely, full-year commitments ($365\text{ days}$) represent only **4.10% (2,340 records)**.
- `[OBSERVED]` **Capital-Duration Divergence:** Small operators overwhelmingly choose minimum durations, whereas large institutional pools lock for longer horizons ($\text{Corr}(\log S, \log d) = +0.246$). Commitments under 16 days represented 62% to 69% of new stints during the Durango and Fortuna network phases, but accounted for only 3% to 5% of committed AVAX-days.
- `[OBSERVED]` **Renewal Inertia:** Consecutive stints by the same node operator display strong behavioral persistence ($\text{Corr}(d_t, d_{t-1}) = 0.690$). Approximately **44.54% of renewing validators repeat their exact previous duration**, and **75.32% remain within the same duration cohort**. Under a 7-day return window, the historical renewal rate is 80.7% across 2021–2024 and 78.1% across 2025 to Granite.

### 3.2 Factual Forensic Context: August 2025 Restructuring
Prior informal analyses hypothesized that a large drop in validator node counts in August 2025 reflected an adversarial Sybil attack or retail exodus. Detailed forensic decomposition of on-chain event logs refutes this hypothesis:
- `[OBSERVED]` Between August 1, 2025, and September 1, 2025, the network experienced 602 gross validator expirations and 96 new entries (a net decline of 506 active nodes).
- `[OBSERVED]` The top five exiting entities accounted for **472 of the 602 gross expirations (78.4%)**:
  1. *Liquid Staking Pool Rebalancing:* GoGoPool operator restructuring accounted for 296 nodes (`avax10f83...`).
  2. *Genesis Holder Consolidation:* An early holder consolidated 85 individual staking nodes into delegation structures (`avax1dwkw...`).
  3. *Subnet Infrastructure Sunsetting:* A single infrastructure provider retired 42 subnet nodes.
  4. *Solo Fleet Wind-Down:* A private multi-node operator wound down 25 nodes.
  5. *Consolidation into High-Stake Nodes:* An institutional operator consolidated 24 distinct 2,000-AVAX nodes into a single large-stake node (`avax134sy...`).

This empirical finding demonstrates that historical validator contractions were driven primarily by institutional treasury rebalancing rather than malicious Sybil swarms, reinforcing that protocol admission rules must account for institutional operational patterns.

---

## 4. The Mechanism Design Problem & The Decoupled Parameter Dilemma

### 4.1 Capital-Time Commitment Geometry
The economic barrier to consensus participation can be conceptualized as the product of capital scale and commitment duration. Under the historical baseline, the minimum commitment invariant ($K_{\text{base}}$) is:

$$K_{\text{base}} = S_{\min} \cdot d_{\min} = 2{,}000\text{ AVAX} \times 14\text{ days} = 28{,}000\text{ AVAX-days}$$

This quantity represents the minimum opportunity cost required to occupy an active consensus slot.

If governance were to lower both parameters independently—for instance, setting an uncoupled floor of $S_{\min} = 500\text{ AVAX}$ and $d_{\min} = 2\text{ days}$—the minimum capital-time commitment collapses:

$$K_{\text{decoupled}} = 500\text{ AVAX} \times 2\text{ days} = 1{,}000\text{ AVAX-days}$$

$$\frac{K_{\text{decoupled}}}{K_{\text{base}}} = \frac{1{,}000}{28{,}000} = 0.0357 \quad (96.43\%\text{ reduction in commitment barrier})$$

![The Decoupled Parameter Dilemma](/Phase-II/Milestone-2/2-8-Collaborative-Mechanism-Design/figures/decoupled_parameter_dilemma.png)

### 4.2 Hazards of Decoupled Admission
Lowering the commitment barrier by 96.43% introduces three primary operational and economic hazards:

1. `[HYPOTHESIS]` **Consensus Sampling Instability:** In Snowman consensus, validators are sampled with probability proportional to stake. An uncoupled 500 AVAX / 2-day regime allows a fixed capital pool (e.g., 28,000 AVAX) to fund 56 simultaneous validator slots rather than 14 slots, or to cycle through 28 sequential 48-hour periods per 28,000 AVAX-days of budget. High turnover among micro-stake validators increases sampling variance and network routing entropy.
2. `[OBSERVED]` **P-Chain State-Transition Overhead:** Historical telemetry indicates that validator registrations and delegation actions represent significant P-Chain write volume. Rapid turnover of 48-hour validators accelerates cryptographic BLS key additions and removals in the active validator set, expanding database commit latency across all verifying nodes.
3. `[HYPOTHESIS]` **Consensus Churn and Re-Registration Friction:** Transient node turnover degrades gossip-layer peer discovery and increases validation overhead without contributing durable capital lockup to the network.

---

## 5. Behavioral Mechanics & The Validator Refusal Rule

To evaluate how node operators respond when an admission frontier is introduced, we formalize the **Validator Refusal Rule**.

When a prospective or renewing validator submits a stint with self-stake $S_i$ and preferred duration $d_i$, the admission engine evaluates whether $S_i \ge S_{\min}(d_i)$. If this condition is violated, the stint is rejected at the protocol boundary. The validator then faces three structural response pathways:

![Validator Consensus Admission and Refusal Architecture](/Phase-II/Milestone-2/2-8-Collaborative-Mechanism-Design/figures/validator_refusal_flowchart.png)

### 5.1 Structural Response Pathways
1. `[HYPOTHESIS]` **Path A: Extend Duration (Earned Decentralization Pathway):**  
   Operators with constrained capital (e.g., exactly $2{,}000\text{ AVAX}$) who desire a short duration (e.g., 7 days) are blocked if $S_{\min}(7) > 2{,}000\text{ AVAX}$. They can qualify by extending their commitment duration to the smallest duration that satisfies the frontier:
   $$d_{\text{feasible}} = \min \{ d \in \mathcal{D} : S_i \ge S_{\min}(d) \}$$
   This pathway allows sovereign home operators to trade liquidity for protocol admission without requiring additional capital.
2. `[HYPOTHESIS]` **Path B: Commit Additional Capital (Capital Addition Pathway):**  
   Operators with strict duration requirements (e.g., institutional market makers or liquidity providers needing a 48-hour lockup) can qualify by injecting additional self-stake:
   $$\Delta S = S_{\min}(d_i) - S_i$$
   This pathway ensures that transient participants pay a proportionate capital commitment to access consensus sampling.
3. `[HYPOTHESIS]` **Path C: Migrate to Delegation or Exit (Non-Consensus Pathway):**  
   Operators who are both capital-constrained and unwilling to extend duration choose not to run an active validator node. They may allocate capital to liquid delegation or alternative on-chain activities. This response filters low-commitment, high-churn actors out of the consensus set while preserving their ability to earn staking yield through delegation.

### 5.2 Interaction with the Three-Layer Delegation Architecture
Consensus self-stake rules operate in conjunction with the network's delegation framework. Concurrent delegation is structurally bounded by protocol rules (delegation capped at $4 \times S_{\text{self}}$, node cap at $3{,}000{,}000\text{ AVAX}$) and market access gates:

| Delegation Layer | Operational Mechanism | Impact on Duration-Dependent Admission |
| :--- | :--- | :--- |
| **Layer 1: Protocol Firewall** | Minimum delegator lockup duration ($d_{\text{del}} \ge 14\text{ days}$). | `[DERIVED]` Validators choosing $d < 14\text{ days}$ cannot receive delegation ($A_{\text{del}}(d) = 0$). |
| **Layer 2: Provider Market Gates** | Liquid staking protocols (e.g., BENQI) impose strict minimum self-stake and fee thresholds. | `[OBSERVED]` Empirical records show that BENQI allocates $<1\%$ of delegated stake to nodes with $S_{\text{self}} < 6{,}000\text{ AVAX}$. |
| **Layer 3: Duration Occupancy Gradient** | Delegators preferentially select nodes with longer remaining tenors. | `[OBSERVED]` Nodes with tenors $\ge 180\text{ days}$ capture $29.5\%$ of delegation capacity vs. $3.7\%$ for short tenors. |

This multi-layer structure reinforces that lowering self-stake at long durations does not automatically confer access to delegated capital unless operators satisfy external market criteria.

---

## 6. Design Axioms and Required Properties

Before selecting or testing specific mathematical functions, we formulate the structural properties that any viable admission frontier $S_{\min}(d)$ should satisfy.

### 6.1 Formal Axioms for Admission Frontiers

- **Axiom 1 (Domain Boundary Validity):**  
  The frontier must be well-defined on the closed interval $d \in [d_{\min}, d_{\max}]$, where $d_{\min} > 0$ and $d_{\max} \ge d_{\min}$. For Avalanche, $d_{\min} = 2\text{ days}$ and $d_{\max} = 365\text{ days}$. The stake requirements at the boundaries must be finite and strictly positive:
  $$0 < S_{\text{floor}} \le S_{\min}(d) \le S_{\text{anchor}} < \infty \quad \forall d \in [d_{\min}, d_{\max}]$$

- **Axiom 2 (Strict Monotonicity):**  
  The required self-stake must be a strictly decreasing function of duration. A longer lockup commitment must strictly reduce or maintain the required capital:
  $$\frac{\partial S_{\min}}{\partial d} < 0 \quad \forall d \in [d_{\min}, d_{\max})$$

- **Axiom 3 (Strict Global Convexity / Diminishing Marginal Relief):**  
  The marginal reduction in required stake per additional day of commitment must be diminishing. The initial extension of duration (e.g., from 2 days to 14 days) should provide greater capital relief than an extension late in the term (e.g., from 300 days to 312 days):
  $$\frac{\partial^2 S_{\min}}{\partial d^2} > 0 \quad \forall d \in [d_{\min}, d_{\max}]$$
  Convexity prevents cliff-edge arbitrage and ensures smooth economic incentives across all commitment tenors.

- **Axiom 4 (Exact Boundary Convergence):**  
  At the maximum staking duration, the function must converge exactly to the designated decentralization floor:
  $$S_{\min}(d_{\max}) = S_{\text{floor}}$$
  At the minimum staking duration, the function must converge to the short-duration anchor:
  $$S_{\min}(d_{\min}) = S_{\text{anchor}}$$

- **Axiom 5 (Continuity and Absence of Arbitrage Discontinuities):**  
  The underlying continuous curve must be continuous ($C^0$) and smooth ($C^1$) across the entire domain, preventing threshold exploitation where an infinitesimal change in duration yields a discrete jump in capital requirements.

- **Axiom 6 (Interpretability and Calibration Tractability):**  
  The functional form should possess parameters with clear economic interpretations (e.g., floor, anchor, curvature) that can be analytically calibrated to specific empirical or policy pivot points $(d_{\text{pivot}}, S_{\text{pivot}})$.

- **Axiom 7 (Quantization Robustness):**  
  The continuous formulation must map monotonically into discrete integer schedules (evaluated in integer time and token units) without introducing inversion steps or rounding ambiguities.

---

## 7. Evaluated Candidate Functional Forms

Five candidate functional forms were evaluated against the design axioms:

![Candidate Admission Frontier Functional Forms](/Phase-II/Milestone-2/2-8-Collaborative-Mechanism-Design/figures/candidate_curve_families.png)

### 7.1 Mathematical Definitions of Candidates

1. **Fixed Baseline (Status Quo):**
   $$S_{\min}(d) = S_0 = 2{,}000\text{ AVAX}$$
   *Evaluation:* Violates duration sensitivity (Axiom 2). If $d_{\min}$ is lowered to 2 days without adjusting $S_0$, transient capital enters at 2,000 AVAX, creating an unmitigated 48-hour churn risk.

2. **Iso-Commitment (Constant Capital-Time):**
   $$S_{\min}(d) = \max\left(S_{\text{floor}}, \frac{K_{\text{base}}}{d}\right)$$
   *Evaluation:* If calibrated to $K_{\text{base}} = 28{,}000\text{ AVAX-days}$, $S_{\min}(2) = 14{,}000\text{ AVAX}$. However, the curve clamps to $S_{\text{floor}} = 500\text{ AVAX}$ at $d = 28{,}000 / 500 = 56.0\text{ days}$. For all durations between 57 days and 365 days (84.7% of the domain), the curve is completely flat, offering zero marginal incentive for commitments beyond 8 weeks.

3. **Standard Hyperbolic Decay:**
   $$S_{\min}(d) = S_{\text{floor}} + \frac{S_{\text{anchor}} - S_{\text{floor}}}{1 + \alpha (d - d_{\min})}$$
   *Evaluation:* Possesses a heavy algebraic tail. If calibrated to pass through an intermediate pivot, the tail overshoots the desired floor at $d_{\max} = 365\text{ days}$, requiring artificial truncation or discontinuity to meet Axiom 4.

4. **Piecewise Step Function (Unlinked Tiers):**
   $$S_{\min}(d) = S_k \quad \text{for } d \in [d_k, d_{k+1})$$
   *Evaluation:* Violates continuity (Axiom 5). Unlinked step schedules create cliff edges where a validator staking for 13 days 23 hours pays a massive penalty compared to one staking for 14 days, incentivizing boundary gaming and schedule manipulation.

5. **Bounded Harmonic Decay Family:**
   $$S_{\min}(d) = S_{\text{floor}} + (S_{\text{anchor}} - S_{\text{floor}}) \cdot \left[ \frac{\frac{1}{d} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}} \right]^p$$
   *Evaluation:* Uses an inverse-duration kernel $\eta(d)$ that directly mirrors turnover frequency. Satisfies exact boundary convergence (Axiom 4), strict monotonicity (Axiom 2), and strict global convexity (Axiom 3) for all $p \ge 1$.

### 7.2 Axiom Compliance Matrix

| Design Axiom | Fixed Baseline | Iso-Commitment | Standard Hyperbolic | Piecewise Cliffs | Bounded Harmonic |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **A1: Domain Boundary Validity** | Satisfied | Satisfied | Satisfied | Satisfied | Satisfied |
| **A2: Strict Monotonicity** | **Violated** (Flat) | **Violated** ($d > 56\text{d}$) | Satisfied | **Violated** (Steps) | Satisfied |
| **A3: Strict Global Convexity** | **Violated** | Satisfied | Satisfied | **Violated** | Satisfied ($p \ge 1$) |
| **A4: Exact Boundary Convergence**| N/A | Satisfied (Clamped)| **Violated** | Satisfied | Satisfied |
| **A5: Absence of Cliff Discontinuities** | Satisfied | Satisfied | Satisfied | **Violated** | Satisfied |
| **A6: Calibration Tractability** | Trivial | Limited | Moderate | Arbitrary | Closed-Form Invertible |
| **A7: Quantization Robustness** | Satisfied | Moderate | Moderate | Inherent | Highly Robust |

The Bounded Harmonic family satisfies all seven axioms simultaneously while providing an analytical kernel for parameter calibration.

---

## 8. Mathematical Analysis of the Bounded Harmonic Family

### 8.1 Continuous Formulation
Let $d \in [d_{\min}, d_{\max}]$, with $d_{\min} = 2\text{ days}$ and $d_{\max} = 365\text{ days}$. Let $S_{\text{floor}}$ denote the long-duration floor and $S_{\text{anchor}}$ denote the short-duration anchor, with $\Delta S = S_{\text{anchor}} - S_{\text{floor}} > 0$.

The normalized inverse-duration kernel $\eta(d)$ is defined as:
$$\eta(d) = \frac{\frac{1}{d} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}}$$

The admission frontier is defined by:
$$S_{\min}(d) = S_{\text{floor}} + \Delta S \cdot \eta(d)^p, \quad p \ge 1$$

Evaluating $\eta(d)$ across standard tenors:
$$\eta(2) = 1.000000, \quad \eta(7) = 0.281804, \quad \eta(14) = 0.138135, \quad \eta(30) = 0.061524, \quad \eta(365) = 0.000000$$

### 8.2 Proof of Strict Global Convexity ($p \ge 1$)
The first and second derivatives of the kernel $\eta(d)$ with respect to $d$ are:
$$\eta'(d) = -\frac{1}{d^2 \left(\frac{1}{d_{\min}} - \frac{1}{d_{\max}}\right)} < 0 \quad \forall d > 0$$
$$\eta''(d) = \frac{2}{d^3 \left(\frac{1}{d_{\min}} - \frac{1}{d_{\max}}\right)} > 0 \quad \forall d > 0$$

Applying the chain rule to $S_{\min}(d)$:
$$S'_{\min}(d) = \Delta S \cdot p \cdot \eta(d)^{p-1} \cdot \eta'(d) < 0$$
$$S''_{\min}(d) = \Delta S \cdot p \cdot \left[ (p-1)\eta(d)^{p-2} (\eta'(d))^2 + \eta(d)^{p-1} \eta''(d) \right]$$

Since $\Delta S > 0$, $p \ge 1$, $\eta(d) > 0$, and $\eta''(d) > 0$ for all $d \in (d_{\min}, d_{\max})$, both terms inside the bracket are strictly positive for $p \ge 1$:
$$S''_{\min}(d) > 0 \quad \forall d \in (d_{\min}, d_{\max}) \quad \iff \quad p \ge 1$$

`[DERIVED]` This establishes that $p \ge 1$ is a necessary and sufficient condition for strict global convexity.

### 8.3 Retraction and Analysis of the Sub-Convex Regime ($p < 1$)
`[DERIVED]` Earlier preliminary drafts considered values in the range $p \in [0.60, 0.65]$. Mathematical analysis reveals two critical defects when $p < 1$:
1. **Interior Inflection Point:** Setting $S''_{\min}(d^*) = 0$ yields a closed-form inflection point at:
   $$d^* = \frac{p+1}{2} \cdot d_{\max}$$
   For $p = 0.62$, an inflection point occurs at $d^* = \frac{1.62}{2} \times 365 = 295.65\text{ days}$. For durations beyond $d^*$, the curve becomes concave ($S''_{\min} < 0$), causing marginal relief to accelerate rather than diminish.
2. **Infinite Terminal Slope:** As $d \to d_{\max}$, $\eta(d) \to 0$. For $p < 1$, the exponent $p-1 < 0$, causing $\lim_{d \to 365} S'_{\min}(d) = -\infty$.

Consequently, all formulations with $p < 1$ are mathematically unsuitable and formally excluded from the design space.

### 8.4 Closed-Form Pivot Feasibility Bound
If governance specifies a target continuity pivot $(d_{\text{pivot}}, S_{\text{pivot}})$, the exponent $p$ is determined by:
$$p = \frac{\ln\left(\frac{S_{\text{pivot}} - S_{\text{floor}}}{S_{\text{anchor}} - S_{\text{floor}}}\right)}{\ln(\eta(d_{\text{pivot}}))}$$

To ensure strict convexity ($p \ge 1$), the ratio must satisfy $\frac{S_{\text{pivot}} - S_{\text{floor}}}{S_{\text{anchor}} - S_{\text{floor}}} \le \eta(d_{\text{pivot}})$, yielding the **Convex Pivot Feasibility Bound**:
$$S_{\text{pivot}} \le S_{\text{floor}} + (S_{\text{anchor}} - S_{\text{floor}}) \cdot \eta(d_{\text{pivot}})$$

`[DERIVED]` This closed-form inequality establishes whether any proposed policy pivot is mathematically compatible with strict convexity:
- An anchor of $S(14) = 2{,}000\text{ AVAX}$ with $S_{\text{anchor}} = 14{,}000\text{ AVAX}$ and $S_{\text{floor}} = 500\text{ AVAX}$ yields an upper bound of $500 + 13{,}500 \times 0.138135 = 2{,}364.8\text{ AVAX}$. Because $2{,}000 \le 2{,}364.8$, the 14-day pivot is feasible and yields $p = 1.110 \ge 1.0$.
- In contrast, an 84-day pivot at $2{,}000\text{ AVAX}$ with $S_{\text{anchor}} = 18{,}000\text{ AVAX}$ yields an upper bound of $500 + 17{,}500 \times 0.018431 = 822.5\text{ AVAX}$. Because $2{,}000 > 822.5$, setting $S(84) = 2{,}000$ strictly forces $p < 1$, introducing the aforementioned inflection defect.

---

## 9. Exploratory Sensitivity Analysis & Parity Scenarios

To assist the Avalanche Foundation in evaluating design trade-offs, we present four exploratory sensitivity scenarios.

> [!IMPORTANT]
> **Exploratory Sensitivity Sweeps, Not Final Governance Recommendations:**  
> These parameter packages represent illustrative numerical sensitivity sweeps designed to explore trade-offs between short-end barriers, intermediate continuity, and long-end floors. They are not final governance proposals and have not been authorized by protocol governance.

| Parameter / Metric | Scenario EM2 (Full Parity) | Scenario P (14d Anchor) | Scenario E (30d LST Pivot) | Scenario B-600 (Cost-Buffered) |
| :--- | :---: | :---: | :---: | :---: |
| **Short-End Anchor $S_{\text{anchor}}$** | $19{,}402\text{ AVAX}$ | $14{,}000\text{ AVAX}$ | $14{,}000\text{ AVAX}$ | $18{,}000\text{ AVAX}$ |
| **Terminal Floor $S_{\text{floor}}$** | $500\text{ AVAX}$ | $500\text{ AVAX}$ | $500\text{ AVAX}$ | $600\text{ AVAX}$ |
| **Calibration Pivot** | $S(14) = 2{,}000\text{ AVAX}$ | $S(14) = 2{,}000\text{ AVAX}$ | $S(30) = 1{,}200\text{ AVAX}$ | $S(14) = 2{,}000\text{ AVAX}$ |
| **Exponent $p$** | **1.282** | **1.110** | **1.061** | **1.250** |
| **Strictly Convex ($p \ge 1$)?** | **Yes** | **Yes** | **Yes** | **Yes** |
| **$S_{\min}(2\text{d})$** | $19{,}402\text{ AVAX}$ | $14{,}000\text{ AVAX}$ | $14{,}000\text{ AVAX}$ | $18{,}000\text{ AVAX}$ |
| **$S_{\min}(7\text{d})$** | $4{,}226\text{ AVAX}$ | $3{,}809\text{ AVAX}$ | $4{,}021\text{ AVAX}$ | $4{,}172\text{ AVAX}$ |
| **$S_{\min}(14\text{d})$** | **$1{,}994\text{ AVAX}$** | **$2{,}000\text{ AVAX}$** | $2{,}153\text{ AVAX}$ | **$2{,}065\text{ AVAX}$** |
| **$S_{\min}(30\text{d})$** | $1{,}030\text{ AVAX}$ | $1{,}111\text{ AVAX}$ | **$1{,}200\text{ AVAX}$** | $1{,}133\text{ AVAX}$ |
| **$S_{\min}(60\text{d})$** | $693\text{ AVAX}$ | $755\text{ AVAX}$ | $804\text{ AVAX}$ | $799\text{ AVAX}$ |
| **$S_{\min}(90\text{d})$** | $601\text{ AVAX}$ | $645\text{ AVAX}$ | $677\text{ AVAX}$ | $705\text{ AVAX}$ |
| **$S_{\min}(180\text{d})$** | $525\text{ AVAX}$ | $543\text{ AVAX}$ | $556\text{ AVAX}$ | $627\text{ AVAX}$ |
| **$S_{\min}(365\text{d})$** | **$500\text{ AVAX}$** | **$500\text{ AVAX}$** | **$500\text{ AVAX}$** | **$600\text{ AVAX}$** |
| **Min. Commitment $K(d)$** | $27{,}917\text{ AVAX-d}$ | **$26{,}634\text{ AVAX-d}$** | $27{,}726\text{ AVAX-d}$ | $28{,}618\text{ AVAX-d}$ |
| **Location of Min $K(d)$** | $d = 13.94\text{d}$ | $d = 6.08\text{d}$ | $d = 3.72\text{d}$ | $d = 10.65\text{d}$ |

### 9.2 Key Trade-Off Insights from Sweeps
1. **Uniform Parity vs. Anchor Parity:**  
   Scenario EM2 enforces strict commitment parity ($K(d) \ge 28{,}000\text{ AVAX-days}$) across the entire continuous domain, but requires a higher 48-hour barrier ($S_{\text{anchor}} \approx 19{,}402\text{ AVAX}$). Scenario P accepts a modest 4.88% dip in capital-time commitment between 3 and 10 days (reaching a minimum of $26{,}634\text{ AVAX-days}$ at $d = 6.08\text{ days}$) to achieve a round anchor of $14{,}000\text{ AVAX}$ at 48 hours and exact parity at 14 days ($2{,}000\text{ AVAX} \times 14\text{d} = 28{,}000\text{ AVAX-days}$).
2. **LST Tenor Alignment:**  
   Scenario E calibrates the intermediate curve to match typical 30-day liquid staking rebalancing cycles ($S(30) = 1{,}200\text{ AVAX}$), demonstrating how the frontier can accommodate institutional treasury rhythms.
3. **Decentralization Cushion:**  
   Scenario B-600 evaluates the effect of elevating the long-duration floor to $600\text{ AVAX}$, which provides a greater revenue buffer against operational server expenses.

---

## 10. Reference Data & External Inputs

To contextualize the admission frontier within broader network economics, we examine reference data on validator hosting costs and protocol reward dynamics. These data serve as informational baselines rather than definitive proof of validator solvency.

### 10.1 Validator Server Cost Tiers
Running an Avalanche validator node requires continuous hardware hosting, high-throughput network connectivity, and storage maintenance. Typical market hosting costs span three primary operational tiers:
- **Tier 1 (Solo Bare Metal / Low-Cost VPS, e.g., Hetzner / OVH):** $\approx 600\text{ USD/year}$ (\$50 / month).
- **Tier 2 (Commercial Cloud / Mid-Tier VPS, e.g., Contabo / Latitude):** $\approx 1{,}200\text{ USD/year}$ (\$100 / month).
- **Tier 3 (Enterprise Multi-AZ Redundant Cloud, e.g., AWS / GCP):** $\approx 2{,}400\text{ USD/year}$ (\$200 / month).

### 10.2 Break-Even Staking Revenue Relationships
`[DERIVED]` For a validator with self-stake $S$, annualized reward rate $\text{ARR}(d)$, token price $P_{\text{AVAX}}$, and historical uptime ratio $p_{\text{up}}$, annual net staking yield in fiat terms is modeled as:
$$\text{Yield}_{\text{USD}} = S \cdot \text{ARR}(d) \cdot P_{\text{AVAX}} \cdot p_{\text{up}}$$

Setting $\text{Yield}_{\text{USD}} = \text{Cost}_{\text{server}}$ yields the nominal break-even self-stake requirement:
$$S_{\text{break-even}} = \frac{\text{Cost}_{\text{server}}}{P_{\text{AVAX}} \cdot \text{ARR}(d) \cdot p_{\text{up}}}$$

Evaluating this relationship at current annual reward rates ($\text{ARR}(365) \approx 6.378\%$) and historical empirical uptime ($p_{\text{up}} = 0.9753$):

| Server Cost Tier | Annual Cost | Break-Even @ \$15 AVAX | Break-Even @ \$25 AVAX | Break-Even @ \$40 AVAX |
| :--- | :---: | :---: | :---: | :---: |
| **Tier 1 (Solo VPS)** | \$600 / yr | **$643.0\text{ AVAX}$** | **$385.8\text{ AVAX}$** | **$241.1\text{ AVAX}$** |
| **Tier 2 (Mid-Tier VPS)** | \$1,200 / yr | $1{,}286.1\text{ AVAX}$ | $771.6\text{ AVAX}$ | $482.3\text{ AVAX}$ |
| **Tier 3 (Enterprise Cloud)**| \$2,400 / yr | $2{,}572.2\text{ AVAX}$ | $1{,}543.3\text{ AVAX}$ | $964.6\text{ AVAX}$ |

`[ASSUMED]` **Analytical Takeaway:** These calculations demonstrate that at conservative price levels (\$15 AVAX), solo operators hosting on cost-effective bare metal require approximately $600\text{ to }650\text{ AVAX}$ to achieve operational break-even solely on self-stake yield. At higher price levels (\$25–\$40 AVAX), break-even falls comfortably below $500\text{ AVAX}$. However, this static relationship does not account for delegation revenue, fee-share, or opportunity costs of capital, which require dynamic validation in agent-based simulation.

### 10.3 Integration with Reward Curves (ACP-285)
`[OBSERVED]` Staking rewards on Avalanche have incorporated a duration-dependent reward rate since Genesis:
$$\text{ARR}(d) = r_{\min} + (r_{\max} - r_{\min}) \cdot \frac{d}{365}$$
providing an annualized yield of approximately 5.36% at 14 days and 6.38% at 365 days (at current circulating supply).

Under ACP-285, protocol discussions have proposed steepening this yield curve by lowering the minimum consumption rate to 7.5%, expanding the yield spread between short and long durations from ~1.02 percentage points to ~2.30 percentage points. This steepening works synergistically with the admission frontier: the admission frontier acts as an **entry filter** preventing low-capital churn at short durations, while ACP-285 provides the **macroeconomic incentive** encouraging large capital to commit for longer periods.

---

## 11. Architectural Implementation Requirements

Implementing a duration-dependent admission rule within Avalanche's consensus layer requires strict alignment with the deterministic execution requirements of `vms/platformvm`.

### 11.1 Deterministic Integer Quantization
`[DERIVED]` Floating-point arithmetic is inherently non-deterministic across differing CPU architectures, compiler flags, and operating systems. Evaluating non-linear mathematical functions ($x^p$, logarithms, or floating-point division) inside consensus validation would risk consensus forks.

Therefore, any production deployment of an admission frontier must be implemented via **discrete integer quantization**:
- Durations evaluated in discrete integer time units (nanoseconds or seconds).
- Minimum stake evaluated in integer token units (`nAVAX`, where $1\text{ AVAX} = 10^9\text{ nAVAX}$).
- Frontier represented as a pre-computed, strictly monotonic lookup schedule or piecewise-linear integer function within PlatformVM state validation.

### 11.2 State Transition & Compatibility Considerations
1. **Grandfathering Active Validators:** Staking positions registered prior to the protocol activation timestamp must be evaluated according to the rules active at their registration time. Active validators continue to validate and earn rewards until their scheduled end time without interruption.
2. **Syntactic Mempool Verification:** Newly submitted `AddPermissionlessValidatorTx` transactions must be validated against the discrete integer schedule during syntactic transaction parsing. Transactions providing insufficient weight for their specified duration are rejected before block inclusion or mempool propagation.
3. **P-Chain Serialization Invariance:** The proposed admission rules require zero modifications to on-chain transaction serialization formats, BLS signatures, or cryptographic proofs, preserving full backwards compatibility across network clients.
4. **Engineering Responsibility:** Protocol implementation details, exact bracket counts, and Go code specifications are properly determined by Ava Labs PlatformVM core engineers during the client integration phase.

---

## 12. Epistemic Status, Research Boundaries & Questions for the Foundation

### 12.1 Epistemic Taxonomy of Claims
To ensure complete transparency and academic discipline, every major claim in this memorandum is classified under our strict epistemic validation standard:

| Epistemic Class | Subject Matter | Evidentiary Basis |
| :--- | :--- | :--- |
| **`[OBSERVED]`** | Baseline validator distributions, 14-day clustering (16.38%), median stake (2,015 AVAX), August 2025 entity restructuring (78.4% institutional), historical ARR yields (5.36%–6.38%). | Primary on-chain panel (`01-renewal-panel.parquet`, 57,067 stints, 7,635 nodes, ending 2026-08-13). |
| **`[DERIVED]`** | Strict convexity theorem ($p \ge 1$), inflection point derivation ($d^* = \frac{p+1}{2}d_{\max}$), closed-form pivot feasibility bound, break-even stake formula ($S_{\text{break-even}}$). | Closed-form mathematical proofs and numerical root-finding verified to machine precision. |
| **`[HYPOTHESIS]`** | Operational hazards of decoupled admission (sampling variance, state churn), behavioral response pathways (Validator Refusal Rule splits). | Formal mechanism models and qualitative protocol analysis awaiting dynamic simulation. |
| **`[ASSUMED]`** | Server hosting cost tiers (\$600–\$2,400/yr), validator hardware requirements, delegator risk preferences. | Industry hosting benchmarks, public cloud pricing sheets, and operator survey samples. |
| **`[UNIDENTIFIED]`** | Endogenous validator supply elasticity under simultaneous price and yield shocks, cross-subnet validator migration. | Unobserved regimes requiring parameter calibration during digital-twin (cadCAD) simulation. |

### 12.2 Research Boundaries: Established vs. Unresolved
- **What Has Been Established:**
  - Independent static reductions in stake and duration collapse the economic commitment barrier by over 96%, creating severe churn incentives.
  - The Bounded Harmonic family satisfies all structural design axioms, guaranteeing strict convexity for $p \ge 1$ and exact boundary convergence.
  - Closed-form bounds determine whether any proposed policy pivot is mathematically feasible under convex admission geometry.
  - Historical baseline records show that validator exits in August 2025 were dominated by institutional restructuring rather than Sybil attacks.
- **What Remains to Be Tested (Stage 4 / Digital Twin Scope):**
  - Dynamic agent-based response distributions under varying validator refusal pathways.
  - Network-wide staking supply elasticity when admission frontiers interact with ACP-285 reward curve steepening.
  - Formal quantification of consensus sampling variance under synthetic high-churn regimes.

---

### 12.3 Structured Collaborative Questions for the Avalanche Foundation

To guide the next phase of digital-twin simulation and protocol specification, we submit four strategic questions for Foundation review:

#### Question 1: Ecosystem Continuity vs. Short-End Churn Defense
- **The Evidence:** Historical records demonstrate that 16.38% of all stints cluster at exactly 14 days and 2,000 AVAX. Setting an anchor of $14{,}000\text{ AVAX}$ at 48 hours allows exact continuity at $(14\text{d}, 2{,}000\text{ AVAX})$ while maintaining $p = 1.110 \ge 1$ (Scenario P). However, achieving strict uniform commitment parity ($K(d) \ge 28{,}000\text{ AVAX-days}$ across every continuous day) requires elevating the 48-hour barrier to $\approx 19{,}402\text{ AVAX}$ (Scenario EM2).
- **The Trade-off:** A lower short-end anchor provides greater liquidity optionality for institutional participants but introduces a minor commitment discount (up to 4.88%) at intermediate tenors (3–10 days). A higher short-end anchor guarantees absolute capital-time parity but increases entry frictions for short-duration stakers.
- **Knowns & Unknowns:** Closed-form parity trajectories are known with certainty. The elasticity of institutional demand for 48-hour consensus slots under an $18{,}000\text{--}19{,}400\text{ AVAX}$ requirement is unknown and unobserved in pre-Helicon data.
- **Guidance Needed:** Does the Foundation prioritize absolute uniform capital-time parity ($K(d) \ge 28{,}000\text{ AVAX-days}$), or is an anchor-point parity design (with exact continuity at 14 days and 48 hours, and a controlled intermediate dip) preferred to maximize capital efficiency?

#### Question 2: Delegator Time-Matching Firewall under ACP-273
- **The Evidence:** Delegations currently account for 46% of P-Chain transaction volume. Under existing rules, delegator lockups require a minimum of 14 days. If ACP-273 enables 48-hour validator stints, a validator staking for 48 hours cannot accept a 14-day delegation unless delegation mechanics are modified.
- **The Trade-off:** Enforcing a strict firewall ($A_{\text{del}}(d) = 0$ for $d < 14\text{d}$) prevents short-duration validators from accessing retail delegation pools, insulating the delegation market from high-frequency churn. Relaxing the firewall would require creating short-duration delegation tenors, significantly increasing P-Chain staking transaction volume.
- **Knowns & Unknowns:** The mathematical access ratio $A_{\text{del}}(d) = \max(0, (d - 14)/d)$ is formally derived. The willingness of retail delegators to accept 48-hour re-delegation friction is unmeasured.
- **Guidance Needed:** Does Ava Labs intend to maintain the 14-day delegator firewall under ACP-273, restricting sub-14-day validation strictly to sovereign self-stake?

#### Question 3: Long-End Floor Calibration & Operational Solvency
- **The Evidence:** Physical bare-metal hosting costs for reliable solo validation baseline at $\approx 600\text{ USD/year}$. At conservative token valuations (\$15 AVAX) and baseline uptime, a validator with $500\text{ AVAX}$ self-stake earns $\approx 466\text{ USD/year}$, leaving a modest operational deficit unless supported by higher token prices, delegation commissions, or subsidized infrastructure. A $600\text{ AVAX}$ floor provides break-even solvency at \$15 AVAX.
- **The Trade-off:** A lower floor ($500\text{ AVAX}$) maximizes marketing accessibility and decentralization optics for sovereign operators, relying on price appreciation or home hardware to achieve solvency. A cost-buffered floor ($600\text{ AVAX}$) provides a greater economic buffer against hardware cost inflation.
- **Knowns & Unknowns:** Nominal server pricing tiers are well-documented. The percentage of potential home validators utilizing existing non-dedicated hardware (reducing marginal hosting cost to near zero) is unknown.
- **Guidance Needed:** Does the Foundation prefer calibrating the 365-day terminal floor strictly to the round $500\text{ AVAX}$ threshold, or should simulation models incorporate a cost-buffered floor ($600\text{ AVAX}$) to prioritize long-term solo validator economic solvency?

#### Question 4: Consensus Rule Enforcement vs. Fee-Based Pacing
- **The Evidence:** Floating-point curves cannot execute deterministically in PlatformVM, requiring discrete integer quantization.
- **The Trade-off:** Implementing $S_{\min}(d)$ as a strict consensus validity rule directly restricts block validity and drops invalid transactions during mempool verification. An alternative architectural approach would enforce admission pacing via multi-dimensional transaction fees (e.g., ACP-103), charging higher registration fees for short-duration stints while keeping nominal stake requirements flat.
- **Knowns & Unknowns:** The 8-tier discrete integer table format is verified for deterministic Go execution. The economic incidence of upfront burning fees versus locked staking bonds across differing operator classes requires further comparative modeling.
- **Guidance Needed:** Does the Foundation view duration-dependent admission primarily as a **consensus validity rule** governing bonded stake weight ($S_{\min}(d)$), or as a candidate for **fee-based admission pacing** within the transaction fee architecture?
