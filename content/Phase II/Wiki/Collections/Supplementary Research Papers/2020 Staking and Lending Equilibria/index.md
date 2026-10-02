---
title: "Competitive Equilibria Between Staking and On-Chain Lending"
description: "Chitra shows that when on-chain lending pays more than staking, rational token holders move stake out of validation and weaken a proof-of-stake network's security."
authors: ["Tarun Chitra"]
published: 2020-11-30
venue: "*Cryptoeconomic Systems*"
url: "https://doi.org/10.21428/58320208.9ce1cd26"
full_text: "/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2020-Staking-and-Lending-Equilibria/Source-Paper"
tags: ["security-budget", "issuance-and-rewards"]
key_terms: ["outside option", "block reward", "mean-variance investor", "utilization curve", "phase transition", "commitment"]
deliverables: ["1.3", "2.1", "2.2", "2.3", "2.6"]
---

Tarun Chitra shows that when on-chain lending pays more than staking, rational token holders move their tokens out of validation and weaken a proof-of-stake network's security, and that the block reward schedule decides whether this happens.

<!-- overview-table:start -->

| | |
| --- | --- |
| **Authors** | Tarun Chitra |
| **Published** | November 30, 2020 |
| **Source** | *Cryptoeconomic Systems*, [original](https://doi.org/10.21428/58320208.9ce1cd26), [full text](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2020-Staking-and-Lending-Equilibria/Source-Paper) |
| **Topics** | [security budget](/tags/security-budget), [issuance and rewards](/tags/issuance-and-rewards) |
| **Key terms** | outside option, block reward, mean-variance investor, utilization curve, phase transition, [commitment](/Phase-II/Wiki/Reference/Glossary-and-Notation) |
| **Serves deliverables** | [1.3](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/), [2.1](/Phase-II/Milestones/Milestone-2/2-1-PSUU-Infrastructure/), [2.2](/Phase-II/Milestones/Milestone-2/2-2-Simulation-Execution/), [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/), [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/) |

<!-- overview-table:end -->

In a **proof-of-stake** network, security is bought with capital. Validators lock tokens as collateral, and the protocol pays them a **block reward** for doing so. Chitra's starting point, posted by Gauntlet in January 2020 and published in *Cryptoeconomic Systems* that November, is that this ties security to the **cost of capital**. A proof-of-work miner cannot quickly move a data center into another use. A staker can move tokens with one transaction. The rise of **decentralized finance**, and of lending protocols such as Compound in particular, gave stakers an alternative with a visible yield. The paper asks what happens to staked supply when that alternative pays more than staking.

The model gives each token holder a choice between two assets, staking and lending. Each holder is a **mean-variance investor** in the sense of Markowitz: it weighs expected return against risk, with its own risk tolerance, and rebalances its portfolio every block. The staking yield is the block reward divided by total stake, so it falls as more tokens are staked. The lending yield follows a Compound-style **utilization curve**, so it rises as more tokens are borrowed. The two yields feed back on each other through the holders' choices. The paper compares **monetary policies**, from deflationary block rewards that shrink over time to polynomial and exponential inflation.

The main result is a **phase transition** in monetary policy. Under deflationary rewards, tokens move from staking to lending in large swings that the paper compares to a bank run, even though no holder coordinates with any other. Under inflationary rewards, staking dominates and the spread between borrowing and lending rates stays tight. Security therefore depends on keeping the staking reward above expected lending yields by a margin set by the spread of holders' risk preferences. Proofs cover a simplified two-state version. Agent-based simulations with 512 holders over 250,000 blocks, averaged over 100 random seeds per setting and using Compound's rate parameters, confirm the pattern. The paper's broader claim is that a threat model built only on malicious validators misses this risk, because the harm comes from ordinary yield-seeking.

![Figure 1 of the paper: share of token supply staked and lent over time, in two simulations](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2020-Staking-and-Lending-Equilibria/_page_2_Figure_0.jpeg)

*Figure 1 of the paper: the share of all tokens that is staked (blue) and lent (orange) as a simulation runs, block by block. In the top run, lending pays at the rates Compound used. Staking at first dominates, with close to 90% of supply staked, but after about 70,000 blocks holders move into lending until about 80% of supply is lent. In the bottom run, lending pays up to 75%, and staked supply falls to zero. No holder coordinates with any other. Each one only moves toward the better yield, and together they drain the stake that secures the network. Each run has 512 holders.*

## How it relates to our research

**Where it enters the model.** The Foundation has asked that our staking model treat a validator's **outside option**, what the same AVAX would earn elsewhere, as a portfolio of alternative uses of capital rather than lending alone. This paper is the first formal treatment of staking as one asset in such a portfolio, and its mean-variance weights extend naturally to more than two assets. One block of the model in deliverable [1.3](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/) can therefore hold staking, on-chain lending, treasury bills, and liquid staking yields together, with each holder's risk tolerance drawn from a distribution as Chitra draws them.

**What changes for Avalanche.** Chitra's holders can leave staking at any block. Avalanche stake is locked for a fixed **commitment** of 48 hours to one year, so giving up liquidity costs more the longer the commitment. The Foundation's [validator rewards article](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/) measures that cost at about 0.8 percentage points of annualized yield per extra week. Our model keeps Chitra's portfolio choice but makes it only at the end of a commitment, and adds a **duration term** so that a longer commitment must pay more to be chosen. The paper also has no transaction fees and a fixed number of holders, and the Avalanche model needs both fees and entry and exit of validators and delegators.

**Why the deflationary result matters here.** Avalanche's reward rate is scaled by a **remaining-supply factor**, so rewards per unit of stake fall as supply approaches the 720 million AVAX cap. Over time Avalanche therefore moves toward the declining-reward setting in which Chitra finds stake least stable. This is the same concern the Foundation raises in [Why Avalanche Validator Economics Need a Redesign](/Phase-II/Wiki/Collections/Essential-Readings/Why-Avalanche-Validator-Economics-Need-a-Redesign/), and the paper gives it a testable form: security holds only while the staking reward clears the best outside yield by a margin.

**How we will use it in the sweeps.** In deliverables [2.1](/Phase-II/Milestones/Milestone-2/2-1-PSUU-Infrastructure/) to [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/), the best outside yield enters as an input the Foundation does not control, and the **spread between the staking reward and the best outside yield** is reported beside each parameter setting. Proposals that lower short-duration rewards, such as [ACP-285](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-285-Minimum-Consumption-Rate/), narrow that spread for short commitments, so the model should show where each proposal brings it close to zero. The region where it turns negative belongs on the risk map of deliverable [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/).

**Liquid staking weakens the trade-off.** On Avalanche a holder does not have to choose between staking and lending in the way the paper assumes. A **liquid staking token** earns the staking reward and can be lent at the same time. BENQI told us that its liquid staking delegations run 14 to 18 days, a length set for its users' liquidity. The model therefore needs liquid staking as a separate route with its own duration choice, not as a third asset in Chitra's portfolio. Related work in this collection extends the same question: [Restaking Security Pricing](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2024-Restaking-Security-Pricing/) prices stake reused across services, and [The Tokenomics of Staking](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2025-The-Tokenomics-of-Staking) treats staking as a choice against holding liquid tokens in equilibrium.

**Open questions for the Foundation.** Which outside yields should the portfolio include, and from which markets? Should holders of liquid staking tokens be modeled as stakers, as lenders, or as both?

## Source

Tarun Chitra. 2020. Competitive equilibria between staking and on-chain lending. *Cryptoeconomic Systems*, published 30 November 2020. DOI [10.21428/58320208.9ce1cd26](https://doi.org/10.21428/58320208.9ce1cd26). Preprint arXiv:2001.00919. Read the [full paper](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2020-Staking-and-Lending-Equilibria/Source-Paper), with all figures.
