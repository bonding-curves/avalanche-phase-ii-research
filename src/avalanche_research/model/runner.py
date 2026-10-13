"""A streaming sweep runner: design rows run one per task in a bounded process pool, each finished row written to its
own Parquet file, so a 50,000-run sweep never holds more than a few rows in memory and resumes after a stop.

Each worker builds the base model once from a pickle, so a task carries only its row. A row runs the base model with the
row's settings through ``engine.run``, keeps the requested variables for every run and day, and adds the row's identity,
the model's own specification hash and the worker's peak memory. State values stay exact integers: nAVAX amounts fit in
64 bits, and a float would round them.

A design builds each base model in a forked child process, which writes the model's pickle and specification, so the
parent never holds the inputs a model fits and stays small however large they are.

A row's file is written to a temporary name and renamed, so a stopped sweep never leaves a file that resume would trust.
On a second start, rows whose ids already have a file are skipped, so an interrupted and resumed sweep writes the same
files as an uninterrupted one. At most ``in_flight`` rows are submitted and not yet written.
"""

from __future__ import annotations

import contextlib
from datetime import date, datetime
import io
import json
import multiprocessing
import os
import pickle
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

import duckdb
import pandas as pd

from .designs import check_cardinality, check_origins, design_hash, row_id, settings
from .engine import SimulationModel, run

_BASE: SimulationModel | None = None
_VARIABLES: tuple[str, ...] = ()
_REDUCER: Callable[[pd.DataFrame], pd.DataFrame] | None = None
DAILY = ("active_validators", "active_validator_stake_navax", "supply_navax", "issued_navax")


def finished_ids(out: Path) -> set[str]:
    """Row ids that already have a complete file under ``out``."""
    return {path.stem for path in out.glob("*.parquet")}


def _init(base_path: str, variables: tuple[str, ...], reducer) -> None:
    global _BASE, _VARIABLES, _REDUCER
    _BASE = pickle.loads(Path(base_path).read_bytes())
    _VARIABLES = variables
    _REDUCER = reducer


def model_settings(row: Mapping) -> dict:
    """A row's settings as the model takes them: a ``mechanism`` given by class name, or by a mapping with ``name`` and
    keyword settings, becomes that reward mechanism from ``avalanche_research.mechanisms``."""
    from .. import mechanisms
    import param

    values = settings(row)
    spec = values.get("mechanism")
    if spec is not None and not isinstance(spec, mechanisms.RewardMechanism):
        name, options = (spec, {}) if isinstance(spec, str) else (spec["name"], {k: v for k, v in spec.items() if k != "name"})
        cls = getattr(mechanisms, name, None)
        if not (isinstance(cls, type) and issubclass(cls, mechanisms.RewardMechanism)):
            raise ValueError(f"unknown reward mechanism {name!r}")
        for key, value in options.items():
            if key in cls.param and isinstance(cls.param[key], (param.Date, param.CalendarDate)) and isinstance(value, str):
                try:
                    options[key] = date.fromisoformat(value) if isinstance(cls.param[key], param.CalendarDate) or len(value) == 10 else datetime.fromisoformat(value)
                except ValueError as error:
                    raise ValueError(f"mechanism {name} {key} must be an ISO date or timestamp") from error
        values["mechanism"] = cls(**options)
    return values


def _simulate(row: dict) -> pd.DataFrame:
    import resource

    values = model_settings(row)
    if "draw" in values:
        draw = values.pop("draw")
        if type(draw) is not int or draw < 0:
            raise ValueError("row draw must be a nonnegative integer")
        if values.get("runs", _BASE.runs) != 1:
            raise ValueError("a per-row draw requires one trajectory per row")
        if getattr(_BASE, "draws", None) is None or not 0 <= draw < len(_BASE.draws):
            raise ValueError(f"row {row.get('row_id')} asks for draw {draw}, which the base model's draws table does not have")
        values["draws"] = _BASE.draws.iloc[[draw]].reset_index(drop=True)
    model = _BASE.with_settings(**values)
    with contextlib.redirect_stdout(io.StringIO()):  # cadCAD prints a banner per execution
        table = run(model)
    if _REDUCER is not None:
        paths = _REDUCER(table, row)
    else:
        paths = table[table["variable"].isin(_VARIABLES)][["run", "timestep", "variable", "value"]].copy()
        paths["value"] = paths["value"].map(int).astype("int64")
    paths.insert(0, "row_id", row["row_id"])
    paths.insert(1, "design", row["design"])
    paths.insert(2, "index", int(row["index"]))
    for key, value in row.items():
        if key in ("row_id", "design", "index"):
            continue
        if isinstance(value, Mapping):  # a mechanism with settings, kept as its JSON
            value = json.dumps(value, sort_keys=True)
        elif key == "origin":
            value = str(value)
        paths[key] = value
    paths["specification"] = model.specification_hash()
    paths["base_specification"] = _BASE.specification_hash()
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


def _build_child(build_base: Callable[[object, str], SimulationModel], origin: object, model: str, base_path: str) -> None:
    base = build_base(origin, model)
    Path(base_path).write_bytes(pickle.dumps(base))
    built = {"specification_hash": base.specification_hash(),
             "specification": json.loads(json.dumps(base.specification(), default=str))}
    Path(base_path).with_suffix(".json").write_text(json.dumps(built))


