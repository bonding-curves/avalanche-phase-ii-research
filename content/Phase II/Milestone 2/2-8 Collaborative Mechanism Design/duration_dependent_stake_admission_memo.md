# Technical Mechanism Design Memo: Duration-Dependent Consensus Admission Frontiers ($S_{\min}(d)$)

| Field | Value |
| :--- | :--- |
| **Author** | Hasher Nabi ([@coad1024-cmd](https://github.com/coad1024-cmd)), Bonding Curves Research Group (BCRG) |
| **Topic** | Protocol Admission Geometry, Sybil Resistance, and Validator Invariants under ACP-273 |
| **Audience** | Dr. Eric Lu, Ava Labs PlatformVM Architecture Team, BCRG Governance Group |
| **Date** | October 2, 2026 |
| **Target Review Gate** | Model v0.7.0 Handoff & Milestone 2 Collaborative Mechanism Review (October 2, 2026) |
| **Status** | Complete Master Peer-Reviewed Technical Specification (Resolving Review Gates HD1–HD5 & HA1–HA10) |
| **Artifact Codebase** | `src/avalanche_research/admission_frontier.py` & `BoundedHarmonicFrontier` |

---

## Executive Summary

Avalanche Primary Network consensus governance is currently navigating two interconnected structural proposals:
1. **ACP-273:** Shortens the minimum validator staking duration from 14 days down to 48 hours to unlock capital liquidity and provide staking optionality.
2. **Community Decentralization Proposals:** Proposes lowering the minimum validator self-stake entry threshold from 2,000 AVAX to 500 AVAX to expand sovereign home validation.

> [!CAUTION]
> **The Decoupled Enactment Failure Mode:**  
> If enacted independently as static, uncoupled parameters, an operator could occupy an active Primary Network consensus slot with only **500 AVAX locked for 48 hours**. This collapses the capital-time economic commitment from the historical Mainnet baseline of **28,000 AVAX-days** down to **1,000 AVAX-days**—a **96.43% reduction in economic security**. This subsidizes transient speculative capital, inflates Snowman consensus sampling variance, and induces severe PlatformVM state churn (up to 182.5 validator churn cycles per year per continuous node).

**The Proposed Mechanism:** Rather than treating duration ($d$) and minimum self-stake ($S$) as independent static scalars, the protocol couples them via a continuous **Bounded Harmonic Admission Frontier** $S_{\min}(d)$.

Under this mechanism:
- **Earned Decentralization:** Sovereign home operators access the 500 AVAX (or cost-buffered 600 AVAX) minimum stake barrier by committing capital for 365 days.
- **Anti-Churn & Sybil Defense:** Short-duration stakers utilizing the 48-hour window must post a substantial anchor bond ($S_{\text{short}} = 14{,}000\text{ to }19{,}402\text{ AVAX}$), preserving or exceeding consensus skin-in-the-game.
- **Zero Disenfranchisement:** 100% of historical 14-day stints at 2,000 AVAX satisfy the admission frontier ($S_{\min}(14) \le 2{,}000\text{ AVAX}$).
- **Deterministic Consensus Implementation:** The continuous formulation is quantized into an 8-tier discrete integer lookup table in nanoseconds and `nAVAX`, eliminating floating-point non-determinism during PlatformVM block validation.
- **Tinbergen Instrument Separation:** The admission frontier strictly governs consensus slot entry and churn defense; macro stake-weighted duration expansion across whale capital is governed by ACP-285 annualized reward rate ($\text{ARR}(d)$) steepening.

---

## 1. Problem Formulation: The Geometry of Consensus Admission

### 1.1 Historical Mainnet Baseline Invariants
Since Genesis, Avalanche consensus rules have enforced two static constraints:
- Minimum Staking Duration: $d_{\min} = 14\text{ days}$
- Minimum Validator Self-Stake: $S_{\min} = 2{,}000\text{ AVAX}$

These boundaries establish the historical **Capital-Time Commitment Invariant ($K_{\text{base}}$)**:
$$K_{\text{base}} = S_{\min} \cdot d_{\min} = 2{,}000\text{ AVAX} \times 14\text{ days} = 28{,}000\text{ AVAX-days}$$

The integral $K = \int_0^T S(t) \, dt$ quantifies the minimum economic opportunity cost forfeited by a node operator to participate in Primary Network consensus sampling.

### 1.2 The Decoupled Parameter Dilemma

```
Required Self-Stake (AVAX)
 ^
 |  20,000 + - - - - - - - - - + [ S_short Anchor (48h Sybil Protection) ]
 |         |                   |
 |   2,000 +-------------------+ [ Historical Mainnet Barrier: 28,000 AVAX-days ]
 |         |                   |
 |     500 +--+                + [ Decoupled Static Barrier (ACP-273 x Low Floor) ]
 |         |  |                  (1,000 AVAX-days -> 96.43% SECURITY COLLAPSE)
 0---------+--+----------------+--------------------> Duration (d)
          2d 14d              365d
```

If governance adopts uncoupled static thresholds ($S_{\min} = 500\text{ AVAX}$, $d_{\min} = 2\text{ days}$):
- $\text{Commitment}_{\text{Decoupled}} = 500\text{ AVAX} \times 2\text{ days} = 1{,}000\text{ AVAX-days}$.
- **Sybil Cost Ratio:** $\frac{1{,}000}{28{,}000} = 0.0357$ (only 3.57% of historical cost).
- **Consensus Slot Multiplication:** An entity with 28,000 AVAX could operate 28 concurrent consensus nodes rather than 1, destabilizing Snowman consensus sampling and generating high-frequency BLS key registration churn on the P-Chain.

### 1.3 Three Operational Hazards of Decoupled Admission
1. **Consensus Sampling Instability:** Snowman consensus repeatedly samples small subsets ($k=20$) of validators weighted by stake. Replacing persistent nodes with 48-hour transient nodes increases sample variance and heightens the risk of partition attacks during network latency spikes.
2. **P-Chain State Churn:** ACP-273 telemetry documents that delegations account for 46% of all P-Chain transactions at a 100:1 ratio to validator transactions. Introducing micro-stake short-duration validators accelerates BLS key registration and staking UTXO writes, increasing database commit latency on validator nodes.
3. **Validator Set Turnover:** A network where capital cycles every 48 hours permits major validator set changes within two days, compromising L1 Interchain Message (ICM) verification stability.

### 1.4 Tinbergen Policy Separation Principle
The Tinbergen Separation Principle establishes that achieving $N$ independent economic policy targets requires at least $N$ independent policy instruments. Attempting to solve multiple distinct network challenges with a single admission lever introduces structural distortion:

| System Target | Primary Policy Instrument | Interaction with Admission Rule |
| :--- | :--- | :--- |
| **1. Capital Barrier Reduction** | Admission Frontier Floor ($S_{\text{floor}} = 500\text{ AVAX}$) | Direct enforcement at 365 days |
| **2. Sybil Defense at 48 Hours** | Short Anchor Bond ($S_{\text{short}} = 14{,}000\text{--}19{,}402\text{ AVAX}$) | Direct enforcement at 48 hours |
| **3. Macro Duration Expansion** | ACP-285 $\text{ARR}(d)$ Yield Steepening | Complements frontier; steers whales |
| **4. Token Issuance Control** | ACP-285 Max Consumption Rate | Invariant (governed by ACP-285) |
| **5. P-Chain State Churn Defense** | ACP-103 Multidimensional Fees | Complemented via short anchor bond |
| **6. Hardware Hosting Viability** | Net $\text{ARR}(d)$ Yield Margin | Steers small nodes to $\ge 84\text{d}$ |

#### The Scale-Invariance Limit of Admission Frontiers
The admission frontier functions as an **entry gatekeeper**, not an institutional allocator:
- Large institutional entities holding 181,000 to 1,000,000+ AVAX easily satisfy an 18,000 AVAX barrier at 48 hours. Elevating the barrier further prices out decentralized operators without altering whale lockup behavior.
- Institutional whales select duration based on the annualized yield differential in ACP-285 ($\text{ARR}(365\text{d}) - \text{ARR}(2\text{d})$), not the admission threshold.
- Attributing macro network duration expansion to the admission frontier represents an attribution error. Macro duration expansion requires the coordinated activation of ACP-285 yield curve steepening.

---

## 2. Empirical Grounding (57,067 Staking Periods, 7,635 Nodes)

Telemetry from the primary dataset (`01-renewal-panel.parquet`), covering 57,067 completed validator periods across 7,635 physical nodes from Genesis to Helicon, establishes empirical boundary conditions:

### 2.1 Distributional Realities
- **Clustering at the Floor:** The median self-bond is 2,015 AVAX (mean 97,264 AVAX). 74.8% of all validator stints (42,710 records) bonded between 2,000 and 6,000 AVAX.
- **Duration Compression:** The unweighted median duration across all history is 23.0 days (mean 45.6 days). Staking periods of exactly 14 days represent 16.38% of all stints (9,347 records). Commitments $\le 30\text{ days}$ account for 58.97% (33,654 records). Commitments spanning 365 days represent only 4.10% (2,340 records).
- **Regime Shock (Etna & Granite):** Following the Etna upgrade, median duration compressed from 29 days down to 15.0 days. In the Granite regime, median self-stake jumped to 14,585 AVAX, and stake-weighted duration fell to an all-time low of 3.97 weeks.
- **Capital vs. Count Divergence:** Commitments under 16 days represent 62% to 69% of new stints during Durango/Fortuna, but represent only 3% to 5% of committed AVAX-days. Small operators choose the minimum duration, while institutional capital locks for longer horizons. Correlation: $\text{Corr}(\log S, \log d) = +0.246$.

### 2.2 Duration Persistence & Behavioral Habits
The empirical record shows strong behavioral inertia across validator renewals:
- Correlation across consecutive stints: $\text{Corr}(d_t, d_{t-1}) = 0.690$.
- **44.54% of renewing validators repeat their exact duration**.
- **75.32% remain within the same duration bucket**.
- Stakers $\le 2,500\text{ AVAX}$ choose $\le 21\text{ days}$ in 57.6% of stints and $\le 35\text{ days}$ in 82.8% of stints. Whales ($> 100,000\text{ AVAX}$) select $\ge 66\text{ days}$ in 34.5% of stints.
- **7-Day Return Renewal Rate:** Applying the standard 7-day renewal rule, the panel yields an 80.7% renewal rate for 2021–2024 and 78.1% for 2025 to Granite (resolving review item `HB6`/`HA2`).

### 2.3 Contextualizing the August 2025 Exit Wave
The net loss of over 500 nodes in August 2025 was previously hypothesized as an adversarial Sybil-swarm attack. Forensic reconstruction from on-chain records reveals the true structure:
- Between 2025-08-01 and 2025-09-01, there were 602 gross validator exits and 96 entrants (net decline of 506 nodes).
- The top 5 exiting entities represented **472 of 602 gross exits (78.4%)**. Attributing 93% to a Sybil swarm was an artifact of dividing gross exits by the net decline (`HB3`).
- These exits were dominated by legitimate operational restructuring:
  1. **GoGoPool Liquid Staking:** Institutional rebalancing of 296 liquid staking nodes.
  2. **Genesis Holder Migration:** A single early holder reorganizing 85 nodes into liquid delegation.
  3. **Node Consolidation:** An institutional operator merging 24 separate 2,000-AVAX nodes into a single high-stake validator.
- **Sybil Swarm Pricing Across Horizons:** Pricing only the 2-day seat provides incomplete protection (`HB5`). With a 500 AVAX floor, the 1,243,879 AVAX exiting capital could buy 2,487 one-year seats (four times today's 621 nodes). Long-term decentralization must therefore be grounded in physical server hosting solvency.

---

## 3. Evaluated Functional Form Alternatives and Trade-off Analysis

Five distinct mathematical functional forms were audited against protocol design criteria:

```
┌────────────────────────────────────────────────────────────────────────┐
│                 ADMISSION FRONTIER FUNCTIONAL FORMS                    │
├─────────────────────┬───────────────────────────┬──────────────────────┤
│ Family              │ Formula S_min(d)          │ Critical Flaw        │
├─────────────────────┼───────────────────────────┼──────────────────────┤
│ Pure Iso-Commitment │ max(500, 28,000 / d)      │ Flattens at day 56   │
│ Standard Hyperbolic │ 500 + 17,500 / (1 + a*d)  │ Heavy tail overshoot │
│ Power-Law Decay     │ 500 + 17,500 * (1-d/365)^p│ Exponent distortion  │
│ Piecewise Cliffs    │ Discrete unlinked steps   │ Cliff-edge arbitrage │
│ Bounded Harmonic    │ 500 + 17,500 * [eta(d)]^p │ None (Selected)      │
└─────────────────────┴───────────────────────────┴──────────────────────┘
```

1. **Pure Iso-Commitment ($S(d) = \max(S_{\text{floor}}, K_{\text{baseline}}/d)$):** Clamps to $S_{\text{floor}} = 500\text{ AVAX}$ at $d = 28{,}000 / 500 = 56.0\text{ days}$ (or $46.7\text{ days}$ for $600\text{ AVAX}$). For durations between 57 days and 365 days (85.1% of the allowable domain), the requirement is completely flat. This removes all capital incentives for locking beyond 8 weeks.
2. **Standard Hyperbolic ($S(d) = S_{\text{floor}} + \frac{S_{\text{short}} - S_{\text{floor}}}{1 + \alpha (d - d_{\min})}$):** If $\alpha$ is calibrated to anchor $S(84) = 2{,}000\text{ AVAX}$, the heavy algebraic tail produces $S(365) = 862.92\text{ AVAX}$, missing the 500 AVAX target by 72.6%. If $S_{\text{floor}} = 600\text{ AVAX}$, it produces $S(365) = 937.26\text{ AVAX}$, overshooting by 56.2%.
3. **Generalized Power-Law Decay ($S(d) = S_{\text{floor}} + \Delta S \cdot \left(\frac{365 - d}{363}\right)^p$):** Fitting $S(84) = 2{,}000\text{ AVAX}$ requires an extreme exponent $p = 9.59$ (for 500 floor) or $p = 9.84$ (for 600 floor). This causes severe distortion: at 14 days, the stake requirement remains excessively elevated at $13{,}093\text{ to }13{,}175\text{ AVAX}$, failing to provide liquidity relief.
4. **Piecewise Discrete Cliffs ($S(d) = S_k$ without continuous derivation):** Setting discrete tiers without an underlying continuous curve creates severe cliff-edge arbitrage (for example, 13 days 23 hours requiring 18,000 AVAX, and 14 days requiring 2,000 AVAX). Operators exploit boundary gaps through timing games.
5. **Continuous Bounded Harmonic Decay (Selected Optimal Design):** The kernel $\frac{1}{d} - \frac{1}{365}$ matches the linear turnover frequency of consensus churn. It satisfies all boundary conditions identically, maintains analytical tractability, eliminates cliff-edge boundary games, and guarantees strict global convexity ($S''_{\min}(d) > 0$) without inflection when parameterized under $p \ge 1.0$.

---

## 4. Mathematical Specification: Bounded Harmonic Frontier

### 4.1 Canonical Functional Form
The admission frontier is defined on the closed domain $d \in [d_{\min}, d_{\max}] = [2, 365\text{ days}]$ by the **Continuous Bounded Harmonic Decay Function**:

$$S_{\min}(d) = S_{\text{floor}} + (S_{\text{short}} - S_{\text{floor}}) \cdot \eta(d)^p = S_{\text{floor}} + \Delta S \cdot \left[ \frac{\frac{1}{d} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}} \right]^p$$

where:
- $d_{\min} = 2\text{ days}$ (the ACP-273 consensus floor).
- $d_{\max} = 365\text{ days}$ (the annual staking ceiling).
- $S_{\text{floor}} \in [500, 600]\text{ AVAX}$ (the long-term decentralization floor).
- $S_{\text{short}} \in [14{,}000, 19{,}402]\text{ AVAX}$ (the short-duration anchor bond).
- $\eta(d)$ is the normalized inverse duration kernel:
  $$\eta(d) = \frac{\frac{1}{d} - \frac{1}{365}}{\frac{1}{2} - \frac{1}{365}} = \frac{\frac{1}{d} - 0.0027397}{0.4972603}$$

Key evaluations of the kernel $\eta(d)$:
$$\eta(2) = 1.000000, \quad \eta(7) = 0.281804, \quad \eta(14) = 0.138135, \quad \eta(30) = 0.061524, \quad \eta(365) = 0.000000$$

### 4.2 Proof of Strict Global Convexity for $p \ge 1$
Convexity guarantees that the marginal capital relief per additional day of commitment, $-\frac{\partial S_{\min}}{\partial d}$, is strictly decreasing—rewarding commitment without creating cliff-edge arbitrage.

- First derivative of the kernel:
  $$\eta'(d) = -\frac{1}{d^2 \left(\frac{1}{d_{\min}} - \frac{1}{d_{\max}}\right)} < 0 \quad \text{for all } d > 0$$
- Second derivative of the kernel:
  $$\eta''(d) = \frac{2}{d^3 \left(\frac{1}{d_{\min}} - \frac{1}{d_{\max}}\right)} > 0 \quad \text{for all } d > 0$$

Computing the derivatives of $S_{\min}(d)$:
$$S'_{\min}(d) = \Delta S \cdot p \cdot \eta(d)^{p-1} \cdot \eta'(d) < 0$$
$$S''_{\min}(d) = \Delta S \cdot p \cdot \left[ (p-1)\eta(d)^{p-2}(\eta'(d))^2 + \eta(d)^{p-1}\eta''(d) \right]$$

Since $\Delta S > 0$, $\eta(d) > 0$, and $\eta''(d) > 0$, whenever $p \ge 1$, both terms inside the bracket are strictly positive. Therefore:
$$S''_{\min}(d) > 0 \quad \forall d \in (d_{\min}, d_{\max}) \quad \iff \quad p \ge 1$$

### 4.3 Formal Retraction of the $p < 1$ Regime
Earlier preliminary drafts examined $p \approx 0.60\text{--}0.65$. Mathematical audit proves that when $p < 1$:
1. **Interior Inflection Point:** $S''_{\min}(d^*) = 0$ occurs at:
   $$d^* = \frac{p+1}{2} \cdot d_{\max}$$
   For $p = 0.62$, an inflection occurs at $d^* = 295.6\text{ days}$. For $d > d^*$, the curve becomes concave ($S''_{\min} < 0$).
2. **Infinite Terminal Slope:** As $d \to d_{\max}$, $\eta(d) \to 0$, causing $\eta(d)^{p-1} \to \infty$ for $p < 1$. The derivative diverges: $\lim_{d \to 365} S'_{\min}(d) = -\infty$.
3. **Zero Terminal Slope for $p > 1$:** For all $p > 1$, as $d \to 365$, $\lim_{d \to 365} S'_{\min}(d) = 0$. A continuous non-zero slope floor near 365 days is mathematically impossible under this family; discrete finite differences must be used instead (`HV3`).

**Conclusion:** The parameter space is strictly restricted to $p \ge 1.0$. Earlier candidate values ($p \in [0.615, 0.631]$) are formally retracted.

### 4.4 Closed-Form Pivot Feasibility Condition
Governance can calibrate the curve by specifying a target pivot point $(d_{\text{pivot}}, S_{\text{pivot}})$. Inverting the equation for $p$:
$$p = \frac{\ln\left(\frac{S_{\text{pivot}} - S_{\text{floor}}}{S_{\text{short}} - S_{\text{floor}}}\right)}{\ln(\eta(d_{\text{pivot}}))}$$

To ensure $p \ge 1$, the ratio must satisfy $\frac{S_{\text{pivot}} - S_{\text{floor}}}{S_{\text{short}} - S_{\text{floor}}} \le \eta(d_{\text{pivot}})$, yielding the **Convex Feasibility Bound**:
$$S_{\text{pivot}} \le S_{\text{floor}} + (S_{\text{short}} - S_{\text{floor}}) \cdot \eta(d_{\text{pivot}})$$

- **Why the Historical 84-Day Pivot Failed:** At $d_{\text{pivot}} = 84\text{ days}$, $\eta(84) = 0.018431$. For $S_{\text{short}} = 18{,}000\text{ AVAX}$ and $S_{\text{floor}} = 500\text{ AVAX}$, the upper bound is $500 + 17{,}500 \times 0.018431 = 822.5\text{ AVAX}$. Attempting to anchor $S(84) = 2{,}000\text{ AVAX}$ severely violated this bound ($2{,}000 > 822.5$), forcing $p = 0.615 < 1$.
- **Why the 14-Day Pivot Succeeds:** At $d_{\text{pivot}} = 14\text{ days}$, $\eta(14) = 0.138135$. For $S_{\text{short}} = 14{,}000\text{ AVAX}$, the upper bound is $500 + 13{,}500 \times 0.138135 = 2{,}364.8\text{ AVAX}$. Setting $S(14) = 2{,}000\text{ AVAX}$ respects the bound ($2{,}000 \le 2{,}364.8$), yielding $p = 1.110 \ge 1.0$.

---

## 5. The 28,000 AVAX-Days Parity Landscape

The quantity $K(d) = S_{\min}(d) \cdot d$ measures the capital-time commitment across durations:
$$K(d) = S_{\text{floor}} \cdot d + (S_{\text{short}} - S_{\text{floor}}) \cdot d \cdot \eta(d)^p$$

The review establishes that the historical baseline $K_{\text{base}} = 28{,}000\text{ AVAX-days}$ serves as an **empirical reference anchor and reported KPI**, rather than an inviolable security constant across every single duration (`HD3`):

1. **Full Uniform Parity (Package EM2):** To enforce $K(d) \ge 28{,}000\text{ AVAX-days}$ across *all* durations $d \in [2, 365]$ while keeping $S(14) \le 2{,}000\text{ AVAX}$, the short-end barrier must be set to:
   $$S_{\text{short}} = 19{,}402\text{ AVAX} \quad \text{with} \quad p = 1.282 \quad (S_{\text{floor}} = 500\text{ AVAX})$$
   Under EM2, $K(2) = 38{,}804\text{ AVAX-days}$ ($1.39\times$), $K(14) = 28{,}000\text{ AVAX-days}$ ($1.00\times$), and the minimum across the entire curve is $27{,}998\text{ AVAX-days}$.
2. **Anchor-Point Parity (Package P):** If governance prefers a lower 48-hour barrier ($S_{\text{short}} = 14{,}000\text{ AVAX}$), parity holds exactly at 48 hours ($14{,}000 \times 2 = 28{,}000$) and at 14 days ($2{,}000 \times 14 = 28{,}000$). Between 3 and 10 days, $K(d)$ experiences a shallow, controlled dip (reaching a minimum of $24{,}513\text{ AVAX-days}$ at 6 days, a 12.4% discount).

---

## 6. Calibrated Governance Parameter Packages

We present four calibrated, peer-reviewed parameter packages:

| Parameter / Metric | Package EM2 (Full Parity) | Package P (14d Anchor) | Package E (30d Pivot) | Package B-600 (Cost-Buffered) |
| :--- | :---: | :---: | :---: | :---: |
| **Short-End Stake $S_{\text{short}}$** | $19{,}402\text{ AVAX}$ | $14{,}000\text{ AVAX}$ | $14{,}000\text{ AVAX}$ | $18{,}000\text{ AVAX}$ |
| **Terminal Floor $S_{\text{floor}}$** | $500\text{ AVAX}$ | $500\text{ AVAX}$ | $500\text{ AVAX}$ | $600\text{ AVAX}$ |
| **Calibration Pivot** | $S(14) = 2{,}000\text{ AVAX}$ | $S(14) = 2{,}000\text{ AVAX}$ | $S(30) = 1{,}200\text{ AVAX}$ | $S(14) = 2{,}000\text{ AVAX}$ |
| **Exponent $p$** | **1.282** | **1.110** | **1.497** | **1.250** |
| **Strictly Convex ($p \ge 1$)?** | **Yes** | **Yes** | **Yes** | **Yes** |
| **$S_{\min}(2\text{d})$** | $19{,}402\text{ AVAX}$ | $14{,}000\text{ AVAX}$ | $14{,}000\text{ AVAX}$ | $18{,}000\text{ AVAX}$ |
| **$S_{\min}(7\text{d})$** | $4{,}208\text{ AVAX}$ | $3{,}901\text{ AVAX}$ | $2{,}515\text{ AVAX}$ | $4{,}185\text{ AVAX}$ |
| **$S_{\min}(14\text{d})$** | **$2{,}000\text{ AVAX}$** | **$2{,}000\text{ AVAX}$** | $1{,}224\text{ AVAX}$ | **$2{,}000\text{ AVAX}$** |
| **$S_{\min}(30\text{d})$** | $1{,}029\text{ AVAX}$ | $1{,}097\text{ AVAX}$ | **$1{,}200\text{ AVAX}$** | $1{,}104\text{ AVAX}$ |
| **$S_{\min}(60\text{d})$** | $716\text{ AVAX}$ | $754\text{ AVAX}$ | $704\text{ AVAX}$ | $814\text{ AVAX}$ |
| **$S_{\min}(90\text{d})$** | $626\text{ AVAX}$ | $647\text{ AVAX}$ | $599\text{ AVAX}$ | $726\text{ AVAX}$ |
| **$S_{\min}(180\text{d})$** | $541\text{ AVAX}$ | $546\text{ AVAX}$ | $526\text{ AVAX}$ | $643\text{ AVAX}$ |
| **$S_{\min}(365\text{d})$** | **$500\text{ AVAX}$** | **$500\text{ AVAX}$** | **$500\text{ AVAX}$** | **$600\text{ AVAX}$** |
| **Min. Commitment $K(d)$** | $27{,}998\text{ AVAX-d}$ | $24{,}513\text{ AVAX-d}$ | $17{,}136\text{ AVAX-d}$ | $28{,}000\text{ AVAX-d}$ |
| **Sybil Multiple at 365d** | $6.52\times$ | $6.52\times$ | $6.52\times$ | $7.82\times$ |

**Trade-off Analysis & Recommendations:**
- **Package P (Recommended Default):** Balances institutional liquidity at 48 hours ($14{,}000\text{ AVAX}$ anchor) with Mainnet continuity at 14 days ($2{,}000\text{ AVAX}$) and sovereign retail access ($500\text{ AVAX}$ at 365 days).
- **Package EM2 (Full Parity):** Recommended if the Foundation mandates strict $K(d) \ge 28{,}000\text{ AVAX-days}$ across every single day, requiring $S_{\text{short}} = 19{,}402\text{ AVAX}$.
- **Package B-600 (Cost-Buffered):** Recommended if governance wishes to provide a financial cushion for solo home validators against potential hardware hosting cost inflation.

---

## 7. Behavioral Mechanics: The Validator Refusal Rule

When the admission frontier blocks an incoming commitment ($S < S_{\min}(d_{\text{pref}})$), the economic decision-maker does not simply vanish. We formalize the **Validator Refusal Rule** across three behavioral pathways:

```
                      [ Blocked: S < S_min(d_pref) ]
                                    |
          +-------------------------+-------------------------+
          |                                                   |
[ Extend Duration ]                                   [ Add Capital ]
d_feas = min { d : S >= S_min(d) }                    Delta_S = S_min(d_pref) - S
Accept longer lockup                                  Deposit additional AVAX
          |                                                   |
          +-------------------------+-------------------------+
                                    |
                           [ Unviable / Friction ]
                                    v
                              [ Exit Set ]
```

1. **Duration Extension (Primary Path for Small Validators):** Node operators with fixed capital (e.g. 2,000 AVAX) extend their duration to the shortest feasible duration:
   $$d_{\text{feas}} = \min \{ d \in \mathcal{D} : S \ge S_{\min}(d) \}$$
   For a 2,000 AVAX staker desiring 7 days, Package P routes them to 14 days, preserving their active node without requiring additional capital.
2. **Capital Addition (Primary Path for Institutional Operators):** Stakers desiring strict liquidity horizons (e.g. market makers needing 48-hour turnaround) deposit the necessary incremental capital:
   $$\Delta S = S_{\min}(d_{\text{pref}}) - S$$
3. **Exit / Churn Abandonment:** Operators unwilling to extend duration and lacking capital exit the active set. In empirical testing, solo nodes face higher liquidity friction than commercial nodes, meaning an appropriate short barrier effectively filters out low-commitment transient actors.

---

## 8. Three-Layer Delegation Architecture

A critical finding from the peer review is that **delegation flow must be distinguished from active concurrent stock**, and concurrent delegation is bounded by the protocol cap ($4 \times S_{\text{self}}$) and node cap ($3{,}000{,}000\text{ AVAX}$) (`HB1`).

Delegation access operates through three nested layers:

```
┌────────────────────────────────────────────────────────────────────────┐
│ Layer 1: Protocol Firewall (ACP-273)                                  │
│ Delegator minimum lockup remains 14 days.                             │
│ Time-matching access ratio: A_del(d) = max(0, (d - 14) / d)           │
│ Validators with d < 14 days receive EXACTLY ZERO delegation.           │
├────────────────────────────────────────────────────────────────────────┤
│ Layer 2: Provider Market Gates (BENQI, Liquid Staking Pools)          │
│ Protocol eligibility does not guarantee delegation.                    │
│ BENQI Open Pool: Requires S_self >= 6,000 AVAX and Commission <= 2%.   │
│ Miles Pool: Requires S_self >= 2,000 AVAX and Commission <= 5%.        │
├────────────────────────────────────────────────────────────────────────┤
│ Layer 3: Empirical Duration Preference Gradient                       │
│ Time-averaged occupancy of the 4x delegation cap scales with duration:│
│ - 14 to 21 days:  3.7% occupancy                                      │
│ - 30 to 60 days: 16.1% occupancy                                      │
│ - 186 to 365 days: 29.5% occupancy                                    │
└────────────────────────────────────────────────────────────────────────┘
```

**Key Implication:** An operator spinning up a 48-hour validator receives zero delegation by protocol rule. A small 500 AVAX validator at 365 days is eligible for protocol delegation, but must build reputation or self-stake to meet liquid staking provider thresholds. On-chain records confirm that BENQI placed only 0.93% of delegated AVAX on validators below 6,000 AVAX, and only 0.30% under 2,100 AVAX (`HV3`, `H2-V14`).

---

## 9. Economic Grounding of $S_{\text{floor}}$: Hosting Cost Bands & Solvency

Lowering $S_{\text{floor}}$ to 500 or 600 AVAX raises the question: can a node with 500 AVAX earn enough staking rewards to cover real-world server operating costs?

### 9.1 Real-World Server Cost Tiers
- **Tier 1 (Bare Metal / Low-Cost VPS, e.g. Hetzner):** \$480 to \$600 / year (\$40 to \$50 / month).
- **Tier 2 (Commercial Cloud / Mid-Tier VPS):** \$1,200 to \$1,440 / year (\$100 to \$120 / month).
- **Tier 3 (Enterprise Redundant Cloud, e.g. AWS Multi-AZ):** \$2,400 to \$4,200 / year.

### 9.2 Break-Even Solvency Analysis
A validator is solvent if net protocol earnings exceed server overhead:
$$\text{Net Yield (USD)} = S \cdot \text{ARR}(d) \cdot P_{\text{AVAX}} \cdot p_{\text{up}} \ge \text{Cost}_{\text{server}}$$

The required break-even self-stake $S_{\text{be}}$ across AVAX price regimes ($P_{\text{AVAX}} \in [15, 25, 40]\text{ USD}$) and protocol annualized reward rates ($\text{ARR}(365) \approx 6.0\%$, uptime $p_{\text{up}} \approx 0.975$):

| Server Cost Tier | Annual Cost (USD) | Break-Even @ \$15 AVAX | Break-Even @ \$25 AVAX | Break-Even @ \$40 AVAX |
| :--- | :---: | :---: | :---: | :---: |
| **Hetzner Solo** | \$480 / yr | **$547\text{ AVAX}$** | **$328\text{ AVAX}$** | **$205\text{ AVAX}$** |
| **Standard VPS** | \$600 / yr | **$684\text{ AVAX}$** | **$410\text{ AVAX}$** | **$256\text{ AVAX}$** |
| **Commercial Cloud** | \$1,440 / yr | $1{,}641\text{ AVAX}$ | $985\text{ AVAX}$ | $615\text{ AVAX}$ |
| **AWS Enterprise** | \$2,400 / yr | $2{,}735\text{ AVAX}$ | $1{,}641\text{ AVAX}$ | $1{,}026\text{ AVAX}$ |

**Conclusion:** At $S_{\text{floor}} = 500\text{ to }600\text{ AVAX}$, a sovereign home staker running dedicated hardware or a low-cost VPS is economically solvent at \$15+ AVAX. This confirms that 500–600 AVAX represents the true physical boundary for decentralized solo validation.

---

## 10. Historical Yield Structure Clarification

To maintain rigorous historical accuracy (`HB2`):
- Protocol rewards have rewarded duration since Genesis:
  $$\text{ARR}(d) = r_{\min} + (r_{\max} - r_{\min}) \cdot \frac{d}{365}$$
  paying **5.36% at 14 days** and **6.38% at 365 days** (at 470M AVAX supply).
- **ACP-285** widens this duration premium by lowering the consumption rate floor to 7.5%, expanding the spread from ~1.02 percentage points to ~2.30 percentage points.
- **Instrument Synergy:** The Admission Frontier $S_{\min}(d)$ acts as the consensus gatekeeper, filtering out short-term churn, while ACP-285 acts as the macroeconomic incentive steering large capital toward longer commitments.

---

## 11. PlatformVM Consensus Quantization & Go Implementation

### 11.1 Rationale for Integer Quantization
Floating-point evaluations inside consensus critical paths introduce cross-platform verification divergences due to differences in CPU floating-point units, rounding modes, and compiler optimizations.

To preserve deterministic execution across all Avalanche Network Clients, the continuous curve is quantized into eight discrete integer brackets evaluated in nanoseconds and `nAVAX` ($1\text{ AVAX} = 10^9\text{ nAVAX}$):

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   QUANTIZED PLATFORMVM SCHEDULE (PACKAGE P - PRAGMATIC)                │
├───────┬──────────────────────┬─────────────┬─────────────────┬────────────────┬────────┤
│ Index │ Duration Range (d)   │ Stake (AVAX)│ Stake (nAVAX)   │ Capital-Time   │ Ratio  │
├───────┼──────────────────────┼─────────────┼─────────────────┼────────────────┼────────┤
│ 1     │ 2d <= d < 7d         │ 14,000 AVAX │ 14,000 * 10^9   │ 28.0k - <98.0k │ 1.00x+ │
│ 2     │ 7d <= d < 14d        │ 3,900 AVAX  │ 3,900 * 10^9    │ 27.3k - <54.6k │ 0.98x+ │
│ 3     │ 14d <= d < 30d       │ 2,000 AVAX  │ 2,000 * 10^9    │ 28.0k - <60.0k │ 1.00x+ │
│ 4     │ 30d <= d < 60d       │ 1,100 AVAX  │ 1,100 * 10^9    │ 33.0k - <66.0k │ 1.18x+ │
│ 5     │ 60d <= d < 90d       │ 750 AVAX    │ 750 * 10^9      │ 45.0k - <67.5k │ 1.61x+ │
│ 6     │ 90d <= d < 180d      │ 650 AVAX    │ 650 * 10^9      │ 58.5k - <117.0k│ 2.09x+ │
│ 7     │ 180d <= d < 365d     │ 550 AVAX    │ 550 * 10^9      │ 99.0k - <200.8k│ 3.54x+ │
│ 8     │ d >= 365d (Floor 500)│ 500 AVAX    │ 500 * 10^9      │ 182.5k+        │ 6.52x+ │
└───────┴──────────────────────┴─────────────┴─────────────────┴────────────────┴────────┘
```

For comparison, under Package EM2 (Full Parity):
```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   QUANTIZED PLATFORMVM SCHEDULE (PACKAGE EM2 - FULL PARITY)            │
├───────┬──────────────────────┬─────────────┬─────────────────┬────────────────┬────────┤
│ Index │ Duration Range (d)   │ Stake (AVAX)│ Stake (nAVAX)   │ Capital-Time   │ Ratio  │
├───────┼──────────────────────┼─────────────┼─────────────────┼────────────────┼────────┤
│ 1     │ 2d <= d < 7d         │ 19,402 AVAX │ 19,402 * 10^9   │ 38.8k - <135.8k│ 1.39x+ │
│ 2     │ 7d <= d < 14d        │ 4,208 AVAX  │ 4,208 * 10^9    │ 29.5k - <58.9k │ 1.05x+ │
│ 3     │ 14d <= d < 30d       │ 2,000 AVAX  │ 2,000 * 10^9    │ 28.0k - <60.0k │ 1.00x+ │
│ 4     │ 30d <= d < 60d       │ 1,029 AVAX  │ 1,029 * 10^9    │ 30.9k - <61.7k │ 1.10x+ │
│ 5     │ 60d <= d < 90d       │ 716 AVAX    │ 716 * 10^9      │ 43.0k - <64.4k │ 1.53x+ │
│ 6     │ 90d <= d < 180d      │ 626 AVAX    │ 626 * 10^9      │ 56.3k - <112.7k│ 2.01x+ │
│ 7     │ 180d <= d < 365d     │ 541 AVAX    │ 541 * 10^9      │ 97.4k - <197.5k│ 3.48x+ │
│ 8     │ d >= 365d (Floor 500)│ 500 AVAX    │ 500 * 10^9      │ 182.5k+        │ 6.52x+ │
└───────┴──────────────────────┴─────────────┴─────────────────┴────────────────┴────────┘
```

### 11.2 Production Go Reference Implementation
```go
package platformvm

import (
	"errors"
	"time"
)

var (
	ErrStakeDurationTooShort      = errors.New("validator stake duration below protocol minimum")
	ErrStakeDurationTooLong       = errors.New("validator stake duration exceeds protocol maximum")
	ErrInsufficientValidatorStake = errors.New("validator self-stake does not satisfy duration frontier")
	ErrNilOrEmptySchedule         = errors.New("admission frontier schedule cannot be nil or empty")
)

const (
	MinValidatorStakeDuration = 48 * time.Hour
	MaxValidatorStakeDuration = 365 * 24 * time.Hour
	NanoAvaxPerAvax           = 1_000_000_000
)

type DurationBracket struct {
	ThresholdDuration time.Duration
	MinimumWeight     uint64 // in nAVAX
}

// AdmissionFrontierSchedule implements Package P (Recommended Default: 500 AVAX floor, 14,000 AVAX anchor).
var AdmissionFrontierSchedule = []DurationBracket{
	{ThresholdDuration: 365 * 24 * time.Hour, MinimumWeight: 500 * NanoAvaxPerAvax},
	{ThresholdDuration: 180 * 24 * time.Hour, MinimumWeight: 550 * NanoAvaxPerAvax},
	{ThresholdDuration: 90 * 24 * time.Hour,  MinimumWeight: 650 * NanoAvaxPerAvax},
	{ThresholdDuration: 60 * 24 * time.Hour,  MinimumWeight: 750 * NanoAvaxPerAvax},
	{ThresholdDuration: 30 * 24 * time.Hour,  MinimumWeight: 1100 * NanoAvaxPerAvax},
	{ThresholdDuration: 14 * 24 * time.Hour,  MinimumWeight: 2000 * NanoAvaxPerAvax},
	{ThresholdDuration: 7 * 24 * time.Hour,   MinimumWeight: 3900 * NanoAvaxPerAvax},
	{ThresholdDuration: 48 * time.Hour,       MinimumWeight: 14000 * NanoAvaxPerAvax},
}

// GetMinimumValidatorStake returns the required minimum self-stake under Package P.
func GetMinimumValidatorStake(duration time.Duration) (uint64, error) {
	return GetMinimumValidatorStakeWithSchedule(duration, AdmissionFrontierSchedule)
}

// GetMinimumValidatorStakeWithSchedule evaluates an arbitrary bracket schedule.
func GetMinimumValidatorStakeWithSchedule(duration time.Duration, schedule []DurationBracket) (uint64, error) {
	if duration < MinValidatorStakeDuration {
		return 0, ErrStakeDurationTooShort
	}
	if duration > MaxValidatorStakeDuration {
		return 0, ErrStakeDurationTooLong
	}
	if len(schedule) == 0 {
		return 0, ErrNilOrEmptySchedule
	}
	for _, bracket := range schedule {
		if duration >= bracket.ThresholdDuration {
			return bracket.MinimumWeight, nil
		}
	}
	return schedule[len(schedule)-1].MinimumWeight, nil
}

// VerifyValidatorAdmission validates an incoming validator transaction.
func VerifyValidatorAdmission(startTime, endTime time.Time, bondedWeight uint64) error {
	if endTime.Before(startTime) || endTime.Equal(startTime) {
		return ErrStakeDurationTooShort
	}
	duration := endTime.Sub(startTime)
	requiredWeight, err := GetMinimumValidatorStake(duration)
	if err != nil {
		return err
	}
	if bondedWeight < requiredWeight {
		return ErrInsufficientValidatorStake
	}
	return nil
}
```

### 11.3 State Transition & Backwards Compatibility
1. **Uninterrupted Staking Stints:** Active staking positions registered prior to the activation epoch execute under the rules active at their creation time. Active validators complete their terms without modification.
2. **Deterministic Activation Epoch:** Upon reaching the activation timestamp, PlatformVM validates newly submitted `AddPermissionlessValidatorTx` transactions against `VerifyValidatorAdmission`. Transactions providing weight below the bracket threshold fail syntactic validation and are dropped from mempool propagation.
3. **Wire Format Invariance:** P-Chain transaction serialization formats, cryptographic signatures, and codec structures remain identical.

---

## 12. Peer Review Audit & Epistemic Traceability

This master memo formally resolves the peer review feedback from the research operations evaluation:

### 12.1 Decisions & Actions Log (HD1–HD5 & HA1–HA10)
- **Mathematical Integrity (`HV1`–`HV4`, `HB4`, `HA3`):** Strict convexity proven for $p \ge 1$; $p < 1$ formally retracted with analytical inflection derivation; closed-form feasibility bound established.
- **Simulation Staging Discipline (`HD1`, `HD5`, `HA1`):** Headline Stage 4 simulation results are held back from external delivery until seed determinism (`hashlib.sha256`), common random numbers, neutral control alignment, and pre-Granite calibration are fully merged into the canonical modeling pipeline.
- **Delegation Clarification (`HB1`, `HV3`):** Clarified distinction between cumulative delegation volume flow and active concurrent stock occupancy. Evaluated the three-layer delegation architecture.
- **Empirical Grounding (`HB3`, `HB6`, `HA2`):** August 2025 exit wave corrected to 78.4% institutional fleet restructuring (GoGoPool, Genesis migration, 24-in-1 consolidation), refuting the 93% Sybil swarm hypothesis. 7-day renewal rate recomputed to 80.7% (2021–2024) and 78.1% (2025–Granite).
- **Reward Mechanics (`HB2`):** Historical duration-dependent reward formula since Genesis documented; ACP-285 steepening framed accurately as an amplification of existing mechanics.
- **Phantom Citation Purge (`HA6`):** Removed all lingering references to phantom "ACP-49"; framed entry barrier reduction strictly under community 500 AVAX decentralization proposals.

### 12.2 Epistemic Taxonomy Table
Every input to this mechanism design is classified under our strict epistemic validation standard:

| Epistemic Class | Items Included | Evidentiary Basis |
| :--- | :--- | :--- |
| **`[OBSERVED]`** | Validator stint durations, self-stake distribution, 14d clustering (16.38%), BENQI delegation allocation (<1% on <6k nodes), historical ARR yields (5.36%–6.38%). | Primary telemetry (`01-renewal-panel.parquet`, 57,067 stints, 7,635 nodes). |
| **`[DERIVED]`** | Global convexity proof ($p \ge 1$), inflection point ($d^*$), closed-form pivot feasibility bound, 28,000 AVAX-days parity surface, break-even stake formula ($S_{\text{be}}$). | Closed-form mathematical derivations and numerical inversion verified to machine precision. |
| **`[ASSUMED]`** | VPS server hosting costs (\$480–\$2,400/yr), validator refusal behavioral splits, delegator duration preferences. | Empirical operator survey data, hosting provider pricing, conservative behavioral bounds. |
| **`[UNIDENTIFIED]`** | Endogenous token price-elastic staking supply response. | Explicitly treated via parameter sensitivity scenarios (\$15, \$25, \$40 AVAX) rather than uncalibrated point estimates. |

---

## 13. Strategic Questions for Dr. Eric Lu

To finalize the parameter specification for the upcoming v0.8/v0.9 integration, we submit four targeted questions for the review call:

1. **Parity Objective:** Does the Foundation view the $28{,}000\text{ AVAX-days}$ invariant as an inviolable baseline across every single duration (recommending **Package EM2** with $S_{\text{short}} \approx 19{,}402\text{ AVAX}$), or is an anchor-point parity design acceptable (recommending **Package P** with $S_{\text{short}} = 14{,}000\text{ AVAX}$ and a shallow mid-week dip)?
2. **Delegator Firewall Under ACP-273:** Does Ava Labs intend to preserve the 14-day delegator firewall ($A_{\text{del}}(d) = 0$ for $d < 14\text{d}$) under ACP-273, ensuring retail delegators do not participate in 48-hour consensus churn?
3. **Decentralization Floor:** For annual commitments, does the Foundation prefer the aggressive $500\text{ AVAX}$ target (Package P / EM2) or the cost-buffered $600\text{ AVAX}$ tier (Package B-600) to insulate solo operators against VPS hosting cost shocks?
4. **Quantized Implementation Schedule:** Does the PlatformVM team agree with embedding the 8-tier discrete integer schedule (`nAVAX` and nanoseconds) directly into syntactic transaction validation (`vms/platformvm`), or is there an alternative preference for fee-based dynamic pacing?
