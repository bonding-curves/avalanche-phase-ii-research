---
title: Run a research cycle
description: "Connect a question, experiment and assessment, then review the method separately."
kind: guide
reader: "A researcher extending the staking analysis"
question: "How do I preserve what was predicted, run and learned?"
---

A research cycle starts with a question and prediction, runs a bounded experiment and records what its result supports. A separate reflection considers the method and research direction. The delivered example uses the [small reward comparison](/Phase-II/Wiki/Reproduce/). Its [complete guide](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/research-cycle/README.md) explains the records, resumption and authored reflection.

```sh
uv run --frozen --group model --group notebook python scripts/research_cycle.py run --output release/research-cycle
uv run --frozen --group model --group notebook python scripts/research_cycle.py read --output release/research-cycle
```

The declared example tests whether mean paired reward saving is positive. Its four paired results support that point-sign prediction under the recorded assumptions. Expected results are packaged, so the exercise demonstrates reproduction and recordkeeping. It establishes no statistical significance, policy optimum or predictive validity.

| Record | Purpose |
| --- | --- |
| Hypothesis and experiment | Preserve the question, prediction, input identities, test and execution bound |
| Receipt and attempt | Distinguish successful, failed and interrupted execution while retaining history |
| Analysis and insight | Bind the numeric assessment and its scope to actual model output |
| Methodology reflection | Assess assumptions, uncertainty and the next experiment, with explicit proposal dispositions |

The [authored reflection](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/research-cycle/reflection.json) proposes a response-sensitivity comparison and a paired precision criterion. Those proposals require their own declared experiments. Running the identical completed cycle reads it back without another simulation. Interrupted work can resume, while changed inputs or source require a new output directory. The command starts no recurring schedule.
