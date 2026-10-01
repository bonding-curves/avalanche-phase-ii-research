---
title: "2026-10-01-staking-model-v0"
description: "The staking model reproduces the chain's stake and reward records exactly on all 1,896 complete days before Granite, prices every reward mechanism on the same year of real stakes, and shows how the mechanisms separate once validators respond to pay. Version 0, under review."
date: 2026-10-01
status: draft
deliverables: ["2.1", "2.4", "2.8"]
tags: ["model-validation", "issuance-and-rewards", "mechanism-design", "parameter-selection-under-uncertainty"]
---

# The staking model reproduces the chain exactly and shows how reward mechanisms separate as validators respond to pay

![Active validator stake replayed by the model against the on-chain record, 2020 to 2025](/Phase-II/Wiki/Memos/drafts/2026-10-01-staking-model-v0/model-v0-replay.png)

*Active validator stake each day, in millions of AVAX. The wide pale line is the chain's record. The thin dark line is the model replaying every recorded stake start, end, and reward payment. Shaded bands mark alternate upgrade periods. Source runs: `staking-periods-2026-09-30` and `avax-monetary-daily-2026-09-30`. [Interactive version](/Phase-II/Wiki/Memos/drafts/2026-10-01-staking-model-v0/model-v0-replay.html).*

The staking model runs. It reproduces the chain's own records exactly: on all 1,896 complete days from 10 September 2020 to 18 November 2025, the replayed active validator stake, delegated stake, validator count, delegation count, and rewards paid equal the ledger to the smallest unit of AVAX. On that foundation it prices every reward mechanism on the same year of real stakes, and it simulates how the validator set evolves under each. The mechanisms separate once validators respond to pay. At the strongest response we tested, the tenure boost ends 180 days with 8.8% more validators than today's rules, for 12.5% more AVAX issued.

This is version 0 of the model. It ships with this release, labelled "v0, under review".

## What the model is

The model steps the staking system forward one day at a time. Its state is the open validator commitments, their stakes, and the AVAX supply. Each day some commitments end, some renew, and new ones begin, and each new commitment is paid by the reward mechanism under test. Every setting has stated bounds, and the model checks its accounting at every step, so stake can never be created or lost unnoticed.

Four pieces run today:

1. **A replay of the chain.** This is the chart above. It confirms the model's day boundaries, accounting, and units before any behaviour is added. Everything from Granite on 19 November 2025 onward is held back, untouched, to test the model once it is fitted.
2. **Reward and admission mechanisms.** These are today's reward formula, the ACP-285 settings, a tenure boost, a quadratic curve, and the quadratic curve held to today's issuance. Today's formula equals the protocol's reward calculation to the smallest unit, and each alternative equals today's formula at its neutral setting. The duration-dependent minimum stake has [its own memo](/Phase-II/Wiki/Memos/drafts/2026-10-01-duration-dependent-minimum/).
3. **A validator lifecycle.** Each ending commitment renews at the share observed in the year before a forecast starts. New commitments arrive at that year's rate, with durations and stakes drawn from it.
4. **An explorer.** In this notebook each mechanism's settings are sliders. Its reward curve and the AVAX it would mint for a real year of stakes update as they move.

## What the results show

![Annual reward rate by staking duration under today's rules and four alternatives](/Phase-II/Wiki/Memos/drafts/2026-10-01-staking-model-v0/model-v0-reward-curves.png)

*Annual reward per AVAX by staking duration, for stakes starting 22 December 2026, after the ACP-285 ramp ends. The tenure boost is drawn for a validator in its ninth consecutive commitment. [Interactive version](/Phase-II/Wiki/Memos/drafts/2026-10-01-staking-model-v0/model-v0-reward-curves.html).*

**Every mechanism priced on the same stakes.** We repriced every commitment of the year before Granite, 14,215 validator periods and 1,233,029 delegations, as if each started on 22 December 2026. Today's rules mint 11.46 million AVAX for that year of stakes. Against that:
- ACP-285 with a 5% target mints 13.6% less,
- the tenure boost mints 5.8% more,
- the quadratic curve mints 4.4% less,
- the quadratic curve held to today's issuance mints the same.

Issuance is the cost side of every comparison the model reports.

![Five reward mechanisms from the Fortuna upgrade: active validators after 180 days against AVAX issued, at three strengths of response](/Phase-II/Wiki/Memos/drafts/2026-10-01-staking-model-v0/model-v0-sweep.png)

*Five mechanisms, each started at the Fortuna upgrade on 8 April 2025 and run for 180 days. Each point is the mean of 20 runs, and each bar spans the 10th to 90th percentile. The panels differ in one setting: how much more likely validators are to renew, and to join, for each percentage point of annual reward above today's. [Interactive version](/Phase-II/Wiki/Memos/drafts/2026-10-01-staking-model-v0/model-v0-sweep.html).*

**How the mechanisms separate.** With no response to pay, every mechanism ends with the same 1,363 validators and differs only in what it mints: from 4.57 million AVAX under ACP-285 to 5.52 million under the tenure boost. Once validators respond, cost and validators move together:
- **Tenure boost:** 1,408 validators at a response of 0.1, and 1,483 at 0.3. That is 8.8% above today's rules, for 12.5% more AVAX.
- **Quadratic curve held to today's issuance:** 1,412 validators at 0.3, 3.6% above today's.
- **ACP-285, started at the same date:** it issues 31% less over the period and ends with 941 validators at 0.3. It trades validator count for lower issuance.

History alone does not fix how strong that response is. So we will report every recommendation across the full range of responses, together with its issuance, rather than at one assumed value.

## Next steps

1. Fit behaviour in place of observed shares: renewal by tenure and by era, entry, and the moves of large operators. Each behaviour is a separate block that can be swapped and scored.
2. Add delegations and their rewards to the lifecycle, so issuance covers the full reward flow, and report staking ratios against realized supply.
3. Score the first Helicon forecasts on 22 October. The live Helicon reward ramp is the first real measurement of how strongly validators respond to pay.
4. Present the rebuilt validation report at the 30 October call, and walk through the full model at Workshop 1 on 13 November.

On Friday 2 October we would like to agree what "better" should mean for the behaviour model, since each version is measured against the last.

**For you:** which range of validator response to pay would the Foundation find credible enough to plan around, and which reward mechanisms should the first full comparison include?
