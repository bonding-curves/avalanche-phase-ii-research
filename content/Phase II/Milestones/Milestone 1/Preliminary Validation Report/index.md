---
title: "Preliminary Validation Report"
description: "Milestone 1's success criterion: a first goodness-of-fit assessment of staking model v0.7 against the P-Chain's history, covering verification of its protocol layer, forecast scores at 19 dates against simple forecasts, the contract's correlation test, and the held-back test still to come."
status: delivered
source: signed-grant-agreement
tags: ["model-validation"]
---

This report is a first assessment of how well the Avalanche staking model fits history. It tests version 0.7 of the model in three ways: whether its accounting reproduces the chain's records, how well it forecasts validator stake and the number of validators from 19 past dates, and how it scores on the correlation test the agreement names. It finds three things.

1. **The protocol layer is exact.** The model's reward formula matches the chain's recorded reward on 3,769,919 of 3,769,920 stakes that started when they were accepted, before the held-back period. Replaying the recorded commitments reproduces the chain's daily ledger to the nAVAX on all 1,896 complete days from 10 September 2020 to 18 November 2025.
2. **The behavior layer is too simple to forecast stake.** v0.7's error on validator stake is larger than that of simply holding today's value at 30, 90 and 180 days. On the validator count its mean errors are close to those of holding today's value.
3. **The correlation test needs an agreed definition.** The simplest forecast, which is the hardest to beat, has no defined correlation within a forecast window. The report proposes a standard and asks the Foundation for a written answer by 20 October.

The final test, on data held back from every fit, is scored on 27 October 2026.

## Contract requirement

Milestone 1 success criterion:

> Preliminary Validation Report delivered and approved by Avalanche team

Quoted from the [Signed Grant Agreement](/Phase-II/Milestones/Milestone-0/Signed-Grant-Agreement).

## Status

Delivered for the Foundation's review and approval on 8 October 2026. Not yet approved. The held-back test is scored on 27 October 2026, and its result will be added to this page when it lands.

## Result

The result is set out in seven parts: what validation means here, verification, forecast validation, the agreement's correlation test, the held-back test, what v0.7 can be trusted for, and what comes next.

### 1. What validation means here

A simulation model can be wrong in three different ways, and each needs its own test. This part separates them, describes the model under test, and names the standards followed.

#### 1.1 Three kinds of test

**Verification** asks whether the code does what the specification says: here, whether the model's accounting reproduces the chain's records when given the chain's own inputs. It says nothing about whether the model's assumptions about people are right. **Validation** asks whether the specification matches the world: here, whether the rules for renewal and entry produce the paths of stake and validator count the chain followed. **Forecasting skill** is the part of validation that can be scored. A forecast made from a past date, using only the data available then, is compared with what happened next, and its error with that of simple forecasts that use no model. A model has skill only if it beats them.

#### 1.2 The model under test

Version 0.7 is a simulation that follows every open validator **commitment** on the P-Chain, one day at a time. A commitment is one staking transaction: an amount of AVAX a node locks from a start time to an end time. The model has two layers, as the [staking model specification](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/) describes. The **protocol layer** applies the chain's reward formula and keeps its accounts. The **behavior layer** decides, each day, which ending commitments renew and how many new ones enter.

A **renewal** is a new commitment on the same node that starts within seven days after the previous one ends. Any other commitment is an **entry**. v0.7's behavior is two numbers measured before each forecast starts. The **renewal probability** is the share of commitments ending in the 365 days up to seven days before that date whose node started another within seven days. The **entry rate** is the year's entries divided by 365. At the Fortuna upgrade on 8 April 2025 they were 81.68% and 7.61 a day.

Every forecast in this report runs under the chain's own reward rule, so the model's **response**, how strongly renewal and entry move when a design pays more or less than that rule, plays no part in these tests. The chain's history before Helicon does not identify that response, because the reward rule never changed, so the model sweeps it across assumed values when it compares designs. [Behavioral calibration](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/) covers that question.

#### 1.3 Standards followed

The model's specification follows the **ODD protocol** (Overview, Design concepts, Details), the standard for describing individual-based models, in its 2020 update (Grimm and others, 2020). The record of testing follows the structure of **TRACE** (Grimm and others, 2014), which documents model development, testing and analysis as separate elements: verification of the implementation, then evaluation of the model's output against data. Results are reported with their model version, inputs and settings, as the guidelines of Rahmandad and Sterman (2012) ask.

