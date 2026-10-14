#!/usr/bin/env python3
"""The v0.8.1 candidate at the 19 development origins: delegated stake, open delegations and BENQI's delegated stake at
30, 90 and 180 days against the record, with the delegations the containment rule left unplaced.

    uv run --group model python scripts/model_v081_origins.py OUT_DIR --pin PIN [--runs N] [--workers W] [--days D] [--origins NAME ...]

The origins are the five upgrades from Banff to Fortuna and the quarter starts from 2022-07-01 to 2025-10-01, as
``scripts/model_development_scores.py`` lists them. At each origin the candidate is prepared once from the two runs the
pin ``PIN`` names and verifies: the staking periods and the seamed delegator stakes (the funding addresses that set
BENQI's delegations apart). No newer build is read in their place. One parameter draw per run. Run ``r`` is batch ``r`` of one
run under base seed ``r``, reading draw ``r``, so every run has its own specification hash, recorded with its
construction in ``specifications.csv`` and ``construction.json``.

A horizon is scored only when its day falls before the held-back period, which starts 2025-11-19 16:00 UTC: the record
at a later day is not read. The record is the staking periods' open delegations at 23:59:59 UTC of the horizon day, as
the replay counts them, with BENQI's by its funding address and evidence date. Beside the candidate, ``no new
delegations`` is the same build with no flow, so the open delegations only run off: the comparison the plan asks for
against v0.8.0 with no delegations. ``origins.csv`` holds one row per origin and horizon, ``parameters.csv`` the flow
and BENQI share each origin read, and ``unplaced.csv`` the unplaced count per origin and run over the whole horizon.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_development_scores import HORIZONS, QUARTERS, UPGRADES

from avalanche_research.datasets.derived import delegation_inputs as di
from avalanche_research.experiments.v081_inputs import candidate_tables, pinned_inputs
from avalanche_research.model.delegation_blocks import DelegationFlow
from avalanche_research.model.engine import run
from avalanche_research.model.replay import LOCKBOX_FIRST_DAY
from avalanche_research.model.variants import VARIANTS, Prepared

CANDIDATE = "v0.8.1 candidate"
VARIABLES = ("active_delegated_stake_navax", "active_delegations", "benqi_delegated_stake_navax")
DRAW_SEED = 0
RECORD_SQL = """
SELECT count(*)::BIGINT AS active_delegations, coalesce(sum(p.stake_navax), 0)::BIGINT AS active_delegated_stake_navax,
       coalesce(sum(p.stake_navax) FILTER (WHERE f.delegator_address = ? AND p.accepted_at >= ?::TIMESTAMP), 0)::BIGINT AS benqi_delegated_stake_navax
FROM read_parquet(?) p LEFT JOIN read_parquet(?) f USING (transaction_hash)
WHERE p.role = 'delegator' AND p.stake_navax IS NOT NULL AND p.start_time <= ?::TIMESTAMP
  AND greatest(p.end_time, coalesce(p.last_cycle_end_time, p.end_time)) > ?::TIMESTAMP
"""


def origins() -> dict[str, date]:
    return {**UPGRADES, **QUARTERS}


def scored(origin: date, horizon: int) -> bool:
    """Whether the horizon day lies before the held-back period."""
    return origin + timedelta(days=horizon) <= LOCKBOX_FIRST_DAY - timedelta(days=1)


def record_at(periods: str, delegators: str, day: date) -> dict[str, int]:
    """The open delegations at the last second of ``day``, never read at or after the held-back period's first day."""
    if day >= LOCKBOX_FIRST_DAY:
        raise ValueError(f"{day} is in the held-back period, which is not read")
    instant = pd.Timestamp(day).as_unit("us") + pd.Timedelta(hours=23, minutes=59, seconds=59)
    row = duckdb.execute(RECORD_SQL, [di.BENQI_FUNDING, di.BENQI_EVIDENCE, periods, delegators, instant, instant]).df().iloc[0]
    return {name: int(row[name]) for name in VARIABLES}


def at_horizons(table: pd.DataFrame) -> pd.DataFrame:
    """Each run's value of the three variables at each horizon, with the unplaced delegations summed to that horizon."""
    wide = table.pivot_table(index=["run", "timestep"], columns="variable", values="value", aggfunc="first")
    rows = []
    for run_id, path in wide.groupby(level="run"):
        path = path.droplevel("run")
        for horizon in HORIZONS:
            if horizon in path.index:
                rows.append({"run": run_id, "horizon_days": horizon, **{name: int(path.loc[horizon, name]) for name in VARIABLES},
                             "unplaced": int(path.loc[1:horizon, "unplaced_delegations"].sum()),
                             "delegator_issued_navax": int(path.loc[1:horizon, "delegator_issued_navax"].sum())})
    return pd.DataFrame(rows)


