---
title: "ACP-285 Minimum Consumption Rate"
description: "ACP-285 lowers the Primary Network minimum consumption rate from 10% to 7.5% over a 90-day ramp keyed to each stake's start time."
authors: ["Matias Antonio", "Eric Lu", "Martin Eckardt", "Meaghan FitzGerald"]
published: 2026-06-08
venue: "Avalanche Community Proposal"
url: "https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/285-reduce-minimum-consumption-rate/README.md"
full_text: "/Phase-II/Wiki/Collections/Economic-ACPs/ACP-285-Minimum-Consumption-Rate/Source-Proposal"
tags: ["issuance-and-rewards", "staking-duration-and-liquidity", "protocol-governance"]
key_terms: ["minimum consumption rate", "maximum consumption rate", "remaining-supply factor", "ninety-day ramp", "annualized reward rate", "minting period"]
deliverables: ["1.3", "1.4", "2.5"]
---

ACP-285 is the first change to a Primary Network reward parameter since genesis. It sets the yield a validator earns at each commitment duration, which is one of the governance parameters the staking model varies, and it is the proposal whose behavioral effect the Foundation estimated before activation. The question it raises for the research is how far validators move toward longer commitments when the reward for short commitments falls and the reward for a 365-day commitment does not.

<!-- overview-table:start -->

| | |
| --- | --- |
| **Authors** | Matias Antonio, Eric Lu, Martin Eckardt, Meaghan FitzGerald |
| **Published** | June 8, 2026 |
| **Source** | Avalanche Community Proposal, [original](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/285-reduce-minimum-consumption-rate/README.md), [full text](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-285-Minimum-Consumption-Rate/Source-Proposal) |
| **Topics** | [issuance and rewards](/tags/issuance-and-rewards), [staking duration and liquidity](/tags/staking-duration-and-liquidity), [protocol governance](/tags/protocol-governance) |
| **Key terms** | minimum consumption rate, maximum consumption rate, remaining-supply factor, ninety-day ramp, [annualized reward rate](/Phase-II/Wiki/Reference/Glossary-and-Notation), minting period |
| **Serves deliverables** | [1.3](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/), [1.4](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/), [2.5](/Phase-II/Milestones/Milestone-2/2-5-Sensitivity-Analysis/) |

<!-- overview-table:end -->

The full text of the ACP-285 proposal is replicated on the [Source Proposal](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-285-Minimum-Consumption-Rate/Source-Proposal) page.

## What it changes

The reward formula interpolates linearly between a minimum and a maximum **consumption rate** as commitment duration rises from zero to the 365-day minting period, then multiplies by the remaining-supply factor, the unminted part of the 720,000,000 AVAX supply cap divided by current supply. ACP-285 lowers the minimum rate and leaves everything else unchanged.

| Parameter | Before Helicon | After the ramp |
| --- | --- | --- |
| Minimum consumption rate | 10%, stored as 100,000 millionths | 7.5%, stored as 75,000 millionths |
| Maximum consumption rate | 12% | 12%, unchanged |
| Minting period | 365 days | 365 days, unchanged |
| Supply cap | 720,000,000 AVAX | 720,000,000 AVAX, unchanged |

The new minimum is reached through a linear ramp. A stake's rate is fixed once, from its start time, and holds for its whole duration. Stakes that started before activation keep 10%. Table 1 gives the rate a new stake locks in on selected days of the ramp, computed with the protocol kernel.

| Stake start, UTC | Day of ramp | Minimum consumption rate locked in |
| --- | ---: | ---: |
| 2026-09-22 15:00 | 0 | 10.0000% |
| 2026-10-22 15:00 | 30 | 9.1667% |
| 2026-11-06 15:00 | 45 | 8.7500% |
| 2026-11-21 15:00 | 60 | 8.3334% |
| 2026-12-21 15:00 and later | 90 | 7.5000% |

*Table 1. The minimum consumption rate a stake locks in by its start time. The rate falls by one millionth about every 5.184 minutes, so starting one day earlier during the ramp locks in about 0.028 percentage points more.*

The effect on realized yield is smaller than the 2.5-point parameter change because the remaining-supply factor was about 0.53 at the supply the proposal uses. Table 2 compares the proposal's reward table with our reproduction at the same supply of 470,134,316 AVAX.

