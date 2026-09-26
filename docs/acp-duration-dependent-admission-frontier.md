| ACP | (TBD) |
| :--- | :--- |
| **Title** | Duration-Dependent Minimum Validator Stake Frontier |
| **Author(s)** | Hasher Nabi ([@coad1024-cmd](https://github.com/coad1024-cmd)), BCRG Systems Engineering Team |
| **Status** | Proposed |
| **Track** | Standards |

## Abstract

This proposal establishes a duration-dependent admission frontier, $S_{\min}(d)$, for Primary Network consensus validators in AvalancheGo. The protocol currently enforces a static minimum self-stake of 2,000 AVAX across all allowable durations from 14 days to 365 days. In the historical record of 57,067 validator stints spanning 7,635 distinct nodes, this static requirement produced extreme duration compression: the median staking period is 23 days, compressing to 15 days following the Etna network upgrade. Independent proposals reduce the minimum stake to 500 AVAX (ACP-49) and shorten the minimum duration to 48 hours (ACP-273). If implemented as uncoupled static parameters, an operator can register a consensus validator with 500 AVAX for 48 hours. This reduces the capital-time Sybil commitment from the historical 28,000 AVAX-days to 1,000 AVAX-days, a 96.43% reduction in economic security.

This specification couples validator self-stake to commitment duration through a bounded harmonic decay function. Long-term stakers committing for 365 days access a reduced entry barrier of 500 AVAX (or 600 AVAX under conservative calibration). Short-term stakers utilizing the 48-hour window provide an 18,000 AVAX anchor bond, preserving a 36,000 AVAX-days Sybil commitment that exceeds the historical Mainnet baseline (1.286x parity). The continuous function is quantized into eight discrete integer brackets within `vms/platformvm` evaluated in nanoseconds and `nAVAX` to eliminate floating-point non-determinism during block verification.

Tinbergen instrument separation governs the mechanism: the admission frontier $S_{\min}(d)$ exists for three explicit protocol objectives: Retail Entry Relief (500 to 600 AVAX), 48-Hour Sybil Parity (18,000 AVAX anchor bond), and P-Chain Churn Defense—while macro stake-weighted duration expansion across institutional whale capital is governed by ACP-285 annualized reward rate $\text{ARR}(d)$ steepening.

## Motivation

### Empirical Baseline and Historical Telemetry

The Avalanche Primary Network enforces a static minimum self-stake rule:

```
S_min = 2,000 AVAX for all d in [14 days, 365 days]
```

Onchain telemetry from the primary staking dataset (`01-renewal-panel.parquet`), comprising 57,067 completed validator stints across 7,635 physical nodes, documents the structural consequences of this static barrier:

1. **Extreme Capital Clustering at the Static Floor:** The median self-bond across all historical stints is 2,015 AVAX (mean 97,264 AVAX). Over 74.8% of all validator stints (42,710 records) registered with self-bonds between 2,000 AVAX and 6,000 AVAX.
2. **Short-Tenor Duration Compression:** The unweighted median staking duration is 23 days (mean 45.6 days). Staking periods of exactly 14 days represent 16.38% of all validator stints (9,347 records). Stints under 30 days account for 58.97% (33,654 records). Commitments spanning 365 days represent 4.10% of historical stints (2,340 records).
3. **Regime Shock and Duration Erosion:** Across the Etna upgrade boundary, median validator duration compressed from 29 days to 15 days (2.14 weeks). In the Granite regime, median self-stake jumped to 14,585 AVAX, and stake-weighted duration fell to an all-time low of 3.97 weeks.
4. **Institutional Delegation Concentration:** Liquid staking contracts (principally BENQI) mandate a 6,000 AVAX self-stake for Open Pool delegation eligibility. Stints with self-bonds at or above 6,000 AVAX (14,357 records) captured 2.67 billion AVAX in cumulative delegations (97.18% of all network delegation volume). Stints below 6,000 AVAX captured 77.4 million AVAX (2.82% of volume).
5. **P-Chain Transaction Distribution:** Delegations account for 46.0% of all P-Chain transactions at a 100:1 ratio to validator transactions (ACP-273 telemetry).

```
┌────────────────────────────────────────────────────────────────────────┐
│              HISTORICAL STAKING TELEMETRY (57,067 STINTS)              │
├──────────────────────────┬──────────────────────┬──────────────────────┤
│ Metric                   │ Measured Value       │ Source Dataset       │
├──────────────────────────┼──────────────────────┼──────────────────────┤
│ Total Validator Stints   │ 57,067 records       │ 01-renewal-panel     │
│ Unique Physical NodeIDs  │ 7,635 nodes          │ 01-renewal-panel     │
│ Median Self-Bond         │ 2,015 AVAX           │ Snowflake UTXO logs  │
│ Mean Self-Bond           │ 97,264 AVAX          │ Snowflake UTXO logs  │
│ Median Staking Duration  │ 23.00 days           │ P-Chain State DB     │
│ Mean Staking Duration    │ 45.59 days           │ P-Chain State DB     │
│ Stints <= 30 Days        │ 33,654 (58.97%)      │ 01-renewal-panel     │
│ Stints >= 365 Days       │ 2,340 (4.10%)        │ 01-renewal-panel     │
│ Post-Etna Median Tenor   │ 15.00 days           │ 01-renewal-panel     │
│ Granite Median Self-Stake│ 14,585 AVAX          │ 01-renewal-panel     │
│ Delegation-to-Validator  │ 100:1 ratio          │ ACP-273 Telemetry    │
│ Delegation P-Chain Share │ 46.0% of P-Chain txs │ ACP-273 Telemetry    │
└──────────────────────────┴──────────────────────┴──────────────────────┘
```

### Decoupled Sybil Vulnerability

Two pending proposals modify these parameters independently:
- **ACP-49:** Lowers minimum validator self-stake from 2,000 AVAX to 500 AVAX.
- **ACP-273:** Lowers minimum validator duration from 14 days to 48 hours.

Implementing these proposals as uncoupled static parameters allows a node operator to occupy an active consensus slot with:

$$K_{\text{decoupled}} = 500\text{ AVAX} \times 2\text{ days} = 1{,}000\text{ AVAX-days}$$

The historical Mainnet baseline requires:

$$K_{\text{baseline}} = 2{,}000\text{ AVAX} \times 14\text{ days} = 28{,}000\text{ AVAX-days}$$

This combination reduces the economic commitment per validator slot by 96.43%. An attacker with 28,000 AVAX can operate 28 concurrent consensus validators under decoupled parameters, compared to a single validator under historical rules.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   DECOUPLED SYBIL COLLAPSE METRICS                     │
├──────────────────────────┬──────────────────────┬──────────────────────┤
│ Metric                   │ Historical Mainnet   │ Decoupled ACP-49/273 │
├──────────────────────────┼──────────────────────┼──────────────────────┤
│ Minimum Self-Stake       │ 2,000 AVAX           │ 500 AVAX             │
│ Minimum Duration         │ 14 Days              │ 2 Days               │
│ Capital-Time Commitment  │ 28,000 AVAX-days     │ 1,000 AVAX-days      │
│ Relative Sybil Cost      │ 1.000x               │ 0.0357x (-96.43%)    │
│ Slots per 28,000 AVAX    │ 1 consensus slot     │ 28 consensus slots   │
└──────────────────────────┴──────────────────────┴──────────────────────┘
```

This vulnerability generates three concrete operational hazards:
1. **Consensus Sampling Instability:** Snowman consensus repeatedly samples small subsets of validators. Replacing persistent nodes with 48-hour transient nodes increases sample variance and heightens the risk of partition attacks during network latency spikes.
2. **P-Chain State Churn:** ACP-273 documents that delegations account for 46% of all P-Chain transactions at a 100:1 ratio to validator transactions. Introducing micro-stake short-duration validators accelerates BLS key registration and staking UTXO writes, increasing database commit latency on validator nodes.
3. **Validator Set Churn:** As stated in ACP-273 Security Considerations, a network where capital cycles every 48 hours permits major ownership changes within two days, compromising L1 Interchain Message (ICM) verification stability.

### Capital-Time Equivalence Principle

Protocol security requires a stable aggregate capital-time integral:

$$K = \int_0^T S(t) \, dt$$

Capital and duration act as technical substitutes in providing Sybil resistance:
- Operators committing capital for 365 days provide persistent network anchoring, warranting a lower capital barrier ($500\text{ to }600\text{ AVAX}$).
- Operators demanding 48-hour liquidity optionality introduce turnover and state overhead, requiring an $18{,}000\text{ AVAX}$ capital commitment.

Coupling stake to duration via an admission frontier $S_{\min}(d)$ guarantees that short-term stakers fully internalize the cost of transient membership.

### Policy Goals and System Objectives

This specification enforces three explicit protocol objectives:

1. **48-Hour Sybil Parity Invariant:** Guarantee that short-duration validator commitments satisfy $K(2\text{d}) = S_{\min}(2\text{d}) \cdot 2\text{d} \ge 36{,}000\text{ AVAX-days}$, establishing a 1.286x security buffer relative to the historical Mainnet baseline ($2,000\text{ AVAX} \times 14\text{d} = 28,000\text{ AVAX-days}$).
2. **Retail Entry Relief:** Lower the capital entry barrier for 365-day stakers from 2,000 AVAX down to 500 AVAX (Package B) or 600 AVAX (Package B-600), delivering a 70% to 75% barrier reduction for sovereign home operators.
3. **P-Chain Churn Defense:** Constrain high-frequency validator turnover through the $18,000\text{ AVAX}$ anchor bond and maintain the 14-day Delegator Firewall to isolate retail delegation traffic from transient consensus churn.

Macro stake-weighted network duration expansion across institutional whale capital is explicitly governed by ACP-285 annualized reward rate $\text{ARR}(d)$ steepening—not by the admission frontier.

### Modeling Assumptions and Behavioral Invariants

The design of the admission frontier rests upon five empirical and behavioral assumptions:

1. **Rational Economic Optimization:** Node operators evaluate duration choices through net economic returns, balancing liquidity optionality against protocol yield $\text{ARR}(d)$, server hosting costs ($40/month VPS), and delegation fee income.
2. **Bimodal Capital Distribution:** Consensus capital divides into a retail sovereign tier (< 6,000 AVAX, median bond 2,015 AVAX) and an institutional whale tier ($\ge 6,000$ AVAX, median bond 181,000 AVAX, commanding over 99% of consensus stake weight).
3. **Institutional Delegation Infrastructure:** Delegation volume continues to route through liquid staking protocols (BENQI managing 18.14M AVAX, representing 70.5% of annual delegation flow) requiring 6,000 AVAX validator self-bonds and durations $\ge 14\text{ days}$.
4. **Stationary Continuous Arrival:** Ongoing staking contracts mature as a continuous arrival process ($\tau_{\text{rem}} \sim U(1, d_{\text{choice}})$), precluding synthetic synchronization shocks and artificial harmonic resonance.
5. **Transaction Dominance:** P-Chain transaction volume is dominated by delegations at a 100:1 ratio relative to validator registrations.

### Boundary Constraints and Tinbergen Policy Separation

The Tinbergen Separation Principle establishes that achieving $N$ independent economic policy targets requires at least $N$ independent policy instruments. Attempting to solve multiple distinct network challenges with a single admission lever introduces structural distortion.

```
┌─────────────────────────────────┬─────────────────────────────────┬─────────────────────────────────┐
│ System Target                   │ Primary Policy Instrument       │ Interaction with Admission Rule │
├─────────────────────────────────┼─────────────────────────────────┼─────────────────────────────────┤
│ 1. Capital Barrier Reduction    │ Admission Frontier Floor (500)  │ Direct enforcement via S_floor  │
│ 2. Sybil Defense at 48h         │ Short Anchor Bond (18,000 AVAX) │ Direct enforcement via S_short  │
│ 3. Macro Duration Expansion     │ ACP-285 ARR(d) Yield Steepening │ Guided via 12-week pivot        │
│ 4. Token Issuance Control       │ ACP-285 Max Consumption Rate    │ Invariant (governed by ACP-285) │
│ 5. P-Chain State Churn Defense  │ ACP-103 Multidimensional Fees   │ Complemented via short bond     │
│ 6. Hardware Hosting Viability   │ Net ARR(d) Yield Margin         │ Steers small nodes to >=84d     │
└─────────────────────────────────┴─────────────────────────────────┴─────────────────────────────────┘
```

#### Achievable Cryptoeconomic Objectives

1. **Sybil Parity at 48 Hours:** Enforcing an 18,000 AVAX requirement at 48 hours establishes $K(2\text{d}) = 36{,}000\text{ AVAX-days}$, providing a 1.286x security surplus relative to the historical baseline.
2. **Capital Barrier Relief for Annual Commitments:** Long-term validators committing for 365 days access a 500 AVAX floor (Package B) or 600 AVAX floor (Package B-600), lowering entry barriers for home stakers.
3. **Retail Validator Duration Lift:** Small nodes facing VPS hosting overhead are guided toward the 84-day pivot horizon ($2{,}000\text{ AVAX}$) where annualized yields $\text{ARR}(d)$ produce positive net income.
4. **P-Chain State Protection:** Combining the 18,000 AVAX anchor bond with the 14-day Delegator Firewall isolates retail delegation traffic from transient consensus turnover.

#### Structural Boundaries and the Scale-Invariance Limit

1. **Whale Duration Invariance:** The admission frontier operates as an entry barrier. Large institutional entities holding 181,000 to 1,000,000+ AVAX easily satisfy an 18,000 AVAX barrier at 48 hours. Elevating the barrier further prices out decentralized operators without altering whale lockup behavior.
2. **Macro Stake-Weighted Duration Expansion:** Macro stake-weighted duration is driven by whale capital allocation, as institutional entities control over 99% of network consensus stake weight. Whales select duration based on the annualized yield differential in ACP-285 ($\text{ARR}(365\text{d}) - \text{ARR}(2\text{d})$), not the admission threshold.
3. **Attribution Error Correction:** Attributing macro network duration expansion to the admission frontier represents an attribution error. The admission frontier functions as an entry control and anti-Sybil instrument. Protocol emission and yield steering operate as separate macroeconomic instruments. Macro duration expansion requires the coordinated activation of ACP-285 yield curve steepening.

### Evaluated Functional Form Alternatives and Trade-off Analysis

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
│ Bounded Harmonic    │ 500 + 17,500 * [H(d)]^p   │ None (Selected)      │
└─────────────────────┴───────────────────────────┴──────────────────────┘
```

1. **Pure Iso-Commitment ($S(d) = \max(S_{\text{floor}}, K_{\text{baseline}}/d)$):** Clamps to $S_{\text{floor}} = 500\text{ AVAX}$ at $d = 28{,}000 / 500 = 56.0\text{ days}$ (or $46.7\text{ days}$ for $600\text{ AVAX}$). For durations between 57 days and 365 days (85.1% of the allowable domain), the requirement is completely flat. This removes all capital incentives for locking beyond 8 weeks.
2. **Standard Hyperbolic ($S(d) = S_{\text{floor}} + \frac{S_{\text{short}} - S_{\text{floor}}}{1 + \alpha (d - d_{\min})}$):** If $\alpha$ is calibrated to anchor $S(84) = 2{,}000\text{ AVAX}$, the heavy algebraic tail produces $S(365) = 862.92\text{ AVAX}$, missing the 500 AVAX target by 72.6%. If $S_{\text{floor}} = 600\text{ AVAX}$, it produces $S(365) = 937.26\text{ AVAX}$, overshooting by 56.2%.
3. **Generalized Power-Law Decay ($S(d) = S_{\text{floor}} + \Delta S \cdot \left(\frac{365 - d}{363}\right)^p$):** Fitting $S(84) = 2{,}000\text{ AVAX}$ requires an extreme exponent $p = 9.59$ (for 500 floor) or $p = 9.84$ (for 600 floor). This causes severe distortion: at 14 days, the stake requirement remains excessively elevated at $13{,}093\text{ to }13{,}175\text{ AVAX}$, failing to provide liquidity relief.
4. **Piecewise Discrete Cliffs ($S(d) = S_k$ without continuous derivation):** Setting discrete tiers without an underlying continuous curve creates severe cliff-edge arbitrage (for example, 13 days 23 hours requiring 18,000 AVAX, and 14 days requiring 2,000 AVAX). Operators exploit boundary gaps through timing games.
5. **Continuous Bounded Harmonic Decay (Selected Optimal Design):** The kernel $\frac{1}{d} - \frac{1}{365}$ matches the linear turnover frequency of consensus churn. It satisfies all boundary conditions exactly, aligns the 12-week pivot at 2,000 AVAX, maintains exponent stability ($p \in [0.615, 0.631]$), and provides smooth, monotonic convexity across the entire duration spectrum.

## Specification

### Mathematical Formulation

The admission frontier is defined on the closed domain $d \in [d_{\min}, d_{\max}]$ by the continuous bounded harmonic decay function:

$$S_{\min}(d) = S_{\text{floor}} + (S_{\text{short}} - S_{\text{floor}}) \cdot \left[ \frac{\frac{1}{d} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}} \right]^p$$

where:
- $d_{\min} = 2\text{ days}$ (the 48-hour floor specified in ACP-273).
- $d_{\max} = 365\text{ days}$ (the annual staking limit).
- $S_{\text{floor}} = 500\text{ AVAX}$ (the ACP-49 barrier) or $600\text{ AVAX}$ (the balanced barrier).
- $S_{\text{short}} = 18{,}000\text{ AVAX}$ (the short-term anchor bond).
- $d_{\text{target}} = 84\text{ days}$ (the 12-week intermediate calibration pivot).
- $S(d_{\text{target}}) = 2{,}000\text{ AVAX}$ (the legacy Mainnet stake threshold).

The curvature exponent $p$ is derived analytically from the pivot condition:

$$p = \frac{\ln\left(\frac{2{,}000 - S_{\text{floor}}}{S_{\text{short}} - S_{\text{floor}}}\right)}{\ln\left(\frac{\frac{1}{d_{\text{target}}} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}}\right)}$$

