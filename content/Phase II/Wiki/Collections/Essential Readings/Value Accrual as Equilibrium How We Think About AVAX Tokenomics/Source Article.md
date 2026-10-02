---
title: "Source Article"
source_title: "Value Accrual as Equilibrium: How We Think About AVAX Tokenomics"
description: "Faithful local reproduction of the canonical LinkedIn article."
date: 2026-03-19
author: "Siyu (Eric) Lu, PhD"
canonical_url: "https://www.linkedin.com/pulse/value-accrual-equilibrium-how-we-think-avax-siyu-eric-lu-phd-pokvc"
source_id: "lit:eric-equilibrium"
source_type: article
source_record: "source.json"
build_receipt: "receipts/build.json"
capture_sha256: "66e19b5802e274e43f2610d8175e1473a182777ea977c1d3dfd35354e5fa0988"
topics: [Avalanche, tokenomics, value accrual, staking, equilibrium]
---

**Article** · Siyu (Eric) Lu, PhD · Published March 19, 2026 · [Original article on LinkedIn](https://www.linkedin.com/pulse/value-accrual-equilibrium-how-we-think-avax-siyu-eric-lu-phd-pokvc)

![Value Accrual as Equilibrium: How We Think About AVAX Tokenomics](/Phase-II/Wiki/Collections/Essential-Readings/Value-Accrual-as-Equilibrium-How-We-Think-About-AVAX-Tokenomics/raw/assets/cover.jpg)

At the Avalanche Foundation, we view value accrual not as a *narrative*, but as an equilibrium outcome of basic economic forces.

Many cryptoassets such as AVAX have two critical aspects at the same time:

- They are **money-like**: holding liquid, tradable tokens generates a transaction convenience flow.
- And they are **asset-like**: locking tokens earns a revenue stream in the form of staking rewards, and entitles stakers to voting rights.

The Cong, et al. 2025 paper ([https://www.nber.org/papers/w33640](https://www.nber.org/papers/w33640)) provides a useful lens for evaluating policy and design changes that affect AVAX value accrual. The key takeaway is to not value those aspects separately. They must be evaluated in a general-equilibrium framework that ties transaction convenience, staking rewards, and platform adoption dynamics together in one system.

This is exactly the framework we need for Avalanche, where AVAX functions as the stake asset securing consensus and the unit supporting onchain activity across C-Chain and the L1 ecosystems.

---

## Beyond the Supply vs. Demand Divide

A lot of tokenomics debates split into camps: *"supply-side people"* vs. *"demand-side people."*

While it might be sensible to focus on one side over the other in early stages, we cannot evolve into a truly sustainable ecosystem without bringing the two sides together as the ecosystem matures. This framework forces us to do exactly that.

For AVAX tokenomics, this maps cleanly to how we think about value accrual:

- **Supply-side levers**: issuance policy, and how burn/buyback-type mechanics affect the realized supply path.
- **Demand-side drivers**: productivity and value created by C-Chain apps and Avalanche L1s form the backbone of demand for AVAX.

The key point isn't "pick supply" or "pick demand." It's that policies often move both, sometimes in opposite directions.

For example: higher staking rewards improve security and finality, which drives up demand. But they also impose a higher inflation tax (emissions that dilute the value of all token holders is like imposing a tax on them) on all token holders, which drives down demand. Equilibrium is where you see what you actually bought.

---

## Staking as a Portfolio Choice, Not a Feature

Crypto discourse often treats staking APR-like numbers as a "feature."

This model forces the rational framing: staking is a portfolio choice trading off staking rewards against a loss of transaction convenience. This fits well into the Avalanche context because staking explicitly locks the token.

More staking can strengthen security and commitment, but it can also tighten aggregate liquidity, which affects user experience.

This is even more relevant when staking rewards are funded entirely through an inflation tax on all token holders. Incentive design is a careful balancing act that must lead to net value accrual, otherwise it can create forces that ultimately neutralize each other.

---

## Reward Rates Are Endogenous

One of the paper's most important insights: reward rates are endogenous in equilibrium, not a dial you set and forget.

Has there ever been a central bank that kept interest rates stable across economic cycles? No. So why should blockchains be any different?This helps us see through the "APR = value" narratives.

The right questions are:

- what equilibrium aggregate staking does a policy produce?
- What does that do to transaction convenience and adoption?
- And what distributional effects does it create across users vs. stakers?

---

## Emissions as Redistribution, Not Free Yield

Emissions-funded staking rewards behave like an inflation tax.

The paper highlights that emissions can redistribute wealth from transaction-focused users to investment-focused participants such as node operators, whales, and institutions.

Issuance is not "free yield." It is a redistribution tool with real incidence:

- **Who bears the cost**: all token holders pay the inflation tax pro-rata to finance staking rewards.
- **Who receives the revenue**: transaction fees in Avalanche are all burned, meaning all token holders receive the revenue pro-rata, yet validators are the ones doing the work to secure the chain.

Treating emissions as political economy, not marketing, is part of responsible tokenomics.

---

## Valuation with Conceptual Clarity

The paper cleanly separates money-like aspects (transaction convenience, adoption) from asset-like aspects (staking rewards), and shows how both are pinned down in equilibrium.

This is why we like this framework as a baseline lens: it forces us to articulate which channel any mechanism is actually operating through, instead of collapsing everything into a single term called "narrative."

---

## Adapt to Avalanche-specific Problems

This paper provides a strong backbone framework, but two challenges must be addressed before prescribing actionable policy recommendations:

1. **Reduced-form network fundamental value**: The model assumes network productivity is driven by a single aggregate state variable. There is no micro-foundation for other channels through which fundamental values can be improved, making it hard to apply directly to individual governance parameters or specific governance mechanisms. However, the model is reasonably flexible in accommodating a richer productivity process.
1. **Fee distribution**: The baseline assumption is that transaction fees flow to validators at least partially. For AVAX, all fees are burned. So the feedback loop between more validation, more adoption, and more rewards is structured differently for AVAX, since transaction fees are burned rather than distributed to validators. However, the model can be easily adapted for AVAX-specific mechanisms.

The first challenge is arguably the most important to overcome, because all policies and programs aiming to drive demand for AVAX can be wrapped into this fundamental value process.

---

## The Road Ahead

For us, the biggest value of this paper isn't that it "answers" what the best tokenomics looks like for AVAX. It's that it gives us a coherent and systematic approach to the problem: a small set of primitives, token supply dynamics, network fundamental value and productivity, and the aggregate staking ratio, jointly determine all the outcomes we actually care about: liquidity conditions, security level, adoption, and ultimately network value dynamics.

Once you adopt that map, tokenomics debates stop being debates about slogans ("more staking is good," "burn is good," "APR is good") and become more constructive debates about trade-offs:

- How does a policy change alter the wedge between "being liquid" vs. "being staked"?
- How does it shift the incidence of the inflation tax or fee burn across users vs. holders vs. validators?
- And most importantly: does it *actually* improve network fundamental value in a way that scales with ecosystem growth across C-Chain apps and Avalanche L1s, and does that improvement accrue to and through AVAX?

That last question is the real "value accrual" question for Avalanche. It's not whether the ecosystem creates value (it does, a lot). It's how the mechanisms route that value through AVAX in a way that is sustainable, incentive-compatible, and robust to governance, market structure, and market condition realities.

Thank you for reading, and I look forward to sharing more insights and thoughts moving forward.

I encourage discussion and feedback in the comments.
