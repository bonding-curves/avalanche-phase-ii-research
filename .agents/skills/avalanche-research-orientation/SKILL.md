---
name: avalanche-research-orientation
description: Orient to the Avalanche research checkout, wiki, model and evidence before starting an investigation, resuming work or locating reports. Use the local CLI trees to find relevant sources and frame the next research step.
---

# Avalanche research orientation

Use orientation as the first step in the research methodology. Establish the question, available material and relevant model before choosing an experiment or drafting a finding.

## Locate the work

Run from the repository root after the [locked installation](../../../SETUP.md):

```sh
uv run --frozen avalanche research tree wiki
uv run --frozen avalanche research tree repo
```

The commands print the wiki's page hierarchy and the repository's files and directories. They read local Git inventory and page titles. They require no research datasets, credentials, model execution or running website.

For both views, more detail or machine-readable context:

```sh
uv run --frozen avalanche research tree
uv run --frozen avalanche research tree repo --depth 3
uv run --frozen avalanche research tree both --json
```

The default inventory covers tracked files that exist in the working checkout. Titles reflect working-file contents. The header reports the checkout revision and scope. A collapsed branch reports how many files are omitted. Use `--include-untracked` when the task concerns new local work, and retain that scope distinction when summarizing the output. Use `--root PATH` to inspect another Avalanche checkout. Git is required.

## Follow the research question

Read the relevant repository instructions and the [research field guide](references/field-guide.md). Follow only the sources needed for the task. The trees establish where material exists. A page's presence or title does not establish completion, scientific validity or client acceptance.

1. State the question and the decision or understanding it serves.
2. Identify the relevant model, population and evidence. Read the setup and source record before relying on a reported result.
3. Distinguish observed data, simulation outcomes, behavioural assumptions and policy preferences.
4. Choose the smallest next analysis or explanation that can resolve the question. Use the existing experiment or memo record to retain the source identities and conclusion.

For a result comparison, identify the input snapshot, origin and clock, design and comparator, paired draws and seeds, horizon, measures and uncertainty. Preserve unknown identities explicitly. Reading a saved result and reproducing its simulation have different input requirements.

When returning an orientation, give the requested tree and the relevant source paths. If the user requests a research recommendation, state the question, consequential evidence limit and next step. Keep historical editions identifiable by their source date and link later corrections rather than treating old claims as current findings.
