# The `avalanche_research` package

This folder is the Python package behind the research. It captures data from each provider, builds and checks the datasets the data catalog defines, encodes the Primary Network's staking and reward rules, runs the staking model, and draws the charts the notebooks and the site show. The scripts, the notebooks, and the `avalanche` command line tool all call it.

The package is arranged in layers that import in one direction only. `core` imports nothing else in the package. `sources` and `domain` import `core`. `datasets` and `model` sit above them, and `views` and `cli` sit on top. The model's rules and simulations import no data code, so they run on any table passed to them. The rules are declared in `pyproject.toml`, and `tests/test_architecture.py` fails on any break that is not in its list of known exceptions.

## Main files and folders

| Path | What it holds |
| --- | --- |
| `core/` | Errors, hashing, units, the clock, and the data catalog with each dataset's contract |
| `sources/` | One module per outside provider, such as Snowflake, the P-Chain and C-Chain nodes, the Data API, and price and yield sources. Each writes a captured run |
| `datasets/` | Loading built runs by catalog ID (`datasets.load`, `datasets.connect`), pinned input sets (`pins.py`), and `derived/`, the tables built from other runs, such as the staking-period log and the daily monetary ledger |
| `domain/protocol/` | The staking and reward rules, each cited to the ACP text and the AvalancheGo code it follows, with integer arithmetic in the same order as the Go code |
| `model/` | The staking model: engine, replay, lifecycle models v0.7 and v0.8, and forecast scoring. See [`model/README.md`](model/README.md) |
| `mechanisms/` | Reward and admission designs as Param classes, each equal to the chain's rule at its neutral settings |
| `views/` | Notebook and site figures: model structure, model results, the mechanism explorer, and generated diagrams |
| `staking_*.py`, `freshness.py`, `reproduction.py` | Staking summaries by cohort, duration, renewal, and active state, the source freshness check, and reproductions of published results |
| `practice/` | Small textbook models with known answers, used to test the modelling conventions |
| `cli.py` | The `avalanche` command: `data` and `model` subcommands |

Most other single files here, such as `pchain.py`, are older import names kept for compatibility with the modules' new locations.

## Install and run

From the repository root:

```sh
uv sync --locked --group model --group notebook
uv run avalanche --help
uv run avalanche model describe
uv run avalanche data list
```

`model describe` needs no data. It prints the mainnet reward parameters and the 13 protocol changes the rules encode, each with its ACP, its upgrade, and the time it is keyed by. In Python, load a built dataset with `from avalanche_research import datasets` and `datasets.load("derived.staking-periods")`.

## How this folder connects to the rest

The package reads its dataset definitions from [`data/`](../../data/README.md) and its built runs from `data/runs/`. The [scripts](../../scripts/README.md) and [notebooks](../../notebooks/README.md) call it to make every table and figure that the research site under `content/` publishes. The [tests](../../tests/README.md) cover each layer.
