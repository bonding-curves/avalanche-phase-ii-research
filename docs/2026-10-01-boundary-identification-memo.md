# BOUNDARY IDENTIFICATION MEMO: S_floor AND S_short

**Date:** 2026-10-01  
**Project:** Avalanche Phase II Research — Admission Frontier  
**Document Type:** Formal Systems Engineering & Economic Boundary Specification  
**Status:** Canonical Endpoint Identification (Pre-Pivot / Pre-Curvature)  

---

## 1. Executive Conclusion

This memorandum identifies defensible, evidence-based parameter ranges for the two boundary endpoints of the duration-dependent admission frontier:

$$S_{\min}(d) = S_{\mathrm{floor}} + (S_{\mathrm{short}} - S_{\mathrm{floor}})\cdot\eta(d)^p$$

over the protocol domain $d \in [d_{\min}, d_{\max}] = [2\text{ days}, 365\text{ days}]$.

### Current Working Bounds

$$S_{\mathrm{floor}} \in [500, 2{,}000]\text{ AVAX}$$

$$S_{\mathrm{short}} \in [10{,}000, 20{,}000]\text{ AVAX}$$

### Precise Working Conclusions

1. **Long-Duration Floor ($S_{\mathrm{floor}}$):**
   The current economic analysis supports a working range of 500–2,000 AVAX, with the lower end representing a stressed solvency case and the upper end anchored by the observed current solo-validator population. Further narrowing requires external cost and capital-opportunity-cost assumptions.
   - At 500 AVAX, annual gross rewards at ACP-285 rates (~6.38%) generate only 31.9 AVAX per year. If AVAX trades at \$15, gross annual earnings are \$478, which is insufficient to cover even a basic \$600/year VPS hosting bill. Thus, 500 AVAX is a **stressed solvency lower bound**, viable only under low-cost hosting (\$50/month) and baseline-to-high AVAX prices ($\ge \$20\text{--}\$25$).
   - The upper bound (2,000 AVAX) preserves the status quo protocol minimum and guarantees solvency for standard dedicated bare-metal hosting (\$1,200/year) even under bear-market price stress (\$15/AVAX).

2. **Short-Duration Barrier ($S_{\mathrm{short}}$):**
   The current analysis establishes an **empirical anti-swarm / identity-compression range** of 10,000–20,000 AVAX, not yet a formal consensus-security threshold.
   - Higher $S_{\mathrm{short}}$ compresses the capacity for ephemeral validator swarms (reducing node capacity by 80% at 10,000 AVAX and 90% at 20,000 AVAX for a given capital allocation).
   - What has been empirically proven is the relationship between capital requirement and swarm suppression. We have not yet established what specific amount of swarm capacity or churn is acceptable to consensus engineers. Further narrowing requires an explicit consensus-engineering requirement.

3. **Reconciliation of the August 2025 Contraction Data:**
   - *Total Network Contraction:* Between July 1, 2025 (1,436 active nodes) and September 1, 2025 (900 active nodes), the Primary Network experienced a net decline of **536 active nodes**.
   - *Primary Farming Operator Exits:* Four multi-node operators accounted for **451 of these exits** by September 1, 2025 (and 482 exits by October 1, 2025). Adding a fifth smaller operator brought the cluster's exits to **506 nodes**.
   - *Theoretical Swarm Capacity:* The figure of **621 nodes** represents the theoretical maximum simultaneous identity capacity that the combined 1.24M AVAX of these five operators could fund at once at the 2,000-AVAX minimum bond ($\lfloor 1{,}243{,}879 / 2{,}000 \rfloor = 621$). In reality, their active nodes peaked at 584 simultaneous nodes on July 31, 2025.

### Research Status
**Stage 1: endpoint ranges established as working bounds, subject to explicit unresolved assumptions.**

---

## 2. S_floor Model and Evidence

### 2.1 The Economic Grounding: Profile A Solvency
Under the Avalanche Primary Network rules, commercial validators (Profile B) receive delegation and earn commission fees ($f_{\mathrm{del}} \in [2\%, 10\%]$) on up to 4x their self-stake, while institutional nodes (Profile C) are co-funded by Subnet/L1 operations.

