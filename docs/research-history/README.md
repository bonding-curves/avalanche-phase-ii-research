# Research History

The staking research developed from an aggregate adjustment model into a simulation of individual validator commitments. Earlier plans and results explain the questions and assumptions behind that change. The archival editions below preserve their original text and figures, with brief context linking them to the October explanations.

## May and June research

Dates identify the event the source establishes. Creation dates locate a source in the journal. They do not establish submission or acceptance. All three editions come from an export labelled 1 July 2026, and retain their recorded edit times.

| Date and basis | Original entry | Kind | Interpretation |
| --- | --- | --- | --- |
| 1 May 2026, source creation | [Detailed Work Plan](detailed-work-plan.md) | Work plan | Proposed response functions, validation targets and handoff. The implemented model and tests subsequently changed |
| 21 May 2026, source creation | [Qualitative Calibration & Stakeholder Interviews](qualitative-calibration.md) | Methods note | Proposed interviews to understand operational constraints. The note contains no completed interview evidence |
| 5 June 2026, date in body | [Tier-1 Results & Notebook Series — Meeting Prep 2026-06-05](tier-1-june-5.md) | Meeting brief | Early model 0.3.2 results with an uncalibrated response. The recovered version was edited through 1 July |

## October explanations

The [modeling memo](../review/2026-10-30/modeling.md) explains model v0.8.0 and separates observed behaviour, assumed responses and reward arithmetic. The [evidence guide](../review/2026-10-30/evidence.md) identifies its experiments and reproduction requirements. The [results memo](../review/2026-10-30/results.md) reports the corresponding comparisons as a draft for review.

## Source fidelity

Each edition includes the exported Markdown as a text download. The reading edition preserves wording and equations, changes heading depth, metadata line breaks and local image routes, and lists earlier repository-file URLs as historical references. All twelve figures are retained without image edits. The [source manifest](assets/content/Phase%20II/Wiki/Research%20History/manifest.json) records the page identities, original byte hashes, dates and figure hashes.

Verify the retained bytes and the reading editions from the repository root:

```sh
python scripts/research_history.py
python scripts/research_history.py --export --check
```

The first command checks the original text, source metadata, displayed historical body and figure files. The second also checks the GitHub reading copies. These checks establish fidelity to the recovered sources. Scientific interpretation remains specific to each model and experiment.

This first collection covers three entries. The complete reporting history from May onward is still being recovered.
