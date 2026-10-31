# Complete CLI reference

*Draft for review.*

The installed Click definitions supply every command, argument, option and default below. There are 17 executable commands and 4 groups including the root. Help inspection invokes no command callbacks. Effects and input requirements are reviewed annotations. The [CLI walkthrough](usage.md) explains the working sequence.

## avalanche

```text
Usage: avalanche [OPTIONS] COMMAND [ARGS]...

  Inspect and reproduce Avalanche Phase II research.

Options:
  --version  Show the package version, the released model and the code commit, then
             exit.
  --help     Show this message and exit.

Commands:
  data      Inspect, retrieve, build, and check research data.
  model     Run, inspect and check the staking model and its source-linked protocol...
  research  Orient in the wiki and source checkout without loading research data.
```

## avalanche data

```text
Usage: avalanche data [OPTIONS] COMMAND [ARGS]...

  Inspect, retrieve, build, and check research data.

Options:
  --help  Show this message and exit.

Commands:
  build      Build a normalized Parquet dataset from a capture.
  check      Check capture integrity, optional built output, and an optional...
  derive     Build a derived dataset from built runs into a new run directory with...
  describe   Describe one source or dataset ID.
  fetch      Fetch one immutable source capture into a new directory.
  freshness  Read the newest record of each source live; any older than 36 hours,...
  list       List implemented sources and datasets.
  manifest   Show the declared dataset manifest.
  pin        Write data/pins/NAME.json: one checked run per dataset, with its...
  pin-check  Confirm every run a pin file names still exists, is unchanged, and...
  runs       List built runs under data/runs for one dataset or for every dataset.
```

## avalanche data build

Inputs: Capture directory --from, registered dataset ID, new --output.

Effects: Creates normalized Parquet and build receipts. --preview resolves local inputs/writes without creating output; no capture retrieval.

Credentials: None for local normalization of an existing capture.

```text
Usage: avalanche data build [OPTIONS] DATASET_ID

  Build a normalized Parquet dataset from a capture.

Options:
  --from PATH    [required]
  --output PATH  [required]
  --preview      Resolve inputs and writes without creating output.
  --json         Emit the complete result as JSON.
  --help         Show this message and exit.
```

## avalanche data check

Inputs: Capture directory, optional built dataset and optional repeatable built reference directories.

Effects: When --dataset is supplied writes or replaces its check.json, even though command is named check. Without --dataset reports capture-only validation. Multiple --against allowed for metrics or builderhub primary dataset; otherwise at most one. Non-pass status exits 1.

Credentials: None for checks over delivered local captures and references.

```text
Usage: avalanche data check [OPTIONS] DATASET_ID

  Check capture integrity, optional built output, and an optional reference cross-check.

Options:
  --capture PATH  [required]
  --dataset PATH
  --against PATH  Built reference dataset directory for a cross-check; repeatable where
                  a check takes several.
  --json          Emit the complete result as JSON.
  --help          Show this message and exit.
```

## avalanche data derive

Inputs: Derived dataset ID and existing built upstream runs. --input DATASET_ID=RUN overrides otherwise-newest selection.

Effects: Creates derived capture/build/Parquet receipts in a new output run. No --preview option. Rejects modules without derive. Newest selection is not a frozen research input unless pinned explicitly.

Credentials: No generic provider credentials for local derived builds; fetch needed upstream runs separately.

```text
Usage: avalanche data derive [OPTIONS] DATASET_ID

  Build a derived dataset from built runs into a new run directory with capture and
  dataset receipts.

Options:
  --output PATH           [required]
  --input DATASET_ID=RUN  Pin an input run; the newest built run of each input is used
                          otherwise.
  --json                  Emit the complete result as JSON.
  --help                  Show this message and exit.
```

## avalanche data describe

Inputs: Known source or dataset ID.

Effects: Read-only; unknown ID is an error.

Credentials: None.

```text
Usage: avalanche data describe [OPTIONS] IDENTITY

  Describe one source or dataset ID.

Options:
  --json  Emit the complete result as JSON.
  --help  Show this message and exit.
```

## avalanche data fetch

Inputs: Registered dataset ID, new output path, source-specific repeated KEY=VALUE params; some captures require built upstream runs.

Effects: Without --preview makes network/provider requests and creates immutable capture files/receipts in a new directory. May consume API limits or billable query resources. --preview resolves requests/writes without network; may read local catalog/upstream run metadata.

Credentials: Source-dependent: Snowflake named connection avalanche (AVALANCHE_SNOWFLAKE_CONNECTION overrides name). Optional AVALANCHE_DATA_API_KEY for glacier-api host. SEC captures require AVALANCHE_SEC_CONTACT identity. Other supported endpoints commonly public; inspect selected module/source contract.

```text
Usage: avalanche data fetch [OPTIONS] DATASET_ID

  Fetch one immutable source capture into a new directory.

Options:
  --output PATH          [required]
  --param KEY=VALUE      Bound a parameterized query.
  --preview              Resolve requests and writes without network access.
  --timeout FLOAT RANGE  Request and statement timeout in seconds.  [default: 20;
                         1<=x<=600]
  --json                 Emit the complete result as JSON.
  --help                 Show this message and exit.
```

