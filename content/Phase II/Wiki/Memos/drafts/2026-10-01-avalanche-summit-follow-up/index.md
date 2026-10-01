---
title: "2026-10-01-avalanche-summit-follow-up"
description: "What the Avalanche Summit's stage sessions imply for staking: security that issuance cannot fund for ever, a steeper duration curve, and ETFs that need part of their AVAX liquid within 48 hours."
date: 2026-10-01
status: draft
deliverables: ["1.4", "2.8"]
tags: ["staking-duration-and-liquidity", "validator-economics", "mechanism-design"]
---

# The Summit points the model at three things: revenue-funded security, longer commitments, and ETF liquidity

## Finding

Three messages from the Summit's stage sessions bear on the staking model. The Foundation's economics keynote argued that no chain's security is sustainable on issuance alone, and named paying validators from revenue as a way to bring inflation toward zero. The Helicon panel said the old incentive for longer staking was not carefully designed, and that the upgrade aims to push commitments longer. Speakers on both stages tied Helicon's 48-hour minimum to exchange-traded funds, which must keep part of their AVAX redeemable within two days.

Each message is a speaker's view, which the model turns into something it can test. Below are the sessions they come from, what we take from them for the model, and the next steps.

## The sessions

We captured the full public agenda: 69 items over two days, of which 53 are talks and panels, with 124 distinct speakers. We recorded the sessions below on stage. Quotations come from our machine transcripts, and each time counts from the start of our recording.

**The Economics of Avalanche**, the Foundation's keynote by Matias A., 16 September. "No chain finds its security sustainable. Full stop. No layer one." (51:36). Later: "What if you were to pay the validators? Bring inflation to zero. That's another way." (1:03:03). In the same passage he described steepening the reward curve so that validators stay longer, and tied the 48-hour minimum to ETFs' liquidity requirements.

**Inside Helicon: The Thinking Behind the Upgrade**, with Martin Eckardt, Stephen Buttolph, and Arran Schlosberg of Ava Labs, 17 September. Commitments can now run "anything between 48 hours and one year" (5:55:15). An ETF with a 48-hour redemption period cannot stake all the AVAX it holds (5:55:41). On the old design: "the original design on the incentivizing longer staking was definitely not incredibly deeply thought through" (5:57:07). Stakers are "pretty aggressive on having a short-term staking duration", and the upgrade aims at "pushing that out" (5:58:06).

**What Comes After the ETF?**, with 21Shares, Bitwise, and Grayscale, moderated by Finality Capital, 16 September. A panellist described the ETF as packaging institutional custody, liquidity, and staking into one product, and expected more capital to stay off-chain, held through ETFs (29:06, 34:40).

**Follow the Flows: Where Institutional Capital Is Moving**, with Kraken, Coinbase, and L1D, 17 September. One panellist said pension funds were the only new capital they saw in the last 18 months, and that such investors commit when "there's revenue there's an asset that captures those revenues" (4:52:14, 4:55:45).

## What it means for the model

This is our reading, not the speakers' claims.

1. **Revenue-funded rewards belong in the mechanism set.** The model compares mechanisms where captured revenue replaces part of issuance. The keynote makes that the Foundation's own question. In the year to 20 September, stakers were paid about 13.06 million AVAX, while fees burned were about 0.31 million AVAX, so revenue today covers a small fraction of what issuance pays.
2. **Duration is now a real choice, and its response can be measured.** Helicon lets each commitment choose its length and changes the reward for doing so. The weeks after 22 September give the first data on how strongly stakers respond to the duration reward, which the model treats as unknown until then.
3. **An ETF is two pools.** A fund that must redeem within 48 hours keeps a liquid reserve at the minimum duration and stakes a core for longer. The model represents ETF issuers as named operators with that structure, not as many independent delegators.
4. **Few large holders decide more of the stake.** As staking reaches investors through ETFs and custodians, decisions concentrate in a few holders with fixed policies. Concentration is one of the measures every mechanism is scored on.

## Next steps

1. **The institutional staking panel.** "Beyond Yield: The Institutional Case for Staking", with Josh Deems of Figment, Konstantin Richter of Blockdaemon, Pete Wylie of AVAX One, and Matias A., is the session closest to our questions on institutional stakers. We add it when its recording is published, and the keynote's summary of it, that "staking is a very difficult business to be in", sets the questions we take to those operators.
2. **Treasury companies.** "Built for Business", with the Avalanche Treasury Co., and "Institutions Are Here" follow with the same recordings.
3. **Exact quotations.** We check each quotation above against the audio, and the Foundation's slides would let us quote the keynote from its own text.
4. **Liquid staking and auto-renewal.** Our own data covers these directly: the BENQI memo in this set and the Helicon memo measure them on chain.

## For you

On 25 September you offered to follow up with Matias on two things: introductions to the operators on the institutional staking panel, and the Summit slides for the economics keynote and the Helicon panel. Is either available yet? The keynote slides would let us quote the Foundation's position from its own text rather than from our transcript.
