---
title: "Sensitivity Analysis Report"
description: "Milestone 2 experiments on issuance, validator participation and the reward settings that trade between them."
date: 2026-10-29
status: draft
kind: deliverable
reader: "Avalanche Foundation and Ava Labs researchers and decision makers"
question: "What do the Milestone 2 experiments establish about reward designs and the choices that follow?"
---

Date: 29 October 2026\
To: Avalanche Foundation and Ava Labs\
From: Bonding Curve Research Group\
Subject: Milestone 2 simulation and analysis

## Introduction

Starting ACP-285's ramp before Helicon reduces issuance in the central one-year experiment. The comparison follows the proposed early start beside a reference formula that adopts ACP-285 on its historical date. The reduction serves the Foundation's aims of lowering inflation and extending Avalanche's finite issuance budget. Its participation effect depends on how validators respond.

[ACP-285](https://github.com/avalanche-foundation/ACPs/blob/b80ea34682b419603f0241f114560dea5d61e03a/ACPs/285-reduce-minimum-consumption-rate/README.md) lowers the minimum consumption rate from 10% to 7.5% while keeping the maximum at 12%. These are parameters of the reward formula. At the experiment's starting supply counter, a 48-hour stake earns about 4.1% of stake a year at the 7.5% minimum, compared with about 5.5% at 10%. The [methodology memo](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/methodology) explains the formula, the statistical model and the evaluation methods.

Milestone 2 compares formulas through paired simulations of validators' own stake. A **twin** uses the chain's formula under the same conditions and random draws. Issuance saved is the percentage reduction in cumulative rewards promised to validator stake, relative to that twin. Stake retained is the design's own stake at the horizon as a percentage of the twin's. Delegations are outside the model.

The [grant agreement](/Phase-II/Milestones/Milestone-0/Signed-Grant-Agreement) calls for a Sensitivity Analysis Report covering all key parameters. Quantitative findings use BCRG's working assumptions and goals. The Foundation can use them to choose its own criteria at the workshop.

## 2.1 PSUU Infrastructure

The experiment pipeline makes comparisons repeatable by binding a design, its inputs and its outputs to a receipt. Parameter selection under uncertainty, or PSUU, varies reward settings alongside uncertain behaviour and outside conditions. It then turns the resulting trajectories into measures and goal scores.

| Pipeline component | Role |
| --- | --- |
| Experiment specification | Names the formulas, input ranges, horizons and repeated runs |
| Pinned data | Fixes the historical input copies by byte hash |
| Paired runner | Simulates each design beside its twin |
| Analysis | Computes measures, utilities and sensitivity results |
| Receipt | Records code identity, inputs and output hashes |

A repeat check reproduced all 28,672 checked values in 512 repeated rows. This establishes repeatability for that check. Full simulation reproduction from a fresh clone also needs the historical input snapshots, which are not yet distributed. The [evidence guide](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence) separates these requirements.

The pipeline ran on BCRG's compute server. The agreement specifies cloud compute. That infrastructure requirement remains distinct from the completed sweep execution.

## 2.2 Simulation Execution

Two one-year sweeps produced 199,887 runs, including their chain-reference runs. They vary reward settings, outside yields and behavioural responses. Renewal response changes the log-odds of renewing per percentage point of annual yield on a standard 30-day stake. Entry response changes the log arrival rate on the same basis. A one-point yield reduction at the working responses lowers an 80% renewal probability to about 79.6% and expected entry by about 4%.

| Experiment | Size | What varies |
| --- | ---: | --- |
| First one-year sweep | 132,800 runs | Four design families plus chain references, outside yields of 3%, 5%, 7% and 10% annually, responses from 0 to 0.1 and stress anchors at 0.3 |
| Second one-year sweep | 67,087 runs | Broader reward parameters and bear, neutral and bull conditions |
| Central comparison | 50 pairs per design | Specific ramp floors at fixed working responses and 5% outside yield |
| Five-year sweep | 4,096 pairs | Ramp settings, response uncertainty and outside yields |
| Ten-year sweep | 8,192 pairs | Ramp and duration-curve scenarios |

The first sweep compares ACP-285's ramp, the pre-ACP-285 formula, an alternative duration curve and a tenure boost against separate historical chain references. The second adds independently chosen rates and duration limits. A duration curve changes how rewards rise with commitment length, while a tenure boost rewards repeated completed periods.

The central comparison starts on 18 November 2025, ten months before Helicon. Its proposed formula begins ACP-285's 90-day ramp immediately. Its twin follows the historical protocol schedule, adopting ACP-285 on 22 September 2026. The result measures the effect of an early start over one year, rather than ACP-285 against a permanently unchanged formula.

At working renewal and entry responses of 0.025 and 0.04, and an outside yield of 5% a year, the central comparison gives:

| Outcome at one year | Median paired share | 10th–90th percentile across 50 pairs |
| --- | ---: | ---: |
| Validator issuance saved | 12.8% | 11.6%–15.4% |
| Validator own stake retained | 98.7% | 95.3%–99.9% |

These percentiles describe variation between simulated pairs. They are not confidence intervals for a causal effect or for the median. The [central-case evidence](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence#central-case) identifies the underlying comparison and summary.

Figure 1 compares the central simulated paths with the recorded population. The record moves toward fewer, larger validators, while the runs retain more validators with less own stake. This descriptive comparison shows a model limitation alongside the paired policy estimates.

![Recorded validator stake, count and supply alongside the central simulated paths.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/central-record-comparison.png)
*Figure 1. Recorded paths through 26 October 2026 and 50 paired runs from 18 November 2025. Lines are simulation medians and bands span the 10th to 90th percentiles, at renewal response 0.025 and entry response 0.04. The reference adopts ACP-285 at Helicon. Simulated supply includes validator issuance and a burn assumption, while delegated issuance is omitted. The overlay is descriptive and does not replace the separate held-back evaluation.*

## 2.3 KPI Computation

Every run is evaluated using explicit measures rather than a single preferred outcome. The first sweep computes fourteen reported measures at 180 and 365 days. Nine expressions feed five working goals. The **Nakamoto coefficient** is the fewest validator nodes holding more than one third of validator own stake. The **return margin** subtracts the outside yield and an assumed annual operating cost of 1.5% of stake from validators' annualized reward rate.

| Working goal | Main acceptance conditions |
| --- | --- |
| G1 Stake participation | Retain at least 95% of the twin's stake and avoid a worst 30-day fall more than two percentage points deeper |
| G2 Validator participation and distribution | Retain at least 95% of validators, lose at most one node in the Nakamoto coefficient and lose at most one percentage point of annual return margin |
| G3 Issuance and inflation | Save some validator issuance and keep net inflation below the working 5% annual limit on total supply |
| G4 Stake per AVAX issued | Retain at least as much stake per unit of issuance as the twin |
| G5 Staking duration | Retain at least 99% of the twin's stake-weighted duration |

The Nakamoto coefficient measures node-level concentration, without identifying common ownership. The duration measure captures changes in the mix of periods. Individual duration choices do not yet respond to reward incentives. The net-inflation measure subtracts a fixed burn assumption from simulated validator issuance. It omits delegated issuance, so it does not represent network-wide AVAX inflation.

A **utility score** maps each measure to a preference scale from zero to one. The working combined score weights G1–G4 equally and G5 at half their weight. A **pass rate** instead counts how often every threshold is met. These answer different questions: which outcomes rank highest and which outcomes meet minimum conditions.

BCRG supplied these thresholds and weights for exploration. They are not confirmed Foundation preferences. The Foundation's stated objectives are lower inflation, a longer issuance budget and the potential for longer staking durations. Stake and count thresholds help examine participation risks alongside those objectives.

## 2.4 Validation Confirmation

Development tests support the model more strongly for validator stake than for validator count. At each historical forecast origin, the model is fitted on earlier observations and compared with six simple benchmarks. The continuous ranked probability score, CRPS, evaluates the full distribution of runs. Lower scores are better.

| Horizon | Forecast origins | Model stake score | Best benchmark stake score | Realized coverage of the nominal 80% stake interval |
| --- | ---: | ---: | ---: | ---: |
| 30 days | 19 | 4.41 | 5.38 | 57.9% |
| 90 days | 18 | 5.15 | 5.69 | 55.6% |
| 180 days | 17 | 5.54 | 7.54 | 82.4% |

The scores are scaled by the mean absolute daily change before each origin. At 180 days, the model's score is 26.6% below the best benchmark's, with a corrected one-sided p-value of 0.0397. Its short-horizon intervals cover too few outcomes. The validator-count forecast ranks third at 30 days and second at 90 and 180 days.

Figure 2 shows both outputs, so the stronger stake result can be assessed alongside the count result. The [committed development evidence](https://github.com/AVL-Foundation/ext-bcrg-validator-research/tree/model-v0.8.0/results/model-v0.8.0-selection) contains the original scores.

![Forecast scores against six benchmarks](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/forecast-scores.png)
*Figure 2. Scaled CRPS for stake and validator count at three horizons. Blue is v0.8.0, and lower is better. The model leads the six benchmarks for stake, while a benchmark leads for count. Scores average 200 model runs at each eligible development origin.*

The agreement names a greater-than-90% correlation criterion. The reported level correlations are about 0.79–0.83, so that criterion has not been demonstrated. Forecast scoring supplies additional scientific evidence, rather than establishing that the contractual criterion has been met.

The separate held-back evaluation from Granite to Helicon has no completed verdict in this package. Neither the development forecast scores nor shared random draws validate the preliminary reward-response estimates. Errors shared by a design and its twin can still affect their counterfactual comparison.

## 2.5 Sensitivity Analysis

The minimum consumption rate explains most of the variation in issuance saved within the ramp experiment. Participation is more sensitive to how validators respond and to stochastic variation.

| Analysis | Supported interpretation |
| --- | --- |
| Rank correlations | The ramp's minimum rate correlates at about −0.98 with issuance saved in the reported one-year slice |
| Sobol variance estimates | The minimum rate's first-order index for issuance saved is about 0.95–0.97, with convergence qualifications |
| Random forests | The minimum rate and renewal response are important predictors of the working combined score |
| Classification trees | Conditional splits describe regions where the working thresholds are met more often |

Of 512 sets of Sobol indices, 310 passed the convergence check. None of the 32 stake-retention sets passed, so a precise percentage allocation of stake variation to individual inputs is not supported. Repeated design points estimate that stochastic variation accounts for roughly 40%–52% of stake-retention variance in the examined cases.

The maximum consumption rate also matters because it prices longer commitments. ACP-285 leaves that parameter unchanged. Testing the minimum and maximum together therefore answers a different design question from lowering the minimum alone.

Figure 3 compares the mechanism settings across all five working goals and their combined score. The ramp scores better on issuance and efficiency, while the duration curve and tenure boost score better on participation. These differences depend on the working utility mappings and weights.

![Goal utilities and combined score for four reward designs at one year.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/goal-utilities.png)
*Figure 3. Mean utilities for 16,384 design runs at one year, with 4,096 per design family. Cells pool outside yields of 3%, 5%, 7% and 10% annually and renewal and entry responses from 0 to 0.1. The combined score weights the first four goals equally and duration at half their weight. A utility is a preference score. It is distinct from the share passing a threshold. Source: the included frozen goal-utility aggregates.*

Figure 4 expresses the ramp's trade-off in the original outcome units. Saving more issuance generally accompanies lower retained stake across the sampled settings. The fixed working-response comparison sits above the wider sweep's average stake retention near the same minimum rate.

![Issuance saved against validator stake retained across ramp settings.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/issuance-stake-tradeoff.png)
*Figure 4. First-sweep ramp results at one year. Teal points are half-point minimum-rate bin means, with shaded 10th to 90th percentiles of stake retained. The black point and error bars show simulated medians and marginal 10th to 90th percentiles across 50 pairs at the preliminary working responses and 5% annual outside yield. Both comparisons use the historical reward formula as the reference and an early ramp start. Source: the existing sweep and central-case artifacts.*

Figure 5 shows which combinations of minimum rate and renewal response are associated with meeting every working goal. Follow each yes-or-no branch to a group of runs. The pass share at the end describes that group under BCRG's thresholds. The splits summarize the sampled simulations and are not exact policy boundaries.

![Decision tree showing where sampled runs meet every working goal.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/decision-tree.png)
*Figure 5. Classification tree for 4,096 independent one-year ramp runs from the first sweep, pooling four outside yields and renewal and entry responses from 0 to 0.1. Minimum consumption rate supplies most splits. One lower-rate branch also splits on renewal response at 0.041. Boxes show run counts and the share meeting every working threshold. Leaf shares differ from shares pooled over all responses. The marked response estimate is preliminary. Source: the [included figure manifest](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/figure-manifest.json).*

## 2.6 Risk Surface Map

The range meeting every working threshold depends on the response sample and the comparison formula. The table below uses half-percentage-point minimum-rate bands and pools all four outside yields.

| Response sample | Minimum-rate band | Runs meeting every working threshold |
| --- | --- | ---: |
| Near the central responses | 7.5% to below 8.0% | 48 of 54, or 88.9% |
| Near the central responses | 8.0% to below 9.5% | 93.5%–98.1% across the three bands |
| Wider renewal range | 8.5% to below 9.5% | 90.6%–93.5% across the two bands |
| Wider renewal range | 9.5% to 10.0% | 65.6% |

The near-central sample uses renewal responses from 0.01 to 0.04 and entry responses from 0.02 to 0.06. The wider sample uses renewal from 0.01 to 0.06 and the full entry range from 0 to 0.1. These are slices of the original sweep, with about 50 or 200 runs per band respectively. They are not experiments at an exact minimum rate. The [full count tables](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence#conditional-goal-regions) preserve their denominators.

Above 9.5%, the pass rate falls because the twin starts lowering its own minimum at Helicon. A higher-rate proposed formula can then issue more than its twin and fail the issuance-saving goal. This upper boundary explains why “from 8.5%” would be misleading.

The preliminary response estimates remain an important source of uncertainty. Bitcoin-controlled renewal estimates span about 0.035–0.057 and Ether-controlled alternatives reach 0.09–0.11. Some specifications' uncertainty intervals include zero. The 0.01–0.06 working range is not a confidence interval, and the original 0–0.1 sweep does not cover every alternative estimate.

Longer horizons ask a different question because both central formulas eventually adopt ACP-285. The early-start advantage diminishes after adoption. Exploratory comparisons with near-unchanged floors of 9.75%–10% suggest cumulative issuance reductions of about 14% over five years and 16% over ten, alongside lower retained stake. These approximate-comparator scenarios have no long-horizon forecast validation and do not establish the lifetime of the remaining issuance budget.

The broader governance sweep also encounters available-supply constraints. One run stopped when stake reached the supply counter, and 11,957 runs exceeded half of that counter. Recommendations for those regions require a model with participation and available-supply feedback.

## 2.7 Workshop #1

The workshop can turn the working analysis into Foundation-specific evaluation criteria. The proposed 13 November session follows the 30 October model walkthrough.

| Workshop decision | Why it matters |
| --- | --- |
| Confirm objectives and measures | Separates the Foundation's aims from BCRG's exploratory additions |
| Choose acceptable ranges | Determines which outcomes count as satisfactory |
| Choose preference weights | Ranks satisfactory designs without hiding trade-offs |
| Select scenarios and response ranges | Defines the uncertainty a recommendation must withstand |

The sequence matters. Choosing weights first can make a high average score appear decisive even when an important minimum condition is often missed. Confirming the conditions first gives that ranking an explicit meaning.

## 2.8 Collaborative Mechanism Design

The released reward interface supports changes to rate schedules, duration curves and completed-period multipliers. Those components allow a new formula to reuse the lifecycle simulation and analysis. Neutral-setting tests check that the released alternatives reproduce the chain's formula on the tested inputs.

| Proposal | Evaluation question |
| --- | --- |
| Minimum and maximum rates changed together | Can issuance and the duration premium be adjusted jointly? |
| A different duration curve | How do issuance and participation change when the duration premium changes? |
| Node-tenure weighting | What issuance pays for repeated participation? |
| Revenue-funded rewards | What changes when part of the reward comes from revenue rather than minting? |

Revenue funding is a development extension, separate from the released interface. Its evaluation needs a specified revenue stream and a formula for periods when revenue is insufficient. The agreement's under-five-business-day turnaround remains an operational target to demonstrate through an end-to-end proposal evaluation.

## Next steps

The next research pass should strengthen the parts that determine the counterfactuals: renewal and entry responses, the observed mix of entrants and the response of duration to rewards. A completed held-back evaluation will add evidence about forecast levels. Delegations and available-supply feedback will broaden the economic accounting.

The proposed Milestone 3 sequence develops recommendations and a scenario playbook against the Foundation's chosen criteria, with working delivery targets in December and January. The [meeting brief](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/brief) identifies the decisions needed to settle that sequence. The [evidence guide](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence) provides the numerical tables, source identities and reproduction boundary for this report.
