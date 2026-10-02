---
title: "Source Paper: How Much Should You Pay for Restaking Security?"
description: "A full replica of the paper, converted from its openly licensed source with figures and equations."
licence: "Creative Commons Attribution 4.0 International (CC BY 4.0)"
source_url: "https://arxiv.org/abs/2408.00928"
captured: 2026-09-29
---

*Tarun Chitra, Mallesh Pai (2024). How Much Should You Pay for Restaking Security?. arXiv:2408.00928. [https://arxiv.org/abs/2408.00928](https://arxiv.org/abs/2408.00928). Licence: Creative Commons Attribution 4.0 International (CC BY 4.0) Converted on 2026-09-29 from `the source` with marker, figures and equations included. Check a passage against the original before quoting it.*

# How much should you pay for restaking security?

Tarun Chitra Gauntlet tarun@gauntlet.xyz

Mallesh Pai Rice University and SMG mallesh.pai@mechanism.org

August 5, 2024

#### Abstract

Restaking protocols have aggregated billions of dollars of security by utilizing token incentives and payments. A natural question to ask is: How much security do restaked services really need to purchase? To answer this question, we expand a model of Durvasula and Roughgarden [\[DR24](#page-19-0)] that includes incentives and an expanded threat model consisting of strategic attackers and users. Our model shows that an adversary with a strictly submodular profit combined with strategic node operators who respond to incentives can avoid the large-scale cascading failures of [\[DR24](#page-19-0)]. We utilize our model to construct an approximation algorithm for choosing token-based incentives that achieve a given security level against adversaries who are bounded in the number of services they can simultaneously attack. Our results suggest that incentivized restaking protocols can be secure with proper incentive management.

### 1 Introduction

Decentralized networks, such as blockchains, rely on a combination of cryptography and economic incentives to corral disparate operators to maintain network services. These operators, often referred to as node operators, bear the cost of running infrastructure and maintaining high network availability to guarantee network service level agreements. In exchange, these operators receive a combination of a fixed subsidy (often termed a block reward) and a variable fee that is accrued based on network usage.

In these systems, properties such as safety (*i.e.* valid transactions cannot be removed from the network) and liveness (*i.e.* the network does not halt) are dependent on how many resources are committed by network participants. For instance, Byzantine Fault Tolerant (BFT) Proof of Stake (PoS) networks guarantee safety and liveness only if at most <sup>1</sup>/<sup>3</sup> of resources committed by node operators are adversarial and/or dishonest. As such, these networks need to continually pay fixed and variable payments to ensure that there is sufficient honest stake. As protocols often compete with applications built on top of blockchains (such as decentralized finance or DeFi) for stake, there is a minimum payment needed to achieve security (see, *e.g.* [\[Chi21;](#page-18-0) [CK22](#page-18-1); [CE20\]](#page-18-2)). This has led to a state where blockchains are continually searching for new forms of yield to give to node operators in order to ensure secure, orderly operation.

Restaking. As blockchains have evolved, there have been various forms of fees paid to node operators. The majority of fees earned by node operators are transaction fees that users pay in order to have their transactions included within a block. These fees are generally fixed and not proportional to the value of the transactions involved. Other fee mechanisms unique to blockchains such as miner extractable value (MEV) [\[CK22](#page-18-1); [KDC23](#page-19-1); [Dai+20\]](#page-18-3) also exist. These forms of fees involve strategic users taking advantage of non-strategic user transactions and generally provide additional yet highly variable yield.

A newer form of yield for node operators is *restaking*, pioneered by Eigenlayer [\[Eig23;](#page-19-2) [Eig24\]](#page-19-3). Restaking involves node operators of an existing PoS network (referred to as the *host network*) locking their stake into a smart contract. The node operators provide services to the smart contract that are in addition to the services the host network requires (*e.g.* ensuring transaction validity, voting on block finalization, etc.). If the node operator does not meet a covenant, their stake that is locked in the contract on the host network is slashed. On the other hand, if the node operator provides services within a service-level agreement (SLA) defined by the contract, they receive incentive payments. To demonstrate the diversity of restaking services, note that currently live Eigenlayer actively validated services for price oracles, Zero Knowledge proof generation, rollup sequencing, decentralized exchanges, and AI co-processing [\[u–24\]](#page-20-0).

To illustrate payments and slashing, consider a price oracle service that requires node operators to provide a price from an off-chain venue (*i.e.* Coinbase) on every block. If the node operator provides a price, they receive a portion of the revenue that price oracle smart contract receives. On the other hand, if the node operator doesn't tender a price, then the operator can have their stake slashed. Note that this slashing rule is in addition to existing host network slashing rules (*i.e.* an Ethereum or Solana node operator is slashed for not posting a block during a slot they are the proposer). This shows that restaking can be thought of as a node operator earning extra fees by opting into excess risk from a service's slashing rules.

Risks of Restaking. Restaking has attracted over \$20 billion in capital in 2024 alone [\[Lla24\]](#page-19-4), serving as one of the fastest capital formation events within the history of cryptocurrency. Much of this capital formation has arisen because long-term Ethereum holders view restaking as a means for enhancing their PoS yield with minimal excess risk. However, restaking poses extra risks to users due to services' slashing rules. A specific novel risk arises from service pooling. Service pooling refers to a single operator using the same stake to operate multiple services. For instance, a node operator might lock up 100 ETH of stake into k services. If each service provides yield γ<sup>1</sup> , . . . , γ<sup>k</sup> , then the node operator can earn up to P i γ<sup>i</sup> yield. On the other hand, if the user is slashed on *any* service, then their total staked quantity goes down for all services. If the same node operator is slashed on service i for 10 ETH, then the

operator has 90 ETH staked on all k services.

Pooling shares slashing risk across all services with common node operators, which implies that services themselves indirectly bear risk from other services. The worst-case outcome is a cascading attack. This is where slashes in one service impacts other services that are pooled via common node operators. If a malicious node operator is willing to be slashed in order to earn a profit from corrupting the network, groups of services can be attacked sequentially until the entire network's stake is slashed. The seminal work [\[DR24](#page-19-0)] demonstrated that this can happen given an adversary can attack arbitrarily large groups of services and if the network is not sufficiently overcollateralized.

Prior Work. The Eigenlayer restaking network [\[Eig23,](#page-19-2) App. B] was the first to address restaking risks. This paper focused on computing how much honest stake is needed to secure a service s that has a maximum profit from adversarial behavior, π<sup>s</sup> . While this paper provides a polynomial time algorithm for detecting if a network can be exploited given π<sup>s</sup> , it does not provide any formal guarantees on the losses of stake under attacks.

Subsequent work [\[DR24\]](#page-19-0) considered the problem of measuring cascades by representing restaking networks with bipartite graphs. These graphs represent the relationship between services and node operators. Properties of this graph and π<sup>s</sup> can lead to cascades, with [\[DR24\]](#page-19-0) constructing an infinite family of graphs that have a worst-case cascade (*i.e.* all of the stake is destroyed via correlated slashes). On the other hand, the paper proves that if the network is overcollateralized in a particular sense (see §[2\)](#page-4-0), then the size of the largest cascade decays. However, it should be noted that the overcollateralization is global, *i.e.* services require overcollateralization that depends on arbitrarily numbers of other services.

Finally, there have been a number of works on analyzing the effect of token incentives to impact PoS network security. These papers analyzed concentration of wealth effects [\[Fan+19\]](#page-19-5), competition between PoS and application yield [\[Chi21\]](#page-18-0), and the principalagent problem with liquid staking (which are also popular within restaking) [\[CE20;](#page-18-2) [TZ23\]](#page-20-1). These works are related to this paper as they analyze the interaction between economic incentives and network security.

### 1.1 Our results

We expand the model of [\[DR24\]](#page-19-0) in two main ways:

- 1. Inclusion of incentives paid by services to attract node operators
- 2. Expand the types of adversarial attacks possible

Realistic Adversaries. We show that for a realistic adversary, which we term a *strictly submodular adversary*, one can choose rewards to ensure that cascades are bounded. These adversaries realize decreasing marginal returns for attacking larger sets of services. Bounded cascade sizes imply adversaries cannot execute a sequence of attacks that leads to the entire network being slashed. Such a bound is important for analyzing how a restaking network implicitly affects the security of its host PoS network. We show that for such an adversary, the length of a cascade degrades to the minimum length as the number of services grows to infinity. Our results provide a more optimistic view on security against cascading failures as it is substantially weaker than a global overcollateralization condition (*i.e.* γ-security [\[DR24,](#page-19-0) Thm. 1]; see Appendix [B\)](#page-21-0).

We note that our model of strictly submodular adversaries represents a realistic model where the cost of attacking multiple services grows as more services are attacked concurrently. For instance, if an attacker needs to aggregate stake across k services and has to purchase at least σ units of stake for each service, they will push the price up of the staking asset in order to execute the attack. This, in particular, will lower the profitability of the attack as k increases, potentially restricting the number of services that can be attacked simultaneously.

Incentives and Strategic Operators. Our model relies on more than strictly submodular adversaries. We also require node operators to rebalance or adjust which services they are restaking with. Node operators are modeled as strategic, adjusting their allocation to services based on the expected profit they receive via service incentive payments. This is also realistic given that liquid restaking protocols (who make up over 50% of restaked capital [\[Lla24\]](#page-19-4)) employ strategies to optimize their allocation to services [\[Li24](#page-19-6); [NC24](#page-19-7); [LB24\]](#page-19-8).

These incentive payments can be viewed as analogous to block rewards that are paid out as a subsidy to attract stakers in PoS networks. Akin to work on PoS networks that shows that block rewards need to be sufficiently high to ensure that networks have sufficient stake to avoid attacks [\[Chi21\]](#page-18-0), we demonstrate that with sufficiently high rewards, one can ensure that node operators rebalance in a manner that reduces cascades. We note that services and liquid restaking tokens on Eigenlayer have already paid out tens of millions of dollars of incentives far [\[Lla24;](#page-19-9) [Pat24\]](#page-19-10).

Threat Models and Algorithms for Optimal Incentives. One can view the choice of a submodular adversary as a choice of threat model for feasible attacks. The main model of strictly submodular adversary studied within this paper is the ℓ<sup>p</sup> -adversary. This adversary faces weighted p-norm costs for attacking k services out of a set of S possible services. When an adversary has this profit function, it implicitly means that an adversary cannot attack more than O(S <sup>1</sup>/p) services simultaneously. Note that this implies that for p → ∞, we degrade to the threat model of S independent PoS networks (*i.e.* we assume an adversary can only attack 1 network at a time).

Our main result in Theorem 1 shows that there exist sufficiently high rewards (incentives) rs (p) that can be paid to each service s to ensure that the cascade length is bounded under the assumption of ℓ<sup>p</sup> adversaries. This result implies that services can individually and locally choose a risk tolerance (parametrized by p ∈ (1, ∞) and pay rewards to ensure they have no large cascades. Given that submodular functions are known to have minima that are easy to approximate [\[AMM21;](#page-18-4) [PRS23](#page-19-11)], a natural question is if there exist algorithms for computing the optimal rewards to distribute given a choice of p. We show that this is indeed possible in §[4](#page-16-0) and provide an approximate guarantee dependent on attack profitability and <span id="page-4-0"></span>a choice of p.

## 2 Model

Analogous to [\[DR24](#page-19-0)], we define a restaking graph as a bipartite graph with associated profit, stake, and threshold functions. These functions will be used to define what it means for a restaking network to be secure to cascading risks. Our model generalizes that of [\[DR24\]](#page-19-0) in that we consider a larger set of profit functions and we introduce a notion of rewards that services can pay to node operators and costs that node operators face for operating a service. Our model is sufficiently general to handle both deterministic costs (*i.e.* cost of running hardware) and probabilistic costs (*i.e.* cost of being slashed).

#### Restaking Graphs. A *restaking graph* G = (S, V, E, σ, π, α, f) consists of

- Bipartite graph with vertex set S ⊔ V where S is the set of services[1](#page-4-1) and V is the set of node operators
- An edge (v, s) ∈ E ⊂ V × S if node operator v is a node operator for service s
- σ ∈ R V <sup>+</sup> is the amount of stake that node operator v ∈ V has in the network
- π ∈ R S <sup>+</sup> is the maximum profit from corruption that can be realized for each service s ∈ S
- α ∈ [0, 1]<sup>S</sup> is the threshold percentage of stake that needs to collude to corrupt the service s ∈ S (*e.g.* α = <sup>1</sup>/<sup>3</sup> is the threshold for a BFT service)
- f : R S <sup>+</sup> × 2 <sup>S</sup> → R<sup>+</sup> is a profit function, where f(π, A) is the maximum profit that can be realized by corrupting all services s ∈ A simultaneously

See Figure [1](#page-5-0) for a picture of a restaking graph. Our definition generalizes [\[DR24](#page-19-0)] since they restrict attention to the linear profit function f(π, A) = P s∈A πs . For a node operator v, we define its neighbor set (or boundary) as ∂v = {s : (v, s) ∈ E}. Similarly, for a service s, we define its neighborhood as ∂s = {v : (v, s) ∈ E}. For each service, we define the total stake as service s, σ∂s as

$$
\sigma_{\partial s} = \sum_{v : (v,s) \in E} \sigma_v
$$

We define the set Dψ(G) as the set of coalitions of node operators with stake less than ψ ∈ (0, 1) fraction of the total amount staked:

$$
D_{\psi}(G) = \left\{ D \subseteq V \middle| \sum_{v \in D} \sigma_v \leq \psi \sum_{v \in V} \sigma_v \right\}
$$

<span id="page-4-1"></span><sup>1</sup> In Eigenlayer terminology, a service would be called an 'actively validated service' (AVS)

<span id="page-5-0"></span>![](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2024-Restaking-Security-Pricing/_page_5_Figure_0.jpeg)

Figure 1: Example of a restaking graph G = (S, V, E, α, σ, π) with S = {s<sup>1</sup> , s2}, V = {v<sup>1</sup> , v2}, E = {(s<sup>1</sup> , v<sup>1</sup> ),(s<sup>1</sup> , v<sup>2</sup> ),(s<sup>2</sup> , v<sup>1</sup> ),(s<sup>2</sup> , v<sup>2</sup> )}. We consider f(π, A) = P s∈A π<sup>s</sup> as the profit function. Note that each individual service cannot be attacked here as π<sup>i</sup> < σ<sup>i</sup> for i ∈ {1, 2}. However, the set S might be vulnerable since the profitability condition [\(1\)](#page-5-1), π<sup>1</sup> + π<sup>2</sup> > σ<sup>i</sup> holds for the potential attack ({s<sup>1</sup> , s2}, {vi}) ⊂ S × V . This attack is only valid, however, if σ<sup>i</sup> > αs<sup>j</sup> (σ<sup>1</sup> + σ<sup>2</sup> ), which implies that we need to have <sup>α</sup>s<sup>j</sup> <sup>&</sup>lt; <sup>1</sup> 2 for j ∈ {1, 2} for this to be an attack. So if s<sup>1</sup> , s<sup>2</sup> were BFT protocols with α<sup>s</sup> = 1 3 , this graph would be insecure. However, if it they were longest-chain protocols with α<sup>s</sup> = 1 2 , it would be secure.

For any set D ⊂ V or set A ⊂ S, we will slightly abuse notation and write

$$
\sigma_D = \sum_{v \in D} \sigma_v \qquad \qquad \pi_A = \sum_{s \in A} \pi_s
$$

Finally, for any set A ⊂ S and a vector v ∈ R S , we denote by v(A) ∈ R A the restriction of v to the coordinate in A (and similarly for B ⊂ V ).

Security and Overcollateralization. A restaking graph G has an f-*attack* at (A, B) ⊂ S × V if:[2](#page-5-2)

<span id="page-5-3"></span><span id="page-5-1"></span>
$$
f(\pi, A) \ge \sum_{v \in B} \sigma_v = \sigma_B \tag{1}
$$

$$
\forall s \in A: \sum_{v \in B \cap \partial s} \sigma_v \ge \alpha_s \sum_{v \in \partial s} \sigma_v = \alpha_s \sigma_{\partial s} \tag{2}
$$

When the context is clear, we will refer to an f-attack simply as an attack:

- We call [\(1\)](#page-5-1) the *profitability* condition for an attack, as it requires that the net profit from corruption of a set of services A exceed the total amount staked by the attacking operators B.
- We refer to [\(2\)](#page-5-3) as the *feasibility* condition for an attack as it represents a coalition B ⊂ V having sufficient stake to execute an attack.

<span id="page-5-2"></span><sup>2</sup>These conditions were originally identified in the Eigenlayer whitepaper [\[Eig23](#page-19-2)] for the special case that f(π, A) = πA.

A graph is said to be *secure* if there does not exist an f-attack (A, B) ⊂ S ×V . See Figure [1](#page-5-0) for an example of a graph that is secure for α<sup>s</sup> ≥ 1 2 and insecure otherwise.

A restaking graph is said to be γ*-secure* if G is secure and for all attacking coalitions (A, B) ⊂ S × V (*e.g.* where [\(2\)](#page-5-3) is feasible):

$$
(1+\gamma)f(\pi,A) \le \sum_{v \in B} \sigma_v = \sigma_B \tag{3}
$$

This is an overcollateralization condition providing a multiplicative gap between the profit over attacking A and the stake held by B.

As per [\[DR24](#page-19-0)], given an attack (A, B), we define the graph G ց B to be the subgraph G = (S − A, V − B, E − (S × B ∪ A × V ), σ(V − B), π(S − A), α(S − A), f). This is simply the restaking graph where the services in A and the node operators in B are removed. Note that we use a slightly different definition relative to [\[DR24\]](#page-19-0) in that we remove services that have been attacked to simplify the dynamics of our model. A disjoint sequence (A<sup>1</sup> , B<sup>1</sup> ), . . . ,(A<sup>T</sup> , B<sup>T</sup> ) is a *cascading sequence of attacks* if for each t ∈ [T], (A<sup>t</sup> , B<sup>t</sup> ) is a valid attack on G ց B<sup>1</sup> · · · ց Bt−<sup>1</sup> . We let C(G) denote the set of sequences of valid attacks on a restaking graph G and as per [\[DR24\]](#page-19-0), we define the cascade coefficient Rψ(G) as

$$
R_{\psi}(G) = \psi + \max_{D \in D_{\psi}(G)} \max_{(A_1, B_1), \dots, (A_T, B_T) \in C(G \setminus D)} \frac{\sigma_{\bigcup_{t=1}^T B_t}}{\sigma_V}
$$

One can interpret Rψ(G) as the maximum loss of stake that can occur if stake of at most ψ is slashed or removed. In Figure [2,](#page-7-0) we show a cascading attack of length T = 4 with R1/V (G) = 1 that is inspired by [\[DR24,](#page-19-0) Theorem 7].

In [\[DR24\]](#page-19-0), the authors show that when f(π, A) = P s∈A πs , one can have Rψ(G) = 1, which represents the entire network being slashed in a cascading failure. However, the authors also demonstrate that if G is γ–secure, then we have

$$
R_{\psi}(G) \le \left(1 + \frac{1}{\gamma}\right)\psi\tag{4}
$$

This demonstrates that networks are safer as they increase their overcollateralization. Note, however, that γ is a global variable for overcollateralization (*i.e.* every service needs to be overcollateralized by at least this amount) which can make service profitability difficult. Finally, we note [\[DR24,](#page-19-0) Theorem 1, Corollary X], [\[Eig23](#page-19-2), App. B] that a computationally efficient sufficient condition for Eigenlayer nodes to be γ-secure is: ∀v ∈ V, (1+γ) P s∈∂v πs αsσ∂s ≤ 1. Note that condition need not hold for all γ-secure restaking graphs.

Overlap. One of the main advantages of restaking systems is the ability to reuse capital to secure multiple services. This allows node operators to earn yield from many sources and increase their overall profitability. However, on the flip side, this also increases the profit from attack. As a simple example, consider the restaking graph of Figure [1.](#page-5-0) In this graph, we have two services a and b with π<sup>a</sup> = π<sup>b</sup> = 1. Moreover, there is a single node operator σ<sup>1</sup>

<span id="page-7-0"></span>![](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2024-Restaking-Security-Pricing/_page_7_Figure_0.jpeg)

Figure 2: An example of a cascading failure in a restaking network based on [\[DR24](#page-19-0), Thm. 7, Figure 1] In this sequence of figures, black dots represent validators v<sup>i</sup> , i ∈ [12] and the red and blue boxes containing v<sup>i</sup> represent services s<sup>i</sup> , i ∈ [6]. For this system, we have σv<sup>i</sup> = 1 and αs<sup>i</sup> = 1 for all s<sup>i</sup> , v<sup>i</sup> . We have π<sup>s</sup> = 2 for the services represented by red boxes and π<sup>s</sup> = 4 for the services represented by the blue boxes. One can view this as the hypergraph representation of a bipartite graph implicit in a restaking graph. When we go from the upper left diagram to the upper right diagram, we first have a loss of ψ = 1 <sup>12</sup> , which represents the loss of a single node's stake. Losing this node's stake makes the left red box vulnerable as π<sup>s</sup> = 2σ<sup>v</sup> when s is a red box, which is represented when one goes from the upper right box to the middle right box in attack (A<sup>1</sup> , B<sup>1</sup> ). This leads to the bottom row becoming vulnerable as π<sup>s</sup> = 4σ<sup>v</sup> when s is a blue box (which is the attack (A<sup>2</sup> , B<sup>2</sup> ). This attack now leads the middle red service vulnerable and it is attacked in (A<sup>3</sup> , B<sup>3</sup> ). Finally, the remaining nodes in the blue service in the top row are vulnerable and attacked in (A<sup>4</sup> , B<sup>4</sup> ), leading to R1/12(G) = 1

who is validating both services a and b. As σ<sup>1</sup> = 1.1, then on their own, neither service a nor b are attackable as π<sup>i</sup> − σ<sup>1</sup> < 0 for i ∈ {a, b}. However, if f(π, A) = P s∈A πs , then it is profitable to attack both a and b simultaneously since π<sup>a</sup> + π<sup>b</sup> − σ<sup>1</sup> > 0. On the other hand, if there were two node operators with σ<sup>1</sup> = σ<sup>2</sup> = 1.1 with σ<sup>1</sup> operating a and σ<sup>2</sup> operating b, then there is no viable attack. This example demonstrates that when two services share stake operated by the same operator, they increase the profitability of attacking both services simultaneously.

One can view the risk of being attacked as related to the *overlap* of stake between services s and t. We define the overlap between s and t, θs,t as θs,t = σ∂s∩∂t where ∂s∩∂t ⊂ V is the set of operators validating both services. In particular, as two services have higher overlap, the profit from attacking them together (as in our example) goes up. For each service s ∈ S, we define the minimum and maximum overlap, θ<sup>s</sup> , θ<sup>s</sup> , as θ<sup>s</sup> = mint∈S/{s} θs,t, θ<sup>s</sup> = maxt∈S/{s} θs,t.

In Appendix [B,](#page-21-0) we demonstrate an example of a graph whose maximum cascade length is controlled completely by the overlap. For this graph, if one required γ-security to hold, we demonstrate that one would need Ω(P s∈S πs ) more stake than necessary to have small cascade length. In a scenario where one service has a profit π<sup>1</sup> = 1 and another service has π<sup>2</sup> = 1, 000, this implies that π<sup>1</sup> has to aggregate stake on the order of 1, 000 times more stake to be γ-secure than if they were an isolated network. This example demonstrates that γ-security is often a highly inefficient means of overcollateralizing a restaking system to avoid cascades.

One of the main insights of this paper is that if one can control the overlap suitably and rational node operators can adjust their stake in response to an attack, then one can bound cascade length without needing a condition as strong as being γ-secure. In the sequel, we demonstrate that control over the minimum and maximum overlap between services allows one to bound the profitability of an attack. For instance, when the profitability is sublinear in |A|, then constraints on the overlap between services upper and lower bound f(π, A)−σB. Our results in §[3](#page-10-0) show that these bounds allow for incentives to be used to control over the overlap and Rψ(G).

Strictly Submodular Adversaries. We say that a restaking graph G = (S, V, E, σ, π, α, f) is strictly submodular if f(π, A) is a strictly submodular function of A,*i.e.* , f(π, A ∪ A ′ ) + f(π, A ∩ A ′ ) < f(A) + f(A ′ ) for all A, A′ ⊂ S with A 6⊂ A ′ , A′ 6⊂ A. A submodular adversary can be viewed as an adversary who faces costs for simultaneously attacking many services. Note that the linear payoff function f(π, A) = P s∈A π<sup>s</sup> of [\[DR24](#page-19-0)] does not yield a strictly submodular restaking graph. Strictly submodular restaking graphs can be thought of as those where attackers face a cost that increases with the number of services |A| they are trying to concurrently attack. For instance, if an attacker faces an acquisition cost for acquiring stake in each service they attack, they could have a profit that is sublinear in |A|. We say that an attack is a *costly attack* if f is strictly submodular.

For example, suppose an adversary faces a multiplicative cost c(π, A) for attacking services A ⊂ S, *i.e.* f(π, A) = c(π, A) P s∈A πs . If for all s, c(π, A) = Θ 1 |A| c for c (*i.e.* non-constant cost, increasing in A), then f(π, A) = O(|A| 1−c ), which is strictly submodular [\[PRS23,](#page-19-11) §2]. Such a multiplicative cost might arise if one has an additively supermodular cost (which can be thought of as a strictly convex cost).

This is also equivalent to having diminishing returns for attacking multiple services. This occurs when the costs for acquiring stake to attack different services are correlated. For instance, acquiring stake to attack service A can cause the price of acquiring stake to attack service B to increase. Such non-trivial costs growing with the maximum profit exist in other blockchain attacks: oracle manipulation [\[MNW22;](#page-19-12) [AB22\]](#page-18-5), intents [\[Chi+24](#page-18-6)], transaction fee manipulation [\[Yai+23;](#page-20-2) [CRS24](#page-18-7)], liquid staking manipulation [\[CE20](#page-18-2); [TZ23\]](#page-20-1) and time-bandit attacks [\[YTZ22\]](#page-20-3).

We also note that if f(π, A) is a weighted ℓ<sup>p</sup> -norm of A, then it is strictly submodular if p > 1 [\[PRS23,](#page-19-11) Obs. 2.1]. The majority of this paper will focus on studying the p-norm profit, f<sup>p</sup> (π, A):

<span id="page-9-0"></span>
$$
f_p(\pi, A) = \left(\sum_{s \in A} \pi_s^p\right)^{1/p} \tag{5}
$$

We note that for strictly submodular adversaries, Corollary 1 of [\[DR24\]](#page-19-0) does not hold. When f(π, A) = P s∈A πs , this corollary says that if (A<sup>1</sup> , B<sup>1</sup> ), . . . ,(A<sup>T</sup> , B<sup>T</sup> ) is a valid attack sequence then (S <sup>t</sup> A<sup>t</sup> , S <sup>t</sup> B<sup>t</sup> ) is a valid attack sequence. We demonstrate that this is not true for p-attacks in Appendix [A.](#page-20-4)

Incentives. We say a restaking graph is *incentivized* if there are two additional functions:

- r ∈ R S <sup>+</sup>: r<sup>s</sup> is the reward paid out by service s to node operators ∂s
- c ∈ R S <sup>+</sup>: c<sup>s</sup> is the cost to an operator of operating service s

Costs should be thought of as including both the cost of operating the service and the losses faced from not conforming to the protocol (*i.e.* slashes). Given a reward r<sup>s</sup> , each node operator v with an edge (v, s) ∈ E receives a reward ρsv = βsvr<sup>s</sup> . If (v, s) 6∈ E, we define ρsv = 0. A service s is *pro-rata* if βsv = σv σ∂s , *i.e.* <sup>ρ</sup>sv <sup>=</sup> <sup>r</sup><sup>s</sup> <sup>P</sup> <sup>σ</sup><sup>v</sup> <sup>v</sup>:(v,s)∈<sup>E</sup> σ<sup>v</sup> = r<sup>s</sup> σv σ∂s . The majority of reward systems within decentralized networks and cryptocurrencies follow a pro-rata reward distribution [\[Joh+23;](#page-19-13) [CPR19\]](#page-18-8) and this is the main form of incentive studied in this paper. Finally, we say an incentivized restaking graph is *dynamic* if r(t) ∈ R S <sup>+</sup>, σ(t) ∈ R V <sup>+</sup>, E<sup>t</sup> ⊂ 2 S×V are updated sequentially for rounds t ∈ N.

A node operator is *profitable without impact* at a service s if ρsv − c<sup>s</sup> = r<sup>s</sup> σv σ∂s − c<sup>s</sup> ≥ 0 which is equivalent to:

$$
\sigma_v \ge \frac{c_s \sigma_{\partial s}}{r_s} \tag{6}
$$

However, a node operator also needs to measure the impact of adding their own stake when computing profitability. Recall that upon depositing σ<sup>v</sup> into service s, σ∂s will increase by σv . A node operator is said to be *profitable with impact* if σ<sup>v</sup> ≥ cs (σ∂s+σ<sup>v</sup> ) rs which can be rewritten as

<span id="page-9-1"></span>
$$
\sigma_v \ge \frac{c_s \sigma_{\partial s}}{r_s - c_s} \tag{7}
$$

Rebalancing. Consider a node operator v ∈ V who is validating a set of services ∂v(0) ⊂ S at time t = 0. We say that v is *strategic* if given a dynamic, incentivized staking graph G<sup>t</sup> and an attack sequence (A<sup>1</sup> , B<sup>1</sup> ), . . . ,(A<sup>T</sup> , B<sup>T</sup> ), they have ∂v(t) = Update(∂v(t − 1), σ∂s, r<sup>s</sup> , c<sup>s</sup> ) after each attack (A<sup>t</sup> , B<sup>t</sup> ). A strategic node operator can be thought of one that updates the services the validate in response to change in yield after t attacks, ρsv(t). If that the function Update : 2<sup>S</sup> × R<sup>+</sup> × R<sup>+</sup> × R<sup>+</sup> → 2 S is non-constant, we say that a node operator is *strategically rebalancing*.

If we view ∂v(t) as a portfolio of financial assets, a strategically rebalancing node operator is one who aims to maximize their expected value as the restaking graph changes. For instance, if a slashing event reduces competition at a service s so that ρsv(t) > ρsv(t − 1), then a strategically rebalancing node operator can add s to ∂v to earn more incentives. When rebalancing is present, we consider a three-step iterated game between services, node operators, and attackers given an attack sequence:

- 1. Services choose rewards r<sup>s</sup> (t) to offer node operators
- 2. Attackers execute a single attack (A<sup>i</sup> , B<sup>i</sup> )
- 3. Strategically rebalancing node operators update the services they are validating, ∂v(t)

We note that one can view this as an online Stackelberg security game with the services acting as leader and the attacker and node operators as followers [\[Sin+18](#page-19-14); [Bal+15\]](#page-18-9).

We construct an explicit example of rebalancing arresting a cascading attack in Figure [3.](#page-11-0) We take the same example as in Figure [2](#page-7-0) and show that if a node operator can strategically rebalance and rewards are sufficiently high, they can halt a cascading attack. In this example, we are able to reduce an attack (A<sup>1</sup> , B<sup>1</sup> ), . . . ,(A<sup>T</sup> , B<sup>T</sup> ) to an attack (A<sup>1</sup> , B<sup>1</sup> ). The main results of §[3](#page-10-0) construct sufficient conditions for how high rewards need to be in order to halt an attack and force it to have length 1.

<span id="page-10-0"></span>

### 3 Costly Attacks and Strategic Operators

Given the model of the previous section, we are now ready to describe our main results. We consider a weaker adversary and a stronger operator than [\[DR24\]](#page-19-0) in that we consider a dynamic, incentivized restaking graph G<sup>t</sup> = (S, V, E<sup>t</sup> , α, σ<sup>t</sup> , π, f, r(t), c) where f is strictly submodular. For the remainder of this section, we will consider the G p <sup>t</sup> = (S, V, E<sup>t</sup> , α, σ<sup>t</sup> , π, f<sup>p</sup> , r(t), c) where f<sup>p</sup> (π, A) is defined in [\(5\)](#page-9-0).

We will term a costly attack for G p <sup>t</sup> a p*-attack*. We prove similar results to those in this section for strictly submodular functions, where the analog of the parameter p is curvature of a submodular function [\[SVW17](#page-19-15)], in the full version of this paper. Our main result can be stated as:

<span id="page-10-1"></span>Theorem 1. *Consider* G p <sup>t</sup> *with strategically rebalancing node operators. There exist rewards* r(t) ∈ R S <sup>+</sup> *such that for a constant* C > 0 *we have*

$$
R_{\psi}(G) \leq \psi + \frac{C}{S^{1-\frac{1}{p}}}
$$

<span id="page-11-0"></span>![](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2024-Restaking-Security-Pricing/_page_11_Figure_0.jpeg)

Figure 3: A cascading attack halted by a rebalance. This is the same example as in Figure [2,](#page-7-0) except that rewards r<sup>s</sup> are chosen sufficiently high such that after the validator in the upper left corner is slashed, the adjacent validator in the upper blue service (i.e. second from the left), joins the lower blue service. This leads to the cascading failure not being viable in that (A<sup>2</sup> , B<sup>2</sup> ) is no longer a valid attack after rebalancing. One can view this as an equilibrium condition: if we start in equilibrium, then every (v, s) ∈ E must be profitable with impact. This implies that if they are slashed, then another validator with at most the same stake can profitably join the service after they're slashed (which is what the validator second from the left in the top row is doing).

*The rewards* r(t) *are local in that the optimal choice of* r<sup>s</sup> (t) *is only a function of* ∂s(t) *and any service* s ′ ∈ S *such that* ∂s′ (t) ∩ ∂s(t) 6= ∅

Outline of Proof of Theorem [1.](#page-10-1) We prove this theorem in a sequence of steps:

1. We first show that for any costly attack (A, B), one has

|B| ≤ KS<sup>1</sup>/p

for K = max<sup>s</sup> π<sup>s</sup> min<sup>v</sup> σ<sup>v</sup> . Note that min<sup>v</sup> σ<sup>v</sup> is a control parameter that a restaking protocol designer can choose (*i.e.* analogous to the 32 ETH that are needed to stake in Ethereum mainnet).

- 2. We next show that if ∀s, t ∈ S, θs,t = Θ(S <sup>1</sup>/p) , then |A| = o(S)
- 3. For any costly attack sequence (A<sup>1</sup> , B<sup>1</sup> ), . . . ,(A<sup>T</sup> , B<sup>T</sup> ) ∈ C(G p 0 ), we show that if |A<sup>t</sup> | = o(S), r<sup>s</sup> = Ω(S <sup>1</sup>/p), then rebalancing node operators only allow (A<sup>1</sup> , B<sup>1</sup> ) to be a valid attack. That is, after the first attack (A<sup>1</sup> , B<sup>1</sup> ) is executed, rebalancing node operators place sufficient stake on services in a manner that makes (A<sup>2</sup> , B<sup>2</sup> ) an invalid attack on G p 1 .
- 4. Next, we show that given high enough rewards, rebalanced stake cannot cause further attacks. That is, rebalancing cannot cause an attack that was infeasible prior to rebalancing to be feasible post rebalancing.
- 5. Given these sufficiently high rewards, we also show that in the presence of strategically rebalancing node operators and if V > S, we have σ<sup>V</sup> ≥ (min<sup>v</sup> σ<sup>v</sup> ) S which implies that cascades are bounded as:

<span id="page-12-0"></span>
$$
R_{\psi}(G) \leq \psi + \max_{D \in D_{\psi}(G)} \max_{(A_1, B_1) \in C(G - D)} \frac{\sigma_{B_1}}{\sigma_V} \leq \psi + \frac{KS^{1/p}}{(\min_v \sigma_v) S} = \psi + \frac{C}{S^{1 - \frac{1}{p}}} \tag{8}
$$

6. All of the above results rely on ensuring that θ<sup>s</sup> , θ<sup>s</sup> = Θ(S <sup>1</sup>/p). We demonstrate that there exists a simple update to dynamically choose rewards r<sup>s</sup> (t) = f(θ<sup>s</sup> (t), θ<sup>s</sup> (t), σ∂s(t), r<sup>s</sup> (t− 1)) in response to rebalances to ensure that θ<sup>s</sup> θ<sup>s</sup> = Θ(S <sup>1</sup>/p). This update rule gives lower rewards to node operators who increase overlap and higher rewards to those who decrease overlap. We note that such incentive mechanisms have been used as so-called incentive 'boosts' within various restaking point systems [\[Lla24;](#page-19-9) [Pat24\]](#page-19-10).

Combined, these results ensure that one can ensure small cascade coefficient by dynamically updating rewards in the presence of strategically rebalancing node operators.

### 3.1 Proofs of Steps 1 and 2

The claim that |B| = O(S <sup>1</sup>/p) for a p-attack is straightforward:

Claim 1 (Step 1). *Suppose that* max<sup>s</sup> <sup>π</sup><sup>s</sup> min<sup>v</sup> σ<sup>v</sup> ≤ K*. If* (A, B) *is* p*-attack, then* |B| ≤ KS<sup>1</sup>/p

*Proof.* For a p-attack (A, B), [\(1\)](#page-5-1) and [\(5\)](#page-9-0) imply that |A| <sup>1</sup>/p (maxs∈<sup>A</sup> π<sup>s</sup> ) ≥ f<sup>p</sup> (π, A) ≥ σ<sup>B</sup> ≥ (minv∈<sup>B</sup> σ<sup>v</sup> )|B|. Therefore |B| ≤ maxs∈<sup>A</sup> <sup>π</sup><sup>s</sup> minv∈<sup>B</sup> σ<sup>v</sup> |A| <sup>1</sup>/p ≤ KS<sup>1</sup>/p

The second claim, *i.e.* |A| = o(S), relies on upper and lower bounding the overlap between services.

Claim 2 (Step 2). *Suppose that there exists* δ > 0 *such that for all* s, t ∈ S*,* |∂s ∩ ∂t| ≥ (1 + δ)KS<sup>1</sup>/p *and* θ<sup>s</sup> ≤ (max<sup>v</sup> σ<sup>v</sup> ) KS<sup>1</sup>/p *for all* s ∈ S*. If* <sup>δ</sup>(min<sup>v</sup> <sup>σ</sup><sup>v</sup> ) (max<sup>v</sup> <sup>σ</sup>v) ≥ 1− 1 <sup>e</sup>(S−1)<sup>2</sup> *, then for any* p*-attack* (A, B)*, we have*

$$
|A| \le \left(\frac{2K(S-1)}{S-2}\right)^{\frac{p}{p-1}}
$$
  
\n
$$
K = o(S^{\frac{p-1}{p}}) \quad then \ |A| = o(S)
$$
\n(9)

*where* K = max<sup>s</sup> π<sup>s</sup> min<sup>v</sup> σ<sup>v</sup> *. Therefore if* K = o(S <sup>p</sup> )*, then* |A| = o(S)

This bound demonstrates the number of attacked services is sublinear in S provided that the overlap is sufficiently small and that the adversary is submodular. Furthermore, note that the assumption |∂s∩∂t| ≥ (1 +δ)KS<sup>1</sup>/p implies that θ<sup>s</sup> = Ω(S <sup>1</sup>/p) since θ<sup>s</sup> ≥ (min<sup>v</sup> σ<sup>v</sup> )|∂s∩ ∂t|. We prove this claim in Appendix [C](#page-22-0) but briefly sketch it here for completeness. The main ingredient of the proof is expanding σ<sup>B</sup> into a sum of terms depending on B ∩ ∂s for different services s. We then lower bound this expansion and show σ<sup>B</sup> = Ω(|A|). On the other hand, the profitability condition implies that σ<sup>B</sup> ≤ f<sup>p</sup> (π, A) = O(|A| <sup>1</sup>/p). Combining these inequalities yields the claim. We note that if one adds extra constraints (*i.e.* G is d-regular), then one can get achieve stronger bounds.

### 3.2 Proof of Step 3

The third step demonstrates that with sufficient incentives, one is able to rebalance enough stake to ensure that the p-attack (A<sup>2</sup> , B<sup>2</sup> ) is not viable. Recall that a costly attack needs to be both profitable [\(1\)](#page-5-1) and feasible [\(2\)](#page-5-3). When a set of node operators rebalances, they do not change the profitability of the p-attack (A<sup>2</sup> , B<sup>2</sup> ), but rather, make the setup infeasible. Suppose D<sup>s</sup> ⊂ V is the set of node operators who rebalance into service s after p-attack (A<sup>1</sup> , B<sup>1</sup> ). Then the rebalance has successfully thwarted a p-attack (A<sup>2</sup> , B<sup>2</sup> ) if the following conditions hold:

| fp<br>(π, A1<br>)<br>σB                            | (10)             |
|----------------------------------------------------|------------------|
| ∀s<br>∈<br>A1<br>σ∂s∩B<br>≥<br>αsσ∂s               | (11)             |
| ≥<br>fp<br>(π, A2<br>)<br>σB                       | (12)             |
| ∀s<br>∈<br>A2<br>σ(∂s−B<br>1)∩B2 ≥<br>αsσ∂s−B<br>1 | (13)             |
|                                                    | ≥<br>1<br>1<br>2 |

[Attack 2 is infeasible with rebalancing] ∀s ∈ A<sup>2</sup> σ(∂s−B1+D<sup>s</sup>

<span id="page-13-2"></span><span id="page-13-1"></span><span id="page-13-0"></span>
$$
\beta \in A_2 \quad \sigma_{(\partial s - B_1 + D_s) \cap B_2} \le \alpha_s \sigma_{\partial s - B_1 + D_s} \quad (14)
$$

<span id="page-14-0"></span>Our claim demonstrates that [\(14\)](#page-13-0) holds under conditions on the rewards and overlap. We first prove a simple lemma that will simplify the proof.

#### Lemma 1. *Suppose that* <sup>r</sup><sup>s</sup> cs ≥ KS<sup>1</sup>/p + 1*. Then there exists* κ > 0 *such that*

$$
\sigma_{D_s(B_1)} \geq \kappa \sigma_{\partial s - B_1}
$$

*Proof.* We first define the sets D<sup>s</sup> (B<sup>1</sup> ) as the set of node operators who are not profitable at s prior to B<sup>1</sup> being attacked and are profitable afterwards. Formally, define

$$
\mathcal{D}_s(B_1, r_s, c_s) = \left\{ D \subset V - B_1 : \forall v \in D, \ \sigma_v \ge \frac{c_s \sigma_{\partial s - B_1 + D}}{r_s - c_s}, \ \sigma_v \le \frac{c_s \sigma_{\partial s}}{r_s - c_s} \right\}
$$

where we use eq. [\(7\)](#page-9-1) to define profitability conditions. Let D<sup>s</sup> (B<sup>1</sup> ) ∈ argmaxD∈D<sup>s</sup> (B<sup>1</sup> ,r<sup>s</sup> ,c<sup>s</sup> ) σD. Next, we bound the amount of stake in D<sup>s</sup> (B<sup>1</sup> ) by σ∂s and the attack σ<sup>B</sup><sup>1</sup> :

$$
\sigma_{D_s(B_1)} = \sum_{v \in D_s(B_1)} \sigma_v \ge \sum_{v \in D_s(B_1)} \frac{c_s \sigma_{\partial s - B_1 + D_s(B_1)}}{r_s - c_s} = |D_s(B_1)| \frac{c_s \sigma_{\partial s - B_1 + D_s(B_1)}}{r_s - c_s}
$$

This implies that 1 − |D<sup>s</sup> (B<sup>1</sup> )| cs rs−c<sup>s</sup> σ<sup>D</sup><sup>s</sup> (B1) ≥ |D<sup>s</sup> (B1)|c<sup>s</sup> rs−c<sup>s</sup> σ∂s−B<sup>1</sup> . Therefore when |D<sup>s</sup> (B<sup>1</sup> )| cs rs−c<sup>s</sup> < 1, this is a non-trivial bound: σ<sup>D</sup><sup>s</sup> (B1) ≥ κσ∂s−B<sup>1</sup> . As |D<sup>s</sup> (B<sup>1</sup> )| ≤ KS<sup>1</sup>/p, this condition holds when <sup>r</sup><sup>s</sup> cs ≥ KS<sup>1</sup>/p + 1.

Claim 3 (Step 3). *Suppose that* <sup>r</sup><sup>s</sup> cs ≥ KS<sup>1</sup>/p + 1*,* |A<sup>t</sup> | = o(S) *and for all* s ∈ S σ∂s ≥ (1+ (min<sup>v</sup> σ<sup>v</sup> ))K (max<sup>v</sup> σ<sup>v</sup> ) S <sup>1</sup>/p*. Moreover, suppose that* (min<sup>s</sup> α<sup>s</sup> ) (max<sup>v</sup> σ<sup>v</sup> ) ≥ 2*. Then* [\(14\)](#page-13-0) *holds.*

*Proof.* From the feasibility of (A<sup>2</sup> , B<sup>2</sup> ) without rebalancing, eq. [\(13\)](#page-13-1), we have αsσ∂s−B<sup>1</sup> ≤ σ(∂s−B1)∩B<sup>2</sup> ≤ σ<sup>B</sup><sup>2</sup> . Since |A| = o(S), the profitability of attack 2 (eq. [\(12\)](#page-13-2)) implies

$$
\sigma_{B_2} \le f_p(\pi, A_2) \le \left(\max_s \pi_s\right) |A_2|^{1/p} \le \left(\max_s \pi_s\right) S^{o(1/p)}
$$

This implies that σ(∂s−B1)∩B<sup>2</sup> = O(S o(1/p) ). Similarly, we have σ<sup>D</sup><sup>s</sup> (B1)∩B<sup>2</sup> ≤ σ<sup>B</sup><sup>2</sup> = O(S o(1/p) ). From the lemma and by our assumption on r<sup>s</sup> , we have σ<sup>D</sup><sup>s</sup> (B1) ≥ κσ∂s−B<sup>1</sup> . Moreover, note that

$$
\sigma_{\partial s - B_1} \ge \sigma_{\partial s} - |B_1| \left( \max_v \sigma_v \right) \ge \left( \min_v \sigma_v \right) K \left( \max_v \sigma_v \right) S^{1/p} = \left( \max_s \pi_s \right) \left( \max_v \sigma_v \right) S^{1/p}
$$

This implies that σ∂s−B1+D<sup>s</sup> ≥ (1 + κ)σ∂s−B<sup>1</sup> ≥ (1 + κ) (max<sup>s</sup> π<sup>s</sup> ) (max<sup>v</sup> σ<sup>v</sup> ) S <sup>1</sup>/p. Combined, we have

$$
\sigma_{(\partial s - B_1 + D_s) \cap B_2} = \sigma_{(\partial s - B_1) \cap B_2} + \sigma_{D_s \cap B_2} \le 2 \left( \max_s \pi_s \right) S^{o(1/p)} \n\le (1 + \kappa) \alpha_s \left( \max_s \pi_s \right) \left( \max_v \sigma_v \right) S^{1/p} \le \alpha_s \sigma_{\partial s - B_1 + D_s}
$$

which proves [\(14\)](#page-13-0).

We note that our assumptions are mild: the condition on σ∂s simply says the initial stake at each service needs to be above a p dependent threshold while the condition on min<sup>s</sup> α<sup>s</sup> effectively says we need services that don't have low attack percentages relative to stake.

### 3.3 Proof of Step 4

As π, σ are fixed, rebalancing can only change the feasiblity of an attack [\(2\)](#page-5-3). It is possible that a rebalance to thwart an attack (A<sup>2</sup> , B<sup>2</sup> ) makes a profitable yet infeasible (A, ˜ B˜) ⊂ S×V profitable and feasible. If our rebalance set for service s is D<sup>s</sup> ⊂ V , this occurs when the following conditions hold:

$$
[(\tilde{A}, \tilde{B}) \text{ is infeasible without rebalancing}] \qquad \forall s \in \tilde{A} \quad \sigma_{(\partial s - B_1) \cap \tilde{B}} \le \alpha_s \sigma_{\partial s - B_1} \tag{15}
$$

<span id="page-15-0"></span>
$$
[(\tilde{A}, \tilde{B}) \text{ is feasible with rebalancing}] \quad \forall s \in \tilde{A} \quad \sigma_{(\partial s - B_1 + D_s) \cap \tilde{B}} \ge \alpha_s \sigma_{\partial s - B_1 + D_s} \tag{16}
$$

We demonstrate a simple sufficient condition depending on the rewards that ensures that there exists a rebalance where this does not occur.

Claim 4. *Suppose* <sup>r</sup><sup>s</sup> cs ≥ 2 σmax σmin KS<sup>1</sup>/p + 1*, then for all* D<sup>s</sup> ∈ D<sup>s</sup> (B<sup>1</sup> , r<sup>s</sup> , c<sup>s</sup> ) [\(16\)](#page-15-0) *does not hold Proof.* Rewrite [\(16\)](#page-15-0) as σB˜∩D<sup>s</sup> ≥ (αsσ∂s−B<sup>1</sup> −σ(∂s−B<sup>1</sup> )∩B˜) +αsσ<sup>D</sup><sup>s</sup> . First note that αsσ∂s−B<sup>1</sup> − <sup>σ</sup>(∂s−B1)∩B˜ <sup>≥</sup> <sup>α</sup>sσ∂s−B<sup>1</sup> <sup>−</sup> <sup>σ</sup>B˜ <sup>≥</sup> <sup>α</sup>sσ∂s−B<sup>1</sup> <sup>−</sup> <sup>σ</sup>maxKS<sup>1</sup>/p. Any <sup>D</sup><sup>s</sup> ∈ D<sup>s</sup> (B<sup>1</sup> , r<sup>s</sup> , c<sup>s</sup> ) has σ∂s ≥ rs−c<sup>s</sup> cs σ<sup>v</sup> ≥ 2 σmax σmin KS<sup>1</sup>/p σ<sup>v</sup> ≥ 2σmaxKS<sup>1</sup>/p so αsσ∂s−B<sup>1</sup> − σ(∂s−B1)∩B˜ ≥ KσmaxS <sup>1</sup>/p. Since any attacking coalition <sup>B</sup>˜ has <sup>σ</sup><sup>D</sup>s∩B˜ <sup>≤</sup> <sup>σ</sup>B˜ <sup>≤</sup> Kσmax<sup>S</sup> <sup>1</sup>/p, [\(16\)](#page-15-0) does not hold.

Therefore, with sufficient rewards, any attack that is infeasible prior to rebalancing will not be feasible after rebalancing.

### 3.4 Proof of Steps 5 and 6

Provided that ∀s ∈ S, ∃r<sup>s</sup> > 0 and V ≥ S, it is clear that σ<sup>V</sup> ≥ (min<sup>v</sup> σ<sup>v</sup> ) S. When combined with steps 1, 2, and 3, this implies equation [\(8\)](#page-12-0). What remains to be shown is that the assumptions that exist within step 2 — namely that for all s ∈ S, θ<sup>s</sup> , θ<sup>s</sup> = Θ(S <sup>1</sup>/p) — can also be incentivized via rewards r<sup>s</sup> .

To do this, we consider operator-specific rewards rsv for s ∈ S, v ∈ V , which incentivize targeting a particular overlap range. For any service s, let τ (s) = argmaxt∈S,t6=<sup>s</sup> σ∂s∩∂t ⊂ S and let ∂τ (s) = {v ∈ V : ∃s ∈ τ (s) v ∈ ∂s}. For each service s, let δ<sup>s</sup> > 0 and define

$$
r_{sv}(r,\delta,\sigma) = (1 - \delta_s \mathbf{1}_{v \in \partial \tau(s)}) r_s \tag{17}
$$

This reward linearly decreases the reward received by v if v increases θ<sup>s</sup> . We make the following simple claim:

Claim 5 (Step 5). *If* r<sup>s</sup> = Ω(S <sup>1</sup>/p) *and* δ<sup>s</sup> ≥ 1 − S 1/p rs *, then* θ<sup>s</sup> = O(S <sup>1</sup>/p)

*Proof.* For these rewards, a node operator v is profitable if rsv σv σ∂s − c<sup>s</sup> > 0 which implies the profitability with impact condition σ<sup>v</sup> > cs (σ∂s+σv) rsv . This simplifies to σ<sup>v</sup> > csσ∂s rsv−c<sup>s</sup> . Now consider a p-attack (A, B) and define the set

$$
\mathcal{D}_s(B,\delta_s) = \left\{ D \subset V - B : \forall v \in D, \ \sigma_v \ge \frac{c_s \sigma_{\partial s - B + D}}{r_{sv}(\delta_s) - c_s}, \ \sigma_v \le \frac{c_s \sigma_{\partial s}}{r_{sv}(\delta_s) - c_s} \right\}
$$

Let D ∈ D<sup>s</sup> (B, δ<sup>s</sup> ). By Lemma [1,](#page-14-0) we have σ<sup>D</sup> ≥ κσ∂s−B. This implies that

$$
\sigma_{\partial S-B+D} = \sigma_{\partial S-B} + \sigma_D \ge (1+\kappa)\sigma_{\partial S-B} \ge (1+\kappa)\left(\sigma_{\partial S} - \sigma_{\max}S^{1/p}\right)
$$

By the definition of D<sup>s</sup> (B, δ<sup>s</sup> ), we have

$$
\sigma_D = \sum_{v \in D} \sigma_v \ge c_s \sigma_{\partial s - B + D} \sum_{v \in D} \frac{1}{r_{sv}(\delta_s) - c_s} = (c_s \sigma_{\partial s - B + D}) \left( \frac{|D \cap \partial \tau(s)|}{r_s(1 - \delta_s) - c_s} + \frac{|D - \partial \tau(s)|}{r_s - c_s} \right)
$$
  
$$
\ge (c_s \sigma_{\partial s - B + D}) \frac{|D \cap \partial \tau(s)| + C|D - \partial \tau(s)|}{r_s(1 - \delta_s) - c_s} \ge \frac{(1 + \kappa)c_s C|D|}{r_s(1 - \delta_s) - c_s} \left( \sigma_{\partial s} - \sigma_{\text{max}} S^{1/p} \right)
$$
  
$$
\ge \frac{(1 + \kappa)c_s K}{r_s(1 - \delta_s) - c_s} \left( \overline{\theta}_s - \sigma_{\text{max}} S^{1/p} \right)
$$

Note that the first inequality follows from the first bound in D<sup>s</sup> (B, δ<sup>s</sup> ), the second from the definition of rsv. The third, fourth, and fifth inequalities stem from the fact that C = rs (1−δ<sup>s</sup> )−c<sup>s</sup> rs−c<sup>s</sup> = Ω S 1/p rs and that C|D| = C(|D ∩∂τ (s)| + |D − ∂τ (s)|) ≥ K. Rearranging this yields

<span id="page-16-1"></span>
$$
\overline{\theta}_s \le \frac{1}{(1+\kappa)c_s K} (r_s (1-\delta_s) - c_s + \sigma_{\max} S^{1/p})
$$
\n(18)

Given [\(18\)](#page-16-1), the choice of δ<sup>s</sup> ≥ 1 − S 1/p rs implies that θ<sup>s</sup> = O(S <sup>1</sup>/p).

This claim shows that for sufficiently large discount δ<sup>s</sup> , one can ensure the maximum overlap satisfies the conditions of the prior steps. We note a similar technique can be used for ensuring lower bounds on overlap that provides boosts or extra incentives for increasing overlap between services that are too low.

<span id="page-16-0"></span>

### 4 Reward Selection Algorithms

We have demonstrated that provided rewards are sufficiently high, one can bound Rψ(G). However, in practice, there is the question of how to compute optimal rewards r ⋆ <sup>s</sup> given a restaking graph G. Given that the profit functions are submodular, we demonstrate that utilizing Algorithm [1,](#page-24-0) one can approximate the optimal rewards up to a multiplicative factor E(S, p).

Sequential Profit Function. Consider the function Profit<sup>p</sup> : C(G) → R<sup>+</sup> that is defined as:

$$
Profit_p((A_1, B_1), \dots, (A_T, B_T)) = \sum_{t=1}^{T} f_p(\pi, A_i) - \sigma_{B_i}
$$
 (19)

This function is strictly positive for attack sequences. Our goal will be to take an bound T ∈ N<sup>+</sup> on sequence length and find a sequence (Aˆ 1 , Bˆ 1 ), . . . ,(Aˆ k , Bˆ k ), k ≤ T such that Profit<sup>p</sup> ((Aˆ 1 , Bˆ 1 ), . . . ,(Aˆ k , Bˆ k )) ≥ α(p) maxS∈C(G),|S|≤<sup>T</sup> Profit<sup>p</sup> (S). Given this sequence, one can solve for rewards that ensure that attack (Aˆ 2 , Bˆ 2 ) is invalid in the presence of rebalancing.

Optimal Rewards. Let (A ⋆ 1 , B<sup>⋆</sup> 1 ), . . . ,(A ⋆ <sup>T</sup> , B<sup>⋆</sup> <sup>T</sup> ) ∈ argmaxS∈C(G) Profit(S), then we can compute the optimal rewards r ⋆ s to ensure that Rψ(G) by computing the minimum rewards such that [\(14\)](#page-13-0) holds. This implies that we need αsσ∂s−<sup>B</sup> ⋆ <sup>1</sup>−D(r<sup>s</sup> ) ≥ σ(∂s−<sup>B</sup> ⋆ <sup>1</sup> +D<sup>s</sup> )∩B ⋆ 2 for all s ∈ A ⋆ 2 . This can be formulated as the following minimax program:

$$
f(r_s) = \max_{D \in \mathcal{D}_s(B_1, r_s, c_s)} \sum_{s \in A_2^{\star}} \log(\alpha_s \sigma_{\partial s - B_1^{\star} + D} - \sigma_{(\partial s - B_1^{\star} + D) \cap B_2^{\star}})
$$
  
$$
r_s^{\star} = \min\{r_s \ge 0 : f(r_s) > 0\}
$$
 (20)

We consider a convex relaxation of this problem. Note that D ∈ D<sup>s</sup> (B<sup>1</sup> , r<sup>s</sup> , c<sup>s</sup> ) implies a V -size set of linear constraints on D of the form σ<sup>v</sup> ≥ csσ∂s−<sup>B</sup> ⋆ <sup>1</sup> <sup>+</sup>Dr<sup>s</sup> − c<sup>s</sup> ⇐⇒ σ<sup>D</sup> ≤ (r<sup>s</sup> − c<sup>s</sup> )σ<sup>v</sup> − σ∂s−<sup>B</sup> ⋆ 1 since ∂s, B<sup>⋆</sup> <sup>1</sup> are fixed. Let ∆<sup>n</sup> = {x ∈ R n <sup>+</sup> : P i x<sup>i</sup> ≤ 1} be the simplex. We define

<span id="page-17-0"></span>
$$
\hat{f}(r_s, k) = \max_{D \in \left( (r_s - c_s)k - \sigma_{\partial s - B_1^*} \right) \Delta^n} \sum_{s \in A_2^*} \log(\alpha_s \sigma_{\partial s - B_1^* + D} - \sigma_{(\partial s - B_1^* + D) \cap B_2^*}) \tag{21}
$$

Note that ˆf is monotone increasing in r<sup>s</sup> and k and that this is a logarithmic barrier problem over a convex set [\[BV04](#page-18-10), Ch. 11]. Moreover, note that ˆf ≥ f since D<sup>s</sup> (B ⋆ 1 , r<sup>s</sup> , c<sup>s</sup> ) ⊂ (r<sup>s</sup> − c<sup>s</sup> )(max<sup>v</sup> σ<sup>v</sup> ) − σ∂s−<sup>B</sup> ∗ 1 ∆ n . This implies that unless f(r<sup>s</sup> ) < 0 for all r<sup>s</sup> > 0, then we can find r<sup>s</sup> by a combination of bisection and solving [\(21\)](#page-17-0) by an interior point method.

Approximation Guarantees. We prove the following claim in Appendix [D:](#page-23-0)

Claim 6. *Suppose* [\(20\)](#page-17-1) *is feasible for some* r<sup>s</sup> > 0 *and that* min<sup>s</sup> <sup>π</sup><sup>s</sup> max<sup>s</sup> π<sup>s</sup> ≥ C*. Then Algorithm [1](#page-24-0) returns an approximation* rˆ<sup>s</sup> *that satisfies*

<span id="page-17-1"></span>
$$
\hat{r}_s \geq \frac{Cr_s^*}{S^{1/p}} + G
$$

*where* G *is the integrality gap* G = sup<sup>r</sup>s><sup>0</sup> maxv∈<sup>V</sup> ˆf(r<sup>s</sup> , σ<sup>v</sup> ) − f(r<sup>s</sup> )*.*

### 5 Conclusion and Future Directions

Our results demonstrate that cascade risk in restaking networks can be bounded with incentives. Services can utilize our results to choose a rewards r<sup>s</sup> that ensure they can only be attacked by Ω(S <sup>1</sup>/p)-sized attacking coalitions. This allows smaller services to choose a threat model that offers fewer rewards should their local corruption profit be low. On the other hand, our results show that strategic node operators (such as liquid restaking tokens [\[Li24\]](#page-19-6), who aggregate stake and delegate to node operators) need to rebalance efficiently to ensure network security. Future work includes numerical evaluation of our algorithm on live restaking networks [\[u–24](#page-20-0)] and to account for the price volatility and liquidity of r<sup>s</sup> . The latter problem exists as services often pay rewards in their native tokens rather than in the restaked asset [\[Lla24](#page-19-9); [Pat24](#page-19-10); [Sym24\]](#page-19-16) and have to consider the impact of price and liquidity on whether their rewards are sufficient for node operators to be profitable.

### 6 Acknowledgments

We want to thank Tim Roughgarden, Naveen Durvasula, Soubhik Deb, Sreeram Kannan, Victor Xu, Walter Li, Gaussian Process, Manvir Schneider, Theo Diamandis, Matheus Ferreria, Guillermo Angeris, Kshitij Kulkarni for helpful comments and inspiration.

<span id="page-18-5"></span>

### References

<span id="page-18-11"></span><span id="page-18-10"></span><span id="page-18-9"></span><span id="page-18-8"></span><span id="page-18-7"></span><span id="page-18-6"></span><span id="page-18-4"></span><span id="page-18-3"></span><span id="page-18-2"></span><span id="page-18-1"></span><span id="page-18-0"></span>

| [AB22]   | Ayana T Aspembitova and Michael A Bentley. "Oracles in decentralized finance:<br>Attack costs, profits and mitigation measures". In:<br>Entropy<br>25.1 (2022), p. 60.                                                     |
|----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [AMM21]  | Saeed Alaei, Ali Makhdoumi, and Azarakhsh Malekian. "Maximizing sequence<br>submodular functions and its application to online advertising". In:<br>Management<br>Science<br>67.10 (2021), pp. 6030–6054.                  |
| [Bal+15] | Maria-Florina Balcan et al. "Commitment without regrets: Online learning in<br>stackelberg security games". In:<br>Proceedings of the sixteenth ACM conference on<br>economics and computation. 2015, pp. 61–78.           |
| [BS18]   | Eric Balkanski and Yaron Singer. "The adaptive complexity of<br>maximizing a<br>submodular function". In:<br>Proceedings of the 50th annual ACM SIGACT sym<br>posium on theory of computing. 2018, pp. 1138–1151.          |
| [BV04]   | Stephen P Boyd and Lieven Vandenberghe.<br>Convex optimization. Cambridge<br>university press, 2004.                                                                                                                       |
| [CE20]   | Tarun Chitra and Alex Evans. "Why stake when you can borrow?" In:<br>arXiv<br>preprint arXiv:2006.11156<br>(2020).                                                                                                         |
| [Chi21]  | Tarun Chitra. "Competitive Equilibria Between Staking and On-chain Lending".<br>url:<br>In:<br>Cryptoeconomic Systems<br>0.1 (2021).<br>https://cryptoeconomicsystems.pubpub.org/                                          |
| [Chi+24] | Tarun Chitra et al. "An Analysis of Intent-Based Markets". In:<br>arXiv preprint<br>arXiv:2403.02525<br>(2024).                                                                                                            |
| [CK22]   | Tarun Chitra and Kshitij Kulkarni. "Improving proof of stake<br>economic security<br>via MEV redistribution". In:<br>Proceedings of the 2022 ACM CCS Workshop on<br>Decentralized Finance and Security. 2022, pp. 1–7.     |
| [CPR19]  | Xi Chen, Christos Papadimitriou, and Tim Roughgarden. "An<br>axiomatic ap<br>proach to block rewards". In:<br>Proceedings of the 1st ACM Conference on Ad<br>vances in Financial Technologies. 2019, pp. 124–131.          |
| [CRS24]  | Hao Chung, Tim Roughgarden, and Elaine Shi. "Collusion-resilience in transac<br>tion fee mechanism design". In:<br>arXiv preprint arXiv:2402.09321<br>(2024).                                                              |
| [Dai+20] | Philip Daian et al. "Flash boys 2.0: Frontrunning in decentralized exchanges,<br>miner extractable value, and consensus instability". In:<br>2020 IEEE symposium<br>on security and privacy (SP). IEEE. 2020, pp. 910–927. |

- <span id="page-19-0"></span>[DR24] Naveen Durvasula and Tim Roughgarden. *Robust Restaking Networks*. 2024. url: <https://arxiv.org/abs/2407.21785>.
- <span id="page-19-3"></span><span id="page-19-2"></span>[Eig23] EigenLayer Team. *EigenLayer: The Restaking Collective*. 2023. url: [https://docs.eigenlayer.x](https://docs.eigenlayer.xyz/eigenlayer/overview/whitepaper)
- [Eig24] EigenLayer Team. *EIGEN: The Universal Intersubjective Work Token*. 2024. url: <https://docs.eigenlayer.xyz/eigenlayer/overview/whitepaper>.
- <span id="page-19-5"></span>[Fan+19] Giulia Fanti et al. "Compounding of wealth in proof-of-stake cryptocurrencies". In: *Financial Cryptography and Data Security: 23rd International Conference, FC 2019, Frigate Bay, St. Kitts and Nevis, February 18–22, 2019, Revised Selected Papers 23*. Springer. 2019, pp. 42–61.
- <span id="page-19-13"></span>[Joh+23] Nicholas AG Johnson et al. "Concave pro-rata games". In: *International Conference on Financial Cryptography and Data Security*. Springer. 2023, pp. 266– 285.
- <span id="page-19-1"></span>[KDC23] Kshitij Kulkarni, Theo Diamandis, and Tarun Chitra. "Routing MEV in Constant Function Market Makers". In: *International Conference on Web and Internet Economics*. Springer. 2023, pp. 456–473.
- <span id="page-19-8"></span>[LB24] Walter Li and Carson Brown. "Liquid Restaking Token (LRT) Market Risk Framework". In: *Gauntlet* (2024). url: [https://www.gauntlet.xyz/resources/liquid-restaki](https://www.gauntlet.xyz/resources/liquid-restaking-token-lrt-market-risk-framework)
- <span id="page-19-6"></span>[Li24] Walter Li. "Optimizing AVS Allocations for Liquid Restaking Tokens (LRTs)". In: *Gauntlet* (2024). url: [https://www.gauntlet.xyz/resources/optimizing-avs-allocat](https://www.gauntlet.xyz/resources/optimizing-avs-allocations-for-liquid-restaking-tokens-lrts)
- <span id="page-19-4"></span>[Lla24] DeFi Llama. *Restaking — DeFi Llama*. <https://defillama.com/restaking>. July 2024. url: <https://defillama.com/restaking>.
- <span id="page-19-12"></span><span id="page-19-9"></span>[Lla24] Llama Legal. "EigenLayer & LRT Points". In: *LlamaRisk* (2024). url: [https://llamarisk.com/res](https://llamarisk.com/research/eigenlayer-lrt-points)
- [MNW22] Torgin Mackinga, Tejaswi Nadahalli, and Roger Wattenhofer. "Twap oracle attacks: Easier done than said?" In: *2022 IEEE International Conference on Blockchain and Cryptocurrency (ICBC)*. IEEE. 2022, pp. 1–8.
- <span id="page-19-7"></span>[NC24] Michael Neuder and Tarun Chitra. "The Risks of LRTs". In: *ethresearch* (2024). url: <https://ethresear.ch/t/the-risks-of-lrts/18799>.
- <span id="page-19-11"></span><span id="page-19-10"></span>[Pat24] Yash Patil. "EigenLayer Rewards Calculation". In: *HackMD* (2024). url: [https://hackmd.io/u-](https://hackmd.io/u-NHKEvtQ7m7CVDb4_42bA#3-Operator-Reward-Amounts)
- [PRS23] Kalen Patton, Matteo Russo, and Sahil Singla. "Submodular norms with applications to online facility location and stochastic probing". In: *arXiv preprint arXiv:2310.04548* (2023).
- <span id="page-19-14"></span>[Sin+18] Arunesh Sinha et al. "Stackelberg security games: Looking beyond a decade of success". In: IJCAI. 2018.
- <span id="page-19-15"></span>[SVW17] Maxim Sviridenko, Jan Vondr´ak, and Justin Ward. "Optimal approximation for submodular and supermodular optimization with bounded curvature". In: *Mathematics of Operations Research* 42.4 (2017), pp. 1197–1218.
- <span id="page-19-16"></span>[Sym24] Symbiotic Team. "Symbiotic Vault Reward". In: *Symbiotic* (2024). url: [https://docs.symbiotic.f](https://docs.symbiotic.fi/core-modules/vaults#rewards)

- <span id="page-20-1"></span>[TZ23] Apostolos Tzinas and Dionysis Zindros. "The principal–agent problem in liquid staking". In: *International Conference on Financial Cryptography and Data Security*. Springer. 2023, pp. 456–469.
- <span id="page-20-2"></span><span id="page-20-0"></span>[u–24] u–1. *u–1: Eigenlayer Directory*. <https://u--1.com>. July 2024. url: <https://u--1.com>.
- [Yai+23] Aviv Yaish et al. "Speculative Denial-of-Service Attacks in Ethereum." In: *IACR Cryptol. ePrint Arch.* 2023 (2023), p. 956.
- <span id="page-20-3"></span>[YTZ22] Aviv Yaish, Saar Tochner, and Aviv Zohar. "Blockchain stretching & squeezing: Manipulating time for your best interest". In: *Proceedings of the 23rd ACM Conference on Economics and Computation*. 2022, pp. 65–88.

<span id="page-20-4"></span>

## A Unions of p-attacks need not be valid attacks

We first demonstrate an explicit example of a sequence (A<sup>1</sup> , B<sup>1</sup> ), . . . ,(A<sup>T</sup> , B<sup>T</sup> ) such that for f∞(π, A), we have

$$
f_{\infty}(\pi, \cup_{t} A_{t}) \leq \sigma_{\cup_{t} B_{t}}
$$
  
$$
f_{\infty}(\pi, A_{t}) \geq \sigma_{B_{t}}
$$

This will provide intuition for the example we show for general p.

Suppose that we have maxs∈A<sup>t</sup> π<sup>s</sup> = 1.1 for all t ∈ [T] and σ<sup>B</sup><sup>t</sup> = 1 for all t. Then we have

$$
\max_{s \in \bigcup_i A_t} \pi_s = \max_{t \in [T]} \max_{s \in A_t} \pi_s = 1.1
$$

On the other hand, we have σ<sup>∪</sup>tB<sup>t</sup> = P<sup>T</sup> <sup>t</sup>=1 σ<sup>B</sup><sup>t</sup> = T. Therefore we have

$$
f_{\infty}(\pi, A_t) - \sigma_{B_t} = \max_{s \in A_t} \pi_s - \sigma_{B_t} = 1.1 - 1 = 0.1
$$

and

$$
f_{\infty}(\pi, \cup_t A_t) - \sigma_{\cup_t B_t} = 1.1 - T \le 0
$$

for T > 1. We claim that a sufficient condition for the union of valid p-attacks to not be a valid p-attack is

$$
\sum_{t \in [T]} |A_t|^{1/p} < \frac{(\min_v \sigma_v) \sum_{t \in [T]} |B_t|}{\max_{s \in \cup_t A_t} \pi_s}
$$

To see this, note that f<sup>p</sup> (π, A) ≤ (maxs∈<sup>A</sup> π<sup>s</sup> )|A| <sup>1</sup>/p and when this sufficient condition holds, this implies that

$$
f_p(\pi, \cup_t A_t) \le \left(\max_{s \in \cup_t A_t} \pi_s\right) \sum_{t \in [T]} |A_t|^{1/p} \le \left(\min_v \sigma_v\right) \sum_{t \in [T]} |B_t| \le \sigma_{\cup_t B_t}
$$

From this, one can see that is is relatively easy to modify our example for f<sup>∞</sup> to construct examples of p-attacks that are invalid.

![](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2024-Restaking-Security-Pricing/_page_21_Figure_0.jpeg)

<span id="page-21-1"></span>Figure 4: Example of a graph with overlap where the overlap controls the cascading likelihood

<span id="page-21-0"></span>

## B Overlap is easier to control than γ-security

We construct an example to show that the overlap θs,t is a finer means to control cascading than γ-security via an example. Consider the restaking graph in Figure [4](#page-21-1) where θ1,<sup>2</sup> = θ2,<sup>1</sup> = σ∩, as the services only overlap in validator v∩. Suppose that the potential attacks ({si}, {vi}) are profitable but infeasible, *i.e.*

$$
\pi_i > \sigma_i \qquad \qquad \sigma_i < \alpha_s(\sigma_i + \sigma_\cap)
$$

Similarly, the potential attacks ({si}, {v∩}) are profitable and infeasible, *i.e.*

$$
\pi_i > \sigma_{\cap} \qquad \qquad \sigma_{\cap} < \alpha_s(\sigma_i + \sigma_{\cap})
$$

On the other hand, suppose that the potential attacks ({si}, {v<sup>i</sup> , v∩}) are unprofitable but are (tautologously) feasible, *i.e.*

$$
\pi_i < \sigma_i + \sigma_\cap \qquad \qquad \sigma_i + \sigma_\cap > \alpha_s(\sigma_i + \sigma_\cap)
$$

Finally, suppose that the potential attack ({s<sup>1</sup> , s2}, {v<sup>1</sup> , v<sup>2</sup> , v∩}) has zero profit and is (tautologously) feasible, *i.e.*

$$
\pi_1 + \pi_2 = \sigma_1 + \sigma_2 + \sigma_{\cap} \qquad \qquad \sigma_i + \sigma_{\cap} > \alpha_s(\sigma_i + \sigma_{\cap})
$$

Now suppose let σ<sup>1</sup> = σ<sup>2</sup> = σ and that σ<sup>∩</sup> = Kσ for K ≥ 1. When ψ < <sup>σ</sup><sup>∩</sup> σV , we have

$$
R_{\psi}(G) < \psi + \frac{\sigma_i}{\sigma_V} < \frac{1}{2 + K}
$$

since σ<sup>V</sup> = σ<sup>1</sup> + σ<sup>2</sup> + σ<sup>∩</sup> = (K + 2)σ. This is because no attack is feasible without removing σ<sup>∩</sup> and losing σ<sup>i</sup> for i ∈ {1, 2} is not sufficient to cause a cascade. On the other hand, note that

$$
\frac{\pi_i - \sigma}{(K+2)\sigma} < \frac{\sigma_{\cap}}{\sigma_V} = \frac{K}{K+2} < \frac{\pi_i}{(K+2)\sigma}
$$

For large K and π<sup>i</sup> ≤ (1 − ǫ)(K + 2)σ, this implies that Rψ(G) < 1 2+K for ψ < 1 − ǫ. Under these conditions, the graph has low cascading risk and it is completely controlled by σ∩. This implies that local changes to σ<sup>∩</sup> alone (without needing to adjust σ<sup>i</sup> ) are sufficient to ensure low cascade risk. As we demonstrate in the rebalancing section of §[2,](#page-4-0) in the presence of rebalancing, one can bound how low σ<sup>∩</sup> can go and thus, one can bound the worst case cascade.

On the other hand, we will now compute how large σ<sup>∩</sup> would have to be if we enforced γsecurity. Let ǫ<sup>i</sup> = πi−σ be the profit achieved if v<sup>i</sup> could attack s<sup>i</sup> . From the second condition, we have σ<sup>∩</sup> > π<sup>i</sup> − σ<sup>i</sup> = ǫ<sup>i</sup> . Suppose we consider a γ-secure version of this graph where we have stakes σ<sup>1</sup> , σ<sup>2</sup> , σ γ <sup>∩</sup>. The γ-secure condition implies that (1 + γ)(π<sup>1</sup> + π<sup>2</sup> ) < σ<sup>1</sup> + σ<sup>2</sup> + σ γ ∩ which can be rearranged to

$$
\sigma_\cap^\gamma>(\pi_1-\sigma_1)+(\pi_2-\sigma_2)+\gamma(\pi_1+\pi_2)=\epsilon_1+\epsilon_2+\gamma(\pi_1+\pi_2)>2\sigma_\cap+\gamma(\pi_1+\pi_2)
$$

This implies that σ γ <sup>∩</sup> − σ<sup>∩</sup> = Ω(π<sup>1</sup> + π<sup>2</sup> ), suggesting that γ-security is far too strong as all services in this graph have to attract Ω(π<sup>1</sup> +π<sup>2</sup> ) stake. Concretely, suppose that π<sup>1</sup> = \$1, 000 and π<sup>2</sup> = \$1, 000, 000, 000. The γ-security condition implies that service 1, which can only be exploited for at most \$1,000 has to attract stake proportional to \$1,000,001,000 in order to be γ-secure. Yet, if one can control only the stake held by v∩, one can avoid most cascades (*i.e.* for ψ < <sup>σ</sup><sup>∩</sup> σV ) without requiring such a high amount of stake.

<span id="page-22-0"></span>

### C Proof of Claim 2

*Proof.* Let V<sup>s</sup> = B ∩ ∂s and note that B = S s∈V Vs . By inclusion-exclusion, we have

$$
\sigma_B = \sum_{s \in S} \sigma_{V_s} - \sum_{1 \le s < s' \le S} \sigma_{V_s \cap V_{s'}} + \dots = \sum_{\emptyset \ne J \subset S} (-1)^{|J|} \sigma_{\cap_{s \in J} V_s}
$$

We now claim that there exists <sup>ξ</sup> <sup>∈</sup> (0, 1) such that <sup>σ</sup><sup>V</sup>s<sup>1</sup> ∩· · ·∩σ<sup>V</sup>sk ≤ ξ k−1 σ<sup>V</sup>sj for any j ∈ [k]. By assumption, every intersection ∂s∩∂t has at least δKS<sup>1</sup>/p more node operators than any attacking coalition B ⊂ V , since |B| ≤ KS<sup>1</sup>/p. This means that for any pair s, t ∈ S, we have |∂s ∩ ∂t − B| ≥ δKS<sup>1</sup>/p. Therefore, we have

$$
\sigma_{V_s \cap V_t} = \sigma_{(B \cap \partial s) \cap (B \cap \partial t)} \le \left(1 - \frac{(\min_v \sigma_v) |\partial s \cap \partial t - B|}{\sigma_{\partial s \cap \partial t}}\right) \sigma_{V_s} \le \left(1 - \frac{\delta (\min_v \sigma_v) K S^{1/p}}{\overline{\theta}_s}\right) \sigma_{V_s}
$$

Since θ<sup>s</sup> ≤ (max<sup>v</sup> σ<sup>v</sup> ) KS<sup>1</sup>/p, we have <sup>σ</sup><sup>V</sup>s∩V<sup>t</sup> <sup>≤</sup> 1 − δ(min<sup>v</sup> σv) (max<sup>v</sup> σ<sup>v</sup> ) σ<sup>V</sup><sup>s</sup> = ξσ<sup>V</sup><sup>s</sup> , where we defined ξ = 1 − δ(min<sup>v</sup> σv) (max<sup>v</sup> σv) . One can recurse this argument to get σ<sup>V</sup>s<sup>1</sup> <sup>∩</sup>Vs<sup>2</sup> ···∩Vsk ≤ ξ k−1 σ<sup>V</sup>si . Therefore, we have

$$
\sigma_B = \sum_{s \in S} \sigma_{V_s} - \sum_{1 \le s < s' \le S} \sigma_{V_s \cap V_{s'}} + \dots = \sum_{\emptyset \ne J \subset S} (-1)^{|J|} \sigma_{\cap_{s \in J} V_s}
$$
\n
$$
\ge \sum_{s \in S} \sigma_{V_s} - (S - 1) \xi \sigma_{V_s} + \sum_{s, s', s''} \sigma_{V_s \cap V_{s'} \cap V_{s''}} - \binom{S - 1}{3} \xi^3 \sigma_{V_s} - \dots
$$
\n
$$
\ge \sum_{s \in S} \sigma_{V_s} \left( 1 - \sum_{i=0}^{\lfloor \frac{S - 1}{2} \rfloor} \binom{S - 1}{2i + 1} \xi^{2i + 1} \right) \ge \left( 1 - \sum_{i=0}^{\lfloor \frac{S - 1}{2} \rfloor} \left( \frac{e(S - 1)}{2i + 1} \right)^{2i + 1} \xi^{2i + 1} \right) \sum_{s \in S} \sigma_{V_s}
$$

where the last step uses the binomial bound n k ≤ en k k . Note that ξ = 1 − δ(min<sup>v</sup> σv) (max<sup>v</sup> <sup>σ</sup>v) ≤ (S−1)2/p <sup>e</sup>(S−1)<sup>2</sup> , by assumption. This implies that <sup>P</sup>⌊ S−1 2 ⌋ <sup>i</sup>=0 e(S−1) <sup>2</sup>i+1 <sup>2</sup>i+1 ξ <sup>2</sup>i+1 ≤ C S−1 for a constant C < 1. This implies for a costly attack with profit function f<sup>p</sup> that we have

$$
\left(1 - \frac{C}{S - 1}\right) \left(\min_{v} \sigma_{v}\right) |A| \le \sigma_{B} \le f_{p}(\pi, A) \le \left(\max_{s} \pi_{s}\right) |A|^{1/p}
$$
\n
$$
\text{the claim } |A|^{1 - 1/p} \le \max_{s} \pi_{s} \quad 2 \qquad \max_{s} \pi_{s} \quad 2(S - 1) \le \max_{s} \pi_{s} \quad 2(S - 1) \le \max_{s} \pi_{s} \quad 2(S - 1) \le \sigma_{B}
$$

which implies the claim |A| <sup>1</sup>−1/p ≤ max<sup>s</sup> π<sup>s</sup> min<sup>v</sup> σ<sup>v</sup> 2 (1<sup>−</sup> <sup>C</sup> <sup>S</sup>−<sup>1</sup> ) = max<sup>s</sup> π<sup>s</sup> min<sup>v</sup> σ<sup>v</sup> 2(S−1) <sup>S</sup>−1−<sup>C</sup> ≤ max<sup>s</sup> π<sup>s</sup> min<sup>v</sup> σ<sup>v</sup> 2(S−1) S−2

<span id="page-23-0"></span>

### D Approximation Algorithm

Algorithm [1](#page-24-0) proceeds to output a set of rewards r<sup>s</sup> using the following steps:

- 1. Let C(G) = {(A<sup>1</sup> , B<sup>1</sup> ), . . . ,(A<sup>T</sup> , B<sup>T</sup> ) : (A<sup>i</sup> , B<sup>i</sup> ) ∈ (S−∪<sup>i</sup>−<sup>1</sup> <sup>j</sup>=1A<sup>i</sup> , V −∪<sup>i</sup>−<sup>1</sup> <sup>j</sup>=1B<sup>i</sup> )} be the set of possible attack sequences on a restaking graph G and let C<sup>T</sup> (G) = {s ∈ C(G) : |s| ≤ T} be the set of sequences of length at most T.
- 2. For a sequence (A<sup>1</sup> , B<sup>1</sup> ), . . . ,(A<sup>T</sup> , B<sup>T</sup> ) ∈ C<sup>T</sup> (G), define the net profit function

<span id="page-23-1"></span>
$$
Profit_p((A_1, B_1), \dots, (A_T, B_T)) = \sum_{t=1}^{T} f_p(\pi, A_i) - \sigma_{B_i}
$$
 (22)

3. Given an upper bound T ∈ N on the attack length, utilize a greedy algorithm to find (Aˆ 1 , Bˆ 1 ), . . . ,(Aˆ k , Bˆ k ) ∈ C<sup>T</sup> (G), k ∈ [T], such that

<span id="page-23-2"></span>
$$
Profit((\hat{A}_1, \hat{B}_1), ..., (\hat{A}_k, \hat{B}_k)) \ge \alpha(p) \max_{s \in C_T(G)} Profit(s)
$$
\n(23)

where the approximation factor α(p) only depends on the choice of p and bounds on min<sup>s</sup> π<sup>s</sup> , max<sup>s</sup> π<sup>s</sup>

4. Given this sequence, compute a rebalance D and rewards ˆr<sup>s</sup> that ensure that (Aˆ 2 , Bˆ 2 ) is infeasible after rebalancing

<span id="page-24-0"></span>input : Incentivized restaking graph: G = (S, V, E, α, σ, π, r, c) Upper bound on maximal attack sequence length: T ∈ N Curvature of submodularity: p ∈ (1, ∞) output: Approximately Optimal Reward Vector: ˆr ∈ R S + (Aˆ 1 , Bˆ 1 ), . . . ,(Aˆ k , Bˆ k ) ← Greedy(Profit<sup>p</sup> , T) (See Algorithm [2\)](#page-25-0); r ← ∅; for s ∈ S do D ← ∅; maxSoFar ← −∞ ; r<sup>s</sup> ← σ∂s−B<sup>ˆ</sup> 1 maxv∈<sup>V</sup> σ<sup>v</sup> + c<sup>s</sup> ; while maxSoFar < 0 do for v ∈ V do // Solve for ˆf with an interior point method maxSoFar ← max( ˆf(r<sup>s</sup> , σ<sup>v</sup> ), maxSoFar); end if maxSoFar ≥ 0 then break; end r<sup>s</sup> ← 2r<sup>s</sup> ; end end for r<sup>s</sup> ∈ r do // Increase reward by profit approximation error r<sup>s</sup> ← <sup>r</sup><sup>s</sup> E(p) ; end return r; Algorithm 1: Compute Approximately Optimal Rewards 5. Return rewards rsv = rˆsv 1−e −α(p)

We claim such rewards will incentive a graph G with Rψ(G) ≤ ψ + C S <sup>1</sup>−1/p while only being Gα(p)-times worse than the minimum rewards needed to achieve such a graph in the worse case, where G is the integrality gap.

Sequential Submodularity. We first claim that the profit function [\(22\)](#page-23-1) is a *sequentially submodular* function [\[AMM21](#page-18-4); [BS18](#page-18-11)]. To define a sequentially submodular function, we consider sets of sequences S <sup>∞</sup> = S <sup>k</sup><sup>∈</sup>N{(s<sup>1</sup> , . . . , s<sup>k</sup> ) : s ∈ S} of a set S. We define a partial order < for A, B ∈ S<sup>∞</sup> where A < B iff A is a subsequence of B. Moreover, given two sequences A = (s<sup>1</sup> , . . . , s<sup>k</sup> ), B = (t<sup>1</sup> , . . . , t<sup>j</sup> ) ∈ S<sup>∞</sup>, we define the concatenation A ⊥ B = (s<sup>1</sup> , . . . , s<sup>k</sup> , t<sup>1</sup> , . . . , t<sup>j</sup> ) ∈ S<sup>∞</sup>. A function f : S <sup>∞</sup> → R is sequentially submodular if for all A < B and C ∈ S<sup>∞</sup> we have

$$
f(B \perp C) - f(B) \le f(A \perp C) - f(A)
$$

Note that this is a diminishing marginal utility condition, much like the standard set submodularity definition, f(S ∪ T) + f(S ∩ T) ≤ f(S) + f(T). In our scenario, we have S <sup>∞</sup> = C(G) and note that Profit is a sequentially submodular function since each term f<sup>p</sup> (π, A) − σ<sup>B</sup> is set submodular (as it is the sum of two submodular functions).-

<span id="page-25-0"></span>input : Sequentially submodular function f : S <sup>∞</sup> → R, Time horizon T ∈ N output: (A<sup>1</sup> , B<sup>1</sup> ), . . . ,(A<sup>k</sup> , B<sup>k</sup> ) with k < T (Aˆ 1 , Bˆ 1 ), . . . ,(Aˆ k , Bˆ k ) ← Greedy(Profit<sup>p</sup> , T); n ← length of S; Initialize t ← 0; i ← 1; H ← ∅; while t < T do Find s<sup>i</sup> ∈ S such that u(H ⊥ s<sup>i</sup> ) − u(H) ≥ α maxs∈<sup>S</sup> u(H ⊥ s) − u(H) H ← H ⊥ s<sup>i</sup> end return H; Algorithm 2: Greedy Sequential Submodular Optimization (Algorithm 3 of [\[AMM21](#page-18-4)])

Approximation Error. We next recall a theorem from [\[AMM21\]](#page-18-4) that demonstrates that a greedy algorithm has low approximation error for sequentially submodular functions:

<span id="page-25-1"></span>Theorem 2. *[\[AMM21,](#page-18-4) Thm. 3] Suppose* f : S <sup>∞</sup> → R *is a sequentially submodular function. Suppose that for a history* S = (s<sup>1</sup> , . . . , s<sup>T</sup> ) ∈ S<sup>∞</sup>*that* f *satisfies the following for all* t ∈ [T−1]

$$
f((s_1,\ldots,s_t)\perp s_{t+1})-f(s_1,\ldots,s_t)\geq \alpha \max_{s\in\mathcal{S}}f((s_1,\ldots,s_t)\perp s)-f((s_1,\ldots,s_t))
$$

*for* α > 0*. Then we have*

$$
\frac{f((s_1, \ldots, s_T))}{\max_{s \in \mathcal{S}^{\infty}} f(s)} \ge 1 - \frac{1}{e^{\alpha}}
$$

*where* (s<sup>1</sup> , . . . , s<sup>T</sup> ) *is the history generated by the greedy algorithm [2](#page-25-0)* This theorem implies that if we can find a lower bound on the marginal increase, then we can bound the worst case approximation error. We now claim that if min<sup>s</sup> <sup>π</sup><sup>s</sup> max<sup>s</sup> π<sup>s</sup> ≥ K and as |A<sup>t</sup> | ≥ 1, then [\(23\)](#page-23-2) holds with

$$
\alpha(p) \ge KS^{-\frac{1}{p}}
$$

To see this, note that

$$
f_p(\pi, A_i)^p = \sum_{s \in A_i} \pi_s^p \ge (\min_s \pi_s)^p |A_i| \ge K^p (\max_s \pi_s)^p \ge \frac{K^p (\max_s \pi_s)^p}{S} S \ge \frac{K^p}{S} \sum_{s \in A} \pi_s^p
$$

for any other set A. This implies that

$$
f_p(\pi, A_i) \ge \frac{K}{S^{1/p}} \max_{A} f_p(\pi, A)
$$

which implies that α(p) ≥ K S 1/p

Generally, we will have KS<sup>−</sup>1/p ≤ σmaxV . This implies that α(p) increases as p increases. Using Theorem [2,](#page-25-1) this implies that the greedy algorithm of [\[AMM21](#page-18-4)] achieves an approximation error of

$$
E(p) = 1 - e^{-\alpha(p)} = 1 - e^{-KS^{-1/p}} \ge \frac{K}{2S^{1/p}}
$$

where the last inequality holds when K/S<sup>1</sup>/p ≤ 1 <sup>2</sup> This error is highest when p = 1 and lowest when p = ∞. As such, a service can view choosing p ∈ [1, ∞) as choosing a security level (*e.g.* secure up to node operator cartels of size O(S <sup>1</sup>/p)) and then utilize our algorithm to choose the rewards to ensure security. These rewards are guaranteed to be within O( 1 E(p) ) of the minimum possible rewards needed to achieve security but can be easily computed.

Since Algorithm [1](#page-24-0) optimizes ˆf(r<sup>s</sup> , k) instead of f(r<sup>s</sup> ), it computes an overestimate of the optimal rewards if f(r<sup>s</sup> ) is feasible. This overestimate is bounded by the integrality gap G = max<sup>r</sup>s><sup>0</sup> maxv∈<sup>V</sup> f(r<sup>s</sup> , σ<sup>v</sup> ) − f(r<sup>s</sup> ), which gives the additive term in the approximation error.
