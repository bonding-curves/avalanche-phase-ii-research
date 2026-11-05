"""Duration-curve reward rules against the chain's rule: paired one-year runs at the measured and swept responses.

Runs model v0.8.0's lifecycle (variant ``v0.8.0``) from the Milestone 2 origin of 2025-11-18 on the Milestone 2
sweep's own parameter draws: key ``n`` is draw ``n`` of the sweep's ``draws.parquet`` and model seed ``n + 1``. Every
cell runs on the same keys as its twin under the chain's rule at the same responses, so a cell-minus-twin difference
removes the noise the pair shares.

The cells are five consumption-rate formulas as ``DurationCurve`` settings, applied from the origin with no ramp:
the rule before Helicon (10% to 12%), ACP-285's target (7.5% to 12%), the bump curve of the July 2026 discussion,
and two flat minima that lift ACP-285's line to a floor. ACP-285's 90-day ramp started at the origin is kept as the
reference cell of the Milestone 2 central case. Each formula runs at every response point given.

Without ``--duration-responses`` a validator's next duration comes from the fitted continuation table and does not read
the reward rule, so these runs show what each formula costs and keeps with the duration mix held as the record had it.
With it (E036, H74), the base model draws a renewing or returning node's next duration from the duration transition
fitted on its own moves, tilted by ``duration_response`` (ML28), and records the stake started in each band. Every
formula then runs at each listed strength on the same keys as its twin under the chain's rule at the same response and
strength, and the horizons table adds the started share under 21 days and in 45 to 100 days, each formula's annual
rate on a 14-day stake, and its issuance against ACP-285's line on the same key, response and strength.

Usage, from the client repository root on branch ``prototype/bump-curve-v0``::

    python scripts/bump_curve_runs.py --out DIR --seeds 50 --workers 8

Writes ``daily.parquet``, ``horizons.parquet``, ``cells.json`` and ``receipt.json`` into ``DIR``.
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
import pandas as pd

ORIGIN = date(2025, 11, 18)
TIMESTEPS = 365
HORIZONS = (180, 365)
OUTSIDE_YIELD_PP = 5.0
RESPONSES = {
    "zero": (0.0, 0.0),
    "central": (0.025, 0.04),
    "upper": (0.06, 0.09),
    "mid-sweep": (0.15, 0.15),
    "top-sweep": (0.3, 0.3),
}
"""Renewal and entry responses: zero, the measured central values, the upper ends of their 95% ranges, and two points
of the Milestone 2 sweep's range, which ran both from 0 to 0.3."""
PIN = Path("data/pins/p2-model-v0.8.json")
SWEEP_DESIGN = Path.home() / ".local/share/bcrg/data-engineering/2026-10-13/m2-full-prepared"
DRAWS_SHA256 = "0e4a238778597b44e33b1be31a6179b715d67de0d2dd773ad6faca12331df75d"
STATE = ("active_validators", "active_validator_stake_navax", "supply_navax", "issued_navax", "started_stake_navax",
         "started_stake_d0_21_navax", "started_stake_d45_100_navax")
FLOATS = ("offered_rate_30d", "yield_gap_pp", "started_stake_days_navax")
"""The long table carries the state variables as rows and these three as columns of each row."""
BUMP = {"bump_scale": 1.274, "bump_power": 25.0}


def formulas(equal_floor: float) -> dict[str, dict]:
    return {
        "chain": {"name": "ChainReward"},
        "before": {"name": "DurationCurve", "min_rate": 0.10},
        "acp285": {"name": "DurationCurve"},
        "bump": {"name": "DurationCurve", **BUMP},
        "flat-9.5": {"name": "DurationCurve", "floor": 0.095},
        "flat-equal": {"name": "DurationCurve", "floor": equal_floor},
        "ramp-7.5": {"name": "ACP285Ramp", "activation": "2025-11-18T16:00:00+00:00", "ramp_days": 90, "target_min_rate": 0.075},
    }


def rate_14d(mechanism: dict) -> float | None:
    """A formula's consumption rate on a 14-day stake, before the remaining-supply ratio, for H74's check (c)."""
    if mechanism["name"] != "DurationCurve":
        return None
    from avalanche_research.mechanisms import DurationCurve

    return float(DurationCurve(**{k: v for k, v in mechanism.items() if k != "name"}).rate(14))


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def cells_from(equal_floor: float, strengths: list[float] | None = None) -> dict[str, dict]:
    cells = {}
    for response, (renewal, entry) in RESPONSES.items():
        for strength in strengths if strengths is not None else [None]:
            suffix = "" if strength is None else f"@d{strength:g}"
            for formula, mechanism in formulas(equal_floor).items():
                cells[f"{formula}@{response}{suffix}"] = {
                    "formula": formula, "mechanism": mechanism, "response": response, "renewal_response": renewal,
                    "entry_response": entry, "duration_response": strength,
                    "twin": None if formula == "chain" else f"chain@{response}{suffix}"}
    return cells


