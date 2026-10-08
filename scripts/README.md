# Scripts

This folder holds the command-line scripts that sit on top of the Python package. They check the research site, generate its data-driven pages, score the model's forecasts, check the notebooks, and, in [`figures/`](figures/README.md), draw every chart the site shows. The package in `src/avalanche_research/` holds the logic. A script reads data runs through it, often the runs a pin names, and writes tables, figures, or pages.

Each script's own docstring gives its exact usage, and `--help` prints it for the scripts that take arguments.

## Main files

| File | What it does |
| --- | --- |
| `figures/` | One script per chart or set of charts. See [`figures/README.md`](figures/README.md) |
| `model_v07_report_runs.py` | Reruns staking model v0.7 exactly as tagged `model-v0.7.0` on the pinned inputs, for the v0.7 report's experiment charts |
| `model_development_scores.py` | Runs models v0.7 and v0.8 from 19 forecast origins, 200 runs each, and scores them against simple forecasts at 30, 90, and 180 days |
| `model_distribution_scores.py` | Scores the same runs as distributions, from the file the previous script writes |
| `renewal_block_scores.py` | Compares v0.8's renewal model with v0.7's on the commitments that end after each origin |
| `helicon_activation_open.py` | Lists the validator commitments open when Helicon activated and reconciles them with the first validator snapshot after it |
| `verify_notebooks.py` | Checks the pinned input set against its receipts and executes the two delivered notebooks into a temporary folder |
| `notebook_budgets.py` | Reports each notebook's code cells, code lines, and largest cell |
| `milestone_pages.py` | Generates the Milestone 1.1 and 1.2 pages from the data catalog, run receipts, and pins (`build` or `check`) |
| `overview_tables.py`, `research_navigation.py` | Build and check the site's collection overviews, topic pages, and collection index |
| `check_site.py`, `check_links.py` | Check the published content and every link in the built site |
| `check_commit_message.py` | The commit-message check run by the hook in `.githooks/` |
| `test_*.py` | Tests for the site scripts, run with the standard library's `unittest` |

## Run

Install the environment once from the repository root, then run a script with `uv run`. Scripts that run the model need the `model` group, and scripts that draw need the `notebook` group.

```sh
uv sync --locked --group model --group notebook
uv run python -m unittest discover -s scripts -p 'test_*.py'
uv run --group notebook python scripts/notebook_budgets.py
uv run --group notebook python scripts/verify_notebooks.py
```

The first two commands need no data. `verify_notebooks.py` needs the pinned input set extracted into `data/runs/`, as [SETUP.md](../SETUP.md) describes. The site checks run together from `.site/` with `uv run --project .. npm run verify`.

Scoring scripts take an output folder. For example, `uv run --group model python scripts/model_development_scores.py <output folder> [workers]` writes every run's value and the score tables there, and `model_distribution_scores.py` then reads that folder.

## How this folder connects to the rest

The scripts read the dataset definitions and pins in [`data/`](../data/README.md) and the code in [`src/avalanche_research/`](../src/avalanche_research/README.md). Their outputs are the tables, figures, and generated pages under `content/`, which the research site publishes.
