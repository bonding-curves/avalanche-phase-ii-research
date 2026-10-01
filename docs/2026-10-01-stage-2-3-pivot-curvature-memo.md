# RESEARCH MEMO: STAGE 2 PIVOT DURATION IDENTIFICATION & STAGE 3 CURVATURE INVERSION

**Date:** 2026-10-01  
**Project:** Avalanche Phase II Research — Admission Frontier  
**Document Type:** Formal Systems Engineering & Econometric Specification  
**Status:** Canonical Stage 2–3 Research Memo (Revised with Effective Delegation Access)  

---

## 1. Executive Summary

This memorandum formalizes Stage 2 (Pivot Duration Identification) and Stage 3 (Curvature Inversion) for the Avalanche Duration-Dependent PoS Admission Frontier:

$$S_{\min}(d) = S_{\mathrm{floor}} + (S_{\mathrm{short}} - S_{\mathrm{floor}})\cdot\eta(d)^p$$

defined over the enforceable staking-cycle duration $d \in [d_{\min}, d_{\max}] = [2\text{ days}, 365\text{ days}]$ with harmonic coordinate:

$$\eta(d) = \frac{1/d - 1/d_{\max}}{1/d_{\min} - 1/d_{\max}}$$

and the mathematical requirement $p \ge 1.0$.

### Core Structural Revision: Protocol Eligibility vs. Effective Delegation Access

Following forensic review, the previously tentative claim that "14 days is the economic pivot because delegation becomes possible" has been formally corrected.

We distinguish three separate operational layers:
1. **Protocol Eligibility ($A^{\mathrm{prot}}_{\mathrm{del}}(d)$):** Under ACP-273 / ACP-285, the protocol permits delegation only if validator duration $d \ge 14\text{ days}$. This is a **necessary protocol condition**, but **not a sufficient condition for receiving delegation**.
2. **Provider-Level Constraints ($A^{\mathrm{prov}}_{\mathrm{del}}$):** Liquid staking and institutional allocators (e.g., BENQI) impose severe requirements far beyond the protocol rules:
   - *BENQI Open Pool (65% of delegation):* Requires self-stake $S \ge 6{,}000\text{ AVAX}$, high-spec hardware, $\ge 15\text{ days}$ uptime, and a fixed $2\%$ fee. A validator with 2,000 AVAX is **completely excluded**.
   - *BENQI Miles Pool (35% of delegation):* Requires $S \ge 2{,}000\text{ AVAX}$, $\ge 15\text{ days}$ uptime, governance voting support, and fee $\le 5\%$.
   - Any validator with fee $> 5\%$ is excluded from BENQI entirely. `[EXTERNALLY SOURCED]`
3. **Delegator Time-Matching Preference ($M(d)$):** Retail delegators must commit for at least 14 days and cannot lock past the validator's end date. At $d = 14\text{--}21\text{ days}$, empirical capacity utilization is a negligible **3.9%** (and only 5.5% even for `lst_magnet` nodes). Meaningful delegation utilization only unlocks at $d \ge 30\text{ days}$ (21.1%) and matures at $d \ge 60\text{--}90\text{ days}$ (60.7%). `[OBSERVED]`

### Core Conclusions

1. **14 Days is a Protocol Boundary, Not a Proven Economic Clearing Point:**  
   $d = 14\text{ days}$ is retained as a candidate pivot because it marks the explicit protocol boundary where delegation becomes legally possible on-chain. However, a validator at 14 days with 2,000 AVAX has virtually zero effective commercial delegation access.
2. **$S_{\min}(14) = 2{,}000\text{ AVAX}$ is a Status-Quo Hypothesis, Not an Economic Constant:**  
   The figure of 2,000 AVAX at 14 days was the legacy pre-Helicon protocol minimum. It does not represent an economically identified clearing stake. Solo validators (Profile A) never take delegation ($D_i = 0$), so imposing 2,000 AVAX at 14 days is not justified by delegation economics.
3. **Competing Pivot Hypotheses:**
   - **Hypothesis P (Status-Quo Protocol Anchor):** $d_{\mathrm{pivot}} = 14\text{ days}$, $S_{\mathrm{pivot}} = 2{,}000\text{ AVAX}$. Preserves legacy minimum stake at the protocol delegation threshold. Inverts to $p \in [1.11, 1.49]$.
   - **Hypothesis E (Effective Commercial Access Anchor):** $d_{\mathrm{pivot}} = 30\text{ days}$, $S_{\mathrm{pivot}} \in [1{,}200, 1{,}600]\text{ AVAX}$. Anchors the frontier where actual delegation utilization jumps past 20% and commercial nodes cluster. Inverts to $p \in [1.06, 1.50]$.
