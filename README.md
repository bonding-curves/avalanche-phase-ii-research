# Avalanche Staking Economics

Avalanche pays validators with newly issued AVAX. Which reward rules sustain stake and participation while spending less on rewards?

BCRG, the Bonding Curve Research Group, studies this question for the Avalanche Foundation. We reconstruct staking history, model validator decisions, and compare reward designs across market conditions and assumptions about how strongly validators respond to rewards.

The [Milestone 2 report](<content/Phase II/Milestones/Milestone 2/Sensitivity Analysis Report/index.md>) brings together the model, experiments, findings and policy questions. The [model guide](src/avalanche_research/model/README.md) explains the implementation.

## From staking history to reward policy

Stake and validator counts can move differently. A reward rule therefore needs to be assessed by both the AVAX it keeps staked and the validators who remain active. The [staking record](<content/Phase II/Wiki/Reference/Data.md>) supplies the observed commitments, rewards and participation behind the model.

Model v0.8.0 follows validators' own staking periods through renewal, departure, return and new entry. It computes rewards using the protocol's arithmetic. Historical decisions supply the behavioural estimates, while experiments vary how strongly renewal and entry respond to rewards. The [model selection evidence](results/model-v0.8.0-selection/README.md) compares its forecasts with simple alternatives.

Reward comparisons follow parameter selection under uncertainty, or PSUU:

1. Run each reward design across reward settings, market conditions and behavioural responses.
2. Reduce each simulated daily path to measures of issuance, stake, participation, concentration and commitment length.
3. Convert the measures to scores between zero and one, called utilities, expressing the working network goals.
4. Use decision trees, forests and response curves to identify which settings meet each goal and where they fall short.

Each design is compared with the chain's rule under the same sampled conditions and random draws. The Foundation sets the acceptable outcomes and tradeoffs used to turn the comparisons into recommendations.

## Milestone 2 compares issuance with stake retained

ACP-285 gradually lowers rewards for shorter staking periods over 90 days by reducing the reward formula's minimum consumption rate. Annual reward rates on stake also depend on duration and supply.

The first sweep, a set of 132,800 one-year simulations including reference and control runs, compared an early start to ACP-285's reward ramp, the rule before ACP-285, a tenure boost and a quadratic duration curve.

Across that sweep's parameter samples, the early-start ramp saved about 13% of validator reward issuance and retained about 97% of validators' own stake relative to the chain-rule runs. The comparison starts on 18 November 2025. Its reference follows the historical schedule, introducing ACP-285 in September 2026.

![One-year issuance savings and validator stake retained for four reward designs, grouped by outside yield](<content/Phase II/Milestones/Milestone 2/Sensitivity Analysis Report/fig4-design-comparison.png>)

*Panels vary the annual return available outside staking, measured in AVAX. The teal points show the early-start ramp. Moving right saves issuance. Moving down loses stake relative to the matched reference. Bars show the 10th to 90th percentiles across sampled runs. [Experiment and results](<content/Phase II/Milestones/Milestone 2/Sensitivity Analysis Report/index.md#7-findings>).*

The comparisons are conditional on the model and the sampled settings. The preferred setting depends on the participation thresholds and goal weights. The report explains the experiment design, assumptions, sensitivity analysis and recommendation tiers.

## Run the code

Released staking model: v0.8.0, tagged `model-v0.8.0`. With `git` and [uv](https://docs.astral.sh/uv/):

```sh
git clone --branch milestone-2 git@github.com:AVL-Foundation/ext-bcrg-validator-research.git avalanche-phase-ii-research
cd avalanche-phase-ii-research
uv sync --locked --group model --group notebook
uv run avalanche model describe
uv run pytest -q
```

The description and installation tests work without data. Pinned input snapshots and full sweep outputs are not yet distributed with this repository, so a fresh clone cannot reproduce every simulation or report figure. Saved notebook outputs remain readable.

## Read further

| Task | Guide |
| --- | --- |
| Understand the findings | [Milestone 2 report](<content/Phase II/Milestones/Milestone 2/Sensitivity Analysis Report/index.md>) |
| Inspect or change the model | [Model guide](src/avalanche_research/model/README.md) |
| Install and open the notebooks | [Setup](SETUP.md) |
| Identify the required inputs | [Data guide](data/README.md) |
| Inspect the sweep calculations | [Analysis guide](src/avalanche_research/analysis/README.md) |
| Find a contractual deliverable | [Milestone index](<content/Phase II/Milestones/index.md>) |

## Writing links

Pages in `content/` use published routes, such as `/Phase-II/Milestones/Milestone-2/`, with `#heading` for a section. Images use their published asset routes. Repository code links use GitHub URLs. Check content changes with `npm --prefix .site run verify`.

## License

Copyright 2026 Longtail Financial Corp., operating as BCRG. All rights reserved. See [LICENSE.md](LICENSE.md). The [Quartz site engine](.site/LICENSE.txt) has its own MIT license.
