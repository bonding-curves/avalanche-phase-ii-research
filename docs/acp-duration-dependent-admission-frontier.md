| ACP | Draft |
| :--- | :--- |
| **Title** | Duration-Dependent Minimum Validator Stake Frontier |
| **Author(s)** | BCRG Systems Engineering Team, Cryptoeconomics Research Group |
| **Status** | Proposed |
| **Track** | Standards |

## Abstract

This proposal establishes a duration-dependent admission frontier, $S_{\min}(d)$, for the Avalanche Primary Network. Currently, the minimum validator self-stake is fixed at a static threshold of 2,000 AVAX across all durations between 14 days and 365 days. Independent proposals have sought to lower the minimum stake to 500 AVAX (ACP-49) and shorten the minimum staking duration from 14 days to 48 hours (ACP-273). If implemented independently as static thresholds, these changes permit a 48-hour validator stake of 500 AVAX, reducing the capital-time Sybil commitment from the historical 28,000 AVAX-days to 1,000 AVAX-days, representing a 96.43% reduction in economic security. 

This proposal resolves that structural vulnerability by coupling minimum stake to commitment duration through a bounded harmonic decay function. Stakers committing capital for the maximum 365-day term access the 500 AVAX threshold established in ACP-49. Stakers utilizing the 48-hour term introduced in ACP-273 provide a 18,000 AVAX anchor bond, preserving a 36,000 AVAX-days Sybil commitment that exceeds the historical Mainnet baseline. The continuous curve is quantized into discrete integer brackets within `vms/platformvm` to eliminate floating-point non-determinism during consensus validation.

## Motivation

### Current State

The Avalanche Primary Network currently enforces a flat minimum validator self-stake requirement:

```
S_min = 2,000 AVAX for all d in [14 days, 365 days]
```

This static threshold creates two structural inefficiencies:

1. **Capital Exclusion for Long-Term Operators:** Decentralized home validators and community stakers willing to lock capital for an entire year must aggregate 2,000 AVAX. This capital requirement creates a high barrier to entry that restricts validator set growth.
2. **Disproportionate Sybil Vulnerability for Short-Term Stakers:** The 14-day minimum duration locks stakers into a minimum capital-time commitment of:

$$K_{\text{baseline}} = 2{,}000\text{ AVAX} \times 14\text{ days} = 28{,}000\text{ AVAX-days}$$

### The Decoupled Sybil Vulnerability

Two recent proposals address these frictions independently:
- **ACP-49:** Reduces the minimum validator stake from 2,000 AVAX to 500 AVAX.
- **ACP-273:** Reduces the minimum validator staking duration from 14 days to 2 days (48 hours).

Evaluating these proposals independently exposes a compounding vulnerability. If ACP-49 and ACP-273 activate concurrently as orthogonal static parameters, an entity can register a consensus validator with:

$$K_{\text{decoupled}} = 500\text{ AVAX} \times 2\text{ days} = 1{,}000\text{ AVAX-days}$$

