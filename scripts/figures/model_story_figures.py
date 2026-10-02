#!/usr/bin/env python3
"""The model v0.7 memo's model figures: structure, mechanisms, response sweep, scorecard, and roadmap.

    uv run --group notebook --group model python scripts/figures/model_story_figures.py <figures folder>

Draws each figure with the library functions in ``avalanche_research.views`` on the pinned runs
``staking-periods-2026-09-30``, reading only staking periods accepted before the validation lockbox
(2025-11-19 16:00 UTC). Writes ``model-structure.{dot,svg,png}`` with Graphviz, and HTML and CSV for the
rest. PNGs of the HTML figures are browser captures of these files.
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

import holoviews as hv

from avalanche_research import datasets
from avalanche_research.mechanisms.cohort import group_stakes, load_periods
from avalanche_research.views import model_results as mr
from avalanche_research.views.model_structure import lifecycle_dot, render

RUN = "staking-periods-2026-09-30"
SUPPLY_NAVAX = 465_373_500 * 10**9
PRICED_AT = datetime(2026, 12, 22, tzinfo=UTC)
TODAY = date(2026, 10, 1)


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    hv.extension("bokeh")
    periods = str(datasets.parquet_path("derived.staking-periods", RUN))

    render(lifecycle_dot(), out / "model-structure")

    cohort = group_stakes(load_periods(periods))
    mechanisms = mr.reference_mechanisms(cohort, SUPPLY_NAVAX, PRICED_AT)
    curves = mr.mechanism_table(mechanisms, SUPPLY_NAVAX, PRICED_AT)
    issuance = mr.reference_issuance(mechanisms, cohort, SUPPLY_NAVAX, PRICED_AT)
    curves.to_csv(out / "mechanism-curves.csv", index=False)
    issuance.to_csv(out / "mechanism-issuance.csv", index=False)
    hv.save(mr.mechanism_plot(curves, issuance), out / "mechanism-curves.html")

    sweep = mr.response_sweep(periods)
    sweep.to_csv(out / "response-sweep.csv", index=False)
    hv.save(mr.sweep_plot(sweep), out / "response-sweep.html")

    scores = mr.lifecycle_scores(periods)
    scores.to_csv(out / "scorecard.csv", index=False)
    hv.save(mr.score_plot(scores), out / "scorecard.html")

    hv.save(mr.roadmap_plot(today=TODAY), out / "roadmap.html")
    print(issuance.to_string(index=False))
    print(sweep.round(1).to_string(index=False))
    wins = (scores.model_abs_error < scores.persistence_abs_error).sum()
    print(f"model wins {wins} of {len(scores)}")


if __name__ == "__main__":
    main()
