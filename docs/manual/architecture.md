# 3. Modules compose the research system

*Draft for review.*

The research system turns evidence into a model, the model into trajectories and trajectories into a documented comparison. The modules separate those responsibilities so a change in one can be examined without silently changing every other part.

The package's [architecture contracts](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/pyproject.toml) constrain imports, with known exceptions recorded by the architecture tests. The structure is a design with explicit checks, rather than a claim that every old module has already been migrated.

## The economic model and software architecture describe different structures

The stock-and-flow view explains the economic processes. Validator periods persist, enter, end and restart. Reward promises change the supply counter. Figure 1 is the starting point for understanding what the code represents.

![Validator periods, population movements and reward accounting.](assets/content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/assets/stocks-and-flows.png)
*Figure 1. Stocks and flows for model v0.8.0. Solid arrows move periods or AVAX and dashed arrows pass information. Response settings are preliminary. The source figure is retained from the modeling memo.*

Software modules implement those processes and the work surrounding them. Their principal connections are:

```text
provider records → source capture → normalized and derived datasets → checked pins
                                                                    ↓
                                                  origin preparation and fits
                                                                    ↓
experiment design + reward formula + scenarios + keyed draws → daily simulation
                                                                    ↓
                                                       trajectories and receipts
                                                                    ↓
                                                measures → analysis → evaluation
                                                                    ↓
                                                  figures → memo → next question
```

A data pin identifies inputs. The preparation layer turns them into the model's initial state and fitted blocks. The experiment layer chooses settings and runs the model. Analysis consumes authenticated results. A report connects those results back to the economic question.

## Each layer has a specific job

The table gives the major modules, their contents and their connections. The [complete module reference](modules.md) covers every Python file and the functions and classes it defines.

| Module group | Purpose and contents | Operation and connection |
| --- | --- | --- |
| `core/` | Units, hashing, clock, errors, catalog contracts and reserved-period rules | Supplies common definitions used by other layers |
| `sources/` | Provider adapters, query construction, captures and source checks | Retains external observations and their request/response identities |
| `datasets/` | Loading, pins and derived tables | Normalizes captures, reconciles records and constructs model-ready observations |
| `domain/protocol/` | Reward arithmetic, staking constraints and upgrade configuration | Computes protocol quantities from supplied stake, time and supply |
| `mechanisms/` | Reward and admission alternatives | Replaces a design component while retaining a common interface |
| `model/variants.py` | Named model builds and `Prepared` inputs | Selects preparation and model class for an origin |
| `model/parts/` | Renewal, return, arrival, duration, stake and daily stages | Converts state and fitted blocks into decisions and next commitments |
| `model/engine.py` | Param configuration, cadCAD execution and invariant checks | Runs state transitions and returns trajectory data |
| `experiments/` | Pin loading, design expansion, workers and receipts | Connects local inputs to models and persists experiment outputs |
| `model/kpis.py`, `analysis/` | Measures, matched comparisons, sensitivity and regions | Reduces trajectories and evaluates declared statistical questions |
| `model/evaluation.py` | Forecast scores and adoption criteria | Compares predictive distributions with observations and benchmarks |
| `views/`, figure scripts | Structure diagrams, trajectories and report figures | Presents stored quantities with defined units and source records |
| `cli.py`, research commands | User entry points | Calls the underlying modules and reports structured outcomes |
| `research_cycle.py` | Hypothesis, execution, assessment and reflection records | Connects an experiment to a traceable research continuation |

## The experiment layer keeps data access out of the model

The model can run on arrays and tables passed to it. It does not need to query Snowflake or choose the newest local dataset while simulating a day. `experiments/sweep.py` performs input resolution and then calls the registered variant's preparation and simulation methods.

This separation matters when reproducing a result. Changing a provider connection should not silently change a frozen experiment. Changing an input pin should change the recorded experiment identity. A synthetic test can exercise the engine without access to the historical data provider.

## Some files preserve older interfaces

Several top-level package modules re-export names moved into `core`, `sources` or `datasets`. `model/fitted_blocks.py` similarly preserves imports from the earlier combined behaviour module. These compatibility surfaces help existing callers continue to work. Their presence does not mean the model executes a second independent set of behavioural equations.

The released runtime is v0.8.0. Older lifecycle models remain for historical experiments. Delegated lifecycle, named-operator and other candidate components may be present in source without being the released model. Registration, tests and file presence establish different facts from adoption and validation. The [extension chapter](advanced.md) records these boundaries.

## Inspect a module through its contract

For each module, ask what problem it solves, what it contains, what it reads, what it writes and how its output is checked. Then follow one value through its neighbors. For example, a validator stake moves from a recorded period to the initial state, through renewal and stake choice, into reward pricing, then into the stake and issuance measures.

The following chapter opens those modules in execution order. The CLI reference then shows how their user-facing capabilities are invoked.

[Manual contents](README.md)
