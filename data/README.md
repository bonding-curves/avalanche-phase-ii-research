# Research data

This folder defines every dataset the research uses and records how each one was obtained. It holds the data catalog, the SQL behind each Snowflake dataset, the pinned input sets, and two small sets of committed evidence. The data files themselves are too large for Git and are not stored here. They are rebuilt from their definitions with the `avalanche` command line tool into `data/runs/`, which Git ignores.

A **dataset** is one table with a catalog ID, such as `derived.staking-periods`. A **run** is one build of a dataset: a folder `data/runs/<run>/` with a `capture/` folder holding what was fetched and its receipt, and a `dataset/` folder holding the typed Parquet file, its build receipt `build.json`, and its check result `check.json`.

| Path | What it holds |
| --- | --- |
| [`data-catalog.json`](data-catalog.json) | Every source and dataset: provider, endpoint or query, fields, units, and derivation. It lists 20 sources and 89 datasets |
| [`data-catalog.schema.json`](data-catalog.schema.json) | The JSON schema that validates the catalog |
| [`queries/`](queries/) | The exact SQL text each Snowflake dataset runs |
| [`pins/`](pins/) | Pinned input sets: the exact runs a result was made from, with their hashes. See [`pins/README.md`](pins/README.md) |
| `evidence/` | Committed evidence: the receipt capture that repairs C-Chain block 95,492,477, and the validator commitments open when Helicon activated, with their receipt |
| [`operator-attributions.json`](operator-attributions.json) | Every name or role attached to a validator reward address, funding address, or node, with its evidence |
| [`monetary-source-audit.md`](monetary-source-audit.md) | How each part of the daily monetary ledger was sourced and reconciled |
| [`research-navigation.json`](research-navigation.json) | The registry behind the research site's source collections |
| [`quartz-link-baseline.json`](quartz-link-baseline.json) | The known rendered-link failures the site check tolerates |
| `runs/` | Built runs. Not stored in Git |

## Inspect and rebuild

The catalog can be read without any data or credentials. These commands run from the repository root after `uv sync --locked`:

```sh
uv run avalanche data list
uv run avalanche data describe derived.staking-periods
uv run avalanche data manifest --json
```

Each dataset is rebuilt in three steps, `avalanche data fetch`, `build`, and `check`, into a new run folder. A derived table is built with `avalanche data derive` from runs already built. The Snowpeer summary needs no credentials, the Snowflake datasets need authorized access to the Avalanche data share, and the sections below give the commands for each dataset. To confirm that a set of runs matches the inputs of a published result, check its pin:

```sh
uv run avalanche data pin-check data/pins/p6-v0.7-report.json
```

## How this folder connects to the rest

The package in [`src/avalanche_research/`](../src/avalanche_research/) reads the catalog. Its `sources` modules capture each provider, and its `datasets` modules build, check, and load runs. The model in `src/avalanche_research/model/` reads two derived tables, `derived.staking-periods` and `derived.avax-monetary-daily`. The scripts in [`scripts/`](../scripts/) and the notebooks in [`notebooks/`](../notebooks/) load runs by catalog ID, usually the runs a pin names, and write the figures and tables shown on the research site.

The rest of this guide gives the status of every dataset and how to reproduce each one.

## Current coverage

| Dataset | Output | Status |
| --- | --- | --- |
| `snowpeer.network-summary` | One timestamped row in JSON and Parquet | Implemented and tested |
| `snowflake.primary-validator-stakes` | One Parquet row per validator staking transaction since 2020-09-10 | Implemented, tested, and captured live |
| `snowflake.primary-delegator-stakes` | One Parquet row per delegation transaction since 2020-09-10 | Implemented, tested, and captured live |
| `snowflake.primary-staking-rewards` | One Parquet row per reward transaction closing a staking period | Implemented, tested, and captured live |
| `snowflake.primary-staking-supply` | One Parquet row per staking transaction with the block supply context behind its potential reward | Implemented, tested, and captured live |
| `snowflake.primary-burn-events` | One deduplicated P- or X-Chain transaction per row with recorded AVAX burn | Implemented, tested, and captured for 2026-09-16; not an all-chain burn total |
| `data-api.c-chain-atomic-burn` | One C-Chain import or export per row with the exact AVAX input-minus-output burn | Implemented, tested, and captured for the full history on 2026-09-23: 1,171,886 transactions, five imports left for the node record below |
| `c-chain-rpc.receipt-gap-repairs` | One C-Chain transaction receipt per row for a specified block missing from the Snowflake share | Implemented and checked for block 95,492,477; a source repair, not a combined daily burn |
| `snowflake.primary-burn-daily` | One Parquet row per UTC date and chain (P or X) with the AVAX burned, how each burn was established, the L1 validator fees, and the hashes the share cannot settle | Implemented, tested, and captured for the full history on 2026-09-23; 24 P-Chain imports settled by the node record below |
| `p-chain-rpc.transactions` | One Parquet row per requested P-Chain transaction with the AVAX it consumed, created, and burned, from the node's own record | Implemented, tested, and captured for the 24 imports the share and the Data API cannot settle |
| `c-chain-rpc.atomic-transactions` | One Parquet row per requested C-Chain import with the AVAX it consumed, created, and burned, decoded from the node's signed transaction | Implemented, tested, and captured for the five 2021 imports whose consumed UTXOs the Data API lists incompletely |
| `snowflake.c-chain-evm-burn-daily` | One Parquet row per UTC day with the exact EVM fee burn over the share's complete C blocks, the blocks read once where the share repeats them, and the absent and short blocks counted | Implemented, tested, and captured 2020-09-23 to 2026-09-21 in seven year runs; three days of 2023 and about forty of 2025 wait on the block-fee capture |
| `snowflake.c-chain-block-gaps` | One Parquet row per C block the share lacks or holds without all its receipts | Implemented and tested; the full-history capture is the next step |
| `data-api.c-chain-block-fees` | One Parquet row per gap block read from the Data API block record with the fees burned in it | Implemented and tested; captured in part, as far as the key's daily allowance reached |
| `c-chain-rpc.block-receipt-fees` | The same rows computed from a public node's block header and receipts, with no key | Implemented and tested; captured for the 2023 gap blocks on 2026-09-24 |
| `derived.avax-monetary-daily` | One Parquet row per UTC date with recognised reward issuance, burns by chain, realised supply replayed from genesis and effective active stake, every amount in wei with coverage per component | Run `monetary-daily-2026-09-26` checks 2,202 complete UTC days from genesis through 2026-09-20. Its API reward-total difference is an apparent accrual-versus-payout definition gap, not missing historical ledger coverage; see the monetary source audit |
| `coingecko.avax-market-daily` | One Parquet row per day of AVAX price, market capitalization, volume, log return, and 30-day realized volatility | Implemented, tested, and captured live; public API serves the trailing 365 days only |
| `binance.avax-usdt-daily` | One Parquet row per UTC day of AVAX/USDT open, high, low, close, volumes, log return, and 30-day realized volatility from Binance's public archive | Implemented, tested, and captured from 2020-09-22 to 2026-09-25; every file checked against its published SHA-256 |
| `defillama.avax-price-daily` | One Parquet row per daily AVAX price observation since 2020-09-22 with log return and 30-day realized volatility | Implemented, tested, and captured live |
| `p-chain-rpc.current-validators` | One Parquet row per validator in the current Primary Network set with stake, fee, observed uptime, connection, and delegator totals | Implemented, tested, and captured live; a snapshot, not a history |
| `defillama.pool-yields` | One Parquet row per DefiLlama pool on Avalanche or in a declared proof-of-stake staking project, with yields, TVL, and risk descriptors | Implemented, tested, and captured live; a snapshot |
| `us-treasury.par-yield-daily` | One Parquet row per business day and tenor of the US Treasury par yield curve since 2020 | Implemented, tested, and captured live |
| `metrics-api.primary-staking-daily` | One Parquet row per day of Metrics API validator and delegator counts and weights since 2021-02-28 | Implemented, tested, captured live, and reconciled against the Snowflake datasets |
| `metrics-api.c-chain-activity-daily` | One Parquet row per day of Metrics API C-Chain active addresses, transactions, gas, fees, and gas price since 2021-03-21 | Implemented, tested, and captured live |
| `data-api.avax-supply` | One Parquet row per capture with the Data API's current supply, staked, locked, cumulative reward, and burn totals | Implemented, tested, and captured live; the API publishes no history |
| `data-api.validators-active` | One Parquet row per active Primary Network validation at the capture instant with the Data API's uptime, health, delegation capacity and fill, version, geolocation, and staking type | Implemented, tested, captured daily beside the RPC snapshot, and reconciled against it as a second observer |
| `data-api.validators-completed` | One Parquet row per completed Primary Network validation with its reward addresses, potential reward, and cumulative delegation | Implemented, tested, captured once for the full history (56,963 rows on 2026-09-22), and reconciled against the Snowflake stake captures |
| `data-api.validators-completed-recent` | The newest 15 pages of completed Primary Network validations, about 1,500 rows, captured daily so the completed history grows without another full pull | Implemented, tested, and checked against the full history where the two overlap |
| `builder-hub.validator-uptime` | One capture of Builder Hub's validator explorer: one Parquet row per validator per hour of its rolling 332-hour window of median uptime across Ava Labs' observing nodes, with companion tables of validator scalars, daily bench totals, and hourly block proposals | Implemented, tested, and captured daily from 2026-09-24; the first capture reaches back to 2026-09-10 08:00 UTC |
| `derived.staking-periods` | One Parquet row per staking period, validators and delegators together, with reward outcome, supply reading, upgrade regime, and the protocol kernel's reward for the row | Implemented, tested, and derived from the four Snowflake staking runs |
| `derived.node-table` | One Parquet row per validator node: the three clocks (span, tenure, current streak) and their stake weights, stake and fee history, delegation, rewards and failures, upgrade regimes, and the reward address as an operator proxy, all clipped at the validator capture time | Implemented, tested, and derived from the staking-period log and the two Snowflake stake runs |
| `derived.validator-weeks` | One Parquet row per validator node per UTC week, from 2020-09-21 to the last full week before Helicon: stake, fee, age, days staked, completed and started periods, the reward address, delegated weight and capacity, and whether the node was on offer, all known at the Monday cutoff, with the week's delegations as outcomes | Implemented, tested, and derived on 2026-09-27: 385,922 rows on 7,644 nodes over 313 weeks |
| `derived.observed-delegations` | One Parquet row per delegation accepted in the same window, with its exact duration, week, delegator address, and whether its validator was on offer at that week's cutoff | Implemented, tested, and derived on 2026-09-27: 7,056,204 delegations |
| `derived.market-weeks` | One Parquet row per week of the same window: the unstaked supply stock at the Monday cutoff, the week's delegated volume by stratum, the concentrated address's share, and the AVAX price and 30-day volatility at the cutoff | Implemented, tested, and derived on 2026-09-27: 313 weeks |
| `derived.validator-uptime-hourly` | One Parquet row per validator per hour across every Builder Hub capture, with the number of captures that held the hour and whether they disagreed | Implemented, tested, and derived daily; the only record of hourly uptime percentages outside Ava Labs, and it exists only from the captures on |
| `derived.helicon-commitments` | One Parquet row per validation cycle started at or after Helicon's activation, with its duration and bin, whether the node validated before Helicon, the change from the node's previous period, and whether the transaction auto-renewed | Implemented, tested, and derived daily from 2026-09-28 over every validator snapshot: 73 cycles on 67 nodes on the first run |
| `snowflake.subnet-validator-transactions` | One Parquet row per P-Chain transaction that adds, removes, converts, registers, or disables a Subnet or L1 validator, one per initial validator of each conversion | Implemented, tested, and captured on 2026-09-29: 6,530 rows, 329 converted Subnets |
| `derived.subnet-validation` | One Parquet row per node and Subnet: Subnet periods, the Subnet's L1 conversion, the node's L1 registration, and its Primary Network span | Implemented, tested, and derived on 2026-09-29: 4,257 rows on 3,946 nodes, reproducing the catalog's ACP-77 counts |
| `derived.operators` | One Parquet row per validator node with its operator (latest reward address) and fleet (same entry week, exit week, and fee), and named agents with their evidence | Implemented, tested, and derived on 2026-09-29: 7,644 nodes, 3,963 operators, 4,247 fleets |
| `c-chain-rpc.minipool-records` | One Parquet row per minipool record of GoGoPool's MinipoolManager contract, with its node, owner, multisig, amounts and times, every call made at one recorded C-Chain block | Implemented, tested, and captured on 2026-11-05 at block 99,494,695: 1,639 records, 244 owner addresses |
| `derived.operator-clusters` | One Parquet row per validator staking period with four groupings known before the held-back cut of 2025-11-19: its reward address, an owner key that splits the pool address by minipool owner, the entry cohort, and a connected component | Implemented, tested, and derived on 2026-11-05: 58,213 periods on 7,681 nodes |
| `allium.prices-hourly` | One Parquet row per token and hour of Allium's USD price for native AVAX, WAVAX, sAVAX, ggAVAX and yyAVAX, from the Foundation's Snowflake account | Implemented, tested, and captured on 2026-11-05: 158,017 rows from 2022-06-01 01:00 UTC to 2026-11-05 14:00 UTC |
| `allium.dex-token-prices-hourly` | One Parquet row per hour with trades of Allium's WAVAX price from decentralised exchange trades, from the Foundation's Snowflake account | Implemented, tested, and captured on 2026-11-05: 50,320 hours from 2021-02-02 15:00 UTC, 128 hours without a row |
| `af.economy-gas-fees-daily` | One Parquet row per UTC day of the C-Chain gas fees the Foundation's Gross Chain Product economy counts, in AVAX and USD | Implemented, tested, and captured on 2026-11-05: 2,201 days from 2020-09-23 to 2026-11-04, 33 days of 2020 and January 2021 without a row |
| `derived.market-daily-vector` | One Parquet row per UTC day from 2021-02-02 to 2025-11-18 with the AVAX close and log return, the realised variance of hourly returns, the Bitcoin log return and the log gas burn | Implemented, tested, and derived on 2026-11-05: 1,751 days, none on or after the held-back cut |
| `allium.lending-interest-rates` | One Parquet row per lending rate update on Avalanche for WAVAX, AVAX, sAVAX, USDC and USDt, from the Foundation's Snowflake account | Implemented, tested, and captured on 2026-11-05: 6,253,614 updates from 2021-08-18; the rows stay in the run |
| `af.benchmark-rates-daily` | One Parquet row per UTC day of the Foundation's DTB3 bill rate, with its source label | Implemented, tested, and captured on 2026-11-05: 1,040 days from 2024-01-01, its 710 published days equal to FRED's |
| `derived.aave-wavax-filled` | One Parquet row per UTC day of DefiLlama's Aave v3 WAVAX supply rate, its two gaps filled from Allium's daily mean | Implemented, tested, and derived on 2026-11-05: 1,520 days, 159 of them filled |
| `derived.outside-yields-daily` | One Parquet row per decision day from 2021-02-02 to 2025-11-18 with the AVAX lending composite, the sAVAX yield and the hedged bill rate, each from days before the decision | Implemented, tested, and derived on 2026-11-05: 1,751 days, none on or after the held-back cut |
| `allium.p-chain-atomic-transactions` | One Parquet row per atomic transaction between the C-Chain and the P-Chain, with its C-Chain address, its P-Chain owner addresses and its amount in nAVAX, from the Foundation's Snowflake account | Implemented, tested, and captured on 2026-11-05: 188,830 exports and 198,381 imports from 2021-12-02 to 2026-10-28 |
| `allium.identity-labels-atomic` | One Parquet row per C-Chain address with an atomic transaction to or from the P-Chain that Allium labels, with its entity, category and attribution time | Implemented, tested, and captured on 2026-11-05: 520 of the 51,500 such addresses |
| `af.address-mapping-atomic` | One Parquet row per such address that the Foundation's Gross Chain Product mapping names | Implemented, tested, and captured on 2026-11-05: the same 520 addresses, every row sourced from Allium's labels |
| `derived.stake-owner-types` | One Parquet row per P-Chain address, entity-labelled C-Chain address and direction of the atomic transactions between them, with the label's owner class | Implemented, tested, and derived on 2026-11-05: 1,187 links of 1,061 P-Chain addresses, 111 of them first seen after the held-back cut |
| `allium.c-chain-daily-last-blocks` | One Parquet row per UTC day with its first and last C-Chain block, from the Foundation's Snowflake account | Implemented, tested, and captured on 2026-11-05: 2,214 days from 2020-09-23, every day starting at the height after the previous day's last block |
| `c-chain-rpc.savax-state-daily` | One Parquet row per UTC day from 2022-01-27 with the sAVAX supply, the AVAX it claims and the AVAX one sAVAX redeems for, read from BENQI's contract at the day's last block | Implemented, tested, and captured on 2026-11-05: 1,743 days to 2026-11-04, every block hash equal to Allium's, 351 days held back |
| `etf-issuers.avax-fund-snapshot` | One Parquet row per AVAX exchange-traded product per capture with the issuer's NAV, net assets, shares outstanding, AVAX held, and share staked: BAVA, VAVX, the 21Shares Avalanche product and two baskets holding AVAX, and GAVA from its latest 10-Q | Implemented, tested, and captured daily from 2026-09-28: 7,464,611 AVAX across six funds on the first run |
| `etf-issuers.avax-fund-history` | One Parquet row per fund per valuation date from the histories issuers publish: 21Shares daily since launch, BAVA's daily NAV since 2026-04-14, and GAVA's quarter ends | Implemented, tested, and captured daily from 2026-09-28: 4,619 rows on the first run |

