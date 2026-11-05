# The held-back test of model v0.8.0

The record from the Granite upgrade, 19 November 2025 at 16:00 UTC, to Helicon, 22 September 2026 at 15:00 UTC, was kept out of every fit and every model choice. This test scores model v0.8.0 once on that record. The machine-readable specification is [specification.json](specification.json) and the script is [`scripts/heldback_test_v080.py`](../../scripts/heldback_test_v080.py). The registration is [manifest.json](manifest.json). It holds the SHA-256 hash, a fingerprint of a file's exact bytes, of the script, this specification, the pinned inputs and the model commit, and it was committed and tagged `heldback-registered-v0.8.0` before any score existed.

## The forecast under test

**Model.** Released v0.8.0, the tag `model-v0.8.0` at commit `b18a4a2`, at its released defaults: a renewal response and an entry response of zero. The test scores the level of validator stake and validator count the model forecasts. A response to reward is outside it.

**Fit.** Every fitted block, duration table and the 200 parameter draws are built once at the origin 18 November 2025, the last whole UTC day before Granite, from rows that started by its end. Nothing is refitted. At each later origin only the observed state is replaced: the open commitments, the scheduled commitments and the supply counter accepted by that origin's end.

**Inputs.** The pin `data/pins/p2-model-v0.8.json`, whose staking periods run `staking-periods-2026-09-30` comes from BCRG's own feed of the P-Chain, the Avalanche chain that records every stake and records through Helicon. The same run gives the fit, each origin's state, the realized series and every benchmark. The realized series is built as the development scores built it: daily stake and count changes accumulated from period starts and ends, on every UTC day before 22 September 2026. The monetary run of the same pin is compared with it at every scored endpoint and reported, and decides nothing.

**Origins and horizons.** The fit origin and the first day of each month from December 2025 to August 2026, ten origins. Horizons of 30, 90 and 180 days, scored only where the endpoint falls before 22 September 2026. The rule gives ten cases at 30 days, eight at 90 and five at 180, for each of two variables, validators' own stake and the active validator count.

**Ensemble.** 200 runs per origin, as ten batches of 20 runs with base seeds 0 to 9. Batch b reads draws 20b to 20b + 19 of the fit's draw table, the development design.

**Benchmarks.** The six naive forecasts of the development scores, each built from the realized record up to its origin only. Three are points: N1, the value at the origin, N2, the origin value plus the mean daily change of the last 180 days, and N3, an autoregression on weekly changes. Three are distributions: N1d and N2d, which spread N1 and N2 by every change of the same length in the 730 days before the origin, and N4, a Gaussian local-level model fitted on every day to the origin. The reference is N1d.

**Score.** Scaled CRPS. The continuous ranked probability score, CRPS, measures the distance between a forecast distribution and the value that happened. The score is divided by the mean absolute one-day change of the series before the origin, so stake and count score on one scale. A point benchmark's CRPS is its absolute error. The test is the one-sided Diebold-Mariano test, with the Harvey, Leybourne and Newbold correction, that the model's scaled CRPS is lower than the reference's over the origins in date order. Its lag count is one plus the most later origins inside one forecast window.

## The verdict

The primary cell is validators' own stake at 90 days, eight origins.

| Verdict | Rule |
| --- | --- |
| Pass | The model's mean scaled CRPS is below every one of the six benchmarks', and the one-sided p that it is below N1d's is under 0.05 |
| Fail | The model's mean scaled CRPS is at or above any one of the six benchmarks' |
| Inconclusive | The model is below all six but the p is 0.05 or more, or the primary cell's inventory is incomplete or any of its scores is undefined |

The verdict says whether v0.8.0's forecast distribution of validators' own stake at 90 days beats the naive forecasts on the record it never saw. It says nothing about a response to reward, about delegated stake, or about Foundation acceptance of deliverable 2.4.

## Reported beside the verdict

- Every variable and horizon: the mean scaled CRPS of the model and the six benchmarks, the CRPS skill against N1d, the origins where the model is closer than N1d, and the one-sided p against N1d.
- Coverage: the share of origins where the realized value fell inside the model's central 50% and 80% intervals, with a Clopper-Pearson 95% range, the count of origins where the realized value fell in either 10% tail of the forecast, and the mean 80% width. The validation protocol's test B4.5 asks the 80% interval to cover 0.60 to 0.95 of origins and the 50% interval 0.30 to 0.70. Coverage is reported against those bands and does not enter the verdict.
- The ensemble mean's scaled absolute error against N1, N2 and N3 with the same test, the rule the 26 October proposal declared, kept visible as a secondary.
- The agreement's measures on each origin's daily ensemble-mean path against the realized path: Pearson correlation on levels and on first differences, the root mean square error, the share of seven-day moves in the same direction, and the phase lag. These measures are not the acceptance test.

## One run

The scoring runs once. The script refuses to run without the registration tag on `origin` and refuses when a verdict already exists in `results/model-v0.8.0-heldback`. Nothing in the specification, the script or the model changes after the scores are read. A rehearsal on data before Granite, to check that the script runs, writes outside the results folder and reads no held-back row.
