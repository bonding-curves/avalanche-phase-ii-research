# MEMO: Primary Network Cryptoeconomic Policy Architecture

**Date**: September 25, 2026  
**To**: Daniel Ortiz, Dr. Siyu (Eric) Lu, Matias Antonio (Avalanche Foundation)  
**From**: Hash N., BCRG Research Lane  
**Subject**: Admission Frontier Capital Geometry, Empirical Upgrade Regimes, PlatformVM Delegator Firewall, Game-Theoretic Payoff Matrix, and Tinbergen Policy Matrix  

> [!INFO] **Executive Summary**  
> Proof-of-Stake consensus security represents a continuous operational expenditure funded by a finite 720,000,000 AVAX issuance budget that decays continuously by protocol construction. To sustain decentralization and protect network float following the Durango, Etna, and Helicon upgrades, the network must replace static constants with dynamic, mathematically coupled policy mechanisms. This memo presents the complete empirical regime breakdown of all 57,521 historical validator periods, analyzes the multi-agent payoff matrix under the 14-day PlatformVM Delegator Firewall, establishes the standalone capital geometry of the Admission Frontier $S_{\min}(d)$, and defines the Tinbergen Policy Separation Matrix governing the Avalanche Primary Network.

---

## 1. Empirical Protocol Upgrade Regimes and Network State Evolution

### 1.1 Historical Staking Metric Decomposition Across Fifteen Regimes
The Avalanche Primary Network has operated across fifteen distinct protocol upgrade regimes since Genesis. Every validator staking period in network history (57,521 total periods across 7,635 unique physical NodeIDs in `derived.staking-periods` and Snowflake census data) is mapped to its exact on-chain acceptance regime.

| Protocol Regime | Start Timestamp (UTC) | End Timestamp (UTC) | Length (Weeks) | Validator Staking Periods | Median Duration (Weeks) | Stake-Weighted Duration (Weeks) | Median Self-Stake (AVAX) | Total Bonded Self-Stake (AVAX) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Genesis** | 2020-09-10 | 2021-03-31 14:00 | 28.9 | 2,951 | 4.43 | 12.39 | 5,000 | 756,334,177 |
| **Apricot Phase 1** | 2021-03-31 14:00 | 2021-05-10 11:00 | 5.7 | 505 | 4.28 | 4.43 | 2,711 | 37,259,243 |
| **Apricot Phase 2** | 2021-05-10 11:00 | 2021-08-24 14:00 | 15.2 | 1,509 | 4.42 | 13.01 | 3,244 | 196,263,382 |
| **Apricot Phase 3** | 2021-08-24 14:00 | 2021-09-22 21:00 | 4.2 | 655 | 4.98 | 25.71 | 4,000 | 168,337,684 |
| **Apricot Phase 4** | 2021-09-22 21:00 | 2021-12-02 18:00 | 10.1 | 1,471 | 4.14 | 4.29 | 2,075 | 100,440,544 |
| **Apricot Phase 5** | 2021-12-02 18:00 | 2022-09-05 01:30 | 39.5 | 6,875 | 4.29 | 8.83 | 2,033 | 683,514,631 |
| **Apricot Phase Pre-6** | 2022-09-05 01:30 | 2022-09-06 20:00 | 0.25 | 47 | 6.00 | 8.84 | 2,549 | 17,421,353 |
| **Apricot Phase 6** | 2022-09-06 20:00 | 2022-09-07 03:00 | 0.04 | 2 | 14.58 | 25.01 | 33,113 | 66,225 |
| **Apricot Phase Post-6** | 2022-09-07 03:00 | 2022-10-18 16:00 | 5.9 | 783 | 4.42 | 12.86 | 2,140 | 67,516,771 |
| **Banff** | 2022-10-18 16:00 | 2023-04-25 15:00 | 27.0 | 3,431 | 4.43 | 9.67 | 2,202 | 389,656,227 |
| **Cortina** | 2023-04-25 15:00 | 2024-03-06 16:00 | 45.2 | 9,101 | 4.25 | 7.00 | 2,005 | 725,396,653 |
| **Durango** | 2024-03-06 16:00 | 2024-12-16 17:00 | 40.7 | 12,657 | 2.14 | 4.43 | 2,005 | 730,947,782 |
| **Etna (ACP-77)** | 2024-12-16 17:00 | 2025-04-08 15:00 | 16.1 | 5,179 | 2.14 | 4.43 | 2,000 | 301,102,662 |
| **Fortuna** | 2025-04-08 15:00 | 2025-11-19 16:00 | 32.2 | 7,775 | 2.14 | 4.15 | 2,000 | 601,308,277 |
| **Granite** | 2025-11-19 16:00 | 2026-09-22 15:00 | 43.9 | 4,580 | 3.65 | 3.97 | 14,585 | 890,144,577 |
| **Helicon (Live Census)**| 2026-09-22 15:00 | Active State | Current | 602 nodes | 2.14 (15.0d) | 8.90 (62.3d) | 18,140 | 166,742,110 |