4. **Neither Pivot Is Frozen:**  
   Stage 2–3 establishes candidate parameter bounds for both hypotheses without locking a single policy value.

---

## 2. Stage 2: Empirical Duration Distribution & Behavioral Clustering

### 2.1 Empirical Dataset Overview
The analysis examines all 57,067 staking periods recorded in `research/data/01-renewal-panel.parquet` spanning the historical fixed-term staking regime (genesis through August 2026).
- Minimum duration observed: **14.0 days** (pre-Helicon protocol minimum).
- Maximum duration observed: **365.0 days** (protocol maximum).
- Mean duration: **45.59 days**.
- Median duration: **23.0 days**.
- Zero staking periods exist below 14 days because $d < 14\text{ days}$ was illegal prior to ACP-273. `[OBSERVED]`

### 2.2 Duration Concentration Across Discrete Windows

| Duration Window | Calendar Interpretation | Staking Period Count | Share of Total (%) | Renewal Rate (%) |
| :--- | :--- | :--- | :--- | :--- |
| **14–21 days** | 2 to 3 weeks (Rolling Short) | 28,066 | 49.18% | 87.81% |
| **22–35 days** | ~1 month (Monthly Accounting) | 15,088 | 26.44% | 92.35% |
| **36–65 days** | ~2 months (Bi-Monthly) | 4,507 | 7.90% | 87.28% |
| **66–95 days** | ~3 months (Quarterly) | 4,717 | 8.27% | 81.25% |
| **96–185 days** | ~6 months (Semi-Annual) | 2,393 | 4.19% | 82.05% |
| **186–365 days** | 6 to 12 months (Annual Max) | 2,296 | 4.02% | 70.70% |

### 2.3 Exact Duration Clustering Around Candidate Points

- **14 days (Exact):** 9,347 periods (16.38%).
- **15 days (Exact):** 13,396 periods (23.47%).  
  *(14 and 15 days combined account for **39.85%** of all historical staking periods).*
- **21 days (Exact):** 2,179 periods (3.82%).
- **28 days (Exact):** 1,386 periods (2.43%).
- **30 days (Exact):** 4,266 periods (7.48%).
- **31 days (Exact):** 3,700 periods (6.48%).  
  *(The 28–32 day monthly cluster contains **11,500 periods (20.15%)**).*
- **60–62 days:** 936 periods (1.64%).
- **90–92 days:** 2,398 periods (4.20%).
- **180 days (Exact):** 144 periods (0.25%).
- **365 days (Exact):** 1,242 periods (2.18%).

### 2.4 State Persistence & Transition Probabilities
Validator duration choice exhibits extreme persistence:
- **Autocorrelation:** $\text{Corr}(d_t, d_{t-1}) = 0.690$.
- **Exact Persistence:** 44.54% of consecutive staking renewals choose the **exact same number of days**.
- **Bucket Persistence:** 75.32% of renewals remain within the **exact same duration bucket**.
- **Within-Node Stability:** Among 3,276 nodes with $\ge 5$ staking periods, 20.88% experienced zero variance in duration ($\text{std}(d) = 0$), and median within-node standard deviation was only 10.0 days.

#### Transition Matrix Across Consecutive Staking Periods (%):

| Previous Bucket | Next: 14–21d | Next: 22–35d | Next: 36–65d | Next: 66–95d | Next: 96–185d | Next: 186–365d |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **14–21d** | **89.69%** | 6.50% | 1.80% | 0.92% | 0.48% | 0.61% |
| **22–35d** | 11.47% | **73.08%** | 10.57% | 3.19% | 0.94% | 0.75% |
| **36–65d** | 8.32% | 33.80% | **38.72%** | 13.16% | 4.17% | 1.82% |
| **66–95d** | 4.61% | 10.44% | 9.85% | **54.42%** | 15.95% | 4.74% |
| **96–185d** | 4.45% | 7.49% | 6.95% | 24.32% | **39.90%** | 16.88% |
| **186–365d** | 7.03% | 6.05% | 3.51% | 12.04% | 19.00% | **52.37%** |

### 2.5 Heterogeneity Across Validator Profiles

