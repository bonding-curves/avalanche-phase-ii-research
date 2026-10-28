#!/usr/bin/env python3
"""The v0.8.1 candidate's system test against v0.8.0 at the 19 development origins, under the variant rule.

    uv run --group model python scripts/model_v081_selection.py OUT_DIR --pin PIN [--workers W] [--batches B] [--origins NAME ...]

The rule is the one v0.8.0 was chosen by (``scripts/model_v080_selection.py``, ``evaluation.adoption_verdict``): 200
runs per origin, each its own simulation under seed 20b + r - 1 for run r of batch b, one parameter draw per run, scored as distributions at
30, 90 and 180 days for active validators and validator stake, the mean worsening of the scaled CRPS of validator
stake at 90 days below 2.2, and no cell of the six clearly worse by a one-sided Diebold-Mariano test at 0.05/6. Both
models read the same seeds and draws at each origin. The candidate is prepared from the staking periods and the seamed
delegator stakes the pin names, as ``scripts/model_v081_origins.py`` does, so its delegations are the origin's own.

Writes ``development-runs.csv.gz`` and ``development-specifications.csv`` in the form of
``scripts/model_development_scores.py``, then scores them with ``scripts/model_distribution_scores.py`` into
``development-distribution.csv`` and its summary, and applies the rule into ``verdict.json``. The verdict's event-test
field is left open: the delegation blocks' own held-out tests are data science's, recorded with the frozen laws, and
this script does not restate them. ``--batches`` below ten is a rehearsal, not a score.
"""

from __future__ import annotations

import argparse
import gc
import json
import multiprocessing
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_development_scores import (
    BATCH_RUNS,
    BATCH_SEEDS,
    DRAW_SEED,
    HORIZONS,
    QUARTERS,
    UPGRADES,
    VARIABLES,
    batch_draws,
)

from avalanche_research.experiments.v081_inputs import candidate_tables, pinned_inputs
from avalanche_research.model import evaluation
from avalanche_research.model.engine import run
from avalanche_research.model.variants import VARIANTS

INCUMBENT, CHALLENGER = "v0.8.0", "v0.8.1 candidate"


def worker_setup(memory_limit: str = "1000MB", threads: int = 2) -> None:
    """Cap the worker's DuckDB connection, which the model's input queries share, so a pool of workers beside other
    jobs on one machine stays within its memory: the default limit is 80% of the machine's memory per connection."""
    duckdb.execute(f"SET memory_limit='{memory_limit}'")
    duckdb.execute(f"SET threads={threads}")


def task_files(out: Path, name: str, model: str) -> tuple[Path, Path]:
    """Where one origin and model's runs and specification hashes are checkpointed."""
    stem = f"{name}_{model.replace(' ', '-').replace('.', '')}"
    return out / "tasks" / f"{stem}-runs.csv.gz", out / "tasks" / f"{stem}-specifications.csv"


def model_runs(task: tuple[str, date, str, str, str, str, int, Path]) -> tuple[Path, Path]:
    """Every run's value at each horizon for one origin and model, and each run's specification hash, written to the
    task's own files so a stopped run resumes from the tasks already done."""
    name, origin, model, run_name, periods, delegators, batches, out = task
    runs_file, spec_file = task_files(out, name, model)
    if runs_file.exists() and spec_file.exists():
        print(f"{name} {model}: already done", flush=True)
        return runs_file, spec_file
    variant = VARIANTS[model]
    tables = {"delegations": candidate_tables(periods, delegators, origin)} if model == CHALLENGER else {}
    prepared = variant.prepare(periods, origin, run_name, BATCH_RUNS * len(BATCH_SEEDS), DRAW_SEED, **tables)
    parts, specifications = [], []
    # One run per simulation: a 20-run batch of the candidate would hold every run's daily delegation arrays until the
    # batch ends, tens of gigabytes at an origin with 150,000 open delegations. Run r of batch b runs under seed
    # 20b + r - 1 and reads draw row 20b + r - 1, the row the batch design gave it, for both models alike.
    for batch in list(BATCH_SEEDS)[:batches]:
        draws = batch_draws(prepared.draws, batch)
        for r in range(1, BATCH_RUNS + 1):
            seed = BATCH_RUNS * batch + r - 1
            simulation = variant.simulation(prepared, seed=seed, timesteps=max(HORIZONS), runs=1, draws=draws.iloc[[r - 1]].reset_index(drop=True))
            specifications.append({"origin": name, "model": model, "batch_seed": batch, "run": r, "seed": seed, "specification": simulation.specification_hash()})
            t = run(simulation)
            t = t[t.timestep.isin(HORIZONS) & t.variable.isin(VARIABLES)]
            parts.append(pd.DataFrame({"origin": name, "model": model, "batch_seed": batch, "run": r,
                                       "variable": t.variable.to_numpy(), "horizon_days": t.timestep.to_numpy(),
                                       "value": t.value.astype(float).to_numpy()}))
            del t, simulation
            gc.collect()
    runs_file.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(parts, ignore_index=True).to_csv(runs_file, index=False, compression={"method": "gzip", "mtime": 0})
    pd.DataFrame(specifications).to_csv(spec_file, index=False)
    print(f"{name} {model}: done", flush=True)
    return runs_file, spec_file