```
[Fig 1: Trajectory of Median Duration and Self-Stake Across Protocol Upgrades]
Genesis to Cortina:     Median Duration held steady at 4.25 to 4.98 weeks (28 to 35 days)
Durango Activation:     Median Duration fell 50% to exactly 2.14 weeks (15.0 days)
Granite Activation:     Median Self-Stake rose 627% from 2,005 AVAX to 14,585 AVAX
```

### 1.2 Two Structural Regime Shocks
The longitudinal record demonstrates two decisive structural transformations:
1. **The Durango Timestamp Alignment Shift (March 2024):** Unweighted median commitment duration held constant between 4.14 and 4.98 weeks from Genesis through Cortina. At Durango, median duration dropped to exactly 2.14 weeks (15.0 days). Durango eliminated client-side transaction timestamp padding by moving validator start times to exact on-chain block acceptance. Operators defaulted to the 14-day protocol floor plus a 1-day execution buffer.
2. **The Granite Subnet Decoupling Shock (Post-ACP-77):** ACP-77 eliminated the mandate requiring sovereign Subnet validators to stake 2,000 AVAX on the Primary Network. Smaller Subnet operators withdrew their capital, reducing the Primary Network staking ratio to an all-time low of 35.19%. Consequently, median validator self-stake rose from 2,005 AVAX to 14,585 AVAX, stake-weighted duration fell to an all-time low of 3.97 weeks, and 41% of 2026 entrant nodes closed themselves to delegation by setting a 100% fee.

### 1.3 Behavioral Invariants from the Shawn Anderson Renewal Panel
Analysis of the 57,067 resolved validator staking periods in the canonical renewal panel (`01-renewal-panel.parquet`) establishes three empirical invariants:

| Staking Period Sequence Number | Observed Staking Decisions | Exit Probability at Expiration | Renewal Probability | Mean Tenure Hazard Ratio |
| :---: | :---: | :---: | :---: | :---: |
| **Period 1** | 7,603 | 28.9% | 71.1% | 1.00x (Baseline) |
| **Period 2** | 5,357 | 17.6% | 82.4% | 0.61x |
| **Period 3** | 4,384 | 14.7% | 85.3% | 0.51x |
| **Period 5** | 3,254 | 11.1% | 88.9% | 0.38x |
| **Period 7** | 2,475 | 7.3% | 92.7% | 0.25x |
| **Period 10** | 1,824 | 14.9% | 85.1% | 0.52x |
| **Period 15** | 1,091 | 4.0% | 96.0% | 0.14x |
| **Period 20** | 783 | 8.3% | 91.7% | 0.29x |

- **Tenure Invariant:** A validator completing its first staking period exhibits an exit hazard nearly three times higher than a node on its fifth staking period (28.9% versus 11.1%).
- **Cohort Polarization:** The top 903 delegation-magnet nodes (11.8% of historical operators) exhibit a 95.6% renewal rate. The remaining 6,732 nodes exhibit an 84.9% renewal rate.
- **Diagonal State-Dependence:** Stakers rarely alter their duration category across renewals. Among validators choosing 14 days, 74.5% choose 14 days on their next renewal. Operators treat duration selection as a fixed operational cadence.