## avalanche data freshness

Inputs: Live configured sources plus existing local walk runs.

Effects: Live Snowflake queries, P-Chain/Tenderly/Data API/metrics requests and local Parquet reads. Can use provider quota/query resources. No output-file option; unreadable or >36-hour-old sources become findings. Not an offline status command.

Credentials: Snowflake named connection and access to referenced share tables; optional Data API key.

```text
Usage: avalanche data freshness [OPTIONS]

  Read the newest record of each source live; any older than 36 hours, or unreadable, is
  a finding.

Options:
  --timeout FLOAT RANGE  Request and statement timeout in seconds.  [default: 60;
                         1<=x<=600]
  --json                 Emit the complete result as JSON.
  --help                 Show this message and exit.
```

## avalanche data list

Inputs: Local catalog JSON.

Effects: Read-only; prints declared implemented sources/datasets. Not a provider connectivity test.

Credentials: None.

```text
Usage: avalanche data list [OPTIONS]

  List implemented sources and datasets.

Options:
  --json  Emit the complete result as JSON.
  --help  Show this message and exit.
```

## avalanche data manifest

Inputs: Local catalog JSON.

Effects: Read-only; reports declarations, not existing run inventory.

Credentials: None.

```text
Usage: avalanche data manifest [OPTIONS]

  Show the declared dataset manifest.

Options:
  --json  Emit the complete result as JSON.
  --help  Show this message and exit.
```

## avalanche data pin

Inputs: One or more dataset IDs with built runs whose recorded check status passes; optional explicit DATASET=RUN; local Git object/ref for code binding.

Effects: Creates data/pins/NAME.json, hashes Parquets and records capture identities. Refuses an existing pin. Defaults to newest run per dataset. --code-ref requires --code-commit and must point to that commit.

Credentials: None.

```text
Usage: avalanche data pin [OPTIONS] NAME DATASET_IDS...

  Write data/pins/NAME.json: one checked run per dataset, with its capture ID and
  Parquet hash.

Options:
  --run DATASET=RUN   Pin this run instead of the newest; repeatable.
  --code-commit TEXT  The client commit the pinned results were made with.
  --code-ref TEXT     A tag or branch that must point at --code-commit, such as
                      model-v0.7.0.
  --json              Emit the complete result as JSON.
  --help              Show this message and exit.
```

## avalanche data pin-check

Inputs: Existing pin, its local built Parquets/receipts/check records, and any bound Git objects/refs.

Effects: Read-only; hashes inputs and checks stored check.json status. Does not rerun each dataset checker and does not download missing snapshots. Changed/missing inputs or code bindings produce attention and exit 1.

Credentials: None.

```text
Usage: avalanche data pin-check [OPTIONS] PATH

  Confirm every run a pin file names still exists, is unchanged, and still passes its
  check.

Options:
  --json  Emit the complete result as JSON.
  --help  Show this message and exit.
```

## avalanche data runs

Inputs: Existing data/runs receipts; dataset ID is optional.

Effects: Read-only; scans run metadata, does not fetch missing datasets.

Credentials: None.

```text
Usage: avalanche data runs [OPTIONS] [DATASET_ID]

  List built runs under data/runs for one dataset or for every dataset.

Options:
  --json  Emit the complete result as JSON.
  --help  Show this message and exit.
```

## avalanche model

```text
Usage: avalanche model [OPTIONS] COMMAND [ARGS]...

  Run, inspect and check the staking model and its source-linked protocol rules.

Options:
  --help  Show this message and exit.

Commands:
  check     Recompute every captured potential reward from the formula and report...
  describe  Show the mainnet staking parameters, upgrade schedule, and mechanism...
  reward    Compute the Primary Network potential reward for one stake.
  run       Run one scenario from a pin file: one origin, model and seed, written...
  sweep     Run a sweep design file: one Parquet file per row under OUT, and the...
```

## avalanche model check

Inputs: Built primary-validator-stakes, primary-delegator-stakes and primary-staking-supply dataset directories.

Effects: Reads local Parquets, recomputes potential protocol rewards by regime and reports mismatches. No check.json write in this CLI callback. May scan many rows; does not validate behavioral forecasts.

Credentials: None for local captured reward reconstruction.

```text
Usage: avalanche model check [OPTIONS]

  Recompute every captured potential reward from the formula and report disagreement by
  regime.

Options:
  --validators PATH  Built primary-validator-stakes dataset directory.  [required]
  --delegators PATH  Built primary-delegator-stakes dataset directory.  [required]
  --supply PATH      Built primary-staking-supply dataset directory.  [required]
  --json             Emit the complete result as JSON.
  --help             Show this message and exit.
```

## avalanche model describe

Inputs: Source-linked protocol constants/upgrade definitions.

Effects: Read-only; describes protocol parameters/mechanisms, not fitted responses or a full model specification.

Credentials: None.

