---
title: "1.1 Data Ingestion"
description: "Contract deliverable 1.1: Data Ingestion."
status: review-ready
source: signed-grant-agreement
---

# 1.1 — Data Ingestion

## Contract requirement

Ingest Avalanche-provided historical data (validator/delegator flows, rewards, durations)

## Evidence status

Three datasets from the Avalanche Primary Network Snowflake share cover the four named quantities. Each resolves to a source contract in `data/data-catalog.json`, the exact SQL in `data/queries/`, an immutable capture receipt carrying the Snowflake query ID and result hash, a typed Parquet build, and validation checks. The implementation is client repository commit `4635bf3`. All three were captured live on 2026-09-14 with the full history from genesis.

| Quantity | Dataset | Rows | Coverage | Validation |
| --- | --- | ---: | --- | --- |
| Validator flows and durations | `snowflake.primary-validator-stakes` | 57,438 | 2020-09-10 to 2026-09-14 | 12 checks, 0 findings |
| Delegator flows and durations | `snowflake.primary-delegator-stakes` | 7,043,968 | 2020-09-22 to 2026-09-14 | 12 checks, 0 findings |
| Rewards | `snowflake.primary-staking-rewards` | 7,069,947 | 2020-10-06 to 2026-09-14 | 12 checks, 0 findings |

### Capture receipts

| Dataset | Capture ID | Snowflake query ID |
| --- | --- | --- |
| `snowflake.primary-validator-stakes` | `capture:avalanche-snowflake:2026-09-14T22:22:01Z:dd427e53c8a6` | `01c712fd-0108-7881-000f-0d5e006cd07a` |
| `snowflake.primary-delegator-stakes` | `capture:avalanche-snowflake:2026-09-14T22:21:36Z:a4fe55f0f8da` | `01c712fa-0108-79cd-000f-0d5e006d6046` |
| `snowflake.primary-staking-rewards` | `capture:avalanche-snowflake:2026-09-14T22:28:11Z:e2917b75bd2d` | `01c71301-0108-7afd-000f-0d5e006de00e` |

### Verified structure

- Every one of the 7,043,968 delegations lies inside one validator staking period on its node, and each delegation row names that validator transaction.
- Every reward transaction links to exactly one Primary Network staking period. Rewarded validators never receive less than the potential reward and delegators never more; the difference is the delegation fee transfer.
- Stake weights declared in transaction metadata equal the summed staked UTXOs wherever UTXO rows exist.

### Known gaps

- The share lacks UTXO rows for 973 rewarded delegations and for 124 staking transactions. They are counted in the build summaries, not removed or imputed.
- Uptime is not observable beyond the protocol's rewarded flag.
- Captures are working data and are not committed. The `data/README.md` guide reproduces them with authorized Snowflake access.

This is internal review-ready evidence. It does not establish Avalanche acceptance.

[Signed Grant Agreement](/Phase-II/Milestone-0/Signed-Grant-Agreement)