### The 2 November 2026 captures and the ETF rebuild

The daily captures did not run on 2 November 2026 UTC, when the capture host was unreachable, so no run of any daily dataset carries that date. Derived tables are rebuilt from their full inputs in every run, so the runs of 3 November and later cover that day. Four datasets record only the state at the capture instant, and nothing can rebuild them for 2 November: `p-chain-rpc.current-validators`, `data-api.validators-active`, `data-api.avax-supply` and `etf-issuers.avax-fund-snapshot`. Builder Hub's rolling 332-hour uptime window overlaps the missed day, so `derived.validator-uptime-hourly` holds every hour of it.

The ETF snapshots of 31 October to 4 November 2026 were rebuilt on 5 November from their saved issuer responses. The builds had failed because the 21Shares KEYS basket dropped AVAX at its rebalance after 29 October. KEYS holds zero AVAX from then on. The snapshots of 31 October and 1 November report BAVA's published NAV times shares as more than 0.5% off its net assets for 30 October, as the issuer published them.

## From the chain to the model's tables

The model reads two tables: `derived.staking-periods`, one row per validator or delegation staking transaction, and `derived.avax-monetary-daily`, one row per UTC day. Every row in them reaches the model through the same four steps, and every step leaves a receipt. `uv run python scripts/figures/diagrams.py data_path <folder>` draws the whole path from those receipts, with each table's row count and each seam's comparison read from the runs themselves.

**Capture, build, check, derive.** `avalanche data fetch` writes a run's `capture/`: the exact request (for the Snowflake share, the SQL text, its bound parameters, the query ID, role, warehouse, database, and schema; for a node or an API, each request and response), the response bodies, their SHA-256, and the hash of the dataset's catalog contract. `avalanche data build` loads the capture into DuckDB with the declared types and writes `dataset/`: a typed Parquet file and `build.json` with its row count and hash. `avalanche data check` writes `check.json`, `pass` or `attention`, from checks on the same rows: repeated keys, times outside their bounds, amounts outside the protocol's limits, and outputs that do not sum to the declared stake. A derived table's `capture.json` names every input run with its capture ID and Parquet SHA-256, and its check re-hashes every input and rebuilds the table from them. `datasets.load` verifies a table's hash against its build receipt before it returns it, and `avalanche data pin` freezes a set of checked runs for a study or model.

**Two sources for the P-Chain record.** The Avalanche Primary Network data share on Snowflake was the source of the staking history: four datasets, `snowflake.primary-validator-stakes`, `-delegator-stakes`, `-staking-rewards`, and `-staking-supply`, plus the daily burns. The share stopped loading on 2026-09-22, its P-Chain tables ending that morning UTC. We had already built a second source from the chain itself:

1. `p-chain-rpc.blocks` reads every P-Chain block from a public node, from a fixed height to the head, and each day's run extends the previous one. When `api.avax.network` refuses a long walk, it reads from PublicNode's public P-Chain node.
2. Three captures fill in what a block walk cannot see. `data-api.p-chain-staking-transactions` gives the record of each stake that began before the walk and ended unrewarded. `p-chain-rpc.reward-utxos` gives the reward outputs of each closed stake. `p-chain-rpc.current-validators` and `data-api.validators-completed-recent` name the validator of a delegation whose validator began before the walk.
3. From these, `derived.p-chain-validator-stakes`, `-delegator-stakes`, `-staking-rewards`, and `-staking-supply` rebuild the share's four tables with the share's columns, and `derived.p-chain-staking-cycles` adds one row per cycle of an auto-renewed validator.
4. The supply counter is replayed block by block with the protocol's reward formula: each stake adds its potential reward when it starts, and each stake that ends unrewarded removes it. Its starting value is read from no provider. It is the one value whose replay ends exactly on the node's own counter at the walk's last height, found by bisection, because the replay never decreases as the starting value rises.

**The seam.** Each `derived.seamed-*` table keeps the share's rows before one instant and the walk's rows from it on, and a last column, `source`, names which side each row came from. The instant is the same for all four staking tables, so a stake, its supply reading, and its reward never come from different sides. In the runs of 2026-09-30 it is 2026-09-22 07:37:02 UTC. A backup is used only after every row both sources hold before the seam has been compared column by column, and a single difference stops the derive. In those runs 111 validator stakes, 12,498 delegations, 10,199 reward payments, and 12,609 supply readings were compared, and none differed. The daily burn tables seam on a date in the same way.

**The two tables the model reads.** `derived.staking-periods` reads the four seamed tables and the cycles. Each row joins a stake to its reward and its supply reading, assigns the upgrade in force when it was accepted, and records whether the protocol's reward formula reproduces its potential reward. In the run of 2026-09-30 that is 7,131,321 rows, and the formula reproduces 4,455,120 of the 4,455,121 that start on acceptance. `derived.avax-monetary-daily` reads the staking-period log, the seamed rewards, supply, and burns, and the C-Chain burn record. For each UTC day from genesis it gives recognised reward issuance, burns by chain, effective active stake at 23:59:59 UTC, and supply at the open and close. Each close is the open plus issuance less burns. Ordinary rewards keep net payout timing. Auto-renewed cycles recognise current rewards once at the verified cycle event and use each cycle's actual stake weight. Protocol-counter and Data API comparisons remain diagnostic checks with explicit bases and tolerances.

**Every day.** A scheduled job runs the chain in order at 02:30 UTC: the Data API supply snapshot, the P- and X-Chain walks to the head, the Data API block lists and stake records, the reward outputs, the P-Chain tables, the burns, the seamed tables, and then the staking-period log, the node table, the operators, the ledger, the upgrade-period table, and the validator weeks. A step whose check passed that day is skipped, so a run that stopped resumes where it stopped. A separate check each morning reads the newest record of every source and reports any that has stopped.

## Reproduce the Snowpeer summary

Resolve all requests and writes without using the network:

```bash
uv run --locked avalanche data fetch snowpeer.network-summary \
  --output data/runs/snowpeer-example/capture \
  --preview
```

Create an immutable raw capture, build the normalized dataset, and verify both:

```bash
uv run --locked avalanche data fetch snowpeer.network-summary \
  --output data/runs/snowpeer-example/capture

uv run --locked avalanche data build snowpeer.network-summary \
  --from data/runs/snowpeer-example/capture \
  --output data/runs/snowpeer-example/dataset

uv run --locked avalanche data check snowpeer.network-summary \
  --capture data/runs/snowpeer-example/capture \
  --dataset data/runs/snowpeer-example/dataset
```

The capture contains the original response bytes, URLs, timestamps, sizes, and SHA-256 hashes. The build contains a normalized JSON row, a Parquet table, and a receipt that links both outputs to the source capture. Existing output directories are never overwritten.

