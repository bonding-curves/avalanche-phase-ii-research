# Research field guide

Choose a route by the question being investigated. Follow a source's own model and date labels when it differs from the released implementation.

| Research task | Start with | Check before drawing a conclusion |
| --- | --- | --- |
| Understand the model | [Modeling memo](../../../../docs/review/2026-10-30/modeling.md) and [model implementation](../../../../src/avalanche_research/model/) | Population, state, five decisions, daily order and what is fitted or assumed |
| Review a reported comparison | [Results](../../../../docs/review/2026-10-30/results.md) and [evidence](../../../../docs/review/2026-10-30/evidence.md) | Source identity, experimental design, denominators and consequential limits |
| Locate inputs | [Data guide](../../../../data/README.md), catalog and pins | Recorded provenance and actual local availability. A pin identifies bytes but does not retrieve them |
| Specify an experiment | [Sweep design](../../../../scripts/m2_sweep_design.py), [reward implementations](../../../../src/avalanche_research/mechanisms/) and [KPI definitions](../../../../src/avalanche_research/model/kpis.py) | Question, hypothesis, controlled formula change, comparator, scenarios, draws, seeds and output definitions |
| Assess predictive evidence | [Model-selection evidence](../../../../results/model-v0.8.0-selection/README.md) | Development versus held-back evaluation, horizons, baselines and interval coverage |
| Find a figure or document | [Figure gallery](../../../../content/Phase%20II/Wiki/Figures/index.md), wiki tree and [review package](../../../../docs/review/2026-10-30/modeling.md) | The model and result identity, caption, drawn-data source and actual available assets |
| Recover historical context | [Research history](../../../../docs/research-history/README.md), [memo index](../../../../content/Phase%20II/Wiki/Memos/index.md) and [brief index](../../../../content/Phase%20II/Wiki/Briefs/index.md) | Original source and submission evidence, later corrections and archive coverage |

## Match the measure to the population

A staking period, a node and an operator are different units. Validator own stake and delegated AVAX are different populations. Gross new commitments differ from the change in active stake. AVAX-days measure an amount multiplied by its commitment duration. Use the population and units defined by the experiment before combining observations or comparing figures.

Consumption rate is a parameter of the reward formula. Annualized reward rate is the return on stake over a year. Promised issuance and rewards actually paid also differ. Keep those quantities named and defined beside their reported values.

## Separate the sources of an inference

An observed change can motivate a hypothesis. A simulation estimates a conditional outcome under its model and assumptions. A paired comparison controls shared simulation randomness, while model error can still affect both paths. Predictive tests and a policy counterfactual answer different questions. Goal thresholds and utility weights express preferences that must be stated alongside a score.

Carry those distinctions through the research sequence: question, hypothesis, model and assumptions, experiment, outcomes, interpretation and next question. Record useful null results and reasons for rejecting an approach. Use the existing run or memo records rather than starting a second registry.

## Record the implementation being read

Use the installed CLI to report the package, released model and checkout identity:

```sh
uv run --frozen avalanche --version
uv run --frozen avalanche model describe
```

The description lists protocol settings and upgrade inventory. It does not fit behaviour or validate a result. Read the producing code identity in each result's evidence record, since a document can describe an earlier implementation than the current checkout.

The [worked experiment](../../../../examples/first-experiment/README.md) includes its compact input snapshot and expected results. The [research-cycle guide](../../../../examples/research-cycle/README.md) connects a prediction to execution, assessment and a separate methodology reflection. Full historical report reruns still require the separate pinned snapshots, fitted draws and experiment artifacts identified by the evidence guide.
