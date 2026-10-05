#!/usr/bin/env python3
"""Score the lifecycle models v0.7 and v0.8 at the validation protocol's development origins, against its naive benchmarks.

    uv run --group model python scripts/model_development_scores.py <output folder>

The origins are the five upgrades from Banff to Fortuna and the quarter starts from 2022-07-01 to 2025-10-01, 19 in
all. Each origin runs each model with every input measured or fitted before it, 20 seeded runs, and scores the mean of the runs
at 30, 90 and 180 days for active validators and validator stake. A horizon that would reach the held-back period,
from 2025-11-19, is skipped. Each forecast and each benchmark (`N1` persistence, `N2` 180-day drift, `N3` weekly
AR(1)) gets its absolute error scaled by the mean one-day change before the origin. Writes `development-scores.csv`
with one row per origin, variable, horizon and forecast, and `development-summary.csv` with the mean scaled error of
each model by variable and horizon and a Diebold-Mariano test of it against each benchmark and of v0.8 against v0.7.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from avalanche_research import datasets
from avalanche_research.model import evaluation as ev
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_lifecycle import FittedLifecycle, fitted_inputs
from avalanche_research.model.lifecycle import (
    ValidatorLifecycle,
    actual_path,
    origin_inputs,
)
from avalanche_research.model.replay import LOCKBOX_FIRST_DAY, daily_events

RUN = "staking-periods-2026-09-30"
UPGRADES = {"Banff": date(2022, 10, 18), "Cortina": date(2023, 4, 25), "Durango": date(2024, 3, 6),
            "Etna": date(2024, 12, 16), "Fortuna": date(2025, 4, 8)}
QUARTERS = {f"{y}-{m:02d}-01": date(y, m, 1) for y in (2022, 2023, 2024, 2025) for m in (1, 4, 7, 10)
            if date(2022, 7, 1) <= date(y, m, 1) <= date(2025, 10, 1)}
HORIZONS = (30, 90, 180)
VARIABLES = ("active_validators", "active_validator_stake_navax")
MODELS = ("v0.7", "v0.8")


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    periods = str(datasets.parquet_path("derived.staking-periods", RUN))
    actual = actual_path(daily_events(periods))
    actual.index = pd.to_datetime(actual.pop("date_utc"))
    last_day = pd.Timestamp(LOCKBOX_FIRST_DAY) - pd.Timedelta(1, unit="D")
    rows = []
    for name, origin in {**UPGRADES, **QUARTERS}.items():
        tables = {
            "v0.7": run(ValidatorLifecycle(origin=origin, inputs_source=RUN, timesteps=max(HORIZONS), **origin_inputs(periods, origin))),
            "v0.8": run(FittedLifecycle(timesteps=max(HORIZONS), **fitted_inputs(periods, origin, RUN))),
        }
        for variable in VARIABLES:
            series = actual[variable].astype(float)
            scale = ev.mase_scale(series, origin)
            for h in HORIZONS:
                if pd.Timestamp(origin + timedelta(days=h)) > last_day:
                    continue
                realized = ev.actual_at(series, origin, h)
                forecasts = {
                    **{m: float(t[(t.variable == variable) & (t.timestep == h)].value.astype(float).mean()) for m, t in tables.items()},
                    **{b: rule(series, origin, h) for b, rule in ev.BENCHMARKS.items()},
                }
                for forecast, value in forecasts.items():
                    rows.append({"origin": name, "origin_date": origin, "kind": "upgrade" if name in UPGRADES else "quarter",
                                 "variable": variable, "horizon_days": h, "forecast": forecast, "value": value,
                                 "actual": realized, "scaled_error": ev.scaled_error(value, realized, scale)})
    scores = pd.DataFrame(rows)
    scores.to_csv(out / "development-scores.csv", index=False)
    summary = []
    for (variable, h), part in scores.groupby(["variable", "horizon_days"]):
        wide = part.pivot(index="origin", columns="forecast", values="scaled_error")
        pairs = [(m, b) for m in MODELS for b in ev.BENCHMARKS] + [("v0.8", "v0.7")]
        for model, benchmark in pairs:
            test = ev.diebold_mariano(wide[model], wide[benchmark], horizon=1)
            summary.append({"variable": variable, "horizon_days": h, "model": model, "benchmark": benchmark, "origins": len(wide),
                            "model_mase": wide[model].mean(), "benchmark_mase": wide[benchmark].mean(),
                            "model_closer": int((wide[model] < wide[benchmark]).sum()),
                            "dm_statistic": test["statistic"], "p_model_better": test["p_less"]})
    pd.DataFrame(summary).to_csv(out / "development-summary.csv", index=False)
    print(pd.DataFrame(summary).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
