---
title: "Avalanche Phase II research context"
description: "Source-linked starting context for Phase II research, separating the signed scope, proposed methodology, and historical problem framing."
date: 2026-09-10
participants: [Shawn Anderson, Eric Lu, Hash, Jeff Emmett]
topics: [Avalanche staking economics, PSUU, behavioral calibration, reward design]
review_status: "Draft synthesis. January 7 primary transcript is unrecovered."
---

# Avalanche Phase II research context

Phase II investigates how Avalanche staking parameters and reward mechanisms perform under uncertainty. The active contractual work is a simplified staking model, behavioral calibration, PSUU simulation and sensitivity analysis, and decision support for alternative reward mechanisms. It is not a general reconstruction of the entire Avalanche economy.

## Current mandate

The signed agreement is the current scope authority. Its milestones require:

- historical data ingestion and a data manifest;
- a simplified staking model with behavioral state variables;
- fitted stake, unstake, and restake response functions with confidence intervals;
- PSUU sweeps, KPI computation, validation confirmation, sensitivity analysis, and a risk-surface map;
- evaluation support for alternative reward mechanisms; and
- a parameter recommendation report, scenario playbook, open-source delivery, and knowledge transfer.

See [signed grant agreement](/Phase%20II/Milestone%200/Signed%20Grant%20Agreement), Exhibit A. The agreement should govern delivery claims when it differs from an earlier proposal or meeting discussion.

## Research question and method

The April proposal frames the central question as identifying staking-governance configurations that sustain validator and delegator participation across market conditions and competing yields while maintaining the required security properties. Its proposed method is Parameter Selection Under Uncertainty (PSUU): vary controllable governance parameters and environmental scenarios, run stochastic simulations, calculate KPIs, convert agreed success conditions into utilities, and analyse the resulting parameter-outcome relationships.

The proposal is a methodological and design reference, not proof that its illustrative parameter ranges, response-function form, trajectory count, or KPI thresholds are already validated. In particular, it calls the displayed design space preliminary and assigns calibration and validation to the first milestone. See [Phase II proposal v2.5](/Phase%20II/Milestone%200/Proposal%20v2.5/).

## Historical problem framing

The recovered January evidence explains why the work narrowed to the staking subsystem.

The Jan. 7 meeting notes report a request to work with a reduced-form system centered on validator/delegator incentives, staking behavior, and price dynamics. They identify emissions and burn mechanisms as open design variables, call for sensitivity analysis, and list unresolved questions about behavioral calibration, the use of `tanh`, behavioral response functions, and the staking term in a price equation. These are derived notes rather than an original recording or transcript.

The Jan. 14 Hash/Shawn transcript repeats the same direction: reduce the model to validator/delegator mechanics, staking supply dynamics, and endogenous price formation; treat reward mechanisms as a design space; and use an evidence-based model to evaluate alternatives. It is a later internal recap, not direct evidence of what Eric said on Jan. 7.

The [historic meeting inventory](../meetings/index.md#mh-2026-01-07) records the Jan. 7 event as uncertain because the original recording and independently verified original notes remain unrecovered. The source limitation applies to attribution and exact wording, not to the existence of the subsequent research artifacts.

## Working model boundary

Phase II should keep these categories distinct:

| Category | Role in the work |
| --- | --- |
| Governance parameters | Candidate controllable reward, duration, allocation, or mechanism choices. |
| Environmental scenarios | Conditions outside protocol control, such as market state, competing yields, and network growth. |
| Behavioral dynamics | Empirically fitted responses to incentives and opportunity costs, with uncertainty retained. |
| State and flow variables | Observed or simulated quantities that must not be collapsed into governance controls. |
| KPIs and utilities | Explicit outcome measures and success rules used to compare simulations. |
| Recommendations | Derived decision support, conditional on model, data, scenario, and validation limits. |

The model must not present a convenience assumption as a measured behavioral fact. It must not represent a candidate mechanism as a Foundation decision. It must not treat a historically expressed perspective as a standing position without current evidence.

## Evidence status and current gaps

| Item | Status | Consequence |
| --- | --- | --- |
| Signed agreement | Preserved source document | Governs deliverables and contractual milestones. |
| April proposal | Preserved source document | Governs proposed methodology and explanatory context, subject to agreement and validation. |
| Jan. 7 meeting | Primary recording/transcript unrecovered | Do not quote or attribute exact speech from the derived notes. |
| Jan. 14 Hash call | Preserved transcript | Use as dated internal framing and a lead to earlier sources, not as direct Jan. 7 testimony. |
| Historic meeting corpus | Inventory and candidate records exist | Speaker attribution and semantic review remain incomplete for most records. |
| Ontology authority | Unconfirmed | Use working types with explicit review status; do not claim final ontology compliance. |

## Immediate context-compilation sequence

1. Read the signed agreement and proposal together, recording every delivery-relevant term that needs a stable glossary definition.
2. Establish a source map for Phase I artifacts, historical data, the differential specification, the current model, and current research outputs.
3. Define the research question, system boundary, controllable parameters, environmental scenarios, state variables, behavioral assumptions, KPIs, and validation criteria in source-linked records.
4. Process held meetings under the active five-file contract, beginning with the existing July 14 full-record example and preserving attribution limits.
5. Only then build cross-resource query projections. A ledger or temporal graph must be generated from validated canonical records, not used to fill missing evidence.

## Source map

| Source | Role | Limit |
| --- | --- | --- |
| [Signed grant agreement](/Phase%20II/Milestone%200/Signed%20Grant%20Agreement) | Current contractual scope | Not a technical validation report. |
| [Phase II proposal v2.5](/Phase%20II/Milestone%200/Proposal%20v2.5/) | Proposed methodology, initial design space, and explanatory framing | Illustrative values and mechanisms require validation. |
| [Historic meeting inventory](../meetings/index.md) | Meeting occurrence, source, and readiness register | Not a substitute for full transcript/audio review. |
| Jan. 7 Eric meeting notes | Historical problem framing | Derived notes; original transcript unrecovered. Reference recorded in the meeting inventory. |
| Jan. 14 Hash call transcript | Internal recap and project-preparation context | Does not independently establish Jan. 7 speech or attendance. |
| [Resource knowledge plan](../plans/2026-09-10-initialization/resource-knowledge/plan.md) | Active contract for corpus processing and Graphiti evaluation | Planning document, not research evidence. |

## Current conclusion

The research direction is coherent: turn a historically broad tokenomics model into a validated, data-grounded decision system for staking incentives and reward-mechanism choices under uncertainty. The immediate work is to establish the evidence and model boundary that make those recommendations defensible. The January materials explain the origin of that direction but do not replace the need for current data, calibration, validation, and source-aware meeting processing.
