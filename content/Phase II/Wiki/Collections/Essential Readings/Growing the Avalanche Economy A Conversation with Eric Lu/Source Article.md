---
title: "Source Article"
source_title: "Growing the Avalanche Economy: A Conversation with Eric Lu"
description: "Faithful local reproduction of the Team1 interview with Eric Lu."
date: 2026-08-17
author: "Avalanche Team1 and BKL1023, with Siyu (Eric) Lu"
source_id: "lit:team1-eric-interview"
source_type: article
canonical_url: "https://www.team1.blog/p/growing-the-avalanche-economy-a-conversation"
captured_at: "2026-09-21"
status: source-reproduced
---

**Interview** · Avalanche Team1 and BKL1023, with Siyu (Eric) Lu, Lead Economist, Avalanche Foundation · Published August 17, 2026 · [Original on the Team1 blog](https://www.team1.blog/p/growing-the-avalanche-economy-a-conversation)

*Captured from the Team1 blog on 2026-09-21. The blog's subscription prompts and a Summit ticket advertisement are omitted. The text is otherwise as published.*

*Eric Lu discusses measuring Avalanche’s onchain value, strengthening AVAX value accrual, and building sustainable validator economics.*

![Growing the Avalanche Economy: A Conversation with Eric Lu](/Phase-II/Wiki/Collections/Essential-Readings/Growing-the-Avalanche-Economy-A-Conversation-with-Eric-Lu/raw/assets/cover.png)

Blockchains talk about value all the time, but few measure it, and the Avalanche Foundation (Foundation) is doing blockchain’s hardest math in public.

***[Economics of Blockchain](https://www.avax.network/about/blog/the-avalanche-foundation-unveils-its-economic-research-agenda)*** is the Foundation’s ongoing research series, and the premise behind it is simple. Strengthening an economy starts with seeing it clearly. To do this, the research team led with measurement, building tools to track what the Avalanche ecosystem produces, then asking how to route that value back to the token that secures the network.

The agenda runs on three steps: measure the value the ecosystem creates, capture part of it at the protocol level, and route it to AVAX and the Avalanche ecosystem. The sequence is relatively easy to talk about but much harder to deliver.

Each step anchors on a problem nobody in crypto has solved, and the Foundation is upfront about which one matters most today. The gap between ecosystem activity and AVAX is the weak link, and closing it is the point of the whole agenda.

Much of this work sits with **[Eric Lu](https://x.com/eric_lu_sc)**, the Foundation’s Lead Economist. Two pieces of the measurement puzzle he is working on are [Gross Chain Product](https://www.avax.network/about/blog/measuring-blockchain-economies-introducing-gross-chain-product) (GCP) and [Gross Chain Income](https://www.avax.network/about/blog/from-gross-chain-product-to-gross-chain-income-where-the-value-goes) (GCI) - a way to size an onchain economy using the same accounting logic that governments use for GDP (Gross Domestic Product) and GNI (Gross National Income).

Where GCP measures what the ecosystem produces, GCI measures what it earns, including income that originates outside the onchain economy but flows to people and balances inside it. He ran GCP against the Avalanche C-Chain from January 2025 through March 2026, and together the two metrics turn a vague question - how much is this ecosystem worth - into auditable numbers published openly. Every other piece of the agenda builds on that measurement.

We asked Eric the questions the community keeps raising, ranging from what the series is to the one on everybody’s mind: how does value accrue back to AVAX and the ecosystem?

His answers follow:

---

## Why Publish This in Public
**For someone seeing a piece in the “Economics of Blockchain” series for the first time, what problem does this series exist to solve, and why does the Foundation think it’s worth doing the research in public rather than internally?**

The series is closely related to the work from the Economic Research and Ecosystem team at the Foundation. It will be the main outlet for the research projects. So you can expect to see articles in the series on topics and questions laid out in our [research roadmap](https://www.avax.network/about/blog/the-avalanche-foundation-unveils-its-economic-research-agenda), which has been published recently as well.

As you may have seen, the first couple of articles are about measuring how much value there is in the ecosystem, and where it is. In the next couple of months, you can expect to see articles around how we will capture these values for the protocol to ensure alignment between network security and ecosystem growth.

## The Logic of Measure, Capture, Distribute
**The agenda is built around a framework of Measure, Capture, Distribute. Can you walk through why measurement has to come first, and what the industry gets wrong when it skips straight to incentives and TVL?**

In my view, Measure, Capture, Distribute is really a first-principle type of thinking: we cannot capture anything until we know how much value there is and where it is; and we cannot distribute any value if we haven’t already captured any value. So you can see the whole thing starts with measurement. I also wouldn’t say this is something that the industry gets wrong. It’s more about having the right measurement to support the actions we need to take. Metrics like TVL, active accounts, transaction counts, etc., all serve some kind of purpose. But here, since we are trying to improve the value accrual issues for the protocol, we need more informative measures, and this is where GCP and GCI come in.

## Sizing the Economy: Gross Chain Product
**Gross Chain Product (GCP) borrows from national GDP accounting. In plain terms, what does GCP show you about Avalanche’s economy that existing metrics miss, and has anything in the January 2025 to March 2026 data surprised you?**

The whole GCP framework has at least three important improvements over the existing metrics: 1) it measures the economic value creation on the blockchain, which is a natural base for potential value capture, 2) it is applicable across pretty much any verticals, as long as you want to measure the onchain value creation, and 3) it allows you to disentangle the changes in real activities from the changes just due to price changes, which is particularly informative given the high level of fluctuation in crypto market.

## Beyond Production: Gross Chain Income
**GCP measures production, but you’re also working on Gross Chain Income (GCI). What does GCI capture that GCP doesn’t, and why do you need both to get a complete picture of the ecosystem’s value?**

You are exactly right: GCP measures production, but that also hints at its limitations, because not all value in an economy exists in its productive output. GCI is a natural extension of GCP that fills this gap. Just like an open economy, some value in the Avalanche ecosystem originates from outside. Think of it like a multinational corporation that generates profit abroad and repatriates it to its home country. An obvious example of value that is included in GCI but not GCP is the yield generated by assets backing Real World Assets (RWAs) or stablecoins on Avalanche. This yield accrues to on-chain users or token issuers, both of which are integral parts of the ecosystem. GCI complements GCP by clarifying the sources and scale of the value base, further informing how we capture that value.

## Closing the Gap Between Activity and AVAX
**The Economics of Blockchain research agenda names the connection between ecosystem value and AVAX as the most important gap today. How do you think about closing it, and what would “value reaching AVAX” concretely look like a year or two from now?**

This is really a core problem that the Foundation and my team are trying to address. Conceptually, we would close the gap via two actions talked about extensively in the research agenda: Capture and Distribute. Capture gives us the value that can possibly be connected to AVAX, and Distribute establishes the ownership of the value stream at the protocol level by AVAX holders. There is a lot of work to be done here to figure out how to effectively take out the two actions, and most of it has no working precedents.

To name a few fundamental challenges: for Capture, most of the general-purpose Layer 1s (L1s) like Avalanche heavily rely on transaction fees for protocol revenue; some add Maximal Extractable Value (MEV) profit and stablecoin yield. I would argue that all these common capture mechanisms do not provide sufficient exposure for the protocol to ecosystem value. So we need to explore alternative revenue sources and capture mechanisms with better alignment with ecosystem growth. This is also where the GCP/GCI framework comes in.

For Distribute, most of the chains rely on either direct burn or buyback and burn to distribute protocol revenue. However, even basic corporate finance theory would tell us that direct distribution is not the value-maximizing distribution policy in many circumstances, even though direct distribution might have the lowest agency cost. It remains to be studied what the optimal distribution policy is that strikes a good balance between value maximizing through all kinds of productive activities and agency cost minimization through direct distribution.

## Where Capture Actually Comes From
**Protocol revenue is mostly Primary Network fees right now, which you’ve called a narrow base. Which capture mechanisms (e.g., fees, MEV, L1 and app revenue sharing) look most promising, and how do you expand that base without taxing the activity that creates the value?**

I do want to emphasize that we are not overlooking any potential revenue base, including fees, MEV profit, L1 and app revenue, and corresponding capture mechanisms. One of the key tradeoffs we consider when we are prioritizing the research into these revenue sources is the magnitude and the feasibility of capture. So if a revenue source has a large scale and a feasible path to capture, it will be on our top priority list. For such a revenue source, the research work would mainly involve measuring the size of the source, designing the mechanism for sustainable capture, and assessing the impact on protocol revenue and ultimately network security.

You used the term “taxing” above, which is what value capture eventually achieves. But I do want to point out a key design principle we are trying to follow: we always explore voluntary value capture first, which we believe is mutually beneficial for the protocol and the source of revenue, and the only sustainable mechanism in the long term, in contrast to a real tax imposed by a sovereign state, which is almost always compulsory.

## Validator Economics After Issuance
**Today, validator rewards come mostly from new AVAX issuance, the fresh tokens the protocol mints as staking rewards, and that budget is finite. As it winds down, fees have to cover more of the security budget. What does that transition look like in practice, and what has to be true for validators to keep staking for the long term?**

The issue you point out about validator rewards is very well embedded in our research agenda. Specifically, a good distribution policy would need to allocate protocol revenue to validators. So eventually, validator rewards will be more and more funded by real protocol revenue instead of emissions.

Intuitively, the level of rewards needs to be higher than some kind of opportunity cost of staking for validators to validate. So we need to have an understanding of their opportunity cost, which is the supply side of validation. At the same time, validation is a public good with strong positive externalities, which means it is typically under-supplied in a competitive market. So we also need to have an understanding of the user and the “social” benefit from validation, or really the security provided by validation, which is the demand side of validation. If I had to really imagine, we would need a market mechanism to reveal the validators’ cost of validation and the network’s demand for validation, and then supplement it with some protocol-level subsidy to compensate for the externalities, to really have a long-term sustainable staking rewards mechanism.

## Distribution as a Design Choice
**Once value is captured, distribution is a design choice: burns, validator-directed revenue, other routes. How are you weighing those options, and how should AVAX holders track whether this is working over time?**

As I briefly touched on above, the distribution policy is ultimately a delicate balance of these different channels. Again, taking basic intuitions from corporate finance, when the industry is booming and there are a lot of high-potential projects, it might make sense to reinvest more and distribute less, whereas in a slow market, direct distribution may be demanded by the stakeholders to reduce wasteful investments. Just like a corporation needs to adjust its policy depending on all kinds of conditions, our protocol needs to. Our research agenda doesn’t really give a fixed prescription on how to do the best distribution policy, but rather provides an understanding of the different tradeoffs and forces, so we know how to make adjustments under different conditions to drive long-term network growth and security.

## Where Outside Researchers Fit In
**You opened a \$50,000 research grant program on Avalanche network economics. What approaches are you seeing researchers take, and are there any early insights you can share?**

It is too early to share any concrete insights at the moment, as we are still reviewing the proposals. Once the winners are selected, they still need to actually execute the proposals to reach any concrete findings and policy prescriptions. What I can share is that we received close to 200 submissions in total, and we have seen a lot of high-quality proposals.

In terms of research topics, we see about one-third in validator incentives and economics, where the research questions surround validators’ cost of capital, required return, and long-term sustainable incentives. Another third is around cryptoasset pricing, where the questions are mostly about how to incorporate the key different features of a cryptoasset into a unified equilibrium-based asset pricing model. The rest are scattered across multiple different topics such as emission policy, transaction fee optimization, L1 mechanisms, and MEV economics.

---

### Join the work
If you research economics, finance, computer science, or a related field, the Foundation is funding original work on Avalanche network economics through its research grant program, with up to \$50,000 available and applications reviewed on a rolling basis. You can read the criteria and apply [here](https://build.avax.network/grants/avalanche-research-proposals).

### Read the full series
***Economics of Blockchain*** is an ongoing body of work, and each piece builds on the last. If you want the complete picture behind this interview, start here:

* [The Avalanche Foundation Unveils its Economic Research Agenda](https://www.avax.network/about/blog/the-avalanche-foundation-unveils-its-economic-research-agenda)
* [From Gross Chain Product to Gross Chain Income: Where the Value Goes](https://www.avax.network/about/blog/from-gross-chain-product-to-gross-chain-income-where-the-value-goes)
* [Measuring Blockchain Economies: Introducing Gross Chain Product](https://www.avax.network/about/blog/measuring-blockchain-economies-introducing-gross-chain-product)
* [From Static Constants to Dynamic Variables: What Three ACPs Say About Where Avalanche’s Economics Are Headed](https://www.avax.network/about/blog/from-static-constants-to-dynamic-variables-what-three-acps-say-about-where-avalanches-economics-are-headed)
* [The Avalanche Foundation Opens Up to \$50,000 in Research Grants on Avalanche Network Economics](https://www.avax.network/about/blog/research-grants-avalanche-network-economics)
* [How Do Avalanche Validators Actually Think About Staking Rewards?](https://www.avax.network/about/blog/how-do-avalanche-validators-actually-think-about-staking-rewards)
* [Why Avalanche Validator Economics Need a Redesign](https://www.avax.network/about/blog/why-avalanche-validator-economics-need-a-redesign)
* [Value Accrual as Equilibrium: How We Think About AVAX Tokenomics](https://www.avax.network/about/blog/value-accrual-as-equilibrium)

---

### Who is Eric?
Siyu (Eric) Lu is a cryptoeconomist and data scientist with a PhD in Financial Economics, bringing over a decade of experience across traditional finance and digital assets. His expertise spans quantitative modeling, machine learning, tokenomics, and large-scale data systems.

At the Avalanche Foundation, Eric works closely with Matias A., and the ecosystem team on research across protocol design, including liquidity dynamics, staking economics, and token models - helping to support data-driven, sustainable growth across Avalanche.

Previously, Eric served as a Cryptoeconomist and Senior Data Scientist at TRM Labs, where he led the development of on-chain analytics and risk-scoring models for regulators and institutions, and as a Financial Economist at Cornerstone Research.
