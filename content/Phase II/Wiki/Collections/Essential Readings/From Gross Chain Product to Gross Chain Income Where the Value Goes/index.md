---
title: "From Gross Chain Product to Gross Chain Income: Where the Value Goes"
description: "Eric Lu extends gross chain product to gross chain income in three nested levels and shows that AVAX captures only the C-Chain fee burn, a small share of the most cyclical level, while the largest and steadiest level is not captured at all."
authors: ["Siyu (Eric) Lu"]
published: 2026-08-12
venue: "Avalanche Foundation blog"
url: "https://www.avax.network/about/blog/from-gross-chain-product-to-gross-chain-income-where-the-value-goes"
full_text: "/Phase-II/Wiki/Collections/Essential-Readings/From-Gross-Chain-Product-to-Gross-Chain-Income-Where-the-Value-Goes/Source-Article"
tags: ["economic-measurement", "fees-and-value-capture", "security-budget", "market-conditions"]
key_terms: ["gross chain income", "holder yield", "issuer reserve income", "coefficient of variation", "voluntary revenue sharing", "protocol-owned stablecoin"]
deliverables: ["1.1", "2.2", "2.3", "2.6", "2.8", "3.2"]
---

Eric Lu extends gross chain product to gross chain income in three nested levels and shows that AVAX captures only the C-Chain fee burn, a small share of the most cyclical level, while the largest and steadiest level, the yield issuers earn on stablecoin reserves, is not captured at all.

<!-- overview-table:start -->