Therefore, the long-duration floor $S_{\mathrm{floor}}$ must be justified by the economically independent solo validator population (Profile A):
- 70 active nodes across 55 unique operators in current live data.
- Zero delegation received ($D_i = 0$).
- 100% of infrastructure costs absorbed by self-stake staking yield.

### 2.2 Break-Even Mathematical Formulation
At $d_{\max} = 365$ days, the net economic value $V(S)$ over a one-year horizon is:

$$V(S) = S \cdot P_{\mathrm{AVAX}} \cdot \big(r_{\mathrm{stake}} \cdot p_{\mathrm{up}} - r_{\mathrm{opp}}\big) - C_{\mathrm{op}} \ge 0$$

Where:
- $S$: Self-stake in AVAX.
- $P_{\mathrm{AVAX}}$: AVAX price in USD.
- $r_{\mathrm{stake}}$: Annualized reward rate at 365 days under ACP-285 ($\text{ARR}(365) \approx 0.06378$, or 6.38%).
- $p_{\mathrm{up}}$: Probability of satisfying the 90% uptime requirement (ACP-267) to receive rewards.
- $r_{\mathrm{opp}}$: Annual capital opportunity cost / hurdle rate.
- $C_{\mathrm{op}}$: Annual validator operating hardware and hosting cost in USD.

Setting $V(S_{\mathrm{floor}}) = 0$ yields the break-even self-stake floor:

$$S_{\mathrm{floor}} = \frac{C_{\mathrm{op}}}{P_{\mathrm{AVAX}} \cdot \big(r_{\mathrm{stake}} \cdot p_{\mathrm{up}} - r_{\mathrm{opp}}\big)}$$

### 2.3 Empirical Inputs and Evidence

1. **Staking Yield ($r_{\mathrm{stake}}$):**
   - Formula: $\text{ARR}(365) = \text{MaxConsumptionRate} \times \frac{S_{\max} - S_{\mathrm{circ}}}{S_{\mathrm{circ}}}$.
   - Under ACP-285 with $\text{MaxConsumptionRate} = 0.12$ and $S_{\mathrm{circ}} \approx 473.6\text{M}$ AVAX, $r_{\mathrm{stake}} = 0.06378$ (6.378%). `[PROTOCOL-DEFINED]`

2. **Empirical Reward Eligibility ($p_{\mathrm{up}}$):**
   - Analysis of all 56,465 completed staking periods in `research/data/01-renewal-panel.parquet` shows 55,071 periods were rewarded (`own_rewarded = True`).
   - Empirical uptime success rate: $p_{\mathrm{up}} = 0.9753$ (97.53%).
   - For long durations (180 to 365 days): $p_{\mathrm{up}} = 0.9466$ (94.66%). `[OBSERVED]`

3. **Operating Hardware Costs ($C_{\mathrm{op}}$):**
   Avalanche Primary Network requirements (8 vCPU, 16-32 GB RAM, 1 TB NVMe SSD, 100 Mbps network) span three distinct hosting tiers:
   - *Low-Tier Cloud / Budget VPS (Hetzner, OVH, Contabo):* \$40 to \$60/month $\implies C_{\mathrm{op}} = \$600/\text{year}$.
   - *Mid-Tier Cloud / Dedicated Bare-Metal (Latitude.sh, Equinix, OVH Dedicated):* \$80 to \$120/month $\implies C_{\mathrm{op}} = \$1{,}200/\text{year}$.
   - *High-Tier Enterprise Cloud (AWS m5.2xlarge with gp3 IOPS, GCP, Azure):* \$180 to \$250/month $\implies C_{\mathrm{op}} = \$2{,}400/\text{year}$. `[EXTERNALLY SOURCED]`

4. **AVAX Fiat Price ($P_{\mathrm{AVAX}}$):**
   - Base Case: \$25.00 / AVAX.
   - Stress Scenarios: \$15.00 (stress bear market) and \$40.00 (expansion market). `[SCENARIO]`

