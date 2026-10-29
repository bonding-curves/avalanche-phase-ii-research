# Minutes: BENQI liquid staking interview with Hansen

**Date.** 2026-08-31, 19:00 America/New_York. **Class.** interviews. **Duration.** 1:05:13.

**Participants.** Hansen (BENQI, liquid staking protocol on Avalanche (interviewed 2026-08-31)); Hash (Researcher, BCRG); Shawn Anderson (Research lead, BCRG).

**Mentioned, not present.** Eric, Matthias, Martin, Dan.

**Source.** Machine transcript `tx_293_9ccee9eb` and machine diarization, not audio reviewed. Speaker names per the table in [transcript.md](/Phase-II/Interviews/BENQI-2026-08-31/transcript). Derived items from automated extraction run `tpf_293_20260909163544`; each is one machine reading with its evidence segment, not a reviewed record. Follow-through is updated as later meetings and commits land.

## Summary

The Bonding Curve Research Group (BCRG), represented by Hash and Shawn, met with Hansen, co-founder of BENQI, to gather qualitative data for their predictive models on validator staking and delegator economics within the Avalanche ecosystem. BCRG is utilizing a "Complex Adaptive Dynamics" (CAD) framework to model how validators respond to various Avalanche Chain Proposals (ACPs) and reward modifications.

The discussion focused heavily on the operational shift toward shorter staking durations. Hansen indicated that BENQI is moving toward two-day staking durations following the Helicon upgrade, as the yield difference compared to longer durations is negligible. He expressed skepticism regarding the belief that institutional capital will drive a return to long-term staking, noting that institutions typically use professional partners and prioritize liquidity. Additionally, Hansen highlighted a discrepancy between actual validator operating costs (AWS/GCP) and the lower figures reported by Avalanche Labs.

The participants also explored the intersection of Liquid Staking Tokens (LSTs) and network stability. Hash presented a proposal for a native Avalanche stablecoin using sAVAX as a base layer to capture value currently lost to USDT/USDC and avoid compromising network security. The meeting concluded with a discussion on governance, where Hansen advocated for increasing delegation capacity from 4x to 24x to empower smaller validators, and a candid critique of Avalanche's need for a "compelling product" to attract top-tier developers and sustain demand.

## Topics

