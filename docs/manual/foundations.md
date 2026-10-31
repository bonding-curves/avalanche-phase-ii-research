# 1. The network gives staking its economic purpose

*Draft for review.*

A staking model is useful only when its quantities retain their economic meaning. An amount of AVAX, a validator count and a transaction count describe different parts of the network. Understanding those parts comes before choosing a reward formula or interpreting a simulation.

## A blockchain records transitions agreed by a network

A **blockchain** records accepted transactions and the resulting state. A transaction requests a change, such as transferring an asset or registering stake. Nodes check proposed changes against protocol requirements. Consensus determines which valid history the network accepts.

Validation and consensus answer different questions: whether a transition is allowed, and which history is agreed. Economic incentives support the participants operating that process. The staking model studies their participation. It does not simulate packet propagation, adversarial consensus or transaction execution.

Avalanche's [Snowman consensus](https://build.avax.network/docs/primary-network/avalanche-consensus) uses repeated subsampled polling to build agreement. The security implications depend on protocol assumptions and the distribution of stake. A simulated increase in own stake alone is therefore insufficient to quantify attack cost or prove consensus security.

## Avalanche separates chain responsibilities

The [Primary Network](https://docs.avax.network/docs/primary-network) contains three built-in chains. The P-Chain manages staking, validator registration and platform operations. The C-Chain executes smart contracts. The X-Chain supports native asset operations. Their responsibilities explain why staking data and activity data come from different sources.

Avalanche L1s can have their own validator arrangements. Their registration and fee economics differ from Primary Network AVAX staking. The [node documentation](https://build.avax.network/docs/nodes) distinguishes these roles. The released simulation represents Primary Network validator own stake, rather than every economic process on every Avalanche chain.

## AVAX is both an asset and a protocol unit

AVAX is used for Primary Network stake and transaction fees. Staking rewards create additional AVAX, while fees remove AVAX through burning. The [tokenomics explanation](https://support.avax.network/en/articles/6912428-tokenomics-faq) describes a 720 million AVAX cap, issuance-funded validator rewards and the separation between burned fees and those rewards.

The cap constrains the issuance budget. Reward design determines its use over time, and participation determines how much stake accepts the offered return. AVAX prices and outside investment opportunities affect the dollar value of that return. In v0.8.0, those relationships enter through supplied scenarios and response assumptions. The model does not generate a market price for AVAX.

**Issuance** means newly created AVAX. **Burn** means AVAX permanently removed. Net issuance subtracts burn from issuance over a stated interval. A percentage called inflation also needs a supply denominator and annualization convention. The [accounting chapter](data.md) distinguishes the P-Chain supply counter, realized supply and circulating supply.

## A node is not the same unit as an operator

A **node** has a network identity. A **validator** participates in validation. An **operator** controls one or more nodes. A **delegator** commits AVAX to a validator without operating that validator. Node counts therefore differ from operator counts, and node-level concentration differs from concentration of ownership.

Validator **own stake** is the AVAX committed by the validator itself. Delegated AVAX adds to its total validation weight but is a separate population and income source. Delegation fees transfer part of delegator rewards to the validator. The [staking parameters](https://docs.avax.network/docs/primary-network/validate/how-to-stake) specify a 2,000 AVAX validator minimum and a 25 AVAX delegation minimum, with further duration, capacity and eligibility requirements.

An operator weighs returns against operating costs, liquidity needs, risk and alternatives. The model fits patterns in observed node decisions and adds explicit responses to changed yields. It does not reconstruct each operator's private objectives or identify common ownership from a NodeID alone.

## A commitment fixes an amount and a time interval

A **staking period** commits an amount from its start to its end. Acceptance can precede the start, so those timestamps must be distinguished. The potential reward is calculated under the applicable protocol configuration. Payment depends on satisfying eligibility requirements.

At the [Helicon upgrade](https://docs.avax.network/docs/primary-network/helicon-upgrade), Mainnet validator minimum duration fell from 14 days to 48 hours, the uptime requirement rose from 80% to 90%, automatic renewal became available and ACP-285 began its rate ramp. Delegator duration and automatic-renewal treatment differ. A pre-upgrade duration assumption should not be applied to every later commitment.

The chain can record multiple cycles for an automatic-renewal registration. Transaction counts, cycle counts and node counts answer different questions. The equal-window Helicon figures use new transactions at their first cycle and exclude later automatic cycles. The released behavioural model's seven-day renewal classification is also distinct from a descriptive fourteen-day renewal statistic.

## Reward design allocates a finite budget across participation

ACP-285 aims to lower inflation, extend the issuance-funded security budget and encourage longer staking. Lower offered returns may also change renewal and entry. The [proposal](https://github.com/avalanche-foundation/ACPs/blob/b80ea34682b419603f0241f114560dea5d61e03a/ACPs/285-reduce-minimum-consumption-rate/README.md) changes the minimum consumption-rate parameter while retaining the maximum.

The research compares budget use with participation outcomes under explicit conditions. Validator stake, count, duration and concentration are useful measures, with distinct interpretations. The Foundation chooses which should be objectives, safeguards or descriptive information. The model and evaluation system make those choices visible.

## Check the economic interpretation

Before reading a result, identify the population, unit, time interval and comparator. A rise in gross commitments can coexist with fewer active validators. Scheduled AVAX-days include future time and potentially repeated capital. Neither observation alone identifies an upgrade's causal effect. The [brief's matched-window example](../../content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/brief.md#1-commitments-increased-after-helicon-while-active-validators-declined) demonstrates these distinctions.

[Manual contents](README.md)
