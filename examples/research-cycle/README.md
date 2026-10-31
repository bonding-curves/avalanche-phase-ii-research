# Run and review one research cycle

A research cycle connects a question and prediction to an experiment, its numerical assessment and the next question. This example runs the [worked reward comparison](../first-experiment/README.md), evaluates its declared point-sign prediction and preserves execution separately from scientific interpretation. A second, authored record assesses the method and research direction.

## Inspect the prediction before running

Read [hypotheses.jsonl](hypotheses.jsonl) and [experiment.json](experiment.json). The prediction is that mean paired reward saving is positive in the declared development example, with at least two pairs. A negative mean contradicts it. Zero or insufficient pairs is inconclusive. Failed execution supplies no scientific insight.

The packaged expected results are available. This exercise demonstrates reproduction and research recordkeeping, with no blinded confirmation or new causal estimate.

## Execute one bounded cycle

After the [locked installation](../../SETUP.md#3-install-the-python-environment), run from the repository root:

```sh
uv run --frozen --group model --group notebook python scripts/research_cycle.py run --output release/research-cycle
uv run --frozen --group model --group notebook python scripts/research_cycle.py read --output release/research-cycle
```

The default cycle reports `completed` and the declared prediction as `supported`. Read `analysis.json` for the numeric test, `insight.json` for its scope and continuation question, and `receipt.json` for hashes and attempt status. Outputs from the model remain inside the attempt directory.

Running the identical command again authenticates completed output and leaves the attempt count unchanged. After an interrupted or failed attempt, use `--resume` to retain it and make another attempt. A changed hypothesis, design, input, source, Python version or lockfile requires a new output directory. Use the locked installation for third-party dependencies. A failed or interrupted run is marked scientifically invalid and has no insight.

## Reflect on methodology separately

Read the [authored example reflection](reflection.json). It asks how response assumptions and a larger paired-run budget could change interpretation. Its proposals are recorded as proposed, with no automatic application.

For your own cycle, author a new JSON record using that format. Bind `analysis_sha256` to your actual `analysis.json`, identify the author, assess methods and direction, and give each proposal an owner, expected benefit, success check and disposition. Then attach it:

```sh
uv run --frozen --group model --group notebook python scripts/research_cycle.py reflect --output release/research-cycle --record YOUR-REFLECTION.json
```

The runner verifies that the reflection names this experiment and analysis. An existing reflection is preserved. The [recorded example](example-output/receipt.json) shows one completed attempt and the separate attached reflection.

This command runs one bounded cycle and starts no recurring schedule. Further cycles begin with a new declared question or design. [Research orientation](../../.agents/skills/avalanche-research-orientation/SKILL.md) helps locate relevant evidence before changing either.
