# Setup: run the notebooks

These steps take a new machine from nothing to both notebooks running in JupyterLab. They are written so that a person or an AI coding agent can follow them in order: each step gives the command, what you should see, and what to do if you do not.

The commands are for macOS and Linux. On Windows, run them inside WSL.

## What you get

| Notebook | What it shows |
| --- | --- |
| `notebooks/validator-rewards-article.ipynb` | The data behind *How Do Avalanche Validators Actually Think About Staking Rewards?*: what the article reports and what the data can reproduce, validator commitments and their durations, and validator commitments compared across protocol upgrades, with supply and staking ratios |
| `notebooks/staking-periods.ipynb` | Every validator and delegator staking period since genesis: validator lifelines, arrivals by stake and by duration, the active stock of open periods, and a linked canvas where a selection on one chart filters the others |

Both notebooks are saved with their outputs, so GitHub shows their text and code. The interactive charts draw only when the notebook runs in JupyterLab.

## 1. Prerequisites

You need `git` and `uv`, and about 2 GB of free disk space and 8 GB of memory.

```sh
git --version
uv --version
```

Each command prints a version. If `uv` is missing, install it with `curl -LsSf https://astral.sh/uv/install.sh | sh` and open a new terminal. `uv` installs the right Python by itself.

## 2. Clone the repository

```sh
git clone --branch phase-ii https://github.com/AVL-Foundation/ext-bcrg-validator-research.git
cd ext-bcrg-validator-research
```

Every later command runs from this folder.

## 3. Install the Python environment

```sh
uv sync --locked --group notebook
uv run avalanche data list
```

The second command prints a table of the catalogued datasets. If `uv sync` fails with a lock error, run `git status` and make sure no file was changed after cloning.

## 4. Download and extract the data

The notebooks read built data tables that are too large for Git. They are attached to the repository's release `v0.1.0` as one archive of about 700 MB with a checksum file.

With the GitHub CLI (`gh auth login` first if you have not signed in):

```sh
gh release download v0.1.0 --repo AVL-Foundation/ext-bcrg-validator-research --dir release
```

Or download `data-2026-09-22.tar.gz` and `SHA256SUMS` from the release page in a browser into a folder named `release`.

Check and extract:

```sh
cd release && shasum -a 256 -c SHA256SUMS && cd ..
mkdir -p data/runs
tar -xzf release/data-2026-09-22.tar.gz -C data/runs
uv run avalanche data runs
```

`shasum` prints `data-2026-09-22.tar.gz: OK`. If it prints `FAILED`, the download is incomplete: delete it and download again. The last command lists seven runs. `release/MANIFEST.md` describes each one.

## 5. Verify

```sh
uv run --group notebook python scripts/verify_notebooks.py
```

This checks each data run against its receipt, then runs both notebooks from start to finish in the background, which takes about two minutes. Every line starts with `PASS` and the last line is `All checks passed.` A `FAIL` line names the problem. A failed data run means step 4 is incomplete.

## 6. Open the notebooks

```sh
uv run --group notebook jupyter lab notebooks/
```

JupyterLab opens in the browser. Open a notebook and choose **Run > Run All Cells**. The charts draw as each cell finishes. The widgets beside each chart change what it shows, and on the linked canvas at the end of `staking-periods.ipynb` a box drawn on one chart filters the others.

## What the data is

Each folder under `data/runs/` is one run: the receipt of how the data was captured, the built table as a Parquet file, and the build and check receipts with SHA-256 hashes. `data/README.md` explains the layout, and `data/data-catalog.json` defines every dataset. The staking data comes from the Avalanche Foundation's Snowflake data share, and the price data from DefiLlama and CoinGecko.

The release leaves out three large Snowflake inputs, the delegator stakes, staking rewards, and staking supply tables. Their rows are already joined into `derived.staking-periods`. The article notebook's data table marks them as not in the data release.
