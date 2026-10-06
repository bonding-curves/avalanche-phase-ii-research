# Behaviour calibration inputs

`behaviour-calibration-inputs.json` supplies descriptive development targets for
the assembled-model moment check and scorecard. It contains validator duration
mix (AM1) and same-node seven-day renewal (AM2), with separately matured
fourteen-day sensitivity. AM3–AM7 remain unsupported with explicit reasons.
The supplementary 365-day no-return share is an endpoint probability, not a
hazard or permanent exit.

The source is `derived.staking-periods`, run `staking-periods-2026-10-02`. The
parquet SHA256, dataset contract and capture hashes are embedded in the JSON.
The method was checked against prototype
`cfdd9d373562200cb9ec6ef81c4715671cebefd3` and its canonical renewal helper.
Each measured definition includes executable SQL and its SHA256. Values are
source censuses. Standard errors are null because repeated nodes, unresolved
operators and common time shocks preclude an IID interval.

The development cutoff is exclusive at 2025-11-19 16:00 UTC. Every reported
moment window ends strictly before it. AM1 reports the first and last observed
acceptance timestamps. AM2 uses an ending window whose upper bound is exclusive
and whose follow-up must finish strictly before the cutoff. Count weights are
one per commitment. AVAX weights sum the original commitment stakes, including
repeated commitments. They do not measure active stock or distinct capital.

These full-development values can check pooled model moments. Earlier-origin
fitting must rebuild that origin's input history. This file supplies no causal
response slope, fitted parameter or predictive validation.

To reproduce from a clean checkout, provide the named cached parquet at
`data/runs/staking-periods-2026-10-02/dataset/staking-periods.parquet`, install
the locked core environment, and run this from the repository root. The named
run is a checked input artifact supplied separately from Git. No notebook or
provider capture is required. The parquet is checked before its development-only
SQL projections are evaluated.

```bash
uv run --locked python - <<'PY'
import hashlib
import json
from pathlib import Path
import duckdb

bundle = json.loads(Path('notebooks/results/behaviour-calibration-inputs.json').read_text())
parquet = Path('data/runs') / bundle['run'] / 'dataset/staking-periods.parquet'
h = hashlib.sha256()
with parquet.open('rb') as handle:
    for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
        h.update(block)
assert h.hexdigest() == bundle['sources']['parquet_sha256']
con = duckdb.connect()
for moment in bundle['moments']:
    if not moment['supported']:
        assert moment['value'] is None and moment['standard_error'] is None
        continue
    variants = [moment]
    if moment['id'] == 'AM2':
        variants.append(moment['sensitivity_14d'])
    for variant in variants:
        definition = variant['definition']
        assert hashlib.sha256(definition['sql'].encode()).hexdigest() == definition['sha256']
        rows = con.execute(definition['sql'], [str(parquet)]).fetchall()
        if moment['id'] == 'AM1':
            for actual, expected in zip(rows, moment['details']['bins'], strict=True):
                assert tuple(map(int, actual)) == (
                    expected['lower_days_inclusive'], expected['upper_days_exclusive'],
                    expected['commitments'], expected['stake_navax'])
                assert abs(expected['commitments'] / moment['n'] - expected['count_share']) < 1e-12
        else:
            n, renewed, stake, renewed_stake = map(int, rows[0])
            detail = variant['details']
            assert (n, renewed, stake, renewed_stake) == (
                variant['n'], detail['renewed_ends'],
                detail['eligible_stake_navax'], detail['renewed_stake_navax'])
            assert abs(renewed / n - variant['value']) < 1e-12
print('Pinned duration and renewal counts/nAVAX match exactly.')
PY
```