The forecast tests follow forecasting research. Forecasts are scored **out of sample**: each is made from data available up to its start date and compared only with data after it, as Tashman (2000) recommends. Errors are scaled by how much each series usually moves, with the measure of Hyndman and Koehler (2006), so that errors can be compared across dates and quantities.

#### 1.4 How this test relates to the proposal

The proposal's [goodness-of-fit protocol](/Phase-II/Milestones/Milestone-0/Proposal/#goodness-of-fit-protocol) starts the model from the observed state in January 2025, simulates through December 2025, and compares the result with what happened. Its targets are a correlation above 0.90, a staking ratio error under 2 percentage points, trend direction matched more than 85% of the time, and changes timed within 7 days. This report changes the design in two ways. First, it starts forecasts from 19 dates instead of one. One window cannot separate a model's skill from the luck of that window, and a run from January to December 2025 would end inside the held-back period, which begins on 19 November 2025. Second, it scores forecasts with the scaled error against simple forecasts and reports the correlation beside it, for the reasons in [Part 4](#4-the-contracts-correlation-test). The proposal's other three metrics are not computed in this report. Which measures define the final test is a question for the Foundation in Part 4.

### 2. Verification

Verification comes before any forecast, because a comparison of reward designs means nothing if the model's accounting differs from the chain's. This part checks the protocol layer against the chain in two ways, then the model's internal consistency.

#### 2.1 The reward formula against the chain

The protocol fixes each stake's reward when the stake starts and pays it when it ends. For a stake $s$ committed for $D$ days, it pays

$$
\text{reward}(s, D, S) = (C - S)\cdot\frac{s}{S}\cdot\frac{D}{P}\cdot r(D), \qquad r(D) = r_{\min} + (r_{\max} - r_{\min})\,\frac{D}{P} \tag{1}
$$

where $C$ is the supply cap of 720 million AVAX, $P$ the 365-day minting period, and $r(D)$ the **consumption rate**, which rises from $r_{\min}$ for the shortest commitment to $r_{\max}$ for a full year. Before Helicon $r_{\min}$ was 10% and $r_{\max}$ 12%. $S$ is the **supply counter**: a running total the P-Chain keeps of the genesis supply plus every reward promised, read when the stake starts.

The model's implementation of Equation 1 works in integer **nAVAX**, one billionth of an AVAX, as the chain's own code does, with the same order of integer divisions. It was checked against the chain's own recorded potential reward on every stake that started when it was accepted.

Before the held-back period, it reproduces 3,769,919 of 3,769,920 such stakes exactly, to the nAVAX: all 25,611 validator commitments and all but one of 3,744,309 delegations. The one miss is a delegation 31 nAVAX apart. The 685,201 stakes in the held-back period all reproduce too.

![Share of recorded rewards the formula reproduces exactly, by role and start](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/reward-kernel-reproduction.png)

*Figure 1. Share of recorded potential rewards the model's formula reproduces exactly, by role and by whether the stake started at acceptance. Pale bars are the held-back period, shown as description. Source: every staking period recorded on the P-Chain from 10 September 2020, priced by the model's formula at model v0.7. Data: [reward-kernel-reproduction.csv](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/reward-kernel-reproduction.csv).*

Stakes that started after they were accepted, which the protocol allowed before the Durango upgrade, reproduce only 19% to 25% of the time. The likely cause is the input, not the formula: the chain priced these stakes at the supply counter on their start day, while the record holds the counter on their acceptance day. The model prices every simulated renewal and entry at its own day's counter, as the chain does.

#### 2.2 The replay against the daily ledger

The **replay** feeds every recorded start, end and reward payment through the model's accounting, with no behavior at all, and compares each day's totals with the chain's **daily ledger**, one row per UTC day of validator and delegated stake, their counts and rewards paid. The replay and the ledger are built by separate code paths from one record, so their agreement is an accounting identity: if either path mishandles a commitment, a day, or a unit, the two disagree.

The replay equals the ledger to the nAVAX on all 1,896 complete days from 10 September 2020 to 18 November 2025. The difference is zero on every day for validator stake, delegated stake, rewards paid and both counts.

![The replay against the daily ledger, 2020 to 2025](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/replay-against-ledger.png)

*Figure 2. Above: validator stake recorded on the ledger (wide green) and replayed by the model (thin black). Below: the daily difference in nAVAX, zero on every day. The replay stops where the held-back period begins. Source: the P-Chain staking record and daily ledger, replayed by model v0.7. Data: [replay-against-ledger.csv](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/replay-against-ledger.csv).*

#### 2.3 Invariants, tests and the specification hash

The model also checks itself as it runs. Four conditions, its **invariants**, are checked at the end of every simulated day, and the first failure stops the run:

1. every stake is non-negative,
2. validator stake equals the sum of the open commitments,
3. the supply counter is within the 720 million AVAX cap,
4. validator stake is within the supply counter.

The library's test suite checks the reward formula on 72 fixed combinations of stake, duration and start, and on every recorded stake (Section 2.1), the replay, and the model's six textbook companions, small models with known answers such as logistic growth and a bathtub stock, which run on the same engine. Every run records a **specification hash** covering the model, every setting and the content of each input table, so two runs with the same hash used the same model, settings and input bytes.

One defect was found after release. At the tagged version the daily output table stored the supply counter as a floating-point number, and long runs lost up to 4 nAVAX in that table. The model's own arithmetic was exact throughout. The table was fixed on 5 October, and no number in this report depends on it.

### 3. Forecast validation

This part scores the behavior layer. It forecasts validator stake and the number of active validators from 19 past dates and compares the model's errors with those of three simple forecasts.

#### 3.1 Design of the test

An **origin** is the date, at 23:59:59 UTC, from which a forecast starts. The model knows only the record up to it. The 19 **development origins** are the first day of each quarter from July 2022 to October 2025, plus the five network upgrades in that span: Banff (18 October 2022), Cortina (25 April 2023), Durango (6 March 2024), Etna (16 December 2024) and Fortuna (8 April 2025).

From each origin, the model runs 20 times with the chain's own reward rule and no behavioral response, and the forecast is the mean of the 20 runs at 30, 90 and 180 days, the three **horizons**. Forecasts that would reach past 19 November 2025 are not scored, so the latest origins have fewer horizons: 19 origins are scored at 30 days, 18 at 90 and 17 at 180.

Each forecast is compared with three simple forecasts, built only from data up to the origin:

1. **Holding today's value**, also called persistence: the value on the origin day, held constant.
2. **Extending the 180-day trend**: the origin value plus the mean daily change over the 180 days before.
3. **A weekly time-series fit**: an autoregressive model of order one on weekly changes, fitted on the data before the origin and iterated forward.

Forecasts are compared descriptively, by mean scaled error and by the number of origins at which each is closer. The origins, quarterly plus the five upgrades, are irregularly spaced, and forecasts from neighboring origins overlap. Formal tests across these origins would need to allow for overlapping windows, so none is relied on.

#### 3.2 The scaled error

A forecast's raw error is in AVAX or in validators, and its size depends on how much the series moves. To compare errors across origins and quantities, each is divided by a scale: the mean absolute one-day change of the series up to the origin. The **scaled error** of a forecast $\hat{y}$ of a value $y$ made at origin $T$ is

$$
\text{scaled error} = \frac{|\hat{y} - y|}{\frac{1}{T-1}\sum_{t=2}^{T} |y_t - y_{t-1}|} \tag{2}
$$

where $y_1, \dots, y_T$ is the series up to the origin. This is the mean absolute scaled error of Hyndman and Koehler (2006), applied to one forecast at a time and then averaged over origins. A scaled error of 10 means the forecast missed by ten average days' movement. It is a relative measure: it ranks forecasts of the same quantity, and its absolute level depends on how quiet the series has been. Lower is better.

#### 3.3 Results

v0.7's forecasts of validator stake are further off than holding today's value at every horizon, and the gap widens with the horizon. Its mean errors on the validator count are close to those of holding today's value at 30 and 90 days, and lower at 180 days, on these origins. Table 1 and Figure 3 give the scores.

| Quantity | Days after the origin | Model v0.7 | Holding today's value | Extending the 180-day trend | Weekly time-series fit | Origins scored |
| --- | --- | --- | --- | --- | --- | --- |
| Validator stake | 30 | 7.94 | 6.80 | 7.49 | 7.14 | 19 |
| Validator stake | 90 | 15.49 | 7.58 | 9.71 | 8.40 | 18 |
| Validator stake | 180 | 20.15 | 9.80 | 14.91 | 12.29 | 17 |
| Active validators | 30 | 6.29 | 6.41 | 8.34 | 5.95 | 19 |
| Active validators | 90 | 11.95 | 11.54 | 17.67 | 17.46 | 18 |
| Active validators | 180 | 21.90 | 24.57 | 41.28 | 35.40 | 17 |

*Table 1. Mean scaled error by quantity, horizon and forecast. Lower is better. Source: model v0.7 forecasts at the 19 development origins, 20 runs per origin.*

![Mean scaled error by horizon, v0.7 against three simple forecasts](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/forecast-scores.png)

*Figure 3. Mean scaled error of v0.7 and of three simple forecasts, at the 19 development origins, by days after the origin. Above: validator stake. Below: active validators. Lower is better. Source: model v0.7 forecasts, 20 runs per origin, scored against the P-Chain daily ledger. Data: [forecast-scores.csv](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/forecast-scores.csv), which also counts the origins at which v0.7 is closer than each simple forecast.*

The means hide how the comparison varies from one origin to the next. At 90 days, v0.7 has a larger error on stake than holding today's value at 15 of 18 origins. On the count, its mean errors are close to holding today's value and lower than the trend and the weekly fit at 90 and 180 days. Figure 4 shows the stake comparison origin by origin.

![Scaled error at 90 days at each origin, v0.7 against holding today's value](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/forecast-scores-by-origin.png)

*Figure 4. Scaled error of v0.7 (filled) and of holding today's value (open) on validator stake at 90 days, at each development origin in date order. A long grey bar is an origin where the two differ most. Source: model v0.7 forecasts, 20 runs per origin. Data: [forecast-scores-by-origin.csv](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/forecast-scores-by-origin.csv), which holds every origin, quantity and horizon, with forecast and actual values.*

#### 3.4 Why holding today's value is hard to beat

Holding today's value is the hardest simple forecast to beat because validator stake moves slowly. Most of it sits in long commitments held by a few large operators: commitments over 100,000 AVAX are 9.6% of commitments but 94.3% of the AVAX committed. On most days little of it ends. Holding today's value is therefore close to right over weeks, and its error grows only as fast as the stake drifts.

A model beats it only if it knows which way the stake will drift, and by how much. A model whose behavior is a constant renewal rate and a constant entry rate does not: it drifts towards the level those rates imply, which is not where the stake is going. Its runs are also smooth, while actual stake steps down and back up by tens of millions of AVAX within days, as large operators end and restart commitments. After Fortuna the validator count fell from 1,417 on 30 July 2025 to 936 on 21 August, about 480 nodes in three weeks, as whole fleets left. No run of v0.7 comes near it.

#### 3.5 Bias by era

The error is not noise around the right answer. It is a **bias**, an error with a consistent sign, and its sign changes in 2024.

![Signed error of v0.7 on validator stake at 90 days, by origin date](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/forecast-bias-by-era.png)

*Figure 5. Forecast minus actual, as a percentage of actual, for v0.7's 90-day forecast of validator stake at each origin. Diamonds are network upgrades. The dashed lines are the mean before 2024 and from 2024. Source: model v0.7 forecasts, 20 runs per origin. Data: [forecast-bias-by-era.csv](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/forecast-bias-by-era.csv).*

Before 2024 v0.7 under-forecast stake by 5.6% on average at 90 days, and from 2024 it over-forecast by 14.8%. The largest miss is the origin of 1 October 2024, which over-forecast by 48.46%, which the v0.7 research report rounds to 49%.

Differences between the model's fixed inputs and the renewal and entry that followed are possible contributors, since the model holds each origin's measured rates for the whole forecast. Over the 18 origins with a full 90-day window, renewal in the next 90 days differed from the input by up to 10 points, and entry ran from 44% below the input to 69% above. Before 2024, renewal in the next 90 days exceeded the input at six of eight origins, while v0.7 under-forecast stake. Over the ten complete windows from 2024, renewal was above the input at five and below at five, while v0.7 over-forecast stake. The sign of the stake error does not follow renewal alone.

Renewal shares also differ by how many commitments a node has completed, so changes in the mix of new and old nodes are another possible contributor. These associations do not establish the cause or the size of the forecast bias. One specification limit is clear, though its contribution is not measured. A node that returns after more than seven days counts in v0.7 as an exit and, later, a new entry with a typical entrant's stake, so when a large node pauses and returns, v0.7 loses its stake. The outcome is sensitive to renewal: in the model's sensitivity tests, a 10% error in the renewal probability moves the validators after 180 days by a quarter to two fifths.

#### 3.6 Are the forecast ranges honest?

A forecast's stated uncertainty can be tested too. The 10th to 90th percentile of the 20 runs is an 80% **conditional simulation interval**: the range the model expects under its fixed inputs. If it described the real uncertainty, it would contain the actual value about 80% of the time. At 90 days it contains the actual stake at 5 of the 18 eligible origins and the actual count at 3 of 18.

![Spread of 20 runs at 90 days against the actual value, at each origin](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/forecast-run-spread.png)

*Figure 6. At each development origin, the 20 runs' values at 90 days (dots) and their 10th to 90th percentile (bar), as a percentage of the runs' mean, with the actual value (black diamond). The last origin's actual falls in the held-back period and is not shown. Source: model v0.7, 20 runs per origin. Data: [forecast-run-spread.csv](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/forecast-run-spread.csv).*

The runs include random renewal, entry, stake and duration. They omit uncertainty in the estimated renewal probability and entry rate, which are fixed at their measured values, and the operator structure that moves stake by millions of AVAX at once. They also draw the daily number of entries from a Poisson distribution, whose variance equals its mean, while within each era from Banff to Fortuna the daily number of entries varied 3.7 to 13.5 times as much. The poor observed coverage means these intervals should not be treated as calibrated uncertainty about actual outcomes.

### 4. The contract's correlation test

The agreement sets one numeric target for the model's fit, and this part reports it. Deliverable [2.4](/Phase-II/Milestones/Milestone-2/2-4-Validation-Confirmation/) asks for a "Final goodness-of-fit achieving >90% correlation", and the proposal's protocol names it as the Pearson correlation between simulated and actual trajectories, above 0.90. Neither names the series or the window.

#### 4.1 What was computed

The reading computed here is the correlation within each forecast window. For one origin and horizon, let $x_t$ be the mean simulated daily validator stake on day $t$ of the window and $y_t$ the actual daily stake. The **Pearson correlation** over the $h$ days of the window is

$$
r = \frac{\sum_{t=1}^{h} (x_t - \bar{x})(y_t - \bar{y})}{\sqrt{\sum_{t=1}^{h} (x_t - \bar{x})^2}\,\sqrt{\sum_{t=1}^{h} (y_t - \bar{y})^2}} \tag{3}
$$

where $\bar{x}$ and $\bar{y}$ are the means over the window. Across the 19, 18 and 17 eligible origins at 30, 90 and 180 days, the mean within-window Pearson correlation between v0.7's mean simulated daily validator stake and the actual daily stake is 0.21, 0.00 and 0.09.

#### 4.2 Why the correlation alone cannot be the standard

The correlation in Equation 3 measures co-movement within each window and ignores errors in level. A forecast that rises and falls with the actual path scores well even if it sits millions of AVAX away from it. Holding today's value is constant within a window, so every $x_t$ equals $\bar{x}$, the denominator of Equation 3 is zero, and its Pearson correlation is undefined, even though its scaled errors are the hardest to beat. A test that cannot score the strongest simple forecast cannot show whether a model beats it.

Other readings of the contract, such as correlating levels across origins, give different numbers, which is why the measure has to be agreed.

#### 4.3 The proposed standard

This report proposes the held-back test of Part 5 as the standard, scored once against the simple forecasts with the scaled error of Equation 2, with the correlation reported beside it. Table 2 sets out the question for the Foundation.

| Question | Why it matters | Default if we hear nothing | Answer needed by |
| --- | --- | --- | --- |
| **The standard for deliverable 2.4, in writing.** Does the Foundation accept that 2.4 is met by the held-back period scored once on 27 October, against simple forecasts with the scaled error of Equation 2, with the correlation reported beside it? | The mean within-window correlations of v0.7's stake forecasts are low, and holding today's value has no defined within-window correlation, so the population, series, window and aggregation behind the contract's test must be agreed. The contract's test stays unless both sides agree a change in writing, and the held-back period can be scored only once | No default. A written answer is needed | 20 October 2026 |

*Table 2. The question on the validation standard put to the Foundation.*

### 5. The held-back test

Every score in Part 3 comes from data visible while the model was built, and a model built with data in view can fit it by accident. The final test therefore uses data no fit has touched.

The **held-back period** runs from the Granite upgrade, at 16:00 UTC on 19 November 2025, to the Helicon upgrade on 22 September 2026. Data from this period is held back from every model fit and every score. The model refuses any origin on or after that moment, and no forecast in Part 3 is scored on a day inside the period. The figures on this page show it only as description.

The period is scored once, on 27 October 2026, by a script fixed in advance. Fixing the script before the scoring means the measures and the comparison cannot be changed after the result is seen. Because the period can be scored only once, the Foundation's answer on the standard (Table 2) is needed before that date. The result will be added to this page when it lands.

The Helicon forecast comparison has separate 30-day and 90-day windows. Only the simple forecasts of its five quantities were committed by 29 September for the 30-day window. The model forecast missed that deadline, so the 22 October score reports the simple forecasts only. A model forecast is planned for the 90-day window, scored on 21 December.

### 6. What v0.7 can be trusted for

The verification, the scores and the bias together say what v0.7 can and cannot be used for. Its protocol layer can be trusted fully. Its behavior layer cannot yet be trusted to forecast stake.

| Use | Trust | Why |
| --- | --- | --- |
| Issuance of a design on given stakes | High | The protocol layer is exact (Part 2) |
| Ranking designs by issuance | High | The ranking holds at every response swept |
| Validator count over 30 to 90 days | Moderate | Mean errors close to holding today's value on these origins. Interval coverage poor |
| Validator stake over 90 days or more | Low | Worse than holding today's value, with a bias that changes sign |
| Effect of a design on validators | Conditional | It depends entirely on the assumed response |

*Table 3. What v0.7 can be used for. Source: the v0.7 research report of 8 October 2026, which the Foundation holds. Its Part 7 holds the design comparison behind the ranking row: the order of the designs on issuance is the same at every response swept.*

The last row is conditional because the chain's history before Helicon does not identify the response (Section 1.2). Every statement about a design's effect on validators holds only for the response assumed.

### 7. What comes next

The scores above set the bar every later version must clear. This part shows the first candidate that clears part of it, with its caveats.

The candidate reported here is the v0.8 candidate at commit `1c891a4`, scored with the random draws it had at that commit: one stream for each run and day. Since 7 October the library gives each decision its own stream, so that a decision that differs between two designs moves no other draw. A rerun with today's library therefore gives slightly different values. It keeps v0.7's unit, the commitment, and its exact protocol layer, and replaces the two observed rates with fitted behavior. Renewal depends on a node's tenure, whether it returned after a gap, its committed duration and its stake. A node's first commitment renews about three times in five, and its seventh or later about 86% of the time, for commitments ending 2021 to 2024. Entry splits nodes that have never validated from nodes returning after more than a week away, each with its own rate. A renewing or returning node draws its next duration from nodes with a similar habit.

| Validator stake, mean scaled error | 30 days | 90 days | 180 days |
| --- | --- | --- | --- |
| v0.8 candidate | 6.30 | 8.39 | 7.73 |
| v0.7 | 7.94 | 15.49 | 20.15 |
| Holding today's value | 6.80 | 7.58 | 9.80 |
| Extending the 180-day trend | 7.49 | 9.71 | 14.91 |
| Weekly time-series fit | 7.14 | 8.40 | 12.29 |

*Table 4. Validator stake mean scaled error, using 19, 18 and 17 eligible development origins at 30, 90 and 180 days, respectively. The v0.8 row uses 20 runs with base seed 0. The 200-run forecast uses ten 20-run batches with base seeds 0 to 9; its mean scaled errors are 5.87, 8.47 and 7.91. Every batch is below all three simple forecasts at 30 and 180 days and above holding today's value at 90 days. At 90 days, 2 of the 10 batches are below the weekly fit's 8.40 and 8 are above it, with batch means from 8.11 to 8.92.*

On mean scaled error, the v0.8 candidate halves v0.7's error at 90 days and is lower than every simple forecast at 30 and 180 days. At 90 days it is numerically near the weekly fit in the displayed 20-run batch. Its 200-run error is slightly higher than the weekly fit, and both remain behind holding today's value. These are descriptive comparisons, without a claim of statistical equivalence. It remains a candidate and does not improve the validator count.

Separately, checks of its conditional predictions of renewal within seven days miss their calibration tolerance. The mean absolute monthly calibration error and the absolute gaps for first and seventh commitments exceed the checks' three-percentage-point tolerance. Independent verification of training-data timing, including the label-maturity cutoff convention, remains open, as does uncertainty that accounts for repeated nodes and overlapping windows. These conditional-prediction checks do not establish whether the full lifecycle trajectories are valid.

Each later version adds one structure the record shows v0.7 lacks, and each must pass a test written before its results are seen. Version 1.0, shown at the call of 20 November, is the version whose test is the held-back period and the Helicon forecasts scored. Deliverable [2.4](/Phase-II/Milestones/Milestone-2/2-4-Validation-Confirmation/) repeats the validation on that final model, under the standard agreed in Part 4.

## How it was built

Every number on this page comes from the v0.7 research report of 8 October 2026, which the Foundation holds, and the runs behind it. The model is the class `ValidatorLifecycle` in the library `avalanche_research`, released as tag `model-v0.7.0` at commit `087484b`. It runs on cadCAD 0.5.3, with every setting declared in Param 2.4 with its bounds. The inputs are pinned in `data/pins/p6-v0.7-report.json`, which names each data run with its sha256, among them the staking periods and the daily ledger of 30 September 2026.

| What | How it is rebuilt |
| --- | --- |
| Reward formula against the chain (Figure 1), ledger replay (Figure 2) | `uv run --group notebook python scripts/figures/model_v07_record.py kernel figures/` and `uv run --group notebook python scripts/figures/model_v07_record.py replay figures/`. The script checks its pinned inputs and writes each chart, CSV and receipt |
| Run spread and reward-design experiments | `scripts/model_v07_report_runs.py`, which exports the tag, checks the pin and reruns the model inside the export. It takes about two minutes |
| Forecast scores at the 19 development origins | `scripts/model_development_scores.py`, run on the model at the tag |
| Figures | `scripts/figures/model_v07_report.py` and `scripts/figures/model_v07_experiments.py`, at commit `1616146` or later |

*Table 5. What to run to rebuild each result.*

To rebuild the experiment results and their charts:

```bash
uv run --group notebook python scripts/model_v07_report_runs.py results/
uv run --group notebook python scripts/figures/model_v07_experiments.py results/ figures/
```

When rebuilt, each chart script writes a receipt beside its chart, naming each input with its sha256. This page ships each chart with the CSV of its drawn data, not the receipt. Day $t$ of run $r$ draws from NumPy's `default_rng([seed, r, t])` with base seed 0, so a rerun at the tag gives the same draws. The library now scores 200 runs per origin instead of 20, which gives slightly different values, for example 7.86 against 7.94 for stake at 30 days.

The Foundation's repository holds this model on its `phase-ii` branch at commit `4597b8a`, with the same model code as the tag and its tests. The pin file and the scoring scripts reach that branch with the next delivery.

## Open questions

These questions are for the Foundation. The first decides how the final model is judged.

1. **The validation standard.** The question in Table 2 needs a written answer by 20 October 2026, before the held-back period is scored. Without it, the contract's test stands as written, with its series and window still undefined.
2. **The horizon that matters.** v0.7's mean errors on the count are close to holding today's value, and worse on stake at every horizon. Which horizon do decisions on reward designs need: 30, 90 or 180 days, or longer?
3. **Approval of this report.** Milestone 1 is complete when the Foundation approves this report. Is approval given by a written note after the call of 23 October? A written answer is needed by 6 November.

## References

- Grimm, V. and others (2014). Towards better modelling and decision support: documenting model development, testing, and analysis using TRACE. *Ecological Modelling* 280, 129–139. <https://doi.org/10.1016/j.ecolmodel.2014.01.018>
- Grimm, V. and others (2020). The ODD protocol for describing agent-based and other simulation models: a second update. *Journal of Artificial Societies and Social Simulation* 23(2), 7. <https://doi.org/10.18564/jasss.4259>
- Hyndman, R. J. and Koehler, A. B. (2006). Another look at measures of forecast accuracy. *International Journal of Forecasting* 22(4), 679–688. <https://doi.org/10.1016/j.ijforecast.2006.03.001>
- Rahmandad, H. and Sterman, J. D. (2012). Reporting guidelines for simulation-based research in social sciences. *System Dynamics Review* 28(4), 396–411. <https://doi.org/10.1002/sdr.1481>
- Tashman, L. J. (2000). Out-of-sample tests of forecasting accuracy: an analysis and review. *International Journal of Forecasting* 16(4), 437–450. <https://doi.org/10.1016/S0169-2070(00)00065-0>
