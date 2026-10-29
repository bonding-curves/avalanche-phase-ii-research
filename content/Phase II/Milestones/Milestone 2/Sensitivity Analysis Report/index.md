---
title: "Sensitivity Analysis Report"
description: "Milestone 2 of Avalanche Phase II tests reward designs on a model of every validator. ACP-285's lower minimum rate makes each AVAX issued hold more stake, and the thresholds the Foundation sets for security and participation decide whether the best minimum rate is near 6% or near 9%."
status: delivered
source: signed-grant-agreement
tags: ["parameter-selection-under-uncertainty", "sensitivity-analysis", "model-validation"]
---

## 1. Introduction

Phase II learns how Avalanche's validators behave from the network's full history, then tests reward designs across market conditions to measure how each one changes participation, security and issuance. Milestone 2 has run that test on four reward designs and on the protocol's own reward parameters, nearly 200,000 simulated years in two sweeps, and scored 26,624 design runs, each against its twin, on five goals for the network. Its main answer concerns ACP-285, which lowers the minimum rate at which new staking periods are rewarded. A lower minimum rate saves issuance and costs some stake, and each AVAX issued then holds more stake. Under the working weights, equal on the first four goals and half on longer staking, the best minimum rate is 6% to 7%. Keeping 95% of the chain rule's stake and validators in nine runs out of ten needs a minimum rate of about 8.5%, and meeting every threshold, including the duration goal's, needs 9%. ACP-285's 7.5% sits between them, so the thresholds the Foundation sets decide which answer applies.

The question matters because the reward rule sets the price of the network's security. Avalanche pays validators by minting new AVAX from the room left under a cap of 720 million, and the rule that sets each reward decides how fast that room is spent and how much stake the payment holds. ACP-285, activated with the Helicon upgrade on 22 September 2026, lowers the minimum consumption rate, the rate that prices the shortest staking periods, from 10% to 7.5% over a 90-day ramp that ends on 21 December 2026. The Foundation and the community are weighing further changes, from rewarding validators who stay longer to funding part of the reward from network revenue. Each change trades issuance against participation, and each behaves differently when markets rise, fall or pay better elsewhere. A change tested on the live network takes months to show its effect and cannot be undone cheaply, so the research tests it in a model first.

Milestone 1 built the record of every staking period since the network launched in September 2020 and the first model fitted to it. Milestone 2 runs the model on alternative reward designs under many conditions, turns every run into measures of the network's goals, and shows which parameter choices move each goal and by how much. The method is Parameter Selection Under Uncertainty, PSUU, which finds the parameter choices that meet the network's goals across conditions nobody controls. Sections 2 and 3 describe the model and how it is validated. Sections 4 to 6 set out the method, the runs and the goals. Section 7 gives the findings, section 8 the insights for reward policy, section 9 the questions still open and section 10 the next steps. Appendix A maps each deliverable in the agreement to the section that delivers it.

## 2. The model follows every validator's staking period one day at a time

The model, version 0.8.0, simulates the validators securing Avalanche's Primary Network as a population of staking periods. A staking period is one validator's commitment of its own AVAX: a node, an amount, a start and an end. The model starts from the chain's actual state on 18 November 2025, with every open staking period and every node that recently stopped validating, and moves forward one day at a time.

![The staking life cycle in model v0.8.0](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/fig2-model.png)

*Figure 1. Validators arrive, renew, leave and return, and each new staking period mints its reward from the rule under test.*

Each simulated day runs six steps. A staking period that ends either renews on the same node or leaves the active set. A node that left may return. New nodes arrive. Every renewing, returning or new node chooses a duration and an amount to stake. The reward rule under test then prices each staking period that starts that day, and the reward is added to the supply. The surviving and new staking periods become the next day's state.

The reward step reproduces the protocol exactly. Avalanche fixes a staking period's reward when it starts, from its stake, its duration and the supply on that day, using integer arithmetic in a fixed order. The model repeats that arithmetic. Milestone 1 tested it against the chain's record. Of the 3,769,920 stakes, validators' and delegators', that started at the moment the chain accepted them and before 19 November 2025, the formula reproduces 3,769,919 to the last nAVAX, a billionth of an AVAX. Those include all 25,611 such validator staking periods, and the one it misses, a delegation, is off by 31 nAVAX. Issuance in the model is therefore the protocol's issuance for the staking periods that start.

The behavioural steps are fitted to the chain's own record. The odds that a staking period renews depend on the node's completed periods, its record of returning, its duration and its stake. The daily odds that a departed node returns depend on how long it has been out. New arrivals follow the daily counts of the past year. Durations and stake amounts follow what similar nodes chose before, and a node stakes only if its amount clears a fitted minimum. Each of these five parts is fitted by maximum likelihood to the year or two of decisions before 18 November 2025. Each run refits all of them except that minimum on a fresh resample of the record, so the spread across runs carries the uncertainty of the fit as well as the chance in validators' choices.

How strongly validators respond to a change in the reward rate is set rather than fitted. The rate has drifted slowly with supply for six years, and ACP-285's ramp is the first change to the shape of the reward curve that the record can measure. The model therefore treats the response as an input with two parts, one for renewal and one for arrival. Each runs from none to 0.1 per percentage point of reward rate, a range chosen to span from no response to a strong one. At 0.1, a reward rate one point lower cuts the odds of renewal and the rate of arrivals by about a tenth. A stress level of 0.3 tests what lies beyond the range.

