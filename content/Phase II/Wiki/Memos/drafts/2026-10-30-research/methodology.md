---
title: "Modeling Avalanche's staking economy"
description: "How the staking simulation represents validators, computes rewards, learns from the record and evaluates alternative reward formulas."
date: 2026-10-30
status: draft
aliases:
  - Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/index
kind: report
reader: "Avalanche Foundation and Ava Labs researchers and decision makers"
question: "How can a staking simulation support the design and evaluation of Avalanche's reward formulas?"
---

Date: 30 October 2026\
To: Avalanche Foundation and Ava Labs\
From: Bonding Curve Research Group\
Subject: Modeling Avalanche's staking economy

Read this memo for the model and simulation setup. The [evidence guide](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence) supplies source identities and numerical tables; the [results memo](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results) is an optional next read. Reading requires no installation. The [setup guide](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/SETUP.md) includes a data-free reward calculation. The [central-case replay](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/report-reproduction/README.md) supplies a checked input download for the reported one-year comparison. Other historical reruns require separate snapshots and fitted draws.

## Introduction

Avalanche rewards its Primary Network validators with newly minted AVAX from a finite supply budget. Its reward formula determines how quickly that budget is used and how the return varies with staking duration. [ACP-285](https://github.com/avalanche-foundation/ACPs/blob/b80ea34682b419603f0241f114560dea5d61e03a/ACPs/285-reduce-minimum-consumption-rate/README.md) changes that formula to reduce inflation, extend the issuance budget and encourage longer commitments. The network-wide effects unfold as validators complete their existing commitments and choose what to do next.

A staking simulation makes those choices explicit. It follows individual validator staking periods, computes their rewards with the protocol's arithmetic and compares alternative formulas under the same conditions. The resulting differences show how a design could change issuance, participation and staking duration. Repeating the comparison across uncertain behaviour makes clear which conclusions depend on validators' responses.

Bonding Curve Research Group's system combines a checked chain record, a model of validator decisions and an experiment pipeline. New reward formulas can reuse the data, fitted behaviour and evaluation criteria. Model v0.8.0 is the implementation used in the [Milestone 2 results](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results). Its own-stake population covers the AVAX validators lock themselves. Delegated AVAX is outside its simulated population.

## 1. The reward formula links duration to the issuance budget

A validator commits an amount of AVAX for a chosen period. The protocol promises a reward when that period starts, conditional on meeting its eligibility requirements. The reward increases with the stake, its duration and the rate parameters set by the protocol.

The **consumption rate** is a parameter of the formula. The **annualized reward rate** is the reward divided by stake and duration, expressed per year. The remaining-supply ratio scales the former into the latter, so a 7.5% consumption rate does not mean a validator earns 7.5% a year. The [protocol implementation](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/model-v0.8.0/src/avalanche_research/domain/protocol/__init__.py) computes the reward with whole-number arithmetic and rounding.

Let the staking duration be $d$ days and the minting period be $T=365$ days.

The duration-dependent consumption rate $r(d)$ rises linearly between $r_{\min}$ and $r_{\max}$, the protocol's MinConsumptionRate and MaxConsumptionRate:

$$
r(d)=r_{\min}+(r_{\max}-r_{\min})\,d/T.
$$

At the earlier 10% minimum and 12% maximum, a 14-day stake has a consumption rate of 10% + 2% × 14/365 = 10.077%. A longer commitment approaches the maximum.

Let $S$ be the P-Chain's CurrentSupply counter in AVAX and $C=720$ million AVAX be SupplyCap. The remaining-supply ratio, also called the scarcity factor $\kappa$, is

$$
\kappa=(C-S)/S.
$$

At a counter of about 465 million AVAX, the ratio is 255/465 = 0.548. Multiplying a consumption rate by this ratio gives its annualized reward rate before integer rounding. As the counter rises, the same consumption rate pays a smaller percentage of stake.

For a stake of $s$ AVAX, the reward $R$ in AVAX is approximately

$$
R=s\,\frac{d}{T}\,\kappa\,r(d).
$$

A 2,000 AVAX stake for 14 days at the preceding counter and rates earns about 2,000 × 14/365 × 0.548 × 0.10077 = 4.24 AVAX. The simulation repeats the integer calculation rather than this rounded approximation.

ACP-285 keeps the 12% maximum and lowers the minimum from 10% to 7.5% over 90 days after Helicon. A period receives the configuration applicable at its start. The direct reduction is therefore greatest for short commitments, while a one-year commitment keeps the same consumption rate.

Figure 1 compares annualized rewards before Helicon and after the ramp at the same supply counter.

![Annualized reward against duration before Helicon and after the completed ACP-285 ramp.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/reward-duration.png)
*Figure 1. Formula illustration at a supply counter of 465 million AVAX, a supply cap of 720 million AVAX and a 12% maximum consumption rate. Curves start at each configuration's minimum duration: 14 days before Helicon and 2 days after. Orange uses the 7.5% minimum reached after the 90-day ramp. Values precede integer rounding. Source: the [v0.8.0 reward implementation](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/b18a4a2f0ad2d995a6ab30c8438ff19f446dcfdc/src/avalanche_research/domain/protocol/__init__.py).*

## 2. The data fixes what the model can learn

Each experiment starts on an **origin**, the day used to initialize the simulation. Its **state** is the information carried between days, including open periods and the supply counter. Fitting uses only observations available through the end of the origin's UTC day. The model can therefore be compared with subsequent observations without having learned their outcomes.

The central experiments use 18 November 2025 as their origin. Their inputs describe open validator periods, validators that have left and periods accepted ahead of their start. The historical record also supplies the decisions used to fit behaviour.

| Input | What the model learns or initializes |
| --- | --- |
| Open and scheduled periods | Stake, end dates and commitments already made |
| Endings and subsequent starts | Whether a node renews or returns later |
| First-ever validator periods | Daily entry and new entrants' initial stake and duration |
| Consecutive periods on one node | Changes in duration and stake |
| Supply readings and protocol configuration | The reward applicable to each new period |

The [data guide](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/data/README.md) separates the original records from derived tables. A **pin** identifies the exact input copies an experiment reads, including their byte hashes. An experiment rejects a missing or changed pinned input. A pin establishes which data were used. The separate data checks establish whether those records satisfy the required accounting and schema checks.

The [rewards reconstructed from the chain](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/data/README.md) provide one strong verification test. The checked data pipeline reproduces all but one of 4,455,121 rewards for periods that started when accepted. The exception is a delegation differing by 31 nAVAX, where one nAVAX is a billionth of an AVAX. Periods accepted ahead of their start are outside that comparison. Agreement on reward arithmetic supports the accounting component. The behavioural model needs separate evaluation.

## 3. Five decisions turn the historical record into daily behaviour

The model follows staking periods because periods are the commitments the chain records. Figure 2 shows how arrivals, renewals, departures and returns change the validator population, while new commitments update the supply counter.

![Validator staking periods and supply represented as stocks and flows.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/stocks-and-flows.png)
*Figure 2. Stocks and flows in model v0.8.0. Filled boxes persist between days, solid arrows move periods or AVAX, and dashed arrows carry information. Renewal and entry responses remain preliminary working settings. Source: the released implementation, with figure identity in the evidence manifest.*

Five decisions determine those movements and commitments, each with a statistical form suited to its outcome. A **logistic model** estimates the probability of a yes-or-no decision. Their [implementations](https://github.com/AVL-Foundation/ext-bcrg-validator-research/tree/model-v0.8.0/src/avalanche_research/model/parts) keep the questions separate.

| Decision | Representation | Reason for the choice |
| --- | --- | --- |
| Renew on the same node within seven days | A penalized logistic model using tenure, previous return, duration and stake bands | Produces a probability between zero and one while allowing repeated patterns in the record |
| Return after 8–365 days away | A daily logistic hazard using time away and node history | Allows the chance of return to change with the length of absence |
| Start validating for the first time | A negative-binomial daily count | Allows daily arrivals to vary more than a Poisson count with the same mean |
| Choose a duration | Draws from historical choices conditional on the kind of start and previous duration | Preserves concentrations at common durations |
| Choose a stake amount | A hurdle distinguishing an unchanged reference amount from a changed amount | Preserves both repeated amounts and the distribution of actual changes |

The logistic model turns a weighted combination of predictors into a probability. Its weights are fitted to make observed decisions likely. Penalization limits extreme weights supported by little data. For returns, a prior encourages neighboring time-away bands to have similar effects. The release omits the additional node-specific renewal-record term tested in development.

For arrivals, the fitted mean $\lambda$ is the expected number of first-ever validators per day. The dispersion $k$ controls how variable that count is:

$$
\mathrm{Var}(\text{daily arrivals})=\lambda+\lambda^2/k.
$$

The origin's [fitted arrival values](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/results/arrivals.csv) are about 3.89 arrivals a day and dispersion 0.493. They imply variance 3.89 + 3.89²/0.493 ≈ 34.6, almost nine times the mean. A Poisson count would require the variance to equal the mean and would understate those daily fluctuations.

Duration and stake use empirical distributions, meaning distributions constructed from observed choices. For renewed and returning periods, the model draws a duration using the previous-duration band. The stake hurdle then draws whether the reference amount changes and, if so, the size of that change. New entrants use the minimum validator stake as their reference amount because they have no previous stake.

Most fitting windows cover the preceding year. Returns use two years of endings to observe longer absences. Follow-up still stops at the origin, so a recent departure is not treated as if its eventual return were already known.

## 4. The response to reward is separate from habitual behaviour

Historical renewal, entry and duration patterns describe what validators did under the incentives they faced. Comparing a different reward formula requires an additional assumption about how behaviour changes when its return changes.

The model represents two explicit responses. The **renewal response** $\beta_R$ changes renewal log-odds per percentage point of annual yield gained. The **entry response** $\beta_E$ changes the log arrival rate on the same basis. A one-percentage-point yield gain multiplies renewal odds by $\exp(\beta_R)$ and the arrival mean by $\exp(\beta_E)$, with arrivals capped at 100 new nodes a day.

The **yield gap** compares the design's annual reward yield with the reward yield of the menu used during fitting, then subtracts the change in the yield available outside staking. Both reward yields use a standard 30-day stake and the origin's supply counter. Renewal uses typical renewing-node tenure, while entry uses zero completed periods. The [response implementation](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/model-v0.8.0/src/avalanche_research/model/response.py) keeps those references fixed through a run.

For example, if a validator renews with probability 80%, its odds are four to one. A response of 0.025 and a one-percentage-point yield reduction multiply those odds by $\exp(-0.025)=0.975$. The renewal probability becomes about 79.6%. The same yield reduction at an entry response of 0.04 multiplies expected entry by $\exp(-0.04)=0.961$.

BCRG's preliminary working values, 0.025 for renewal and 0.04 for entry, use historical AVAX price variation to study changes in dollar rewards. Translating that evidence into an annualized reward-yield response assumes validators respond similarly to the two sources of dollar-reward changes. Market sentiment can affect both AVAX's price and staking decisions, so these are specification-dependent estimates. The experiments vary the responses to test the dependence on these central values. The [evidence notes](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence#response-estimates) give the alternative estimates.

## 5. A paired simulation follows each formula through the same decisions

Each proposed formula runs beside a **twin**, a simulation under the chain's formula using the same origin, fitted-parameter draw, outside conditions and keyed random numbers. The pairing reduces variation caused by unrelated random choices. Model error can still affect both paths and their difference.

Figure 3 shows the order of one simulated day. The first four stages determine who starts a new period and what they commit. The reward stage prices those periods, then assembly constructs the next day's state.

![One simulated day in model v0.8.0](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/daily-model.png)
*Figure 3. Renewal, return, arrival, continuation, rewards and assembly run in that order. Green stages draw stochastic decisions. Gray stages apply accounting. The final checks stop a run on invalid stake, inconsistent totals or supply violations. This existing diagram is traced from the v0.8.0 implementation.*

The daily state includes open periods and their attributes, departed nodes and their history, scheduled starts, and supply accounting. Validator stake, validator count and issuance are derived from the evolving periods. The model checks individual stake bounds, the reconciliation of stake totals, the maximum absence tracked, supply below the cap and stake within supply.

Repeated runs carry several forms of uncertainty:

| Source | How it enters |
| --- | --- |
| Daily chance | Random renewals, returns, arrivals and commitment choices |
| Fitting uncertainty | Resampling nodes for renewal, returns and continuation, and 28-day blocks of arrival counts |
| Drift in renewal | A run-level shift estimated from variation between historical fitting windows |
| Uncertain economic response | Experiment settings for renewal and entry responses |

Fitted behaviour is drawn once for a run and then used through its simulated days. The stake hurdle remains at its fitted point estimate in v0.8.0. The distinction matters because the run distribution does not include uncertainty in every model component.

### The central experiment fixes one comparison

The central case compares an early ACP-285 ramp with the historical chain schedule. Both paths start from the same observed state. Their difference measures the effect of starting earlier over this horizon.

| Setting | Recorded specification |
| --- | --- |
| Model | v0.8.0, source commit `b18a4a2f0ad2d995a6ab30c8438ff19f446dcfdc`. The execution checkout was `76bc75898629e035401f6ad54d9b2aa1d2c2c873` |
| Inputs | Pin `p2-model-v0.8`: `staking-periods-2026-09-30` and `avax-monetary-daily-2026-09-30`. Initialization and fitting stop at 18 November 2025, 23:59:59 UTC |
| Clock | One-day steps for 365 days, 19 November 2025 to 18 November 2026. New simulated commitments are priced at noon UTC |
| Proposed formula | Cell `ramp-7.5-central`: `ACP285Ramp`, configured to activate at 16:00 UTC on 18 November 2025, reaching a 7.5% minimum over 90 days. The first simulated pricing is 20 hours into that ramp |
| Reference | Cell `chain-central`: `ChainReward`, following the historical schedule. Helicon activates at 15:00 UTC on 22 September 2026, calendar day 308. Noon pricing first uses the activated configuration on day 309 |
| Behaviour and outside yield | Renewal response 0.025 and entry response 0.04 per percentage point of annual reward yield on a 30-day stake. Outside yield is 5% annually. The fitted reference is about 4.1444% |
| Draws and seeds | 50 pairs. Key `k`, from 0 to 49, selects row `k` of the original 24,896-row draw table and model seed `k+1`, shared by both paths. The draw-generation seed is 53,588,821 |
| Outputs | Cumulative promised validator issuance saved, terminal own stake retained and active validators retained, each relative to its paired reference. Summaries are percentiles of per-pair ratios |

The [central-case source record](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/central-case-provenance.json) includes input hashes, cell settings and every pair mapping. It binds the recovered metadata to the stored output identity. The execution receipt does not bind the driver script to a specific revision, and the small record does not contain the underlying datasets or trajectories.

## 6. Forecast tests evaluate what the behavioural model predicts

A plausible explanation of past choices can still make poor predictions. Each candidate therefore forecasts from historical origins using only earlier data. Its outcomes are compared with the chain's realized stake and validator count.

The **continuous ranked probability score**, or CRPS, evaluates the whole forecast distribution. For equally weighted runs, it is the average distance from a run to the realized outcome, less half the average distance between two runs. This [proper scoring formula](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf) rewards accurate distributions and penalizes misleading certainty or excessive spread.

Consider 200 illustrative runs, half predicting 100 million AVAX of stake and half 120 million, with a realized 110 million. The distance from a run to the outcome averages 10 million. Distances between all ordered pairs of runs also average 10 million. The CRPS is therefore 10 − 10/2 = 5 million AVAX. The model evaluation scales this score by the mean absolute daily change before the origin, making performance comparable across origins.

| Test | Question it answers |
| --- | --- |
| Held-out decisions within development | Does a proposed behavioural component improve predictions of its own decision? |
| Repeated historical forecasts | Does the whole model beat simple forecasts at 30, 90 and 180 days? |
| Interval coverage | Does a stated forecast interval include outcomes as often as it should? |
| A separate held-back period | Does a model selected in development generalize to later data? |

The benchmarks include holding the last value, extending recent drift, a weekly autoregression, distributional versions of the first two, and a local-level statistical model. Candidate adoption follows a criterion specified before the development scores. The [selection evidence](https://github.com/AVL-Foundation/ext-bcrg-validator-research/tree/model-v0.8.0/results/model-v0.8.0-selection) records the outcomes.

The period from 19 November 2025 to Helicon on 22 September 2026 is reserved for a separate evaluation. No completed held-back verdict is reported here. Forecast skill on stake levels also provides a different test from the validity of a consumption-rate counterfactual. Both forms of evidence matter.

## 7. Experiments turn trajectories into design comparisons

**Parameter selection under uncertainty**, or PSUU, compares reward settings across behaviour and outside conditions the Foundation cannot choose. A **sweep** runs many such settings. Each design is paired with the historical chain formula, which adopts ACP-285 at Helicon. The experiments distinguish changing the reward formula from changing the conditions under which it operates.

### 7.1 The run families test different mechanisms and horizons

The first two one-year sweeps contain 199,887 recorded runs, including reference runs. The first compares the ACP-285 ramp, a constant pre-ACP-285 formula, an alternative duration curve and a boost for completed staking periods. The second adds broader protocol settings. Their run counts describe coverage, rather than independent confirmations of a policy effect.

| Experiment | Size | What varies and what it tests |
| --- | ---: | --- |
| First one-year sweep | 132,800 runs | Four design families, annual outside yields of 3%, 5%, 7% and 10%, and behavioural responses. Identifies which inputs drive issuance and participation |
| Second one-year sweep | 67,087 runs | Minimum and maximum consumption rates, duration limits and bear, neutral and bull conditions. Examines interactions and available-supply constraints |
| Central comparisons | 50 pairs per design | Random draws at fixed working responses and 5% annual outside yield. Quantifies variation for a specific formula comparison |
| Five-year experiment | 4,096 pairs | Ramp settings, responses and outside yields. Examines how an early-start advantage changes over time |
| Ten-year experiment | 8,192 pairs | Ramp and duration-curve scenarios. Explores longer-run implications without forecast validation at that horizon |

A pair contains a design run and its reference. Shared references and repeated runs must be reconciled before combining counts. The second sweep records one failed available-supply check. The [experiment results](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results#22-simulation-execution) distinguish these populations and report the conditional findings. Revenue-funded rewards are a proposed next evaluation, requiring a specified funding source and shortfall formula.

### 7.2 Goals guide which outcomes the experiments measure

Eric Lu's ACP-285 presentation names three aims: lower inflation, extend the issuance-funded security budget and encourage longer staking. These motivate the measurements. Stake and validator participation provide additional information about what a reward reduction could cost. [ACP-285 presentation](/Phase-II/Wiki/Collections/Essential-Readings/ACP-285-Avalanche-Community-Call-Staking-Reward-Curve-Adjustment/Source-Video#three-intended-goals).

A **KPI**, or key performance indicator, is a measurable outcome. The five working goals group those outcomes for evaluation. Their thresholds and weights are BCRG's exploratory choices, rather than confirmed Foundation preferences.

| Working goal | KPIs and interpretation |
| --- | --- |
| G1 Stake participation | Own stake retained and the worst 30-day stake fall relative to the reference |
| G2 Validator participation and distribution | Validator count, node-level stake concentration and annual return margin after outside yield and operating cost |
| G3 Issuance and inflation | Validator issuance saved and annual net issuance relative to total supply. Delegated issuance is omitted, so the inflation proxy is not network-wide |
| G4 Stake per AVAX issued | Retained own stake per unit of issuance relative to the reference, measuring reward efficiency |
| G5 Commitment duration | Stake-weighted duration relative to the reference. Individual duration choices do not respond to incentives in v0.8.0, so changes reflect the mix of participating validators |

Cumulative issuance also measures budget use over a stated horizon. A longer budget lifetime remains a projection dependent on the future reward formula and participation. Measuring an outcome does not establish that it must be an acceptance condition. The [working goal definitions](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results#23-kpi-computation) specify the existing thresholds.

### 7.3 Utilities make the scoring choices explicit

A **utility** maps a KPI onto a preference scale from zero to one. For a simple increasing utility, a lower value scores zero and a target scores one, with a straight line between them. The combined score weights G1 to G4 equally and gives G5 half their weight. The [goal-by-setting heatmap](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/goal-utilities.png) retains both the individual goals and their combined score.

A **pass threshold** asks whether an outcome is acceptable. Matching reference duration, for example, earns a G5 utility of 0.29 and passes the 99% duration-retention threshold. The utility reaches one at 105% of reference duration. A low score can therefore coexist with a passing outcome, and a high combined score can coexist with failures on individual goals.

The [aggregate utilities](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/goal-utilities.csv) and [score mappings](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/utility-mappings.json) preserve those choices. Correlations show direction, trees describe conditional regions, forests rank predictive inputs and Sobol indices estimate shares of output variance. A numerical variance split is reported only where its convergence check supports it.

The [figure manifest](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/figure-sources.json) identifies the frozen inputs. Rebuild the detailed heatmap and its mechanism-level summary from the repository root:

```bash
uv run --frozen --group notebook --with matplotlib==3.10.8 python \
  scripts/figures/reward_rule_report_figures.py \
  'content/Phase II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons'
```

The summary weights setting-cell means by their run counts. Both figures reuse stored scores without new simulation or scoring.

## 8. Separate components make the system reusable

A new question can often reuse most of the system. The [reward interface](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/model-v0.8.0/src/avalanche_research/mechanisms/reward.py) separates the rate configuration, the duration curve and the multiplier for completed periods. Released alternatives have neutral-setting tests against the chain's formula.

| Change | What can be reused |
| --- | --- |
| A new reward formula | Fitted behaviour, experiment conditions and existing measures |
| Different thresholds or weights | Stored measures, when all required columns were retained |
| New historical inputs | Reward implementations and experiment structure after refitting |
| A better behavioural component | Data interfaces, reward formulas and analysis after evaluation |

The next extensions address specific economic questions. Delegations and available-supply feedback broaden the simulated population. Price and holder types add feedback absent from v0.8.0. A duration choice that responds to rewards is needed to test ACP-285's hoped-for shift toward longer commitments. Revenue-funded rewards require a separate funding component, being developed alongside the released interface.

Every result should identify its model, inputs, design and comparator. The code and development evidence are in the [Foundation repository](https://github.com/AVL-Foundation/ext-bcrg-validator-research/tree/milestone-2). The central-case replay is available from a clean checkout with its checked download. Inputs for other historical simulations remain separate. The accompanying [evidence and reproduction guide](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence) states what can be checked from this package and what still requires those inputs.
