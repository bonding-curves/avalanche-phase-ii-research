# AVAX monetary source audit

Status: checked P/X and C atomic one-day sources, 2026-09-21. Historical total supply and all-chain burn are **not** ready for study use.

## Source decisions

| Measure | Source | Current result | Remaining check |
| --- | --- | --- | --- |
| P/X burn | Snowflake `P_TRANSACTIONS` and `X_TRANSACTIONS`, `BURNED_AVAX` | `snowflake.primary-burn-events` is a checked, timestamped transaction dataset. Amounts are nAVAX; repeated P hashes are deduplicated before summing. | Capture and reconcile the full date range against independent cumulative P/X totals. |
| C-Chain EVM burn | Snowflake `C_RECEIPTS`, `TRANSACTIONRECEIPTGASUSED × TRANSACTIONRECEIPTEFFECTIVEGASPRICE` | The product is wei. On 2026-09-16, the sum agrees with the Metrics API `feesPaid` value expressed in AVAX. | Capture a complete range and validate coverage and lag. |
| C-Chain atomic burn | Data API C-Chain import/export transactions, AVAX unlocked minus AVAX created | `data-api.c-chain-atomic-burn` preserves paginated transaction responses and checks the AVAX amounts against each transaction's inputs and outputs. The 2026-09-16 result matches every Snowflake C block carrying atomic gas. | Capture the historical range and reconcile cumulative C burn against a dated Data API supply checkpoint. The endpoint pages backward from latest and cannot date-filter an all-address query. |
| Staking issuance | Existing `snowflake.primary-staking-rewards` reward UTXOs | Payout-time realized rewards are timestamped; a transfer of delegation fees is not new issuance. | Reconcile cumulative rewards to the Data API snapshot and examine missing UTXOs over the full history. |
| Historical realized supply | Genesis unlock + cumulative payout-time issuance − cumulative P/C/X burn | Cannot be completed until all sources cover the historical range. The current Data API snapshot is a checkpoint, not a historical series. | Resolve missing P burns and reconcile a replay to multiple dated supply snapshots. |
| Active stake | Existing `derived.staking-periods`, start/end intervals | Self-stake and delegated stake can be reconstructed at declared UTC instants. | Reconcile sampled days to the Metrics API and disclose its aggregation-time differences. |

A full-share P-Chain probe found 320 deduplicated transaction hashes outside the two known zero-burn system types with null `BURNED_AVAX`, including 200 delegations and 75 genesis validators. The dataset preserves these as missing and its check reports them; it never replaces them with `FEE` or zero. The one-day checked sample below has no such missing transaction.

