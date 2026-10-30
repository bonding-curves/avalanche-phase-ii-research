---
title: "2026-10-30-milestone-2"
description: "The agenda brief for the 30 October call: the chain's data since Helicon, Milestone 2 and the model, Workshop 1 on 13 November, and Milestone 3 in December and January."
date: 2026-10-30
status: submitted
tags: ["parameter-selection-under-uncertainty", "sensitivity-analysis", "model-structure"]
---

The Foundation's thresholds, the least outcome it accepts on each goal, choose ACP-285's minimum consumption rate in the [sensitivity analysis](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/), because the rate decides how much AVAX the network issues and validators' response decides the stake each AVAX saved costs. The call walks through the whole model and agrees the plans for Workshop 1 and Milestone 3.

## 1. Validators held more stake and renewed at the same rate after Helicon

The Helicon upgrade of 22 September 2026 allowed commitments of 48 hours and activated ACP-285. ACP-285 lowers the minimum consumption rate from 10% to 7.5% over 90 days, which at the supply counter of 26 October cuts a 48-hour stake's annualized reward rate from about 5.1% to 3.9% of stake a year.

Validators' own stake closed 26 October at 170.26M AVAX, 4.27M AVAX above its Helicon-day close, held by 590 active validators against 606.

![Figure 1](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/figure-01-f107.png)
*Figure 1. Validators' own stake fell 24.40M AVAX to a low on 8 October, then rose to close 26 October 4.27M AVAX above its Helicon-day level, held by 16 fewer validators.*

Short first cycles, of 48 hours to under 7 days, made 26% to 27% of each week's new validator commitments from 6 to 26 October.

![Figure 2](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/figure-02-f108.png)
*Figure 2. Nearly every short commitment since Helicon lasts exactly two days, so short commitments hold 8.7% of the stake committed since Helicon and 0.33% of its AVAX-days, an AVAX-day being one AVAX staked for one day.*

Stakes started since Helicon, delegations included, are promised 38,929 AVAX, or 3.5%, less than the old 10% minimum rate would pay. The stakes started on 26 October, mostly about 16 days long, earn a stake-weighted 4.70% of stake a year against 5.17% under the old rate.

![Figure 3](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/figure-03-f109.png)
*Figure 3. The saving against the old rate grows as the ramp proceeds, and stakes started on 15 and 20 October, when large validators committed for 79 to 365 days, make 19,204 AVAX of it.*

Of 320 validator nodes whose staking ended from Helicon to 12 October, 86.2% staked again within 14 days, twice the model's 7-day window, against 85.6% of 1,235 endings in the 90 days before Helicon.

![Figure 4](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/figure-04-f110.png)
*Figure 4. Renewal within 14 days held near 86% through the first three weeks of the ramp, while the 77 nodes that left after Helicon held 17.7M AVAX and the 61 that arrived brought 21.3M AVAX.*

Bitwise's BAVA exchange-traded fund started 25 validator commitments after Helicon, all 15.1 to 19.1 days long.

![Figure 5](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/figure-05-f111.png)
*Figure 5. No BAVA commitment since Helicon is shorter than the old 14-day minimum, and the three exchange-traded funds whose holdings are published daily held 6.15M AVAX together on 26 October.*

## 2. The Foundation's thresholds choose ACP-285's minimum rate

Model v0.8.0 simulates validators' own stake daily from 18 November 2025 with exact reward arithmetic and leaves out delegations, 20.8% of all stake at that origin.

The measured responses, 0.025 for renewal and 0.04 for entry, are the rises in the log-odds of renewing within 7 days and in the log arrival rate of new validators per percentage point of annualized reward rate gained against the rule before ACP-285. They treat a 1% rise in dollar reward from the AVAX price like one from the rate, which market sentiment specific to AVAX most threatens. Holding the Bitcoin or the Ether price fixed gives renewal 0.035 to 0.057 or 0.09 to 0.11, so the central 0.025 puts a design's stake cost at the low end.

1. At the measured responses and an outside yield of 5% a year, starting ACP-285's ramp on 18 November 2025 saves a median 12.8% of validators' one-year issuance and keeps 98.7% of their stake against a twin on the same draws under the chain's rule. The 10th to 90th percentiles over 50 paired runs are 11.6% to 15.4% saved and 95.3% to 99.9% kept, and the shares change little between runs whose twin's stake ends high and low ([2.6](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/#26-risk-surface-map)).
2. The minimum rate explains about 96% of the variance in issuance saved, and each percentage point it falls trades about 5.5 points of issuance saved for 1.3 points of stake ([2.5](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/#25-sensitivity-analysis)).
3. Combined utility, a weighted score of five goals, peaks at 0.77 at minimum rates of 6% to 6.5%, which pay a 48-hour stake about 3.3% to 3.6% of stake a year at the model's start. At least 90% of runs meet every threshold at once only at 9% to 9.5%, about 4.9% to 5.2% ([2.6](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/#26-risk-surface-map)).
4. At 180 days the model's continuous ranked probability score for validator stake is 27% below the best of six benchmarks, one-sided p = 0.04 ([2.4](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/#24-validation-confirmation)).
5. In paired model scenarios against the rule before ACP-285, ACP-285 issues 13.8% less and keeps 92.5% of stake at 5 years, and issues 16.1% less with 89.4% kept at 10 years ([2.6](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/#26-risk-surface-map)).

## 3. Workshop 1 sets the goals that Milestone 3 scores against

Workshop 1 on 13 November records the Foundation's goals, against which Milestone 3 scores every recommendation. The Foundation first sets a threshold for each of the [five working goals](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/#23-kpi-computation) and then weights them. The workshop also hears the held-back test of the model from 19 November 2025 to Helicon.

## 4. Milestone 3 runs in two blocks and ends about 15 January

Milestone 3 delivers the Parameter Recommendation Report, the Scenario Playbook with one rule per market condition, the documented model code, and Workshop 2. The Milestone 2 code is on the Foundation's `milestone-2` branch, with the market sweep on branch `m2-market-sweep`, and the Milestone 3 code arrives on 11 December.

## 5. Three answers from the Foundation set the next two weeks

1. Can Workshop 1 run for 60 minutes, who from the Foundation will attend, and may we record it?
2. Which revenue source should the evaluation of revenue-funded rewards assume?
3. Who at the Foundation will run the model code, and does transfer to its private repository meet the agreement's open-source release term?

## 6. The next dates run from 2 November to 15 January

| Date | What happens | Owner |
| --- | --- | --- |
| 2 to 6 November | Evaluation of revenue-funded rewards | BCRG |
| 3 to 6 November | Renewal response measured within nodes across months | BCRG |
| 6 November | Workshop 1 pre-reads and goals worksheet sent | BCRG |
| 11 November | Goals worksheets returned | Foundation |
| 13 November | Workshop 1 sets thresholds and weights | Foundation and BCRG |
| 1 to 11 December | Milestone 3 first block, draft report and code | BCRG |
| 4 to 15 January 2027 | Milestone 3 second block | BCRG |
| 8 January 2027 | Workshop 2, where the Foundation runs a scenario | Foundation and BCRG |
| 15 January 2027 | Final report and playbook | BCRG |
