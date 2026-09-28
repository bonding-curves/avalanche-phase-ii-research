"""Run a sweep design in batches across processes, one Parquet file of per-trajectory KPI rows per batch.

A run directory holds ``batch-NNNNN.parquet`` files, ``manifest.json`` (design, seeds, code revision, ranges,
scenarios, counts, timing, failures), and ``receipt.json`` (SHA-256, size, and rows of every file) once every batch
is written. Re-running the same design into the same directory skips batches already written.
"""

from __future__ import annotations

import argparse
import importlib
import json
import multiprocessing
import os
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from ..catalog import ROOT, canonical_bytes, now, sha256
from . import design as design_module
from .kpis import kpis

ENGINES = {
    "stub": ("avalanche_research.psuu.stub", "avalanche_research.psuu.stub", "avalanche_research.psuu.stub"),
    "sim": ("avalanche_research.sim.engine", "avalanche_research.sim.params", "avalanche_research.sim.scenario"),
}
PARAM_FIELDS = ("min_consumption_rate", "max_consumption_rate", "min_stake_days", "max_stake_days",
                "min_delegation_fee", "mechanism", "mechanism_args")


class SweepError(RuntimeError):
    """A sweep could not start or finished with failed batches."""


def load_engine(name: str) -> tuple[Any, type, type]:
    """(run, Params, Scenario) for an engine name in ``ENGINES``."""
    try:
        engine, params, scenario = (importlib.import_module(module) for module in ENGINES[name])
    except KeyError as error:
        raise SweepError(f"unknown engine: {name}; known: {sorted(ENGINES)}") from error
    return engine.run, params.Params, scenario.Scenario


def default_run_dir(run_id: str) -> Path:
    return ROOT / "data" / "runs" / run_id


def batch_path(out_dir: Path, index: int) -> Path:
    return out_dir / f"batch-{index:05d}.parquet"


def batches(n_trajectories: int, batch_size: int) -> list[tuple[int, int, int]]:
    return [(index, start, min(start + batch_size, n_trajectories))
            for index, start in enumerate(range(0, n_trajectories, batch_size))]


