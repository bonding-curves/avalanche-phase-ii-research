# Avalanche Staking Model

The model simulates validators' own stake on Avalanche's Primary Network, one day at a time. Each staking period is a commitment by a validator node: an amount of AVAX, a start date and an end date.

BCRG, the Bonding Curve Research Group, builds the model for the Avalanche Foundation to compare how reward rules change stake, participation and issuance. The released version is [v0.8.0](src/avalanche_research/model/README.md), tagged `model-v0.8.0`.

[![Model v0.8.0: historical staking events supply behavioural rules, six daily stages update the state, and daily outputs supply performance measures](src/avalanche_research/model/images/v0.8-structure.png)](src/avalanche_research/model/images/v0.8-structure.png)

*Read left to right: historical observations, behavioural rules and experiment settings, daily updates, then state and outputs. Click the diagram to enlarge it.*

## State and daily updates

A run starts from the chain at an **origin**, the last observed day. Its [state](src/avalanche_research/model/fitted_lifecycle.py) contains open commitments, nodes out of the active set for up to 365 days, commitments accepted but not yet started, and the supply counter used to price rewards.

Each day follows six stages:

1. Decide which ending commitments renew and which leave.
2. Draw returns by nodes that previously left the active set.
3. Draw arrivals of first-ever validators.
4. Draw the duration and stake of each new commitment.
5. Apply the selected reward rule to commitments started that day.
6. Assemble the next state from continuing, newly created and previously scheduled commitments.

The [daily stage implementation](src/avalanche_research/model/parts/stages.py) fixes this order. cadCAD executes the state updates, and Param declares settings and their bounds.

## Model components and experiment settings

The protocol rules determine potential rewards. Historical decisions supply renewal, return and arrival estimates, together with empirical duration and stake choices. Experiments vary reward designs, outside yields and the strength of renewal and entry responses to rewards.

| Component | Responsibility |
| --- | --- |
| [Protocol](src/avalanche_research/domain/protocol/) | Integer reward arithmetic and upgrade rules |
| [Behaviour](src/avalanche_research/model/parts/) | Renewal, return, arrival, duration and stake choices |
| [Mechanisms](src/avalanche_research/mechanisms/) | Reward and admission rules with their own parameters |
| [Execution](src/avalanche_research/model/engine.py) | Daily simulation and parameter sweeps |
| [Measures and analysis](src/avalanche_research/analysis/README.md) | Trajectory comparisons, sensitivity and goal scoring |

A mechanism can change without replacing the behavioural model. The [model guide](src/avalanche_research/model/README.md) explains the rules, fitting procedures, uncertainty and change recipes. The [selection evidence](results/model-v0.8.0-selection/README.md) records how v0.8.0 was evaluated.

## From daily outputs to policy comparisons

Each run writes a daily table of stake, active validators, supply and issuance. [Performance measures](src/avalanche_research/model/kpis.py) aggregate that trajectory at a stated horizon. Utilities convert measures to scores between zero and one using working network goals.

Parameter selection under uncertainty, or PSUU, repeats this calculation across reward settings, scenarios and behavioural responses. Each design is compared with the chain's rule under the same sampled conditions and random draws. Trees, forests and response curves show how settings affect the goals.

The [Milestone 2 report](<content/Phase II/Milestones/Milestone 2/Sensitivity Analysis Report/index.md>) presents the experiments and findings.

## Run the code

With `git` and [uv](https://docs.astral.sh/uv/):

```sh
git clone --branch milestone-2 git@github.com:AVL-Foundation/ext-bcrg-validator-research.git avalanche-phase-ii-research
cd avalanche-phase-ii-research
uv sync --locked --group model --group notebook
uv run avalanche model describe
uv run pytest -q
```

The description and installation tests work without data. Pinned input snapshots and full sweep outputs are not yet distributed with this repository, so a fresh clone cannot reproduce every simulation or report figure. Saved notebook outputs remain readable. [Setup](SETUP.md) covers installation and notebooks. The [data guide](data/README.md) identifies required inputs.

## Writing links

Pages in `content/` use published routes, such as `/Phase-II/Milestones/Milestone-2/`, with `#heading` for a section. Images use their published asset routes. Repository code links use GitHub URLs. Check content changes with `npm --prefix .site run verify`.

## License

Copyright 2026 Longtail Financial Corp., operating as BCRG. All rights reserved. See [LICENSE.md](LICENSE.md). The [Quartz site engine](.site/LICENSE.txt) has its own MIT license.
