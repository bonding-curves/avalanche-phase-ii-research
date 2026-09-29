---
title: Glossary and Notation
description: "The terms, symbols, units, and network upgrades used across the notebooks, datasets, and milestone pages of this research, each defined once."
tags: ["issuance-and-rewards", "staking-duration-and-liquidity", "delegation-market"]
---

Every page on this site uses the words and symbols below with the meanings given here.

## Terms

Dataset identifiers such as `derived.staking-periods` and field names such as `stake_avax` refer to entries in the project's data catalog, `data/data-catalog.json`.

| Term | Definition | Unit | Where it is used |
| --- | --- | --- | --- |
| Acceptance time | The block time at which the P-Chain accepted a staking transaction. | UTC timestamp | Field `accepted_at` in every staking dataset |
| Active stake | Stake in commitments that are open at a given instant. It is a stock measured at one time and differs from the stake summed over commitments accepted during a window. | AVAX | `derived.avax-monetary-daily`, `derived.market-weeks`, active stock chart in the staking periods notebook |
| Annualized reward rate | The potential reward divided by the stake and scaled from the commitment duration to one year. The gross rate is before the delegation fee and the net rate is after it. | Fraction per year | `derived.validator-weeks`, `derived.observed-delegations` |
| Auto-renewed staking | A Helicon validation mode in which stake restarts automatically at the end of each cycle, with reward and uptime computed per cycle. After Helicon one transaction can therefore hold several commitments. | None | Field `staking_type` in the Data API validator datasets |
| AVAX burned | AVAX destroyed by transaction fees and L1 validator fees on the P-, X-, and C-Chains. Burns reduce the realized total supply. | wei or nAVAX | Burn datasets, `derived.avax-monetary-daily` |
| Commitment | One staking transaction's period from its start time to its end time, with its node, stake, and delegation fee. It is the counted observation in the analysis. The datasets and the staking periods notebook call the same object a staking period. | One per staking transaction | Both notebooks, `derived.staking-periods` |
| Commitment duration | The time from a commitment's start to its end. The protocol allowed 14 to 365 days for every commitment before Helicon. | Days in datasets, weeks in charts | Field `duration_days`, both notebooks |
| Committed AVAX-days | Stake multiplied by the time it is committed, summed over commitments. AVAX-weeks is the same quantity divided by seven. It measures capital held over time, not stake open at one instant. | AVAX-days or AVAX-weeks | Field `stake_days_avax` in `derived.node-table`, validator rewards notebook |
| Concentrated address | The single delegator address that made 93% of delegation events. Weekly delegation counts are reported with and without it. | P-Chain address | `derived.validator-weeks`, `derived.observed-delegations`, `derived.market-weeks` |
| Current streak | The length of a node's latest streak, measured to the capture time for a node that is still validating. | Days | Field `current_streak_days` in `derived.node-table` |
| Days staked | The sum of a node's commitment durations with gaps excluded and overlapping commitments counted once. | Days or weeks | Fields `tenure_days` and `days_staked_weeks` |
| Delegated stake | AVAX that delegators stake to a validator's commitment. It adds to the validator's weight but not to its self-stake. | AVAX | Fields `delegated_avax`, `delegated_avax_at_week_start` |
| Delegatee reward | The validator's fee income from its delegators. From Cortina it is withheld from each delegator's reward and paid to the validator at the end of the validator's own commitment. | nAVAX | Fields `fee_transfer_navax`, `delegatee_fees_avax` |
| Delegation capacity | The most delegated stake a validator can accept: four times its self-stake, limited so that self-stake plus delegations stay at or below 3,000,000 AVAX. | AVAX | Fields `capacity_left_avax`, `delegation_capacity_navax` |
| Delegation fee | The share of a delegator's reward that the validator keeps. The protocol minimum is 2%. A fee of 100% closes the validator to delegation in practice. | Fraction | Field `delegation_fee_rate`, staking periods notebook |
| Delegation fill | Delegated stake divided by delegation capacity. | Ratio | Fields `delegation_fill`, `delegation_fill_api` |
| Delegator | A token holder who stakes AVAX to an existing validator's commitment and pays that validator the delegation fee. The minimum delegation is 25 AVAX. | None | Field `role`, both notebooks |
| Immediate start and pending start | An immediate start begins at acceptance. A pending start was accepted with a later start time and waited until it arrived. Every commitment accepted from Durango on is an immediate start. | None | Field `start_kind` in `derived.staking-periods` |
| KPI | A key performance indicator: an output measure computed for every simulated trajectory. | Varies | Milestone 2 |
| L1 validator | A validator of one Avalanche L1 that pays a continuous fee from a balance and has no end time. It is separate from Primary Network staking, which is the subject of this research. | None | Burn datasets |
| Network upgrade | A coordinated activation of protocol changes at a set time. The protocol upgrades table below lists each one. | UTC timestamp | Both notebooks, protocol code |
| Node | One machine identity on the network, named by a NodeID. A node is not an operator, because one operator can run many nodes. | NodeID | Field `node_id`, `derived.node-table` |
| On offer | A validator is on offer in a week when, at the Monday cutoff, it is validating, has at least 14 days left in its commitment, and has at least 25 AVAX of delegation capacity left throughout the next 14 days. | Flag | Field `offered_at_week_start` in `derived.validator-weeks` |
| Potential reward | The reward the protocol fixes for a commitment from its stake, duration, and the supply at its start. It is added to the P-Chain supply counter when fixed. | nAVAX | Field `potential_reward_navax` |
| Primary Network | The set of validators that validate Avalanche's P-, X-, and C-Chains and earn the staking reward. | None | Every page |
| Protocol kernel | The project's reimplementation of the AvalancheGo reward and staking rules in integer arithmetic. The field `reproduced` records whether it matches the recorded potential reward. | None | Fields `kernel_reward_navax`, `reproduced`, staking periods notebook |
| PSUU | Parameter selection under uncertainty: running the model across ranges of protocol parameters and uncertain conditions to find parameter choices that perform well across them. | None | Milestone 2 |
| Realized reward | The reward actually paid at the end of a commitment. It equals the potential reward when the uptime requirement is met and zero when it is not. | nAVAX | Field `realized_reward_navax` |
| Realized total supply | AVAX in existence, replayed daily from the 360,000,000 AVAX genesis supply by adding rewards paid and subtracting AVAX burned. | wei | Field `total_supply_close_wei` in `derived.avax-monetary-daily` |
| Realized volatility | The sample standard deviation of the last 30 daily log returns of the AVAX price, multiplied by $\sqrt{365}$. | Annualized fraction | Fields `realized_volatility_30d`, `volatility_30d` |
| Reward address | The P-Chain address that receives a commitment's reward. The site uses a shared reward address as an operator proxy. It suggests one operator but does not prove one. | P-Chain address | Fields `reward_address`, `operator_group` |
| Self-stake | The AVAX a validator stakes in its own commitment, excluding delegations. | AVAX | Fields `stake_avax` for validators, `self_stake_avax` |
| Span | The time from a node's first commitment start to the end of its last commitment, gaps included. | Days or weeks | Fields `span_days`, `node_age_weeks` |
| Staker | A validator or a delegator. The protocol uses this word when a rule applies to both. | None | Protocol code, datasets |
| Staking ratio | Active validator and delegated stake divided by the realized total supply at the same instant. | Fraction | Phase I economic model pages, computable from `derived.avax-monetary-daily` |
| Stock and flow | A stock is measured at an instant, such as active stake. A flow is summed over a window, such as stake accepted in a week. Summing a stock across weeks double counts it. | Varies | Staking periods notebook, `derived.market-weeks` |
| Streak | Consecutive commitments by one node with no gap longer than one day between one commitment's end and the next start. | Days | Fields `streaks`, `current_streak_days` in `derived.node-table` |
| Supply cap | The 720,000,000 AVAX limit that the reward formula approaches and never exceeds. | AVAX | Protocol code |
| Supply counter | The P-Chain's running supply, which includes potential rewards when fixed and removes those forfeited. It is the supply input to the reward formula, and it differs from the realized total supply. | nAVAX | Fields `supply_before_navax`, `supply_counter_avax` |
| Tenure | A word used in Foundation discussions for how long a node has validated. It can mean span, days staked, or current streak, so the site uses those three terms instead. | None | Field `tenure_days`, which holds days staked |
| Trajectory | One simulated path of the model over time under one parameter set and one draw of uncertain conditions. | None | Milestone 2 |
| Unstaked supply | Realized total supply minus active validator and delegated stake at the same instant. | AVAX | Field `unstaked_supply_avax` in `derived.market-weeks` |
| Upgrade period | The time from one network upgrade's activation to the next, named by the upgrade that opens it. It includes its opening instant. The eight Apricot phases form one upgrade period. The datasets store the upgrade name in the field `regime`. | UTC interval | Both notebooks, field `regime` |
| Uptime | The share of a commitment during which a validator was online and responsive, as measured by other nodes. Different observers can report different values. | Fraction or percent | Fields `uptime`, `uptime_rpc_pct`, `uptime_api_pct`, `p50_uptime_pct` |
| Uptime requirement | The uptime a validator needs to receive any reward. It is 80% for validations that started before Helicon and 90% for validations that start at or after Helicon, 2026-09-22 15:00 UTC. | Fraction | Protocol code, fields `failed_periods`, `realized_reward_navax` |
| Validator | A node while it holds stake in the Primary Network validator set. The minimum self-stake is 2,000 AVAX. | None | Both notebooks, every staking dataset |
| Validator-week | One validator node in one UTC week, with every feature computed from transactions accepted before the Monday 00:00 UTC cutoff. | Node and week | `derived.validator-weeks` |

