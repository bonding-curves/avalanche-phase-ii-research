---
title: "2.2 Simulation Execution"
description: "132,800 simulated trajectories across four reward designs, four outside yields and the full range of validator response."
status: delivered
source: signed-grant-agreement
tags: ["parameter-selection-under-uncertainty", "market-conditions"]
---

## Contract requirement

> 50,000+ trajectories across governance × environment space

Milestone 2 success criterion:

> Sensitivity Analysis Report delivered covering all key parameters

Quoted from the [Signed Grant Agreement](/Phase-II/Milestones/Milestone-0/Signed-Grant-Agreement).

## Status

Delivered on 28 October 2026. The first sweep is complete, and its results are in the [Sensitivity Analysis Report](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/). A second sweep adds market conditions from 2 November 2026.

## Result

The first sweep ran the staking model 132,800 times. Each run, called a trajectory, follows the network's validators one day at a time for a year from 18 November 2025, the last day before the period held back from every model fit. The runs cover four reward designs, four outside yields and the full range of how strongly validators respond to a change in reward.

ACP-285's lower floor starts its 90-day ramp on the first day of the run, with a target minimum rate from 5% to 10%. The rule before ACP-285 keeps the minimum at 10% all year. A tenure boost pays validators up to 20% more as they complete more periods. A quadratic duration curve pays less for shorter commitments, with an exponent from 1 to 3.

The outside yield stands for the return an investor could earn elsewhere, at 3%, 5%, 7% and 10% a year. The response of renewals and of arrivals to the reward rate runs from none to strong, because the record has not yet measured it. Each design run has a twin under the chain's own rule on the same simulated future, so the difference between the two is the design's effect alone.

## Next step

A second sweep of 67,087 trajectories, run on 27 and 28 October 2026, crossed the four designs with bear, neutral and bull markets and swept four parameters of the protocol's own reward rule: the minimum rate, the gap to the maximum rate, and the shortest and longest staking periods. It repeats 512 runs of the first sweep, and all 28,672 of their values match exactly. Its results are in section 7.6 of the report.