---

## 2. Foundation Cryptoeconomic Objectives and Macro Health Invariants

### 2.1 The Measure, Capture, Distribute Sequence (Matias Antonio Doctrine)
The Foundation economic doctrine establishes that on-chain value generation does not automatically accrue to native token value:
- **Measure:** Total Value Locked (TVL) tracks idle capital stock, while Market Capitalization reflects speculative sentiment. The Foundation replaces these with Gross Chain Product (GCP):
  $$\text{Value Added} = \text{Protocol Onchain Profit} + \text{Transaction Fees Generated}$$
  Deflated through a Fisher Chain-Weighted Index across approximately 700 active tokens:
  $$\text{Fisher Growth} = \sqrt{\text{Laspeyres Growth} \times \text{Paasche Growth}}$$
  Between January 2025 and March 2026, while nominal C-Chain output dropped 60% during token price depreciation, Real GCP dropped only 25%, establishing underlying economic resilience. Gross Chain Income (GCI) tracks off-chain flows settling on Avalanche.
- **Capture:** Broadens protocol revenue capture beyond C-Chain gas burns through ACP-283 dynamic base fee governance, ACP-77 continuous L1 validator burns (1 AVAX per validator per month), and ACP-103 dynamic P-Chain transaction pricing.
- **Distribute:** Manages the equilibrium allocation between token supply burns (distributing value to passive holders through supply contraction) and active validator staking yields.

```
       ┌─────────────────────────────────────────────────────────────┐
       │             GROSS CHAIN PRODUCT (GCP) & GCI                 │
       │   Real Output = Onchain Profit + Network Transaction Fees   │
       └──────────────────────────────┬──────────────────────────────┘
                                      │
                         [ 1. MEASURE ECOSYSTEM VALUE ]
                                      │
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │                 PROTOCOL REVENUE CAPTURE                    │
       │  * Primary Network Transaction Burns (ACP-283 / ACP-103)    │
       │  * Continuous Avalanche L1 Validator Burns (ACP-77)         │
       │  * Cross-L1 Settlement & Interoperability Surplus           │
       └──────────────────────────────┬──────────────────────────────┘
                                      │
                         [ 2. CAPTURE AT PROTOCOL LEVEL ]
                                      │
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │             DISTRIBUTE & SUSTAIN CONSENSUS SECURITY         │
       │  * Supply Burn (Permanent Scarcity Accrual to Liquid AVAX)  │
       │  * Validator Staking Subsidy Transition (Emissions -> Fees)  │
       │  * Admission Frontier & Yield Steering (ACP-273 x ACP-285)  │
       └─────────────────────────────────────────────────────────────┘
```

### 2.2 Macro Health Invariants and Targets (Dr. Eric Lu Specifications)
The Foundation macro health targets establish four quantitative operational boundaries:

| Macro Target Metric | Historical Genesis / Peak | Granite Regime Baseline | Foundation Strategic Corridor | Systems Engineering Justification |
| :--- | :--- | :--- | :--- | :--- |
| **Network Staking Ratio** ($\sigma$) | 64.2% | 35.19% | **50.0% to 60.0%** | Defends Byzantine quorum thresholds against market buyout float. |
| **Active Validator Set** ($N_{\text{nodes}}$) | 1,500+ nodes | 602 concurrent nodes | **>= 600 Independent Nodes** | Preserves Snow consensus sample entropy and physical decentralization. |
| **Stake-Weighted Duration** ($\bar{d}_{\text{macro}}$) | 38.5 weeks | 3.97 weeks | **>= 16.9 weeks (~4 months)** | Eliminates macro rollover cliffs and short-term capital flight risks. |
| **Validator Liveness Floor** | 80.0% | 93.4% median | **>= 90.0% Uptime (ACP-267)** | Enforces DAG consensus finality speed and low-latency round trip times. |

