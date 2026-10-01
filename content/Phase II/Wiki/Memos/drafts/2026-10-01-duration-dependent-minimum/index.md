---
title: "2026-10-01-duration-dependent-minimum"
description: "A minimum validator stake that falls with committed duration can hold 2,000 AVAX for 14 days of capital at every duration, keep today's two-week validators, and still lower the one-year minimum to 500 AVAX. The settings drafted so far do not."
date: 2026-10-01
status: draft
deliverables: ["2.8"]
tags: ["mechanism-design", "staking-duration-and-liquidity", "validator-economics"]
---

# A minimum stake that falls with duration can meet all three of its goals, but not at the settings drafted so far

![Minimum validator stake by committed duration under today's rule and five frontier settings, and the stake times days each requires against the 28,000 AVAX-day baseline](/Phase-II/Wiki/Memos/drafts/2026-10-01-duration-dependent-minimum/minimum-stake-by-duration.png)

*Left: the minimum validator stake at each committed duration. Packages A and B are Hash's drafted settings, and purple is the setting this memo proposes for discussion. Right: that minimum times its duration. The red line is 2,000 AVAX for 14 days, the least capital a validator committed before Helicon. Both axes are logarithmic.*

## Finding

The frontier Hash designed can meet all three of its goals at once. With a one-year minimum of 500 AVAX, a curvature of 1.28 and 19,400 AVAX at 48 hours, it:

- asks for exactly 2,000 AVAX at 14 days,
- never asks for less capital than 2,000 AVAX for 14 days at any duration, and
- admits every validator commitment of the year before Granite.

The settings drafted so far, Packages A and B, keep the capital baseline. They do it by raising the 14-day minimum to 4,387 and 5,680 AVAX. Under them, only 29.9% and 25.7% of that year's commitments would have qualified, although those commitments held about 98% of the stake.

## Why a minimum that depends on duration

Helicon lowered the minimum validator duration from 14 days to 48 hours on 22 September and kept the 2,000 AVAX minimum stake. So the least capital a validator commits fell from 28,000 AVAX-days (2,000 AVAX for 14 days) to 4,000 (2,000 AVAX for 2 days), a seventh of the old baseline. Hash's proposal replaces the flat minimum with one that falls as the committed duration rises. Short commitments post more stake, and long ones less.

The rule only admits or rejects a stake. It predicts nothing about how validators respond, which the staking model will estimate.

Hash set three goals for it:

1. **Capital parity.** Stake times days never falls below 28,000 AVAX-days.
2. **Relief for small validators.** A validator committing for a year can enter with less than 2,000 AVAX.
3. **A barrier to cycling nodes.** It must be costly to split capital across many short-lived nodes.

His curve, a bounded harmonic decay, falls from a 48-hour stake to a one-year floor, at a rate set by a curvature parameter. His specification requires it to be strictly convex, so each day cut from a commitment costs more stake the shorter the commitment already is. That holds only at a curvature of at least 1.

**A correction to our 25 September brief.** It called a 500 AVAX minimum stake "ACP-49". No ACP has that number. The 500 AVAX floor is a value we propose, not an Avalanche proposal.

## Evidence

Most validators sit exactly where a duration-dependent minimum acts. From Durango to Fortuna, 62% to 69% of new validator commitments lasted the 14-day minimum, and the typical one staked 2,000 AVAX (run `staking-periods-2026-09-22`). In the year before Granite, from 19 November 2024 to 19 November 2025, 10,176 of 14,215 validator commitments, 72%, staked under 2,100 AVAX (run `staking-periods-2026-09-30`).

How each setting treats those 14,215 commitments, each judged at its actual stake and duration:

| Setting | 48 hours | 14 days | 1 year | Reaches 2,000 AVAX at | Least AVAX-days | Commitments admitted | Stake admitted | Strictly convex |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Today | 2,000 | 2,000 | 2,000 | any duration | 4,000 | 100% | 100% | not applicable |
| Package A | 14,000 | 4,387 | 500 | 56 days | 28,000 | 29.9% | 97.9% | no |
| Package B | 18,000 | 5,680 | 500 | 84 days | 36,000 | 25.7% | 97.7% | no |
| Package B anchors at curvature 1 | 18,000 | 2,917 | 500 | 22 days | 36,000 | 40.8% | 98.2% | yes |
| Proposed: curvature 1.28 | 19,400 | 2,000 | 500 | 14 days | 27,998 | 100% | 100% | yes |

All of these commitments ran at least 14 days, since the 48-hour minimum did not exist yet. The table shows who each rule would have turned away, not how validators will respond after Helicon. The proposed setting touches the baseline only at 14 days, where 27,998 AVAX-days reflects rounding 2,000.01 AVAX down to 2,000.

Two results here are ours and Hash has not yet confirmed them:

1. **Packages A and B are not strictly convex.** Their curvatures are 0.629 and 0.615, below the 1 his own specification requires. Below 1 the curve steepens again in the last weeks before a year, so the minimum drops sharply just short of 365 days. The right panel shows it as the bend at the end of the blue and green lines.
2. **The proposed setting.** It came from a search over curvatures from 1 to 4. For each curvature, the search found the lowest 48-hour stake that keeps capital parity at every duration, then kept the curvature with the lowest 14-day minimum. With a 500 AVAX floor, that minimum is 2,000 AVAX, at curvature 1.28. With a 1,000 AVAX floor it is also 2,000 AVAX, but the curvature rises to 1.93 and the 48-hour stake to about 46,000 AVAX.

## What it means for a decision

The open question in our 25 September brief was where the curve should sit at 14 days. The first numbers suggest that is not a free choice. Parity fixes the curve at 2,000 AVAX for 14 days or above. Any setting above 2,000 AVAX turns away validators who stake today's minimum for two weeks, and in the year before Granite they were most validators.

The proposed setting keeps them and still lowers the one-year minimum to 500 AVAX. Its cost falls on short commitments: 19,400 AVAX at 48 hours and about 4,235 AVAX at 7 days. Of the first 20 validator commitments under Helicon, two chose 48 hours at about 2,000 AVAX (our 25 September brief, captures to 24 September). This rule would ask them for 19,400 AVAX.

## What is open

1. Hash's confirmation of the two results above, and his choice of the 48-hour stake and the one-year floor.
2. Whether a stake near BENQI's reported 6,000 AVAX threshold for delegation belongs anywhere on the curve, now that 14 days is pinned at 2,000 AVAX.
3. How validators respond. The staking model will test each setting against observed duration choices once its behaviour blocks are fitted.
4. An explorer for the Foundation to set the curve's parameters, which we are building in the staking model.

## How it was built

The admission rule, its convexity check and the shares come from the staking model's prototype, in review and not yet in the shared repository. Commitments are validator periods in `derived.staking-periods` accepted from 19 November 2024 to 19 November 2025, each judged at its own stake and duration. Packages A and B are from Hash's draft specification of 26 September.

**For you:** is a minimum that stays at 2,000 AVAX for 14 days, rises for shorter commitments, and falls to 500 AVAX at a year the shape the Foundation would want evaluated alongside the tenure-weighted and fee-funded reward designs?
