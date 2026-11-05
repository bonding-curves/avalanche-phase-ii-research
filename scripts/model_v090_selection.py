#!/usr/bin/env python3
"""The v0.9.0 system test: the v0.8.1 candidate with the v0.9.0 loops on, against the same candidate at the defaults,
at the 19 development origins, under the variant rule.

    uv run --group model python scripts/model_v090_selection.py OUT_DIR --pin PIN --price-pin PRICE_PIN [--workers W] [--batches B] [--origins NAME ...]

The rule, the runs and the keys are those of ``scripts/model_v081_selection.py``: 200 runs per origin, run r of batch b
under seed 20b + r - 1 with draw row 20b + r - 1, both models on the same seeds and draws, scaled CRPS at 30, 90 and
180 days, the 2.2 margin on validator stake at 90 days and no cell clearly worse at 0.05/6. The incumbent is the v0.8.1
candidate at its defaults on this code, which is also v0.9.0 at its defaults, so its scores reproduce the v0.8.1
reselection's (H33). The challenger is the same candidate with the loops of v0.9.0 on (``LOOPS``): the yield gap at the
day's own counter and staked share, a price path from the origin's price in the neutral scenario, and the concave dollar
margin in renewal at the fit on all validators of 2,100 AVAX or less to 18 November 2025, 0.19 at a node cost of 5,000
dollars a year (D16, breakeven_profile.csv). The origin's price is the last one observed at or before the origin's
last instant, 23:59:59 UTC, in the price run ``PRICE_PIN`` names, read by its ``observed_at`` time, so no quote that
was not yet observed enters. ``--batches`` below ten is a rehearsal, not a score.
"""

from __future__ import annotations

import argparse
import gc
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
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

from avalanche_research.datasets import parquet_path, pins
from avalanche_research.experiments.v081_inputs import candidate_tables, pinned_inputs
from avalanche_research.model.price import PRICE_SCENARIOS
from avalanche_research.model import evaluation
from avalanche_research.model.engine import run
from avalanche_research.model.variants import VARIANTS

VARIANT = "v0.8.1 candidate"
INCUMBENT, CHALLENGER = "v0.9.0 defaults", "v0.9.0 loops"
PRICE_DATASET = "defillama.avax-price-daily"
LOOPS = {"yield_gap_at": "live", "price_drift_pa": PRICE_SCENARIOS["neutral"][0],
         "price_volatility_pa": PRICE_SCENARIOS["neutral"][1], "margin_response": 0.1926, "node_cost_usd_pa": 5000.0}
"""The challenger's settings beside the origin's price. The margin response and cost are the all-validator fit at 5,000
dollars a year; E033 sweeps the cost."""


def origin_price(price_pin: Path, origin: date) -> float:
    """The last AVAX price observed at or before the origin's last instant, 23:59:59 UTC, in the pinned price run. The
    run's Parquet file must have the SHA-256 the pin records, so a run rebuilt under the same name is refused."""
    import hashlib

    entry = next(run for run in pins.read(price_pin)["runs"] if run["dataset_id"] == PRICE_DATASET)
    parquet = parquet_path(PRICE_DATASET, entry["run"])
    with open(parquet, "rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != entry["sha256"]:
        raise ValueError(f"{parquet} has SHA-256 {digest}, not the {entry['sha256']} that {price_pin} pins")
    row = duckdb.execute("SELECT price_usd FROM read_parquet(?) WHERE observed_at <= ?::TIMESTAMP ORDER BY observed_at DESC LIMIT 1",
                         [str(parquet), f"{origin.isoformat()} 23:59:59"]).fetchone()
    if row is None:
        raise ValueError(f"no price observed by {origin} in {parquet}")
    return float(row[0])


def worker_setup(memory_limit: str = "1000MB", threads: int = 2) -> None:
    """Cap the worker's DuckDB connection, which the model's input queries share, so a pool of workers beside other
    jobs on one machine stays within its memory: the default limit is 80% of the machine's memory per connection.
    Each worker spills to its own folder, since an in-memory connection otherwise spills to `.tmp` under the working
    directory, which every worker shares."""
    duckdb.execute(f"SET temp_directory='{tempfile.mkdtemp(prefix=f'duckdb-spill-{os.getpid()}-')}'")
    duckdb.execute(f"SET memory_limit='{memory_limit}'")
    duckdb.execute(f"SET threads={threads}")


def task_files(out: Path, name: str, model: str) -> tuple[Path, Path]:
    """Where one origin and model's runs and specification hashes are checkpointed."""
    stem = f"{name}_{model.replace(' ', '-').replace('.', '')}"
    return out / "tasks" / f"{stem}-runs.csv.gz", out / "tasks" / f"{stem}-specifications.csv"


def model_runs(task: tuple[str, date, str, str, str, str, int, Path, float]) -> tuple[Path, Path]:
    """Every run's value at each horizon for one origin and model, and each run's specification hash, written to the
    task's own files so a stopped run resumes from the tasks already done."""
    name, origin, model, run_name, periods, delegators, batches, out, price0 = task
    runs_file, spec_file = task_files(out, name, model)
    if runs_file.exists() and spec_file.exists():
        print(f"{name} {model}: already done", flush=True)
        return runs_file, spec_file
    variant = VARIANTS[VARIANT]
    tables = {"delegations": candidate_tables(periods, delegators, origin)}
    loops = {**LOOPS, "price0_usd": price0} if model == CHALLENGER else {}
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
            if loops:
                simulation = simulation.with_settings(**loops)
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
    # The rule checks each cell against every registered origin, given here and not read from the scores, so a folder
    # missing an origin's scores raises rather than passing on the origins it holds.
    origins = sorted(set(dates.values()))
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
    parser.add_argument("--price-pin", type=Path, required=True)
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
        # The defaults at every origin first, then the loops from the earliest origin, so the largest origins come last.
        by_date = sorted(origins.items(), key=lambda item: item[1])
        prices = {n: origin_price(args.price_pin, o) for n, o in by_date}
        print({n: round(p, 4) for n, p in prices.items()}, flush=True)
        tasks = [(n, o, m, run_name, periods, delegators, args.batches, args.out, prices[n]) for m in (INCUMBENT, CHALLENGER) for n, o in by_date]
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
