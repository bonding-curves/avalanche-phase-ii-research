# Avalanche Phase II: Staking Economics Research

This repository holds the Phase II research on Avalanche staking economics, carried out for the Avalanche Foundation by BCRG, the Bonding Curve Research Group. The research asks how validator and delegator behavior, the reward design, and protocol changes together set the network's economic security. Its aim is a calibrated model of Primary Network staking that tests reward parameters and mechanisms before the Foundation changes them.

The repository contains the model and data code, its tests, two notebooks, and a research site that maps every deliverable in the grant agreement to its evidence and status.

## What is in it

| Folder | Contents |
| --- | --- |
| [`src/avalanche_research/`](src/avalanche_research/) | The Python package: data sources and builds, the protocol staking rules, the staking model, reward and admission mechanisms, chart views, and the `avalanche` command line tool |
| [`tests/`](tests/) | The test suite for the package |
| [`notebooks/`](notebooks/) | Two notebooks saved with their outputs |
| [`content/`](content/) | The research site's pages: Phase II milestones and deliverables, briefs, reference pages, source collections, and the Phase I archive |
| [`.site/`](.site/) | The site engine, Quartz, pinned with its Node dependencies |
| [`data/`](data/) | The data catalog, its JSON schema, the SQL queries behind each Snowflake dataset, and the data guide. Data files are not stored in Git |
| [`scripts/`](scripts/) | Site checks, milestone page and figure builders, and the notebook check |

## Deliverables

| Deliverable | Where it lives |
| --- | --- |
| Milestone pages | [`content/Phase II/Milestones/`](<content/Phase II/Milestones/index.md>). Each deliverable in the agreement has its own page with its status and evidence |
| Milestone 1 | [Milestone 1](<content/Phase II/Milestones/Milestone 1/index.md>). [1.1 Data Ingestion](<content/Phase II/Milestones/Milestone 1/1-1 Data Ingestion/index.md>) and [1.2 Data Manifest](<content/Phase II/Milestones/Milestone 1/1-2 Data Manifest/index.md>) are delivered for review. 1.3 Staking Model Spec, 1.4 Behavioral Calibration, and the Preliminary Validation Report are being rebuilt within Milestone 2 |
| Status of every deliverable | [Phase II overview](<content/Phase II/index.md>) |
| Staking model v0.7 | [`src/avalanche_research/model/`](src/avalanche_research/model/) and [`src/avalanche_research/mechanisms/`](src/avalanche_research/mechanisms/). The protocol reward rules, the validator lifecycle model on cadCAD and Param, and the reward and admission mechanisms it compares |
| Model notebook | [`notebooks/model-story.ipynb`](notebooks/model-story.ipynb). Model v0.7's structure traced from its code, the reward designs it compares, the validator response to issuance, a test of the lifecycle model across five protocol upgrades, and the model's version roadmap |
| Mechanism notebook | [`notebooks/mechanism-explorer.ipynb`](notebooks/mechanism-explorer.ipynb). Reward and admission mechanisms compared on one reference cohort of real stakes |
| Reports and briefs | [Briefs](<content/Phase II/Wiki/Briefs/index.md>) and the reference pages on [data](<content/Phase II/Wiki/Reference/Data.md>) and [glossary and notation](<content/Phase II/Wiki/Reference/Glossary and Notation.md>) |
| Governing documents | [Milestone 0](<content/Phase II/Milestones/Milestone 0/index.md>): the signed agreement and proposal v2.5 |
| Phase I archive | [Phase I](<content/Phase I/index.md>), the 2025 research as delivered |

The pages under `content/` are best read on the research site, where links, charts, and diagrams render. GitHub shows their text.

## Quick start

You need `git`, [uv](https://docs.astral.sh/uv/), Node.js 22 or later, and Graphviz. [SETUP.md](SETUP.md) gives every step for a fresh machine.

```sh
git clone --branch phase-ii git@github.com:AVL-Foundation/ext-bcrg-validator-research.git
cd ext-bcrg-validator-research
uv sync --locked --group model --group notebook
uv run pytest -q
uv run avalanche model describe
```

The suite has 652 tests and takes 2 to 3 minutes. Without the input data, 649 pass and 3 skip. `avalanche model describe` needs no data. It prints the mainnet staking parameters and upgrade schedule the model uses.

Open the notebooks:

```sh
uv run jupyter trust notebooks/model-story.ipynb notebooks/mechanism-explorer.ipynb
uv run jupyter lab notebooks/
```

GitHub shows the notebooks' text and code but does not draw their interactive charts. In JupyterLab, a trusted notebook draws its saved charts without running any cell. Do not run the notebooks before the input data arrives (see below).

Run the research site:

```sh
cd .site
npm ci
uv run --project .. npm run dev
```

Open <http://localhost:8844>.

## Data availability

Data files are too large for Git and are not stored here. The [data guide](data/README.md) and the [data catalog](data/data-catalog.json) define every dataset, its source, and how it is captured and checked.

The model's input data, a pinned input set, follows on 2026-10-07. Until then the notebooks show their saved outputs and cannot be rerun. Run without the data, a notebook stops at its first data cell with a `DataError` that names the missing run. Without it, 3 of the 652 tests skip.

## Versions

| Item | Version |
| --- | --- |
| Python package `avalanche-phase-ii-research` | 0.1 (`0.1.0.dev0` in [`pyproject.toml`](pyproject.toml)) |
| Staking model | v0.7. Each model run records `MODEL_VERSION = "0.7.0"` |

## License

Copyright (c) 2026 Longtail Financial Corp., operating as the Bonding Curve Research Group (BCRG). All rights reserved. See [LICENSE.md](LICENSE.md). The site engine in `.site/` is Quartz, under its own MIT license in [`.site/LICENSE.txt`](.site/LICENSE.txt).
