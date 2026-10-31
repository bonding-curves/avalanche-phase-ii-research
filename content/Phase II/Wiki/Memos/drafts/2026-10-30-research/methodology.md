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
From: Bonding Curve Research Group (BCRG)\
Subject: Modeling Avalanche's staking economy

Avalanche's reward formula connects a finite issuance budget to the return on staking. Changing the formula changes the rewards offered to validators. Its network-wide effects depend on what validators do as existing commitments end.

The simulation follows those commitments and five decisions: renew, return, enter, choose a duration and choose a stake amount. Alternative reward formulas run beside the historical protocol schedule under the same conditions. The comparison estimates changes in validator participation and reward promises under stated behavioural assumptions.

Model v0.8.0 covers validators' **own stake**, the AVAX they lock themselves. Delegated AVAX is outside its population. The [results memo](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results) reports the experiments. The [evidence guide](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence) supplies numerical tables, source identities and reproduction instructions.

## 1. The reward formula links duration to the issuance budget

A validator commits AVAX for a chosen period. The protocol calculates a reward at the period's start, payable if the validator meets the eligibility requirements. [ACP-285](https://github.com/avalanche-foundation/ACPs/blob/b80ea34682b419603f0241f114560dea5d61e03a/ACPs/285-reduce-minimum-consumption-rate/README.md) changes that calculation to lower issuance and increase the incentive for longer commitments.

The **consumption rate** is an annual parameter of the reward formula. The **annualized reward rate** expresses the reward as a percentage of stake per year. The remaining issuance budget connects the two, so a 7.5% consumption rate does not mean a 7.5% annual return.

For a duration $d$ and minting period $T=365$ days, the consumption rate rises linearly from the minimum $r_{\min}$ toward the maximum $r_{\max}$:

$$
r(d)=r_{\min}+(r_{\max}-r_{\min})\,d/T.
$$

Here $d$ and $T$ are in days, and all rates are dimensionless. With a 10% minimum and 12% maximum, a 14-day period uses 10% + 2% × 14/365 = 10.077%.

Let $C$ be the 720 million AVAX supply cap and $S$ the P-Chain's CurrentSupply counter, also in AVAX. The **remaining-supply ratio** is $\kappa=(C-S)/S$. For a stake $s$ AVAX, the reward $R$ AVAX is approximately

$$
R=s\,\frac{d}{T}\,\kappa\,r(d).
$$

