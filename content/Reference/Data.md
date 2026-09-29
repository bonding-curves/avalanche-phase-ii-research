---
title: Data
description: The sources behind the research, how each dataset is captured, built, and checked, and how to load the published data release.
---

Every number in this research comes from a dataset declared in `data/data-catalog.json`. The catalog names 13 sources and 35 datasets, with each dataset's query or request, fields, units, and derivation. Each built dataset sits in a run folder that holds a receipt of what was captured, the table built from it, and the result of its checks. A number in a notebook therefore traces back to a Parquet file, the receipt that hashes it, and the raw capture or input runs it came from.

`data/README.md` in the repository gives the commands that reproduce every dataset. Two generated pages list the current state: [1.1 Data Ingestion](/Phase-II/Milestone-1/1-1-Data-Ingestion/) shows coverage, row counts, check results, and known gaps for each dataset, and [1.2 Data Manifest](/Phase-II/Milestone-1/1-2-Data-Manifest/) lists each source's authority and each dataset's fields and latest runs.

## Sources

The staking record comes from the Avalanche Snowflake data share. The other sources supply prices, yields, current network state, and cross-checks.

| Source | What it provides | How it is accessed |
| --- | --- | --- |
| Avalanche Primary Network Data Snowflake share | Every validator and delegation staking transaction since 2020-09-10, the reward transaction that closed each one, the supply reading at each staking block, P- and X-Chain burns, and C-Chain EVM fees | SQL queries kept in `data/queries/`, run with authorized Snowflake credentials. Not public. |
| Avalanche Data API | Current AVAX supply totals, active and completed validations, C-Chain atomic import and export burns, and fees of C-Chain blocks the share lacks | Public REST API. Works without a key at a lower request limit. An optional key raises the limit. |
| Avalanche Metrics API | Daily validator and delegator counts and weights, and daily C-Chain activity | Public REST API, no key |
| Avalanche P-Chain public RPC | The current validator set, and single P-Chain transactions by hash | Public JSON-RPC, no key |
| Avalanche C-Chain public RPC | Receipts and atomic transactions for named gaps in the share and the Data API | Public JSON-RPC, no key |
| Tenderly public C-Chain gateway | Block headers and receipts for the C-Chain blocks the share lacks, as a second record beside the Data API | Public JSON-RPC, no key |
| Avalanche Builder Hub | Hourly median uptime of each current validator over a rolling 332-hour window, as observed by Ava Labs' nodes | Public REST routes, no key, captured daily from 2026-09-24 |
| Binance public data archive | Daily AVAX/USDT candles since 2020-09-22 | Static files, each published beside its SHA-256 |
| DefiLlama | Daily AVAX price since 2020-09-22, and a snapshot of pool yields | Public REST API, no key |
| CoinGecko | Daily AVAX price, market capitalization, and volume | Public REST API, no key. Covers the trailing 365 days only. |
| US Treasury | Daily par yield curve since 2020 | Public XML feed, no key |
| Snowpeer | Six network-wide summary metrics | Public REST API, no key. A curated secondary source, used for cross-checks only. |
| Derived | Tables built in this repository from other runs, such as `derived.staking-periods` and `derived.avax-monetary-daily` | Built locally with `avalanche data derive` |

## Capture, build, check, derive

A dataset read from a source goes through `fetch`, `build`, and `check`. A derived dataset goes through `derive` and `check`. All four are subcommands of `uv run avalanche data`, and none of them overwrites an existing folder.

1. `fetch` captures the source into `capture/`. It keeps the raw response bytes or result rows, the request URLs or the exact SQL text and parameters, timestamps, sizes, and a SHA-256 hash of each file. The receipt also records `contract_sha256`, a hash of the dataset's queries and field list, so a later change to either marks the capture as stale.
2. `build` loads the capture into DuckDB with the catalog's column types and writes a typed Parquet table to `dataset/`. Its receipt records the Parquet file's SHA-256, the capture it came from, the row count, time coverage, and null counts.
3. `check` hashes the capture and the build again and runs the dataset's rules, such as unique transaction hashes, stake and duration bounds, and reconciliation with other datasets. It writes the status and every finding to `check.json`.
4. `derive` builds a derived dataset from the newest built runs of its inputs, or from runs pinned with `--input`. Its receipt names each input run and its hash, so the derived table can be rebuilt from those inputs alone.

A run folder under `data/runs/` holds these files:

