# AVAX monetary source audit

Status: the daily ledger `derived.avax-monetary-daily` is built and checked (2026-09-23). P- and X-Chain burns, staking issuance, and active stake are settled over the full history. C-Chain EVM fees are settled on every day the Snowflake share holds completely; three days of 2023 and about forty of 2025 wait on the Data API block record. The C-Chain atomic history waits on the Data API's keyless rate limit. Supply is verified through 2020-09-22 and advances as those two captures complete.

## Source decisions

| Measure | Source | Result on 2026-09-23 | Remaining |
| --- | --- | --- | --- |
| P/X burn | Snowflake `P_TRANSACTIONS` and `X_TRANSACTIONS` by day (`snowflake.primary-burn-daily`), consumed and created AVAX UTXOs where the record is null, the P-Chain node's transaction record (`p-chain-rpc.transactions`) where the UTXOs are not in the share | 15,486,379 P and 4,677,969 X transactions, every one settled: 13,489,373 recorded, 6,674,039 zero-burn system transactions, 78 genesis, 834 from UTXOs, 24 from the node. P transaction burns 782.69 AVAX, X 45,618.73 AVAX, through 2026-09-22 | None |
| P-Chain L1 validator fees | The P-Chain counters `L1_VALIDATOR_ACCRUED_FEES` and `L1_VALIDATOR_ACTIVE_COUNT` on every P transaction since Etna | Previous count times the counter's increase, summed: 17,951.43 AVAX to 2026-09-19 11:00 UTC against the Data API's 17,951.41 | None |
| C-Chain EVM burn | Snowflake `C_RECEIPTS` by day over complete blocks (`snowflake.c-chain-evm-burn-daily`), the Data API block record for the blocks the share lacks or holds short (`snowflake.c-chain-block-gaps`, `data-api.c-chain-block-fees`) | 2020-09-23 to 2026-09-21 captured in seven year runs. The share lacks every receipt of 2023-10-06 and a third of those of 2023-12-13 and 2023-12-14, lacks about 15,000 blocks on 37 days of 2025, and loaded 2025-08-28 and 2025-09-07 twice. The Data API's `feesSpent` per block equals the receipt sum on 16 blocks of 2021, 2023, and 2025 | Read about 143,000 gap blocks from the Data API, one request each |
| C-Chain atomic burn | Data API C-Chain transactions, AVAX unlocked minus created (`data-api.c-chain-atomic-burn`), one walk from the newest transaction back to the first C block | 1,020 pages of about 9,000 kept, walk resumable | Finish the walk under the rate limit |
| Staking issuance | `snowflake.primary-staking-rewards`, reward UTXOs at payout time | 110.44 million AVAX paid through 2026-09-21. The Snowflake UTXO record sums to the same; the P-Chain supply counter reconciles within 0.004% | Explain the Data API's `totalRewards`, 2.53 million AVAX higher (below) |
| Realized supply | 360,000,000 AVAX at genesis plus rewards paid minus every burn, replayed by day | Verified through 2020-09-22; every day after waits on the C atomic walk | The two C captures |
| Active stake | `derived.staking-periods` at 23:59:59 UTC | Validator and delegated stake and counts on every day before the stake capture | None |

## 2026-09-23 findings

`F1` The Data API's `totalPBurned` is the sum of two things: the AVAX destroyed by P-Chain transactions and the L1 validator fees consumed from validator balances. The share's `BURNED_AVAX` for `IncreaseL1ValidatorBalanceTx`, `RegisterL1ValidatorTx`, and `ConvertSubnetToL1Tx` includes the balance deposited (25,225 AVAX in all), which is held by the P-Chain and burned later as those fees; the ledger subtracts the deposit (`L1_VALIDATOR_PAYG_BALANCE` per validator row) and reports it apart. On ten sampled transactions the split equals the Data API's `amountBurned` and `amountL1ValidatorBalanceBurned`. Transaction burns 782.55 plus fees 17,951.43 give 18,733.98 AVAX against the API's 18,730.25 at 2026-09-19 11:00 UTC; the 3.73 AVAX difference is the three negative records of `F2`, which the API carries as negatives and the ledger settles from UTXOs.

`F2` The share's `BURNED_AVAX` is null on 320 P and 613 X hashes and negative on three P imports of January 2022. Consumed minus non-reward created AVAX UTXOs settles 834 of them (222 P, 612 X) and reproduced the recorded burn on 30 P and 60 X control transactions; the 78 genesis transactions burn nothing; 24 P imports of 2025-03-11 and 2025-03-14 consume UTXOs the share does not hold. The Data API lists those 24 with no consumed UTXOs and a zero burn, which is its incomplete view, not a settlement. The P-Chain node's `platform.getTx` returns their inputs: 115,780 nAVAX in all, 4,135 nAVAX each on the first two, equal to the share's `FEE` column. The API's `totalXBurned` equals the share's recorded X burns and omits the 612 null-burn X transactions of 2025-09-13 to 2025-09-15, 0.679 AVAX.

