# Avalanche staking research brief

*Draft for review.*

Date: 30 October 2026\
To: Avalanche Foundation and Ava Labs\
From: Bonding Curve Research Group (BCRG)\
Subject: Staking research and the next review

The model compares reward formulas on issuance and validator participation. The latest work combines the observed post-Helicon record, conditional simulation results and a runnable repository. The next review should settle how to judge the trade-offs and which evidence to strengthen.

The [modeling memo](modeling.md) explains the system. The [results memo](results.md) develops the findings.

## 1. Commitments increased after Helicon while active validators declined

Equal windows around Helicon contain 514 new commitments from 342 nodes after the upgrade, compared with 440 from 309 nodes before. Scheduled AVAX-days rise from 5.31 billion to 6.17 billion. These gross commitments include repeated capital and future days. Active stake gives a different view: own stake closed 26 October at 170.26 million AVAX, up 4.27 million since Helicon, while active validators fell from 606 to 590. [Data and definitions](evidence.md#post-helicon-observations).

Figures 1 and 2 show individual commitments and the distribution of their scheduled AVAX-days, where one AVAX-day is one AVAX committed for one day. Sub-seven-day periods account for 21.2% of post-upgrade commitments but only 0.33% of AVAX-days. These observations describe the record and do not isolate Helicon's effect.

![New validator commitments before and after Helicon, with duration, stake and AVAX-day histograms.](assets/content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/report-exports/helicon-scatter.png)
*Figure 1. Equal 34-day, 9-hour windows around 22 September 2026, 15:00 UTC, through 26 October. Each point is a commitment. Bubble area is proportional to the square root of scheduled AVAX-days. Both axes are logarithmic. Bars show each era's AVAX-day shares. These are gross commitments, including future days and potentially repeated capital, rather than net stake added. [Data and methods](evidence.md#post-helicon-observations).*

![AVAX-day weighted density before and after Helicon, on the same duration and stake axes.](assets/content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/report-exports/helicon-kde.png)
*Figure 2. The same commitments, weighted by scheduled AVAX-days. Kernel density estimation smooths their distribution using common bandwidths of 1.5 days and 0.12 log₁₀-AVAX. Density is normalized within each era. Smoothing below 14 days before Helicon and 2 days after is hidden. The plots describe the record and do not isolate Helicon's effect. [Density definition and source](evidence.md#post-helicon-observations).*

## 2. The model compares reward formulas on issuance and stake

At working responses, starting ACP-285's ramp early saves a median 12.8% of validator reward promises over one year while retaining 98.7% of the historical twin's own stake. The scenario advances adoption from September 2026 to November 2025 and simulates through 18 November 2026. The [50-pair comparison](evidence.md#central-case) is conditional on response assumptions and 5% outside yield.

Figure 3 summarizes four designs across five working goals. The [detailed setting comparison](results.md#25-sensitivity-analysis) scores highest at a minimum consumption rate from 6% to below 6.5%. Higher-rate bands pass the participation safeguards more often. A preferred average and a satisfactory minimum are different choices.

![Mean utilities for four reward designs across five goals and the combined score.](assets/content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/mechanism-utilities.png)
*Figure 3. Run-weighted mean utilities at one year across 16,384 design runs. Outside yields and behavioural responses are pooled. Combined weights are equal for the first four goals and half for duration. A high combined score does not guarantee that every goal passes. [Mechanisms, KPIs and experiments](modeling.md#7-experiments-turn-trajectories-into-design-comparisons).*

## 3. The workshop should settle the evaluation criteria

Figure 4 separates the Foundation's objectives from the measures, acceptance conditions and preference weights used to evaluate them. The current thresholds and weights are BCRG's exploratory choices.

![Objectives, KPIs, acceptance thresholds and preference weights as successive evaluation choices.](assets/content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/assets/evaluation-criteria.png)
*Figure 4. Proposed evaluation choices for Workshop 1. The existing results use BCRG's working thresholds and weights. The Foundation can select its own criteria. [Goals, measures and scoring](modeling.md#72-goals-guide-which-outcomes-the-experiments-measure).*

**Q1.** Which issuance and duration measures should lead, and which stake, count and concentration thresholds should act as safeguards?

## 4. Review the setup before choosing the next experiment

The [repository handoff](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/docs/handoff/README.md) has been shared with Eric. It includes setup, local wiki and gallery instructions, an included-input example and the central-result replay. Figure 5 updates the proposed sequence.

![Proposed work periods and workshops from 30 October 2026 through final delivery on 15 January 2027.](assets/content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/assets/proposed-schedule.png)
*Figure 5. The repository was shared on 30 October. Reading and comments target 2–6 November, with 27 November proposed for the workshop. December and January dates are planning targets. Meeting invitations and workshop attendance remain to confirm.*

The reading targets are polished links from Shawn on 2 November and comments integrated by 6 November. Eric and the Foundation team can review the setup and results beforehand. The moved review invitation and proposed 27 November workshop still need confirmation. Later dates in the figure remain planning targets.

**Q2.** Which mechanism should follow the review? Revenue-funded rewards are one candidate, requiring a named funding stream, a shortfall policy and a Foundation reviewer.
