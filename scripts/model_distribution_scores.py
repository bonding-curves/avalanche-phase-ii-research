#!/usr/bin/env python3
"""Score the lifecycle models' runs as distributions at the development origins.

    uv run --group model python scripts/model_distribution_scores.py <folder>

Reads ``development-runs.csv.gz``, which ``scripts/model_development_scores.py`` writes in the same folder, so a change
to the scoring needs no new simulation. For each origin, variable and horizon it scores every model's runs and these
benchmarks, all built from data up to the origin only:

* ``N1d`` and ``N2d``: persistence and drift spread by every change of the same length in the 730 days before the
  origin (``evaluation.dressed``).
* ``N4``: a Gaussian local-level model fitted on every day to the origin (``evaluation.local_level``). Reported, not used
  as the reference, because its band is too wide on stake at 90 days and beyond.
* ``<model> pool``: one half the model's runs and one half ``N1d``'s sample.
* ``N1`` to ``N3``: point forecasts, whose CRPS is their absolute error.

Scores are the CRPS, the PIT, whether the realized value falls in the central 50% and 80% intervals, the 80% interval
score and the 80% width, with CRPS, score and width divided by the mean one-day change before the origin. A horizon
that would reach the held-back period, from 2025-11-19, is skipped.

Writes ``development-distribution.csv``, one row per origin, variable, horizon and forecast, and
``development-distribution-summary.csv``: per variable, horizon and forecast, the mean scaled CRPS, 50% and 80% coverage
with a binomial 95% range, the tail counts (PIT below 0.1 and above 0.9, against 10% each), the mean 80% width, the
CRPS skill against ``N1d``, and a Diebold-Mariano test on CRPS against ``N1d``, with the origins in date order and the
horizon from their dates (``evaluation.dm_horizon``).
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from avalanche_research import datasets
from avalanche_research.model import evaluation as ev
from avalanche_research.model.lifecycle import actual_path
from avalanche_research.model.replay import LOCKBOX_FIRST_DAY, daily_events

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_development_scores import QUARTERS, RUN, UPGRADES

REFERENCE = "N1d"


def normal_scores(mean: float, sd: float, actual: float, scale: float) -> dict[str, float]:
    lower50, upper50 = stats.norm.ppf([0.25, 0.75], mean, sd)
    lower80, upper80 = stats.norm.ppf([0.1, 0.9], mean, sd)
    return {"crps": ev.crps_normal(mean, sd, actual) / scale, "pit": float(stats.norm.cdf(actual, mean, sd)),
            "in50": float(lower50 <= actual <= upper50), "in80": float(lower80 <= actual <= upper80),
            "is80": ev.interval_score(lower80, upper80, actual, 0.8) / scale, "width80": (upper80 - lower80) / scale}


def point_scores(value: float, actual: float, scale: float) -> dict[str, float]:
    return {"crps": abs(value - actual) / scale, "pit": np.nan, "in50": np.nan, "in80": np.nan,
            "is80": np.nan, "width80": 0.0}


def binomial_range(hits: float, n: int) -> tuple[float, float]:
    """The Clopper-Pearson 95% range of a coverage share."""
    if n == 0:
        return np.nan, np.nan
    k = round(hits)
    lower = stats.beta.ppf(0.025, k, n - k + 1) if k > 0 else 0.0
    upper = stats.beta.ppf(0.975, k + 1, n - k) if k < n else 1.0
    return float(lower), float(upper)


def main() -> None:
    folder = Path(sys.argv[1])
    runs = pd.read_csv(folder / "development-runs.csv.gz")
    periods = str(datasets.parquet_path("derived.staking-periods", RUN))
    actual = actual_path(daily_events(periods))
    actual.index = pd.to_datetime(actual.pop("date_utc"))
    last_day = pd.Timestamp(LOCKBOX_FIRST_DAY) - pd.Timedelta(1, unit="D")
    origins = {**UPGRADES, **QUARTERS}
    rows = []
    for (name, variable, h), part in runs.groupby(["origin", "variable", "horizon_days"]):
        origin = origins[name]
        if pd.Timestamp(origin + timedelta(days=int(h))) > last_day:
            continue
        series = actual[variable].astype(float)
        scale, realized = ev.mase_scale(series, origin), ev.actual_at(series, origin, int(h))
        n1d = ev.dressed(series, origin, int(h), "N1")
        scored = {"N1d": ev.distribution_scores(n1d, realized, scale),
                  "N2d": ev.distribution_scores(ev.dressed(series, origin, int(h), "N2"), realized, scale),
                  "N4": normal_scores(*ev.local_level(series, origin, int(h)), realized, scale)}
        for b, rule in ev.BENCHMARKS.items():
            scored[b] = point_scores(rule(series, origin, int(h)), realized, scale)
        for model, draws in part.groupby("model").value:
            x = draws.to_numpy(dtype=float)
            scored[model] = ev.distribution_scores(x, realized, scale)
            pooled = np.concatenate([x, n1d])
            weights = np.concatenate([np.full(len(x), 0.5 / len(x)), np.full(len(n1d), 0.5 / len(n1d))])
            scored[f"{model} pool"] = ev.distribution_scores(pooled, realized, scale, weights=weights)
        for forecast, s in scored.items():
            rows.append({"origin": name, "variable": variable, "horizon_days": int(h), "forecast": forecast, **s,
                         "scale": scale, "actual": realized})
    scores = pd.DataFrame(rows)
    scores.to_csv(folder / "development-distribution.csv", index=False)
    summary = []
    for (variable, h), part in scores.groupby(["variable", "horizon_days"]):
        crps = part.pivot(index="origin", columns="forecast", values="crps")
        crps = crps.loc[ev.chronological(crps.index, origins)]
        lags = ev.dm_horizon(int(h), [origins[o] for o in crps.index])
        for forecast, g in part.groupby("forecast"):
            n = int(g.in80.notna().sum())
            row = {"variable": variable, "horizon_days": h, "forecast": forecast, "origins": len(g),
                   "crps": g.crps.mean(), "skill_vs_N1d": 1 - g.crps.mean() / crps[REFERENCE].mean()}
            for level in ("50", "80"):
                hits = g[f"in{level}"].sum()
                lower, upper = binomial_range(hits, n)
                row |= {f"cov{level}": hits / n if n else np.nan, f"cov{level}_low": lower, f"cov{level}_high": upper}
            row |= {"pit_below_10": int((g.pit < 0.1).sum()), "pit_above_90": int((g.pit > 0.9).sum()),
                    "width80": g.width80.mean()}
            if forecast != REFERENCE:
                test = ev.diebold_mariano(crps[forecast], crps[REFERENCE], horizon=lags)
                row |= {"closer_than_N1d": int((crps[forecast] < crps[REFERENCE]).sum()),
                        "dm_statistic": test["statistic"], "p_better_than_N1d": test["p_less"], "dm_horizon": lags}
            summary.append(row)
    summary = pd.DataFrame(summary)
    summary.to_csv(folder / "development-distribution-summary.csv", index=False)
    with pd.option_context("display.width", 200):
        print(summary[["variable", "horizon_days", "forecast", "origins", "crps", "cov80", "cov80_low", "cov80_high",
                       "pit_below_10", "pit_above_90", "width80", "skill_vs_N1d", "p_better_than_N1d"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
