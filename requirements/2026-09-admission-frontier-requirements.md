# Engineering Requirements Document (ERD): Duration-Dependent Stake Admission Frontier S_min(d)

| Metadata | Value |
| :--- | :--- |
| **Document ID** | REQ-2026-09-ADMISSION-FRONTIER |
| **Revision** | Rev 2.1 (Liquid Staking Arbitrage & Delegation Subsidy Equilibrium) |
| **Status** | DRAFT - FOR COLLABORATIVE REVIEW |
| **Authors** | Antigravity AI, BCRG Systems Engineering Team |
| **Collaborators** | Shawn Anderson (Longtail Financial / BCRG), Dr. Eric Lu (Avalanche Foundation), Hansen Niu (BENQI) |
| **Date** | September 22, 2026 |
| **Target Milestone** | Milestone 2 Policy Matrix & Milestone 3 Parameter Recommendation |
| **System Boundary** | PlatformVM Consensus, Stake Admission & Liquid Staking Ecosystem |
| **Interactive Reader** | [http://localhost:8099/requirements_rendered.html](http://localhost:8099/requirements_rendered.html) |

---

## 1. Executive Summary & Purpose

The purpose of this document is to specify the **functional, economic, mathematical, and architectural requirements** for the **Duration-Dependent Stake Admission Frontier** $S_{\min}(d)$ on the Avalanche Primary Network.

This mechanism resolves a multi-policy deadlock between competing Avalanche Community Proposals:
1. **Community 500 AVAX Proposals:** Proposes reducing minimum validator self-stake from $2{,}000\text{ AVAX}$ to $500\text{ AVAX}$ to lower capital barriers and expand node accessibility.
2. **ACP-273:** Proposes reducing minimum staking duration from $14\text{ days}$ to $2\text{ days}$ to enhance validator capital efficiency.
3. **The Sybil Catastrophe:** Permitting $500\text{ AVAX}$ at $2\text{ days}$ creates a critical vulnerability where an attacker can spin up ephemeral consensus nodes for only $1{,}000\text{ AVAX-days}$ ($96.4\%$ cheaper than Mainnet's $28{,}000\text{ AVAX-days}$ baseline), risking sybil disruption.
4. **The Target Horizon:** Historical empirical data indicates that $2{,}000\text{ AVAX}$ retail validators average only **$37.1\text{ days}$ ($5.3\text{ weeks}$)**, while whale stakers average **$64.8\text{ days}$ ($9.3\text{ weeks}$)**. The system objective is to systematically improve duration commitments across **all capital tiers** without disenfranchising the physical node operator base.

---

## 2. The Liquid Staking Outside Option & Cloud Economics

Physical nodes are not bound by sunk bare-metal hardware. Instead, retail validators run on cloud VPS instances (AWS, GCP, Hetzner) costing $\sim \$40/\text{month} = \$480/\text{year} \approx 19.2\text{ AVAX/year}$ ($0.96\%$ annual overhead on $2{,}000\text{ AVAX}$).

### 2.1 The Competitive Baseline: sAVAX (BENQI)
From DefiLlama historical oracle data (`defillama__savax_yield_history.parquet`):
- **Current sAVAX APY (August 2026):** **$3.20\% - 4.93\%$** (30-day mean: **$4.15\%$**, all-time median: **$5.19\%$**).
- **Properties:** Zero cloud server costs, zero maintenance, instant DeFi liquidity, zero lockup.

### 2.2 The Economic Spread: Standalone Validator vs. sAVAX

| Lockup Duration | Gross APY (ACP-285) | Cloud Drag (2k AVAX) | Net Standalone APY | sAVAX APY (Liquid) | Net Spread vs. LST | Operator Economic Verdict |
| :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **$6\text{w}$ ($42\text{d}$)** | $4.26\%$ | $-0.96\%$ | **$3.30\%$** | $4.50\%$ | **$-1.20\%$** | **Negative Spread:** Exit to LST unless compensated. |
| **$8\text{w}$ ($56\text{d}$)** | $4.35\%$ | $-0.96\%$ | **$3.39\%$** | $4.50\%$ | **$-1.11\%$** | **Negative Spread:** Exit to LST unless compensated. |
| **$12\text{w}$ ($84\text{d}$)** | $4.54\%$ | $-0.96\%$ | **$3.58\%$** | $4.50\%$ | **$-0.92\%$** | **Negative Spread:** Exit to LST unless compensated. |
| **$17\text{w}$ ($119\text{d}$)**| $4.76\%$ | $-0.96\%$ | **$3.80\%$** | $4.50\%$ | **$-0.70\%$** | **Negative Spread:** Heavy attrition to LST. |
| **$52\text{w}$ ($365\text{d}$)**| $6.38\%$ | $-0.96\%$ | **$5.42\%$** | $4.50\%$ | **$+0.92\%$** | **Positive Spread:** Profitable over liquid staking! |

**Key Finding:** Without delegation revenue, running a standalone $2{,}000\text{ AVAX}$ validator on cloud pays **$-70\text{ to } -120\text{ bps LESS}$ than holding sAVAX liquidly**. Over 52 weeks, rational operators shut down their VPS and convert to liquid staking.

---

## 3. The Dual Solution: Lowering Barriers (Community Proposals) & Delegation Offset

To preserve node decentralization ($6{,}440$ physical nodes), the mechanism must incorporate two balancing forces:

1. **Lowering Barrier to Entry (Community 500 AVAX Floor):**
   - At $365\text{ days}$, the bond requirement drops to **$500\text{ AVAX}$**, where gross yield is **$6.38\%$**.
   - Operators who commit long-term earn a **$+188\text{ bps}$ premium over sAVAX**, overcoming cloud costs.
2. **Community Delegation Matching (Offsetting Opportunity Cost):**
   - In Avalanche, validators can accept up to $4\times$ their self-stake in delegations ($8{,}000\text{ AVAX}$ delegation on a $2{,}000\text{ AVAX}$ bond).
   - Routing delegation support (from ecosystem foundations or community pools) at a $3\% - 5\%$ commission fee generates:
     $$\text{Fee Revenue} = \frac{D_{\text{received}}}{S_{\text{bond}}} \cdot \text{ARR}(d) \cdot \text{Fee} \approx +0.35\% \text{ to } +0.65\% \text{ APY boost}$$
   - This delegation subsidy flips the net spread positive, keeping physical cloud validators profitable relative to sAVAX.

---

## 4. Core Non-Negotiable Requirements

1. **Strict Global Sybil Resistance Invariant:**
   $$\forall d \in [2, 365], \quad \Sigma(d) = S_{\min}(d) \cdot d \ge 28{,}000\text{ AVAX-days}$$
   At $d = 2\text{d}$, $S_{\min}(2) \ge 14{,}000\text{ AVAX}$.
2. **Decentralization Viability via Delegation Offsets:**
   The protocol must support delegation matching to ensure standalone validators earn a positive spread over liquid staking ($U_{\text{val}} \ge U_{\text{LST}}$).
3. **Universal Duration Lift Across All Capital Tiers:**
   - **Retail ($2{,}000\text{ AVAX}$):** Lift tenure from $37.1\text{d}$ toward $56\text{d} - 84\text{d}$ ($+51\% \text{ to } +126\%$).
   - **Large Capital ($\ge 6{,}000\text{ AVAX}$):** Shift from $11.6\text{w}$ toward $20\text{w}-23\text{w}$ via ACP-285 yield incentives.
4. **14-Day Transition Harmony:**
   - **Smooth Bridge:** $S(14\text{d}) \approx 4{,}387 - 5{,}043\text{ AVAX}$.
   - **BENQI Harmony:** $S(14\text{d}) \equiv 6{,}000\text{ AVAX}$.
5. **Exact Asymptotic Floor Preservation:**
   $$S_{\min}(365) \equiv 500\text{ AVAX}$$

---

## 5. Mathematical Model: Harmonic Bounded Decay

$$S_{\min}(d) = 500 + (S_{\text{short}} - 500) \cdot \left[ \frac{\frac{1}{d} - \frac{1}{365}}{\frac{1}{2} - \frac{1}{365}} \right]^{p(d_{\text{target}}, S_{\text{short}})}$$

- **Left Boundary ($d = 2\text{d}$):** $S_{\min}(2) = S_{\text{short}}$ identically.
- **Right Boundary ($d = 365\text{d}$):** $S_{\min}(365) = 500\text{ AVAX}$ identically.
- **Pivot Solver:**
  $$p(d_{\text{target}}, S_{\text{short}}) = \frac{\ln\left(\frac{1{,}500}{S_{\text{short}} - 500}\right)}{\ln\left(\frac{1/d_{\text{target}} - 1/365}{1/2 - 1/365}\right)}$$

---

## 6. Evaluated Governance Packages

| Package | $S_{\text{short}}$ | $d_{\text{target}}$ (2k AVAX) | $S(14\text{d})$ | Retail Duration Lift | Net Validator Spread vs. sAVAX (w/ Deleg.) | Physical Node Retention |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Package A: Gradual Bridge (Recommended)** | **$14{,}000\text{ AVAX}$** | **$8.0\text{ weeks}$ ($56\text{d}$)** | **$4{,}387\text{ AVAX}$** | **$+51\%$** | **$+0.15\%$ (Viable)** | **$65\% - 75\%$** |
| **Package B: BENQI Harmony** | **$20{,}000\text{ AVAX}$** | **$12.0\text{ weeks}$ ($84\text{d}$)** | **$5{,}969\text{ AVAX}$** | **$+126\%$** | **$+0.32\%$ (Viable)** | **$55\% - 65\%$** |
| **Package C: Aggressive Extension (Eric Lu)**| **$20{,}000\text{ AVAX}$** | **$16.9\text{ weeks}$ ($118\text{d}$)**| **$6{,}756\text{ AVAX}$** | **$+218\%$** | **$-0.10\%$ (Under Pressure)** | **$40\% - 50\%$** |