For $S_{\text{floor}} = 500\text{ AVAX}$ (Package B), evaluating this quotient yields:

$$p = \frac{\ln(1{,}500 / 17{,}500)}{\ln(0.009165 / 0.497260)} = \frac{-2.4567}{-3.9937} = 0.6151 \approx 0.615$$

For $S_{\text{floor}} = 600\text{ AVAX}$ (Package B-600), the quotient yields:

$$p = \frac{\ln(1{,}400 / 17{,}400)}{\ln(0.009165 / 0.497260)} = \frac{-2.5200}{-3.9937} = 0.6310 \approx 0.631$$

For $S_{\text{short}} = 14{,}000\text{ AVAX}$ with an 8-week pivot ($d_{\text{target}} = 56\text{d}$) under $S_{\text{floor}} = 500\text{ AVAX}$ (Package A), the quotient yields:

$$p = \frac{\ln(1{,}500 / 13{,}500)}{\ln(0.015117 / 0.497260)} = \frac{-2.1972}{-3.4932} = 0.6290 \approx 0.629$$

### Governance Parameter Packages

This specification presents three calibrated governance packages:

```
┌────────────────────────────────────────────────────────────────────────┐
│                     GOVERNANCE PARAMETER PACKAGES                      │
├──────────────────────────┬──────────────┬──────────────┬───────────────┤
│ Parameter                │ Package A    │ Package B    │ Package B-600 │
│                          │ Conservative │ Recommended  │ Balanced 600  │
├──────────────────────────┼──────────────┼──────────────┼───────────────┤
│ Short-End Anchor S_short │ 14,000 AVAX  │ 18,000 AVAX  │ 18,000 AVAX   │
│ Terminal Floor S_floor   │ 500 AVAX     │ 500 AVAX     │ 600 AVAX      │
│ Pivot Horizon d_target   │ 56 Days (8w) │ 84 Days (12w)│ 84 Days (12w) │
│ Stake at Pivot           │ 2,000 AVAX   │ 2,000 AVAX   │ 2,000 AVAX    │
│ Curvature Exponent p     │ 0.629        │ 0.615        │ 0.631         │
│ Capital-Time at 48h      │ 28,000 d*AVAX│ 36,000 d*AVAX│ 36,000 d*AVAX │
│ Sybil Ratio at 48h       │ 1.000x       │ 1.286x       │ 1.286x        │
│ Stake at 14 Days         │ 4,390 AVAX   │ 5,678 AVAX   │ 5,590 AVAX    │
│ Capital-Time at 365 Days │ 182,500 d*AV │ 182,500 d*AV │ 219,000 d*AV  │
│ Sybil Ratio at 365 Days  │ 6.518x       │ 6.518x       │ 7.821x        │
└──────────────────────────┴──────────────┴──────────────┴───────────────┘
```