### 2.3 Finite Issuance Exhaustion Dynamics
Under the Avalanche genesis specification, total supply is strictly capped at 720,000,000 AVAX, with 360,000,000 minted at genesis and the remaining 360,000,000 allocated for staking emissions. The emission rate at time $t$ is governed by the remaining unminted supply $S_{\text{rem}}(t)$:
$$\Delta S(t) = \left( r_{\min} + (r_{\max} - r_{\min}) \frac{d}{T} \right) \cdot \frac{S_{\text{rem}}(t)}{S_{\text{cap}}} \cdot S_{\text{staked}}$$
Because $S_{\text{rem}}(t) \to 0$ over time, the protocol staking subsidy decays continuously. Long-term security requires capturing transaction revenues through ACP-283, ACP-77, and ACP-103 to replace decaying minting subsidies.

---

## 3. Consensus Capital Distribution and the Delegator Firewall

### 3.1 Network Capital Distribution
The post-Etna consensus active set comprises 602 concurrent validators exhibiting structural capital polarization:
- **Retail Sovereign Tier (< 6,000 AVAX):** 229 nodes holding 599,000 AVAX self-bond (0.34% of consensus capital). Median bond: 2,070 AVAX. Median duration: 15.0 days.
- **Whale Institutional Tier (>= 6,000 AVAX):** 373 nodes holding 175,000,000 AVAX self-bond (99.66% of consensus capital) and 191,600,000 AVAX of delegated stake. Median self-bond: 181,000 AVAX (top tier exceeding 1,200,000 AVAX).

### 3.2 The 14-Day Delegator Firewall (PlatformVM Consensus Rule)
ACP-273 reduced the minimum duration to 48 hours strictly for Primary Network validator self-stakes. **Delegator staking duration remains hardcoded at 14 days (336 hours)**. PlatformVM state validation strictly enforces:
$$\text{delegation.startTime} \ge \text{validator.startTime} \quad \text{AND} \quad \text{delegation.endTime} \le \text{validator.endTime}$$

This consensus verification rule establishes a cryptographic boundary:
- **Zero Delegations for 48-Hour Stints:** A node registered for less than 14 days cannot accept delegations. Any `AddDelegatorTx` targeting a 48-hour validator is rejected by every consensus node on the network.
- **Institutional Quarantine:** Liquid staking protocols (BENQI managing 18,143,774 AVAX) and commercial validator fleets cannot utilize the 48-hour window without forfeiting their entire delegation fee revenue model. The 48-hour window is quarantined to proprietary solo treasury capital.

```
                                  CRITICAL FRICTION POINTS
                                  
     [ ACP-273: 48h Validator ] ───────────────┬───────────────> [ ACP-49: 500 AVAX Floor ]
                    │                           │
                    │               THE DECOUPLED SYBIL TRAP
                    │               (96.4% Skin-in-the-game Collapse)
                    │
                    ▼
     [ 14-DAY DELEGATOR FIREWALL ] ────────────┼───────────────> [ BENQI LST / Custodial Pools ]
     * Delegator min = 14d                      │                 * 18.14M AVAX Locked
     * delegator.end <= validator.end           │                 * Forced into >= 14d stints
     * 48h nodes reject delegations!            │
                    │
                    ▼
     [ ACP-236: Auto-Renewal ] ────────────────┼───────────────> [ ACP-285: Yield Steepening ]
     * Auto-restakes every 48h                 │                 * Must create steep penalty at 48h
     * Maximizes liquidity option              │                 * Prevents rational tenure collapse
```

### 3.3 The BENQI Capital Footprint and Open Pool Knot
On-chain analysis of BENQI's delegation footprint reveals their dominant structural role:
- **Active Delegated Stock:** 18,143,774 AVAX (46.9% of all delegated capital on Avalanche).
- **Trailing 365-Day Volume Flow:** 467,435,493 AVAX (70.5% of total network delegation flow).
- **Annual Capital Turnover:** 25.76 times per year ($365 / 25.76 = 14.17\text{ days}$). BENQI systematically churns in 14-day terms.
- **The 6,000 AVAX Threshold Knot:** BENQI's Open Pool (accounting for 65% of delegation volume) requires validator self-stake $\ge 6{,}000\text{ AVAX}$, a fee of exactly 2%, and uptime $\ge 15\text{ days}$. Validators with $\ge 6{,}000\text{ AVAX}$ captured 97.18% of all delegation volume in network history (2.67 billion AVAX). The Admission Frontier must preserve the knot at $(14\text{d}, 6{,}000\text{ AVAX})$ to maintain physical node financing.

