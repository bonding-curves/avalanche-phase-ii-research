---
title: "The model compares reward rules on issuance and stake"
description: "Reward mechanisms, goals, measures and experiments, with their findings and remaining research needs."
date: 2026-10-29
status: draft
kind: report
reader: "Avalanche Foundation and Ava Labs researchers and decision makers"
question: "Which reward mechanisms have been examined, what do the experiments establish, and which choices remain open?"
---

Date: 29 October 2026\
To: Avalanche Foundation and Ava Labs\
From: Bonding Curve Research Group

## Introduction

Avalanche pays validators to commit AVAX as stake. Changing the reward rule changes issuance directly and may also change whether validators enter or renew. A useful comparison therefore measures both the AVAX issued and the validator stake retained.

The model compares each proposed rule with a **paired reference**, a simulation using the chain's historical reward schedule under the same conditions and random draws. The experiments show how reward settings change issuance and participation under stated behavioural assumptions. Selecting a reward rule also requires deciding which outcomes matter and which losses are acceptable.

## The mechanisms change different parts of the reward rule

A **mechanism** specifies how a staking commitment earns its reward. The experiments distinguish a change in the minimum consumption rate from a change in the duration curve or a reward for repeated participation. Consumption rates are protocol parameters, rather than the annual yield received by a validator. Yield also depends on the supply counter and staking duration.

A **sweep** varies mechanism settings alongside uncertain behaviour and outside conditions. The table distinguishes rules already used in these experiments from the proposed next mechanism.

| Mechanism | What changes | Evidence available |
| --- | --- | --- |
| Historical chain rule | Uses the rule before Helicon, then adopts ACP-285 on its historical date | Paired reference for the experiments |
| ACP-285 ramp | Lowers the minimum consumption rate gradually, with alternative final settings | One-year sweeps, central paired comparisons and exploratory longer horizons |
| Constant pre-ACP-285 rule | Keeps the minimum consumption rate at 10% throughout the experiment | One-year comparison with the historical chain rule |
| Alternative duration curve | Changes how rewards increase with commitment duration | One-year sweep and exploratory ten-year cases |
| Tenure boost | Adds reward as a validator completes more staking periods | One-year sweep |
| Broader protocol settings | Varies minimum and maximum rates and duration limits | Second one-year sweep, including regions affected by available-supply constraints |
| Revenue-funded rewards | Uses protocol revenue to fund rewards | Proposed next experiment, with funding and shortfall rules still to specify |

