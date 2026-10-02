---
title: "Summoning the Money God: Applying Control Theory to Cryptocurrency Monetary Policy"
description: "Zargham, Bernardineli, Clark, Shorish, and Emmett show how the feedback controller behind the RAI stablecoin was chosen by simulation before launch, and conclude that a proportional controller was the simplest and safest choice."
authors: ["Michael Zargham", "Danilo Lessa Bernardineli", "Andrew Clark", "Jamsheed Shorish", "Jeff Emmett"]
published: 2021-04-09
venue: "BlockScience technical article"
url: "https://doi.org/10.5281/zenodo.10474385"
full_text: "/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2021-Control-Theory-for-Monetary-Policy/Source-Paper"
tags: ["mechanism-design", "parameter-selection-under-uncertainty", "protocol-governance"]
key_terms: ["feedback controller", "PID controller", "redemption rate", "governance surface", "windup", "leak", "steady-state error"]
deliverables: ["2.1", "2.2", "2.3", "2.6", "2.8"]
---

Zargham, Bernardineli, Clark, Shorish, and Emmett show how BlockScience chose the feedback controller that sets the RAI stablecoin's redemption rate, by testing candidate controllers in simulation against an attack, a slow drift, and a price shock before launch, and conclude that a proportional controller was the simplest and safest choice.

<!-- overview-table:start -->

