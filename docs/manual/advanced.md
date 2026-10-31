# 9. Extensions need a question and a test

*Draft for review.*

A useful extension resolves a consequential research question. It needs an economic mechanism, a software interface and evidence that the addition improves the model for that use. More detail alone can increase uncertainty without improving the decision.

The table distinguishes delivered methods, development code and proposed research. Source availability is not equivalent to release adoption or scientific validation.

| Capability | Current status | How to use or evaluate it |
| --- | --- | --- |
| Alternative rate schedules, duration curves and tenure multipliers | Released reward interfaces | Reuse the lifecycle, compare matched paths and test neutral settings |
| Keyed common randomness and fitted-parameter draws | Delivered | Reduce unrelated variation and retain draw/seed identities |
| Grid, Sobol-space and explicit-row designs | Implemented runner capabilities | Choose a sampling design matching the analysis question |
| Paired reduction, rank analysis, CART, PRIM and Sobol methods | Implemented analysis modules | Supply authenticated outputs and their sampling/uncertainty contracts |
| Node-level fits and development variant comparisons | Delivered methods and retained candidate code | Judge improvements on declared decision and whole-model tests |
| Delegated lifecycle and named-operator events | Development components outside the released v0.8.0 path | Define required inputs, accounting and candidate evaluation before adoption |
| Reward-responsive duration | Research extension | Specify a choice model and identify the duration incentive response |
| Available-supply and participation feedback | Research extension | Define feasible allocation and test high-participation scenarios |
| Revenue-funded rewards | Development/research extension | Specify revenue, allocation, reserves and a shortfall policy |
| Endogenous AVAX price or holder types | Research extension | Add a market/behaviour mechanism with identifiable data and validation |
| Adaptive design or surrogate optimization | Proposed advanced technique | Declare search objectives and retain separate evaluation data |
| Continuous autonomous research | Bounded cycle delivered; scheduling and scientific governance separate | Preserve declared questions, failed attempts and authored methodology reflection |

## Improve a component without losing the comparison

Start with the current component's failure or the economic effect it omits. Preserve its input/output meaning while introducing the candidate. Test known cases and failure conditions, then compare held-out decisions and complete-model predictions under a declared rule.

A more flexible renewal model may fit past choices better while forecasting aggregate count worse. A new duration response may change the interpretation of G5 even when total stake is unchanged. Such differences belong in the model-version record alongside accepted and rejected candidates.

## Extend the existing interfaces explicitly

A **reward formula** extends `RewardMechanism` with bounded Param settings and the appropriate configuration, numerator or multiplier hooks. Preserve integer potential-reward semantics and expose the class through `mechanisms` if JSON designs must resolve it. Test neutral settings, timestamps, duration boundaries and supply accounting before comparing behaviour. The [reward implementation](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/mechanisms/reward.py) shows the supported contracts.

A **behavioural component** must satisfy its concrete ClassSelector, preparation tables, stage outputs and parameter-draw mapping. A generic `sample` method alone is insufficient. Decide what is fitted, assumed or resampled, and how its source provenance is retained. Test event-level predictions and whole-model consequences. [Variant preparation](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/variants.py) shows how alternatives are selected.

A **dataset** needs a catalog contract, a capture/build/check path or derived producer, CLI dispatch and an authenticated pin. Declare fields, units, timestamps, missingness and coverage. A Parquet file alone does not supply those contracts. [Dataset readers](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/__init__.py) and the [catalog](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/data/data-catalog.json) define this boundary.

A **measure or goal** needs units, population, horizon, baseline and missing-column behaviour. Add the calculation and metadata, then declare any utility or threshold separately. Changing an accounting threshold can reuse primitive results. Changing an incentive or behavioural equation requires new paths. [KPI definitions](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/kpis.py) keep these choices inspectable.

## Compare model versions through the same questions

A reusable version record should name the question, changed assumptions and components, input identity, fitting procedure, uncertainty, experiment and acceptance criterion. Retain rejected candidates and the evidence for their disposition. This is a documentation template, rather than a claim that every historical version already has a complete record.

Compare versions on the same forecast origins, observations, benchmark set and scoring quantities where their contracts permit it. Regenerate the structure diagram, state trajectories, distribution checks and goal views with the version and source identity visible. Differences in inputs, horizon or response settings must remain explicit when a common comparison is impossible. A successful version should improve the intended scientific use, not merely produce a more detailed diagram.

## Use richer uncertainty deliberately

Current draws cover selected fitted components and daily randomness. A future study could vary structural choices, propagate stake-hurdle uncertainty or use an alternative response-identification design. Each requires a justified sampling or inference contract.

Variance reduction, sequential allocation of more runs to uncertain comparisons and multi-fidelity models are potential methods. They are not additional registered CLI commands. Their benefit should be measured against the present approach using the same quantity and computational budget, with evaluation criteria declared before selection.

## Separate exploration from confirmation

A tree, surrogate or adaptive search can identify promising parameter regions. Using those same observations to claim confirmatory evidence overstates what was tested. Preserve a subsequent evaluation step and the existing reserved-period protocol.

A proposed optimum also depends on the Foundation's goals and scenario assumptions. Changing weights, safeguards or the comparison schedule can move it. Retain goal-by-goal outcomes beside the combined score.

## Extend the research cycle before automating its direction

The shipped cycle records a hypothesis, bounded execution, numerical assessment and separate authored reflection. An operating loop additionally needs scheduling, resource limits, data availability, failure handling and an owner for methodological decisions. The [cycle example](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/research-cycle/README.md) starts no recurring scheduler.

The outer reflection should ask whether the question remains useful, whether new evidence changes the model boundary and which proposed change has the highest expected research value. A proposal should name its rationale, owner, success test and disposition. Recording that proposal does not automatically apply it to the model.

[Manual contents](README.md)
