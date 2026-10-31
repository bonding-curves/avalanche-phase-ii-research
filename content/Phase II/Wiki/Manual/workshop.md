---
title: "10. Teach the complete research system"
date: 2026-10-31
status: draft
kind: explanation
reader: "Avalanche Foundation, Ava Labs and researchers using the model"
question: "How can the team understand, operate and critically evaluate the model together?"
---

[Manual contents](/Phase-II/Wiki/Manual/)

The workshop should leave the team able to explain the model, trace a decision through it, run a checked comparison and design the next experiment. Covering those outcomes requires a proposed half-day session with preparation. The date, duration and participants still need agreement.

The teaching has two equally developed strands. One explains Avalanche, AVAX, validators, staking and their economic relationships. The other explains modeling choices, statistical methods, uncertainty, experimental practice and evaluation. Each model component connects a network process to its mathematical representation, implementation and evidence.

## Prepare the environment and the questions

Before the session, participants should have repository access, complete the [locked installation](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/SETUP.md), read the [brief](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/brief) and open the [small example](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/first-experiment/README.md). Download the central replay inputs in advance if that exercise will be used. Installation and access troubleshooting should be completed before teaching time.

The facilitator should verify the exact repository revision, CLI reference and example receipt. Have the model figures, goal heatmap, decision trees and replay output available locally. Review the [figure gallery](/Phase-II/Wiki/Figures/) to choose the views that answer the workshop's questions.

Participants should bring one policy question, one concern about a model assumption and one result they would want to verify. These questions help distinguish what the existing model answers from what needs a new experiment or capability.

## Proposed four-hour walkthrough

| Time from start | Topic and material | Participant task |
| --- | --- | --- |
| 0–40 min | [Foundations](/Phase-II/Wiki/Manual/foundations): blockchain agreement, Avalanche chains, AVAX flows, validator and delegator roles | Define stake, reward promise, payment, burn, supply and operator |
| 40–80 min | [Architecture](/Phase-II/Wiki/Manual/architecture) and [modeling](/Phase-II/Wiki/Manual/modeling): economic structure, modules, state, transitions and uncertainty | Follow a source record into a model input and identify a scientific assumption |
| 80–100 min | [Data and accounting](/Phase-II/Wiki/Manual/data): timestamps, stocks, flows, pins and cutoffs | Explain why commitments, active stake and AVAX-days differ |
| 100–110 min | Break | |
| 110–150 min | [Components](/Phase-II/Wiki/Manual/components): preparation, five choices, reward pricing and six daily stages | Trace an expiring validator through one day and explain its alternatives |
| 150–185 min | [CLI walkthrough](/Phase-II/Wiki/Manual/usage) and [experiments](/Phase-II/Wiki/Manual/experiments) | Inspect help, calculate a reward, run/check the small paired example and read its receipt |
| 185–195 min | Break | |
| 195–230 min | [Analysis and evaluation](/Phase-II/Wiki/Manual/analysis), reports and gallery | Interpret trajectories, goal utilities, thresholds, decision trees and uncertainty |
| 230–240 min | [Advanced methods](/Phase-II/Wiki/Manual/advanced) and next decisions | Propose an experiment with a hypothesis, evidence requirement and success test |

The allocation gives roughly 110 minutes each to domain understanding and modeling practice, plus breaks. The strands are combined within exercises. If the group needs more hands-on time, split the same sequence into two sessions rather than dropping the foundations or evaluation.

## Open each technical section with its reason for existing

For each process, first explain the real-world decision and why it matters to the research question. Define the input, unit and timing. Then show the equation or empirical law, its fitting evidence, its source implementation and its connection to the next component. Close with the assumption, alternative and evaluation that would change our confidence.

For renewal, this means explaining locked stake and the choice at expiry before introducing a logit. For return, explain why past nodes differ from first-ever entrants before showing a hazard. For KPIs, explain the policy objective and comparator before showing a combined utility score. This sequence makes the mathematics explanatory rather than decorative.

## Work through the decisions explicitly

The [component decision table](/Phase-II/Wiki/Manual/components#discuss-design-decisions-with-their-consequences) provides a starting agenda. Cover the daily time step, origin and fitting windows, event definitions, regularization, empirical choice laws, reward response, supply references, parameter uncertainty and excluded populations.

For each choice, distinguish a protocol requirement, an implementation convenience, an empirical result and an analyst judgment. Record the rationale when known. Record an open question when it is not. Historical code alone does not establish why a particular design was chosen.

## Use figures to answer specific questions

| Question | View to examine | Interpretation check |
| --- | --- | --- |
| What changed around Helicon? | Equal-window scatter and density views in the brief | New commitments are flows, rather than active population stocks |
| How does the model work? | Stock-and-flow diagram and daily stages | Distinguish economic flows, information and code execution |
| How do formulas differ? | Reward versus duration | Separate potential reward from payment and annualized return |
| What did a design change? | Paired trajectories and retained-stake comparison | Check baseline, conditions, horizon and uncertainty unit |
| Which goals does it meet? | Goal heatmap and combined score | Inspect individual safeguards as well as the weighted average |
| Under what conditions does it pass? | Decision trees and conditional pass views | A split describes this experiment's sampled conditions |
| What predicts better? | Forecast scores and interval diagnostics | Prediction quality is distinct from policy-response identification |

Open a figure's provenance and source data before treating it as evidence. Different model versions or experiment families can produce visually similar plots with different meanings.

## Evaluate what participants can do

**Domain check.** Explain why a lower promised reward can save issuance while changing renewal, and why more AVAX-days does not prove more active stake or a causal upgrade effect.

**Model check.** Trace one expiring node through renewal, duration, stake, rewards and assembly. Explain what a non-renewing node can do later, which decisions directly respond to yield and which do not.

**Operational check.** Locate the current docs, inspect an input identity, execute and check the small example, identify the source commit and distinguish its response settings from the reported central case.

**Research check.** State a new hypothesis, paired comparator, KPI, horizon, uncertainty design and evaluation criterion. Explain what can be rescored from saved outputs and what requires a fresh simulation.

These are observable learning outcomes. Attendance or a successful installation alone is insufficient evidence that the handoff worked.

## Close with a review record

Capture unresolved model assumptions, proposed experiments, data needs and agreed reporting changes. For each action, name its owner, required evidence and completion test. Separately record any decisions about goals, utility weights, pass thresholds or operating-cost assumptions. They should remain visible preferences rather than becoming undocumented model facts.

A later methodology reflection should ask whether the research questions still match the policy decision, whether omitted mechanisms matter and whether the next experiment could overturn the current interpretation. That reflection guides the outer research loop. It is distinct from checking whether one run finished successfully.
