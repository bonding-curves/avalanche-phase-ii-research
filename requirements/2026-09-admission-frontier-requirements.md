# Engineering Requirements Document (ERD): Duration-Dependent Stake Admission Frontier S_min(d)

| Metadata | Value |
| :--- | :--- |
| **Document ID** | REQ-2026-09-ADMISSION-FRONTIER |
| **Status** | DRAFT - FOR COLLABORATIVE REVIEW |
| **Authors** | Antigravity AI, BCRG Systems Engineering Team |
| **Collaborators** | Shawn Anderson (Longtail Financial / BCRG), Dr. Eric Lu (Avalanche Foundation), Hansen Niu (BENQI) |
| **Date** | September 22, 2026 |
| **Target Milestone** | Milestone 2 Policy Matrix & Milestone 3 Parameter Recommendation |
| **System Boundary** | PlatformVM Consensus & Stake Admission Subsystem (Primary Network) |
| **Interactive Reader** | [http://localhost:8099/requirements_rendered.html](http://localhost:8099/requirements_rendered.html) |

---

## 1. Executive Summary & Purpose

The purpose of this document is to specify the **functional, economic, mathematical, and architectural requirements** for the **Duration-Dependent Stake Admission Frontier** $S_{\min}(d)$ on the Avalanche Primary Network.

This mechanism resolves a multi-policy deadlock:
1. **ACP-49:** Proposes reducing minimum validator self-stake from $2{,}000\text{ AVAX}$ to $500\text{ AVAX}$ to lower capital barriers.
2. **ACP-273:** Proposes reducing minimum staking duration from $14\text{ days}$ to $2\text{ days}$ to enhance capital efficiency.
3. **The Sybil Catastrophe:** Permitting $500\text{ AVAX}$ at $2\text{ days}$ creates an attack vector where a malicious node can be spun up for only $1{,}000\text{ AVAX-days}$ ($96.4\%$ cheaper than Mainnet's $28{,}000\text{ AVAX-days}$ baseline), triggering massive consensus churn and P-Chain state bloat.
4. **The Target Horizon:** Dr. Eric Lu’s econometric modeling demonstrates that stabilizing the network requires shifting average lockup to **$16.9\text{ weeks}$ ($118\text{ days}$)**.

By formalizing a **monotonically decreasing admission frontier** $S_{\min}(d)$, the protocol imposes a liquidity surcharge on short durations while granting retail accessibility ($500\text{ AVAX}$) in exchange for long-term time commitment ($365\text{ days}$).

---

## 2. Definitive Forensic Verification: Capital vs. Node Distribution

To ground all design choices in empirical reality, the table below partitions all **$57{,}067$ structurally valid stints** and **$7{,}635$ unique nodes** from Genesis to 2026 (`01-renewal-panel.parquet`):

| Staker Cohort | Historical Stints | Unique Nodes (`node_id`) | Cumulative Self-Bond (AVAX) | Cumulative Delegations Received (AVAX) | Mean Stint Duration |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Whales / BENQI-Eligible ($\ge 6{,}000\text{ AVAX}$)** | **$14{,}357$** ($25.16\%$) | **$1{,}735$** ($22.72\%$) | **$5{,}455{,}523{,}274.9\text{ AVAX}$ ($98.29\%$)** | **$2{,}671{,}027{,}131.9\text{ AVAX}$ ($97.18\%$)** | **$64.8\text{ days}$ ($9.3\text{w}$)** (weighted: $81.0\text{d}$) |
| **Small & Mid-Tier Retail ($< 6{,}000\text{ AVAX}$)** | **$42{,}710$** ($74.84\%$) | **$6{,}440$** ($84.35\%$) | **$95{,}020{,}892.4\text{ AVAX}$ ($1.71\%$)** | **$77{,}402{,}305.1\text{ AVAX}$ ($2.82\%$)** | **$39.1\text{ days}$ ($5.6\text{w}$)** (weighted: $40.9\text{d}$) |
| *— of which: Exactly $2{,}000\text{ AVAX}$ Stakers* | *$22{,}477$* ($39.39\%$) | *$5{,}011$* ($65.63\%$) | *$44{,}954{,}000.0\text{ AVAX}$ ($0.81\%$)** | *$22{,}739{,}433.5\text{ AVAX}$ ($0.83\%$)** | *$37.1\text{ days}$ ($5.3\text{w}$)* |

### Invariant Architectural Realities:
1. **The Capital Invariant:** Nodes with $\ge 6{,}000\text{ AVAX}$ self-stake hold **$98.29\%$ of all bonded capital** and capture **$97.18\%$ of all delegations**. Network macro-stability and the $50\%–60\%$ Staking Ratio ($\rho_{\text{stake}}$) are determined **entirely by this group**.
2. **The Decentralization Invariant:** $84.35\%$ of physical nodes ($6{,}440$ unique machines) hold $<6{,}000\text{ AVAX}$. Their role is geographic distribution, consensus liveness, and client diversity—**not capital provision**.
3. **The Immunity Invariant:** Shifting minimum duration requirements for small stakers ($<6\text{k AVAX}$) cannot destabilize network staking capital or threaten the $50\%$ security ratio, because their entire combined float is only **$1.71\%$** of total bonded AVAX.

---

## 3. Mathematical Model: Harmonic Bounded Decay

Standard asymptotic hyperbolas cannot hit $500\text{ AVAX}$ at exactly $d = 365$ without shifting the asymptote below $500$. The mathematically consistent formulation that guarantees exact boundary enforcement at both endpoints is **Harmonic Bounded Decay**:

$$S_{\min}(d) = 500 + (S_{\text{short}} - 500) \cdot \left[ \frac{\frac{1}{d} - \frac{1}{365}}{\frac{1}{2} - \frac{1}{365}} \right]^p$$

- **Left Boundary ($d = 2\text{ days}$):** $\left[\frac{1/2 - 1/365}{1/2 - 1/365}\right]^p = 1.0 \implies S_{\min}(2) = S_{\text{short}}$ identically.
- **Right Boundary ($d = 365\text{ days}$):** $\left[\frac{1/365 - 1/365}{1/2 - 1/365}\right]^p = 0.0 \implies S_{\min}(365) = 500\text{ AVAX}$ identically.
- **Intermediate Pivot ($d = d_{\text{target}}$):** We solve for the power exponent $p$ such that $S(d_{\text{target}}) = 2{,}000\text{ AVAX}$:
  $$p = \frac{\ln\left(\frac{1{,}500}{S_{\text{short}} - 500}\right)}{\ln\left(\frac{1/d_{\text{target}} - 1/365}{1/2 - 1/365}\right)}$$

---

## 4. Relaxing $S_{\text{short}}$: Comprehensive Sensitivity & Scenario Analysis

Instead of anchoring exclusively to $20{,}000\text{ AVAX}$, we systematically relax $S_{\text{short}}$ from **$5{,}000\text{ AVAX}$ to $100{,}000\text{ AVAX}$** across two duration targets:
- **Target A: 12-Week Transition ($d_{\text{target}} = 84\text{ days}$)**
- **Target B: 17-Week Transition ($d_{\text{target}} = 119\text{ days}$, Eric Lu's Target)**

### 4.1 Macro Frontier Sweep: Minimum Required Stake Across Durations

#### Target A: 12-Week Pivot ($S(84\text{d}) = 2{,}000\text{ AVAX}$)

| $S_{\text{short}}$ (2d) | Exponent $p$ | 2d Sybil Multiplier | 7d Stake | 14d Stake | 30d Stake | 60d Stake | 84d (12w) | 180d Stake | 365d (1y) | Unique Eligible Nodes |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$5{,}000\text{ AVAX}$** | $0.275$ | **$0.36\times$ (Vulnerable)** | $3{,}676\text{ A}$ | $3{,}110\text{ A}$ | $2{,}590\text{ A}$ | $2{,}183\text{ A}$ | **$2{,}000\text{ A}$** | $1{,}584\text{ A}$ | **$500\text{ A}$** | $1{,}838$ ($24.1\%$) |
| **$10{,}000\text{ AVAX}$** | $0.462$ | **$0.71\times$ (Discount)** | $5{,}790\text{ A}$ | $4{,}305\text{ A}$ | $3{,}118\text{ A}$ | $2{,}320\text{ A}$ | **$2{,}000\text{ A}$** | $1{,}369\text{ A}$ | **$500\text{ A}$** | $1{,}506$ ($19.7\%$) |
| **$14{,}000\text{ AVAX}$** | $0.550$ | **$1.00\times$ (Strict Parity)**| $7{,}225\text{ A}$ | $5{,}043\text{ A}$ | $3{,}411\text{ A}$ | $2{,}388\text{ A}$ | **$2{,}000\text{ A}$** | $1{,}284\text{ A}$ | **$500\text{ A}$** | $1{,}336$ ($17.5\%$) |
| **$20{,}000\text{ AVAX}$** | $0.642$ | **$1.43\times$ (Reference)** | $9{,}145\text{ A}$ | **$5{,}969\text{ A}$** | $3{,}753\text{ A}$ | $2{,}462\text{ A}$ | **$2{,}000\text{ A}$** | $1{,}203\text{ A}$ | **$500\text{ A}$** | $1{,}227$ ($16.1\%$) |
| **$35{,}000\text{ AVAX}$** | $0.785$ | **$2.50\times$ (Conservative)**| $13{,}263\text{ A}$ | $7{,}792\text{ A}$ | $4{,}364\text{ A}$ | $2{,}583\text{ A}$ | **$2{,}000\text{ A}$** | $1{,}094\text{ A}$ | **$500\text{ A}$** | $1{,}012$ ($13.3\%$) |
| **$50{,}000\text{ AVAX}$** | $0.876$ | **$3.57\times$ (Institutional)**| $16{,}830\text{ A}$ | $9{,}249\text{ A}$ | $4{,}809\text{ A}$ | $2{,}664\text{ A}$ | **$2{,}000\text{ A}$** | $1{,}034\text{ A}$ | **$500\text{ A}$** | $900$ ($11.8\%$) |

---

#### Target B: 17-Week Pivot ($S(119\text{d}) = 2{,}000\text{ AVAX}$, Eric Lu Target)

| $S_{\text{short}}$ (2d) | Exponent $p$ | 2d Sybil Multiplier | 7d Stake | 14d Stake | 30d Stake | 60d Stake | 84d (12w) | 119d (17w) | 365d (1y) | Unique Eligible Nodes |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$5{,}000\text{ AVAX}$** | $0.245$ | **$0.36\times$ (Vulnerable)** | $3{,}797\text{ A}$ | $3{,}268\text{ A}$ | $2{,}769\text{ A}$ | $2{,}371\text{ A}$ | $2{,}188\text{ A}$ | **$2{,}000\text{ A}$** | **$500\text{ A}$** | $1{,}838$ ($24.1\%$) |
| **$10{,}000\text{ AVAX}$** | $0.412$ | **$0.71\times$ (Discount)** | $6{,}134\text{ A}$ | $4{,}699\text{ A}$ | $3{,}508\text{ A}$ | $2{,}674\text{ A}$ | $2{,}329\text{ A}$ | **$2{,}000\text{ A}$** | **$500\text{ A}$** | $1{,}506$ ($19.7\%$) |
| **$14{,}000\text{ AVAX}$** | $0.491$ | **$1.00\times$ (Strict Parity)**| $7{,}748\text{ A}$ | $5{,}608\text{ A}$ | $3{,}934\text{ A}$ | $2{,}833\text{ A}$ | $2{,}400\text{ A}$ | **$2{,}000\text{ A}$** | **$500\text{ A}$** | $1{,}336$ ($17.5\%$) |
| **$20{,}000\text{ AVAX}$** | $0.573$ | **$1.43\times$ (Reference)** | $9{,}935\text{ A}$ | **$6{,}770\text{ A}$** | $4{,}444\text{ A}$ | $3{,}012\text{ A}$ | $2{,}477\text{ A}$ | **$2{,}000\text{ A}$** | **$500\text{ A}$** | $1{,}227$ ($16.1\%$) |
| **$35{,}000\text{ AVAX}$** | $0.701$ | **$2.50\times$ (Conservative)**| $14{,}703\text{ A}$ | $9{,}119\text{ A}$ | $5{,}390\text{ A}$ | $3{,}318\text{ A}$ | $2{,}602\text{ A}$ | **$2{,}000\text{ A}$** | **$500\text{ A}$** | $1{,}012$ ($13.3\%$) |
| **$50{,}000\text{ AVAX}$** | $0.781$ | **$3.57\times$ (Institutional)**| $18{,}899\text{ A}$ | $11{,}041\text{ A}$ | $6{,}103\text{ A}$ | $3{,}530\text{ A}$ | $2{,}685\text{ A}$ | **$2{,}000\text{ A}$** | **$500\text{ A}$** | $900$ ($11.8\%$) |

---

## 5. Architectural Implications of Changing $S_{\text{short}}$

### Scenario 1: Low $S_{\text{short}}$ ($5{,}000\text{ to }10{,}000\text{ AVAX}$) — "High Accessibility / High Churn"
* **What Happens:** 2-day micro-staking is accessible to $1{,}500\text{ to }1{,}800$ nodes ($20\%–24\%$ of all historical operators).
* **The Sybil Failure Mode:** At $S_{\text{short}} = 5{,}000\text{ AVAX}$, a 2-day attack costs only $10{,}000\text{ AVAX-days}$ (**$0.36\times$ of Mainnet**). At $10{,}000\text{ AVAX}$, it costs $20{,}000\text{ AVAX-days}$ (**$0.71\times$ of Mainnet**).
* **Network Impact:** Subsidizes short-duration churn. Validators have an economic incentive to run short rolling stints, congesting the P-Chain with frequent `AddValidatorTx` registrations.
* **Verdict:** Unacceptable from a security perspective unless combined with high registration burn fees.

### Scenario 2: The Iso-Commitment Floor ($S_{\text{short}} = 14{,}000\text{ AVAX}$) — "Zero-Discount Floor"
* **What Happens:** $14{,}000 \times 2\text{d} = 28{,}000\text{ AVAX-days}$ (**exact $1.00\times$ Mainnet Sybil parity**).
* **Network Impact:** Ensures that no 2-day staker can lock up less total capital-time than current 14-day validators. 
* **14-Day Effect:** Requires **$5{,}043\text{ to }5{,}608\text{ AVAX}$** at 14 days, naturally approaching BENQI's $6{,}000\text{ AVAX}$ qualification gate.
* **Verdict:** The absolute theoretical minimum bound for $S_{\text{short}}$ without subsidizing attackers.

### Scenario 3: The Reference Surcharge ($S_{\text{short}} = 20{,}000\text{ AVAX}$) — "The BENQI Harmony Corridor"
* **What Happens:** Imposes a $1.43\times$ liquidity surcharge ($40{,}000\text{ AVAX-days}$) on 2-day micro-lockups. Accessible to $1{,}227$ historical nodes ($16.1\%$).
* **The Organic BENQI Alignment:** Under a 12-week transition, the 14-day minimum stake naturally evaluates to **$5{,}969\text{ AVAX} \approx 6{,}000\text{ AVAX}$**!
* **Network Impact:** Perfect harmony with liquid staking rules. Discourages low-stake retail churn at 14 days while leaving high-stake professional nodes eligible for both consensus and BENQI delegations.
* **Verdict:** The most balanced operational recommendation.

### Scenario 4: High Anti-Churn ($S_{\text{short}} = 35{,}000\text{ to }50{,}000\text{ AVAX}$) — "Institutional-Only Short End"
* **What Happens:** 2-day lockups require $\$875\text{k to } \$1.25\text{M}$ (at $\$25/\text{AVAX}$). Restricts 2-day staking to $900\text{ – }1{,}012$ elite nodes ($11.8\%–13.3\%$).
* **Network Impact:** P-Chain gossip churn is crushed. 2-day micro-staking is strictly reserved for high-frequency institutional rebalancing.
* **14-Day Effect:** 14-day stake rises to **$7{,}792\text{ – }11{,}041\text{ AVAX}$**, pushing even standard BENQI stakers into longer lockup tiers.
* **Verdict:** Highly effective for P-Chain scalability, but may face pushback from mid-tier validators.

---

## 6. Implementation Architecture in PlatformVM

PlatformVM can enforce this harmonic frontier via two distinct methods:

### Method A: Discrete Consensus Step-Brackets (Recommended for Go)
Quantize the continuous harmonic curve into integer validation brackets to eliminate floating-point non-determinism:
```go
// GetMinimumValidatorStake returns the required self-stake for a given duration.
// Calibrated for S_short = 20,000 AVAX with 12-Week Pivot (p=0.642) and S(365d) = 500 AVAX.
func GetMinimumValidatorStake(duration time.Duration) uint64 {
    days := duration.Hours() / 24
    switch {
    case days < 2:
        return math.MaxUint64 // Below consensus minimum
    case days < 7:
        return 20_000 * units.Avax
    case days < 14:
        return 9_000 * units.Avax
    case days < 30:
        return 6_000 * units.Avax  // BENQI Open Pool Alignment
    case days < 84:
        return 3_500 * units.Avax
    case days < 180:
        return 2_000 * units.Avax  // 12-Week Transition Gate
    case days < 365:
        return 1_000 * units.Avax
    default:
        return 500 * units.Avax    // ACP-49 Floor at 1 Year
    }
}
```

### Method B: Fixed-Point Wad Math
If continuous precision is desired, evaluate the expression in 18-decimal fixed-point arithmetic (`wad` math):
$$S_{\min}(d) = 500 + (S_{\text{short}} - 500) \cdot \text{wadPow}\left( \frac{365 - d}{363 \cdot d}, p \right)$$

---

## 7. Governance Decision Matrix for Dr. Eric Lu (Sept 25 Review)

To resolve the remaining degrees of freedom with the Avalanche Foundation, present the three viable governance packages:

| Decision Package | $S_{\text{short}}$ (2d) | 14d Requirement | $2{,}000\text{ AVAX}$ Lockup | $500\text{ AVAX}$ Lockup | Primary Target Audience | Primary Trade-Off |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **Package 1: Maximum Liquidity** | $14{,}000\text{ AVAX}$ | $5{,}043\text{ AVAX}$ | $12\text{ weeks}$ ($84\text{d}$) | $365\text{ days}$ | Liquidity-focused traders & L1 operators | $1.0\times$ Sybil parity leaves no safety margin. |
| **Package 2: Institutional Harmony (Recommended)** | **$20{,}000\text{ AVAX}$** | **$5{,}969\text{ AVAX}$** | **$12\text{ to }17\text{ weeks}$** | **$365\text{ days}$** | **Foundation, BENQI & Core Infrastructure** | **Balances $1.43\times$ Sybil barrier with BENQI 6k alignment.** |
| **Package 3: Maximum Anti-Churn** | $35{,}000\text{ AVAX}$ | $7{,}792\text{ AVAX}$ | $17\text{ weeks}$ ($119\text{d}$) | $365\text{ days}$ | PlatformVM performance & state minimization | Excludes small nodes from $<60\text{d}$ tiers. |