_BASE = None  # the base model, inherited by forked workers


def simulate(task: dict) -> pd.DataFrame:
    from avalanche_research.model.engine import run
    from avalanche_research.model.runner import model_settings

    cell = task["cell"]
    values = model_settings({"seed": task["seed"], "mechanism": dict(cell["mechanism"]),
                             "renewal_response": cell["renewal_response"], "entry_response": cell["entry_response"],
                             "outside_yield_pp": OUTSIDE_YIELD_PP, "fitted_outside_yield_pp": task["fitted_yield_pp"]})
    values["draws"] = _BASE.draws.iloc[[task["draw"]]].reset_index(drop=True)
    if cell.get("duration_response") is not None:
        values["duration_response"] = float(cell["duration_response"])
    model = _BASE.with_settings(**values, timesteps=task["timesteps"])
    with contextlib.redirect_stdout(io.StringIO()):
        table = run(model)
    return wide_table(table, task["cell_name"], task["seed"], task["draw"], model.specification_hash())


def wide_table(table: pd.DataFrame, cell_name: str, seed: int, draw: int, specification: str) -> pd.DataFrame:
    present = [name for name in STATE if name in set(table["variable"])]
    wide = table[table["variable"].isin(present)].pivot_table(index="timestep", columns="variable", values="value", aggfunc="first")
    wide.columns.name = None
    for column in FLOATS:
        wide[column] = table.groupby("timestep")[column].first()
    for name in STATE:
        if name not in wide.columns:
            wide[name] = 0
        wide[name] = wide[name].map(int).astype("int64")
    wide = wide.reset_index().rename(columns={"timestep": "day"})
    for name in ("issued_navax", "started_stake_navax", "started_stake_d0_21_navax", "started_stake_d45_100_navax"):
        wide[f"cumulative_{name}"] = wide[name].cumsum().astype("int64")
    wide["cumulative_started_stake_days_navax"] = wide["started_stake_days_navax"].fillna(0.0).cumsum()
    wide.insert(0, "cell", cell_name)
    wide.insert(1, "seed", seed)
    wide.insert(2, "draw", draw)
    wide["specification"] = specification
    return wide


