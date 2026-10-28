---
title: "2026-10-30-milestone-2"
description: "The agenda brief for the 30 October call: what the chain's data shows since Helicon, Milestone 2 and the structure of the model, the plan for Workshop 1 on 13 November, and the plan for Milestone 3 in December and January."
date: 2026-10-30
status: submitted
tags: ["parameter-selection-under-uncertainty", "sensitivity-analysis", "model-structure"]
---

Milestone 2's analysis is complete, and [the Sensitivity Analysis Report](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/) gives the full account of its model, method and results. On this call we walk through the model as a whole, as you asked on 16 October, show what the results mean for reward policy, and agree the plan for Workshop 1 on 13 November and for Milestone 3 in December and January.

## 1. Five weeks after Helicon, validators hold more stake and renew as before

Five weeks after Helicon, validators hold more stake than on Helicon day, renew at the same rate as before, and use the two-day option for a quarter of new commitments but little of their AVAX. The Helicon upgrade activated ACP-285 on 22 September 2026 at 15:00 UTC. ACP-285 lowers the minimum consumption rate from 10% to 7.5% over 90 days, ending 21 December 2026, and lets a validator commit for as little as 48 hours. Every number below comes from our own record of the P-Chain. The record runs to the close of 26 October 2026, 23:59:59 UTC.

### DI1. Validator stake is 4.3M AVAX above Helicon day with 16 fewer validators

Active validator stake closed 26 October at 170.26 million AVAX, 4.27 million above its level at the close of Helicon day. It fell to 141.59 million on 8 October while large nodes paused, and rose to 177.09 million on 22 October as they returned and new long commitments started. The count of active validators fell from 606 to 590 over the same five weeks, so the average validator held 0.289 million AVAX on 26 October against 0.274 million on Helicon day.

![DI1. Validator stake is 4.3M AVAX above Helicon day with 16 fewer validators](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/di1-stake-and-count.png)

*DI1. Active validator stake and the count of active validators at each day's close, 1 September to 26 October 2026. The grey dashes mark the level at the close of 22 September. Source: our P-Chain record.*

### DI2. Two-day commitments hold at a quarter of new starts and 0.3% of AVAX-days

Short commitments, nearly all exactly two days long, made 26%, 27% and 26% of new validator commitments in the three weeks to 26 October, up from 11% in Helicon's first week. Across everything committed since Helicon they are 21.2% of commitments, against 18.9% in the 16 October brief, while their share of AVAX-days, stake times length, fell from 0.40% to 0.33%. At the 26 October close, 27 nodes held 3.96 million AVAX on short cycles, 2.3% of validator stake, and the six two-day nodes over 100,000 AVAX are those of 16 October.

![DI2. Two-day commitments hold at a quarter of new starts and 0.3% of AVAX-days](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/di2-short-commitments.png)

*DI2. Panel A shows the short share of each week's new validator commitments, where short means a first cycle of 48 hours to under 7 days. Panel B compares the short share of all commitments since Helicon to 15 October and to 26 October, by count, by stake and by AVAX-days. Source: our P-Chain record.*

### DI3. The ramp has cut 39,000 AVAX or 3.5% from promised rewards

Stakes started from Helicon to the 26 October close are promised 1,074,269 AVAX in rewards, which is 38,929 AVAX less than the same stakes and lengths would earn under the old 10% floor. Stakes started on 26 October earn 4.70% a year against 5.17% under the old rule, as the minimum consumption rate for that day had fallen to 9.06%. Stakes started on 15 and 20 October, when large validators committed for 79 to 365 days, make 19,204 AVAX of the saving, and 3,255 AVAX sits on stakes already paid.

![DI3. The ramp has cut 39,000 AVAX or 3.5% from promised rewards](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/di3-ramp-reward.png)

*DI3. Panel A shows the annual reward rate of each day's new stakes, weighted by stake, under ACP-285 and under the old 10% floor. Panel B shows the running total of rewards saved, by the day each stake started. Validators, delegators and every auto-renewed cycle count. Source: our P-Chain record.*

### DI4. Renewals held at 86% within two weeks as 77 nodes left and 61 arrived

