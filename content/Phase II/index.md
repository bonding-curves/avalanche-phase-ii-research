---
title: Phase II
description: "The Phase II agreement's milestones and deliverables, the proposal v2.5 schedule, and the status of every deliverable."
date: 2026-09-28
---

Phase II builds a calibrated model of Avalanche staking and uses it to test reward parameters and mechanisms before the Foundation changes them. The agreement names sixteen deliverables across three milestones, plus the governing documents of Milestone 0. This page lists each one with its status. Each deliverable has its own page with the contract's wording, its status, its result, and how the result was built.

## Schedule

The research works to the schedule of [proposal v2.5](Milestone%200/Proposal%20v2.5/). The [signed agreement](Milestone%200/Signed%20Grant%20Agreement) sets the deliverables and each milestone's success criterion.

| Milestone | Working period | Focus | Success criterion in the agreement |
| --- | --- | --- | --- |
| [Milestone 1](Milestone%201/) | June 15 to August 14, 2026 | Data ingestion, model definition, and behavioural calibration | Preliminary Validation Report delivered and approved by the Avalanche team |
| [Milestone 2](Milestone%202/) | August 15 to October 14, 2026 | Parameter sweeps, Monte Carlo simulation, and sensitivity analysis | Sensitivity Analysis Report covering all key parameters |
| [Milestone 3](Milestone%203/) | October 15 to December 14, 2026 | Recommendations, playbook, open-source release, and knowledge transfer | Final Parameter Report delivered and code repository transferred |

In September the research was rebuilt from the chain up: every dataset recaptured with receipts, and the protocol's reward formula reimplemented and checked against the chain. Milestone 1 is therefore being delivered again inside Milestone 2's window.

## Deliverables

Status is one of not started, in progress, delivered, or accepted by Avalanche.

| ID | Deliverable | Status on 2026-09-28 |
| --- | --- | --- |
| [1.1](Milestone%201/1-1%20Data%20Ingestion/) | Data Ingestion | Delivered for review |
| [1.2](Milestone%201/1-2%20Data%20Manifest/) | Data Manifest | Delivered for review |
| [1.3](Milestone%201/1-3%20Staking%20Model%20Spec/) | Staking Model Spec | In progress |
| [1.4](Milestone%201/1-4%20Behavioral%20Calibration/) | Behavioral Calibration | In progress |
| [M1](Milestone%201/Preliminary%20Validation%20Report/) | Preliminary Validation Report | Not started |
| [2.1](Milestone%202/2-1%20PSUU%20Infrastructure/) | PSUU Infrastructure | Not started |
| [2.2](Milestone%202/2-2%20Simulation%20Execution/) | Simulation Execution | Not started |
| [2.3](Milestone%202/2-3%20KPI%20Computation/) | KPI Computation | Not started |
| [2.4](Milestone%202/2-4%20Validation%20Confirmation/) | Validation Confirmation | Not started |
| [2.5](Milestone%202/2-5%20Sensitivity%20Analysis/) | Sensitivity Analysis | Not started |
| [2.6](Milestone%202/2-6%20Risk%20Surface%20Map/) | Risk Surface Map | Not started |
| [2.7](Milestone%202/2-7%20Workshop%201/) | Workshop 1 | Not started |
| [2.8](Milestone%202/2-8%20Collaborative%20Mechanism%20Design/) | Collaborative Mechanism Design | Not started |
| [3.1](Milestone%203/3-1%20Parameter%20Recommendation%20Report/) | Parameter Recommendation Report | Not started |
| [3.2](Milestone%203/3-2%20Scenario%20Playbook/) | Scenario Playbook | Not started |
| [3.3](Milestone%203/3-3%20Open%20Source%20Release/) | Open Source Release | Not started |
| [3.4](Milestone%203/3-4%20Workshop%202/) | Workshop 2 | Not started |

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

## Supporting material

- [Calls](Calls/2026-10-02/): the agenda for each call with the Foundation and what was done about the comments on the last one.
- [Essential Readings](Essential%20Readings/): the six Foundation articles and sources the research reproduces and builds on.
- [Interviews](Interviews/): what stakeholders told us, starting with BENQI.
- [Data](../Reference/Data), [Notebooks](../Reference/Notebooks), and [Glossary and Notation](../Reference/Glossary%20and%20Notation).