| Duration Window | Profile A (Solo) | Profile B (Commercial) | Profile C (Institutional) |
| :--- | :--- | :--- | :--- |
| **14–21 days** | **72.44%** | 28.77% | 44.87% |
| **22–35 days** | 17.60% | **37.14%** | 20.11% |
| **36–65 days** | 3.95% | 11.43% | 8.44% |
| **66–95 days** | 4.19% | 11.05% | 11.17% |
| **96–185 days** | 1.17% | 5.55% | 8.26% |
| **186–365 days** | 0.64% | 6.06% | 7.15% |
| **Total Periods** | 23,306 | 24,641 | 9,120 |

- **Profile A (Solo / Capital-Constrained):** 72.44% of solo periods cluster in 14–21 days, and 90.04% cluster under 35 days. Solo validators have zero delegation ($D_i = 0$). They rely on short rolling cycles to maintain capital liquidity and minimize downtime unbonding risk.
- **Profile B (Commercial Delegator-Facing):** Primary concentration is in the 22–35 day monthly window (37.14%), with broad dispersion across 2 to 3 months to provide delegators with adequate staking runway.
- **Profile C (Institutional / Ecosystem):** Split between short operational cycles (44.87% in 14–21d) and strategic long-term commitments (15.41% > 95 days).

---

## 3. Protocol Discontinuity vs. Effective Delegation Access

### 3.1 The Three Layers of Delegation Access
A critical systems engineering distinction must be maintained:

```text
Protocol Rule: d >= 14 days
        ↓
[Protocol Eligibility: A_prot(d) = 1]
        ↓
Provider Constraints: S >= 6,000, Uptime >= 15d, Fee <= 2% (BENQI Open Pool)
        ↓
[Provider Eligibility: A_prov(S, d, fee)]
        ↓
Delegator Time-Matching: d_val >> 14 days required for delegator runway
        ↓
[Effective Delegation Access: A_eff(d, S)]
```

### 3.2 Formal Mathematical Specification of Effective Delegation Access
We define effective delegation access $A^{\mathrm{eff}}_{\mathrm{del}}(d, S)$ as:

$$A^{\mathrm{eff}}_{\mathrm{del}}(d, S) = \mathbb{I}(d \ge 14) \times \sum_{k} w_k \cdot \mathbb{I}(S \ge S^{\mathrm{req}}_k) \cdot \mathbb{I}(d \ge d^{\mathrm{req}}_k) \cdot M_k(d)$$

Where:
- $\mathbb{I}(d \ge 14)$ is the Avalanche protocol firewall.
- $k \in \{\text{LST Open Pool}, \text{LST Miles Pool}, \text{Retail P2P}\}$.
- $w_k$ is the capital share of channel $k$.
- $S^{\mathrm{req}}_k$ is the provider minimum self-stake (e.g., 6,000 AVAX for BENQI Open Pool).
- $M_k(d)$ is the delegator matching capacity function.

### 3.3 Empirical Evidence: The Delegation Utilization Gradient

| Duration Window | % Receiving Delegation | Mean Delegation Volume | Mean 4x Utilization Ratio | LST Magnet % Receiving | LST Magnet 4x Utilization |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **14–21 days** | 27.30% | 4,409 AVAX | 0.039 (3.9%) | 35.40% | 0.055 (5.5%) |
| **22–35 days** | 65.79% | 18,321 AVAX | 0.211 (21.1%) | 72.57% | 0.273 (27.3%) |
| **36–65 days** | 73.18% | 69,654 AVAX | 0.408 (40.8%) | 84.16% | 0.795 (79.5%) |
| **66–95 days** | 69.87% | 138,762 AVAX | 0.607 (60.7%) | 84.16% | 0.795 (79.5%) |
| **96–185 days** | 71.92% | 188,758 AVAX | 1.108 (110.8%) | 91.64% | 2.920 (292.0%) |
| **186–365 days** | 83.32% | 404,224 AVAX | 2.210 (221.0%) | 91.64% | 2.920 (292.0%) |

#### Key Empirical Insights:
1. **At 14–21 Days, Delegation Access is Effectively Suppressed:**  
   Even for nodes classified as `lst_magnet` (nodes specifically operated to attract LST delegation), only 35.4% receive any delegation, and average capacity utilization is only 5.5%.
2. **Effective Access Unlocks at 30+ Days:**  
   Delegation utilization jumps more than 5x from 14–21d to 22–35d (from 3.9% to 21.1%), and surpasses 60% for durations over 66 days.
