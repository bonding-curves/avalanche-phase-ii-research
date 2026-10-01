---
title: "Validator interview process strategy and method"
description: "Private draft of participant selection, the eight-topic question spine, consent, evidence handling, and the sourced interview schedule."
date: 2026-09-30
status: draft
owner: project-manager
interview_id: mh-2026-08-31-benqi-liquid-staking-interview
---

# Validator interview process strategy and method

The interviews explain staking decisions that the chain can record but cannot explain by itself. Their output is a set of traceable, testable hypotheses about duration, renewal, delegation, entry, and exit. Chain data test the observed actions. A single interview supplies neither population preferences nor calibrated response parameters.

This private `I3` draft follows the September 30 modeling request at 18:40. Its method comes from the September 13 collaborator and interview plan. Its survey wording comes from the accompanying survey protocol. Those documents contain proposed gates and historical state, not proof that all approvals or activities occurred. Shawn's current authorization covers preparation of these drafts, not participant consent or client publication.

## Research strategy and selection

Use semi-structured framework analysis: ask a consistent set of core questions, probe neutrally for definitions and examples, and allow new topics to emerge. The unit is a participant's account of a defined operation and decision. Hansen's product operation and personal AVAX holdings must be distinguished even though one person discussed both.

The plan specifies purposive maximum-variation sampling. Select participants to expose different constraints, rather than estimate a representative average. The intended groups include independent operators, institutional custodians and staking services, liquid staking pool operators, and protocol or treasury operators. Record scale, self-stake, delegation exposure, business objective, permitted geography or regulatory context, and experience of upgrades. Record who introduced the participant and why the case was selected.

| ID | Selection purpose | Comparison it supports |
| --- | --- | --- |
| `S1` | Independent operators across self-stake and operating-cost levels | Personal liquidity, yield, cost, and break-even constraints |
| `S2` | Institutional or staking-service operators | Client mandates, custody, compliance, operational friction, and liquidity requirements |
| `S3` | Liquid staking operators | Product redemptions, allocation rules, fee revenue, and governance direction |
| `S4` | Protocol or treasury operators | Capital dedicated to network participation and objectives beyond immediate yield |
| `S5` | Contrasting duration, renewal, and upgrade responses within these groups | Cases that challenge the first explanation rather than repeat it |

These are selection dimensions, not an approved quota or a list of already recruited people. Referral sampling may improve access, but referrals can share incentives and networks. Keep that recruitment path visible in the evidence record. Do not use interview frequency to assign agent-type weights.

### The completed BENQI case