---

## 4. Multi-Agent Game Theory and Payoff Matrix

### 4.1 Payoff Matrix Across Capital Profiles
Evaluating actor payoffs across durations under live ACP-285 yield curves ($r(2\text{d}) = 3.950\%$, $r(14\text{d}) = 4.078\%$, $r(84\text{d}) = 4.536\%$, $r(118\text{d}) = 4.759\%$):

| Actor and Capital Profile | Decision Strategy | Duration ($d$) | Nominal ARR(d) | Delegation Fee Income | Net Effective ARR(d) | Liquidity Window | Strategic Equilibrium Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Whale Validator** (181,000 AVAX bond, 220k delegation) | **Strategy W1: 48h Churn** | 2 days | 3.950% | 0.000% (Firewall blocked) | 3.950% | 48 hours | Dominated by delegation revenue loss. |
| **Whale Validator** (181,000 AVAX bond, 220k delegation) | **Strategy W2: Status Quo** | 14 days | 4.078% | +0.248% (2% fee on 220k) | 4.326% | 14 days | Baseline under legacy delegation rules. |
| **Whale Validator** (181,000 AVAX bond, 220k delegation) | **Strategy W3: Macro Lock** | 84 days | 4.536% | +0.276% (2% fee on 220k) | 4.812% | 12 weeks | **Strictly Dominant** under ACP-285 yield steepening (+48.6 bps net gain). |
| **Retail Validator** (2,000 AVAX bond, 0 delegation) | **Strategy R1: 48h Churn** | 2 days | 3.950% | 0.000% | 2.990% (after -0.96% VPS drag) | 48 hours | Exit state: Net ARR(d) (2.99%) falls below sAVAX outside option (4.15%). |
| **Retail Validator** (2,000 AVAX bond, 0 delegation) | **Strategy R2: 14d Stint** | 14 days | 4.078% | 0.000% | 3.118% (after -0.96% VPS drag) | 14 days | Sub-economic: Operator experiences net drag relative to sAVAX (4.15%). |
| **Retail Validator** (2,000 AVAX bond, 0 delegation) | **Strategy R3: Target Lock** | 84 to 118 days | 4.536% to 4.759% | 0.000% | 3.576% to 3.799% | 12 to 17 weeks | **Individual Rationality Sustained:** Compensates operator hardware overhead while unlocking solo validation. |
| **BENQI LST Pool** (18.14M AVAX pooled stake) | **Strategy B1: Route to 48h** | 2 days | 3.950% | N/A | Protocol failure | 48 hours | Cryptographically rejected by PlatformVM firewall. |
| **BENQI LST Pool** (18.14M AVAX pooled stake) | **Strategy B2: 14d Cadence** | 14 days | 4.078% | +2.000% protocol fee | 4.078% pool ARR(d) | 14 days | Operational baseline. |
| **BENQI LST Pool** (18.14M AVAX pooled stake) | **Strategy B3: 60d Tranche** | 60 days | 4.380% | +2.000% protocol fee | 4.380% pool ARR(d) | 60 days | Captures +30.2 bps higher ARR(d) for sAVAX holders, constrained by liquidity buffers. |

### 4.2 Nash Equilibrium Configuration
The resulting Nash Equilibrium settles into a bifurcated architecture:
1. **Whale Validators:** Settle at durations >= 14 days (dominantly 60 to 180 days). Dropping to 48 hours forfeits delegation fee cash flow and surrenders 80.9 basis points of ACP-285 yield.
2. **Retail Validators:** Guided by the Admission Frontier into 70 to 118-day commitments, earning higher protocol ARR(d) to offset server overhead ($40/month VPS drag).
3. **Institutional LSTs:** Quarantined to durations >= 14 days by the PlatformVM consensus firewall, aligning institutional liquidity with macro network duration targets.

---

