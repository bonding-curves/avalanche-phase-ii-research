# The held-back test of model v0.8.0

Model v0.8.0 was scored once on the record from the Granite upgrade, 19 November 2025, to Helicon, 22 September 2026, which no fit or model choice had used. The verdict is **inconclusive**: on validators' own stake at 90 days, the model's forecast distribution scores below all six naive forecasts, but the margin over the best of them is not significant on eight origins. The test was registered before any score existed, in commit `6f85eadb` and the tag `heldback-registered-v0.8.0`. Its specification is [`validation/heldback/specification.md`](../../validation/heldback/specification.md).

## The verdict

The primary cell is validators' own stake at 90 days, eight origins from 18 November 2025 to 1 June 2026. The score is the scaled CRPS. The continuous ranked probability score, CRPS, is the distance between a forecast distribution and the value that happened. Scaled means divided by the mean absolute one-day change of the series before the origin. Lower is better.

| Forecast | Mean scaled CRPS, stake at 90 days |
| --- | --- |
| Model v0.8.0 | 7.05 |
| N4, local-level model | 7.29 |
| N1d, persistence spread by past 90-day changes | 7.63 |
| N1, persistence | 9.39 |
| N3, weekly autoregression | 9.74 |
| N2d, drift spread by past 90-day changes | 11.35 |
| N2, 180-day drift | 15.28 |

The model is closer than N1d at five of the eight origins, with a CRPS skill of 0.08 against it. The one-sided test that the model beats N1d gives p of 0.25 against the registered line of 0.05, so the rule returns inconclusive. The model is below all six benchmarks and the margin is within what eight origins can show.

## The stake level matches the naive forecasts and the count misses the exit of small validators

**The level of stake is forecast as well as the naive forecasts, no better.** At 30 days the model's mean scaled CRPS is 6.04 against 6.00 for N1d and 5.93 for N4. At 90 days it is 7.05 against 7.63 and 7.29. At 180 days, five origins, it is 7.48 against 6.04 and 8.21. The ensemble mean's scaled absolute error at 90 days is 9.33 against 9.39 for persistence, 9.74 for the weekly autoregression and 15.28 for drift, which under the 26 October proposal's point rule is also inconclusive.

**The stake forecast's spread is too narrow.** The realized stake fell inside the model's central 80% interval at 3 of 10 origins at 30 days, 5 of 8 at 90 days and 2 of 5 at 180 days. The validation protocol's test B4.5 asks for 0.60 to 0.95, which only the 90-day cell meets. At the first three 90-day origins, November, December and January, the realized stake ended above all but at most one of the 200 runs. The model forecast a fall in stake over the winter, and stake rose instead, from 160 million AVAX on 18 November to 193 million on 16 February. From February on, the realized stake sat inside the interval at every 90-day origin.

**The validator count is forecast badly.** The record moved to fewer and larger validators: 819 active validators on 18 November 2025, 656 by the end of December and about 600 from June. The model's runs keep the count near 800, so the realized count fell below the model's central 80% interval at 9 of 10 origins at 30 days and at every origin at 90 and 180 days. Its mean scaled CRPS is 7.42, 13.55 and 16.52 at the three horizons, against 3.09, 4.26 and 7.63 for N1d.

**The agreement's measures.** On each origin's daily ensemble-mean path, the Pearson correlation of stake levels with the realized path runs from 0.14 at the November origin to 0.81 at the August origin. The correlation of first differences runs from 0.11 to 0.62, and the share of seven-day moves in the same direction from 0.55 to 0.83. For the validator count the level correlation is negative at eight of the ten origins. The agreement's measures are reported beside the verdict and are not the acceptance test.

## The stake level can be trusted as far as persistence can

The test asked one question: does the model's level of validator stake beat a naive forecast on a period it never saw? The answer is that it matches the best naive forecasts and does not beat them with the eight origins the window holds. The model's stake level can be trusted as far as persistence can, and no further. Its validator count cannot be trusted on this period, because the model does not represent the exit of small validators that the record shows after Granite. Both findings are measured on the released defaults, with no response to reward, so they say nothing about that response.

## One fit, one rule, one run

- Nothing was fitted on the held-back period. One fit at 18 November 2025 served every origin, and only the observed state at each origin changed. The fit's fingerprint hash `744922e8...` and its draw table's hash `999c788c...` equal the ones adopted in `validation/lockbox/specification.json` on 27 October.
- Nothing was tuned after the scores were read. The rule, the origins, the horizons, the benchmarks and the score were fixed in the registered specification.
- No row was reread. The daily stocks of the monetary run of the same pin equal the realized series at all 40 scored endpoints.

## Files

| File | What it holds |
| --- | --- |
| [`verdict.json`](verdict.json) | The verdict, the six comparisons at the primary cell, the p against N1d and the coverage states |
| [`summary.csv`](summary.csv) | Per variable, horizon and forecast: mean scaled CRPS, skill against N1d, 50% and 80% coverage with their 95% ranges, PIT tails, mean 80% width, and the test against N1d |
| [`scores.csv`](scores.csv) | Each case: the scaled CRPS, PIT, coverage, 80% width, point and scaled error of the model and every benchmark |
| [`point-comparisons.csv`](point-comparisons.csv) | The ensemble mean's scaled absolute error against N1, N2 and N3 with the test |
| [`contract-diagnostics.csv`](contract-diagnostics.csv) | The agreement's measures on each origin's daily ensemble-mean path |
| [`daily-paths.csv.gz`](daily-paths.csv.gz) | Each origin's daily ensemble mean beside the realized value |
| [`runs.csv.gz`](runs.csv.gz) | Every run's value at 30, 90 and 180 days |
| [`realized-crosscheck.csv`](realized-crosscheck.csv) | The realized series against the monetary run's daily stocks at every scored endpoint |
| [`specifications.csv`](specifications.csv) | The specification hash of every 20-run batch |
| [`receipt.json`](receipt.json) | The registration commit, the tag, the code commit, the fit fingerprint, the environment, the times and the hash of every output |

## Reproduce

```sh
uv run --group model python scripts/heldback_test_v080.py rehearse <folder>
```

runs the same code on data before Granite, into a folder outside the results. The scoring itself ran once, on 5 November 2026 from 06:47 to 06:48 UTC, and the script refuses to run it again while `verdict.json` exists.
