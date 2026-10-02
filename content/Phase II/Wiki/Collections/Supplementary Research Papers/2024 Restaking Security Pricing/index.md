---
title: "How Much Should You Pay for Restaking Security?"
description: "Chitra and Pai show that services sharing restaked operators can stop a cascade of slashing attacks by paying rewards high enough that operators move stake to where it is needed, without every service having to be overcollateralized."
authors: ["Tarun Chitra", "Mallesh Pai"]
published: 2024-08-01
venue: "arXiv"
url: "https://arxiv.org/abs/2408.00928"
full_text: "/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2024-Restaking-Security-Pricing/Source-Paper"
tags: ["liquid-staking-and-restaking", "security-budget"]
key_terms: ["service pooling", "profit from corruption", "slashing", "participation constraint", "Stackelberg security game", "overcollateralization", "operator costs"]
deliverables: ["1.3", "2.3", "2.6", "2.8"]
---

Tarun Chitra and Mallesh Pai show that services secured by the same restaked operators can stop a cascade of slashing attacks by paying rewards high enough that operators move stake to where it is needed, without requiring every service to be overcollateralized.

<!-- overview-table:start -->

| | |
| --- | --- |
| **Authors** | Tarun Chitra, Mallesh Pai |
| **Published** | August 1, 2024 |
| **Source** | arXiv, [original](https://arxiv.org/abs/2408.00928), [full text](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2024-Restaking-Security-Pricing/Source-Paper) |
| **Topics** | [liquid staking and restaking](/tags/liquid-staking-and-restaking), [security budget](/tags/security-budget) |
| **Key terms** | service pooling, profit from corruption, slashing, participation constraint, Stackelberg security game, overcollateralization, operator costs |
| **Serves deliverables** | [1.3](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/), [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/), [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/), [2.8](/Phase-II/Milestones/Milestone-2/2-8-Collaborative-Mechanism-Design/) |

<!-- overview-table:end -->

Chitra, of Gauntlet, and Pai, of Rice University and SMG, posted the paper to arXiv on 1 August 2024. Its subject is **restaking**, which EigenLayer introduced. Operators of an existing proof-of-stake network lock their stake into a contract and run extra services with it. Each service pays operators **incentives** for meeting its service-level agreement and **slashes** their stake, destroying part of it, if they break its rules. Citing LlamaRisk, the paper puts the capital restaking drew in 2024 alone at over \$20 billion. Its question is how much security each service really needs to buy.

The risk comes from **service pooling**, where one operator uses the same stake for several services, so a slash on one service reduces its stake on all of them. Each service has a **profit from corruption**, the most an attacker can gain by corrupting it, and a **threshold**, the share of its stake that must collude to corrupt it. An attack is valid when it is **profitable**, meaning the gain covers the attackers' stake, and **feasible**, meaning the attackers hold at least the threshold share in every target. Earlier work by Durvasula and Roughgarden showed that one attack can enable the next until the whole network's stake is slashed. They proved that overcollateralization keeps cascades small, but their condition is global: each service's required collateral depends on arbitrarily many other services.

Chitra and Pai change the model in two ways. First, the attacker has **diminishing returns** from attacking several services at once, because buying stake to attack many services pushes up its price. Its profit is a $p$-norm of the services' profits with $p > 1$, so a profitable attack can involve at most on the order of $S^{1/p}$ operators, where $S$ is the number of services. Second, services pay rewards **pro rata** to stake, operators bear costs that include expected slashing, and operators **rebalance** toward services whose yield has risen. Each round, services set rewards, the attacker makes one attack, and operators rebalance. The authors frame this as an online **Stackelberg security game** in which the services lead.

The main result, Theorem 1, is that rewards exist which bound the share of all stake lost after an initial loss of share $\psi$ by $\psi + C/S^{1-1/p}$ for a constant $C$. The loss beyond the initial shock shrinks as services are added. The rewards are **local**: each depends only on a service's own operators and on services that share operators with it. The proof requires each service's reward to exceed its operators' cost by a factor on the order of $K S^{1/p}$, where $K$ is the largest profit from corruption divided by the smallest operator stake. The minimum stake is a parameter the designer controls, as 32 ETH is on Ethereum. With rewards that high, other operators join a service as soon as a slash leaves room, and the cascade stops after the first attack. The stake shared between services must also stay within a band of order $S^{1/p}$, which rewards can enforce by paying less to operators who add overlap. An appendix example shows the cost of the global condition: a service worth at most \$1,000 to an attacker would need stake on the order of \$1 billion, because it shares an operator with a service worth \$1 billion. An algorithm approximates the lowest sufficient rewards. The paper reports no simulations or data, so its results are bounds, not measured magnitudes.

![Figure 1 of the paper: a restaking graph of two services and two operators](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2024-Restaking-Security-Pricing/_page_5_Figure_0.jpeg)

*Figure 1 of the paper: two services (orange) are each secured by the same two operators (blue). Corrupting either service is worth 1, and each operator stakes 1.1, so attacking one service alone loses more than it gains. Because one operator's stake secures both services, attacking both at once gains 2 for a loss of 1.1 under the additive profit of earlier work. The joint attack is feasible if one operator's half of the stake clears the threshold. It does for a Byzantine fault tolerant service, whose threshold is one third, and not for a longest-chain service, whose threshold is one half.*

## How it relates to our research

**Where it enters the model.** Deliverable [2.8](/Phase-II/Milestones/Milestone-2/2-8-Collaborative-Mechanism-Design/) compares reward mechanisms, and each should say what its payment protects against. The paper's **participation constraint** is the first check: an operator stays with a service only while its share of the reward covers its cost, allowing for the dilution its own stake causes. Avalanche fixes each commitment's reward from its stake, duration and consumption rate, so a validator's reward does not shrink as others join. The constraint then reduces to the reward on a validator's own stake covering its operating cost. Each mechanism can be checked for validators at the 2,000 AVAX minimum and at the 3,000,000 AVAX weight cap. **Operator costs** are not recorded on-chain, so the check needs a cost figure from the Foundation or from validators, as [Why Avalanche Validator Economics Need a Redesign](/Phase-II/Wiki/Collections/Essential-Readings/Why-Avalanche-Validator-Economics-Need-a-Redesign/) also requires.

**A candidate measure of security.** Our overview of the Foundation's [research agenda](/Phase-II/Wiki/Collections/Essential-Readings/The-Avalanche-Foundation-Unveils-its-Economic-Research-Agenda/) notes that it gives no measure of security adequacy, and names the stake-weighted cost of acquiring a controlling share as one candidate. The paper's two conditions give that measure a precise form: the stake an attacker must hold to reach the threshold, set against what the attack would earn. It can be computed for each trajectory in deliverable [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/). Settings where the cost falls toward the gain belong on the risk map of deliverable [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/).

**What changes for Avalanche.** The Primary Network is one service secured by one validator set, and Avalanche does not slash stake. A validator that misses the [uptime requirement](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-267-Uptime-Requirement/) keeps its stake and loses that period's reward. The paper's cascades run through slashing across services that share operators, so they do not occur on the Primary Network as it stands. The participation constraint and the attack-cost comparison transfer. The graph results matter only if Avalanche validators come to secure several services with the same stake.

**Rebalancing is slower on Avalanche.** The paper relies on operators that move stake as soon as yields change. It points to liquid restaking protocols, which it says hold over half of restaked capital. On Avalanche the nearest match is BENQI's liquid staking. BENQI told us that it holds 10% to 12% of all stake and allocates delegations with bots that weigh each validator's capacity, uptime, duration and stake. Its delegations run 14 to 18 days, and the delegation minimum is 14 days, so stake moves only when a commitment ends. The staking model in deliverable [1.3](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/) should let an allocator move delegated stake at the end of each commitment, not at every step.

**How it connects to the collection.** The paper cites two others here. [Competitive Equilibria Between Staking and On-Chain Lending](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2020-Staking-and-Lending-Equilibria/) shows that block rewards must be high enough to keep stake securing a network. [Why Stake When You Can Borrow?](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2020-Why-Stake-When-You-Can-Borrow) treats liquid staking. Chitra and Pai extend the first idea from one network to many services: a reward buys a stated level of protection against a stated attacker. The authors leave tests on live networks, and the price risk of rewards paid in a service's own token, to future work.

**Open questions for the Foundation.** What profit from corruption should the risk map assume for the Primary Network? Does the Foundation expect validators to secure other services with the same stake?

## Source

Tarun Chitra and Mallesh Pai. 2024. How much should you pay for restaking security? arXiv:2408.00928, 1 August 2024. <https://arxiv.org/abs/2408.00928>. Licensed CC BY 4.0. Read the [full paper](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2024-Restaking-Security-Pricing/Source-Paper), with all figures.
