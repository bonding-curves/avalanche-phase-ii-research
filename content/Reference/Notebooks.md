---
title: Notebooks
description: What the two research notebooks answer and show, which datasets they read, and how to run them.
---

The repository holds two Jupyter notebooks in `notebooks/`. Both read the built datasets described on [Data](Data.md) and never fetch or build data themselves. A commitment in both is the period of one staking transaction, from its start time to its end time.

| Notebook | Question | Datasets |
| --- | --- | --- |
| `validator-rewards-article.ipynb` | What does the article *How Do Avalanche Validators Actually Think About Staking Rewards?* report, and how much of it can the data reproduce? | `snowflake.primary-validator-stakes`, `derived.staking-periods`, `derived.avax-monetary-daily`, `defillama.avax-price-daily`, `coingecko.avax-market-daily` |
| `staking-periods.ipynb` | Does one log of every validator and delegator commitment hold up row by row against the protocol's reward formula, and where does the source data have gaps? | `derived.staking-periods`, `derived.node-table` |

## Validator rewards article

`validator-rewards-article.ipynb` rebuilds the evidence, data, and results of the article published on April 28, 2026, and keeps each assumption and open gap in view. The notebook is a work in progress. The article itself is on [How Do Avalanche Validators Actually Think About Staking Rewards?](../Phase%20II/Essential%20Readings/How%20Do%20Avalanche%20Validators%20Actually%20Think%20About%20Staking%20Rewards/index.md).

The notebook has these parts, in order:

1. The article evidence table lists the 40 targets of the reproduction from `notebooks/validator-rewards-article-evidence.csv`, each with its research domain, stage, evidence state, and status.
2. The evidence map is a heatmap of how many targets are complete for each research domain and each stage, from source to validation. A selector filters it by evidence state.
3. The article data table lists the six datasets the article needs, with coverage, row count, join keys, and whether each loaded as expected. The table marks the three Snowflake inputs that the data release leaves out.
4. Validator commitments defines one validator commitment and marks which ones are valid for analysis: complete fields, a unique transaction hash, a duration of 14 to 365 days, a positive stake, and a delegation fee of 2% to 100%. Each valid commitment is rewarded, unrewarded, or pending.
5. Observed commitment durations is a bar chart of valid commitments in one-week bins, with the mean and median marked. A selector switches between share and count.
6. Stake by commitment duration is a bar chart of validator self-stake summed in each duration bin. It measures stake committed over time, not the stake active at one moment.
7. Upgrade periods assigns each commitment to the network upgrade in force when it was accepted, with the Apricot phases combined, and tabulates counts and duration statistics per period.
8. Observed duration by upgrade period is a heatmap of the share of commitments at each duration within each upgrade period.
9. Validator commitments by protocol era is a table of counts, nodes, self-stake, and plain and stake-weighted durations for each era.
10. The last table adds mean realized total supply, validator and delegator stake, and the validator and combined staking ratios for each era, from the monetary ledger. It reports how many days of checked supply and stake each mean covers.

The notebook pins validator stakes to the run `validator-stakes-2026-09-19` and reads the newest run of every other dataset.

## Staking periods

`staking-periods.ipynb` reads `derived.staking-periods`, which joins the four Snowflake staking datasets into one row per commitment, validators and delegators together. Each row has its upgrade regime, its recorded potential reward, its realized reward where one exists, and the reward the protocol formula gives from the supply reading before its block. Where the two rewards agree, the row is reproduced.

The notebook has these parts, in order:

1. A summary table reads the run's check result. It gives the rows by role, how many commitments the formula reproduces, the gaps, and the time each query takes. The notebook stops if the check did not pass or a query takes over 100 ms.
2. Findings states what the log shows, such as the number of commitments by role, where the formula reproduces the recorded reward, and the two gaps in the source data. The findings were written from the run of 2026-09-19, so their counts differ from the summary table, which reads the run of 2026-09-22.
3. V1 Validator lifelines draws one row per validator node over time, with each commitment as a bar coloured by fee class, zero reward, or still open. Network upgrades are shaded bands. Rows and filters read `derived.node-table`.
4. V2 Arrivals grid shows weeks across and stake size up, coloured by the count, duration, or first-time share of commitments accepted in each cell. Validators are above and delegators below.
5. V2b Duration grid shows weeks across and commitment length up, coloured by count, total stake, or median or mean stake.
6. V2c Size against duration plots stake against duration in four panels, one per era: before Banff, Banff and Cortina, Durango, and Etna onward. The panels share one colour scale.
7. V3 Active stock shows how many commitments are open in each week, stacked by duration class, as counts or stake and as totals or shares.
8. V2d Linked canvas puts the two grids, the lifelines, and the active stock on one week axis. A zoom moves all four. A box on a grid filters the others to the nodes it holds, a box on the lifelines marks those nodes' commitments on the grids, and a tap on a lifeline row lists its nodes.

Each chart section is followed by a list of what to look for, with the numbers behind each observation.

## Run time

`scripts/verify_notebooks.py` runs both notebooks from start to finish in about two minutes, with a peak memory of about 3.4 GB. `SETUP.md` asks for 8 GB of memory and about 2 GB of free disk space.

## Run the notebooks

`SETUP.md` in the repository gives the full steps for macOS, Linux, and Windows under WSL. It is written so that a person or an AI coding agent can follow it in order.

1. In step 1, install `git` and `uv`.
2. In step 2, clone the repository on its `phase-ii` branch.
3. In step 3, install the environment with `uv sync --locked --group notebook`.
4. In step 4, download `data-2026-09-22.tar.gz` from the release `v0.1.0`, check it, and extract it into `data/runs/`.
5. In step 5, run `uv run --group notebook python scripts/verify_notebooks.py`. Every line starts with `PASS`, and the last line is `All checks passed.`
6. In step 6, open JupyterLab with `uv run --group notebook jupyter lab notebooks/` and choose **Run > Run All Cells**.

GitHub shows the notebooks' text and code. It does not draw the interactive charts. The charts, their widgets, and the linked canvas work only when the notebook runs in JupyterLab.
