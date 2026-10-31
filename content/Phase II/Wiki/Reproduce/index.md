---
title: Reproduce a reward comparison
description: "Run the released model on included inputs and check one small paired experiment."
kind: tutorial
reader: "A researcher running the model for the first time"
question: "How can I run a complete staking-model experiment without provider credentials?"
---

The worked experiment runs model v0.8.0 using an included validator-data snapshot. It fits the released estimator, compares reward schedules under matched simulation draws and produces a table, interactive chart and checked result record. Follow the [complete tutorial](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/first-experiment/README.md) after the [locked installation](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/SETUP.md#3-install-the-python-environment).

```sh
uv run --frozen --group model --group notebook python scripts/first_experiment.py --output release/first-experiment
uv run --frozen --group model --group notebook python scripts/first_experiment.py --output release/first-experiment --check
```

Both commands should report `status: pass`. Open the generated `figure.html` in a browser. The check reads the saved result without running the simulation again. Each new experiment uses a new output directory.

![Mean cumulative validator reward promises under the historical schedule and a hypothetical earlier ACP-285-style ramp.](/Phase-II/Wiki/Reproduce/first-experiment.png)

*The newly declared example has four paired 30-day comparisons from an 18 November 2025 origin. The alternative starts its 90-day ramp on 19 November, with assumed renewal and entry responses of 0.5. The gray control has zero reward response. [Interactive chart](/Phase-II/Wiki/Reproduce/first-experiment.html), [paired table](/Phase-II/Wiki/Reproduce/first-experiment-comparison.csv) and [figure provenance](/Phase-II/Wiki/Reproduce/first-experiment-figure.json).*

The default comparison saves a mean 12,390.24 AVAX in new reward promises. These are full rewards committed when new periods begin, rather than payouts during the horizon. The mean paired final-stake ratio is 0.998336824. Four pairs and one response assumption establish a worked conditional comparison. They supply no confidence interval, policy optimum or predictive validation. The [tutorial](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/first-experiment/README.md) explains the counter's earlier observation time, incomplete ramp and input scope.

Use the [research cycle](/Phase-II/Wiki/Research/) to connect a stated prediction to the experiment, assessment and a separate reflection on methodology.