## Symbols

Symbols with subscript $i$ refer to one commitment. The reward symbols follow the AvalancheGo reward calculator, and the protocol code computes them in nAVAX with integer arithmetic.

| Symbol | Meaning | Unit |
| --- | --- | --- |
| $i$ | One commitment | Identifier, the transaction hash |
| $a_i$ | Acceptance time of commitment $i$ | UTC timestamp |
| $b_i$, $e_i$ | Start time and end time of commitment $i$ | UTC timestamp |
| $\Delta t_i = e_i - b_i$ | Commitment duration | Days or weeks |
| $S_i$ | Stake of commitment $i$. For a validator this is its self-stake. | AVAX |
| $X_i = S_i\,\Delta t_i$ | Committed AVAX-weeks of commitment $i$ over its full duration | AVAX-weeks |
| $r$, $[A_r, B_r)$ | One upgrade period and its bounds. Commitment $i$ belongs to $r$ when $A_r \le a_i < B_r$. | UTC interval |
| $Q$ | Supply counter read before the commitment's reward is fixed | nAVAX |
| $Q_{\max}$ | Supply cap, 720,000,000 AVAX | nAVAX |
| $T_m$ | Minting period, 365 days | Seconds in the protocol |
| $c_{\min}$, $c_{\max}$ | Minimum and maximum consumption rates, 0.10 and 0.12 | Fraction per year |
| $c(\Delta t) = c_{\min} + (c_{\max} - c_{\min})\,\dfrac{\Delta t}{T_m}$ | Consumption rate for duration $\Delta t$, rising linearly from $c_{\min}$ at zero duration to $c_{\max}$ at one year | Fraction per year |
| $R = \min\!\left((Q_{\max} - Q)\,\dfrac{S}{Q}\,c(\Delta t)\,\dfrac{\Delta t}{T_m},\; Q_{\max} - Q\right)$ | Potential reward of stake $S$ committed for $\Delta t$ | nAVAX |
| $c_{\min}(b) = 0.10 - 0.025\,\min\!\left(1, \dfrac{b - t_H}{90\ \text{days}}\right)$ for $b \ge t_H$ | ACP-285 minimum consumption rate for a stake starting at $b$, where $t_H$ is Helicon's activation. It moves from 0.10 to 0.075 over 90 days and is fixed at the stake's start. | Fraction per year |
| $u_i$, $u_{\min}$ | Observed uptime of commitment $i$ and the uptime requirement, 0.80 or 0.90 | Fraction |
| $\hat R_i = R_i$ if $u_i \ge u_{\min}$, else $0$ | Realized reward | nAVAX |
| $f$ | Delegation fee rate, at least 0.02. The protocol stores it in millionths. | Fraction |
| $fR$, $(1 - f)R$ | Split of a delegation's reward: the validator's delegatee reward and the delegator's payout | nAVAX |
| $\mathrm{ARR} = \dfrac{R}{S}\cdot\dfrac{T_m}{\Delta t}$ | Gross annualized reward rate | Fraction per year |
| $(1 - f)\,\mathrm{ARR}$ | Net annualized reward rate for a delegator | Fraction per year |
| $\kappa$ | Delegation multiplier, 4 on mainnet. ACP-247 proposes 24 and is not part of Helicon. | Ratio |
| $W_{\max} = \min\!\left((1 + \kappa)\,S,\; 3{,}000{,}000\ \text{AVAX}\right)$ | Maximum validator weight, self-stake included | AVAX |
| $\phi_t = \dfrac{S^{\mathrm{val}}_t + S^{\mathrm{del}}_t}{M_t}$ | Staking ratio at time $t$: active validator stake plus active delegated stake, over realized total supply $M_t$ | Fraction |
| $\sigma_{30} = \mathrm{sd}\left(\ln\dfrac{P_d}{P_{d-1}}\right)\sqrt{365}$ | Realized volatility from the last 30 daily log returns of the closing price $P_d$ | Annualized fraction |