def origin_task(task: tuple[str, date, str, str, str, int, int]) -> dict:
    name, origin, run_name, periods, delegators, runs, days = task
    tables = candidate_tables(periods, delegators, origin)
    variant = VARIANTS[CANDIDATE]
    prepared = variant.prepare(periods, origin, run_name, draws=runs, draw_seed=DRAW_SEED, delegations=tables)
    flow, benqi = prepared.inputs["delegation_flow"], prepared.inputs["benqi_allocation"]
    parameters = {"origin": name, "origin_date": origin.isoformat(), "flow_mean_per_day": flow.mean_per_day, "flow_benqi_share": flow.benqi_share,
                  "benqi_new_share": benqi.new_share, "open_delegations": len(tables["open"]), "prior_use_periods": len(prepared.inputs["benqi_validators"]),
                  "terms": len(tables["terms"]), "named_operators": len(prepared.inputs["named_operators"]), "tau": prepared.tau, "tau_source": prepared.tau_source}
    parts, specifications = [], []
    for seed in range(runs):
        simulation = variant.simulation(prepared, seed=seed, timesteps=days, runs=1, draws=prepared.draws.iloc[[seed]].reset_index(drop=True))
        specifications.append({"origin": name, "model": CANDIDATE, "batch_seed": seed, "draw": seed, "specification": simulation.specification_hash()})
        table = at_horizons(run(simulation))
        parts.append(table.assign(run=seed, origin=name))
    still = Prepared({**prepared.inputs, "delegation_flow": DelegationFlow()}, prepared.draws, prepared.tau, prepared.tau_source)
    quiet = at_horizons(run(variant.simulation(still, seed=0, timesteps=days, runs=1, draws=prepared.draws.iloc[[0]].reset_index(drop=True))))
    rows = []
    for horizon in HORIZONS:
        if horizon > days:
            continue
        everyone = pd.concat(parts)
        mine = everyone[everyone["horizon_days"] == horizon]
        no_new = quiet[quiet["horizon_days"] == horizon].iloc[0]
        row = {"origin": name, "origin_date": origin.isoformat(), "horizon_days": horizon, "horizon_date": (origin + timedelta(days=horizon)).isoformat(),
               "scored": scored(origin, horizon), "runs": runs,
               "unplaced_mean": float(mine["unplaced"].mean()), "unplaced_max": int(mine["unplaced"].max()),
               "attempted_mean": float(flow.mean_per_day * horizon), "delegator_issued_navax_mean": float(mine["delegator_issued_navax"].mean())}
        for name_ in VARIABLES:
            row |= {f"{name_}_mean": float(mine[name_].mean()), f"{name_}_median": float(mine[name_].median()),
                    f"{name_}_min": int(mine[name_].min()), f"{name_}_max": int(mine[name_].max()), f"{name_}_no_new": int(no_new[name_])}
        if row["scored"]:
            actual = record_at(periods, delegators, origin + timedelta(days=horizon))
            for name_ in VARIABLES:
                row[f"{name_}_record"] = actual[name_]
                row[f"{name_}_error"] = (row[f"{name_}_mean"] - actual[name_]) / actual[name_] if actual[name_] else float("nan")
                row[f"{name_}_no_new_error"] = (row[f"{name_}_no_new"] - actual[name_]) / actual[name_] if actual[name_] else float("nan")
        rows.append(row)
    print(f"{name}: done", flush=True)
    return {"rows": rows, "parameters": parameters, "specifications": specifications,
            "unplaced": pd.concat(parts)[["origin", "run", "horizon_days", "unplaced"]].to_dict("records")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--pin", type=Path, required=True, help="the pin file naming the staking periods and seamed delegator stakes to read")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--days", type=int, default=max(HORIZONS))
    parser.add_argument("--origins", nargs="*", default=None)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    inputs = pinned_inputs(args.pin)
    pinned, periods, delegators_path = inputs.periods_run, str(inputs.periods), inputs.delegators
    chosen = {name: day for name, day in origins().items() if not args.origins or name in args.origins}
    tasks = [(name, day, pinned, periods, str(delegators_path), args.runs, args.days) for name, day in chosen.items()]
    with ProcessPoolExecutor(args.workers) as pool:
        results = list(pool.map(origin_task, tasks))
    pd.DataFrame([row for r in results for row in r["rows"]]).to_csv(args.out / "origins.csv", index=False)
    pd.DataFrame([r["parameters"] for r in results]).to_csv(args.out / "parameters.csv", index=False)
    pd.DataFrame([s for r in results for s in r["specifications"]]).to_csv(args.out / "specifications.csv", index=False)
    pd.DataFrame([u for r in results for u in r["unplaced"]]).to_csv(args.out / "unplaced.csv", index=False)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip()
    construction = {
        "command": "uv run --group model python scripts/model_v081_origins.py " + " ".join(sys.argv[1:]),
        "code_commit": commit,
        "python": platform.python_version(),
        "pin": str(args.pin), "pin_sha256": hashlib.sha256(args.pin.read_bytes()).hexdigest(),
        "staking_periods_run": pinned, "staking_periods_sha256": inputs.periods_sha256,
        "delegator_stakes_run": inputs.delegators_run, "delegator_stakes_sha256": inputs.delegators_sha256,
        "specification_hash": {
            "object": f"VARIANTS[{CANDIDATE!r}].simulation(prepared, seed=r, timesteps={args.days}, runs=1, draws=prepared.draws.iloc[[r]].reset_index(drop=True))",
            "prepared": f"VARIANTS[{CANDIDATE!r}].prepare(periods, origin, {pinned!r}, draws={args.runs}, draw_seed={DRAW_SEED}, delegations=tables)",
            "tables": "candidate_tables(periods, delegators, origin): delegation_inputs.build with delegation_terms and benqi_choices, BENQI by its funding address from its evidence date; both files from the pin",
            "method": "SimulationModel.specification_hash: the first 16 hex digits of the SHA-256 of json.dumps(model.specification(), sort_keys=True, default=str)",
            "specification": "the model class, every setting not at an omitted default, and the SHA-256 digest of every input table (engine.SimulationModel.specification)",
        },
        "held_back_from": "2025-11-19 16:00 UTC; a horizon on or after 2025-11-19 is not scored and its record is not read",
    }
    (args.out / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
