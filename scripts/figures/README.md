# Figure scripts

This folder holds one script per chart, or per set of related charts, shown on the research site and in the research reports. Each script reads named data runs through `avalanche_research.datasets`, or the score tables another script wrote, and draws them with the plotting functions of the package. Any published image can therefore be redrawn from its inputs.

Most scripts write four files with one stem: a PNG for the page, an HTML file for interactive use, a CSV holding exactly the drawn data under readable column names, and a JSON **receipt** that names every input with its SHA-256 hash. Some older scripts write only HTML and CSV. Each script's docstring names its inputs, its outputs, and the definitions behind the chart.

## Main files

| Files | Charts |
| --- | --- |
| `model_v07_record.py`, `model_v07_report.py`, `model_v07_experiments.py` | The v0.7 research report: the staking record, the model's inputs and reward formula, forecast scores, forecast fans, the five reward designs, and sensitivity |
| `model_v08_figures.py`, `m1_calibration.py` | The v0.8 candidate: its forecast scores, and its fitted renewal terms and return hazard with 95% intervals |
| `model_story_figures.py`, `model_v0_figures.py` | The model notebook's figures, and the earlier model memo's replay, reward curves, and mechanism sweep |
| `ingestion_coverage.py` | Staking periods ingested per month since 2020, for deliverable 1.1 |
| `helicon_first_days.py`, `helicon_institutional.py`, `helicon_eda.py`, `helicon_scatter.py`, `commitments_by_upgrade.py` | Validator commitments by duration and upgrade, before and after Helicon |
| `benqi_delegation_share.py`, `gogopool_short_share.py` | BENQI's share of delegated AVAX, and the share of short commitments made through GoGoPool |
| `etf_holdings.py`, `opportunity_costs.py` | AVAX held by exchange-traded funds, and the annual rates AVAX holders can earn outside staking |
| `em2_minimum_stake.py`, `cheapest_seat.py`, `pilot_admission_frontier.py`, `pilot_levers_diagram.py` | A minimum validator stake that falls with committed duration, and the levers on a validator's choice |
| `diagrams.py` | The data path from sources to the model's tables, drawn from run receipts with Graphviz |
| `model_v08_structure.py` | The released v0.8.0 model's structure, traced from its code and drawn with Graphviz, for the model README |
| `png.py` | Shared helper that renders a saved HTML chart to PNG with a headless Chromium |

## Run

Run from the repository root. Charts need the `notebook` group, and charts that build a model or a mechanism also need the `model` group. Each script takes an output folder, and some take a chart name or input files:

```sh
uv sync --locked --group model --group notebook
uv run --group notebook python scripts/figures/model_v07_report.py --help
uv run --group notebook python scripts/figures/model_v07_record.py record <output folder>
```

The `--help` command needs no data. A chart needs the runs its docstring names in `data/runs/`. `model_v07_record.py` also verifies its pin and stops on any finding. PNG output from HTML needs Chromium and network access, because the page loads BokehJS from its public CDN. The diagram scripts need Graphviz's `dot`.

## How this folder connects to the rest

The inputs are the runs defined in [`data/`](../../data/README.md) and pinned in [`data/pins/`](../../data/pins/README.md), and the score tables written by the scoring scripts in [`scripts/`](../README.md). Shared drawing code lives in [`src/avalanche_research/views/`](../../src/avalanche_research/README.md). The outputs go into the page folders under `content/`, where each figure appears with a caption that names its source.
