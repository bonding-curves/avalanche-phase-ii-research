# Paired sweep analysis

This package authenticates a complete sweep, reconstructs matched ChainReward comparisons and supplies rank association and structured Sobol calculations. Keep mechanism, yield and response scopes separate. A calculation becomes a scientific result only after its source, sampling and uncertainty contracts are accepted.

## Read a frozen sweep

Install the locked model and development dependencies from the repository root:

```bash
uv sync --locked --group model
uv run pytest -q tests/test_paired_sweep.py tests/test_rank_associations.py tests/test_sobol_analysis.py
```

Supply a bundle containing `design.json`, `rows.json`, `labels.csv` and `draws.parquet`, the producer's output directory and an independently retained freeze:

```json
{
  "bundle_sha256": {
    "design.json": "<64-character SHA256>",
    "rows.json": "<64-character SHA256>",
    "labels.csv": "<64-character SHA256>",
    "draws.parquet": "<64-character SHA256>"
  },
  "code_commit": "<accepted producer commit>",
  "pin_sha256": "<accepted input pin SHA256>",
  "receipt_sha256": "<accepted producer receipt SHA256>"
}
```

Obtain these values from the accepted producer handoff. Computing replacement hashes after a failed read does not authenticate a changed run.

```bash
uv run python scripts/m2_sweep_analysis.py bundle outputs freeze.json analysis-output
```

The destination must be new. The command writes absolute KPIs, three relative KPIs, declared control verdicts and an analysis receipt with output hashes. Failed controls retain these tables and return exit code 1. Missing cells, changed inputs, invalid pairings and nonfinite ratios refuse consumption. A smoke run without the declared controls cannot receive a control PASS.

Each design row must reference a ChainReward row with identical origin, model, seed, draw, yield and response settings. Shared baselines remain explicit. Issuance saved is `1 - issued / baseline_issued`. Stake and validator retention are `value / baseline_value`. Denominators must be positive. Relative measures use IEEE float64 and do not establish exact one-nAVAX differences above `2**53`. The supported reducer records both 180 and 365 days, with one trajectory per row and every declared cost level.

## Rank associations

`rank_associations.analyze_mm1` computes Spearman correlations and partial rank correlations within each variant and response stratum. Supply parameter and KPI column names, a response column and an explicit `Resampling` declaration. The complete input table carries `row_id`, `run`, `pair_id`, `variant`, `status`, `disposition` and `table.attrs["cell_accounting"] = {"expected": N, "success": N, "failed": 0}`. This accounting must come from authenticated upstream consumption.

Whole independent blocks travel together across strata. Paired or replicated rows refuse independent row resampling. Rank deficient controls, constant outcomes and invalid bootstrap draws remain explicitly unassessable. Intervals summarize the declared sampling design, conditional on the caller's independence assertion.

## Structured Sobol calculations

`sobol.analyze` accepts explicit binary64 A, B and AB coordinate arrays, their complete KPI outputs, success statuses and a frozen `Receipt`. AB replaces one A coordinate with its corresponding B coordinate. The calculator checks coordinate order and input/output hashes. Deterministic calls have empty noise identities. The supported stochastic declaration requires independent A/B noise identities and AB inheritance from A.

For pooled A/B mean `m` and population variance `V`, the first estimate is `mean((B - m) * (AB_j - A)) / V`. The total estimate is `mean((A - AB_j)^2) / (2 * V)`. These use the first and total formulas in the [SALib implementation](https://salib.readthedocs.io/en/latest/_modules/SALib/analyze/sobol.html). Pooled A/B centering and percentile intervals differ from SALib’s expanded-output normalization and normal-width intervals. Finite estimates outside zero to one remain unchanged.

Bootstrap draws resample whole A/B/all-AB base rows jointly across KPIs. Any invalid draw makes the corresponding interval unassessable. Base identifiers fix reproducible ordering. Low discrepancy sequence dependence, shared baselines and cross-scope coupling require an accepted uncertainty law before interpreting intervals. Hashes and distinct labels establish integrity, while actual sampling independence and output provenance require producer evidence.
