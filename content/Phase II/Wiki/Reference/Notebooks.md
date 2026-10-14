---
title: Notebooks
description: What the two notebooks of the staking model v0.7 show, how to open their saved outputs, and how to run them once the input data is published.
tags: ["staking-duration-and-liquidity", "issuance-and-rewards", "structural-estimation"]
---

Of the five Jupyter notebooks in `notebooks/`, this page describes the two for the staking model v0.7. Both are saved with their outputs, so every table and chart can be read without running anything. Both read one dataset, `derived.staking-periods`, from its run `staking-periods-2026-09-30`. That run is part of the pinned input sets, which are not yet distributed with the repository. [Data](/Phase-II/Wiki/Reference/Data) describes the dataset.

| Notebook | What it shows |
| --- | --- |
| `mechanism-explorer.ipynb` | Reward and admission mechanisms compared on one reference cohort of real stakes |
| `model-story.ipynb` | The model v0.7 from its structure to its roadmap: structure, mechanisms, response, scorecard, and versions |

## Mechanism explorer

`mechanism-explorer.ipynb` compares reward and admission mechanisms on real stakes. Each mechanism is a Param class: its settings have bounds and documentation, and it offers its curve, the AVAX it would mint for a set of stakes, and a check of the properties it must keep.

The reference cohort is every validator period and delegation accepted from 2024-11-19 to 2025-11-19 16:00 UTC, the year before Granite. It stops where the validation lockbox starts. Each stake is repriced as if it started on one evaluation date.

The notebook has these parts, in order:

1. Annual reward rate by duration draws the curve of today's chain reward, the ACP-285 ramp, a tenure boost, a quadratic reward, and a quadratic reward scaled to the chain's issuance.
2. What each mechanism would mint for the cohort tabulates the AVAX each reward mechanism issues and its change against today's chain. Issuance is the cost every comparison scores.
3. Admission by duration compares today's admission rule with a bounded harmonic frontier that asks more of short commitments and less of long ones. A table gives the share of the cohort's validator periods, and of their AVAX, that each rule admits.
4. Explore has one tab per mechanism. Moving a setting updates the curve and the AVAX minted for the cohort at once.

## Model story

`model-story.ipynb` presents the model v0.7. Each code cell calls one function in `avalanche_research.views`, so the notebook and the figures in the memos draw the same plots. It uses only staking periods accepted before the validation lockbox.

The notebook has these parts, in order:

1. The model's structure, traced from its code, as a diagram.
2. Reward designs: the annual rate by duration, and the AVAX each design mints for the reference cohort.
3. Validators after 180 days against AVAX issued, at three response strengths, from the Fortuna upgrade on.
4. The lifecycle model against holding the origin value, at five network upgrades.
5. The model's versions, by the call that shows each one.

## Open the saved notebooks

1. Set up the repository as `SETUP.md` describes, including `uv sync --locked --group notebook`.
2. Mark both notebooks as trusted: `uv run --group notebook jupyter trust notebooks/mechanism-explorer.ipynb notebooks/model-story.ipynb`.
3. Open JupyterLab with `uv run --group notebook jupyter lab notebooks/` and open either notebook.

The charts are HoloViews and Bokeh outputs. JupyterLab draws them only when the notebook is trusted, and an untrusted notebook shows the text, code, and tables but leaves the charts blank. GitHub shows the text, code, and tables and does not draw the charts. In the saved charts, pan, zoom, and hover work. The settings in the Explore section recompute in Python, so they respond only while the notebook runs.

## Run the notebooks

Running the notebooks needs the pinned input sets, which are not yet distributed with the repository. A command that fetches and checks them is planned with the code transfer of Milestone 3. Once a set is extracted into `data/runs/`:

1. Run `uv run --group notebook python scripts/verify_notebooks.py`. It checks the run `staking-periods-2026-09-30` against its build receipt and runs both notebooks into a temporary folder, so the saved copies are never changed. Every line starts with `PASS`, and the last line is `All checks passed.` It takes about a minute and a half.
2. In JupyterLab, choose **Run > Run All Cells** in either notebook.
