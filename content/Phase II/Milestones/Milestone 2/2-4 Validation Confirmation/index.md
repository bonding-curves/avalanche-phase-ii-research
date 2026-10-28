---
title: "2.4 Validation Confirmation"
description: "The forecast-skill standard that chose model v0.8.0, its scores against simple forecasts, and the frozen held-back test."
status: in progress
source: signed-grant-agreement
tags: ["model-validation"]
---

## Contract requirement

> Final goodness-of-fit achieving >90% correlation

Milestone 2 success criterion:

> Sensitivity Analysis Report delivered covering all key parameters

Quoted from the [Signed Grant Agreement](/Phase-II/Milestones/Milestone-0/Signed-Grant-Agreement).

## Status

In progress. The validation standard and the scores that chose model v0.8.0 are delivered in the [Sensitivity Analysis Report](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/). The held-back test is frozen, and its result is presented at Workshop 1 on 13 November 2026.

## Result

The model is judged by whether it forecasts what validators did better than simple rules do, on data it was never fitted to. The standard compares the model's forecasts with three simple ones: the current value held constant, the current value with the spread of its past changes, and a small time-series model. Each forecast is a full distribution of outcomes, scored with the continuous ranked probability score, CRPS, which rewards a forecast for being close to what happened and no wider than it needs to be. A lower score is better.

Model v0.8.0 was chosen by a rule fixed on 6 October 2026, before any score existed. A candidate change entered the model only if it left the model's forecasts no worse at 19 forecast dates from July 2022 to October 2025. The result forecasts validators' own stake better than every simple alternative at 30, 90 and 180 days. At 180 days its score is 27% lower than the best simple forecast's.

## Next step

The held-back test checks the model on data it has never been fitted or chosen on: the period from the Granite upgrade on 19 November 2025 to Helicon on 22 September 2026. The test forecasts validators' own stake 90 days ahead from eight dates in that period against the three simple forecasts. Its scoring rule was frozen on 27 October 2026, before any score was computed.
