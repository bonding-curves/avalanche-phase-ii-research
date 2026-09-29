---
title: "ACP-273 Minimum Validator Duration"
description: "ACP-273 lowers the Mainnet minimum validator duration from 14 days to 48 hours, leaving the delegator minimum at 14 days."
---

ACP-273 widens the range of commitment lengths a validator can choose, which is the first governance parameter the staking model names. Before Helicon no validator could commit for less than 14 days. The question for the research is how many validators move to shorter commitments, what that does to delegation and to how fast stake can turn over, and whether ACP-285's steeper reward curve offsets the pull toward liquidity.

The full text of the ACP-273 proposal is replicated on the [Source Proposal](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-273-Minimum-Validator-Duration/Source-Proposal) page.

## What it changes

| Parameter | Before Helicon | After Helicon |
| --- | --- | --- |
| Minimum validator duration, Mainnet | 14 days, 336 hours | 48 hours |
| Minimum validator duration, Fuji | 24 hours | 12 hours |
| Minimum delegator duration | 14 days | 14 days, unchanged |
| Maximum duration | 365 days | 365 days, unchanged |
| Minimum validator stake | 2,000 AVAX | 2,000 AVAX, unchanged |

The proposal's abstract describes the 14-day minimum as applying to validators and delegators. Its specification and the released code shorten only the validator minimum. A delegation must fit inside its validator's period and last at least 14 days, so a validator that chooses less than 14 days cannot accept delegation. This follows from the two rules together and is the constraint behind the Foundation's estimate, cited below, that a shorter minimum alone reduces delegation.

## Status and activation

| Item | Value |
| --- | --- |
| Authors | Eric Lu, Martin Eckardt, Meaghan FitzGerald, Stephen Buttolph |
| Repository status | Proposed, Standards track |
| Discussion | Opened 2026-02-17 under the title "Reduce Minimum Validator Staking Period to 24 Hours", last updated 2026-03-03, 3 comments |
| Mainnet activation | 2026-09-22 15:00 UTC, with Helicon in AvalancheGo v1.15.0 |
| Applies to | Validators added at or after activation, judged by chain time when the transaction is verified |

The discussion began with a 24-hour minimum. The proposal specifies 48 hours for Mainnet, and the release ships 48 hours. The Foundation article on validator rewards links this proposal under the name ACP-275. The repository has no ACP-275, and the link points to this proposal's discussion.

## How it enters the staking model

The protocol kernel selects the minimum duration by the time a validator is added and rejects shorter periods. In the [1.3 Staking Model Spec](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/) it sets the minimum commitment length. In [1.4 Behavioral Calibration](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/) the duration choice must be fitted over a choice set that now starts at 2 days, which lies outside every commitment in the historical record. In [2.6 Risk Surface Map](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/) it bounds how fast the validator set can change.

The yield difference the proposal cites is small. It reports 6.08% for 48 hours against 6.12% for 14 days, a gap of about 0.04 percentage points, at a supply it does not state. Our kernel gives 5.321% against 5.356%, a gap of 0.035 points, at the 470,134,316 AVAX supply ACP-285 uses, and 3.999% against 4.078% after ACP-285's ramp ends. The proposal's own security section states the consequence: if the incentive to commit longer is too weak, most stake may choose 48 hours, and a validator could move from 1% to 20% of network stake within hours. ACP-285 was written as its companion for that reason.

The Foundation's estimate in [How Do Avalanche Validators Actually Think About Staking Rewards?](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/) found that a shorter minimum alone barely changes average duration and reduces delegation by 53%, and that in its primary scenario, which also lowers the minimum consumption rate, delegation falls by 40%. These are attributed estimates outside the historical data. Eric Lu's reply in the discussion reports that about 16% of validating nodes and 6% of validating stake historically chose the 14-day minimum. We have not reproduced those shares.

## What our data can measure

The derived dataset `derived.helicon-commitments` records every validation cycle that started at or after activation, from daily P-Chain snapshots of the current validator set. Table 1 compares its first six days with the validator periods that started in the 30 days before activation.

| Duration | 30 days before activation | 2026-09-22 15:00 to 2026-09-29 00:15 UTC |
| --- | ---: | ---: |
| 48 hours to 7 days | 0 | 11 |
| 7 to 14 days | 0 | 1 |
| 14 to 30 days | 304 | 46 |
| 30 to 90 days | 58 | 12 |
| 90 to 180 days | 26 | 4 |
| 180 to 365 days | 13 | 4 |
| Total | 401 | 78 |

*Table 1. Validator periods by duration before Helicon and validation cycles by duration after it. The 12 cycles under 14 days were impossible under the earlier rule and confirm that the new minimum is active on Mainnet.*

These counts are weak evidence. They cover six days and 78 cycles, from 72 nodes of which 6 are new. The snapshots were up to 40 hours apart, so a 48-hour cycle that started and ended between two snapshots is missed and short cycles are undercounted. Among cycles with an earlier period on the same node, 15 were more than one day shorter than the node's previous period and 13 were longer. The share of cycles under 14 days, 12 of 78, is an observation about the first week, not an equilibrium.

The staking record also gives, for every commitment since 2020, the stake, duration, and delegations it carried, which is the input for fitting the duration choice and for measuring how much delegated stake sits with validators that choose less than 14 days.

## Open questions

1. What share of validator stake settles below 14 days once the reward ramp ends on 2026-12-21, and how much delegation does it exclude?
2. How fast can stake weight move among validators when many periods are 48 hours long? The proposal names this as a security cost but gives no bound.
3. Does the 14-day delegator minimum now bind? A validator that wants delegation must still commit for 14 days or longer, and the staking record can show whether delegated stake concentrates on those validators. The proposal's 14-fold state-growth estimate assumed a 48-hour delegator minimum, which did not ship.
4. Next evidence: daily snapshots with a gap under 24 hours, so every 48-hour cycle is observed.

## Public links

- Proposal: [ACP-273, Reduce Minimum Validator Staking Duration](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/273-reduce-minimum-staking-duration/README.md)
- Discussion: [Discussion 274](https://github.com/avalanche-foundation/ACPs/discussions/274)
- Upgrade overview: [Helicon Upgrade, Avalanche Builder Hub](https://build.avax.network/docs/primary-network/helicon-upgrade)
