---
title: "The Avalanche Foundation Unveils its Economic Research Agenda"
description: "The Foundation's research agenda names the link between ecosystem output and AVAX value as its central problem, orders the work as measure, capture, and distribute, and gives the funding of validator security as issuance declines its own research stream."
authors: ["Avalanche Foundation"]
published: 2026-07-30
venue: "Avalanche Foundation blog"
url: "https://www.avax.network/about/blog/the-avalanche-foundation-unveils-its-economic-research-agenda"
full_text: "/Phase-II/Wiki/Collections/Essential-Readings/The-Avalanche-Foundation-Unveils-its-Economic-Research-Agenda/Source-Article"
tags: ["fees-and-value-capture", "security-budget", "economic-measurement", "distributional-effects"]
key_terms: ["gross chain product", "gross chain income", "value accrual", "research streams", "emissions", "MEV"]
deliverables: ["1.1", "2.2", "2.3", "2.6", "2.8", "3.1"]
---

The Avalanche Foundation's economic research agenda names the link between ecosystem output and AVAX value as its central problem, orders the work to solve it as measure, capture, and distribute, and gives the funding of validator security as issuance declines its own research stream.

<!-- overview-table:start -->

| | |
| --- | --- |
| **Authors** | Avalanche Foundation |
| **Published** | July 30, 2026 |
| **Source** | Avalanche Foundation blog, [original](https://www.avax.network/about/blog/the-avalanche-foundation-unveils-its-economic-research-agenda), [full text](/Phase-II/Wiki/Collections/Essential-Readings/The-Avalanche-Foundation-Unveils-its-Economic-Research-Agenda/Source-Article) |
| **Topics** | [fees and value capture](/tags/fees-and-value-capture), [security budget](/tags/security-budget), [economic measurement](/tags/economic-measurement), [distributional effects](/tags/distributional-effects) |
| **Key terms** | gross chain product, gross chain income, value accrual, research streams, emissions, MEV |
| **Serves deliverables** | [1.1](/Phase-II/Milestones/Milestone-1/1-1-Data-Ingestion/), [2.2](/Phase-II/Milestones/Milestone-2/2-2-Simulation-Execution/), [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/), [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/), [2.8](/Phase-II/Milestones/Milestone-2/2-8-Collaborative-Mechanism-Design/), [3.1](/Phase-II/Milestones/Milestone-3/3-1-Parameter-Recommendation-Report/) |

<!-- overview-table:end -->

The Foundation published the agenda on its blog on July 30, 2026. It describes work already underway on the Foundation's research team and sets the questions and priorities for the next phase. The Foundation says it publishes the agenda openly so that the community can see how it approaches these problems. Two people are quoted. Matias Antonio, Chief Investment Officer, names the organizing problem: "The connection between ecosystem output and AVAX value accrual is the central problem we are working on." Eric Lu, Lead Economist, says the gross chain product framework "is the foundation this research agenda is built on."

The starting point is that value created by applications and users does not accrue automatically to the token that secures the network. Unless the protocol has a deliberate mechanism to take a share of that value, it passes through the network without strengthening it. The agenda therefore orders its work in three steps. **Measure** comes first, because "a protocol cannot design a capture mechanism for value it has not properly identified." **Capture**, the protocol taking a share of that value for AVAX, comes second. **Distribute**, the routing of captured value back to the token and the ecosystem, comes third.

The central hypothesis is that growth in **gross chain product** (GCP), the value added produced on-chain, "is the backbone that generates capturable protocol value in the form of surplus and income." Routed to AVAX, that value supports validator incentives and network security, and security and healthy economics attract the activity that grows GCP further. The agenda treats security as "a cost paid continuously," not something a protocol ships once. **Gross chain income** (GCI) extends the measure to income that originates outside the on-chain economy but flows to people and balances inside it. The agenda promised a fuller account of GCI from Eric Lu's research, which followed in August.

The work is split into three **research streams**. The first, tokenomics and protocol revenue capture, starts from the fact that protocol revenue is today "predominantly transaction fees from the Primary Network," a narrow base. It asks how to expand that base through fees, **MEV** (the value available from ordering transactions within blocks), and application and L1 revenue sharing, without damaging the activity that creates the value. The second, validator economics and long-term staking incentives, notes that security is "funded primarily through emissions" and that "as the supply budget is drawn down, fee revenue will need to take its place." The third, ecosystem capital allocation, asks how captured value should be distributed, through burns, validator-directed revenue, and other mechanisms. The agenda reports no measurements. Its statements about the present are that revenue is mostly Primary Network fees, that security is paid mostly from emissions, and that the Foundation runs no public grant program.

![Measure, capture, distribute](/Phase-II/Wiki/Collections/Essential-Readings/The-Avalanche-Foundation-Unveils-its-Economic-Research-Agenda/raw/assets/measure-capture-distribute.png)

*The agenda's three steps, as the article draws them. Measure asks how much value the ecosystem creates and channels, using GCP extended to GCI. Capture asks how much of that value accrues to AVAX today and how to capture more. Distribute asks how captured value returns to the token and the ecosystem. Each step depends on the one before it.*

## How it relates to our research

**Our work sits in the second stream.** The [Phase II proposal](/Phase-II/Milestones/Milestone-0/Proposal/) asks under which governance settings Avalanche's staking incentives keep validators and delegators participating across bull markets, bear markets, and competing DeFi yields while keeping the network secure. That is the second stream's question in contract form. The agenda gives the staking model its objective: security is a continuous cost, paid today from a finite issuance budget. Each trajectory in deliverable [2.2](/Phase-II/Milestones/Milestone-2/2-2-Simulation-Execution/) should therefore report the path of that budget, the supply remaining to the 720,000,000 AVAX cap, beside the staking ratio and net inflation. A recommendation in deliverable [3.1](/Phase-II/Milestones/Milestone-3/3-1-Parameter-Recommendation-Report/) can then state how fast it spends the budget.

**The move from emissions to fees is a mechanism question.** The second stream says fee revenue must replace emissions, and the third names validator-directed revenue and burns as routes. Deliverable [2.8](/Phase-II/Milestones/Milestone-2/2-8-Collaborative-Mechanism-Design/) must evaluate alternative reward mechanisms without restructuring the simulation. A reward interface that accepts a share of fee revenue as an input covers that transition. Today every C-Chain fee is burned, and the burn does not reach validators even indirectly. The reward formula reads the P-Chain supply counter, which does not subtract C-Chain burns, as the [ACP-283 page](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-283-Dynamic-Minimum-Gas-Price/) records. A fee share for validators would therefore be a new flow, not a reweighting of an existing one.

**What our data can measure.** The measure step belongs to the Foundation. Our part is the staking side. Deliverable [1.1](/Phase-II/Milestones/Milestone-1/1-1-Data-Ingestion/) ingests every validator and delegation transaction since 2020, the P- and X-Chain burns, and C-Chain fees, as the [data page](/Phase-II/Wiki/Reference/Data) lists. From these the model tracks issuance and burn in AVAX, and the net inflation KPI of deliverable [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/) compares them. The proposal sets that KPI's target as a path toward a crossover where burn exceeds issuance. The [GCI article](/Phase-II/Wiki/Collections/Essential-Readings/From-Gross-Chain-Product-to-Gross-Chain-Income-Where-the-Value-Goes/) sizes the burn in USD, and our data give it in AVAX, the unit in which issuance is paid.

**The return loop is a hypothesis.** The agenda states the loop from AVAX value to security to activity as a hypothesis and does not test it. Until a source supports that return path, the staking model keeps price and activity as external inputs rather than outputs of staking. The sweep in deliverable 2.2 varies market condition and network growth as environment settings, so each result holds under stated conditions rather than predicting them.

**The agenda frames the other readings.** [Value Accrual as Equilibrium](/Phase-II/Wiki/Collections/Essential-Readings/Value-Accrual-as-Equilibrium-How-We-Think-About-AVAX-Tokenomics/), from March, gives the Foundation's economic framework. [Why Avalanche Validator Economics Need a Redesign](/Phase-II/Wiki/Collections/Essential-Readings/Why-Avalanche-Validator-Economics-Need-a-Redesign/), from April, states the second stream's problem. [Measuring Blockchain Economies](/Phase-II/Wiki/Collections/Essential-Readings/Measuring-Blockchain-Economies-Introducing-Gross-Chain-Product/), from May, and the GCI article, from August, are the measure step. [From Static Constants to Dynamic Variables](/Phase-II/Wiki/Collections/Essential-Readings/From-Static-Constants-to-Dynamic-Variables-Where-Avalanches-Economics-Are-Headed/), from July, reads ACP-273, ACP-285, and ACP-283 as the start of managing parameters that were fixed at launch.

**Open questions for the Foundation.** The agenda gives no measure of security adequacy, and deliverable [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/) needs one to mark the parameter regions that under-fund security. Candidates are the stake-weighted cost of acquiring a controlling share, the validator count, and the share of stake whose commitment can end within a day. Which should be the constraint? And of the value captured in future, what share is meant for validators rather than for burns?

## Source

Avalanche Foundation. 2026. The Avalanche Foundation Unveils its Economic Research Agenda. Avalanche Foundation blog, July 30, 2026. <https://www.avax.network/about/blog/the-avalanche-foundation-unveils-its-economic-research-agenda>. Read the [Source Article](/Phase-II/Wiki/Collections/Essential-Readings/The-Avalanche-Foundation-Unveils-its-Economic-Research-Agenda/Source-Article), a reading copy of the article with its figures.