Generated captures are working data and are not committed by default. A reviewed study may publish a bounded snapshot when its evidence contract requires one.

Every capture receipt carries `contract_sha256`, the hash of the dataset's inputs (its endpoints or queries) and its field list. Documentation in the catalog, such as descriptions, provider notes, and consumer studies, can change without invalidating captures; a change to an input or a field makes earlier captures stale and requires a new one. `avalanche data check --dataset` writes its result to `check.json` beside the build receipt, and `scripts/milestone_pages.py build` renders the Milestone 1.1 and 1.2 pages from the catalog and the latest receipts.

## Reproduce the staking transactions and reward outcomes

The Snowflake share requires authorized credentials. Install the optional connector and describe the connection once in the connector's own configuration file, outside the repository:

```bash
uv sync --locked --extra snowflake
```

```toml
# ~/.snowflake/connections.toml, file mode 600
[avalanche]
account = "<account identifier>"
user = "<user name>"
authenticator = "SNOWFLAKE_JWT"
private_key_file = "/absolute/path/to/rsa_key.p8"
role = "<role>"
warehouse = "<warehouse>"
database = "AVALANCHE_PRIMARY_NETWORK_DATA"
schema = "PRIMARY"
```

Set `AVALANCHE_SNOWFLAKE_CONNECTION` to use a different connection name. The connector's `SNOWFLAKE_HOME` variable relocates the configuration directory. Credentials never enter captures, receipts, or command output.

Resolve the query, parameters, and writes without connecting:

```bash
uv run --locked --extra snowflake avalanche data fetch snowflake.primary-validator-stakes \
  --output data/runs/validator-stakes-example/capture \
  --preview
```

Capture, build, and check. The optional `--param start=YYYY-MM-DD` and `--param end=YYYY-MM-DD` bound the acceptance timestamp as a half-open UTC window. The defaults cover the full history from the 2020-09-10 genesis through the capture day.

```bash
uv run --locked --extra snowflake avalanche data fetch snowflake.primary-validator-stakes \
  --output data/runs/validator-stakes-example/capture \
  --timeout 120

uv run --locked avalanche data build snowflake.primary-validator-stakes \
  --from data/runs/validator-stakes-example/capture \
  --output data/runs/validator-stakes-example/dataset

uv run --locked avalanche data check snowflake.primary-validator-stakes \
  --capture data/runs/validator-stakes-example/capture \
  --dataset data/runs/validator-stakes-example/dataset
```

The capture contains the exact SQL text, bound parameters, Snowflake query ID, session role, warehouse, database, and schema, the compressed result rows, and their SHA-256 hash. The build loads the compressed capture into DuckDB with declared column types and writes a typed Parquet table plus a receipt with row counts, time coverage, and null counts. The checks run as SQL over the same rows, so datasets with millions of rows build and check in seconds. The check verifies hashes, query text, field types, unique transaction hashes, the acceptance window, time ordering, duration bounds of 14 to 365 days, stake bounds of 2,000 to 3,000,000 AVAX, delegation fee bounds of 2% to 100%, and the staked-UTXO reconciliation of each declared stake weight. Rows without a staked UTXO record are counted in the summary rather than reported as findings, because the stake weight comes from the transaction itself.

The delegator dataset follows the same commands with `snowflake.primary-delegator-stakes`. It is about 120 times larger, so its full-history capture takes minutes rather than seconds; use `--timeout 600` and, when a smaller window is enough, the `--param` dates. Each delegation row names the validator staking transaction whose period contains it, and the check reports any delegation that no validator period on its node contains. The funding address is the address behind the largest share of the staked UTXOs, with the number of funding addresses kept alongside it.

The rewards dataset, `snowflake.primary-staking-rewards`, is the same size as the delegator dataset and follows the same commands. Each row is one reward transaction, linked to its staking period through the reward transaction's metadata, with the realized reward summed from reward UTXOs and the difference from the potential reward recorded as the fee transfer: positive for a validator's delegation fee income, negative for a delegator's fee paid. The check confirms the link, the reward timing, agreement between the rewarded flag and the paid amount, and the fee direction for each side. Rewarded periods with no reward UTXO record in the share are counted in the summary rather than reported as findings, like staked UTXOs that are absent from the other two datasets.

The supply dataset, `snowflake.primary-staking-supply`, records for every staking transaction the Primary Network supply after the previous block and after its own block, plus the in-block deltas from earlier staking additions and unrewarded removals. It exists so the protocol reward formula can be backtested against captured potential rewards without a live connection. Its summary reports how often the provider's block supply change differs from the summed staking deltas; the backtest establishes which supply reading the protocol used in each regime.

The P/X burn dataset, `snowflake.primary-burn-events`, uses the same fetch, build, and check commands. Bound a capture with `--param start=YYYY-MM-DD --param end=YYYY-MM-DD`; the dates define a half-open UTC window. A repeated P-Chain transaction hash contributes at most once, preferring the row with a recorded burn. The output keeps transaction time and identity so upgrade-period flow totals can use the exact activation instant. It does not contain C-Chain fees or historical total supply. See the [monetary source audit](monetary-source-audit.md) before using it in a monetary calculation.

Amounts are preserved in nAVAX integers and converted once to AVAX. The delegation fee is preserved in millionths and converted once to a rate. Price observations and outside-option yields are separate datasets that do not exist yet.

## Reproduce the AVAX market observations

The public CoinGecko API needs no credential. It limits historical requests to the trailing 365 days (error code 10012); full history from the 2020 listing requires a paid CoinGecko plan, which this repository does not assume.

```bash
uv run --locked avalanche data fetch coingecko.avax-market-daily \
  --output data/runs/avax-market-example/capture

uv run --locked avalanche data build coingecko.avax-market-daily \
  --from data/runs/avax-market-example/capture \
  --output data/runs/avax-market-example/dataset

uv run --locked avalanche data check coingecko.avax-market-daily \
  --capture data/runs/avax-market-example/capture \
  --dataset data/runs/avax-market-example/dataset
```

The capture preserves the raw response bytes and hash. The build aligns prices, market capitalizations, and volumes on their timestamps, keeps the latest partial-day point flagged, and derives daily log returns and annualized 30-day realized volatility. The check verifies unique observations, one-day spacing, partial-day placement, and the volatility window.

Full price history comes from the DefiLlama coins series, which carries CoinGecko lineage (`coingecko:avalanche-2`) and a per-series confidence value. The endpoint returns at most 500 points per request, so the contract declares five fixed 500-day windows from the 2020-09-22 series start; windows past the capture day return only the points that exist. The CoinGecko dataset then serves as a cross-check of the trailing year:

```bash
uv run --locked avalanche data fetch defillama.avax-price-daily \
  --output data/runs/avax-price-example/capture

uv run --locked avalanche data build defillama.avax-price-daily \
  --from data/runs/avax-price-example/capture \
  --output data/runs/avax-price-example/dataset

uv run --locked avalanche data check coingecko.avax-market-daily \
  --capture data/runs/avax-market-example/capture \
  --dataset data/runs/avax-market-example/dataset \
  --against data/runs/avax-price-example/dataset
```

The Binance archive gives the same history with exact UTC day boundaries: each day's close is the price at the next midnight, so a feature observed at a Monday 00:00 cutoff reads Sunday's close. The archive publishes a SHA-256 beside every file, and the capture refuses a file that differs. The quote is USDT: against Coinbase's AVAX/USD closes on 1,453 days from October 2021 to September 2025 the median difference is 0.05% and the largest 1.22%. The check compares each day's open with CoinGecko's USD price at the same midnight and reports a day only when the price is both beyond 2% of the open and outside the day's range widened by 2%; on the 365 shared days of 2026-09-26 the median difference is 0.09% and no day is reported. DefiLlama's points are stamped at 00:00, 00:01, or 23:59, so its date labels shift by up to a day; aligned by time of day it agrees with Binance at a median of 0.11%.

```bash
uv run --locked avalanche data fetch binance.avax-usdt-daily --output data/runs/binance-avax-example/capture --param end=<first day not captured>
uv run --locked avalanche data build binance.avax-usdt-daily --from data/runs/binance-avax-example/capture --output data/runs/binance-avax-example/dataset
uv run --locked avalanche data check binance.avax-usdt-daily --capture data/runs/binance-avax-example/capture --dataset data/runs/binance-avax-example/dataset --against data/runs/avax-market-example/dataset
```

The cross-check pairs each CoinGecko midnight observation with the DefiLlama observation nearest that day's start when it lies within three hours, reports the median and maximum relative difference and the days it could not align, and raises a finding for any aligned day beyond 10%.

## Reproduce the Bitcoin price and the AVAX funding rates

