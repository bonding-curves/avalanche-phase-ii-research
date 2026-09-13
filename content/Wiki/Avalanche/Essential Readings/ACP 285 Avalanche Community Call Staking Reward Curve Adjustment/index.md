---
title: "ACP 285 - Avalanche Community Call - Staking Reward Curve Adjustment"
description: "A timestamped reading view of the ACP-285 presentation and community discussion."
source_id: "lit:acp-285-community-call"
source_type: video
date: 2026-07-07
event_date: 2026-06-29
published_date: 2026-07-07
duration: "1:13:03"
canonical_url: "https://www.youtube.com/watch?v=sx4-AW7HcSU"
status: source-indexed
review_status: "timestamped analytical summary; automatic captions not verified as verbatim"
---

# ACP 285 - Avalanche Community Call - Staking Reward Curve Adjustment

**Video** · Avalanche · Held June 29, 2026 · Published July 7, 2026 · [Watch the recording](https://www.youtube.com/watch?v=sx4-AW7HcSU)

This community call presents ACP-285, relates it to ACP-236 and ACP-273, and records questions about validator behavior, concentration, liquidity, issuance, security funding, and future value-capture mechanisms. The page is a timestamped analytical reading view, not a verbatim transcript.

## Presentation

### [Introduction and agenda](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=0s)

The host introduces ACP-285 as a change to the minimum consumption rate in the Primary Network staking reward formula. Eric Lu then outlines a presentation followed by open discussion.

### [Motivation and related ACPs](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=43s)

Eric organizes the motivation around three observations. Avalanche's realized inflation rate remains material even though it declines as the remaining supply falls. The reward difference between short and long commitments has narrowed over time. ACP-236 and ACP-273 reduce operational renewal costs and the minimum commitment period, which changes the relative attractiveness of short-duration staking.

The economic question is not only whether shorter positions receive fewer total rewards. Shorter commitments preserve liquidity and the option to change position. The proposal therefore concerns the reward required to compensate for that foregone flexibility.

### [Three intended goals](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=555s)

The proposal is presented as serving three goals: reduce net AVAX inflation, conserve the finite issuance-funded security budget, and restore a stronger relative reward for longer staking commitments. These are intended outcomes rather than guarantees. Realized effects depend on the staking choices made after the parameter change.

### [Reward formula](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=780s)

The reward curve combines a remaining-supply factor with a linear interpolation between minimum and maximum consumption rates over staking duration. Lowering the minimum parameter changes the short-duration end of the curve while leaving the maximum-duration endpoint unchanged. The raw parameter change is larger than the change in realized annualized reward because the remaining-supply factor is below one.

### [Inflation and supply paths](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=925s)

The presentation first isolates the mechanical effect by comparing reward and inflation paths under alternative minimum-rate settings. It then distinguishes that calculation from a counterfactual in which validators and delegators may change their choices. Lower issuance also slows the use of the remaining security budget and the rate at which newly minted AVAX enters supply.

### [Duration premium](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=1170s)

Historical curves show both a declining reward level and a flattening difference between short and long commitments. ACP-285 is intended to widen that difference. The relevant behavioral question is whether the larger spread is enough to move participants whose liquidity preferences currently dominate the duration premium.

### [Structural model](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=1320s)

Eric describes a structural model of validator and delegator preferences estimated from historical choices. The model supplies counterfactual changes in staking duration and inflation under the proposed parameter setting. These outputs depend on the model specification, estimation data, behavioral stability, and extrapolation beyond historically observed conditions.

### [Ninety-day ramp](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=1415s)

The proposed implementation changes the minimum consumption rate gradually over ninety days. A ramp avoids giving two otherwise similar staking positions substantially different locked-in rates solely because they begin immediately before or after one activation instant. It also gives dependent applications time to adjust.

## Discussion

### [Validator count and economic security](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=1585s)

The first questions ask whether lower short-duration rewards could cause validators to leave. Participants distinguish validator count from stake-weighted economic security. An exit by a large validator changes secured stake more than many very small exits, while shorter entry periods may also reduce barriers for new operators.

### [Concentration and duration clustering](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=1920s)

The discussion examines whether stronger duration incentives could concentrate delegated stake among long-running validators. Eric notes that observed choices cluster around common durations and expects a shift at the margin rather than a single uniform outcome. This remains a hypothesis to test against later on-chain behavior.

### [Delegation economics](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=2220s)

Participants raise delegation capacity and fee income as possible offsets to validator economics. The ACP authors explain that delegation changes were intentionally separated from ACP-285 so the duration incentive remains easier to understand. This boundary is analytically important because validator choices respond to expected delegation fee income.

### [Small-validator experience and model limits](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=2440s)

Community members describe real operating decisions, including moving from validation to delegation. The responses emphasize that ACP-285 directly varies rewards by duration rather than stake size. Participants also acknowledge that theoretical and structural models may omit operational constraints and individual circumstances.

### [Security funding and value accrual](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=2830s)

The conversation broadens from one parameter to the long-run problem of paying for network security. Participants discuss the eventual transition from issuance-funded security toward economic value captured from network activity, including unresolved questions about who receives that value and how it reaches validators or AVAX holders.

### [Supply-side and demand-side research](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=3150s)

The group characterizes reward and fee parameter changes as relatively tractable supply-side interventions. Demand for blockspace, sensitivity to transaction fees, and the value created by applications and L1s require additional data and modeling. The stated direction is to connect both sides rather than treat issuance changes as a complete token-economic strategy.

### [Original formula intent](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=3570s)

The call revisits why the existing formula rewards longer commitments. Avalanche requires a staking period to be chosen in advance, so duration is a direct configuration choice. Auto-renewal changes the operational cost of repeatedly choosing short periods and therefore changes the mechanism's effective incentives.

### [Future mechanism questions](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=3840s)

Participants consider dynamic fees, auctions, and other mechanisms that could connect future cash flows or blockspace demand to network value. These ideas are explicitly exploratory. They require empirical demand estimates, implementation analysis, and clear distribution rules before becoming proposals.

### [L1 economics and conclusion](https://www.youtube.com/watch?v=sx4-AW7HcSU&t=4200s)

The final exchange considers how high-value Avalanche L1s might contribute to network economics and security. Validation of the Primary Network, interoperability activity, and other forms of contribution remain possible mechanisms rather than settled requirements.

## Primary materials

- [ACP-285: Reduce Minimum Consumption Rate](https://github.com/avalanche-foundation/ACPs/tree/main/ACPs/285-reduce-minimum-consumption-rate)
- [ACP-236: Auto-Renewed Staking](https://github.com/avalanche-foundation/ACPs/tree/main/ACPs/236-auto-renewed-staking)
- [ACP-273: Reduce Minimum Validator Staking Duration](https://github.com/avalanche-foundation/ACPs/tree/main/ACPs/273-reduce-minimum-staking-duration)

## Evidence limits

- This page summarizes the recording and does not reproduce a complete transcript.
- The automatic captions were used to locate sections but were not verified word-for-word against the audio.
- The section boundaries are analytical navigation aids, not chapters supplied by the publisher.
- Protocol definitions and status are governed by the versioned ACP files.
- Quantitative projections remain attributed model outputs until independently reproduced.
