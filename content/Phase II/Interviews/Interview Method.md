---
title: "Validator interview method"
description: "Participant selection, neutral questions, permissions, source handling, and corroboration for staking interviews."
date: 2026-10-01
---

The interviews explain staking decisions that the chain can record but cannot explain by itself. Their output is a set of traceable, testable hypotheses about duration, renewal, delegation, entry, and exit. Chain data test the observed actions. A single interview supplies neither population preferences nor calibrated response parameters.

This page sets out participant selection, interview conduct, source handling, corroboration, and interpretation. It distinguishes the proposed research method from what has been completed. The [BENQI analysis](/Phase-II/Interviews/BENQI-2026-08-31/Analysis) is the first published application.

## Research strategy and selection

Use semi-structured framework analysis: ask a consistent set of core questions, probe neutrally for definitions and examples, and allow new topics to emerge. The unit is a participant's account of a defined operation and decision. Hansen's product operation and personal AVAX holdings must be distinguished even though one person discussed both.

The method specifies purposive maximum-variation sampling. Select participants to expose different constraints, rather than estimate a representative average. The intended groups include independent operators, institutional custodians and staking services, liquid staking pool operators, and protocol or treasury operators. Record scale, self-stake, delegation exposure, business objective, permitted geography or regulatory context, and experience of upgrades. Record who introduced the participant and why the case was selected.

| Selection purpose | Comparison it supports |
| --- | --- |
| Independent operators across self-stake and operating-cost levels | Personal liquidity, yield, cost, and break-even constraints |
| Institutional or staking-service operators | Client mandates, custody, compliance, operational friction, and liquidity requirements |
| Liquid staking operators | Product redemptions, allocation rules, fee revenue, and governance direction |
| Protocol or treasury operators | Capital dedicated to network participation and objectives beyond immediate yield |
| Contrasting duration, renewal, and upgrade responses within these groups | Cases that challenge the first explanation rather than repeat it |

These are selection dimensions, not an approved quota or a list of already recruited people. Referral sampling may improve access, but referrals can share incentives and networks. Keep that recruitment path visible in the evidence record. Do not use interview frequency to assign agent-type weights.

### The completed BENQI case

The BENQI source records one interview on August 31, 2026, lasting approximately 65 minutes. At 06:16, Hansen describes personal validators and a liquid staking operation. At 44:08, the interviewer describes the Foundation's recommendation to speak to him. The introduction at 05:01 to 06:15 describes interviews as a supplement to on-chain analysis. This supports the rationale for an information-rich first case. It does not establish that the participant was selected through the later maximum-variation protocol or represents casual validators generally.

The interview predates the written method of September 13. At 05:50, the interviewer says an eight-topic question set is on screen, but the preserved source does not establish that its wording matches the later survey. The analysis therefore applies the topic framework retrospectively, without claiming prior protocol approval.

## Question spine and interview conduct

The open questions preserve the participant's reasoning. The survey is a separate, approximately five-minute instrument with 12 questions. It can gather standardized descriptions and identify follow-up participants, but a 65-minute exploratory interview should not be described as a completed survey response.

| Topic | Neutral question | Model question |
| --- | --- | --- |
| Profile and objective | What operation do you run, whose capital is involved, and what objective governs your staking decisions? | Which decision maker and objective does an agent represent? |
| Costs, revenue, viability | Which costs and revenue sources determine whether validation remains viable? | What could cause entry, expansion, contraction, or exit? |
| Duration, renewal, liquidity | How do you choose duration and renewal timing, and what prevents shorter or longer commitments? | Which choices are preferences, operational limits, or liquidity constraints? |
| Reward response | How would reward levels or curve shapes affect stake, duration, renewal, expansion, or exit? | Which competing response mechanisms should be tested? |
| Delegation and competition | How do demand, fees, capacity, liquid staking tokens, and institutional capital affect your decisions? | How is stake allocated among feasible alternatives? |
| Markets and outside options | How do price, volatility, external yields, and other uses of capital change decisions? | Which market effects need separation from protocol effects? |
| Protocol change and security | How do upgrades affect risk, confidence, decentralization, and security? | What changes across regimes, and when is a choice feasible? |
| Scenarios and measurement | What would make you expand, reduce, exit, or reconfigure, and what should be monitored? | Which observables can support or contradict a proposed behavior? |

Researchers should review wording before use. For each material number, ask for its unit, denominator, time window, whether it is an estimate or observation, and an example or source. Distinguish a hypothetical policy response from a completed action. When the same person has personal and business roles, name the role in the follow-up.

The survey needs that review before new deployment. Its duration choices begin at two weeks, while its Helicon question mentions 48 hours without separating validator and delegator roles. Its capacity question includes a below-2% fee option that needs feasibility review. Its stated outside-option yields are time-sensitive. These issues need resolution before field use. The survey has not been deployed as part of this analysis.

