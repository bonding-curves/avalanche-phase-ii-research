---
title: "Sensitivity Analysis Report"
description: "Milestone 2 experiments on issuance, validator participation and the reward settings that trade between them."
date: 2026-10-30
status: draft
kind: deliverable
reader: "Avalanche Foundation and Ava Labs researchers and decision makers"
question: "What do the Milestone 2 experiments establish about reward designs and the choices that follow?"
---

Date: 30 October 2026\
To: Avalanche Foundation and Ava Labs\
From: Bonding Curve Research Group (BCRG)\
Subject: Milestone 2 simulation and analysis

Starting ACP-285's ramp early saves validator reward promises in the central one-year simulation while retaining most validator own stake. The size of that trade-off depends on behavioural responses, the comparison schedule and the evaluation criteria.

The experiment starts on 18 November 2025. Its proposed formula begins a 90-day ramp toward a 7.5% minimum consumption rate. Its reference follows the historical schedule and starts ACP-285 at Helicon on 22 September 2026. Both eventually adopt the lower rate, so the comparison measures the effect of starting earlier.

Milestone 2 also varies formulas, response assumptions and outside conditions to examine how that result changes. The [modeling memo](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/methodology) explains the system. The eight sections below follow the [grant's Milestone 2 deliverables](/Phase-II/Milestones/Milestone-0/Signed-Grant-Agreement), separating completed analysis from workshop and operational work still to demonstrate.

## 2.1 PSUU Infrastructure

Parameter selection under uncertainty, or PSUU, compares reward settings across uncertain behaviour and outside conditions. Each design runs beside a **twin**, the historical chain schedule with the same input state, parameter draw and random seed. Receipts bind experiment settings to input and output identities.

A repeatability check matched 28,672 values in 512 repeated rows. The [central-case replay](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/report-reproduction/README.md) now independently rebuilds the reported comparison, including all 100 paths, the percentile table and trajectory figure. Other historical sweeps still need separate input artifacts. The [evidence guide](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence) identifies them.

Execution used BCRG's compute server. The agreement's cloud-compute requirement remains distinct from the completed simulations.

## 2.2 Simulation Execution

Two one-year sweeps record 199,887 runs, including references. They compare issuance and validator participation across formulas, response strengths and outside conditions.

| Experiment | Recorded size | Main variation |
| --- | ---: | --- |
| First one-year sweep | 132,800 runs | Ramp, pre-ACP-285, duration curve and tenure boost. Outside yields 3%, 5%, 7% and 10%. Responses 0–0.1, plus 0.3 stress anchors |
| Second one-year sweep | 67,087 runs | Broader rates, duration limits and bear, neutral and bull scenarios |
| Central comparisons | 50 pairs per design | Specific settings at fixed working responses and 5% outside yield |
| Five-year sweep | 4,096 pairs | Ramp settings and uncertain responses |
| Ten-year sweep | 8,192 pairs | Ramp and duration-curve scenarios |

The central comparison uses renewal response 0.025 and entry response 0.04 per percentage point of annual yield. These working assumptions make a one-point yield reduction lower an 80% renewal probability to about 79.6% and expected entry by about 4%. Outside yield is 5% annually.

| Outcome at one year | Median paired share | 10th–90th percentile across 50 pairs |
| --- | ---: | ---: |
| Validator reward promises saved | 12.8% | 11.6%–15.4% |
| Validator own stake retained | 98.7% | 95.3%–99.9% |
| Active validators retained | 97.0% | 96.0%–97.6% |

Saved issuance is the reduction in cumulative new validator reward promises relative to the twin. Retained stake and count compare their terminal values. These are percentiles of paired ratios, describing simulated variation under fixed response settings. Delegated issuance is omitted. The [central-case evidence](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence#central-case) supplies exact values and source identities.

Figure 1 compares simulated levels with the later record. Over their shared dates, the chain moves toward fewer, larger validators, while the simulation retains more validators with less own stake. This discrepancy motivates further work on participation and stake choices.

![Recorded validator stake, count and supply alongside the central simulated paths.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/central-record-comparison.png)
*Figure 1. Recorded paths through 26 October 2026 and 50 paired runs from 18 November 2025. Lines are simulation medians and bands span the 10th to 90th percentiles, at renewal response 0.025 and entry response 0.04. The reference adopts ACP-285 at Helicon. Simulated supply includes validator issuance and a burn assumption, while delegated issuance is omitted. Recorded endpoint labels refer to 26 October, while simulated endpoints refer to 18 November. The overlay is descriptive and does not replace the separate held-back evaluation.*

## 2.3 KPI Computation

Fourteen reported measures are computed at 180 and 365 days in the first sweep. Nine expressions feed five working goals. BCRG's thresholds make the conditions for a satisfactory comparison explicit.

The **Nakamoto coefficient** counts the fewest validator nodes holding more than one third of own stake. It measures node concentration, without identifying shared ownership. **Return margin** subtracts outside yield and an assumed annual operating cost of 1.5% of stake from annualized rewards.

| Working goal | Acceptance conditions |
| --- | --- |
| G1 Stake participation | Retain at least 95% of twin stake. Worst 30-day fall at most two percentage points deeper |
| G2 Validator participation and distribution | Retain at least 95% of validators. Lose at most one node in the Nakamoto coefficient and one percentage point of annual return margin |
| G3 Issuance and inflation | Save some validator issuance. Keep the net-inflation proxy at or below 5% annually |
| G4 Stake per AVAX issued | Retain at least as much own stake per unit of promised issuance as the twin |
| G5 Duration | Retain at least 99% of twin stake-weighted duration |

The inflation proxy uses fixed burn and omits delegated issuance, so it is narrower than network-wide AVAX inflation. Duration changes reflect the mix of participants because individual duration choices do not yet respond to rewards.

A **utility** maps a measure onto a preference scale from zero to one. The combined score weights G1–G4 equally and G5 at half their weight. The all-goal pass share counts runs meeting every threshold. Scores rank trade-offs, while pass shares measure satisfaction of the stated conditions. These are BCRG's exploratory preferences, awaiting Foundation confirmation. [Definitions and mappings](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/methodology#72-goals-guide-which-outcomes-the-experiments-measure).

## 2.4 Validation Confirmation

Development forecasts perform better for own stake than for validator count. Fitted only on observations available at each origin, the model is compared with six simple benchmarks using the continuous ranked probability score, or CRPS. This score evaluates the forecast distribution, with lower values better.

| Horizon | Origins | Model stake score | Best benchmark | Coverage of nominal 80% stake interval |
| --- | ---: | ---: | ---: | ---: |
| 30 days | 19 | 4.41 | 5.38 | 57.9% |
| 90 days | 18 | 5.15 | 5.69 | 55.6% |
| 180 days | 17 | 5.54 | 7.54 | 82.4% |

Scores are scaled by the pre-origin mean absolute daily change. At 180 days, the stake score is 26.6% below the best benchmark, with a corrected one-sided p-value of 0.0397. Short-horizon intervals cover too few realized outcomes. Validator count ranks third at 30 days and second at 90 and 180 days. Figure 2 shows both outputs, using the [committed development results](https://github.com/AVL-Foundation/ext-bcrg-validator-research/tree/model-v0.8.0/results/model-v0.8.0-selection).

![Forecast scores against six benchmarks](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/forecast-scores.png)
*Figure 2. Scaled CRPS for stake and validator count at three horizons. Blue is v0.8.0, and lower is better. The model leads the six benchmarks for stake, while a benchmark leads for count. Each origin uses a 200-run forecast distribution. Displayed scores average across eligible development origins.*

Reported level correlations of about 0.79–0.83 do not demonstrate the agreement's greater-than-90% criterion. The Granite-to-Helicon held-back evaluation also remains outstanding. Development forecast skill and numerical reproduction provide evidence about different properties of the model. Neither establishes the causal reward response used for policy comparisons.

## 2.5 Sensitivity Analysis

Within the ramp experiment, the minimum consumption rate explains most variation in issuance saved. Its rank correlation is about −0.98, and reported first-order Sobol variance shares are about 0.95–0.97 where convergence supports them. Participation depends more strongly on behavioural responses and simulation randomness.

Of 512 Sobol index sets, 310 pass convergence. None of the 32 stake-retention sets pass, preventing a precise variance allocation for stake. Repeated settings suggest stochastic variation accounts for roughly 40%–52% of stake-retention variance in the examined cases. These counts describe this report's analysis slice, rather than every index set produced during Milestone 2.

Figure 3 compares settings across goals. Ramp designs gain utility on issuance and efficiency. Duration-curve and tenure-boost alternatives retain more participation under the working evaluation.

![Goal utilities and combined score for four reward designs at one year.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/goal-utilities.png)
*Figure 3. Mean utilities for 16,384 design runs at one year, with 4,096 per design family. Cells pool outside yields of 3%, 5%, 7% and 10% annually and renewal and entry responses from 0 to 0.1. The combined score weights the first four goals equally and duration at half their weight. A utility is a preference score. It is distinct from the share passing a threshold. Source: the included frozen goal-utility aggregates.*

The highest mean combined score among the displayed setting bins is about 0.772 for minimum rates from 6% to below 6.5%. That bin pools all four outside yields and responses from 0 to 0.1. It is a weighted preference result, not the rate range with the highest all-goal pass share. The [frozen aggregates](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/goal-utilities.csv) preserve the exact scores and populations.

Figure 4 returns to outcome units: larger issuance savings generally accompany lower retained stake. Its black marker isolates the fixed working-response comparison from the broader sweep.

![Issuance saved against validator stake retained across ramp settings.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/issuance-stake-tradeoff.png)
*Figure 4. First-sweep ramp results at one year. Teal points are half-point minimum-rate bin means, with shaded 10th to 90th percentiles of stake retained. The black point and error bars show simulated medians and marginal 10th to 90th percentiles across 50 pairs at the preliminary working responses and 5% annual outside yield. Both comparisons use the historical reward formula as the reference and an early ramp start. The inherited “measured” label denotes preliminary regression-informed response settings. Source: the existing sweep and central-case artifacts.*

Figure 5 partitions the independent ramp runs by minimum rate and renewal response. Its terminal groups show where the working thresholds pass more often. The splits summarize this sample and should not be treated as exact policy boundaries.

![Decision tree showing where sampled runs meet every working goal.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/decision-tree.png)
*Figure 5. Classification tree for 4,096 independent one-year ramp runs from the first sweep, pooling four outside yields and renewal and entry responses from 0 to 0.1. Minimum consumption rate supplies most splits. One lower-rate branch also splits on renewal response at 0.041. Boxes show run counts and the share meeting every working threshold. Leaf shares differ from shares pooled over all responses. The marked “measured” response is a preliminary regression-informed setting. Source: the [included figure manifest](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/figure-manifest.json).*

## 2.6 Risk Surface Map

Near the working response assumptions, most sampled runs pass every goal at minimum rates from 7.5% to below 8.0%. Broadening the response window reduces that share. Figure 6 shows the full bands and their denominators.

![All-goal pass shares and integer counts across ten minimum-rate bands and two behavioural response windows.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/conditional-goal-pass.png)
*Figure 6. Share meeting all five working goals in the first sweep's independent A and B blocks at 365 days. Each cell shows the pass percentage and passes/runs. Bands include their lower boundary and exclude their upper boundary. Outside yields of 3%, 5%, 7% and 10% annually are pooled. The response windows overlap. These sample shares depend on BCRG's thresholds and do not measure confidence in a response estimate. Source: the [included frozen counts](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/numerical-evidence.json).*

The near-central window uses renewal response 0.01–0.04 and entry response 0.02–0.06. The wider window uses renewal 0.01–0.06 and entry 0–0.1. At minimum rates from 7.5% to below 8.0%, 48 of 54 near-central runs pass (88.9%), compared with 140 of 206 wider-window runs (68.0%). At 6% to below 6.5%, those shares are 7 of 50 (14.0%) and 20 of 207 (9.7%). The samples overlap and pool four outside yields. These are conditional sample shares, not probabilities that a particular response estimate is correct. [Full counts](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence#conditional-goal-regions).

Together, the score heatmap and pass map expose a decision: the best weighted average can require more participation loss than the chosen safeguards allow. Their response populations differ, so the score and pass percentages must retain their own denominators. Neither establishes a universal optimum at 7.5%.

Pass shares fall above 9.5% because the historical twin begins lowering its own rate at Helicon. A higher-rate design can then issue more than its twin and fail the saving goal. Comparator timing therefore shapes both ends of the satisfactory range.

Response estimates remain specification-sensitive. Bitcoin-controlled renewal estimates are about 0.035–0.057, while Ether-controlled alternatives reach 0.09–0.11. Some intervals include zero. The 0.01–0.06 working range is an exploration range, rather than a confidence interval. [Regression outputs](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence#response-estimates).

The longer-horizon comparison reverses the perspective: historical-schedule ACP-285 is evaluated against near-unchanged minimum rates of 9.75%–10%. Historical-schedule ACP-285 saves about 14% of validator reward promises at five years and 16% at ten years, with lower retained stake. These are separate scenarios from the central early-start comparison. Their forecast validity and the remaining budget's lifetime remain unestablished. [Comparator definitions](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence#longer-horizons).

Available supply also limits interpretation. The broader sweep records one stopped run when stake reached the supply counter and 11,957 runs above half that counter. Those regions require participation and available-supply feedback before recommendations.

## 2.7 Workshop #1

The workshop should settle the Foundation's objectives, measures, participation safeguards and preference weights. Current results make those choices visible and can be reevaluated under revised criteria.

The proposed workshop date is 27 November. Shawn and Eric have agreed to move the preceding model/results review to next week, with the exact invitation still to confirm. The [brief](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/brief) sets out the questions and proposed sequence. Workshop completion is still an open deliverable.

## 2.8 Collaborative Mechanism Design

The released reward interface supports rate schedules, duration curves and completed-period multipliers. New designs can reuse the lifecycle simulation and measures, with neutral-setting tests against the chain formula.

A next proposal could change minimum and maximum rates together, change the duration premium or introduce revenue-funded rewards. Revenue funding needs a defined revenue stream and an explicit shortfall policy. It remains a development extension. The agreement's under-five-business-day turnaround should be demonstrated by evaluating one specified proposal end to end.

The next research priorities are reward-response estimation, the changing entrant mix and reward-responsive duration. Held-back evaluation, delegated accounting and available-supply feedback address separate evidence gaps. Recommendations should follow the Foundation's chosen criteria and these improvements. The [evidence guide](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence) preserves the sources and reproducibility boundaries.
