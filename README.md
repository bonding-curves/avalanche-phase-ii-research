# Avalanche Phase II: Staking Economics Research

Avalanche pays validators with newly issued AVAX. This research compares how reward designs change that issuance, the stake validators commit, and participation in the Primary Network. BCRG, the Bonding Curve Research Group, builds the model for the Avalanche Foundation.

The model follows individual validator staking periods through renewal, departure, return and arrival. Parameter selection under uncertainty, or **PSUU**, compares reward settings across sampled conditions, reduces the simulated paths to measures, and scores those measures against working network goals. The Foundation chooses the goals and acceptable tradeoffs.

[![Model v0.8.0: historical staking events supply the behaviour blocks, six ordered daily stages update the state, and daily outputs supply the performance measures](src/avalanche_research/model/images/v0.8-structure.png)](src/avalanche_research/model/README.md)

Release as of 28 October 2026: staking model v0.8.0, tagged `model-v0.8.0`. The Foundation copy is on [`milestone-2`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/tree/milestone-2). Installation checks and the model description work without data. Repeating a simulation requires pinned input snapshots that are not yet distributed with this repository.

## Contents

1. [Start here](#start-here)
2. [Quick start](#quick-start)
3. [Economic model](#economic-model)
4. [Goals and measures](#goals-and-measures)
5. [Model terminology](#model-terminology)
6. [Structure of the model](#structure-of-the-model)
7. [Background](#background)
8. [Change an experiment](#change-an-experiment)
9. [Analysis and evidence](#analysis-and-evidence)
10. [Data availability](#data-availability)
11. [Deliverables and resources](#deliverables-and-resources)
12. [Versions](#versions)
13. [Writing links](#writing-links)
14. [License](#license)

## Start here

**Model and simulation setup:** read the [30 October pre-read](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/docs/review/2026-10-30/modeling.md). It explains the model, fixes one central experiment and links to the supporting evidence. No installation is needed to read it.

| Your task | Entry point |
| --- | --- |
| Assess a reward-policy comparison | Read [Economic model](#economic-model), then the [results memo](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/docs/review/2026-10-30/results.md) for the experiment, working goals and findings |
| Review the mathematics and evidence | Read the [model README](src/avalanche_research/model/README.md), the [v0.7 model specification](<content/Phase II/Milestones/Milestone 1/1-3 Staking Model Spec/index.md>) and the [v0.8.0 selection evidence](results/model-v0.8.0-selection/README.md) |
| Install, run or extend the package | Follow [Quick start](#quick-start), then the model README's [run instructions](src/avalanche_research/model/README.md#run-it) and [change recipes](src/avalanche_research/model/README.md#change-it) |
| Locate a contractual deliverable | Open the [milestone index](<content/Phase II/Milestones/index.md>) |
| Follow the earlier research | Read the [research history](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/docs/research-history/README.md) for original May and June texts, figures and later context |

Inspect the wiki and repository structure without research inputs:

```sh
uv run --frozen avalanche research tree wiki
uv run --frozen avalanche research tree repo
```

Use `--depth 3` for more detail or `both --json` for machine-readable context. The [research orientation skill](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/.agents/skills/avalanche-research-orientation/SKILL.md) combines these commands with a guide to the model, evidence and research methodology. Invoke it as `$avalanche-research-orientation` in Codex, or read its `SKILL.md` in another agent.

## Quick start

You need repository access, `git` and [uv](https://docs.astral.sh/uv/). [SETUP.md](SETUP.md) gives the fresh-machine instructions, including Graphviz for model diagrams and Node.js for the research site.

```sh
git clone --branch milestone-2 git@github.com:AVL-Foundation/ext-bcrg-validator-research.git avalanche-phase-ii-research
cd avalanche-phase-ii-research
uv sync --locked --group model --group notebook
uv run avalanche model describe
uv run pytest -q
```

The description starts with `PASS | model describe | 13 mechanisms` and prints the protocol settings and upgrade schedule. The checked fresh installation without input data passes 2,127 tests and skips 37 in about four minutes. Those checks establish installation and tested software behaviour. Forecast evaluation is recorded separately in [Analysis and evidence](#analysis-and-evidence).

Read the saved notebook outputs in JupyterLab:

```sh
uv run jupyter trust notebooks/*.ipynb
uv run jupyter lab notebooks/
```

Trusting the delivered notebooks allows JupyterLab to display their saved interactive charts. Read them without rerunning cells until the required input snapshots are available. GitHub displays notebook text and code but does not render those interactive charts. [SETUP.md](SETUP.md) also covers building and serving the research site.

## Economic model

A validator commits AVAX for a staking period. When the period ends, its owner can renew, leave, or return later. New validators enter. The model starts from the observed commitments at an origin date and advances one UTC day at a time, recording stake, validator counts and rewards.

The [protocol layer](src/avalanche_research/domain/protocol/) computes potential rewards from stake, duration, the supply counter and the selected reward rule. The [behavioural layer](src/avalanche_research/model/README.md#what-is-fitted-swept-and-fixed) supplies renewal probabilities, return probabilities, arrival counts, durations and stake choices from historical decisions before the origin. In v0.8.0, three blocks use likelihood estimation. Duration uses conditional empirical resampling, and stake uses a hurdle model with empirical draws. The assumed strength of response to rewards is varied across experiments.

[cadCAD](https://github.com/cadCAD-org/cadCAD) executes the ordered state updates. Param declares the model's settings and bounds. A run produces a daily trajectory, which the performance measures reduce at a stated horizon. Matched runs under the chain's rule share random draws with each alternative, allowing the analysis to compare outcomes under the same simulated conditions.

The [model README](src/avalanche_research/model/README.md) explains the six daily stages, fitted and assumed settings, equations, code and use boundaries. Model v0.8.0 represents validator choices. Delegators' independent choices and automatic-renewal decisions are outside that release's behavioural model.

## Goals and measures

The research uses five working goals. Their thresholds and weights express policy judgements for the Foundation to refine. A **key performance indicator**, or KPI, is a measure computed from a simulated trajectory.

| Working goal | Measures used to assess it |
| --- | --- |
| Security holds | Validator stake retained against the matched chain-rule run, and the worst 30-day stake decline |
| Validators stay and stay spread | Active validators retained, concentration measured by the smallest node count holding more than a third of stake, and return margin |
| Holders pay less | Issuance saved against the matched chain-rule run, and annual net inflation |
| Security per AVAX issued | Stake retained relative to issuance retained |
| Longer staking | Stake-weighted duration of new commitments |

A utility converts a measure to a score between zero and one using a stated floor and target. The report distinguishes a setting with the highest weighted score from a range meeting the thresholds in a specified share of sampled runs. A sampled pass share describes the experiment's chosen conditions. It is not an estimated probability of real-world success.

The [report's goal definitions](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/docs/review/2026-10-30/results.md#23-kpi-computation) give the thresholds, weights and comparison horizons. In v0.8.0, rewards change commitment length only through the composition of participants. The longer-staking measure therefore needs separate interpretation from a directly modelled duration response.

## Model terminology

The [glossary and notation](<content/Phase II/Wiki/Reference/Glossary and Notation.md>) supplies the full vocabulary. These terms connect the model to an experiment:

| Term | Meaning |
| --- | --- |
| Origin | The observed date from which a simulation starts. Behavioural inputs use earlier observations |
| Mechanism | A reward or admission rule, with its own settings |
| Scenario | A declared environmental condition, such as an outside yield |
| Run | One simulated path for a specified mechanism, scenario, parameter draw and random seed |
| Sweep | A collection of runs covering a declared set of settings and conditions |
| Pinned input | A reference to exact input runs and their recorded hashes |
| Receipt | The record binding an output to its code, inputs, settings and hashes |

A consumption rate is a reward-formula parameter. It differs from the annual reward rate paid on stake. The model specification defines the conversion and units.

## Structure of the model

The package separates protocol rules, behaviour, experiment execution and analysis.

| Path | Responsibility |
| --- | --- |
| [`src/avalanche_research/domain/protocol/`](src/avalanche_research/domain/protocol/) | Mainnet reward arithmetic and upgrade rules |
| [`src/avalanche_research/mechanisms/`](src/avalanche_research/mechanisms/) | Alternative reward and admission rules |
| [`src/avalanche_research/model/`](src/avalanche_research/model/) | Validator behaviour, daily state updates, sweep execution, KPIs and forecast evaluation |
| [`src/avalanche_research/analysis/`](src/avalanche_research/analysis/README.md) | Matched comparisons, sensitivity calculations, decision trees and risk analysis |
| [`data/`](data/README.md) | Dataset catalog, source queries, run layout and input pins |
| [`results/`](results/) | Committed result tables, specifications and reproduction instructions |
| [`notebooks/`](notebooks/) | Explanatory and exploratory notebooks saved with outputs |
| [`tests/`](tests/) | Software checks, including synthetic inputs for data-free execution |
| [`content/`](<content/Phase II/index.md>) | Research pages, milestone evidence, briefs and source collections |

## Background

Reward policy trades issuance against the stake and participation it sustains. Issuance per unit of stake measures the cost of paying for security. It differs from the cost of attacking the network. Both the reward rule and holders' responses matter when comparing alternatives.

The [Essential Readings](<content/Phase II/Wiki/Collections/Essential Readings/index.md>) introduce the Foundation's economic questions. The [v0.7 model specification](<content/Phase II/Milestones/Milestone 1/1-3 Staking Model Spec/index.md>) connects those questions to protocol rules and simulated behaviour. Use the model README for v0.8.0 changes. The [data reference](<content/Phase II/Wiki/Reference/Data.md>) describes the observational basis.

## Change an experiment

With the required input data in place, use the model README's [change recipes](src/avalanche_research/model/README.md#change-it) to change the origin state, a behavioural parameter, an environmental scenario or the reward mechanism. Keep the measured origin state, an assumed response and a policy lever distinct in the experiment specification.

The [run instructions](src/avalanche_research/model/README.md#run-it) give a 30-day example and the sweep entry point. [`scripts/m2_sweep_design.py`](scripts/m2_sweep_design.py) constructs the Milestone 2 design. New mechanisms use the interface in [`mechanisms/`](src/avalanche_research/mechanisms/). A neutral setting should reproduce the chain's rule before a new rule enters a policy comparison.

## Analysis and evidence

The research follows one sequence: experiment settings produce daily trajectories, KPIs reduce the trajectories, utilities express the working goals, and sensitivity and risk analysis explain how settings change outcomes.

| Evidence | What you can inspect |
| --- | --- |
| [Sensitivity Analysis Report](<content/Phase II/Milestones/Milestone 2/Sensitivity Analysis Report/index.md>) | Reward comparisons, goals, trees, response curves, sensitivity findings and recommendation tiers |
| [v0.8.0 selection](results/model-v0.8.0-selection/README.md) | Committed forecast scores and the command that recomputes the adoption verdict |
| [Preliminary Validation Report](<content/Phase II/Milestones/Milestone 1/Preliminary Validation Report/index.md>) | Protocol verification and model v0.7 forecast evaluation |
| [Paired sweep analysis](src/avalanche_research/analysis/README.md) | Required sweep artifacts, authentication, matching, estimators and failure handling |
| [Model story notebook](notebooks/model-story.ipynb) | The v0.7 model's structure and worked comparisons |
| [Mechanism explorer](notebooks/mechanism-explorer.ipynb) | Reward and admission designs on one observed reference cohort |

The [v0.8.0 selection verdict](results/model-v0.8.0-selection/verdict.json) can be recomputed from its committed score tables. Repeating the underlying simulations requires the pinned inputs. The report's full sweep outputs are not bundled here, so the repository alone does not reproduce every report result. Comparisons between mechanism families also retain their declared budgets and pairing structure.

## Data availability

Input files are too large for Git and are not stored here. The [data guide](data/README.md), [catalog](data/data-catalog.json) and [pins](data/pins/) identify the required datasets and recorded inputs.

The pinned snapshots are not yet distributed with this repository. Building a new snapshot from a source does not recreate an earlier pinned input. Without the required runs, notebook execution stops at its first missing-data dependency. Saved outputs remain readable. [SETUP.md](SETUP.md) describes the run layout and the notebook verification command for use after the inputs arrive.

## Deliverables and resources

The [milestone index](<content/Phase II/Milestones/index.md>) maps the agreement's deliverables to their pages and evidence. [Milestone 1](<content/Phase II/Milestones/Milestone 1/index.md>) was accepted in August 2026. Its five deliverables were rebuilt on model v0.7 and published on 8 October 2026. The [Phase II overview](<content/Phase II/index.md>) records delivery status, and [Milestone 0](<content/Phase II/Milestones/Milestone 0/index.md>) holds the agreement and proposal. The [Phase I archive](<content/Phase I/index.md>) preserves the 2025 work.

Read pages under `content/` on the research site for rendered charts, mathematics and diagrams. GitHub shows their source text. [SETUP.md](SETUP.md) covers the site build.

The Foundation's `m2-market-sweep` branch preserves the separate execution source cited by the report. The earlier `phase-ii` branch is retained.

## Versions

| Item | Version |
| --- | --- |
| Python package `avalanche-phase-ii-research` | `0.1.0.dev0` in [`pyproject.toml`](pyproject.toml) |
| Staking model | v0.8.0, tagged `model-v0.8.0` on 13 October 2026. Each model run records `MODEL_VERSION = "0.8.0"`. Previous release `model-v0.7.0` |

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