def build_apart(build_base: Callable[[object, str], SimulationModel], origin: object, model: str, base_path: Path) -> dict:
    """Build one base model in a forked child process. The child writes the model's pickle to ``base_path`` and its
    specification beside it, and the parent reads only the specification. Returns the pickle's path, the specification
    hash and the specification. A child that fails raises here, with the child's traceback already on stderr."""
    child = multiprocessing.get_context("fork").Process(target=_build_child, args=(build_base, origin, model, str(base_path)))
    child.start()
    child.join()
    if child.exitcode != 0:
        raise RuntimeError(f"building the {model} base model at {origin} failed in its child process (exit {child.exitcode})")
    return {"path": base_path, **json.loads(base_path.with_suffix(".json").read_text())}


def run_sweep(base: SimulationModel, rows: Iterable[Mapping], out: Path, variables: Sequence[str] = DAILY, *, workers: int = 2,
              in_flight: int | None = None, stop_after: int | None = None,
              reducer: Callable[[pd.DataFrame], pd.DataFrame] | None = None) -> dict:
    """Run every row not yet finished under ``out``. Returns counts and timing. ``stop_after`` stops after that many rows
    are written, to test resume. ``reducer``, a module-level function or a picklable callable, turns a row's long table and the row into the rows to keep,
    such as one row of KPIs per run; without it the row keeps the daily paths of ``variables``."""
    with tempfile.TemporaryDirectory() as scratch:
        base_path = Path(scratch) / "base.pickle"
        base_path.write_bytes(pickle.dumps(base))
        return _run_pickled(base_path, base.specification_hash(), rows, out, variables, workers=workers,
                            in_flight=in_flight, stop_after=stop_after, reducer=reducer)


def _run_pickled(base_path: Path, base_hash: str, rows: Iterable[Mapping], out: Path, variables: Sequence[str], *, workers: int,
                 in_flight: int | None, stop_after: int | None, reducer: Callable[[pd.DataFrame], pd.DataFrame] | None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob(".*.parquet.tmp"):
        stale.unlink()
    done = finished_ids(out)
    in_flight = in_flight or 2 * workers
    stats = {"base_specification": base_hash, "skipped": 0, "written": 0, "stopped": False}
    started = time.perf_counter()
    pending: set = set()

    def drain(futures) -> None:
        for future in futures:
            _write(future.result(), out)
            stats["written"] += 1

    with ProcessPoolExecutor(workers, initializer=_init, initargs=(str(base_path), tuple(variables), reducer)) as pool:
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
    import resource

    stats["parent_peak_mib"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    return stats


def run_design(rows: Sequence[Mapping], expected_rows: int, build_base: Callable[[object, str], SimulationModel], out: Path,
               variables: Sequence[str] = DAILY, **options) -> dict:
    """A whole design across origins and models. The design is checked (row count, repeated settings, lockbox origins),
    each base model is built once per origin and model in a child process, and ``design.json`` with every row id and
    the design hash is written before the first row runs. Rows then run group by group into ``out``. The totals carry
    each group's base specification under ``base_specifications``, in group order."""
    rows = [dict(row) for row in rows]
    check_cardinality(rows, expected_rows)
    check_origins(rows)
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        groups.setdefault((str(row.get("origin")), row.get("model")), []).append(row)
    with tempfile.TemporaryDirectory() as scratch:
        bases = {key: build_apart(build_base, group[0].get("origin"), key[1], Path(scratch) / f"base-{number}.pickle")
                 for number, (key, group) in enumerate(groups.items())}
        return _run_groups(groups, bases, rows, out, variables, options)


def _run_groups(groups: dict, bases: dict, rows: list[dict], out: Path, variables: Sequence[str], options: dict) -> dict:
    record = {"rows": len(rows), "groups": [], "row_ids": []}
    for key, group in groups.items():
        base_hash = bases[key]["specification_hash"]
        record["groups"].append({"origin": key[0], "model": key[1], "base_specification": base_hash, "rows": len(group)})
        record["row_ids"] += [row_id(row, base_hash) for row in group]
    record["design_hash"] = design_hash([{"row_id": r} for r in record["row_ids"]], "design")
    out.mkdir(parents=True, exist_ok=True)
    (out / "design.json").write_text(json.dumps(record, indent=1, sort_keys=True, default=str) + "\n")
    totals = {"design_hash": record["design_hash"], "skipped": 0, "written": 0, "groups": len(groups), "seconds": 0.0,
              "base_specifications": [bases[key]["specification"] for key in groups]}
    for key, group in groups.items():
        base = bases[key]
        stats = _run_pickled(base["path"], base["specification_hash"], group, out, variables, workers=options.get("workers", 2),
                             in_flight=options.get("in_flight"), stop_after=options.get("stop_after"), reducer=options.get("reducer"))
        totals["skipped"] += stats["skipped"]
        totals["written"] += stats["written"]
        totals["seconds"] = round(totals["seconds"] + stats["seconds"], 3)
        totals["parent_peak_mib"] = max(totals.get("parent_peak_mib", 0), stats["parent_peak_mib"])
        if stats["stopped"]:
            totals["stopped"] = True
            break
    return totals


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


def available_mib(meminfo: Path = Path("/proc/meminfo")) -> float:
    """Memory available now, in MiB, as the kernel estimates it (``MemAvailable``). Read at launch, since free memory on
    a shared machine moves with other jobs."""
    for line in meminfo.read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024
    raise OSError(f"no MemAvailable in {meminfo}")


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