def horizons_table(daily: pd.DataFrame, cells: dict, horizons: list[int]) -> pd.DataFrame:
    """One row per cell, key and horizon: the run's values at the horizon beside its twin's on the same key."""
    at = daily[daily["day"].isin(horizons)].copy().rename(columns={"day": "horizon_days"})
    at["started_weighted_days"] = at["cumulative_started_stake_days_navax"] / at["cumulative_started_stake_navax"]
    means = daily.groupby(["cell", "draw"])["offered_rate_30d"].mean().rename("mean_offered_rate_30d")
    at = at.merge(means, left_on=["cell", "draw"], right_index=True, how="left")
    columns = ["active_validators", "active_validator_stake_navax", "cumulative_issued_navax", "started_weighted_days", "mean_offered_rate_30d"]
    at["twin"] = at["cell"].map(lambda c: cells[c]["twin"])
    twins = at[at["twin"].isna()][["cell", "draw", "horizon_days", *columns]].rename(columns={c: f"twin_{c}" for c in columns} | {"cell": "twin"})
    out = at.merge(twins, on=["twin", "draw", "horizon_days"], how="left")
    for key in ("formula", "response", "renewal_response", "entry_response", "duration_response"):
        out[key] = out["cell"].map(lambda c: cells[c].get(key))
    for band in ("d0_21", "d45_100"):
        out[f"started_share_{band}"] = out[f"cumulative_started_stake_{band}_navax"] / out["cumulative_started_stake_navax"]
    # Each formula against ACP-285's line on the same key, response and strength.
    acp = out[out["formula"] == "acp285"][["draw", "horizon_days", "response", "duration_response", "cumulative_issued_navax"]]
    acp = acp.rename(columns={"cumulative_issued_navax": "acp285_cumulative_issued_navax"})
    out = out.merge(acp, on=["draw", "horizon_days", "response", "duration_response"], how="left")
    out["issuance_vs_acp285"] = out["cumulative_issued_navax"] / out["acp285_cumulative_issued_navax"] - 1
    out["issuance_saved"] = 1 - out["cumulative_issued_navax"] / out["twin_cumulative_issued_navax"]
    out["validator_stake_kept"] = out["active_validator_stake_navax"] / out["twin_active_validator_stake_navax"]
    out["validators_kept"] = out["active_validators"] / out["twin_active_validators"]
    out["started_weighted_days_shift"] = out["started_weighted_days"] - out["twin_started_weighted_days"]
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--equal-floor", type=float, required=True, help="the flat minimum that issues what the bump issues on the observed mix")
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timesteps", type=int, default=TIMESTEPS)
    parser.add_argument("--responses", default="all")
    parser.add_argument("--duration-responses", default=None,
                        help="comma-separated duration-response strengths; draws durations from the fitted transition (E036)")
    args = parser.parse_args(argv)

    from avalanche_research.experiments.sweep import load_draws, pinned_periods
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
    strengths = None if args.duration_responses is None else [float(s) for s in args.duration_responses.split(",")]
    cells = cells_from(args.equal_floor, strengths)
    if args.responses != "all":
        keep = set(args.responses.split(","))
        cells = {name: cell for name, cell in cells.items() if cell["response"] in keep}
    horizons = [h for h in HORIZONS if h <= args.timesteps] or [args.timesteps]

    print(f"building the base model at {ORIGIN} from {periods_run} ...", flush=True)
    variant = VARIANTS["v0.8.0"]
    prepared = variant.prepare(periods, ORIGIN, periods_run, draws=0)
    global _BASE
    _BASE = variant.model(timesteps=args.timesteps, runs=1, seed=0, **prepared.inputs, draws=draws.iloc[keys].reset_index(drop=True))
    if strengths is not None:
        from avalanche_research.model.fitted_lifecycle import decided_by_us, fit_moves

        durations = fit_moves(_BASE.moves, decided_by_us(ORIGIN), f"{periods_run}: moves before {ORIGIN}")
        _BASE = _BASE.with_settings(durations=durations, record_duration_bands=True)
    print(f"base built in {time.time() - clock:.0f}s, specification {_BASE.specification_hash()}", flush=True)

    tasks = [{"cell_name": name, "cell": cell, "seed": k + 1, "draw": k, "fitted_yield_pp": fitted_yield_pp, "timesteps": args.timesteps}
             for name, cell in cells.items() for k in keys]
    t0 = time.time()
    first = simulate(tasks[0])
    one_run_seconds = time.time() - t0
    print(f"{len(tasks)} runs: {len(cells)} cells x {len(keys)} keys on {args.workers} workers, one run {one_run_seconds:.2f}s", flush=True)
    frames = [first]
    done = 1
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context("fork")) as pool:
        futures = [pool.submit(simulate, task) for task in tasks[1:]]
        for future in as_completed(futures):
            frames.append(future.result())
            done += 1
            if done % 100 == 0 or done == len(tasks):
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
    cells_path = args.out / "cells.json"
    cells_path.write_text(json.dumps({"cells": cells, "responses": RESPONSES, "outside_yield_pp": OUTSIDE_YIELD_PP,
                                      "fitted_outside_yield_pp": fitted_yield_pp, "equal_floor": args.equal_floor,
                                      "duration_responses": strengths,
                                      "rate_14d": {f: rate_14d(m) for f, m in formulas(args.equal_floor).items()}}, indent=1) + "\n")
    files = [daily_path, at_path, cells_path]
    receipt = {
        "model": "v0.8.0 lifecycle on branch prototype/bump-curve-v0", "client_head": head, "source_dirty": dirty.splitlines(),
        "origin": ORIGIN.isoformat(), "timesteps": args.timesteps, "horizons": horizons,
        "pin": str(PIN), "pin_sha256": sha256_file(PIN), "staking_periods_run": periods_run,
        "draws_file": str(SWEEP_DESIGN / "draws.parquet"), "draws_sha256": DRAWS_SHA256,
        "keys": keys, "seeds": [k + 1 for k in keys], "cells": list(cells), "runs": len(tasks), "workers": args.workers,
        "responses": RESPONSES, "outside_yield_pp": OUTSIDE_YIELD_PP, "fitted_outside_yield_pp": fitted_yield_pp,
        "equal_floor": args.equal_floor, "base_specification": _BASE.specification_hash(),
        "started": started_at, "finished": datetime.now().astimezone().isoformat(timespec="seconds"),
        "seconds": round(time.time() - clock, 1), "one_run_seconds": round(one_run_seconds, 2),
        "files": {path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size} for path in files},
        "daily_columns": list(daily.columns), "daily_rows": int(len(daily)),
    }
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=1, default=str) + "\n")
    print(json.dumps({k: receipt[k] for k in ("runs", "seconds", "one_run_seconds", "daily_rows", "files")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
