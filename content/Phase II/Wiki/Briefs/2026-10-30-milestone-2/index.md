---
title: "2026-10-30-milestone-2"
description: "The agenda brief for the 30 October call: the chain's data since Helicon, Milestone 2 and the model, Workshop 1 on 13 November, and Milestone 3 in December and January."
date: 2026-10-30
status: submitted
tags: ["parameter-selection-under-uncertainty", "sensitivity-analysis", "model-structure"]
---

The reward setting decides how much AVAX Avalanche issues, and validators' response to the reward decides how much stake each AVAX saved costs, as the [Milestone 2 Sensitivity Analysis Report](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/) shows. On this call we walk through the whole model, as the Foundation asked on 16 October, and agree the plan for Workshop 1 on 13 November and for Milestone 3 in December and January.

## 1. Validators hold more stake and renew as before five weeks after Helicon

The Helicon upgrade activated ACP-285 on 22 September 2026. ACP-285 lowers the minimum consumption rate, a parameter of the reward formula, over 90 days ending 21 December 2026. The rate falls from 10%, which at the supply of 26 October 2026 pays a 48-hour stake about 5.4% of its stake a year, to 7.5%, which pays about 4.1%. Helicon also lets a validator commit for as little as 48 hours. Every number on validators since Helicon comes from our record of the P-Chain to the close of 26 October 2026, 23:59:59 UTC.


Validators' own stake closed 26 October at 170.26M AVAX, 4.27M AVAX above the Helicon-day close, while active validators fell from 606 to 590. The average validator therefore holds more AVAX than on Helicon day.

![Figure 1](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/figure-01-f107.png)
*Figure 1. Validators' own stake fell to a low on 8 October and then closed 26 October 4.27M AVAX above its Helicon-day level, held by 16 fewer validators.*

Short first cycles, meaning 48 hours to under 7 days, made 26% to 27% of each week's new validator commitments from 6 to 26 October, and hold 0.33% of AVAX-days committed since Helicon. An AVAX-day is one AVAX staked for one day, so short first cycles are frequent but carry little of the network's committed stake.

![Figure 2](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/figure-02-f108.png)
*Figure 2. Since 6 October about a quarter of each week's new validator commitments take a short first cycle, and since Helicon those commitments hold 0.33% of the AVAX-days committed.*

Since Helicon, ACP-285 has cut promised rewards by 38,929 AVAX, 3.5% of the old rule's total, and stakes started on 26 October earn 4.70% of stake a year under ACP-285, against 5.17% under the old 10% floor.

![Figure 3](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/figure-03-f109.png)
*Figure 3. Stakes started since Helicon are promised 38,929 AVAX less than the old 10% floor would pay, and the saving grows on the days large validators commit for long periods.*

Of 320 validator node endings from Helicon to 12 October, 86.2% staked again within 14 days, against 85.6% of 1,235 endings in the 13 weeks before.

![Figure 4](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/figure-04-f110.png)
*Figure 4. Renewal within 14 days held near 86% of validator node endings through the first weeks of the ramp, while more but smaller nodes left than before Helicon.*

Bitwise's BAVA exchange-traded fund started 25 validator commitments after Helicon, all 15.1 to 19.1 days long, and its 11 validators held 66.9% of its 2.67M AVAX.

![Figure 5](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/figure-05-f111.png)
*Figure 5. Every BAVA validator commitment since Helicon is longer than the old 14-day minimum, and the three funds recorded daily held 6.15M AVAX on 26 October.*

## 2. The reward setting sets issuance and the response sets its stake cost

Model v0.8.0 simulates every staking period one day at a time from the chain's state on 18 November 2025. Each day it renews or ends each period, returns departed nodes, adds new nodes, chooses each stake and duration, and prices every new period with the protocol's own reward arithmetic, which matches 3,769,919 of 3,769,920 stakes started before 19 November 2025. Parameter Selection Under Uncertainty, PSUU, runs each reward design across market conditions and strengths of validator response, scores each run against goals, and compares it with a twin run under the chain's rule on the same random draws. The strength of validator response to reward was swept from 0 to 0.1. On 28 October it was first measured from AVAX price swings, assuming a dollar of reward from price weighs like a dollar from the rate.


