# Avalanche research handoff

Start with the [research brief](../review/2026-10-30/brief.md) for the findings and next review questions, or the [modeling memo](../review/2026-10-30/modeling.md) for model and simulation setup. For a first run, use the [small worked experiment](../../examples/first-experiment/README.md), whose input snapshot is included. To check the reported finding, use the central-case replay below. Both run without Snowflake or data-provider credentials.

| Task | Entry point |
| --- | --- |
| Read | [Brief](../review/2026-10-30/brief.md), [modeling memo](../review/2026-10-30/modeling.md), [evidence](../review/2026-10-30/evidence.md) and [draft results](../review/2026-10-30/results.md) |
| Browse | [Local wiki setup](../../SETUP.md#8-run-the-research-site), then the wiki's Figures and Research History pages. The [historical reading copies](../research-history/README.md) also work on GitHub |
| Reproduce | [Reported central case](../../examples/report-reproduction/README.md): 50 paired one-year comparisons, a checked 12.1 MB input download, percentile table and rebuilt trajectory figure |
| Research | [One research cycle](../../examples/research-cycle/README.md): declared hypothesis, execution, numerical assessment and separate methodology reflection |

After the [locked installation](../../SETUP.md#3-install-the-python-environment), run from the repository root:

```sh
uv run --frozen --group model --group notebook python scripts/first_experiment.py --output release/first-experiment
uv run --frozen --group model --group notebook python scripts/first_experiment.py --output release/first-experiment --check
```

The second command verifies the saved result without running the simulation again. Open `release/first-experiment/figure.html` in a browser. Each new experiment uses a new output directory.

The small example is a newly declared comparison, separate from the report. The central-case replay rebuilds the reported 12.7721% median reward saving and 98.6901% own-stake retention, checking all 100 paths against the original. Other historical report reruns still require their separate pinned inputs and experiment artifacts.

The archive accounts for eight entries from the recovered July export. It distinguishes four originals, three redacted editions and one metadata record. The gallery covers delivered figures and their document uses. The research-cycle command runs one bounded cycle, with explicit resumption and authored reflection. It starts no recurring schedule.