1. **Communication tool check-in.** Shawn confirmed he successfully gained access to Twitter, WhatsApp, and Telegram.
2. **Technical tip for ID retrieval.** Shawn explained how to use developer tools and the network console to find specific IDs.
3. **Personal health and camera status.** A participant mentioned feeling under the weather and decided to keep their camera off.
4. **Camera habits and time zones.** The group discussed Hash's history of keeping his camera off and the fact that it was early morning for some.
5. **Bonding Curve Research Group introduction.** Hash and Shawn introduced their firm as a complex systems engineering group working with Avalanche.
6. **Shift in research focus.** The team explained their transition from general system composition to focusing on validator staking and delegator economics.
7. **Validator sensitivity research.** The team described their goal of soliciting information from validators to improve their model's predictions on reward rates.
8. **CAD framework explanation.** Shawn described the Complex Adaptive Dynamics framework used to model validator behavior and policy responses.
9. **Interview goals and outreach.** Shawn explained the need for interviews with stakeholders to supplement on-chain analysis and requested connections to other validators.
10. **Hansen's background and roles.** Hansen introduced himself as a co-founder of BENQI and a long-time Avalanche participant who runs his own validators.
11. **sAVAX staking strategy.** Hansen explained that sAVAX prioritizes user liquidity by using short-term delegations but maintains some long-term validators to raise yield.
12. **Post-Helicon upgrade plans.** Hansen discussed the possibility of reducing all stakes to two days due to the minimal APR difference.
13. **ACP 273 and institutional capital.** Hash and Hansen discussed how ACP 273 aims to attract institutional capital and the role of staking partners for ETFs.
14. **Validator operating costs.** The group discussed the high costs of running validators on AWS and GCP compared to official claims.
15. **sAVAX risk profile.** Hansen explained the smart contract and agency risks associated with sAVAX compared to raw AVAX.
16. **Capital efficiency and looping.** Hansen described how sAVAX is used as collateral for looping on money markets to increase capital efficiency.
17. **Native stablecoin proposals.** The group discussed ACP 66/67 and the Foundation's efforts to capture value through a native stablecoin.
18. **Novel stablecoin design.** Hash described a research project involving securitizing and tranching using sAVAX as a base layer to create a stablecoin.
19. **Stablecoin implementation and rewards.** Hash explained that their design allows for 100% on-chain reward distribution without third-party negotiation.
20. **Impact of two-day staking on revenue.** Hansen noted that the Helicon upgrade and a shift to two-day staking would significantly reduce sAVAX revenue.
21. **Validator subsidy proposals.** Hash discussed using ecosystem revenue to subsidize validators, referencing ACP 67.
22. **ACP 285 and curve shaping.** Hash explained his proposal to change the reward curve to protect LST businesses and address inflation.
23. **Foundation feedback on technical complexity.** Hash recounted the Foundation's rejection of his proposal due to technical implementation concerns and overflow issues.
24. **Validator infrastructure investment.** Hansen stated that infrastructure is rarely a deciding factor and he prefers the lowest cost possible for personal validation.
25. **Network requirements and Avalanche GO.** Hansen mentioned updating validators to the latest Avalanche GO version at the request of the network.
26. **Personal staking habits.** Hansen shared that he now prioritizes liquidity with fortnightly staking and avoids staking during high upside volatility.
27. **Opportunity costs for holders.** Hansen mentioned that his primary alternative to staking is selling AVAX to buy other assets.
28. **BENQI delegation algorithm.** Hansen explained how bots analyze validator capacity and uptime to automate delegations.
29. **Delegation capacity limits.** The group discussed a proposal to increase the delegation multiple from 4x to 24x to empower smaller validators.
30. **BENQI revenue leakage.** Hansen revealed that BENQI loses approximately \$270,000 a year by delegating to other validators instead of running their own.
31. **Validator networking challenges.** The participants lamented the difficulty of finding and connecting with active validators.
32. **Staking spread requirements.** Hansen suggested that a very high yield spread (10-12%) would be necessary to convince him to stake for a full year.
33. **Inflation and emission strategies.** The group compared Avalanche's inflation to Solana, Ethereum, and Hyperliquid, arguing against reducing emissions too early.
34. **Value capture leakage.** Hash calculated that a significant portion of created value is lost to external stablecoin providers like USDT and USDC.
35. **Business exit strategy.** Hash expressed a desire to sell their stablecoin startup to the Foundation rather than running it as a long-term business.
36. **BENQI team management.** Hansen described his eight-person team as having a laissez-faire management style.
37. **Diversification and security.** Hansen discussed the time-consuming nature of hardening LST security and the current instability of small DeFi protocols.
38. **Lending market architecture.** Hansen confirmed that BENQI uses a modified version of Compound V2.
39. **Automatic renewal feature.** The group discussed the potential for "autostake" in the Helicon upgrade to reduce overhead for ETFs.
40. **Avalanche ecosystem outlook.** Hansen shared a mixed view of Avalanche, praising the BD team but questioning the lack of a compelling demand-side product.
41. **Meme coin incubation.** The group critiqued the effectiveness of the Foundation's meme coin programs.
42. **Foundation management observations.** Hash mentioned a period of "free money" where they received payments without any oversight or meetings from the Foundation.
43. **Connecting with Dan.** The participants arranged to add Hansen's co-founder, Dan, to their group chat.
44. **Group chat administration.** The participants discussed transferring ownership of the chat and removing a former member.
45. **Cold plunge discussion.** After the main meeting ended, Shawn and Hash discussed Shawn's morning cold plunge routine and shared a video.

## Decisions

