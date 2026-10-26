# Pinned input sets

This folder holds the research's pin files. A **pin file** names the exact data runs a result was made from, with the hash of each run's data file, so the result can be rebuilt from those inputs and no others. A **run** is one build of a dataset, a folder under `data/runs/` (see the [data guide](../README.md)). Without a pin, a script reads a dataset's newest run, which changes with every refresh.

## What a pin file holds

Each pin file is JSON with schema version `avalanche-pins/v1`, a `name`, the time it was written (`pinned_at`), and a list of `runs` with these fields.

| Field | Meaning |
| --- | --- |
| `dataset_id` | The dataset's catalog ID, such as `derived.staking-periods` |
| `run` | The run folder under `data/runs/` |
| `capture_id`, `captured_at` | The capture the run was built from, and when it finished |
| `parquet`, `bytes`, `sha256` | The run's Parquet file, its size, and its SHA-256 hash |
| `check` | The run's check result when it was pinned. Only `pass` is accepted |

A pin may also carry `code`: the full commit of this repository the results were made with (`client_commit`) and an optional tag (`ref`).

| File | What it pins |
| --- | --- |
| `p1-brief.json` | The seamed validator stakes and staking periods of 2026-10-02 |
| `p2-model-v0.8.json` | The staking periods and daily monetary ledger of 2026-09-30, read by the model scoring and v0.7 report scripts |
| `p3-helicon-etf.json` | Eight runs behind the Helicon and exchange-traded fund figures |
| `p4-opportunity-costs.json` | Frozen historical inputs for the opportunity-cost figure. Native rates use a realised-supply approximation, and the saved price artifact repeats date labels |
| `p4-opportunity-costs-qualified-2026-10-26.json` | Additive rebuild: unique nearest-midnight price dates from the original capture, with explicit native approximation basis, nominal quote time and realised supply input. Does not certify an exact protocol offer |
| `p5-v0.7-report.json` | Four runs of 2026-09-30 behind the v0.7 research report, at commit `087484b`, tag `model-v0.7.0` |
| `p6-v0.7-report.json` | The runs of `p5` plus the operator table, at the same commit and tag |
| `p7-systems-learning-weeks.json` | The validator-week panel of 2026-10-06, whose reward addresses as of each week allow an operator grouping that reads no later data |
| `p8-v0.9.5-inputs.json` | The scenario inputs for revenue-funded rewards: the monetary ledger, AVAX price, Avalanche fees and revenue, and the competing yields |
| `p9-staking-records.json` | Frozen staking records of 2026-10-14: staking periods, daily monetary ledger, seamed validator and delegator stakes, and auto-renewed cycle history. The original ledger predates the cycle accounting repair |
| `staking-records-accounting-qualified-2026-10-26.json` | Canonical era-table successor using the qualified cycle-effective ledger and exact 26 October staking/cycle inputs. Principal and effective stock are separate, with restake counted once |
| `monetary-accounting-qualified-2026-10-26.json` | Explicit successor daily ledger and upgrade-period summary through 2026-10-25, with cycle-recognised issuance, effective cycle stake and inclusive C-EVM burn once. Records the producing code commit and receipt hashes |

The qualified rebuild preserves all original point timestamps and prices. Its date label is the nearest midnight, which may follow the observation time. Use `observed_at` and an explicit availability rule for as-of decisions. A date label alone does not establish that a quote was available at the start of that date. Historical `p4` and `p8` remain unchanged.

## Check a pin

`pin-check` confirms that each pinned run's Parquet file exists, has the recorded size and SHA-256, and still passes its check. When the pin names code, it also confirms that the commit exists in this repository and that the tag points at it.

```sh
uv run avalanche data pin-check data/pins/p6-v0.7-report.json
```

With the runs in place it prints `PASS | data pin-check | p6-v0.7-report.json: 5 runs; 0 findings`. Otherwise it prints one finding per problem, such as a missing or changed run, and exits with status 1.

## Make a pin

`pin` takes each dataset's newest run, or the one named with `--run`. It refuses a run whose check has not passed, an existing pin name, and a commit or tag that does not resolve.

```sh
uv run avalanche data pin NAME derived.staking-periods --run derived.staking-periods=staking-periods-2026-09-30
```

## How pins connect to the rest

The runs come from the build steps in the [data guide](../README.md). The model runs for the v0.7 report, `scripts/model_v07_report_runs.py`, and the record charts, `scripts/figures/model_v07_record.py`, read their runs through `avalanche_research.pins.runs`, which maps each dataset to its pinned run, and stop on any finding. Other scripts in [`scripts/`](../../scripts/) and [`scripts/figures/`](../../scripts/figures/) name a pinned run directly. The figures they write are the ones shown on the research site.

The accounting successor leaves p2, p4, p8 and p9 unchanged. Its daily ledger includes a byte-bound cycle event companion. Consumers that added restake separately must migrate that adjustment before selecting the new ledger. See the [accounting basis and archived inputs](../README.md#cycle-accounting-and-archived-inputs).

The canonical successor is selected explicitly. With its exact runs available, export it with:

```sh
uv run --group notebook python scripts/staking_record_tables.py \
  --pin data/pins/staking-records-accounting-qualified-2026-10-26.json \
  --runs-root data/runs --out /tmp/staking-era-qualified --threads 4 --memory-limit 2GB
```

The exporter writes `era-table.csv`, `metadata.json` and a byte-bound receipt. It refuses an existing output directory. The new ledger already includes cycle restake in effective validator stock. This consumer reconstructs the principal separately and uses the effective amount once in exposure and rate denominators. Original-principal identity weights retain their meaning. The old p9 pin continues through its archived accounting path.