| Path | Contents |
| --- | --- |
| `capture/capture.json` | The capture receipt: source, query or request, time, hashes, and for a derived dataset the input runs |
| `capture/raw/` | The raw capture files. Derived runs have none. |
| `dataset/<name>.parquet` | The typed table |
| `dataset/build.json` | The build receipt, with the Parquet file's SHA-256 and a summary of rows, coverage, and nulls |
| `dataset/check.json` | The check result: status, checks run, and findings |

## List and load data

Run these commands from the repository root after the setup in `SETUP.md`:

```sh
uv run avalanche data list
uv run avalanche data runs
uv run avalanche data runs derived.staking-periods
uv run avalanche data describe derived.staking-periods
```

`data list` prints the catalogued sources and datasets. `data runs` lists the built runs under `data/runs/` with capture time and row count, newest first. `data describe` prints one source or dataset from the catalog.

In Python, `avalanche_research.datasets` reads the run folders. Nothing is fetched on load. Every call checks the Parquet file against the SHA-256 in its build receipt and raises an error if they differ.

```python
from avalanche_research import datasets

periods = datasets.load("derived.staking-periods")          # newest run, as a pandas DataFrame
receipt = datasets.receipt("derived.staking-periods")       # capture and build receipts of that run
datasets.runs("snowflake.primary-validator-stakes")          # every built run of one dataset
old = datasets.load("snowflake.primary-validator-stakes", run="validator-stakes-2026-09-19")

db = datasets.connect()                                      # DuckDB, one view per dataset
db.execute("SELECT role, count(*) FROM staking_periods GROUP BY role").fetchall()
```

`datasets.connect()` creates one view per dataset over its newest run. A view name drops the source prefix and any `primary-` prefix, so `derived.staking-periods` is `staking_periods` and `snowflake.primary-validator-stakes` is `validator_stakes`.

## The data release

The built tables are too large for Git. The seven runs the notebooks read are attached to the repository's GitHub release `v0.1.0` as `data-2026-09-22.tar.gz`, about 700 MB, with a `SHA256SUMS` file. Step 4 of `SETUP.md` downloads the archive, checks it, and extracts it into `data/runs/`. After that, `uv run avalanche data runs` lists seven runs.

| Run | Dataset | Rows | Captured |
| --- | --- | ---: | --- |
| `staking-periods-2026-09-22` | `derived.staking-periods` | 7,114,358 | 2026-09-22 |
| `node-table-2026-09-22b` | `derived.node-table` | 7,644 | 2026-09-22 |
| `validator-stakes-2026-09-22` | `snowflake.primary-validator-stakes` | 57,560 | 2026-09-22 |
| `validator-stakes-2026-09-19` | `snowflake.primary-validator-stakes` | 57,521 | 2026-09-19 |
| `avax-price-helicon-baseline-early` | `defillama.avax-price-daily` | 2,188 | 2026-09-21 |
| `avax-market-helicon-baseline-early` | `coingecko.avax-market-daily` | 366 | 2026-09-21 |
| `monetary-daily-2026-09-24-interim` | `derived.avax-monetary-daily` | 2,204 | 2026-09-24 |

Every run in the release passed its check. `scripts/verify_notebooks.py` checks each of the seven against its build receipt before it runs the notebooks.

## Limits

The Snowflake data is the Avalanche Foundation's own share, read with authorized credentials. Its redistribution terms have not been assessed. Anyone without access to the share can use the built runs in the release but cannot capture new ones.

The release leaves out three large Snowflake inputs: `snowflake.primary-delegator-stakes`, `snowflake.primary-staking-rewards`, and `snowflake.primary-staking-supply`. Their rows are joined into `derived.staking-periods`, which has one row per commitment, validators and delegators together. A commitment is the period of one staking transaction. The article notebook's data table marks the three inputs as not in the data release. Rebuilding `derived.staking-periods` needs all four Snowflake staking runs.

The monetary ledger in the release is an interim run. It writes a checked total supply only through 2023-10-05, because its C-Chain fee data is incomplete from 2023-10-06 on. Stake is checked over more days than supply. The article notebook reports how many days each mean covers.

CoinGecko's keyless API serves only the trailing 365 days, so the full price history comes from DefiLlama and Binance. Current-state sources such as the P-Chain RPC, the Data API supply endpoint, and Builder Hub hold no history. Their datasets are dated snapshots, and history exists only from the first capture on.

Each dataset's known gaps are listed on [1.1 Data Ingestion](/Phase-II/Milestone-1/1-1-Data-Ingestion/). To run the notebooks on this data, see [Notebooks](/Reference/Notebooks).
