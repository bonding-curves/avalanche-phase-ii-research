# Tests

This folder holds the test suite for the `avalanche_research` package. The tests check that each data source captures, builds, and checks its dataset correctly, that the protocol rules reproduce the chain's arithmetic, and that the model, the mechanisms, and the scoring give known answers on small inputs. They run with pytest and need no network access and no credentials.

The subfolders mirror the package. Most tests build small synthetic inputs whose correct result is known in advance, such as a two-validator node response or a short series with a known forecast error. A source test passes the capture code a fake response in place of the provider, then builds and checks the result.

## Main files and folders

| Path | What it tests |
| --- | --- |
| `core/` | The data catalog and the clock |
| `sources/` | One file per provider module: request, capture receipt, build, and check |
| `datasets/` | Loading runs, pins, and each derived table, such as the staking-period log, the seam between sources, the node and operator tables, and the monetary ledger |
| `domain/` | The protocol's reward and staking rules, and the key and address derivation |
| `test_replay.py`, `test_lifecycle.py`, `test_fitted_lifecycle.py`, `test_blocks.py`, `test_streams.py`, `test_evaluation.py` | The model: the replay against the ledger, models v0.7 and v0.8, behaviour blocks, keyed random draws, and forecast scores |
| `test_mechanisms.py`, `test_admission.py`, `test_mechanism_cohort.py` | Reward and admission mechanisms equal the chain's rule at neutral settings and keep their required properties |
| `test_staking_*.py` | The staking summaries by cohort, duration, renewal, and active state |
| `test_practice_*.py` | Textbook models with known answers, which test the modelling conventions |
| `test_seed_audit.py` | Every random draw in the library and scripts is keyed through `model.streams` or is a listed exception with its reason |
| `test_architecture.py`, `architecture-baseline.txt` | The package's import rules from `pyproject.toml`. A new break fails, and the baseline lists the known ones |
| `test_model_story_views.py`, `test_diagrams.py`, `test_check_links.py`, `test_notebook_budgets.py` | Figures, generated diagrams, the site link check, and the notebook measures |

## Run

From the repository root:

```sh
uv sync --locked --group model --group notebook
uv run pytest -q
```

The full suite takes a few minutes. To run one area, name its folder or file:

```sh
uv run pytest tests/core tests/datasets/test_pins.py -q
uv run --group model python -m pytest tests/test_lifecycle.py -q
```

A few tests read the built staking-period log or monetary ledger and skip when those runs are not in `data/runs/`. The diagram test skips when Graphviz's `dot` is not installed. The tests of the site scripts are in `scripts/` and run with `uv run python -m unittest discover -s scripts -p 'test_*.py'`.

## How this folder connects to the rest

Each test imports the code in [`src/avalanche_research/`](../src/avalanche_research/README.md) and, for the catalog tests, the definitions in [`data/`](../data/README.md). The [scripts](../scripts/README.md) and [notebooks](../notebooks/README.md) call the same code to make the figures and tables the research site publishes.