Package B is recommended for protocol deployment. Package B-600 provides an immediate alternative if governance chooses to maintain a higher annual floor to account for validator hosting costs.

### PlatformVM Consensus Quantization

Floating-point evaluations inside consensus critical paths introduce cross-platform verification divergences due to differences in CPU floating-point units, rounding modes, and compiler optimizations.

To preserve deterministic execution across all Avalanche Network Clients, the continuous curve is quantized into eight discrete integer brackets evaluated in nanoseconds and `nAVAX` ($1\text{ AVAX} = 10^9\text{ nAVAX}$):

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   QUANTIZED PLATFORMVM SCHEDULE (PACKAGE B - RECOMMENDED)              │
├───────┬──────────────────────┬─────────────┬─────────────────┬────────────────┬────────┤
│ Index │ Duration Range (d)   │ Stake (AVAX)│ Stake (nAVAX)   │ Capital-Time   │ Ratio  │
├───────┼──────────────────────┼─────────────┼─────────────────┼────────────────┼────────┤
│ 1     │ 2d <= d < 7d         │ 18,000 AVAX │ 18,000 * 10^9   │ 36.0k - <126.0k│ 1.29x+ │
│ 2     │ 7d <= d < 14d        │ 8,500 AVAX  │ 8,500 * 10^9    │ 59.5k - <119.0k│ 2.13x+ │
│ 3     │ 14d <= d < 30d       │ 5,678 AVAX  │ 5,678 * 10^9    │ 79.5k - <170.3k│ 2.84x+ │
│ 4     │ 30d <= d < 60d       │ 3,680 AVAX  │ 3,680 * 10^9    │ 110.4k - <220.8│ 3.94x+ │
│ 5     │ 60d <= d < 84d       │ 2,520 AVAX  │ 2,520 * 10^9    │ 151.2k - <211.7│ 5.40x+ │
│ 6     │ 84d <= d < 180d      │ 2,000 AVAX  │ 2,000 * 10^9    │ 168.0k - <360.0│ 6.00x+ │
│ 7     │ 180d <= d < 365d     │ 1,120 AVAX  │ 1,120 * 10^9    │ 201.6k - <408.8│ 7.20x+ │
│ 8     │ d >= 365d (Floor 500)│ 500 AVAX    │ 500 * 10^9      │ 182.5k+        │ 6.52x+ │
└───────┴──────────────────────┴─────────────┴─────────────────┴────────────────┴────────┘
```

For governance transparency, the quantized schedule under Package B-600 evaluates as:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   QUANTIZED PLATFORMVM SCHEDULE (PACKAGE B-600 - BALANCED)             │
├───────┬──────────────────────┬─────────────┬─────────────────┬────────────────┬────────┤
│ Index │ Duration Range (d)   │ Stake (AVAX)│ Stake (nAVAX)   │ Capital-Time   │ Ratio  │
├───────┼──────────────────────┼─────────────┼─────────────────┼────────────────┼────────┤
│ 1     │ 2d <= d < 7d         │ 18,000 AVAX │ 18,000 * 10^9   │ 36.0k - <126.0k│ 1.29x+ │
│ 2     │ 7d <= d < 14d        │ 8,420 AVAX  │ 8,420 * 10^9    │ 58.9k - <117.9k│ 2.10x+ │
│ 3     │ 14d <= d < 30d       │ 5,590 AVAX  │ 5,590 * 10^9    │ 78.3k - <167.7k│ 2.80x+ │
│ 4     │ 30d <= d < 60d       │ 3,600 AVAX  │ 3,600 * 10^9    │ 108.0k - <216.0│ 3.86x+ │
│ 5     │ 60d <= d < 84d       │ 2,420 AVAX  │ 2,420 * 10^9    │ 145.2k - <203.3│ 5.19x+ │
│ 6     │ 84d <= d < 180d      │ 2,000 AVAX  │ 2,000 * 10^9    │ 168.0k - <360.0│ 6.00x+ │
│ 7     │ 180d <= d < 365d     │ 1,260 AVAX  │ 1,260 * 10^9    │ 226.8k - <459.9│ 8.10x+ │
│ 8     │ d >= 365d (Floor 600)│ 600 AVAX    │ 600 * 10^9      │ 219.0k+        │ 7.82x+ │
└───────┴──────────────────────┴─────────────┴─────────────────┴────────────────┴────────┘
```

