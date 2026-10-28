---
title: "2.1 PSUU Infrastructure"
description: "The pipeline that sweeps reward designs across outside conditions, from the design of a sweep to a receipt for every run."
status: delivered
source: signed-grant-agreement
tags: ["parameter-selection-under-uncertainty"]
---

## Contract requirement

> Full parameter sweep pipeline with cloud compute

Milestone 2 success criterion:

> Sensitivity Analysis Report delivered covering all key parameters

Quoted from the [Signed Grant Agreement](/Phase-II/Milestones/Milestone-0/Signed-Grant-Agreement).

## Status

Delivered on 28 October 2026. The pipeline ran Milestone 2's full sweep, which the [Sensitivity Analysis Report](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/) describes in its section on the sweep.

## Result

Parameter Selection Under Uncertainty, PSUU, runs the staking model many times over every combination of the settings the Foundation controls and the conditions it does not, then scores each run against stated goals. The pipeline designs a sweep, runs it and keeps a checkable record of every run.

A sweep design names the reward designs to test, their parameter ranges, the outside conditions and the strengths of validator response. The pipeline arranges the runs with a Sobol sequence, which spreads parameter values evenly through each range, so that the spread of every result can later be divided among its inputs. It then runs the model once for every combination, a year of simulated days each, and pairs each design run with a twin under the chain's own reward rule on the same random draws.

Every run writes its results with a hash, and a receipt names the code, the input data and every output. Anyone with the repository and the pinned data can run any row again and check that it matches. The pipeline runs on any machine with the repository. Milestone 2's sweep of 132,800 runs ran on the team's dedicated compute server in 8.0 hours on four workers, with no failed run, and every one of its 1,344 control checks passed.

The runs feed deliverables [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/) to [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/), where each run is scored against goals and analysed for which inputs decide each outcome.
