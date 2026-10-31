# 7. Results need both analysis and evaluation

*Draft for review.*

A trajectory is a simulated outcome under a model and its settings. Analysis explains how outcomes vary. Evaluation asks whether the model or the outcomes satisfy a stated standard. Keeping those tasks separate prevents a visually persuasive chart from becoming a stronger claim than its evidence supports.

## Measures describe quantities before preferences rank them

`model/kpis.py` computes stake, count, issuance, duration, concentration, volatility and related measures at a declared horizon. Absolute values describe a path. Paired values describe its difference from a matched reference. The analysis layer authenticates pair identities before comparing them.

For positive reference denominators, issuance saved is one minus the design's cumulative issuance divided by reference issuance. Retained stake is terminal design stake divided by terminal reference stake. Promised validator issuance and delegated payments remain distinct populations. The [paired-analysis contract](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/README.md) specifies denominator and sampling requirements.

## A utility score and a pass share answer different questions

A utility maps a measured outcome onto an analyst's preference scale. It does not describe the validator's private decision utility. The working combined score averages goal utilities with declared weights. A pass share counts runs satisfying every required threshold.

Figure 1 retains both goals and the combined score. Its comparisons use BCRG's exploratory thresholds and weights, pending Foundation choices.

![Utilities by design setting for five goals and their combined score.](assets/content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/goal-utilities.png)
*Figure 1. Frozen means for 16,384 independent design runs at one year, with 4,096 per family. G1–G4 have equal combined weights and G5 half their weight. Response settings and four outside yields are pooled. Utility is a preference score, rather than an all-goal pass probability.*

The displayed pooled score peaks near a 6%–6.5% minimum consumption rate. The [conditional pass map](../../content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/results.md#26-risk-surface-map) uses different response windows and is more favorable at higher-rate bands. Both can be true because a weighted average and minimum conditions serve different decisions. Preserve each population and denominator when interpreting the difference.

## Sensitivity methods ask different statistical questions

A rank correlation summarizes direction of association. Partial rank correlation adjusts for included inputs and relies on its conditioning design. A random forest ranks inputs useful for prediction in the sample. A classification tree describes conditional groups. PRIM searches regions with specified outcome properties. These methods do not independently establish causal effects.

Sobol analysis estimates how input uncertainty contributes to output variance under a specified input distribution and sampling construction. Structured A, B and AB rows, noise inheritance and shared-baseline dependence matter. The package's [Sobol contract](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/README.md#structured-sobol-calculations) explains the supported estimator and resampling conditions.

An unconverged index remains unassessable. In the report's slice, 310 of 512 index sets converge and none of 32 stake-retention sets does. Reporting a precise variance allocation for stake from those failed sets would overstate the calculation. These counts refer to that analysis slice, not every Milestone 2 output.

## Verification checks what the code computes

Software tests exercise behaviour and failure conditions. Protocol reconstruction compares potential rewards with chain records. Ledger replay follows recorded events without fitting behaviour. Numerical reproduction reruns the intended comparison and checks stored results.

The [central replay](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/report-reproduction/README.md) matches 100 original paths across 36,600 daily rows. Its original execution-time driver identity remains unresolved. The new replay records its own source and environment, establishing numerical equivalence while retaining that provenance gap.

## Validation checks predictions against observations

A forecast origin restricts fitting to earlier data. Benchmarks test whether a complex model adds predictive value over simpler alternatives. CRPS evaluates the full predictive distribution, while interval coverage checks how often its intervals include realized outcomes.

Figure 2 shows that v0.8.0 performs more strongly for stake than count in development evaluation. Good scores on one output do not establish good scores on another.

![Forecast distribution scores for own stake and validator count.](assets/content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/assets/forecast-scores.png)
*Figure 2. Scaled CRPS at 30, 90 and 180 days, with lower values better. Each origin uses a 200-run forecast distribution, then scores are averaged over eligible development origins. Blue identifies v0.8.0. The [committed selection evidence](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/results/model-v0.8.0-selection/README.md) records the comparisons.*

The separate Granite-to-Helicon held-back verdict remains outstanding. The recorded greater-than-90% contractual correlation criterion is also distinct from distributional forecast scoring. Neither numerical reproduction nor development forecast performance validates the causal reward-response assumption.

## Economic evaluation belongs to the decision maker

The Foundation's objectives, safeguards and trade-offs determine which simulated differences matter. The workshop should distinguish descriptive measures, pass conditions and preference weights before ranking designs. Node-level concentration should not be presented as common-ownership concentration, and own stake per AVAX issued should not be presented as a complete measure of security.

For each result, record the claim, measured quantity, comparison, uncertainty, source and the observation that would change the interpretation. The [results memo](../../content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/results.md) demonstrates these distinctions for the current experiments.

[Manual contents](README.md)