The [Avalanche transaction-fee guide](https://build.avax.network/docs/rpcs/other/guides/txn-fees) confirms that fees burn, that C-Chain base and priority fees both burn, and that atomic transactions charge separately. [AvalancheGo's atomic fee code](https://github.com/ava-labs/avalanchego/blob/master/graft/coreth/plugin/evm/atomic/tx.go) rounds the protocol minimum upward per transaction: `ceil(gas_used × block_base_fee_wei / 1e9)` nAVAX. The same code accepts AVAX burned above that minimum as a block fee contribution. Therefore `C_BLOCKS.BLOCKEXTDATAGASUSED` alone cannot reconstruct actual atomic burn. The [Snowflake share documentation](https://build.avax.network/docs/api-reference/data-api/snowflake) names the source tables. The [Data API supply endpoint](https://build.avax.network/docs/api-reference/data-api/avax-supply/getAvaxSupply) reports current cumulative rewards and P/C/X burns, with no date parameter.

## One-day proof, 2026-09-16 UTC

The checked P/X capture is `capture:avalanche-snowflake:2026-09-21T19:36:28Z:794763e68b1c`. Its query, raw rows, hashes, and Snowflake query ID are retained by `avalanche data fetch`. The normalized Parquet build passed eight checks with zero findings. A separate 2022-06-01 test also passed; its temporary run was removed after the test so it cannot displace the current sample in latest-run selection.

| Result | Value | Evidence |
| --- | ---: | --- |
| P burn | 31.032005816 AVAX | 2,803 unique P transactions; Snowflake `BURNED_AVAX` sum 31,032,005,816 nAVAX; four duplicate rows of one hash had null burn and were not summed. |
| X burn | 0.190000000 AVAX | 135 unique X transactions; Snowflake `BURNED_AVAX` sum 190,000,000 nAVAX. |
| C EVM fees only | 679.507693734542888415 AVAX | 672,231 unique `C_RECEIPTS`; sum of `gasUsed × effectiveGasPrice` was 679,507,693,734,542,888,415 wei. The previously captured Metrics API day reports 679.5076937345427 AVAX and 672,231 transactions. |
| C atomic burn | 0.248693196 AVAX | The checked Data API capture has 212 import/export transactions in 212 distinct blocks; AVAX unlocked minus created sums to 248,693,196 nAVAX. Every block height and hash matches one of the 212 Snowflake blocks with positive atomic gas, and no block is unmatched. All 212 burns exceed the per-transaction protocol minimum, which sums to 149,444 nAVAX. |
| C EVM plus atomic burn | 679.756386930542888415 AVAX | Sum of the independent receipt and atomic transaction measurements above; not a historical cumulative checkpoint. |
| Realized staking rewards | 8,888.852145255 AVAX | Existing reward capture: 1,091 reward rows; no rewarded row lacked reward UTXOs on this day. |
| Active stake at 23:59:59 UTC | 166,154,421.557630879 validator AVAX and 38,749,919.119590262 delegated AVAX | Existing staking-period intervals; 593 validator and 32,474 delegator periods active. This is not yet a staking ratio. |

The Snowflake audit query IDs for P, X, C receipts, and C blocks are `01c7398a-0208-942c-000f-0d5e0076b01e`, `01c7398a-0208-910a-000f-0d5e0076d016`, `01c7398a-0208-9403-000f-0d5e0076903a`, and `01c7398a-0208-9434-000f-0d5e0076f01e`, respectively. Those queries used half-open UTC bounds. The P/X capture is the durable raw-row record; the other three results are source-audit probes, not published datasets.

The C atomic capture is `capture:avalanche-data-api:2026-09-21T20:20:43Z:f1f13e9ff4cb`. It contains 13 raw API pages and passed seven checks with zero findings. The independent C-block count and gas query is Snowflake ID `01c739e7-0208-93b4-000f-0d5e0076702e`. The capture covers one UTC day, not all C atomic history.

## Reproduce the checked P/X sample

Use an authorized Snowflake connection as described in [Research data](README.md). From the repository root:

```bash
uv run --locked --extra snowflake avalanche data fetch snowflake.primary-burn-events \
  --output data/runs/burn-events-example/capture \
  --param start=2026-09-16 --param end=2026-09-17 --timeout 120
uv run --locked avalanche data build snowflake.primary-burn-events \
  --from data/runs/burn-events-example/capture \
  --output data/runs/burn-events-example/dataset
uv run --locked avalanche data check snowflake.primary-burn-events \
  --capture data/runs/burn-events-example/capture \
  --dataset data/runs/burn-events-example/dataset
```

## Reproduce the C atomic sample

The [Data API C-Chain transaction endpoint](https://build.avax.network/docs/api-reference/data-api/primary-network-transactions/listLatestPrimaryNetworkTransactions) lists imports and exports. With no address filter, it does not accept date filters; the capture pages backward until it passes the requested start date. A distant historical window may need a larger `max_pages` parameter.

```bash
uv run --locked avalanche data fetch data-api.c-chain-atomic-burn \
  --output data/runs/atomic-burn-example/capture \
  --param start=2026-09-16 --param end=2026-09-17 --timeout 30
uv run --locked avalanche data build data-api.c-chain-atomic-burn \
  --from data/runs/atomic-burn-example/capture \
  --output data/runs/atomic-burn-example/dataset
uv run --locked avalanche data check data-api.c-chain-atomic-burn \
  --capture data/runs/atomic-burn-example/capture \
  --dataset data/runs/atomic-burn-example/dataset
```

Next: check full historical coverage of C receipts and atomic transactions, classify the 320 unresolved P burn records, then reconcile all three chain totals with a dated supply checkpoint. Until then, do not derive historical total supply or report a complete C or all-chain burn total.
