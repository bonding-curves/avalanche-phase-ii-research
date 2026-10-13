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
| Milestone 1 | [Milestone 1](<content/Phase II/Milestones/Milestone 1/index.md>). Accepted by the Foundation in August 2026. Its five deliverables were rebuilt on model v0.7 and published on 8 October 2026 |
| Status of every deliverable | [Phase II overview](<content/Phase II/index.md>) |
| Staking model v0.8.0 | [`src/avalanche_research/model/`](src/avalanche_research/model/) and [`src/avalanche_research/mechanisms/`](src/avalanche_research/mechanisms/). The protocol reward rules, the validator lifecycle model on cadCAD and Param, and the reward and admission mechanisms it compares |
| Model notebook, written for v0.7 | [`notebooks/model-story.ipynb`](notebooks/model-story.ipynb). Model v0.7's structure traced from its code, the reward designs it compares, the validator response to issuance, a test of the lifecycle model across five protocol upgrades, and the model's version roadmap |
| Mechanism notebook | [`notebooks/mechanism-explorer.ipynb`](notebooks/mechanism-explorer.ipynb). Reward and admission mechanisms compared on one reference cohort of real stakes |
| Reports and briefs | [Briefs](<content/Phase II/Wiki/Briefs/index.md>) and the reference pages on [data](<content/Phase II/Wiki/Reference/Data.md>) and [glossary and notation](<content/Phase II/Wiki/Reference/Glossary and Notation.md>) |
| Governing documents | [Milestone 0](<content/Phase II/Milestones/Milestone 0/index.md>): the signed agreement and proposal v2.5 |
| Phase I archive | [Phase I](<content/Phase I/index.md>), the 2025 research as delivered |

The pages under `content/` are best read on the research site, where links, charts, and diagrams render. GitHub shows their text.

## Quick start

You need `git`, [uv](https://docs.astral.sh/uv/), Node.js 22 or later, and Graphviz. [SETUP.md](SETUP.md) gives every step for a fresh machine.

```sh
git clone git@github.com:bonding-curves/avalanche-phase-ii-research.git
cd avalanche-phase-ii-research
uv sync --locked --group model --group notebook
uv run pytest -q
uv run avalanche model describe
```

The suite has 1,636 tests and takes about 3 minutes. With the input data all pass. Without it, 37 skip and 17 tests of the one-time scoring script fail, because they read a data run instead of skipping. The Foundation's copy of the code is the `phase-ii` branch of `AVL-Foundation/ext-bcrg-validator-research`, last updated on 1 October 2026. `avalanche model describe` needs no data. It prints the mainnet staking parameters and upgrade schedule the model uses.

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

The model's pinned input sets are not yet distributed with this repository. A command that fetches and checks them is planned with the code transfer of Milestone 3. Until then the notebooks show their saved outputs and cannot be rerun. Run without the data, a notebook stops at its first data cell with a `DataError` that names the missing run.

## Versions

| Item | Version |
| --- | --- |
| Python package `avalanche-phase-ii-research` | 0.1 (`0.1.0.dev0` in [`pyproject.toml`](pyproject.toml)) |
| Staking model | v0.8.0, released on `main` on 13 October 2026. Each model run records `MODEL_VERSION = "0.8.0"`. The tag `model-v0.8.0` follows its release review. v0.7 is tagged `model-v0.7.0` |

## Writing links

Pages under `content/` are published by the research site, so their links must point at what the site publishes, not at files in this repository.

| Link to | Write it as | Example |
| --- | --- | --- |
| Another page | The page's site route, from the root | `[1.3 Staking Model Spec](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/)` |
| A heading on a page | The route with the heading's anchor | `[the boundary](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/#boundary)` |
| An image or data file | Copy it into the page's folder and link its route from the root. Relative links such as `figure.png` break, because the site resolves links from its root | `![Figure 1](/Phase-II/Milestones/Milestone-1/milestone-1-chain.png)` |
| An outside source | Its full `https://` address | `[ACP-285](https://github.com/avalanche-foundation/ACPs)` |

A source file elsewhere in the repository, such as a script or a notebook, is not a published page. Name it in code format, for example `scripts/milestone_pages.py`, rather than linking it. Before committing a change to `content/`, run `npm --prefix .site run verify`, which fails on any new link the site cannot resolve.

## License

Copyright (c) 2026 Longtail Financial Corp., operating as the Bonding Curve Research Group (BCRG). All rights reserved. See [LICENSE.md](LICENSE.md). The site engine in `.site/` is Quartz, under its own MIT license in [`.site/LICENSE.txt`](.site/LICENSE.txt).