## 5. Capital Geometry of the Admission Frontier $S_{\min}(d)$

### 5.1 Global Sybil Parity Invariant
To prevent stake-splitting attacks that dilute Snow consensus sampling or bloat P-Chain state, the cumulative capital-duration commitment at any duration $d$ must equal or exceed Mainnet's canonical baseline ($2{,}000\text{ AVAX} \times 14\text{ days} = 28{,}000\text{ AVAX-days}$):
$$\kappa(d) = S_{\min}(d) \cdot d \ge 28{,}000\text{ AVAX-days} \implies S_{\min}(2\text{d}) \ge 14{,}000\text{ AVAX}$$

Decoupling ACP-49 ($500\text{ AVAX}$) and ACP-273 ($2\text{ days}$) without the frontier produces a 96.4% collapse in skin-in-the-game ($1{,}000\text{ AVAX-days}$), allowing an attacker to generate 28 times more validator identities for identical capital exposure.

### 5.2 Mathematical Formulation of Harmonic Bounded Decay
The Continuous Harmonic Bounded Decay curve operates as a standalone protocol-level state transition gate:
$$S_{\min}(d) = 500 + (S_{\text{short}} - 500) \cdot \left[ \frac{\frac{1}{d} - \frac{1}{365}}{\frac{1}{2} - \frac{1}{365}} \right]^p$$
$$\text{where}\quad p = \frac{\ln\left(\frac{2{,}000 - 500}{S_{\text{short}} - 500}\right)}{\ln\left(\frac{\frac{1}{d_{\text{target}}} - \frac{1}{365}}{\frac{1}{2} - \frac{1}{365}}\right)}$$

- **Left Boundary ($d = 2\text{d}$):** $S_{\min}(2) = S_{\text{short}}$ identically.
- **Right Boundary ($d = 365\text{d}$):** $S_{\min}(365) = 500\text{ AVAX}$ identically (ACP-49).
- **Pivot Knot ($d = d_{\text{target}}$):** $S_{\min}(d_{\text{target}}) = 2{,}000\text{ AVAX}$ identically.

### 5.3 Governance Schedule Comparison
Comparing candidate policy schedules from the requirements specification:

| Evaluation Dimension | Package A: Gradual Bridge | Package B: Target Corridor (RECOMMENDED) | Package C: Aggressive Extension |
| :--- | :--- | :--- | :--- |
| **Short Anchor Stake ($S_{\text{short}}$ at 2d)** | 14,000 AVAX | **18,000 AVAX** | 20,000 AVAX |
| **Target Lockup ($d_{\text{target}}$ for 2k)** | 56 days (8.0 weeks) | **84 days (12.0 weeks)** | 118 days (16.9 weeks) |
| **Exponent Parameter ($p$)** | 0.58 | **0.65** | 0.72 |
| **14-Day Admission Stake ($S_{\min}(14\text{d})$)**| 4,387 AVAX | **5,678 AVAX** | 6,756 AVAX |
| **BENQI 6k Knot Alignment** | Fits beneath 6k floor | **Harmonious (5,678 < 6,000)** | Exceeds 6k floor (friction) |
| **2-Day Sybil Parity Ratio** | 1.00x (28,000 AVAX-d) | **1.29x (36,000 AVAX-d)** | 1.43x (40,000 AVAX-d) |
| **Macro Duration Lift** | Lifts to ~19.5 weeks | **Lifts to 21.6 weeks** | Lifts to 23.8 weeks |
| **Systems Engineering Assessment** | Conservative entry | **Optimal balance of security and access** | High friction on 2k nodes |

---

## 6. Tinbergen Policy Separation Matrix and Structural Limits

### 6.1 The Tinbergen Rule in Avalanche Governance
Jan Tinbergen established that achieving $N$ independent economic policy targets requires at least $N$ independent policy instruments. Attempting to solve multiple distinct failures with a single blunt instrument introduces severe systemic distortion.