### Implementation Details and State Transition Rules

The admission check executes within `vms/platformvm/txs/builder.go` and `vms/platformvm/txs/validator.go` during the verification of `AddPermissionlessValidatorTx`.

1. **Duration Calculation:**

```
duration = tx.EndTime - tx.StartTime
```

2. **Syntactic Admission Check:**

```
if tx.Weight < GetMinimumValidatorStake(duration) {
    return ErrInsufficientValidatorStake
}
```

3. **Preservation of the Delegator Firewall:**
PlatformVM enforces two independent invariants on delegation transactions (`AddPermissionlessDelegatorTx`):

$$d_{\text{delegator}} \ge 14\text{ days}$$
$$d_{\text{delegator}} \le d_{\text{validator}}$$

Validators registering under Brackets 1 and 2 ($2\text{ days} \le d < 14\text{ days}$) cannot receive delegations. These nodes operate strictly as self-bonded consensus units. This isolates the retail delegation market from short-duration validator churn.

## Backwards Compatibility

This proposal introduces a state transition change requiring an orchestrated network upgrade.

1. **Uninterrupted Staking Stints:** Staking positions registered prior to the activation epoch execute under the rules active at their creation time. Active validators complete their terms without modification.
2. **Deterministic Activation Epoch:** Upon reaching the activation timestamp, the PlatformVM validates all newly submitted `AddPermissionlessValidatorTx` transactions against `GetMinimumValidatorStake`. Transactions providing weight below the bracket threshold fail syntactic validation and are dropped from mempool propagation.
3. **Wire Format Invariance:** P-Chain transaction serialization formats, cryptographic signatures, and codec structures remain identical.

