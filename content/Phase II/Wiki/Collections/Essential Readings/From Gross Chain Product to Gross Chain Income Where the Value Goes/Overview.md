---
title: Overview
description: "Eric Lu extends gross chain product to gross chain income in three nested levels and shows that AVAX captures only the C-Chain fee burn, a small share of the most cyclical level."
---

Read the [source](/Phase-II/Wiki/Collections/Essential-Readings/From-Gross-Chain-Product-to-Gross-Chain-Income-Where-the-Value-Goes/Source-Article).

![GCI nested levels](/Phase-II/Wiki/Collections/Essential-Readings/From-Gross-Chain-Product-to-Gross-Chain-Income-Where-the-Value-Goes/raw/assets/figure-03.png)

*Monthly NGCP, the holder-yield increment, and the issuer-yield increment from January 2024 to June 2026, all estimates in USD. The dark line near the bottom is the C-Chain fee burn, the one flow AVAX captures today.*

## Question

Eric Lu published the article on August 12, 2026, as the measurement step of the Foundation's measure, capture, distribute sequence. It asks: "of all this value, how much actually accrues to AVAX today, and how much could?"

## Method

The article builds three nested levels on the model of GDP and gross national income.

1. **NGCP**, nominal gross chain product, is monthly on-chain value added in USD: onchain profit plus transaction fees.
2. **NGCI** adds **holder yield**, income earned off-chain that accrues directly to Avalanche-resident holders of tokenized funds and yield-bearing stablecoins.
3. **NGCI-general** adds **issuer reserve income**, the yield issuers retain on reserves backing the Avalanche-resident float. It is benchmarked to the 3-month US Treasury bill, 3.63% at June 2026. The appendix states that true reserve yields differ by roughly plus or minus 100 basis points.

Cyclicality is compared with the coefficient of variation, the standard deviation of a monthly series divided by its mean. Only full months are used.

## Main results

1. June 2026: NGCP was $3.1M. Holder yield added $2.7M, giving $5.8M of NGCI. Issuer reserve income added $6.9M, giving $12.7M of NGCI-general. The issuer increment alone exceeded NGCP.
2. Over the full history: $954.8M of NGCP, $32.3M of holder yield, and $242.8M of issuer reserve income.
3. Capture: the C-Chain burned about $23.5M of fees since the start of 2024. In the latest month the burn was near 3% of NGCP. The burn line uses whole-chain gas, which the appendix calls "a generous view of capture."
4. Holder yield across 7 entities is led by Avant at $12.4M, BlackRock BUIDL at $9.0M, and Janus Henderson JAAA at $6.7M.
5. Cyclicality over the 30 months from January 2024 to June 2026, shown in Figure 5: NGCP had a coefficient of variation of 0.51 and swung 7.5x peak to trough. Issuer reserve income had 0.16 and swung 2.1x. NGCI-general as a whole had 0.29.
6. The two largest issuers account for about 96% of reserve income, $173.2M and $59.7M.

The article names two capture routes: voluntary revenue sharing at the GCP level, and a protocol-owned stablecoin under ACP-67 at the reserve-income level. It notes that ACP-283 makes the C-Chain gas price adjustable by validator vote, a lever on the burn.

## What it gives this research

1. The burn series for deliverable [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/). Net inflation is issuance less burn. The article's monthly burn is the outflow the KPI needs, once converted from USD to AVAX.
2. The size of each base for deliverable [2.8](/Phase-II/Milestones/Milestone-2/2-8-Collaborative-Mechanism-Design/). A mechanism that pays validators from fees, from shared protocol revenue, or from reserve yield draws on a base the article measures. A comparison of mechanisms can state each one's funding as a share of a named level.
3. A funding scenario for deliverables [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/) and [3.2](/Phase-II/Milestones/Milestone-3/3-2-Scenario-Playbook/). A security budget drawn partly from reserve income would vary with a coefficient near 0.16 rather than 0.51. That difference can be tested as a scenario on how often validator rewards fall below a threshold.

## Limits and open questions

All figures are estimates, not audited financials, as the mandatory caveats state. Issuer income rests on a single Treasury-bill proxy, some holder-yield series are understated where price history is short, and one product's assets are backed out of its fee schedule.

The article measures opportunity, not response. It states that a levy on application revenue "can discourage usage and development" and that capture from holders "can be distortionary," but gives no estimate of how usage responds to either. A capture mechanism therefore enters the staking model as a scenario input with its size taken from the article, not as an estimated relation.

The levels are monthly USD flows. Staking rewards are AVAX fixed per commitment at its start. Joining them requires an AVAX price path, and the research has to state which price path each result assumes.
