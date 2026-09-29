---
title: "Source Paper: Competitive Equilibria Between Staking and On-Chain Lending"
description: "A full replica of the paper, converted from its openly licensed source with figures and equations."
licence: "Journal version: Creative Commons Attribution 4.0 International (CC BY 4.0). arXiv preprint: CC BY-NC-SA 4.0."
source_url: "https://doi.org/10.21428/58320208.9ce1cd26"
captured: 2026-09-29
---

*Tarun Chitra (2020). Competitive Equilibria Between Staking and On-Chain Lending. Cryptoeconomic Systems, published 30 November 2020 (preprint arXiv:2001.00919). [https://doi.org/10.21428/58320208.9ce1cd26](https://doi.org/10.21428/58320208.9ce1cd26). Licence: Journal version: Creative Commons Attribution 4.0 International (CC BY 4.0). arXiv preprint: CC BY-NC-SA 4.0. Converted on 2026-09-29 from `chitra-2020-staking-lending-2001.00919.pdf` with marker, figures and equations included. Check a passage against the original before quoting it.*

# **Competitive equilibria between staking and on-chain lending**

Tarun Chitra, Gauntlet Networks, Inc.

Proof of Stake (PoS) is a burgeoning Sybil resistance mechanism that aims to have a digital asset ("token") serve as security collateral in crypto networks. However, PoS has so far eluded a comprehensive threat model that encompasses both Byzantine attacks from distributed systems and financial attacks that arise from the dual usage of the token as a means of payment and a Sybil resistance mechanism. In particular, the existence of derivatives markets makes malicious coordination among validators easier to execute than in Proof of Work systems. We demonstrate that it is also possible for on-chain lending smart contracts to cannibalize network security in PoS systems. When the yield provided by these contracts is more attractive than the inflation rate provided from staking, stakers will tend to remove their staked tokens and lend them out, thus reducing network security. In this paper, we provide a simple stochastic model that describes how rational validators with varying risk preferences react to changes in staking and lending returns. For a particular configuration of this model, we provide a formal proof of a phase transition between equilibria in which tokens are predominantly staked and those in which they are predominantly lent. We further validate this emergent adversarial behavior (e.g. reduced staked token supply) with agentbased simulations that sample transitions under more realistic conditions. Our results illustrate that rational, non-adversarial actors can dramatically reduce PoS network security if block rewards are not calibrated appropriately above the expected yields of on-chain lending.

## **1. INTRODUCTION**

There is currently an intense effort to improve the scalability of blockchains and other decentralized value systems known as crypto networks. These networks use cryptographic proofs and game theoretic constructions to provide tamper-resistant updates to a global ledger. While there are a variety of research and engineering challenges in setting up these systems, one of the major bottlenecks to network throughput is the cost of Sybil resistance mechanisms within a decentralized consensus protocol. Proof of Work (PoW) networks achieve Sybil resistance by requiring consensus-participating nodes to provably burn energy to compute many iterations of a particular cryptographic hash function. PoW, while effective and permissionless, expends a large amount of natural resources and has resulted in concentrated ownership of the underlying digital assets (e.g. Bitcoin). Proof of Stake (PoS) was first introduced as an alternative in a 2012 BitcoinTalk post [\[QuantumMechanic 2011\]](#page-21-0) that showed the equivalence between a PoW miner who could immediately reinvest her block rewards into hash power within the network and a PoS validator who can reinvest their validation earnings into network security. PoS works by instead allowing users to 'lock' a digital asset, known as a token, into a smart contract that provides them with token-denominated returns in exchange for validating transactions and providing network security. Using shared, verifiable randomness, all network participants can use a multi-party computation protocol to sample the distribution of asset ownership locked into the contract and choose participant(s) who receive the block reward emitted by the network. This is analogous to how PoW can be thought of as a protocol that samples the distribution of hash power to choose the next block producer [\[Pass et al. 2017\]](#page-21-1). One of the main benefits of PoS is that one does not have to commit a costly natural resource to participate in the network. Instead, a purely digital asset is used as collateral for the network and the network can control its supply to provide the desired properties. For an introductory background on PoS protocols and their complex security models, please see [\[Kiayias et al. 2017;](#page-20-0) [King and Nadal 2012;](#page-20-1) [Saleh 2019;](#page-21-2) [Daian et al. 2019;](#page-20-2) [Neuder et al. 2019\]](#page-21-3).

In this paper, we show that these purported benefits do not come for free. As PoS algorithms inherently connect a decentralized network's security with the capital cost of a digital asset, PoS protocols tie their security to the cost of capital rather than to the cost of a natural resource. Volatility in the cost of capital, which is usually higher than that of natural resources [\[Poelhekke and van der Ploeg](#page-21-4) [2007\]](#page-21-4), can have adverse effects on capital commitments to PoS networks. The main result we show is that alternative sources of yield can drive staking token capital allocators to collectively drain a network's security, akin to a bank run. In particular, we find that PoS in deflationary systems is unstable and unlikely to work and that for more reasonable inflation rates, the effectiveness of PoS depends on the relationship between staking and lending rates. This relationship should inform the further design of PoS systems, especially as a large number of networks are launching in 2020.

## **Transitioning Security from PoW to PoS**

The move from PoW to PoS presents a plethora of challenges. In a PoS system, the network relies on participants who are staked in the system to stay online in order to achieve liveness. In practice, this is implemented by slashing participants — redistributing or burning a participant's stake that is committed for validation rewards when they perform a malicious act — who go offline or miss a block that they are supposed to produce. Moreover, there are attacks that are unique to PoS such as the *nothing-at-stake* and *long-range* attacks [\[Houy 2014;](#page-20-3) [Gazi et al. 2018\]](#page-20-4). These attacks are ˇ impossible in PoW, as resource costs of digital assets are practically zero, especially when compared to costs of natural resources [\[Brown-Cohen et al. 2019\]](#page-19-0). Lastly, as the asset used for staking is also the medium of exchange, a malicious validator needs to only aggregate 33% of the token to perform a Byzantine attack.[1](#page-1-0)

However, if there exist physically settled futures contracts on PoS tokens, then it is possible for an attacker to buy futures that allow for staking participants to sell their staked token in the future. This attacker can aggregate this stake and upon reaching an attack threshold, begin to perform a double spend or other malicious attack [\[Chitra et al. 2019\]](#page-20-5). As these derivatives can be settled off-chain (e.g. using a centralized exchange like BitMEX or Deribit), monitoring of this type of attack can be difficult. In PoW, one would need to aggregate the hash power needed to produce 50% of the network's hashrate, which is a much harder task that relies on aggregating data centers, specialized hardware, cheap electricity, and a favorable country of residence. Moreover, PoS systems are vulnerable to *financial attacks*, or attacks that utilize the fact that PoS tokes serve as both the instrument of security and as the medium of exchange. Such attacks are often feasible due to emergent and unexpected coordination between participants in a PoS network and an external market.

Given the vulnerability of PoS to cartel-like behavior that can be coordinated via an external market, one might naturally ask if there are also any endogenous financial risks on PoS protocols that support smart contracts. Recently, there has been an uptick in interest in Decentralized Finance ('DeFi'), which uses smart contracts to implement standard financial primitives in a purely on-chain manner [\[Klages-Mundt and Minca 2019\]](#page-20-6). These primitives, such as exchanges [\[Warren and Bandeali 2017\]](#page-21-5), lending [\[Leshner and Hayes 2019\]](#page-21-6), and stable reserve currencies [\[Kamvar et al. 2019;](#page-20-7) [Al-Naji](#page-19-1) [et al. 2017;](#page-19-1) [MakerDAO 2017\]](#page-21-7), decentralize banking functions by creating incentives that encourage rational participants to receive arbitrage profits for maintaining the system's security, while also meting out financial punishments for misbehavior. Instead of explicitly punishing fraud via legal recourse, these protocols use purely financial modes of recourse to encourage network participation and growth. One of the biggest sectors within DeFi is the on-chain lending market, in which the largest single platform is Compound [\[Leshner and Hayes 2019\]](#page-21-6), an Ethereum smart contract that allows users to lend and borrow assets that conform to the ERC-20 token standard. The Compound smart contract has held up to \$175 million of assets, has had over 40% of the float of the Dai stablecoin [\[MakerDAO 2017\]](#page-21-7), and saw double digit asset growth during 2019. Given that Ethereum is likely to transition to PoS soon one must evaluate: are there any financial attacks against chain security that result from an on-chain lending system? A simple gedanken experiment for answering this question from the view of on-chain lending might be of the form:

Suppose that we assume that validators are rational financial agents. Would they not simply move their assets between staking and on-chain lending, depending on which has a higher yield?

<span id="page-1-0"></span><sup>1</sup>The majority of Proof of Stake systems use traditional Byzantine Fault Tolerant algorithms [\[Lamport et al. 1982;](#page-20-8) [Castro](#page-20-9) [et al. 1999\]](#page-20-9) once validators are sampled, which is why they are only resistant to 33% Byzantine actors versus 50% for Nakamoto consensus

<span id="page-2-0"></span>![](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2020-Staking-and-Lending-Equilibria/_page_2_Figure_0.jpeg)

Fig. 1: Staking and lending with Compound's smart contract parameters (left) and more aggressive parameters with yields of up to 75%. The y-axis in both figures is the percentage of the total outstanding token supply that is allocated to staking versus that which is allocated to lending. This simulation had 512 agents whose parameters were sampled as in equations [\(3\)](#page-8-0) and [\(4\)](#page-9-0). Note that the two figures have different time-scales to illustrate how the parameters of the model (see §[3.2.1\)](#page-6-0) affect the oscillations between staked and lent supply

In particular, it is clear that there is a relationship between the price of capital availability and participant's willingness to stake, as stakers have to earn more than a risk-adjusted market rate on their staked capital. However, unlike Proof of Work, there are no physical limits that prevent validators in staking networks from rapidly moving their assets into higher yielding activities. Onchain lending, such as Compound, makes this particularly efficient, as validators simply have to post a single Ethereum transaction to unbond their tokens and begin earning yield within a single block time. High lending yields would likely lead to a reduction in network security (e.g. a financial attack) as these yields would encourage rational actors to unexpectedly coordinate and reduce network security by optimizing for financial gain.

We answer these questions with a stochastic model that can be theoretically solved in certain situations and is easily simulated via Monte Carlo methods. Our aim is not to model realistic networks parameters perfectly, but rather to show that even in the most simplified model of agents optimizing portfolios composed of staked and lent tokens, on-chain lending can cause dramatic volatility in network security. In particular, we construct an agent-based model, where each network participant is represented via an agent with a utility and decision function. Agent-based modeling has been previously used for modeling censorship properties in sharded PoW chains [\[Chitra et al. 2019\]](#page-20-10) and can serve as a conduit for comparing theoretical results to empirical data in a statistically rigorous manner. Our model for rational network agents involves having each participant view their total token wealth as a two component portfolio of tokens staked and lent. We assume that the agents

<span id="page-3-0"></span>![](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2020-Staking-and-Lending-Equilibria/_page_3_Figure_0.jpeg)

Fig. 2: Plots of relative amount of staking to lending, with inflation increasing in a clockwise manner. When these plots are negative, there is, on average, more lending than staking and vice-versa, when positive. When we are deflationary (top two rows), we see that regardless of the lending rate parameters (the x-axis is β<sup>0</sup> and the y-axis is β<sup>1</sup> from equation [\(1\)](#page-6-1)), tokens on average lent. This empirically demonstates that there is a phase transition from a lending-dominated regime (which is deflationary) to one that is staking-dominated and inflationary. This simulation also uses 512 agents and the titles state the inflation rate (which is deflationary if it is less than 1), block reward, half-life, and borrow threshold (see §[5.3\)](#page-15-0) and each sample involves an average over a hundred random seeds.

have different risk preferences and locally optimize their token portfolios using mean-variance optimization [\[Markowitz 1952\]](#page-21-8), which allows for agents to adjust their portfolios based on observed returns and risk preferences. Figure [2](#page-3-0) illustrates that there is a phase transition in inflation rate that leads to tokens going from being predominantly lent in deflationary regimes to predominantly staked in inflationary regimes. Moreover, figure [3](#page-4-0) shows that the spread between borrowing and lending rates is significantly worse for deflationary PoS assets, further confirming the existence of a phase transition. We explicitly state our simplifying assumptions in §[2](#page-4-1) and note that agent-based modeling allows one to relax these assumptions and analyze how these results carry over to real PoS protocols, such as Cosmos [\[Buchman 2019\]](#page-19-2) and Tezos [\[Goodman 2014\]](#page-20-11). In section §[4,](#page-10-0) we prove properties of this model that match the observed phase transition from figures [2](#page-3-0) and [5.](#page-16-0) A single sample path is depicted in Figure [1,](#page-2-0) which visually show that agents participating in on-chain lending and staking can cause a "flippening," where there are more assets lent out than staked. The observed volatility in the amount of assets staked is tantamount to dramatically reducing the cost of taking over a staking network, which implies that the security model of PoS networks needs to account for attacks on the network that stem from reduced cost of capital. The combination of theoretical and simulation-based results demonstrate that the threat model for PoS networks needs to be expanded to include financial attacks that result from yield competition with on-chain financial products. For provenance, note that the mathematical notation used in this paper is documented in Appendix [A.](#page-22-0)

<span id="page-4-0"></span>![](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2020-Staking-and-Lending-Equilibria/_page_4_Figure_0.jpeg)

Fig. 3: Plots of the relative spread between borrowing and lending rates. If the value is higher, then borrowing costs more than lending. Note that in the deflationary regime, as the lending rates increase (e.g. as β0,β<sup>1</sup> from [\(1\)](#page-6-1) increase), the spread also increases, whereas this effect is far more muted. The simulation parameters are the same as figure [2.](#page-3-0)

<span id="page-4-1"></span>

## **2. PROTOCOL ASSUMPTIONS**

In order to simplify our model, we will make some simplifying assumptions. These assumptions hold for all models analyzed in this paper and they focus on properties of the underlying distributed ledger rather than properties about the economic behavior of participants, which is described in the proceeding section.

Assumption 1 (Cryptographic). *All sampling processes use true randomness and not pseudorandomness*

This differs from many standard cryptographic threat models that assume pseudorandomness and provide an ε-approximation to true random sampling [\[Koblitz and Menezes 2015\]](#page-20-12). In the Appendix, we use this property to ensure that our PoS algorithm is non-anticipating (e.g. adapted to a suitably chosen filtration), allowing for conditional probabilities to be computed without having to aggregate the ε error terms. One can remove this assumption, in a similar manner to [\[Chan et al. 2018\]](#page-20-13), with a significant increase in proof complexity.

Assumption 2 (Distributed Systems). *All communication between participants is synchronous.*

This can be relaxed to partial synchrony, with an increase in complexity in the proofs and simulations described in the following section.

Assumption 3 (Identity). *All pseudonymous identities are known by all participants and the number of participants (measured by unique addresses), n, is fixed.*

Assumption 4 (Time). *The entire system will update at discrete time intervals, with each tick to be thought of as a block update.*

While participants will likely execute strategies in continuous time, assuming discrete time evolution ensures that participants only respond to event updates that are received on-chain. One can also remove this assumption at the cost of increased variance using 'Poissonization' techniques [\[Kane](#page-20-14) [2016\]](#page-20-14) and 'sleepy consensus' assumptions [\[Pass and Shi 2017\]](#page-21-9).

Assumption 5 (No External Markets). *Only on-chain lending, borrowing, and staking will be considered.*

We are ignoring off-chain lending (e.g. OTC desks or lending businesses, such as Galaxy and Tagomi) and are assuming that there always exists block space for any participant's action to succeed. We are omitting this to reduce the complexity of our model, as off-chain lending has varied pricing models and term structures.

Assumption 6 (Money Supply is Deterministic). *The block reward at time t*,*R<sup>t</sup> and the money supply at time t*,*S<sup>t</sup>* = ∑ *t <sup>s</sup>*=<sup>0</sup> *R<sup>t</sup> are deterministic and known to all participants.*

In particular, we avoid assuming that there exist governance mechanisms for changing the block reward, which have been proposed for protocols such as Algorand [\[Gilad et al. 2017\]](#page-20-15) and Celo [\[Kamvar et al. 2019\]](#page-20-7).

Assumption 7 (No Transaction Fee Revenue). *The only revenue that validators receive from staking comes from the block reward.*

This is a model assumption that removes the complexity of modeling crypto network fee markets, which currently have unstable dynamics and are poorly understood.

Assumption 8 (PoS). *The following properties hold for our idealized PoS algorithm:*

- *—* No compounding*: PoS mechanism uses epoch-based sampling and does not immediately reinvest block rewards. This is to avoid the concentration behavior described in [\[Fanti et al. 2019\]](#page-20-16). One can relax our model to handle Polya urn processes, at the cost of significantly worse variance. ´*
- *—* Single validator per block*: To simplify the model, we avoid using committees [\[Gilad et al. 2017;](#page-20-15) [Rocket et al. 2019;](#page-21-10) [Kamvar et al. 2019;](#page-20-7) [Goodman 2014;](#page-20-11) [Buchman 2019;](#page-19-2) [Chitra and Chitra 2019;](#page-20-17) [Pass and Shi 2018;](#page-21-11) [Neuder et al. 2019\]](#page-21-3) and verifiers [\[Bagaria et al. 2018;](#page-19-3) [Baudet et al. 2018\]](#page-19-4) as they add more variance and make both formal and simulation methods more difficult.*
- *—* Constant slashing probability*: We assume that each validator has a fixed probability pslash of being slashed on a block that they produce. This is simplistic as it assumes that all validators have the same chance of being slashed, regardless of stake and validation history. However, in practice, we have seen very few live slashes and this model encourages simpler formal and simulation analysis.*
- *—* Sharded state is synchronously traversed *Any sharded state in our PoS blockchain is read synchronously and we assume linearizability in our blockchain. This can be relaxed to nonlinearizable protocols like Avalanche [\[Rocket et al. 2019\]](#page-21-10), but will depend on the scoring function used for each branch.*
- *—* No unbonding period *We do not assume that the PoS protocol has an unbonding period like that of Cosmos [\[Buchman 2019\]](#page-19-2) or Tezos [\[Goodman 2014\]](#page-20-11).*

## **3. MODEL**

## **3.1. PoS Model**

Let *S<sup>t</sup>* be the total outstanding token supply of a PoS protocol at time *t* and let *S<sup>t</sup>* = ζ*<sup>t</sup>* +`*<sup>t</sup>* , where ζ*t* is the number of staked tokens and `*<sup>t</sup>* is the number of lent tokens. We use a simple model of a PoS system that samples a single block producer from a discrete time-series of stake distributions, denoted by πstake(*t*) ∈ ζ*t*∆ *n* , where ∆ *n* is the *n*-dimensional probability simplex (see Appendix [A\)](#page-22-0). The main input parameters are:

— πstake(0): Initial asset distribution

- *R<sup>t</sup>* : Staking block reward at block height *t*
- *S*(*i*,πstake): Slash that validator *i* receives if the staking distribution is πstake

The formal specification of the algorithm can be found in Algorithm [1](#page-23-0) in Appendix [B.](#page-23-1) The algorithm state includes the current stake distribution, the current epoch's reward set, the current epoch's slash set, and the current block time. At a high-level, for each block, we select a validator who should receive a block reward and decide if they are to be slashed by flipping a coin with probability *p*slash. If they are slashed, we add their *id* and the amount that they are to be slashed to the current epoch's slash set. Otherwise, we add them to the block reward set. The algorithm updates the stake distribution on a per epoch basis.

#### **3.2. Lending Model**

We will study two models for lending, one involving an explicit model for borrowing demand and one that is implicit. The implicit model, which is simpler, provides a prototype for constant borrowing demand and is amenable to theoretical results. On the other hand, the model involving an explicit description of borrowing demand is more realistic and amenable to being fit by historical data.

<span id="page-6-0"></span>*3.2.1. Two-State Lending Model.* In the two-state lending model, we track the time evolution of two token distributions, πstake(*t*),πlend(*t*) ∈ *St*∆ *n* , which respectively represent the distribution of staked tokens and those locked in a lending contract. The *i*th component of the stake distribution, πstake(*t*)*<sup>i</sup>* , corresponds to the amount of tokens that the *i*th agent has staked. Each agent has a wealth *Wi*(*t*) at time *t* that is equal to the sum of their portfolio of staked and lent tokens, i.e. *Wi*(*t*) = πstake(*t*)*<sup>i</sup>* +πlend(*t*)*<sup>i</sup>* . By definition, the total lending supply is equal to the sum of all lent portfolios, i.e. `*<sup>t</sup>* = kπlend(*t*)k1, and the total money supply is equal to the sum of all portfolios, i.e. *S<sup>t</sup>* = kπstake(*t*)k<sup>1</sup> +kπlend(*t*)k1. At each time step, agents update their portfolios based on returns accrued from the previous time step and after portfolios are updated, the lending rate, γ*<sup>t</sup>* , is updated based on the total amount lent. This means that we are making two implicit assumptions:

- (1) *Constant relative borrowing demand*: We are assuming that ratio of borrowing demand (represented via a quantity of tokens) to the total token supply stays constant, as the rate only depends on the lending and staking supplies. Formally, this means that the demand at time *t* is equal to *kS<sup>t</sup>*
- (2) *Flows are the only determining factor*: Participants who move tokens from staking to lending or vice versa are the only causes for changes to the lending rate

We draw inspiration from Compound [\[Leshner and Hayes 2019\]](#page-21-6), which provides a simple formula for the borrow lending rate, β*<sup>t</sup>* , and the lending rate, γ*<sup>t</sup>* . The Compound model computes a utilization rate *U<sup>t</sup>* at block height *t*, which is the ratio of the borrowing demand to the token supply locked in the contract, and uses that to update formulas for β*<sup>t</sup>* , γ*t* . Mathematically, they define the utilization rate as

<span id="page-6-1"></span>
$$
U_t = \frac{kS_t}{\ell_t + kS_t}
$$

We compute the borrow and lend rates using the following formulas, where β0,β<sup>1</sup> ∈ (0,1) are interest-rate parameters and γ<sup>0</sup> ∈ (0,1) is a measure of the spread between lending and borrowing (i.e. 1−γ<sup>0</sup> is the relative spread).

$$
\beta_t = U_t(\beta_0 + \beta_1 U_t) \tag{1}
$$

$$
\gamma_t = (1 - \gamma_0)\beta_t \tag{2}
$$

For reference, the Compound V2 contract uses the values β<sup>0</sup> = 5% and β<sup>1</sup> = 45%. As depicted in Figure [1,](#page-2-0) there can be an enormous amount of volatility in the fraction of the token supply that is lent, `*<sup>t</sup> St* . In §[4,](#page-10-0) we prove tail bounds on the inflows and outflows of lent tokens over a time step, e.g. Pr[|`*<sup>t</sup>* − `*t*−1| > ε*S<sup>t</sup>* ], that explicitly depend on the block reward, *R<sup>t</sup>* and the interest rate parameters. These bounds suggest that even for the overly simplistic setting of the two-state model, PoS protocols need to carefully choose their block rewards if they desire to have a large fraction of the outstanding token supply staked at all times.[2](#page-7-0)

*3.2.2. Three-State Model.* Instead of assuming that there is constant relative borrowing demand, we can relax this by specifying an additional distribution, πborrow(*t*), such that πtoken = πstake + πlend +πborrow and *S<sup>t</sup>* = ζ*<sup>t</sup>* +`*<sup>t</sup>* +ξ*<sup>t</sup>* , where ξ*<sup>t</sup>* = kπborrow(*t*)k<sup>1</sup> is the total amount borrowed at time *t*. In this world, the utilization ratio is now defined as:

$$
U_t = \frac{\xi_t}{\ell_t + \xi_t}
$$

Formally analyzing this model has a variety of difficulties that stem from that fact that we have to explicitly model the borrow demand distribution and disentangle how it couples to each participant's local model of risk, which is defined in the next section. In §[5,](#page-14-0) we simulate this model with a variety of different borrowing demand distributions, but all formal proofs that follow only analyze the twostate lending model. Since the pool of borrowers (e.g. arbitrageurs) is often disjoint from the pool of stakers and lenders, we will make the following assumption:

<span id="page-7-1"></span>Assumption 9 (Borrowing demand is independent of staking and lending). *The borrowing demand distribution* π*borrow is probabilistically independent of the lending and staking distributions.*

<span id="page-7-2"></span>

#### **3.3. State Transition**

The final task needed to completely specify this model is to define the state transition rule that sends πlend(*t*),πborrow(*t*), πtoken(*t*) to πlend(*t* + 1),πborrow(*t* + 1),πtoken(*t* + 1). As per Assumption [9,](#page-7-1) the evolution of πborrow(*t*) is independent of staking and lending, and will be specified separately in §[5.](#page-14-0) We therefore need to specify state transition rules on a per agent basis, where each agent's state is their token portfolio (πstake(*t*)*<sup>i</sup>* ,πlend(*t*)*i*). Traditionally, the strategy space of rational actors is described via an expected utility function that an agent aims to maximize by taking various allowable actions. Before specifying the strategy space that we will sample, let's consider a few examples to motivate the need for agents who have varying risk preferences. If at time *t*, staking is returning more than lending and every agent moves their entire portfolio from lending to staking, then we will observe a correlated spike in lending rates `*<sup>t</sup>* will go to zero and *U<sup>t</sup>* = 1. Moreover, the relative staking reward to any agent will decrease as *S<sup>t</sup>* will increase by the amount of tokens that flow from lending to staking as the expected return on an epoch for an agent is their staked tokens divided by the token supply, <sup>π</sup>stake(*t*)*<sup>i</sup> St*−`*t* . Thus the greedy strategy of moving all of one's assets to the higher yielding activity and causes drastic swings in the relative yields of staking and lending is unstable and doesn't accurately represent reality, where token holders have differing risk preferences and will not immediately move their entire portfolio from staking to lending (or vice-versa). Furthermore, cryptocurrency holders are often looking for returns that are multiples of their initial investment and have a long time-preference [\[Weber 2016\]](#page-21-12). In our evolution of each agent's portfolio, we also assume that an agent making a decision at time *t* can only use the information about all portfolios up to time *t*, {π*i*(*t*) : *i* ∈ [*n*]}, and the implied rate γ*<sup>t</sup>* . Since we are dealing with on-chain lending only, this assumption says that players cannot use strategies that look into the future and that all agent portfolios are public. In order to capture strategies that are independent of front-running and latency arbitrage, we will make the following assumption:

<span id="page-7-3"></span>Assumption 10 (Martingale Ordering). *There exists an* [*n*]*-valued martingale Z<sup>t</sup> that chooses the ordering in which participants are allowed to update their portfolios at time t to those at time t* +1*.*

Under this assumption, agents receive no advantage in expected returns by trying to predict when their strategy is executed (e.g. is agent 1's strategy executed before agent 2's strategy because agent

<span id="page-7-0"></span><sup>2</sup> It should be noted that this has been a stated goal of large pools of validators and the existence of staking services that pool tokens and operate nodes exemplifies this collective desire to have a large portion of the token supply staked [\[fig 2019;](#page-19-5) [Manian 2019\]](#page-21-13)

1 has more staked than agent 2?). This assumption is reasonable as our goal is to figure out if rational, but non-Byzantine, agents will cause PoS network security to decrease when on-chain lending activity is sizeable.

*3.3.1. Optimal Portfolio Construction.* Mean-variance methods, pioneered by Markowitz's Nobel Prize winning work on portfolio theory [\[Markowitz 1952\]](#page-21-8), provide a way for rational traders of risky assets to construct portfolios that trade-off individual preferences for maximizing returns with those of risk minimization. These methods, which are the backbone of the majority of trillions of dollars of passive portfolios and statistical arbitrage strategies, provide a simple, easy-to-solve model that involves two parameters for constructing portfolios of *n* assets: an expected return vector *µ* ∈ R *n* and a positive-definite covariance matrix Σ ∈ *S n*×*n* <sup>+</sup> . Given these parameters, one solves a strongly convex program that aims to compute the fraction of an agent's wealth that should be allocated to each asset while ensuring that the sum of the allocations is one and each entry is positive. In particular, the seminal work of Markowitz aimed to optimize the quadratic form *f* : R *<sup>n</sup>* ×R *<sup>n</sup>* ×R× *S n*×*n* <sup>+</sup> → R, *f*(*w*,*µ*,λ,Σ) = *w <sup>T</sup>*Σ*w* − λ*µ*, where λ is a parameter that controls the riskiness of the output portfolio and *w* is the portfolio allocation. As λ is varied, the *efficient frontier* of admissible portfolios is defined as the surface *S*(*µ*,Σ) = {*w* ∈ R *n* : ∃λ such that *w* ∈ argmin *f*(*w*,*µ*,Σ,λ)}. The original work of Markowitz [\[Markowitz 1952\]](#page-21-8) focused on the single period allocation problem, where an investor aims to find the optimal portfolio over a single time-period, which corresponds to assuming that *µ* and Σ do not change over time. Further work on multiple period [\[Li and Ng](#page-21-14) [2000\]](#page-21-14) and continuous-time methods [\[Zhou and Yin 2003\]](#page-21-15) for mean-variance optimization allow for *µ* and Σ to vary as functions of time, with the continuous-time methodology drawing *µ* from an ˆIto process, such as a solution to the Black-Scholes equation for options pricing. As blockchain systems have incremental updates with independent games per update (e.g. transaction fee markets can differ wildly from block to block), we will necessarily have to consider the multiple period model and define how each agent's mean vector and risk-preferences evolve over time. Finally, we note that our methodology is directly comparable to that of multistrategy backtesting in quantitative trading [\[Boyd et al. 2017\]](#page-19-6).

We will assume that each agent treats their token wealth, (πlend(*t*)*<sup>i</sup>* ,πstake(*t*)*i*) as a Markowitz portfolio and updates, on receiving tokens from staking and lending, an estimate for a time-dependent return vector *µi*(*t*) ∈ R 2 . We also assume that each agent has a different, time-independent covariance matrix Σ*<sup>i</sup>* that is drawn from a random matrix ensemble[3](#page-8-1) . In other words, the expected return vector adjusts with time (it depends on the staked and lent quantities), while the covariance stays fixed in time. As long as there is some variance in the chosen random matrix ensemble (e.g. ∃*i*, *j* ∈ [*n*] such that Pr[Σ*<sup>i</sup>* 6= Σ*<sup>j</sup>* ] > 0), then the dynamics will not deadlock into a state where all participants end up with the same portfolio (e.g. all outstanding tokens are 100% allocated to staking or lending). If agents simply move all of their assets from one pool to another, as opposed to some risk-adjusted proportion, then the system can deadlock quickly when borrowing demand is constant. Using the notation of the prequel, we define *µi*(*t*) = *µi*(πstake(*t*),πlend(*t*)) as:

<span id="page-8-0"></span>
$$
\mu_i(t) = \begin{bmatrix} \mu_{\text{state}}(t)_i \\ \mu_{\text{lend}}(t)_i \end{bmatrix} = \begin{bmatrix} \frac{\pi_{\text{stack}}(t)_i}{S_t - \ell_t} \\ \gamma_t \end{bmatrix} = \begin{bmatrix} \frac{\pi_{\text{state}}(t)_i}{\zeta_t} \\ \gamma_t \end{bmatrix}
$$
(3)

Let us motivate this choice of expected return vector. Recall that the return vector is supposed to represent the relative rate of return (usually referred to as an alpha in the quantitative finance literature) over a riskless asset. In this situation, the riskless asset is holding our tokens (as bearer

<span id="page-8-1"></span><sup>3</sup> In graphical models and probability, such as the Ising model or spin glasses, this is known as "quenched disorder" [\[Mezard](#page-21-16) [et al. 2009\]](#page-21-16)

instruments) and we expect to earn yields[4](#page-9-1) of *<sup>R</sup><sup>t</sup> St*−`*t* and γ*<sup>t</sup>* for staking and lending, respectively. However, note that the former yield can be greater than 1 (when *S<sup>t</sup>* − `*<sup>t</sup>* < *Rt*), whereas the latter yield cannot as per equation [\(1\)](#page-6-1). In order for Markowitz optimization to be well-defined, we need to choose yields that are directly comparable (e.g. have the same range). Moreover, we note that the na¨ıvely calculated staking yield loses the dependence on the *i*th party's current wealth. Since our system allows for slashing and each validator incurs a variance in reward proportional to the inverse square root of the epoch length, it is preferable to find a yield that depends on the *i*th parties wealth to reflect this variance. The simplest estimator for a staking validator's yield that is in [0,1] (comparable to lending yield) and has a component of the variance is the probability of winning the block reward, <sup>π</sup>stake(*t*)*<sup>i</sup> St*−`*t* , which is exactly what [\(3\)](#page-8-0) describes.

In order to describe the covariance matrix, we will first state an assumption that aims to connect the variances in the system with the expected staked and lent times:

<span id="page-9-3"></span>Assumption 11. *The ith agent's covariance matrix* Σ*<sup>i</sup> will be static (e.g. does not vary with block height), diagonal, and will have variances connected to the expected stake time* τ*stake and expected lent time* τ*lend*

Formally we use the following model for the covariance matrix:

$$
\Sigma_i^{-1} = \begin{bmatrix} \alpha_i & 0\\ 0 & \beta_i \end{bmatrix} \tag{4}
$$

<span id="page-9-0"></span>
$$
\alpha_i \sim \text{Exp}(\tau_{\text{stack}}) \tag{5}
$$

$$
\beta_i \sim \text{Exp}(\tau_{\text{lend}}) \tag{6}
$$

One can interpret τstake as the expected epoch length (see Algorithm [1\)](#page-23-0), while τlend represents the withdrawal window under which a lender can remove their tokens from the lent pool.[5](#page-9-2) By connecting the covariance matrix to these quantities, we encode the connection between a validator's expected risk preference and the time that capital is locked into either staking or lending. Equation [\(4\)](#page-9-0) represents the fact that risk and time preferences are, to first-order, inversely correlated (e.g. you are willing to lock up capital for the longest duration in the least risky assets) [\[De Santis and](#page-20-18) [Gerard 1997\]](#page-20-18). To explain these choices of random variables, first recall that the Markowitz objective function is of the form *f*(*µ*,Σ,*w*,λ) = *w <sup>T</sup>*Σ*w*−λ*µ*, where λ parametrizes the agent's preference for return maximization over risk minimization. If we divide this objective function by λ, provided that λ > 0, we get an equivalent optimization problem for λ −1 *f* . Note that λ can be thought of as encoding 'collective' risk-preferences for all agents (e.g. a 'bull market' when λ is large, a 'bear market' when λ is small). As such we need a methodology for choosing λ that depends on the network size and/or number of agents. We make λ ∼ χ 2 (*n*) in order to capture the fact that as the number of participants increases, so should the expected number that are risk seeking. Once we do this, we can directly interpret the variables α*<sup>i</sup>* ,β*<sup>i</sup>* as encoding both this risk preference and the inherent duration difference between lending risk and staking risk. The static nature of the covariance matrix in Assumption [11](#page-9-3) implies that each agent has an 'equilibrium' risk-preference. Moreover, this implies that the distribution of risk-preferences amongst changes is not changing — which one can expect in

$$
\frac{\pi_{\text{state}}(t)_i + R_t \frac{\pi_{\text{stack}}(t)_i}{S_t - \ell_t}}{\pi_{\text{state}}(t)_i} - 1 = \frac{R_t}{S_t - \ell_t}
$$

<span id="page-9-1"></span><sup>4</sup>For staking, the relative yield is defined as future expected staked wealth divided by current stake wealth minus 1, which is

<span id="page-9-2"></span>This is the standard form of how yields are specified in traditional Markowitz portfolio theory [\[Markowitz 1952\]](#page-21-8). <sup>5</sup>This is implemented in a manner analogous to how hedge funds only let you recall your invested capital in small chunks over a window of time

the limit as the number of agents goes to infinity.[6](#page-10-1) Making this assumption allows for significantly faster simulation (e.g. less compute needed to reduce the variance of the estimator below an error threshold ε)

To summarize, we evolve the system by having each agent update their Markowitz estimate at each time step, which changes the lending and staking distributions for the next time step. In simulation, agents will only be able to migrate their staking tokens at times *k*τstake, *k* ∈ N. Explicitly, we evolve the system via the following loop:

- Initialize distributions {πstake(0)*i*}*i*∈[*n*] ,{πlend(0)*i*}*i*∈[*n*] .
- Initialize empirical distributions {πˆstake(0)*i*}*i*∈[*n*] ,{πˆlend(0)*i*}*i*∈[*n*]
- For *t* = 1,2,3,...
  - Observe empirical distributions πˆstake(*t*)*<sup>i</sup>* ,πˆlend(*t*)*<sup>i</sup>*
  - (generated via actual staking / lending rewards accrued in the epoch)
  - Compute Markowitz weights *wi*,*<sup>t</sup>* = (*p*,1− *p*), *p* = *p*(πˆstake(*t*)*<sup>i</sup>* ,πˆlend(*t*)*<sup>i</sup>* ,α*<sup>i</sup>* ,β*i*) ∈ [0,1]
  - Define new portfolio as *pi*(*t*) = *p*(*pi*(*t* −1) +`*i*(*t* −1)), `*i*(*t*) = (1− *p*)(*pi*(*t* −1) +`*i*(*t* −1))

<span id="page-10-0"></span>

#### **4. FORMAL PROPERTIES**

We will describe a few formal properties (proved in the appendix) of the two-state model, as it is feasible to analytically analyze this model. Our goal in this section is to bound the amount of turnover in the stake distribution that is caused by on-chain lending becoming more attractive than staking rewards to rational stakers. A secondary goal is to understand what properties of the stochastic processes that represent the evolution of the lending and staking distributions are necessary and/or sufficient for ensuring that we do not have a lot of volatility in agent token portfolios. This is important as volatility in these portfolios implies that PoS networks have volatile security, which is a distinct defect when compared to PoW. We will make a few additional assumptions that are necessary to provide analytical results:

<span id="page-10-5"></span>Assumption 12 (Bounded Size). *There is a minimum fraction* δ > 0 *of the money supply that needs to be staked, e.g. S<sup>t</sup>* −`*<sup>t</sup>* > δ*S<sup>t</sup>*

If no one is staking then the on-chain lending contract has no value (as it doesn't have any security), so this is a realistic assumption that matches the practical parameters chosen in live networks such as Tezos [\[Goodman 2014\]](#page-20-11) and Cosmos [\[Buchman 2019\]](#page-19-2). Note that one can directly interpret δ as the fraction of altruistic validators who will never reallocate or rebalance their assets.

<span id="page-10-6"></span>Assumption 13 (Number of Agents). *The number of agents n is larger than a constant multiple of the product of the exponential parameters, e.g. n* = Ω(τ*stake*τ*lend*)*.*

This assumption is required for purely technical reasons that are explained in the proofs in the appendix.[7](#page-10-2) If we solve the *unconstrained* problem[8](#page-10-3) for the Markowitz objective function, *f*(*µ*,Σ,*w*,λ) = *w <sup>T</sup>*Σ*w* − λ*µ*, then *w* needs to satisfy the first-order condition, ∇*<sup>w</sup> f*(*µ*,Σ,*w*,λ) = 0. This yields,

<span id="page-10-4"></span>
$$
w = \lambda \Sigma^{-1} \mu \tag{7}
$$

Given that we are in the multi-period Markowitz setting, this means that we can estimate the *i*th participant's portfolio weights via *wi*(*t*) = λΣ−<sup>1</sup> *i µi*(*t*). As a measure of volatility in the security of

<span id="page-10-1"></span><sup>6</sup>The easiest way to see this is to note that one expects a central limit theorem (e.g. Marchenko-Pastur law [\[Tao 2012\]](#page-21-17)) for the distribution of <sup>√</sup><sup>1</sup> *<sup>n</sup>* ∑ *n <sup>i</sup>*=<sup>1</sup> Σ*<sup>i</sup>* . Thus, as the number of participants goes to infinity, we get closer and closer to having the staticity assumption hold true

<span id="page-10-2"></span><sup>7</sup>Also note that the equilibrium assumption (Assumption [11\)](#page-9-3) implicitly also requires a lower bound on *n* that is a function of τstake and τlend in order for the covariance matrix distribution to be ε away from the limit distribution

<span id="page-10-3"></span><sup>8</sup> In the constrained version of the problem needs to satisfy Karush-Kuhn-Tucker conditions [\[Mangasarian 1994\]](#page-21-18) that enforce *w <sup>T</sup>* 1 = 1 and *w<sup>i</sup>* > 0, ∀*i*. For simplicity of exposition, we elided these during this section (even though these conditions are satisfied during simulation).

the underlying staking mechanism, we will first look at how *wi*(*t*) changes in time. Intuitively, this change corresponds to how large rebalancing events (e.g. moving tokens from staking to lending, or vice-versa) are between subsequent blocks. If this rebalancing is large, then the network could dramatically reduce it's security as holders move their assets from staking to lending. On the other hand, if this rebalancing is small and decreases over time, then we know that the staked token supply is stable. Using the Markowitz update rule [\(7\)](#page-10-4), we have the following bound.

$$
||w_i(t+1) - w_i(t)||_1 = ||\Sigma^{-1}(\mu_i(t+1) - \mu_i(t))||_1 \le ||\Sigma^{-1}||_{1 \to 1} ||\mu_i(t+1) - \mu_i(t)||_1 \tag{8}
$$

where k*A*k1→<sup>1</sup> = max*v*∈R*n*,k*v*k1=<sup>1</sup> k*Av*k<sup>1</sup> is the *L* <sup>1</sup> operator norm. This simple inequality implies that the volatility in portfolio weights, represented by the single block difference in weights, is controlled by the difference in the mean vector, as E[kΣ <sup>−</sup>1k1→1] = E[α∨β] ≤ τstake∨τlend. Therefore, we focus on trying to bound the difference in expected returns as a function of the block reward at time *t*, *R<sup>t</sup>* , the total token supply *S<sup>t</sup>* , the lent supply `*<sup>t</sup>* , and the Compound lending curve parameters β0,β1.

Let πstake(*t* +1)*<sup>i</sup>* −πstake(*t*)*<sup>i</sup>* = ∆ stake *i* (*t*) and `*t*+<sup>1</sup> −`*<sup>t</sup>* = ∆lend(*t*). Since the PoS algorithm is adapted to a filtration *F<sup>t</sup>* on *St*∆ *n* and the covariance matrices are constant as time evolves,[9](#page-11-0) πstake(*t*),πlend(*t*) are also *Ft*-adapted random variables. Note that by definition, ∆ stake *i* (*t*) ≤ *S<sup>t</sup>* and ∆lend(*t*) ≤ *S<sup>t</sup>* , since we cannot change the amount staked or lent by more than the outstanding money supply. We will first bound the difference in expected returns as a function of ∆ stake *i* (*t*),∆lend(*t*), and *S<sup>t</sup>* :

Claim 1. *There exist constants C*,*C* <sup>0</sup> > 0 *such that*

$$
\|\mu_i(t+1) - \mu_i(t)\|_1 < \frac{C|\Delta_i^{state}(t)|}{S_{t+1}} + C'\Delta_{lend}^2(t)
$$

Note that these constants are allowed to depend on δ from Assumption [12.](#page-10-5) If we have an compounding and inflationary rewards schedule, e.g. *S<sup>t</sup>* = *e* λ*t* , then this claim implies the following:

<span id="page-11-3"></span>Claim 2. *If there exists* λ > τ*stake such that S<sup>t</sup>* = Ω(*e* λ*t* ) *and* min*iWi*(*t*) > 0*, then as t* → ∞*, the maximum change in stake is bounded above by the lending volatility,* ∆ 2 *lend*(*t*)*, w.h.p.*

This claim implies that if there is not much variance in the lending rate, either due to choosing small parameters β0,β<sup>1</sup> or because borrowing demand is minimal, then we should not expect portfolios to rebalance regularly and rational stakers will tend to keep their tokens locked in a staking contract. Another natural quantity to look at is the variance of the lent assets. We show that the money supply and time-preference for lending, τlend, control the variance of lent assets.

<span id="page-11-2"></span>Claim 3. *Let F<sup>t</sup> be the filtration such that the lending process* `*<sup>t</sup> is adapted. Then we have:*

$$
\mathsf{Var}[\ell_{t+1}|\mathcal{F}_t] = \frac{\gamma_t}{\tau_{lend}^2} \|W(t)\|_2^2
$$

*Moreover, we have the following bounds:*

$$
\frac{\gamma_t^2 S_t^2}{\tau_{lend}^2 \sqrt{n}} \leq \mathsf{Var}[\ell_{t+1} | \mathcal{F}_t] \leq \frac{\gamma_t^2 S_t^2}{\tau_{lend}^2}
$$

Note that if *k* is the constant representing the ratio of borrowing demand to *S<sup>t</sup>* (c.f. §[3.2.1\)](#page-6-0), there exists a constant[10](#page-11-1) ℵ that depends on *k* such that γ*<sup>t</sup>* ≥ ℵ. As such, Claim [3](#page-11-2) implies that as long as *S<sup>t</sup>* = Ω *n* 1 4 , we have reallocation from staking to lending. Thus, any monetary policy that grows sufficiently quickly with the number of users of the network will *always* have assets moving into

<span id="page-11-0"></span><sup>9</sup> In particular, they are random at time *t* = 0 and defined in *F*0, but are constant throughout. This is a measure theoretic way of defining quenched disorder [\[Talagrand 2010\]](#page-21-19)

<span id="page-11-1"></span><sup>10</sup>Since *U<sup>t</sup>* = *kSt* `*t*+*kSt* and Assumption 12 implies that `*<sup>t</sup>* < (1−δ)*S<sup>t</sup>* , we have *U<sup>t</sup>* > *k k*+1−δ and γ*<sup>t</sup>* > β<sup>1</sup> *k k*+1 2 +β<sup>0</sup> *k k*+1 .

and out of lending. If we place constraints on the demand *k*, we can strengthen this result into a bound on how much ∆ 2 lend oscillates:

<span id="page-12-0"></span>Claim 4. *Let* η*<sup>t</sup>* = 1 + k*W*(*t*)k 2 2 *S* 2 *t* ≥ 1 + √ 1 *n and* α*<sup>t</sup>* = `*<sup>t</sup>* τ*lend St*η*t If for all t, k* ≥ α*t* 1−α*t , where and the hypotheses of claim [2](#page-11-3) hold, then* ∆ 2 *lend*(*t*) *is a submartingale and we have*

$$
\Pr\left[\max_{t} \Delta_{lend}^{2}(t) > \lambda\right] < \frac{1}{\lambda^{2}} \text{Var}[\Delta_{lend}^{2}(t)]
$$

*and subsequently,*

<span id="page-12-3"></span>
$$
\Pr\left[\max_{t} \|\mu_i(t+1) - \mu_i(t)\|_1 > \lambda\right] < \frac{1}{\lambda^2} \text{Var}[\Delta_{lend}^2(t)]\tag{9}
$$

In words, this claim says that as long as we have inflation and there is enough borrowing demand, then we can be sure that the *worst-case* rebalancing is bounded by the variance of lending volatility. If we add another constraint on the behavior of the increments ∆ 2 lend(*t*), then we can strengthen this claim to get a phase transition that resembles the Galton-Watson phase transition [\[Asmussen and](#page-19-7) [Hering 1983\]](#page-19-7).

Claim 5. *Suppose that for all t* > 0,∆*lend*(*t*) < ` 2 *t* 2`*t*−1η*<sup>t</sup> ,* E[∆*lend*(*t*)] > 0*, and let* η*<sup>t</sup> be as in Claim [4.](#page-12-0) Define r*<sup>±</sup> *as follows:*

$$
r_{\pm} = \frac{\ell_t \tau_{lend}}{S_t \eta_t} \left( 1 \pm \sqrt{1 + \frac{\eta_t \ell_{t-1} (\ell_{t-1} - 2\ell_t)}{\ell_t^2}} \right)
$$

*Then* ` 2 *t is a supermartingale when* γ*<sup>t</sup>* ∈ (*r*−,*r*+)*, a submartingale when* γ*<sup>t</sup>* ∈ [0,*r*−)∪(*r*+,1]*, and a martingale when* γ*<sup>t</sup>* ∈ {*r*−,*r*+}*.*

The intuition for this is as follows:

- When there is either too little or too much borrowing demand (e.g. γ*<sup>t</sup>* < *r*<sup>−</sup> or γ*<sup>t</sup>* > *r*+), then the expected lent supply either increases (on average) to one or decreases to zero. This is analogous to a gambler's wealth after playing a game with probability *p* < 1/2 for *n* rounds — the wealth concentrates into either the house (staked supply) or the gambler (lent supply).
- When there is a moderate amount of borrowing demand, γ*<sup>t</sup>* ∈ [*r*−,*r*+], then we have stable, potentially oscillatory behavior. Doob's Supermartingale Convergence Theorem [\[Billingsley 2008\]](#page-19-8) intimates that the distribution is stationary as *t* → ∞. This corresponds to a gambler playing a game in which their chance of winning is *p* > 1/2.

These results for the simpler two-level model suggest that our simulated phase transition results convey the existence of a deeper phase transition.

*Agent-level Behavior.* In order to get a stronger understanding of what is going on at the agent level and for different monetary policies, one needs an understanding of the probability that a single agent has a large rebalancing event that affects the staked portion of their portfolio. This involves studying how the staking components of *µi*(*t*) changes over time. Let *µ*stake(*t*)*<sup>i</sup>* be the different in the staking component of *µi*(*t*) between times*t* and *t* +1. We can bound the probability that an agent rebalances their portfolio by an ε fraction via the following claim:

<span id="page-12-2"></span><span id="page-12-1"></span>
$$
\textbf{Claim 6. } Let \mu_{stable}(t)_i = \frac{\pi_{stable}(t+1)_i}{S_{t+1} - \ell_{t+1}} - \frac{\pi_{stable}(t)_i}{S_t - \ell_t}. \text{ Then for all } t > 0, \text{ we have}
$$
\n
$$
\Pr[|\mu_{state}(t)_i| < \varepsilon | \mathcal{F}_{t-1}] = \Omega \left( 1 - \left( \left( \frac{\varepsilon S_{t+1}}{\gamma_t} \right)^n e^{-\tau_{state} \tau_{lend} \frac{\varepsilon S_{t+1}}{\gamma_t} \right) \right) \tag{10}
$$

Bounds like [\(10\)](#page-12-1) are of the form Pr[*X<sup>t</sup>* < ε] = *Y<sup>t</sup>* , which imply that the extrema of *Y<sup>t</sup>* provide a guaranteed bound of how large *X<sup>t</sup>* can be when *Y<sup>t</sup>* is minimized. This means that we can try to bound the first hitting time *t* ∗ for the maxima of |*µ*stake(*t*)*<sup>i</sup>* | by analyzing the minima of the righthand side of [\(10\)](#page-12-1). Note that the function 1 − (*kx*) *n e* −*k* 0 *kx* has a minima at *x* = *nkn*−<sup>2</sup> *k* 0 , which means that we can estimate when, as a function of *S<sup>t</sup>* , γ*t* , ε, we have maximal deviations in stake. In the following section, we examine this claim for different monetary policies *S<sup>t</sup>* .

<span id="page-13-0"></span>

#### **4.1. Deflationary Monetary Policy**

In this case, *R<sup>t</sup>* = *kr*−*<sup>t</sup>* ,*r* < 1 and *S<sup>t</sup>* = *k*(1−*r* −*t*−1 ) <sup>1</sup>−*<sup>r</sup>* =*C*∞−*C* 0 *r* −*t*−1 , where*C*<sup>∞</sup> is the final money supply (e.g. 21 million, for Bitcoin). Letting ε = δ*St*+<sup>1</sup> and plugging this into the right hand side of [\(10\)](#page-12-1) and optimizing for *t* using the chain rule gives the condition *t* <sup>∗</sup> = −log *C* − q *n*δ <sup>γ</sup>*<sup>t</sup>* <sup>τ</sup>stakeτlend . Requiring that *t* <sup>∗</sup> > 0 gives the condition *C* − √ *n*δγ*t*τstakeτlend ∈ (0,1) or

$$
\delta > \frac{(C_{\infty} - 1)\gamma_t \tau_{\text{stack}} \tau_{\text{lend}}}{n}
$$

The above condition implies that at the time with the highest expected amount of removed stake, we expect that quantity to at be on the order of *<sup>C</sup>*<sup>∞</sup> *n* . If there are fewer terminal coins than participants, *C*<sup>∞</sup> *n*, then we should expect large rebalances for every staker. This formalizes the intuition that totally deflationary currencies are vulnerable to large rebalances that depend strongly on the number of coins in the system. It also confirms the intuition that if there are fewer coins than participants, then borrowing demand will be high and we should again expect large rebalances.

#### **4.2. Inflationary Monetary Policy**

Next, we consider what Claim [6](#page-12-2) implies about inflationary monetary policies. We will consider two types of inflationary policies: Polynomial (*S<sup>t</sup>* = Ω(*t k* )) and Exponential (*S<sup>t</sup>* = Ω(*e* λ*t* )).

*4.2.1. Polynomial Inflation.* For polynomial inflation, we have *R<sup>t</sup>* = *ctk*−<sup>1</sup> and *S<sup>t</sup>* = Ω(*t k* ). Optimizing [\(10\)](#page-12-1) with this form of *S<sup>t</sup>* gives *t* <sup>∗</sup> = *n*δ <sup>γ</sup>*<sup>t</sup>* <sup>τ</sup>stakeτlend 1/*<sup>k</sup>* . Plugging this into the right-hand side of [\(10\)](#page-12-1) gives a lower bound of

$$
1-\frac{\delta^2 n}{\gamma_t \tau_{\text{state}} \tau_{\text{lend}}} e^{-\tau_{\text{state}} \tau_{\text{lend}} \delta^2 n/\gamma_t}
$$

which means that if δ = *O*(*n* −1/2 ), individual agents will not have rebalances of size δ*S<sup>t</sup>* with high probability. These guarantees do not depend on the polynomial degree *k*, which means that even simple linear policies (*k* = 1) are sufficient to get low stake turnover.

*4.2.2. Exponential Inflation.* In the case of exponential inflation, *S<sup>t</sup>* = *C*0*e* λ*t* for some λ > 0 and initial token distribution *C*0. Following the logic of the §[4.1](#page-13-0) section, we arrive at a conclusion of,

$$
\delta > \frac{C_0 \gamma_t \tau_{\text{state}} \tau_{\text{lend}}}{n}
$$

This states that the worst-case rebalancing is bounded by the *initial token distribution* as opposed to the final token distribution. Given that most networks assume that there will be more users than the *initial* distribution, *C*0, this implies that large rebalancing events should become rarer once the network achieves a scale of *n C*0.

#### **4.3. Conclusions**

The results of this section show that the model of §[3.3](#page-7-2) has a volatility that is mainly dependent on lending volatility. This volatility, if demand is sufficiently shallow, is small enough to help bound the worst-case portfolio rebalancing for any validator in the system. However, the turnover in staked quantity, measured by how each agent's expected reward changes over each epoch period, is sensitive to the precise nature of the monetary policy, *S<sup>t</sup>* . In particular, deflationary policies cannot support on-chain lending, as the worst-case rebalancing rate depends on the terminal money supply, whereas the rebalancing rate for exponentially inflationary monetary policies only depends on the initial money supply (e.g. Ethereum's pre-mine). Finally, we note that polynomial inflation provides particularly good rebalancing guarantees that are independent of the rate of growth of the money supply. Many of these results rely on asymptotic behavior of agents in this system and all of these results depend on simple models for borrowing demand. The remainder of the paper will focus on using simulation to provide a more realistic picture of §[3.3.](#page-7-2)

<span id="page-14-0"></span>

#### **5. AGENT-BASED SIMULATIONS**

In order to test the three-state model in a quantitatively rigorous and realistic fashion, we turn to agent-based simulations. One of the main reasons to use agent-based simulation over formal methods is that it hard to formally prove what block reward growth rate is ideal for mitigating volatility in portfolio allocation. For instance, it is difficult to evaluate whether *R<sup>t</sup>* = Ω(*t* 2 ) or *R<sup>t</sup>* = Ω(*t*) provide ideal mitigation for on-chain lending with parameters β0,β1. Moreover, we can test various realistic demand distributions, including ones that are atomic and do not have a probability density. Prior work on agent-based simulations of blockchain systems [\[Chitra et al. 2019\]](#page-20-10) has focused on analyzing consensus protocols via event-based simulation. We follow a similar event-based framework for simulating staking and lending, albeit ignoring the details of peer-to-peer networking and consensus. Our goal is to sample as many trajectories *X<sup>t</sup>* |*F<sup>t</sup>* = (πstake(*t*),πlend(*t*), γ*t*) as possible for different combinations of parameters β0,β1, and block reward schedules *R<sup>t</sup>* .

#### **5.1. Initialization**

In order to generate sample paths *X<sup>t</sup>* , we need to specify the following variables:

- Initial distributions: πstake(0),πlend(0)
- Initial interest rate: γ<sup>0</sup> ∈ (0,1)
- Interest rate parameters: β0,β<sup>1</sup> ∈ (0,1)
- Demand-generating distribution parameters (vary depending on the demand generating distributions chosen): *P*<sup>ξ</sup>
- Staking and lending time scale: τstake, τlend
- Slashing probability: *p*slash
- PRNG seed: *<sup>s</sup>* <sup>∈</sup> <sup>Z</sup><sup>2</sup> 64

We chose to model πstake(0)*<sup>i</sup>* ∼ Exp(λstake) and πlend(0)*<sup>i</sup>* ∼ Exp(λlend), as these distributions exemplify the extreme concentration of wealth that accompanies most token distributions. Exponential distributions are also useful in that the order statistics are also exponential[11](#page-14-1), which represents the idea that the *k*th entrant to a network should have a decaying fraction (in this case <sup>1</sup> *k* ) of the total token supply. We note that we do not use power law distributions as there are conflicting reports of the wealth distribution in Bitcoin actually following a power law [\[Kondor et al. 2014;](#page-20-19) [Alvarez-](#page-19-9)[Ramirez et al. 2018\]](#page-19-9). Given the statistical difficulty of discerning if one has a power law versus an exponential decay [\[Shalizi 2007;](#page-21-20) [Stumpf and Porter 2012\]](#page-21-21) and the extra parameter in a power law (e.g. *p*(*x* = *t*) ∝ *x*min*t* −*a* ), we decided to use exponential initial distributions.

In our simulations, we kept the initial interest rate at 10%, as we saw very little sensitivity to the initial choice. In particular, agents quickly rebalance their portfolio into lending, if the rate is high enough and this appeared to equilibrate within a small number of time steps. We swept the other parameters, β0,β1, τstake, τlend, *p*slash, over realistic ranges and for each choice of parameter, we sampled trajectories for a variety of seeds *s* to get an ensemble average.

<span id="page-14-1"></span><sup>11</sup>If πstake(0)(1) < ... < πstake(0)(*n*) are the order statistics for the stake distribution, then πstake(0)(*i*+1) − πstake(0)(*i*) ∼ Exp λstake *n*−*i* and by the tower property for telescoping sums, E[πstake(0)(*i*) ]] = Θ log*i* <sup>λ</sup>stake

<span id="page-15-2"></span>![](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2020-Staking-and-Lending-Equilibria/_page_15_Figure_0.jpeg)

Fig. 4: Borrowing demand sample paths, ξ*<sup>t</sup>* , juxtaposed with the money supply *S<sup>t</sup>* . The sample paths in the upper left (linear, *R<sup>t</sup>* = *c*), upper right (deflationary, *R<sup>t</sup>* = *kr<sup>t</sup>* ,*r* < 1), and lower left (inflationary, *R<sup>t</sup>* = *kr<sup>t</sup>* ,*r* > 1) use simple random walks, whereas the figure in the lower right samples a geometric Brownian motion path with reflecting boundary conditions at (1−η0)*S<sup>t</sup>* ,(1+η1)*S<sup>t</sup>* .

## **5.2. Simulation Loop**

The main simulation loop follows that as described at the end of §[3.3.](#page-7-2) We exactly evaluate the Markowitz update rule, with constraints, via the exact solution for optimal portfolios [\[Boyd et al.](#page-19-6) [2017\]](#page-19-6). Given that we are solving *n* independent, two-dimensional Markowitz problems, we evaluated the constraints analytically (as opposed to using a convex solver like Gurobi or CVX). The main event loop has the following causal ordering:

- (1) If *t* = *k*τstake for some *k* ∈ N, allow agents to update their Markowitz portfolios[12](#page-15-1)
- (2) Sample the borrowing demand distribution
- (3) Update γ*<sup>t</sup>* as a function of the new borrowing demand
- (4) Run Algorithm 1 to determine who wins the reward *R<sup>t</sup>* and/or if they get slashed

<span id="page-15-0"></span>

#### **5.3. Borrowing Demand Distributions**

We sampled a variety of borrowing demand distributions for deflationary and inflationary block rewards, as illustrated via the sample paths in Figure [4.](#page-15-2) These stochastic borrowing demand paths each have four parameters: mean, variance, maximum, and minimum demand. We define the maximum and minimum demand parameters as multipliers of the token supply, so that the minimum is (1−η0)*S<sup>t</sup>* and the maximum is (1+η1)*S<sup>t</sup>* (illustrated via the lower and upper bounds in figure [4,](#page-15-2) respectively).

#### **5.4. Results**

In order to evaluate a variety of realistic conditions, we swept through many parameters illustrated above. The most interesting results come from looking at individual trajectories, such as

<span id="page-15-1"></span><sup>12</sup>Note that Assumption [10](#page-7-3) allows us to sample the agent portfolio updates in any order

<span id="page-16-0"></span>![](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2020-Staking-and-Lending-Equilibria/_page_16_Figure_0.jpeg)

Fig. 5: Heat maps of *f*(β0,β1) = E*<sup>t</sup> St*−`*t St*+`*t* β0,β<sup>1</sup> for different deflation schedules at a half-life equal to 0.25% of the total simulation time (400 Bitcoin-style halvenings occur). Each pixel is the average of 100 random initializations with the other parameters fixed. On the left, we have a very high deflationary rate and we can see that the values are negative, implying that `*<sup>t</sup>* > *S<sup>t</sup>* , whereas on the far right picture, which is non-deflationary, we see that *S<sup>t</sup>* > `*<sup>t</sup>*

[1,](#page-2-0) and heatmaps of how certain scalar functions behave as we vary the lending rate parameters β0,β1. We generated heatmaps for number of random seeds and took averages over these random instantiations to generate Figures [6](#page-17-0) and [7.](#page-18-0) The two main measurements that we looked

at were *f*(β0,β1) = E*<sup>t</sup>* " *St*−`*t St*+`*t* β0,β1, τ # and *g*(β0,β1) = E*<sup>t</sup>* [γ*<sup>t</sup>* − β*<sup>t</sup>* |β0,β1, τ], where given a nonanticipating stochastic process *X<sup>t</sup>* and a function stopped at time τ, E*<sup>t</sup>* [ *f*(*Xt*)|τ] = <sup>R</sup> <sup>τ</sup> 0 *f*(*Xt*)*dX<sup>t</sup>* , for the stochastic measure *dX<sup>t</sup>* . We ran all trajectories for τ =250,000 blocks and approximate E*t* [ *f*(*Xt*)|τ] ≈ ∑ τ/∆ *i*=0 *f*(*Xi*)ξ*<sup>i</sup>* , where ξ*<sup>i</sup>* is sampled from *dXt*+<sup>∆</sup> − *dX<sup>t</sup>* . The first quantity, *f*(β0,β1), is the normalized difference between the staked supply and the lent supply and when it is greater than zero, there is more quantity staked, on average. It is normalized relative to the total money supply *S<sup>t</sup>* + `*<sup>t</sup>* so that ∀*t*, *St*−`*t St*+`*t* ∈ (0,1) and thus we can compare the relative staking to lending proportions at different times. The second quantity, *g*(β0,β1) measures the linear spread between borrowing and lending rates, which varies over time even though 1−γ<sup>0</sup> = β*t*−γ*t* β*t* is constant. If the market for borrowing is efficient and there is less churn, we should expect that this rate should be quite low. Note that in all simulations used, we set the relative spread, 1−γ0, to be 0.5%.

In Figure [5,](#page-16-0) we see plots of *f*(β0,β1) for different inflation rates *r* ∈ {0.25,0.5,1.0}. Note that when *r* = 1.0, then we have a linear polynomial inflation rate. This figure demonstrates that even though the dependence on β0,β<sup>1</sup> appears to be random, it is clear that the deflationary figures tend to have significantly more lending than staking. On the other hand, the linearly inflating component enjoys a significant advantage with regards to staked supply. Note that the dependence on β0,β<sup>1</sup> appears mostly random because of the use of a common scale to plot them. The usage of a common scale dampens the correct scale to plot the figures at (which should be on the order of Var(*f*(β0,β1)), which varies dramatically as a function of the other parameters that we sample, such as the block

<span id="page-17-0"></span>![](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2020-Staking-and-Lending-Equilibria/_page_17_Figure_0.jpeg)

Fig. 6: Plots of *g*(β0,β1) = E[γ*<sup>t</sup>* −β*<sup>t</sup>* |β0,β1]. As you go from left to right, we increase the inflation rate *r* (recall that when *r* < 1, we are deflationary) and as we go from top to bottom, the borrow threshold increased. Recall that the borrow threshold is the lower bound line from figure [4.](#page-15-2) We see that when the system has linearly increasing block rewards, we receive very tight spreads and a smooth, almost linear *g*(β0,β1). On the other hand, as we have increasing deflationary policies, we see that we cause the expected spread to become more random and larger.

reward. In some of the other plots that we will look at, we use independent color scales for each plot to emphasize the variation as a function of β<sup>0</sup> and β1.

On the other hand, in figure [6,](#page-17-0) we see an array of plots that show how the borrowing spread, *g*(β0,β<sup>1</sup> changes as a function of inflation rate and borrowing threshold. The third column, which is the linearly increasing block rewards regime, demonstrates very tight spreads, suggesting that even changing the borrowing demand threshold causes little variation in spreads. On the other hand, the

<span id="page-18-0"></span>![](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2020-Staking-and-Lending-Equilibria/_page_18_Figure_0.jpeg)

Fig. 7: Plots of *f*(β0,β1) for differing inflation rates and borrowing thresholds. Note that the color bars vary for each figure. We see that when the policy is deflationary, *f*(β0,β1) < 0. Moreover, when the borrowing threshold is high, we cause the plots to become less random and have a more clear dependence on β0,β1.

deflationary regime is much more sensitive to shocks in borrowing demand, as illustrated by the plots in the upper left hand corner of figure [6.](#page-17-0) These empirical results validate Claims 2 and 3, as we directly see that lending volatility has a much more muted effect on inflationary systems. Finally, in figure [7,](#page-18-0) we see heatmaps of *f*(β0,β1) for different borrowing thresholds and inflation rates. Note that these plots have different scales, unlike [5,](#page-16-0) and that the deflationary figures are all mainly negative. From the first two columns, it becomes clear that as borrowing demand increases, *g*(β0,β1) becomes increasingly monotonically decreasing in β0,β1. This means that as borrowing demand increases, the system's loss of security to lending increases in a more predictable manner. On the other hand, the linearly inflating regime does not have this issue and continues to have relatively random and non-monotonic dependence on β0,β<sup>0</sup> as we adjust the borrowing threshold.

## **6. CONCLUSIONS AND FUTURE WORK**

This paper has explored how on-chain lending affects network security in PoS networks by studying how rational multiple period Markowitz optimizing agents optimize their token portfolios. In particular, we find that 'bank runs' can occur when many agents collectively move their tokens from staking contracts to lending contracts even when agents have indpendently drawn risk preferences. These attacks, which are coordinated only by rational optimization, show that the strictly Byzantine threat model is insufficient to describe security in PoS networks. Our theoretical and empirical findings show that deflationary PoS tokens are susceptible to attack by non-Byzantine, but rational participants who constantly turnover and rebalance their staking and lending portfolios to chase yield. Moreover, these findings show that one needs to choose a block reward schedule that increases relative to the yield that these on-chain contracts provide. Our theoretical results give explicit probabilities for the constant relative borrowing demand regime and show that there is a clear and strong dependence on the lending rate γ*<sup>t</sup>* in these probabilities. We buffet these results with agent-based simulations to confirm that these properties hold in more realistic borrowing scenarios. In the future, we aim to look at how unbonding times and transaction fees (e.g. gas costs) affect these protocols and how different lending curves will affect staking security. We also aim to provide more precise theoretical results by relaxing a number of the assumptions that are utilized in this paper.

## **Acknowledgments**

The author would like to thank Yi Sun, Rei Chiang, Hasu, Haseeb Qureshi, Ivan Bogatyy, Georgios Konstantopoulos, John Morrow, Tony Salvatore, Wei Wang, Hsien-Tang Kao, Jonathan Reem, Josh Chen, Tina Zhen, Nader Al-Naji, Michael Jordan, Tim Roughgarden, and Matteo Leibowitz for comments and feedback. The author would also like to thank Barnabe Monnot and Ariah Klages- ´ Mundt for correcting an earlier error in Claim 1 and for helpful expository comments. Finally, the author would like to acknowledge the helpful input from the reviewers of both the Stanford Blockchain Conference and the MIT Cryptoeconomics Systems journal.

## **7. REFERENCES**

<span id="page-19-5"></span>2019. Tezos (Figment Networks). (Oct 2019).<https://figment.network/networks/tezos/>

<span id="page-19-1"></span>Nader Al-Naji, Josh Chen, and Lawrence Diao. 2017. Basis: A Price-Stable Cryptocurrency with an Algorithmic Central Bank. (2017).

<span id="page-19-9"></span>Jose Alvarez-Ramirez, Eduardo Rodriguez, and Carlos Ibarra-Valdez. 2018. Long-range correlations and asymmetry in the Bitcoin market. *Physica A: Statistical Mechanics and its Applications* 492 (2018), 948–955.

<span id="page-19-7"></span>Søren Asmussen and Heinrich Hering. 1983. *Branching processes*. Vol. 3. Springer.

<span id="page-19-3"></span>Vivek Bagaria, Sreeram Kannan, David Tse, Giulia Fanti, and Pramod Viswanath. 2018. Deconstructing the blockchain to approach physical limits. *arXiv preprint arXiv:1810.08092* (2018).

<span id="page-19-4"></span>Mathieu Baudet, Avery Ching, Andrey Chursin, George Danezis, Franc¸ois Garillot, Zekun Li, Dahlia Malkhi, Oded Naor, Dmitri Perelman, and Alberto Sonnino. 2018. State machine replication in the Libra Blockchain. (2018).

<span id="page-19-8"></span>Patrick Billingsley. 2008. *Probability and measure*. John Wiley & Sons.

<span id="page-19-6"></span>Stephen Boyd, Enzo Busseti, Steve Diamond, Ronald N Kahn, Kwangmoo Koh, Peter Nystrup, Jan Speth, and others. 2017. Multi-period trading via convex optimization. *Foundations and Trends* R *in Optimization* 3, 1 (2017), 1–76.

<span id="page-19-0"></span>Jonah Brown-Cohen, Arvind Narayanan, Alexandros Psomas, and S Matthew Weinberg. 2019. Formal barriers to longest-chain proof-of-stake protocols. In *Proceedings of the 2019 ACM Conference on Economics and Computation*. ACM, 459–473.

<span id="page-19-2"></span>Ethan Buchman. 2019. Byzantine Fault Tolerant State Machine Replication in Any Programming Language. In *Proceedings of the 2019 ACM Symposium on Principles of Distributed Computing*. ACM, 546–546.

<span id="page-20-20"></span>Donald L Burkholder. 1973. Distribution function inequalities for martingales. *the Annals of Probability* (1973), 19–42.

<span id="page-20-9"></span>Miguel Castro, Barbara Liskov, and others. 1999. Practical Byzantine fault tolerance. In *OSDI*, Vol. 99. 173–186.

<span id="page-20-13"></span>T-H Hubert Chan, Rafael Pass, and Elaine Shi. 2018. PaLa: A Simple Partially Synchronous Blockchain. *IACR Cryptology ePrint Archive* 2018 (2018), 981.

<span id="page-20-5"></span>Tarun Chitra, Rei Chiang, John Morrow, and Aseem Sood. 2019. Comment for CFTC RFI on Crypto-asset Mechanics and Markets. (Feb 2019). [https://comments.cftc.gov/PublicComments/](https://comments.cftc.gov/PublicComments/ViewComment.aspx?id=61960) [ViewComment.aspx?id=61960](https://comments.cftc.gov/PublicComments/ViewComment.aspx?id=61960)

<span id="page-20-17"></span>Tarun Chitra and Uthsav Chitra. 2019. Committee Selection is More Similar Than You Think: Evidence from Avalanche and Stellar. *arXiv preprint arXiv:1904.09839* (2019).

<span id="page-20-10"></span>T. Chitra, M. Quaintance, S. Haber, and W. Martino. 2019. Agent-Based Simulations of Blockchain protocols illustrated via Kadena's Chainweb. In *2019 IEEE European Symposium on Security and Privacy Workshops (EuroS PW)*. 386–395. DOI:<http://dx.doi.org/10.1109/EuroSPW.2019.00049>

<span id="page-20-2"></span>Phil Daian, Rafael Pass, and Elaine Shi. 2019. Snow white: Robustly reconfigurable consensus and applications to provably secure proof of stake. In *International Conference on Financial Cryptography and Data Security*. Springer, 23–41.

<span id="page-20-18"></span>Giorgio De Santis and Bruno Gerard. 1997. International asset pricing and portfolio diversification with time-varying risk. *The Journal of Finance* 52, 5 (1997), 1881–1912.

<span id="page-20-16"></span>Giulia Fanti, Leonid Kogan, Sewoong Oh, Kathleen Ruan, Pramod Viswanath, and Gerui Wang. 2019. Compounding of wealth in proof-of-stake cryptocurrencies. In *International Conference on Financial Cryptography and Data Security*. Springer, 42–61.

<span id="page-20-21"></span>MV Fedoryuk. 1987. Asymptotic: Integrals and series. (1987).

<span id="page-20-4"></span>Peter Gazi, Aggelos Kiayias, and Alexander Russell. 2018. Stake-bleeding attacks on proof-of- ˇ stake blockchains. In *2018 Crypto Valley Conference on Blockchain Technology (CVCBT)*. IEEE, 85–92.

<span id="page-20-15"></span>Yossi Gilad, Rotem Hemo, Silvio Micali, Georgios Vlachos, and Nickolai Zeldovich. 2017. Algorand: Scaling byzantine agreements for cryptocurrencies. In *Proceedings of the 26th Symposium on Operating Systems Principles*. ACM, 51–68.

<span id="page-20-11"></span>LM Goodman. 2014. Tezos—a self-amending crypto-ledger White paper. *URL: https://www. tezos. com/static/papers/white paper. pdf* (2014).

<span id="page-20-3"></span>Nicolas Houy. 2014. It Will Cost You Nothing to'Kill'a Proof-of-Stake Crypto-Currency. *Available at SSRN 2393940* (2014).

<span id="page-20-7"></span>Sep Kamvar, Marek Olszewski, and Rene Reinsberg. 2019. Celo: A Multi-Asset Cryptographic Protocol for Decentralized Social Payments. (2019).

<span id="page-20-14"></span>Daniel M Kane. 2016. A New Approach to Distribution Testing. (2016).

<span id="page-20-0"></span>Aggelos Kiayias, Alexander Russell, Bernardo David, and Roman Oliynykov. 2017. Ouroboros: A provably secure proof-of-stake blockchain protocol. In *Annual International Cryptology Conference*. Springer, 357–388.

<span id="page-20-1"></span>Sunny King and Scott Nadal. 2012. Ppcoin: Peer-to-peer crypto-currency with proof-of-stake. *selfpublished paper, August* 19 (2012).

<span id="page-20-6"></span>Ariah Klages-Mundt and Andreea Minca. 2019. (In) Stability for the Blockchain: Deleveraging Spirals and Stablecoin Attacks. *arXiv preprint arXiv:1906.02152* (2019).

<span id="page-20-12"></span>Neal Koblitz and Alfred J Menezes. 2015. The random oracle model: a twenty-year retrospective. *Designs, Codes and Cryptography* 77, 2-3 (2015), 587–610.

<span id="page-20-19"></span>Daniel Kondor, M ´ arton P ´ osfai, Istv ´ an Csabai, and G ´ abor Vattay. 2014. Do the rich get richer? An ´ empirical analysis of the Bitcoin transaction network. *PloS one* 9, 2 (2014), e86197.

<span id="page-20-8"></span>Leslie Lamport, Robert Shostak, and Marshall Pease. 1982. The Byzantine generals problem. *ACM Transactions on Programming Languages and Systems (TOPLAS)* 4, 3 (1982), 382–401.

<span id="page-21-6"></span>Robert Leshner and Geoffrey Hayes. 2019. *Compound: The Money Market Protocol*. Technical Report.

<span id="page-21-14"></span>Duan Li and Wan-Lung Ng. 2000. Optimal dynamic portfolio selection: Multiperiod meanvariance formulation. *Mathematical finance* 10, 3 (2000), 387–406.

<span id="page-21-23"></span>George Lowther. 2010. The Burkholder-Davis-Gundy Inequality. (Apr 2010). [https://almostsure.](https://almostsure.wordpress.com/2010/04/06/the-burkholder-davis-gundy-inequality/) [wordpress.com/2010/04/06/the-burkholder-davis-gundy-inequality/](https://almostsure.wordpress.com/2010/04/06/the-burkholder-davis-gundy-inequality/)

<span id="page-21-7"></span>MakerDAO. 2017. The Dai Stablecoin System. *URl: https://makerdao. com/whitepaper/DaiDec17WP. pdf* (2017).

<span id="page-21-18"></span>Olvi L Mangasarian. 1994. *Nonlinear programming*. SIAM.

<span id="page-21-13"></span>Zaki Manian. 2019. Iqlusion: accelerating cryptofinance. (Oct 2019).<https://iqlusion.io>

<span id="page-21-8"></span>Harry Markowitz. 1952. Portfolio selection. *The journal of finance* 7, 1 (1952), 77–91.

<span id="page-21-16"></span>Marc Mezard, Marc Mezard, and Andrea Montanari. 2009. *Information, physics, and computation*. Oxford University Press.

<span id="page-21-3"></span>Michael Neuder, Daniel J Moroz, Rithvik Rao, and David C Parkes. 2019. Selfish Behavior in the Tezos Proof-of-Stake Protocol. *arXiv preprint arXiv:1912.02954* (2019).

<span id="page-21-1"></span>Rafael Pass, Lior Seeman, and Abhi Shelat. 2017. Analysis of the blockchain protocol in asynchronous networks. In *Annual International Conference on the Theory and Applications of Cryptographic Techniques*. Springer, 643–673.

<span id="page-21-9"></span>Rafael Pass and Elaine Shi. 2017. The sleepy model of consensus. In *International Conference on the Theory and Application of Cryptology and Information Security*. Springer, 380–409.

<span id="page-21-11"></span>Rafael Pass and Elaine Shi. 2018. Thunderella: Blockchains with optimistic instant confirmation. In *Annual International Conference on the Theory and Applications of Cryptographic Techniques*. Springer, 3–33.

<span id="page-21-4"></span>Steven Poelhekke and Rick van der Ploeg. 2007. Volatility, financial development and the natural resource curse. (2007).

<span id="page-21-0"></span>QuantumMechanic. 2011. Proof of stake instead of proof of work. (Jul 2011). [https://bitcointalk.](https://bitcointalk.org/index.php?topic=27787.0) [org/index.php?topic=27787.0](https://bitcointalk.org/index.php?topic=27787.0)

<span id="page-21-10"></span>Team Rocket, Maofan Yin, Kevin Sekniqi, Robbert van Renesse, and Emin Gun Sirer. 2019. ¨ Scalable and Probabilistic Leaderless BFT Consensus through Metastability. *arXiv preprint arXiv:1906.08936* (2019).

<span id="page-21-20"></span><span id="page-21-2"></span>Fahad Saleh. 2019. Blockchain without waste: Proof-of-stake. *Available at SSRN 3183935* (2019). CR Shalizi. 2007. So You Think You Have a Power Law—Well Isn't That Special. *Three-Toed Sloth* (2007).

<span id="page-21-22"></span>Michael Sipser. 2012. *Introduction to the Theory of Computation*. Cengage learning.

<span id="page-21-21"></span>Michael PH Stumpf and Mason A Porter. 2012. Critical truths about power laws. *Science* 335, 6069 (2012), 665–666.

<span id="page-21-19"></span>Michel Talagrand. 2010. *Mean field models for spin glasses: Volume I: Basic examples*. Vol. 54. Springer Science & Business Media.

<span id="page-21-17"></span>Terence Tao. 2012. *Topics in random matrix theory*. Vol. 132. American Mathematical Soc.

<span id="page-21-5"></span>Will Warren and Amir Bandeali. 2017. 0x: An open protocol for decentralized exchange on the Ethereum blockchain. *URl: https://github. com/0xProject/whitepaper* (2017).

<span id="page-21-12"></span>Warren E Weber. 2016. *A Bitcoin standard: Lessons from the gold standard*. Technical Report. Bank of Canada Staff Working Paper.

<span id="page-21-15"></span>Xun Yu Zhou and George Yin. 2003. Markowitz's mean-variance portfolio selection with regime switching: A continuous-time model. *SIAM Journal on Control and Optimization* 42, 4 (2003), 1466–1482.

#### **Appendix**

<span id="page-22-0"></span>

#### **A. NOTATION**

- ∆ *n* is n-dimensional probability simplex, ∆ *<sup>n</sup>* = {(*x*1,..., *xn*) ∈ R *n* : ∑ *n i*=1 *x<sup>i</sup>* = 1,∀*i*, *x<sup>i</sup>* ≥ 0}
- For any *x* ∈ R *n* , we define the *p*-norm as k*x*k*<sup>p</sup>* = (∑ *n i*=1 |*xi* | *p* ) 1/*p*
- We turn any nonzero vector *x* ∈ R *<sup>n</sup>* with *x* ≥ 0 into a probability distribution by defining ˆ*x* = *x* k*x*k<sup>1</sup> ∈ ∆ *n* .

.

- *S n* <sup>+</sup> ⊂ R *n*×*n* is the cone of positive definite, symmetric matrices
- ∨,∧ are the standard join and meet of two elements of a lattice. For example if *a*,*b* ∈ R, *a*∨*b* = max(*a*,*b*),*a*∧*b* = min(*a*,*b*)
- We use standard Landau notation [\[Sipser 2012\]](#page-21-22) on totally ordered sets *D*: Given functions *f* : *D* → R,*g* : *D* → R, we use the following asymptotic notations:
  - *f* ∈ *O*(*g*) ⇐⇒ ∃*C* > 0,∀*d* ∈ *D*, *f*(*d*) ≤ *Cg*(*d*)
  - *f* ∈ Ω(*g*) ⇐⇒ ∃*c* > 0,∀*d* ∈ *D*, *f*(*d*) ≥ *cg*(*d*) *f*(*d*)
  - *f* ∈ *o*(*g*) ⇐⇒ lim*d*→sup*<sup>D</sup> <sup>g</sup>*(*d*) = 0
  - *f* ∈ Θ(*g*) ⇐⇒ *f* ∈ *O*(*g*) and *f* ∈ Ω(*g*)

<span id="page-23-1"></span><span id="page-23-0"></span>Algorithm 1 Epoch-based PoS Simulation

πstake ← πstake(0) ∈ ∆ *n S* → 0/ Initialize current epoch's slash set *t* ← 0 for *epoch* ∈ N do # Update Staking Distribution for *id* in {1,...,*nstakers*} do if (*id*,*reward*) ∈ *R* then πstake[*id*]+ = *reward* end if if (*id*,*slash*) ∈ *S* then πstake[*id*]− = *slash* end if *R* ← 0/,*S* ← 0/

# Draw next epoch from stake distribution

```
πˆstake ← πstake
              kπstakek1
                                                       Create normalized probability distribution
     for block ∈ {1,..., τstake} do
       id ∼ πˆstake # Draw a winner from the stake distribution
       X ∼ Bern(pslash)
       if X == 1 then
          if ∃(id,s) ∈ S then
            S ← S∪ {(id,s−S(id,πstake))}
            S ← S− {(id,s)}
          else
            if ∃(id,r) ∈ R then
               R ← R∪ {(id,r +R(t))}
               R ← R− {(id,r)}
            end if
          end if
       end if
       t += 1
     end for
  end for
end for
```

## **C. PROOF OF CLAIM 1**

In Assumption [12,](#page-10-5) we assert that for all *t*,*S<sup>t</sup>* −`*<sup>t</sup>* > δ*S<sup>t</sup>* or 1− `*t St* > δ and <sup>1</sup> 1− `*t St* < 1 δ . Since the function 1 1−*x* is convex on [0,1], we have, for any *x* ∈ [0,1−δ],*s* ∈ [0,1], 1 <sup>1</sup>−*<sup>x</sup>* < *s* 1 δ + (1−*s*) = *s* 1−δ δ +1. Using this bound on the function <sup>1</sup> 1− `*t St* , we have, for any *s* ∈ [0,1]:

$$
\frac{1}{S_t - \ell_t} = \frac{1}{S_t} \frac{1}{1 - \frac{\ell_t}{S_t}} < \frac{1}{S_t} \left( s \left( \frac{1 - \delta}{\delta} \right) + 1 \right)
$$

Initial token distribution *R* → 0/ Initialize current epoch's reward set In particular, since `*<sup>t</sup>* < *S<sup>t</sup>* , we can use this bound at *s* = `*t St* to get

<span id="page-24-0"></span>
$$
\frac{1}{S_t - \ell_t} < \frac{1}{S_t} \left( \frac{\ell_t}{S_t} \left( \frac{1 - \delta}{\delta} \right) + 1 \right) \tag{11}
$$

This implies that

$$
\mu_{\text{stack}}(t)_i = \frac{\pi_{\text{state}}(t+1)_i}{S_t - \ell_t} < \frac{\pi_{\text{stack}}(t+1)_i}{S_t} \left(\frac{\ell_t}{S_t} \left(\frac{1-\delta}{\delta}\right) + 1\right)
$$

Note that the condition *S<sup>t</sup>* −`*<sup>t</sup>* > δ*S<sup>t</sup>* also implies that `*<sup>t</sup> St* < 1−δ, so that we can right this as:

$$
\mu_{\text{stack}}(t)_i = \frac{\pi_{\text{state}}(t+1)_i}{S_t - \ell_t} < \frac{\pi_{\text{state}}(t+1)_i}{S_t} \left(\frac{(1-\delta)^2}{\delta} + 1\right)
$$

On the other hand, since *S<sup>t</sup>* > *S<sup>t</sup>* −`*<sup>t</sup>* , we also have *µ*stake(*t*)*<sup>i</sup>* > πstake(*t*+1)*<sup>i</sup> St* . Thus we have

$$
|\mu_{\text{stack}}(t+1)_i - \mu_{\text{stack}}(t)_i| = \Theta\left(\frac{\pi_{\text{state}}(t+1)_i}{S_{t+1}} - \frac{\pi_{\text{state}}(t)_i}{S_t}\right)
$$

Let *f*(δ) be a constant such that

$$
|\mu_{\text{stack}}(t+1)_i - \mu_{\text{stack}}(t)_i| \le f(\delta) \left( \frac{\pi_{\text{state}}(t+1)_i}{S_{t+1}} - \frac{\pi_{\text{state}}(t)_i}{S_t} \right)
$$

which exists as per the last statement. Given these equation, we can now bound the single time step rebalance as follows:

$$
\|\mu_{i}(t+1) - \mu_{i}(t)\|_{1} = \left| \frac{\pi_{\text{stack}}(t+1)_{i}}{S_{t} - \ell_{t}} - \frac{\pi_{\text{stack}}(t)_{i}}{S_{t} - \ell_{t}} \right| + |\gamma_{t+1} - \gamma_{t}|
$$
\n
$$
\leq f(\delta) \left| \frac{\pi_{\text{stack}}(t+1)_{i}}{S_{t+1}} - \frac{\pi_{\text{stack}}(t)_{i}}{S_{t}} \right| + \beta_{1}\gamma_{0} \left| \left( \frac{\ell_{t+1}}{S_{t+1}} \right)^{2} - \left( \frac{\ell_{t}}{S_{t}} \right)^{2} \right|
$$
\n
$$
= \left| \frac{\pi_{\text{stack}}(t+1)_{i}}{S_{t} + R_{t}} - \frac{\pi_{\text{stack}}(t)_{i}}{S_{t}} \right| + \beta_{1}\gamma_{0} \left| \left( \frac{\ell_{t+1}}{S_{t} + R_{t}} \right)^{2} - \left( \frac{\ell_{t}}{S_{t}} \right)^{2} \right|
$$
\n
$$
\leq f(\delta) \left| \frac{\pi_{\text{stack}}(t)_{i} + \Delta_{i}^{\text{take}}(t)}{S_{t} + R_{t}} - \frac{\pi_{\text{stack}}(t)_{i}}{S_{t}} \right| + \beta_{1}\gamma_{0} \left| \left( \frac{\ell_{t} + \Delta_{\text{lend}}(t)}{S_{t} + R_{t}} \right)^{2} - \left( \frac{\ell_{t}}{S_{t}} \right)^{2} \right|
$$
\n
$$
\leq \pi_{\text{state}}(t)_{i} \left| \frac{f(\delta)}{S_{t} + R_{t}} - \frac{f(\delta)}{S_{t}} \right| + \frac{f(\delta)|\Delta_{i}^{\text{take}}(t)}{S_{t} + R_{t}} + \beta_{1}\gamma_{0} \left| \left( \frac{\ell_{t} + \Delta_{\text{lend}}(t)}{S_{t} + R_{t}} \right)^{2} - \left( \frac{\ell_{t}}{S_{t}} \right)^{2} \right|
$$
\n
$$
\leq \pi_{\text{state}}(t)_{i} \left| \frac{f(\delta)_{R_{t}}}{S_{t} + R_{t}} - \frac{f(\delta)|\Delta_{
$$

#### **D. PROOF OF CLAIM 2**

Since *R<sup>t</sup>* = *o*(2 *n* ),*S<sup>t</sup>* = ∑*i*<*<sup>t</sup> R<sup>i</sup>* , we reach the desired conclusion if for any β ∈ (0,1],Pr[|∆ stake *i* (*t*)| > *S* β1 *t* ] = *O*(2 −*S* β *<sup>t</sup>* ). Let *Wi*(*t*) = πstake(*t*)*<sup>i</sup>* +πlend(*t*)*<sup>i</sup>* be the wealth of agent *i*. Then the unconstrainted Markowitz update gives,

$$
\pi_{\text{state}}(t+1)_i = \frac{\alpha_i \pi_{\text{state}}(t)_i}{S_t - \ell_t} W_i(t)
$$

where α*<sup>i</sup>* is the inverse covariance sample for agent *i*. Thus,

$$
|\Delta_i^{\text{stack}}(t)| = |\pi_{\text{stack}}(t+1)_i - \pi_{\text{stack}}(t)_i| = \pi_{\text{stack}}(t)_i \left| \frac{\alpha_i W_i(t)}{S_t - \ell_t} - 1 \right|
$$

Thus, we have:

$$
\Pr\left[|\Delta_i^{\text{stack}}(t)| > S_t^{\beta}\right] = \Pr\left[\pi_{\text{state}}(t)_i \left| \frac{\alpha_i W_i(t)}{S_t - \ell_t} - 1 \right| > S_t^{\beta}\right]
$$
(13)

$$
= \Pr\left[\alpha_i > \left(\frac{S_t - \ell_t}{W_i(t)}\right)(S_t^{\beta} + \pi_{\text{stack}}(t)_i)\right] < 2^{-\tau_{\text{stack}}S_t^{\beta}}
$$
(14)

where the last step holds since α*<sup>i</sup>* is an exponential random variable with parameter τstake.

#### **E. PROOF OF CLAIM 3**

Recall that β*<sup>i</sup>* was defined in equation [4](#page-9-0) and is different than the lending rate β*<sup>t</sup>* . Note the following, which uses β*<sup>i</sup>* ∼iid Exp(τlend):

$$
E[\ell_{t+1}^2 | \mathcal{F}_t] = E\left[ \left( \gamma_t \sum_{i=1}^n \beta_i W_i(t) \right)^2 \middle| \mathcal{F}_t \right]
$$
\n(15)

$$
= \gamma_t^2 \mathsf{E}\left[\sum_{i=1}^n \beta_i^2 W_i(t)^2 + \sum_{i \neq j} \beta_i \beta_j W_i(t) W_j(t)\right]
$$
(16)

$$
= \gamma_t^2 \left( \frac{2}{\tau_{\text{lend}}^2} \sum_{i=1}^n W_i(t)^2 + \frac{1}{\tau_{\text{lend}}^2} \sum_{i \neq j} W_i(t) W_j(t) \right)
$$
(17)

$$
= \gamma_t^2 \left( \frac{1}{\tau_{\text{lend}}^2} \left( \sum_{i=1}^n W_i(t) \right)^2 + \frac{1}{\tau_{\text{lend}}^2} \sum_{i=1}^n W_i(t)^2 \right)
$$
(18)

$$
= \gamma_t^2 \left( \frac{S_t^2}{\tau_{\text{lend}}^2} + \frac{1}{\tau_{\text{lend}}^2} \sum_{i=1}^n W_i(t)^2 \right) \tag{19}
$$

<span id="page-25-0"></span>
$$
= \gamma_t^2 \left( \frac{S_t^2}{\tau_{\text{lend}}^2} + \frac{\|W(t)\|_2^2}{\tau_{\text{lend}}^2} \right) \tag{20}
$$

Furthermore, we have the following:

<span id="page-25-1"></span>
$$
E[\ell_{t+1}|\mathcal{F}_t] = E\left[\sum_{i=1}^n \gamma_t \beta_i W_i(t)\middle|\mathcal{F}_t\right] = \frac{\gamma_t S_t}{\tau_{\text{lend}}}
$$
(21)

Combining equations [\(20\)](#page-25-0) and [\(21\)](#page-25-1) yields:

$$
\text{Var}[\ell_{t+1}|\mathcal{F}_t] = \mathsf{E}[\ell_{t+1}^2|\mathcal{F}_t] - (\mathsf{E}[\ell_{t+1}|\mathcal{F}_t])^2 = \frac{\gamma_t^2 \|W(t)\|_2^2}{\tau_{\text{lead}}^2}
$$
(22)

as claimed. As the Cauchy-Schwarz inequality implies that k*x*k 2 <sup>2</sup> ≤ k*x*k 2 <sup>1</sup> ≤ √ *n*k*x*k 2 2 and *S<sup>t</sup>* = k*W*(*t*)k1, we have:

$$
1 \le \frac{S_t^2}{\|W(t)\|_2^2} = \frac{\|W(t)\|_1^2}{\|W(t)\|_2^2} \le \sqrt{n}
$$
 (23)

Thus we have the final part of the claim:

$$
\text{Var}[\ell_{t+1}|\mathcal{F}_t] = \frac{\gamma_t \|W(t)\|_2^2}{\tau_{\text{lend}}^2} = \frac{\gamma_t S_t^2}{\tau_{\text{lend}}^2} \left(\frac{\|W(t)\|_2^2}{S_t^2}\right) \in \frac{\gamma_t S_t^2}{\tau_{\text{lend}}^2} \left[\frac{1}{\sqrt{n}}, 1\right]
$$
(24)

#### **F. PROOF OF CLAIM 4**

Noting that γ*<sup>t</sup>* = *kSt* `*t*+*kSt* = 1 1+ `*t kSt* implies that for the choice of *k* in the claim, [\(20\)](#page-25-0) is greater than ` 2 *t* and thus ` 2 *t* is a non-negative submartingale with bounded differences (e.g. ∆ 2 lend(*t*) ≤ *S* 2 *t* ). In particular, note that γ*<sup>t</sup>* ≥ β<sup>1</sup> *k k*+1 2 +β<sup>0</sup> *k k*+1 = Ω *k k*+1 . Thus via equation [\(20\)](#page-25-0), we have:

<span id="page-26-0"></span>
$$
E[\ell_t^2 | \mathcal{F}_t] = \frac{\gamma_t^2 S_t^2}{\tau_{\text{lend}}^2} \left( 1 + \frac{\|W(t)\|_2^2}{S_t^2} \right) = \frac{\gamma_t^2 S_t^2 \eta_t}{\tau_{\text{lend}}^2} \ge C' \left( \frac{k}{k+1} \right)^2 \frac{S_t^2 \eta_t}{\tau_{\text{lend}}^2}
$$
(25)

The choice *k* = Ω α*t* 1−α*t* ensures that the right-hand side of equation [\(25\)](#page-26-0) is greater than ` 2 *t* . The norm equivalence between a non-negative submartingale and its quadaratic variation (e.g. Burkholder's inequality [\[Burkholder 1973\]](#page-20-20)) applies to ` 2 *t* and implies that ∆ 2 lend(*t*) is also a submartingale. Note that this relies on the being able to pass bounds on the quadratic variation process to the individual increments, which only applies to the discrete setting [\[Lowther 2010\]](#page-21-23). The tail bound [\(9\)](#page-12-3) comes from Doob's submartingale inequality and Kolmogorov's inequality for submartingales [\[Billingsley 2008\]](#page-19-8).

#### **G. PROOF OF CLAIM 5**

Recall that ∆ 2 lend(*t*) is a martingale if E[∆ 2 lend(*t*)|*F<sup>t</sup>* ] = ∆ 2 lend(*t*), a supermartingale if E[∆ 2 lend(*t*)|*F<sup>t</sup>* ] ≤ ∆ 2 lend(*t*), and a submartingale if E[∆ 2 lend(*t*)|*F<sup>t</sup>* ] ≥ ∆ 2 lend(*t*). The expansion of E[∆ 2 lend(*t* +1)|*F<sup>t</sup>* ] is;

$$
E[\Delta_{\text{lend}}^2(t) | \mathcal{F}_t] = E[(\ell_{t+1} - \ell_t)^2 | \mathcal{F}_t]
$$
  
= 
$$
E[\ell_{t+1}^2 | \mathcal{F}_t] - 2\ell_t E[\ell_{t+1} | \mathcal{F}_t] + \ell_t^2
$$
  
= 
$$
\frac{\gamma_t^2 S_t^2 \eta_t}{\tau_{\text{lend}}^2 - 2\ell_t \frac{\gamma_t S_t}{\tau_{\text{lend}}} + \ell_t^2
$$
 (26)

Define the quadratic function *f* : R → R as:

$$
f(\gamma_t) = \gamma_t^2 \left(\frac{S_t^2 \eta_t}{\tau_{\text{lend}}^2}\right) - \gamma_t \left(\frac{2\ell_t S_t}{\tau_{\text{lend}}}\right) + \left(\ell_t^2 - (\ell_t^2 - 2\ell_t \ell_{t-1} + \ell_{t-1}^2)\right)
$$
$$
= \gamma_t^2 \left(\frac{S_t^2 \eta_t}{\tau_{\text{lend}}^2}\right) - \gamma_t \left(\frac{2\ell_t S_t}{\tau_{\text{lend}}}\right) + \left(2\ell_t \ell_{t-1} - \ell_{t-1}^2\right)
$$
(27)

Note that *f*(γ*t*) = E[∆ 2 lend(*t*)|*F<sup>t</sup>* ] − ∆ 2 lend(*t* − 1) so that the roots of *f* correspond to when ∆ 2 lend is a martingale. Moreover, when *f* > 0,∆ 2 lend(*t*) is a submartingale, and a supermartingale otherwise. Thus, we only need to find the roots of *f* and to figure out when *f* > 0 and *f* < 0 to classify this transition. The roots of *f*,*r*<sup>±</sup> are:

<span id="page-26-1"></span>
$$
r_{\pm} = \frac{\ell_t \tau_{\text{lend}}}{S_t \eta_t} \left( 1 \pm \sqrt{1 + \frac{\eta_t \ell_{t-1} (\ell_{t-1} - 2\ell_t)}{\ell_t^2}} \right)
$$

Thus, the roots are real if and only if we have:

$$
\eta_t(2\ell_t\ell_{t-1} - \ell_{t-1}^2) < \ell_t^2
$$
\n
$$
\iff \eta_t\ell_{t-1}(\Delta_{\text{lend}}(t-1) + \ell_t) < \ell_t^2
$$
\n
$$
\tag{28}
$$

$$
\iff \Delta_{\text{lend}}(t-1) < \frac{\ell_t^2}{\eta_t \ell_{t-1}} - \ell_t \tag{29}
$$

$$
\Rightarrow \Delta_{\text{lend}}(t-1) < \ell_t \left(\frac{\ell_t}{2\ell_{t-1}} - 1\right) \tag{30}
$$

Recall that for a quadratic function *f*(*x*) = *ax*<sup>2</sup> +*bx*+*c* with real roots *r*±, we have *f* −1 ((−∞,0)) = [*r*−,*r*+] if *f <sup>r</sup>*++*r*<sup>−</sup> 2 = *f* − *b* 4*a* < 0, otherwise *f* −1 ((−∞,0)) = (−∞,*r*−) ∪ (*r*+,∞). For equation [\(27\)](#page-26-1), we have <sup>−</sup>*<sup>b</sup>* <sup>4</sup>*<sup>a</sup>* = `*<sup>t</sup>* τlend 2*St*η*t* , which gives:

$$
f\left(\frac{\ell_t \tau_{\text{lend}}}{2S_t \eta_t}\right) = \left(\frac{\ell_t^2 \tau_{\text{lend}}^2}{4S_t^2 \eta_t^2}\right) \left(\frac{S_t^2 \eta_t}{\tau_{\text{lend}}^2}\right) - \left(\frac{\ell_t \tau_{\text{lend}}}{2S_t \eta_t}\right) \left(\frac{2\ell_t S_t}{\tau_{\text{lend}}}\right) + \ell_{t-1} (\Delta_{\text{lend}}(t-1) + \ell_t)
$$
  
= 
$$
\frac{\ell_t^2}{4\eta_t} - \frac{\ell_t^2}{\eta_t} + \ell_{t-1} (\Delta_{\text{lend}}(t-1) + \ell_t)
$$
  
= 
$$
-\frac{3\ell_t^2}{4\eta_t} + \ell_{t-1} (\Delta_{\text{lend}}(t-1) + \ell_t)
$$
(31)

Note that equation [\(31\)](#page-27-0) is less than zero when

<span id="page-27-1"></span><span id="page-27-0"></span>
$$
\Delta_{\text{lend}}(t-1) < \ell_t \left( \frac{3\ell_t}{4\ell_{t-1}} - 1 \right)
$$

which is already subsumed by the condition for having real roots. Thus, provided that *r*<sup>±</sup> ∈ (0,1), we have the desired conclusion.

#### **H. PROOF OF CLAIM 6**

As before, let the *i*th agent's token wealth be denoted *Wi*(*t*) = πstake(*t*)*<sup>i</sup>* + πlend(*t*)*<sup>i</sup>* . Using the Markowitz update rule, we have the following:

$$
\mu_{\text{stack}}(t)_i = \frac{\pi_{\text{stack}}(t+1)_i}{S_{t+1} - \ell_{t+1}} - \frac{\pi_{\text{stack}}(t)_i}{S_t - \ell_t} = \frac{\pi_{\text{stack}}(t)_i}{S_t - \ell_t} - \frac{\alpha_i W_i(t)}{S_{t+1} - \ell_{t+1}} - \frac{\pi_{\text{stack}}(t)_i}{S_t - \ell_t}
$$
\n
$$
= \frac{\pi_{\text{stack}}(t)_i}{S_t - \ell_t} \left( \frac{\alpha_i W_i(t)}{S_{t+1} - \ell_{t+1}} - 1 \right) \tag{32}
$$

Applying [\(11\)](#page-24-0) at *s* = `*t*+<sup>1</sup> *St*+<sup>1</sup> to [\(32\)](#page-27-1) gives:

$$
\mu_{\text{stack}}(t)_i = \frac{\pi_{\text{stack}}(t)_i}{S_t - \ell_t} \left( \frac{\alpha_i W_i(t)}{S_{t+1} - \ell_{t+1}} - 1 \right) = \frac{\pi_{\text{stack}}(t)_i}{S_t - \ell_t} \left( \frac{\alpha_i W_i(t)}{S_{t+1}} \frac{1}{1 - \frac{\ell_{t+1}}{S_{t+1}}} - 1 \right) \n< \frac{\pi_{\text{stack}}(t)_i}{S_t - \ell_t} \left( \frac{\alpha_i W_i(t)}{S_{t+1}} \left( \frac{\ell_{t+1}}{S_{t+1}} \left( \frac{1 - \delta}{\delta} \right) + 1 \right) - 1 \right)
$$
\n(33)

Recall that `*t*+<sup>1</sup> = γ*<sup>t</sup>* ∑ *n <sup>i</sup>*=<sup>1</sup> β*iWi*(*t*) and that for positive functions *f* ≥ *g*, Pr[ *f* < ε] ≤ Pr[*g* < ε]. Note that πstake(*t*)*<sup>i</sup>* as adapted to a natural filtration *F<sup>t</sup>* that is non-anticipating, by construction[13](#page-27-2). This

<span id="page-27-2"></span><sup>13</sup>As we sample the PoS algorithm and Markowitz weights randomly (and not psuedorandomly), there is no advantage to looking into the future.

means that we can compute probabilities conditional on *F<sup>t</sup>* , e.g. Pr[`*<sup>t</sup>* |*Ft* ] = `*<sup>t</sup>* , Using this and recalling that the money supply *S<sup>t</sup>* is a deterministic function yields:

$$
Pr[|\mu_{\text{state}}(t)_i| < \varepsilon | \mathcal{F}_t] \ge Pr\left[\left|\frac{\pi_{\text{state}}(t)_i}{S_t - \ell_t} \left(\frac{\alpha_i W_i(t)}{S_{t+1}} \left(\frac{\ell_{t+1}}{S_{t+1}} \left(\frac{1-\delta}{\delta}\right) + 1\right) - 1\right)\right| < \varepsilon \middle| \mathcal{F}_t\right] \tag{34}
$$
\n
$$
\ge Pr\left[\left|\frac{\pi_{\text{state}}(t)_i}{S_t - \ell_t} \left(\frac{\alpha_i W_i(t)}{S_{t+1}} \left(\frac{\ell_{t+1}}{S_{t+1}} \left(\frac{1-\delta}{\delta}\right)\right)\right)\right| < \varepsilon \middle| \mathcal{F}_t\right] (1 - e^{-\frac{S_{t+1}}{W_i(t)}}) \tag{35}
$$
\n
$$
\ge \left(1 - e^{-S_{t+1}/W_i(t)}\right) Pr\left[\alpha_i \sum_{i=1}^n \beta_i < \varepsilon \left(\frac{S_t - \ell_t}{P_i(t)}\right) \left(\frac{S_{t+1}}{\gamma_t}\right) \left(\frac{\delta}{1-\delta}\right) \left(\frac{1}{W_i(t)(\max_i W_i(t))}\right)\right| \mathcal{F}_t \tag{36}
$$

<span id="page-28-4"></span><span id="page-28-2"></span><span id="page-28-1"></span><span id="page-28-0"></span>#

where [\(35\)](#page-28-0) comes from splitting equation [\(34\)](#page-28-1) into two terms by conditioning on n *A* = α*iWi*(*t*) *St*+<sup>1</sup> −1 < 0 o and *A c* and throwing away the term dependent on *A c* and the third inequality [\(36\)](#page-28-2) comes from *Wi*(*t*) < *St*+<sup>1</sup> and majorizing the sum ∑*<sup>i</sup>* β*iWi*(*t*). Note that [\(36\)](#page-28-2) is the CDF for the product of an exponentially distributed random variable α and an Erlang distributed random variable, ∑ *n <sup>i</sup>*=<sup>1</sup> β*<sup>i</sup>* . Let *A* ∼ Exp(τstake) and *B* ∼ Erlang(*n*, τlend). Then the product CDF[14](#page-28-3) is:

$$
\Pr[AB \le y] = \int_0^\infty \frac{\tau_{\text{stack}}^n}{(n-1)!} x^{n-1} e^{-\tau_{\text{lend}} x} \Pr\left[A < \frac{y}{x}\right] dx
$$
\n
$$
= 1 - \frac{\tau_{\text{stack}}^n}{(n-1)!} \int_0^\infty x^{n-1} e^{-\tau_{\text{stack}} x - \tau_{\text{lend}} \frac{y}{x} dx
$$
\n
$$
= 1 - \frac{\tau_{\text{stack}}^n}{(n-1)!} \int_0^\infty e^{-\tau_{\text{stack}} x - \tau_{\text{lend}} \frac{y}{x} (-n-1) \log x dx
$$
\n(37)

The integrand in [\(37\)](#page-28-4) is maximized around the saddle point of the large deviation function Λ(*x*) = τstake*x*− τlend*y <sup>x</sup>* −(*n*−1)log*x*. Let *x* <sup>∗</sup> = argmaxΛ(*x*). Using the first-order condition ∇Λ(*x*) = 0 and the quadratic formula, we get:

$$
x^* = \frac{n-1}{2\tau_{\text{lend}}} \left( \sqrt{1 + \frac{4\tau_{\text{stack}}\tau_{\text{lend}}}{(n-1)^2}} - 1 \right)
$$

From Assumption [13,](#page-10-6) we know that 4τstakeτlend < (*n* − 1) 2 , so *x* <sup>∗</sup> ≈ 2τstake*y*. Applying the method of steepest descent [\[Fedoryuk 1987\]](#page-20-21) to [\(37\)](#page-28-4) implies that there exists *C* > 0 such that R <sup>∞</sup> 0 *e* −τstake*x*−τlend *y <sup>x</sup>* <sup>−</sup>(*n*−1)log*xdx* < *Ce*−Λ(*<sup>x</sup>* ∗ ) so that we have:

<span id="page-28-5"></span>
$$
\Pr[AB \le y] \ge 1 - \frac{C\tau_{\text{state}}^n}{(n-1)!}e^{-\Lambda(X^*)} = 1 - \frac{C\tau_{\text{state}}^n}{(n-1)!}(2\tau_{\text{state}}y)^{n-1}e^{-\tau_{\text{state}}^2y + \frac{\tau_{\text{lend}}^2}{2\tau_{\text{state}}}}
$$
(38)

Combining [\(36\)](#page-28-2) with [\(38\)](#page-28-5) gives the result.

<span id="page-28-3"></span><sup>14</sup>Recall that the density of an exponential random variable with parameter α is α*e* −α*x* and the PDF of an Erlang distribution with parameters *n*,λ is <sup>λ</sup> *n* (*n*−1)! *x n*−1 *e* −λ*x*
