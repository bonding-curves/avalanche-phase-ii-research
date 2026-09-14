# Avalanche Phase II Research

This repository is the client-facing research environment for Avalanche staking economics. It connects economic questions, observed data, published research, validator evidence, protocol mechanisms, and reproducible simulations into clear decision support for the Avalanche Foundation.

Phase II focuses on validator and delegator behavior, staking rewards, economic security, protocol changes, and the conditions under which alternative parameter choices succeed or fail. Research is organized so every result can be inspected through exploratory data analysis, independent reproduction, and dynamic modeling.

## Table of contents

- [Executive summary](#executive-summary)
- [Start here](#start-here)
- [Milestone evidence](#milestone-evidence)
- [Research program](#research-program)
- [Research method](#research-method)
- [Repository map](#repository-map)
- [Run and verify](#run-and-verify)
- [Current limitations](#current-limitations)
- [Contributing](#contributing)

## Executive summary

The repository currently provides the Phase II requirements, the Phase I research archive, six Essential Reading source editions, one initialized validator-rewards study, a reproducible Snowpeer network-summary dataset, and a standalone Quartz research site. The Essential Readings establish the Foundation's Measure, Capture, Distribute agenda, value-accrual and ecosystem-income frameworks, a published model of validator and delegator choices, ACP-285 community discussion, and the January staking-and-price model artifacts.

The research implementation remains in development. Published claims have not yet been independently reproduced here, the dynamic Avalanche model is not complete, and the milestone pages are evidence maps rather than assertions of contractual acceptance. Source publication, implementation verification, empirical validation, research review, and client acceptance are separate states.

## Start here

| Reader | Recommended path |
| --- | --- |
| Avalanche economic team | Begin with the [Phase II overview](<content/Phase II/index.md>), then inspect the [Essential Readings](<content/Phase II/Studies/Essential Readings/index.md>) and [milestone evidence](<content/Phase II/Milestone 0/index.md>). |
| Research reviewer | Open the [validator-rewards study package](<content/Phase II/Studies/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/index.md>) to read its source and, when published, its research components. |
| Engineer or agent | Read [AGENTS.md](AGENTS.md), run the verification command below, and follow links from the [research program](<content/Phase II/index.md>). |
| Phase I reviewer | Open the preserved [Phase I research overview](<content/Phase I/index.md>) and [source index](<content/Phase I/source-index.md>). |

## Milestone evidence

The signed agreement and accepted proposal are preserved under Milestone 0. Each later milestone page maps the verbatim deliverables to the research and evidence that will support review.

| Milestone | Scope | Current repository state |
| --- | --- | --- |
| [Milestone 0](<content/Phase II/Milestone 0/index.md>) | Project authorization and governing documents | Signed agreement and accepted proposal available |
| [Milestone 1](<content/Phase II/Milestone 1/index.md>) | Data ingestion, data manifest, staking model specification, and behavioral calibration | Requirement and evidence pages available; research evidence remains under development |
| [Milestone 2](<content/Phase II/Milestone 2/index.md>) | PSUU, simulations, KPIs, validation, sensitivity, risk surfaces, workshop, and mechanism evaluation | Requirement pages available; final results not yet published |
| [Milestone 3](<content/Phase II/Milestone 3/index.md>) | Recommendations, scenario playbook, open-source release, and knowledge transfer | Requirement pages available; final deliverables not yet published |

## Research program

### Essential Readings

The [six-source collection](<content/Phase II/Studies/Essential Readings/index.md>) is the current research foundation:

1. The Avalanche Foundation's economic research agenda.
2. AVAX value accrual as an equilibrium outcome.
3. Validator and delegator responses to staking rewards.
4. Gross Chain Product and Gross Chain Income.
5. The ACP-285 community call on the staking reward curve.
6. The January staking-and-price model reconstruction.

Each study package preserves its source evidence boundary and adds research components only after they become reviewable.

### Current study

[How Do Avalanche Validators Actually Think About Staking Rewards?](<content/Phase II/Studies/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/index.md>) is the first initialized research node. Its source is published; EDA, Reproduction, and Dynamic Model work remains private until reviewed.

### Next research collections

The next source program covers Economic ACPs and their proposals, discussions, implementations, activation evidence, and observed effects. Supplementary Research Papers provide the theoretical and methodological comparison set. Validator Interviews will add structured operator evidence while preserving consent, attribution, and publication boundaries.

## Research method

```text
decision question
  -> source and claim map
  -> data contract and exploratory analysis
  -> independent reproduction
  -> smallest useful dynamic model
  -> bounded experiments and uncertainty analysis
  -> reviewed findings and decision support
```

Not every source requires every analytical method. A study may classify a component as blocked or not applicable when the evidence does not support it. The repository favors the smallest model that answers the decision question and adds complexity only when it changes the result or resolves a measured limitation.

## Repository map

| Path | Purpose |
| --- | --- |
| [`content/`](content/) | Phase I archive, Phase II studies, milestone evidence, and the source-linked Wiki |
| [`data/`](data/) | Data-source contracts, dataset schemas, reproducible capture instructions, and research navigation |
| [`src/avalanche_research/`](src/avalanche_research/) | Reusable data retrieval, transformation, and validation code |
| [`scripts/`](scripts/) | Deterministic content, link, site, and publication checks |
| [`.site/`](.site/) | Pinned Quartz publication engine and Node environment |
| [`.codex/`](.codex/) | Client-safe agent instructions and reusable capabilities |

Quartz is publication infrastructure, not the research product. Research notebooks and the reusable modeling package will appear only after their interfaces and evidence contracts are exercised.

## Run and verify

Install the pinned site dependencies and start the local research site:

```bash
cd .site
npm ci
npm run dev
```

Open <http://127.0.0.1:8844>. Content changes rebuild automatically.

Run the independent content, collection, site, and publication checks:

```bash
cd .site
npm run verify
```

Install the Python environment and inspect the implemented data sources:

```bash
uv sync --locked
uv run --locked pytest
uv run --locked avalanche data list
uv run --locked avalanche data manifest
```

See the [`data/` guide](data/) for the preview, capture, build, and validation workflow.

The generated site is written to `.site/public/`. Generated output and installed dependencies are not committed.

## Current limitations

- Only one Essential Reading currently has an initialized study package.
- No published empirical result has yet been independently reproduced and accepted in this repository.
- The integrated cadCAD model, PSUU results, data adapters beyond Snowpeer and the Snowflake validator staking dataset, and main synthesis notebook remain under development.
- Milestone pages preserve requirements and evidence structure; their presence does not establish completion or acceptance.
- The ACP-285 page is a timestamped analytical video summary, not a verified verbatim transcript.
- The January model is reconstructed from three indirectly attributed images with material definitions still missing.

## Contributing

Read [AGENTS.md](AGENTS.md) before changing the repository. Contributions should address one bounded research or engineering question, preserve source and result provenance, run the documented checks, and arrive as focused reviewable commits.

Repository release: pre-`0.1.0` research baseline. See [LICENSE.txt](LICENSE.txt) for reuse terms.
