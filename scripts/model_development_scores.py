#!/usr/bin/env python3
"""Score the lifecycle models v0.7 and v0.8 at the validation protocol's development origins, against its naive benchmarks.

    uv run --group model python scripts/model_development_scores.py <output folder> [workers]

The origins are the five upgrades from Banff to Fortuna and the quarter starts from 2022-07-01 to 2025-10-01, 19 in
all. Each origin runs each model with every input measured or fitted before it, 200 runs as ten 20-run batches with
base seeds 0 to 9, in a pool of ``workers`` processes (default six), and scores the mean of the runs at 30, 90 and 180
days for active validators and validator stake. Every run's value is written to ``development-runs.csv.gz``, which
``scripts/model_distribution_scores.py`` scores as a distribution, and each batch's specification hash, which covers the
model, its settings and a digest of every input, to ``development-specifications.csv``. A horizon that would reach the held-back period,
from 2025-11-19, is skipped. Each forecast and each benchmark (`N1` persistence, `N2` 180-day drift, `N3` weekly
AR(1)) gets its absolute error scaled by the mean one-day change before the origin. Writes `development-scores.csv`
with one row per origin, variable, horizon and forecast, and `development-summary.csv` with the mean scaled error of
each model by variable and horizon and a Diebold-Mariano test of it against each benchmark and of v0.8 against v0.7.
The test takes the origins in date order, and its horizon is one plus the most later origins inside one forecast's
window (``evaluation.dm_horizon``), counted from the dates because an upgrade can fall a week from a quarter start.
``v0.8 separate`` fits its renewal block separately for commitments above 1M AVAX and at or below it. ``v0.8 u`` is v0.8
with one draw of every fitted parameter per run: 200 draws per origin from ``parameter_draws``, with the renewal shift's
SD from ``window_sd``, batch b reading draws 20b to 20b + 19. The draws depend only on the origin, so every model and
design at an origin that uses them gets the same rows. They go to ``draws.csv.gz``, and each origin's shift SD, its
source and the number of draws at the renewal clip to ``tau.csv``.
"""

from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from avalanche_research import datasets
from avalanche_research.model import evaluation as ev
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_lifecycle import (
    FittedLifecycle,
    clipped_draws,
    fit_blocks,
    fitted_inputs,
    parameter_draws,
    training_events,
    window_sd,
)
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
MODELS = ("v0.7", "v0.8", "v0.8 separate", "v0.8 u")
LARGE_ABOVE_AVAX = 1_000_000
BATCH_SEEDS = range(10)
BATCH_RUNS = 20
DRAW_SEED = 0


def batch_draws(draws: pd.DataFrame, batch: int) -> pd.DataFrame:
    """Batch ``batch``'s rows of an origin's draw table, renumbered from 0, so its run r reads draw 20 x batch + r - 1."""
    return draws.iloc[batch * BATCH_RUNS:(batch + 1) * BATCH_RUNS].reset_index(drop=True)


