---
title: "2026-10-01-duration-dependent-minimum"
description: "Hash's duration-dependent minimum stake can keep 2,000 AVAX at 14 days, hold at least 28,000 AVAX-days of capital at every duration, and lower the one-year minimum to 500 AVAX. Every validator commitment of the year before Granite already meets that setting."
date: 2026-10-01
status: draft
deliverables: ["2.8"]
tags: ["mechanism-design", "staking-duration-and-liquidity", "validator-economics"]
---

# A minimum stake that falls with duration can keep 2,000 AVAX at 14 days and open validation at 500 AVAX for a year

![Minimum validator stake by committed duration: today's flat 2,000 AVAX, Hash's recommended package, and the setting with 2,000 AVAX at 14 days](/Phase-II/Wiki/Memos/drafts/2026-10-01-duration-dependent-minimum/minimum-stake-by-duration.png)

*The minimum validator stake at each committed duration, both axes logarithmic. Grey dashed: today's rule. Blue: Hash's recommended package, 18,000 AVAX at 48 hours falling to 500 AVAX at a year. Green: the setting this memo describes, 19,400 AVAX at 48 hours, 2,000 AVAX at 14 days, and 500 AVAX at a year. [Interactive version](/Phase-II/Wiki/Memos/drafts/2026-10-01-duration-dependent-minimum/minimum-stake-by-duration.html).*

Hash's duration-dependent minimum stake can meet all three of its goals with one setting:
- 19,400 AVAX at 48 hours,
- 2,000 AVAX at 14 days,
- 500 AVAX at a year, on a curve of curvature 1.28.

At that setting the capital a validator commits, stake times days, never falls below 28,000 AVAX-days, which is 2,000 AVAX for 14 days. Every one of the 14,215 validator commitments accepted in the year before Granite already meets it.

## Why a minimum that depends on duration

Helicon lowered the minimum validator duration from 14 days to 48 hours on 22 September and kept the 2,000 AVAX minimum stake. So the least capital a validator commits fell from 28,000 AVAX-days to 4,000. Hash's proposal replaces the flat minimum with one that falls as the committed duration rises. Short commitments post more stake and long ones less. It is an admission rule: it decides which stakes the chain accepts. How validators respond to it is what the staking model will estimate.

Hash's draft specification sets three goals:

1. **Short-duration parity.** A 48-hour validator commits at least as much capital as a two-week validator did before Helicon.
2. **Relief for small validators.** A validator committing for a year can enter with 500 AVAX instead of 2,000.
3. **Defence against churn.** Cycling capital through many short-lived nodes stays costly, and delegation keeps its 14-day minimum.

His curve is a bounded harmonic decay. It runs from a stake at 48 hours down to a floor at one year, and a single curvature parameter sets how quickly it falls. Those three numbers are the whole design space.

## What the design space shows

![Minimum stake times duration, against 2,000 AVAX for 14 days](/Phase-II/Wiki/Memos/drafts/2026-10-01-duration-dependent-minimum/capital-by-duration.png)

*Stake times duration at the minimum, in AVAX-days. The dotted line is 2,000 AVAX for 14 days. The green setting touches it at 14 days and stays above it everywhere else. [Interactive version](/Phase-II/Wiki/Memos/drafts/2026-10-01-duration-dependent-minimum/capital-by-duration.html).*

| Setting | 48 hours | 7 days | 14 days | 30 days | 90 days | 1 year | Least AVAX-days |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Today | 2,000 | 2,000 | 2,000 | 2,000 | 2,000 | 2,000 | 4,000 |
| Hash's recommended package | 18,000 | 8,530 | 5,680 | 3,650 | 1,920 | 500 | 36,000 |
| 2,000 AVAX at 14 days | 19,400 | 4,235 | 2,000 | 1,033 | 601 | 500 | 27,998 |

*Minimum stake in AVAX at each committed duration. The least AVAX-days of the third setting is 27,998 rather than 28,000 because its 48-hour stake is rounded to 19,400.*

The two curves make different choices about where 2,000 AVAX sits. Hash's recommended package places it at about 12 weeks and sets a higher capital bar at 48 hours, 36,000 AVAX-days. The setting with 2,000 AVAX at 14 days keeps today's two-week validator exactly where it is. It asks more of shorter commitments and less of longer ones. That matters because two weeks at 2,000 AVAX is where most validators sit. From Durango to Fortuna, 62% to 69% of new validator commitments lasted the 14-day minimum, and in the year before Granite 10,176 of 14,215 validator commitments, 72%, staked under 2,100 AVAX.

We found the setting by searching curvatures from 1 to 4 with a 500 AVAX floor. For each curvature, the search took the smallest 48-hour stake that holds 28,000 AVAX-days at every duration, then kept the curvature with the lowest 14-day minimum. With a 1,000 AVAX floor the same search also lands on 2,000 AVAX at 14 days, at curvature 1.93 and about 46,000 AVAX at 48 hours.

## What it means for a decision

The open question in our 25 September brief was where the curve should sit at 14 days. These numbers turn it into a choice between two clear options:
- 2,000 AVAX at 14 days, which keeps today's two-week validators and gives the deepest relief at long durations;
- a higher 14-day stake, which buys a larger capital buffer at 48 hours.

Both reach 500 AVAX at a year.

The Foundation can set the curve itself. The model ships with an explorer in which the 48-hour stake, the one-year floor, and the curvature are sliders. As they move, the curve updates, along with the share of real validator commitments that meet it.

## Next steps

1. Review with Hash the setting with 2,000 AVAX at 14 days, and his choice of 48-hour stake and one-year floor.
2. Place BENQI's reported 6,000 AVAX delegation threshold on the curve.
3. Test each setting in the staking model against observed duration choices, once its behaviour blocks are fitted, including the first Helicon commitments.

*A note on our 25 September brief: it referred to a 500 AVAX minimum stake as "ACP-49". The 500 AVAX floor is a proposed setting, not an existing ACP.*

*Source: validator commitments in run `staking-periods-2026-09-30` accepted from 19 November 2024 to 19 November 2025, each judged at its own stake and duration, and the 22 September run for the Durango to Fortuna shares. The admission rule and its checks are part of the staking model.*

**For you:** should a minimum that holds 2,000 AVAX at 14 days and falls to 500 AVAX at a year be evaluated alongside the tenure-weighted and fee-funded reward designs?
