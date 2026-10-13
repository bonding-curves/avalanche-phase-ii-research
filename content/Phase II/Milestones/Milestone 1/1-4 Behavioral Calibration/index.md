---
title: "1.4 Behavioral Calibration"
description: "Fitted response functions for staking, unstaking, and restaking, with confidence intervals."
status: delivered
source: signed-grant-agreement
tags: ["structural-estimation", "staking-duration-and-liquidity"]
---

## Contract requirement

> Fitted response functions for stake/unstake/restake with confidence intervals

Milestone 1 success criterion:

> Preliminary Validation Report delivered and approved by Avalanche team

Quoted from the [Signed Grant Agreement](/Phase-II/Milestones/Milestone-0/Signed-Grant-Agreement).

## Status

Delivered for the Foundation's review on 8 October 2026. This page gives the v0.8 candidate model's fitted functions for restaking, unstaking and staking, with 95% intervals, and a test of the restaking function on held-out decisions. The response of behavior to the reward rate is not fitted, because history before the Helicon upgrade cannot measure it. [The response to reward](#the-response-to-reward) explains why and what will.

## Result

The calibration estimates four parts of validator behavior from the chain's own decisions in the year or two before a forecast date, three by maximum likelihood and one by resampling observed moves. The results below are fitted at **origin** 18 November 2025, the last day before the **held-back period**. An origin is the date a forecast starts from, and every fit uses only events before it. The held-back period runs from the Granite upgrade's activation on 19 November 2025 at 16:00 UTC to Helicon. It is kept out of every fit and is scored once, on 27 October 2026.

The main findings are these.

1. **Restaking depends most on a node's record.** A node's first commitment renews about half the time, 0.50 (95% interval 0.48 to 0.53) for a typical small node. Its second renews 0.81 of the time (0.79 to 0.84).
2. **A return after a gap lowers renewal.** A commitment that began after the node had been away for more than seven days renews less, with log-odds 1.32 lower (1.15 to 1.51 lower).
3. **Nodes that leave come back most often in their first month out.** In that month, 1.2% of minimum-stake nodes return each day, and 2.4% to 2.5% of larger ones. After 90 days the rate falls below 0.01% a day for minimum-stake nodes.
4. **New nodes arrive in bursts.** First-ever validators arrive at 3.89 a day (3.10 to 4.86), with a variance about nine times the mean.
5. **The restaking function predicts better than the one it replaces.** On commitments ending in the 90 days after each of 19 forecast dates, it scores a log loss of 0.4505 against 0.4916 for the single renewal probability of model v0.7, lower at all 19. It still misses two calibration checks.

### From the contract's words to the model

The contract names three behaviors. The model has no single "stake" or "unstake" event. It follows each **validator commitment**, one staking transaction that locks a node's AVAX from a start time to an end time chosen in advance, and asks what happens when a commitment ends and before a node's first commitment. The table maps each of the contract's words to the decision the model fits.

| Contract word | Decision in the model | Fitted form | Fitted on |
| --- | --- | --- | --- |
| Restake | An ending commitment is renewed: the same node starts another within seven days | Logistic regression on 12 terms | 14,977 endings by 2,968 nodes |
| Unstake | An ending commitment is not renewed. The node joins the out-of-set pool and may return later | The complement of restaking, then a daily return hazard in nine cells | 5,981 endings without renewal |
| Stake | A node with no earlier commitment starts its first | Negative binomial count per day | 1,420 first-ever commitments |
| Stake amount and duration | The stake and length of each new commitment | Drawn from moves observed before the origin | 12,788 moves and the 1,420 first-ever commitments |

*Table 1. The contract's three behaviors and the model decisions that carry them, with the events each is fitted on at origin 18 November 2025.*

A **renewal** is a new commitment by the same node starting within seven days of the previous one ending. This is the model's restake. A commitment that is not renewed is an exit, the model's unstake. The node then enters the **out-of-set pool**, the set of nodes that recently left the active set, for up to 365 days, and can **return** from it by starting a new commitment after more than seven days away. A **first-ever arrival** is a node that has never validated before. Together, arrivals and returns are the model's stake. The [staking model specification](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/) gives the full model these parts sit in.

The proposal's response function was an illustrative tanh of the spread between the staking rate and an outside yield ([Proposal](/Phase-II/Milestones/Milestone-0/Proposal/)). Separately, the proposal listed Phase I's fixed restake rate of 67% and proposed to turn it into a state variable that depends on the compounding incentive. The proposal states that the form would be calibrated against the data, and names logistic and piecewise linear forms as examples. The calibration uses a logistic form for restaking, a piecewise constant hazard for returns, and a negative binomial count for arrivals. The reasons are given with each part below. The restake share in the year before the last origin was 78.6%, not a fixed 67%, and it varies by node in the ways Figure 1 shows.

### Restaking and unstaking: the renewal function

The renewal function gives the probability that an ending commitment renews. It is a **logistic regression**, or logit, in which the **log-odds** of renewing, $\ln\frac{p}{1-p}$, is a sum of terms. For commitment $i$ ending on day $t$,

$$
\operatorname{logit} \Pr(i \text{ renews}) = \beta_0 + \sum_{k=1}^{11} \beta_k\, x_{ik} + \beta_R\, g^R_t \tag{1}
$$

where each $x_{ik}$ is 1 if commitment $i$ falls in group $k$ and 0 otherwise. The eleven groups are four for **tenure**, the commitment's number on its node, one for whether the commitment began after a return, three for its duration and three for its stake. The **baseline node**, with every $x_{ik}$ equal to 0, is a first commitment of 20 days or less with a stake of up to 2,100 AVAX. The intercept $\beta_0$ is the baseline's log-odds of renewing. The last term, $\beta_R\, g^R_t$, is the response to reward, discussed [below](#the-response-to-reward). It is 0 in the fit.

The logit keeps every probability between 0 and 1 whatever the terms add to, and with the intercept alone it returns the observed share. These two properties are why the logit form was chosen. It is fitted by **penalized maximum likelihood**. With $y_i$ equal to 1 for a renewal and $\eta_i$ the right side of Equation 1, the fitted terms maximize

$$
\sum_{i} \Big( y_i\, \eta_i - \ln\big(1 + e^{\eta_i}\big) \Big) - \frac{1}{2} \sum_{k=1}^{11} \beta_k^2 \tag{2}
$$

The second sum is a penalty equal to a normal prior with variance 1 on every term but the intercept. It holds a term near zero when its group is nearly empty in a short window, instead of letting it run to infinity. The fit uses every commitment that ended in the 365 days up to seven days before the origin, so each has a full week to show whether it renewed. At origin 18 November 2025 those are 14,977 endings by 2,968 nodes, of which 11,767, or 78.6%, renewed.

![The renewal function's eleven terms with 95% intervals](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/renewal-terms.png)

*Figure 1. The fitted terms of the renewal function at origin 18 November 2025, as changes in the log-odds of renewing within seven days against the baseline node. Dots are estimates. The pale bar is the node-bootstrap 95% interval and the dark line the Laplace 95% interval, both defined in [How the intervals were computed](#how-the-intervals-were-computed). Terms right of the dashed line raise renewal. Data: [renewal-terms.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/renewal-terms.csv), rebuilt from [results/renewal-terms.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/results/renewal-terms.csv), which [calibrate.py](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/calibrate.py) wrote. An [interactive version](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/renewal-terms.html) is available.*

Tenure carries the largest effects. Moving from a first to a second commitment raises the log-odds by 1.46, which multiplies the odds of renewing by 4.3. The rise is not smooth: third to sixth commitments sit below the second, and the tenth or later sit highest. A commitment that began after a return renews less than one that followed a renewal, by 1.32 in log-odds, about a quarter of the odds. Commitments of 21 to 40 days renew slightly more than shorter ones, and those over 100 days much less. Stakes of 100,000 to 1 million AVAX renew more than the minimum, and stakes over 1 million less, with a node-bootstrap interval that includes zero.

| Term | Estimate (log-odds) | Laplace 95% interval | Node bootstrap 95% interval |
| --- | --- | --- | --- |
| Intercept: the baseline node | 0.015 | −0.090 to 0.119 | −0.083 to 0.121 |
| Second commitment | 1.457 | 1.268 to 1.646 | 1.277 to 1.652 |
| Third to sixth commitment | 1.192 | 1.058 to 1.325 | 1.055 to 1.313 |
| Seventh to ninth commitment | 1.602 | 1.433 to 1.770 | 1.422 to 1.771 |
| Tenth or later commitment | 1.890 | 1.765 to 2.015 | 1.751 to 2.021 |
| Begun after a return | −1.317 | −1.447 to −1.188 | −1.513 to −1.145 |
| Duration 21 to 40 days | 0.226 | 0.092 to 0.360 | 0.098 to 0.377 |
| Duration 41 to 100 days | −0.333 | −0.463 to −0.203 | −0.439 to −0.194 |
| Duration over 100 days | −0.889 | −1.077 to −0.701 | −1.092 to −0.714 |
| Stake 2,100 to 100,000 AVAX | 0.127 | 0.003 to 0.250 | −0.018 to 0.282 |
| Stake 100,000 to 1 million AVAX | 0.567 | 0.371 to 0.762 | 0.325 to 0.811 |
| Stake over 1 million AVAX | −0.317 | −0.592 to −0.042 | −0.728 to 0.041 |

*Table 2. The renewal function's 12 fitted terms at origin 18 November 2025. Source: [renewal-terms.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/renewal-terms.csv).*

Log-odds are hard to read directly, so Table 3 turns the fitted terms into renewal probabilities for six typical nodes. Each interval is the 2.5th to 97.5th percentile of the probability across the node-bootstrap refits.

| Typical node | Renewal probability | 95% interval |
| --- | --- | --- |
| First commitment, 14 to 20 days, 2,000 AVAX | 0.50 | 0.48 to 0.53 |
| Second commitment, 14 to 20 days, 2,000 AVAX | 0.81 | 0.79 to 0.84 |
| Seventh to ninth commitment, 14 to 20 days, 2,000 AVAX | 0.83 | 0.81 to 0.85 |
| Seventh to ninth commitment, over 100 days, 100,000 to 1 million AVAX | 0.78 | 0.73 to 0.83 |
| Fourth commitment begun after a return, 14 to 20 days, 2,000 AVAX | 0.47 | 0.42 to 0.52 |
| Seventh to ninth commitment, 14 to 20 days, over 1 million AVAX | 0.79 | 0.70 to 0.84 |

*Table 3. Renewal probability of typical nodes at origin 18 November 2025, with node-bootstrap 95% intervals. Unstaking is the complement: a first commitment of this kind ends without renewal half the time. Source: [results/renewal-profiles.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/results/renewal-profiles.csv).*

The fitted function describes the year before one origin. Figure 2 shows the same rise with a node's record in the raw record from July 2022 to the held-back period.

![Renewal within seven days by commitment number on the node](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/renewal-by-tenure.png)

*Figure 2. Share of ending validator commitments whose node started another within seven days, by the commitment's number on its node, for 40,506 endings from July 2022 to the held-back period. The band is the range of model v0.7's single renewal probability across its 19 forecast dates, and the dashed line its mean. Source: the v0.7 research report, sent to the Foundation on 8 October 2026, Figure 21. Data: [renewal-by-tenure.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/renewal-by-tenure.csv). An [interactive version](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/renewal-by-tenure.html) is available.*

Over that span, 62% of first commitments renewed and 91% of the 25th or later. Model v0.7 used one probability per forecast date, between 75% and 83%, for every node, and the fitted function replaces it.

### Returning after a gap

A node that does not renew is not gone for good. The return function gives the daily probability, or **hazard**, that a node in the out-of-set pool starts a new commitment. It is constant within each of nine cells, three stake bands by three spans of time since the node's last commitment ended. For a node $b$ in cell $c$,

$$
\Pr(b \text{ returns on day } t) = h_c, \qquad \hat h_c = \frac{\text{returns in cell } c}{\text{node-days at risk in cell } c} \tag{3}
$$

The estimate $\hat h_c$ is the maximum-likelihood hazard. A node is at risk from the eighth day after its last commitment ended, since the first seven belong to renewal. It stays at risk until it returns or observation stops, for at most 365 days, and a node out longer leaves the model. A piecewise constant hazard was chosen because the record shows most returns in the first weeks and few after three months, which one constant rate cannot fit. The function is fitted on the 5,981 commitments that ended without renewal in the 730 days before the origin.

![Daily probability of returning by stake band and time out](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/return-hazard.png)

*Figure 3. The fitted daily probability that a node in the out-of-set pool returns, by its last stake and the days since its last commitment ended, at origin 18 November 2025, on a log scale. Vertical bars are exact Poisson 95% intervals. Data: [return-hazard.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/return-hazard.csv), rebuilt from [results/return-hazard.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/results/return-hazard.csv), which [calibrate.py](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/calibrate.py) wrote. An [interactive version](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/return-hazard.html) is available.*

| Last stake | Days out | Returns | Node-days at risk | Daily hazard (%) | 95% interval (%) |
| --- | --- | --- | --- | --- | --- |
| Up to 2,100 AVAX | 8 to 30 | 989 | 85,309 | 1.159 | 1.088 to 1.234 |
| Up to 2,100 AVAX | 31 to 90 | 286 | 184,349 | 0.155 | 0.138 to 0.174 |
| Up to 2,100 AVAX | 91 to 365 | 31 | 519,962 | 0.006 | 0.004 to 0.008 |
| 2,100 to 100,000 AVAX | 8 to 30 | 404 | 17,048 | 2.370 | 2.144 to 2.613 |
| 2,100 to 100,000 AVAX | 31 to 90 | 100 | 31,449 | 0.318 | 0.259 to 0.387 |
| 2,100 to 100,000 AVAX | 91 to 365 | 38 | 102,091 | 0.037 | 0.026 to 0.051 |
| Over 100,000 AVAX | 8 to 30 | 205 | 8,200 | 2.500 | 2.169 to 2.867 |
| Over 100,000 AVAX | 31 to 90 | 80 | 12,629 | 0.633 | 0.502 to 0.788 |
| Over 100,000 AVAX | 91 to 365 | 30 | 26,924 | 0.111 | 0.075 to 0.159 |

*Table 4. The fitted return hazard at origin 18 November 2025, with exact Poisson 95% intervals. Source: [return-hazard.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/return-hazard.csv).*

Larger nodes return more readily and stay returnable longer. A minimum-stake node out for more than 90 days returns at 0.006% a day, while a node of more than 100,000 AVAX returns at 0.111%, about nineteen times as often. This matters for forecasts because model v0.7 counted any node returning after more than seven days as a new entrant, with a stake drawn from the year's entrants and its tenure reset to zero.

### Staking: first-ever arrivals

The arrival function gives the number of nodes that start their first commitment on a day. It is a **negative binomial** count, whose variance can exceed its mean. With $N_t$ the first-ever arrivals on day $t$, $\mu$ the mean per day and $k$ the **dispersion**,

$$
N_t \sim \operatorname{NegBin}\!\big(\mu\, e^{\beta_E\, g^E_t},\ k\big), \qquad \operatorname{Var}(N_t) = \mu + \frac{\mu^2}{k} \tag{4}
$$

where $\beta_E\, g^E_t$ is the response to reward, 0 in the fit. The mean is the average daily count, which is its maximum-likelihood value, and the dispersion maximizes the likelihood given that mean. A smaller dispersion means burstier arrivals. Model v0.7 used a Poisson count, whose variance equals its mean, but within each era from Banff to Fortuna the daily number of entries varied 3.7 to 13.5 times as much as a Poisson count allows. The negative binomial form was chosen to carry that spread into the forecasts.

| Parameter | Estimate | 95% interval |
| --- | --- | --- |
| Mean first-ever arrivals per day, $\mu$ | 3.89 | 3.10 to 4.86 |
| Dispersion, $k$ | 0.49 | 0.42 to 0.58 |

*Table 5. The fitted arrival function at origin 18 November 2025, on the 1,420 first-ever commitments in the 365 days before it, with moving-block bootstrap 95% intervals. Source: [results/arrivals.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/results/arrivals.csv).*

At these values, Equation 4 gives a daily variance of about 34.6, nine times the mean of 3.89. Arrivals come in clusters rather than one at a time.

### The stake and duration of each new commitment

A new commitment needs a stake and a duration, and these are drawn, not fitted as functions. A node that renews or returns draws its next duration from the moves observed before the origin by nodes whose previous duration fell in the same of four bins: up to 20, 21 to 40, 41 to 100 and over 100 days. This keeps a node's habit. Its next stake is its previous stake times a ratio drawn from moves in the same of three stake bands, kept within the protocol's validator bounds of 2,000 and 3,000,000 AVAX. A first-ever node draws its stake and duration from the year's first-ever commitments. At origin 18 November 2025 the move table holds 12,788 moves from the 365 days before it. These draws have no parameters and so no intervals. Their uncertainty is the sampling of the moves themselves.

### How the intervals were computed

Every interval on this page is a 95% interval, and each part uses a method suited to how its data were generated. The values were computed by [calibrate.py](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/calibrate.py), which calls the model's own fitting code and checks that its fitted values equal those the model uses. They were reproduced exactly when the script was rerun for this page. The intervals have not yet been reviewed independently, and they should be read as computed by the methods below, nothing more.

- **Laplace interval.** The estimate plus or minus 1.96 standard errors, with the standard errors taken from the inverse of the curvature of Equation 2 at its maximum. This assumes every ending is an independent decision.
- **Node bootstrap.** The renewal function refitted 300 times, each time on nodes drawn with replacement, keeping all of a node's endings together. The interval is the 2.5th to 97.5th percentile of the refits. This allows for one node's decisions being alike.
- **Moving-block bootstrap.** The arrival function refitted 1,000 times on the year's daily counts resampled in blocks of 14 consecutive days, which keeps bursts that span several days together.
- **Exact Poisson interval.** For each return cell, the Garwood interval for a count of returns over the node-days at risk.

For most renewal terms the node-bootstrap interval is about as wide as the Laplace one, with a median ratio of widths of 1.04. For the after-return term and the stake bands it is 1.2 to 1.4 times wider. Those terms rest on fewer nodes that each make many decisions, so treating their decisions as independent overstates the information in them. The node bootstrap is the safer of the two.

### What the intervals leave out

An interval measures how far a fitted value could move if the same year were drawn again. It does not include three other sources of uncertainty.

**Change from one window to the next.** Behavior changes from year to year. Refitting the same function at the Fortuna origin, 8 April 2025, on endings from 1 April 2024 to 1 April 2025, gives different values. The two windows share the endings from 11 November 2024 to 1 April 2025.

| Term | Fitted at 8 April 2025 | Fitted at 18 November 2025 | Node bootstrap 95% interval at 18 November 2025 |
| --- | --- | --- | --- |
| Intercept: the baseline node | 0.474 | 0.015 | −0.083 to 0.121 |
| Second commitment | 0.821 | 1.457 | 1.277 to 1.652 |
| Tenth or later commitment | 1.470 | 1.890 | 1.751 to 2.021 |
| Begun after a return | −1.295 | −1.317 | −1.513 to −1.145 |
| Stake over 1 million AVAX | −0.778 | −0.317 | −0.728 to 0.041 |
| Mean first-ever arrivals per day | 4.063 | 3.890 | 3.10 to 4.86 |
| Dispersion of arrivals | 0.645 | 0.493 | 0.42 to 0.58 |

*Table 6. Selected fitted values at two origins, from the same code and data. Of the 12 renewal terms, 9 of the April values lie outside the November node-bootstrap intervals.*

The after-return effect is stable, and the tenure effects stay large and positive. The baseline and the second-commitment effect move far more than their intervals. The model refits every part at each origin, so its forecasts use the latest year, but a forecast's uncertainty must also allow for behavior changing after the origin. The intervals here do not.

**Repeated lapses.** The return intervals treat every node-day as independent. A node that lapses twice in two years counts twice, so those intervals are somewhat too narrow.

**The response to reward.** The terms $\beta_R$ and $\beta_E$ in Equations 1 and 4 are not fitted, so they have no interval. The next section explains why.

### Held-out fit of the renewal function

The renewal function was tested on decisions outside its fit. At each of 19 **development origins**, the first day of each quarter from July 2022 to October 2025 plus the five network upgrades in that span, the function was fitted on the year before and scored on the commitments ending in the 90 days after. Each ending was labelled with its seven days of follow-up, and none whose label would reach the held-back period was scored. The score is the **log loss**, the average of $-\ln$ of the probability the function gave to what happened. Lower is better.

| Check, on held-out endings | Renewal function | Model v0.7's single probability | Tolerance set before scoring | Result |
| --- | --- | --- | --- | --- |
| Pooled log loss | 0.4505 | 0.4916 | Below v0.7 by a paired bootstrap at p < 0.05, and lower at 14 or more of the 19 origins | Met: p 0.0000, lower at 19 of 19 origins |
| Expected calibration error, 10 bins | 0.0194 | | At most 0.02 | Met |
| Monthly renewal, mean absolute error over 41 months | 0.0449 | 0.0489 | At most 0.03 | Missed |
| Predicted minus observed, first commitments | +0.054 | +0.201 | Within 0.03 | Missed |
| Predicted minus observed, second commitments | +0.015 | +0.101 | Within 0.03 | Met |
| Predicted minus observed, seventh commitments | −0.050 | −0.079 | Within 0.03 | Missed |

*Table 7. The renewal function on held-out endings at the 19 development origins, against model v0.7's single renewal probability. The tolerances were written before the scores were seen. Source: scripts/renewal_block_scores.py at commit 1c891a4.*

The function also beats a simpler block that uses only the node's previous outcome, with a log loss of 0.4505 against 0.4621. The **expected calibration error** sorts held-out endings into ten equal groups by predicted probability and averages the gap between predicted and observed renewal across them. The function meets that check overall. It misses two finer ones. Its monthly renewal share is off by 4.5 points on average, against a tolerance of 3, though v0.7 was off by 4.9. And it over-predicts first commitments by 5.4 points and under-predicts seventh commitments by 5.0 points, where the record shows 60.2% and 88.3% renewing. The fitted tenure gradient is too flat. It is far closer than v0.7's single probability, which was 20.1 points high for first commitments, but it is not yet within tolerance.

Two limits apply. Independent checks of the training-data timing, and an uncertainty measure that allows for repeated nodes and overlapping windows, are still open. And these checks score single decisions, not whole forecasts. In the full model the fitted parts halve v0.7's mean error on validator stake at 90 days, but do not improve the forecast of the validator count. The [Preliminary Validation Report](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/) tests the full model against history.

### The response to reward

The response that matters for comparing reward designs is how renewal and arrival change when a design changes the reward rate. The model carries it as the **response**, $\beta_R$ for renewal and $\beta_E$ for arrivals in Equations 1 and 4. Each multiplies the **yield gap**, the design's annual reward rate minus the chain's own rate, in percentage points, for a 30-day stake started that day. $\beta_R$ shifts the log-odds of renewing and $\beta_E$ the log of the arrival mean, per percentage point. Returns do not respond in the v0.8 candidate.

**Why history cannot measure it.** Under the chain's own rule the yield gap is zero on every day of its history, so history gives no direct variation in it. The offered rate did change, but only in level. Before Helicon, the protocol's reward rate for a stake of $D$ days was approximately $\frac{C-S}{S}\, r(D)$, with $C$ the supply cap, $S$ the supply counter and $r(D)$ the consumption rate. The ratio of any two durations' rates therefore did not depend on the counter:

$$
\frac{\text{rate}(365)}{\text{rate}(14)} = \frac{r(365)}{r(14)} = \frac{0.12}{0.10 + 0.02 \cdot \frac{14}{365}} = 1.19 \tag{5}
$$

The rate for a 365-day commitment was 1.19 times the 14-day rate on every day before Helicon. The shape of the reward curve never changed. What changed was its level, which fell slowly as the counter rose, together with everything else that changed over five years: the price of AVAX, outside yields, the operators on the network, and the rise and closure of the GoGoPool liquid staking protocol. No regression on that history can separate "paid less" from "later in time". An earlier regression of renewal on the spread between the 14-day staking rate and the 3-month Treasury yield gave −0.035 per percentage point (95% interval −0.062 to −0.008), but its sign reversed when its window was split in half, so it is not evidence of a negative response.

**What history does not bound.** Renewal was near 80% in both 2021 and 2023, while the yearly mean 14-day rate fell about 1.9 points. If a fall in the chain's own rate moved renewal as a design's gap does, a response of 0.3 per point would have cut renewal to about 69%. That reading assumes the two responses are the same and that nothing else changed, but GoGoPool's arrival, the AVAX price and the mix of operators all changed, so it shows the scale of 0.3 and is not evidence against it.

**How the model handles it.** The response is swept, not fitted. Every comparison of designs is run at $\beta_R = \beta_E \in \{0,\ 0.1,\ 0.3\}$, with 0.3 treated as a stress case, and each result is reported at all three. At zero every design keeps the fitted behavior, so designs differ only in what they issue. Results that hold at every value are robust to the unknown, and results that do not are reported as conditional on it.

**What will measure it.** Helicon's activation of [ACP-285](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-285-Minimum-Consumption-Rate/) lowers the minimum consumption rate from 10% to 7.5% over 90 days, for stakes that start after activation. By Equation 5 with the new minimum, the ratio of the 365-day to the 14-day rate rises from 1.19 to 1.56. This is the first change in the reward curve's shape, and it differs by duration and by day of the ramp. It is the first data that can identify a response, under assumptions stated in advance. Using it needs a design written before the data are examined: the reward path that would have held without the change, a mapping to the model's response terms, and assumptions about what else changed in the same weeks. That analysis will be run only after the held-back period is scored on 27 October 2026. Two other sources would help. Interviews with validators on the reward at which they would stop renewing are planned. And the Foundation's structural estimates of how duration responds to the consumption rate, shown on the ACP-285 community call, would let the response be calibrated rather than swept, if they can be shared.

## How it was built

The fitted values come from the model's v0.8 candidate at commit `1c891a4` of the research repository, on the staking periods run `staking-periods-2026-09-30` described in [1.1 Data Ingestion](/Phase-II/Milestones/Milestone-1/1-1-Data-Ingestion/) and [1.2 Data Manifest](/Phase-II/Milestones/Milestone-1/1-2-Data-Manifest/).

1. **Fit and intervals.** [calibrate.py](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/calibrate.py) runs the model's own fitting function at origin 18 November 2025, asserts that its values equal the model's, and computes every interval with fixed random seeds. To rerun it, export commit `1c891a4`, make the staking periods run available to its data catalog, and run `uv run --group model python calibrate.py <output folder>` from the export. Its five output files are delivered unchanged in this page's `results` folder. A rerun on 8 October 2026 reproduced all five byte for byte. Table 6's April values come from the same fitting function at origin 8 April 2025.
2. **Held-out checks.** Table 7 comes from `scripts/renewal_block_scores.py` at commit `1c891a4`.
3. **Figures.** `scripts/figures/m1_calibration.py` draws Figures 1 and 3 from the files in `results`. For each figure it writes a PNG, an interactive HTML, a CSV of the drawn data under readable column names, and a JSON receipt. The receipt records the sha256 of calibrate.py, of the input in `results`, and of each file the figure wrote. Running the script with `--check` recomputes every recorded sha256, rebuilds each figure's CSV from its input, and exits with an error on any difference. Figure 2 is reproduced from the v0.7 research report, sent to the Foundation on 8 October 2026.

| File | What it holds |
| --- | --- |
| [calibrate.py](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/calibrate.py) | The fitting and interval script |
| [results/renewal-terms.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/results/renewal-terms.csv) | calibrate.py's output: the 12 renewal terms with Laplace and node-bootstrap intervals |
| [results/renewal-profiles.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/results/renewal-profiles.csv) | calibrate.py's output: Table 3's six typical nodes with node-bootstrap intervals |
| [results/arrivals.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/results/arrivals.csv) | calibrate.py's output: Table 5's arrival mean and dispersion with moving-block bootstrap intervals |
| [results/return-hazard.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/results/return-hazard.csv) | calibrate.py's output: the nine return cells with counts, exposure and exact Poisson intervals |
| [results/summary.json](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/results/summary.json) | calibrate.py's output: origin, run, commit, counts of endings, nodes and first-ever commitments, and bootstrap replicates |
| [renewal-terms.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/renewal-terms.csv) | Figure 1 and Table 2: the renewal terms under readable names, with odds multipliers |
| [return-hazard.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/return-hazard.csv) | Figure 3 and Table 4: the return cells under readable names, as percentages |
| [renewal-by-tenure.csv](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/renewal-by-tenure.csv) | Figure 2: renewal share by commitment number, 2022 to 2025 |
| [renewal-terms.json](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/renewal-terms.json), [return-hazard.json](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/return-hazard.json) | Receipts for Figures 1 and 3: the sha256 of calibrate.py, of the input in `results`, and of each file the figure wrote |

*Table 8. The files behind this page, all in this page's folder or its `results` folder.*
