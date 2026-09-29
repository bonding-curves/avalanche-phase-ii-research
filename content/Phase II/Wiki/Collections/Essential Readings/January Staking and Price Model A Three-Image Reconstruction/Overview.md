---
title: Overview
description: "Three January images attributed to Eric Lu describe a staking and price equilibrium in which the staking ratio and reward rate solve a fixed point, price clears the market, and a stochastic demand state moves both."
---

Read the [source](/Phase-II/Wiki/Collections/Essential-Readings/January-Staking-and-Price-Model-A-Three-Image-Reconstruction/Source-Model-Artifact).

![Equilibrium solution](/Phase-II/Wiki/Collections/Essential-Readings/January-Staking-and-Price-Model-A-Three-Image-Reconstruction/assets/02-equilibrium-solution.jpg)

*The second of the three images. First-order conditions give holdings and the staking ratio as functions of the reward rate and expected appreciation, a fixed point pins the equilibrium staking ratio and reward rate, and a market-clearing condition gives price.*

## Question

The artifact is three images of model work attributed to Eric Lu, recorded in a January 13 recap during the scoping of Phase II. The original deck and its date have not been recovered. The model asks how individual staking choices, the aggregate staking ratio, the reward rate, and the AVAX price determine one another, and how a demand shock moves them.

## Argument

The images state the model in three steps.

1. The holder's problem. Given aggregate states, a holder trades off "convenience utility from holding liquid tokens," the "convenience loss from locking tokens in staking," and staking rewards.
2. The equilibrium. First-order conditions give the holding $x_t$ and staking ratio $\theta_t$ as functions of the reward rate $r_t$ and expected appreciation $\mu_t$. With homogeneous holders, $\theta_t$ equals the aggregate ratio $\Theta_t$, which determines $r_t$. The equilibrium $\Theta_t^*$ and $r_t^*$ solve a fixed point. Price then clears the market:

$$P_t = \frac{S_t}{Q_t}\int_0^1 x^*_{i,t}\,di = \frac{(1-\Theta_t)S_tA_t}{Q_t^*}\left(\frac{1-\alpha}{r^f-\mu_t-\Gamma_t}\right)^{1/\alpha}.$$

3. The demand shock. A demand state follows $dS_t/S_t = \mu^S\,dt + \sigma^S\,dZ_t^S$, with drift and volatility that may depend on aggregate states.

## Main results

The images give structure, not numbers. The reconstruction's quantity map in section 5 lists what is missing: the utility function, the reward rule $R$ that maps $\Theta_t$ to $r_t$, and definitions and units for $S_t$, $Q_t$, $Q_t^*$, $A_t$, $r^f$, $\Gamma_t$, and $\alpha$. The distinction between $Q_t$ and $Q_t^*$ is visible in the image but not explained. The equations are transcribed visually and have not been checked against an original source.

## What it gives this research

1. A computational core for deliverable [1.3](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/). Section 3 writes the equilibrium as the root of $F(\Theta) = \theta^*\!\left(R(\Theta; z), \mu\right) - \Theta$ on $[0,1]$. This is a small function that can be tested on its own, reporting every admissible root, before any dynamics are added.
2. An environment process for deliverable [2.2](/Phase-II/Milestones/Milestone-2/2-2-Simulation-Execution/). The demand state $S_t$, discretized as geometric Brownian motion when its coefficients are constant over a step, is a candidate driver for the market conditions each trajectory samples.
3. A link to the published literature. The factor $(1-\Theta_t)A_t$ in the price equation matches the result of [Cong, He, and Tang](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/2025-The-Tokenomics-of-Staking) that price rises with the productivity of unstaked tokens. The images appear to specialize that model, which the [value accrual article](/Phase-II/Wiki/Collections/Essential-Readings/Value-Accrual-as-Equilibrium-How-We-Think-About-AVAX-Tokenomics/Overview) later adopts by name. This reading is ours and needs the author's confirmation.

## Limits and open questions

The model cannot be calibrated until its symbols are defined. The questions below are for the author.

1. Is there an original deck, note, or code, and what date and purpose did it serve?
2. What is $S_t$ empirically: total demand, a demand shifter, or expenditure? What distinguishes $Q_t$ from $Q_t^*$, and what are $A_t$, $\Gamma_t$, and $\alpha$?
3. Which reward rule $R$ was intended? On Avalanche the reward per commitment is fixed at its start by duration and remaining supply, so $r_t$ depends on $\Theta_t$ only through the supply counter unless the rule is changed.
4. Does the homogeneous-holder fixed point survive the split between validators and delegators, and the duration choice that the later [validator-rewards article](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/Overview) estimates?
5. How does this model relate to that later two-sided model? Is one meant to supply prices and the other staking choices?
