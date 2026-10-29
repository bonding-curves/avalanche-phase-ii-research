---
title: "30 October research discussion"
description: "Meeting brief: the post-Helicon record, the model and Milestone 2 findings, Workshop 1 and the Milestone 3 plan."
date: 2026-10-30
status: draft
kind: brief
reader: "Avalanche Foundation and Ava Labs meeting participants"
question: "What should the Foundation and BCRG discuss and decide at the 30 October research meeting?"
---

Date: 30 October 2026\
To: Avalanche Foundation and Ava Labs\
From: Bonding Curve Research Group\
Subject: Reward-design research and the next evaluation priorities

Avalanche's reward-design research can now connect proposed rules to explicit estimates of issuance and validator participation. The discussion brings the post-Helicon record together with the modeling system and its first comparisons. The decisions concern which outcomes matter most, what evidence is needed next and how to organize the workshops.

The [methodology memo](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/methodology) explains the system. The [Sensitivity Analysis Report](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results) develops the results and their conditions.

## 1. The post-Helicon record shows more stake on fewer validators

Validator own stake closed 26 October at 170.26 million AVAX, 4.27 million above its Helicon-day close, while the active validator count fell from 606 to 590. Stake and validator count therefore tell different stories about participation.

Commitments shorter than seven days made about 26%–27% of weekly new validator commitments during 6–26 October. Across commitments started since Helicon, they held only 0.33% of AVAX-days, where one AVAX-day is one AVAX staked for one day. Their frequency alone overstates their importance to committed capital.

Renewal within fourteen days was 86.2% for 320 nodes ending between Helicon and 12 October, compared with 85.6% of 1,235 endings in the preceding 90 days, using the same fourteen-day follow-up. These descriptive observations do not isolate the upgrade's effect. The model uses a separate seven-day renewal definition. [Data and definitions](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence#post-helicon-observations).

## 2. The model compares reward rules on issuance and stake

Each reward design runs beside the historical chain rule under the same conditions and random draws. The heatmap summarizes four designs across the five working goals. The ramp scores better on issuance, while the alternatives score better on participation. The combined score expresses their balance under BCRG's working weights.

![Mean utilities for four reward designs across five goals and the combined score.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/mechanism-utilities.png)
*Figure 1. Run-weighted mean utilities at one year across 16,384 design runs. Outside yields and behavioural responses are pooled. Combined weights are equal for the first four goals and half for duration. Scores reflect working preferences and do not establish a recommended mechanism. [Mechanisms, KPIs and experiments](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/methodology#7-experiments-turn-trajectories-into-design-comparisons).*

## 3. Workshop 1 should settle the evaluation criteria

The proposed 13 November workshop will review the system, its results and the criteria for subsequent recommendations. The Foundation should select the objectives and participation safeguards, then the thresholds and preference weights.

**Q1.** Which measures should lead: inflation on which supply base, use of the remaining issuance budget and stake-weighted duration? Which participation measures should act as safeguards?

**Q2.** Can we confirm the 13 November workshop, its participants and a 60-minute format?

## 4. Milestone 3 should evaluate the next mechanism against those criteria

The proposed sequence develops recommendations and a scenario playbook during 1–11 December and 4–15 January, with Workshop 2 proposed for 8 January and final delivery targeted for 15 January 2027. These are working targets to confirm.

Revenue-funded rewards are a useful next mechanism because they directly address the transition from issuance to protocol revenue. Their evaluation needs an explicit funding source and a rule for revenue shortfalls.

**Q3.** Should revenue-funded rewards be the next mechanism evaluated? If so, the preparation will specify the revenue stream, the shortfall rule and a Foundation reviewer. The delivery schedule and the person running the model also need confirmation.