The model covers validators' own stake, with durations chosen as in the past. Delegated stake, the AVAX price and a choice of duration that responds to the reward come in the next model versions, which section 10 places on the path to Milestone 3. Longer staking, one of the two aims of ACP-285 that the Foundation chose, is therefore the goal the model can test least well.

## 3. The model is judged by whether it forecasts better than simple alternatives

A model of validator behaviour earns trust when it forecasts what validators did better than simple rules do, on data it was not fitted to. The Foundation set that direction in its reviews. Eric Lu said on 31 July 2026 that he never expected the model to fit the time series. On 14 August he asked "what's the standard we hold in the end to say, okay, this is the model we want to settle on … we have to have some kind of criteria."

The standard compares the model's forecasts with three simple ones. The first holds today's value. The second extends today's value with the spread of its past changes. The third is a small time-series model. Each forecast is a full distribution of outcomes, so it is scored with the continuous ranked probability score, CRPS, which rewards a forecast for being close to what happened and no wider than it needs to be. The score is divided by the average one-day change in stake before each forecast date, so that scores compare across dates. A lower score is better.

Model v0.8.0 was chosen by a rule fixed on 6 October 2026, before any score existed. A candidate change entered the model only if it forecast its own decisions better on events left out of its fit and left the model's forecasts no worse at 19 forecast dates from July 2022 to October 2025. Three of eight candidate changes passed, and two remain in v0.8.0, because the third was replaced by a better form of the same idea. On those dates, v0.8.0 forecasts validator stake better than every simple alternative and better than v0.7, the version before it, at every horizon tested.

| Validator stake, scaled CRPS, lower is better | 30 days | 90 days | 180 days |
| --- | --- | --- | --- |
| Model v0.8.0 | 4.41 | 5.15 | 5.54 |
| Model v0.7 | 6.18 | 11.88 | 15.85 |
| Today's value with the spread of its past changes | 5.38 | 5.69 | 7.54 |
| Small time-series model | 5.48 | 6.86 | 9.34 |
| Today's value | 6.80 | 7.58 | 9.80 |

![Forecast skill of v0.8.0 against the simple forecasts](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/fig8-validation.png)

*Figure 2. Version 0.8.0 forecasts validator stake best at 30, 90 and 180 days. Its lead over the strongest simple forecast is clearest at 180 days.*

The model's lead is largest over months, the horizon over which reward policy acts. At 180 days its score is 27% lower than the best simple forecast's, with a one-sided p of 0.04 on the 17 forecast dates that have 180 days of record after them. Those dates were also used to choose the model, so the held-back test below is the stricter check. For the number of active validators, the small time-series model forecasts better at all three horizons, by 10% to 16%, and the next model versions target that measure.

A held-back test checks the model on a period it has never been fitted or chosen on, from the Granite upgrade on 19 November 2025 to Helicon. The test forecasts validators' own stake 90 days ahead from eight dates in that period. It scores a single forecast, the average of the model's runs, so its simple forecasts are those suited to a single number: no change, the 180-day trend and a small model of weekly changes. It uses the mean absolute scaled error and a Diebold-Mariano test of whether the model's lead is larger than chance. The rule was frozen on 27 October 2026, before any score was computed, and the result will be presented at Workshop 1.

The test matters because the model's year of runs from 18 November 2025 sits below where the chain went. Under the chain's own rule, the model's validator stake falls from 160.3 million AVAX to a mean of 124.2 million a year later, with 80% of runs between 97.7 and 151.0 million. On the chain, validator stake was 132.5 million AVAX on 17 May 2026, inside the model's range for that date, and 170.3 million on 26 October 2026, above its range. The model draws new arrivals from the pattern of the year before 18 November 2025 and carries none of Helicon's new rules, such as 48-hour staking periods and automatic renewal, so it continues that year's patterns. Every finding in section 7 compares a design with the chain's rule on the same simulated future and is stated as a share of it, which removes the level from the comparison, though not every effect of it. The held-back test measures the level itself.

## 4. PSUU scores every design against the network's goals across the futures sampled

Parameter Selection Under Uncertainty runs a model many times over combinations of the settings a decision maker controls and the conditions it does not, then scores each run against stated goals. BlockScience developed the method and used it to choose the token issuance of Subspace Network from more than 200,000 simulated runs. The method looks for choices that meet the goals across all the futures sampled, without predicting which future will happen.

A PSUU study has three kinds of input. The first is the design: a reward rule and the parameters that set it, such as ACP-285's minimum consumption rate. The second is the scenario: conditions outside the network's control, such as the yield an investor could earn elsewhere or the direction of the market. The third is behavioural uncertainty: how strongly validators respond to a change in reward. Each combination of the three is one run of the model, called a trajectory, and each trajectory follows the network day by day for a year. The full set of runs is called a sweep.

Each trajectory is reduced in two steps. The first step aggregates it into measures, such as the AVAX issued over the year, the validator stake at its end and the network's net inflation. The grant proposal calls these key performance indicators, KPIs. The second step turns the measures into utilities, scores between zero and one that express how well the run serves each goal. A run that issues less while keeping its validators scores high on both the issuance goal and the participation goal, and a run that loses a third of its stake scores low on participation however little it issued.

The utilities are then analysed as a function of the design's parameters. Random forests, ensembles of decision trees, learn which parameters decide each goal's utility and rank them by importance. Response curves trace how each goal's utility rises or falls as one parameter moves across its range, with the spread across conditions and behaviour drawn around it. Together they show which value of each parameter serves the network's goals, how sure that answer is, and under which conditions it fails.

![The PSUU loop: designs, scenarios and behavioural uncertainty feed the model, whose runs become measures, utilities, forests and response curves](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/fig1-method.png)

