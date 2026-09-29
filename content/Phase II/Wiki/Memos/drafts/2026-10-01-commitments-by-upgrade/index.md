---
title: "Most new validator commitments stop at the minimum, but hold little of the capital"
description: "Since Durango, 62% to 69% of new validator commitments last the 14-day minimum, yet they hold 3% to 11% of committed AVAX-days. By upgrade period, from one pinned run."
date: 2026-10-01
status: draft
deliverables: ["1.4", "2.8"]
---

![Share of new validator commitments at the minimum duration, and their share of committed AVAX-days, by upgrade period](/Phase-II/Wiki/Memos/drafts/2026-10-01-commitments-by-upgrade/commitments-by-upgrade.png)

*For each upgrade period, the solid line is the share of validator commitments that began in it and lasted the minimum, under 16 days. The dashed line is those commitments' share of committed AVAX-days, each commitment's self-stake times its duration. See the jump at Durango and how far the two lines stay apart. Data: run `staking-periods-2026-09-22`, 57,560 validator commitments. [Interactive version](/Phase-II/Wiki/Memos/drafts/2026-10-01-commitments-by-upgrade/commitments-by-upgrade.html).*

## Finding

From Durango to Fortuna, 62% to 69% of new validator commitments lasted the 14-day minimum, against 9% to 30% in every earlier period. Those commitments held 3% to 5% of committed AVAX-days, and 11% under Granite. Most staking decisions now sit at the minimum, while almost all of the capital commits for longer.

## What it means

A rule aimed at short commitments reaches most validators but little of the stake. Helicon's 48-hour minimum and a minimum stake that falls with duration both act on this group. The capital a change moves is the dashed line, not the solid one, so the effect of either rule on economic security is bounded by 3% to 11% of committed AVAX-days, while its effect on validator behaviour reaches up to two thirds of decisions.

## The numbers

| Period | Commitments | Median weeks | Stake-weighted median weeks | Median self-stake (AVAX) | At the minimum | Their AVAX-days |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Genesis | 2,951 | 4.4 | 12.4 | 5,000 | 18% | 1% |
| Apricot | 11,847 | 4.3 | 8.8 | 2,085 | 18% | 2% |
| Banff | 3,431 | 4.4 | 9.7 | 2,202 | 9% | 1% |
| Cortina | 9,101 | 4.2 | 7.0 | 2,005 | 30% | 1% |
| Durango | 12,657 | 2.1 | 4.4 | 2,005 | 62% | 3% |
| Etna | 5,179 | 2.1 | 4.4 | 2,000 | 69% | 3% |
| Fortuna | 7,775 | 2.1 | 4.2 | 2,000 | 63% | 5% |
| Granite | 4,619 | 3.6 | 4.0 | 14,655 | 41% | 11% |

Node counts per period are in `commitments-by-upgrade.csv` beside this page.

The median commitment falls from about 4.3 weeks to 2.1 weeks at Durango and stays there until Granite. The median self-stake stays at the 2,000 AVAX floor until Granite, when it rises to 14,655 AVAX. The stake-weighted median falls from 7.0 to about 4 weeks, so large validators shortened too, but less.

## How it was built

- **Measure.** A [commitment](/Phase-II/Wiki/Reference/Glossary-and-Notation) is one validator staking transaction's period. Its upgrade period is the one in force when the transaction was accepted, with all Apricot phases as one. "At the minimum" is a duration under 16 days, which holds the 14-day minimum and the start delays of up to two days observed before Durango. Committed AVAX-days sum self-stake times duration, so they measure capital over time, not stake held at one moment.
- **Data.** Run `staking-periods-2026-09-22` of `derived.staking-periods`, described in [Data](/Phase-II/Wiki/Reference/Data). Commitments begun after Helicon are left out, because Helicon had been active for 80 minutes when the data was captured.
- **Code.** `scripts/figures/commitments_by_upgrade.py` in the repository writes this table and chart. The [validator rewards notebook](/Phase-II/Wiki/Reference/Notebooks) shows the same table interactively.

## What is open

1. What changed at Durango that moved most new commitments to the minimum. Durango changed how a staking period starts, and whether that alone explains the jump is not yet tested.
2. Granite's rise in median self-stake to 14,655 AVAX, and whether it comes from a few operators or many.
3. What Helicon's 48-hour minimum does to both lines. The first full comparison runs after 2026-09-29.