```text
Usage: avalanche model describe [OPTIONS]

  Show the mainnet staking parameters, upgrade schedule, and mechanism sources.

Options:
  --json  Emit the complete result as JSON.
  --help  Show this message and exit.
```

## avalanche model reward

Inputs: AVAX stake, days duration, UTC start and AVAX supply. Parser accepts nonnegative numbers; protocol applies further validity rules.

Effects: Data-free deterministic potential reward calculation. Converts AVAX to integer nAVAX and days to integer seconds using round. Does not predict validator behavior, check uptime or pay/submit a reward.

Credentials: None.

```text
Usage: avalanche model reward [OPTIONS]

  Compute the Primary Network potential reward for one stake.

Options:
  --stake FLOAT RANGE             Staked amount in AVAX.  [x>=0; required]
  --duration FLOAT RANGE          Staking duration in days.  [x>=0; required]
  --start [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%d %H:%M:%S]
                                  Stake start time, UTC.  [required]
  --supply FLOAT RANGE            Current AVAX supply at the stake start.  [x>=0;
                                  required]
  --json                          Emit the complete result as JSON.
  --help                          Show this message and exit.
```

## avalanche model run

Inputs: Existing pin and pinned input datasets; valid pre-lockbox --origin; registered model variant; output directory.

Effects: Fits/prepares and simulates one scenario as a one-row sweep, writes Parquet output plus sweep receipt, may use worker processes and substantial CPU/RAM. Defaults v0.8.0, 20 runs, 180 days, seed 0, auto workers. No dry-run/preview flag.

Credentials: None for offline simulation after inputs are available. Pin never retrieves snapshots.

```text
Usage: avalanche model run [OPTIONS] PIN OUT

  Run one scenario from a pin file: one origin, model and seed, written as a one-row
  sweep under OUT.

Options:
  --origin TEXT              Model origin day, before the validation lockbox.
                             [required]
  --model TEXT               Model variant name, as in a design's models. The default is
                             the released model; v0.7, v0.8 and the other registered
                             variants also run.  [default: v0.8.0]
  --runs INTEGER RANGE       Monte Carlo runs of the scenario.  [default: 20; x>=1]
  --timesteps INTEGER RANGE  Days simulated.  [default: 180; x>=1]
  --seed INTEGER RANGE       Base random seed of the runs.  [default: 0; x>=0]
  --workers TEXT             A number, or auto to size from free memory.  [default:
                             auto]
  --json                     Emit the complete result as JSON.
  --help                     Show this message and exit.
```

## avalanche model sweep

Inputs: Existing JSON design, its pin and pinned local datasets, optional hash-bound rows/draws files and KPI design; optional --pin override.

Effects: Executes design rows across selected registered variants/origins/settings, with row Parquets and receipt; may fit, simulate and reduce KPIs. Existing valid rows can be skipped/resumed by runner contract. Controls for runs/days/seeds/workers live in design, not CLI flags. No dry-run/preview flag.

Credentials: None for offline simulation after inputs are available.

```text
Usage: avalanche model sweep [OPTIONS] DESIGN OUT

  Run a sweep design file: one Parquet file per row under OUT, and the sweep's receipt
  beside them.

  Each name in the design's models must be a registered model variant, such as v0.8.0,
  the released model.

Options:
  --pin FILE  Pin file replacing the design's.
  --json      Emit the complete result as JSON.
  --help      Show this message and exit.
```

## avalanche research

```text
Usage: avalanche research [OPTIONS] COMMAND [ARGS]...

  Orient in the wiki and source checkout without loading research data.

Options:
  --help  Show this message and exit.

Commands:
  tree  Print tracked wiki pages, repository structure, or both (the default).
```

## avalanche research tree

Inputs: Git checkout with project markers. Optional root/view/depth.

Effects: Read-only; Git-index path inventory and current working-tree frontmatter. Default excludes untracked/missing/symlink/runtime/private-cache paths; optional nonignored untracked inventory excludes data. Default wiki depth 4 and repo depth 2; explicit --depth exposes nested files. No data contents or network. Tree schema differs from standard CLI result envelope.

Credentials: None.

```text
Usage: avalanche research tree [OPTIONS] [wiki|repo|both]

  Print tracked wiki pages, repository structure, or both (the default).

  Titles are simple frontmatter scalars. Nodes describe files, not delivery status.
  Missing files and symlinks are excluded. No data contents or network are read.

Options:
  --root DIRECTORY       Avalanche repository root. Default: discover from cwd, then
                         package checkout.
  --depth INTEGER RANGE  Edges below the root (0: root only). Defaults: wiki 4, repo 2;
                         explicit depth shows nested files.  [0<=x<=20]
  --include-untracked    Also inventory nonignored untracked files, excluding data,
                         runtime and private cache directories.
  --json                 Emit the same bounded tree as JSON with checkout provenance.
  --help                 Show this message and exit.
```

## Structured inventory

The [reference inventory](assets/content/Phase%20II/Wiki/Manual/reference-inventory.json) retains typed parameter metadata, including repeatability and required arguments, plus source hashes. Regenerate with `uv run --frozen python scripts/manual_reference.py build`; use `check` to detect changes.