## Reference Implementation

The following Go implementation provides the complete, deterministic admission verification function for inclusion in `vms/platformvm`:

### Consensus Verification Logic (`vms/platformvm/admission.go`)

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
	// MinValidatorStakeDuration defines the 48-hour floor under ACP-273
	MinValidatorStakeDuration = 48 * time.Hour

	// MaxValidatorStakeDuration defines the 365-day maximum lockup horizon
	MaxValidatorStakeDuration = 365 * 24 * time.Hour

	// NanoAvaxPerAvax defines the denomination scalar for P-Chain transactions
	NanoAvaxPerAvax = 1_000_000_000
)

// DurationBracket defines a duration threshold and its corresponding minimum self-stake.
type DurationBracket struct {
	ThresholdDuration time.Duration
	MinimumWeight     uint64 // in nAVAX
}

// AdmissionFrontierSchedule implements Package B quantized integer brackets (Recommended: 500 AVAX floor).
// Ordered descending by duration to support single-pass threshold evaluation.
var AdmissionFrontierSchedule = []DurationBracket{
	{ThresholdDuration: 365 * 24 * time.Hour, MinimumWeight: 500 * NanoAvaxPerAvax},
	{ThresholdDuration: 180 * 24 * time.Hour, MinimumWeight: 1120 * NanoAvaxPerAvax},
	{ThresholdDuration: 84 * 24 * time.Hour,  MinimumWeight: 2000 * NanoAvaxPerAvax},
	{ThresholdDuration: 60 * 24 * time.Hour,  MinimumWeight: 2520 * NanoAvaxPerAvax},
	{ThresholdDuration: 30 * 24 * time.Hour,  MinimumWeight: 3680 * NanoAvaxPerAvax},
	{ThresholdDuration: 14 * 24 * time.Hour,  MinimumWeight: 5678 * NanoAvaxPerAvax},
	{ThresholdDuration: 7 * 24 * time.Hour,   MinimumWeight: 8500 * NanoAvaxPerAvax},
	{ThresholdDuration: 48 * time.Hour,       MinimumWeight: 18000 * NanoAvaxPerAvax},
}

