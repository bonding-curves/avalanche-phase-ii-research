---
title: "2.6 Risk Surface Map"
description: "The regions of input space where staking incentives fail, confirmed on held-out runs for 197 of 384 failure conditions."
status: delivered
source: signed-grant-agreement
tags: ["parameter-selection-under-uncertainty", "kpis-and-goals", "market-conditions"]
---

## Contract requirement

> Parameter regions where staking incentives fail

Milestone 2 success criterion:

> Sensitivity Analysis Report delivered covering all key parameters

Quoted from the [Signed Grant Agreement](/Phase-II/Milestones/Milestone-0/Signed-Grant-Agreement).

## Status

Delivered on 28 October 2026. The findings of the [Sensitivity Analysis Report](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/) give the failure regions confirmed for 197 of 384 failure conditions. The region where every goal passes is added with the goal-level results.

## Result

A failure region is the box of input values where a goal's floor fails. The patient rule induction method, PRIM, finds the box where a failure concentrates on half of the runs and confirms it on the other half. Across the four designs, the four outside yields and the goal floors of deliverable [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/), there are 384 failure conditions, and the method confirmed a region for 197 of them.

In 189 of the 197, the region spans the whole sampled range of every input, so the failure holds under that design and outside yield whatever the setting. Only eight regions bound a setting, such as the floors from 5.00% to 7.67% at which ACP-285's ramp fails the margin before costs at a 5% outside yield.

For the validator margin, the market drives these failures more than the reward design does. Net inflation stays under the 5% line in every one of the 132,800 runs, with the highest at 2.66% a year on total supply. Validators' margin over their outside yield, averaged by stake, at a 1.5% yearly operating cost, fails under every design at outside yields of 7% and 10%. At 3%, every design except the ramp pays the margin in every run, and the ramp in 90% of them.

## Next step

The report also gives the region of settings where every goal holds in at least 90% of runs: under ACP-285's ramp, a minimum rate of 9% to 9.5% at most outside yields. The second sweep adds bear, neutral and bull markets to the inputs, and the region does not move with them.
