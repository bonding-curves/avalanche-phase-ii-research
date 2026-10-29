# BENQI liquid staking interview with Hansen

Machine-generated narrative for transcript `tx_293_9ccee9eb`, with speaker names normalized to the speaker table. This reading aid has not been reviewed against the audio. Its interpretations require review before they are cited as findings.

## Introduction and Project Scope (00:04)

The meeting opened with informal greetings between **Hash**, **Shawn**, and **Hansen**, a co-founder of **BENQI**. **Hash** and **Shawn** represent the **Bonding Curve Research Group (BCRG)**, a complex systems engineering firm. They explained that for the past eighteen months, BCRG has collaborated with **Avalanche**, initially focusing on the composition of the entire system into subsystems to build a "digital twin" for the network.

Over the last year, their focus has narrowed specifically to validator staking and delegator economics. **Hash** noted that because Avalanche's inflation and minting rates have remained largely static, it has been difficult to determine the "market regime" or understand how validators react to different reward rates. To solve this, BCRG is soliciting information from validators and ecosystem experts to refine their predictive models.

**Shawn** elaborated on the technical framework they are employing, noting that they use a library called **CAD (Complex Adaptive Dynamics Computer Aided Design)**. Originally created by **Block Science** (now the **Dynamical Systems Group**), CAD allows them to model the state of the system and the policy functions that govern how that state changes over time. Specifically, they are modeling validator sensitivity to various **Avalanche Chain Proposals (ACPs)** regarding reward modifications and duration requirements. While they have conducted on-chain analysis to cluster validator behavior, they are supplementing this data with interviews from experienced stakeholders like **Hansen**.

## BENQI and sAVAX Operational Strategy (06:17)

**Hansen** introduced himself as a co-founder of **BENQI**, noting that he has been involved with Avalanche since pre-mainnet and has worked closely with **Avalanche Labs**. He personally runs a validator stack and manages several validators through **sAVAX**, though the majority of their stake is delegated to the open network.

Regarding **sAVAX**, which represents approximately 10% to 12% of the total stake, **Hansen** explained their current strategy:

*   **Liquidity Prioritization:** Prior to the **Helicon** upgrade, they primarily utilized 14-to-18-day stake delegations to ensure users maintained liquidity.
*   **Stability:** They maintain a mix of longer-running validators because the churn rate is low—estimated at 8% or less. **Hansen** mentioned that they successfully serviced a single stake of 3 million AVAX from **Avat**, with some stakes remaining for three months or longer.
*   **Post-Helicon Shift:** Following the Helicon upgrade, **Hansen** indicated that BENQI is leaning toward reducing all stake durations to two days. He noted that the APR delta between a two-day and a 14-day stake is minimal—perhaps only five to twenty "bits."

**Hansen** expressed a dissenting view from **Eric** and **Matthias**, who believe validators will stake for longer durations. **Hansen** remains skeptical and intends to observe the actual rollout before fully implementing a shift to two-day staking, a process he expects could take months.

## Institutional Capital and Validator Costs (09:56)

**Hash** questioned whether **ACP 273**—which aims to reduce staking durations—is intended to attract institutional capital, as these entities often prioritize liquidity over raw returns. **Hansen** countered that while the proposal may target ETFs, those entities typically employ professional staking partners like **BlockDaemon** or **TwinStake**. He suggested that using **sAVAX** would be further out on the "risk curve" for an ETF, though it might offer higher yields.

When discussing the costs of operating a validator, **Hansen** noted that his engineers find the actual running costs—specifically **AWS** and **GCP** expenses—to be significantly higher than the figures claimed by **Avalanche Labs**. He clarified that BENQI does not have institutional arrangements requiring **SOC2** compliance; if such requirements became necessary, they would simply divert stake to partners like BlockDaemon.

## The Ignite Program and Mempool Access (15:25)

**Hansen** provided a history of the **Ignite** program, which was created to bypass the 2,000 AVAX requirement for running a validator. Previously, teams needing to validate a subnet L1 also had to validate the primary network, which often required at least five validators per subnet—a cost of 10,000 AVAX that was prohibitively expensive when the token price was \$10–\$15. Ignite allowed teams to "rent" the necessary stake.

While the **Blueberry** upgrade removed this requirement—effectively killing the primary value proposition of Ignite—the program persisted through 2024 and 2025. This was because running a validator remained the only way to access the mempool. **Hansen** noted that hundreds of validators used Ignite specifically to "snipe" launches and engage in MEV front-running. Currently, however, the program is largely dormant, with only about six active validators.

## sAVAX Risk Profile and Capital Efficiency (17:48)

**Shawn** asked for clarification on why **sAVAX** is considered further down the risk curve. **Hansen** explained that while holding raw AVAX is the "risk-free rate," **sAVAX** introduces:
1.  **Smart Contract Risk:** The risk associated with the C-Chain contracts.
2.  **Agency Risk:** The risk associated with the BENQI team.
3.  **Fees:** The additional charger fees applied.

