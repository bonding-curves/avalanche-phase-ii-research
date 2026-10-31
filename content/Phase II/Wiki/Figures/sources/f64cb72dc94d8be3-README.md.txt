# The Avalanche staking model, v0.8.0

A simulation of how Avalanche Primary Network validators commit, renew, leave and come back, fitted to the chain's own history, so that reward designs can be compared on the validator stake, issuance and decentralisation they would produce. It is built for the Avalanche Foundation's reward-design decisions and for the researchers who review them.

[![The v0.8.0 model: staking events measured before the origin fit the behaviour blocks, six stages run each day in order and read and write the state, and the run writes a daily table that the KPIs read](images/v0.8-structure.png)](images/v0.8-structure.svg)

**Status:** model version 0.8.0, the variant `v0.8.0`. Tagged `model-v0.8.0` on 13 October 2026. Chosen against candidate a by the variant rule fixed on 6 October 2026 ([evidence](../../../results/model-v0.8.0-selection/README.md)). The previous release is tagged `model-v0.7.0`.

## Contents

1. [What the model does](#what-the-model-does)
2. [Questions it answers](#questions-it-answers)
3. [How a day runs](#how-a-day-runs)
4. [What is fitted, swept and fixed](#what-is-fitted-swept-and-fixed)
5. [Results: how v0.8.0 was chosen](#results-how-v080-was-chosen)
6. [Use and limits](#use-and-limits)
7. [Run it](#run-it)
8. [Change it](#change-it)
9. [Files](#files)
10. [Terms](#terms)

**Start here.** A reader deciding on reward designs: sections 1, 2, 5 and 6. A reviewer checking the model: sections 3 to 6 and the [selection evidence](../../../results/model-v0.8.0-selection/README.md). An engineer running or extending it: sections 7 to 9.

## What the model does

Each validator on the Primary Network stakes AVAX for a period it chooses, between two weeks and a year, and earns rewards set by the protocol's reward formula. When the period ends, the validator renews, leaves, or leaves and later comes back. New validators arrive. The total stake, the number of validators and the issuance all follow from those choices.

The model starts from the chain as it stood on an **origin** day: every open commitment, every node that left in the past year, and every commitment accepted but not yet started. It then steps forward one UTC day at a time. Each day it decides which ending commitments renew, which absent nodes return and how many new nodes arrive, and draws each new commitment's duration and stake. It prices each new commitment with the reward design under study, and records the day.

Every decision is a **behaviour block** fitted by likelihood to the decisions validators made before the origin, mostly in the year before it. The return hazard reads the endings of the two years before it, so that nodes out for up to a year have a full year to come back. Nothing after the origin is used to fit the model, so the days after it test the forecast. Every fitted parameter except the stake hurdle is drawn once per run from its uncertainty, so many runs give a distribution, not a single path.

## Questions it answers

| Question | KPIs in [`kpis.py`](kpis.py) |
| --- | --- |
| Does the network stay secure? | `validator_stake_navax`, `lowest_validator_stake_navax`, `active_validators`, `validator_staking_ratio`, `worst_30_day_stake_fall` |
| What does it cost in issuance? | `issued_navax`, `net_inflation`, `issuance_half_life` |
| Compared with the chain's own rule? | `issuance_saved`, `validator_stake_retained`, `active_validators_retained`, each a run over the same run under the chain's rule |
| Is validating worth it? | `earned_rate`, `return_margin`, `reward_rate_volatility` |
| Do validators commit for longer? | `stake_weighted_duration` |
| Does stake stay spread out? | `nakamoto_coefficient`, the fewest nodes holding more than a third of validator stake |
| Is stake stable? | `stake_volatility` |

Each KPI is one function of a run's daily table, with its unit, horizon and definition in its docstring. The Milestone 2 sweep reads them at 180 and 365 days.

## How a day runs

The daily step is an ordered list of stages ([`parts/stages.py`](parts/stages.py)). Each stage reads the state at the start of the day and the outputs of the stages before it.

1. **Renewal** ([`parts/renewal.py`](parts/renewal.py)). Each commitment that ends today renews on the same node with a probability from a logit on the node's tenure, whether it came back after a gap, its duration and its stake.
2. **Returns** ([`parts/return_hazard.py`](parts/return_hazard.py)). A node that left the active set in the past 365 days comes back with a daily probability that depends on its own history.
3. **Arrivals** ([`parts/arrivals.py`](parts/arrivals.py)). Nodes that never validated arrive as a negative binomial count per day.
4. **Continuation** ([`parts/continuation.py`](parts/continuation.py), [`parts/stake_choice.py`](parts/stake_choice.py)). Each renewed, returning or new commitment draws its duration from similar moves before the origin, then its stake from the stake hurdle given that duration.
5. **Rewards.** The reward design prices each new commitment at its start ([`../mechanisms/`](../mechanisms/)).
6. **Assembly.** Commitments that continue, then those started today, then the scheduled ones due today, become the next day's state.

Read the diagram above left to right. The blue frame holds the fitted blocks, the red frame the settings a run compares, and the green cylinders the state carried from day to day. A dashed green arrow is state a stage reads, and a two-headed arrow is state whose next value comes from that stage. The drawing is traced from the code: `fitted_lifecycle_dot` in [`../views/model_structure.py`](../views/model_structure.py) runs one day of a small v0.8.0 model and records what each stage reads and returns, and stops on anything it has no words for. Redraw it after any change to the stages with `uv run --group model python scripts/figures/model_v08_structure.py`, which needs Graphviz.

Every random draw is keyed by its purpose, node and decision count ([`streams.py`](streams.py)), so two reward designs run on the same seed face the same draws, and their difference is the design's effect.

## What is fitted, swept and fixed

| Kind | What | Where it comes from |
| --- | --- | --- |
| Fitted before each origin | The renewal logit, the return hazard, the arrival count, the duration moves and the stake hurdle | The staking-period log before the origin: the year before it for every block except the return hazard, which reads the endings of the two years before it. In [`fitted_lifecycle.py`](fitted_lifecycle.py) and [`stake_lifecycle.py`](stake_lifecycle.py) |
| Drawn once per run | Every fitted parameter except the stake hurdle, from a bootstrap over nodes, plus a renewal shift for drift between windows | `parameter_draws` in [`fitted_lifecycle.py`](fitted_lifecycle.py) |
| Swept | The renewal and entry responses to the reward rate, and the outside yield a validator could earn instead | History before Helicon does not identify the responses, so each is a setting with its source in its metadata |
| Fixed by the protocol | The reward formula, the supply counter, ACP-285 from Helicon, the admission rules | [`../domain/protocol/`](../domain/protocol/) and [`../mechanisms/`](../mechanisms/) |

Every setting is a Param parameter with bounds. Each assumed setting carries its source and evidence in its metadata.

## Results: how v0.8.0 was chosen

Each candidate was scored at 19 development origins, 200 runs per origin, against what happened, with nothing fitted after 19 November 2025. The rule was fixed before any score existed. Full evidence and files: [`results/model-v0.8.0-selection/`](../../../results/model-v0.8.0-selection/README.md).

| Question | Answer | Uncertainty | Evidence | Model revision | Reproduce |
| --- | --- | --- | --- | --- | --- |
| Does v0.8.0 forecast validator stake at 90 days better than candidate a? | Yes, by 0.81 in scaled CRPS | One-sided p that it is worse 0.83, over the 18 origins whose 90-day horizon ends before the held-back period | [verdict](../../../results/model-v0.8.0-selection/verdict.json) | `v0.8-a stake return u` against `v0.8-a u` | `uv run --group model python scripts/model_v080_selection.py verdict` |
| Is any forecast clearly worse? | No. The largest worsening is active validators at 90 days, +0.04 | p 0.43 against a threshold of 0.05/6 | [cells](../../../results/model-v0.8.0-selection/README.md#the-result) | same | same |

Six other changes were tested by the same rule. The ten stake bands were adopted and then superseded by the stake hurdle. The node's renewal record, a duration transition, uptime, GoGoPool as its own group and large operators were rejected. The [selection evidence](../../../results/model-v0.8.0-selection/README.md#how-it-was-tested) gives each reason. Their runs are not in this repository, so only the final comparison has a reproduce command.

## Use and limits

**Intended use.** Comparing reward designs against each other and against the chain's own rule, on the same random draws, over horizons up to a year from an origin before 19 November 2025.

**Not for.** A point forecast of a single day's stake. Statements about how validators respond to the reward rate, which history does not identify and the model sweeps. Delegators' own choices, which come in v0.8.1. Any period after the origin used to fit it.

**Known limits.**

- The stake hurdle is badly calibrated on exact repeats: it under-predicts renewals that keep exactly the same stake and over-predicts returns that keep theirs.
- The stake hurdle stays at its point estimate across runs, so the forecast spread leaves out its uncertainty.
- The day-to-day spread of new validators does not match the record, and no tested alternative did better.
- Delegations, named operators and operator types are not in v0.8.0. They are the v0.8.1 blocks.

## Run it

Install the locked environment and run the tests, which use synthetic inputs and need no data:

```sh
uv sync --locked --group model
uv run --group model python -m pytest tests/test_fitted_lifecycle.py tests/test_stake_lifecycle.py tests/test_variant_switches.py -q
```

With the staking periods of pin [`data/pins/p2-model-v0.8.json`](../../../data/pins/p2-model-v0.8.json) built as the [data guide](../../../data/README.md) describes, run the released model for 30 days from the last origin before the held-back period:

```sh
uv run --group model avalanche model run data/pins/p2-model-v0.8.json runs/v0.8.0-demo --origin 2025-11-18 --runs 20 --timesteps 30
uv run --group model avalanche --version
```

The run prints `PASS | model run | 1 row written` with a receipt identifier. It writes the run's output as one Parquet file with its SHA-256, the design it ran and a `receipt.json` naming the code, data and seeds. `--version` names the package, the released model and the code commit. A sweep of many settings is `avalanche model sweep` on a design file. The Milestone 2 design is written by [`scripts/m2_sweep_design.py`](../../../scripts/m2_sweep_design.py).

## Change it

Each recipe starts from the released model prepared at an origin:

```python
from datetime import UTC, date, datetime

from avalanche_research import datasets
from avalanche_research.mechanisms import ACP285Ramp
from avalanche_research.model.engine import run
from avalanche_research.model.variants import VARIANTS

periods_run = "staking-periods-2026-09-30"
periods = str(datasets.parquet_path("derived.staking-periods", periods_run))
v080 = VARIANTS["v0.8.0"]
prepared = v080.prepare(periods, date(2025, 11, 18), periods_run, draws=20, draw_seed=0)
table = run(v080.simulation(prepared, seed=0, timesteps=30, runs=20, draws=prepared.draws))
```

1. **The initial state.** The state is measured at the origin, so pass another origin to `prepare`, any day before 19 November 2025. The tables it measures (`initial`, `out_of_set`, `scheduled`) are in `prepared.inputs` and can be edited before building the model.
2. **A parameter.** Override a setting when building the model, for example a renewal response of 0.05 per percentage point:
   ```python
   model = v080.model(timesteps=30, runs=20, seed=0, draws=prepared.draws,
                      **{**prepared.inputs, "renewal_response": 0.05})
   ```
3. **A scenario.** The outside yield and its fitting-window level are settings (`outside_yield_pp`, `fitted_outside_yield_pp`), set the same way. A whole scenario grid is a design file for `avalanche model sweep` ([`designs.py`](designs.py)).
4. **A mechanism.** Pass any reward design from [`../mechanisms/`](../mechanisms/), or a new subclass of `RewardMechanism`, as `mechanism`. This starts ACP-285's ramp at the origin with a 6% target, so the commitments started in the run earn less than under the chain's rule:
   ```python
   ramp = ACP285Ramp(activation=datetime(2025, 11, 18, 16, tzinfo=UTC), ramp_days=90, target_min_rate=0.06)
   model = v080.model(timesteps=30, runs=20, seed=0, draws=prepared.draws, **{**prepared.inputs, "mechanism": ramp})
   ```

## Files

| File | What it holds |
| --- | --- |
| [`variants.py`](variants.py) | Every named model variant and how its inputs are built at an origin. `v0.8.0` is the release |
| [`fitted_lifecycle.py`](fitted_lifecycle.py) | `FittedLifecycle`, the v0.8 model, with `fitted_inputs`, which fits every block before the origin, and `parameter_draws` |
| [`stake_lifecycle.py`](stake_lifecycle.py) | `StakeLifecycle`, the fitted lifecycle with the stake hurdle |
| [`parts/`](parts/) | One module per behaviour block, and the daily stage order in `stages.py` |
| [`engine.py`](engine.py) | `SimulationModel`, the Param and cadCAD base, with `run` and `sweep` |
| [`streams.py`](streams.py) | Keyed random draws by seed, run, purpose and node |
| [`kpis.py`](kpis.py) | Every KPI as one function of a daily table |
| [`response.py`](response.py) | The reward-rate gap the swept responses act on |
| [`evaluation.py`](evaluation.py) | Forecast scores, distribution scores and the variant rule `adoption_verdict` |
| [`designs.py`](designs.py), [`runner.py`](runner.py) | Sweep designs and the row runner the sweep command uses |
| [`replay.py`](replay.py) | Replays recorded starts, ends and rewards with no behaviour, to check the engine against the ledger |
| [`lifecycle.py`](lifecycle.py) | v0.7, `ValidatorLifecycle`, kept for its tagged release |
| [`delegated_lifecycle.py`](delegated_lifecycle.py), [`delegation_blocks.py`](delegation_blocks.py), [`operator_events.py`](operator_events.py) | The v0.8.1 delegation and named-operator blocks, in development |
| [`versions.py`](versions.py), [`backtest.py`](backtest.py) | The version table, and the check that recomputes each recorded reward from the protocol formula |

## Terms

| Term | Meaning |
| --- | --- |
| Commitment | One validator staking period: a node, a stake, a start and an end |
| Origin | The last observed day. Inputs come from before it, and the days after test the forecast |
| Behaviour block | One fitted decision, such as renewal or arrival, with a probability for the simulator and a likelihood for fitting |
| Variant | A named way of building the model's inputs at an origin, registered in `variants.py` |
| Run | One simulated path from the origin. A forecast is many runs |
| Parameter draw | One run's draw of every fitted parameter from its uncertainty |
| Stake hurdle | The block that draws a new commitment's stake given its duration |
| Return hazard | The daily probability that a node out of the active set comes back |
| CRPS | Continuous ranked probability score: how far a forecast distribution is from what happened. Lower is better |
| Variant rule | The test, fixed before scoring, that a change must pass to enter the model |
| Held-back period | From 19 November 2025 16:00 UTC: no model is fitted or chosen on it |
| nAVAX | One billionth of an AVAX, the unit of every stake and reward amount in the model |