This represents a 96.43% collapse in the economic weight required to occupy a Primary Network consensus slot. An adversary with 28,000 AVAX could operate 28 concurrent short-term validators compared to a single 14-day validator, magnifying consensus sampling churn, peer-to-peer gossip load, and stake-table volatility.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   THE DECOUPLED SYBIL COLLAPSE                         │
├──────────────────────────┬──────────────────────┬──────────────────────┤
│ Metric                   │ Mainnet Baseline     │ Decoupled ACP-49/273 │
├──────────────────────────┼──────────────────────┼──────────────────────┤
│ Minimum Self-Stake       │ 2,000 AVAX           │ 500 AVAX             │
│ Minimum Duration         │ 14 Days              │ 2 Days               │
│ Capital-Time Commitment  │ 28,000 AVAX-days     │ 1,000 AVAX-days      │
│ Sybil Cost Relative Base │ 1.00x                │ 0.0357x (-96.43%)    │
└──────────────────────────┴──────────────────────┴──────────────────────┘
```

ACP-273 explicitly highlights this operational instability in its Security Considerations section:

> "Additionally, if the incentive to stake for longer than 48 hours is insufficient, the vast majority of stake may opt for the minimum 48-hour duration... In this scenario, essentially all entities securing the network could change completely within 48 hours. The entire validator set could disappear, or a low-stake-weight validator could become a high-stake-weight validator within a very short time frame... This instability poses a real cost in terms of network security and should be weighed against the benefits of shorter staking periods."

### Capital-Time Equivalence as a Design Principle

Security in Proof-of-Stake consensus derives from the verifiable commitment of capital over time. Capital and duration substitute for each other:
- An operator committing capital for 365 days provides durable network stability, justifying a lower entry barrier ($500\text{ AVAX}$).
- An operator retaining liquidity optionality through 48-hour stints introduces turnover and state growth, requiring a substantial capital anchor bond ($18{,}000\text{ AVAX}$).

By formalizing a duration-dependent admission frontier, $S_{\min}(d)$, the protocol achieves capital efficiency for long-term stakers while safeguarding consensus against short-term churn.

## Specification

### Mathematical Formulation

The admission frontier is defined by a continuous bounded harmonic decay function:

$$S_{\min}(d) = S_{\text{floor}} + (S_{\text{short}} - S_{\text{floor}}) \cdot \left[ \frac{\frac{1}{d} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}} \right]^p$$

where the domain is bounded by $d \in [d_{\min}, d_{\max}]$, with:
- $d_{\min} = 2\text{ days}$ (the minimum duration established in ACP-273).
- $d_{\max} = 365\text{ days}$ (the maximum protocol staking duration).
- $S_{\text{floor}} = 500\text{ AVAX}$ (the terminal stake floor established in ACP-49).
- $S_{\text{short}} = 18{,}000\text{ AVAX}$ (the short-term anchor bond at $d_{\min}$).
- $d_{\text{target}} = 84\text{ days}$ (the 12-week horizon at which $S_{\min}(d) = 2{,}000\text{ AVAX}$).

The curvature exponent $p$ is derived analytically from the pivot condition $S_{\min}(d_{\text{target}}) = 2{,}000\text{ AVAX}$:

$$p = \frac{\ln\left(\frac{2{,}000 - S_{\text{floor}}}{S_{\text{short}} - S_{\text{floor}}}\right)}{\ln\left(\frac{\frac{1}{d_{\text{target}}} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}}\right)}$$

Substituting the governance parameters yields $p \approx 0.615$ (standardized to $p = 0.65$ for parameter stability).

### Mathematical Properties and Functional Comparison

The bounded harmonic decay form fulfills three protocol requirements:
1. **Exact Boundary Satisfaction:** $S_{\min}(2\text{d}) = S_{\text{short}}$ exactly, and $S_{\min}(365\text{d}) = S_{\text{floor}}$ exactly.
2. **Strict Monotonicity:** $\frac{dS_{\min}}{dd} < 0$ across all $d \in [2, 365]$, guaranteeing that longer commitments always enjoy lower capital thresholds.
3. **Strict Convexity:** $\frac{d^2S_{\min}}{dd^2} > 0$ across all $d$, ensuring the marginal capital reduction per day of commitment decreases smoothly with duration.

Alternative functional forms demonstrate severe structural failure modes:

| Functional Form | Mathematical Definition | Failure Mode |
| :--- | :--- | :--- |
| **Pure Iso-Commitment** | $S_{\min}(d) = \max\left(500, \frac{28{,}000}{d}\right)$ | Reaches the 500 AVAX floor prematurely at 56 days. Completely flat for days 57 through 365, offering zero capital reduction for commitments beyond 8 weeks. |
| **Standard Hyperbolic** | $S_{\min}(d) = 500 + \frac{17{,}500}{1 + \alpha (d - 2)}$ | Over-penalizes medium durations. Fails to satisfy $S_{\min}(365) = 500\text{ AVAX}$ and $S_{\min}(84) = 2{,}000\text{ AVAX}$ simultaneously without residual errors ($S(365) \approx 553.6\text{ AVAX}$). |
| **Generalized Power-Law** | $S_{\min}(d) = 500 + 17{,}500 \cdot \left(\frac{365 - d}{363}\right)^p$ | Decays rapidly at short durations, leaving the critical 14-day to 30-day window under-collateralized ($S_{\min}(14\text{d}) < 1{,}000\text{ AVAX}$). |
| **Continuous Bounded Harmonic** | $S_{\min}(d) = S_{\text{floor}} + \Delta S \cdot \left[\frac{1/d - 1/365}{1/2 - 1/365}\right]^p$ | Satisfies all boundary conditions, aligns the 12-week pivot at 2,000 AVAX, and provides continuous, smooth curvature throughout the domain. |

### Governance Parameter Packages

To support protocol governance evaluation, three calibrated parameter packages are defined:

| Parameter | Package A (Conservative Parity) | Package B (Recommended Balanced) | Package C (Anti-Churn Anchor) |
| :--- | :---: | :---: | :---: |
| **Short-End Anchor ($S_{\text{short}}$)** | 14,000 AVAX | **18,000 AVAX** | 25,000 AVAX |
| **Terminal Floor ($S_{\text{floor}}$)** | 500 AVAX | **500 AVAX** | 500 AVAX |
| **Pivot Duration ($d_{\text{target}}$)** | 56 Days (8 Weeks) | **84 Days (12 Weeks)** | 112 Days (16 Weeks) |
| **Pivot Stake ($S(d_{\text{target}})$)** | 2,000 AVAX | **2,000 AVAX** | 2,000 AVAX |
| **Curvature Exponent ($p$)** | 0.82 | **0.65** | 0.54 |
| **Capital-Time at 48h** | 28,000 AVAX-days | **36,000 AVAX-days** | 50,000 AVAX-days |
| **Sybil Multiplier at 48h** | 1.00x | **1.29x** | 1.79x |
| **Stake at 14 Days** | 3,920 AVAX | **5,678 AVAX** | 8,140 AVAX |

Package B is recommended. It establishes a 1.29x Sybil security margin at 48 hours ($36{,}000\text{ AVAX-days}$), preserves the 2,000 AVAX threshold at 12 weeks, positions the 14-day threshold ($5{,}678\text{ AVAX}$) directly beneath the 6,000 AVAX institutional liquid staking boundary, and delivers the 500 AVAX accessibility objective at 365 days.

### PlatformVM Consensus Quantization

Floating-point operations are non-deterministic across diverse processor architectures, compiler versions, and hardware platforms. Evaluating transcendental equations or fractional powers inside consensus validation logic compromises network safety.

Therefore, this specification quantizes the continuous Package B curve into discrete, deterministic integer brackets evaluated in nanoseconds:

| Bracket Index | Duration Range ($d$) | Minimum Stake ($S_{\min}$) | Minimum Stake in nAVAX | Capital-Time Commitment | Baseline Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | $2\text{ days} \le d < 7\text{ days}$ | 18,000 AVAX | $18{,}000 \times 10^9\text{ nAVAX}$ | 36,000 to 108,000 AVAX-days | 1.29x to 3.86x |
| 2 | $7\text{ days} \le d < 14\text{ days}$ | 8,500 AVAX | $8{,}500 \times 10^9\text{ nAVAX}$ | 59,500 to 110,500 AVAX-days | 2.13x to 3.95x |
| 3 | $14\text{ days} \le d < 30\text{ days}$ | 5,678 AVAX | $5{,}678 \times 10^9\text{ nAVAX}$ | 79,492 to 164,662 AVAX-days | 2.84x to 5.88x |
| 4 | $30\text{ days} \le d < 60\text{ days}$ | 3,680 AVAX | $3{,}680 \times 10^9\text{ nAVAX}$ | 110,400 to 217,120 AVAX-days | 3.94x to 7.75x |
| 5 | $60\text{ days} \le d < 84\text{ days}$ | 2,520 AVAX | $2{,}520 \times 10^9\text{ nAVAX}$ | 151,200 to 209,160 AVAX-days | 5.40x to 7.47x |
| 6 | $84\text{ days} \le d < 180\text{ days}$ | 2,000 AVAX | $2{,}000 \times 10^9\text{ nAVAX}$ | 168,000 to 358,000 AVAX-days | 6.00x to 12.79x |
| 7 | $180\text{ days} \le d < 365\text{ days}$ | 1,120 AVAX | $1{,}120 \times 10^9\text{ nAVAX}$ | 201,600 to 407,680 AVAX-days | 7.20x to 14.56x |
| 8 | $d \ge 365\text{ days}$ | 500 AVAX | $500 \times 10^9\text{ nAVAX}$ | 182,500+ AVAX-days | 6.52x+ |

### Implementation Details

Validation of incoming validator registration transactions (`AddPermissionlessValidatorTx`) is modified within `vms/platformvm/txs/builder.go` and `vms/platformvm/txs/validator.go`.

When verifying an incoming transaction, the PlatformVM calculates transaction duration:

```
duration = tx.EndTime - tx.StartTime
```

The node verifies that the bonded self-stake satisfies the quantized threshold:

```
tx.Weight >= GetMinimumValidatorStake(duration)
```

The delegator duration firewall remains unaltered:
- Delegator duration must satisfy $d_{\text{delegator}} \ge 14\text{ days}$.
- Delegator duration cannot exceed validator duration: $d_{\text{delegator}} \le d_{\text{validator}}$.

Consequently, validators registering for durations shorter than 14 days ($2 \le d < 14$) operate strictly as standalone, non-delegated consensus nodes.

## Reference Implementation

The following Go implementation provides the complete, deterministic admission verification function:

```go
package platformvm

