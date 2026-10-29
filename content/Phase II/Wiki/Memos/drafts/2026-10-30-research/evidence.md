---
title: "Evidence and reproduction"
description: "Numerical evidence, source identities and reproduction requirements for the two research memos and meeting brief."
date: 2026-10-29
status: draft
kind: reference
reader: "Researchers checking the accompanying memos"
question: "Which calculations and sources support the reported findings, and what is needed to repeat them?"
---

The numerical exhibits below support the [methodology memo](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/methodology), [Sensitivity Analysis Report](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/results) and [meeting brief](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/brief). The package includes the aggregate values, regression output tables and figure bytes used for review. Repeating the full simulations additionally requires the historical input snapshots.

## Central case

The central result uses model v0.8.0, origin 18 November 2025, horizon 365 days, a 90-day ramp to a 7.5% minimum consumption rate, renewal response 0.025, entry response 0.04 and an annual outside yield of 5%. Each of 50 design runs shares its seed and fitted-parameter draw with its chain-rule twin.

The twin follows the historical protocol schedule. ACP-285 starts on day 308, and its 90-day ramp ends after the one-year horizon. The proposed design begins its ramp on the origin. These results describe an early-start comparison.

| Paired quantity | 10th percentile | Median | 90th percentile |
| --- | ---: | ---: | ---: |
| Validator issuance saved | 11.5968% | 12.7721% | 15.3888% |
| Validator own stake retained | 95.3483% | 98.6901% | 99.9003% |
| Active validators retained | 96.0306% | 96.9785% | 97.6430% |

The summaries are percentiles of per-pair ratios. Dividing the median of one set of absolute trajectories by another median gives a different statistic.

The [numerical evidence JSON](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/numerical-evidence.json) records the producing code commit, input identities and original result hash. The central trajectory artifact has SHA-256 d7a2a2db3e52fc16446252f80e9e41e006a82383e4d0406e0730bdc65cf18e7f. It is 7,087,697 bytes.

## Conditional goal regions

The following counts come from the independent A and B blocks of the first ramp sweep at 365 days. The bands include their lower boundary and exclude the upper boundary. All four outside yields, 3%, 5%, 7% and 10% annually, are pooled.

The near-central window uses renewal response 0.01–0.04 and entry response 0.02–0.06, inclusive. The wider window uses renewal response 0.01–0.06 and leaves entry unrestricted within the original 0–0.1 range.

| Response window | Minimum consumption rate | All-goal passes | Runs | Pass share |
| --- | --- | ---: | ---: | ---: |
| Near central | 5.0%–5.5% | 0 | 54 | 0.0% |
| Near central | 5.5%–6.0% | 0 | 53 | 0.0% |
| Near central | 6.0%–6.5% | 7 | 50 | 14.0% |
| Near central | 6.5%–7.0% | 26 | 42 | 61.9% |
| Near central | 7.0%–7.5% | 38 | 47 | 80.9% |
| Near central | 7.5%–8.0% | 48 | 54 | 88.9% |
| Near central | 8.0%–8.5% | 43 | 46 | 93.5% |
| Near central | 8.5%–9.0% | 46 | 49 | 93.9% |
| Near central | 9.0%–9.5% | 51 | 52 | 98.1% |
| Near central | 9.5%–10.0% | 29 | 48 | 60.4% |
| Wider renewal | 5.0%–5.5% | 0 | 200 | 0.0% |
| Wider renewal | 5.5%–6.0% | 1 | 211 | 0.5% |
| Wider renewal | 6.0%–6.5% | 20 | 207 | 9.7% |
| Wider renewal | 6.5%–7.0% | 71 | 199 | 35.7% |
| Wider renewal | 7.0%–7.5% | 115 | 206 | 55.8% |
| Wider renewal | 7.5%–8.0% | 140 | 206 | 68.0% |
| Wider renewal | 8.0%–8.5% | 176 | 209 | 84.2% |
| Wider renewal | 8.5%–9.0% | 183 | 202 | 90.6% |
| Wider renewal | 9.0%–9.5% | 188 | 201 | 93.5% |
| Wider renewal | 9.5%–10.0% | 137 | 209 | 65.6% |

