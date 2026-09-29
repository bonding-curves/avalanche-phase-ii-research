---
title: Call, 2026-10-02
description: "The agenda for the 2026-10-02 call with the Avalanche Foundation, the results it covers, and what was done about each comment on the 2026-09-25 agenda."
date: 2026-09-28
---

The call planned for 2026-09-25 moved to 2026-10-02. This page carries its results, the answers to the Foundation's comments on the agenda of 2026-09-25, and what is new since. The terms used here are defined in [Glossary and Notation](/Reference/Glossary-and-Notation).

## 1. How validators commit, six years of staking

A **commitment** is one staking transaction's period, from its start to its end. The research holds all 57,560 validator commitments and 7,056,798 delegator commitments since September 2020 in one checked table. From Durango to Fortuna the median validator commitment lasted 2.1 weeks, down from about 4.3 weeks before Durango. The typical commitment at that minimum also stakes the minimum, 2,000 AVAX. Short commitments are most of the decisions but little of the capital: 62% to 69% of new validator commitments from Durango to Fortuna, holding 3% to 5% of committed AVAX-days.

Validator commitments by the upgrade period in which they began:

| Upgrade period | Commitments | Nodes | Median duration (weeks) | Stake-weighted median duration (weeks) | Median self-stake (AVAX) | Self-stake committed (million AVAX) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Genesis | 2,951 | 1,218 | 4.4 | 12.4 | 5,000 | 756 |
| Apricot | 11,847 | 2,811 | 4.3 | 8.8 | 2,085 | 1,271 |
| Banff | 3,431 | 1,360 | 4.4 | 9.7 | 2,202 | 390 |
| Cortina | 9,101 | 2,388 | 4.3 | 7.0 | 2,005 | 725 |
| Durango | 12,657 | 2,672 | 2.1 | 4.4 | 2,005 | 731 |
| Etna | 5,179 | 1,762 | 2.1 | 4.4 | 2,000 | 301 |
| Fortuna | 7,775 | 2,012 | 2.1 | 4.2 | 2,000 | 601 |
| Granite | 4,580 | 996 | 3.6 | 4.0 | 14,585 | 890 |

The median duration falls to 2.1 weeks at Durango and holds there until Granite. Weighted by self-stake, the median falls from 7.0 weeks under Cortina to about 4 weeks from Durango on, so large validators shortened too, but less. Under Granite the median self-stake rises from 2,000 to 14,585 AVAX. Self-stake committed sums every commitment's stake, so a validator that renews every two weeks is counted at each renewal. It measures decisions, not stake held at one time. The table is built from the 2026-09-19 capture of 57,521 validator commitments by the [validator rewards notebook](/Reference/Notebooks), which runs it and shows it interactively.

The [staking-periods notebook](/Reference/Notebooks) holds four linked views on one time axis: commitments begun by stake, commitments begun by duration, each node's history as a line coloured by its fee, and the stock of commitments open each week. A selection in one view filters the others.

## 2. Answers to the comments on the 2026-09-25 agenda

| Comment | What was done |
| --- | --- |
| "Do you mean the amount or duration?", on what changed at Durango | Duration. The median validator commitment moves to 2.1 weeks at Durango and stays there until Granite, as the table above shows. The question stands: what changed at Durango that moved most new commitments to the minimum duration? |
| "Interesting idea", and "Sure if it does not result in a huge incremental lift.", on a minimum stake that falls as committed duration rises | It will be evaluated as one more reward mechanism in the parameter sweeps of Milestone 2, through the swappable mechanism interface of [2.8](/Phase-II/Milestone-2/2-8-Collaborative-Mechanism-Design/). It adds a mechanism, not a new model, so the added work is small |
| "Yes, let me follow up with Matias on that.", on introductions to the institutional staking panel and the Summit slides | Waiting on the Foundation |
| Live tracking after Helicon of new nodes' duration choices, old nodes lowering their duration, and the overall duration distribution | Started. The validator set has been captured daily since Helicon, and the first full comparison runs on 2026-09-29, after the first 48-hour cycles have renewed. The three views are next |
| New flow is likely to come from ETFs, so check for a notable NAV increase in the AVAX ETF or ETFs holding AVAX | To be added to the data catalogue |
| Use https://snowpeer.io/delegations to identify BENQI's addresses | Will be used to measure BENQI's share of delegated stake directly, instead of inferring it |

## 3. Helicon, the first week

Helicon activated on 2026-09-22 at 15:00 UTC. It allows validator commitments of 48 hours with automatic renewal and raises the uptime requirement to 90% for validations that start after it. By 2026-09-24, 20 validator commitments had begun under the new rules. Two chose 48 hours, both auto-renewed, both at about 2,000 AVAX. The largest new commitments went the other way: two of about 1.75 million AVAX each, for about 198 days. Delegations keep the 14-day minimum. The first full comparison is added here after its run on 2026-09-29.

## 4. Access to the research

The Foundation's repository now carries this site, the code, both notebooks, and the data. `SETUP.md` in the repository takes a new machine from cloning to running notebooks, and an AI coding agent can follow it as written. The data is attached to the repository's release `v0.1.0`.

## 5. Next steps

1. The Helicon comparison after 2026-09-29, with the three tracking views.
2. Milestone 1 deliverables 1.3 and 1.4, then the Preliminary Validation Report.
3. The ETF and BENQI measurements from the comments above.
4. Introductions for the next interviews, when the Foundation has followed up with Matias.
