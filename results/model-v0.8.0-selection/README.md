# How v0.8.0 was chosen

This folder holds the evidence for the released model, v0.8.0, and the script that recomputes its verdict.

## The result

v0.8.0 is candidate a, the fitted lifecycle with one draw of every fitted parameter per run, with two additions:

- **The stake hurdle.** Each new commitment's stake is drawn given its duration, from the stakes chosen in the year before the origin.
- **The return hazard on each node's own history.** A node out of the active set comes back with a daily probability that depends on its own record.

Against candidate a (`v0.8-a u`), v0.8.0 (`v0.8-a stake return u`, released as the variant `v0.8.0`) improves the 90-day validator stake forecast by 0.81 in scaled CRPS, and no forecast is clearly worse:

| Forecast | Horizon | Difference in scaled CRPS, v0.8.0 minus candidate a | One-sided p that v0.8.0 is worse |
| --- | --- | --- | --- |
| Validator stake | 30 days | -0.047 | 0.564 |
| Validator stake | 90 days | **-0.813** | 0.834 |
| Validator stake | 180 days | -0.237 | 0.666 |
| Active validators | 30 days | -0.023 | 0.582 |
| Active validators | 90 days | +0.039 | 0.435 |
| Active validators | 180 days | -0.193 | 0.688 |

Negative is better. CRPS, the continuous ranked probability score, scores a whole forecast distribution against what happened, scaled here by the mean one-day change before the origin. A cell is clearly worse only if its p is below 0.05/6.

## How it was tested

The rule was fixed on 6 October, before any of these scores existed, and was not changed after them:

1. **Event test.** A change must forecast its own decisions better on held-out data before it enters a system test: a lower pooled score, a paired bootstrap p below 0.05 (2,000 replicates), lower at 14 or more of the 19 origins, and a calibration error of at most 0.02.
2. **System test.** 200 runs per origin at 19 development origins, the five upgrades from Banff to Fortuna and the quarter starts from July 2022 to October 2025. Every input is measured or fitted before each origin, and nothing is fitted after 19 November 2025, when the held-back test period begins. The change is adopted if the mean worsening of the 90-day validator stake score is below 2.2 and no cell is clearly worse.

The adoption order was declared before the scores: each change was tested alone on candidate a, then the adopted changes together. A horizon that would reach the held-back period is not scored, so the 90-day comparison covers 18 origins and the 180-day one fewer.

This folder holds the system test of the final comparison. The event tests of the stake hurdle and the return hazard, and the scores of the rejected changes, are not in this repository. `verdict` takes the two event tests as passed, as they were, and recomputes only the system test.

| Change | Outcome |
| --- | --- |
| Stake hurdle | Adopted alone, then with the return hazard |
| Return hazard on the node's own history | Adopted alone, then with the stake hurdle |
| Ten stake bands for the next stake | Adopted alone, then superseded by the stake hurdle, which replaces the draw the bands reshape |
| The node's own renewal record in the renewal logit | Rejected: its own decisions were forecast better, but stake at 90 days and validators at 30 days were clearly worse |
| A duration transition for the next duration | Rejected: validators at 180 days were clearly worse |
| Uptime in renewal | Rejected at the event test: calibration error just above 0.02 |
| GoGoPool as its own group | Rejected at the event test: better at too few origins, because the group is absent at several |
| Large operators at the operator level | Rejected: their stake was forecast worse than candidate a's |

## Limits stated with the release

- **The stake hurdle is badly calibrated on exact repeats.** It under-predicts renewals that keep exactly the same stake and entries at exactly the 2,000 AVAX minimum, and over-predicts returns that keep their stake. Its calibration on those repeats is outside the 0.02 the rule allows for a whole block, although the block as a whole passed.
- **The stake hurdle is not resampled.** Every other fitted parameter is drawn once per run. The stake hurdle stays at its point estimate, so the spread of the forecasts leaves out its uncertainty.
- **The spread of daily new validators does not match the record.** Arrivals follow a negative binomial count, and its day-to-day spread failed its test at most origins. No tested alternative did better.
- **Responses to the reward rate are not estimated.** History before Helicon does not identify how renewal and entry respond to the reward rate, so those responses are swept settings.

## Files

| File | What it holds |
| --- | --- |
| [`development-distribution.csv`](development-distribution.csv) | Each forecast's CRPS by origin, variable and horizon, for both models and the benchmarks |
| [`development-distribution-summary.csv`](development-distribution-summary.csv) | Each forecast's mean score, coverage and comparison with the benchmarks over the 19 origins |
| [`development-specifications.csv`](development-specifications.csv) | The specification hash of every 20-run batch: the model, its settings and a digest of every input |
| [`development-runs.csv.gz`](development-runs.csv.gz) | Every run's value at 30, 90 and 180 days, the input to the distribution scores |
| [`verdict.json`](verdict.json) | The verdict the rule gives on these scores |

## Reproduce

```sh
uv run --group model python scripts/model_v080_selection.py verdict
```

recomputes the verdict from the committed scores and checks it against `verdict.json`, in seconds and with no data.

```sh
uv run --group model python scripts/model_v080_selection.py specifications
```

rebuilds both models at every origin from the staking periods of pin [`data/pins/p2-model-v0.8.json`](../../data/pins/p2-model-v0.8.json) and checks every batch's specification hash against `development-specifications.csv`. Equal hashes show the same settings, fitted parameters and input digests as the scored models. They do not identify the code.

```sh
uv run --group model python scripts/model_v080_selection.py outputs Banff Durango 2025-10-01
```

reruns the first 20-run batch of both models at those origins and checks every run's value against `development-runs.csv.gz`. Equal values show that this code reproduces the scored runs there.

Both checks compare exact values. The hash covers every fitted coefficient to the last bit, and a machine whose linear algebra library rounds differently can change the last digit of a fitted coefficient, and with it the hash and the runs. On 13 October both checks passed on the machine that ran the scores. On a second machine the specification hashes differed only through such last-digit differences. A difference is therefore checked by comparing the specifications themselves before it is read as a different model. Rerunning the 200 runs per origin is [`scripts/model_development_scores.py`](../../scripts/model_development_scores.py) with the two models, then [`scripts/model_distribution_scores.py`](../../scripts/model_distribution_scores.py).
