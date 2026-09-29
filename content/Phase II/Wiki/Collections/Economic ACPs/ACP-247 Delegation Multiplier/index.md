---
title: "ACP-247 Delegation Multiplier"
description: "ACP-247 proposes raising the most delegated stake a validator can accept from 4 to 24 times its self-stake, under the unchanged 3,000,000 AVAX weight cap."
authors: ["Giacomo Barbieri", "BENQI"]
published: 2025-11-13
venue: "Avalanche Community Proposal"
url: "https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/247-delegation-multiplier-increase/README.md"
full_text: "/Phase-II/Wiki/Collections/Economic-ACPs/ACP-247-Delegation-Multiplier/Source-Proposal"
tags: ["delegation-market", "decentralization", "validator-economics"]
key_terms: ["delegation capacity", "delegation multiplier", "self-stake", "maximum validator weight", "node splitting", "consensus weight"]
deliverables: ["2.6", "2.8"]
---

ACP-247 is a proposal from outside the Foundation, by Giacomo Barbieri and BENQI, to raise validator income by allowing more delegation per unit of self-stake. It did not ship with Helicon. It matters to the research because it is the kind of alternative mechanism [2.8 Collaborative Mechanism Design](/Phase-II/Milestones/Milestone-2/2-8-Collaborative-Mechanism-Design/) exists to evaluate, and because its effect depends on one measurable fact: whether the current **delegation capacity** limits delegation at all.

<!-- overview-table:start -->

| | |
| --- | --- |
| **Authors** | Giacomo Barbieri, BENQI |
| **Published** | November 13, 2025 |
| **Source** | Avalanche Community Proposal, [original](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/247-delegation-multiplier-increase/README.md), [full text](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-247-Delegation-Multiplier/Source-Proposal) |
| **Topics** | [delegation market](/tags/delegation-market), [decentralization](/tags/decentralization), [validator economics](/tags/validator-economics) |
| **Key terms** | [delegation capacity](/Phase-II/Wiki/Reference/Glossary-and-Notation), delegation multiplier, [self-stake](/Phase-II/Wiki/Reference/Glossary-and-Notation), maximum validator weight, node splitting, consensus weight |
| **Serves deliverables** | [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/), [2.8](/Phase-II/Milestones/Milestone-2/2-8-Collaborative-Mechanism-Design/) |

<!-- overview-table:end -->

The full text of the ACP-247 proposal is replicated on the [Source Proposal](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-247-Delegation-Multiplier/Source-Proposal) page.

## What it changes

The proposal changes one parameter. The most delegated stake a validator can accept becomes the lesser of 24 times its self-stake and the room left under the 3,000,000 AVAX maximum validator weight.

| Parameter | Current | Proposed |
| --- | --- | --- |
| Delegated stake per unit of self-stake | 4 | 24 |
| AvalancheGo total-weight factor, self-stake plus delegation | 5 | 25 |
| Maximum validator weight | 3,000,000 AVAX | 3,000,000 AVAX, unchanged |
| Minimum validator stake | 2,000 AVAX | 2,000 AVAX, unchanged |

Table 1 applies both limits at four self-stake levels.

| Self-stake, AVAX | Delegation capacity now | Delegation capacity under ACP-247 |
| ---: | ---: | ---: |
| 2,000 | 8,000 | 48,000 |
| 10,000 | 40,000 | 240,000 |
| 120,000 | 480,000 | 2,880,000 |
| 500,000 | 2,000,000 | 2,500,000 |

*Table 1. Delegation capacity by self-stake. Above 120,000 AVAX of self-stake the 3,000,000 AVAX cap binds before the 24 times limit.*

The proposal text carries stale wording from an earlier version. Its abstract says the multiplier rises from 5 to 24, while its specification says 4 to 24. The earlier version also cut the maximum validator weight from 3,000,000 to 1,000,000 AVAX. The current text, last changed on 2026-02-10, drops that part, but the discussion title and many comments still analyze it.

## Status and activation

| Item | Value |
| --- | --- |
| Authors | Giacomo Barbieri, BENQI |
| Repository status | Implementable, Standards track |
| Discussion | Opened 2025-11-13, last updated 2025-12-29, 14 comments |
| Implementation | Not present in AvalancheGo v1.15.0. The weight factor is still 5. |
| Activation | Not scheduled |

## How it enters the staking model

The protocol kernel computes a validator's maximum weight from its self-stake, a delegation multiplier, and the weight cap, with 4 as the default. ACP-247 is a change to that one argument. What the kernel cannot supply is the behavioral response. The proposal's profit tables assume that the added capacity fills with delegation: at a 5% fee, $20 per AVAX, and 8.25% yield, a 2,000 AVAX validator's monthly profit rises from $180 to $455 at full capacity. Discussion participants disputed that assumption and raised node splitting, the rise in consensus weight of small self-stake validators, and attack-cost estimates that range from about $190 million to $1.4 billion. All of these are attributed and not reproduced. In [2.6 Risk Surface Map](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/) the multiplier is a parameter whose concentration and consensus-weight effects must be mapped before any recommendation.

## What our data can measure

The public P-Chain RPC snapshot of 2026-09-29 00:15 UTC lists every current validator's self-stake and delegated stake. Among its 601 validators:

1. Delegated stake was 40.2 million AVAX against a capacity of 331.8 million AVAX at the current limit, 12.1% of capacity.
2. 113 validators were at 90% or more of their capacity and held 21.6 million AVAX of delegation, 54% of the total.
3. 344 validators, 57%, had no delegation.
4. Under ACP-247 the capacity of the same validators would be 631.7 million AVAX.

The current limit therefore binds for about one validator in five and not for the network as a whole. This is a single snapshot and counts nodes, not operators, since one operator can run many nodes. It agrees in size with a discussion comment that about 41 million AVAX was delegated against more than 600 million AVAX of capacity in November 2025. The staking record holds every delegation since 2020 with its validator, so the same measure can be taken weekly over the full history.

## Open questions

1. Where would delegation move if capacity rose, given that the validators already full attract most of it? This needs an allocation model, which the proposal does not supply.
2. Does the added capacity reward splitting stake across nodes, and how much consensus weight could one operator gain?
3. Is fee income the constraint on small validators, or is it delegator demand? The 57% of validators without delegation is consistent with limited demand. That is a hypothesis to test, not a finding.

## Public links

- Proposal: [ACP-247, Delegation Multiplier Increase](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/247-delegation-multiplier-increase/README.md)
- Discussion: [Discussion 248](https://github.com/avalanche-foundation/ACPs/discussions/248)
