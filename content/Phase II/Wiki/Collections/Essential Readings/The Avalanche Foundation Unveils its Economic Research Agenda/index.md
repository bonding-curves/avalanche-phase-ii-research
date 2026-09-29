---
title: "The Avalanche Foundation Unveils its Economic Research Agenda"
description: "The Foundation's research agenda orders its economics work as measure, capture, distribute, and places the funding of validator security second in that sequence."
---

Read the [source](/Phase-II/Wiki/Collections/Essential-Readings/The-Avalanche-Foundation-Unveils-its-Economic-Research-Agenda/Source-Article).

![Measure, capture, distribute](/Phase-II/Wiki/Collections/Essential-Readings/The-Avalanche-Foundation-Unveils-its-Economic-Research-Agenda/raw/assets/measure-capture-distribute.png)

*The agenda's three phases. Measure asks how much value the ecosystem creates and channels, capture asks how much of it accrues to AVAX, and distribute asks how captured value returns to the token and the ecosystem.*

## Question

The Avalanche Foundation published its economic research agenda on July 30, 2026. It names one organizing problem, in Matias Antonio's words: "The connection between ecosystem output and AVAX value accrual is the central problem we are working on." The agenda sets out which research will close that gap and in what order.

## Argument

Value created by applications and users does not accrue to the token unless the protocol has a mechanism to capture it. Measurement comes first because "a protocol cannot design a capture mechanism for value it has not properly identified." Capture comes second and distribution third.

The central hypothesis is that growth in **gross chain product**, GCP, the value added produced on-chain, "is the backbone that generates capturable protocol value in the form of surplus and income." Routed to AVAX, that value supports validator incentives and security, and security attracts the activity that grows GCP. The agenda calls security "a cost paid continuously." **Gross chain income**, GCI, extends GCP to income that originates off-chain and flows to Avalanche residents.

The section on research streams assigns the work to three streams:

1. Tokenomics and protocol revenue capture. Protocol revenue is today "predominantly transaction fees from the Primary Network," and the stream asks how to expand it through fees, MEV, and application and L1 revenue sharing without damaging the activity that creates it.
2. Validator economics and long-term staking incentives. Security is "funded primarily through emissions," and "as the supply budget is drawn down, fee revenue will need to take its place."
3. Ecosystem capital allocation. Captured value is distributed through burns, validator-directed revenue, and other mechanisms.

## Main results

The agenda reports no measurements. It states an objective, a sequence, and a hypothesis. Its two statements about the present are the ones quoted above: revenue is mostly Primary Network fees, and security is paid mostly from emissions.

## What it gives this research

The Phase II staking model sits in the second stream. The agenda gives it an objective and names the mechanisms it must be able to compare.

1. An objective for deliverables [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/) and [3.1](/Phase-II/Milestones/Milestone-3/3-1-Parameter-Recommendation-Report/). The second stream asks how security is paid for as issuance declines. Each trajectory should therefore report the path of the issuance budget, the supply remaining to the 720,000,000 AVAX cap, beside the staking ratio and net inflation. A recommendation can then state how fast it spends that budget.
2. Candidate mechanisms for deliverable [2.8](/Phase-II/Milestones/Milestone-2/2-8-Collaborative-Mechanism-Design/). Validator-directed revenue and burns are the distribution routes the agenda names. A reward interface that accepts a share of fee revenue as an input covers the transition from emissions to fees that the second stream describes.
3. An order for the recommendations in [3.1](/Phase-II/Milestones/Milestone-3/3-1-Parameter-Recommendation-Report/). Each recommendation can be placed by the step it serves and the measured quantity it moves.

## Limits and open questions

The agenda states the loop from AVAX value to security to activity as a hypothesis and does not test it. Until a source supports that return path, the staking model keeps price and activity as external inputs rather than outputs of staking.

The agenda gives no measure of security adequacy. The research needs one before deliverable [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/) can mark a region of parameters as under-funding security. Candidates are the stake-weighted cost of acquiring a controlling share, the validator count, and the share of stake that could leave within a day. Which of these the Foundation wants as the constraint is a question for the Foundation.
