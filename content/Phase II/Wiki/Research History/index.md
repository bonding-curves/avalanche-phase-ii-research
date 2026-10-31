---
title: Research History
description: "Earlier staking research with dated sources and links to the October explanations."
kind: research-history
reader: "Avalanche Foundation and Ava Labs researchers"
question: "How did the staking research develop and which explanations should a reader use?"
---

The staking research developed from an aggregate adjustment model into a simulation of individual validator commitments. Earlier plans and results explain the questions and assumptions behind that change. The records below distinguish preserved originals, redacted editions and a metadata record, with context linking them to the October explanations.

## May and June research

Dates identify the event the source establishes. Creation dates locate a source in the journal. They do not establish submission or acceptance. All eight records come from an export labelled 1 July 2026 and retain their recorded edit times.

| Date and basis | Original entry | Kind | Interpretation |
| --- | --- | --- | --- |
| 1 May 2026, source creation | [Detailed Work Plan](/Phase-II/Wiki/Memos/historical/detailed-work-plan/) | Work plan | Proposed response functions, validation targets and handoff. The implemented model and tests subsequently changed |
| 1 May 2026, source creation | [Data Access Setup](/Phase-II/Wiki/Memos/historical/data-access-setup/) | Research update | Redacted access record. Historical source coverage and calibration claims require separate checks |
| 2 May 2026, source creation | [Milestone 1 Foundation](/Phase-II/Wiki/Memos/historical/milestone-1-foundation/) | Research update | Redacted draft claiming calibration and simulation capacity, with no supporting artifacts in the source |
| 17 May 2026, source creation | [Research Methodological Pivot](/Phase-II/Wiki/Memos/historical/methodological-pivot/) | Methods note | Proposed archetypes and extensions, distinct from the released statistical decisions |
| 21 May 2026, source creation | [Qualitative Calibration & Stakeholder Interviews](/Phase-II/Wiki/Memos/historical/qualitative-calibration/) | Methods note | Proposed interviews to understand operational constraints. The note contains no completed interview evidence |
| 21 May 2026, source creation | [Behavioral Modeling and Dynamical Transitions in Token Staking Markets](/Phase-II/Wiki/Memos/historical/behavioral-transitions/) | Metadata record | Original audience was the internal team. Its body is excluded from this client collection |
| 22 May 2026, source creation | [Data Access Follow-up](/Phase-II/Wiki/Memos/historical/data-access-follow-up/) | Research update | Redacted source narrative retaining the disclosed cumulative, constant and zero-exit approximations |
| 5 June 2026, date in body | [Tier-1 Results & Notebook Series — Meeting Prep 2026-06-05](/Phase-II/Wiki/Briefs/historical/tier-1-june-5/) | Meeting brief | Early model 0.3.2 results with an uncalibrated response. The recovered version was edited through 1 July |

## October explanations

The [modeling memo](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/methodology) explains model v0.8.0 and separates observed behaviour, assumed responses and reward arithmetic. The [evidence guide](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/evidence) identifies its experiments and reproduction requirements. The [results memo](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results) reports the corresponding comparisons as a draft for review.

## Source fidelity

Four entries include unchanged exported Markdown as text downloads. Three include redacted text with visible omission markers. One is a metadata record with no source body. The reading editions adjust heading depth, metadata line breaks, image routes, currency escapes and unavailable historical links. All twelve figures remain unchanged. The [source manifest](/Phase-II/Wiki/Research-History/manifest.json) distinguishes original hashes from redacted-text hashes and records dates and figure identities.

Verify the retained bytes and the reading editions from the repository root:

```sh
python scripts/research_history.py
python scripts/research_history.py --export --check
```

The first command checks delivered source text, source metadata, displayed historical bodies and figure files, distinguishing original, redacted and metadata-only records. The second also checks the GitHub reading copies. Original checks establish byte fidelity. Redacted checks establish consistency with the supplied redacted edition. Metadata records make no claim to supply a verified source body. Scientific interpretation remains specific to each model and experiment.

This collection accounts for all eight entries in the recovered July journal export. Later journal entries and the complete reporting history from May onward are still being recovered.