def model_runs(task: tuple[str, date, str, str]) -> tuple[pd.DataFrame, pd.DataFrame, dict | None]:
    """Every run's value at each horizon for one origin and model, one row per batch seed, run, variable and horizon,
    each batch's specification hash, and for ``v0.8 u`` the origin's draws and shift SD."""
    name, origin, model, periods = task
    draws, extras = None, None
    if model == "v0.7":
        inputs = origin_inputs(periods, origin)
    elif model == "v0.8 separate":
        inputs = fitted_inputs(periods, origin, RUN, LARGE_ABOVE_AVAX)
    elif model == "v0.8 u":
        events = training_events(periods, origin, RUN)
        inputs = {**fit_blocks(events), "moves": events.moves, "first_commitments": events.first_commitments}
        tau, source = window_sd(periods, origin, inputs["renewal"])
        draws = parameter_draws(events, BATCH_RUNS * len(BATCH_SEEDS), DRAW_SEED, tau)
        extras = {"draws": draws.assign(origin=name, draw=range(len(draws))),
                  "tau": {"origin": name, "tau": tau, "source": source, "clipped_draws": clipped_draws(draws)}}
    else:
        inputs = fitted_inputs(periods, origin, RUN)
    parts, specifications = [], []
    for seed in BATCH_SEEDS:
        if model == "v0.7":
            simulation = ValidatorLifecycle(origin=origin, inputs_source=RUN, timesteps=max(HORIZONS), runs=BATCH_RUNS, seed=seed, **inputs)
        elif draws is not None:
            simulation = FittedLifecycle(timesteps=max(HORIZONS), runs=BATCH_RUNS, seed=seed, draws=batch_draws(draws, seed), **inputs)
        else:
            simulation = FittedLifecycle(timesteps=max(HORIZONS), runs=BATCH_RUNS, seed=seed, **inputs)
        specifications.append({"origin": name, "model": model, "batch_seed": seed, "specification": simulation.specification_hash()})
        t = run(simulation)
        t = t[t.timestep.isin(HORIZONS) & t.variable.isin(VARIABLES)]
        parts.append(pd.DataFrame({"origin": name, "model": model, "batch_seed": seed, "run": t.run.to_numpy(),
                                   "variable": t.variable.to_numpy(), "horizon_days": t.timestep.to_numpy(),
                                   "value": t.value.astype(float).to_numpy()}))
    return pd.concat(parts, ignore_index=True), pd.DataFrame(specifications), extras


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    periods = str(datasets.parquet_path("derived.staking-periods", RUN))
    origins = {**UPGRADES, **QUARTERS}
    with ProcessPoolExecutor(workers) as pool:
        results = list(pool.map(model_runs, [(n, o, m, periods) for n, o in origins.items() for m in MODELS]))
    runs = pd.concat([r for r, _, _ in results], ignore_index=True)
    pd.concat([s for _, s, _ in results], ignore_index=True).to_csv(out / "development-specifications.csv", index=False)
    extras = [e for _, _, e in results if e is not None]
    if extras:
        drawn = pd.concat([e["draws"] for e in extras], ignore_index=True)
        drawn[["origin", "draw", *[c for c in drawn.columns if c not in ("origin", "draw")]]].to_csv(
            out / "draws.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
        pd.DataFrame([e["tau"] for e in extras]).to_csv(out / "tau.csv", index=False)
    # mtime 0 keeps the gzip header free of the clock, so identical runs give identical bytes.
    runs.to_csv(out / "development-runs.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    means = runs.groupby(["origin", "model", "variable", "horizon_days"]).value.mean()
    actual = actual_path(daily_events(periods))
    actual.index = pd.to_datetime(actual.pop("date_utc"))
    last_day = pd.Timestamp(LOCKBOX_FIRST_DAY) - pd.Timedelta(1, unit="D")
    rows = []
    for name, origin in origins.items():
        for variable in VARIABLES:
            series = actual[variable].astype(float)
            scale = ev.mase_scale(series, origin)
            for h in HORIZONS:
                if pd.Timestamp(origin + timedelta(days=h)) > last_day:
                    continue
                realized = ev.actual_at(series, origin, h)
                forecasts = {
                    **{m: float(means[(name, m, variable, h)]) for m in MODELS},
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
        wide = wide.loc[ev.chronological(wide.index, origins)]
        lags = ev.dm_horizon(h, [origins[o] for o in wide.index])
        pairs = [(m, b) for m in MODELS for b in ev.BENCHMARKS] + [("v0.8", "v0.7"), ("v0.8 u", "v0.8")]
        for model, benchmark in pairs:
            test = ev.diebold_mariano(wide[model], wide[benchmark], horizon=lags)
            summary.append({"variable": variable, "horizon_days": h, "model": model, "benchmark": benchmark, "origins": len(wide),
                            "model_mase": wide[model].mean(), "benchmark_mase": wide[benchmark].mean(),
                            "model_closer": int((wide[model] < wide[benchmark]).sum()),
                            "dm_statistic": test["statistic"], "p_model_better": test["p_less"], "dm_horizon": lags})
    pd.DataFrame(summary).to_csv(out / "development-summary.csv", index=False)
    print(pd.DataFrame(summary).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