*Figure 3. The PSUU method as Milestone 2 applies it.*

Each run of a design has a twin that uses the chain's own rule on the same simulated future: the same random draws, the same fitted parameters and the same conditions. Both runs compute every reward with the protocol's formula. The difference between a run and its twin is the design's effect on that future, and every result in section 7 is measured that way. The effect still varies from one future to another, and that variation is what the analysis reads as chance.

## 5. The first sweep ran four designs at four outside yields

Milestone 2 ran the model 132,800 times, each run a year from 18 November 2025. The runs cover four reward designs, each across its own parameter range, four levels of outside yield and the full range of validator response. Every design is compared with the chain's own rule as it ran: the rule before ACP-285 until Helicon on 22 September 2026, day 308 of a run, then ACP-285's ramp.

| Design | What it changes | Parameter and range |
| --- | --- | --- |
| ACP-285's ramp, started early | Starts ACP-285's 90-day ramp on the first day of the run, ten months before the chain did | The target minimum consumption rate, 5% to 10%. ACP-285 sets 7.5% |
| The rule before ACP-285 | Keeps the minimum consumption rate at 10% for the whole year | None. It shows what Helicon changed |
| A tenure boost | Pays validators more as they complete more staking periods | The extra reward at full tenure, 0 to 20% |
| A quadratic duration curve | Pays less for shorter staking periods than the current straight-line curve | The curve's exponent, 1 to 3. One is today's shape |

The outside yield stands for the return a validator could earn elsewhere, at 3%, 5%, 7% and 10% a year. The model has no AVAX price, so both the reward and the outside yield are read in AVAX terms. A higher outside yield makes staking less attractive, and through the response inputs it lowers renewal and arrivals.

The runs are arranged so that the variance of every result can be divided among its inputs. Within each design and yield, the parameter values come from a Sobol sequence, which spreads points evenly through the range, in the arrangement that Saltelli's method needs to attribute variance. Further runs repeat 64 points with eight random draws each, to measure how much of the spread is chance, and others push the response to the stress level of 0.3. The 74,176 design runs share 58,624 twin runs under the chain's rule, because runs that differ only in their design share one twin.

![The sweep design](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/fig3-sweep-design.png)

*Figure 4. What the sweep varies and how many runs each part holds.*

Every run finished. Each wrote its results with a hash, and a receipt names the code, the input data and every output, so anyone with the repository and the pinned data can run any row again and check that it matches on the same environment. A second sweep of 67,087 runs adds four parameters of the protocol's own reward rule and three market conditions, and section 7.6 gives its results.

A new reward design enters the model as one rule. Any rule that turns a staking period's stake, duration and start, and the node's completed periods, into a reward can be written as one class of the model's reward interface. The class carries bounded parameters and a check that rejects a rate that falls with duration or turns negative. Each of the four designs above is such a class. A proposal from the Foundation is written the same way, given a neutral setting that reproduces the chain's rule, and run through the same sweep and analysis. The interface is how the research meets the agreement's aim of evaluating a new proposal in under five business days.

## 6. Five goals score every run against one working objective