The alternative band from 7.25% to below 7.75% passes in 41 of 49 near-central runs, or 83.7%, and 131 of 207 wider-window runs, or 63.3%. That centered band is different from the half-point band beginning at 7.5%.

These are sample proportions under the original five-goal specification. The result does not assign probabilities to which response coefficient is correct. Each sample retains its own denominator.

The JSON includes the integer counts for every individual goal as well as the all-goal count. Its source utility artifact has SHA-256 88abb18296b1ffc1e35fd12a74baefd2d1425f4c3fe92ecc4f5d88666baac1b6. The stored scoring configuration identifies its inputs but omits the producing code commit. The package preserves that missing identity explicitly rather than inferring it from a later checkout.

## Response estimates

The central responses are working settings informed by preliminary analysis of historical dollar rewards. They are separate from the lifecycle probabilities fitted for each simulation origin.

| Quantity | Working setting or alternative | Interpretation |
| --- | --- | --- |
| Renewal response | Central 0.025 | Change in renewal log-odds per percentage point of annual yield on a 30-day reference stake |
| Entry response | Central 0.04 | Change in the log arrival rate on the same basis |
| Renewal with Bitcoin controls | About 0.035–0.057 | Sensitivity to controlling for broader market movements |
| Renewal with Ether controls | About 0.09–0.11 | Further specification sensitivity, partly above the original sweep |
| Renewal working range | About 0.01–0.06 | A specification-dependent exploration range, not a confidence interval |

Renewal regressions use 51,707 decisions by 7,216 nodes across 62 months, all before 19 November 2025. Entry regressions use monthly first-ever validator counts. The main identification assumption is that dollar rewards changed through price in a way that informs responses to changes in annual reward yield. Shared market sentiment is a competing explanation.

The [renewal regression output](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/renewal-regressions.csv), [entry output](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/entry-regressions.csv), [renewal market controls](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/renewal-market-controls.csv) and [entry market controls](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/entry-market-controls.csv) retain the original coefficient units, specification labels and intervals. A log-price coefficient is not a model response coefficient. Translating between them requires a reference yield and the stated price-to-reward assumption. The rounded working settings should therefore be read as scenario anchors informed by this evidence, rather than precisely identified structural parameters.

## Development forecasts

The [forecast summary CSV](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/forecast-summary.csv) is copied unchanged from the committed model-selection results. The source [provenance](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/results/model-v0.8.0-selection/provenance.json) records the input pin, producing source identity, environment and output hashes.

| Horizon | Origins | Model stake CRPS | Best benchmark | Relative reduction |
| --- | ---: | ---: | ---: | ---: |
| 30 days | 19 | 4.41 | 5.38 | About 18% |
| 90 days | 18 | 5.15 | 5.69 | About 9% |
| 180 days | 17 | 5.54 | 7.54 | 26.6% |

The release's forecast label in the CSV is v0.8-a stake return u. Scores use 200 runs per forecast origin and are scaled by the mean absolute daily change before that origin. Coverage of the nominal 80% stake interval is 57.9%, 55.6% and 82.4% at the three horizons.

The 180-day improvement has a one-sided corrected p-value of approximately 0.0397 in the reported Diebold-Mariano comparison. It is evidence about development forecasts. It is not a completed held-back evaluation or direct validation of reward-policy effects.

## Post-Helicon observations

The brief's descriptive quantities use the P-Chain record through 26 October 2026, as documented in the [existing data brief](/Phase-II/Wiki/Briefs/2026-10-30-milestone-2/). Their populations and windows differ from those of the simulation experiments.

| Observation | Definition |
| --- | --- |
| Own stake 170.26 million AVAX and 590 validators | Closing active validator population on 26 October |
| Own stake up 4.27 million AVAX | Difference from the Helicon-day close |
| Short commitments at 26%–27% of weekly new commitments | Validator commitments lasting 48 hours to under seven days, weeks in 6–26 October |
| Short commitments at 0.33% of AVAX-days | Their share of committed capital multiplied by duration among post-Helicon starts |
| Renewal 86.2% after Helicon | 320 nodes ending from Helicon to 12 October, with fourteen days of follow-up |
| Renewal 85.6% before Helicon | 1,235 endings in the preceding 90 days, with the same fourteen-day definition |