1. The first measured responses are about 0.025 for renewal and 0.04 for entry, in log-odds or log arrival rate per percentage point of the annual reward rate on a 30-day stake. At those responses, ACP-285's ramp started early to 7.5% saves 12.8% of one year's issuance against the chain's rule and keeps 98.7% of validator stake, over 50 paired runs at a 5% yearly outside yield ([summary](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/)).
2. The design's setting explains about 96% of the variance in issuance saved where that estimate converged, and each percentage point the minimum consumption rate falls saves about 5.5 percentage points of one year's issuance and gives up about 1.3 percentage points of validator stake ([2.5](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/#25-sensitivity-analysis)).
3. Over the swept range of response, the best weighted score falls at minimum consumption rates of 6% to 7%, and every proposed threshold is met in 90% of runs only near 9% to 9.5%. ACP-285's 7.5% sits between, so the thresholds the Foundation sets choose the rate ([2.6](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/#26-risk-surface-map)). A minimum consumption rate of 6% to 7% pays a 48-hour stake about 3.3% to 3.8% of its stake a year, and 9% to 9.5% pays about 4.9% to 5.2%.
4. The model forecasts validator stake better than six simple benchmarks at 30, 90 and 180 days, with a score 27% lower than the best benchmark's at 180 days ([2.4](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/#24-validation-confirmation)).
5. In model scenarios that hold the 2024 to 2025 arrival pattern fixed, ACP-285 against the rule before it issues 13.8% less with 92.5% of stake kept at 5 years, and 16.1% less with 89.4% kept at 10 years ([2.2](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/#22-simulation-execution)).

## 3. Workshop 1 sets the goals that Milestone 3 scores against

Workshop 1 on Friday 13 November turns the Foundation's goals into a written record, and every recommendation in Milestone 3 is scored against that record. Milestone 2 proposes five working goals: security holds, validators stay and stay spread, holders pay less, security per AVAX issued, and longer staking. Each goal has a measure and a threshold.

The workshop takes two decisions in order. The Foundation first sets the threshold each goal must meet, which is the least outcome it will accept. It then weights the goals for the trade-offs above those thresholds. A worksheet records, for each goal, the objective, the measure, the threshold, its weight and the reason, and the record is read back before the call ends. The held-back test, which forecasts stake from Granite on 19 November 2025 to Helicon with a rule frozen on 27 October before any score was computed, is presented at the same workshop.


Three pre-reads reach the Foundation on Friday 6 November: a two-page decision sheet, a whole-model explanation and a one-page goals worksheet. We ask for the worksheet back by Wednesday 11 November, so that each person's first answer is their own.

## 4. Milestone 3 runs in two blocks and ends about 15 January

Milestone 3 delivers the Parameter Recommendation Report, the Scenario Playbook, the model code with its documentation, and Workshop 2. We propose two working blocks, 1 to 11 December 2026 and 4 to 15 January 2027. The Milestone 2 code is already on the Foundation's repository, on branch `milestone-2`. The Milestone 3 code and a clean-install guide follow at the end of the first block, so the Foundation's team can run the model over the break.

Each recommendation names its goal, the range or value recommended, our confidence in it, and the strength of validator response that would reverse it. The playbook gives one rule per market condition, which says which parameter to adjust and in which direction, with the evidence behind the rule.


| Date | Outcome |
| --- | --- |
| Fri 13 Nov | Workshop 1 sets the goals and thresholds |
| Fri 11 Dec | Draft report, playbook and model code with its install guide |
| Fri 8 Jan | Workshop 2, in which the Foundation runs a scenario |
| Fri 15 Jan | Final report and playbook with the Foundation's feedback |

## 5. Three answers from the Foundation set the next two weeks

1. Can Workshop 1 run for 60 minutes on 13 November, who from the Foundation will attend, and may we record it?
2. The first timed evaluation, revenue-funded rewards, starts on 2 November with results within five business days. Which revenue source should it assume?
3. Who at the Foundation will install and run the model code, and does transfer to the Foundation's private repository meet the agreement's open-source release term?

## 6. The next dates run from 2 November to 15 January

| Date | What | Owner |
| --- | --- | --- |
| 2 to 6 November | First timed evaluation, revenue-funded rewards | BCRG |
| 6 November | Workshop 1 pre-reads sent | BCRG |
| 11 November | Goals worksheet returned | Foundation |
| 13 November | Workshop 1, with the held-back test's result | Foundation and BCRG |
| 1 to 11 December | Milestone 3, first block, ending with the draft report and code | BCRG |
| 8 January 2027 | Workshop 2 | Foundation and BCRG |
| 15 January 2027 | Final report and playbook | BCRG |