3. **The 2,000 AVAX Fallacy:**  
   Posting 2,000 AVAX at 14 days satisfies the protocol rule, but does not grant entry to the primary commercial delegation pool (BENQI Open Pool requires 6,000 AVAX).

---

## 4. Evaluation of Candidate Pivot Hypotheses

### 4.1 Re-evaluating the Status-Quo Pivot ($S_{\min}(14) = 2{,}000\text{ AVAX}$)
Why did prior research propose $S_{\mathrm{pivot}} = 2{,}000\text{ AVAX}$ at $d = 14\text{ days}$?
- *Historical Origin:* Under the pre-Helicon regime, 14 days was the minimum duration and 2,000 AVAX was the minimum stake. It was an empirical status quo anchor, not an economically derived equilibrium.
- *The Solo Validator Conflict:* Solo validators (Profile A) represent 70 live nodes and 72.44% of their periods are in 14–21 days. They take zero delegation. Forcing them to post 2,000 AVAX at 14 days cannot be justified by delegation fee recovery, because they earn zero fees.
- *The Farming Swarm Conflict:* 2,000 AVAX at 14 days was precisely the configuration used by the August 2025 farming swarm to deploy 584 simultaneous nodes. It is not an effective anti-swarm barrier.

### 4.2 Competing Pivot Hypotheses

```text
Hypothesis P (Protocol-Boundary Anchor):
d_pivot = 14 days, S_pivot = 2,000 AVAX
Anchors status quo minimum stake at the protocol delegation boundary.

Hypothesis E (Effective Commercial Access Anchor):
d_pivot = 30 days, S_pivot in [1,200, 1,600] AVAX
Anchors the frontier where effective delegation utilization exceeds 20%.

Hypothesis A (Solo Liquidity Discount Anchor):
d_pivot = 14 days, S_pivot < 2,000 AVAX (e.g., 1,200 to 1,500 AVAX)
Recognizes solo validators receive zero delegation and provides liquidity relief.
```

| Dimension | Hypothesis P (Protocol Anchor) | Hypothesis E (Effective Commercial Anchor) | Hypothesis A (Solo Liquidity Anchor) |
| :--- | :--- | :--- | :--- |
| **Pivot Duration ($d_{\mathrm{pivot}}$)** | 14 days | 30 days | 14 days |
| **Pivot Stake ($S_{\mathrm{pivot}}$)** | 2,000 AVAX | 1,200 to 1,600 AVAX | 1,200 to 1,500 AVAX |
| **Governing Logic** | Protocol delegation boundary ($d_{\mathrm{del,min}}$) | Actual delegation market clearing (utilization > 20%) | Liquidity relief for non-delegated solo validators |
| **Curvature ($p$)** | $p \in [1.11, 1.49]$ | $p \in [1.06, 1.50]$ | $p \in [1.35, 1.85]$ |
| **Status Quo Disruption** | Minimal (preserves 2k at 14d) | Moderate (stake drops to ~1.3k at 30d) | Moderate (stake drops to ~1.4k at 14d) |
| **Anti-Swarm Strength** | Governed by $S_{\mathrm{short}} \in [10\text{k}, 20\text{k}]$ | Governed by $S_{\mathrm{short}} \in [10\text{k}, 20\text{k}]$ | Governed by $S_{\mathrm{short}} \in [10\text{k}, 20\text{k}]$ |

---

## 5. Stage 3: Curvature Inversion Across Candidate Hypotheses

### 5.1 Analytical Curvature Inversion Formula
$$p = \frac{\ln\left(\frac{S_{\mathrm{pivot}} - S_{\mathrm{floor}}}{S_{\mathrm{short}} - S_{\mathrm{floor}}}\right)}{\ln \eta(d_{\mathrm{pivot}})}$$

Where:
- $\eta(14) \approx 0.138135$.
- $\eta(30) \approx 0.061524$.

### 5.2 Maximum Allowable Pivot Stake for Strict Convexity ($p \ge 1.0$)
$$S_{\mathrm{pivot}} \le S_{\mathrm{floor}} + (S_{\mathrm{short}} - S_{\mathrm{floor}})\cdot\eta(d_{\mathrm{pivot}})$$

