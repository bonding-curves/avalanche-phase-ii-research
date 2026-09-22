# Research data

This directory defines the machine-readable contracts for research data used in Avalanche Phase II. The first dataset reconstructs Snowpeer's six network-wide summary metrics. The others preserve every validator staking transaction, every delegation transaction, and every staking reward outcome on the Avalanche Primary Network from the Avalanche Snowflake share. All of them keep the source evidence, transformation, and validation records required to inspect the result.

## Current coverage

| Dataset | Output | Status |
| --- | --- | --- |
| `snowpeer.network-summary` | One timestamped row in JSON and Parquet | Implemented and tested |
| `snowflake.primary-validator-stakes` | One Parquet row per validator staking transaction since 2020-09-10 | Implemented, tested, and captured live |
| `snowflake.primary-delegator-stakes` | One Parquet row per delegation transaction since 2020-09-10 | Implemented, tested, and captured live |
| `snowflake.primary-staking-rewards` | One Parquet row per reward transaction closing a staking period | Implemented, tested, and captured live |
| `snowflake.primary-staking-supply` | One Parquet row per staking transaction with the block supply context behind its potential reward | Implemented, tested, and captured live |
| `snowflake.primary-burn-events` | One deduplicated P- or X-Chain transaction per row with recorded AVAX burn | Implemented, tested, and captured for 2026-09-16; not an all-chain burn total |
| `data-api.c-chain-atomic-burn` | One C-Chain import or export per row with the exact AVAX input-minus-output burn | Implemented, tested, and captured for 2026-09-16; not a historical C burn total |
| `c-chain-rpc.receipt-gap-repairs` | One C-Chain transaction receipt per row for a specified block missing from the Snowflake share | Implemented and checked for block 95,492,477; a source repair, not a combined daily burn |
| `coingecko.avax-market-daily` | One Parquet row per day of AVAX price, market capitalization, volume, log return, and 30-day realized volatility | Implemented, tested, and captured live; public API serves the trailing 365 days only |
| `defillama.avax-price-daily` | One Parquet row per daily AVAX price observation since 2020-09-22 with log return and 30-day realized volatility | Implemented, tested, and captured live |
| `p-chain-rpc.current-validators` | One Parquet row per validator in the current Primary Network set with stake, fee, observed uptime, connection, and delegator totals | Implemented, tested, and captured live; a snapshot, not a history |
| `defillama.pool-yields` | One Parquet row per DefiLlama pool on Avalanche or in a declared proof-of-stake staking project, with yields, TVL, and risk descriptors | Implemented, tested, and captured live; a snapshot |
| `us-treasury.par-yield-daily` | One Parquet row per business day and tenor of the US Treasury par yield curve since 2020 | Implemented, tested, and captured live |
| `metrics-api.primary-staking-daily` | One Parquet row per day of Metrics API validator and delegator counts and weights since 2021-02-28 | Implemented, tested, captured live, and reconciled against the Snowflake datasets |
| `metrics-api.c-chain-activity-daily` | One Parquet row per day of Metrics API C-Chain active addresses, transactions, gas, fees, and gas price since 2021-03-21 | Implemented, tested, and captured live |
| `data-api.avax-supply` | One Parquet row per capture with the Data API's current supply, staked, locked, cumulative reward, and burn totals | Implemented, tested, and captured live; the API publishes no history |
| `data-api.validators-active` | One Parquet row per active Primary Network validation at the capture instant with the Data API's uptime, health, delegation capacity and fill, version, geolocation, and staking type | Implemented, tested, captured daily beside the RPC snapshot, and reconciled against it as a second observer |
| `data-api.validators-completed` | One Parquet row per completed Primary Network validation with its reward addresses, potential reward, and cumulative delegation | Implemented, tested, captured once for the full history (56,963 rows on 2026-09-22), and reconciled against the Snowflake stake captures |
| `derived.staking-periods` | One Parquet row per staking period, validators and delegators together, with reward outcome, supply reading, upgrade regime, and the protocol kernel's reward for the row | Implemented, tested, and derived from the four Snowflake staking runs |
| `derived.node-table` | One Parquet row per validator node: the three clocks (span, tenure, current streak) and their stake weights, stake and fee history, delegation, rewards and failures, upgrade regimes, and the reward address as an operator proxy, all clipped at the validator capture time | Implemented, tested, and derived from the staking-period log and the two Snowflake stake runs |

[`data-catalog.json`](data-catalog.json) records source authority, endpoints, queries, field definitions, units, and derivations. [`data-catalog.schema.json`](data-catalog.schema.json) validates its structure. [`queries/`](queries/) holds the exact SQL text each Snowflake dataset runs. [`research-navigation.json`](research-navigation.json) supports deterministic navigation across the published research.

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

The cross-check pairs each CoinGecko midnight observation with the DefiLlama observation nearest that day's start when it lies within three hours, reports the median and maximum relative difference and the days it could not align, and raises a finding for any aligned day beyond 10%.

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

The active check verifies every RPC node is present, the two observers' uptimes differ by a median under one point, and delegated weight agrees per node on at least 85% and in total within 2%. The completed check verifies the first reward address, stake, and potential reward equal the Snowflake validator capture on every validation in both, and when the delegator capture sits in the same `--against` directory, that cumulative delegation and delegation count equal its sum and count. The full completed history is about 570 pages and 35 minutes keyless.

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

## Use datasets from a notebook

Notebooks load built datasets by catalog ID. Nothing is fetched on load; the functions read the receipts and Parquet files that `fetch` and `build` wrote under `data/runs/`, verify the Parquet hash against the build receipt, and hand back typed tables.

```python
from avalanche_research import datasets

validators = datasets.load("snowflake.primary-validator-stakes")          # latest built run, pandas DataFrame
receipt = datasets.receipt("snowflake.primary-validator-stakes")          # capture and build receipts of that run
db = datasets.connect()                                                   # DuckDB with one view per built dataset
db.execute("SELECT COUNT(*) FROM delegator_stakes JOIN validator_stakes ON validator_transaction_hash = transaction_hash").fetchone()
```

`datasets.runs(dataset_id)` lists the built runs with capture time and row count; pass `run="<directory name>"` to any call to pin one. View names drop the source prefix and the `primary-` prefix: `validator_stakes`, `delegator_stakes`, `staking_rewards`, `staking_supply`, `staking_periods`, `avax_market_daily`, `avax_price_daily`, `network_summary`. The same listing is available as `avalanche data runs [dataset_id]`.

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
