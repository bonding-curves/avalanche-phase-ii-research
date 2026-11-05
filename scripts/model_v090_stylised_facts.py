#!/usr/bin/env python3
"""The stylised facts SF1 to SF10 on paths of the record's length from the two v0.9.0 models.

    uv run --group model python scripts/model_v090_stylised_facts.py OUT_DIR --pin PIN --price-pin PRICE_PIN [--workers W] [--batches B] [--days N]

Both models are the v0.8.1 candidate prepared at the last development origin, 1 October 2025, as
``scripts/model_v090_selection.py`` prepares it. The loops model carries that script's ``LOOPS``. The defaults model
carries the same price path, from the origin's price in the neutral scenario, and nothing else of the loops, so the
stake test SF4 can read a price on it. Its margin response stays 0, so the path changes none of its other outputs. Both
models record turnover. Each path runs 1,882 days after the origin, 1,883 days with it, the length of the record the
facts are measured on. Run r of batch b runs under seed 20b + r - 1 and reads draw row 20b + r - 1, as in the
selection, for both models alike. Two batches give 40 paths a model.

The facts each model must pass are ``model.stylised_paths.REQUIRED``, and a required fact that does not run counts as
a failure. The model counts an ending as renewed only when the node starts again the same day, where the record also
counts a return within 7 days, so the renewal facts compare the immediate part of renewal with the record's whole.
``--days`` below 1,883 or ``--batches`` below 2 is a rehearsal and writes no verdict.
"""

from __future__ import annotations

import argparse
import gc
import json
import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_development_scores import BATCH_RUNS, BATCH_SEEDS, DRAW_SEED, QUARTERS, batch_draws
from model_v090_selection import CHALLENGER, INCUMBENT, LOOPS, VARIANT, origin_price, worker_setup

from avalanche_research.experiments.v081_inputs import candidate_tables, pinned_inputs
from avalanche_research.model.engine import run
from avalanche_research.model.stylised_paths import REQUIRED, check, paths_from_table
from avalanche_research.model.variants import VARIANTS

ORIGIN_NAME = "2025-10-01"
ORIGIN = QUARTERS[ORIGIN_NAME]
DAYS = 1883
"""The record's length: 23 September 2020 to 18 November 2025."""
BATCHES = 2
MODELS = (INCUMBENT, CHALLENGER)
PRICE_PATH = {name: LOOPS[name] for name in ("price_drift_pa", "price_volatility_pa")}


def settings(model: str, price0: float) -> dict:
    """The settings each model adds to the prepared candidate."""
    both = {"price0_usd": price0, **PRICE_PATH, "record_turnover": True}
    return {**LOOPS, **both} if model == CHALLENGER else both


def task_files(out: Path, model: str, batch: int) -> tuple[Path, Path]:
    stem = f"{model.replace(' ', '-').replace('.', '')}_batch{batch}"
    return out / "tasks" / f"{stem}-paths.csv.gz", out / "tasks" / f"{stem}-specifications.csv"


def model_paths(task: tuple) -> tuple[Path, Path]:
    """One model's daily paths for one batch, written to the task's own files so a stopped run resumes."""
    model, batch, run_name, periods, delegators, days, out, price0 = task
    paths_file, spec_file = task_files(out, model, batch)
    if paths_file.exists() and spec_file.exists():
        print(f"{model} batch {batch}: already done", flush=True)
        return paths_file, spec_file
    variant = VARIANTS[VARIANT]
    prepared = variant.prepare(periods, ORIGIN, run_name, BATCH_RUNS * len(BATCH_SEEDS), DRAW_SEED,
                               delegations=candidate_tables(periods, delegators, ORIGIN))
    draws = batch_draws(prepared.draws, batch)
    parts, specifications = [], []
    for r in range(1, BATCH_RUNS + 1):
        seed = BATCH_RUNS * batch + r - 1
        simulation = variant.simulation(prepared, seed=seed, timesteps=days - 1, runs=1,
                                        draws=draws.iloc[[r - 1]].reset_index(drop=True)).with_settings(**settings(model, price0))
        specifications.append({"model": model, "batch_seed": batch, "run": r, "seed": seed, "specification": simulation.specification_hash()})
        path = paths_from_table(run(simulation), ORIGIN)[0]
        parts.append(path.rename_axis("day").reset_index().assign(model=model, batch_seed=batch, run=r, seed=seed))
        del simulation, path
        gc.collect()
    paths_file.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(parts, ignore_index=True).to_csv(paths_file, index=False, compression={"method": "gzip", "mtime": 0})
    pd.DataFrame(specifications).to_csv(spec_file, index=False)
    print(f"{model} batch {batch}: done", flush=True)
    return paths_file, spec_file


def read_paths(files: list[Path]) -> dict[str, list[pd.DataFrame]]:
    """Each model's paths, one frame per run indexed by calendar day, from the task files."""
    table = pd.concat([pd.read_csv(f, parse_dates=["day"]) for f in files], ignore_index=True)
    by_model = {}
    for (model, _, _), rows in table.groupby(["model", "batch_seed", "run"], sort=True):
        path = rows.drop(columns=["model", "batch_seed", "run", "seed"]).set_index("day").sort_index()
        path.index.name = None
        by_model.setdefault(model, []).append(path)
    return by_model


def measure(files: list[Path]) -> tuple[pd.DataFrame, dict]:
    """Every fact's result for each model, and each model's required facts that did not pass."""
    rows, verdict = [], {}
    for model, paths in read_paths(files).items():
        results, failing = check(paths, model)
        rows.append(results.assign(model=model))
        verdict[model] = {"required": list(REQUIRED[model]), "failing": sorted(set(failing["code"])),
                          "passed": failing.empty, "paths": len(paths)}
    return pd.concat(rows, ignore_index=True), verdict


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--pin", type=Path, required=True)
    parser.add_argument("--price-pin", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--batches", type=int, default=BATCHES)
    parser.add_argument("--days", type=int, default=DAYS)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    inputs = pinned_inputs(args.pin)
    periods, delegators, run_name = str(inputs.periods), str(inputs.delegators), inputs.periods_run
    price0 = origin_price(args.price_pin, ORIGIN)
    print(f"origin {ORIGIN_NAME}, price {price0:.4f}", flush=True)
    tasks = [(m, b, run_name, periods, delegators, args.days, args.out, price0) for m in MODELS for b in range(args.batches)]
    # As in the selection: fresh workers, each with its own DuckDB spill folder, one task each.
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context("spawn"), initializer=worker_setup,
                             max_tasks_per_child=1) as pool:
        results = list(pool.map(model_paths, tasks))
    pd.concat([pd.read_csv(s) for _, s in results], ignore_index=True).to_csv(args.out / "specifications.csv", index=False)
    table, verdict = measure([p for p, _ in results])
    table.to_csv(args.out / "stylised-facts.csv", index=False)
    if args.days == DAYS and args.batches == BATCHES:
        (args.out / "verdict.json").write_text(json.dumps(verdict, indent=2) + "\n")
        print(json.dumps(verdict, indent=2))
    else:
        print("rehearsal: shorter paths or fewer batches than the measurement, so no verdict is written")


if __name__ == "__main__":
    main()
