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
| `data-api.c-chain-atomic-burn` | One C-Chain import or export per row with the exact AVAX input-minus-output burn | Implemented, tested, and captured for the full history on 2026-09-23: 1,171,886 transactions, five imports left for the node record below |
| `c-chain-rpc.receipt-gap-repairs` | One C-Chain transaction receipt per row for a specified block missing from the Snowflake share | Implemented and checked for block 95,492,477; a source repair, not a combined daily burn |
| `snowflake.primary-burn-daily` | One Parquet row per UTC date and chain (P or X) with the AVAX burned, how each burn was established, the L1 validator fees, and the hashes the share cannot settle | Implemented, tested, and captured for the full history on 2026-09-23; 24 P-Chain imports settled by the node record below |
| `p-chain-rpc.transactions` | One Parquet row per requested P-Chain transaction with the AVAX it consumed, created, and burned, from the node's own record | Implemented, tested, and captured for the 24 imports the share and the Data API cannot settle |
| `c-chain-rpc.atomic-transactions` | One Parquet row per requested C-Chain import with the AVAX it consumed, created, and burned, decoded from the node's signed transaction | Implemented, tested, and captured for the five 2021 imports whose consumed UTXOs the Data API lists incompletely |
| `snowflake.c-chain-evm-burn-daily` | One Parquet row per UTC day with the exact EVM fee burn over the share's complete C blocks, the blocks read once where the share repeats them, and the absent and short blocks counted | Implemented, tested, and captured 2020-09-23 to 2026-09-21 in seven year runs; three days of 2023 and about forty of 2025 wait on the block-fee capture |
| `snowflake.c-chain-block-gaps` | One Parquet row per C block the share lacks or holds without all its receipts | Implemented and tested; the full-history capture is the next step |
| `data-api.c-chain-block-fees` | One Parquet row per gap block read from the Data API block record with the fees burned in it | Implemented and tested; captured in part, as far as the key's daily allowance reached |
| `c-chain-rpc.block-receipt-fees` | The same rows computed from a public node's block header and receipts, with no key | Implemented and tested; captured for the 2023 gap blocks on 2026-09-24 |
| `derived.avax-monetary-daily` | One Parquet row per UTC date with rewards paid out, burns by chain, realized total supply replayed from genesis, and active stake, every amount in wei with a coverage state per component | Implemented, tested, and derived on 2026-09-23; supply is verified through 2020-09-22 until the C-Chain atomic walk and the gap-block fees complete |
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
| `etf-issuers.avax-fund-snapshot` | One Parquet row per AVAX exchange-traded product per capture with the issuer's NAV, net assets, shares outstanding, AVAX held, and share staked: BAVA, VAVX, the 21Shares Avalanche product and two baskets holding AVAX, and GAVA from its latest 10-Q | Implemented, tested, and captured daily from 2026-09-28: 7,464,611 AVAX across six funds on the first run |
| `etf-issuers.avax-fund-history` | One Parquet row per fund per valuation date from the histories issuers publish: 21Shares daily since launch, BAVA's daily NAV since 2026-04-14, and GAVA's quarter ends | Implemented, tested, and captured daily from 2026-09-28: 4,619 rows on the first run |

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

The Binance archive gives the same history with exact UTC day boundaries: each day's close is the price at the next midnight, so a feature observed at a Monday 00:00 cutoff reads Sunday's close. The archive publishes a SHA-256 beside every file, and the capture refuses a file that differs. The quote is USDT: against Coinbase's AVAX/USD closes on 1,453 days from October 2021 to September 2025 the median difference is 0.05% and the largest 1.22%. The check compares each day's open with CoinGecko's USD price at the same midnight and reports a day only when the price is both beyond 2% of the open and outside the day's range widened by 2%; on the 365 shared days of 2026-09-26 the median difference is 0.09% and no day is reported. DefiLlama's points are stamped at 00:00, 00:01, or 23:59, so its date labels shift by up to a day; aligned by time of day it agrees with Binance at a median of 0.11%.

```bash
uv run --locked avalanche data fetch binance.avax-usdt-daily --output data/runs/binance-avax-example/capture --param end=<first day not captured>
uv run --locked avalanche data build binance.avax-usdt-daily --from data/runs/binance-avax-example/capture --output data/runs/binance-avax-example/dataset
uv run --locked avalanche data check binance.avax-usdt-daily --capture data/runs/binance-avax-example/capture --dataset data/runs/binance-avax-example/dataset --against data/runs/avax-market-example/dataset
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

The ledger replays AVAX supply from genesis: rewards paid out minus every burn on the P-, X-, and C-Chains, in integer wei, one row per UTC day, with the validator and delegated stake active at 23:59:59 UTC. It is derived from built runs of six source datasets and settles their gaps from three more. Read the [monetary source audit](monetary-source-audit.md) first: it records what each source can and cannot settle and where the providers disagree.

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

The check verifies the input runs still hash as recorded, that every day with a supply conserves exactly (close equals open plus rewards minus burns) and opens at the previous close, that every coverage value is one of complete, repaired, incomplete, or missing, that each Data API supply snapshot's cumulative rewards and burns by chain lie between the ledger's totals through the day before and through the snapshot day when the ledger is complete that far (the API's C burn counts EVM fees only, so it is compared with the ledger's EVM burns), and that the P-Chain supply counter equals genesis plus rewards paid plus the potential rewards of open periods within 0.05%. The build summary names the first incomplete day and the last day with a verified supply.

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