| Duration | ACP, 10% floor | ACP, 7.5% floor | Kernel, 10% floor | Kernel, 7.5% floor |
| --- | ---: | ---: | ---: | ---: |
| 2 days | not allowed | 4.00% | not allowed | 3.999% |
| 14 days | 5.36% | 4.08% | 5.356% | 4.078% |
| 90 days | 5.58% | 4.58% | 5.577% | 4.576% |
| 182 days | 5.85% | 5.18% | 5.845% | 5.179% |
| 365 days | 6.38% | 6.38% | 6.378% | 6.378% |

*Table 2. Annualized reward rate by duration. The kernel reproduces every published value to its two printed decimals. The spread between 14 and 365 days widens from 1.02 to 2.30 percentage points.*

## Status and activation

| Item | Value |
| --- | --- |
| Authors | Matias Antonio, Eric Lu, Martin Eckardt, Meaghan FitzGerald |
| Repository status | Proposed, Standards track |
| Discussion | Opened 2026-06-08, last updated 2026-06-24, 2 comments |
| Community call | 2026-06-29 |
| Fuji activation | 2026-07-28 15:00 UTC |
| Mainnet activation | 2026-09-22 15:00 UTC, with Helicon in AvalancheGo v1.15.0 |
| Ramp end | 2026-12-21 15:00 UTC |

AvalancheGo applies the ramp inside the Primary Network reward calculator, selecting the rate from each stake's start time. The proposal's reference-implementation section describes an earlier code path that selects the rate from the chain timestamp. The released code governs.

The discussion records two alternatives. One comment proposed keeping the 14-day rate and steepening the curve only below 14 days, to protect liquid staking and DeFi users. An early comment described a 30-day ramp. The proposal and the release both use 90 days.

## How it enters the staking model

The protocol kernel applies the ramp by stake start time and computes every commitment's potential reward with the Go integer operation order. In the [1.3 Staking Model Spec](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/) the minimum consumption rate sets the yield at each commitment length. In [1.4 Behavioral Calibration](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/) it is the lever whose effect on duration choice must be fitted, and in [2.5 Sensitivity Analysis](/Phase-II/Milestones/Milestone-2/2-5-Sensitivity-Analysis/) it is a swept parameter.

The proposal's behavioral claims are attributed and not reproduced by us. It projects that annual inflation falls about 0.5 percentage point with behavior held fixed and 0.5 to 1 point once durations respond, and that the stake-weighted average duration rises about two months. The Foundation's estimate in [How Do Avalanche Validators Actually Think About Staking Rewards?](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/) found that lowering the rate from 10% to 8% lengthens validator durations by 68%, from 10.0 to 16.9 weeks. In its scenarios that also shorten the minimum duration, average duration rises to 16.7 weeks at 8% and 20.9 weeks at 7%. The article states that these values lie outside the historical data and are directional. The shipped 7.5% lies between the two tested values.

## What our data can measure

The staking record holds each commitment's start time, duration, stake, recorded potential reward, and the supply counter at its start. Three measures follow.

1. Ramp reproduction. Comparing each recorded potential reward with the kernel's value tests the ramp commitment by commitment. The latest staking capture, taken 2026-09-22 16:20 UTC, holds transactions accepted up to 08:30 UTC that day, before activation, so no commitment under the ramp has been checked yet.
2. Duration response. The derived dataset `derived.helicon-commitments` records every validation cycle started after activation, from daily P-Chain snapshots. The first six days are summarized on the [ACP-273 page](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-273-Minimum-Validator-Duration/). Those days mix ACP-285 with the shorter minimum and auto-renewal, so they do not isolate this proposal.
3. Issuance. `derived.avax-monetary-daily` replays the realized total supply from rewards paid and AVAX burned, which is the series against which the proposal's inflation projection can be tested.

## Open questions

1. Does the stake-weighted average duration rise by about two months, as projected, once ACP-273 and ACP-236 are also in force? The first test needs a staking capture that covers commitments started through the ramp.
2. Which cohorts bear the lower short-duration reward: solo validators, delegators, liquid staking protocols, or exchange-traded products? The aggregate issuance change does not answer this.
3. Does the ramp pull staking forward, since each day of delay costs about 0.028 percentage points for the full term of a new stake?
4. Is 7.5% a point the Foundation expects to revisit? The proposal itself leaves open a further cut and a simultaneous change to the maximum rate.

## Public links

- Proposal: [ACP-285, Reduce Minimum Consumption Rate](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/285-reduce-minimum-consumption-rate/README.md)
- Discussion: [Discussion 288](https://github.com/avalanche-foundation/ACPs/discussions/288)
- Community call: [ACP 285 Avalanche Community Call](/Phase-II/Wiki/Collections/Essential-Readings/ACP-285-Avalanche-Community-Call-Staking-Reward-Curve-Adjustment/)