def verdict(folder: Path) -> dict:
    """The rule applied to ``development-distribution.csv`` in ``folder``, with the system figures of every cell."""
    scores = pd.read_csv(folder / "development-distribution.csv")
    dates = {**UPGRADES, **QUARTERS}
    rows = []
    for (origin, variable, horizon), group in scores.groupby(["origin", "variable", "horizon_days"]):
        crps = group.set_index("forecast")["crps"]
        rows.append({"origin": origin, "date": pd.Timestamp(dates[origin]), "variable": variable, "horizon": int(horizon),
                     "challenger": float(crps[CHALLENGER]), "incumbent": float(crps[INCUMBENT])})
    table = pd.DataFrame(rows)
    origins = sorted({dates[o] for o in table.origin.unique()})
    result = evaluation.adoption_verdict({"event_test": None, "calibration": True, "origin_available": None}, table, origins)
    cells = {f"{variable} {horizon}": {"mean_difference": round(cell["mean_difference"], 3), "p_worse": round(cell["p_worse"], 4)}
             for (variable, horizon), cell in result["cells"].items()}
    system_pass = (result["primary_mean_difference"] < evaluation.ADOPTION_MARGIN
                   and all(cell["p_worse"] >= evaluation.ADOPTION_CELL_ALPHA for cell in result["cells"].values()))
    return {"challenger": CHALLENGER, "incumbent": INCUMBENT, "origins": int(table.origin.nunique()),
            "verdict": result["verdict"], "reasons": result.get("reasons", []),
            "system_test": "pass" if system_pass else "fail",
            "stake_90_day_difference": round(result["primary_mean_difference"], 4), "cells": cells}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--pin", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--batches", type=int, default=len(BATCH_SEEDS))
    parser.add_argument("--origins", nargs="*", default=None)
    parser.add_argument("--score-only", action="store_true", help="skip the runs and score the folder's development-runs.csv.gz")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    inputs = pinned_inputs(args.pin)
    periods, delegators, run_name = str(inputs.periods), str(inputs.delegators), inputs.periods_run
    origins = {**UPGRADES, **QUARTERS}
    if args.origins:
        origins = {name: origins[name] for name in args.origins}
    if not args.score_only:
        # The released model at every origin first, then the candidate from the earliest origin, so the largest origins come last.
        by_date = sorted(origins.items(), key=lambda item: item[1])
        tasks = [(n, o, m, run_name, periods, delegators, args.batches, args.out) for m in (INCUMBENT, CHALLENGER) for n, o in by_date]
        # Workers start afresh rather than forked, since a forked copy of the parent's DuckDB connection deadlocks on its
        # first query, and each serves one task, so the memory a task grew is returned to the machine when it ends.
        with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context("spawn"), initializer=worker_setup,
                                 max_tasks_per_child=1) as pool:
            results = list(pool.map(model_runs, tasks))
        pd.concat([pd.read_csv(r) for r, _ in results], ignore_index=True).to_csv(args.out / "development-runs.csv.gz", index=False,
                                                                                  compression={"method": "gzip", "mtime": 0})
        pd.concat([pd.read_csv(s) for _, s in results], ignore_index=True).to_csv(args.out / "development-specifications.csv", index=False)
    full = len(origins) == len({**UPGRADES, **QUARTERS}) and args.batches == len(BATCH_SEEDS)
    # The scorer's summary needs three origins for its test, so a rehearsal keeps its per-cell scores and may lose the summary.
    subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "model_distribution_scores.py"), str(args.out)], check=full)
    if full:
        result = verdict(args.out)
        (args.out / "verdict.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    else:
        print("rehearsal: fewer origins or batches than the rule, so no verdict is written")


if __name__ == "__main__":
    main()