`F3` The share's `C_RECEIPTS` is incomplete and repeated in places the daily count does not reveal: 2023-10-06 has its 43,156 blocks and none of its 506,038 receipts; 2023-12-13 and 2023-12-14 hold 3.2 of 4.5 million and 3.6 of 5.5 million; 2025 lacks about 15,000 blocks on 37 days, two of them at day boundaries; 2025-08-28 and 2025-09-07 are loaded twice, blocks and receipts. `C_TRANSACTIONS` is incomplete on the same days and its `TRANSACTIONCOST` is not the fee. The Metrics API's daily `feesPaid` equals the share's receipt sum on those days, gaps and doubles included, so it is the same indexer and not an independent check. The daily query now reads blocks and receipts once by height and hash and sums only complete blocks; the gaps dataset lists the rest.

`F4` The Data API's block record (`GET /v1/chains/43114/blocks/{height}`) carries `feesSpent`, equal to the receipt sum on every block checked; its block listing takes no height range, so each gap block is one request. `eth_getBlockReceipts` is not served by the public node. Keyless, the Data API answered HTTP 429 after about 130 requests at three a second and again after about 1,000 at one a second, and kept refusing for more than forty minutes. With a key from AvaCloud the API reports `ratelimit-policy: 8000;w=60`, about 750 block requests a minute; the key is accepted by `glacier-api.avax.network` and rejected by the `data-api.avax.network` alias, so the atomic endpoint moved to the first host and the key is sent nowhere else.

`F5` The Data API's `totalRewards` (112,959,343 AVAX at 2026-09-19 11:00 UTC) is 2.53 million AVAX above the reward UTXOs the share records (110,427,761 in the 2026-09-19 capture, 110,485,970 summed live on 2026-09-23). The P-Chain supply counter agrees with the UTXO record: 360,000,000 plus rewards paid plus the potential rewards of open periods differs from the counter by 20,160 AVAX, 0.004%. None of the following reproduces the API's figure: potential rewards of all closed periods (111.02 million), of all accepted periods (115.18 million), rewards paid plus open potential (114.59 million), or the completed validations' reward fields from the API's own validators endpoint (110.55 million). The ledger issues what was paid; the API gap is reported by the check until its definition is found.

`F6` 5,320 `C_RECEIPTS` rows carry no partition date, no hash, and no gas: one placeholder per block without transactions between 2023-11-02 and 2025-03-03. They burn nothing and are not counted as missing fee inputs. The C-Chain produces no empty blocks, so a calendar day without blocks in 2020 burns nothing.

`F7` The Data API lists five C-Chain imports from the X-Chain, 2021-02-10 to 2021-02-12, with fewer consumed UTXOs than the transactions spent: one with none, four with some missing. Their AVAX unlocked falls below the AVAX created, so the API's burn is negative, out of 1,171,886 imports and exports from the first C block to 2026-09-21 in the full walk of 2026-09-23, which burned 2,533.86 AVAX in all. The C-Chain node's `avax.getAtomicTx` returns each signed transaction; decoded, every one consumes exactly what it creates and burns nothing. The atomic dataset keeps the five with a null burn and `c-chain-rpc.atomic-transactions` settles them. Each node response is checked against its hex checksum and against the transaction ID, the CB58 SHA-256 of the signed bytes.

`F8` The Data API key's plan carries a daily allowance besides its 8,000 units a minute. It ran out at 02:10 UTC on 2026-09-24 after about 85,000 block requests and 11,648 atomic pages, and the API then refused every request for about 17 hours ("Rate limit for plan exceeded"). A second source removes the wait: Tenderly's public C-Chain gateway serves `eth_getBlockReceipts` and JSON-RPC batches with no key, which the AvaCloud public node does not. The sum of gas used times effective gas price over a block's receipts equals the Data API's `feesSpent` on all 21 blocks compared, from the 2023 and 2025 gaps, and the gateway answered 240 blocks at 7.7 a second with eight workers and no refusal. Of the other public endpoints tried, publicnode returned no receipts for 2023 blocks, dRPC none for some, and 1RPC, Ankr, and Nodies refuse the method or require a key.

A full-share P-Chain probe found 320 deduplicated transaction hashes outside the two known zero-burn system types with null `BURNED_AVAX`. The dataset preserves these as missing and its check reports them; it never replaces them with `FEE` or zero. The one-day checked sample below has no such missing transaction. Their separate resolution audit appears below.

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

## C EVM daily coverage finding

