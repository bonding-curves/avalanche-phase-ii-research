# Report pack

This package writes the standard PSuU outputs of a sweep. PSuU, parameter selection under uncertainty, scores every run against declared goals and asks which settings of each reward design keep the goals met across scenarios.

Install the report dependencies from the repository root:

```bash
uv sync --locked --group report
```

## Inputs

A pack reads three files.

1. The sweep's wide table, one row per run and horizon, as Parquet.
2. The sweep manifest, `sweep-manifest.json`, which gives every column of the wide table one role: `setting`, `scenario`, `behaviour`, `kpi` or `id`. It also names the family, horizon, block and pairing columns, the baseline rows, the blocks to analyse and the column that groups runs sharing their draws. A column the manifest does not list stops the run. [`results/m2-analysis/sweep-manifest.json`](../../../results/m2-analysis/sweep-manifest.json) is the manifest of the Milestone 2 sweep.
3. The goal and utility specification, which sets each goal's KPIs, pass lines, utilities and weights, and the region rules.

For a new sweep, draft a manifest and then check every role by hand:

```bash
uv run avalanche report manifest --wide wide.parquet --out sweep-manifest.json
```

## Commands

```bash
uv run avalanche report psuu --wide wide.parquet --manifest sweep-manifest.json --spec utility-spec.json --out psuu
uv run avalanche report pack --wide wide.parquet --manifest sweep-manifest.json --spec utility-spec.json --out pack \
  --model-version v0.8.0
```

`report psuu` writes the scored runs, goal and KPI summaries, random forests, response curves, regions and four figure kinds. `report pack` writes those and adds the following, with an `index.md` that lists every output and a `pack-receipt.json` with the input hashes.

| Module | Output |
| --- | --- |
| `heatmaps` | Sorted cells of each design's settings by goal utility, each setting against each scenario, each pair of settings |
| `trees` | Depth-three trees from settings and scenario to the pass of each goal and each KPI, with out-of-fold accuracy and importance |
| `grid` | Each input against each KPI: a seeded sample of runs, binned means and 10th to 90th percentile bands |
| `recommend` | Recommendation tables (point estimate, range per goal, range for every goal, with confidence) and the sign-and-confidence matrix, as Markdown and CSV |

Every figure is a PNG and an SVG, and the figures these four modules add carry a CSV of the data they draw. Every split, sample and resample uses `--seed`, so a rerun on the same inputs writes the same tables.

The trees are for reading. They describe where runs pass and make no causal claim. Their accuracy is measured on folds the tree did not see, grouped by shared draws, and is shown beside the accuracy of always predicting the larger class.