| | |
| --- | --- |
| **Authors** | Siyu (Eric) Lu |
| **Published** | August 12, 2026 |
| **Source** | Avalanche Foundation blog, [original](https://www.avax.network/about/blog/from-gross-chain-product-to-gross-chain-income-where-the-value-goes), [full text](/Phase-II/Wiki/Collections/Essential-Readings/From-Gross-Chain-Product-to-Gross-Chain-Income-Where-the-Value-Goes/Source-Article) |
| **Topics** | [economic measurement](/tags/economic-measurement), [fees and value capture](/tags/fees-and-value-capture), [security budget](/tags/security-budget), [market conditions](/tags/market-conditions) |
| **Key terms** | gross chain income, holder yield, issuer reserve income, coefficient of variation, voluntary revenue sharing, protocol-owned stablecoin |
| **Serves deliverables** | [1.1](/Phase-II/Milestones/Milestone-1/1-1-Data-Ingestion/), [2.2](/Phase-II/Milestones/Milestone-2/2-2-Simulation-Execution/), [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/), [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/), [2.8](/Phase-II/Milestones/Milestone-2/2-8-Collaborative-Mechanism-Design/), [3.2](/Phase-II/Milestones/Milestone-3/3-2-Scenario-Playbook/) |

<!-- overview-table:end -->

Eric Lu, the Avalanche Foundation's Lead Economist, published the article on the Foundation blog on August 12, 2026. It is the fuller account of gross chain income that the Foundation's [research agenda](/Phase-II/Wiki/Collections/Essential-Readings/The-Avalanche-Foundation-Unveils-its-Economic-Research-Agenda/) promised. It belongs to the agenda's measure step and uses the measurements to size the capture step. It asks the agenda's capture question: "of all this value, how much actually accrues to AVAX today, and how much could?"

The framework follows national accounts. GDP measures value added inside a country, and **gross national income** (GNI) adds the income residents earn from abroad. The article builds three nested levels on that model. **GCP** is the value added produced on-chain, as defined in the [earlier article](/Phase-II/Wiki/Collections/Essential-Readings/Measuring-Blockchain-Economies-Introducing-Gross-Chain-Product/). **GCI** adds **holder yield**, income earned outside the on-chain economy that accrues directly to Avalanche-resident holders of tokenized funds and yield-bearing stablecoins. **GCI-general** adds **issuer reserve income**, the yield that issuers keep on the assets backing the Avalanche-resident float of their tokens. That income exists because of balances held on Avalanche, but it accrues off-chain to the issuers. It is estimated with the 3-month US Treasury bill rate, 3.63% in June 2026, and the appendix states that true reserve yields differ by roughly plus or minus 100 basis points. All levels are monthly USD flows, prefixed N for nominal, and the article states that all figures are estimates, not audited financials.

In June 2026, NGCP was \$3.1M. Holder yield added \$2.7M, for \$5.8M of NGCI. Issuer reserve income added \$6.9M, for \$12.7M of NGCI-general, so the issuer increment alone exceeded all on-chain production that month. Over the full history the ecosystem produced about \$954.8M of NGCP and \$242.8M of issuer reserve income, and channeled \$32.3M of holder yield. Holder yield comes from 7 entities, led by Avant at \$12.4M, BlackRock BUIDL at \$9.0M, and Janus Henderson JAAA at \$6.7M. The two largest issuers account for about 96% of reserve income, \$173.2M and \$59.7M.

Capture runs opposite to size. All C-Chain transaction fees, base and priority, are burned, so they accrue to every AVAX holder through lower supply. Since the start of 2024 the burn totals about \$23.5M, and in June 2026 it was near 3% of NGCP. The burn line uses whole-chain gas, which the appendix calls "a generous view of capture." Holder yield is barely captured, and issuer reserve income not at all. Stability also runs opposite. Over the 30 months from January 2024 to June 2026, NGCP had a **coefficient of variation**, the standard deviation of a monthly series divided by its mean, of 0.51 and swung 7.5x peak to trough. Issuer reserve income had 0.16 and swung 2.1x, and NGCI-general as a whole had 0.29. The article names two capture routes. At the GCP level it proposes **voluntary revenue sharing**, in which protocols route value to the network in exchange for public goods such as shared security, liquidity, and distribution. At the reserve level it points to a **protocol-owned stablecoin** under ACP-67. It notes that ACP-283 lets validators vote on the C-Chain gas price, a lever on the burn, and warns that a levy on application revenue "can discourage usage and development."

![Figure 3 of the article: GCI nested levels from January 2024 to June 2026](/Phase-II/Wiki/Collections/Essential-Readings/From-Gross-Chain-Product-to-Gross-Chain-Income-Where-the-Value-Goes/raw/assets/figure-03.png)

*Figure 3 of the article: monthly NGCP (gray), the holder-yield increment (red), and the issuer-yield increment (orange), stacked from January 2024 to June 2026, all estimates in USD. The dark line near the bottom is the C-Chain fee burn, the one flow AVAX captures today. It is small against every layer. The gray base also moves far more from month to month than the orange layer above it.*

## How it relates to our research

**It gives the outflow for net inflation.** Net inflation, a KPI in deliverable [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/), is issuance less burn, and the proposal's target for it is a path toward a crossover where burn exceeds issuance. The article's monthly burn is that outflow in USD. Deliverable [1.1](/Phase-II/Milestones/Milestone-1/1-1-Data-Ingestion/) ingests daily C-Chain fees, so our data give the same burn in AVAX, the unit in which issuance is paid, and can check the article's line. The burn lowers the realized total supply but not the supply counter that the reward formula reads, as the [ACP-283 page](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-283-Dynamic-Minimum-Gas-Price/) records. It changes net inflation without changing any staking reward.

**It sizes each funding base for mechanism design.** A mechanism that pays validators from fees, from shared protocol revenue, or from reserve yield draws on a level the article measures. The comparison of mechanisms in deliverable [2.8](/Phase-II/Milestones/Milestone-2/2-8-Collaborative-Mechanism-Design/) can state each one's funding as a share of a named level. The gas floor of ACP-283, active since Helicon on 2026-09-22, is a lever on the burn that validators already hold. Its effect depends on how fee demand responds to price, which neither the article nor our model estimates, so it enters as a scenario.

**Steadier funding can be tested as a scenario.** Validator profitability is a proposal KPI: rewards and fees must cover operating costs. A security budget drawn partly from reserve income would vary with a coefficient near 0.16 rather than 0.51. Deliverables [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/) and [3.2](/Phase-II/Milestones/Milestone-3/3-2-Scenario-Playbook/) can test that as a funding scenario, measured by how often validator income falls below a cost threshold. The reserve benchmark is also an outside yield. The Treasury bill rate of 3.63% lies inside the 3% to 10% range of external yields that the sweep in deliverable [2.2](/Phase-II/Milestones/Milestone-2/2-2-Simulation-Execution/) varies. The overview of [Competitive Equilibria Between Staking and On-Chain Lending](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2020-Staking-and-Lending-Equilibria/) already lists treasury bills among the outside yields in the model's portfolio.

**The units and the response must be added for Avalanche.** The levels are monthly USD flows. Staking rewards are AVAX fixed per commitment at its start. Joining the two requires an AVAX price path, and each result has to state which path it assumes. The article also measures opportunity, not response. It gives no estimate of how usage would respond to a levy, and its own example shows that adoption is the hard part of a protocol-owned stablecoin: Hyperliquid's USDH reached 2% of that network's stablecoin balance and was later phased out. A capture mechanism therefore enters the model as a scenario input sized from the article, not as an estimated relation.

**It sizes the fee share the redesign article proposes.** [Why Avalanche Validator Economics Need a Redesign](/Phase-II/Wiki/Collections/Essential-Readings/Why-Avalanche-Validator-Economics-Need-a-Redesign/) proposes fee revenue for validators. This article shows that the fee base is small and cyclical today, so a fee share would be small and volatile at current levels. The larger and steadier base is reserve income, which no mechanism yet reaches. The [ACP-285 community call](/Phase-II/Wiki/Collections/Essential-Readings/ACP-285-Avalanche-Community-Call-Staking-Reward-Curve-Adjustment/) raised the same point: security funding must move from issuance toward value captured from activity, and who receives that value and how it reaches validators is unresolved.

**Open questions for the Foundation.** Which capture route should the model carry first: a share of fees, voluntary revenue sharing, or reserve yield? Of the value captured, what share would go to validators rather than to the burn?

## Source

Siyu (Eric) Lu. 2026. From Gross Chain Product to Gross Chain Income: Where the Value Goes. Avalanche Foundation blog, August 12, 2026. <https://www.avax.network/about/blog/from-gross-chain-product-to-gross-chain-income-where-the-value-goes>. Read the [Source Article](/Phase-II/Wiki/Collections/Essential-Readings/From-Gross-Chain-Product-to-Gross-Chain-Income-Where-the-Value-Goes/Source-Article), a reading copy of the article with all figures.
