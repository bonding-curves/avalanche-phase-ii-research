---
title: "2026-10-01-benqi-interview"
description: "BENQI's interview checked against the chain: its address made 93% of all delegations, holds about half of delegated stake, never delegates longer than 17 days, and since 2026 places most of it on validators that pay BENQI."
date: 2026-10-01
status: draft
deliverables: ["1.4", "2.8"]
tags: ["delegation-market", "staking-duration-and-liquidity", "validator-economics"]
---

# BENQI's delegations follow liquidity and capacity, not validator preference

## Finding

On 31 August we interviewed Hansen, a co-founder of BENQI, the largest liquid staking protocol on Avalanche. We then checked his account against the P-Chain. Most of it holds. BENQI's funding address made 93.3% of every delegation since January 2022, held 18.27 million AVAX of active delegations on the day of the interview, which is 48.8% of all delegated stake, and never delegated for longer than 17 days. One part of his account has changed since 2026: 62.5% of BENQI's delegated stake now sits on validators that pay their rewards to BENQI's own labelled address, where earlier almost none did.

For the model, this means BENQI is one operator with a rule, not a population of delegators expressing preferences. Its delegations say little about which validators delegators prefer.

## What Hansen told us

We spoke for about an hour, after an introduction from the Foundation. In summary:

1. BENQI's liquid staking product holds about 10% to 12% of all staked AVAX.
2. Before Helicon, BENQI delegated for 14 to 18 days at a time, so that its users can redeem quickly.
3. Bots allocate each delegation by weighing a validator's free delegation capacity, uptime, staking duration, and stake, and in practice favour validators with at least 8,000 AVAX of their own stake.
4. BENQI runs five or six validators of its own and delegates the rest to the open network.
5. After Helicon, BENQI was leaning toward two-day durations. The delegation minimum is still 14 days, so it could only shorten through validators it runs itself, and building that would take months.

Hansen also mentioned churn, revenue effects of Helicon, fees paid to validators, and votes by holders of BENQI's governance token that direct part of the delegations. We have not checked any of these.

## What the chain shows

We identify BENQI by two addresses. A delegation-tracking site, Snowpeer, labels BENQI's reward address. The address that funds 93.3% of all delegations is BENQI's funding address: of the 111 validators it delegated to after 21 September, 104 are on Snowpeer's BENQI list. Both identifications are our inference, which is why we ask you below to confirm them.

| Check | Hansen | Chain | Source run |
| --- | --- | --- | --- |
| Share of delegations | Most delegations | 6,585,312 of 7,056,204 since January 2022, 93.3% | `observed-delegations-2026-09-28` |
| Share of delegated stake | Not stated | 18.27M of 37.43M AVAX on 31 August, 48.8% | Same, with `avax-monetary-daily-2026-09-30` |
| Share of all stake | 10% to 12% | 8.6% from delegations alone. The stake of the validators paying BENQI would add to it, which we have not yet measured | Same |
| Duration | 14 to 18 days | Every delegation between 14.0 and 17.0 days | `observed-delegations-2026-09-28` |
| Where the stake goes | Mostly the open network | 11.42M of 18.27M AVAX, 62.5%, on validators paying BENQI's labelled address, on 31 August | Same, with `operators-2026-09-30` |
| After Helicon | Leaning to two days | Not yet measurable. Our delegation capture ends on 22 September, before Helicon activated | |

## What it means for the model

This is our reading.

1. **BENQI is a named operator.** The model treats it as one agent with a rule: delegate for 14 to 17 days, fill free capacity, prefer larger and more reliable validators, and, since 2026, favour its own. The other 270,270 delegating addresses form the population whose choices we estimate.
2. **Delegator demand is estimated without BENQI first.** Its allocation follows capacity and liquidity, not a validator's fee or yield, so including it would make delegators look more sensitive to capacity and less to price than they are. We report the estimate with BENQI included as a second result.
3. **The delegation minimum is BENQI's lever.** Helicon's 48-hour minimum applies to validators. BENQI's duration is set by the 14-day delegation minimum and its users' need to redeem, so only a shorter delegation minimum, or validators BENQI runs itself, would change it.
4. **One interview sets hypotheses, not parameters.** Each claim above enters the model only through the on-chain check beside it.

## For you

On 25 September you pointed us to Snowpeer for BENQI's addresses, and we used it. Can the Foundation confirm the two addresses, and that the validators paying BENQI's reward address run BENQI's own capital? On 14 August you wrote that BENQI "basically randomly delegate". The chain suggests its allocation follows free capacity and, since 2026, its own validators. Did you mean an earlier period, or random with respect to fee and yield?
