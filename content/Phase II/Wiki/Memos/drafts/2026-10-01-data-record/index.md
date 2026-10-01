---
title: "2026-10-01-data-record"
description: "The data record behind every number: 66 checked datasets from 15 sources. When the Snowflake share stopped on 22 September, a second source rebuilt from the P-Chain took over, and it agrees with the share on every overlapping row. What Milestone 1 delivers."
date: 2026-10-01
status: draft
deliverables: ["1.1", "1.2", "1.3"]
tags: ["economic-measurement", "issuance-and-rewards", "validator-economics"]
---

# The data record: when the Snowflake share stopped, the chain took over, and the two agree

## Finding

Every number in these memos comes from one data record: 66 datasets from 15 sources, each captured with a receipt, built into a typed table, and checked. Every time a table is loaded, it is checked against its receipt. On 22 September, the Foundation's Snowflake share stopped loading. Its P-Chain tables end that morning, UTC, and it has not updated since. We already had a second source by then: every P-Chain block, read from public nodes and rebuilt into the same tables. Where the share and our rebuild overlap, they agree on every row we compared. So the record now runs from genesis to today without depending on any one provider.

## The record

| Table | What it holds | How it is checked | Run |
| --- | --- | --- | --- |
| Staking-period log | 7,131,321 commitments, 57,651 validators and 7,073,670 delegations, from genesis to 30 September 02:28 UTC | Our implementation of the protocol's reward formula reproduces the recorded potential reward of 4,455,120 of the 4,455,121 commitments that start on acceptance, which since Durango is every commitment | `staking-periods-2026-09-30` |
| Monetary ledger | Supply, rewards paid, burns by chain, and active stake, for 2,210 complete days from 10 September 2020 to 28 September 2026 | Each day's opening supply is the previous close, and close equals open plus rewards less burns. The P-Chain's own supply counter agrees within 0.0045%, and delegation fees held until validators' periods end explain nearly all of the difference | `avax-monetary-daily-2026-09-30` |
| Rebuild across the seam | Validator and delegator stakes, rewards, supply readings, and burns after the share stopped | Before the share stopped, the rebuild matches the share on 111 validator stakes, 12,498 delegations, 10,199 reward payments, and 12,609 supply readings, with no value different | `seamed-*-2026-09-30` |
| Validator set | One snapshot a day from the P-Chain since 19 September, and from Ava Labs' Data API since 22 September | Each snapshot is checked when it is captured | `current-validators-2026-10-01`, `validators-active-2026-10-01` |
| Hourly uptime | 282,656 node-hours for 627 nodes, 10 September to 1 October, from Ava Labs' Builder Hub | Every node-hour once, and agreement with the earlier captures checked daily | `validator-uptime-hourly-2026-10-01` |
| Helicon commitments | Every validator cycle since activation, including auto-renewals | Every cycle starts after activation and lasts at least the 48-hour minimum | `helicon-commitments-2026-10-01` |

The P-Chain rebuild, the validator set, uptime, the Data API supply snapshot, and the ETF holdings now refresh every day without anyone running them. A separate check reads the newest record of every source each morning and reports any that stops.

## What the record has already caught

Outside figures change without notice, and a daily record shows when.

- **The Snowflake share** stopped on 22 September, and nothing reported it. The daily check now does.
- **The Metrics API's** staking series, validator and delegator counts and weights, have no point after 31 August.
- **Builder Hub** cut its uptime window from about 332 hours to about 175 between 27 and 29 September. It also restated 74% of the hours it still showed, by small amounts. We keep the newest value for each hour and mark the restated ones.
- **The Data API's** reported total of staking rewards matched what the chain paid plus what open stakes had earned, to 0.0014%, on 19 September. From about 20 September it has grown about 11,000 AVAX a day more slowly than that sum, and it was 100,092 AVAX lower on 29 September. Its total stake still matches the chain exactly, so its index is current. We report the gap and do not use the figure.

None of these changes enters the record unnoticed. Each figure is rebuilt from the chain, compared against it, or marked where its source changed it.

## What it means

The model work that follows can rest on chain data alone. The inputs for the Milestone 2 model will be frozen on 7 October as one named set: each table at one run, with its file's hash. Every model run will carry a receipt that names the code, the settings, those inputs, its seeds, and its checks, so any result can be rebuilt exactly.

## Milestone 1

Milestone 1 covers data ingestion, the data manifest, and the staking model's protocol layer. Its three pages are drafted on the research site:

- **Data ingestion** shows what was captured, from where, and with what coverage, including the seam where the rebuild takes over from the share.
- **Data manifest** lists every dataset with its source, how it is requested, and its size.
- **Protocol layer** sets out the protocol rules the staking model reproduces, such as the reward formula checked in the first row above.

You will receive access to the site, the notebook, and the data with them.

## What is open

1. Whether the Snowflake share resumes, and whether a reload would change any day it already held.
2. How the Data API computes its rewards total, and why it changed around 20 September.
3. A second capture of the Helicon state on 21 December, when the new reward curve has fully phased in. It is scheduled.

**For you:** can the Foundation ask whoever runs the Snowflake share why it stopped loading on 22 September, and whether it will resume? Our rebuild covers every table we use, but the share remains the reference for history.