import (
	"errors"
	"time"
)

var (
	ErrStakeDurationTooShort = errors.New("validator stake duration below protocol minimum")
	ErrStakeDurationTooLong  = errors.New("validator stake duration exceeds protocol maximum")
	ErrInsufficientStake     = errors.New("validator self-stake does not satisfy admission frontier")
)

const (
	// MinValidatorStakeDuration defines the 48-hour floor under ACP-273
	MinValidatorStakeDuration = 48 * time.Hour

	// MaxValidatorStakeDuration defines the 365-day maximum lockup horizon
	MaxValidatorStakeDuration = 365 * 24 * time.Hour

	// NanoAvaxPerAvax defines the denomination scalar for P-Chain transactions
	NanoAvaxPerAvax = 1_000_000_000
)

// DurationBracket defines a lower duration bound and required minimum self-stake
type DurationBracket struct {
	ThresholdDuration time.Duration
	MinimumWeight     uint64 // in nAVAX
}

// AdmissionFrontierSchedule implements Package B quantized integer brackets.
// Ordered descending by duration for optimal single-pass evaluation.
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

// GetMinimumValidatorStake returns the required minimum self-stake for a target duration.
func GetMinimumValidatorStake(duration time.Duration) (uint64, error) {
	if duration < MinValidatorStakeDuration {
		return 0, ErrStakeDurationTooShort
	}
	if duration > MaxValidatorStakeDuration {
		return 0, ErrStakeDurationTooLong
	}

	for _, bracket := range AdmissionFrontierSchedule {
		if duration >= bracket.ThresholdDuration {
			return bracket.MinimumWeight, nil
		}
	}

	return AdmissionFrontierSchedule[len(AdmissionFrontierSchedule)-1].MinimumWeight, nil
}

