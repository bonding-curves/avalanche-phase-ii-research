---
title: Reproduce the report's central result
description: "Rebuild the reported 50-pair one-year comparison, its percentile table and trajectory figure."
kind: tutorial
reader: "An Avalanche researcher checking the reported model result"
question: "Can the reported reward-saving and stake-retention result be reproduced from obtainable inputs?"
---

The [reproduction guide](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/report-reproduction/README.md) downloads a checked 12.1 MB input bundle, runs the original tagged model and rebuilds the reported central comparison. It uses 50 paired one-year runs from 18 November 2025. Every pair shares its original fitted-parameter draw and simulation seed.

| Paired quantity | 10th percentile | Median | 90th percentile |
| --- | ---: | ---: | ---: |
| Validator reward promises saved | 11.5968% | 12.7721% | 15.3888% |
| Validator own stake retained | 95.3483% | 98.6901% | 99.9003% |
| Active validators retained | 96.0306% | 96.9785% | 97.6430% |

The alternative starts ACP-285's ramp earlier. The reference follows the historical schedule, adopting ACP-285 at Helicon. Both use working renewal and entry responses of 0.025 and 0.04, with 5% annual outside yield. These percentiles summarize simulated pairs under those settings. They are not confidence intervals for a causal effect.

![Rebuilt central-case panels showing validator own stake, active validator count and supply under the historical schedule and earlier ramp.](/Phase-II/Wiki/Reproduce/central-case.png)

*The original three panels are rebuilt from reproduced paths and the pre-origin record. Supply adds validator reward promises to initial ledger supply and subtracts fixed burn, omitting delegated issuance. [SVG](/Phase-II/Wiki/Reproduce/central-case.svg), [plotted values](/Phase-II/Wiki/Reproduce/central-case-figure-data.csv), [paired summary](/Phase-II/Wiki/Reproduce/central-case-comparison.csv) and [figure provenance](/Phase-II/Wiki/Reproduce/central-case-figure-provenance.json).*

All 36,600 daily rows reproduce, including 183,000 integer quantities checked exactly. The compact inputs produce the same preparation and initial model state as the full pinned data. The original execution-time driver remains unidentified. The newly frozen replay records its own code, inputs and environment, and checks numerical equivalence. It performs no forecast evaluation or new response estimation. The guide states the full checks and limits.
