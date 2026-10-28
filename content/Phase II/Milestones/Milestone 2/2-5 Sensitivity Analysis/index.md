---
title: "2.5 Sensitivity Analysis"
description: "Rank correlations, variance shares, decision trees and forests that show which inputs decide each measure and goal."
status: delivered
source: signed-grant-agreement
tags: ["sensitivity-analysis", "kpis-and-goals"]
---

## Contract requirement

> Decision trees and correlation matrices for all KPIs

Milestone 2 success criterion:

> Sensitivity Analysis Report delivered covering all key parameters

Quoted from the [Signed Grant Agreement](/Phase-II/Milestones/Milestone-0/Signed-Grant-Agreement).

## Status

Delivered on 28 October 2026. The findings of the [Sensitivity Analysis Report](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/) give rank correlations with resampled intervals, variance shares, classification trees and forests for every measure and goal. The goal-level results follow as the report's findings are completed.

## Result

The sensitivity analysis asks which inputs decide each outcome. Rank correlations between each input and each outcome, with intervals from resampling, give the direction and strength of each relationship. Variance shares, computed with Saltelli's method on the Sobol arrangement of deliverable [2.1](/Phase-II/Milestones/Milestone-2/2-1-PSUU-Infrastructure/), say how much of an outcome's spread each input explains. Classification trees and forests learn which inputs decide whether a goal is met, and rank them by importance.

The design's own setting decides issuance. Under ACP-285's ramp, the floor's rank correlation with issuance saved is −0.98 at every outside yield, and the floor explains about 96% of its variance where that estimate converged.

A design moves stake only through validators' response to the reward. With no response the ramp keeps all of the chain rule's stake. Around that, the spread in stake kept comes from the floor, the response and chance, which includes the uncertainty in the model's fitted parameters, in shares of about a third, a sixth and a half.

Each relationship carries a confidence rating. A relationship is rated High when its sign holds, with an interval that excludes zero, in every band of validator response. The ramp floor's relationships with issuance saved and with stake kept are rated High at every outside yield.

## Next step

The report adds forests and response curves for each of the five goals, the region of settings where every goal holds, and the second sweep's results across bear, neutral and bull markets, which leave the ranking of designs unchanged.