These observations establish changes in the recorded population. They do not identify which changes were caused by Helicon or ACP-285.

## Source identities

The economic interpretation follows ACP-285's stated objectives. The simulation methods follow the released implementation and its development evidence.

| Source | Use |
| --- | --- |
| [ACP-285 at its recorded revision](https://github.com/avalanche-foundation/ACPs/blob/b80ea34682b419603f0241f114560dea5d61e03a/ACPs/285-reduce-minimum-consumption-rate/README.md) | Objectives, consumption-rate change and ramp |
| [Helicon upgrade documentation](https://docs.avax.network/docs/primary-network/helicon-upgrade) | Activation and validator-duration changes |
| [Model v0.8.0](https://github.com/AVL-Foundation/ext-bcrg-validator-research/tree/model-v0.8.0) | Release commit b18a4a2f0ad2d995a6ab30c8438ff19f446dcfdc |
| [Model-selection results](https://github.com/AVL-Foundation/ext-bcrg-validator-research/tree/model-v0.8.0/results/model-v0.8.0-selection) | Development forecasts and adoption verdict |
| [Gneiting and Raftery 2007](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf) | Proper scoring rules and CRPS |
| [Grant agreement](/Phase-II/Milestones/Milestone-0/Signed-Grant-Agreement) | The eight Milestone 2 deliverables |

The [figure manifest](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/assets/figure-manifest.json) identifies the reused image bytes. The [goal-utility manifest](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/reward-rule-comparisons/assets/figure-sources.json) records the frozen aggregates used for the detailed and summary heatmaps. The central trajectory figure omits delegated issuance. The trade-off plot separates the original response sweep from the fixed working-response case. Its black marker represents simulated outcomes under preliminary settings.

## Notation

The methodology defines each symbol beside its first use. This register collects the meanings and units for reference.

| Symbol | Meaning | Unit or convention |
| --- | --- | --- |
| $d$ | Staking duration | Days in the displayed examples |
| $T$ | MintingPeriod | 365 days |
| $r(d)$ | Duration-dependent consumption rate | Dimensionless annual protocol parameter |
| $r_{\min}$ | MinConsumptionRate | Dimensionless annual protocol parameter |
| $r_{\max}$ | MaxConsumptionRate | Dimensionless annual protocol parameter |
| $C$ | SupplyCap | AVAX |
| $S$ | CurrentSupply counter | AVAX |
| $\kappa$ | Remaining-supply ratio | Dimensionless |
| $s$ | Individual stake | AVAX |
| $R$ | Reward promised to one period | AVAX |
| $\lambda$ | Mean arrivals | New validator nodes per day |
| $k$ | Negative-binomial dispersion | Positive count-distribution parameter |
| $\beta_R$ | Renewal response | Log-odds per percentage point of annual reward yield |
| $\beta_E$ | Entry response | Log arrival rate per percentage point of annual reward yield |

## Reproduction

The repository supports code inspection, installation and recomputation of the committed selection verdict without access to historical provider data. With repository access and uv installed:

~~~sh
git clone --branch milestone-2 https://github.com/AVL-Foundation/ext-bcrg-validator-research.git
cd ext-bcrg-validator-research
git checkout model-v0.8.0
uv sync --locked --group model
uv run python scripts/model_v080_selection.py verdict
~~~

The included JSON and CSV files allow checking the displayed counts, ratios and forecast summaries. They contain aggregate evidence and omit individual validator records.

Full simulation reproduction also needs the pinned historical staking tables, fitted-parameter draws, experiment specifications and the corresponding analysis code. A data pin checks input bytes already present. It does not download those snapshots. The [setup guide](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/SETUP.md) records that distribution requirement. The package reports no completed held-back score and performs no new scoring of the reserved period.