The research works to one objective: buy the most validator security for each AVAX issued, while security, participation and the cost to holders stay within thresholds the network can accept. A reward rule makes an attack on the network cost more than it could gain, and every AVAX it pays dilutes the holders who do not stake, so security and issuance are the two sides of every design. Matias Antonio of the Foundation wrote that a reward parameter has "no right value" in the abstract, because "what counts as right depends entirely on the objective" ([Matias A., 2026](https://www.linkedin.com/pulse/from-static-constants-dynamic-variables-where-avalanches-matias-a-xh02e)). The objective is the research's proposal, and question Q1 in section 9 asks the Foundation to confirm or replace it.

Three sources already named goals, and the five goals below unite them. The grant proposal grouped seven KPIs under incentive alignment, participation distribution and network security, and called them a starting point. ACP-285 named three aims: reduce inflation, extend the security budget and encourage longer stakes. Asked on 14 August 2026 which aims mattered most, Eric Lu chose reducing inflation and encouraging longer stakes. Each goal below traces to at least one of those sources.

| Goal | What it asks | Measure, against the chain's rule on the same run | Threshold a run must meet |
| --- | --- | --- | --- |
| G1 Security holds | Validators' own stake stays close to what the chain's rule keeps | Validator stake kept, and the worst 30-day fall in stake | At least 95% of the stake, and a worst month no more than 2 points deeper |
| G2 Validators stay and stay spread | The set keeps its size and its spread, and validators keep their margin | Active validators kept, the Nakamoto coefficient, and the return margin | At least 95% of the validators, at most one node fewer, and at most one point of margin lost |
| G3 Holders pay less | The design issues less and inflation stays low | Issuance saved, and net inflation | Some issuance saved, and net inflation at most 5% a year |
| G4 Security per AVAX issued | Each AVAX issued holds at least as much stake | Validator stake kept divided by the share of issuance kept | At least 1 |
| G5 Longer staking | Validators stake for longer | Stake-weighted duration of new staking periods | No more than 1% shorter |

Three measures need a definition. The return margin is the reward rate validators earn, averaged by stake, less the outside yield and a 1.5% yearly operating cost. The Nakamoto coefficient is the fewest validators that together hold a third of the stake. Net inflation is the AVAX issued less the AVAX burned in fees over a year, as a share of total supply. In the runs it counts issuance to validators' own stake, with fees burned at their past average.

Every measure is read against the twin under the chain's rule, for two reasons. The twin shares every random draw, so the measure is the design's effect on that future. The grant proposal's absolute thresholds also sit where no design can reach them on validators' own stake. Its floor of 1,000 validators is above the 819 active on 18 November 2025, and its staking-ratio band of 50% to 60% counts delegations, which model v0.8.0 does not yet carry. The return margin has the same problem from the market's side. At an outside yield of 5% or more, the chain's own rule pays validators less than the outside yield plus their costs, so an absolute threshold of zero would score the market rather than the design.

Each measure becomes a utility between zero and one. The utility is zero at a level the network should not accept, one at a level that fully meets the goal, and a straight line between the two. Issuance saved, for example, scores zero at no saving and one at a fifth less issuance, so a saving of about 13% scores about 0.65. A goal's utility is the weighted mean of its measures' utilities. Within G1 and G3 the main measure, stake kept or issuance saved, carries twice the weight of the other.

The goals are judged in a fixed order. First, a design meets a goal at a setting when at least 90% of its runs there meet every threshold of that goal, across the whole range of validator response. A setting that meets every goal is acceptable. Second, among acceptable settings, the trade between issuance saved and stake kept is shown in full, because how much stake is worth one million fewer AVAX is the Foundation's judgement to make. Third, for a single ranking, the combined utility is the weighted mean of the five goal utilities. The first four goals carry equal weight, and G5 carries half, because v0.8.0 changes duration only through which validators renew. The Foundation sets its own weights at Workshop 1, by ranking how much it values moving each goal from its worst to its best tested level. Section 9 lists the other choices the goals leave to the Foundation.

## 7. Findings

Every number in this section compares a design's run with its twin under the chain's rule, from the first sweep, and every range runs across the four outside yields unless the text says otherwise. Issuance and stake count validators' own stake only.

### 7.1 ACP-285's ramp started early saves 13% of issuance and keeps 97% of stake

Starting ACP-285's ramp on the first day of the run, rather than on day 308 as the chain did, saves 13.0% to 13.4% of the AVAX the chain's rule issues to validators' own stake in the year, or 0.85 to 1.02 million AVAX. The ramp keeps 97.1% to 97.3% of the chain rule's validator stake and 94.9% to 95.5% of its active validators, and it lowers net inflation by 0.18 to 0.22 percentage points, to between 1.16% and 1.35% a year. The ramp saves issuance in 97.2% of its runs. The rest have target rates near 10%, where the ramp barely lowers rewards while the chain's rule switches to 7.5% on day 308.

![Issuance saved and validator stake kept by each design at one year](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/fig4-design-comparison.png)

*Figure 5. At one year, ACP-285's ramp started early saves about 13% of issuance and keeps about 97% of validator stake at every outside yield. The tenure boost holds a little more stake with about 9% more issuance.*

The other three designs move issuance far less or in the other direction. The quadratic duration curve saves 1.0% of issuance and keeps all of the stake. Short staking periods, the ones it pays less, held little stake in the year before the run began. The tenure boost issues 8.6% to 8.9% more, 0.58 to 0.65 million AVAX, and keeps 101.4% to 101.5% of the stake and 102.4% to 102.5% of the validators. The rule before ACP-285 issues 0.7% to 0.8% more than the chain's rule, all of it after day 308. The designs rank in the same order at every outside yield on every measure and in every band of response, except for one near tie in stake kept between the quadratic curve and the rule before ACP-285.

### 7.2 Each point of minimum rate trades 5.5 points of issuance for 1.3 of stake

Each percentage point by which the ramp lowers the minimum rate saves about 5.5 points of issuance and gives up about 1.3 points of validator stake. ACP-285's own 7.5% saves 13.3% of issuance and keeps 97.2% of stake, on average 0.95 million AVAX less issued and 3.5 million AVAX less validator stake at the end of the year.

| Target minimum rate | Issuance saved | Validator stake kept | 10th percentile of stake kept | Active validators kept |
| --- | --- | --- | --- | --- |
| 5% to 6% | 24.1% | 94.7% | 89.6% | 90.8% |
| 6% to 7% | 18.7% | 95.9% | 91.5% | 92.9% |
| 7.25% to 7.75% | 13.3% | 97.2% | 93.5% | 95.0% |
| 8% to 9% | 7.8% | 98.3% | 95.7% | 97.3% |
| 9% to 10% | 2.1% | 99.8% | 98.4% | 99.7% |

Both columns are close to straight lines in the minimum rate, so the value at any rate between 5% and 10% can be read from the table. The lower tail of stake kept widens as the rate falls. At 5% to 6%, one run in ten keeps less than 90% of the stake.

### 7.3 The design sets issuance and validators' response sets the stake it costs

The design's own setting explains almost all of the spread in issuance saved. Under the ramp, the minimum rate's rank correlation with issuance saved is −0.98 at every yield. The rate explains about 96% of the variance of issuance saved where that estimate converged, meaning it moved by less than 0.02 when the number of runs doubled. Under the tenure boost the boost explains about 93%, and under the quadratic curve the exponent about 70%. The analysis rates a relationship High confidence when its sign is the same, with an interval that excludes zero, in each of nine bands of validator response, three for renewal by three for arrival. The minimum rate's relationship with issuance saved is rated High at every yield.

![Rank correlations between each design's inputs and its outcomes](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/fig5-correlations.png)

*Figure 6. Each design's own setting moves its issuance saved almost one for one. The stake and the validators it keeps also move with how strongly validators respond to the reward.*

A design moves validator stake only through validators' response to the reward. With no response, the ramp keeps exactly all of the chain rule's stake and validators in every run. Across the response range it keeps about 97%, and at the stress level of 0.3 about 87%. The spread in stake kept comes from the minimum rate, the response and chance in shares of about a third, a sixth and a half. Chance here covers the run-to-run variation in validators' choices and the uncertainty in the model's fitted parameters. The minimum rate's relationship with stake kept is also rated High at every yield, and its sign never reverses in 96 checks across response strengths.

![Where the spread in each outcome comes from](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/fig6-variance.png)

*Figure 7. The design's setting decides issuance saved. The spread in stake kept comes from the setting, validators' response, and chance with the uncertainty of the fitted parameters, and the setting moves stake only when validators respond. Hatched segments come from estimates that have not converged.*

The issuance a design saves is therefore a narrow range, and the stake it keeps a wide one. How much stake a design costs depends on the strength of validators' response, which section 8 shows the record cannot yet measure.

### 7.4 The thresholds favour a minimum rate near 9% and the weighted score one near 6%

Scored against the five goals of section 6, the ramp has the highest combined utility of the four designs. It scores 0.70 to 0.71 at every outside yield, against 0.60 for the quadratic curve, 0.58 for the rule before ACP-285 and 0.53 for the tenure boost. The tenure boost and the rule before ACP-285 issue more than the chain's rule, so they fail G3 in almost every run and meet every goal at no setting.

![Share of runs passing each goal, by design and outside yield](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/pass-rates-365.png)

*Figure 8. Share of runs that pass each goal at one year, pooled over each design's setting. The ramp passes the issuance goals almost always and the participation goal in about half of its runs.*

The ramp's minimum rate decides which goals it meets, and raising it helps some goals while hurting others. Raising the rate from near 5% to near 10% lifts the utility of security from 0.68 to 0.99 and of participation from 0.53 to 0.99. It lowers the utility of holders paying less from 0.93 to 0.25 and of security per AVAX issued from 1.00 to 0.28. The response curves show each goal moving steadily with the rate at every outside yield. The forests find the rate about eight times as important as the renewal response for the combined utility. Outside yield barely moves any goal, because every measure is read against the chain's rule under the same yield.

![Response curves of each goal's utility against the ramp's minimum rate and validators' response](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/response-ramp-365.png)

*Figure 9. Each goal's utility against the ramp's target minimum rate, labelled floor, and against the renewal and entry responses, at one year. Lines are the mean at each outside yield, the grey band holds 80% of runs, and the dashed line is the forest's estimate.*

The thresholds and the weighted score then point to different minimum rates.

| Target minimum rate | Combined utility | Runs meeting every threshold | Runs meeting G2 |
| --- | --- | --- | --- |
| 6% to 6.5% | 0.77, the highest | 7% | 9% |
| 7% to 7.5% | 0.76 | 40% | 45% |
| 7.5% to 8% | 0.72 | 53% | 60% |
| 8.5% to 9% | 0.65 | 88% | 99% |
| 9% to 9.5% | 0.63 | 93% | 100% |

Under the working weights, equal on the first four goals and half on longer staking, the combined utility is highest at minimum rates of 6% to 7%, where issuance falls by about a fifth and stake and validators fall by a few percent. At least 90% of runs meet every threshold only at 9% to 9.5%, or 8.5% to 9.5% at a 3% outside yield, where the saving is about 2% to 5% of issuance. The thresholds that bind are G1's and G5's at 8.5% to 9%, where keeping 95% of stake and validators together already holds in 95% of runs, and G2's validator count below 8.5%. ACP-285's own 7.5% sits between the two. It scores within about 0.04 of the best combined utility and meets every threshold in 40% to 53% of its runs.

The 9% answer rests on the assumed response. With no response the ramp keeps every validator at any minimum rate, so the security and participation thresholds bind only because the response range assumes validators react. The 8.5% edge also rests on the count of active validators, the measure the model forecasts least well. The full history bounds the response from above, as insight I6 explains, and in the lowest third of the range the thresholds bind less: with the renewal response in the lowest third, every threshold holds from a minimum rate of 8% to 9.5%. A stronger response moves the weighted optimum up as well, from 5.5% to 6% when the renewal response is in the lowest third of its range to 6.5% to 7% in the highest. The quadratic curve meets every threshold in at least 90% of runs at exponents from 1.4 to 3 at every yield, because it changes so little. Its combined utility of about 0.61 is below the ramp's at every minimum rate under 9.5%. At 180 days the picture is the same. The ramp's best minimum rate is again 6% to 6.5%, at a combined utility of 0.78, and every threshold holds at 8.5% to 10%. A replication on 16,384 fresh runs, with new random draws and new parameter draws, gives the same best minimum rate, 6% to 6.5% at 0.771 against 0.772. Its region where every threshold holds reproduces at outside yields of 3% and 5%, widens to 8.5% to 9.5% at 7%, and is empty at 10%. Pooled over the yields its best cells pass in 89.7% of runs, just under the line, so the edges of the region are less firm than its centre.

In the agreement's terms, these results are the recommendation tiers. The point estimate for the ramp is the minimum rate with the highest combined utility under the working weights, 6% to 6.5%, with 80% of runs scoring between 0.69 and 0.85. The per-goal ranges are the rates at which each goal alone holds in 90% of runs: below 9.5% for G3 and G4, and 8.5% or more for G1, G2 and G5. The global range, where every goal holds, is 9% to 9.5%. All tiers stay provisional until the recommended settings are rerun on fresh random draws in Milestone 3.

### 7.5 Validators' margin over the outside yield follows from the yield itself

Net inflation stays under 5% a year in every one of the 132,800 runs, with the highest at 2.66%. That line, which Eric Lu called high on 3 July 2026, does not limit any design tested on total supply. Section 9 asks which denominator the Foundation wants.

Validators' margin over the outside yield is negative under every design once the outside yield reaches 5%, and the arithmetic of the inputs explains it. The designs pay average reward rates of 5.1% under the ramp to 6.2% under the tenure boost, against 5.7% under the chain's rule. Less a 1.5% operating cost, no design clears an outside yield of 7% or more, and only the tenure boost comes near 5%. The margin is negative in every run of every design at outside yields of 7% and 10%, and in at least 91% of runs at 5%. At 3%, every design except the ramp keeps it positive in every run, and the ramp in 90%. The reward rates the designs pay differ by about one percentage point, while the outside yields tested differ by seven.

![Pass shares by design setting and outside yield](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/fig7-risk-regions.png)

*Figure 10. Net inflation passes everywhere. The validator margin passes at a 3% outside yield and fails at 5% and above, whatever the design's setting.*

A search for failure regions confirms that the setting rarely matters for the margin. The patient rule induction method, PRIM, looks for the box of inputs where a failure concentrates on half of the runs and confirms it on the other half. A failure condition is one design, outside yield, horizon and failing rule, 384 in all. The method confirmed a region for 197 of them. In 189 of the 197, the region spans the whole sampled range of every input, so the failure holds at that design and yield whatever the setting and the response. Only eight regions bound a setting. At a 5% outside yield, for example, the ramp's margin at zero operating cost fails at minimum rates from 5.00% to 7.67%, and the quadratic curve saves no issuance at exponents below about 1.3.

### 7.6 Market conditions leave the ranking unchanged, and a lower maximum rate scores highest

A second sweep of 67,087 runs, from the same origin, crossed the four designs with bear, neutral and bull markets and swept four parameters of the protocol's own reward rule. It repeats 512 runs of the first sweep with their twins, and all 28,672 of their values match exactly, so the two sweeps can be read together. One run broke the model's check that stake stays within supply and is recorded as failed.

The market condition, as model v0.8.0 carries it, barely moves any result. Each market shifts validators' odds of renewing and the rate of arrivals, measured from the record before the held-back period. Under ACP-285's ramp, stake kept, validators kept and issuance saved each move by about one point or less between bear, neutral and bull at every outside yield. The ramp still keeps 97.2% of stake and saves 13.1% of issuance, its best minimum rate is still 6% to 6.5%, and every threshold still holds at 9% to 9.5%. The four designs rank in the same order in every market. The reason is the paired design itself. A market shifts a design and its twin under the chain's rule alike, so the difference between them hardly moves. Markets may matter more once the model carries the AVAX price and validators weigh rewards in dollars, which a later model version adds.

The protocol's own reward rule, swept over its minimum rate of 5% to 15%, the gap to its maximum rate of 0 to 8 points, and its shortest and longest staking periods, behaves differently. Over that whole space it issues 59% more than the chain's rule on average, because most of the space pays higher rates from the first day with no ramp. It also keeps more stake and validators, mostly through its shortest-period setting: a longer minimum period raises stake kept even with no response to reward, so the gain comes from how the model bounds durations rather than from validators' response. Only 1.5% of its runs meet every threshold, no setting meets them all in 90% of runs, and the best reaches 17%. The settings with the highest combined utility, 0.87, pair a minimum rate of 5% to 8.3% with a maximum rate of 5% to 11%, a shortest period of 14 to 39 days and a longest of about 307 to 365 days. They meet every threshold in only 1.3% of their runs, because they pay validators about 1.8 points less than the chain's rule, and much of their stake gain comes from the shortest-period setting. The maximum rate, 12% today, is the second strongest setting after the minimum rate, and it is the lever ACP-285 left alone. These figures are upper bounds on stake and issuance. In 11,957 of the second sweep's 67,087 runs, all under this rule, staking passed half of supply by the end of the year, a level at which a limit on the AVAX left unstaked would admit a third to 45% fewer new validators than model v0.8.0 does. Model v0.8.1 adds that limit, and the rule's runs will be repeated with it.

## 8. Insights

Seven insights for reward policy follow from the findings.

### I1. The thresholds the Foundation sets for security and participation decide the best minimum rate

The issuance goals hold across most of the ramp's range, and the thresholds on security and participation bind. Keeping 95% of the chain rule's stake and validators in nine runs out of ten needs a minimum rate of about 8.5%, and meeting every threshold needs 9%, which saves only 2% to 5% of issuance, while the working weights favour 6% to 7%. ACP-285's 7.5% sits between them. Whether those thresholds are hard requirements or goals to weigh against the others is therefore the most useful decision for Workshop 1.

### I2. ACP-285 makes each AVAX of issuance hold more stake

Under the ramp, validator stake per AVAX issued is about 12% higher than under the chain's rule, because issuance falls by 13% while stake falls by 3% across the response range. Compared with the chain's rule, the ramp ends the year with 3.5 to 3.9 AVAX less validator stake for each AVAX it does not issue during the year. How much stake is given up depends on how strongly validators respond: none with no response, about 3% across the range and about 13% at the stress level. Whether the exchange is worth making depends on how much security the network needs, which is the Foundation's judgement.

### I3. A higher base rate holds stake more cheaply than a tenure reward

Moving along each design's own setting, a point of minimum rate moves about 4.0 AVAX of year-end validator stake for each AVAX of issuance, and the tenure boost about 2.3. Compared with the chain's rule, the tenure boost holds 2.7 to 3.0 AVAX more stake for each extra AVAX it issues. A design that aims to hold more stake reaches it at a lower cost in issuance by paying a higher base rate than by paying long-serving validators more. Both rates depend on the strength of validators' response, so the order is firmer than the size.

### I4. Paying less for short staking periods saves little because little stake is short

The quadratic curve cuts the reward on short staking periods and saves only 1% of issuance, with durations chosen as in the past. The chain since Helicon shows why. From 22 September to 26 October 2026, staking periods of under a week were about a fifth of new validator staking periods but a third of a percent of their AVAX-days, by our record of the P-Chain. A design aimed at short stakes reaches little AVAX.

### I5. Rewards funded by revenue are the design to test when markets pay well elsewhere

The designs tested change validators' average reward rate by about one percentage point, while the outside yields tested span seven. At an outside yield of 5% or more and a 1.5% operating cost, validators earn less than their alternative under every design in at least 91% of runs. Holding validators when markets pay well elsewhere needs more reward, and reward funded from somewhere other than new issuance does not dilute holders. The revenue-funded rewards the Foundation has proposed are the first design to test for that reason.

### I6. The price record bounds validators' response, and a comparison will measure it

The issuance a design saves is predictable, and the stake it keeps depends on validators' response, which the model takes as a range from 0 to 0.1. A first estimate from the five weeks of ACP-285's ramp on chain puts the renewal response, in the model's unit of the 30-day reward gap, at 1.26 per percentage point, with a 95% interval from −1.9 to 4.4, on 555 renewal decisions. The interval is about 63 times as wide as the range, so the data rule out no value in it. The ramp alone will not close that gap. The reward gap stops growing when the ramp ends on 21 December 2026, and week-to-week drift in renewal then sets a floor, so even by late January 2027 the interval stays near ±1, ten times the range. The record since 2020 holds far more variation. From January 2021 to November 2025 it holds 50,957 renewal decisions and 6,520 first-ever arrivals, all before the held-back period. The offered rate fell steadily for six years as supply grew, but that fall moves in step with the network's age, so it cannot be told apart from the network growing older. The AVAX price ranged 42-fold, from \$3.21 to \$134.47, and it bounds the response. Read as a response to the dollar margin after a \$2,400 yearly running cost, it puts the renewal response at 0.019, with an interval from −0.008 to 0.051, and the entry response at 0.038, from −0.018 to 0.089. Both rule out the stress level of 0.3 and the upper part of the swept range, and neither rules out zero. The bound assumes validators weigh a rise in the price like a rise in the rate. The price also moves with market cycles that change validators' alternatives, its renewal timing check fails, and one variant reaches 0.13. A comparison of staking periods whose rate ACP-285 cut against one-year periods whose rate it left unchanged measures the response to the rate itself, and it needs more one-year periods to end before it can decide.

### I7. The maximum rate is the parameter ACP-285 left alone

ACP-285 lowered the minimum rate, which prices the shortest staking periods, and left the maximum rate of 12%, which prices the longest. Every staking period between the two is priced on the line between them, so the maximum rate moves the reward of every period longer than the shortest. In the second sweep the maximum rate was the second strongest setting of the protocol's rule after the minimum rate, and the settings with the highest combined utility lowered it to 5% to 11%. Those settings met every threshold in only 1.3% of their runs, because they paid validators about 1.8 points less than the chain's rule. A change to the maximum rate, tested against the Foundation's thresholds and with the minimum rate held near ACP-285's, is the next design to evaluate.

## 9. Open questions

Five questions are for the Foundation, and Workshop 1 is designed to answer them.

- Q1. Is the purpose of the reward rule to buy the most security for each AVAX issued, within thresholds on security and participation?
- Q2. What value should the cost of an attack exceed: the stablecoins and bridged assets on the C-Chain, a day's settled value, or AVAX's market value?
- Q3. Should net inflation be measured on total supply or on circulating supply, and is 5% a year a hard ceiling? On circulating supply the same runs read about 1.8 times higher, and the highest come close to 5%.
- Q4. Is keeping 95% of validators a hard threshold, how much validator stake would the Foundation give up to issue one million fewer AVAX a year, and is longer staking wanted for itself or for steadier stake?
- Q5. What does it cost a year to run a validator, for an institution and for a small operator, and which outside return should a validator's reward be compared with?

Four questions are for the research, and the next model versions are built to answer them.

- R1. How strongly do validators respond to a change in reward? The ramp's first five weeks separate no value in the swept range, and the AVAX price bounds renewal near 0.05 and entry near 0.09. A comparison of staking periods ACP-285 changed against those it did not will measure the response to the rate as one-year periods end.
- R2. How do delegators respond, and how much stake do they add? Delegations enter in the next model version.
- R3. How does the AVAX price move stake and the value of rewards? A price path enters after delegations.
- R4. Do validators choose longer staking periods when longer ones pay more? A duration that responds to reward comes after the price path.

## 10. Next steps

The next steps lead to Workshop 1 on 13 November 2026 and to Milestone 3 in December and January.

| Date | Step |
| --- | --- |
| Friday 30 October 2026 | The full Milestone 2 overview on our call, walking through the model, the method and these results |
| 2 to 6 November | The first timed evaluation of a Foundation proposal, revenue-funded rewards, from request to reviewed results within five business days, compared with paying validators the network's fees |
| From 28 October | Experiments that run continuously on the team's compute server, each testing a stated hypothesis: replications on fresh random draws, bear markets, the stress level of response, and each new design as it is built |
| By 13 November | The held-back test scored, and the results and the code that produced them delivered with every input pinned |
| Friday 13 November | Workshop 1: the whole model, these results and the goals, with the Foundation's answers to Q1 to Q5 |
| 1 to 11 December, and 4 to 15 January 2027 | Milestone 3: the parameter recommendation report, the scenario playbook, the open-source release and Workshop 2 |

Workshop 1 sets the thresholds and weights that the recommendations in Milestone 3 are scored against. Until validators' response is measured, every recommendation is stated across the full range of response, with the value of response at which it would change.

## Appendix A. Milestone 2 deliverables

| ID | Deliverable in the agreement | Where it is delivered |
| --- | --- | --- |
| 2.1 | Full parameter sweep pipeline | Section 5. The pipeline designs a sweep, runs it on any machine with the repository, and writes a hash for every output and a receipt for every run. Milestone 2 ran on the team's dedicated compute server |
| 2.2 | 50,000 or more trajectories across governance and environment space | Sections 5 and 7.6. 132,800 trajectories in the first sweep and 67,087 in the second, which adds four governance parameters and three market conditions, with 512 repeated runs matching exactly |
| 2.3 | Automated computation of all KPIs per trajectory | Section 6. Every trajectory is reduced to its measures with no value missing, and 26,624 design runs are scored, each against its twin, as utilities for five goals |
| 2.4 | Final goodness of fit | Section 3. The forecast standard, the scores that chose model v0.8.0, and the frozen held-back test, whose result is presented at Workshop 1 |
| 2.5 | Decision trees and correlation matrices for all KPIs | Section 7. Rank correlations with bootstrap intervals, variance shares, classification trees, and forests for each goal whose utility varies |
| 2.6 | Parameter regions where staking incentives fail | Section 7. Failure regions confirmed on held-out runs for 197 of 384 conditions, eight of which bound a setting, and the region where every goal holds |
| 2.7 | Model walkthrough and preliminary findings review | The overview on 30 October and Workshop 1 on 13 November |
| 2.8 | Pluggable mechanism interface, evaluation in under five business days, and correlation tables with confidence ratings and tiers | Section 5 for the interface, section 7 for the ratings and tiers, and section 10 for the first timed evaluation |

## Sources

The model, the sweep and the analysis are in the research repository, [bonding-curves/avalanche-phase-ii-research](https://github.com/bonding-curves/avalanche-phase-ii-research). The execution-source links are pinned to commit 5d05910, which ran the first sweep. Selection scores, the held-back test specification and analysis files are pinned to commit 0a5331c, which contains those later additions. Model v0.8.0 is tagged `model-v0.8.0`.

- [The model's daily stages](https://github.com/bonding-curves/avalanche-phase-ii-research/blob/5d05910/src/avalanche_research/model/parts/stages.py): renewal, return, arrival, duration and stake, reward and assembly, section 2.
- [The reward interface](https://github.com/bonding-curves/avalanche-phase-ii-research/blob/5d05910/src/avalanche_research/mechanisms/reward.py): the chain's rule, the four designs and the class a new proposal implements, sections 2 and 5.
- [The measures computed from every run](https://github.com/bonding-curves/avalanche-phase-ii-research/blob/5d05910/src/avalanche_research/model/kpis.py): issuance, stake, validators, net inflation, return margin and duration, sections 6 and 7.
- [Model selection scores](https://github.com/bonding-curves/avalanche-phase-ii-research/blob/0a5331ce57c45897392642f2815a8ccf074747ca/results/model-v0.8.0-selection/development-distribution-summary.csv): the forecast scores of v0.8.0 and the simple forecasts, section 3.
- [The held-back test's specification](https://github.com/bonding-curves/avalanche-phase-ii-research/blob/0a5331ce57c45897392642f2815a8ccf074747ca/validation/lockbox/specification.json): the frozen scoring rule, section 3.
- [The sweep design](https://github.com/bonding-curves/avalanche-phase-ii-research/blob/5d05910/scripts/m2_sweep_design.py) and [the sweep runner](https://github.com/bonding-curves/avalanche-phase-ii-research/blob/5d05910/src/avalanche_research/experiments/sweep.py): the Saltelli arrangement, the paired twins and the receipts, section 5.
- [The analysis protocol](https://github.com/bonding-curves/avalanche-phase-ii-research/blob/0a5331ce57c45897392642f2815a8ccf074747ca/results/m2-analysis/protocol.json) and [the agreement's measures](https://github.com/bonding-curves/avalanche-phase-ii-research/blob/0a5331ce57c45897392642f2815a8ccf074747ca/src/avalanche_research/analysis/m2_contract.py): correlations, Sobol indices, trees, failure regions, confidence ratings and tiers, section 7.
- [The second sweep's code](https://github.com/bonding-curves/avalanche-phase-ii-research/commit/3bb3025c): the governance reward rule and the market settings, section 5.
- [ACP-285](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/285-reduce-minimum-consumption-rate/README.md): the lower minimum consumption rate, its ramp and its aims, sections 1 and 6.
- [Matias A., 2026, on reward parameters as variables](https://www.linkedin.com/pulse/from-static-constants-dynamic-variables-where-avalanches-matias-a-xh02e): "no right value" for a reward parameter without an objective, section 6.

The goal and utility specification, the script that scores every run against it and draws the forests and response curves, and the sweep outputs with their hashes are delivered with the pinned outputs of deliverable 2.2 by Workshop 1.
