---
title: "From Gross Chain Product to Gross Chain Income: Where the Value Goes"
description: "A faithful local reading view of Eric Lu's GCP/GCI article, generated from the frozen official page."
date: 2026-08-12
author: "Siyu (Eric) Lu, PhD"
source_id: "lit:eric-gcp-gci"
source_type: article
canonical_url: "https://www.avax.network/about/blog/from-gross-chain-product-to-gross-chain-income-where-the-value-goes"
captured_at: "2026-09-13T10:22:40-07:00"
status: source-reproduced
---

# From Gross Chain Product to Gross Chain Income: Where the Value Goes

**Article** · Siyu (Eric) Lu, PhD · Published August 12, 2026 · [Original article](https://www.avax.network/about/blog/from-gross-chain-product-to-gross-chain-income-where-the-value-goes)

![GCP to GCI article cover](/Wiki/Avalanche/Essential%20Readings/From%20Gross%20Chain%20Product%20to%20Gross%20Chain%20Income%20Where%20the%20Value%20Goes/raw/assets/cover.png)

## A three-step roadmap for value accrual

The Avalanche Foundation's [economic research](https://www.avax.network/about/blog/the-avalanche-foundation-unveils-its-economic-research-agenda) follows a simple logic for improving the long-term value accrual and sustainability of AVAX and the ecosystem.

It has three steps: first, **measure** how much value the ecosystem creates and channels; second, work out how to **capture** a sustainable share of that value; third, decide how to **distribute** what is captured.

The steps are ordered on purpose. You cannot design a sound capture mechanism until you can measure what there is to capture, and you cannot distribute what you have not captured.

This article is about the first step, and about what it reveals for the second. Our earlier work introduced [Gross Chain Product (GCP)](https://www.avax.network/about/blog/measuring-blockchain-economies-introducing-gross-chain-product), a Gross Domestic Product (GDP) style measure of the value that Avalanche protocols produce on-chain. Gross Chain Income (GCI) is the natural extension of that framework. Where GCP measures production, GCI measures income, including income that originates outside the on-chain economy but flows to people and balances inside it. Both metrics live in the "measure" step. Seen together, they turn a vague question ("how much is the ecosystem worth?") into a set of concrete, near real-time, auditable numbers, and they make the capture question sharp: of all this value, how much actually accrues to AVAX today, and how much could?

---

## From GDP to GNI, from GCP to GCI

National accounting already solved a version of this problem. **GDP**measures the value added produced inside a country's borders. **Gross National Income** (GNI) starts from GDP and adds the net income that residents earn from the rest of the world: interest, dividends, and wages earned abroad but flowing home. A country can produce a modest amount within its borders yet receive a large stream of income from foreign assets its residents hold. GDP misses that income; GNI captures it.

Avalanche has the same distinction, and GCI is built to mirror it across three nested levels.

**GCP (Gross Chain Product)** is the GDP analog: the value added produced by Avalanche ecosystem on-chain, the base layer.

**GCI (Gross Chain Income)** is the GNI analog. It starts from GCP and adds **holder yield**: income earned outside the on-chain economy that accrues directly to Avalanche-resident holders of tokenized funds and yield-bearing stablecoins. This is the on-chain equivalent of a resident collecting a coupon on a foreign bond.

![gci identity - embed](/Wiki/Avalanche/Essential%20Readings/From%20Gross%20Chain%20Product%20to%20Gross%20Chain%20Income%20Where%20the%20Value%20Goes/raw/assets/figure-01.png)

**GCI-general** goes one step further than GCI. It adds **issuer reserve income**: the yield that token issuers or fund managers retained on the assets backing the Avalanche-resident float of their tokens. This income exists because of balances held on Avalanche, but under today's arrangements it accrues to the issuer, off-chain, rather than to residents. GCI would not count it, because it does not flow to residents. We track it anyway, precisely because it sizes an opportunity: it is value the ecosystem generates but does not yet receive.

![gci general identity](/Wiki/Avalanche/Essential%20Readings/From%20Gross%20Chain%20Product%20to%20Gross%20Chain%20Income%20Where%20the%20Value%20Goes/raw/assets/figure-02.png)

Stacking the three levels for every month gives the shape of the whole income system.

![gci article nested levels](/Wiki/Avalanche/Essential%20Readings/From%20Gross%20Chain%20Product%20to%20Gross%20Chain%20Income%20Where%20the%20Value%20Goes/raw/assets/figure-03.png)

In the latest full month (June 2026), on-chain production was $3.1M of NGCP (Nominal GCP). Holder yield added $2.7M to reach $5.8M of NGCI (Nominal GCI). Issuer reserve income then added $6.9M to reach $12.7M of NGCI-general. The single-month issuer increment alone was larger than all of on-chain NGCP. Over the full history, the ecosystem has produced roughly $954.8M of NGCP, channeled $32.3M of holder yield, and generated $242.8M of issuer reserve income.

The thin dark line on the chart is the one piece of this value that AVAX already captures, and it is the subject of the rest of this article.

---

## Three layers, three capture problems

The three layers differ on three axes that matter for strategy: how large they are, how cyclical they are, and how much of each is captured for AVAX today. The uncomfortable pattern, which the chart above already hints at, is that capture today runs highest at the base and falls to essentially zero at the top.

### The backbone: GCP

GCP is the backbone of the ecosystem. It reflects genuine value creation on-chain, and it is what drives demand for the services that sit behind the income layers above it. It is also the most cyclical of the three layers and, arguably, the one with the most growth potential. Over the measured window, Nominal Gross Chain Product (NGCP) has swung by more than 7.5x peak to trough, driven primarily by the industry-wide cycles. As explained in more details later in this article, this sharply contrasts the income layer, which is far less exposed to crypto cycles.

Part of GCP is already captured, and it is worth being precise about how. Every transaction on the C-Chain pays a fee, and 100% of C-Chain transaction fees (base and priority) are burned. A burned fee reduces AVAX supply, so it accrues, pro rata, to every AVAX holder. Transaction fees are therefore the one channel through which on-chain value already flows to the token. That is the dark line on the chart, and it is small. Since the start of 2024, when the income layers switched on, the C-Chain has burned about $23.5M of fees, and in the latest month the burn was near 3% of monthly NGCP. The overwhelming majority of GCP is the on-chain profit that protocols and their users retain at the application layer, and none of that is captured for AVAX today. This is mostly by construction, as transaction fees do not automatically reflect the value created by the transactions. Regardless, the recent ACP-283 provides a new policy lever that can directly amplify transaction fee capture by enabling dynamic gas price via validator voting.

Capturing more of it is possible but delicate, especially if we want the value capture to scale with the ecosystem value added. Taking a share of application-layer revenue is, in effect, a tax on the protocols that make the ecosystem worth using, and a poorly designed levy can discourage usage and development. Unlike a nation state, which captures value through compulsory taxation, a blockchain needs to explore a more challenging but also sustainable path if done right: one potential approach is **voluntary revenue sharing**, in which protocols choose to route value to the network in exchange for valuable public goods, better infrastructure, shared security, distribution, liquidity, or coordination that they could not easily build alone. Designing that exchange so that it is attractive rather than extractive is an open research problem, and a robust, sustainable answer is what would durably connect ecosystem growth to AVAX. It is worth adding that GCP capture is not limited to the C-Chain: as the Avalanche network of L1s grows, revenue sharing from those L1s is part of the same capture question. Research and business development work are being done on this front.

### Resident income: GCI

The step from GCP to GCI adds holder yield, income earned outside the on-chain economy that accrues directly to Avalanche-resident users. Across the 7 entities that distribute it, holder yield totals $32.3M to date, led by Avant (savUSD + savBTC) at $12.4M, BlackRock (BUIDL) at $9.0M, Janus Henderson (JAAA) at $6.7M.

Almost none of this layer is captured for AVAX today. Some of it, the yield paid out as an explicit distribution, at least touches the chain. But a large share of holder returns arrives through appreciation of the underlying token: the holder's asset is simply worth more over time, generating no on-chain fee and touching AVAX only indirectly, if at all. Under current mechanisms, this income enriches the holder without routing any share to the network. GCI makes the size of that flow visible, which is the first requirement for ever capturing part of it.

Capturing value from holder yield faces similar challenges as GCP: any value capture from holders can be distortionary discouraging usage and competitiveness relative to other ecosystems. Having a robust set of non-cash benefits is critical to keep the usage while capturing a meaningful share of the value. Research projects are planned for this stream.

### The steady giant: GCI-general

The largest layer is the one hardest to capture. NGCI-general adds issuer reserve income, and that increment is by far the biggest of the three: currently, it consists mainly of the yield that stablecoin issuers earn on the reserves backing their Avalanche-resident float. The income mix below shows how thoroughly it dominates the total in most months.

![gci article increment composition](/Wiki/Avalanche/Essential%20Readings/From%20Gross%20Chain%20Product%20to%20Gross%20Chain%20Income%20Where%20the%20Value%20Goes/raw/assets/figure-04.png)

Two properties make this layer strategically important. The first is stability. On-chain production is highly cyclical, rising and falling with crypto market conditions, but reserve income tracks short-term interest rates and the stablecoin float, both of which move slowly and are driven primarily by factors far less sensitive to crypto cycles. Over the 30 months of overlapping history (January 2024 to June 2026), NGCP had a coefficient of variation of 0.51 and swung 7.5x peak to trough, while issuer reserve income had a coefficient of variation of just 0.16 and swung only 2.1x. It is roughly three times steadier than GCP.

![gci article cyclicality contrast](/Wiki/Avalanche/Essential%20Readings/From%20Gross%20Chain%20Product%20to%20Gross%20Chain%20Income%20Where%20the%20Value%20Goes/raw/assets/figure-05.png)

That steadiness is exactly what a token economy dominated by a volatile production base lacks. A sustainable claim on even part of this layer would provide downside protection denominated in fiat, income that keeps arriving when on-chain activity is depressed.

The second property is that, today, capture of this layer is zero. The reserve income accrues off-chain, to the issuers, and never touches Avalanche at all. The ecosystem supplies the demand (the float that must be backed) but receives none of the yield that demand generates. Reserve income is concentrated: the two largest issuers alone account for about 96% of it ($173.2M and $59.7M to date).

[ACP-67](https://github.com/avalanche-foundation/ACPs/discussions/293) lays out a promising path to capturing this layer through a **protocol-owned stablecoin**, which has spurred many constructive discussions too: if the float is backed by reserves the protocol controls, the reserve yield accrues to the network rather than to a third-party issuer, converting the largest and steadiest income layer from an external flow into a captured one. The hard part is not the mechanism but the adoption.

For example, Hyperliquid started off with an attempt to launch their own stablecoin USDH and reached 2% of the whole network stablecoin balance at its peak, but later phased out. In its place, Hyperliquid managed to get 90% sharing on the yield from USDC reserve assets through Coinbase. A stablecoin is only as valuable as the balances people actually hold and use, and gaining adoption from incumbents with deep liquidity and distribution is the central challenge. That challenge is where measurement pays off again: GCI-general tells us precisely how large the prize is and how steady it would be.

### The pattern

Put the three layers together and the strategic picture is clear. The base layer, GCP, is the most cyclical and only lightly captured. The middle layer, resident income, is barely captured. The top layer, reserve income, is the largest and steadiest, and is not captured at all. Closing that gap, thoughtfully with minimal distortion on the activities that creates the value in the first place, is the work of the second step in the roadmap.

---

## Concluding remarks

GCP gave the ecosystem a rigorous measure of the value it produces. GCI extends that lens to the income the ecosystem channels, including the large, steady streams that currently flow past AVAX to external parties. Measurement is the first step, and it already reframes the strategy: three layers of values need different mechanisms to capture combining effort from research, product, and business development.

The next steps follow the roadmap. Step two is the careful design of capture mechanisms, voluntary value routing in exchange for public goods at the GCP layer, and a protocol-owned stablecoin at the reserve-income layer, each studied for its incentive effects before it is deployed. Step three is the distribution of what is captured back to the ecosystem and the token. All are active areas of research, and rest on the measurement foundation this article describes.

## Appendix

### Metric definitions

- **NGCP (Nominal Gross Chain Product)**: the monthly value added produced by the on-chain Avalanche economy, in nominal USD. The GDP analog and the base of the GCI stack. In the GCP framework, value added equals on-chain profit plus transaction fees.

- **NGCI (Nominal Gross Chain Income)**: NGCP plus the holder-yield increment. The GNI analog.

- **NGCI-general**: NGCI plus the issuer reserve-income increment. The broadest income concept published; it extends beyond the GNI analogy because the reserve income it counts currently accrues to external issuers rather than to residents.

- **Holder yield**: income earned outside the on-chain economy that accrues directly to Avalanche-resident holders of tokenized funds and yield-bearing stablecoins, measured net to the recipient.

- **Issuer yield (issuer reserve income)**: the yield stablecoin issuers earn on the reserve assets backing the Avalanche-resident float of their tokens, benchmarked to the 3-month US Treasury bill rate.

- **Transaction fees**: the gas fees users pay to transact on the C-Chain. 100% are burned (base and priority), so they accrue to AVAX holders through supply reduction. This is the "captured today" line on the nested-levels chart. It uses the whole-chain gas burned; the strict protocol-mapped subset that enters GCP value added is even smaller, so the line is a generous view of capture.

- **Coefficient of variation**: the standard deviation of a monthly series divided by its mean, a scale-free measure of volatility used here to compare the cyclicality of GCP against reserve income.

### Methodology notes

- **Source.** All figures come from the published Gross Chain Income series and definitions produced by the gross-chain-product methodology (linked below), reported in USD.

- **Full months only.** The current month is still in progress and is excluded from every chart and figure. The latest complete month (June 2026) is the reporting endpoint throughout.

- **Transaction-fee overlay.** The "captured today" line is the monthly whole-chain gas burned on the C-Chain, in USD, which is a subset of NGCP in every month.

- **Cyclicality.** Measured over the 30 months in which issuer reserve income is positive (January 2024 to June 2026). For context, NGCI-general as a whole had a coefficient of variation of 0.29 over this window, between GCP and reserve income.

- **Reserve-yield proxy.** Issuer reserve income is estimated with a single benchmark rate (the 3-month US Treasury bill, latest print 3.63% as of June 2026); true reserve yields differ by roughly plus or minus 100 basis points across issuers and over time.

### Caveats (mandatory)

- All figures are **ESTIMATES**, not audited financials.

- Scope is Avalanche-resident supply only; multichain products are counted only for their Avalanche float.

- Issuer income uses the single-rate Treasury-bill proxy described above.

- Some holder-yield series are understated where token price history is short, and daily attribution for a few products is noisy; trust the lifetime magnitudes over any single month.

- One holder product's assets under management are backed out of its fee schedule rather than observed directly, and one issuer's modeled gross yield runs slightly high relative to distributions.

---

*Disclaimer: This material is for informational purposes only and is not investment advice or an offer or solicitation to buy or sell any asset.*

## Source

- Canonical article: <https://www.avax.network/about/blog/from-gross-chain-product-to-gross-chain-income-where-the-value-goes>
- Author: Siyu (Eric) Lu, PhD
- Publisher: Avalanche Foundation
- Published: 2026-08-12
- Captured: 2026-09-13T10:22:40-07:00
- Reuse: private research; client redistribution not assessed