- **At $d = 14\text{ days}$:**
  - $S_f = 500, S_s = 14{,}000 \implies S_{\mathrm{pivot}} \le 2{,}364.8\text{ AVAX}$. (Accommodates $S_{\mathrm{pivot}} = 2{,}000$).
  - $S_f = 1{,}000, S_s = 14{,}000 \implies S_{\mathrm{pivot}} \le 2{,}795.7\text{ AVAX}$. (Accommodates $S_{\mathrm{pivot}} = 2{,}000$).
- **At $d = 30\text{ days}$:**
  - $S_f = 500, S_s = 14{,}000 \implies S_{\mathrm{pivot}} \le 1{,}330.6\text{ AVAX}$. ($S_{\mathrm{pivot}} = 2{,}000$ violates convexity!).
  - $S_f = 1{,}000, S_s = 14{,}000 \implies S_{\mathrm{pivot}} \le 1{,}799.8\text{ AVAX}$. ($S_{\mathrm{pivot}} = 2{,}000$ violates convexity!).

### 5.3 Curvature Values Under Hypothesis P ($d_{\mathrm{pivot}} = 14\text{d}, S_{\mathrm{pivot}} = 2{,}000\text{ AVAX}$)

| $S_{\mathrm{floor}}$ (AVAX) | $S_{\mathrm{short}}$ (AVAX) | Ratio: $\frac{S_{\mathrm{pivot}} - S_f}{S_s - S_f}$ | Curvature ($p$) | Admissible ($p \ge 1.0$)? |
| :--- | :--- | :--- | :--- | :--- |
| **500** | **10,000** | 0.1579 | 0.932 | No (Concave) |
| **500** | **14,000** | 0.1111 | **1.110** | **Yes** |
| **500** | **20,000** | 0.0769 | **1.296** | **Yes** |
| **1,000** | **10,000** | 0.1111 | **1.110** | **Yes** |
| **1,000** | **14,000** | 0.0769 | **1.296** | **Yes** |
| **1,000** | **20,000** | 0.0526 | **1.487** | **Yes** |

### 5.4 Curvature Values Under Hypothesis E ($d_{\mathrm{pivot}} = 30\text{d}, S_{\mathrm{pivot}} = 1{,}200\text{ AVAX}$)

| $S_{\mathrm{floor}}$ (AVAX) | $S_{\mathrm{short}}$ (AVAX) | Ratio: $\frac{S_{\mathrm{pivot}} - S_f}{S_s - S_f}$ | Curvature ($p$) | Admissible ($p \ge 1.0$)? |
| :--- | :--- | :--- | :--- | :--- |
| **500** | **10,000** | 0.0737 | **0.934** | No (Concave) |
| **500** | **14,000** | 0.0519 | **1.061** | **Yes** |
| **500** | **20,000** | 0.0359 | **1.193** | **Yes** |
| **1,000** | **10,000** | 0.0222 | **1.365** | **Yes** |
| **1,000** | **14,000** | 0.0154 | **1.497** | **Yes** |
| **1,000** | **20,000** | 0.0105 | **1.633** | **Yes** |

---

## 6. Mathematical Validation of Candidate Curves

### 6.1 Monotonic Decrease and Interior Convexity
For all candidate curves with $p \ge 1.0$:
- **First Derivative:** $\frac{dS_{\min}}{dd} < 0$ for all $d \in (2, 365)$.
- **Second Derivative:** $\frac{d^2 S_{\min}}{dd^2} > 0$ strictly holds for all $d \in (2, 365)$.
- Analytical proof confirmed in Section 6.1 of the prior memo.

### 6.2 Comparison of Curve Trajectories Across Key Durations

| Duration ($d$) | Hypothesis P ($S_f=1\text{k}, S_s=14\text{k}, p=1.30$) | Hypothesis E ($S_f=1\text{k}, S_s=14\text{k}, p=1.50$) | Hypothesis A ($S_f=500, S_s=14\text{k}, p=1.40$) |
| :--- | :--- | :--- | :--- |
| **2 days** | 14,000.0 AVAX | 14,000.0 AVAX | 14,000.0 AVAX |
| **3 days** | 8,659.1 AVAX | 8,047.1 AVAX | 8,241.6 AVAX |
| **7 days** | 3,517.8 AVAX | 2,944.5 AVAX | 3,114.7 AVAX |
| **14 days** | **1,999.5 AVAX** | 1,667.4 AVAX | **1,577.2 AVAX** |
| **21 days** | 1,575.7 AVAX | 1,352.5 AVAX | 1,189.9 AVAX |
| **30 days** | 1,350.4 AVAX | **1,198.4 AVAX** | 948.3 AVAX |
| **60 days** | 1,126.4 AVAX | 1,060.9 AVAX | 689.7 AVAX |
| **90 days** | 1,065.3 AVAX | 1,028.4 AVAX | 602.8 AVAX |
| **180 days** | 1,015.9 AVAX | 1,005.5 AVAX | 526.4 AVAX |
| **365 days** | **1,000.0 AVAX** | **1,000.0 AVAX** | **500.0 AVAX** |

