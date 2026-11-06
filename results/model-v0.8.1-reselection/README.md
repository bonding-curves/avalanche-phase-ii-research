# How the rebuilt v0.8.1 candidate scored against v0.8.0

This folder holds the system test of the rebuilt v0.8.1 candidate against the released model, v0.8.0, at the 19 development origins, under the rule that chose v0.8.0. It replaces the scores in [`../model-v0.8.1-selection/`](../model-v0.8.1-selection/README.md), which belong to the earlier candidate.

## The candidate forecasts validators exactly as v0.8.0 does

The candidate passes the system test with no difference at all. In every one of the 22,800 paired run values, at every origin, horizon and run, its validator stake and its count of active validators equal v0.8.0's. Every cell of the rule therefore reads a difference of 0.000 in scaled CRPS, the continuous ranked probability score:

| Forecast | Horizon | Origins scored | Scaled CRPS, both models | Difference, candidate minus v0.8.0 |
| --- | --- | --- | --- | --- |
| Validator stake | 30 days | 19 | 4.371 | 0.000 |
| Validator stake | 90 days | 18 | 5.183 | 0.000 |
| Validator stake | 180 days | 17 | 5.469 | 0.000 |
| Active validators | 30 days | 19 | 5.410 | 0.000 |
| Active validators | 90 days | 18 | 10.849 | 0.000 |
| Active validators | 180 days | 17 | 22.533 | 0.000 |

CRPS scores a whole forecast distribution against what happened, and here it is scaled by the mean one-day change before the origin. Lower is better. With no difference, the one-sided p that the candidate is worse is 1 in every cell. The rule's margin of 2.2 and its cell threshold of 0.05/6 are not approached.

The equality follows from the two changes of the rebuild. The candidate's arrivals do not read participation, so they are v0.8.0's arrivals. Its new delegations draw their terms from the delegations started in the 28 days to the origin. Delegations change delegated stake, which these two forecasts do not count.

The 28-day terms window met the numerical criteria as a preregistered challenger across 18 development origins: 15 wins, bootstrap p = 0.0003 and calibration error = 0.0061. The original primary verdict excluded that challenger. These development results informed selection of the rebuilt candidate. They are not a new independent validation of the rebuilt model or all delegation behavior. The original 365-day terms and elasticity 1 tests failed; elasticity 0 retains v0.8.0 arrivals.

The verdict in [`verdict.json`](verdict.json) reads "no event test", because this script leaves the event-test field open, as it did for the earlier candidate. Its system test reads "pass".

## How it was tested

The rule is the one fixed on 6 October and described in [`../model-v0.8.0-selection/README.md`](../model-v0.8.0-selection/README.md). There are 200 runs per origin and model at the 19 development origins: the five upgrades from Banff to Fortuna and the quarter starts from July 2022 to October 2025. Run r of batch b runs as its own simulation under seed 20b + r − 1, with one parameter draw per run. Both models read the same seeds and draws at each origin. Every input is measured or fitted before its origin, and nothing is fitted after 19 November 2025, when the held-back test period begins. A horizon that would reach the held-back period is not scored, so the 90-day comparison covers 18 origins and the 180-day comparison 17.

The candidate is commit `196b5bf2`, with delegation terms from the 28 days to the origin and a participation elasticity of 0. Both models were built from pin [`data/pins/p2-model-v0.8.1.json`](../../data/pins/p2-model-v0.8.1.json). The 7,600 runs ran on one machine from 5 to 6 November 2026, one origin and model per task, each task writing its own file. Six of the candidate's tasks ran in two separate copies of the same code, and each copied file kept its SHA-256 from source to destination.

Three recorded specifications were recomputed from a clean export of the same commit, one for v0.8.0 at 1 July 2022 and two for the candidate at 1 January 2024 and 1 October 2025. All three specification hashes matched. This check repeated preparation and specification construction only. It reran no trajectories or scores.

## Files

| File | What it holds | SHA-256 |
| --- | --- | --- |
| [`development-runs.csv.gz`](development-runs.csv.gz) | Every run's value at 30, 90 and 180 days, the input to the distribution scores | `873d9d59…` |
| [`development-specifications.csv`](development-specifications.csv) | The specification hash of every run: the model, its settings and a digest of every input | `9d6f6191…` |
| [`development-distribution.csv`](development-distribution.csv) | Each forecast's CRPS by origin, variable and horizon, for both models and the benchmarks | `1b1b8fc7…` |
| [`development-distribution-summary.csv`](development-distribution-summary.csv) | Each forecast's mean score, coverage and comparison with the benchmarks over the 19 origins | `d97ed608…` |
| [`verdict.json`](verdict.json) | The verdict the rule gives on these scores | `6c099fea…` |

## Reproduce

```sh
uv run --group model python scripts/model_v081_selection.py OUT_DIR --pin data/pins/p2-model-v0.8.1.json --score-only
```

This command scores the file `development-runs.csv.gz` placed in the folder `OUT_DIR`, in seconds and with no simulation. On a second machine, `verdict.json` came out identical byte for byte. The distribution scores matched to within 3 × 10⁻¹⁵ of each value, differing only in the last binary digits from the order of floating-point additions, as the [v0.8.0 record](../model-v0.8.0-selection/README.md#reproduce) explains.

Rerunning the 7,600 runs drops the flag `--score-only`. It needs up to about 5 GB of memory per worker at the largest origins.