The BENQI conversation also explores an interviewer-proposed stablecoin. Code that material as interviewer context and participant reaction. Agreement with a proposed mechanism is not an independent observation of its effects. Preserve contradictory evidence, such as a liquidity preference alongside a longer validator mix, rather than reduce the account to one binary preference.

## Consent, access, and delivery

The proposed survey describes confidential responses reported in aggregated or anonymized research. That language does not establish consent for a separate named interview or for delivery of its full transcript. The BENQI analysis and this method page were approved for publication on October 1, 2026. The full transcript remains withheld pending Hansen's consent.

For each interview, record the participant's choices for recording, transcription, internal analysis, attribution, quotation, sharing with the Foundation, and public publication. Keep scope and recipients explicit. Record attribution preferences and any limits or withdrawal request. An invitation to continue chatting is not permission to deliver the full interview.

Raw recordings, identifying details and full transcripts require their own access and delivery decisions. Published pages should include only the permitted evidence, with the source and interpretation limits retained. Permission to share and scientific confidence in an interpretation are separate records.

## How a statement becomes evidence

| Step | Required record and work | Failure or limitation to retain |
| --- | --- | --- |
| 1 | Interview ID, date, protocol version, selection rationale, interviewer, consent state, access class, and attribution preference | Use `unknown` or `unrecorded`, rather than infer permission or historical protocol approval. |
| 2 | Preserve source bytes and hashes, recording provenance, transcript version, speaker state, and review coverage | A recorded hash is not audio verification. BENQI has zero seconds of recorded audio review. |
| 3 | Segment by speaker and meaning with IDs, start/end times, exact wording, and source locators | Machine speaker assignments and mixed turns stay visibly uncertain. |
| 4 | Apply multiple topic or emergent codes with analyst, interpretation, and uncertainty | Do not force one code per segment or convert an interviewer proposition into participant evidence. |
| 5 | Draft a participant-by-topic response with supporting and contradicting segments | An empty cell states `not_asked`, `no_answer`, `ambiguous`, or `restricted`. |
| 6 | Run a named corroboration check where possible, retaining dataset version, hash, window, weighting, query, and result | Separate `checked`, `partly_checked`, `not_checked`, and `not_chain_checkable`. A failed match is not proof the participant lied. |
| 7 | Second-review material or disputed interpretations, with method review and recorded adjudication | Preserve the original claim and correction history. A source quote alone does not validate a causal interpretation. |
| 8 | Connect reviewed evidence to a hypothesis, observable, competing explanation, and model-input status | No claim becomes a parameter without an identification method and supporting data. |
| 9 | Obtain the recorded delivery decision and generate only the permitted projection | Keep scientific review and participant delivery permission distinct. |

The [BENQI analysis](/Phase-II/Interviews/BENQI-2026-08-31/Analysis) is a manual claim map under this sequence. It provides elapsed-time quotations and a reproducible chain-check recipe. A reviewed response matrix and fitted behavior parameters remain further work.

The proposed evidence records are `participant`, `interview`, `topic_question`, `segment`, `coding_assertion`, `response`, `embedding`, and `review`. A response record is authoritative for the eventual participant-by-topic matrix. Preserve sources and interpretation separately so a corrected speaker or wording can be recoded without losing the earlier decision.

Use exact filters and full-text search first. The method proposes embeddings only after a reviewed retrieval fixture proves a specific improvement. Cosine similarity means retrieval relevance, not truth, agreement, sentiment, importance, or prevalence. The BENQI analysis uses manual source review and SQL checks.

## Completed work and next evidence

| Date | Completed work and evidence boundary |
| --- | --- |
| 2026-08-31 | BENQI interview, approximately 65 minutes. The historical protocol version is unconfirmed. |
| 2026-09-13 | Written participant-selection and eight-topic method recorded after the interview. |
| 2026-09-24 | Full 603-segment machine transcript exported, with zero seconds of recorded audio review. |
| 2026-09-30 | Interview analysis checked against source segments and selected delegation, duration, stake and attribution extracts. |
| 2026-10-01 | Analysis and method approved for publication. Full transcript delivery remains pending participant consent. |

Before further interviews, review participant selection, wording, probes, coding and permissions. Then construct the participant-by-topic response matrix, keeping source locators, contradictory evidence and missingness visible. Evaluate retrieval tools only against reviewed examples. Connect supported claims to competing behavior hypotheses and identify which additional observations could distinguish them.

The BENQI case still needs audio and speaker review, clarification of ambiguous units and rates, confirmed address ownership, and product-flow and cost records. Population weights require a broader sample and an explicit identification method. Neither a structural data check nor a participant's forecast establishes a causal response coefficient.
