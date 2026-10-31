# 8. Use the CLI from orientation to a checked result

*Draft for review.*

[Manual contents](README.md)

The CLI provides orientation, data inspection and preparation, reward calculations, model execution and checks. Python scripts provide the packaged experiment, central-case replay and bounded research cycle. This walkthrough explains when to use each. The [CLI reference](cli.md) lists every option directly from the installed Click definitions.

Run commands from the repository root. Follow [setup](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/SETUP.md) first, including access to this repository and a supported Python environment. Install the locked modeling and figure dependencies:

```sh
uv sync --locked --group model --group notebook
uv run --frozen avalanche --version
uv run --frozen avalanche --help
```

`uv` creates the project environment. The extra groups supply the model and notebook/figure packages. Provider capture can need additional groups and credentials described in setup. The included example and arithmetic calculation need no Snowflake credentials.

## Find your place before choosing a run

```sh
uv run --frozen avalanche research tree wiki
uv run --frozen avalanche research tree repo
uv run --frozen avalanche research tree both --json
uv run --frozen avalanche model describe
```

`research tree` prints documentation or repository structure. Wiki depth defaults to four and repository depth to two. Explicit depth and format options are in its help. `model describe` lists registered variants and their descriptions. Registration does not guarantee that every developmental variant has the inputs needed by the generic runner.

The trees answer where material lives. Read the manual for the current model and the dated reports for findings. Historical pages preserve earlier assumptions and should be read with their model version.

## Calculate one potential reward without data

```sh
uv run --frozen avalanche model reward --stake 2000 --duration 14 --start 2026-09-01T00:00:00 --supply 465000000
```

This computes **4.239076507 AVAX** of potential reward for the supplied terms. Stake and supply are in AVAX and duration is in days. This is an arithmetic example before Helicon, with an explicit supply input. It neither fetches a historical counter nor verifies eventual uptime or payment. Change one input at a time to see how duration, time and supply affect the formula.

## Inspect local data availability

```sh
uv run --frozen avalanche data list
uv run --frozen avalanche data describe derived.staking-periods
uv run --frozen avalanche data runs derived.staking-periods
uv run --frozen avalanche data manifest
```

`list` shows catalog datasets. `describe` explains a contract. `runs` lists locally installed runs for that identifier. `manifest` summarizes local availability and checks. A catalog entry is a supported data contract, not proof that its tables are installed.

These operations inspect local information. By contrast, `data freshness` contacts providers to compare source and local coverage. Its result describes availability at query time and may require provider authentication.

## Run and inspect the included small experiment

```sh
uv run --frozen --group model --group notebook python scripts/first_experiment.py --output release/first-experiment
uv run --frozen --group model --group notebook python scripts/first_experiment.py --output release/first-experiment --check
```

The [example guide](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/first-experiment/README.md) describes the included snapshot and output contract. The first command executes four paired 30-day paths and writes trajectories, summaries, receipts and a browser figure. The second checks the saved outputs without simulating them again. A successful result reports `pass`. Open `release/first-experiment/figure.html` in a browser.

This tutorial uses renewal and entry responses of 0.5 to make the mechanism visible. It is separate from the central reported comparison, whose responses are 0.025 and 0.04. Its inputs and reduced horizon also differ. Each new experiment should use a new output directory so its contract remains unambiguous.

Inspect the hypothesis, settings, matching baseline, median differences and output hashes. Then ask what the result means under those settings. Passing the output check establishes reproducibility and integrity, rather than an empirical validation of the response coefficients.

## Reproduce the report's central comparison

The [reproduction guide](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/report-reproduction/README.md) provides the complete commands and expected percentile table. Its input download is authenticated against a fixed digest and requires access to the repository's release asset, rather than a live provider connection.

```sh
uv run --frozen --group model python scripts/reproduce_report.py fetch --output release/report-inputs
uv run --frozen --group model python scripts/reproduce_report.py run --inputs release/report-inputs --output release/report-result
uv run --frozen --group model python scripts/reproduce_report.py check --inputs release/report-inputs --output release/report-result
uv run --frozen --group model --group notebook python scripts/figures/central_case_reproduction.py --inputs release/report-inputs --result release/report-result --output release/report-figure
```

This is the reported 50-pair, 365-day comparison with the early 90-day ACP-285 ramp. It verifies the 100 reconstructed paths against the archived record. The median is 12.7721% less promised reward with 98.6901% of baseline own stake retained. These are conditional counterfactual results. The exercise does not reproduce every Milestone 2 sweep or establish the policy's causal effect on the chain.

The input file is about 12.1 MB. Read the guide's environment and evidence qualifications before starting. Keep this output separate from the smaller tutorial.

## Prepare new datasets deliberately

A provider workflow has distinct steps. The command forms below use placeholders. Substitute a catalog identifier, valid paths and provider-specific values after reading `data describe` and the implementation listed in the [dataset reference](datasets.md).

```text
avalanche data fetch ID --output CAPTURE --param KEY=VALUE --preview
avalanche data fetch ID --output CAPTURE --param KEY=VALUE
avalanche data build ID --from CAPTURE --output DATASET --preview
avalanche data build ID --from CAPTURE --output DATASET
avalanche data check ID --capture CAPTURE --dataset DATASET
```

`fetch` captures source records and a receipt. `build` normalizes captured bytes into the dataset contract. Supported preview paths inspect the intended operation before execution. Provider-specific `--param` keys are not universal CLI options. Check the dataset contract for required captured tables. The build command has no generic `--param` option.