These four keyless public series give the model a daily Bitcoin price from 2010 and the AVAX perpetual funding rate on two venues. Each capture takes the parameter `end=<first day not captured>`, which defaults to the current UTC day, pauses before every request, and retries a refusal for rate after a growing wait. [Coin Metrics community data](https://docs.coinmetrics.io/packages/coin-metrics-community-data) is licensed under Creative Commons CC BY-NC 4.0, which requires attribution and forbids commercial use. The Binance archive files fall under the [Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md), version 1.0 of 26 August 2026, which license them CC BY-NC-SA 4.0 and exclude commercial licensing. [Bybit's API terms](https://bybit.nl/en/help-center/article/API-Terms) bar commercial exploitation of its APIs. The catalog field `reuse_status` of each source records these terms.

The dataset `coinmetrics.btc-usd-daily` is Coin Metrics' reference rate, the metric `PriceUSD`: the Bitcoin price in US dollars at 24:00 UTC of each day from 18 July 2010. Its check reads the dataset `binance.btc-usdt-daily`, Binance's daily candles for Bitcoin quoted in the Tether dollar (BTC/USDT) from 2017-08-17. Each archive file is checked against the SHA-256 hash Binance publishes beside it. On the shared days from 1 September 2020 at least 99% of prices must lie within 1% of Binance's close, and the daily log returns must correlate at 0.99 or more. The correlation catches a one-day shift that a level band lets pass in calm months. The check also reports the full overlap from 2017. There Binance's early USDT market sits further from the dollar price: 94.7% of the 3,367 days of the 2026-11-05 capture lie within 1%, against 99.4% of the 2,256 tested days.

```bash
uv run --locked avalanche data fetch binance.btc-usdt-daily --output data/runs/binance-btc-example/capture --param end=<first day not captured>
uv run --locked avalanche data build binance.btc-usdt-daily --from data/runs/binance-btc-example/capture --output data/runs/binance-btc-example/dataset
uv run --locked avalanche data check binance.btc-usdt-daily --capture data/runs/binance-btc-example/capture --dataset data/runs/binance-btc-example/dataset

uv run --locked avalanche data fetch coinmetrics.btc-usd-daily --output data/runs/coinmetrics-btc-example/capture --param end=<first day not captured>
uv run --locked avalanche data build coinmetrics.btc-usd-daily --from data/runs/coinmetrics-btc-example/capture --output data/runs/coinmetrics-btc-example/dataset
uv run --locked avalanche data check coinmetrics.btc-usd-daily --capture data/runs/coinmetrics-btc-example/capture --dataset data/runs/coinmetrics-btc-example/dataset --against data/runs/binance-btc-example/dataset
```

The dataset `binance.avax-usdt-perp-funding` holds every funding event of Binance's AVAXUSDT perpetual contract since its listing on 2020-09-22 16:00 UTC, one every 8 hours. The capture takes the futures API to the window's end and every closed month's archive file with its CHECKSUM. The archive is the record each API rate must equal. The build refuses a capture in which an archived rate is missing from the API or differs from it. It also refuses an API rate that an archived month omits, and two events that are not 8 hours apart. The newest month may not be published yet in a month's first days. Its rates then carry false in the column `in_archive`. The dataset `bybit.avax-usdt-perp-funding` holds the same events on Bybit since the contract's launch on 2021-09-15. Its check reads the Binance run and requires Bybit's 30-day mean within 5 percentage points a year of Binance's on at least 80% of the days both have one.

Both tables give one row per event. The column `funding_rate_per_8h` is the fraction of position value longs pay shorts at the event. The column `annualised_pct_per_year` is that rate times 3 times 365 times 100. Each row also carries its UTC day's event count, the day's mean rate in percent a year, and the mean of the 30 daily figures ending that day. The day's mean in percent a year equals the day's summed rates times 365 times 100 when the day holds all three events.

```bash
uv run --locked avalanche data fetch binance.avax-usdt-perp-funding --output data/runs/binance-funding-example/capture --param end=<first day not captured>
uv run --locked avalanche data build binance.avax-usdt-perp-funding --from data/runs/binance-funding-example/capture --output data/runs/binance-funding-example/dataset
uv run --locked avalanche data check binance.avax-usdt-perp-funding --capture data/runs/binance-funding-example/capture --dataset data/runs/binance-funding-example/dataset

uv run --locked avalanche data fetch bybit.avax-usdt-perp-funding --output data/runs/bybit-funding-example/capture --param end=<first day not captured>
uv run --locked avalanche data build bybit.avax-usdt-perp-funding --from data/runs/bybit-funding-example/capture --output data/runs/bybit-funding-example/dataset
uv run --locked avalanche data check bybit.avax-usdt-perp-funding --capture data/runs/bybit-funding-example/capture --dataset data/runs/bybit-funding-example/dataset --against data/runs/binance-funding-example/dataset
```

In the captures of 2026-11-05, all 6,691 archived Binance rates in 74 monthly files equal the API's, and the API holds 12 later rates. Bybit's 30-day mean lies within 5 points a year of Binance's on 82.2% of 1,848 days, with a median gap of 2.24 points. The pin [`d25-public-series-2026-11-05.json`](pins/d25-public-series-2026-11-05.json) names the four runs.

## Reproduce the daily market vector

The dataset `derived.market-daily-vector` gives the model one row per UTC day of market inputs, from 2021-02-02 to 2025-11-18, the day before the held-back cut of 19 November 2025. Each row holds the AVAX close at 24:00 UTC and its log return, the realised variance of the day, the Bitcoin close and log return at the same instant, and the natural log of the day's C-Chain gas burn in AVAX. The realised variance is the sum of squared hourly log returns within the day ([Corsi 2009](https://doi.org/10.1093/jjfinec/nbp001)), over the hours from 01:00 to 24:00 UTC. A return counts only when both of its hours are priced and come from the same table, and the field `hourly_returns` records how many were summed. Lending-rate and outside-yield columns are planned to follow these fields and are not built yet.

Three inputs come from the Avalanche Foundation's Snowflake account, read-only, under the Foundation's agreement, through a named connection. The catalog source `af-foundation-snowflake` describes it. Describe the connection once in the connector's configuration file, outside the repository, as for the share above:

```toml
# ~/.snowflake/connections.toml, file mode 600
[foundation]
account = "<account identifier>"
user = "<user name>"
authenticator = "SNOWFLAKE_JWT"
private_key_file = "/absolute/path/to/rsa_key.p8"
role = "<read-only role>"
warehouse = "<warehouse>"
```

Set `AVALANCHE_FOUNDATION_SNOWFLAKE_CONNECTION` to use a different connection name. Credentials never enter captures, receipts or command output. Each capture holds every row of its table in the window, held-back dates included, and records the SQL text, the bound window, the Snowflake query ID and the role, warehouse, database and schema the session reports.

1. `allium.prices-hourly` is Allium's hourly price service for native AVAX, WAVAX, sAVAX, ggAVAX and yyAVAX from 2022-06-01 01:00 UTC. A price holds at the instant of its stamp: the price stamped at a midnight agrees with Binance's AVAX/USDT daily open of that midnight to a median 0.12%. The check requires native AVAX and WAVAX within 2% of each other in at least 98% of the hours both are priced. In the 2026-11-05 capture 99.0% of 38,844 hours are, the median difference is 0.08%, and isolated single-hour spikes reach 62%. Missing hours are counted per token in the summary: none for AVAX, 2 for WAVAX.
2. `allium.dex-token-prices-hourly` is Allium's WAVAX price from decentralised exchange trades, from 2021-02-02 15:00 UTC, the only hourly AVAX price before the service starts. An hour without trades has no row, 128 hours in all. Its check, with `--against` a built `allium.prices-hourly` run, requires each day's last exchange price within 3% of the service's WAVAX price at the same hour on at least 95% of the days both hold. On 2026-11-05 99.1% of 1,619 days were.
3. `af.economy-gas-fees-daily` is the Foundation's daily count of C-Chain gas fees in its Gross Chain Product economy. Every C-Chain fee is burned, so its AVAX column is a burn, but the economy's scope is narrower than the chain: its total is about 13% below Allium's daily fee table, a gap not yet traced. The exact receipt-fee burn `snowflake.c-chain-evm-burn-daily` stays the whole-chain reference.

```bash
uv sync --locked --extra snowflake
uv run --locked --extra snowflake avalanche data fetch allium.prices-hourly --output data/runs/prices-hourly-example/capture --timeout 600
uv run --locked avalanche data build allium.prices-hourly --from data/runs/prices-hourly-example/capture --output data/runs/prices-hourly-example/dataset
uv run --locked avalanche data check allium.prices-hourly --capture data/runs/prices-hourly-example/capture --dataset data/runs/prices-hourly-example/dataset

uv run --locked --extra snowflake avalanche data fetch allium.dex-token-prices-hourly --output data/runs/dex-prices-example/capture --timeout 600
uv run --locked avalanche data build allium.dex-token-prices-hourly --from data/runs/dex-prices-example/capture --output data/runs/dex-prices-example/dataset
uv run --locked avalanche data check allium.dex-token-prices-hourly --capture data/runs/dex-prices-example/capture --dataset data/runs/dex-prices-example/dataset --against data/runs/prices-hourly-example/dataset

uv run --locked --extra snowflake avalanche data fetch af.economy-gas-fees-daily --output data/runs/gas-fees-example/capture --timeout 600
uv run --locked avalanche data build af.economy-gas-fees-daily --from data/runs/gas-fees-example/capture --output data/runs/gas-fees-example/dataset
uv run --locked avalanche data check af.economy-gas-fees-daily --capture data/runs/gas-fees-example/capture --dataset data/runs/gas-fees-example/dataset

uv run --locked avalanche data derive derived.market-daily-vector --output data/runs/market-daily-vector-example \
  --input coinmetrics.btc-usd-daily=<Coin Metrics run> --input defillama.avax-price-daily=<DefiLlama run>
uv run --locked avalanche data check derived.market-daily-vector --capture data/runs/market-daily-vector-example/capture --dataset data/runs/market-daily-vector-example/dataset
```

From 2022-06-01 01:00 UTC each hour takes the service's native AVAX price, or its WAVAX price when the native row is missing, and earlier hours take the exchange price. The field `price_source` names the table of each day's close. AVAX has no hourly price before 2021-02-02, so the table starts there. The exchange price is smoother than the service's. On the 1,255 days both tables price completely, the exchange table's realised variance is a median 0.76 of the service's, so the change of table lowers the realised variance before 2022-06-01. The field `dex_realised_variance` gives the exchange table's figure on every day it covers, one table across the change. The field `max_abs_hourly_return` shows a single-hour spike in the source, which the realised variance keeps. The Bitcoin close is Coin Metrics' reference rate of the same date, which holds at 24:00 UTC, the instant of the AVAX close.

The check rebuilds the table from its recorded input runs. It then rebuilds it from the same inputs cut at 2025-11-19 00:00 UTC, the close of 18 November, and requires the same rows, so nothing observed later enters. It also compares each close with DefiLlama's daily AVAX price nearest the same midnight, a recorded input that no field reads. Two price services differ by venue and by the minute of the mark, so the thresholds allow a band. They were set after reading the 2026-11-05 data. On service days at least 95% of closes must lie within 2% and none beyond 10%. On exchange days, which carry pool noise, at least 90% must lie within 2%. The daily log returns must correlate at 0.97 or more. In the 2026-11-05 run 97.2% of 1,264 service closes lie within 1% and 99.7% within 2%, the largest gap 4.4%. Of 481 exchange closes 83.6% lie within 1% and 94.4% within 2%, and two exceed 10%, on 2021-05-09 and 2022-01-22. The returns correlate at 0.984. The pin [`v0.9.1-daily-vector-2026-11-05.json`](pins/v0.9.1-daily-vector-2026-11-05.json) names the five runs.

## Reproduce the outside yields

The dataset `derived.outside-yields-daily` gives the three yields a staker can compare the reward with, one row per decision day from 2021-02-02 to 2025-11-18, in percent a year. A row is dated by the day of the decision, and every value in it comes from complete UTC days before that day. The raw value is that of the day before, which ends at 24:00 UTC. The 7-day median is the median of the 7 days before, kept when at least 4 of them have a value, and the fields ending in `_days_7d` count them. No row is dated on or after the held-back cut of 19 November 2025. The check rebuilds the table from its inputs cut at 2025-11-19 00:00 UTC and requires the same rows.

1. The AVAX lending composite averages the supply rate of the Avalanche lending markets for AVAX and WAVAX, weighted by the amount supplied. Each market that recorded a supply rate on the day gives the mean of its rate updates that day, weighted by its supplied AVAX at its last update of the day. Allium's table has no supply rate for the Compound v2 forks, BENQI among them, so they are left out, and the field `lending_unrated_supplied_avax` reports their supplied AVAX. In the 2026-11-05 run the rated markets hold a median 67% of the AVAX supplied, and Aave v3 holds most of it. A day with no rated update takes the filled Aave v3 WAVAX rate below, which no day of the run needed.
2. The liquid staking yield is the growth of the sAVAX exchange rate over 30 days, as a rate a year. The rate is Allium's sAVAX price over its AVAX price, both stamped at 24:00 UTC. The growth is `((R(x) / R(x-30)) ** (365 / 30) - 1) * 100`, and the series starts on 2022-07-02.
3. The hedged bill rate is the 3-month bill rate less the AVAX perpetual funding rate, the dollar yield of holding bills while short AVAX perpetuals. The bill rate is DTB3 from `af.benchmark-rates-daily` times 100 on its published and carried-forward days. Before 2024, and on 2024-01-01, which that table fills back from 2 January, it is FRED's last published value on or before the day, from `fred.tbill-3m-daily`. The field `bill_source` records which. The funding rate is Binance's mean AVAXUSDT funding rate per 8-hour event on the UTC date times 3 times 365 times 100. That equals the day's summed rate times 365 times 100 when the day holds all three events, as every day of the run does.

Two inputs come from the Foundation's Snowflake account through the named connection described above. `allium.lending-interest-rates` holds every lending rate update for WAVAX, AVAX, sAVAX, USDC and USDt. The per-update rows stay in the run and are not redistributed. `af.benchmark-rates-daily` holds the Foundation's DTB3. Its check, with `--against` a built `fred.tbill-3m-daily` run, requires every day the table marks as FRED's own value to equal FRED's. On 2026-11-05 all 710 such days did.

The dataset `derived.aave-wavax-filled` fills the two gaps in DefiLlama's daily Aave v3 WAVAX rate, the series `aave-wavax` of `derived.opportunity-costs-daily`. The gaps run from 2024-01-04 to 2024-01-10 and from 2024-10-09 to 2025-03-09. Each of their 159 days takes the mean of the day's Allium supply rate updates for protocol `aave_v3` and token WAVAX. Every DefiLlama value is kept, and the field `source` names each row's table. On the 60 days both cover, 1 September to 8 October 2024 and 10 to 31 March 2025, Allium's mean exceeds DefiLlama's by 0.015 points on average. The mean absolute difference is 0.037 points, the median 0.012, the largest 0.50 points on 2025-03-21, and the correlation 0.989. The check requires a mean absolute difference of at most 0.10 points and a correlation of at least 0.95. Over all 1,361 days both cover they agree less well: DefiLlama's value sits a mean 1.6 points above Allium's in 2022 and 0.4 points in 2023, and from 2024 the two agree within 0.03 points on average. The derived capture records the lending run's Snowflake query ID and the hash of its query text.

```bash
uv run --locked --extra snowflake avalanche data fetch allium.lending-interest-rates --output data/runs/lending-example/capture --timeout 600
uv run --locked avalanche data build allium.lending-interest-rates --from data/runs/lending-example/capture --output data/runs/lending-example/dataset
uv run --locked avalanche data check allium.lending-interest-rates --capture data/runs/lending-example/capture --dataset data/runs/lending-example/dataset

uv run --locked --extra snowflake avalanche data fetch af.benchmark-rates-daily --output data/runs/benchmark-example/capture --timeout 600
uv run --locked avalanche data build af.benchmark-rates-daily --from data/runs/benchmark-example/capture --output data/runs/benchmark-example/dataset
uv run --locked avalanche data check af.benchmark-rates-daily --capture data/runs/benchmark-example/capture --dataset data/runs/benchmark-example/dataset --against data/runs/<FRED bill run>/dataset

uv run --locked avalanche data derive derived.aave-wavax-filled --output data/runs/aave-wavax-filled-example \
  --input derived.opportunity-costs-daily=<opportunity-cost run> --input allium.lending-interest-rates=lending-example
uv run --locked avalanche data check derived.aave-wavax-filled --capture data/runs/aave-wavax-filled-example/capture --dataset data/runs/aave-wavax-filled-example/dataset

uv run --locked avalanche data derive derived.outside-yields-daily --output data/runs/outside-yields-example \
  --input allium.lending-interest-rates=lending-example --input derived.aave-wavax-filled=aave-wavax-filled-example
uv run --locked avalanche data check derived.outside-yields-daily --capture data/runs/outside-yields-example/capture --dataset data/runs/outside-yields-example/dataset
```

Both derived builds run DuckDB on one thread, so every floating-point sum adds in the same order and a rebuild gives the same bits. The pin [`v0.9.1-outside-yields-2026-11-05.json`](pins/v0.9.1-outside-yields-2026-11-05.json) names the four runs of this section and the four runs they read: the hourly prices, the FRED bill rate, the Binance funding rates and the opportunity costs.

## Reproduce the current validator snapshot

The public P-Chain RPC needs no credential. The capture posts `platform.getCurrentValidators` and preserves the JSON-RPC response; the receipt records the request body. Uptime is the answering node's current observation of each validator, so the dataset is a dated snapshot and does not supply an uptime history.

```bash
uv run --locked avalanche data fetch p-chain-rpc.current-validators \
  --output data/runs/current-validators-example/capture

uv run --locked avalanche data build p-chain-rpc.current-validators \
  --from data/runs/current-validators-example/capture \
  --output data/runs/current-validators-example/dataset

uv run --locked avalanche data check p-chain-rpc.current-validators \
  --capture data/runs/current-validators-example/capture \
  --dataset data/runs/current-validators-example/dataset \
  --against data/runs/validator-stakes-example/dataset
```

With `--against`, the check reconciles every snapshot validator against the Snowflake validator dataset by staking transaction hash and reports validators absent from the reference despite starting before its last row, and matched validators whose node, period, stake, or fee differ.

## Reproduce the outside-option inputs

Two keyless datasets supply the comparison inputs the opportunity-cost design needs. Neither ranks or compares; the study notebook owns that.

```bash
uv run --locked avalanche data fetch defillama.pool-yields --output data/runs/pool-yields-example/capture
uv run --locked avalanche data build defillama.pool-yields --from data/runs/pool-yields-example/capture --output data/runs/pool-yields-example/dataset
uv run --locked avalanche data check defillama.pool-yields --capture data/runs/pool-yields-example/capture --dataset data/runs/pool-yields-example/dataset

uv run --locked avalanche data fetch us-treasury.par-yield-daily --output data/runs/treasury-example/capture
uv run --locked avalanche data build us-treasury.par-yield-daily --from data/runs/treasury-example/capture --output data/runs/treasury-example/dataset
uv run --locked avalanche data check us-treasury.par-yield-daily --capture data/runs/treasury-example/capture --dataset data/runs/treasury-example/dataset
```

The pool dataset keeps every Avalanche pool and every pool of a declared proof-of-stake staking project on any chain, with the observation time, yields, TVL as the liquidity proxy, and DefiLlama's risk descriptors. Horizon, fee, and lockup are present as null columns because DefiLlama does not report them; the study declares them per comparison. The Treasury dataset preserves one XML feed per year and yields one long row per business day and tenor in fractional rates.

## Reproduce the Metrics API series

The Metrics API is keyless and pages at 2,160 points, so each series is declared as fixed two-year windows. The staking dataset reconciles against the Snowflake validator and delegator datasets: the check rebuilds the end-of-day active counts and weights from period starts and ends and reports the median relative difference overall and by year, and the days beyond 2%. On the 2026-09-19 capture the API sat within about 1% of the rebuilt validator set through 2023 and 3% to 8% below it from 2025, with nine missing days in late 2025; the source record carries the by-year figures.

```bash
uv run --locked avalanche data fetch metrics-api.primary-staking-daily --output data/runs/staking-metrics-example/capture
uv run --locked avalanche data build metrics-api.primary-staking-daily --from data/runs/staking-metrics-example/capture --output data/runs/staking-metrics-example/dataset
uv run --locked avalanche data check metrics-api.primary-staking-daily \
  --capture data/runs/staking-metrics-example/capture --dataset data/runs/staking-metrics-example/dataset \
  --against data/runs/validator-stakes-example/dataset --against data/runs/delegator-stakes-example/dataset
```

The C-Chain activity dataset follows the same commands with `metrics-api.c-chain-activity-daily`. The API serves no P-Chain chain metrics; P-Chain fees and burn stay with the Snowflake transaction columns. Units for fees and gas price are not documented by the API and are recorded as served.

## Reproduce the AVAX supply snapshot

The Data API's supply endpoint answers keyless requests and returns only the current state, so this dataset is one row per capture; historical realized supply needs a reconciled reward-and-burn replay. The check verifies the API's own identity, total supply equals genesis unlock plus cumulative rewards minus the three burn totals, and with `--against` reports the gap to the Snowflake protocol supply counter, which runs ahead of minted rewards by the potential rewards of periods still in progress.

```bash
uv run --locked avalanche data fetch data-api.avax-supply --output data/runs/avax-supply-example/capture
uv run --locked avalanche data build data-api.avax-supply --from data/runs/avax-supply-example/capture --output data/runs/avax-supply-example/dataset
uv run --locked avalanche data check data-api.avax-supply --capture data/runs/avax-supply-example/capture --dataset data/runs/avax-supply-example/dataset --against data/runs/staking-supply-example/dataset
```

## Capture the Data API validator sets

The Data API's validators endpoint is followed through its `nextPageToken`, 100 rows a page, each page one line of the raw file as it arrives, so a long pull shows its progress on disk and a dropped page is retried before the capture fails. Both datasets filter to the Primary Network. The active set carries uptime as Ava Labs' indexer observes it, which is a second observer beside the RPC snapshot's answering node. The completed history carries every finished validation's reward addresses, but its reward is the potential reward whether or not the validation passed, and its delegated amount and delegator count sum every delegation over the period rather than a concurrent weight. Pass or fail and concurrent weight stay with the Snowflake captures.

```bash
uv run --locked avalanche data fetch data-api.validators-active --output data/runs/validators-active-example/capture
uv run --locked avalanche data build data-api.validators-active --from data/runs/validators-active-example/capture --output data/runs/validators-active-example/dataset
uv run --locked avalanche data check data-api.validators-active --capture data/runs/validators-active-example/capture --dataset data/runs/validators-active-example/dataset --against data/runs/current-validators-example/dataset
uv run --locked avalanche data fetch data-api.validators-completed --output data/runs/validators-completed-example/capture --timeout 120
uv run --locked avalanche data build data-api.validators-completed --from data/runs/validators-completed-example/capture --output data/runs/validators-completed-example/dataset
uv run --locked avalanche data check data-api.validators-completed --capture data/runs/validators-completed-example/capture --dataset data/runs/validators-completed-example/dataset --against data/runs/validator-stakes-example/dataset
```

A daily sweep follows the same commands with `data-api.validators-completed-recent`, which walks only the first 15 pages, and its check takes `--against` the full history's dataset directory.

## Capture Builder Hub's hourly validator uptime

The protocol keeps no uptime percentages: each node measures its peers privately and deletes the record when a validation ends, and the P-Chain records only whether a staking period was rewarded. Builder Hub serves, for each current validator, the hourly median uptime across Ava Labs' observing nodes for the last 332 hours, and the window moves forward every hour. A capture takes the list and one detail per node, and asks again for nodes the previous capture listed that have since ended. An interrupted capture keeps its lines in `.<output>.partial` and the next capture into the same output resumes from them. Check each capture against the previous one: `BC5` fails when an hour falls between the two, which means history was lost.

```bash
uv run --locked avalanche data fetch builder-hub.validator-uptime --output data/runs/builder-hub-uptime-example/capture --timeout 60
uv run --locked avalanche data build builder-hub.validator-uptime --from data/runs/builder-hub-uptime-example/capture --output data/runs/builder-hub-uptime-example/dataset
uv run --locked avalanche data check builder-hub.validator-uptime --capture data/runs/builder-hub-uptime-example/capture --dataset data/runs/builder-hub-uptime-example/dataset --against data/runs/builder-hub-uptime-previous/dataset
uv run --locked avalanche data derive derived.validator-uptime-hourly --output data/runs/validator-uptime-hourly-example
uv run --locked avalanche data check derived.validator-uptime-hourly --capture data/runs/validator-uptime-hourly-example/capture --dataset data/runs/validator-uptime-hourly-example/dataset
```

The derived table reads every built capture, keeps the newest capture's value for each hour, and counts how many captures held it. Captures one day apart overlap by about thirteen days, so a missed day loses nothing.

The active check verifies every RPC node is present, the two observers' uptimes differ by a median under one point, and delegated weight agrees per node on at least 85% and in total within 2%. The completed check verifies the first reward address, stake, and potential reward equal the Snowflake validator capture on every validation in both, and when the delegator capture sits in the same `--against` directory, that cumulative delegation and delegation count equal its sum and count. The sweep's check verifies that every validation shared with the full history reads the same and that the sweep spans at least 30 days of end times. The full completed history is about 570 pages and 35 minutes keyless.

## Derive the staking-period log

`derived.staking-periods` is not fetched. It is built from the newest built runs of the four Snowflake staking datasets (or from runs pinned with `--input`): validator and delegator stakes are unioned into one row per staking period, joined to the reward transaction that closed the period and to the supply reading before the period's block, labelled with the network upgrade regime at acceptance, and given the reward the protocol kernel computes for the row. The capture receipt names the input runs and their hashes, so the run is reproducible from those inputs alone.

```bash
uv run --locked avalanche data derive derived.staking-periods --output data/runs/staking-periods-example
uv run --locked avalanche data check derived.staking-periods --capture data/runs/staking-periods-example/capture --dataset data/runs/staking-periods-example/dataset
```

The check verifies the input runs still hash as recorded, the catalog contract and the upgrade schedule are unchanged, every staking transaction appears once, every row with a supply reading has a kernel reward, and the kernel reproduces at least 99.9% of the periods that start at acceptance. The build summary also reports the pending-start reproduction share, rows without a supply reading, and periods that ended before the reward capture without a reward row; those are gaps to explain, not failures.

## Derive the node table

`derived.node-table` folds the staking-period log into one row per validator node. Every column is defined once here and named in the catalog after the glossary term it realises: `span_days` is first stake to last end with gaps included, `tenure_days` is days actually staked with gaps excluded, `current_streak_days` is the latest unbroken run, and `stake_days_avax` is the sum of stake times days. Clocks are clipped at the validator capture time recorded as `as_of`, so a node still validating then is right-censored and `active` says so. `operator_group` is the latest reward address, a proxy for the operator and never proof of one decision maker. The check verifies one row per node, that every node has a reward address, that tenure never exceeds span and the current streak never exceeds tenure, and that periods and realised rewards reconcile to the period log.

```bash
uv run --locked avalanche data derive derived.node-table --output data/runs/node-table-example
uv run --locked avalanche data check derived.node-table --capture data/runs/node-table-example/capture --dataset data/runs/node-table-example/dataset
```

On the 2026-09-22 runs this builds 7,644 rows in about two seconds and loads as the `node_table` view.

## Track validation commitments after Helicon

`derived.helicon-commitments` follows the validator duration choices Helicon opened on 2026-09-22 15:00 UTC, when the minimum validator duration fell from 14 days to 48 hours and auto-renewal began. It has one row per validation cycle that started at or after activation. A cycle is a distinct transaction hash and start time, because an auto-renewed validation keeps its hash while its start and end move forward. For that reason the derive reads every built run of `p-chain-rpc.current-validators` under the current catalog contract, not only the newest, and records each run as its own input in the capture receipt with its run name and hash. The staking-period log is the one pinnable input and gives each node's history before Helicon, together with snapshot cycles the log does not yet hold.

Each row carries the cycle's duration and bin, its stake and fee from the first snapshot that shows it, and its number within the transaction. A node is `returning` when it has a validator period that started before activation and `new` otherwise. `previous_duration_days` is the node's latest validator period that started before the cycle, which for a renewal is the cycle before it. A cycle is `lowered` when it is more than one day shorter than that period. The bins run from the 48-hour minimum to 7, 14, 30, 90, 180, and 365 days, and each includes its lower bound. The build summary counts cycles, nodes, new and returning nodes, lowered and raised cycles, auto-renewed transactions, and cycles and transactions by bin, beside the same bins for the validator periods started in the 30 days before activation.

```bash
uv run --locked avalanche data derive derived.helicon-commitments --output data/runs/helicon-commitments-example
uv run --locked avalanche data check derived.helicon-commitments --capture data/runs/helicon-commitments-example/capture --dataset data/runs/helicon-commitments-example/dataset
```

The check verifies the input runs still hash as recorded, one row per cycle, that every cycle starts at or after activation and lasts at least 48 hours, and that every renewal starts where the transaction's previous cycle ended with the next cycle number. It then rebuilds the table from the recorded inputs and requires the same rows. A cycle is seen only if a snapshot falls inside it, so the summary reports the longest wait between snapshots since activation. Above 48 hours a minimum-length cycle can pass unseen. The daily validator capture derives and checks a new run after each snapshot. On the 2026-09-28 run it builds 73 cycles from nine snapshots in a few seconds.

## Group nodes by operator and fleet

`derived.operators` gives every validator node two groupings, so validator types are fitted on operators, not machines. `operator_id` is the node's latest reward address, the node table's operator proxy: a shared address links nodes, but it does not prove one decision maker. `fleet_id` joins nodes that entered in the same UTC week, left in the same UTC week, and carry the same latest fee. Named agents are flagged with the evidence for each label: GoGoPool and BENQI by Snowpeer's liquid staking provider list, and two unnamed addresses from the protocol mechanism catalog's August 2025 exits.

```bash
uv run --locked avalanche data derive derived.operators --output data/runs/operators-example
uv run --locked avalanche data check derived.operators --capture data/runs/operators-example/capture --dataset data/runs/operators-example/dataset
```

The check requires every node of the node table assigned exactly once, with an operator and a fleet, then rebuilds the table from the recorded input. On the 2026-09-29 run, 7,644 nodes fall into 3,963 operators and 4,247 fleets. GoGoPool's address was the reward address of 1,942 nodes, one of them still active. The fleet rule is fragile: widening its week to two weeks changes the fleet size of 2,914 nodes, so the operator is the grouping to fit on and the fleet a cross-check.

## Group staking periods by owner before the held-back cut

A renewal draw fitted per operator needs an operator label on every staking period that uses nothing from the held-back window, which starts on 19 November 2025 at 00:00 UTC. The dataset `derived.operator-clusters` gives each validator staking period four such labels. Every label is an inference: a shared address links nodes and never proves one decision maker, and the addresses are pseudonymous.

1. The `reward_address` field is the period's own reward address.
2. The `owner_key` field is the reward address, except for periods paid to the pool address of GoGoPool, a liquid staking protocol that has closed. That address paid 1,961 nodes of many node operators, so its periods take the owner of the node's minipool record. Its periods with no usable record share one key, the pool address followed by `/pool`. The pool address is found in the data as the reward address holding most periods of the nodes that have a minipool record.
3. The `cohort_key` field joins the week and the delegation fee of the node's first accepted period. Weeks start on Mondays counted from 2020-09-07, as in the dataset `derived.operators`.
4. The `component_id` field names a connected component of the graph linking each node to the owner keys of its periods accepted before the cut. A period accepted on or after the cut has no component.

The minipool records come from the dataset `c-chain-rpc.minipool-records`, which reads the MinipoolManager contract `0xc300Bc9B4b690BA7A182126299a0618eCe268Ee7` from the public C-Chain node with no key. A capture calls the view function `getMinipoolCount()` and then the view function `getMinipool(int256)` for every index, all at one block, in batches of 25 calls with a one-second pause, about 70 requests in all. The contract keeps one record per node ID with its latest owner, and nodes the protocol funded from its pool alone have no record.

```bash
uv run --locked avalanche data fetch c-chain-rpc.minipool-records --output data/runs/minipool-records-example/capture
uv run --locked avalanche data build c-chain-rpc.minipool-records --from data/runs/minipool-records-example/capture --output data/runs/minipool-records-example/dataset
uv run --locked avalanche data check c-chain-rpc.minipool-records --capture data/runs/minipool-records-example/capture --dataset data/runs/minipool-records-example/dataset
uv run --locked avalanche data derive derived.operator-clusters --output data/runs/operator-clusters-example
uv run --locked avalanche data check derived.operator-clusters --capture data/runs/operator-clusters-example/capture --dataset data/runs/operator-clusters-example/dataset
```

A fetch reads the node's newest block unless `--param block=<height>` names one. The record check requires every index read once at the capture's block and one multisig across the records. The cluster check rebuilds the table from its recorded inputs. It then rebuilds the table from the same inputs cut at the held-back date and requires every row accepted before the cut to come out the same. A minipool record labels a period before the cut only when the record's latest start, the later of its creation and its first cycle start, is before the cut. On the 2026-11-05 run that rule moves 738 periods of 38 minipool nodes into the pool block, because those nodes' records were re-created after the cut. The owner of a record applies to the node's pool-address periods from before the record's latest start too, and the `owner_basis` field marks those periods as carried back. That carry-back assumes a node re-created as a minipool kept its owner. The records cannot show this, because the contract overwrites a node's earlier record when it is re-created. A fit or score dated at an origin before the cut therefore builds its labels from records whose latest start is before that origin, or gives carried-back periods the pool key.

## Link labels to stake

Labels name C-Chain addresses, and stake lives on the P-Chain. AVAX moves between the two by atomic transactions: an export from the C-Chain names its C-Chain sender and the owner addresses of its P-Chain outputs, and an import names its P-Chain sender and C-Chain recipient. The dataset `derived.stake-owner-types` links each P-Chain address to every entity-labelled C-Chain address that paid it by an export or that it paid by an import. A validator's reward addresses, or a delegation's funding address, that appear there take the label's owner class. The class groups Allium's category into exchange, custodian, financial service, decentralised finance, MEV bot, wallet software and other. Wallet software, such as MetaMask user, is Allium's heuristic on how an address behaves. It names the software an address uses, not its owner.

Three datasets come from the Foundation's Snowflake account through the named connection described above. `allium.p-chain-atomic-transactions` holds every atomic transaction between the two chains. Allium writes an export's owner addresses in two forms, and its raw amount in nAVAX on some rows and in wei on 129,609 others. The build reads both forms and takes the unit that matches Allium's AVAX amount. `allium.identity-labels-atomic` and `af.address-mapping-atomic` hold the labels of the C-Chain addresses those transactions touch: 520 of 51,500. Of the 520, 92 are exchanges, 1 a custodian, 5 payment or financial services, 77 MEV bots and 345 wallet software. The Foundation's mapping of these addresses is sourced from Allium's labels, so it confirms nothing on its own. The two name the same entity for every address except the 345 wallet-software rows, where Allium adds the word user.

Counts, amounts and last times read only transactions before the held-back cut of 2025-11-19 00:00 UTC. A link first seen on or after the cut is kept, with `held_back` true and zero counts. The check rebuilds the table from its recorded inputs, and again from the atomic transactions cut at the held-back instant, and requires the same rows before the cut. The labels are one current snapshot, with Allium's attribution time in `label_attributed_at`. A score dated at an origin uses the links whose `first_at` is before that origin, and may also require the attribution to be. Addresses stay in model tables. A client figure, table or text reports linked stake as counts and shares by class, never an address, and nothing joins an address to any identity outside the chain.

At the origin of 2025-11-18 00:00 UTC the link covers little stake. Of 158.9 million AVAX of validator stake active then, 0.64 million AVAX, 0.40%, has a reward address linked to an exchange before the origin, and 1.67 million AVAX, 1.05%, to wallet software. Of 41.6 million AVAX of active delegations, 0.05% has its funding address linked to an exchange and 0.76% to wallet software. When the label's attribution must also precede the origin, no active stake is linked to an exchange. The summary of the build reports both readings by class.

```bash
for id in allium.p-chain-atomic-transactions allium.identity-labels-atomic af.address-mapping-atomic; do
  run=data/runs/${id//./-}-example
  uv run --locked --extra snowflake avalanche data fetch $id --output $run/capture --timeout 600
  uv run --locked avalanche data build $id --from $run/capture --output $run/dataset
  uv run --locked avalanche data check $id --capture $run/capture --dataset $run/dataset
done
uv run --locked avalanche data derive derived.stake-owner-types --output data/runs/stake-owner-types-example \
  --input allium.p-chain-atomic-transactions=allium-p-chain-atomic-transactions-example \
  --input allium.identity-labels-atomic=allium-identity-labels-atomic-example \
  --input af.address-mapping-atomic=af-address-mapping-atomic-example \
  --input derived.seamed-validator-stakes=<seamed validator run> --input derived.seamed-delegator-stakes=<seamed delegator run>
uv run --locked avalanche data check derived.stake-owner-types --capture data/runs/stake-owner-types-example/capture --dataset data/runs/stake-owner-types-example/dataset
```

The pin [`v0.10-label-link-2026-11-05.json`](pins/v0.10-label-link-2026-11-05.json) names the four runs of this section and the two seamed stake runs they read.

## Read the sAVAX supply and exchange rate

sAVAX is the share token of BENQI's liquid staking contract `0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be`. A deposit of AVAX mints shares, and a redemption burns them without a transfer to the zero address. Summing the token's transfers therefore does not give its supply. Allium's transfer table holds 46.8 million sAVAX of mints and no burns, against a supply of 18.7 million on 2026-11-05. The dataset `c-chain-rpc.savax-state-daily` reads the contract's own state instead, at the last C-Chain block of each UTC day: `totalSupply()`, `totalPooledAvax()` and `getPooledAvaxByShares(10^18)`. Together these give the sAVAX outstanding, the AVAX it claims and the AVAX one sAVAX redeems for.

The days and their last blocks come from `allium.c-chain-daily-last-blocks`, read from the Foundation's Snowflake account through the named connection described above. The capture copies them into `raw/days.json` and records the block run's hash. The public C-Chain node answers these calls at past blocks with no key. It takes 3 to 9 seconds to load each past block's state, so the capture sends batches of 12 calls, four at a time, and sends a batch again when the node times out. The run of 2026-11-05 made 6,972 calls in an hour, with 80 such repeats. The check requires every day once, the node's block hash equal to Allium's, the block's time on its day, a positive supply, and the pooled AVAX over the supply equal to the rate of one share within 10^-9. The build cuts nothing, and `held_back` marks the days from 2025-11-19.

On 2025-11-18, the last day before the held-back cut, 20.46 million sAVAX claimed 25.29 million AVAX, at 1.2361 AVAX per sAVAX. The rate never fell between 2022-01-27 and 2026-11-04. Allium's hourly price ratio of sAVAX to AVAX at 24:00 UTC, which `derived.outside-yields-daily` reads, differs from this rate by a median 0.22% and at most 4.3% on the 1,267 days both hold before the cut. It sits 0.27% below the rate on average.

```bash
uv run --locked --extra snowflake avalanche data fetch allium.c-chain-daily-last-blocks --output data/runs/daily-blocks-example/capture --timeout 600
uv run --locked avalanche data build allium.c-chain-daily-last-blocks --from data/runs/daily-blocks-example/capture --output data/runs/daily-blocks-example/dataset
uv run --locked avalanche data check allium.c-chain-daily-last-blocks --capture data/runs/daily-blocks-example/capture --dataset data/runs/daily-blocks-example/dataset
uv run --locked avalanche data fetch c-chain-rpc.savax-state-daily --output data/runs/savax-state-example/capture \
  --param blocks=data/runs/daily-blocks-example/dataset --timeout 90
uv run --locked avalanche data build c-chain-rpc.savax-state-daily --from data/runs/savax-state-example/capture --output data/runs/savax-state-example/dataset
uv run --locked avalanche data check c-chain-rpc.savax-state-daily --capture data/runs/savax-state-example/capture --dataset data/runs/savax-state-example/dataset
```

The pin [`v0.10-savax-state-2026-11-05.json`](pins/v0.10-savax-state-2026-11-05.json) names the two runs of this section.

## Split validator exits by Subnet role

`snowflake.subnet-validator-transactions` holds every P-Chain transaction that adds, removes, converts, registers, or disables a Subnet or L1 validator: 6,530 rows on the 2026-09-29 capture, 2,375 Subnet validator periods, 329 Subnets converted to L1s under ACP-77, 2,176 L1 registrations, and 583 disables. A `ConvertSubnetToL1Tx` has one row per initial L1 validator, so its hash repeats. `RemoveSubnetValidatorTx` names no node, and the Subnet addition it ended carries the early end as `removal_time`.

`derived.subnet-validation` joins those transactions to the staking-period log: one row per node and Subnet, with the node's Subnet periods, the Subnet's conversion time, the node's own L1 registration and disable, and its Primary Network span. It splits the fall in active validators after Etna by whether a node validated a Subnet and when that Subnet became an L1. Its build summary recomputes the protocol mechanism catalog's counts from these recorded inputs: of 1,555 validators active at 12:00 UTC on 2024-12-15, 1,036 never validated again after 2025-12-31, 296 had a Subnet period overlapping 2024-06-01 to Etna, and 270 of those exited, 133 more than the prior year's 46.2% rate would give. The monetary ledger's 1,567 for the same day counts validators active at 23:59:59, and the staking-period log gives 1,567 at that instant too.

```bash
uv run --locked --extra snowflake avalanche data fetch snowflake.subnet-validator-transactions --output data/runs/subnet-validator-transactions-example/capture --timeout 600
uv run --locked --extra snowflake avalanche data build snowflake.subnet-validator-transactions --from data/runs/subnet-validator-transactions-example/capture --output data/runs/subnet-validator-transactions-example/dataset
uv run --locked --extra snowflake avalanche data check snowflake.subnet-validator-transactions --capture data/runs/subnet-validator-transactions-example/capture --dataset data/runs/subnet-validator-transactions-example/dataset
uv run --locked avalanche data derive derived.subnet-validation --output data/runs/subnet-validation-example
uv run --locked avalanche data check derived.subnet-validation --capture data/runs/subnet-validation-example/capture --dataset data/runs/subnet-validation-example/dataset
```

The capture check requires one row per transaction and node, an ordered period for every Subnet addition, and early removals inside their period. The derived check requires one row per node and Subnet, no Subnet period starting after its Subnet converted, and every Subnet period inside a Primary Network period of the same node, the rule before Etna, then rebuilds the table from the recorded inputs. Both hold with no finding on the 2026-09-29 runs. Operators may register L1 validators under new node IDs, so the table is a lower bound on a node's continuity after conversion.

## Capture the AVAX exchange-traded products

These datasets follow AVAX held by the exchange-traded products that hold it, to test whether fund flows rise after Helicon. Each issuer is the authority for its own figures, and none of them is an on-chain observation. Bitwise embeds BAVA's fund record in its page, VanEck serves VAVX's figures as JSON blocks that expect a browser, 21Shares serves gzipped JSON, and Grayscale's GAVA page refuses automated requests, so GAVA comes from its 10-Q filings through SEC EDGAR, which requires a User-Agent that names a contact. The capture stores each response as served, after gzip decoding, with its hash in the receipt. The BAVA page is kept whole, so its custody wallet list stays in the raw capture.

BAVA and VAVX publish shares outstanding and AVAX held only as a current figure, usually as of the prior business day. The snapshot therefore becomes a series only as daily captures accumulate from 2026-09-28. For 21Shares, AVAX held is the AVAX entitlement per unit times units outstanding, and `avax_held_derived` marks it. The history table carries the 21Shares valuation histories, in which the change in units outstanding is the fund flow. For the single-asset product AVAX held is total NAV over the AVAX price. For the MOON and KEYS baskets it is left null because their historical weights are not published. BAVA's history has its NAV for every day and its AVAX held only on the current as-of date.

```bash
uv run --locked avalanche data fetch etf-issuers.avax-fund-snapshot --output data/runs/etf-snapshot-example/capture --timeout 60
uv run --locked avalanche data build etf-issuers.avax-fund-snapshot --from data/runs/etf-snapshot-example/capture --output data/runs/etf-snapshot-example/dataset
uv run --locked avalanche data check etf-issuers.avax-fund-snapshot --capture data/runs/etf-snapshot-example/capture --dataset data/runs/etf-snapshot-example/dataset
uv run --locked avalanche data fetch etf-issuers.avax-fund-history --output data/runs/etf-history-example/capture --timeout 60
uv run --locked avalanche data build etf-issuers.avax-fund-history --from data/runs/etf-history-example/capture --output data/runs/etf-history-example/dataset
uv run --locked avalanche data check etf-issuers.avax-fund-history --capture data/runs/etf-history-example/capture --dataset data/runs/etf-history-example/dataset
```

The snapshot check verifies required values, non-negative AVAX held, one row per fund, that BAVA's AVAX held equals its basket units, that each 21Shares product's AVAX held is within 0.5% of its NAV in AVAX over the AVAX price, that VAVX's AVAX per 1,000 shares agrees with its AVAX in trust, and that NAV times shares agrees with net assets. The history check verifies the same values and BAVA units, one row per fund and date, and that the AVAX price used for the single-asset product equals its index. Two old MOON dates disagree on NAV times units against net assets in the issuer's own record, so the history check lists such dates in its summary rather than failing. A history capture is about 3.4 MB.

## Derive the validator-week panel

`derived.validator-weeks` lays the staking-period log out by node and UTC week, Monday 00:00 to the next Monday, for every week a node is validating at the Monday cutoff or first starts a period during it. Every feature reads only staking transactions accepted before the cutoff: the node's own stake and fee, its age since first stake (gaps included) and its days staked (gaps excluded), its completed and started periods, the reward address of its latest transaction, the stake already delegated to it, and the delegation capacity left under the weight limit of five times its own stake and at most 3 million AVAX. A node is on offer when at least fourteen days remain in its period and at least 25 AVAX of capacity is left throughout them, counting delegations already scheduled to start. The week's outcomes are the delegations accepted in it, with and without the one address behind 93% of delegation events. Gap weeks between a node's periods have no row, because whether the node returns is not known at their cutoff.

Each row also quotes the yield on offer at its cutoff: the protocol kernel's annualized reward rate of a 25 AVAX delegation starting then, against the P-Chain supply counter last read before it (the value the reward formula uses), for fourteen days and for the time left in the node's period, gross and net of the node's fee, with the natural log of the net rate when it is positive. A 100% fee has a net rate of zero and no log, and stays an offer. The first week, 2020-09-21, has no quote, because the counter has no reading before it.

`derived.observed-delegations` keeps every delegation of the window with its exact duration in seconds and in weeks, and flags one whose validator was not on offer at its week's cutoff, which is how a validator renewing mid-week shows. Two delegations of 2023-06-02 have no row at all: they were accepted for validators scheduled to start the following week, which the protocol allowed before Durango.

`derived.market-weeks` holds what belongs to the week rather than to a node. Its stock is the realized total supply minus active validator and delegated stake at the close of the Sunday before the cutoff, from the monetary ledger: a candidate for the population not staking, not a measured outside option. Its flows are the week's delegations, all of them, with the concentrated address's share of events and of AVAX. Its price is the Binance close of that Sunday, the price at the cutoff, with 30-day volatility from the returns ending then, and DefiLlama's USD point nearest the cutoff as the named alternative.

```bash
uv run --locked avalanche data derive derived.validator-weeks --output data/runs/validator-weeks-example
uv run --locked avalanche data check derived.validator-weeks --capture data/runs/validator-weeks-example/capture --dataset data/runs/validator-weeks-example/dataset
uv run --locked avalanche data derive derived.observed-delegations --output data/runs/observed-delegations-example
uv run --locked avalanche data check derived.observed-delegations --capture data/runs/observed-delegations-example/capture --dataset data/runs/observed-delegations-example/dataset
uv run --locked avalanche data derive derived.market-weeks --output data/runs/market-weeks-example
uv run --locked avalanche data check derived.market-weeks --capture data/runs/market-weeks-example/capture --dataset data/runs/market-weeks-example/dataset
```

The panel's check rebuilds every week before 2025-01-06 from staking transactions accepted before that date and requires the rows to be identical to the full build's, which proves no early row reads a later event; on the 2026-09-27 build all 293,690 are. It also requires one row per node and week and that every delegation of the window is counted either in a row's outcomes or as having no row. Each build takes a few seconds.

## Build the monetary daily ledger

The ledger replays AVAX supply from genesis: rewards paid out minus every burn on the P-, X-, and C-Chains, in integer wei, one row per UTC day, with the validator and delegated stake active at 23:59:59 UTC. It is derived from built runs of six source datasets and settles their gaps from three more. Run `monetary-daily-2026-09-26` checks complete days through 2026-09-20. Read the [monetary source audit](monetary-source-audit.md) first: it distinguishes paid rewards and realized supply from the Data API's apparent accrued-reward definition, records the remaining 1,599 AVAX snapshot residual, and names the later incomplete days. Do not use the raw difference between those definitions as a test of historical ledger coverage.

P- and X-Chain burns come from one Snowflake query over the full history, about a minute:

```bash
uv run --locked --extra snowflake avalanche data fetch snowflake.primary-burn-daily --output data/runs/burn-daily-example/capture --timeout 600
uv run --locked avalanche data build snowflake.primary-burn-daily --from data/runs/burn-daily-example/capture --output data/runs/burn-daily-example/dataset
uv run --locked avalanche data check snowflake.primary-burn-daily --capture data/runs/burn-daily-example/capture --dataset data/runs/burn-daily-example/dataset
```

The check reports the transactions whose burn neither the share's record nor its UTXOs settle; the built row lists their hashes. Read those from the P-Chain node, which returns every input and output of a transaction, and the ledger applies them:

```bash
uv run --locked avalanche data fetch p-chain-rpc.transactions --output data/runs/p-transactions-example/capture --param hashes=<hash>,<hash> --timeout 30
uv run --locked avalanche data build p-chain-rpc.transactions --from data/runs/p-transactions-example/capture --output data/runs/p-transactions-example/dataset
uv run --locked avalanche data check p-chain-rpc.transactions --capture data/runs/p-transactions-example/capture --dataset data/runs/p-transactions-example/dataset
```

C-Chain EVM fees come from the Snowflake receipts, one run per year so each query stays under the ten-minute statement limit, with `--param start=YYYY-01-01 --param end=YYYY+1-01-01`; the ledger unions every current run. The check counts the blocks the share lacks (absent) and the blocks it holds without all their receipts (short); their fees are excluded from the day and read from the Data API block record instead. List the gap blocks once over the full history, then read them:

```bash
uv run --locked --extra snowflake avalanche data fetch snowflake.c-chain-block-gaps --output data/runs/c-block-gaps-example/capture --timeout 600
uv run --locked avalanche data build snowflake.c-chain-block-gaps --from data/runs/c-block-gaps-example/capture --output data/runs/c-block-gaps-example/dataset
uv run --locked avalanche data fetch data-api.c-chain-block-fees --output data/runs/c-block-fees-example/capture --param gaps=c-block-gaps-example --param workers=8 --timeout 60
uv run --locked avalanche data build data-api.c-chain-block-fees --from data/runs/c-block-fees-example/capture --output data/runs/c-block-fees-example/dataset
uv run --locked avalanche data check data-api.c-chain-block-fees --capture data/runs/c-block-fees-example/capture --dataset data/runs/c-block-fees-example/dataset --against data/runs/c-block-gaps-example/dataset
```

The atomic check counts the imports whose consumed UTXOs the Data API lists incompletely, so that its AVAX unlocked falls below the AVAX created; their burn is null in the built rows. Read those from the C-Chain node, which returns the signed transaction, and the ledger applies them:

```bash
uv run --locked avalanche data fetch c-chain-rpc.atomic-transactions --output data/runs/c-atomic-transactions-example/capture --param hashes=<hash>,<hash> --timeout 30
uv run --locked avalanche data build c-chain-rpc.atomic-transactions --from data/runs/c-atomic-transactions-example/capture --output data/runs/c-atomic-transactions-example/dataset
uv run --locked avalanche data check c-chain-rpc.atomic-transactions --capture data/runs/c-atomic-transactions-example/capture --dataset data/runs/c-atomic-transactions-example/dataset
```

The same gap blocks can be read without a key from a public node, which returns the block header and all its receipts in one batch; the build computes each block's fees from the receipts after checking they are the header's. The ledger takes either source for a block and reports any block the two give different fees:

```bash
uv run --locked avalanche data fetch c-chain-rpc.block-receipt-fees --output data/runs/c-block-receipt-fees-example/capture --param gaps=c-block-gaps-example --param workers=8 --timeout 60
uv run --locked avalanche data build c-chain-rpc.block-receipt-fees --from data/runs/c-block-receipt-fees-example/capture --output data/runs/c-block-receipt-fees-example/dataset
uv run --locked avalanche data check c-chain-rpc.block-receipt-fees --capture data/runs/c-block-receipt-fees-example/capture --dataset data/runs/c-block-receipt-fees-example/dataset --against data/runs/c-block-gaps-example/dataset
```

The block-fee walk and the C atomic walk write one record per line as it arrives and keep their lines when the Data API refuses further requests; continue either with `--param resume=<kept directory>`. Keyless, the API refused after about a thousand requests an hour on 2026-09-23. With a Data API key from [AvaCloud](https://app.avacloud.io) exported as `AVALANCHE_DATA_API_KEY`, it allows about 750 block requests a minute, and `--param workers=8` on the block-fee walk uses that. The key is sent only to `glacier-api.avax.network` and never enters a capture or a receipt. The atomic history is one walk from the newest transaction back to the first C block, `--param start=2020-09-23 --param end=<yesterday> --param max_pages=30000`, 11,648 pages on 2026-09-23.

Then derive and check the ledger. The derive takes the newest built run of the P and X burns, the staking rewards, the staking-period log, and the staking supply, and every current run of the repairs, the C EVM years, the atomic walks, and the Data API supply snapshots:

```bash
uv run --locked avalanche data derive derived.avax-monetary-daily --output data/runs/monetary-daily-example
uv run --locked avalanche data check derived.avax-monetary-daily --capture data/runs/monetary-daily-example/capture --dataset data/runs/monetary-daily-example/dataset
```

The check verifies the input runs still hash as recorded, that every day with a supply conserves exactly (close equals open plus rewards minus burns) and opens at the previous close, that every coverage value is one of complete, repaired, incomplete, or missing, that each Data API supply snapshot's cumulative rewards and burns by chain lie between the ledger's totals through the day before and through the snapshot day when the ledger is complete that far (the API's C burn counts EVM fees only, so it is compared with the ledger's EVM burns), and that the P-Chain supply counter is within 0.05% of genesis plus recognised rewards, held fees and current open reward reservations. That broad tolerance is a diagnostic, while event identity and source replay independently validate cycle completeness. The build summary names the first incomplete day and the last day with a verified supply.

### Cycle accounting and archived inputs

Current ledger captures declare `ordinary-net-payout-plus-cycle-current-recognition/v1`. Ordinary reward transactions contribute their net reward outputs. Auto-renewed parent payouts are excluded from that ordinary sum. Each closed cycle instead contributes its current eligible validator reward and pending delegatee fees once, whether withdrawn or restaked. Releasing restakes recognised in earlier cycles changes liquidity and contributes no new issuance. This realised supply is not the protocol counter, which also reserves rewards for open commitments.

The selected staking-period capture binds the exact cycle-history run, which binds the exact P-Chain block walk. A closed event needs its parent transaction, cycle end, reward proposal and matching commit or abort, including block identities, heights and equal chain timestamps. Cycle weights apply on half-open intervals `[start_time, end_time)`. Transaction first-period fields retain their original meaning.

Every current ledger build records a `cycle-accounting-events.parquet` companion with bytes and SHA-256. It distinguishes current recognised reward, restake, liquid reward and release of earlier accrual. The ledger check replays its recorded sources and compares both the daily ledger and companion. The upgrade-period producer authenticates that parent replay, then splits ordinary and cycle events at exact activation instants. A daily sum alone cannot validate intraday allocation. Period C-EVM burn includes gap repairs once, and all four chain components must sum to total burn.

Overlapping inputs select whole rows by declared source authority and capture time. Seamed rows take priority over raw rows. A newer NULL remains NULL, and conflicting equal-priority rows refuse. Explicit raw or seamed pins preserve archival selection. Source-run row counts are recorded in the summary.

C-EVM daily queries emit dates with present blocks. An omitted date inside a complete query window can have no blocks or only absent blocks reconstructed by fee records. Gap-list dates are predecessor proxies. Repair settlement uses block identity and a known actual fee date, while burn amounts use the fee record's actual date. A selected row with missing values, an unknown repair date or an unresolved gap stops supply certification. Each accounting connection has its own temporary spill directory.

Older pins and payout-only ledgers remain available for their original source versions. A current ledger changes post-Helicon issuance and stock semantics, so adopt a successor explicitly. Consumers that already add restake to the old ledger must remove that adjustment before adopting cycle-effective stock. A rebuilt price artifact also requires join review because changing nominal dates can change selected prices even when observed timestamps and values are identical.

## Use datasets from a notebook

Notebooks load built datasets by catalog ID. Nothing is fetched on load; the functions read the receipts and Parquet files that `fetch` and `build` wrote under `data/runs/`, verify the Parquet hash against the build receipt, and hand back typed tables.

```python
from avalanche_research import datasets

validators = datasets.load("snowflake.primary-validator-stakes")          # latest built run, pandas DataFrame
receipt = datasets.receipt("snowflake.primary-validator-stakes")          # capture and build receipts of that run
db = datasets.connect()                                                   # DuckDB with one view per built dataset
db.execute("SELECT COUNT(*) FROM delegator_stakes JOIN validator_stakes ON validator_transaction_hash = transaction_hash").fetchone()
```

`datasets.runs(dataset_id)` lists the built runs with capture time and row count; pass `run="<directory name>"` to any call to pin one. View names drop the source prefix and the `primary-` prefix: `validator_stakes`, `delegator_stakes`, `staking_rewards`, `staking_supply`, `staking_periods`, `avax_monetary_daily`, `avax_market_daily`, `avax_price_daily`, `network_summary`. The same listing is available as `avalanche data runs [dataset_id]`.

## Pin an input set

A study or model that must be rebuilt from exactly its inputs reads a pin file instead of the newest runs. `pin` takes each dataset's newest run, or the one named with `--run`, refuses any run whose check has not passed, and writes `data/pins/<name>.json` with each run's capture ID and Parquet sha256. `pin-check` reports a pinned run that is missing, changed, or no longer passes its check.

```bash
uv run --locked avalanche data pin milestone-2 derived.avax-monetary-daily derived.staking-periods --run derived.staking-periods=staking-periods-2026-09-30
uv run --locked avalanche data pin-check data/pins/milestone-2.json
```

```python
from pathlib import Path

from avalanche_research import datasets, pins

pinned = pins.runs(Path("data/pins/milestone-2.json"))                     # dataset ID -> run
ledger = datasets.load("derived.avax-monetary-daily", run=pinned["derived.avax-monetary-daily"])
```

## Inspect the contract

```bash
uv run --locked avalanche data list
uv run --locked avalanche data describe snowpeer
uv run --locked avalanche data describe snowpeer.network-summary
uv run --locked avalanche data describe avalanche-snowflake
uv run --locked avalanche data describe snowflake.primary-validator-stakes
uv run --locked avalanche data describe snowflake.primary-delegator-stakes
uv run --locked avalanche data describe snowflake.primary-staking-rewards
uv run --locked avalanche data describe snowflake.primary-staking-supply
uv run --locked avalanche data describe coingecko.avax-market-daily
uv run --locked avalanche data describe defillama.avax-price-daily
uv run --locked avalanche data describe p-chain-rpc.current-validators
uv run --locked avalanche data describe defillama.pool-yields
uv run --locked avalanche data describe us-treasury.par-yield-daily
uv run --locked avalanche data describe metrics-api.primary-staking-daily
uv run --locked avalanche data describe metrics-api.c-chain-activity-daily
uv run --locked avalanche data describe data-api.avax-supply
uv run --locked avalanche data manifest --json
```

Snowpeer is a curated secondary source. Its results are suitable for discovery, dashboard reproduction, and cross-checking. Claims that require raw on-chain evidence must use an authoritative chain or warehouse source such as the Avalanche Snowflake share.

### Explicit price-clock successors

The price consumers offer additive observed-time policies. Their default calls retain the historical nominal-date behavior. Select the policy by name when rebuilding a result, record the exact input pin and preserve the returned frame metadata in the export. An observation timestamp is a retrospective availability proxy. Historical provider publication and revision times are unverified.

| Consumer and explicit call | Observation-time rule | Meaning |
| --- | --- | --- |
| `market_layer.as_of(..., price_clock=market_layer.OBSERVED_PRICE_CLOCK)` or `market_layer.build(...)` | Latest whole quote with `observed_at` strictly before UTC midnight of the acceptance day. No added age cap | Completed-day market context. Both cutoff age and actual-decision age are exposed |
| `weeks.with_observed_market_prices(frame, price_parquet)` | Latest whole quote strictly before `week_start_utc`, at most 24 hours old | DefiLlama price/volatility projection only. Other weekly fields and their source rules are retained |
| `scenario_inputs.build(..., price_clock=scenario_inputs.OBSERVED_CLOSE_CLOCK)` | Latest whole quote strictly before the next UTC midnight. No added age cap | End-of-day valuation of daily AVAX burn. Neither a prediction-time feature nor an intraday transaction-weighted dollar total |

Price and volatility come from the same row. A latest NULL stays NULL. Exact duplicates collapse and a conflicting simultaneous quote refuses if it would be selected. Nominal dates remain provenance and never govern the join. Weekly stale quotes have missing admitted values, an explicit stale status and retained candidate time/age. All paths record the price-file SHA-256. Missing quotes never fill from future data.

The scenario successor requires qualified native-yield basis, quote time and exact integer supply metadata and carries them into its result. Those rates remain realised-supply approximations. Their supply input can differ from the scenario ledger and must be reported separately. This does not establish an exact historical protocol-counter offer. Changing a named engineering projection does not automatically adopt it into an existing research study or model.

Reproduce the named three-table engineering export from its seven-input pin:

```sh
uv run python scripts/price_consumer_tables.py \
  --pin data/pins/price-consumers-observed-2026-10-26.json \
  --runs-root data/runs --out /tmp/price-consumers-observed
```

The output must be new and outside a Git checkout. The command writes sorted CSVs for each successor and its fixed-input legacy comparison, input selection, quote-age/missingness summaries and byte-hash receipts. The market export reads validator identity and acceptance clocks strictly before 19 November 2025 at 16:00 UTC. It reads no validator outcome fields. Scenario outputs cover the selected ledger's complete days. Weekly outputs retain the selected historical frame and change only its DefiLlama projection. These are engineering exports, with no model fitting or scoring.