5. **Capital Opportunity Cost ($r_{\mathrm{opp}}$):**
   - Base Case: $r_{\mathrm{opp}} = 0.0\%$ (pure cash-flow accounting).
   - Spread Hurdle: $r_{\mathrm{opp}} = 1.5\%$ (requires a positive net yield spread above outside liquidity options). `[ASSUMED]`

### 2.4 Break-Even Sensitivity Grid (S_floor in AVAX)

| Hosting Tier ($C_{\mathrm{op}}$) | Stress Price ($P=\$15$) | Base Price ($P=\$25$) | Expansion Price ($P=\$40$) |
| :--- | :--- | :--- | :--- |
| **Low-Tier VPS (\$600/yr, $r_{\mathrm{opp}}=0$)** | 643.0 AVAX | 385.8 AVAX | 241.1 AVAX |
| **Mid-Tier Dedicated (\$1,200/yr, $r_{\mathrm{opp}}=0$)** | 1,286.1 AVAX | 771.6 AVAX | 482.3 AVAX |
| **High-Tier Cloud (\$2,400/yr, $r_{\mathrm{opp}}=0$)** | 2,572.2 AVAX | 1,543.3 AVAX | 964.6 AVAX |
| **Low-Tier VPS (\$600/yr, $r_{\mathrm{opp}}=1.5\%$)** | 847.4 AVAX | 508.4 AVAX | 317.8 AVAX |
| **Mid-Tier Dedicated (\$1,200/yr, $r_{\mathrm{opp}}=1.5\%$)** | 1,694.7 AVAX | 1,016.8 AVAX | 635.5 AVAX |
| **High-Tier Cloud (\$2,400/yr, $r_{\mathrm{opp}}=1.5\%$)** | 3,389.5 AVAX | 2,033.7 AVAX | 1,271.1 AVAX |

---

## 3. S_short Model and Evidence

### 3.1 The Empirical Stress Benchmark: August 2025 Contraction
The short-duration barrier $S_{\mathrm{short}}$ must not be treated as a pure consensus-security invariant. Under Snow consensus, security is weighted by total staked AVAX, not node count.

Instead, $S_{\mathrm{short}}$ functions as a **sybil barrier, consensus churn throttle, and identity-farming governor**.

The empirical stress benchmark is the observed August 2025 contraction:
- Between July 31 and August 21, 2025, active validators dropped from 1,414 to 931 nodes (-483 nodes in 21 days).
- Five operator entities accounted for 476 of these exits (over 93%).
- Every node in the farming swarm posted exactly 2,000.0 AVAX, staked for minimum 14-day cycles, and carried near-zero delegation.
- Total capital controlled by these 5 operators was $B_{\mathrm{swarm}} = 1{,}243{,}879\text{ AVAX}$.

### 3.2 Swarm Capacity Scaling: N_j(S)
For any candidate short-end bond $S$, the maximum simultaneous validator identities an operator with capital $B_j$ can deploy is:

$$N_j(S) = \left\lfloor \frac{B_j}{S} \right\rfloor$$

Under the 48-hour regime ($d_{\min} = 2$ days under ACP-273), lower capital requirements permit massive multi-node swarms. Evaluating the empirical August 2025 farming capital across candidate $S_{\mathrm{short}}$ values:

| Operator Entity | Attributable Capital ($B_j$) | $S=2\text{k}$ (Status Quo) | $S=5\text{k}$ | $S=10\text{k}$ | $S=14\text{k}$ (Iso-Commitment) | $S=18\text{k}$ | $S=20\text{k}$ | $S=25\text{k}$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Operator 1 (`avax10f...`)** | 836,879 AVAX | 418 nodes | 167 nodes | 83 nodes | 59 nodes | 46 nodes | 41 nodes | 33 nodes |
| **Operator 2 (`avax1dw...`)** | 170,000 AVAX | 85 nodes | 34 nodes | 17 nodes | 12 nodes | 9 nodes | 8 nodes | 6 nodes |
| **Operator 3 (`avax1dt...`)** | 98,000 AVAX | 49 nodes | 19 nodes | 9 nodes | 7 nodes | 5 nodes | 4 nodes | 3 nodes |
| **Operator 4 (`avax1wd...`)** | 88,000 AVAX | 44 nodes | 17 nodes | 8 nodes | 6 nodes | 4 nodes | 4 nodes | 3 nodes |
| **Operator 5 (`avax134...`)** | 51,000 AVAX | 25 nodes | 10 nodes | 5 nodes | 3 nodes | 2 nodes | 2 nodes | 2 nodes |
| **Total Swarm Capacity** | **1,243,879 AVAX** | **621 nodes** | **247 nodes** | **124 nodes** | **88 nodes** | **69 nodes** | **62 nodes** | **49 nodes** |
| **Swarm Suppression Ratio** | — | **0.0%** | **-60.1%** | **-80.0%** | **-85.8%** | **-88.9%** | **-90.0%** | **-92.1%** |
| **Effective Capital-Time ($K$)** | — | 4,000 d·AVAX | 10,000 d·AVAX | 20,000 d·AVAX | 28,000 d·AVAX | 36,000 d·AVAX | 40,000 d·AVAX | 50,000 d·AVAX |

