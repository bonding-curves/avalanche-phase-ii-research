# Transcript, 2026-08-31 19:00 (America/New_York)

Legion transcript `tx_293_9ccee9eb`, 603 segments, 1:05:13 of audio. Machine transcript and machine diarization; not audio reviewed. Speaker names are decided from evidence per the speaker table below (rules MR-N1 to MR-N4 of the meeting records plan). Unresolved labels read as Voice N. Noise labels are dropped from the body and listed here. Wording is unchanged; a correction would be listed in `transcript.json`.

## Speakers

| Name | Labels | Share of words | Status | Evidence |
|---|---|---|---|---|
| Hansen | DOWN_01 | 52% | likely | voice match, Legion assigned hansen to 4074 of 4074 words |
| Hash | DOWN_00 | 37% | likely | voice match, Legion assigned hash to 2946 of 2946 words |
| Shawn Anderson | MIC | 11% | named | microphone track (76% of audio on Shawn's microphone) |

## Turns

[00:04] **Hash:** Good morning.  
<sub>seg-0001</sub>

[00:07] **Hansen:** How's it going?  
<sub>seg-0002</sub>

[00:14] **Hash:** Yeah, I slept late. Oh, by the way, I got the Twitter. Yeah, I did. I got the Twitter. So I have everything I need. it's actually easy you go into the developer tools you like you go to the developer tool then the network console and you get that some some ID get some ID hey Hanson how's it going it's going good  
<sub>seg-0003–seg-0008</sub>

[01:10] **Hansen:** Likewise. Apologies, I'm feeling a little bit under the weather right now. I'm gonna have the camera off.  
<sub>seg-0009–seg-0011</sub>

[01:16] **Shawn:** Yeah, no problem. Yeah. I've been working with Hash for about three years, I think, and for the first two years, he never turned his camera on.  
<sub>seg-0012–seg-0014</sub>

[01:28] **Hansen:** Fair enough.  
<sub>seg-0015</sub>

[01:31] **Hash:** Yeah, it's like literally morning for me, so I'm still in the bed.  
<sub>seg-0016</sub>

[01:37] **Hansen:** All good.  
<sub>seg-0017</sub>

[01:37] **Hash:** That's right.  
<sub>seg-0018</sub>

[01:39] **Hansen:** Thanks for making the time work.  
<sub>seg-0019</sub>

[01:43] **Hash:** Cool.  
<sub>seg-0020</sub>

[01:45] **Shawn:** Hash, do you want to kick it off?  
<sub>seg-0021</sub>

[01:46] **Hansen:** Hello?  
<sub>seg-0022</sub>

[01:57] **Shawn:** Hash, are you there?  
<sub>seg-0023</sub>

[01:57] **Hash:** Yeah, yeah, yeah.  
<sub>seg-0024</sub>

[02:00] **Hansen:** Sorry. I got a little bit.  
<sub>seg-0025–seg-0026</sub>

[02:04] **Hash:** So yeah, I mean, we could start with a little introduction. I'm Hash, he's Shawn, and we are from Bonding Curve Research Group. We are a complex systems engineering firm. We have been working with Avalanche for the past one, one and a half years now. And over the years, our trajectory kind of started with the composition of the entire system. into subsystems and components and trying to build the digital twin for Avalanche but over the past one year after The Economist came our focus shifted from like it narrowed down to the validator staking and delegator economics and that's where we are and for today's call the reason for today's call is that the reason is that Avalanche's inflation rate or a large minting rate has doesn't really have hasn't really changed ever so we couldn't really get the market regime and we don't really know what the validator sensitivity towards towards the you know different reward rate is so we are doing we are soliciting information from validators or people who have informational knowledge about the avalanche ecosystem to get you know get information about the parameters, so we could put them in the sort of in our model to get a better like know make it better and get better answers and predictions so yeah did I miss something Sean or you want to add something to it.  
<sub>seg-0027–seg-0034</sub>

[03:29] **Shawn:** sort of in our model to get a better like know make it better and get better answers and predictions so yeah did I miss something Shawn or do you want to add something to it uh oh yeah um yeah sure thanks Hash So yeah, we've been maintaining, we use this library, it's called CAD CAD, it's Complex Adaptive Dynamics Computer Aided Design. And it was created by a firm called Block Science, which has renamed to Dynamical Systems Group. But essentially, it's a framework for developing a model based on state what is the state of the model and then the policy the policy functions that determine how that state changes over time so we're using this system to yeah model the sensitivity of validators to basically the the set of open ACPs that are focused on modifying validator rewards or validator duration requirements those kinds of things and yeah so we're interesting interested in modeling validator behavior and how sensitive they are going to be to responding to to these different ACPs that can come in. So we've been doing on chain analysis to sort of like cluster validator behavior. but we also want to supplement that with interviews so we're particularly interested in interviewing validators operators and stakeholders like yourself who just have a lot of information you know you have a lot of experience you know responding to the avalanche economy essentially and so we're just curious to get to know you and your perspective and curious if you would have validators that you know that you would have contacts with that you could connect us with to potentially do interviews and I have here on screen the set of interview questions across eight topics which you can see here which we can talk through but yeah that's I think a general introduction to us and maybe we'll pass it over to you Hanson for a general introduction  
<sub>seg-0035–seg-0045</sub>

[06:16] **Hansen:** Cool. Sounds good. I'm one of the co-founders for Banky. I've been on Avalanche since pre-mainnet, really, working with Avalanche Labs, trying to make the chain work. Yeah, I think I run validators personally for my Avalanche, my own Avalanche stack. Avax stack, sorry. And then, obviously, we have Eslovak as well. I run a few validators on that front. We, but we delegate the majority of the stake to the open network.  
<sub>seg-0046–seg-0054</sub>

[06:51] **Hash:** Yeah.  
<sub>seg-0055</sub>

[06:52] **Hansen:** I'm happy to dig through the questions if you want, but I think it's probably useful to discuss how we do it for SOVAX first, since it's about 10% or 12% of stake. So we primarily—well, in the current state, before the Helicon upgrade, we have been just doing 14 to 18-day stakes delegations because we prioritize liquidity for users. And then we have a mix of some longer-running validators because The churn rate is pretty low. I think it's like 8%, maybe less. For SFX, so we're able to have a lot of our validators, a lot of our state go for many months without issue. I think our largest single on Steam was like \$3 million a box. That was from Avat, and we serviced that with no issues, even though we had like, I don't know, \$60 million a box that was Steam for three months or longer. So yeah, we prioritize liquidity, and we try to have a mix of long-term validators just so we can raise the yield a little bit. But post-Telecon, I think that's a point of big discussion internally and research. We are probably leaning towards just reducing all state towards two days, just because the delta between two-day APR and 14-day APR is in like 20 bits or five bits. I can't remember. It was minimal. So that's sort of what we're thinking through. Hilarious because Eric and Matthias' analysis from the ACPs, they think that valid data will take longer, despite my fervent opposition in the forums. In any case, that's sort of what we're leaning towards. Nothing undecided. If it plays out, it'll probably take months for us to implement And I want to see how I can't please out first before we do anything. Yeah, that's, that's about it. On this side.  
<sub>seg-0056–seg-0077</sub>

[09:35] **Shawn:** Okay, interesting. Um, yeah, do you want to jump in? I know it's early morning early morning, but, um.  
<sub>seg-0078–seg-0080</sub>

[09:41] **Hansen:** And I know it's early morning.  
<sub>seg-0081</sub>

[09:44] **Shawn:** But do you want to comment on that or or drive the questions?  
<sub>seg-0082</sub>

[09:44] **Hash:** Yeah, I have a, I mean, not really a comment, but a question. So, um, So you're talking about ACP 273 how it's gonna bring down the but there's also gonna be a lot of institutional capital that because primarily I feel like ACP 273 is the main reason why they bought it that's like personal but personal opinion is because they want to bring in a lot of institutional capital and liquidity matters more to the institutional capital more than the returns and Since a lot of institutional investors won't have the infrastructure to run, they would probably delegate it.  
<sub>seg-0083–seg-0086</sub>

[10:36] **Hansen:** No, it's probably targeted at ETFs, but the ETFs have their own staking partners that they'll pay to handle. So that's sort of, I mean, it's a pretty well-established business on that front, right, for ETFs. It's E-staking.  
<sub>seg-0087–seg-0089</sub>

[10:52] **Hash:** Is there an E-staking ETF?  
<sub>seg-0090</sub>

[10:53] **Hansen:** But I'm sure there is. Anyway, they have sole-staking ETFs already, and they all just hire. Yeah, people like BlockDaemon and TwinStake or whoever else to stake. So I don't know necessarily whether they'll use SFOX for—it's further out the risk curve to use SFOX. So you would expect greater yield. Mm-hmm. I don't know but that's why we're thinking okay if we if we look if we lower it to two-day stake chances are there should be more participation but I don't know okay and what are the costs of like major costs of like operating a validator  
<sub>seg-0091–seg-0097</sub>

[12:00] **Hash:** Like based on who is running like institutions have different like you use that you run with personally and then there are validators who get delegated to buy like it's different.  
<sub>seg-0098</sub>

[12:11] **Hansen:** Like what's the what's the cost structure like And now we run like five or six validators on our own. I don't know what the amounts are, but it's significantly higher than whatever Avalabs claims. What the running cost is, at least that's what I understand from my engineers. Our AWS and GCP though is a lot higher since before. We don't have any, we haven't had any institutional deals or arrangements. So we haven't had any like SOC2 requirements or anything like that for the values that we run. If that was a requirement, there are plenty of people that we can lean into, like blocky and then twin stake for whoever else to divert stake towards. But that really isn't a consideration for us. I feel like the SFOX conversation here is pretty straightforward. It's like a balance of maximizing yield while being able to make the token liquid Well, what I'm thinking actually is, you know, I mentioned our churn rate, something like five to eight percent. I feel like that might be higher. I feel like the rate of unstaking will increase when we do this. If we do it to, sorry, if we do the unstake, I feel like people will unstake more and they might stake more. I'm not sure.  
<sub>seg-0099–seg-0114</sub>

[13:47] **Hash:** Oh. Okay.  
<sub>seg-0115–seg-0116</sub>

[13:51] **Hansen:** Yeah.  
<sub>seg-0117</sub>

[13:54] **Hash:** And while running these values, what information, what signals do you actually watch for?  
<sub>seg-0118</sub>

[14:01] **Hansen:** What do you mean?  
<sub>seg-0119</sub>

[14:05] **Hash:** like when you have to stake when you have to unstake is it more profitable for you should we go on with like what's the signals like when you started off as a validator like you run it what is it that you want is it a reward is it long-term capital like the opportunity costs like what are the signals  
<sub>seg-0120</sub>

[14:16] **Shawn:** What is it that you want? Like the opportunity costs?  
<sub>seg-0121–seg-0122</sub>

[14:25] **Hansen:** For Essovox, it's straightforward. It's just, I mean, on the personal side, that's an economic decision, right? For the Essovox business side, we just take a skim off the total amount of stake that comes through. So we prioritize increasing Essovox TVL as much as we can, and minimizing costs. Security is an ongoing cost on our end, of course, continuous monitoring, all the javs. Yeah. Yeah, we don't consider opportunity because that's not our, we're just infrastructure. We're just providing a service for takeers for SOBOX. So there's no economic decision on that front. Yeah. We can get into the personal one after we close the book on the SOBOX conversation. I recently heard about that they have an ignite program can you talk a little bit more about the ignite program yeah so ignite the purpose of ignite like we built it because beforehand there was a 2k requirement to run a You needed to validate the primary network alongside your subnet, L1, right? So we were like, okay, teams don't want to run their own — they don't want to commit. At the time, they were like, oh, at least five validators. per subnet. So that's \$10,000 a box. At the time, the box price was like \$10, \$15. That was a considerable amount. We figured people can just rent the steak because we had a lot of steak. So that was sort of  
<sub>seg-0123–seg-0143</sub>

[16:17] **Shawn:** So that was sort of.  
<sub>seg-0144</sub>

[16:19] **Hansen:** The reason for it. And then I think after the Blueberry upgrade, they decided to remove that requirement. Made no difference to L1 uptake anyway. But this sort of killed the business. The value prop on that front. However, in order to access the mempool, you still needed to run the validator. So throughout 2024 and 2025, when on-chain was somewhat spot on C-Chain. There's a lot of MBV front-running. A lot of people want to snipe launches, so we had a few hundred validators on Ignite. People are basically just renting a Vox to print out validators so they could have access to the mempool and do the things they wanted to do. Long story short is people would put in a request, pay the Vox, and we would just take 2000 Vox to the validator for the period that they requested. But we don't see much happening right now for Ignite. Maybe just like a few validators. Maybe six, I think. That's all I saw.  
<sub>seg-0145–seg-0160</sub>

[17:45] **Hash:** Shawn, you wanted to ask something before you cut you off.  
<sub>seg-0161</sub>

[17:45] **Shawn:** Shawn, you wanted to ask, I think, before you've got your data, please. Yeah, one question, Hanson, when you said SLVox is further down the risk curve, what did you mean by that?  
<sub>seg-0162–seg-0163</sub>

[18:01] **Hansen:** Validator, like on the validator side, that's, what's the word? I think that's the risk-free rate for C-chain or for a Vox yield. For on SFX, there's smart contract risk, of course, both held on, yeah, on C-chain, smart contract risk. Although we spent, I think it's proven itself to be durable, touch wood, for the last five years. There's agency risk on our end, of course, on the team side, and also the recharger fee on top. So for all these things, so actually you're, if you're just holding raw as a box, you're getting a worse deal than just depositing it and just taking it in the validator. The upside is that you get to use your stick to box as collateral. So it is more efficient. If you wanted to use as a box, if you wanted to collateralize a box, you might as well use as a box because SFOX is around 4.9% APY. USDC borrows around 5.8% APY right now. So your actual net yield. depending on the volatility of the AVAX price is 1.8% in borrow cost for USDT because your AVAX appreciates and says AVAX versus just holding raw AVAX. So that's more capital efficient. That's one example. So the IT foundation in a lot of whales do it. But the main reason why people use SVOX as they do SDE is to do looping on venue markets. But yeah, that's the reason why people do it. But the markets are super compressed right now. Like, there aren't a lot of loops happening, spare market stuff.  
<sub>seg-0164–seg-0183</sub>

[20:26] **Hash:** yeah are you familiar with ACP 66 I believe stronger there 66 or 67 it's about that uh they wanted native stablecoin for um avalanche uh no I didn't realize that was live oh oh that was by knobs right I don't know who it was, but yeah, there is a proposal that they want to launch a native stablecoin. Not necessarily native stablecoin, but they want to actually capture the value that leaks through. Yes. Yeah, I know.  
<sub>seg-0184–seg-0188</sub>

[21:00] **Hansen:** They've been trying to, similar to what Hyperloop is doing with Circle as an AQA proposal.  
<sub>seg-0189</sub>

[21:08] **Hash:** Yeah.  
<sub>seg-0190</sub>

[21:09] **Hansen:** That's something Foundation's been trying, been working on for a while. I think it makes sense.  
<sub>seg-0191–seg-0192</sub>

[21:17] **Hash:** yeah I think it makes sense yeah we were internally like uh trying doing some research but that's more internal it's like nothing to do with it but we were uh because of the nature of SAVAX we were hoping like the design is novel that Stephen Coyne Design is novel and hasn't been actually tried it's trying to securitizing and tranching and we are using SAVAX as the base layer as the base token rather than AVAX because of obvious reasons you know because it's more stable it gives better API people could use it and we were exploring like more use cases for SAVAX  
<sub>seg-0193–seg-0194</sub>

[21:32] **Shawn:** The same coin design that we are building is novel.  
<sub>seg-0195</sub>

[21:55] **Hash:** and yeah I mean it's still in the research phase I mean we have still in the design phase designing and doing some modeling parameter testing for what the correct configuration of the parameters they're like 40 odd parameters for how to do it and yeah yeah and the token we're using is SAVAX instead of AVAX because you know you have SAVAX and then that kind of if people move out of I mean if you used AVAX it would have like compromised the network security for Avalanche because a lot of people would have moved so it's better to use SAVAX because it's AVAX like its correlated assets and all the benefits that come with the yield and everything with it so yeah I mean I just wanted to put it out there in the universe for the stablecoin design is that the same is this something you've discussed with foundation Matthias no not yet we haven't actually discussed with foundation yet  
<sub>seg-0196–seg-0198</sub>

[22:57] **Hansen:** You should do it ASAP, actually. I think they are coming along on their discussion site with the different stablecoin providers. I don't really understand how SFOX fits in it.  
<sub>seg-0199–seg-0201</sub>

[23:18] **Hash:** Sorry, sorry, you didn't understand how Evox would? What?  
<sub>seg-0202–seg-0203</sub>

[23:22] **Hansen:** Yeah, Evox or Esovox. I don't understand how that would fit into the stablecoin design that you're working on. Is it like a CDP?  
<sub>seg-0204–seg-0206</sub>

[23:27] **Shawn:** Is it like a CEP?  
<sub>seg-0207</sub>

[23:29] **Hash:** Like, can be used as a collateral, right? Like if you have a decentralized on-chain stablecoin...  
<sub>seg-0208–seg-0209</sub>

[23:38] **Hansen:** Right, so it's a CDP.  
<sub>seg-0210</sub>

[23:40] **Hash:** Yeah. Okay. But it's not CDP. Like, technically it's not CDP. It's more like a... So what we do is we take the AVAX or SAVAX we split it we have a like into two tranches one is one one like say class A and class B is the class A would serve as the bond and class B absorbs the volatility then we do another splitting for Class A tokens which where that's where you get the actual stablecoin and then the yield token is there and anytime like that there are reset mechanisms in place uh it's like the design progress but we would like to like discuss further about the stablecoin design with you guys and the thing is that because you will have like with the USDTs and USDCs there will be like a lot of negotiation on what they use and if they give out the yield you know it's also there's a big if because they want yeah but with the design we could have it on chain the rewards could be distributed 100% of the rewards could be distributed I mean it could like completely protocol owned it doesn't have to be that doesn't have to be any negotiation with a third party or a fourth party team so yeah interesting yeah that sounds good I'm happy to discuss more of that Yeah, let's discuss more because right now I think we've been working on it for the past three weeks now, right Shawn? So we will put a white paper out, I mean not a white paper but a research paper out and then we can have like solid state information and some interested parties talk about it but yeah It feels like a, it does feel like doing  
<sub>seg-0211–seg-0221</sub>

[25:29] **Hansen:** A two-day stake is better for that, no? A two-day out of stake.  
<sub>seg-0222–seg-0223</sub>

[25:37] **Hash:** Yeah, I mean, wouldn't that, that will be like good for you guys only. 14 days to reduce to two days, you will have to move. Like how does that impact your business? Like does it really impact your business? How does it change?  
<sub>seg-0224–seg-0228</sub>

[25:49] **Hansen:** I mean, Helicon reduces our revenue by 24 0.3% anyway. So moving into a two-day stake reduces our revenue by 24.6, so it's pretty fucked. But I need to find a way to increase our TVL by a quarter, by 25%, just to get back to where we were before.  
<sub>seg-0229–seg-0232</sub>

[26:15] **Hash:** yeah yeah yeah yeah that's why 66 would be like really in like employ like and you'll be really interested in 66 and like ACP 6 is a stable point because the one thing we are like how we are planning it to do it like we have we want to subsidize the value of the ecosystem with it that was within the proposal somebody like I don't know definitely like off the head of the yeah I know I know the ACP  
<sub>seg-0233</sub>

[26:35] **Shawn:** I don't know I just like that it's 67 ACP 67 discussion yeah I know I know the ACP  
<sub>seg-0234</sub>

[26:44] **Hash:** yeah so they were discussing like we will go 15% somewhere 60% somewhere like that was a distribution but without actually testing like the configuration and putting it through tests we cannot really decide on like these are just numbers you know somebody wants to get 60% but is it feasible to actually give 60% so we are like on that route now but the idea is basically to use the revenue and subsidize validators and I mean I think my comment in the my comment in the ACP 285 discussion was around the same thing that the revenues that the stakeholder or the banky or the treehouse their revenues are going to get reduced because of ACP 285 and depending on the shape of the curve we could actually save everybody like we could actually get all the like We could actually address the concerns of all the stakeholders and parties, but we will have to shift or change the shape of the curve.  
<sub>seg-0235–seg-0237</sub>

[27:46] **Hansen:** For? Oh, yes. Yes. But yeah, I mean, Headcon is going live regardless. Like AvaLabs and Foundation kind of didn't care what we said.  
<sub>seg-0238–seg-0242</sub>

[27:57] **Hash:** Yeah. I don't know, man.  
<sub>seg-0243–seg-0244</sub>

[28:06] **Hansen:** Yeah, so much governance. Yeah, I mean, please put the proposal through, like, the change of the curve. I mean, I saw the comments and were supportive of it. It's just I don't think they even—I don't know. I don't know, man.  
<sub>seg-0245–seg-0249</sub>

[28:21] **Hash:** I mean the foundation did ask us for a much easier brief on this we did provide them and they were like interested in how you're doing it I said like you know we are changing the shape of the curve it's like we go we take it up because the because when you move the minimum consumption rate you kind of wreck the car business the 14 day business that LSTs have a banky has so you move up and then you have a like a hump shape curve and you then you drop and you also address the inflation with it you also address the long term staking with it and the business model the 14 day looping will also be safe but they were not really interested in the 14 days they were like okay so what you know if it happens it happens yeah yeah  
<sub>seg-0250–seg-0251</sub>

[29:09] **Hansen:** Is there a net reduction in issuance?  
<sub>seg-0252</sub>

[29:12] **Hash:** There is a net reduction. Yes, there is a net reduction in issuance.  
<sub>seg-0253–seg-0254</sub>

[29:21] **Hansen:** Let me know how the discussion continues with them on that front.  
<sub>seg-0255</sub>

[29:25] **Hash:** Oh, the discussion is like done. I mean, we are not discussing that anymore with them. That was like, I think two months ago, right? Two or like one, one and a half months ago. We were discussing about it and the information, the model, and they were like, no.  
<sub>seg-0256–seg-0260</sub>

[29:44] **Hansen:** Was there a—what's the word? Was there a—was the technical implementation more complicated?  
<sub>seg-0261–seg-0262</sub>

[29:58] **Hash:** uh technical formation more complicated yeah it was it was slightly more complicated because the curve wasn't a smooth linear it was normally a curve the technical accommodation was a little more complicated yeah yeah yeah but then like i tried to make it as technically feasible as i could with keeping all the stakeholders in mind but they still thought it's technically too complicated uh so we'll run into some overflow issues and whatnot like okay your 100 engineers can't figure it out it's not rocket science they just don't have the you just don't have the entity to do it yeah i mean i after that i also gave another proposal like you know that but they wanted it internally they were like oh they were like a little furious about that i shared it in the public and which was more or less similar to how you'd what you had proposed a kinked curve piecewise linear kink yeah it was similar to that but that also in a way I mean it gave on the inflation front it protected the inflation it protected the business and there was some other objective that it did fairly good on but I felt like they're not really interested in anything else I mean they wanted to do what they wanted to do yeah they decided a long time ago it's all right well it's their chain  
<sub>seg-0263–seg-0265</sub>

[31:28] **Hansen:** So okay well let's continue the discussion on the stablecoin beast I think that's really interesting I think it's definitely novel yeah let's continue yeah absolutely Shawn do you have any other questions from the for the for the digital twin  
<sub>seg-0266</sub>

[31:55] **Shawn:** Um, yeah, I guess this, uh, question, um, 6.1 here, um, can you imagine a scenario where you would make the choice to invest more in validator infrastructure?  
<sub>seg-0267</sub>

[32:10] **Hansen:** I don't know, man. Like, well, it's pretty straightforward validating on C-Chain. Oh, P-Chain, sorry. So I don't think it's like, I don't think it's a big consideration, like, if we have to… Yeah, I don't know. Like, investing more is an interesting question. if the business requires it, I guess. Or, as a box, no. If we have to invest in validators in whichever form, be it cloud or physical, in order to run, to serve, the eagle for stakers and you have me do it. Personally, as a personal validator, if I could run it on a toaster, I would. Yeah. I mean, we also have a continue. We also do things for us. Martin, in January, he wanted us to do it. There was a gas target they tried to get to on C-chains and they need an X amount of the state to run the latest version of Avalanche GO. So they asked us to ensure that we ran validators that did that. So we did that. So things like that. It kind of depends on what the network requires. Yeah. Personally, I'm just, like, my personal advice, six years of opportunity cost aside, I just try and get the yield. I pay the least amount that I can.  
<sub>seg-0268–seg-0289</sub>

[34:21] **Shawn:** So with your personal AVOX, what kind of commitment durations do you go for?  
<sub>seg-0290</sub>

[34:32] **Hansen:** Good question. I used to do monthly, but I'm going to do fortnightly. It's because I want the yield. I prioritize liquidity now. um I think during periods of increased volatility to the upside I lower or might not even stake at all yeah I don't know. Sell the box, buy something else. That's the main one. Although I've not done that. I sell the yield for sure. Yeah. I need to sell the yield. Although I might sell the principal or some of the principal now. yeah are there any validators you would like to get us in touch with who are more you know yeah I don't actually know that many validators actually I don't know many people that hold a box anymore other than the 22 million that we have in stake um but I don't actually personally I don't know many validators I think most most of us holders have sort of um turned out yes yeah so state comes in the we have uh we have a combination of bots that analyze available equipment available delegation capacity on chain validators of whatever gap time is um what their stake duration is, how much stake they have, and then we delegate to them accordingly.  
<sub>seg-0291–seg-0306</sub>

[37:10] **Hash:** So validators are, I think validate is above a certain stake.  
<sub>seg-0307</sub>

[37:17] **Hansen:** I think it's like 8,000 or something. I can't remember what we have in the docs. 8,000 of docs receive and receive stake because statistically they have good uptime. That's how we do delegations.  
<sub>seg-0308–seg-0311</sub>

[37:34] **Hash:** Yeah, I think it's the 4X for whatever the stake you have, right? A thousand or two thousand stakes. Yeah, yeah.  
<sub>seg-0312–seg-0314</sub>

[37:41] **Hansen:** Yeah, no, yes. I'm just talking about the requirements to receive a Vox from Benke as deviations. Okay.  
<sub>seg-0315–seg-0317</sub>

[37:49] **Shawn:** Okay.  
<sub>seg-0318</sub>

[37:51] **Hash:** Yeah.  
<sub>seg-0319</sub>

[37:53] **Hansen:** Okay.  
<sub>seg-0320</sub>

[37:54] **Hash:** and does it change if like we wanted to play with that parameter of making I think it was some it was Jack's proposal to increase from 4 to 24 and basically 24 I love I love that yeah so increasing the delegation increasing capacity is great increasing the capacity yeah increasing capacity of delegators yeah  
<sub>seg-0321</sub>

[38:24] **Hansen:** Yeah, it's great. Why not? Why are we artificially limited to 4X? The whole idea of skin in the game. I don't know. I feel like the 4X multiple is overly restrictive.  
<sub>seg-0322–seg-0327</sub>

[38:43] **Hash:** Shawn, what were our results on increasing the... Did we see it from the data? How did the people respond to... Do you remember?  
<sub>seg-0328–seg-0329</sub>

[38:52] **Shawn:** uh yeah I don't have those numbers on hand yeah the increase yeah we were modeling increasing the delegation capacity and um Well, most most nodes aren't at capacity. So the yeah, the impact in our model was was low, but it still might be just a preference, you know, since you're sort of expressing that Henson. Yeah, it's almost more of like a democratic process, right? Like skin in the game, like you said. Yeah.  
<sub>seg-0330–seg-0335</sub>

[39:29] **Hansen:** Yeah. That was the pushback. They were like, oh, why increase it when most validators are empty? I'm like, I can hate the use. It's so lazy. I'm like, dude, King's dying. Just try something, okay? Like, just increase the capacity and maybe validate, like I was arguing in there, like if you increase the capacity, validators will be more interested in sales promotion and there will be more, you have the incentive to do so. But if you want to find proof, I'm like, how must someone prove a negative? It's definitely better for Banky, like, if a validator, like, so we have, so Banky has a product, a feature called vQi. Basically, if you hold, if you stake your Qi, you have a pro rata share, pro rata vote of where delegations can go to. So, for example, yeah, if you own 1% of VG votes, you could direct 1% of a share of SMOX delegations to your chosen node. So as it stands right now, only whales, SMOX whales, can benefit, right? Because Yeah, if you want to fill out your validator, you need, I don't know, like \$300K a Vox, and then you can have, let's say \$100K a Vox, you can have \$400K a Vox delegated to your node, and that's some amount of delegation fees that you can charge on a large amount of stake. But, you know, if it's 24x, someone with \$10,000 a Vox, can suddenly command that amount of stake, that amount of delegations that's beneficial for Banky. And all of a sudden you could have all these, what's the word? Yeah, all these validators, like smaller validators, not just large validators that are motivated to self-promote. So yeah. But obviously they didn't care.  
<sub>seg-0336–seg-0356</sub>

[41:56] **Hash:** Yeah, it could go either way. You could have like the retailers or the small validators winning the game and like trying to really promote themselves and because they want to get more delegators or you could like have entire concentration within these big nodes. But since 93% of all the delegations come through Banky, is that right?  
<sub>seg-0357–seg-0359</sub>

[42:19] **Hansen:** Yes, but that's because we chose to do delegations, right? We could have just ran—like, to be clear, when you do delegations, we leak revenue to all these validators because, you know, we delegate to validators to charge a minimum of 2% to 5%. So we leak revenue. Let me try and find out how much we lose a year. I think it's like \$300K. Give me a second, I have to… As it stands, we leak \$270,000 to validators a year. Like, we could actually, like, I don't, we don't spend, we wouldn't… I'd be hard-pressed to spend a quarter of a million dollars on validators on C-Chain, running it ourselves, right? The idea was that we wanted to give back. We wanted to help out the network. It's like one we love between you and the network.  
<sub>seg-0360–seg-0369</sub>

[43:52] **Hash:** It's all right. Yeah.  
<sub>seg-0370–seg-0371</sub>

[44:02] **Hansen:** Has this been the most interesting conversation around validators that you've had so far?  
<sub>seg-0372</sub>

[44:08] **Shawn:** this this is our first this is our first the foundation we've been trying to get a list of validators from them for months and then finally they're like okay we don't really know many validators they're like but you got to talk to Hanson we're like okay so this is our this is our first I don't know many validators either I think I'm representative of on the personal side I think I'm representative of most  
<sub>seg-0373</sub>

[44:27] **Hansen:** I don't know many validators either. I think I'm representative of, on the personal side, I think I'm representative of most. Like, after the press action that we've seen over the years, and we're still holding a box right now. Like, I'm the only person, I think, that holds a box that I know. Like, I think I'm representative of a lot. Yeah. As a casual validator, yeah, I'm just looking at the yield that I take every few weeks to a month and hope there's some capital appreciation through the cycle for the principal, but that's it.  
<sub>seg-0374–seg-0380</sub>

[45:23] **Hash:** So you are also preferring liquidity over the yield?  
<sub>seg-0381</sub>

[45:33] **Hansen:** Yeah, yeah. I mean, look, the co-founders for AVAX, for Avalanche, they do four-week validation as well. So, yes.  
<sub>seg-0382–seg-0384</sub>

[45:55] **Hash:** and what would have to change like how big of the spread should it be for you to stay longer so for example 365 days staking how much yield would you want other spread between month and 365 no bro what's the what's the what's the t-bill rate for for 12 months now  
<sub>seg-0385</sub>

[46:23] **Hansen:** I think it's still 5% higher, I guess. Yeah, I guess I want 10% or 12%. Okay. Whatever I want, they have served.  
<sub>seg-0386–seg-0389</sub>

[46:34] **Hash:** So it has to be a lot. Okay. Okay. Yeah, that kind of… Yeah.  
<sub>seg-0390–seg-0393</sub>

[46:39] **Hansen:** I mean, we're talking about junk emerging market bonds right now. Like we should be… Look at their box volatility.  
<sub>seg-0394–seg-0395</sub>

[46:50] **Hash:** Hmm.  
<sub>seg-0396</sub>

[46:53] **Hansen:** Yeah. Whatever they want, they can't serve. Like you can only justify a low inflation rate if the parent asset, if the asset is good. So how many are there? Solana, they can afford discussing reducing inflation. Ethereum, talking about having zero. And Hyperliquid then always had two. yeah so so hybrid always has two percent inflation as in like it's hardcoded uh yes it's always been I've always had an attitude I've always only been seeing two percent since genesis if I was able to delegate validate so delegate sorry yeah and then also like  
<sub>seg-0397–seg-0404</sub>

[47:47] **Hash:** I mean, there is certainly interest or direction towards moving from issuance-based to activity-based on Avalanche. Like, they haven't really done anything yet, but they would... Yeah, see, they say that. And I'm like, bro, if that happens, then they will disappear.  
<sub>seg-0405–seg-0407</sub>

[48:04] **Hansen:** Because you're talking about wanting to... wanting to fix the supply side when there is a demand side issue. Yeah. So I, I, the, but the thing is they can't do anything on the demand side. They're just focusing on the supply side. And I'm like, ah, I don't know, man. It's, I don't think touching, I, I, I don't think See, that's why the stable client idea is a good idea. I don't think doing—I don't think trying to reduce inflation now, reduce emissions now makes any sense, because people will just leave. Why would I stay? If I'm—if I'm—if you goes to 2%, I might as well sell everything and just hold hype.  
<sub>seg-0408–seg-0417</sub>

[48:57] **Hash:** Yeah. Yeah, that kind of makes sense. Why would you—  
<sub>seg-0418–seg-0420</sub>

[49:06] **Hansen:** and like entire economy is based on the issue that shows based on why would somebody anybody care yeah and it's fine to have emissions I think it's fine to have emissions I think having it's better to like have the stablecoin yield supplement this then the other way around you know  
<sub>seg-0421</sub>

[49:36] **Hash:** There's a lot of, I mean stablecoin is just but one idea and apparently it's like half of the value and that's like off the top calculation you don't you're not really looking at the leakage through L1s and there's no revenue sharing value capture at the L1s and like it just on top of like off top of my head it's like 12 million dollars of values like that's what value is created and 6.5 million is captured by it's lost to USDT, USDCs and these finance and all that yeah so it's like 50%. I mean even if you decide on like say for example you launch your own latest stablecoin you get 100% of the yield on that you can have or maybe 80% of the captures like you still make a additional two three million dollars on on that. Then again, you have to work on the demand side. Like this is an interesting idea. Great idea. That's why we are working on it.  
<sub>seg-0422–seg-0429</sub>

[50:41] **Hansen:** But yeah, we'll see.  
<sub>seg-0430</sub>

[50:43] **Hash:** We'll see. We can conclude the stablecoin discussion further, like, away from the data side, like that for separate discussion. By the way, are you coming to the summit?  
<sub>seg-0431–seg-0433</sub>

[50:53] **Hansen:** I will not. I'll be at Token in Singapore. Dan, my co-founder, will be at Summit. So you can hit him up.  
<sub>seg-0434–seg-0437</sub>

[51:02] **Hash:** Yeah. Be good to get in touch with them and talk about stuff.  
<sub>seg-0438–seg-0439</sub>

[51:08] **Hansen:** I'm curious. How are you, I mean, why are you proposing to like build a common good stablecoin product for the chain? How does that benefit you?  
<sub>seg-0440–seg-0442</sub>

[51:22] **Hash:** I mean we were hoping to actually not run the not go into the industry side of things and actually run the chain but actually sell the idea like you know sell the startup once we have built it we sell it to Emacs and just be done with it okay because running a business is like I mean we already have so much trouble running this one and we are like a three four five member operation imagine now we are running a stable coin and then oh you could just sell it off  
<sub>seg-0443</sub>

[51:52] **Hansen:** Fair enough. Fair enough. Yeah.  
<sub>seg-0444–seg-0446</sub>

[51:58] **Hash:** How are things on the business side? How do you manage your team?  
<sub>seg-0447–seg-0448</sub>

[52:01] **Shawn:** How big is your team?  
<sub>seg-0449</sub>

[52:02] **Hash:** How do you manage it?  
<sub>seg-0450</sub>

[52:04] **Hansen:** It's like an eight-person team. Same team we've had for years. It's pretty laser-fair, really. Everyone's an adult. Everyone gets paid a decent wage. And yeah, it's been, it's been all right on our end.  
<sub>seg-0451–seg-0456</sub>

[52:20] **Shawn:** and yeah it's been it's been all right on our end they had a good fortune of launching at the right time and sort of just been living off that since but yeah are you diversifying across different projects beyond the AVAX ecosystem is there yeah you mentioned Hyperliquid so do you do you run other operations outside of Avalanche?  
<sub>seg-0457</sub>

[52:24] **Hansen:** They had a good fortune of launching at the right time and sort of just been living off that since. But yeah.  
<sub>seg-0458–seg-0459</sub>

[52:37] **Hash:** And what's  
<sub>seg-0460</sub>

[52:51] **Hansen:** No, I, I mean, I don't run it. Like I, the, the working hours is all on, on Banky. Um, but whether I pay attention and I'm in conversations with different teams and talking to everyone. Yeah, I am. Um, yes.  
<sub>seg-0461–seg-0465</sub>

[53:12] **Hash:** And what are your current priorities? Like, do you plan on moving to other chains or do you have one of the Avalanche?  
<sub>seg-0466–seg-0467</sub>

[53:22] **Hansen:** On Banky, they're not moving anywhere. Honestly, the lending market and the LST is fairly time-consuming. because we have to continually harden on the security side, especially for the LST. And, you know, you see all these lending markets getting hacked over the last 10 days. Yeah, I mean, we had the foresight to prevent all these economic exploits years ago. But, you know, it's still stressful to see. every other marginal lending protocol dropped like flies. Yeah. Yeah, DeFi is in a tough spot, I think. Small DeFi is in a tough spot. I think Morpho, Ave, large teams are okay, but less so far. Less so far smaller teams.  
<sub>seg-0468–seg-0479</sub>

[54:36] **Hash:** Yeah. And what architecture do you use for like the lending markets? What's your architecture, lending market architecture?  
<sub>seg-0480–seg-0482</sub>

[54:49] **Hansen:** Compound V 2.1. I call it 2.1 but Compound.  
<sub>seg-0483–seg-0484</sub>

[54:52] **Hash:** Uh-huh.  
<sub>seg-0485</sub>

[54:55] **Hansen:** Yeah. It's been alright. Compound has these issues that we have a handle on it.  
<sub>seg-0486–seg-0488</sub>

[55:08] **Hash:** and he all gotten pretty used to now compound like you're gonna grip on.  
<sub>seg-0489</sub>

[55:13] **Hansen:** Yeah. Yeah. Yeah. Fortunately.  
<sub>seg-0490–seg-0493</sub>

[55:18] **Hash:** Yeah. Thank you. Any other questions? Do you have any questions Sean?  
<sub>seg-0494–seg-0497</sub>

[55:27] **Shawn:** Do you have any questions, Shawn? Would you be interested in automatic renewal?  
<sub>seg-0498–seg-0499</sub>

[55:43] **Hansen:** Isn't that something that they're implementing in Helicon?  
<sub>seg-0500</sub>

[55:47] **Shawn:** It might be, yeah. The team's been discussing it. I'm not sure if it's in Helicon, but it very well might be.  
<sub>seg-0501–seg-0503</sub>

[55:54] **Hansen:** Yeah, it is autostake, dude. I think I've worked with, like, three different engineers on it, on AvaLabs over the, what, three past two or three years? Yeah, I mean, it's good if they implement it. It's more useful for the ETFs, because if you do two-day stake, then you'd want to, yeah.  
<sub>seg-0504–seg-0507</sub>

[56:22] **Hash:** I mean, it doesn't really have direct economical building, but it reduces the overhead that kind of helps in the churn and everything. It will increase the validability. I mean, not the direct impact on, oh, this is going to move the levers in such a way that the inflation is going to drop and, you know, validators are going to stay more and blah, blah, blah, nothing like that. It just obviously drops and that kind of, it's more behavioral than economical.  
<sub>seg-0508–seg-0511</sub>

[56:47] **Hansen:** Yeah. Yeah, I agree.  
<sub>seg-0512–seg-0513</sub>

[56:50] **Hash:** Yeah.  
<sub>seg-0514</sub>

[56:51] **Shawn:** Hanson, I do have a question, which is, is your co-founder, Dan, is he also a validator?  
<sub>seg-0515</sub>

[57:00] **Hansen:** I don't think anymore. I'm pretty sure he sold all his box. Lucky bastard. It's a tough spot, man, because I spent a lot of time talking to other teams and other Yeah, other operating teams and other chains, other DeFi protocols. I think Avalanche has gone through a lot of flux over the last few years. I think they could have executed better, but they weren't able to for whatever reason. The only upside is that they have a very professional team on the BD side, and that house is really good. A lot of people on Wall Street like them. and they are a very clean business to work with. There's a reason why, out of many, many options, Charles Schwab did choose a Vox, 20 ETFs for a Vox. I think as a token, it's fine, but it's not perfect. And I feel like when you're a startup, when you're in crypto, when it's so competitive, when it's both public, it's a tough spot. Like, if Avalanche were able to create a compelling product, you know, something on the demand side, I think we'll rip. But I don't see where that's coming, where that's going to come from, because whatever talent that exists in crypto is on other chains. Hmm. Necessarily so because like all the eyes are on the other chains, right? Is AvaLabs willing to build anything internally to do it? I don't know. I don't know whether they have the chops to do it. But they have a lot of money. Their treasury is in the billions. So… They will outlast everyone if need be. They will fire their engineers if need be to survive. So, yeah, I mean, you could imagine a scenario where they strike gold in some way and then just takes off like near. or whatever else. But there's still a strong focus on being a general-purpose chain, and it just doesn't feel like that's where we're going, right? I don't know, man. This is all just low-level mid-curve takes from me. I'm still holding on. That's why I still have hopium. That's why I'm still holding on to the same last bag I've had for years.  
<sub>seg-0516–seg-0548</sub>

[1:00:24] **Hash:** Yeah, late to the party is fine, but I don't know whether the team… I don't know. I don't know.  
<sub>seg-0549–seg-0550</sub>

[1:00:51] **Hansen:** like a program for incubating meme coins and you know investing in the meme coins and whatnot and then the trend ends and they're left with bag of order yeah yeah that was yeah i mean that was another thing i was actually talking to a friend about it yesterday and i was like uh was it actually good that they had the meme coin mania Like did that, we just leaked so much money into the into the market, maybe because otherwise the foundation were defeated anyway, I might as well just put it through to the community.  
<sub>seg-0551–seg-0552</sub>

[1:01:29] **Hash:** I do know why everybody from the past one year we didn't really meet anybody because there was nobody on the team. Like for the entire year we didn't meet anybody and we just kept getting bills like we used to send invoices and they used to send us the money and we didn't really meet and nobody really checked what we did we didn't have conversations it was basically free money last year I mean that's good right just keep charging them more like what was the deal with the foundation why did everybody left do you know about it  
<sub>seg-0553–seg-0554</sub>

[1:02:08] **Hansen:** Ah, I don't know, man.  
<sub>seg-0555</sub>

[1:02:08] **Shawn:** I don't know man that's uh that's the conversation over a lot of beers and a lot of tequila um well I look forward to meeting Dan I'm gonna be at the summit um so maybe you you could add if you want you could add him into our group chat or connect me um with him yeah let me see yeah could you share the  
<sub>seg-0556</sub>

[1:02:10] **Hansen:** That's the conversation over a lot of beers and a lot of tequila. Yeah, let me see. Yeah, could you share the… What is the name of our chat? B-G-R-C B-C-R-G Let me add Dan  
<sub>seg-0557–seg-0561</sub>

[1:02:49] **Shawn:** Hash, do you have it? Ah, yeah.  
<sub>seg-0562–seg-0563</sub>

[1:03:08] **Hansen:** I want to kick out Daniel. Can you guys ask Daniel to transfer transfer ownership to one of you guys and then kick him out?  
<sub>seg-0564–seg-0565</sub>

[1:03:26] **Shawn:** Sure.  
<sub>seg-0566</sub>

[1:03:26] **Hansen:** Like the foundation Daniel, sorry.  
<sub>seg-0567</sub>

[1:03:28] **Shawn:** Oh, yeah.  
<sub>seg-0568</sub>

[1:03:34] **Hansen:** Okay, cool. Sorry, guys. I do have to run. Whatever things you want to discuss or ask, just send in the chat. I think the validator side is pretty straightforward. Let's continue talking about the stablecoin side. I do want to see what we can do there. Whatever that's built on SLX. Absolutely. All right. Yeah, don't worry.  
<sub>seg-0569–seg-0579</sub>

[1:04:04] **Hash:** See you guys.  
<sub>seg-0580</sub>

[1:04:04] **Shawn:** Yeah. Take care. Bye. Bye. All right. Nice, bro. We interviewed the one validator. The only validator.  
<sub>seg-0581–seg-0588</sub>

[1:04:18] **Hash:** Take care.  
<sub>seg-0589</sub>

[1:04:20] **Shawn:** We interviewed 100% of the validators.  
<sub>seg-0590</sub>

[1:04:24] **Hash:** The only guy we're going to interview is this guy, and he's not even a validator.  
<sub>seg-0591</sub>

[1:04:33] **Hansen:** Wow.  
<sub>seg-0592</sub>

[1:04:34] **Hash:** Oh my God. Did I tell you I go for cold plunges every morning? Oh yeah, I was supposed to actually leave like half an hour ago, but it's okay. Wait, did I send you the picture? Hold on, I should send you the picture, the video, video, video, video, no, it's, check this out. Oh my God.  
<sub>seg-0593–seg-0599</sub>

[1:04:58] **Hansen:** You're gonna love it. Yeah.  
<sub>seg-0600–seg-0601</sub>

[1:05:05] **Hash:** Take it out. Yeah.  
<sub>seg-0602–seg-0603</sub>

