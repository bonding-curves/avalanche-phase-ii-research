---
title: "ACP-267 Uptime Requirement"
description: "ACP-267 raises the uptime a Primary Network validator needs for any reward from 80% to 90%, for validations starting at or after Helicon."
---

ACP-267 changes which commitments are paid. Avalanche has no slashing: a validator that misses the **uptime requirement** keeps its stake and loses the whole reward of the period, and its delegators lose theirs. Raising the threshold therefore moves the realized reward of every validator whose uptime falls between 80% and 90%. The question for the research is how many validators and how much stake sit in that band, and whether they improve their operations, accept the lost reward, or leave.

## What it changes

| Parameter | Before Helicon | After Helicon |
| --- | --- | --- |
| Uptime requirement, Primary Network | 80% | 90%, for validations starting at or after activation |
| Reward below the requirement | None for the validator and its delegators | None for the validator and its delegators, unchanged |
| Uptime calculation | Each node's observed responsiveness of the validator over its period | Unchanged |
| Principal at risk | None | None, unchanged |

The threshold is chosen by the validator's start time, and the validator's delegators are judged by the same threshold. A validation that started before 2026-09-22 15:00 UTC is still judged at 80% when it ends, even if it ends months later.

## Status and activation

| Item | Value |
| --- | --- |
| Author | Martin Eckardt |
| Repository status | Proposed, Best Practices track |
| Announced | 2026-02-10, according to the proposal |
| Discussion | Opened 2026-02-02, last updated 2026-07-04, 9 comments |
| Mainnet activation | 2026-09-22 15:00 UTC, with Helicon in AvalancheGo v1.15.0 |
| Code | `ACP267UptimeRequirement = 0.9` in AvalancheGo's genesis parameters, selected when the validator's start time is at or after Helicon |

The discussion raised four issues the research must carry. Stakeholders asked that the higher threshold apply only to new periods, which the proposal adopted. They showed that uptime depends on the observer: Snowpeer and AvaScan reported different values for the same validators. They noted that a database failure or a multi-day bootstrap can make a short period unrecoverable. They distinguished professional operators with redundant machines from home validators. Martin Eckardt reported that more than 95% of stake had uptime above 98%. That figure is attributed and not reproduced by us.

## How it enters the staking model

The protocol kernel selects 80% or 90% by the validator's start time. In the [1.3 Staking Model Spec](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/) the requirement decides whether a commitment's potential reward becomes a realized reward. The kernel does not yet simulate uptime itself, so the model needs a distribution of uptime by validator to turn the threshold into expected lost rewards. In [2.6 Risk Surface Map](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/) the threshold interacts with ACP-273 and ACP-236: a validator on a 48-hour period fails the 90% requirement after 4.8 hours offline, and under auto-renewal a failed cycle also ends the validation.

## What our data can measure

The staking record gives the outcome of every closed validator period, rewarded or not, but not the uptime value. Under the 80% rule, 1,397 of 56,958 closed validator periods since 2020 ended without a reward, 2.5%. In periods that ended in the year before the 2026-09-22 capture, 211 of 6,213 failed, 3.4%, holding 11.7 million of the 1,039.4 million AVAX of stake summed over those periods, 1.1%. The record cannot say which of the passing periods would have failed at 90%.

Two current sources give uptime levels, and they disagree. Table 1 compares them for the 599 validators present in both.

| Observer | What it reports | Validators below 90% |
| --- | --- | ---: |
| Public P-Chain RPC node, 2026-09-29 00:15 UTC | One node's observed uptime of each validator over its current period so far | 52 |
| Builder Hub, hourly medians 2026-09-10 to 2026-09-27 | The median over Ava Labs' observing nodes for each hour, averaged per validator | 23 |
| Validators on which the two disagree | Below 90% for one observer and not the other | 37 |

*Table 1. Validators below the 90% threshold according to two observers. The observers cover different windows, so the table shows how much the answer depends on the observer, not which one is right.*

In the full RPC snapshot, 53 of 601 validators report uptime below 90%, holding 8.3 million of 203.0 million AVAX of validator weight, 4.1%. 27 are below 80% and 26 lie between 80% and 90%. These are weak numbers: one observer, periods still open, and a single instant. They bound the stake the new threshold could affect at a few percent of weight, and they show that the answer depends on how uptime is aggregated.

## Open questions

1. How many periods that start after Helicon fail at 90% that would have passed at 80%? The first answer comes from the reward outcomes of those periods, which the staking record will hold once it is captured again.
2. Which aggregation of observers matches the protocol's reward decision, since each validator's reward follows the preferences of the nodes that observed it?
3. Do validators in the 80% to 90% band raise their uptime, or leave, and are they concentrated among smaller operators?

## Public links

- Proposal: [ACP-267, Increase Validator Uptime Requirement from 80% to 90%](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/267-uptime-requirement-increase/README.md)
- Discussion: [Discussion 268](https://github.com/avalanche-foundation/ACPs/discussions/268)