## Units

- AVAX is the native token and the unit used in charts and tables.
- nAVAX is $10^{-9}$ AVAX. The P-Chain records every stake, reward, and supply amount as a whole number of nAVAX, and fields ending in `_navax` use it.
- wei is $10^{-18}$ AVAX, the C-Chain's native unit. The daily monetary ledger stores every amount in wei so that P-Chain and C-Chain amounts add exactly. One nAVAX is $10^{9}$ wei.
- Millionths are the protocol's unit for fractions. A delegation fee of 20,000 millionths is 2%, and a consumption rate of 100,000 millionths is 10%.
- Rates are stored as fractions. Fields ending in `_pct` hold percent.
- All times are UTC. A day is a UTC calendar day. A week runs from Monday 00:00 UTC to the next Monday 00:00 UTC.
- AVAX-days and AVAX-weeks measure stake held over time. One AVAX staked for one week is one AVAX-week, or seven AVAX-days.
- Prices are USD per AVAX from CoinGecko and DefiLlama, or USDT per AVAX from Binance. The two quotes are compared, not treated as identical.

## Protocol upgrades

Activation times are the mainnet schedule in AvalancheGo's `upgrade/upgrade.go`, as copied into the protocol code. Each upgrade opens an upgrade period that lasts until the next activation. The genesis rules that apply throughout unless a row says otherwise are a 2,000 AVAX minimum self-stake, a 25 AVAX minimum delegation, durations of 14 to 365 days, a 2% minimum delegation fee, an 80% uptime requirement, consumption rates of 10% to 12%, and a 720,000,000 AVAX supply cap.

