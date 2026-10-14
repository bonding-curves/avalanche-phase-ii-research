---
title: Phase II
description: "The Phase II agreement's milestones and deliverables, the proposal v2.5 schedule, and the status of every deliverable."
date: 2026-09-28
---

Phase II builds a calibrated model of Avalanche staking and uses it to test reward parameters and mechanisms before the Foundation changes them. The agreement names sixteen deliverables across three milestones, plus the governing documents of Milestone 0. This page lists each one with its status. Each deliverable has its own page with the contract's wording, its status, its result, and how the result was built.

## Schedule

The research works to the schedule of [proposal v2.5](/Phase-II/Milestones/Milestone-0/Proposal/). The [signed agreement](/Phase-II/Milestones/Milestone-0/Signed-Grant-Agreement) sets the deliverables and each milestone's success criterion.

| Milestone | Working period | Focus | Success criterion in the agreement |
| --- | --- | --- | --- |
| [Milestone 1](/Phase-II/Milestones/Milestone-1/) | June 15 to August 14, 2026 | Data ingestion, model definition, and behavioural calibration | Preliminary Validation Report delivered and approved by the Avalanche team |
| [Milestone 2](/Phase-II/Milestones/Milestone-2/) | August 15 to October 14, 2026 | Parameter sweeps, Monte Carlo simulation, and sensitivity analysis | Sensitivity Analysis Report covering all key parameters |
| [Milestone 3](/Phase-II/Milestones/Milestone-3/) | October 15 to December 14, 2026 | Recommendations, playbook, open-source release, and knowledge transfer | Final Parameter Report delivered and code repository transferred |

The Foundation accepted Milestone 1 in August 2026. In September the research was rebuilt from the chain up: every dataset recaptured with receipts, and the protocol's reward formula reimplemented and checked against the chain. Milestone 1's deliverables were rebuilt on that basis and published again on 8 October.

## Deliverables

Status is one of not started, in progress, delivered, or accepted by Avalanche.

| ID | Deliverable | Status on 14 October 2026 |
| --- | --- | --- |
| [1.1](/Phase-II/Milestones/Milestone-1/1-1-Data-Ingestion/) | Data Ingestion | Accepted by Avalanche |
| [1.2](/Phase-II/Milestones/Milestone-1/1-2-Data-Manifest/) | Data Manifest | Accepted by Avalanche |
| [1.3](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/) | Staking Model Spec | Accepted by Avalanche |
| [1.4](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/) | Behavioral Calibration | Accepted by Avalanche |
| [M1](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/) | Preliminary Validation Report | Accepted by Avalanche |
| [2.1](/Phase-II/Milestones/Milestone-2/2-1-PSUU-Infrastructure/) | PSUU Infrastructure | In progress |
| [2.2](/Phase-II/Milestones/Milestone-2/2-2-Simulation-Execution/) | Simulation Execution | In progress |
| [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/) | KPI Computation | In progress |
| [2.4](/Phase-II/Milestones/Milestone-2/2-4-Validation-Confirmation/) | Validation Confirmation | In progress |
| [2.5](/Phase-II/Milestones/Milestone-2/2-5-Sensitivity-Analysis/) | Sensitivity Analysis | In progress |
| [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/) | Risk Surface Map | In progress |
| [2.7](/Phase-II/Milestones/Milestone-2/2-7-Workshop-1/) | Workshop 1 | Not started |
| [2.8](/Phase-II/Milestones/Milestone-2/2-8-Collaborative-Mechanism-Design/) | Collaborative Mechanism Design | Not started |
| [3.1](/Phase-II/Milestones/Milestone-3/3-1-Parameter-Recommendation-Report/) | Parameter Recommendation Report | Not started |
| [3.2](/Phase-II/Milestones/Milestone-3/3-2-Scenario-Playbook/) | Scenario Playbook | Not started |
| [3.3](/Phase-II/Milestones/Milestone-3/3-3-Open-Source-Release/) | Open Source Release | Not started |
| [3.4](/Phase-II/Milestones/Milestone-3/3-4-Workshop-2/) | Workshop 2 | Not started |

## How the deliverables connect

Each deliverable is built from the ones before it. The data of 1.1 and 1.2 feeds the model of 1.3. The model is calibrated to observed behaviour in 1.4 and checked against history in the Preliminary Validation Report. The calibrated model then runs the parameter sweeps of Milestone 2. Their results become the recommendations of Milestone 3.

```text
1.1 data ingestion, 1.2 data manifest
  -> 1.3 staking model, 1.4 behavioural calibration
  -> preliminary validation against history
  -> 2.1 to 2.3 parameter sweeps and KPIs across 50,000+ trajectories
  -> 2.4 validation, 2.5 sensitivity, 2.6 risk surface, 2.8 alternative mechanisms
  -> 3.1 recommendations, 3.2 scenario playbook, 3.3 open-source release
```

## Sections

- [Milestones](/Phase-II/Milestones/): every deliverable, one folder each.
- [Interviews](/Phase-II/Interviews/): what stakeholders told us, starting with BENQI.
- [Wiki](/Phase-II/Wiki/): the [briefs](/Phase-II/Wiki/Briefs/) for each call, one [memo](/Phase-II/Wiki/Memos/) per finding, the [reference](/Phase-II/Wiki/Reference/) pages, and the [collections](/Phase-II/Wiki/Collections/) of sources, starting with the ten Essential Readings.
