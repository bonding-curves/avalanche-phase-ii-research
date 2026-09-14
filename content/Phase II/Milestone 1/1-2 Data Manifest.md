---
title: "1.2 Data Manifest"
description: "Contract deliverable 1.2: Data Manifest."
status: review-ready
source: signed-grant-agreement
---

# 1.2 — Data Manifest

## Contract requirement

Documentation of sources, transformations, quality metrics

## Evidence status

The manifest is machine-readable and rendered by the client command line. It covers the three Snowflake staking datasets attached to [1.1](1-1%20Data%20Ingestion) and the Snowpeer network summary, at client repository commit `4635bf3`.

| Manifest element | Where it lives |
| --- | --- |
| Sources, authority, authentication, and reuse status | `data/data-catalog.json` |
| Queries, parameters, and observed provider semantics | `data/data-catalog.json` and `data/queries/*.sql` |
| Field names, types, units, and derivations | `data/data-catalog.json`, rendered by `avalanche data manifest --json` |
| Transformations | The SQL text and the typed build in `src/avalanche_research/snowflake.py` |
| Quality checks | `avalanche data check`, which verifies hashes, query text, field types, and the domain checks listed below |
| Quality results and coverage | Each build receipt (`build.json`) and check result |

### Domain checks

| Dataset | Checks beyond hashes, query text, and field types |
| --- | --- |
| `snowflake.primary-validator-stakes` | Unique transaction hashes, acceptance window, time ordering, duration 14 to 365 days, stake 2,000 to 3,000,000 AVAX, delegation fee 2% to 100%, staked-UTXO reconciliation |
| `snowflake.primary-delegator-stakes` | The same with stake 25 to 3,000,000 AVAX, plus validator period containment |
| `snowflake.primary-staking-rewards` | Unique reward and staking hashes, reward window, staking period link, reward timing, reward status agreement, validator and delegator fee direction |

### Quality results, 2026-09-14 captures

| Dataset | Rows | Distinct nodes | Rows without UTXO rows | Rows with reward status pending |
| --- | ---: | ---: | ---: | ---: |
| `snowflake.primary-validator-stakes` | 57,438 | 7,640 | 1 | 594 |
| `snowflake.primary-delegator-stakes` | 7,043,968 | 5,093 | 123 | 30,865 |
| `snowflake.primary-staking-rewards` | 7,069,947 | 7,628 | 973 rewarded periods | 0 |

Units are preserved as nAVAX integers with AVAX conversions derived once. Delegation fees are preserved in millionths with the rate derived once. Every dataset resolves to source, exact SQL, raw hash, transformation, schema, quality results, and capture time.

This is internal review-ready evidence. It does not establish Avalanche acceptance.

[Signed Grant Agreement](/Phase-II/Milestone-0/Signed-Grant-Agreement)
