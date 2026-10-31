---
title: "Research Methodological Pivot"
description: "Historical source record with later research context."
date: "2026-10-30"
kind: archival-edition
status: "historical"
source_id: 36360ed9-0ab7-8098-9aa6-f1fc709c9fb0
reader: "Avalanche Foundation and Ava Labs researchers"
question: "What did this earlier research propose or report, and how does it relate to the October model?"
---

Historical context added 30 October 2026.

The proposed architecture divided participants into four behavioural archetypes and described extensions for different validator markets. The note records design intentions. It provides no estimated archetype population, fitted exit threshold or forecast comparison establishing those intentions as results.

Model v0.8.0 instead represents Primary Network validators through statistical decisions about renewal, return, entry, duration and stake. It does not simulate the four named archetypes or L1 validator decisions. The [October model explanation](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/methodology#3-five-decisions-turn-the-historical-record-into-daily-behaviour) describes the implemented decisions. The original Research Questions link is retained as an unavailable historical reference.

## Source record

The source records creation on May 17, 2026 6:30 PM and last editing on May 21, 2026 3:40 AM. The timezone is unspecified. Its creator field names Hash. The source snapshot is labelled 1 July 2026.

[Original Markdown as text](/Phase-II/Wiki/Memos/historical/methodological-pivot/original-36360ed9-0ab7-8098-9aa6-f1fc709c9fb0.txt) · [Source identities and hashes](/Phase-II/Wiki/Research-History/manifest.json) · [Research chronology](/Phase-II/Wiki/Research-History/)

The reading edition adjusts heading depth, metadata line breaks, currency escapes and historical links. Remaining source wording and equations are preserved.

## Historical text

<!-- historical-original:start -->
### Research Methodological Pivot

Created By: Hash  
Creation Time: May 17, 2026 6:30 PM  
Description: We are not engineering a model to deliver a single, fixed recommendation for staking rewards. We are building a Dynamic Behavioral Laboratory.  
By investing in a Composable Archetype architecture that respects the technical realities of Etna and the dynamic fee parameters of ACP-176, the Avalanche Foundation acquires a high-fidelity, future-proof asset. This platform will remain operationally rigorous, empowering the Foundation to confidently stress-test and navigate macroeconomic volatility through 2027 and beyond.
Last Edited Time: May 21, 2026 3:40 AM  
Sprint: Sprint 2  

### The Strategic Rationale for Composable Archetype Architecture

#### 1. The Challenge: Modeling an Evolving Network Economy

Phase II is a nine-month research marathon. A systemic failure mode in blockchain economic research is delivering a "Perfect Model" at Month 1 that becomes a static, obsolete artifact by Month 4 because the underlying network architecture or market regimes have evolved.

The core economic baseline of the network is anchored by the structural overhaul of **Etna (Avalanche9000)** and the dynamic fee optimizations of **ACP-176**. To ensure our research framework can dynamically absorb these specific protocol rules without requiring a complete engine rebuild, our framework leverages a **Heterogeneous Agent Model** built on **Composable Archetypes**. This architecture ensures the simulation engine is adaptive, structurally future-proof, and aligned with Avalanche's multi-layered network reality.

#### 2. Technical Rationale: Moving Beyond the "Representative Agent"

Eric’s neoclassical models relies on a "Representative Agent"—a mathematical abstraction assuming homogeneous, perfectly rational utility optimization. We modify this as a baseline for three reasons:

- **Inherent Species Blindness:** Aggregate models smooth out individual variances, making them structurally blind to centralization risks. They cannot predict whether a macro policy shift will inadvertently enrich whales while inducing a mass extinction of smaller, distributed validators.
- **Non-Linear Feedback Failures:** Real-world network security is governed by discrete "**Exit Triggers**" (e.g., AWS cost thresholds, tax compliance shifts, or Liquid Staking Derivative yield spreads). Homogeneous utility curves obscure these critical economic "cliffs" until a cascade occurs.
- **Static Incentive Constraints:** A generalized, average agent model cannot evaluate temporal or behavioral incentives, such as tenure-weighted or performance-weighted reward distributions, because the agents lack individual state and identity.

#### 3. The Core Agent Topology: Definition & Rationale

To capture the economic dynamics of an Etna-driven ecosystem, the laboratory initializes with four distinct behavioral profiles. These species represent the primary cross-currents of capital, infrastructure, and user behavior interacting on the network.

- **Initial Deployment:** The simulation launches with four core species: *The Veteran (OG)*, *The Mercenary*, *The SaaS Pro*, and *The Retailer*.
    - **The Veteran (OG):**
        - **Who they are:** Early adopters, strategic ecosystem partners, and foundations who view their validator nodes as a permanent commitment to network bedrock and reputational capital.
        - **Why we chose them:** The Veteran provides a baseline of network stability. Because their sensitivity to shifting **APR** is extremely low, they represent the "sticky" security floor of the network. Modeling them prevents the simulation from falsely predicting total network collapse during temporary market downturns.
    - **The Mercenary**
        - **Who they are:** Highly sophisticated, yield-maximizing capital allocators (e.g., cross-chain yield aggregators, algorithmic trading desks) with zero network loyalty.
        - **Why we chose them:** The Mercenary acts as the primary driver of capital flight risk. By hardcoding their exit trigger as a function of macro opportunity costs—specifically exiting immediately if APR < (Treasury + 1%)—we can accurately simulate how rising macroeconomic interest rates or external DeFi yield spreads threaten Avalanche’s liquid security pool.
    - **The SaaS Pro (Software-as-a-Service)**
        - **Who they are:** Commercial node operators, institutional staking providers, and infrastructure businesses running high-availability hardware (e.g., AWS, bare-metal setups) to manage delegated stake.
        - **Why we chose them:** The SaaS Pro represents the operational cost reality of the network. Unlike pure capital allocators, their behavior is strictly bounded by hard physical and operational ROI floors (hardware amortization, bandwidth, and AWS cost baselines). Modeling this species is critical for answering [**Question #4**](#historical-reference-1) regarding operational cost tradeoffs and hardware price shocks under ACP-77.
    - **The Retailer**
        - **Who they are:** Individual token holders, smaller community delegators, and retail users interacting with the network via wallets and liquid staking interfaces.
        - **Why we chose them:** The Retailer is the lifeblood of network velocity and ecosystem GDP. They possess a high sensitivity to transaction friction, gas fees, and validator commission percentages. Including them allows us to model how retail participation scales or contracts in response to UX friction and fee dynamics driven by ACP-226 (Sub-second finality).

#### Strategic & Architectural Advantages

##### Empirical Discovery Over Theoretical Assumption

Rather than imposing top-down assumptions on staker behavior, Milestone 1 applies **unsupervised clustering** to 2024–2025 historical on-chain data. This allows the network’s actual behavioral profiles to emerge organically, ensuring our baseline agent species match empirical reality.

##### "Lego-Style" Extensibility

Our architecture treats individual agent species as isolated, pluggable software modules. If the Foundation introduces a novel validator tier or a new ecosystem incentive framework in Month 6, we can seamlessly construct and inject a fifth archetype with distinct parameter constraints without having to rebuild the core simulation engine.

##### Balancing Conflicting Network Goals

We selected this specific four-part composition because it explicitly mirrors the natural tension between the Foundation’s core KPIs: **Security, Decentralization, and Economic Velocity**. Running simulations where the *Mercenary* chases raw yields, the *SaaS Pro* protects margins, the *Retailer* demands low friction, and the *Veteran* absorbs volatility allows the laboratory to uncover the exact parameter ranges where network incentive structures achieve true equilibrium.

##### Native Alignment with Avalanche9000 (Etna)

The Etna upgrade solidified a distinct structural dichotomy between **Primary Network Validators** and sovereign **Avalanche L1 Validators**. A homogeneous model is fundamentally incapable of capturing the cross-cutting incentives of this two-tier topology. Our HAM framework was explicitly designed from the ground up to model this dual-layer reality.

#### 5. Conclusion: A Living Asset vs. A Static Report

We are not engineering a model to deliver a single, fixed recommendation for staking rewards. We are building a **Dynamic Behavioral Laboratory**.

By investing in a Composable Archetype architecture that respects the technical realities of Etna and the dynamic fee parameters of ACP-176, the Avalanche Foundation acquires a high-fidelity, future-proof asset. This platform will remain operationally rigorous, empowering the Foundation to confidently stress-test and navigate macroeconomic volatility through 2027 and beyond.

- **Future Evolution:** If the Foundation introduces a novel tier (e.g., an "**Institutional Credit**" L1) in Month 6, we can seamlessly construct and inject a fifth archetype with distinct parameter constraints.
- **Benefit:** The core simulation engine never requires a rebuild; we simply scale the agent ecology as new network conditions dictate.

##### C. High-Resolution Risk Mapping

Because each archetype possesses explicit, decoupled breaking points (e.g., the *SaaS Pro* reacting to hardware/AWS cost floors; the *Mercenary* monitoring APR < (Treasury} + 1%) spreads), the laboratory can map complex vulnerability matrices. This allows us to isolate precisely which policy levers protect or expose specific network cohorts.

##### D. Native Alignment with Avalanche9000 (Etna & Granite)

The Avalanche9000 upgrade solidifies a distinct structural dichotomy between **Primary Network Validators** and **L1-Specific Validators**. A homogeneous model is fundamentally incapable of capturing the cross-cutting incentives of this two-tier topology. Our HAM framework was explicitly designed from the ground up to model this dual-layer reality.

### Historical references

The original links below name earlier project references. Their availability has not been established. The text above links here, and the original export retains every URL.

#### Historical reference 1

`../Research%20Questions%2035360ed90ab7802dbd70c55d608b40fe.md`
<!-- historical-original:end -->
