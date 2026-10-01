---
title: "2026-10-01-helicon-first-days"
description: "In Helicon's first eight days, 13 of 105 new validator commitments chose under 7 days, against none of 401 in the 30 days before. They hold 1.25% of the new stake. Every auto-renewed 48-hour commitment has renewed."
date: 2026-10-01
status: draft
deliverables: ["1.4", "2.8"]
tags: ["staking-duration-and-liquidity", "validator-economics", "mechanism-design"]
---

# Helicon's first eight days: one in eight new validator commitments is under a week, holding almost none of the capital

![Share of new validator commitments by duration, in the 30 days before Helicon and in its first eight days](/Phase-II/Wiki/Memos/drafts/2026-10-01-helicon-first-days/helicon-first-days.png)

*Each pair of bars is one duration range. Grey is the 30 days before Helicon activated, 401 validator commitments. Blue is the time since activation, 105 commitments. Look at the first pair: a short tail that did not exist before. The 14-to-30-day bar is still the largest. Data: runs `helicon-commitments-2026-10-01` and `staking-periods-2026-09-30`. [Interactive version](/Phase-II/Wiki/Memos/drafts/2026-10-01-helicon-first-days/helicon-first-days.html).*

## Finding

Helicon activated on 22 September 2026 at 15:00 UTC. It lowered the minimum validator commitment from 14 days to 48 hours and added auto-renewal. Through the validator set captured on 1 October at 00:15 UTC, 105 validator commitments began on 101 nodes. Thirteen of them, 12.4%, chose between 48 hours and 7 days. In the 30 days before activation, none of 401 did.

The short commitments are small. They hold 226,981 AVAX of the 18,181,764 AVAX newly committed, which is 1.25%, and 0.04% of the committed AVAX-days. Most new commitments still last 14 to 30 days, 59% now against 76% before. Five commitments of 180 to 365 days hold two thirds of the committed AVAX-days, two of them from new validators of 1,800,000 and 1,750,113 AVAX for 198 days. Delegations cannot follow, since their minimum is still 14 days. Of 14,807 delegations begun since activation, the shortest lasts 14.0 days.

## The first renewals

The brief of 25 September promised this comparison once the first 48-hour cycles had renewed. Four of the 13 short commitments are auto-renewed, and all four have renewed at least once. One, on a node new to the network with 2,029 AVAX, is in its fourth cycle. The four stakes are 2,000, 2,001, 2,029, and 170,162 AVAX. Three of the four restake their reward: the validator that began with 2,000.30 AVAX holds 2,000.87 AVAX in its second cycle. The other nine short commitments are fixed periods of 2 to 3 days at 2,000 to 9,990 AVAX. Four of them, at 9,990 AVAX for 2 days each, began at 06:01, 06:07, 06:13, and 06:19 UTC on 24, 26, 28, and 30 September. That is one schedule, repeated by hand rather than by auto-renewal.

Validators that already validated before Helicon behave much as they did. Of 99 new periods on returning nodes, 23, or 23.2%, are more than a day shorter than the node's previous period, and 5 of those dropped under 7 days. In the 30 days before activation the same rule gives 91 of 391, or 23.3%, in run `staking-periods-2026-09-22`. So far the lower minimum has not made returning validators shorten more often. It has added a short tail at the minimum stake.

| Duration | Before: commitments | Before: share | Since: commitments | Since: share | Since: share of stake | Since: share of AVAX-days |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 48 hours to 7 days | 0 | 0% | 13 | 12.4% | 1.25% | 0.04% |
| 7 to 14 days | 0 | 0% | 1 | 1.0% | 0.05% | 0.01% |
| 14 to 30 days | 304 | 75.8% | 62 | 59.0% | 64.9% | 19.2% |
| 30 to 90 days | 58 | 14.5% | 16 | 15.2% | 9.0% | 6.2% |
| 90 to 180 days | 26 | 6.5% | 8 | 7.6% | 5.2% | 8.0% |
| 180 to 365 days | 13 | 3.2% | 5 | 4.8% | 19.6% | 66.6% |

## What it means

The short option is used, but by validators at or near the 2,000 AVAX minimum stake. Their median stake is 2,201 AVAX, against 55,532 AVAX for the 14-to-30-day commitments begun in the same days. This is the pattern our memo on validator minimums found from Durango on: most decisions sit at the minimum and hold little of the capital. Helicon has moved the minimum, and the decisions at it have moved with it. The capital has not.

For economic security, eight days show no shift of stake to short commitments. For the reward design, the question is whether this holds as the new reward curve phases in. Helicon lowers the reward rate for short commitments in steps over 90 days, to about 21 December. The first eight days sit at the start of that ramp, while the curve is still close to the old one.

## How it was built

- **Measure.** A commitment is one validator staking transaction's period. Under auto-renewal one transaction runs several cycles, and its first cycle is the commitment, so a renewal is not counted twice. Durations are grouped in the ranges of the table, each including its lower bound.
- **Data.** Run `helicon-commitments-2026-10-01` of `derived.helicon-commitments` holds every validator cycle begun since activation. It is built from 13 snapshots of the validator set, one a day, and the largest gap between two snapshots is 40 hours, so every 48-hour cycle appears in at least one. The 30 days before activation come from run `staking-periods-2026-09-30` of `derived.staking-periods`, which also gives the delegations. Both are described in [Data](/Phase-II/Wiki/Reference/Data).
- **Code.** `scripts/figures/helicon_first_days.py` in the repository writes this chart and its table, `helicon-first-days.csv`, beside this page.

## What is open

1. Eight days and 105 commitments are a small sample. The shares will move as the snapshots continue daily.
2. Whether the short tail grows as the reward curve phases in, or shrinks because short commitments earn less. We committed simple benchmarks for these shares on 29 September and score our forecasts against them on 22 October and 21 December.
3. Who runs the short commitments. Four of the nine fixed short periods repeat on one schedule. We have not tried to attribute them to an operator.

**For you:** does the Foundation expect the 48-hour option to stay with small validators at the minimum stake, or to draw in larger operators as the reward curve phases in? And did the test network show auto-renewal at scale?
