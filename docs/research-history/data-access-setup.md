# Data Access Setup

Historical context added 30 October 2026.

The May access note proposed uniform source adapters and cached data for the staking study. Its reported live status and coverage describe that historical setup. Connection identifiers, workstation configuration and an unavailable implementation reference are omitted from this edition.

The phrase “calibrated tanh” is an assertion in the source, which supplies no fitted artifact or validation result for it. The [October model explanation](../review/2026-10-30/modeling.md#4-the-response-to-reward-is-separate-from-habitual-behaviour) separates fitted habits from assumed reward responses. The [data guide](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/data/README.md) describes the delivered catalog, checked runs and input pins.

## Source record

The source records creation on May 1, 2026 4:13 PM and last editing on May 8, 2026 10:09 AM. The timezone is unspecified. Its creator field names Shawn Anderson. The source snapshot is labelled 1 July 2026.

[Redacted source edition](assets/content/Phase%20II/Wiki/Memos/historical/data-access-setup/source-35360ed9-0ab7-80f2-81df-d0a087d3d58d.txt) · [Source identities and hashes](assets/content/Phase%20II/Wiki/Research%20History/manifest.json) · [Research chronology](README.md)

Redacted source edition. Omission markers identify access or development details removed from the text download. Its retained-text hash is distinct from the original export hash.

The reading edition adjusts heading depth, metadata line breaks, currency escapes and historical links. Remaining source wording and equations are preserved.

## Historical text

<!-- historical-original:start -->
### Data Access Setup

Created By: Shawn Anderson  
Creation Time: May 1, 2026 4:13 PM  
Description: Overview of Avalanche Data Access Setup  
Last Edited Time: May 8, 2026 10:09 AM  
Sprint: Sprint 1  
Status: Draft  

### Why this memo exists

---

The Phase 2 simulation needs four kinds of facts about the world:

- on-chain reality,
- AVAX price history,
- the macro opportunity-cost benchmark,
- validator-level metadata.

Each lives in a different place. This document defines an architecture that tracks all four through one uniform interface.

---

#### The architecture in one paragraph

Every external source is wrapped in a `DataSource` adapter (one Protocol, `query(query_id, **params) → Polars DataFrame`). A content-addressed cache wraps any adapter and writes `data/bronze/<source>/<date>/<sha256>.parquet` with a manifest sidecar. Pinned queries live at `queries/<source>/<query_id>.{sql,json}`. CI runs against a fixture-backed `FauxAdapter` so no test needs secrets.

---

#### The four data access points

##### 1. Snowflake — on-chain ground truth

[REDACTED: access account, user, role or workstation configuration]
- Schema: `AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY` — 14 base tables, ~1.95 TB, partition coverage 2020-12-09 → 2026-05-06.
- Coverage: 7 C-Chain (EVM, ~1.71 TB), 3 P-Chain (validator/delegator events), 3 X-Chain (UTXO), 1 reference (`DATA_DICTIONARY`).
- Adapter: `adapters/snowflake.py`.
- Status: **live**, confirmed by yesterday's programmatic schema profile (appendix).

##### 2. CoinGecko — price and supply

- Public REST API, free tier (~30 calls/min, no key needed at Phase 2 scale).
- Adapter: `adapters/coingecko.py` (replaces ad-hoc `scripts/fetch_supply.py`).
- Status: **live**.

##### 3. FRED — opportunity-cost benchmark

- Federal Reserve Economic Data REST API. Calibrated input: US Fed Funds Effective Rate; also Treasury yields and inflation expectations on demand.
- Each team member: free key from [https://fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html).
- Adapter: `adapters/fred.py` (replaces static `data/raw/fed_funds_rate.csv`).
- Status: **live**.

##### 4. Snowpeer — validator-level metadata

- Public API at `https://api.snowpeer.io/v1/*`. Confirmed live endpoints: `/v1/validators`, `/v1/subnets`, `/v1/blockchains` (HTTP 200, JSON `{metadata, validators, ...}`).
- Docs page at `https://api.snowpeer.io/docs` is a JS-rendered SPA; full endpoint catalogue not surfaced via curl. **Foundation question:** auth scheme + docs URL or OpenAPI spec?
- Adapter: `adapters/snowpeer.py` (currently a stub that conforms to the Protocol; drops in once auth + endpoints confirmed).
- Status: **discovered, awaiting docs/auth** (correction to 2026-05-07 stub note).

---

#### Mapping to `data/manifest/schema.yaml`

The manifest defines 14 columns across three tables. Each column has one source of truth:

| Manifest column | Source | Adapter | Status |
| --- | --- | --- | --- |
| `network_state.total_staked_avax` | Snowflake `P_TRANSACTIONS` (sum of active stake) | snowflake | ✅ live |
| `network_state.active_validator_count` | Snowflake `P_TRANSACTIONS` (`AddValidatorTx` minus end events) | snowflake | ✅ live |
| `network_state.active_delegator_count` | Snowflake `P_TRANSACTIONS` (`AddPermissionlessDelegatorTx` minus end events) | snowflake | ✅ live |
| `network_state.validator_uptime_mean` | Snowpeer `/v1/validators` | snowpeer | ⚠️ pending auth |
| `economic_signals.avax_price_usd` | CoinGecko | coingecko | ✅ live |
| `economic_signals.avax_circulating_supply` | CoinGecko | coingecko | ✅ live |
| `economic_signals.staking_reward_rate_apr` | Snowflake-derived (rewards distributed ÷ total staked, time-weighted) | snowflake | ✅ live (compute) |
| `economic_signals.opportunity_cost_rate` | FRED Fed Funds Effective Rate | fred | ✅ live |
| `behavioral_flows.stake_entry_avax` | Snowflake `P_TRANSACTIONS` (gross add events by day) | snowflake | ✅ live |
| `behavioral_flows.stake_exit_avax` | Snowflake `P_TRANSACTIONS` (gross end events by day) | snowflake | ✅ live |
| `behavioral_flows.net_flow_avax` | Derived (`entry − exit`) | (compute) | ✅ live |
| `*.timestamp` (×3) | Provided by source | all | ✅ live |

**13 of 14 columns are unblocked today.** The one gated column is `validator_uptime_mean`; this becomes available the moment Snowpeer auth is sorted.

---

#### How any team member gets access

[REDACTED: access account, user, role or workstation configuration]
[REDACTED: access account, user, role or workstation configuration]
3. Verify with `python scripts/doctor.py`. Green doctor = clear-to-query.

[REDACTED: access account, user, role or workstation configuration]

---

#### Status

- **M2 simulation: data-unblocked.** Snowflake + CoinGecko + FRED cover the calibrated `tanh` model's inputs (Hash, 2026-05-02 memo).
- **Validator-distribution KPIs:** can run from Snowflake-derived counts today; gain richer per-node metadata when Snowpeer auth lands.

#### Open questions for the Foundation

1. **Snowpeer auth + docs URL.** API is live at `api.snowpeer.io/v1/*` but the docs page is JS-rendered. Need either an OpenAPI spec link or an API-key process.
[REDACTED: access account, user, role or workstation configuration]
3. **Programmatic schema profile completeness.** Yesterday's grok-pass deep-profiled 3 of 14 Snowflake tables; the other 11 are row-counts + bytes only. Resolution: overnight re-run on existing role/warehouse.

---

#### Appendix

[REDACTED: unavailable implementation reference]

---

*This document is an immutable record of Phase 2 data-access state as of May 8, 2026.*<!-- historical-original:end -->
