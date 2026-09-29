---
title: "Brief, 2026-10-02"
description: "The pre-read for the 2026-10-02 call with the Avalanche Foundation: takeaways, questions for the Foundation, next steps, and what was done about each comment on the 2026-09-25 agenda."
date: 2026-09-29
status: draft
---

![Share of new validator commitments at the minimum duration, and their share of committed AVAX-days, by upgrade period](/Phase-II/Wiki/Memos/drafts/2026-10-01-commitments-by-upgrade/commitments-by-upgrade.png)

*Since Durango, most new validator commitments last the 14-day minimum, but they hold 3% to 11% of committed AVAX-days. From the memo in takeaway 1.*

## Takeaways

1. **Most staking decisions sit at the minimum, but little of the capital does.** From Durango to Fortuna, 62% to 69% of new validator commitments lasted the 14-day minimum, holding 3% to 5% of committed AVAX-days, and 11% under Granite. [Memo](/Phase-II/Wiki/Memos/drafts/2026-10-01-commitments-by-upgrade/).
2. **Helicon's first week is being measured.** By 2026-09-24, 20 validator commitments had begun under the new rules. Two chose 48 hours, both auto-renewed, at about 2,000 AVAX. Two of about 1.75 million AVAX each chose about 198 days. The first full comparison runs on 2026-09-29, and new nodes' durations, nodes lowering their duration, and auto-renewals are now tracked daily.
3. **BENQI's delegation address is identified.** The address that delegates about half of all delegated stake is BENQI's funding address: 104 of the 111 validators it delegates to are on Snowpeer's BENQI list, and its 18.36 million AVAX in active delegations is close to Snowpeer's 19.53 million.
4. **AVAX exchange-traded products are captured.** Daily net asset value and AVAX held, with 21Shares' history since 2021, are in the data record, ready for the check you suggested.
5. **The research is yours to run.** The repository with this site, the code, both notebooks, and the data goes to the Foundation's repository on 2026-09-30, with setup steps an AI coding agent can follow.

## For discussion

1. **Durango.** The median validator commitment fell from about 4.3 weeks to 2.1 weeks at Durango and stayed there until Granite. Durango also changed how a staking period starts. **For you:** what else changed for validators at Durango that we should test as a cause?
2. **Reproducing your validator article.** Three inputs decide whether our estimates can match yours. **For you:** what is the eleventh feature and the rule that sets market size, and does tenure mean a node's span, its days staked, or its current streak?
3. **The January staking and price model.** We have reconstructed its equations from three images. **For you:** is there a deck, note, or code behind it that we could reproduce from instead?
4. **Validation.** Before the parameter sweeps, we will propose what "better" means for the model, with a test for each claim. **For you:** which outcomes matter most to the Foundation when judging a reward change: staking ratio, validator count, reward stability, or others?

## Next steps

| Step | Owner | By |
| --- | --- | --- |
| Helicon's first full comparison, with the three tracking views | BCRG | 2026-10-09 |
| The repository and data in the Foundation's repository | BCRG, Shawn | 2026-09-30 |
| The validation standard for the model | BCRG | 2026-10-09 |
| Whether ETF net asset value rose after Helicon | BCRG | 2026-10-09 |
| Introductions to the institutional staking panel and the Summit slides | Foundation, Matias | Open |

## Your comments on the 2026-09-25 agenda

| Comment | What was done |
| --- | --- |
| "Do you mean the amount or duration?" | Duration. See discussion item 1 and the [memo](/Phase-II/Wiki/Memos/drafts/2026-10-01-commitments-by-upgrade/) |
| "Sure if it does not result in a huge incremental lift." On a minimum stake that falls with duration | It will be evaluated as one more reward mechanism in the Milestone 2 sweeps. It adds a mechanism, not a model |
| "Yes, let me follow up with Matias on that." | Waiting on the Foundation |
| Live tracking of new nodes' durations, old nodes lowering duration, and the overall distribution | Tracked daily since 2026-09-28. First comparison in takeaway 2 |
| Check for a NAV increase in the AVAX ETF or ETFs holding AVAX | Captured. The check is a next step |
| Use Snowpeer's delegations page for BENQI's addresses | Done. Takeaway 3 |