The [transcript](/Phase-II/Interviews/BENQI-2026-08-31/transcript) records one interview on August 31, 2026. At [06:16](/Phase-II/Interviews/BENQI-2026-08-31/transcript#turns), Hansen describes personal validators and a liquid staking operation. Shawn describes the Foundation's recommendation to speak to him in `seg-0373`, beginning at 44:08, and describes interviews as a supplement to on-chain analysis in `seg-0042` to `seg-0045` at 05:01 to 06:15. This supports the rationale for an information-rich first case. It does not prove that the participant was selected through the later maximum-variation protocol or represents casual validators generally.

The interview predates the September 13 written plan. Shawn says an eight-topic question set is on screen at 05:50 (`seg-0045`), but the source package does not establish that its wording or version matches the later survey. Treat `VT1` to `VT8` in the analysis as retrospective topic codes. Do not backdate approval of protocol `0.1.0`.

## Question spine and interview conduct

The plan's open questions preserve the participant's reasoning. The survey is a separate, approximately five-minute instrument with 12 questions. It can gather standardized descriptions and identify follow-up participants, but a 65-minute exploratory interview should not be described as a completed survey response.

| Code | Topic | Neutral question | Model question |
| --- | --- | --- | --- |
| `VT1` | Profile and objective | What operation do you run, whose capital is involved, and what objective governs your staking decisions? | Which decision maker and objective does an agent represent? |
| `VT2` | Costs, revenue, viability | Which costs and revenue sources determine whether validation remains viable? | What could cause entry, expansion, contraction, or exit? |
| `VT3` | Duration, renewal, liquidity | How do you choose duration and renewal timing, and what prevents shorter or longer commitments? | Which choices are preferences, operational limits, or liquidity constraints? |
| `VT4` | Reward response | How would reward levels or curve shapes affect stake, duration, renewal, expansion, or exit? | Which competing response mechanisms should be tested? |
| `VT5` | Delegation and competition | How do demand, fees, capacity, liquid staking tokens, and institutional capital affect your decisions? | How is stake allocated among feasible alternatives? |
| `VT6` | Markets and outside options | How do price, volatility, external yields, and other uses of capital change decisions? | Which market effects need separation from protocol effects? |
| `VT7` | Protocol change and security | How do upgrades affect risk, confidence, decentralization, and security? | What changes across regimes, and when is a choice feasible? |
| `VT8` | Scenarios and measurement | What would make you expand, reduce, exit, or reconfigure, and what should be monitored? | Which observables can support or contradict a proposed behavior? |

The plan assigns wording review to Hash and Shawn before use. For each material number, ask for its unit, denominator, time window, whether it is an estimate or observation, and an example or source. Distinguish a hypothetical policy response from a completed action. When the same person has personal and business roles, name the role in the follow-up.

The survey needs that review before new deployment. Its duration choices begin at two weeks, while its Helicon question mentions 48 hours without separating validator and delegator roles. Its capacity question includes a below-2% fee option that needs feasibility review. Its stated outside-option yields are time-sensitive. Those are instrument-review findings, not approved corrections to the source file. No form was created or changed for this draft.

The BENQI conversation also explores an interviewer-proposed stablecoin. Code that material as interviewer context and participant reaction. Agreement with a proposed mechanism is not an independent observation of its effects. Preserve contradictory evidence, such as a liquidity preference alongside a longer validator mix, rather than reduce the account to one binary preference.

## Consent, access, and delivery

The survey promises confidential responses reported only in aggregated or anonymized research. That statement is proposed participant-facing language. It does not record consent for the August 31 conversation or authorize named quotation. The source package documents a recording and machine transcript, but no consent record for Foundation delivery. The September 30 `I1` request assigns the account owner to seek permission through the appropriate contact. It remains separate from preparing `I2` and `I3`.

Before further collection or delivery, record the participant's choices for recording, transcription, internal analysis, attribution, quotation, sharing with the Foundation, and public publication. Keep scope and recipients explicit. Record attribution preferences and any limits or withdrawal request. An invitation to continue chatting or discuss the stablecoin is not permission to deliver the full interview.

Hash leads field coordination and method interpretation. Jeff leads editorial interpretation. Shawn directs the research and decides promotion. Agents prepare bounded evidence maps, checks, and drafts. This draft has no participant approval, scientific approval, or promotion decision attached to it. Raw recordings, identifying details, transcripts, and operational claims remain restricted. A client projection must carry only evidence whose delivery scope has been recorded and whose interpretation has been reviewed.

## How a statement becomes evidence

| Step | Required record and work | Failure or limitation to retain |
| --- | --- | --- |
| `P1` | Interview ID, date, protocol version, selection rationale, interviewer, consent state, access class, and attribution preference | Use `unknown` or `unrecorded`, rather than infer permission or historical protocol approval. |
| `P2` | Preserve source bytes and hashes, recording provenance, transcript version, speaker state, and review coverage | A recorded hash is not audio verification. BENQI has zero seconds of recorded audio review. |
| `P3` | Segment by speaker and meaning with IDs, start/end times, exact wording, and source locators | Machine speaker assignments and mixed turns stay visibly uncertain. |
| `P4` | Apply multiple `VT` or emergent codes with analyst, interpretation, and uncertainty | Do not force one code per segment or convert an interviewer proposition into participant evidence. |
| `P5` | Draft a participant-by-topic response with supporting and contradicting segments | An empty cell states `not_asked`, `no_answer`, `ambiguous`, or `restricted`. |
| `P6` | Run a named corroboration check where possible, retaining dataset, run, hash, window, weighting, query, and result | Separate `checked`, `partly_checked`, `not_checked`, and `not_chain_checkable`. A failed match is not proof the participant lied. |
| `P7` | Second-review material or disputed interpretations, with Hash's method review and recorded adjudication | Preserve the original claim and correction history. A source quote alone does not validate a causal interpretation. |
| `P8` | Connect reviewed evidence to a hypothesis, observable, competing explanation, and model-input status | No claim becomes a parameter without an identification method and supporting data. |
| `P9` | Obtain the recorded delivery decision and generate only the permitted projection | Keep scientific review and participant delivery permission distinct. |

The [analysis draft](/Phase-II/Interviews/BENQI-2026-08-31/analysis-draft) is a first manual claim map under this sequence. It provides exact segment references and a reproducible chain-check recipe. It is not a completed canonical response database, an accepted coding matrix, or the proposed notebook research node.

The plan's canonical records are `participant`, `interview`, `topic_question`, `segment`, `coding_assertion`, `response`, `embedding`, and `review`. A response record is authoritative for the eventual participant-by-topic matrix. Preserve sources and interpretation separately so a corrected speaker or wording can be recoded without losing the earlier decision.

Use exact filters and full-text search first. The plan proposes embeddings only after a reviewed retrieval fixture proves a specific improvement. Cosine similarity means retrieval relevance, not truth, agreement, sentiment, importance, or prevalence. No embedding or heatmap was produced here.

## Schedule and current evidence state

The plan specifies an ordered sequence rather than interview quotas or calendar deadlines. Only the dated work and current D2 deadline below are established by the cited records. Later stages have no authorized completion dates in those sources.

| ID | Date or order | Recorded work and current boundary | Source |
| --- | --- | --- | --- |
| `T1` | 2026-08-31, 19:00:42 America/New_York | BENQI interview held, approximately 65 minutes. Consent and historical protocol version remain unrecorded. | `transcript.json`, source and coverage fields |
| `T2` | 2026-09-13 | Collaboration and eight-topic research plan recorded. Its protocol and interview-node completion boxes remain open. | Interview plan |
| `T3` | 2026-09-24, 14:02:23 UTC | Full 603-segment source export recorded, with machine transcript and zero audio review. | `transcript.json`, processing and coverage fields |
| `T4` | 2026-09-30, 18:40 PDT | Shawn's D2 preparation decision relayed. Account owns `I1` permission, PM owns `I2` analysis and `I3` method. | Modeling thread |
| `T5` | Due 2026-10-01, 12:00 PDT | Private `I2` and `I3` drafts ready for the PM's integration and review. Deadline covers drafts, not consent or publication. | Same D2 request |
| `T6` | Next, `CV3` then `CV4` | Reconcile source, identity, consent, and review states. Hash and Shawn review selection, wording, probes, coding, and claims boundaries before new outreach. | Interview plan's execution sequence |
| `T7` | Then `CV5` and `CV6` | Backfill canonical responses, then produce the first EDA and Reproduction slice with traceable cells and reviewed missingness. No date set. | Same sequence |
| `T8` | Then `CV7` and `CV8` | Evaluate retrieval and encode supported competing behavior hypotheses. Keep weights and coefficients outside interview-frequency inference. No date set. | Same sequence |
| `T9` | `CV9`, after review and permission | Jeff prepares a permitted client explanation, Hash checks interpretation, and Shawn decides promotion before scaling the corpus. No date set. | Same sequence and D2 private-draft boundary |

The plan's earlier onboarding phases `CV0` to `CV2` concern repository access and collaboration, not interview consent. Their completion cannot close `CV3` or validate the research method. `I1` proceeds through the account owner, and drafting does not send an outreach message.

## Acceptance and remaining evidence

| ID | Evidence needed | Current draft state |
| --- | --- | --- |
| `A1` | Identified source and segment-level traceability | BENQI export located. Analysis references exact JSON segments. Audio and uncertain speaker labels remain unreviewed. |
| `A2` | Recorded consent and delivery scope | Unrecorded for named quotation or Foundation transcript delivery. Account owns `I1`. |
| `A3` | Protocol version and method review | Historical version unconfirmed. Later plan and survey provide the proposed spine, with corrections still needed. |
| `A4` | Checked claims with defined denominators and snapshot times | Analysis independently reproduces selected address counts, durations, and stake shares. Other claims remain untested. |
| `A5` | Reviewed responses and model-input rationale | Draft hypotheses and limitations supplied. No accepted matrix or fitted behavior parameter. |
| `A6` | Approved client projection | No promotion decision recorded for these drafts. They stay beside the private interview sources. |

The next review should resolve evidence and interpretation at those boundaries. It should not convert a structural check, a participant's forecast, or one information-rich case into a completed scientific finding.
