---
title: "2026-09-25-sprint-8"
description: "The brief submitted to the Avalanche Foundation in Notion for the call of 2026-09-25, as sent."
date: 2026-09-25
status: submitted
tags: ["staking-duration-and-liquidity", "mechanism-design", "liquid-staking-and-restaking"]
---

# Avalanche economic modeling, 25 September 2026

*As submitted in Notion for the call of 2026-09-25, which moved to 2026-10-02. The text is unchanged. The two images are the per-upgrade table and the linked dashboard the brief refers to, from the notebook screenshots of 2026-09-24.*

Since August we have rebuilt the research from the chain up. We have paused model incrementation in order to focus this sprint on chain analysis and increasing clarity and terminology across all research results. 

## 1. How validators commit, six years of staking

A **commitment** is one staking transaction's period, from its start to its end. We hold all 57,560 validator commitments and 7,056,798 delegator commitments since September 2020 in one checked table. Three results stand out. From Durango to Fortuna the median validator commitment was 15 days. The typical commitment at the minimum also stakes the minimum, 2,000 AVAX. And those short commitments are most of the decisions but little of the capital: 62% to 69% of new validator commitments from Durango to Fortuna, holding 3% to 5% of committed AVAX-days.

![Validator commitments by upgrade period](/Phase-II/Wiki/Briefs/2026-09-25-sprint-8/commitments-by-upgrade.png)

*One column per network upgrade: how many commitments began, on how many nodes, with how much self-stake, and for how long, by count and weighted by stake. The median duration drops to two weeks at Durango and stays there. Under Granite the median self-stake rises from 2,000 to about 14,600 AVAX. The table comes from our 19 September capture, 57,521 validator commitments. The rest of this page uses the 22 September capture, 57,560.*

![The linked dashboard: commitments begun by stake and by duration, validator lifelines, and the active stock](/Phase-II/Wiki/Briefs/2026-09-25-sprint-8/linked-dashboard.png)

*The four views share one time axis: commitments begun by stake, commitments begun by duration, each node's history as a line coloured by its fee, and the stock of commitments open each week. Selecting a region in one view filters the others. You can run it yourself.*

**For you:** what changed at Durango that moved most new commitments to exactly the minimum?

## 2. A minimum stake that depends on duration

Hash has been working on how ACP-49, a 500 AVAX minimum stake, and ACP-273, a 48-hour minimum duration, interact. Adopted together, they would cut the capital a validator commits for its minimum period from 28,000 AVAX-days, 2,000 AVAX for 14 days, to 1,000 AVAX-days, 500 AVAX for 2 days. His proposal is a minimum stake that falls as the committed duration rises, so short commitments stay available to large holders without lowering what each validator puts at stake. The open design question is where the curve should sit at 14 days: 2,000 AVAX, today's floor, or nearer the stake threshold BENQI uses to choose validators for delegation. We are building an explorer so the Foundation can set the curve's parameters itself, and we will share the numbers when they are reconciled with the table above.

**For you:** is this a mechanism you want evaluated alongside the tenure-weighted and fee-funded reward designs?

## 3. Avalanche Summit follow-up

We captured the full public agenda, 69 sessions and 124 speakers, and recorded several sessions, including Matias's economics keynote and the Helicon panel. We will bring what they imply for staking behaviour once we have checked our notes against the recordings. The one session we did not capture is the institutional staking panel with Figment, Blockdaemon, and AVAX One, whose recordings are due about a month after the event.

**For you:** would you introduce us to the operators on that panel, and can the Foundation share the Summit slides for the economics keynote and the Helicon panel?

## 4. Helicon, the first days

Helicon activated on 22 September at 15:00 UTC. We captured the validator set, stakes, rewards, and supply the evening before, and the validator set daily since. By 24 September, 20 validator commitments had begun under the new rules. Two chose 48 hours, both auto-renewed, both at about 2,000 AVAX. The largest new commitments went the other way: two of about 1.75 million AVAX each, for about 198 days. Delegations keep the 14-day minimum. The first full comparison runs on 29 September, when the first 48-hour cycles have renewed, and the new reward curve phases in over 90 days to about 21 December.

**For you:** what adoption of 48-hour and auto-renewed staking does the Foundation expect, and did the test network show anything we should look for?

## 5. Interview with Hansen of BENQI

We interviewed Hansen on 31 August after Daniel's introduction. BENQI runs its liquid staking delegations for 14 to 18 days, for its users' liquidity, and allocates them with bots that weigh each validator's capacity, uptime, duration, and stake. By his account BENQI holds 10% to 12% of all stake, and after Helicon it was leaning toward two-day durations. The delegation minimum is still 14 days, so BENQI could only shorten through validators it runs itself. His figures can be checked on chain, and the largest delegating address in our data holds about half of all delegated stake, consistent with his account.

**For you:** can the Foundation confirm BENQI's addresses, so we measure its share rather than infer it?

## 6. The data record and Milestone 1

Behind every number here is a data layer we built this month: 30 datasets from 11 sources, including the Foundation's Snowflake share, the P-Chain, and Ava Labs' Data API. Each is captured with a receipt, built into a typed table, and checked, and every load verifies the table against its receipt. Our implementation of the protocol's reward formula reproduces the recorded potential reward of 4,438,082 of the 4,438,083 validator and delegator commitments since Durango. The validator set and hourly uptime from Ava Labs' observers are now captured daily, so a record exists that no public source keeps. The Milestone 1 pages for data ingestion, the data manifest, and the staking model's protocol layer are being completed on the research site, and you will receive access to the site, the notebook, and the data.

## 7. Next steps and schedule

1. The Helicon comparison after 29 September.
2. The duration-dependent minimum stake with reconciled numbers and the explorer.
3. Introductions for the next interviews.
4. Access to the site, the notebook, and the data.
5. Reconciling research milestones with the updated modeling framework. 

Next call: 9 October.
