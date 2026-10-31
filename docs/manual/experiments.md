# 6. An experiment makes the comparison explicit

*Draft for review.*

A reward comparison starts with a question about the network. The experiment specifies which change could answer it and which conditions must be held comparable. Its run count is a consequence of that design, rather than a substitute for one.

For the central report example, the question concerns starting ACP-285 earlier. It is distinct from comparing ACP-285 with a permanently unchanged formula. The historical reference itself adopts ACP-285 at Helicon.

## Declare the question before selecting a chart

A hypothesis should predict an observable result under stated conditions. Name the measure, comparator, horizon and the result that would count against the prediction. A question about longer individual commitments needs a duration-response mechanism. The current duration metric alone cannot establish that mechanism.

The [bounded cycle](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/research-cycle/README.md) contains a point-sign prediction for a development example. Because its expected output is supplied, it teaches execution and recordkeeping. It is not a new blinded confirmation.

## Separate settings the designer controls from conditions it faces

A reward formula is a design choice. Outside yield, response strength and uncertain fitted behaviour are conditions or assumptions. Crossing them in a sweep asks whether a conclusion holds across those conditions. Scenario ranges need an economic rationale, and their inclusion does not imply an estimated probability.

A complete specification identifies model version, source code, input pin, origin, horizon, formula, comparator, outside conditions, responses, parameter draws, seeds, output measures and analysis criteria. The [central specification](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/report-reproduction/config.json) is a worked example.

## A run, a design row and a pair are different units

A run is one path. A design row selects a configuration that may contain several runs. A pair matches a design path with its reference. A parameter draw represents fitted uncertainty and can be held common within a pair. Shared reference paths and repeated settings must remain visible when counting experiments.

The original central case uses 50 pairs over 365 days at renewal response 0.025, entry response 0.04 and 5% annual outside yield. The small first experiment uses four pairs over 30 days and responses of 0.5 to make its instructional contrast visible. They are separate experiments with separate interpretations.

## The runner expands a design and retains its evidence

`experiments/sweep.py` accepts Cartesian levels, Sobol parameter designs or explicit rows. Cartesian designs enumerate a grid. Sobol designs cover a bounded space with a low-discrepancy sequence. Explicit rows preserve a supplied arrangement, including structured sensitivity designs. A space-filling sequence alone is not sufficient to compute every Sobol variance estimator.

The runner resolves and checks inputs, prepares each origin/model, allocates workers and records outputs and status. Optional reducers retain measures at declared horizons instead of all daily trajectories. An experiment that needs a later trajectory figure must therefore retain or obtain its trajectory data explicitly.

The source contracts record row counts, file identities and failure dispositions. Failed or incomplete runs remain part of experiment accounting. Replacing a missing setting with a successful one without recording the change would alter the sample being analyzed.

## Controls test the implementation before interpretation

A neutral reward setting should reproduce the chain formula on the tested inputs. A zero-response comparison can test whether participation remains equal when the behavioural channel is disabled. Repeating fixed inputs and seeds tests numerical repeatability. Source and artifact checks test that the intended inputs were consumed.

These controls support their stated properties. They do not prove that every response coefficient is correct. A pilot also establishes whether the chosen run size fits the available time and memory. The generic CLI has no dry-run option for model execution, so inspect the design and input contract before launching it.

## Review the experiment at two levels

The inner cycle checks execution, measures the declared result and records its interpretation. The outer reflection asks whether the mechanism, data, assumptions, uncertainty and research question remain suitable. A useful null result can change that direction without changing the model automatically.

After the workshop, an experiment should be specified well enough that another researcher can name exactly what will vary, what will be paired and what evidence would change the conclusion.

[Manual contents](README.md)
