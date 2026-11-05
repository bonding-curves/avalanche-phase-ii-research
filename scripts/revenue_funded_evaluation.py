"""Revenue-funded rewards against the chain's rule: paired five-year trajectories at the measured responses.

Runs model v0.8.0's lifecycle (variant ``v0.8.0``) from the Milestone 2 origin of 2025-11-18 on the Milestone 2
sweep's own parameter draws: key ``n`` is draw ``n`` of the sweep's ``draws.parquet`` and model seed ``n + 1``. Every
cell runs on the same keys as its twin under the chain's rule, so a cell-minus-twin difference removes the noise the
pair shares. Each run is 1,825 days and is read at 365 and 1,825 days; the script checks on key 0 that a 365-day run
equals the first 365 days of the 1,825-day run.

A cell is the rule ``RevenueFunded`` at the Foundation's share of 0.5 under one shortfall rule (``top_up`` or
``cut``) with one revenue stream in AVAX a year, given by a JSON file of streams::

    {"streams": {"fees-1x": {"avax_pa": 274384, "note": "..."}, ...}, "share": 0.5}

Usage, from the client repository root on branch ``prototype/revenue-funding``::

    python scripts/revenue_funded_evaluation.py --streams streams.json --out DIR --seeds 50 --workers 6

Writes ``daily.parquet`` (one row per cell, key and day), ``horizons.parquet`` (one row per cell, key and horizon
with the twin's values beside it), ``cells.json`` and ``receipt.json`` into ``DIR``.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import multiprocessing
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ORIGIN = date(2025, 11, 18)
TIMESTEPS = 1825
HORIZONS = (365, 1825)
OUTSIDE_YIELD_PP = 5.0
CENTRAL = {"renewal_response": 0.025, "entry_response": 0.04}
"""The responses measured on the record before 19 November 2025 (model-risks/behaviour-responses.md, D9)."""
PIN = Path("data/pins/p2-model-v0.8.json")
SWEEP_DESIGN = Path.home() / ".local/share/bcrg/data-engineering/2026-10-13/m2-full-prepared"
DRAWS_SHA256 = "0e4a238778597b44e33b1be31a6179b715d67de0d2dd773ad6faca12331df75d"
STATE = ("active_validators", "active_validator_stake_navax", "supply_navax", "issued_navax",
         "revenue_paid_navax", "unpaid_need_navax", "revenue_pool_navax", "started_stake_navax")
FLOATS = ("offered_rate_30d", "yield_gap_pp")


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def cells_from(streams: dict, share: float) -> dict[str, dict]:
    cells = {"chain": {"mechanism": {"name": "ChainReward"}, "stream": None, "avax_pa": 0.0, "shortfall": None, "twin": None}}
    for name, stream in streams.items():
        for rule in ("top_up", "cut"):
            cells[f"{name}-{rule}"] = {
                "mechanism": {"name": "RevenueFunded", "revenue_share": share, "shortfall": rule},
                "stream": name, "avax_pa": float(stream["avax_pa"]), "shortfall": rule, "twin": "chain", "note": stream.get("note", ""),
            }
    return cells


_BASE = None  # the base model, inherited by forked workers


def row_settings(cell: dict, fitted_yield_pp: float, seed: int) -> dict:
    from avalanche_research.model.runner import model_settings

    values = model_settings({"seed": seed, "mechanism": dict(cell["mechanism"]), **CENTRAL,
                             "outside_yield_pp": OUTSIDE_YIELD_PP, "fitted_outside_yield_pp": fitted_yield_pp})
    if cell["avax_pa"] > 0:
        values["revenue_avax_pa"] = cell["avax_pa"]
    return values


def simulate(task: dict) -> pd.DataFrame:
    from avalanche_research.model.engine import run

    values = row_settings(task["cell"], task["fitted_yield_pp"], task["seed"])
    values["draws"] = _BASE.draws.iloc[[task["draw"]]].reset_index(drop=True)
    model = _BASE.with_settings(**values, timesteps=task["timesteps"])
    with contextlib.redirect_stdout(io.StringIO()):
        table = run(model)
    return wide_table(table, task["cell_name"], task["seed"], task["draw"], model.specification_hash())


def wide_table(table: pd.DataFrame, cell_name: str, seed: int, draw: int, specification: str) -> pd.DataFrame:
    present = [name for name in STATE if name in set(table["variable"])]
    keep = table[table["variable"].isin(present)]
    wide = keep.pivot_table(index="timestep", columns="variable", values="value", aggfunc="first")
    wide.columns.name = None
    for column in FLOATS:
        wide[column] = table.groupby("timestep")[column].first()
    for name in STATE:
        if name not in wide.columns:
            wide[name] = 0
        wide[name] = wide[name].map(int).astype("int64")
    wide = wide.reset_index().rename(columns={"timestep": "day"})
    for name in ("issued_navax", "revenue_paid_navax", "unpaid_need_navax"):
        wide[f"cumulative_{name}"] = wide[name].cumsum().astype("int64")
    wide.insert(0, "cell", cell_name)
    wide.insert(1, "seed", seed)
    wide.insert(2, "draw", draw)
    wide["specification"] = specification
    return wide


def horizons_table(daily: pd.DataFrame, cells: dict, horizons: list[int]) -> pd.DataFrame:
    """One row per cell, key and horizon: the run's values at the horizon beside its twin's on the same key."""
    at = daily[daily["day"].isin(horizons)].copy()
    at = at.rename(columns={"day": "horizon_days"})
    columns = ["active_validators", "active_validator_stake_navax", "supply_navax", "cumulative_issued_navax",
               "cumulative_revenue_paid_navax", "cumulative_unpaid_need_navax", "revenue_pool_navax"]
    twin = at[at["cell"] == "chain"][["draw", "horizon_days", *columns]].rename(columns={c: f"twin_{c}" for c in columns})
    out = at.merge(twin, on=["draw", "horizon_days"], how="left")
    out["twin"] = out["cell"].map(lambda c: cells[c]["twin"])
    out["stream"] = out["cell"].map(lambda c: cells[c]["stream"])
    out["avax_pa"] = out["cell"].map(lambda c: cells[c]["avax_pa"])
    out["shortfall"] = out["cell"].map(lambda c: cells[c]["shortfall"])
    out["years"] = out["horizon_days"] / 365
    priced = out["cumulative_issued_navax"] + out["cumulative_revenue_paid_navax"] + out["cumulative_unpaid_need_navax"]
    received = out["cumulative_issued_navax"] + out["cumulative_revenue_paid_navax"]
    out["issuance_saved"] = 1 - out["cumulative_issued_navax"] / out["twin_cumulative_issued_navax"]
    out["validator_stake_kept"] = out["active_validator_stake_navax"] / out["twin_active_validator_stake_navax"]
    out["validators_kept"] = out["active_validators"] / out["twin_active_validators"]
    out["revenue_share_of_rewards_received"] = out["cumulative_revenue_paid_navax"] / received
    out["unpaid_share_of_rewards_priced"] = out["cumulative_unpaid_need_navax"] / priced
    out["rewards_received_vs_twin"] = received / out["twin_cumulative_issued_navax"]
    out["coverage_of_half_twin_rewards"] = (out["avax_pa"] * out["years"]) / (0.5 * out["twin_cumulative_issued_navax"] / 1e9)
    out["twin_rewards_avax_pa"] = out["twin_cumulative_issued_navax"] / 1e9 / out["years"]
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--streams", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timesteps", type=int, default=TIMESTEPS)
    parser.add_argument("--cells", default="all")
    args = parser.parse_args(argv)

    from avalanche_research.experiments.sweep import load_draws, pinned_periods
    from avalanche_research.model.engine import run
    from avalanche_research.model.variants import VARIANTS

    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    clock = time.time()
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "scripts"], capture_output=True, text=True, check=True).stdout.strip()
    design = json.loads((SWEEP_DESIGN / "design.json").read_text())
    fitted_yield_pp = float(design["provenance"]["fitted_outside_yield_pp"])
    if sha256_file(SWEEP_DESIGN / "draws.parquet") != DRAWS_SHA256 or design["draws_sha256"] != DRAWS_SHA256:
        raise SystemExit("the sweep's draw table is not the one the Milestone 2 sweep ran")
    draws = load_draws({"draws_file": str(SWEEP_DESIGN / "draws.parquet"), "draws_sha256": DRAWS_SHA256})
    periods, periods_run = pinned_periods(PIN)
    keys = list(range(args.seeds))
    spec = json.loads(args.streams.read_text())
    cells = cells_from(spec["streams"], float(spec.get("share", 0.5)))
    if args.cells != "all":
        cells = {name: cells[name] for name in ("chain", *args.cells.split(","))}
    horizons = [h for h in HORIZONS if h <= args.timesteps] or [args.timesteps]

    print(f"building the base model at {ORIGIN} from {periods_run} ...", flush=True)
    variant = VARIANTS["v0.8.0"]
    prepared = variant.prepare(periods, ORIGIN, periods_run, draws=0)
    global _BASE
    _BASE = variant.model(timesteps=args.timesteps, runs=1, seed=0, **prepared.inputs, draws=draws.iloc[keys].reset_index(drop=True))
    print(f"base built in {time.time() - clock:.0f}s, specification {_BASE.specification_hash()}", flush=True)

    # Check on key 0: a one-year run under the chain's rule equals the first year of the long run, day for day.
    short = {"cell_name": "chain", "cell": cells["chain"], "seed": 1, "draw": 0, "fitted_yield_pp": fitted_yield_pp, "timesteps": min(365, args.timesteps)}
    one = simulate(short)
    t0 = time.time()
    long = simulate({**short, "timesteps": args.timesteps})
    one_run_seconds = time.time() - t0
    compared = ["active_validators", "active_validator_stake_navax", "supply_navax", "issued_navax"]
    equal = one[compared].reset_index(drop=True).equals(long[compared].iloc[: len(one)].reset_index(drop=True))
    if not equal:
        raise SystemExit("the first year of the long run does not equal the one-year run on key 0")
    print(f"check passed: first {len(one)} days of the long run equal the short run on key 0", flush=True)

    tasks = [{"cell_name": name, "cell": cell, "seed": k + 1, "draw": k, "fitted_yield_pp": fitted_yield_pp, "timesteps": args.timesteps}
             for name, cell in cells.items() for k in keys]
    print(f"{len(tasks)} runs: {len(cells)} cells x {len(keys)} keys on {args.workers} workers", flush=True)
    frames = []
    done = 0
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context("fork")) as pool:
        futures = [pool.submit(simulate, task) for task in tasks]
        for future in as_completed(futures):
            frames.append(future.result())
            done += 1
            if done % 25 == 0 or done == len(tasks):
                print(f"  {done}/{len(tasks)} runs, {time.time() - clock:.0f}s elapsed", flush=True)
    daily = pd.concat(frames, ignore_index=True).sort_values(["cell", "seed", "day"]).reset_index(drop=True)
    daily["date"] = [ORIGIN + timedelta(days=int(d)) for d in daily["day"]]
    at = horizons_table(daily, cells, horizons)
    args.out.mkdir(parents=True, exist_ok=True)
    daily_path = args.out / "daily.parquet"
    duckdb.register("daily", daily)
    duckdb.execute(f"COPY (SELECT * FROM daily ORDER BY cell, seed, day) TO '{daily_path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    at_path = args.out / "horizons.parquet"
    duckdb.register("horizons_frame", at)
    duckdb.execute(f"COPY (SELECT * FROM horizons_frame ORDER BY cell, horizon_days, seed) TO '{at_path}' (FORMAT PARQUET)")
    files = [daily_path, at_path]
    cells_path = args.out / "cells.json"
    cells_path.write_text(json.dumps({"cells": cells, **CENTRAL, "outside_yield_pp": OUTSIDE_YIELD_PP, "fitted_outside_yield_pp": fitted_yield_pp,
                                      "share": float(spec.get("share", 0.5)), "streams": spec["streams"]}, indent=1) + "\n")
    files.append(cells_path)
    receipt = {
        "model": "v0.8.0 lifecycle on branch prototype/revenue-funding", "client_head": head, "source_dirty": dirty.splitlines(),
        "origin": ORIGIN.isoformat(), "timesteps": args.timesteps, "horizons": horizons,
        "pin": str(PIN), "pin_sha256": sha256_file(PIN), "staking_periods_run": periods_run,
        "draws_file": str(SWEEP_DESIGN / "draws.parquet"), "draws_sha256": DRAWS_SHA256,
        "keys": keys, "seeds": [k + 1 for k in keys], "cells": list(cells), "runs": len(tasks), "workers": args.workers,
        "responses": CENTRAL, "outside_yield_pp": OUTSIDE_YIELD_PP, "fitted_outside_yield_pp": fitted_yield_pp,
        "base_specification": _BASE.specification_hash(),
        "first_year_check": {"key": 0, "cell": "chain", "days": int(len(one)), "variables": compared, "equal": True},
        "streams_file": str(args.streams), "streams_sha256": sha256_file(args.streams),
        "started": started_at, "finished": datetime.now().astimezone().isoformat(timespec="seconds"),
        "seconds": round(time.time() - clock, 1), "one_long_run_seconds": round(one_run_seconds, 2),
        "files": {path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size} for path in files},
        "daily_columns": list(daily.columns), "daily_rows": int(len(daily)),
    }
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=1, default=str) + "\n")
    print(json.dumps({k: receipt[k] for k in ("runs", "seconds", "one_long_run_seconds", "daily_rows", "files")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
