"""A streaming sweep runner: design rows run one per task in a bounded process pool, each finished row written to its
own Parquet file, so a 50,000-run sweep never holds more than a few rows in memory and resumes after a stop.

Each worker builds the base model once from a pickle, so a task carries only its row. A row runs the base model with the
row's settings through ``engine.run``, keeps the requested variables for every run and day, and adds the row's identity,
the model's own specification hash and the worker's peak memory. State values stay exact integers: nAVAX amounts fit in
64 bits, and a float would round them.

A row's file is written to a temporary name and renamed, so a stopped sweep never leaves a file that resume would trust.
On a second start, rows whose ids already have a file are skipped, so an interrupted and resumed sweep writes the same
files as an uninterrupted one. At most ``in_flight`` rows are submitted and not yet written.
"""

from __future__ import annotations

import contextlib
import io
import os
import pickle
import tempfile
import time
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

import duckdb
import pandas as pd

from .designs import row_id, settings
from .engine import SimulationModel, run

_BASE: SimulationModel | None = None
_VARIABLES: tuple[str, ...] = ()


def finished_ids(out: Path) -> set[str]:
    """Row ids that already have a complete file under ``out``."""
    return {path.stem for path in out.glob("*.parquet")}


def _init(base_path: str, variables: tuple[str, ...]) -> None:
    global _BASE, _VARIABLES
    _BASE = pickle.loads(Path(base_path).read_bytes())
    _VARIABLES = variables


def _simulate(row: dict) -> pd.DataFrame:
    import resource

    model = _BASE.with_settings(**settings(row))
    with contextlib.redirect_stdout(io.StringIO()):  # cadCAD prints a banner per execution
        table = run(model)
    paths = table[table["variable"].isin(_VARIABLES)][["run", "timestep", "variable", "value"]].copy()
    paths["value"] = paths["value"].map(int).astype("int64")
    paths.insert(0, "row_id", row["row_id"])
    paths.insert(1, "design", row["design"])
    paths.insert(2, "index", int(row["index"]))
    for key, value in settings(row).items():
        paths[key] = value
    paths["specification"] = model.specification_hash()
    paths["worker_peak_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    return paths


def _write(frame: pd.DataFrame, out: Path) -> Path:
    final = out / f"{frame['row_id'].iat[0]}.parquet"
    tmp = out / f".{final.stem}.parquet.tmp"
    connection = duckdb.connect()
    try:
        connection.register("frame", frame)
        connection.execute(f"COPY frame TO '{tmp}' (FORMAT parquet)")
    finally:
        connection.close()
    os.replace(tmp, final)
    return final


def run_sweep(base: SimulationModel, rows: Iterable[Mapping], out: Path, variables: Sequence[str], *, workers: int = 2,
              in_flight: int | None = None, stop_after: int | None = None) -> dict:
    """Run every row not yet finished under ``out``. Returns counts and timing. ``stop_after`` stops after that many rows
    are written, to test resume."""
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob(".*.parquet.tmp"):
        stale.unlink()
    base_hash = base.specification_hash()
    done = finished_ids(out)
    in_flight = in_flight or 2 * workers
    stats = {"base_specification": base_hash, "skipped": 0, "written": 0, "stopped": False}
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as scratch:
        base_path = Path(scratch) / "base.pickle"
        base_path.write_bytes(pickle.dumps(base))
        pending: set = set()

        def drain(futures) -> None:
            for future in futures:
                _write(future.result(), out)
                stats["written"] += 1

        with ProcessPoolExecutor(workers, initializer=_init, initargs=(str(base_path), tuple(variables))) as pool:
            for row in rows:
                row = {**row, "row_id": row_id(row, base_hash)}
                if row["row_id"] in done:
                    stats["skipped"] += 1
                    continue
                while len(pending) >= in_flight:
                    finished, pending = wait(pending, return_when=FIRST_COMPLETED)
                    drain(finished)
                if stop_after is not None and stats["written"] >= stop_after:
                    stats["stopped"] = True
                    break
                pending.add(pool.submit(_simulate, row))
            if stats["stopped"]:
                for future in pending:
                    future.cancel()
            else:
                drain(pending)
    stats["seconds"] = round(time.perf_counter() - started, 3)
    return stats


def worker_memory(pilot: pd.DataFrame, runs_per_row: Sequence[int]) -> tuple[float, float]:
    """A worker's memory as ``base + per_run * runs``, fitted by least squares to a pilot's peak memory per row.

    ``pilot`` holds ``row_id`` and ``worker_peak_mib`` from ``read_sweep``; ``runs_per_row`` gives each row's run count in
    the same row order as ``pilot.row_id.unique()``. RG1 measured 409 MiB at 5 runs and 2.1 GB at 40 on v0.8."""
    import numpy as np

    peaks = pilot.groupby("row_id", sort=False)["worker_peak_mib"].max().to_numpy(dtype=float)
    runs = np.asarray(runs_per_row, dtype=float)
    if len(set(runs)) < 2:
        raise ValueError("a pilot needs rows with at least two run counts to separate the base from the per-run memory")
    per_run, base = np.polyfit(runs, peaks, 1)
    return float(base), float(per_run)


def size_pool(available_mib: float, base_mib: float, per_run_mib: float, runs_per_row: int, reserve_mib: float = 2048,
              cpus: int | None = None) -> dict:
    """Workers that fit in ``available_mib`` after ``reserve_mib`` for the parent and the system, at most one per CPU."""
    cpus = cpus or os.cpu_count() or 1
    per_worker = base_mib + per_run_mib * runs_per_row
    workers = int(max(0.0, available_mib - reserve_mib) // per_worker)
    if workers < 1:
        raise ValueError(f"one worker needs {per_worker:,.0f} MiB at {runs_per_row} runs per row; {available_mib - reserve_mib:,.0f} MiB is free")
    workers = min(workers, cpus)
    return {"workers": workers, "per_worker_mib": round(per_worker, 1), "projected_mib": round(workers * per_worker + reserve_mib, 1)}


def read_sweep(out: Path) -> pd.DataFrame:
    """Every finished row's paths, ordered by design index, run, timestep and variable."""
    return duckdb.execute(f"SELECT * FROM read_parquet('{out}/*.parquet') ORDER BY index, run, timestep, variable").df()