| Name | Activation (UTC) | What changed for staking |
| --- | --- | --- |
| Genesis | 2020-09-10 | The network launched with the genesis staking rules. |
| Apricot | Phase 1 2021-03-31 14:00, Phase 2 2021-05-10 11:00, Phase 3 2021-08-24 14:00, Phase 4 2021-09-22 21:00, Phase 5 2021-12-02 18:00, Pre-Phase 6 2022-09-05 01:30, Phase 6 2022-09-06 20:00, Post-Phase 6 2022-09-07 03:00 | The staking rules the research models are unchanged. The eight phases form one upgrade period, and the field `regime` keeps the exact phase. |
| Banff | 2022-10-18 16:00 | Permissionless validator and delegator transactions became available alongside the original transaction types. The first permissionless validator transaction in the data was accepted on 2022-12-22. |
| Cortina | 2023-04-25 15:00 | A delegator's fee is withheld from its reward and paid to the validator at the end of the validator's own commitment. Before Cortina the fee was paid with the delegation's reward. |
| Durango | 2024-03-06 16:00 | ACP-41 removed pending starts, so every commitment begins at acceptance. ACP-62 disabled the original `AddValidatorTx` and `AddDelegatorTx`. |
| Etna | 2024-12-16 17:00 | ACP-77 separated L1 validators from Primary Network staking. ACP-103 introduced dynamic P-Chain fees. The Primary Network reward rules are unchanged. |
| Fortuna | 2025-04-08 15:00 | No staking rule changed. The Phase I pages name the April 2025 upgrade Octane, which activated ACP-176, dynamic C-Chain gas limits. |
| Granite | 2025-11-19 16:00 | No staking rule changed. It activated ACP-181, ACP-204, and ACP-226. |
| Helicon | 2026-09-22 15:00 | ACP-285 lowers the minimum consumption rate from 10% to 7.5% over 90 days, keyed to stake start. ACP-273 lowers the minimum validator duration from 14 days to 48 hours. ACP-267 raises the uptime requirement to 90% for validations starting at or after activation. ACP-236 adds auto-renewed staking. |