Of 320 validator nodes whose staking ended between Helicon and 12 October, 86.2% staked again within 14 days, against 85.6% of 1,235 endings in the 90 days before Helicon. From the 22 September close to the 26 October close, 77 nodes holding 17.7 million AVAX stopped validating and 61 nodes holding 21.3 million AVAX started. In the 34 days before Helicon, 48 nodes left with 18.6 million AVAX and 43 arrived with 5.8 million, so the nodes leaving since Helicon are more but smaller.

![DI4. Renewals held at 86% within two weeks as 77 nodes left and 61 arrived](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/di4-renewals-exits.png)

*DI4. Panel A shows validator node endings by week and the share back within 14 days, from 23 June to the last ending with 14 days of follow-up, 12 October. Panel B compares nodes that left and arrived in the 34 days after the Helicon-day close with the 34 days before Helicon. Source: our P-Chain record.*

### DI5. Bitwise kept all 25 new validator commitments at 15 days or longer

Bitwise's BAVA, the one exchange-traded fund whose validators we can trace on chain, started 25 validator commitments from Helicon to 26 October, all 15.1 to 19.1 days long, so it has not used the two-day option. Its 11 active validators held 1,786,084 AVAX at 00:15 UTC on 27 October, 66.9% of the 2,670,012 AVAX the fund reported for 26 October. 21Shares reported 200,983 AVAX less for 26 October than for 23 October, which leaves the three funds we capture daily at 6.15 million AVAX against 6.34 million on 14 October.

![DI5. Bitwise kept all 25 new validator commitments at 15 days or longer](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/di5-etf-validators.png)

*DI5. Panel A shows each BAVA validator commitment since Helicon by start day and length, with circle area for stake. Panel B shows AVAX held by Bitwise's BAVA, VanEck's VAVX and the 21Shares fund by valuation day. Over the 26 October valuation, 21Shares' shares outstanding fell from 8.8 million to 7.7 million. Source: our P-Chain record matched to BAVA's 32 published wallets, and the issuers' published holdings.*

## 2. Milestone 2 tests reward designs on a model of every validator

Phase II learns how Avalanche's validators behave from the network's full history, then tests reward designs across market conditions to measure how each one changes participation, security and issuance. Milestone 1 built the record and the first model. Milestone 2 tested reward designs on it.

**The model.** Model v0.8.0 follows every validator commitment one day at a time, starting from the chain's actual state. Each day, commitments that end either renew or leave, departed nodes may return, new nodes arrive, each chooses a stake and a duration, and the reward rule under test prices every new commitment with the protocol's own integer formula. The renewal, return, arrival, duration and stake steps are fitted to the chain's record. How strongly validators respond to a change in reward is not yet measured, so it is varied from none to strong.

![The staking life cycle in model v0.8.0](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/fig2-model.png)

*SF1. Validators arrive, renew, leave and return, and each new commitment mints its reward from the rule under test.*

**How far to trust it.** v0.8.0 forecasts validator stake better than every simple forecast at 30, 90 and 180 days, with its largest lead at 180 days, the horizon over which reward policy acts. A held-back test on the period from Granite to Helicon, which no fit or choice has seen, is frozen and will be presented at Workshop 1.

**The method.** Parameter Selection Under Uncertainty, PSUU, runs every reward design across every condition and strength of response, reduces each run to measures, scores the measures against goals, and reads which parameter choices serve each goal with forests of decision trees and response curves. Every run has a twin under the chain's own rule on the same simulated future, so each difference is the design's effect alone.

**What ran.** 132,800 one-year runs from 18 November 2025 cover four designs: ACP-285's ramp started at the beginning of the year, the rule before it, a reward for tenure and a steeper duration curve, at outside yields from 3% to 10%. A second sweep adds the remaining reward parameters and market conditions.

**What it found.**