// AdmissionFrontierScheduleB600 implements Package B-600 quantized integer brackets (Balanced: 600 AVAX floor).
var AdmissionFrontierScheduleB600 = []DurationBracket{
	{ThresholdDuration: 365 * 24 * time.Hour, MinimumWeight: 600 * NanoAvaxPerAvax},
	{ThresholdDuration: 180 * 24 * time.Hour, MinimumWeight: 1260 * NanoAvaxPerAvax},
	{ThresholdDuration: 84 * 24 * time.Hour,  MinimumWeight: 2000 * NanoAvaxPerAvax},
	{ThresholdDuration: 60 * 24 * time.Hour,  MinimumWeight: 2420 * NanoAvaxPerAvax},
	{ThresholdDuration: 30 * 24 * time.Hour,  MinimumWeight: 3600 * NanoAvaxPerAvax},
	{ThresholdDuration: 14 * 24 * time.Hour,  MinimumWeight: 5590 * NanoAvaxPerAvax},
	{ThresholdDuration: 7 * 24 * time.Hour,   MinimumWeight: 8420 * NanoAvaxPerAvax},
	{ThresholdDuration: 48 * time.Hour,       MinimumWeight: 18000 * NanoAvaxPerAvax},
}

// GetMinimumValidatorStake returns the required minimum self-stake under the default Package B schedule.
func GetMinimumValidatorStake(duration time.Duration) (uint64, error) {
	return GetMinimumValidatorStakeWithSchedule(duration, AdmissionFrontierSchedule)
}

// GetMinimumValidatorStakeWithSchedule returns the required minimum self-stake under a specified schedule.
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

// VerifyValidatorAdmission validates that an incoming validator transaction meets the frontier under Package B.
func VerifyValidatorAdmission(startTime, endTime time.Time, bondedWeight uint64) error {
	return VerifyValidatorAdmissionWithSchedule(startTime, endTime, bondedWeight, AdmissionFrontierSchedule)
}

// VerifyValidatorAdmissionWithSchedule validates admission against an explicit schedule.
func VerifyValidatorAdmissionWithSchedule(startTime, endTime time.Time, bondedWeight uint64, schedule []DurationBracket) error {
	if endTime.Before(startTime) || endTime.Equal(startTime) {
		return ErrStakeDurationTooShort
	}

	duration := endTime.Sub(startTime)
	requiredWeight, err := GetMinimumValidatorStakeWithSchedule(duration, schedule)
	if err != nil {
		return err
	}

	if bondedWeight < requiredWeight {
		return ErrInsufficientValidatorStake
	}

	return nil
}
```

### Reference Test Suite (`vms/platformvm/admission_test.go`)

```go
package platformvm

import (
	"testing"
	"time"
)

