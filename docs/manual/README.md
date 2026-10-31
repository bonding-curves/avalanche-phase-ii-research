# Avalanche staking research manual

*Draft for review.*

Avalanche's staking research asks what its reward budget buys: validator participation, committed stake and the ability to sustain them. Answering that question requires both an understanding of the network and a model whose assumptions, computations and evidence can be examined.

The manual develops those two subjects together. Blockchain, Avalanche, AVAX, staking and validator economics provide the context. Model structure, statistical methods, uncertainty, experiment design and evaluation explain how the research addresses it. Model v0.8.0 is the released own-stake model. Development components and proposed extensions are identified separately.

## Follow the explanation from the economy to the result

Each chapter supplies the context needed for the next. The references support detailed lookup after the walkthrough.

| Chapter | Question |
| --- | --- |
| [1. Network and economic foundations](foundations.md) | What system are we studying and why do staking incentives matter? |
| [2. Modeling foundations](modeling.md) | How does a scientific model turn that question into a testable comparison? |
| [3. Architecture](architecture.md) | What are the modules and how does information move between them? |
| [4. Model components](components.md) | How do preparation, five decisions, rewards and state updates work? |
| [5. Data and accounting](data.md) | What do the inputs measure and which identities must reconcile? |
| [6. Experiment design](experiments.md) | How do we specify a comparison and preserve its provenance? |
| [7. Analysis and evaluation](analysis.md) | What do results, uncertainty, scores and tests establish? |
| [8. CLI walkthrough](usage.md) | How do we orient, inspect, run, check and extend an experiment? |
| [9. Advanced methods and future directions](advanced.md) | Which techniques exist and what would additional capabilities require? |
| [10. Workshop](workshop.md) | How can the team work through the whole system together? |
| [CLI reference](cli.md) | Every registered command and option, generated from its definition |
| [Module reference](modules.md) | Every Python module, its components and source descriptions |
| [Dataset reference](datasets.md) | Every CLI dataset-dispatch identifier and implementation |

The [review brief](../../content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/brief.md) is the shorter entry for a decision discussion. The [modeling memo](../../content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/methodology.md), [results memo](../../content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/results.md) and [evidence](../../content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/evidence.md) retain the dated research findings. This manual explains how to understand and use the system behind them.

## Choose a practical reading path

A researcher can follow Chapters 1–7, then run Chapter 8. An engineer can begin with architecture, components and the CLI, returning to the foundations for the meaning of each quantity. A reviewer can follow the source links, experiment records and evaluation distinctions. The workshop uses the complete sequence with discussion and exercises.
