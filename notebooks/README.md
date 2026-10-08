# Notebooks

This folder holds the research notebooks. A notebook here calls functions in the `avalanche_research` package to load pinned data runs and draw interactive charts, so the analysis can be read beside the code that produced it. Every notebook is saved with its outputs, so it can be read without running it.

Two notebooks are delivered for review and are executed by `scripts/verify_notebooks.py`. The other three are working notebooks that document earlier steps of the research and are kept for their record.

## Main files

| File | What it shows |
| --- | --- |
| `model-story.ipynb` | Delivered. Model v0.7's structure traced from its code, the reward designs it compares, the validator response to issuance, a test across five protocol upgrades, and the version roadmap |
| `mechanism-explorer.ipynb` | Delivered. Reward and admission mechanisms compared on one reference cohort of real stakes, accepted in the year before Granite |
| `validator-lifecycle-v0.ipynb` | The first validator lifecycle model run from five upgrade origins against what happened in the 90 days after each |
| `staking-periods.ipynb` | The staking-period log, validators and delegators together, checked row by row against the protocol's reward formula |
| `validator-rewards-article.ipynb` | A reconstruction of the evidence in the public article "How Do Avalanche Validators Actually Think About Staking Rewards?" (April 2026). `validator-rewards-article-evidence.csv` is its evidence register |
| `results/` | Small result files: `gogopool-durations.json`, written by `staking-periods.ipynb` and drawn by `scripts/figures/gogopool_short_share.py`, and `behaviour-calibration-inputs.json`, the duration mix and seven-day renewal targets described in its `.md` file |

## Open and run

From the repository root:

```sh
uv sync --locked --group model --group notebook
uv run jupyter trust notebooks/model-story.ipynb notebooks/mechanism-explorer.ipynb
uv run jupyter lab notebooks/
```

Trusting a notebook lets JupyterLab draw its saved interactive charts without running any cell. GitHub shows the text and code but not the charts.

Running a notebook needs the pinned input set in `data/runs/`. Without it, the first data cell stops with a `DataError` that names the missing run. With it, this command checks every run against its receipt and executes both delivered notebooks into a temporary folder, leaving the saved copies unchanged:

```sh
uv run --group notebook python scripts/verify_notebooks.py
```

To measure each notebook's code cells and lines, run `uv run --group notebook python scripts/notebook_budgets.py`. It needs no data.

## How this folder connects to the rest

The notebooks read runs defined in [`data/`](../data/README.md) by run name. Both delivered notebooks read `staking-periods-2026-09-30`, the staking-period run pinned in [`data/pins/`](../data/pins/README.md) for the v0.7 report. The two delivered notebooks draw with [`src/avalanche_research/views/`](../src/avalanche_research/README.md), the same functions `scripts/figures/model_story_figures.py` uses for the images on the research site (see the [figure scripts](../scripts/figures/README.md)).