Despite these risks, **Hansen** argued that **sAVAX** is more capital efficient for "whales" and the **IT Foundation**. Because **sAVAX** can be used as collateral, users can borrow against it. For example, if **sAVAX** yields 4.9% APY and USDC borrows at 5.8%, the net borrow cost is relatively low, especially if the AVAX price appreciates. He noted that the primary driver for using **sAVAX** (and **SDE**) is "looping" on money markets, though these markets are currently compressed.

## Stablecoin Design and Value Capture (20:26)

The conversation shifted to **ACP 66/67** and the proposal for a native Avalanche stablecoin. **Hash** revealed that BCRG is researching a novel stablecoin design that uses **sAVAX** as the base layer rather than raw AVAX. 

> "We are using sAVAX as the base layer... because it's more stable [and] gives better API. If you used AVAX, it would have compromised the network security for Avalanche because a lot of people would have moved [their stake]. It's better to use sAVAX because it's a correlated asset."

**Hash** described the design as a securitized, tranched system:
*   **Class A Tokens:** Serve as the bond and provide the actual stablecoin.
*   **Class B Tokens:** Absorb the volatility and provide the yield.

**Hash** argued that this on-chain design would allow 100% of rewards to be distributed via the protocol, removing the need for negotiations with third-party stablecoin issuers. He estimated that approximately \$6.5 million in value is currently lost to USDT and USDC; a native solution could capture a significant portion of that leakage. **Hansen** expressed interest in this "common good" product, and **Hash** mentioned the intent to eventually sell the completed startup/design to **Avalanche Labs**.

## Governance and the "Kinked Curve" (24:50)

**Hansen** noted that the shift toward two-day staking would reduce BENQI's revenue by approximately 24.6%. He stated that he would need to increase BENQI's Total Value Locked (TVL) by 25% just to return to previous revenue levels.

**Hash** discussed his previous contributions to the **ACP 285** discussion, where he proposed changing the shape of the reward curve to a "hump shape" or a "piecewise linear kink." He argued that this would protect the business models of LSTs (like BENQI) and address inflation and long-term staking concerns simultaneously. However, **Hash** lamented that **Avalanche Labs** and the **Foundation** seemed uninterested, citing "technical complexity" and potential "overflow issues" as reasons for rejecting the non-linear curve. **Hash** dismissed these concerns, suggesting the engineers simply lacked the will to implement it.

## Validator Infrastructure and Personal Staking (31:44)

When asked if he would invest more in validator infrastructure, **Hansen** was dismissive, stating that for a personal validator, "if I could run it on a toaster, I would." For **sAVAX**, infrastructure investment is only a consideration if the business requires it to serve stakers. He mentioned that in January, they adjusted their validators to help the network reach a specific gas target on the C-Chain at the request of **Martin**.

On a personal level, **Hansen** has shifted from monthly to fortnightly staking because he now prioritizes liquidity. He admitted that during periods of high upward volatility, he might not stake at all, as the opportunity cost is the ability to sell the AVAX for another asset.

## Delegation Capacity and BENQI's "vQi" (37:10)

**Hash** and **Hansen** discussed a proposal to increase delegation capacity from 4x to 24x the validator's own stake. **Hansen** strongly supported this, calling the 4x limit "overly restrictive." He argued that increasing capacity would incentivize smaller validators to engage in self-promotion.

**Hansen** explained how this relates to BENQI's **vQi** feature, where users who stake Qi receive a pro-rata vote on where delegations go. Currently, only "sAVAX whales" can effectively fill a validator. With a 24x limit, a validator with only 10,000 AVAX could command a significant amount of delegated stake, which **Hansen** believes would be beneficial for the ecosystem.

He also revealed that BENQI currently "leaks" approximately \$270,000 per year to other validators because they delegate to nodes that charge 2% to 5% fees. **Hansen** noted that while they could run these themselves for less, they chose to delegate to "give back" to the network.

## Closing Reflections on Avalanche (44:08)

In the final portion of the meeting, **Hansen** shared a candid assessment of Avalanche. He noted that while the Business Development (BD) team is professional and well-regarded on Wall Street—citing **Charles Schwab's** choice of AVAX for 20 ETFs—the chain has suffered from a lack of a "compelling product" on the demand side.

**Hansen** expressed concern that the most talented developers in crypto are currently focused on other chains. He suggested that reducing inflation now would be a mistake, as it would drive users to other ecosystems like **Hyperliquid**. He concluded that while the treasury is large enough to outlast competitors, the network needs a differentiating product to truly "rip."

The meeting concluded with **Shawn** requesting to be connected with **Hansen's** co-founder, **Dan**, via their group chat (**BCRG**).