// VerifyValidatorAdmission validates that an incoming validator transaction meets the frontier.
func VerifyValidatorAdmission(startTime, endTime time.Time, bondedWeight uint64) error {
	duration := endTime.Sub(startTime)
	requiredWeight, err := GetMinimumValidatorStake(duration)
	if err != nil {
		return err
	}

	if bondedWeight < requiredWeight {
		return ErrInsufficientStake
	}

	return nil
}
```

## Backwards Compatibility

This specification introduces a state transition rule modifying consensus transaction validity within the PlatformVM. It requires activation through an orchestrated network upgrade.

Compatibility principles:
1. **No Retrospective Invalidation:** Staking transactions accepted before the activation epoch remain fully valid. Existing validators complete their registered stints under the rules in effect at their registration time.
2. **Deterministic Activation Epoch:** Once the activation timestamp passes, all newly submitted `AddPermissionlessValidatorTx` transactions must satisfy `VerifyValidatorAdmission`. Transactions offering insufficient self-stake for their registered duration fail syntactic validation and are rejected from the mempool.
3. **P-Chain Serialization Compatibility:** Transaction binary serialization formats remain identical. The verification logic executes purely within state-verification execution paths.

## Security Considerations

### Sybil Resistance Analysis

Sybil resistance is evaluated through the cumulative capital-time commitment:

$$K(d) = S_{\min}(d) \cdot d$$

Under historical Mainnet parameters ($S = 2{,}000\text{ AVAX}, d = 14\text{ days}$), the baseline Sybil cost is $28{,}000\text{ AVAX-days}$. 

Under Package B, the capital-time commitment expands across every duration tier:
- At 48 hours ($d = 2$): $K(2) = 18{,}000 \times 2 = 36{,}000\text{ AVAX-days}$ ($1.29\times$ baseline).
- At 14 days ($d = 14$): $K(14) = 5{,}678 \times 14 = 79{,}492\text{ AVAX-days}$ ($2.84\times$ baseline).
- At 84 days ($d = 84$): $K(84) = 2{,}000 \times 84 = 168{,}000\text{ AVAX-days}$ ($6.00\times$ baseline).
- At 365 days ($d = 365$): $K(365) = 500 \times 365 = 182{,}500\text{ AVAX-days}$ ($6.52\times$ baseline).

The network achieves strict Sybil security dominance: at no point along the frontier can an attacker reduce their capital-time commitment below the historical $28{,}000\text{ AVAX-days}$ standard.

### Validator Churn and Consensus Stability

ACP-273 identified the risk that short-duration staking could destabilize consensus if the entire validator set churned rapidly. By requiring an 18,000 AVAX self-bond for 48-hour stints, the admission frontier prevents micro-capital entities from generating high-frequency turnover. 

Only well-capitalized institutions, market makers, or funds with genuine short-term liquidity mandates will lock 18,000 AVAX for 48 hours. Retail and community nodes are economically directed toward 12-week and 1-year lockups where entry barriers fall to 2,000 AVAX and 500 AVAX, providing stability for Avalanche consensus sampling.

### PlatformVM State Growth Mitigation

Each validator registration writes cryptographic keys, BLS public keys, reward addresses, and staking intervals to the P-Chain state database. High turnover increases state growth rates.

Two mechanisms mitigate this impact:
1. **High Capital Barrier at Short Horizons:** The 18,000 AVAX threshold suppresses registration frequency for short-term stints.
2. **PlatformVM Delegator Firewall:** Because delegations must span at least 14 days and cannot outlast their host validator, 48-hour validators cannot receive delegations. This insulates the P-Chain from the high transaction volumes identified in ACP-273 Open Question 1, where delegator transactions represent 46% of P-Chain traffic.

### Economic Boundaries and Tinbergen Separation

The admission frontier is an entry barrier mechanism. Following the Tinbergen Separation Principle, one policy instrument cannot simultaneously solve multiple independent economic objectives:

```
┌─────────────────────────────────┬─────────────────────────────────┬─────────────────────────────────┐
│ Target Objective                │ Primary Policy Instrument       │ Role of Admission Frontier      │
├─────────────────────────────────┼─────────────────────────────────┼─────────────────────────────────┤
│ 1. Capital Barrier Reduction    │ Admission Frontier Floor (500)  │ Direct control via S_floor      │
│ 2. Sybil Defense at 48 Hours    │ Admission Anchor (18,000 AVAX)  │ Direct control via S_short      │
│ 3. Macro Duration Expansion     │ ACP-285 ARR(d) Curve Steepening │ Complements via 12-week pivot   │
│ 4. Supply Issuance Control      │ ACP-285 Max Consumption Rate    │ Invariant (no emission impact)  │
│ 5. P-Chain State Churn Control  │ ACP-103 Multidimensional Fees   │ Complements via high short-bond │
│ 6. Hardware Drag Compensation   │ ARR(d) Net Yield Spread         │ Directs nodes to 84-day tenure  │
└─────────────────────────────────┴─────────────────────────────────┴─────────────────────────────────┘
```

The admission frontier successfully regulates entry capital and duration. It does not alter protocol token emissions, which are governed by ACP-285, nor does it subsidize hardware operating costs directly.

## Open Questions

1. **Coordination with Auto-Renewed Staking (ACP-236):**
   When an active validator enables auto-renewal under ACP-236, does each renewal cycle re-evaluate duration against the admission frontier, or does the initial registration duration govern all renewals? The recommended rule evaluates each renewal period independently according to its scheduled duration.

2. **Governance Adjustment Interface:**
   Should the quantized duration brackets be hardcoded into client software versions, or managed dynamically via P-Chain governance transactions? Maintaining the schedule in consensus code preserves simplicity and security, while governance parameter updates can occur through standard network upgrades.

3. **Delegator Minimum Stake Adjustments:**
   Currently, delegators must supply at least 25 AVAX. As validator self-stake barriers decrease to 500 AVAX at long durations, should the delegator minimum remain at 25 AVAX, or adjust in tandem? Because the 14-day delegator firewall remains in place, retaining the 25 AVAX delegator minimum preserves retail delegation accessibility.

## Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