`check --dataset DATASET` writes or replaces `check.json` in that directory. It is not a read-only inspection. Read the check result before using the dataset. Capture may require a named Snowflake connection, an API credential or public RPC access. Keep credentials in their supported local configuration rather than experiment JSON or reports.

A derived dataset uses previously built runs:

```text
avalanche data derive ID --input INPUT_ID=INPUT_RUN --output DERIVED_RUN
avalanche data pin PIN_NAME ID_A ID_B --run ID_A=RUN_A --run ID_B=RUN_B
avalanche data pin-check PIN_PATH
```

Repeat `--input` for each required producer input. A pin binds selected runs, output hashes and check status. `pin-check` verifies these local identities and stored status. It does not rerun all dataset checks, refresh the source or download missing files. A recipient needs both the pin and its authenticated data.

## Use the generic model runner with a full pin

The following template assumes its pin and required datasets are installed. The small worked snapshot is not a substitute for all inputs of a general run.

```sh
uv run --frozen --group model avalanche model run data/pins/p2-model-v0.8.json release/scenario --origin 2025-11-18 --model v0.8.0 --runs 4 --timesteps 30 --seed 0 --workers 1
```

The arguments select input pin and output directory. The options fix the origin, variant, stochastic runs, horizon, seed and local workers. The general command defaults are `v0.8.0`, 20 runs, 180 days and seed zero, with automatic worker selection. Explicit settings make a tutorial or receipt easier to review.

`model run` executes immediately after validation. It has no preview or dry-run option. Choose the complete settings before launching. Inspect its output receipt and authenticated row outputs. Use the packaged example or report replay checkers when checking those specific saved workflows. The separate `model check` command reconstructs recorded potential rewards from three built datasets. It does not check a generic simulation output.

```text
avalanche model check --validators VALIDATOR_DATASET --delegators DELEGATOR_DATASET --supply SUPPLY_DATASET
```

This check compares protocol arithmetic with captured validator and delegator records, reporting disagreement by regime. It requires the corresponding normalized datasets and is distinct from testing behavioural predictions.

## Specify a sweep before running it

```text
avalanche model sweep DESIGN_JSON OUTPUT_DIRECTORY
```

A sweep JSON declares the input pin, origins, model variants, scenario design, path count, horizon and worker count. Cartesian generation enumerates levels. Scrambled Sobol generation samples bounded settings. Explicit rows can carry externally specified designs and per-row draws with required hashes. The [experiment chapter](experiments.md) explains the distinctions.

Use [`experiments/sweep.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/experiments/sweep.py) for the accepted design schema and [`model/designs.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/designs.py) for generator contracts. Start from a delivered, authenticated experiment definition rather than guessing JSON keys. Standard generic sweeps require the full pin, including monetary inputs when computing KPIs. Optional variants can require additional preparation adapters.

A sweep validates its declared row count and identities, reuses preparation and records output hashes. Verified completed rows support resumption. Worker processes execute local model rows, rather than distributing jobs across machines. There is no sweep preview option. A Sobol sample is a design and does not automatically calculate Sobol sensitivity indices.

## Run one documented research cycle

```sh
uv run --frozen --group model --group notebook python scripts/research_cycle.py run --output release/research-cycle
uv run --frozen --group model --group notebook python scripts/research_cycle.py read --output release/research-cycle
```

The [research-cycle guide](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/research-cycle/README.md) explains the declared hypothesis, experiment, artifact verification and numerical assessment. A methodology reflection is a separately authored JSON record submitted through `reflect --record`. Bind it to the analysis it reviews and state the question, proposed change, owner and success test.

This driver currently wraps the first experiment. Its numeric predicates assess the declared comparison. They are not a generic significance test or an automatic research-quality verdict. Repeating a completed run is idempotent. Interrupted work has an explicit resume path. Changed contracts need a new directory. No recurring scheduler or automatic hypothesis generator starts with these commands.

## Read machine output and failures

Use each command's `--help` to confirm whether it supports JSON output. Most command results use `avalanche-cli-result/v1`. `research tree` has its own format. A non-passing result normally exits with status 1, while declared data/model errors exit with status 2. A consumer should inspect both exit status and the returned result, rather than scraping a success-looking sentence.

| Symptom | First check |
| --- | --- |
| Required model package missing | Confirm the locked install includes the `model` group |
| Pin points to absent data | Install the matching dataset outputs, then run `pin-check` |
| Provider authentication fails | Inspect the selected provider's local connection configuration |
| Coverage stops before the requested origin | Inspect run metadata and checks rather than silently extending history |
| Output directory belongs to another experiment | Use a new directory with the new contract |
| Reward arithmetic and payout differ | Compare promise timestamp, duration, supply and uptime treatment |
| CLI reference differs from help | Run the reference check below and review the source change |

## Keep the manual synchronized with the interface

```sh
uv run --frozen python scripts/manual_reference.py check
uv run --frozen python scripts/export_research_manual.py --check
```

The first checks generated command, module and dataset references against the installed source. It inspects Click definitions without executing command callbacks and parses modules without importing them. The second checks the GitHub reading copy and copied dependencies. Regeneration uses `manual_reference.py build` and the exporter without `--check`. Generated metadata still requires editorial review when command effects change.

By the end of this walkthrough, a reader should be able to locate a report, interpret a reward calculation, distinguish data contracts from installed data, execute the small paired example, verify a saved result and specify the inputs needed for a larger experiment.