| | |
| --- | --- |
| **Authors** | Michael Zargham, Danilo Lessa Bernardineli, Andrew Clark, Jamsheed Shorish, Jeff Emmett |
| **Published** | April 9, 2021 |
| **Source** | BlockScience technical article, [original](https://doi.org/10.5281/zenodo.10474385), [full text](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2021-Control-Theory-for-Monetary-Policy/Source-Paper) |
| **Topics** | [mechanism design](/tags/mechanism-design), [parameter selection under uncertainty](/tags/parameter-selection-under-uncertainty), [protocol governance](/tags/protocol-governance) |
| **Key terms** | feedback controller, PID controller, redemption rate, governance surface, windup, leak, steady-state error |
| **Serves deliverables** | [2.1](/Phase-II/Milestones/Milestone-2/2-1-PSUU-Infrastructure/), [2.2](/Phase-II/Milestones/Milestone-2/2-2-Simulation-Execution/), [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/), [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/), [2.8](/Phase-II/Milestones/Milestone-2/2-8-Collaborative-Mechanism-Design/) |

<!-- overview-table:end -->

The five authors, all at BlockScience, published the article on April 9, 2021. It records work done with Reflexer Labs to set RAI's parameters before its mainnet launch on February 17, 2021. **RAI** is a token backed by ETH that is not pegged to the dollar or any other asset. The authors call it a "dampened ETH," because a controller softens the price swings that ETH passes through to it.

A **feedback controller** measures the gap between a target and what is observed, and sets an action that closes the gap. The common form is the **PID controller**, which adds three terms. The **proportional** term, with gain $K_p$, reacts to the current gap. The **integral** term, with gain $K_i$, reacts to the gap accumulated over time. The **derivative** term reacts to how fast the gap is changing. In RAI the observed value is the market price, and the target is the **redemption price**, the price the system itself sets. The controller's action is the **redemption rate**, the rate at which the redemption price moves. The article calls the parameters that people must set and later change the **governance surface**, and argues that it should be kept small and explicit.

The authors set the derivative term to zero, because "in an economic setting, the D term could become an attack vector." An integral term can build up and bias the controller, a problem called **windup**. So they also test a **leak**, which lets part of the integral decay each period. That gives five candidates: a proportional controller alone, and a proportional-integral controller with positive or negative $K_i$, each with or without a leak. Simple models of the control logic run two tests. In the first, a **whale**, a holder of a large share of the supply, buys RAI to hold the market price fixed. In the second, the market price wanders at random, and the test measures the remaining **steady-state error**. A fuller cadCAD model adds the ETH-backed debt positions and the ETH-RAI Uniswap pool, and runs a check with the controller switched off, shock tests, and Monte Carlo runs.

Against the whale, the redemption price fell toward zero within two weeks in every case "except for the one with negative Ki AND no leak," where it rose without limit. In the random-price test, the hourly redemption rate moved by less than 5e-9, yet small biases in it compounded into large gaps in the redemption price. Integral terms without a leak made the redemption price drift away. A leaky integral term gave only small gains over the proportional controller, so its extra complexity "is not warranted" for now. After a sudden 30% drop in the ETH price two weeks in, the setting the paper gives as "Kp=2e-07 and 5e-09" ran away, while settings from the recommended ranges stayed stable. The authors recommend the proportional controller as "the simplest and safest configuration." An integral term may be added only with a leak, and only if $K_p > -K_i/(1-\alpha)$, where $\alpha$ is the leak parameter. RAI launched with the proportional term alone, after a small test release, ProtoRAI, in October 2020 with low debt caps.

![Figure 1 of the paper: RAI's redemption price under five controllers while a whale holds the market price fixed](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2021-Control-Theory-for-Monetary-Policy/_page_4_Figure_1.jpeg)

*Figure 1 of the paper: RAI's redemption price, in dollars, while a simulated whale holds the market price fixed. Each line is one controller. In four of them the redemption price falls toward zero within about two weeks, so the controller keeps pushing against the whale and the whale loses in the long run. In the fifth, a negative integral gain with no leak (green), the redemption price turns upward and passes 14 within two weeks. The authors rule that setting out on this test alone.*

## How it relates to our research

**It gives the first forms to try for a state-dependent reward.** The signed agreement lists state-dependent reward functions among the alternative forms that deliverable [2.8](/Phase-II/Milestones/Milestone-2/2-8-Collaborative-Mechanism-Design/) must be able to swap in for the current duration-based curve. The Foundation's [Static Constants article](/Phase-II/Wiki/Collections/Essential-Readings/From-Static-Constants-to-Dynamic-Variables-Where-Avalanches-Economics-Are-Headed/) argues that the right value of an economic parameter depends on network conditions that change. A rule that moves the **consumption rate**, the yield parameter in the reward formula, with the gap between the observed [staking ratio](/Phase-II/Wiki/Reference/Glossary-and-Notation) and a target is a feedback controller of the paper's kind. The paper sets the order in which to test forms: a proportional rule first, and a leaky integral term only within its stated bound. It also warns that each gain and each target joins the governance surface.

**Its tests become a test set for the sweeps.** In deliverables [2.1](/Phase-II/Milestones/Milestone-2/2-1-PSUU-Infrastructure/) to [2.3](/Phase-II/Milestones/Milestone-2/2-3-KPI-Computation/), each proposed rule can be run against the same three stresses: a large holder that holds the measured state in place, a slow random drift, and a sudden price shock. A rule is kept only if it stays stable in all three. On Avalanche, BENQI told us that it holds 10% to 12% of all stake, in delegations of 14 to 18 days, so one actor can move the staking ratio a controller would read. As in the paper's check with the controller off, the current fixed reward rule is the baseline for every comparison. Settings that run away, like the paper's shock failure, belong on the risk map of deliverable [2.6](/Phase-II/Milestones/Milestone-2/2-6-Risk-Surface-Map/).

**Avalanche's feedback is slower and less direct.** RAI's controller sets an hourly rate from a price. On Avalanche the protocol fixes each commitment's **potential reward** when the commitment starts, from its stake, its duration, the consumption rate, and the supply counter. A change in the consumption rate therefore reaches only new commitments. Since Helicon, validator commitments run from 48 hours to one year and delegations from 14 days, so the delay between a change and its full effect can be as long as a year and depends on the mix of durations. Gains tuned for RAI do not transfer, and the delay has to be modeled. The current formula already responds to one state variable, the supply counter, through its **remaining-supply factor**, but it does not respond to the staking ratio. The paper's whale also follows a fixed plan. Avalanche validators choose when to commit and for how long, and a published rule is something they can plan around.

**It is the worked case for other pages in the collections.** The article applies the workflow of [How to Perform Parameter Selection Under Uncertainty](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2021-Parameter-Selection-Under-Uncertainty) to one system. The staking ratio and the reward rate form a loop in the [January staking and price model](/Phase-II/Wiki/Collections/Essential-Readings/January-Staking-and-Price-Model-A-Three-Image-Reconstruction/) and in [The Tokenomics of Staking](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2025-The-Tokenomics-of-Staking). Those models find where the loop settles. This paper tests whether a rule that drives it stays stable. [ACP-283](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-283-Dynamic-Minimum-Gas-Price/) shows the other way to make a parameter move, by stake-weighted validator preference rather than a formula.

**The paper's own limits.** Its tests are, in its words, "non-exhaustive examples." It reports charts rather than results across all settings, gives the stability bound without a derivation, and leaves the choice between the proportional and leaky proportional-integral controllers to further tuning and live data.

**Open questions for the Foundation.** Is a reward rule that adjusts itself from network state within scope for deliverable 2.8, or should parameters that move stay under governance vote, as with ACP-283? If a controller is in scope, what staking ratio, or other measure, should it target?

## Source

Michael Zargham, Danilo Lessa Bernardineli, Andrew Clark, Jamsheed Shorish, and Jeff Emmett. 2021. Summoning the Money God: Applying Control Theory to Cryptocurrency Monetary Policy. BlockScience technical article, April 9, 2021. Zenodo, DOI [10.5281/zenodo.10474385](https://doi.org/10.5281/zenodo.10474385). Licensed CC BY 4.0. Read the [full paper](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2021-Control-Theory-for-Monetary-Policy/Source-Paper), with all figures.