func TestGetMinimumValidatorStake(t *testing.T) {
	tests := []struct {
		name        string
		duration    time.Duration
		expected    uint64
		expectError error
	}{
		{"Below 48 Hours - 47h", 47 * time.Hour, 0, ErrStakeDurationTooShort},
		{"Sub-second boundary below 48h", 48*time.Hour - time.Nanosecond, 0, ErrStakeDurationTooShort},
		{"Exact 48 Hours", 48 * time.Hour, 18000 * NanoAvaxPerAvax, nil},
		{"Sub-second boundary above 48h", 48*time.Hour + time.Nanosecond, 18000 * NanoAvaxPerAvax, nil},
		{"Intra-Bracket 5 Days", 5 * 24 * time.Hour, 18000 * NanoAvaxPerAvax, nil},
		{"Sub-second boundary below 7d", 7*24*time.Hour - time.Nanosecond, 18000 * NanoAvaxPerAvax, nil},
		{"Exact 7 Days", 7 * 24 * time.Hour, 8500 * NanoAvaxPerAvax, nil},
		{"Exact 14 Days", 14 * 24 * time.Hour, 5678 * NanoAvaxPerAvax, nil},
		{"Exact 30 Days", 30 * 24 * time.Hour, 3680 * NanoAvaxPerAvax, nil},
		{"Exact 60 Days", 60 * 24 * time.Hour, 2520 * NanoAvaxPerAvax, nil},
		{"Exact 84 Days", 84 * 24 * time.Hour, 2000 * NanoAvaxPerAvax, nil},
		{"Exact 180 Days", 180 * 24 * time.Hour, 1120 * NanoAvaxPerAvax, nil},
		{"Exact 365 Days", 365 * 24 * time.Hour, 500 * NanoAvaxPerAvax, nil},
		{"Sub-second boundary above 365d", 365*24*time.Hour + time.Nanosecond, 0, ErrStakeDurationTooLong},
		{"Exceeds 365 Days - 366d", 366 * 24 * time.Hour, 0, ErrStakeDurationTooLong},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			stake, err := GetMinimumValidatorStake(tt.duration)
			if err != tt.expectError {
				t.Fatalf("expected error %v, got %v", tt.expectError, err)
			}
			if stake != tt.expected {
				t.Fatalf("expected stake %d, got %d", tt.expected, stake)
			}
		})
	}
}

func TestGetMinimumValidatorStakeB600(t *testing.T) {
	tests := []struct {
		name        string
		duration    time.Duration
		expected    uint64
		expectError error
	}{
		{"B600 Below 48 Hours", 47 * time.Hour, 0, ErrStakeDurationTooShort},
		{"B600 Exact 48 Hours", 48 * time.Hour, 18000 * NanoAvaxPerAvax, nil},
		{"B600 Exact 7 Days", 7 * 24 * time.Hour, 8420 * NanoAvaxPerAvax, nil},
		{"B600 Exact 14 Days", 14 * 24 * time.Hour, 5590 * NanoAvaxPerAvax, nil},
		{"B600 Exact 30 Days", 30 * 24 * time.Hour, 3600 * NanoAvaxPerAvax, nil},
		{"B600 Exact 60 Days", 60 * 24 * time.Hour, 2420 * NanoAvaxPerAvax, nil},
		{"B600 Exact 84 Days", 84 * 24 * time.Hour, 2000 * NanoAvaxPerAvax, nil},
		{"B600 Exact 180 Days", 180 * 24 * time.Hour, 1260 * NanoAvaxPerAvax, nil},
		{"B600 Exact 365 Days", 365 * 24 * time.Hour, 600 * NanoAvaxPerAvax, nil},
		{"B600 Exceeds 365 Days", 366 * 24 * time.Hour, 0, ErrStakeDurationTooLong},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			stake, err := GetMinimumValidatorStakeWithSchedule(tt.duration, AdmissionFrontierScheduleB600)
			if err != tt.expectError {
				t.Fatalf("expected error %v, got %v", tt.expectError, err)
			}
			if stake != tt.expected {
				t.Fatalf("expected stake %d, got %d", tt.expected, stake)
			}
		})
	}
}

func TestVerifyValidatorAdmission(t *testing.T) {
	now := time.Now()

	// Valid 48h stint with exact weight
	err := VerifyValidatorAdmission(now, now.Add(48*time.Hour), 18000*NanoAvaxPerAvax)
	if err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}

	// Valid 48h stint with excess weight
	err = VerifyValidatorAdmission(now, now.Add(48*time.Hour), 20000*NanoAvaxPerAvax)
	if err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}

	// Insufficient weight for 48h stint
	err = VerifyValidatorAdmission(now, now.Add(48*time.Hour), 17999*NanoAvaxPerAvax)
	if err != ErrInsufficientValidatorStake {
		t.Fatalf("expected ErrInsufficientValidatorStake, got %v", err)
	}

	// Duration too short (reversed timestamps)
	err = VerifyValidatorAdmission(now.Add(48*time.Hour), now, 18000*NanoAvaxPerAvax)
	if err != ErrStakeDurationTooShort {
		t.Fatalf("expected ErrStakeDurationTooShort, got %v", err)
	}

	// Empty schedule error check
	_, err = GetMinimumValidatorStakeWithSchedule(48*time.Hour, nil)
	if err != ErrNilOrEmptySchedule {
		t.Fatalf("expected ErrNilOrEmptySchedule, got %v", err)
	}
}
```

## Security Considerations

### Empirical Sybil Resistance Analysis

Sybil resistance is evaluated through cumulative capital-time:

$$K(d) = S_{\min}(d) \cdot d$$

The historical Mainnet baseline provides $K_{\text{baseline}} = 28{,}000\text{ AVAX-days}$.

Package B and Package B-600 guarantee that the capital-time commitment exceeds this baseline across every allowable duration:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   CAPITAL-TIME SYBIL PARITY AUDIT                      │
├─────────────┬─────────────────┬───────────────────┬────────────────────┤
│ Duration    │ Stake S_min(d)  │ Capital-Time K(d) │ Parity Ratio       │
├─────────────┼─────────────────┼───────────────────┼────────────────────┤
│ 48 Hours    │ 18,000 AVAX     │ 36,000 AVAX-days  │ 1.286x (Surplus)   │
│ 7 Days      │ 8,500 AVAX      │ 59,500 AVAX-days  │ 2.125x (Surplus)   │
│ 14 Days     │ 5,678 AVAX      │ 79,492 AVAX-days  │ 2.839x (Surplus)   │
│ 30 Days     │ 3,680 AVAX      │ 110,400 AVAX-days │ 3.943x (Surplus)   │
│ 60 Days     │ 2,520 AVAX      │ 151,200 AVAX-days │ 5.400x (Surplus)   │
│ 84 Days     │ 2,000 AVAX      │ 168,000 AVAX-days │ 6.000x (Surplus)   │
│ 180 Days    │ 1,120 AVAX      │ 201,600 AVAX-days │ 7.200x (Surplus)   │
│ 365 Days    │ 500 AVAX        │ 182,500 AVAX-days │ 6.518x (Surplus)   │
│ 365d (B-600)│ 600 AVAX        │ 219,000 AVAX-days │ 7.821x (Surplus)   │
└─────────────┴─────────────────┴───────────────────┴────────────────────┘
```

