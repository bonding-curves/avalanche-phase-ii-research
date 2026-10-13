---
title: Milestone 1
description: "Data ingestion, the model's specification, its behavioral calibration, and the Preliminary Validation Report: all five deliverables of Milestone 1, accepted by the Foundation in August 2026 and rebuilt on the staking model v0.7."
---

Milestone 1 builds the foundation that the parameter sweeps of Milestone 2 run on. It has four deliverables and one success criterion. The deliverables are the staking data, a documented manifest of that data, a specification of the staking model, and the model's behavior calibrated to the record. The success criterion is a Preliminary Validation Report that tests the model against history, delivered and approved by the Avalanche team.

The Foundation accepted Milestone 1 in August 2026. After the research restarted in September 2026, all five deliverables were rebuilt from the chain up, and the rebuilt versions were published on 8 October 2026. They rest on the staking model v0.7, tagged `model-v0.7.0` on 1 October and presented on 2 October.

## How the deliverables depend on each other

Each deliverable is built on the one before it. The data feeds the model, the model is calibrated to the data, and the calibrated model is tested against history.

![Milestone 1's five deliverables in order](/Phase-II/Milestones/Milestone-1/milestone-1-chain.png)

*Figure 1. Milestone 1's deliverables in the order they depend on each other, what each holds, and the approval that completes the milestone.*

**Working period:** June 15 to August 14, 2026, rebuilt inside Milestone 2's period.

**Signed agreement period:** Months 1 to 2, April 15 to June 14, 2026. The project works to the schedule of proposal v2.5, and the agreement's dates are shown for reference.

**Contract success criterion:** Preliminary Validation Report delivered and approved by Avalanche team.

## The deliverables

Each page opens with the contract's exact wording, then gives its result, how it was built, and its open questions.

| ID | Deliverable | Contract requirement | What is delivered |
| --- | --- | --- | --- |
| [1.1](/Phase-II/Milestones/Milestone-1/1-1-Data-Ingestion/) | Data Ingestion | Ingest Avalanche-provided historical data (validator/delegator flows, rewards, durations) | Every validator and delegator staking transaction since September 2020, with its rewards and duration, from checked and pinned runs, with coverage by source and date |
| [1.2](/Phase-II/Milestones/Milestone-1/1-2-Data-Manifest/) | Data Manifest | Documentation of sources, transformations, quality metrics | Every dataset with its source, its transformation, its checks and quality metrics, and the command that rebuilds it |
| [1.3](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/) | Staking Model Spec | Simplified model focused on staking subsystem with behavioral state variables | The full specification of model v0.7: its state per commitment, the daily step, the laws of motion as equations, invariants, inputs and parameters, its lineage, and what v0.8 changes |
| [1.4](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/) | Behavioral Calibration | Fitted response functions for stake/unstake/restake with confidence intervals | Renewal (restake), exit and return (unstake), and entry (stake) fitted to the record with 95% intervals and held-out fit. The response to a change in reward, which the record before Helicon cannot identify, is swept |
| [Report](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/) | Preliminary Validation Report | Milestone 1 success criterion: Preliminary Validation Report delivered and approved by Avalanche team | The reward formula reproduced on 3,769,919 of 3,769,920 stakes, the ledger replayed on every complete day, forecasts scored at 19 origins against simple forecasts, and what the model can be trusted for |

## What the milestone found

Three findings run through the five deliverables.

1. **The protocol side is exact.** The model's reward formula and its daily ledger match the chain's own records, so the cost of any reward design on given stakes is computed exactly.
2. **The behavior side is too simple in v0.7.** v0.7 forecasts validator stake worse than holding today's value. The candidate v0.8 fits renewal, entry and returns to the record and halves v0.7's error at 90 days. It is under test. It becomes `model-v0.8.0` only by passing a test written before its results are seen, which is scheduled for mid-October.
3. **The response to reward is not in the record.** Before Helicon the reward curve never changed shape, so history cannot show how validators respond to a change in it. Every design is therefore reported across a range of responses until the Helicon ramp provides the first evidence.

## For the Foundation

1. **The standard for goodness of fit.** The contract asks for ">90% correlation" without naming the series or the window. The report proposes a standard and asks for a written answer by 20 October, before the held-back period is scored.
2. **The Snowflake share.** It has loaded nothing since 22 September 2026. The record since then comes from our own capture of the P-Chain, which matches the share on every row both hold.
