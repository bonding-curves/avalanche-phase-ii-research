---
title: "2.3 KPI Computation"
description: "Every simulated trajectory reduced to its measures and scored against five goals, with no value missing."
status: delivered
source: signed-grant-agreement
tags: ["kpis-and-goals"]
---

## Contract requirement

> Automated computation of all KPIs per trajectory

Milestone 2 success criterion:

> Sensitivity Analysis Report delivered covering all key parameters

Quoted from the [Signed Grant Agreement](/Phase-II/Milestones/Milestone-0/Signed-Grant-Agreement).

## Status

Delivered on 28 October 2026. Every one of the 132,800 trajectories of deliverable [2.2](/Phase-II/Milestones/Milestone-2/2-2-Simulation-Execution/) is reduced to its measures and scored against five goals, with no value missing. The [Sensitivity Analysis Report](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/) defines each goal in its section on goals.

## Result

A trajectory is one run of the model over a simulated year. Each one is reduced in two steps. The first step aggregates the trajectory into measures. The measures are the AVAX issued over the year, validators' own stake at its end and its worst 30-day fall, the number of active validators, the Nakamoto coefficient, the median validator's margin over the outside yield, net inflation and the stake-weighted committed duration. The second step turns each measure into a utility, a score between zero and one, where zero is a level the network should not accept and one fully meets the goal.

Every measure is read against the twin run under the chain's own rule on the same simulated future, so it reports the design's effect on that future. The measures are grouped under five goals: security holds, validators stay and stay spread, holders pay less, security per AVAX issued, and longer staking. A design meets a goal at a setting when at least 90% of its runs there meet every threshold of that goal, across the whole range of validator response.

## Next step

Workshop 1 on 13 November 2026 asks the Foundation to rank how much it values moving each goal from its worst to its best tested value. Those rankings set the goals' weights, and the recommendations of Milestone 3 are scored against them.