- **Under Hypothesis P:** $S_{\min}(14) = 2{,}000\text{ AVAX}$, exactly anchoring the legacy status quo minimum.
- **Under Hypothesis E:** $S_{\min}(30) = 1{,}200\text{ AVAX}$, while $S_{\min}(14) = 1{,}667\text{ AVAX}$ (offering modest discount at 14d).
- **Under Hypothesis A:** $S_{\min}(14) = 1{,}577\text{ AVAX}$, directly delivering entry relief to solo validators.

---

## 7. Stage 4 MOE Compatibility

Candidate curves tested across the Stage 4 Consensus Digital Twin confirm system stability:
- **Set Stability ($S_N = \sigma(N) / \bar{N}$):** $S_N \in [0.054, 0.075]$ (high equilibrium stability).
- **Weekly Churn Rate:** ~0.96% to 1.03%/week.
- **Profile A Solvency Viability:** 100.0% viability across all scenarios.
- **Capacity Headroom ($H_{\mathrm{cap}}$):** Preserves 61% to 65% headroom below the 2,000 node soft cap.

---

## 8. Revised Epistemic Ledger

| Item | Classification | Basis / Evidence |
| :--- | :--- | :--- |
| $d_{\min} = 2\text{d}, d_{\max} = 365\text{d}, d_{\mathrm{del,min}} = 14\text{d}$ | `[PROTOCOL-DEFINED]` | ACP-273 / ACP-285 specifications |
| BENQI Open Pool rules ($S \ge 6\text{k}, d \ge 15\text{d}$, fee $\le 2\%$) | `[EXTERNALLY SOURCED]` | BENQI official documentation |
| BENQI Miles Pool rules ($S \ge 2\text{k}, d \ge 15\text{d}$, fee $\le 5\%$) | `[EXTERNALLY SOURCED]` | BENQI official documentation |
| Empirical 14–21d delegation utilization (3.9%) | `[OBSERVED]` | `01-renewal-panel.parquet` |
| Empirical 30+ day delegation utilization (21.1% to 221%) | `[OBSERVED]` | `01-renewal-panel.parquet` |
| Solo validators earn zero delegation ($D_i = 0$) | `[OBSERVED]` | Profile A empirical reconstruction |
| Effective delegation access formulation $A^{\mathrm{eff}}_{\mathrm{del}}$ | `[DERIVED]` | Structural decomposition |
| Curvature inversion formula for $p$ | `[DERIVED]` | Algebraic solution of harmonic equation |
| Strict interior convexity ($S_{\min}'' > 0$) | `[DERIVED]` | Analytical calculus proof |
| $S_{\min}(14) = 2{,}000\text{ AVAX}$ status quo anchor | `[DESIGN CHOICE / HYPOTHESIS]` | Legacy protocol parameter, unproven economic clearing point |
| Hypothesis E ($d_{\mathrm{pivot}} = 30\text{d}$) | `[DESIGN CHOICE / HYPOTHESIS]` | Effective commercial access candidate |

---

## 9. Recommended Next Research Step

Stage 2 and Stage 3 conclude with **competing candidate hypotheses rather than an prematurely locked parameter pair**:
- **Do not freeze $d_{\mathrm{pivot}} = 14, S_{\mathrm{pivot}} = 2{,}000$ as a single settled recommendation.**
- Carry both **Hypothesis P ($d_{\mathrm{pivot}} = 14\text{d}, S_{\mathrm{pivot}} = 2{,}000\text{ AVAX}, p \in [1.1, 1.4]$)** and **Hypothesis E ($d_{\mathrm{pivot}} = 30\text{d}, S_{\mathrm{pivot}} \in [1{,}200, 1{,}600]\text{ AVAX}, p \in [1.1, 1.5]$)** into **Stage 4 Counterfactual Simulation**.
- Evaluate how both candidate curves perform under macro price stress, operator revenue distribution, and solo validator entry dynamics.
