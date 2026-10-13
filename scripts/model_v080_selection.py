#!/usr/bin/env python3
"""The v0.8.0 selection: recompute its verdict from the committed scores, and check those scores came from this code.

    uv run --group model python scripts/model_v080_selection.py verdict
    uv run --group model python scripts/model_v080_selection.py specifications [origin ...]
    uv run --group model python scripts/model_v080_selection.py outputs [origin ...]

v0.8.0 is the variant ``v0.8-a stake return u`` of ``avalanche_research.model.variants``, released as ``v0.8.0``. It
was chosen against candidate a with parameter draws, ``v0.8-a u``, by the variant rule
``evaluation.adoption_verdict``: 200 runs per origin at the 19 development origins, scored as distributions
(``scripts/model_development_scores.py`` then ``scripts/model_distribution_scores.py``), the mean worsening of the
scaled CRPS of validator stake at 90 days below 2.2, and no cell of the six (active validators and validator stake at
30, 90 and 180 days) clearly worse by a one-sided Diebold-Mariano test at 0.05/6.

``verdict`` reads ``results/model-v0.8.0-selection/development-distribution.csv``, applies the rule, and prints the
verdict, the 90-day stake difference and each cell, then checks them against ``verdict.json`` beside it. It takes
seconds and needs no data.

``specifications`` rebuilds each origin's two models from the pinned staking periods and compares every batch's
specification hash with ``development-specifications.csv``. Equal hashes mean the same settings, fitted parameters and
input digests as the scored models. They do not identify the code. ``outputs`` reruns batch 0 of both models at each
named origin (Banff by default) and compares every run's values at the three horizons with
``development-runs.csv.gz``, so equal outputs show this code reproduces the scored runs at those origins. It needs the staking periods of pin ``data/pins/p2-model-v0.8.json`` and
takes about a minute per origin. Rerunning the 200 runs themselves is ``scripts/model_development_scores.py`` with
``MODELS = ("v0.8-a u", "v0.8-a stake return u")``, several hours on six workers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_development_scores import (
    BATCH_RUNS,
    BATCH_SEEDS,
    DRAW_SEED,
    HORIZONS,
    QUARTERS,
    UPGRADES,
)

from avalanche_research.model import evaluation

FOLDER = Path(__file__).resolve().parents[1] / "results" / "model-v0.8.0-selection"
CHALLENGER, INCUMBENT = "v0.8-a stake return u", "v0.8-a u"
PIN = Path("data/pins/p2-model-v0.8.json")


VARIABLES = ("active_validator_stake_navax", "active_validators")


def checked_scores(scores: pd.DataFrame) -> pd.DataFrame:
    """Refuse a score table that is not the design: the 19 origins, two variables, the three horizons as exact whole
    days, and one score per model in every cell."""
    dates = {**UPGRADES, **QUARTERS}
    horizons = pd.to_numeric(scores["horizon_days"], errors="coerce")
    if not horizons.isin([float(h) for h in HORIZONS]).all():
        raise ValueError(f"horizons must be exactly {HORIZONS} days, not {sorted(scores['horizon_days'].unique())}")
    if set(scores["origin"]) != set(dates) or set(scores["variable"]) != set(VARIABLES):
        raise ValueError("the scores must cover exactly the 19 development origins and the two variables")
    # A horizon that would reach the held-back period is not scored, so late origins have fewer cells.
    keys = ["origin", "variable", "horizon_days"]
    cells = scores.assign(horizon_days=horizons.astype(int)).groupby(keys)["forecast"].agg(list)
    if any(sorted(f.count(model) for model in (CHALLENGER, INCUMBENT)) != [1, 1] for f in cells):
        raise ValueError("every scored origin, variable and horizon needs exactly one score for each of the two models")
    return scores.assign(horizon_days=horizons.astype(int))


def verdict() -> dict:
    """The variant rule applied to the committed distribution scores."""
    scores = checked_scores(pd.read_csv(FOLDER / "development-distribution.csv"))
    dates = {**UPGRADES, **QUARTERS}
    rows = []
    for (origin, variable, horizon), group in scores.groupby(["origin", "variable", "horizon_days"]):
        crps = group.set_index("forecast")["crps"]
        rows.append({"origin": origin, "date": pd.Timestamp(dates[origin]), "variable": variable, "horizon": int(horizon),
                     "challenger": float(crps[CHALLENGER]), "incumbent": float(crps[INCUMBENT])})
    table = pd.DataFrame(rows)
    # Both blocks passed their held-out event tests before this system test (the stake hurdle and the return hazard).
    result = evaluation.adoption_verdict({"event_test": True, "calibration": True, "origin_available": True}, table,
                                         sorted(set(dates.values())))
    return {"challenger": CHALLENGER, "incumbent": INCUMBENT, "origins": int(table.origin.nunique()),
            "verdict": result["verdict"], "stake_90_day_difference": round(result["primary_mean_difference"], 4),
            "cells": {f"{variable} {horizon}": {"mean_difference": round(cell["mean_difference"], 3),
                                                "p_worse": round(cell["p_worse"], 4)}
                      for (variable, horizon), cell in result["cells"].items()}}


def specifications(origins: list[str]) -> list[str]:
    """Origins whose rebuilt specification hashes differ from the committed ones."""
    from model_development_scores import batch_draws

    from avalanche_research import datasets
    from avalanche_research.datasets import pins
    from avalanche_research.model.variants import VARIANTS

    run = pins.runs(PIN)["derived.staking-periods"]
    periods = str(datasets.parquet_path("derived.staking-periods", run))
    recorded = pd.read_csv(FOLDER / "development-specifications.csv")
    dates = {**UPGRADES, **QUARTERS}
    differ = []
    for name in origins or list(dates):
        for model in (INCUMBENT, CHALLENGER):
            variant = VARIANTS[model]
            prepared = variant.prepare(periods, dates[name], run, BATCH_RUNS * len(BATCH_SEEDS), DRAW_SEED)
            for seed in BATCH_SEEDS:
                simulation = variant.simulation(prepared, seed=seed, timesteps=max(HORIZONS), runs=BATCH_RUNS,
                                                draws=batch_draws(prepared.draws, seed))
                want = recorded.query("origin == @name and model == @model and batch_seed == @seed")["specification"]
                if want.tolist() != [simulation.specification_hash()]:
                    differ.append(f"{name} {model} batch {seed}")
        print(f"{name}: {'differs' if any(d.startswith(name + ' ') for d in differ) else 'equal'}", flush=True)
    return differ


def outputs(origins: list[str]) -> list[str]:
    """Origins where batch 0 of either model, rerun now, differs from the scored runs in ``development-runs.csv.gz``."""
    from model_development_scores import VARIABLES as RUN_VARIABLES
    from model_development_scores import batch_draws

    from avalanche_research import datasets
    from avalanche_research.datasets import pins
    from avalanche_research.model.engine import run as run_model
    from avalanche_research.model.variants import VARIANTS

    run = pins.runs(PIN)["derived.staking-periods"]
    periods = str(datasets.parquet_path("derived.staking-periods", run))
    # Round-trip parsing: the default parser can move the last bit of a float written in full.
    recorded = pd.read_csv(FOLDER / "development-runs.csv.gz", float_precision="round_trip")
    dates = {**UPGRADES, **QUARTERS}
    differ = []
    for name in origins or ["Banff"]:
        for model in (INCUMBENT, CHALLENGER):
            variant = VARIANTS[model]
            prepared = variant.prepare(periods, dates[name], run, BATCH_RUNS * len(BATCH_SEEDS), DRAW_SEED)
            table = run_model(variant.simulation(prepared, seed=0, timesteps=max(HORIZONS), runs=BATCH_RUNS,
                                                 draws=batch_draws(prepared.draws, 0)))
            table = table[table.timestep.isin(HORIZONS) & table.variable.isin(RUN_VARIABLES)]
            now = sorted(zip(table.run, table.variable, table.timestep, table.value.astype(float)))
            then = recorded.query("origin == @name and model == @model and batch_seed == 0")
            then = sorted(zip(then.run, then.variable, then.horizon_days, then.value.astype(float)))
            if now != then:
                differ.append(f"{name} {model}")
        print(f"{name}: {'differs' if any(d.startswith(name + ' ') for d in differ) else 'equal'}", flush=True)
    return differ


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("verdict", "specifications", "outputs"):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    if argv[0] == "verdict":
        got = verdict()
        print(json.dumps(got, indent=1))
        expected = json.loads((FOLDER / "verdict.json").read_text())
        if got != expected:
            print("FAIL: the verdict differs from verdict.json", file=sys.stderr)
            return 1
        print("PASS: the verdict equals verdict.json")
        return 0
    if argv[0] == "outputs":
        differ = outputs(argv[1:])
        if differ:
            print("FAIL: rerun outputs differ for " + "; ".join(differ), file=sys.stderr)
            return 1
        print("PASS: every rerun batch equals the scored runs")
        return 0
    differ = specifications(argv[1:])
    if differ:
        print("FAIL: specification hashes differ for " + "; ".join(differ), file=sys.stderr)
        return 1
    print("PASS: every rebuilt specification hash equals the recorded one")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
