# How the v0.8.1 candidate scored against v0.8.0

This folder holds the system test of the v0.8.1 candidate against the released model, v0.8.0, at the 19 development origins. The test uses the rule that chose v0.8.0.

## The result

The candidate passes the system test. Its 90-day validator stake forecast is worse than v0.8.0's by 0.004 in scaled CRPS, the continuous ranked probability score, far inside the margin of 2.2. No forecast is clearly worse:

| Forecast | Horizon | Difference in scaled CRPS, candidate minus v0.8.0 | One-sided p that the candidate is worse |
| --- | --- | --- | --- |
| Validator stake | 30 days | -0.023 | 0.959 |
| Validator stake | 90 days | **+0.004** | 0.465 |
| Validator stake | 180 days | -0.034 | 0.826 |
| Active validators | 30 days | -0.047 | 0.741 |
| Active validators | 90 days | +0.145 | 0.307 |
| Active validators | 180 days | +0.796 | 0.228 |

Negative is better. CRPS scores a whole forecast distribution against what happened. Here it is scaled by the mean one-day change before the origin. A cell is clearly worse only if its p is below 0.05/6, about 0.0083. The lowest p of the six is 0.228.

The verdict in [`verdict.json`](verdict.json) reads "no event test", because this script leaves the event-test field open. The candidate's two changes are the participation feedback and the supply limit. Their own held-out event tests are recorded with the delegation blocks and are not restated here. With every test this script runs passing, "no event test" is the rule's answer when it is given no event test.

## How it was tested

The rule is the one fixed on 6 October and described in [`../model-v0.8.0-selection/README.md`](../model-v0.8.0-selection/README.md). There are 200 runs per origin and model at the 19 development origins: the five upgrades from Banff to Fortuna and the quarter starts from July 2022 to October 2025. Run r of batch b runs as its own simulation under seed 20b + r − 1, with one parameter draw per run. Both models read the same seeds and draws at each origin. Every input is measured or fitted before its origin, and nothing is fitted after 19 November 2025, when the held-back test period begins. A horizon that would reach the held-back period is not scored, so the 90-day comparison covers 18 origins and the 180-day comparison fewer.

The candidate is the branch at commit `c1d03bd`, with a participation elasticity of 1. Both models were built from pin [`data/pins/p2-model-v0.8.1.json`](../../data/pins/p2-model-v0.8.1.json). The candidate's delegations come from the seamed delegator stakes the pin names, as in [`scripts/model_v081_origins.py`](../../scripts/model_v081_origins.py). All 7,600 runs ran on one machine with an Intel Core i7-13700F, from 04:25 to 18:20 Pacific time on 28 October 2026. They ran three workers at a time, one origin and model per task, and each task wrote its own file.

## Files

| File | What it holds | SHA-256 |
| --- | --- | --- |
| [`development-runs.csv.gz`](development-runs.csv.gz) | Every run's value at 30, 90 and 180 days, the input to the distribution scores | `1e5683ec…` |
| [`development-specifications.csv`](development-specifications.csv) | The specification hash of every run: the model, its settings and a digest of every input | `850c375c…` |
| [`development-distribution.csv`](development-distribution.csv) | Each forecast's CRPS by origin, variable and horizon, for both models and the benchmarks | `02b40826…` |
| [`development-distribution-summary.csv`](development-distribution-summary.csv) | Each forecast's mean score, coverage and comparison with the benchmarks over the 19 origins | `a2b1d01c…` |
| [`verdict.json`](verdict.json) | The verdict the rule gives on these scores | `56aff83c…` |

## Reproduce

```sh
uv run --group model python scripts/model_v081_selection.py OUT_DIR --pin data/pins/p2-model-v0.8.1.json --score-only
```

This command scores the file `development-runs.csv.gz` placed in the folder `OUT_DIR`, in seconds and with no simulation. It rewrites the distribution scores and the verdict. On a second machine with a different CPU, `verdict.json` came out identical byte for byte. The distribution scores matched except for benchmark N4, a local-level forecast that needs no model, which differed in the last binary digit at a few cells. The cause is the order of floating-point additions, as the [v0.8.0 record](../model-v0.8.0-selection/README.md#reproduce) explains.

Rerunning the 7,600 runs drops the flag `--score-only`. It takes about 14 hours at three workers and needs up to 5 GB of memory per worker at the largest origins.
