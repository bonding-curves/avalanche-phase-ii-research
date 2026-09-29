---
title: "Minimum validator stake of 500 AVAX"
description: "A lower minimum validator self-stake of 500 AVAX has been suggested in public discussion but has no ACP number, and the Mainnet minimum remains 2,000 AVAX."
---

Our [brief of 2026-09-25](/Phase-II/Wiki/Briefs/2026-09-25-sprint-8/) described a 500 AVAX minimum stake as ACP-49 and discussed how it would combine with ACP-273's 48-hour minimum. That label is wrong. No ACP-49 exists, and no ACP proposes a 500 AVAX minimum. This page records what does exist, because the minimum self-stake is still a parameter the Foundation may want evaluated under [2.8 Collaborative Mechanism Design](/Phase-II/Milestones/Milestone-2/2-8-Collaborative-Mechanism-Design/).

## What the record shows

| Item | Value |
| --- | --- |
| Mainnet minimum validator self-stake | 2,000 AVAX since genesis, unchanged by Helicon |
| Fuji minimum validator self-stake | 1 AVAX |
| ACPs in the repository on 2026-09-29 | 36, numbered 13 to 285, none numbered 49 |
| Item numbered 49 in the repository | A 2023 pull request that marked ACP-30 as implementable |
| Nearest public source | Discussion 56, "Make Validator Requirements Less Than 500 Avax", brainstorming category, opened 2023-12-16, one comment |
| Related open question | ACP-247 asks whether the minimum should stay at 2,000 AVAX and answers that lowering it would need a separate ACP |

ACP-273 and ACP-285, both activated with Helicon, list the 2,000 AVAX minimum among the parameters they leave unchanged.

## Why the minimum still matters

The minimum self-stake and the minimum duration together set the smallest capital commitment a validator can make. Table 1 gives that product in AVAX-days, the stake multiplied by the days it is committed.

| Rule set | Minimum stake | Minimum duration | Smallest commitment |
| --- | ---: | ---: | ---: |
| Before Helicon | 2,000 AVAX | 14 days | 28,000 AVAX-days |
| After Helicon | 2,000 AVAX | 2 days | 4,000 AVAX-days |
| After Helicon with a 500 AVAX minimum | 500 AVAX | 2 days | 1,000 AVAX-days |

*Table 1. The smallest capital commitment under each rule set. Helicon has already cut it by 86%, and a 500 AVAX minimum would cut it by 96% from the pre-Helicon level.*

This arithmetic is exact. What it implies for security, churn, and P-Chain state growth is a hypothesis and has not been measured. The design the brief described, a minimum stake that falls as committed duration rises, is our own idea for evaluation and not a proposal before the community.

## What our data can measure

The staking record shows how many validators sit at the current minimum, which bounds the demand a lower minimum would meet among existing validators. Of 57,560 validator periods since 2020, 22,561 staked exactly 2,000 AVAX, 39.2%. Of the 5,913 validator periods that started in the year before Helicon, 1,254 did, 21.2%. The record cannot show how many holders stay out because 2,000 AVAX is too much. That needs a different source, such as delegators whose delegation exceeds 500 AVAX.

## Open questions

1. Does the Foundation want a lower minimum stake evaluated at all, and if so, as a flat minimum or as a minimum that depends on duration?
2. What lower bound on commitment in AVAX-days does the Foundation consider safe, now that Helicon has cut it from 28,000 to 4,000?

## Public links

- Discussion: [Discussion 56, Make Validator Requirements Less Than 500 Avax](https://github.com/avalanche-foundation/ACPs/discussions/56)
- Related open question: [ACP-247, Delegation Multiplier Increase](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/247-delegation-multiplier-increase/README.md)
- Repository index: [avalanche-foundation/ACPs](https://github.com/avalanche-foundation/ACPs)