The protocol achieves strict Sybil security dominance: at no point along the frontier can an adversary acquire a validator consensus slot for less than the historical $28{,}000\text{ AVAX-days}$ requirement.

### Consensus Sampling and Validator Stability

ACP-273 identified the risk that 48-hour staking could induce validator churn, destabilizing Snowman consensus sampling. The 18,000 AVAX threshold mitigates this hazard by pricing micro-capital entities out of short-duration slots.

Entities staking 18,000 AVAX for 48 hours represent high-value institutional allocators, market makers, or ETF custodians with formal treasury liquidity requirements. Small-balance retail validators are economically guided toward 12-week and 1-year lockups where capital barriers fall to 2,000 AVAX and 500 AVAX. This increases the stake-weighted mean duration of the network.

### Mitigation of P-Chain State Growth

Staking transactions write BLS keys, network addresses, and staking intervals to the P-Chain database. Accelerated staking turnover increases state storage requirements.

The admission frontier suppresses state growth through two architectural constraints:
1. **High Entry Cost on Short Tenors:** The 18,000 AVAX requirement restrains transaction volume in the 48-hour to 7-day range.
2. **Delegator Firewall Isolation:** Delegators generate 99% of staking transactions on the Primary Network (100:1 ratio to validator transactions). By enforcing $d_{\text{delegator}} \ge 14\text{ days}$, 48-hour validators cannot host delegations, shielding the P-Chain from high-frequency delegation churn.

### Security Boundary and Scale-Invariance Defense

Adversarial analysis confirms the necessity of Tinbergen instrument separation:

1. **Failure Mode of Single-Instrument Steering:** Attempting to force whale duration extension via the admission barrier introduces severe centralization risk. Institutional entities commanding 181,000 to 1,000,000+ AVAX easily satisfy an 18,000 AVAX barrier at 48 hours. Elevating the 48-hour requirement to 50,000 or 100,000 AVAX would price out independent sovereign operators and leave institutional whales unconstrained. This would concentrate consensus power in a shrinking set of large custodians.
2. **Decoupled Emission Security:** Macro stake-weighted duration is driven by whale capital allocation, representing over 99% of network consensus weight. Institutional capital responds directly to annualized yield differentials ($\text{ARR}(365\text{d}) - \text{ARR}(2\text{d})$). Admission thresholds exert zero economic pull on large balances. Decoupling the entry defense mechanism ($S_{\min}(d)$) from the macroeconomic emission curve (governed by ACP-285) guarantees robust defense against Sybil fragmentation without distorting token supply dynamics or consensus stability.
3. **Liquidity Shock Resilience:** During severe macroeconomic market drawdowns, rational validators seeking liquidity cannot cycle into transient consensus slots at negligible cost. Enforcing the 18,000 AVAX anchor bond guarantees that liquid capital pays a substantial security premium, maintaining aggregate network commitment.

## Open Questions

1. **Auto-Renewed Staking Integration (ACP-236):**
   Evaluation of whether each renewal cycle validates against the admission frontier based on its discrete scheduled duration or inherits the initial registration parameters. The recommended specification evaluates each renewal cycle independently.
2. **Terminal Floor Selection (500 AVAX vs 600 AVAX):**
   Governance evaluation of Package B ($S_{\text{floor}} = 500\text{ AVAX}$) versus Package B-600 ($S_{\text{floor}} = 600\text{ AVAX}$). At 500 AVAX, annual hardware hosting costs ($40/month VPS drag) require small nodes to maintain higher uptime to achieve positive economic return. Setting the floor at 600 AVAX increases net validator margin and delivers a 70% capital reduction relative to legacy rules.
3. **Dynamic P-Chain Base Fee Coordination (ACP-103):**
   ACP-103 proposes dynamic multidimensional fees for P-Chain operations. Coordinating the base fee for `AddPermissionlessValidatorTx` with the 18,000 AVAX admission barrier will provide defense against transaction spam during network volatility.

## Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