1. Started at the beginning of the year rather than at Helicon, ACP-285's ramp saves 13% of the issuance to validators' own stake and keeps 97% of their stake. Each AVAX issued holds about 12% more stake.
2. Scored against five proposed goals, the best minimum rate is 6% to 7%. Keeping 95% of the chain rule's stake and validators in nine runs out of ten needs about 8.5%, and meeting every threshold needs 9%. ACP-285's 7.5% sits between, so the thresholds you set decide the answer.
3. Each point by which the minimum rate falls saves about 5.5 points of issuance and gives up about 1.3 points of stake.
4. A higher base rate holds stake more cheaply than a tenure reward: about 4.0 AVAX of stake per AVAX issued along the minimum rate, against 2.3 along the tenure boost.
5. The outside yield decides whether validating pays. At 5% or more, after a 1.5% operating cost, validators earn less than their alternative under every design tested.
6. Bear, neutral and bull markets leave every result and ranking almost unchanged, because a market shifts a design and its comparison alike. In the protocol's own reward rule, the settings that score highest lower the maximum rate, which ACP-285 left at 12%.
7. A design moves stake only through how strongly validators respond to the reward. ACP-285's first five weeks are too few to measure it. The 42-fold swings in the AVAX price since 2021 bound it: the renewal response is below about 0.05 and the entry response below about 0.1, which rules out our stress level and the top of the range we swept.

![Issuance saved and validator stake kept by each design at one year](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/fig4-design-comparison.png)

*SF2. At one year, ACP-285's ramp started early saves about 13% of issuance and keeps about 97% of validator stake at every outside yield.*

## 3. Workshop 1 sets the goals that Milestone 3 scores against

Workshop 1 on Friday 13 November walks through the whole model, reviews three findings and turns the Foundation's goals into a written record. Every recommendation in Milestone 3 is scored against those goals, so the workshop is where the Foundation's judgement enters the research.

The memo proposes five goals: security holds, validators stay and stay spread, holders pay less, security per AVAX issued, and longer staking. Each has a measure and a threshold. The workshop asks the Foundation to confirm, replace or extend them, to set the thresholds it holds, and to say which goal it would most want to improve across the ranges the sweep produced.

| Minutes | Segment |
| --- | --- |
| 0 to 8 | Purpose, and a silent read of a two-page decision sheet |
| 8 to 23 | The model, traced through one validator's day, with the held-back test's result |
| 23 to 35 | Three findings and what would change each |
| 35 to 55 | Goals: your answers side by side, then objectives, measures, thresholds and their order |
| 55 to 60 | The record read back, actions and dates |

Three pre-reads reach you on Friday 6 November: the decision sheet, a whole-model explanation of about six pages and a one-page goals worksheet. We ask for the worksheet back by Wednesday 11 November, so that each person's first answer is their own.

## 4. Milestone 3 runs in two blocks and the code reaches you before the holidays

Milestone 3 delivers the Parameter Recommendation Report, the Scenario Playbook, the model code with its documentation, and Workshop 2. We propose two working blocks: 1 to 11 December 2026 and 4 to 15 January 2027. The code reaches you at the end of the first block, so you can run it over the break. Workshop 2 then shows how to run a scenario and read its result, and the final report follows your review.

The recommendations are scored against the goals, measures and thresholds we agree at Workshop 1 on 13 November. Each recommendation names its goal, the range or value we recommend, how confident we are, and the strength of validator response that would reverse it. The playbook gives one rule per market condition: if the condition holds, adjust this parameter in this direction, with the evidence behind the rule.

| Date | Outcome |
| --- | --- |
| Fri 13 Nov | Workshop 1 sets the goals and thresholds the recommendations are scored against |
| Fri 11 Dec | Draft report and playbook for your review. Model code transferred to your repository, with a clean-install guide |
| Fri 8 Jan | Workshop 2: you run a scenario and we read the results together |
| Fri 15 Jan | Final report and playbook delivered with your feedback worked in |

Three things would help us at Workshop 1. The first is the name of the person who will install and run the code. The second is your preferred date for Workshop 2. The third is the repository the code should be transferred to, and whether the Foundation wants it released publicly.

## What we need from you

1. Can Workshop 1 run for 60 minutes on 13 November, who from the Foundation will attend, and may we record it?
2. Do the five goals in the memo cover what the Foundation wants from staking rewards, or is one missing?
3. Which proposal should the first timed evaluation take? We propose your revenue-funded rewards, starting 2 November, with results within five business days.

## What comes next

| Date | What |
| --- | --- |
| 2 to 6 November | First timed evaluation: revenue-funded rewards |
| 6 November | Workshop 1 pre-reads sent |
| 11 November | Goals worksheet back from you |
| 13 November | Workshop 1, with the held-back test's result |
| 1 to 11 December | Milestone 3, first block |
| 4 to 15 January 2027 | Milestone 3, second block, and delivery |