```
┌─────────────────────────────────┬─────────────────────────────────┬─────────────────────────────────┐
│     MACRO NETWORK TARGET        │       PRIMARY POLICY LEVER      │      COORDINATED MECHANISM      │
├─────────────────────────────────┼─────────────────────────────────┼─────────────────────────────────┤
│ 1. Anti-Sybil & State Health    │ Admission Frontier S_min(d)     │ Hyperbolic Capital Barrier      │
│ 2. Macro Duration Expansion     │ ACP-285 Yield Curve Gradient    │ Asymmetric Floor Reduction      │
│ 3. Institutional Liquidity      │ ACP-273 48h Validator Window    │ Quarantined Proprietary Float   │
│ 4. Permanent Token Deflation    │ ACP-283 & ACP-77 Fee Burns      │ Dynamic Gas Voting & L1 Fees    │
│ 5. PlatformVM DoS Mitigation    │ ACP-103 Dynamic P-Chain Fees    │ Multidimensional Base Fee       │
│ 6. Broad Decentralized Entry    │ Asymptotic Floor (500 AVAX)     │ Tenure Discount at 365 Days     │
└─────────────────────────────────┴─────────────────────────────────┴─────────────────────────────────┘
```

### 6.2 Structural Limits of the Admission Frontier $S_{\min}(d)$
The Admission Frontier is an indispensable mechanism, but its capabilities are strictly bounded by four structural limits:
1. **The Scale-Invariance Limit:** $S_{\min}(d)$ functions as an entry filter. It successfully halts micro-capital Sybil attacks at 48 hours ($500\text{ AVAX} \times 2\text{d} = 1,000\text{ AVAX-days}$). However, it is scale-invariant with respect to large capital: a treasury holding 181,000 AVAX or an LST pool holding 18,143,774 AVAX easily satisfies any flat barrier ($18,000$, $50,000$, or $100,000$ AVAX). Sizing $S_{\text{short}}$ above 20,000 AVAX fails to extend whale duration; it merely prices out decentralized operators.
2. **The Inflation Invariance Limit:** $S_{\min}(d)$ controls access barriers; it does not adjust the network emission rate or supply schedule. Managing the security budget transition as issuance exhausts requires ACP-285 (reward curve steepening) and ACP-283 (dynamic fee burns).
3. **The Hardware Drag Invariance Limit:** $S_{\min}(d)$ cannot alter the off-chain cost of validator hardware ($>\$40/\text{month}$ VPS). It can only guide small nodes toward lockups where protocol ARR(d) covers hosting drag.
4. **The Delegation Concentration Limit:** $S_{\min}(d)$ does not resolve delegation skew (where 52.8% of nodes receive zero delegations). Expanding delegation caps under ACP-247 ($24\times$) without duration weighting further concentrates delegated capital into large custodial operators.

---

## 7. Governance Implementation Schedule and Quantized Brackets

### 7.1 Quantized Integer Schedule for PlatformVM Implementation
To prevent floating-point non-determinism in Go consensus validation (`vms/platformvm`), the continuous curve under Package B ($S_{\text{short}} = 18{,}000\text{ AVAX}$, $d_{\text{target}} = 84\text{ days}$, $S_{\text{floor}} = 500\text{ AVAX}$, $p = 0.65$) is quantized into discrete duration brackets:

| Duration Range (Days) | Representative Tenure | Quantized Minimum Stake ($S_{\min}$) | Capital-Time Commitment | Sybil Parity Multiplier |
| :---: | :---: | :---: | :---: | :---: |
| **$2 \le d < 7$** | 48 Hours to 6 Days | **18,000 AVAX** | 36,000 to 108,000 AVAX-days | 1.29x to 3.86x |
| **$7 \le d < 14$** | 1 Week | **8,500 AVAX** | 59,500 AVAX-days | 2.13x |
| **$14 \le d < 30$** | 2 Weeks (Delegator Floor) | **5,678 AVAX** | 79,492 AVAX-days | 2.84x |
| **$30 \le d < 60$** | 1 Month | **3,680 AVAX** | 110,400 AVAX-days | 3.94x |
| **$60 \le d < 84$** | 2 Months | **2,520 AVAX** | 151,200 AVAX-days | 5.40x |
| **$84 \le d < 180$** | 12 Weeks (Target Horizon) | **2,000 AVAX** | 168,000 AVAX-days | 6.00x |
| **$180 \le d < 365$** | 6 Months | **1,120 AVAX** | 201,600 AVAX-days | 7.20x |
| **$d \ge 365$** | 1 Year (ACP-49 Floor) | **500 AVAX** | 182,500 AVAX-days | 6.52x |

