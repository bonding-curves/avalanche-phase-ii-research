# Avalanche research handoff

Start with the [modeling memo](../review/2026-10-30/modeling.md) to understand the staking model and simulation setup. To run the model, use the worked experiment below. Its compact input snapshot is included, so it needs repository access and the Python environment, with no Snowflake or API credentials.

| Task | Entry point |
| --- | --- |
| Read | [Modeling memo](../review/2026-10-30/modeling.md), [evidence](../review/2026-10-30/evidence.md) and [draft results](../review/2026-10-30/results.md) |
| Browse | [Local wiki setup](../../SETUP.md#8-run-the-research-site), then the wiki's Figures and Research History pages. The [historical reading copies](../research-history/README.md) also work on GitHub |
| Reproduce | [Worked experiment](../../examples/first-experiment/README.md): model v0.8.0, four paired 30-day comparisons, included inputs, expected results and a chart |
| Research | [One research cycle](../../examples/research-cycle/README.md): declared hypothesis, execution, numerical assessment and separate methodology reflection |

After the [locked installation](../../SETUP.md#3-install-the-python-environment), run from the repository root:

```sh
uv run --frozen --group model --group notebook python scripts/first_experiment.py --output release/first-experiment
uv run --frozen --group model --group notebook python scripts/first_experiment.py --output release/first-experiment --check
```

The second command verifies the saved result without running the simulation again. Open `release/first-experiment/figure.html` in a browser. Each new experiment uses a new output directory.

The example is a newly declared comparison using observations available by 18 November 2025. Its assumed reward responses and small run count make it a worked example. Full historical report reruns still require their separate pinned inputs and experiment artifacts.

The archive accounts for eight entries from the recovered July export. It distinguishes four originals, three redacted editions and one metadata record. The gallery covers delivered figures and their document uses. The research-cycle command runs one bounded cycle, with explicit resumption and authored reflection. It starts no recurring schedule.