The [methodology memo](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/methodology) explains the reward calculation and the behavioural model. The [experiment report](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results#22-simulation-execution) describes the simulated mechanism families. Revenue-funded rewards remain a proposed next mechanism in the [meeting brief](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/brief#4-milestone-3-should-evaluate-the-next-mechanism-against-those-criteria).

## The stated aims and the working scores serve different purposes

Eric Lu's ACP-285 presentation names three aims: lower AVAX inflation, extend the issuance-funded security budget and encourage longer staking. Those aims give the evaluation its starting point. Their measurements have different coverage in the model. [ACP-285 presentation](/Phase-II/Wiki/Collections/Essential-Readings/ACP-285-Avalanche-Community-Call-Staking-Reward-Curve-Adjustment/Source-Video#three-intended-goals).

A **KPI**, or key performance indicator, is a measurable outcome. The KPIs below connect each stated aim to the model's outputs.

| Stated aim | Relevant KPIs | What the model can assess |
| --- | --- | --- |
| Reduce AVAX inflation | Validator issuance in AVAX, issuance saved against the reference and annual net issuance relative to a stated supply base | Validator issuance responds to the reward rule. Delegated issuance is omitted, so the inflation proxy does not represent network-wide inflation |
| Extend the security budget | Cumulative issuance and the remaining issuance allowance at a stated horizon | Issuance saving measures slower budget use over that horizon. Five- and ten-year projections are exploratory, without forecast validation at those horizons |
| Encourage longer staking | Stake-weighted commitment duration and the reward difference between short and long periods | The reward incentive changes. Individual duration choices do not yet respond to that incentive, so simulated duration changes reflect the mix of participating validators |

A **utility score** maps one or more outcomes onto a preference scale from zero to one. A **threshold** decides whether an outcome is acceptable. Measuring validator count, for example, does not by itself establish that retaining a particular count should be a condition for accepting a mechanism.

Bonding Curve Research Group uses five working goals in the existing analysis. The table preserves their identifiers so the heatmap can be read against their definitions. The thresholds and utility mappings are exploratory choices, rather than confirmed Foundation preferences. [KPI definitions and scoring](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results#23-kpi-computation).

| Working goal | KPIs used | Working acceptance conditions |
| --- | --- | --- |
| G1 Stake participation | Own stake retained and worst 30-day stake fall | Retain at least 95% of reference stake, with a worst monthly fall at most two percentage points deeper |
| G2 Validator participation and distribution | Validator count, node-level stake concentration and return margin | Retain at least 95% of validators, lose at most one node in the concentration measure and at most one percentage point of annual return margin |
| G3 Issuance and inflation | Issuance saved and annual net-inflation proxy | Save some issuance and keep the proxy below 5% of total supply annually |
| G4 Stake per AVAX issued | Retained own stake per unit of issuance relative to the reference | Retain at least as much stake per AVAX issued |
| G5 Commitment duration | Stake-weighted duration relative to the reference | Retain at least 99% of reference duration |

The concentration measure counts the fewest validator nodes holding more than one third of own stake. It does not identify common ownership. Return margin subtracts the outside yield and an assumed annual operating cost of 1.5% of stake from the validator's annualized reward rate.

## The run families answer different questions

The two one-year sweeps contain 199,887 recorded runs, including chain-reference runs. A paired comparison contains both a design run and its reference. Counts of runs and counts of pairs therefore have different denominators. [Experiment counts](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results#22-simulation-execution).

| Experiment family | Reported size | What differs between runs | What the experiments teach |
| --- | ---: | --- | --- |
| First one-year sweep | 132,800 runs | Four design families, outside yields of 3%, 5%, 7% and 10% annually, and behavioural response strengths | Which settings drive issuance and participation, and which designs meet the working criteria |
| Second one-year sweep | 67,087 runs | Broader protocol parameters and bear, neutral and bull conditions | How rate and duration limits interact with outside conditions. Available-supply constraints limit interpretation in part of the space |
| Central comparisons | 50 pairs per design | Random draws at fixed working responses and 5% annual outside yield | The distribution of outcomes for a specific comparison |
| Five-year experiment | 4,096 pairs | Ramp settings, response uncertainty and outside yields | How an early-start advantage changes over time |
| Ten-year experiment | 8,192 pairs | Ramp and duration-curve scenarios | Longer-run implications under assumptions that lack forecast validation at that horizon |

These counts describe experiment coverage. The second sweep includes one failed available-supply check. Counts should not be added into a total without reconciling shared references and repeated runs. The [execution and sensitivity results](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results) describe the comparisons and their limits.

## Goal utilities expose the trade offs between mechanisms

Lower reward settings can score better on issuance while scoring worse on stake and validator participation. Figure 1 shows that pattern across the five working goals and their combined score. Rows follow mechanism and parameter order. The combined score weights G1 to G4 equally and gives G5 half their weight.

![Goal utility matrix with five goal columns and the combined score.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/goal-utilities.png)
*Figure 1. Mean utility at one year for 16,384 design runs in the independent A and B blocks of the first sweep. The four design families contribute 4,096 runs each. Cells pool annual outside yields of 3%, 5%, 7% and 10% and the original behavioural response range. Scores use BCRG's working utility mappings. A score of 0.8 is neither an 80% pass rate nor a probability of success. Source: the included one-year goal-utility aggregates, rearranged without changing their scores.*

The ramp rows show the cost of treating all goals as simultaneous acceptance conditions. A setting can achieve a high issuance score while losing utility on participation. The combined preference score and the share meeting every threshold answer different questions. A mechanism's suitability therefore depends on which measures the Foundation chooses as objectives and which it chooses as safeguards.

For example, matching the reference's stake-weighted duration receives a G5 utility of 0.29 and passes the 99% duration-retention threshold. The utility mapping reserves a score of one for 105% of reference duration. A low utility can therefore coexist with an acceptable outcome under the working threshold.

The [aggregate CSV](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/goal-utilities.csv) retains the original values and run counts. The [working utility mappings](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/utility-mappings.json) give the thresholds, weights and score transformations used to produce them.

## The central comparison quantifies issuance saved and stake retained

Starting ACP-285's ramp ten months before Helicon saves issuance over the first year in the central experiment. Both rules eventually adopt ACP-285. The result measures the benefit and participation cost of the earlier start under the model's working assumptions.

| Outcome at one year | Median across 50 pairs | 10th to 90th percentile |
| --- | ---: | ---: |
| Validator issuance saved | 12.8% of reference issuance | 11.6% to 15.4% |
| Validator own stake retained | 98.7% of reference stake | 95.3% to 99.9% |

The experiment starts on 18 November 2025 and uses a 90-day ramp to a 7.5% minimum consumption rate. The reference adopts ACP-285 at Helicon on 22 September 2026. Annual outside yield is 5%, with preliminary renewal and entry response settings of 0.025 and 0.04. Those settings describe how renewal odds and arrivals respond to a percentage-point change in annual yield on a standard 30-day stake. The [central-case evidence](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence#central-case) preserves exact statistics and input identities.

Figure 2 places the outcome ratios in the context of the simulated paths. Its bands show variation across runs with those response settings fixed. They do not span every plausible behavioural response or establish ACP-285's realized effect.

![Central paired trajectories comparing the early ramp with the historical chain rule.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/central-trajectories.png)
*Figure 2. Existing central-case trajectories from 18 November 2025, reused unchanged. Lines are medians and bands span the 10th to 90th percentiles of 50 runs per rule. The reference adopts ACP-285 at Helicon. Simulated supply includes validator issuance and a burn assumption, while delegated issuance is omitted. Historical portions provide context. Source: the central-case artifact identified in the evidence guide.*

## Better recommendations need behavioural evidence and chosen criteria

The experiments establish a repeatable way to compare rules and identify issuance-participation trade-offs under stated assumptions. The minimum consumption rate drives most variation in issuance saved in the ramp experiment. Participation depends more strongly on uncertain behaviour. [Sensitivity analysis](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results#25-sensitivity-analysis).

Development forecasts support the model more strongly for own stake than for validator count. Stake forecasts beat six benchmarks, while short-horizon uncertainty bands cover fewer outcomes than intended. The separate held-back evaluation has no completed verdict in this evidence set. Forecast performance also does not directly validate the preliminary responses to reward changes. [Development evaluation](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results#24-validation-confirmation).

The next comparison needs a clear mechanism and a clear interpretation of success. Revenue-funded rewards require a specified revenue source and a rule for shortfalls. Evaluation criteria can begin with Eric's three stated aims, then distinguish outcomes to improve from participation losses to limit. Keeping the individual KPIs available allows the experiments to be reconsidered when those choices change.

## Data and reproduction

The figures use existing aggregate results. The [source manifest](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/figure-sources.json) identifies the included input files by hash. Rebuild Figure 1 from the repository root:

```bash
uv run --frozen --group notebook --with matplotlib==3.10.8 python \
  scripts/figures/reward_rule_report_figures.py \
  'content/Phase II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons'
```

This redraws the stored utilities. It does not rerun simulations or select new scores. Figure 2 is a byte-for-byte copy of the existing central-case image. Full simulation reproduction requires the pinned historical inputs described in the [evidence and reproduction guide](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence#reproduction).
