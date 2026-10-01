---
title: "2026-10-01-staking-model-v0"
description: "The staking model runs, and it reproduces the chain's own reward and stake records exactly. Its first behaviour model does not yet beat the forecast that nothing changes, and every comparison of reward mechanisms depends on how strongly validators respond to pay, which history alone cannot tell us. Version 0, under review."
date: 2026-10-01
status: draft
deliverables: ["2.1", "2.4", "2.8"]
tags: ["model-validation", "issuance-and-rewards", "mechanism-design", "parameter-selection-under-uncertainty"]
---

# The staking model runs and matches the chain exactly, and which reward mechanism wins depends on how validators respond

![Five reward mechanisms from the Fortuna upgrade, 20 runs each: active validators after 180 days against AVAX issued, at three assumed strengths of response](/Phase-II/Wiki/Memos/drafts/2026-10-01-staking-model-v0/model-v0-sweep.png)

*Five reward mechanisms, each started at the Fortuna upgrade on 8 April 2025 and run for 180 days. Each point is the mean of 20 runs, and each bar spans the 10th to 90th percentile. The three panels differ only in one assumed setting: how much more likely validators are to renew, and to join, for each percentage point of annual reward above today's. Source runs: staking-periods-2026-09-30 and avax-monetary-daily-2026-09-30.*

With no response to pay, every mechanism ends with the same 1,363 validators and differs only in what it mints. Once validators respond, the mechanisms separate. At the strongest response we tested, a reward that rises with a validator's tenure ends with 1,483 validators, 8.8% more than today's rules, and issues 12.5% more AVAX. The ACP-285 settings, started at the same date, end with 941. History cannot tell us how strong the response is, so we will report every recommendation across the full range of responses, never at one assumed value.

This is version 0 of the model. Shawn has not yet reviewed the code, and it ships with this release labelled "v0, under review".

## What the model is

The model steps the staking system forward one day at a time. Its state is the set of open validator commitments, their stakes, and the AVAX supply. Each day some commitments end, some renew, and new ones begin, and each started commitment is paid by the reward mechanism under test. Every setting has stated bounds, and a run refuses a setting outside them. The model also checks its accounting on every step, so a run that loses or creates stake stops instead of reporting a number.

Four pieces run today.

1. **A replay of the chain.** We feed in every recorded stake start, end, and reward payment and step them through the model. On all 1,896 complete days from 10 September 2020 to 18 November 2025, the replayed active stake, validator and delegation counts, and rewards paid equal our daily monetary ledger exactly, to the smallest unit of AVAX. That proves the model's day boundaries, accounting, and units before any behaviour is added. Everything from the Granite upgrade on 19 November 2025 onward is held back, untouched, to test the model once it is fitted.
2. **Reward and admission mechanisms.** Today's reward formula, the ACP-285 settings, a tenure boost, a quadratic curve, and the quadratic curve held to today's issuance. Today's formula equals the protocol's reward calculation to the smallest unit, and each alternative equals today's formula at its neutral setting. The duration-dependent minimum stake is modeled the same way, and has [its own memo](/Phase-II/Wiki/Memos/drafts/2026-10-01-duration-dependent-minimum/).
3. **A first validator lifecycle.** Each ending commitment renews with the share observed in the year before the forecast starts. New commitments arrive at that year's rate, with durations and stakes drawn from it.
4. **An explorer.** A notebook in which each mechanism's settings are sliders, and its reward curve and the AVAX it would mint for a real year of stakes update as they move.

## What the results say

![Annual reward rate by staking duration under today's rules and four alternatives](/Phase-II/Wiki/Memos/drafts/2026-10-01-staking-model-v0/model-v0-reward-curves.png)

*Annual reward per AVAX by duration, for stakes starting 22 December 2026, after the ACP-285 ramp ends. Source run: staking-periods-2026-09-30.*

We repriced every validator and delegator commitment from the year before Granite, 14,215 validator periods and 1,233,029 delegations, as if each started on 22 December 2026. Today's rules mint 11.46 million AVAX for that year of stakes. ACP-285 with a 5% target mints 13.6% less, the tenure boost 5.8% more, and the quadratic curve 4.4% less. Issuance is the cost in every comparison. A mechanism that mints more will always look better on stake unless its cost is counted.

![Twenty runs of the validator lifecycle from each of five upgrades against what happened](/Phase-II/Wiki/Memos/drafts/2026-10-01-staking-model-v0/model-v0-lifecycle.png)

*Active validators for 90 days after each of five upgrades, Banff to Fortuna. Pale lines are model runs, and the dark line is what happened. Every input comes from data before the upgrade. Source runs as above.*

The first lifecycle model is worse than the naive forecast that tomorrow looks like today. Across five upgrades, two quantities, and two horizons, it beats that forecast in 8 of 20 comparisons. Its range covers the actual stake in 5 of 10 cases and the actual validator count in 2 of 10. One renewal share and one entry rate cannot capture how much the validator count moves. The data already show what is missing: renewal rises with tenure, from 71% on a node's first commitment to 93% by its seventh, and large operators move as single events. The next lifecycle model has to beat this one.

## Known limits

1. The lifecycle model covers validators only. Delegations and their rewards are not in it yet, so the issuance it reports is below what the chain mints.
2. Renewal and entry are observed shares, not fitted estimates.
3. The supply in the model is the counter the reward formula reads. It ignores burned fees, so it sits 2.6% to 3.4% above the realized supply. That is right for computing rewards, but a staking ratio must use the realized supply.
4. The supply at a forecast's start is read in stake-start order rather than block order, which differs by under 15 AVAX.
5. 81 daily rows with no supply value, 75 in 2020 and 6 in 2026, are skipped silently. They should be refused or stated.
6. Tenure counts an earlier commitment on the same node even while it is still running. One known overlap makes this negligible today.
7. The quadratic curve held to today's issuance mints 1.4% more than today's rules over the 180-day run. It was matched on the stakes open at the start, and the stakes that renew and enter afterwards differ. We have not yet tested whether that gap is larger than run-to-run noise.

## Next

On Friday 2 October we would like to agree what "better" should mean for the behaviour model, since this version sets the bar the next must clear. At the calls every other Friday after that, we add delegations and the reward flow, replace the observed shares with fitted behaviour, and present the rebuilt validation report on 30 October. Workshop 1, at the 13 November call, walks through the full model. The live Helicon reward ramp is the first real test of how strongly validators respond, and we score our first Helicon forecasts on 22 October.

**For you:** which range of validator response to pay would the Foundation find credible enough to plan around, and which reward mechanisms should the first full comparison include?
