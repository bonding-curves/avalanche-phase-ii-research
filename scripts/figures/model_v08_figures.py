#!/usr/bin/env python3
"""The v0.8 candidate's score chart: mean scaled error on validator stake for v0.7, v0.8 and the simple forecasts.

    uv run --group notebook --group model python scripts/figures/model_v08_figures.py <development-summary.csv> <figures folder>

Reads the summary that ``scripts/model_development_scores.py`` writes on ``staking-periods-2026-09-30`` and writes
``development-scores.{csv,html,png}``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import holoviews as hv
import pandas as pd

from avalanche_research.views import model_results as mr

sys.path.insert(0, str(Path(__file__).parent))
from png import save_png  # noqa: E402


def main() -> None:
    summary, out = pd.read_csv(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    hv.extension("bokeh")
    stake = summary[summary.variable == "active_validator_stake_navax"]
    stake.to_csv(out / "development-scores.csv", index=False)
    hv.save(mr.development_score_plot(summary), out / "development-scores.html")
    save_png(out / "development-scores.html", out / "development-scores.png", 940, 500)


if __name__ == "__main__":
    main()
