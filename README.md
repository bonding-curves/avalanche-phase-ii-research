# Avalanche Phase II: Staking Economics Research

A calibrated simulation of Avalanche Primary Network staking, built by BCRG, the Bonding Curve Research Group, for the Avalanche Foundation. It forecasts how validators commit, renew, leave and return under a given reward design, so that reward parameters and mechanisms can be tested before the Foundation changes them.

**The decision it supports:** which reward and admission designs the Foundation proposes for the Primary Network, judged on the stake, issuance and decentralisation each would produce. **Readers:** the Foundation's economics team, the researchers who review the model, and the engineers who run it.

[![The v0.8.0 model: staking events measured before the origin fit the behaviour blocks, six stages run each day in order and read and write the state, and the run writes a daily table that the KPIs read](src/avalanche_research/model/images/v0.8-structure.png)](src/avalanche_research/model/README.md)

**Status, 13 October 2026:** staking model v0.8.0, released on `main`. Tag `model-v0.8.0` pending its release review, previous release `model-v0.7.0`. 1,647 tests, all passing with the input data. The pinned input data is not yet distributed (see [Data availability](#data-availability)).

## Contents

1. [Start here](#start-here)
2. [What is in it](#what-is-in-it)
3. [Deliverables](#deliverables)
4. [Resources](#resources)
5. [Quick start](#quick-start)
6. [Data availability](#data-availability)
7. [Versions](#versions)
8. [Writing links](#writing-links)
9. [License](#license)

## Start here

| Reader | Read |
| --- | --- |
| Client reader at the Foundation | The [model README](src/avalanche_research/model/README.md), sections 1, 2, 5 and 6: what the model does, the questions it answers, how v0.8.0 was chosen, and its limits. Then the [Milestone pages](<content/Phase II/Milestones/index.md>) for each deliverable's status |
| Reviewer | The [model README](src/avalanche_research/model/README.md), sections 3 to 6, and the [v0.8.0 selection evidence](results/model-v0.8.0-selection/README.md), whose script recomputes the verdict from the committed scores. The [v0.7 validation report](<content/Phase II/Milestones/Milestone 1/Preliminary Validation Report/index.md>) covers the protocol layer's verification |
| Engineer | [Quick start](#quick-start) below, [SETUP.md](SETUP.md) for a fresh machine, then the [model README](src/avalanche_research/model/README.md), sections 7 to 9: run it, change it, and its files |

## What is in it

| Folder | Contents |
| --- | --- |
| [`src/avalanche_research/`](src/avalanche_research/) | The Python package: data sources and builds, the protocol staking rules, the staking model, reward and admission mechanisms, chart views, and the `avalanche` command line tool |
| [`tests/`](tests/) | The test suite for the package |
| [`notebooks/`](notebooks/) | Five notebooks saved with their outputs: the model story (v0.7), the mechanism explorer, staking periods, the first lifecycle model (v0), and a reading of Eric Lu's article on validator rewards |
| [`content/`](content/) | The research site's pages: Phase II milestones and deliverables, briefs, reference pages, source collections, and the Phase I archive |
| [`.site/`](.site/) | The site engine, Quartz, pinned with its Node dependencies |
| [`data/`](data/) | The data catalog, its JSON schema, the SQL queries behind each Snowflake dataset, and the data guide. Data files are not stored in Git |
| [`results/`](results/) | Committed results with the script that rebuilds each one, starting with the v0.8.0 selection |
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

## Resources

| Document | What it holds |
| --- | --- |
| [Model README](src/avalanche_research/model/README.md) | Model v0.8.0 for a client reader: its stages, what is fitted, swept and fixed, its limits, how to run and change it |
| [v0.8.0 selection evidence](results/model-v0.8.0-selection/README.md) | The distribution scores that chose v0.8.0, every batch's specification hash, the verdict, and the commands that reproduce them |
| [v0.7 validation report](<content/Phase II/Milestones/Milestone 1/Preliminary Validation Report/index.md>) | Milestone 1's assessment of model v0.7: the protocol layer's verification against the chain and forecast scores at 19 dates |
| [Data guide](data/README.md) | Every dataset, its source, and how it is captured and checked |
| [Glossary and notation](<content/Phase II/Wiki/Reference/Glossary and Notation.md>) | The terms and symbols the reports use |

## Quick start

You need `git`, [uv](https://docs.astral.sh/uv/), Node.js 22 or later, and Graphviz. [SETUP.md](SETUP.md) gives every step for a fresh machine.

```sh
git clone git@github.com:bonding-curves/avalanche-phase-ii-research.git
cd avalanche-phase-ii-research
uv sync --locked --group model --group notebook
uv run pytest -q
uv run avalanche model describe
```

The suite takes 2 to 3 minutes. With the input data all tests pass. Without it, 37 skip and 17 tests of the one-time scoring script fail, because they read a data run instead of skipping. The Foundation's copy of the code is the `phase-ii` branch of `AVL-Foundation/ext-bcrg-validator-research`, last updated on 1 October 2026. `avalanche model describe` needs no data. It prints the mainnet staking parameters and upgrade schedule the model uses.

Open the notebooks:

```sh
uv run jupyter trust notebooks/*.ipynb
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
