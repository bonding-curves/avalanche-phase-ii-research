# The v0.8.1 candidate at the development origins

The variant `v0.8.1 candidate` (`src/avalanche_research/model/variants.py`) is the released v0.8.0 build with delegations under the delegation laws frozen on 13 October 2026, the named operators known at each origin and one operator type. This folder holds its first run at the 19 development origins, written by

```
uv run --group model python scripts/model_v081_origins.py results/model-v0.8.1-candidate/origins --runs 5 --workers 4
```

on the staking periods run `staking-periods-2026-09-30` (pin `data/pins/p2-model-v0.8.json`) and the seamed delegator stakes run `seamed-delegator-stakes-2026-10-14` for the funding addresses, whose SHA-256 are in `manifest.json`. That first run took the delegator stakes as the newest checked build; the script now takes both runs from one pin file (`--pin`), refuses a missing or unverified pin or one that names no delegator stakes run, and reads no newer build in their place. The pin for the candidate is being created, so the command above needs `--pin` with it before it can be rerun. Five runs of 180 days per origin, one parameter draw each. These are development results on a prototype branch, not a scored adoption: the variant rule's event test has not been run on them.

[`manifest.json`](manifest.json) lists the branch head, the changed source files with their blob ids, every input run and pin with its SHA-256, the results files with theirs, the replay results, the origins command, and the test command and count. [`replay.json`](replay.json) holds the reward-counter replay results it summarises. Both are written by `scripts/model_v081_manifest.py`.

## Operator types are not adopted

The candidate carries one operator type with no shift, with the named operators. Data science fitted the latent-class model under the frozen rules: one class fits the held-out renewal endings best, and two to four classes fail the adoption gates. One class is not significantly better than the shrunk operator renewal rate (p = 0.26), and its transfer calibration error is 0.039 against the limit of 0.02. So the operator-type interface is in the code with K = 1 and no shift, and no type is claimed.

## Files

| File | Holds |
| --- | --- |
| `origins/origins.csv` | One row per origin and horizon (30, 90, 180 days): the candidate's delegated stake, open delegations and BENQI delegated stake (mean, median, min, max over the runs), the same build with no new delegations (`_no_new`), the record where the horizon day lies before 2025-11-19 (`_record`, with `_error` as the relative gap of the mean), the delegations left unplaced to the horizon (`unplaced_mean`, `unplaced_max`) against those attempted (`attempted_mean`), and `scored`, false for a horizon in the held-back period, whose record is not read |
| `origins/parameters.csv` | What each origin read: the flow's mean daily starts and BENQI share over the 28 days before it, BENQI's share of choices to a new validator period over the year before it, the open delegations, the prior-use set, the terms and the named operators |
| `origins/unplaced.csv` | The unplaced count per origin, run and horizon |
| `origins/specifications.csv` | Every run's specification hash: origin, batch seed, draw and hash. Run `r` is batch `r` of one run under base seed `r` reading parameter draw `r` |
| `origins/construction.json` | How the hashes were computed (the model object, the preparation call, the input tables and `SimulationModel.specification_hash`), the code commit, the input runs and their SHA-256 |

## What the first run shows

54 of 57 cells are scored; the three horizons of 2025-07-01 and 2025-10-01 that reach the held-back period are not.

- Unplaced delegations: at most 143 of 377,000 attempted over 180 days (Fortuna), a share of 0.0008 at the worst origin. The containment rule does not bind.
- Delegated stake: the median relative gap of the mean to the record is 0.12, the largest 0.35 (Banff at 30 days). The candidate is closer than the build with no new delegations in 54 of 54 cells.
- Open delegations: median gap 0.28, largest 3.3 (2024-10-01 at 90 days, where the record falls from 169,000 to 34,000 open delegations within the horizon and the candidate holds near 145,000). Closer than no new delegations in 46 of 54 cells.
- BENQI's delegated stake: median gap 0.40, largest 1.8 (Banff at 90 days). Closer than no new delegations in 51 of 54 cells.

The BENQI gaps follow from a window mismatch the frozen laws do not settle: the flow is the mean of the 28 days before the origin (VD1), while each new delegation still takes its stake and duration from a delegation of the 365 days before it, as the stub did. At Banff BENQI's starts of the 28 days averaged 148 AVAX against 708 AVAX over the year, so the candidate mints BENQI's stock about five times too large there. A terms window needs a dated note before any score.