- `D1` BENQI is leaning toward reducing all stake durations to two days post-Helicon upgrade. (Hansen). dissent: Hansen noted that Eric and Matthias believe validators will stake for longer durations, which he opposes. [seg-0067](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `D2` BCRG will use sAVAX as the base layer for their novel stablecoin design instead of raw AVAX. (Hash, Shawn) [seg-0194](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `D3` Hansen shifted his personal staking strategy from monthly to fortnightly. (Hansen) [seg-0292](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `D4` Shawn and Hash will connect with BENQI co-founder Dan via the BCRG group chat. (Shawn, Hash, Hansen) [seg-0561](/Phase-II/Interviews/BENQI-2026-08-31/transcript)

## Actions and commitments

- `A1` Connect Shawn with co-founder Dan via the BCRG group chat (shawn-anderson). follow-through: open [seg-0561](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `A2` Produce a research paper on the novel stablecoin design using sAVAX as the base layer (hash and shawn-anderson). follow-through: open [seg-0221](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `A3` Discuss the stablecoin design further with Hansen (hash and shawn-anderson). follow-through: open [seg-0217](/Phase-II/Interviews/BENQI-2026-08-31/transcript)

## Questions

- `Q1` Is there an E-staking ETF? (Hash). answer: Yes, they already exist and typically hire professional staking partners like BlockDaemon or TwinStake. [seg-0090](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q2` What are the major costs of operating a validator? (Hansen). answer: Costs for AWS and GCP are significantly higher than what Avalanche Labs claims. [seg-0097](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q3` What information or signals do you actually watch for when deciding to stake or unstake? (Hash). answer: For the business side, they prioritize increasing TVL and minimizing costs; personally, it is an economic decision based on yield and liquidity. [seg-0118](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q4` Can you talk a little bit more about the Ignite program? (Shawn). answer: It was created to allow teams to rent the 2,000 AVAX required to run a validator, primarily used by those wanting mempool access for MEV. [seg-0134](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q5` When you said sAVAX is further down the risk curve, what did you mean by that? (Shawn). answer: It involves smart contract risk on the C-Chain, agency risk from the BENQI team, and additional charger fees.
- `Q6` Are you familiar with ACP 66 or 67 regarding a native stablecoin for Avalanche? (Hash). answer: Hansen was not aware it was live but agreed that capturing leaked value makes sense. [seg-0184](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q7` Is the stablecoin design something you've discussed with the foundation or Matthias? (Hash). answer: No, they have not discussed it with the foundation yet. [seg-0198](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q8` How does reducing stake duration from 14 days to 2 days impact your business? (Hash). answer: It reduces revenue by approximately 24.6%, requiring a 25% increase in TVL to break even. [seg-0225](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q9` Is there a net reduction in issuance with the proposed curve change? (Hansen). answer: Yes, there is a net reduction in issuance. [seg-0252](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q10` Was the technical implementation of the non-linear curve more complicated? (Hansen). answer: Yes, it was non-linear and the foundation feared it would lead to overflow issues. [seg-0261](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q11` Can you imagine a scenario where you would make the choice to invest more in validator infrastructure? (Shawn). answer: Only if the business requires it to serve the yield for stakers; personally, he prefers minimal infrastructure. [seg-0267](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q12` What kind of commitment durations do you go for with your personal AVAX? (Shawn). answer: He shifted from monthly to fortnightly staking to prioritize liquidity. [seg-0290](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q13` What opportunity costs are you thinking about when deciding whether to restake? (Shawn). answer: The main opportunity cost is selling the AVAX to buy another asset.
- `Q14` Are there any other validators you could put us in touch with? (Shawn). answer: Hansen does not personally know many other validators. [seg-0304](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q15` Is the delegation through BENQI algorithmic? (Shawn). answer: Yes, they use bots to analyze available capacity and stake duration on-chain.
- `Q16` What were the results on increasing delegation capacity from 4x to 24x? (Hash). answer: The model showed low impact because most nodes aren't at capacity, though Hansen argues it would incentivize self-promotion. [seg-0328](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q17` Since 93% of all delegations come through BENQI, is that correct? (Hash). answer: Yes, that is correct.
- `Q18` How big is your team and how do you manage it? (Hash). answer: It is an eight-person team managed in a laissez-faire manner. [seg-0449](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q19` Do you run other operations outside of the Avalanche ecosystem? (Shawn). answer: He doesn't run other operations, but he stays in conversations with other teams and protocols. [seg-0457](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q20` What are your current priorities—do you plan on moving to other chains? (Hash). answer: BENQI is not moving; the lending market and LST are too time-consuming to maintain security. [seg-0466](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q21` What architecture do you use for the lending markets? (Hash). answer: They use Compound V2.1. [seg-0481](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q22` Would you be interested in automatic renewal (autostake)? (Shawn). answer: Yes, it would be useful, especially for ETFs using short-term stakes. [seg-0499](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q23` Is your co-founder, Dan, also a validator? (Shawn). answer: Not anymore; he likely sold his AVAX. [seg-0515](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q24` Are you guys full-on AVAX maxis? (Shawn). answer: He is conflicted because he sees talent and attention on other chains, though he believes the treasury will allow Avalanche to outlast others.
- `Q25` Is AvaLabs willing to build anything internally to create a compelling product? (Shawn) [seg-0533](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q26` What was the deal with the foundation—why did everybody leave? (Hash) [seg-0554](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `Q27` What is the name of our chat? (Hansen). answer: The chat is named BCRG. [seg-0560](/Phase-II/Interviews/BENQI-2026-08-31/transcript)

## Risks

- `R1` Reducing stake durations to two days (post-Helicon) will significantly reduce BENQI's revenue. (Hansen). mitigation: Increase Total Value Locked (TVL) by approximately 25% to offset the loss. [seg-0229](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `R2` Actual validator running costs (AWS/GCP) are significantly higher than the figures claimed by Avalanche Labs. (Hansen) [seg-0100](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `R3` sAVAX carries smart contract risk, agency risk (BENQI team), and additional charger fees compared to raw AVAX. (one participant)
- `R4` Reducing emissions/inflation now may cause users to leave the ecosystem for competitors like Hyperliquid. (Hansen) [seg-0415](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `R5` Avalanche lacks a compelling demand-side product, and top crypto talent is focused on other chains. (Hansen). mitigation: Developing a differentiating product, such as the proposed native stablecoin. [seg-0529](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `R6` The 4x delegation capacity limit is overly restrictive and prevents smaller validators from growing. (Hansen). mitigation: Increase delegation capacity to 24x (as per Jack's proposal). [seg-0327](/Phase-II/Interviews/BENQI-2026-08-31/transcript)

## Goals stated

- `G1` Improve the predictive models regarding validator sensitivity to reward rates and ACPs by soliciting information from ecosystem experts. (Hash) [seg-0033](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `G2` Create a securitized, tranched stablecoin design using sAVAX as the base layer to capture value leakage and provide a common good for the network. (Hash) [seg-0193](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `G3` Increase the validator delegation capacity from 4x to 24x to incentivize smaller validators and improve capital efficiency for LSTs. [seg-0321](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `G4` Shift BENQI's stake delegations toward two-day durations to prioritize user liquidity. (Hansen) [seg-0067](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `G5` Sell the completed stablecoin design/startup to Avalanche Labs rather than operating it as a business. (Hash) [seg-0443](/Phase-II/Interviews/BENQI-2026-08-31/transcript)

## Assumptions

- `S1` Validator sensitivity to reward rates cannot be determined from existing on-chain data because inflation/minting rates have remained stagnant. (Hash) [seg-0033](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `S2` Institutional capital prioritizes liquidity over high returns when choosing staking options. (Hash) [seg-0085](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `S3` Reducing the minimum stake duration to two days will increase validator participation. (shawn-anderson) [seg-0097](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `S4` The current 4x delegation capacity limit is overly restrictive and hinders smaller validators. (shawn-anderson) [seg-0327](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `S5` Reducing emissions/inflation without a corresponding increase in demand will cause users to leave the ecosystem. (shawn-anderson) [seg-0415](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `S6` The Avalanche Foundation is indifferent to the concerns of LST providers regarding revenue loss from Helicon/ACP 285. (group) [seg-0241](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `S7` A native stablecoin design using SAVAX as a base layer is more secure for the network than using AVAX. (Hash) [seg-0197](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `S8` The current state of 'Small DeFi' is precarious compared to large-scale protocols. (shawn-anderson) [seg-0476](/Phase-II/Interviews/BENQI-2026-08-31/transcript)

## Opportunities

- `O1` Develop and launch a novel, securitized, tranched stablecoin using sAVAX as the base layer to capture value currently leaking to USDT/USDC. (Hash) [seg-0194](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `O2` Sell the completed stablecoin startup/design to Avalanche Labs. (Hash) [seg-0443](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `O3` Connect BCRG with Dan (BENQI co-founder) to discuss ecosystem and validator insights. (one participant)
- `O4` Increase validator delegation capacity from 4x to 24x to incentivize smaller validators to self-promote and increase ecosystem diversity. (Hansen) [seg-0343](/Phase-II/Interviews/BENQI-2026-08-31/transcript)
- `O5` BENQI could reduce the \$270,000 annual revenue leak by running more of its own validators instead of delegating to third parties. (one participant)

## Gaps

- Audio not reviewed; speaker attribution rests on the evidence in the speaker table.
- Items are one machine extraction; a reviewer confirms or strikes each against the transcript before it is cited.

