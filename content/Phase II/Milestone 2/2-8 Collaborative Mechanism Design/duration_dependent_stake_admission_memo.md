# Technical Mechanism Design Memo: Duration-Dependent Consensus Admission Frontiers ($S_{\min}(d)$)

| Field | Value |
| :--- | :--- |
| **Author** | Hasher Nabi ([@coad1024-cmd](https://github.com/coad1024-cmd)), Bonding Curves Research Group (BCRG) |
| **Topic** | Protocol Admission Geometry, Sybil Resistance, and Validator Invariants under ACP-273 |
| **Audience** | Dr. Eric Lu, Ava Labs PlatformVM Architecture Team, BCRG Governance Group |
| **Date** | October 2, 2026 |
| **Target Review Gate** | Model v0.7.0 Handoff & Milestone 2 Collaborative Mechanism Review (October 2, 2026) |
| **Status** | Complete Peer-Reviewed Specification (Incorporating Review Gates HD1–HD5 & HA1–HA10) |
| **Artifact Codebase** | `src/avalanche_research/mechanisms/admission.py` & `BoundedHarmonicFrontier` |

---

## Executive Summary

Avalanche consensus governance is currently navigating two interconnected structural proposals:
1. **ACP-273:** Reduces the minimum validator staking duration from 14 days down to 48 hours to provide capital liquidity and improve staking optionality.
2. **Community Decentralization Proposals:** Proposes lowering the minimum validator self-stake entry threshold from 2,000 AVAX to 500 AVAX to expand sovereign home validation.

> [!CAUTION]
> **The Decoupled Enactment Failure Mode:**  
> If enacted independently as static, uncoupled parameters, an operator could occupy an active Primary Network consensus slot with only **500 AVAX locked for 48 hours**. This collapses the capital-time economic commitment from the historical Mainnet baseline of **28,000 AVAX-days** down to **1,000 AVAX-days**—a **96.43% reduction in economic security**. This subsidizes transient speculative capital, increases Snowman consensus sample variance, and induces severe PlatformVM state churn (up to 182.5 validator churn cycles per year per continuous node).

**The Proposed Mechanism:** Rather than treating duration ($d$) and minimum self-stake ($S$) as independent static scalars, the protocol couples them via a continuous **Bounded Harmonic Admission Frontier** $S_{\min}(d)$.

Under this mechanism:
- **Earned Decentralization:** Sovereign home operators access the 500 AVAX (or 600 AVAX) minimum stake barrier by committing capital for 365 days.
- **Anti-Churn & Sybil Defense:** Short-duration stakers utilizing the 48-hour window must post a substantial anchor bond ($S_{\text{short}} = 14{,}000\text{ to }19{,}400\text{ AVAX}$), preserving consensus skin-in-the-game.
- **Zero Disenfranchisement:** 100% of historical 14-day stints at 2,000 AVAX satisfy the admission frontier ($S_{\min}(14) \le 2{,}000\text{ AVAX}$).
- **Deterministic Consensus Implementation:** The continuous formulation is quantized into an 8-tier discrete integer lookup table in nanoseconds and `nAVAX`, eliminating floating-point non-determinism during PlatformVM block validation.

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

---

## 2. Empirical Grounding (57,067 Staking Periods, 7,635 Nodes)

Telemetry from the primary dataset (`01-renewal-panel.parquet`), covering 57,067 completed validator periods across 7,635 physical nodes from Genesis to Helicon, establishes empirical boundary conditions:

### 2.1 Distributional Realities
- **Clustering at the Floor:** The median self-bond is 2,015 AVAX (mean 97,264 AVAX). 74.8% of all validator stints (42,710 records) bonded between 2,000 and 6,000 AVAX.
- **Duration Compression:** The unweighted median duration across all history is 23.0 days (mean 45.6 days). Staking periods of exactly 14 days represent 16.38% of all stints (9,347 records). Following the Etna upgrade, median duration compressed to 15.0 days.
- **Capital vs. Count Divergence:** Commitments under 16 days represent 62% to 69% of new stints during Durango/Fortuna, but represent only 3% to 5% of committed AVAX-days. Small operators choose the minimum duration, while institutional capital locks for longer horizons.

### 2.2 Duration Persistence & Habits
The empirical record shows strong behavioral inertia:
- Correlation across consecutive stints: $\text{Corr}(d_t, d_{t-1}) = 0.690$.
- **44.54% of renewing validators repeat their exact duration**.
- **75.32% remain within the same duration bucket**.
- Stakers $\le 2,500\text{ AVAX}$ choose $\le 21\text{ days}$ in 57.6% of stints. Whales ($> 100,000\text{ AVAX}$) select $\ge 66\text{ days}$ in 34.5% of stints.

### 2.3 Contextualizing the August 2025 Exit Wave
The exit of over 500 nodes in August 2025 was previously hypothesized as an adversarial sybil-swarm attack. Forensic analysis of on-chain records reveals the true structure:
- August 2025 saw 602 gross validator exits and 96 entrants (net decline of 506 nodes).
- The top 5 exiting entities represented **472 of 602 gross exits (78.4%)**.
- These exits were dominated by:
  1. **GoGoPool Liquid Staking:** Institutional rebalancing of 296 liquid staking nodes.
  2. **Genesis Holder Migration:** A single early holder reorganizing 85 nodes into liquid delegation.
  3. **Node Consolidation:** An operator merging 24 separate 2,000-AVAX nodes into a single high-stake validator.
- **Design Insight:** Large operators manage fleets. An admission barrier $S_{\text{short}}$ effectively suppresses transient, high-frequency fleet splitting while accommodating legitimate institutional infrastructure.

---

## 3. Mathematical Specification: Bounded Harmonic Frontier

### 3.1 Canonical Functional Form
The admission frontier is defined on the closed domain $d \in [d_{\min}, d_{\max}] = [2, 365\text{ days}]$ by the **Continuous Bounded Harmonic Decay Function**:

$$S_{\min}(d) = S_{\text{floor}} + (S_{\text{short}} - S_{\text{floor}}) \cdot \eta(d)^p = S_{\text{floor}} + \Delta S \cdot \left[ \frac{\frac{1}{d} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}} \right]^p$$

where:
- $d_{\min} = 2\text{ days}$ (the ACP-273 consensus floor).
- $d_{\max} = 365\text{ days}$ (the annual staking ceiling).
- $S_{\text{floor}} \in [500, 600]\text{ AVAX}$ (the long-term decentralization floor).
- $S_{\text{short}} \in [14{,}000, 20{,}000]\text{ AVAX}$ (the short-duration anchor bond).
- $\eta(d)$ is the normalized inverse duration kernel:
  $$\eta(d) = \frac{\frac{1}{d} - \frac{1}{365}}{\frac{1}{2} - \frac{1}{365}} = \frac{\frac{1}{d} - 0.0027397}{0.4972603}$$

Key evaluations of the kernel $\eta(d)$:
$$\eta(2) = 1.000000, \quad \eta(7) = 0.281804, \quad \eta(14) = 0.138135, \quad \eta(30) = 0.061524, \quad \eta(365) = 0.000000$$

### 3.2 Proof of Strict Convexity for $p \ge 1$
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

### 3.3 Formal Retraction of the $p < 1$ Regime
Earlier preliminary drafts examined $p \approx 0.60\text{--}0.65$. Mathematical audit proves that when $p < 1$:
1. **Inflection Point:** $S''_{\min}(d^*) = 0$ occurs at:
   $$d^* = \frac{p+1}{2} \cdot d_{\max}$$
   For $p = 0.62$, an inflection occurs at $d^* = 295.6\text{ days}$. For $d > d^*$, the curve becomes concave.
2. **Infinite Terminal Slope:** As $d \to d_{\max}$, $\eta(d) \to 0$, causing $\eta(d)^{p-1} \to \infty$ for $p < 1$. The derivative diverges: $\lim_{d \to 365} S'_{\min}(d) = -\infty$.

**Conclusion:** The parameter space is strictly restricted to $p \ge 1.0$.

### 3.4 Closed-Form Pivot Feasibility Condition
Governance can calibrate the curve by specifying a target pivot point $(d_{\text{pivot}}, S_{\text{pivot}})$. Inverting the equation for $p$:
$$p = \frac{\ln\left(\frac{S_{\text{pivot}} - S_{\text{floor}}}{S_{\text{short}} - S_{\text{floor}}}\right)}{\ln(\eta(d_{\text{pivot}}))}$$

To ensure $p \ge 1$, the ratio must satisfy $\frac{S_{\text{pivot}} - S_{\text{floor}}}{S_{\text{short}} - S_{\text{floor}}} \le \eta(d_{\text{pivot}})$, yielding the **Convex Feasibility Bound**:
$$S_{\text{pivot}} \le S_{\text{floor}} + (S_{\text{short}} - S_{\text{floor}}) \cdot \eta(d_{\text{pivot}})$$

---

## 4. The 28,000 AVAX-Days Parity Landscape

The quantity $K(d) = S_{\min}(d) \cdot d$ measures the capital-time commitment across durations:
$$K(d) = S_{\text{floor}} \cdot d + (S_{\text{short}} - S_{\text{floor}}) \cdot d \cdot \eta(d)^p$$

The review establishes that the historical baseline $K_{\text{base}} = 28{,}000\text{ AVAX-days}$ serves as an **empirical reference anchor and reported KPI**, rather than an inviolable security constant across every single duration:

1. **Full Uniform Parity (Package EM2):** To enforce $K(d) \ge 28{,}000\text{ AVAX-days}$ across *all* durations $d \in [2, 365]$ while keeping $S(14) \le 2{,}000\text{ AVAX}$, the short-end barrier must be set to:
   $$S_{\text{short}} = 19{,}402\text{ AVAX} \quad \text{with} \quad p = 1.282 \quad (S_{\text{floor}} = 500\text{ AVAX})$$
   Under EM2, $K(2) = 38{,}804\text{ AVAX-days}$ ($1.39\times$), $K(14) = 28{,}000\text{ AVAX-days}$ ($1.00\times$), and the minimum across the entire curve is $27{,}998\text{ AVAX-days}$.
2. **Anchor-Point Parity (Package P):** If governance prefers a lower 48-hour barrier ($S_{\text{short}} = 14{,}000\text{ AVAX}$), parity holds exactly at 48 hours ($14{,}000 \times 2 = 28{,}000$) and at 14 days ($2{,}000 \times 14 = 28{,}000$). Between 3 and 10 days, $K(d)$ experiences a shallow, controlled dip (reaching a minimum of $24{,}513\text{ AVAX-days}$ at 6 days, a 12.4% discount).

---

## 5. Calibrated Governance Parameter Packages

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

**Recommendation:** 
- **Package EM2** is recommended if the Foundation requires strict $28{,}000\text{ AVAX-days}$ capital-time preservation across every single duration.
- **Package P** is recommended if governance prioritizes setting an accessible $14{,}000\text{ AVAX}$ barrier for 48-hour institutional testing while preserving the 2,000 AVAX barrier at 14 days.

---

## 6. Behavioral Mechanics: The Validator Refusal Rule

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
2. **Capital Addition (Primary Path for Institutional Operators):** Stakers desiring strict liquidity horizons (e.g. market makers needing 48-hour turnaround) deposit the necessary incremental capital $\Delta S = S_{\min}(d_{\text{pref}}) - S$.
3. **Exit / Churn Abandonment:** Operators unwilling to extend duration and lacking capital exit the active set. In empirical testing, solo nodes face higher liquidity friction than commercial nodes, meaning an appropriate short barrier effectively filters out low-commitment transient actors.

---

## 7. Three-Layer Delegation Architecture

A critical finding from the peer review is that **delegation flow must be distinguished from active concurrent stock**, and concurrent delegation is bounded by the protocol cap ($4 \times S_{\text{self}}$) and node cap ($3{,}000{,}000\text{ AVAX}$).

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

**Key Implication:** An operator attempting to spin up a 48-hour validator receives zero delegation by protocol rule. A small 500 AVAX validator at 365 days is eligible for protocol delegation, but must build reputation or self-stake to meet liquid staking provider thresholds.

---

## 8. Economic Grounding of $S_{\text{floor}}$: Hosting Cost Bands & Solvency

Lowering $S_{\text{floor}}$ to 500 or 600 AVAX raises the question: can a node with 500 AVAX earn enough staking rewards to cover real-world server operating costs?

### 8.1 Real-World Server Cost Tiers
- **Tier 1 (Bare Metal / Low-Cost VPS, e.g. Hetzner):** \$480 to \$600 / year (\$40 to \$50 / month).
- **Tier 2 (Commercial Cloud / Mid-Tier VPS):** \$1,200 to \$1,440 / year (\$100 to \$120 / month).
- **Tier 3 (Enterprise Redundant Cloud, e.g. AWS Multi-AZ):** \$2,400 to \$4,200 / year.

### 8.2 Break-Even Solvency Analysis
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

## 9. Historical Yield Structure Clarification

To maintain rigorous historical accuracy:
- Protocol rewards have rewarded duration since Genesis:
  $$\text{ARR}(d) = r_{\min} + (r_{\max} - r_{\min}) \cdot \frac{d}{365}$$
  Paying **5.36% at 14 days** and **6.38% at 365 days** (at 470M AVAX supply).
- **ACP-285** widens this duration premium by lowering the consumption rate floor to 7.5%, expanding the spread from ~1.02 percentage points to ~2.30 percentage points.
- **Instrument Synergy:** The Admission Frontier $S_{\min}(d)$ acts as the consensus gatekeeper, filtering out short-term churn, while ACP-285 acts as the macroeconomic incentive steering large capital toward longer commitments.

---

## 10. PlatformVM Consensus Quantization (8-Tier Integer Schedule)

Floating-point operations inside consensus validation paths create cross-platform verification divergences. We provide the complete, deterministic 8-tier integer quantization schedule in nanoseconds and `nAVAX` ($1\text{ AVAX} = 10^9\text{ nAVAX}$):

```go
// PlatformVM Duration-Dependent Minimum Stake Lookup (Package P / EM2)
// Durations in nanoseconds, Stake in nAVAX
func GetMinValidatorStake(duration time.Duration) uint64 {
    const (
        Day = 24 * time.Hour
        GigaAvax = 1_000_000_000
    )
    switch {
    case duration < 2*Day:
        return math.MaxUint64 // Reject: below protocol minimum
    case duration < 7*Day:
        return 14_000 * GigaAvax // Tier 1: 48h Anchor
    case duration < 14*Day:
        return 3_900 * GigaAvax  // Tier 2: Mid-week Tier
    case duration < 30*Day:
        return 2_000 * GigaAvax  // Tier 3: 14d Mainnet Parity
    case duration < 60*Day:
        return 1_100 * GigaAvax  // Tier 4: 1-Month Tier
    case duration < 90*Day:
        return 750 * GigaAvax    // Tier 5: 2-Month Tier
    case duration < 180*Day:
        return 650 * GigaAvax    // Tier 6: Quarter Tier
    case duration < 365*Day:
        return 550 * GigaAvax    // Tier 7: Half-Year Tier
    default:
        return 500 * GigaAvax    // Tier 8: Annual Decentralization Floor
    }
}
```

---

## 11. Strategic Questions for Dr. Eric Lu

To finalize the parameter specification for the upcoming v0.8/v0.9 integration, we submit three targeted questions:

1. **Parity Objective:** Does the Foundation view the $28{,}000\text{ AVAX-days}$ invariant as an inviolable baseline across every single duration (recommending **Package EM2** with $S_{\text{short}} \approx 19{,}400\text{ AVAX}$), or is an anchor-point parity design acceptable (recommending **Package P** with $S_{\text{short}} = 14{,}000\text{ AVAX}$ and a shallow mid-week dip)?
2. **Delegator Firewall:** Does Ava Labs intend to preserve the 14-day delegator firewall ($A_{\text{del}}(d) = 0$ for $d < 14\text{d}$) under ACP-273, ensuring retail delegators do not participate in 48-hour churn?
3. **Decentralization Floor:** For annual commitments, does the Foundation prefer the aggressive $500\text{ AVAX}$ target or the cost-buffered $600\text{ AVAX}$ tier to insulate against VPS hosting cost shocks?