### 3.3 The 14-Day Delegation Firewall
Under Avalanche protocol rules:
$$d_{\mathrm{del,min}} = 14\text{ days}$$
Validators operating at $d < 14\text{ days}$ (including the new 48-hour minimum) **cannot receive retail delegation**.
- All short-duration nodes must be 100% self-funded by the operator.
- Under ACP-285, ARR at 48 hours is at the protocol floor ($\approx 3.95\%$).
- Gross 48-hour reward on 14,000 AVAX is only 3.03 AVAX (\$75.75 at \$25/AVAX).
- This severely suppresses the economic profitability of legitimate retail validation at 48 hours, confirming that 48-hour validation is exclusively an institutional liquidity option.

---

## 4. Candidate Ranges

### 4.1 Long-Duration Floor Range
$$S_{\mathrm{floor}} \in [500, 2{,}000]\text{ AVAX}$$

The current economic analysis supports a working range of 500–2,000 AVAX, with the lower end representing a stressed solvency case and the upper end anchored by the observed current solo-validator population. Further narrowing requires external cost and capital-opportunity-cost assumptions.

- **Lower Bound ($L_f = 500$ AVAX — Stressed Solvency Case):**
  - Justification: Cash-flow break-even threshold for cost-conscious solo operators running on low-tier cloud VPS (\$600/year) at base prices (\$20 to \$25/AVAX) under ACP-285 maximum staking yields ($\approx 6.38\%$).
  - Limitation / Stress Status: At \$15/AVAX, annual gross rewards (31.9 AVAX = \$478) fail to cover \$600 hosting, producing an annual deficit of \$122. Thus, 500 AVAX is not an equally viable floor across all market conditions; it is a stressed solvency lower bound requiring favorable hosting and token prices.
- **Upper Bound ($U_f = 2{,}000$ AVAX — Current Empirical Anchor):**
  - Justification: Preserves the status quo protocol minimum and reflects the current live solo-validator population. Guarantees solvency for dedicated bare-metal hosting (\$1,200/year) even under bear-market price stress (\$15/AVAX) and positive capital opportunity costs.
  - Limitation: Preserves the existing capital barrier, providing no entry relief for retail sovereign validators.
- **Central Reference Anchor:** $750$ to $1{,}000$ AVAX (supports standard \$1,200/year hardware at \$25/AVAX).

### 4.2 Short-Duration Boundary Range
$$S_{\mathrm{short}} \in [10{,}000, 20{,}000]\text{ AVAX}$$

This range is an **empirical anti-swarm / identity-compression range**, not yet a formal consensus-security threshold. Higher $S_{\mathrm{short}}$ directly compresses the capacity for ephemeral validator swarms. Further narrowing requires an explicit consensus-engineering requirement specifying acceptable churn and swarm tolerance.

- **Lower Bound ($L_s = 10{,}000$ AVAX):**
  - Justification: Compresses the empirical August 2025 farming capacity by 80% (from 621 theoretical nodes down to 124 nodes). Establishes a 20,000 AVAX-day commitment threshold.
  - Limitation: Allows an operator with 1M AVAX to still deploy ~100 transient 48-hour validator seats.