### 7.2 Multi-Stakeholder Target Alignment Matrix
This recommended policy schedule balances the competing demands of all network participants:

| Stakeholder Group | Primary Strategic Objective | Policy Impact Under Recommended Architecture | Performance Against Objective |
| :--- | :--- | :--- | :--- |
| **Avalanche Foundation** | Macro security duration >= 16.9w; inflation reduction; sustainable value accrual. | Macro duration expands to **21.61 weeks**; ACP-285 reduces emission growth by ~20%; ACP-283/77 burns permanently destroy liquid supply. | **Surpasses Target:** Reaches 21.6w security horizon without capital flight. |
| **Node Operators (Validators)** | Positive economic return over hardware VPS hosting costs ($40/month drag). | Retail nodes at 84 days earn $4.536\%$ ARR(d). Net ARR(d) after VPS drag is $3.58\%$, outperforming shorter lockups and preserving node viability. | **Individual Rationality Secured:** Replaces loss-making 14d stints with profitable 12w stints. |
| **Institutional Treasuries & ETFs** | Fast capital liquidity and predictable redemption settlement. | ACP-273 provides 48-hour unstaking capability for proprietary capital backed by 18,000 AVAX anchor bonds. | **Institutional Access Delivered:** Satisfies 24-48h ETF redemption mandates. |
| **Delegators & Retail Holders** | Principal capital safety; liquid staking rewards on sAVAX. | PlatformVM 14-day delegator firewall preserves delegation stability; BENQI captures 4.38% pool ARR(d) at 60-day tranches. | **Consensus Security Preserved:** Protects retail delegators from high-frequency node churn. |

---

## 8. Action Items and Synchronization for Foundation Review

1. **PlatformVM Protocol Synchronization:**
   - Coordinate with Ava Labs engineering to implement `GetMinimumValidatorStake(duration)` as a state validation check within `vms/platformvm/txs/builder.go` for `AddPermissionlessValidatorTx`.
   - Maintain the 14-day delegator duration rule in PlatformVM to ensure the Delegator Firewall remains cryptographically intact.
2. **ACP Governance Coupling:**
   - Enforce coupled voting on ACP-273 (48h duration) and ACP-285 (yield curve steepening). ACP-273 must never activate without ACP-285 yield differentials.
   - Advance ACP-103 to implement dynamic multidimensional base fees on the P-Chain, neutralizing high-frequency staker turnover spam.
3. **Delegation Matching Architecture:**
   - Establish community delegation matching pools to route delegations toward standalone 2,000 AVAX nodes committing to $\ge 84\text{ days}$, offsetting hardware VPS costs.

---

## 9. Remaining Technical Questions

1. **Whale Capital Allocation Under Extreme Volatility:**
   - While the Marginal Rate of Substitution (MRS) is estimated at 0.80 to 0.85 percentage points per additional week of duration across retail delegators, proprietary institutional treasuries (holding > 1,000,000 AVAX) may prioritize absolute liquidity optionality over ARR(d) spreads during severe crypto market drawdown regimes. Empirical validation of whale duration response under a live steepened ACP-285 curve awaits Mainnet activation telemetry.
2. **Dynamic P-Chain Base Fee Calibration (ACP-103):**
   - The gas target and elasticity multipliers for `AddValidatorTx` under ACP-103 have not yet been formalized in a merged ACP specification. Determining the exact fee charged per 48-hour stint requires coordination with Ava Labs PlatformVM maintainers.
3. **Decentralized Delegation Distribution Mechanics:**
   - The admission frontier successfully governs validator entry duration and capital, but does not allocate delegations. Resolving the 52.8% zero-delegation rate among small nodes requires dedicated mechanism design (such as duration-weighted delegation leverage or quadratic delegation matching).