The checked `snowflake.c-chain-evm-burn-daily` capture for 2026-09-16 is `capture:avalanche-snowflake:2026-09-21T21:01:49Z:17c1b05ae96e`. It returns 679,507,693,734,542,888,415 wei from 672,231 receipts, matching the one-day proof above. Its 80,788 C blocks are contiguous; their declared transaction total equals the number of distinct receipts. The preceding and following day's block numbers connect to this day. Fourteen checks pass with zero findings.

The 2026-09-16 through 2026-09-17 capture, `capture:avalanche-snowflake:2026-09-21T21:02:23Z:be1e97b87f26`, has one finding: Snowflake has no C block 95,492,477 between blocks 95,492,476 and 95,492,478 on 2026-09-17. Snowflake also has no receipts for that block. The [archived public RPC capture](evidence/c-chain-block-95492477/capture/capture.json), `capture:avalanche-c-chain-rpc:2026-09-21T23:11:27Z:539af6d13fa7`, preserves the raw `eth_getBlockByNumber` response and nine `eth_getTransactionReceipt` responses with individual SHA-256 hashes. Its block hash is `0x0cd10168ac91452e3f69e7c3b3d9b8f85a8255dc2740180591a1a451480f6a13`; its timestamp is 2026-09-17 08:09:11 UTC. The checked receipts sum to 1,819,969,183,236,450 wei in EVM fees. All six capture, identity, arithmetic, build, and Parquet checks pass. This is an independently attributed source repair, **not yet an applied daily repair**. The September 17 Snowflake daily amount remains incomplete and must not enter realized supply or a staking ratio. The block-continuity check is necessary even when available block transaction counts equal available receipt counts.

To replay the archived capture without network access:

```bash
uv run --locked avalanche data build c-chain-rpc.receipt-gap-repairs \
  --from data/evidence/c-chain-block-95492477/capture \
  --output data/runs/c-rpc-gap-replay/dataset
uv run --locked avalanche data check c-chain-rpc.receipt-gap-repairs \
  --capture data/evidence/c-chain-block-95492477/capture \
  --dataset data/runs/c-rpc-gap-replay/dataset
```

To capture another missing block, use `avalanche data fetch c-chain-rpc.receipt-gap-repairs --output <new-directory> --param block=<height>`, then build and check that capture. A checked RPC block must be joined to an explicitly absent Snowflake block before a combined-day total can be published.

To reproduce the passing September 16 C EVM source from the repository root with an authorized Snowflake connection:

```bash
uv run --locked --extra snowflake avalanche data fetch snowflake.c-chain-evm-burn-daily \
  --output data/runs/c-evm-example/capture \
  --param start=2026-09-16 --param end=2026-09-17 --timeout 60
uv run --locked avalanche data build snowflake.c-chain-evm-burn-daily \
  --from data/runs/c-evm-example/capture --output data/runs/c-evm-example/dataset
uv run --locked avalanche data check snowflake.c-chain-evm-burn-daily \
  --capture data/runs/c-evm-example/capture --dataset data/runs/c-evm-example/dataset
```

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

The full-history captures and the ledger build are described in [Research data](README.md) under "Build the monetary daily ledger". The one-day proofs above remain the unit evidence behind each source.

## Historical P burn gaps

[`primary-burn-gap-audit.sql`](queries/primary-burn-gap-audit.sql) identifies the 320 unique P transaction hashes whose `BURNED_AVAX` is null and joins their AVAX UTXOs. It deduplicates UTXO IDs and excludes `REWARD=true` outputs: those are rewards minted when a staking period ends, even though their `TRANSACTION_HASH` points back to the original staking transaction. For ordinary transactions, AVAX consumed minus non-reward AVAX created is the burn. The Snowflake query ID is `01c739f2-0208-94e8-000f-0d5e0077100e`.

| Gap class | Transactions | Burn | Evidence |
| --- | ---: | ---: | --- |
| Complete UTXO input/output pairs | 219 | 3,107,308 nAVAX | All have nonnegative input-minus-output. A separate 30-transaction sample with populated `BURNED_AVAX` reproduced that field exactly by the same method; query ID `01c739f7-0208-9403-000f-0d5e00769066`. |
| Genesis validators and chain creations | 77 | 0 nAVAX | All 77 individual Data API transaction responses returned zero AVAX burn; query ID selecting the genesis set: `01c739f5-0208-93b4-000f-0d5e0076703e`. |
| Older imports without consumed UTXOs in the Snowflake share | 24 | 0 nAVAX | All 24 individual Data API transaction responses returned zero AVAX burn. Their output-minus-input cannot be calculated from the incomplete Snowflake UTXO record. |

The total missing-field burn is 3,107,308 nAVAX, or 0.003107308 AVAX. The Data API checks were live probes, not immutable captures. This audit has **not** yet changed the P/X dataset or supplied a historical P burn series. The next implementation must preserve the 101 Data API responses or reproduce their checks before applying these repairs; null is safer than an unaudited zero.