- **Upper Bound ($U_s = 20{,}000$ AVAX):**
  - Justification: Compresses farming capacity by 90% (down to 62 nodes). Imposes a 40,000 AVAX-day commitment hurdle.
  - Limitation: Beyond 20,000 AVAX, diminishing returns set in (moving to 25k AVAX suppresses only 13 additional nodes) while creating an extreme capital barrier that penalizes legitimate institutional node rotation.
- **Central Reference Anchor:** $14{,}000$ AVAX (preserves the legacy 28,000 AVAX-day iso-commitment parity at 48 hours).

---

## 5. Key Sensitivities

1. **$S_{\mathrm{floor}}$ Sensitivity:**
   - **Hardware Cost ($C_{\mathrm{op}}$) & AVAX Price ($P_{\mathrm{AVAX}}$):** $S_{\mathrm{floor}}$ scales linearly with $C_{\mathrm{op}} / P_{\mathrm{AVAX}}$. A 50% price decline doubles the required break-even stake.
   - **Uptime Success ($p_{\mathrm{up}}$):** High empirical stability (97.53%) means uptime risk has negligible impact on break-even bounds unless an operator suffers persistent unbonding.
   - **Capital Opportunity Cost ($r_{\mathrm{opp}}$):** Increases break-even requirements by 25% to 40% when operators require a 1.5% net spread above outside liquid staking options.

2. **$S_{\mathrm{short}}$ Sensitivity:**
   - **Swarm Compression Elasticity:** Swarm capacity $N(S) \propto 1/S$. The marginal reduction in identities drops rapidly above 14,000 AVAX.
   - **Consensus Headroom:** Under Snow peer-to-peer gossip bounds ($N_{\mathrm{soft\_cap}} = 2{,}000$), compressing farming swarms from 600 nodes to < 100 nodes restores consensus capacity headroom from ~50% to ~70%.

---

## 6. Identification Limitations

1. **No Causal Identification of $S_{\mathrm{floor}}$ Response:**
   Historical on-chain data contain zero observations of solo validators operating at self-stakes below 2,000 AVAX. How many new solo validators would enter if $S_{\mathrm{floor}} = 500$ or $1{,}000$ AVAX cannot be identified from history. `[UNIDENTIFIED]`

2. **No Causal Identification of Short-Duration Demand:**
   Prior to ACP-273, staking below 14 days was illegal. How many operators will utilize 48-hour validation under ACP-236 auto-renewal is unobserved. `[UNIDENTIFIED]`

3. **Operating Costs are Exogenous:**
   Hardware costs are incurred off-chain in fiat USD and cannot be observed on the Avalanche P-Chain. `[EXTERNALLY SOURCED]`

---

## 7. What Remains Unidentified

- **Empirical Solo Operator Cost Distribution:** The exact fraction of solo operators using low-cost VPS vs dedicated bare metal.
- **Validator Capital Opportunity Cost:** The empirical hurdle rate demanded by AVAX stakers relative to liquid staking or DeFi yields.
- **Post-Helicon 48-Hour Cycle Adoption:** The realized demand for 48-hour staking cycles under ACP-273.
- **Target Network Threat Model:** The maximum tolerable transient identity swarm size specified by Ava Labs consensus engineers.

---

## 8. Recommended Next Research Step

With the boundary ranges established:
$$S_{\mathrm{floor}} \in [500, 2{,}000]\text{ AVAX}$$
$$S_{\mathrm{short}} \in [10{,}000, 20{,}000]\text{ AVAX}$$

The next analytical step is **Stage 2 & 3: Pivot Selection and Curvature Calibration ($p$)**:
1. Analyze historical duration choice clustering (30d, 60d, 90d, 180d) to determine an empirically grounded pivot duration $d_{\mathrm{pivot}}$.
2. Evaluate analytical curvature inversion:
   $$p = \frac{\ln\left(\frac{S_{\mathrm{pivot}} - S_{\mathrm{floor}}}{S_{\mathrm{short}} - S_{\mathrm{floor}}}\right)}{\ln \eta(d_{\mathrm{pivot}})}$$
3. Test interior convexity ($p \ge 1$) and intermediate duration differentiation.