def code_revision() -> dict[str, Any]:
    """HEAD and whether the package source differs from it. Read-only git calls."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()

    try:
        return {"commit": git("rev-parse", "HEAD"), "source_changed": bool(git("status", "--porcelain", "--", "src"))}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "source_changed": None}


_WORKER: dict[str, Any] = {}


def _init(payload: dict[str, Any]) -> None:
    _WORKER.clear()
    _WORKER.update(payload)
    run, params_type, scenario_type = load_engine(payload["engine"])
    if payload["engine"] == "sim":
        from .mechanisms import install_into_sim

        install_into_sim()
    behaviour = None
    if payload["behaviour_path"] is not None:
        from ..sim.behaviour import BehaviourParams

        behaviour = BehaviourParams.from_json(payload["behaviour_path"])
    _WORKER.update(run=run, params_type=params_type, scenario_type=scenario_type, behaviour=behaviour)


def _trajectory(trajectory_id: int) -> dict[str, Any]:
    design: design_module.Design = _WORKER["design"]
    row_index, scenario_index, seed = design.trajectory(trajectory_id)
    row = design.parameters.iloc[row_index]
    spec = design.scenarios[scenario_index]
    fields = {name: row[name] for name in PARAM_FIELDS}
    fields["min_stake_days"], fields["max_stake_days"] = int(fields["min_stake_days"]), int(fields["max_stake_days"])
    fields["mechanism_args"] = tuple(tuple(item) if isinstance(item, list) else item for item in fields["mechanism_args"])
    fields.update(_WORKER["fixed_params"])
    if _WORKER["behaviour"] is not None:
        fields["behaviour"] = _WORKER["behaviour"]
    params = _WORKER["params_type"](**fields)
    scenario = _WORKER["scenario_type"](
        name=spec.name,
        price_usd=design_module.price_path(spec, design.calibration, seed, design.days, design.design_seed),
        external_yield=design_module.yield_path(spec, design.days),
        start_date=design.start_date,
    )
    started = time.perf_counter()
    frame = _WORKER["run"](params, scenario, seed=seed, days=design.days, initial_state=_WORKER["initial_state"])
    if len(frame) != design.days:
        raise SweepError(f"trajectory {trajectory_id}: engine returned {len(frame)} of {design.days} days")
    checked = _invariants(frame, params)
    return {
        "trajectory_id": trajectory_id, "param_id": int(row["param_id"]), "scenario_id": spec.scenario_id,
        "scenario_name": spec.name, "scenario_kind": spec.kind, "market": spec.market, "yield_start": spec.yield_start,
        "seed": seed,
        **{name: fields[name] for name in PARAM_FIELDS if name != "mechanism_args"},
        "mechanism_args": json.dumps(fields["mechanism_args"]),
        **kpis(frame),
        **checked,
        "engine_seconds": time.perf_counter() - started,
    }


def _invariants(frame: pd.DataFrame, params: Any) -> dict[str, Any]:
    """Days failing each accounting invariant (``sim.invariants.check_frame``), or nothing for an engine whose
    frame lacks the diagnostic columns the check needs (the stub)."""
    if not {"supply_counter_avax", "rewards_due_avax", "delegation_capacity_avax"} <= set(frame.columns):
        return {}
    from ..sim.invariants import check_frame

    result = check_frame(frame, params.supply_cap_avax)
    return {**{f"invariant_{name}_days": count for name, count in result["failures"].items()}, "invariants_hold": result["holds"]}


def _write_parquet(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(".parquet.tmp")
    connection = duckdb.connect()
    try:
        connection.register("batch", frame)
        target = str(temporary).replace("'", "''")
        connection.execute(f"COPY batch TO '{target}' (FORMAT parquet)")
    finally:
        connection.close()
    os.replace(temporary, path)


def _run_batch(task: tuple[int, int, int]) -> dict[str, Any]:
    index, start, stop = task
    started = time.perf_counter()
    try:
        rows = [_trajectory(trajectory_id) for trajectory_id in range(start, stop)]
        _write_parquet(pd.DataFrame(rows), batch_path(Path(_WORKER["out_dir"]), index))
    except Exception as error:  # noqa: BLE001  a failed batch is recorded and retried on resume
        return {"batch": index, "rows": 0, "seconds": time.perf_counter() - started, "error": f"{type(error).__name__}: {error}"}
    return {"batch": index, "rows": stop - start, "seconds": time.perf_counter() - started, "error": None}


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_bytes(canonical_bytes(value))
    os.replace(temporary, path)


def write_receipt(out_dir: Path, run_id: str) -> dict[str, Any]:
    files = []
    connection = duckdb.connect()
    try:
        for path in sorted(out_dir.glob("batch-*.parquet")):
            rows = connection.execute("SELECT count(*) FROM read_parquet(?)", [str(path)]).fetchone()[0]
            data = path.read_bytes()
            files.append({"path": path.name, "sha256": sha256(data), "bytes": len(data), "rows": rows})
    finally:
        connection.close()
    manifest = (out_dir / "manifest.json").read_bytes()
    receipt = {
        "run_id": run_id, "written_at": now(), "manifest_sha256": sha256(manifest),
        "rows": sum(item["rows"] for item in files), "files": files,
    }
    _write_json(out_dir / "receipt.json", receipt)
    return receipt


def run_sweep(
    design: design_module.Design,
    out_dir: Path,
    engine: str = "sim",
    workers: int = 30,
    batch_size: int = 100,
    initial_state: Any = None,
    behaviour_path: Path | None = None,
    fixed_params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run every pending batch and return the manifest. Raises ``SweepError`` if any batch failed."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    digest = design.digest()
    if manifest_path.is_file():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous.get("design_digest") != digest or previous.get("engine") != engine or previous.get("batch_size") != batch_size:
            raise SweepError(f"{out_dir} holds a different design, engine, or batch size; use a new run directory")
    fixed = dict(fixed_params or {})
    behaviour_sha = sha256(Path(behaviour_path).read_bytes()) if behaviour_path is not None else None
    all_batches = batches(design.n_trajectories, batch_size)
    pending = [task for task in all_batches if not batch_path(out_dir, task[0]).is_file()]
    manifest: dict[str, Any] = {
        "run_id": out_dir.name, "status": "running", "engine": engine, "design_digest": digest,
        "code_revision": code_revision(), "batch_size": batch_size, "workers": workers,
        "behaviour": {"path": Path(behaviour_path).name, "sha256": behaviour_sha} if behaviour_path is not None else None,
        "fixed_params": fixed, "initial_state": "observed" if initial_state is not None else "engine default (synthetic)",
        "design": design.describe(), "batches": {"total": len(all_batches), "skipped_existing": len(all_batches) - len(pending)},
        "started_at": now(),
    }
    _write_json(manifest_path, manifest)
    payload = {"design": design, "engine": engine, "initial_state": initial_state, "out_dir": str(out_dir),
               "behaviour_path": None if behaviour_path is None else str(behaviour_path), "fixed_params": fixed}
    started = time.perf_counter()
    if workers <= 1:
        _init(payload)
        results = [_run_batch(task) for task in pending]
    else:
        with multiprocessing.get_context("spawn").Pool(workers, initializer=_init, initargs=(payload,)) as pool:
            results = list(pool.imap_unordered(_run_batch, pending))
    failures = sorted((item for item in results if item["error"]), key=lambda item: item["batch"])
    manifest.update(
        status="failed" if failures else "complete",
        finished_at=now(),
        wall_seconds=time.perf_counter() - started,
        batch_seconds=sum(item["seconds"] for item in results),
        batches={**manifest["batches"], "run": len(results), "failed": len(failures)},
        trajectories_written=sum(item["rows"] for item in results),
        failures=failures,
    )
    _write_json(manifest_path, manifest)
    if failures:
        raise SweepError(f"{len(failures)} of {len(pending)} batches failed; first: {failures[0]['error']}")
    manifest["receipt"] = write_receipt(out_dir, out_dir.name)
    return manifest


def load_results(out_dir: Path) -> pd.DataFrame:
    """Every batch's KPI rows, ordered by trajectory id."""
    pattern = str(Path(out_dir) / "batch-*.parquet").replace("'", "''")
    connection = duckdb.connect()
    try:
        return connection.execute(f"SELECT * FROM read_parquet('{pattern}') ORDER BY trajectory_id").df()
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the parameter sweep into data/runs/<run id>/.")
    parser.add_argument("run_id")
    parser.add_argument("--engine", default="sim", choices=sorted(ENGINES))
    parser.add_argument("--workers", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--parameter-sets", type=int, default=design_module.N_PARAMETER_SETS)
    parser.add_argument("--seeds", type=int, default=len(design_module.SEEDS))
    parser.add_argument("--behaviour", type=Path, default=None)
    parser.add_argument("--synthetic-start", action="store_true", help="use the engine's synthetic start instead of the observed state")
    args = parser.parse_args(argv)
    from .. import datasets

    con = datasets.connect()
    con.execute("SET memory_limit='5GB'; SET threads=6;")
    calibration = design_module.calibrate_prices(con)
    design = design_module.build_design(calibration, args.parameter_sets, tuple(range(args.seeds)))
    initial_state = None
    if not args.synthetic_start and args.engine == "sim":
        from ..sim.state import observed_state

        initial_state = observed_state(con, design.start_date)
    con.close()
    manifest = run_sweep(design, default_run_dir(args.run_id), args.engine, args.workers, args.batch_size,
                         initial_state, args.behaviour)
    print(json.dumps({key: manifest[key] for key in ("run_id", "status", "trajectories_written", "wall_seconds")}))


if __name__ == "__main__":
    main()
