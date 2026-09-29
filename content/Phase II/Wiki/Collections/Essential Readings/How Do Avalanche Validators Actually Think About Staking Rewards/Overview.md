---
title: Overview
description: "Eric Lu estimates a two-sided model of delegator and validator staking choices from 278 weeks of P-Chain data, finds that validators choose on annualized yield, and simulates the minimum duration and min_consumption_rate changes."
---

Read the [source](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/Source-Article).

![Validation duration distribution](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/raw/assets/figure-08.png)

*Stake-weighted distribution of validation duration in weeks under the six scenarios of the APY-thinking model. Lowering min_consumption_rate moves mass from the 5 to 13 week peak toward 20 to 52 weeks. The sawtooth comes from the discretized choice grid.*

## Question

Eric Lu published the article on April 28, 2026, ahead of the proposals to shorten the minimum staking duration and adjust the reward curve. It asks how delegators trade off rewards, fees, and duration, and how validators trade off staking income, delegation fee income, and duration.

## Method

The staking market is two-sided. Delegators choose among validator-duration products, and their preferences are recovered from weekly market shares with the inversion of [Berry 1994](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/1994-Discrete-Choice-Demand-Estimation). Validators choose duration and fee by the [conditional logit](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/1973-Conditional-Logit-Analysis) of McFadden, maximizing yield income plus fee income less the optionality cost of locked capital. Validators forecast delegation with the estimated delegator model. Validator stake size is fixed. The data cover 278 weeks of P-Chain history, roughly 375,000 delegator observations, and 1.5 million validator choice-set alternatives.

## Main results

1. Delegators, in the estimation results and Appendix A: coefficients of +0.44 on log APY and −0.64 on log weeks, so a 1% longer duration needs roughly a 1.5% higher net APY. They prefer larger validators, +0.29 on log stake, and avoid long lock-ups when volatility is high, −0.62 on the interaction. The model's R-squared is 0.202.
2. Validators, Tables B1 and B2: the annualized-yield specification has roughly 3x the pseudo R-squared of the period-yield specification. The coefficient on log APY income is 36.6 and on renewal cost 5.4. Fee income enters negatively.
3. Marginal rate of substitution, Table C: at the median point of 9 weeks, 2,000 AVAX, and a 10% fee, validators need 0.80 to 0.85 percentage points per year of added yield per extra week. It varies by less than 7% across price and volatility.
4. Policy scenarios, Appendix D:
   1. A minimum duration of 2/7 weeks alone barely moves average duration and cuts delegation 53%, because delegators cannot delegate to validators staking for less than two weeks.
   2. min_consumption_rate from 0.10 to 0.08 alone lengthens average duration 68%, from 10.0 to 16.9 weeks, and raises delegation 46%.
   3. Combined with the short minimum, average duration is 12.5 weeks at 0.09, 16.7 at 0.08, and 20.9 at 0.07. Delegation falls 40% in the primary scenario.

The article recommends a reduction to about 0.08 and calls the results "directional, not precise."

## What it gives this research

1. A reproduction target for deliverable [1.4](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/). An independent estimate on the same P-Chain data must match or explain the coefficients, the fit comparison, the MRS, and the six scenario durations.
2. A behavioral state for deliverable [1.3](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/). Duration choice driven by annualized yield is the validator response the model carries, beside the stake, unstake, and restake rates.
3. An out-of-sample test for deliverable [2.4](/Phase-II/Milestones/Milestone-2/2-4-Validation-Confirmation/). Helicon activated on 2026-09-22 with a 48-hour minimum and a floor ramping from 0.10 to 0.075 over 90 days. The activated floor lies between Scenario 4 at 0.08 and Scenario 6 at 0.07, which predict average durations of 16.7 and 20.9 weeks. Commitments started after the ramp can confirm or reject that range. Auto-renewal and a 90% uptime requirement arrived in the same upgrade, so the test is of the joint change.

## Limits and open questions

Both levers lie outside the estimation sample. The article attributes the jump from 12.5 to 20.9 weeks over a 0.02 change to the log-linear form, and the model is static, with no adjustment path.

Stake size is fixed, so the model estimates no response of stake amount to reward. The contract's stake and unstake functions need it from another source. The [Static Constants article](/Phase-II/Wiki/Collections/Essential-Readings/From-Static-Constants-to-Dynamic-Variables-Where-Avalanches-Economics-Are-Headed/Overview) reports it as low but publishes no estimate.

The 53% delegation decline rests on the two-week limit for delegation. Whether that limit holds after Helicon should be checked in the protocol code before the scenario is reproduced.

Two questions remain for the author: why fee income enters validator utility with a negative sign, and whether active validators confirm that they think in annualized terms, the check the article itself names.
