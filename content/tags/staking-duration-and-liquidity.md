---
title: "Topic: staking duration and liquidity"
description: "How long stake is committed, what locking costs, and the option to exit."
---

How long stake is committed, what locking costs, and the option to exit.

22 pages are filed under this topic. See [all topics](/tags/).

## Deliverables

| Page | Authors | Date | Summary |
| --- | --- | --- | --- |
| [1.1 Data Ingestion](/Phase-II/Milestones/Milestone-1/1-1-Data-Ingestion/) | BCRG |  | The historical staking data the research runs on: validator and delegator flows, rewards, and durations, each from a checked run. |
| [1.2 Data Manifest](/Phase-II/Milestones/Milestone-1/1-2-Data-Manifest/) | BCRG |  | Where every dataset comes from, how it is transformed, and how its quality is checked, so any number traces to its run. |
| [1.3 Staking Model Spec](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/) | BCRG |  | The specification of a simplified model of the staking subsystem, with behavioral state variables. |
| [1.4 Behavioral Calibration](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/) | BCRG |  | Fitted response functions for staking, unstaking, and restaking, with confidence intervals. |

## Memos

| Page | Authors | Date | Summary |
| --- | --- | --- | --- |
| [2026-10-01-avalanche-summit-follow-up](/Phase-II/Wiki/Memos/drafts/2026-10-01-avalanche-summit-follow-up/) | BCRG | October 1, 2026 | What the Avalanche Summit's stage sessions imply for staking: security that issuance cannot fund for ever, a steeper duration curve, and ETFs that need part of their AVAX liquid within 48 hours. |
| [2026-10-01-benqi-interview](/Phase-II/Wiki/Memos/drafts/2026-10-01-benqi-interview/) | BCRG | October 1, 2026 | BENQI's interview checked against the chain: its address made 93% of all delegations, holds about half of delegated stake, never delegates longer than 17 days, and since 2026 places most of it on validators that pay BENQI. |
| [2026-10-01-duration-dependent-minimum](/Phase-II/Wiki/Memos/drafts/2026-10-01-duration-dependent-minimum/) | BCRG | October 1, 2026 | A minimum validator stake that falls with committed duration can hold 2,000 AVAX for 14 days of capital at every duration, keep today's two-week validators, and still lower the one-year minimum to 500 AVAX. The settings drafted so far do not. |
| [2026-10-01-helicon-first-days](/Phase-II/Wiki/Memos/drafts/2026-10-01-helicon-first-days/) | BCRG | October 1, 2026 | In Helicon's first eight days, 13 of 105 new validator commitments chose under 7 days, against none of 401 in the 30 days before. They hold 1.25% of the new stake. Every auto-renewed 48-hour commitment has renewed. |
| [2026-09-29-validator-minimums](/Phase-II/Wiki/Memos/drafts/2026-09-29-validator-minimums/) | BCRG | September 29, 2026 | Since Durango, 62% to 69% of new validator commitments last the 14-day minimum, yet they hold 3% to 11% of committed AVAX-days. By upgrade period, from one pinned run. |

## Briefs

| Page | Authors | Date | Summary |
| --- | --- | --- | --- |
| [2026-09-25-sprint-8](/Phase-II/Wiki/Briefs/2026-09-25-sprint-8/) | BCRG | September 25, 2026 | The brief submitted to the Avalanche Foundation in Notion for the call of 2026-09-25, as sent. |

## Reference

| Page | Authors | Date | Summary |
| --- | --- | --- | --- |
| [Data](/Phase-II/Wiki/Reference/Data) | BCRG |  | The sources behind the research, how each dataset is captured, built, and checked, and how to load the published data release. |
| [Glossary and Notation](/Phase-II/Wiki/Reference/Glossary-and-Notation) | BCRG |  | The terms, symbols, units, and network upgrades used across the notebooks, datasets, and milestone pages of this research, each defined once. |
| [Notebooks](/Phase-II/Wiki/Reference/Notebooks) | BCRG |  | What the two research notebooks answer and show, which datasets they read, and how to run them. |

## Interviews

| Page | Authors | Date | Summary |
| --- | --- | --- | --- |
| [BENQI, 2026-08-31](/Phase-II/Interviews/BENQI-2026-08-31/) | BCRG |  | Interview with Hansen of BENQI about how BENQI places and times its liquid staking delegations. |

## Essential Readings

| Page | Authors | Date | Summary |
| --- | --- | --- | --- |
| [How Do Avalanche Validators Actually Think About Staking Rewards?](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/) | Siyu (Eric) Lu | April 28, 2026 | Eric Lu estimates from 278 weeks of P-Chain data that Avalanche validators choose commitments by annualized yield, so lowering the minimum consumption rate, not shortening the minimum commitment, is the lever that lengthens them. |
| [From Static Constants to Dynamic Variables: Where Avalanche's Economics Are Headed](/Phase-II/Wiki/Collections/Essential-Readings/From-Static-Constants-to-Dynamic-Variables-Where-Avalanches-Economics-Are-Headed/) | Matias Antonio | July 2, 2026 | Matias Antonio argues that Avalanche is starting to treat its reward curve and fee floor as variables to adjust on purpose, and reads ACP-273, ACP-285, and ACP-283 as the first three steps. |
| [ACP 285 - Avalanche Community Call - Staking Reward Curve Adjustment](/Phase-II/Wiki/Collections/Essential-Readings/ACP-285-Avalanche-Community-Call-Staking-Reward-Curve-Adjustment/) | Avalanche | July 7, 2026 | At the ACP-285 community call, Eric Lu presents the lower minimum consumption rate as a response to shorter and auto-renewed commitments, separates its mechanical effect from the behavioral response, and hears concerns on security, concentration, and delegation. |

## Economic ACPs

| Page | Authors | Date | Summary |
| --- | --- | --- | --- |
| [ACP-236 Auto-Renewed Staking](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-236-Auto-Renewed-Staking/) | Razvan Angheluta | November 11, 2025 | ACP-236 lets a Primary Network validator stake in repeated cycles that renew automatically and restake a chosen share of each cycle's reward. |
| [ACP-273 Minimum Validator Duration](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-273-Minimum-Validator-Duration/) | Eric Lu et al. | February 17, 2026 | ACP-273 lowers the Mainnet minimum validator duration from 14 days to 48 hours, leaving the delegator minimum at 14 days. |
| [ACP-285 Minimum Consumption Rate](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-285-Minimum-Consumption-Rate/) | Matias Antonio et al. | June 8, 2026 | ACP-285 lowers the Primary Network minimum consumption rate from 10% to 7.5% over a 90-day ramp keyed to each stake's start time. |

## Research papers

| Page | Authors | Date | Summary |
| --- | --- | --- | --- |
| [Conditional Logit Analysis of Qualitative Choice Behavior](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/1973-Conditional-Logit-Analysis) | Daniel McFadden | 1973 | McFadden derives the conditional logit from a population of utility maximizers with random tastes and shows how to estimate it, the model the Foundation uses for a validator's choice of duration and delegation fee. |
| [Optimal Replacement of GMC Bus Engines: An Empirical Model of Harold Zurcher](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/1987-Optimal-Replacement-of-Bus-Engines) | John Rust | September 1987 | Rust estimates a forward-looking keep-or-replace decision from one manager's records with a nested fixed point algorithm, the model form for a validator deciding at the end of each commitment whether to renew or exit. |
