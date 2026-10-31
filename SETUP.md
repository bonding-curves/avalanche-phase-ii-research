# Setup

These steps take a fresh machine from nothing to the tests passing, the notebooks open, and the research site running. Each step gives the command and what you should see.

The commands are for macOS and Linux. On Windows, run them inside WSL.

## 1. Prerequisites

| Tool | Version | Used for |
| --- | --- | --- |
| `git` | any recent | Cloning the repository |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | a recent release, last tested with 0.12 | The Python environment. uv installs a suitable Python by itself |
| Python | 3.11 to 3.14 | The package, tests, and notebooks. The tests were last run on Python 3.13 |
| [Node.js](https://nodejs.org/) | 22 or later, with npm 10.9.2 or later | The research site |
| [Graphviz](https://graphviz.org/download/) | any recent | The `dot` command draws the model's structure diagram in `model-story.ipynb` |

Install Graphviz with `brew install graphviz` on macOS or `sudo apt install graphviz` on Debian and Ubuntu. If uv is missing, install it with `curl -LsSf https://astral.sh/uv/install.sh | sh` and open a new terminal.

Check each tool:

```sh
git --version
uv --version
node --version
npm --version
dot -V
```

Each command prints a version. Plan for about 2 GB of free disk space, most of it for the Python environment and the site's Node packages.

## 2. Clone the repository

```sh
git clone --branch milestone-2 git@github.com:AVL-Foundation/ext-bcrg-validator-research.git
cd ext-bcrg-validator-research
```

Every later command runs from this folder unless a step says otherwise.

## 3. Install the Python environment

```sh
uv sync --locked --group model --group notebook
```

This installs the package with its test tools (the `dev` group, installed by default), the model engine (`model`: cadCAD, NumPy, and Param), and JupyterLab with the charting libraries (`notebook`). `--locked` installs the exact versions in `uv.lock`. If it fails with a lock error, run `git status` and make sure no file changed after cloning.

## 4. Run the tests

```sh
uv run pytest -q
```

The suite checks software behaviour. Tests requiring external input runs skip when those runs are absent. Step 7 also provides a complete small simulation with its own included inputs.

## 5. Query the model from the command line

```sh
uv run avalanche model describe
```

This needs no data. The first line reads `PASS | model describe | 13 mechanisms`, followed by the mainnet staking parameters and the upgrade schedule the model uses. The count covers the protocol inventory, including admission settings as well as reward formulas.

Two other commands work without data:

```sh
uv run avalanche model reward --help
uv run avalanche data list
```

`avalanche model reward` computes the Primary Network potential reward for one stake. `avalanche data list` prints the data catalog's sources and datasets.

For a data-free calculation, use an illustrative supply counter of 465 million AVAX:

```sh
uv run avalanche model reward --stake 2000 --duration 14 \
  --start 2026-09-01T00:00:00 --supply 465000000
```

The potential reward is **4.239076507 AVAX**. This exercises protocol arithmetic, using a supplied counter rather than a captured chain state. It does not run a staking simulation.

## 6. Open the notebooks

| Notebook | What it shows |
| --- | --- |
| `notebooks/model-story.ipynb` | Written for model v0.7: its structure traced from the code, the reward designs it compares, the validator response to issuance, a test of the lifecycle model across five protocol upgrades, and the model's version roadmap |
| `notebooks/mechanism-explorer.ipynb` | Reward and admission mechanisms compared on one reference cohort of real stakes: reward rate by duration, the AVAX each would mint, and admission by duration |
| `notebooks/staking-periods.ipynb` | Every validator and delegator staking period since genesis, from the Avalanche Foundation's Snowflake data share |
| `notebooks/validator-lifecycle-v0.ipynb` | The first behaviour model, v0: from five origin days, the validator commitments open at each, set against what happened |
| `notebooks/validator-rewards-article.ipynb` | A reading of Eric Lu's article on how validators think about staking rewards |

All five notebooks are saved with their outputs. GitHub shows their text and code but does not draw their interactive charts.

Trust the notebooks, then start JupyterLab:

```sh
uv run jupyter trust notebooks/*.ipynb
uv run jupyter lab notebooks/
```

JupyterLab opens in the browser. Open a notebook and read it without running it. Jupyter draws saved interactive charts only in a notebook you have trusted, which is why the first command is needed.

Do not choose **Run All** before the input set is in place. The notebooks read the staking periods built from the Avalanche Foundation's Snowflake data share, which are too large for Git. Run without them, a notebook stops at its first data cell with a `DataError` that names the missing run, for example `no built run for derived.staking-periods named staking-periods-2026-09-30`. Reading the saved outputs requires no cell execution. Use a separate copy if you want to experiment without changing the delivered notebooks.

## 7. Run a model experiment or the notebooks

To reproduce the report's central 50-pair one-year result, follow the [central-case guide](examples/report-reproduction/README.md). It obtains a checked 12.1 MB input bundle from the Foundation repository and rebuilds the percentile table and trajectory figure.

The [worked experiment](examples/first-experiment/README.md) includes a compact input snapshot and expected results. It needs no Snowflake or API credentials:

```sh
uv run --frozen --group model --group notebook python scripts/first_experiment.py --output release/first-experiment
uv run --frozen --group model --group notebook python scripts/first_experiment.py --output release/first-experiment --check
```

Both commands report `status: pass`. Open `release/first-experiment/figure.html` in a browser. The guide explains its four paired comparisons, assumptions and checks. Use a new output directory for a new experiment. The [research-cycle guide](examples/research-cycle/README.md) adds a declared hypothesis, numerical assessment and separate methodology reflection.

The full historical inputs for the notebooks and report reruns are separate from that compact example and are not yet distributed with this repository. When you have their pinned input set, extract it into `data/runs/`, so each run is one folder such as `data/runs/staking-periods-2026-09-30/`. Then check it and run the model and mechanism notebooks:

```sh
uv run python scripts/verify_notebooks.py
```

This checks each data run against its receipt and runs the model and mechanism notebooks into a temporary folder, so the saved copies are not changed. Every line starts with `PASS` and the last line reads `All checks passed.` A `FAIL` line names the problem. After that, **Run > Run All Cells** works in JupyterLab.

[`data/README.md`](data/README.md) describes the run layout, and [`data/data-catalog.json`](data/data-catalog.json) defines every dataset.

## 8. Run the research site

The site renders `content/` with Quartz. Its build scripts call Python, so run them through uv:

```sh
cd .site
npm ci
uv run --project .. npm run dev
```

`npm ci` installs the pinned Node packages. The last command builds the site and serves it at <http://localhost:8844>. It rebuilds when a page under `content/` changes. Stop it with Ctrl+C.

## 9. Build and check the site without serving it

From `.site/`:

```sh
uv run --project .. npm run build
```

This writes the static site to `.site/public/`, which any static file server can host.

```sh
uv run --project .. npm run verify
```

This runs the site's script tests, builds the site, checks the published content, and checks every rendered link against the known-failure list in `data/quartz-link-baseline.json`. It exits non-zero on a new failure.