At a counter of 465 million AVAX, $\kappa=255/465\approx0.548$. A 2,000 AVAX stake for 14 days therefore earns about 4.24 AVAX at the preceding rates. The simulation uses the [protocol's integer arithmetic](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/b18a4a2f0ad2d995a6ab30c8438ff19f446dcfdc/src/avalanche_research/domain/protocol/__init__.py), including rounding, rather than this approximation.

ACP-285 lowers the minimum from 10% to 7.5% over 90 days after Helicon and retains the 12% maximum. Each period receives the configuration applicable when it starts. Figure 1 holds the supply counter fixed to show the direct effect: shorter commitments receive a larger reduction, while a one-year commitment keeps the same consumption rate.

![Annualized reward against duration before Helicon and after the completed ACP-285 ramp.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/reward-duration.png)
*Figure 1. Formula illustration at a supply counter of 465 million AVAX, a supply cap of 720 million AVAX and a 12% maximum consumption rate. Curves start at each configuration's minimum duration: 14 days before Helicon and 2 days after. Orange uses the 7.5% minimum reached after the 90-day ramp. Values precede integer rounding. Source: the [v0.8.0 reward implementation](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/b18a4a2f0ad2d995a6ab30c8438ff19f446dcfdc/src/avalanche_research/domain/protocol/__init__.py).*

## 2. The data fixes what the model can learn

An experiment's **origin** is the day used to initialize and fit the model. Only information available through that UTC day's end enters preparation. The central experiments use 18 November 2025, before the subsequent observations used for comparison.

| Historical record | Use in the model |
| --- | --- |
| Open and already scheduled periods | Initialize stake, duration, end dates and commitments already made |
| Endings and later starts on the same node | Fit renewal and delayed return |
| First-ever validator periods | Fit daily entry and entrants' initial choices |
| Consecutive periods on one node | Fit changes in stake and duration |
| Supply readings and protocol configuration | Price new commitments and initialize accounting |

Most fitting windows cover one year. Returns use two years of endings to observe longer absences, with follow-up still stopping at the origin. Recent departures therefore contribute only the return history available by that date.

The [data guide](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/data/README.md) distinguishes original records, derived tables and **pins**, which identify exact input bytes by hash. A pin verifies data identity. Schema, reconciliation and reward checks test the contents separately.

The [reward reconstruction check](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/data/README.md) reconstructs rewards for 4,455,121 periods that started when accepted. All but one match the chain exactly. The exception is a delegation differing by 31 nAVAX, where one nAVAX is a billionth of an AVAX. Ahead-of-start acceptances are outside that comparison. This verifies reward arithmetic on the stated population. Behavioural prediction requires the separate tests in Section 6.

## 3. Five decisions turn the historical record into daily behaviour

New entries and returns add validators. Renewals keep them participating, while departures reduce the active population. Figure 2 shows these movements and the reward promises attached to new commitments.

![Validator staking periods and supply represented as stocks and flows.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/stocks-and-flows.png)
*Figure 2. Stocks and flows in model v0.8.0. Filled boxes persist between days, solid arrows move periods or AVAX, and dashed arrows carry information. Renewal and entry responses remain preliminary working settings. Source: the released implementation, with figure identity in the evidence manifest.*

The five decisions have separate statistical representations in the [released model](https://github.com/AVL-Foundation/ext-bcrg-validator-research/tree/model-v0.8.0/src/avalanche_research/model/parts). A **logistic model** maps a weighted combination of predictors to a probability between zero and one.

| Decision | Representation and purpose |
| --- | --- |
| Renew within seven days | A penalized logistic model estimates the probability using tenure, prior return, duration and stake bands |
| Return after 8–365 days away | A daily logistic hazard lets return probability vary with time away and node history |
| Enter for the first time | A negative-binomial daily count allows arrivals to fluctuate more than a Poisson count |
| Choose a duration | Historical distributions retain common durations and dependence on the previous-duration band |
| Choose a stake amount | A hurdle first draws whether the reference amount changes, then draws the size of the change |

Penalization limits extreme weights supported by little data. The return model also encourages neighboring absence bands to have similar effects. The released renewal model omits the additional node-specific renewal-record term tested during development.

The negative-binomial arrival count has variance $\lambda+\lambda^2/k$, where $\lambda$ is mean entrants per day and $k$ is a positive dispersion parameter. The origin's [fitted values](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/results/arrivals.csv), about 3.89 and 0.493, imply variance 34.6. The variance is almost nine times the mean, explaining the need for a count model with more dispersion than Poisson.

Renewing and returning validators use their previous stake as the reference amount. New entrants use the protocol minimum. Duration and stake choices preserve observed patterns, including repeated amounts. Individual duration choices do not yet change in response to reward incentives.

## 4. The response to reward is separate from habitual behaviour

Historical choices describe behaviour under past incentives. A different reward formula also needs an estimate or assumption about how behaviour changes when annual yield changes.

The **renewal response** $\beta_R$ changes renewal log-odds per percentage point of annual yield gained. The **entry response** $\beta_E$ changes the log arrival rate on the same basis. A one-point yield gain multiplies renewal odds by $\exp(\beta_R)$ and mean arrivals by $\exp(\beta_E)$. The expected daily arrival mean is capped at 100. A realized count can exceed that mean.

For example, an 80% renewal probability gives odds of four to one. With $\beta_R=0.025$, losing one percentage point of yield multiplies those odds by $\exp(-0.025)$, reducing the probability to about 79.6%. With $\beta_E=0.04$, the same loss reduces expected entry by about 4%.

The model's [yield comparison](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/model-v0.8.0/src/avalanche_research/model/response.py) uses a standard 30-day stake at the origin's supply counter. It compares the proposed formula with the fitting reference, then subtracts the change in outside yield. Renewal uses typical renewing-node tenure, while entry uses zero completed periods.

Working responses of 0.025 and 0.04 are informed by preliminary analysis of historical dollar rewards. Their translation to annual-yield responses assumes validators respond similarly to reward changes caused by AVAX prices and by the reward formula. Shared market sentiment is a competing explanation. The [alternative estimates](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence#response-estimates) vary materially across specifications, so experiments vary these responses explicitly.

## 5. A paired simulation follows each formula through the same decisions

Each design runs beside a **twin** using the historical chain schedule. The pair shares its origin, fitted-parameter draw, outside conditions and keyed random numbers. Pairing reduces unrelated random variation. Errors in the model can still affect both paths and their difference.

Figure 3 follows one simulated day from decisions to accounting. The reward stage calculates and books new reward promises before the next day's state is assembled. Payment remains conditional on eligibility at the period's end.

![One simulated day in model v0.8.0](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/daily-model.png)
*Figure 3. Renewal, return, arrival, duration and stake, rewards, and assembly run in that order. Green stages draw stochastic decisions. Gray stages apply accounting. The final checks stop a run on invalid stake, inconsistent totals or supply violations. This existing diagram is traced from the v0.8.0 implementation.*

The state retains open periods, scheduled starts, departed nodes and supply accounting. Checks stop a run for invalid stake, inconsistent totals or supply violations. Repeated runs draw daily decisions and fitted behaviour, with parameters drawn once per run. Node resampling captures fitting uncertainty in renewal, returns and duration continuation. Arrival counts use 28-day resampling blocks. A run-level renewal shift represents variation between fitting windows. The stake hurdle remains at its fitted point estimate, so the run distribution covers only part of model uncertainty.

### The central experiment fixes one comparison

The central comparison starts the ACP-285 ramp early while its twin follows the historical adoption date. The [source record](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/central-case-provenance.json) preserves full identifiers and pair mappings.

| Setting | Specification |
| --- | --- |
| Model and origin | v0.8.0, initialized and fitted through 18 November 2025, 23:59:59 UTC |
| Horizon and clock | 365 days through 18 November 2026, with new commitments priced at noon UTC |
| Early-ramp design | 90-day ramp to 7.5%, configured to start at 16:00 UTC on the origin date. First simulated pricing is 20 hours into the ramp |
| Historical twin | Adopts ACP-285 at Helicon, 22 September 2026, 15:00 UTC. Noon pricing first uses the activated configuration on day 309 |
| Responses and outside yield | Renewal 0.025, entry 0.04 and outside yield 5% annually, against a fitted outside-yield reference of about 4.1444% |
| Pairing | 50 pairs. Key 0–49 selects the corresponding original draw-bank row and model seed equal to key plus one |
| Measures | Per-pair ratios of promised validator issuance, terminal own stake and validator count |

The [replay guide](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/report-reproduction/README.md) supplies compact inputs, original draws, tagged source and checks. Its initialization counter is recorded 193 seconds before the origin cutoff. The replay reproduces the original numerical paths, while the original execution-time driver identity remains unrecorded.

## 6. Forecast tests evaluate what the behavioural model predicts

Historical forecasts test the model against observations it has not used for fitting. Each candidate predicts stake and validator count from earlier origins, with comparisons against six simple benchmarks.

The **continuous ranked probability score**, or CRPS, evaluates the full distribution. It equals the average distance from a run to the realized outcome, less half the average distance between two runs. This [proper scoring formula](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf) balances accuracy and spread. Lower scores are better. Scaling by the pre-origin mean absolute daily change makes scores comparable across origins.

Development tests examine individual decisions, whole-model forecasts at 30, 90 and 180 days, and interval coverage. The [selection evidence](https://github.com/AVL-Foundation/ext-bcrg-validator-research/tree/model-v0.8.0/results/model-v0.8.0-selection) compares persistence, drift, autoregressive and local-level benchmarks, including distributional alternatives.

A separate held-back period runs from Granite, 19 November 2025, to Helicon, 22 September 2026. Its verdict remains outstanding. Forecast performance tests the predicted levels of stake and count. It provides different evidence from the causal response needed for a reward-formula counterfactual.

## 7. Experiments turn trajectories into design comparisons

**Parameter selection under uncertainty**, or PSUU, varies reward settings alongside uncertain behaviour and outside conditions. A **sweep** repeats those comparisons across many settings. Model paths become measures, then goal assessments and design comparisons.

### 7.1 The run families test different mechanisms and horizons

The first two one-year sweeps record 199,887 runs, including references. They cover different designs and settings. Their sizes measure computational coverage rather than independent confirmations of a finding.

| Experiment | Recorded size | Purpose |
| --- | ---: | --- |
| First one-year sweep | 132,800 runs | Compare ramp, pre-ACP-285, duration-curve and tenure-boost designs across four outside yields and response uncertainty |
| Second one-year sweep | 67,087 runs | Vary minimum and maximum rates, duration limits and market scenarios |
| Central comparisons | 50 pairs per design | Examine specific settings at working responses and 5% annual outside yield |
| Five-year experiment | 4,096 pairs | Compare ramp settings with historical adoption, including near-unchanged-floor scenarios |
| Ten-year experiment | 8,192 pairs | Explore ramp and duration-curve scenarios at a longer horizon |

A pair contains a design and reference. Shared references, repetitions and failures must be reconciled before combining counts. The [results memo](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results#22-simulation-execution) supplies the interpretations and execution qualifications.

### 7.2 Goals guide which outcomes the experiments measure

Eric Lu's [ACP-285 presentation](/Phase-II/Wiki/Collections/Essential-Readings/ACP-285-Avalanche-Community-Call-Staking-Reward-Curve-Adjustment/Source-Video#three-intended-goals) names lower inflation, a longer issuance-funded security budget and longer staking as aims. The working evaluation combines these aims with participation safeguards.

A **KPI**, or key performance indicator, is a measured outcome. BCRG groups the measures into five goals and supplies exploratory thresholds and weights. The Foundation has yet to confirm those preferences.

| Goal | Measures and interpretation |
| --- | --- |
| G1 Stake participation | Own stake retained and worst 30-day stake fall relative to the twin |
| G2 Validator participation and distribution | Count retained, node-level concentration and return margin after outside yield and an assumed operating cost |
| G3 Issuance and inflation | Validator reward promises saved and a net-inflation proxy with fixed burn and delegated issuance omitted |
| G4 Stake per AVAX issued | Retained own stake per unit of promised issuance relative to the twin |
| G5 Duration | Stake-weighted duration relative to the twin, reflecting the mix of participants rather than individual reward-driven duration choices |

Cumulative issuance measures budget use over a stated horizon. Estimating the budget's lifetime needs additional assumptions about future participation and formulas. The [working thresholds](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results#23-kpi-computation) state what the current analysis treats as acceptable.

### 7.3 Utilities make the scoring choices explicit

A **utility** maps a measure to a preference score from zero to one. The combined score averages goal utilities, weighting G1–G4 equally and G5 at half their weight. Passing asks a separate question: does every measure meet its threshold?

For example, matching reference duration earns a G5 utility of 0.29 and passes its 99% retention threshold. Utility reaches one at 105% of reference duration. A low utility can therefore pass, and a high combined score can coexist with failures on an individual goal.

The [utility mappings](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/utility-mappings.json) and [frozen goal aggregates](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/goal-utilities.csv) make these choices checkable. Correlations describe direction, decision trees describe conditional regions, forests rank predictive inputs and Sobol indices estimate variance shares where convergence supports them. The evidence guide contains the [figure sources and rebuilding commands](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence#explanatory-figures).

## 8. Separate components make the system reusable

The [reward interface](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/model-v0.8.0/src/avalanche_research/mechanisms/reward.py) separates rate schedules, duration curves and completed-period multipliers. A new formula can reuse fitted behaviour and measures. New thresholds can reuse stored measures. Better behavioural components can reuse the data and reward interfaces after evaluation. Neutral-setting tests check the released alternatives against the chain formula.

The next substantive extensions are reward-responsive duration, delegations and available-supply feedback. Revenue-funded rewards also need an explicit funding stream and treatment of shortfalls. These additions address economic questions beyond the released validator own-stake model.

Eric can inspect the code, browse the wiki, run an included-input example or [reproduce the central report result](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/docs/handoff/README.md). The [evidence guide](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence#reproduction) distinguishes these delivered capabilities from other historical reruns that still require separate inputs.
