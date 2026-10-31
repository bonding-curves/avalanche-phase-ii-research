"""Authenticate inputs and replay the report's two central cells on archived model source.

    uv run --frozen --group model python scripts/reproduce_report.py fetch --output INPUTS
    uv run --frozen --group model python scripts/reproduce_report.py run --inputs INPUTS --output RESULT
    uv run --frozen --group model python scripts/reproduce_report.py check --inputs INPUTS --output RESULT

Fetch accepts --archive FILE for an already downloaded release asset. Run requires
a new output directory. --pilot checks key zero before the complete 50-pair run.
Check authenticates and recomputes saved results without fitting or simulating.
The original execution did not bind its driver bytes. This replay preserves that
limit and authenticates its own producing code, frozen inputs and archived model.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import os
import platform
import signal
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path, PurePosixPath

PROJECT = Path(__file__).resolve().parents[1]
EXAMPLE = PROJECT / "examples/report-reproduction"
MODEL_SOURCE = "b18a4a2f0ad2d995a6ab30c8438ff19f446dcfdc"
INPUT_MANIFEST_SHA256 = "740e60cf824870dc6be3bf8b0410f0011e0cc3430909938f98a0f96bc50db7e3"
CORE = ("active_validators", "validator_stake_navax", "supply_counter_navax", "issued_day_navax",
        "cumulative_issued_navax")
DAILY = ("cell", "key", "seed", "draw", "day", "date", *CORE, "realized_supply_navax")
METRICS = ("issuance_saved", "validator_stake_kept", "active_validators_kept")
OUTPUTS = {"daily.csv", "paired.csv", "comparison.csv", "configuration.json", "execution.json"}
RELEASE = {"repository": "AVL-Foundation/ext-bcrg-validator-research",
           "tag": "central-case-reproduction-2026-10-30", "asset": "central-case-inputs.zip"}
_BASE = None
_DESIGN = None


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def read_json(path):
    def reject(value):
        raise ValueError(f"nonfinite JSON constant: {value}")
    return json.loads(path.read_bytes(), parse_constant=reject)


def record(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"bytes": path.stat().st_size, "sha256": digest}


def relative_path(value):
    require(isinstance(value, str) and value and "\\" not in value and ":" not in value and "\x00" not in value,
            "unsafe input path")
    require(not PurePosixPath(value).is_absolute() and all(p not in ("", ".", "..") for p in value.split("/")),
            "unsafe input path")
    return value


def contract():
    require(record(EXAMPLE / "input-manifest.json")["sha256"] == INPUT_MANIFEST_SHA256,
            "frozen input contract differs")
    value = read_json(EXAMPLE / "input-manifest.json")
    require(value["schema"] == "report-reproduction-inputs/v1" and value["release"] == RELEASE,
            "input release identity differs")
    require(value["model_source_commit"] == MODEL_SOURCE, "archived model identity differs")
    require(bool(value["members"]), "empty input inventory")
    for name, item in value["members"].items():
        relative_path(name)
        require(type(item["bytes"]) is int and item["bytes"] >= 0
                and len(item["sha256"]) == 64, "invalid input inventory record")
    return value


def authenticate_inputs(inputs):
    value = contract()
    require(inputs.is_dir() and not inputs.is_symlink(), "missing or symlinked input directory")
    found = set()
    for path in inputs.rglob("*"):
        require(not path.is_symlink(), "symlinked input dependency")
        if path.is_file():
            name = path.relative_to(inputs).as_posix()
            require(name in value["members"], f"unexpected input member: {name}")
            require(record(path) == value["members"][name], f"changed input member: {name}")
            found.add(name)
    require(found == set(value["members"]), "missing input dependency")
    return value


def extract_archive(archive, output):
    value = contract()
    require(archive.is_file() and not archive.is_symlink(), "missing or symlinked input archive")
    require(record(archive) == value["archive"], "release archive hash or byte count differs")
    require(not output.exists() and not output.is_symlink(), "input destination must be new")
    with zipfile.ZipFile(archive) as zipped:
        members = zipped.infolist()
        names = [relative_path(info.filename) for info in members]
        require(len(names) == len(set(names)) and set(names) == set(value["members"]),
                "archive member inventory differs")
        for info in members:
            kind = stat.S_IFMT(info.external_attr >> 16)
            require(not info.is_dir() and kind in (0, stat.S_IFREG), "archive contains a nonregular member")
            require(info.file_size == value["members"][info.filename]["bytes"], "archive member size differs")
        output.mkdir(parents=True)
        for info in members:
            target = output / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(info) as source, target.open("xb") as destination:
                while body := source.read(1024 * 1024):
                    destination.write(body)
    authenticate_inputs(output)


def fetch_inputs(output, archive=None):
    require(not output.exists() and not output.is_symlink(), "input destination must be new")
    if archive is not None:
        extract_archive(archive, output)
        return
    release = contract()["release"]
    with tempfile.TemporaryDirectory(prefix="report-release-") as temporary:
        subprocess.run(["gh", "release", "download", release["tag"], "--repo", release["repository"],
                        "--pattern", release["asset"], "--dir", temporary], check=True, timeout=600)
        extract_archive(Path(temporary) / release["asset"], output)


def csv_bytes(rows):
    require(bool(rows), "cannot write an empty result table")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def read_daily(body, pairs, design):
    reader = csv.DictReader(io.StringIO(body.decode()))
    require(reader.fieldnames == list(DAILY), "daily columns differ")
    rows, keys = [], []
    for row in reader:
        require(set(row) == set(DAILY) and all(v is not None for v in row.values()), "malformed daily row")
        for key in ("key", "seed", "draw", "day", *CORE):
            text = row[key]
            row[key] = int(text)
            require(str(row[key]) == text and row[key] >= 0, "invalid daily integer")
        row["realized_supply_navax"] = float(row["realized_supply_navax"])
        require(math.isfinite(row["realized_supply_navax"]), "nonfinite realized supply")
        require(row["seed"] == row["key"] + 1 and row["draw"] == row["key"], "seed or draw pairing differs")
        require(row["date"] == (date.fromisoformat(design["origin"]) + timedelta(days=row["day"])).isoformat(),
                "daily date clock differs")
        keys.append((row["cell"], row["key"], row["day"]))
        rows.append(row)
    expected = {(cell, key, day) for cell in design["cells"] for key in range(pairs)
                for day in range(design["timesteps"] + 1)}
    require(len(keys) == len(expected) and set(keys) == expected, "daily paths are missing, repeated or unexpected")
    return sorted(rows, key=lambda r: (r["cell"], r["key"], r["day"]))


def reference_rows(inputs, pairs):
    import duckdb

    rows = duckdb.execute("SELECT * FROM read_parquet(?) WHERE seed<=? ORDER BY cell,seed,day",
                          [str(inputs / "central-reference.parquet"), pairs]).df().to_dict("records")
    require(len(rows) == 2 * pairs * 366, "reference does not cover the selected paths")
    return [{"cell": row["cell"], "key": int(row["seed"]) - 1, "seed": int(row["seed"]),
             "draw": int(row["draw"]), "day": int(row["day"]), "date": str(row["date"])[:10],
             **{key: int(row[key]) for key in CORE}, "realized_supply_navax": float(row["realized_supply_navax"])}
            for row in rows]


def verify_reference(daily, reference, design, tolerance):
    require(len(daily) == len(reference), "reference path count differs")
    for actual, target in zip(daily, reference, strict=True):
        require(all(actual[key] == target[key] for key in DAILY if key != "realized_supply_navax"),
                f"original daily trajectory differs: {actual['cell']} key {actual['key']} day {actual['day']}")
        require(math.isclose(actual["realized_supply_navax"], target["realized_supply_navax"],
                             rel_tol=tolerance["realized_supply_relative"],
                             abs_tol=tolerance["realized_supply_absolute_navax"]), "original realized supply differs")
    indexed = {(r["cell"], r["key"], r["day"]): r for r in daily}
    for row in daily:
        key, cell, day = row["key"], row["cell"], row["day"]
        if day == 0:
            require(row["supply_counter_navax"] == design["supply0_navax"]
                    and row["issued_day_navax"] == row["cumulative_issued_navax"] == 0, "origin state differs")
        else:
            before = indexed[cell, key, day - 1]
            require(row["supply_counter_navax"] - before["supply_counter_navax"] == row["issued_day_navax"]
                    and row["cumulative_issued_navax"] - before["cumulative_issued_navax"] == row["issued_day_navax"],
                    "counter or promised-issuance conservation failed")
    return {"daily_rows": len(daily), "integer_core_values_exact": len(daily) * len(CORE),
            "realized_supply_within_declared_tolerance": True}


def comparison(daily, pairs, design):
    import numpy as np

    ends = {(r["cell"], r["key"]): r for r in daily if r["day"] == design["timesteps"]}
    rows = []
    for key in range(pairs):
        baseline, candidate = (ends[cell, key] for cell in design["cells"])
        require(all(baseline[name] > 0 for name in ("cumulative_issued_navax", "validator_stake_navax", "active_validators")),
                "zero comparison denominator")
        rows.append({"key": key, "seed": key + 1, "draw": key,
                     "issuance_saved": 1 - candidate["cumulative_issued_navax"] / baseline["cumulative_issued_navax"],
                     "validator_stake_kept": candidate["validator_stake_navax"] / baseline["validator_stake_navax"],
                     "active_validators_kept": candidate["active_validators"] / baseline["active_validators"]})
    quantiles = [{"quantile": label, **{metric: float(np.quantile([r[metric] for r in rows], q, method="linear"))
                                       for metric in METRICS}}
                 for label, q in (("p10", 0.1), ("median", 0.5), ("p90", 0.9))]
    return rows, quantiles


def compare_expected(quantiles, expected):
    tolerance = expected["tolerance"]
    require(len(quantiles) == len(expected["comparison"]), "expected comparison shape differs")
    for actual, target in zip(quantiles, expected["comparison"], strict=True):
        require(actual["quantile"] == target["quantile"], "expected quantile identity differs")
        require(all(math.isclose(actual[key], target[key], rel_tol=tolerance["ratio_relative"],
                                 abs_tol=tolerance["ratio_absolute"]) for key in METRICS), "headline ratios differ")


def producing_files():
    return {"scripts/reproduce_report.py": record(Path(__file__)),
            **{f"examples/report-reproduction/{name}": record(EXAMPLE / name)
               for name in ("config.json", "expected.json", "input-manifest.json")}}


def clock_inputs(inputs, design):
    """Check the counter observation and derive burn/supply using pre-origin ledger rows only."""
    import duckdb
    import numpy as np

    with (inputs / "counter.csv").open(newline="") as stream:
        counters = list(csv.DictReader(stream))
    require(len(counters) == 1 and counters[0]["start_time"] == "2025-11-18 23:56:46"
            and counters[0]["accepted_at"] == counters[0]["start_time"]
            and int(counters[0]["supply_before_navax"]) == design["supply0_navax"], "counter observation differs")
    ledger = inputs / "data/runs/avax-monetary-daily-2026-09-30/dataset/avax-monetary-daily.parquet"
    rows = duckdb.execute(
        "SELECT date_utc,burned_wei::VARCHAR,total_supply_close_wei::VARCHAR,complete FROM read_parquet(?) "
        "WHERE date_utc<=CAST(? AS DATE) ORDER BY date_utc", [str(ledger), design["origin"]],
    ).fetchall()
    require(rows and rows[-1][0].isoformat() == design["origin"] and rows[-1][3], "origin ledger observation missing")
    burned = [int(burn) / 1e9 for _, burn, _, complete in rows if complete and burn is not None]
    require(len(burned) >= 365, "fewer than 365 complete pre-origin burn observations")
    burn = float(np.asarray(burned[-365:], dtype=float).mean())
    supply = float(int(rows[-1][2]) / 1e9)
    require(burn == design["burn_navax_per_day"] and supply == design["realized_supply_at_origin_navax"],
            "original ledger burn or realized supply differs")
    return {"supply0_navax": design["supply0_navax"], "counter_observed_at_utc": design["counter_observed_at_utc"],
            "realized_supply_at_origin_navax": supply, "burn_navax_per_day": burn, "burn_complete_days": 365}


def check_result(inputs: Path, output: Path) -> dict:
    """Authenticate all dependencies and saved tables without fitting or model execution."""
    value = authenticate_inputs(inputs)
    require(output.is_dir() and not output.is_symlink(), "missing or symlinked result directory")
    require({p.name for p in output.iterdir()} == OUTPUTS | {"summary.json"}, "result file inventory differs")
    require(all(p.is_file() and not p.is_symlink() for p in output.iterdir()), "unsafe result artifact")
    summary = read_json(output / "summary.json")
    design, expected = read_json(EXAMPLE / "config.json"), read_json(EXAMPLE / "expected.json")
    require(summary["schema"] == "report-reproduction-result/v1" and summary["status"] == "complete",
            "incomplete report result")
    require(summary["mode"] in ("pilot", "full"), "unknown reproduction mode")
    pairs = 1 if summary["mode"] == "pilot" else design["pairs"]
    require(summary["pair_count"] == pairs and summary["design"] == design, "result design differs")
    require(summary["inputs"] == value and summary["producing_files"] == producing_files(), "input or producing-code binding differs")
    require(summary["tolerance"] == expected["tolerance"], "result tolerance differs")
    clocks = clock_inputs(inputs, design)
    require(set(summary["artifacts"]) == OUTPUTS, "artifact bindings differ")
    for name in OUTPUTS:
        require(record(output / name) == summary["artifacts"][name], f"changed result artifact: {name}")
    require(read_json(output / "configuration.json") == design, "saved configuration differs")
    execution = read_json(output / "execution.json")
    require(execution["model_source_commit"] == MODEL_SOURCE
            and execution["prepared_specification_sha256"] == expected["prepared_specification_sha256"]
            and execution["original_execution_driver_identity"] == "unresolved", "execution identity differs")
    require(execution["clocks"] == clocks, "execution clock bindings differ")
    require(execution["archived_source_files"] == {name: item for name, item in value["members"].items()
                                                 if name.startswith("model-source/")}, "model source bindings differ")
    daily = read_daily((output / "daily.csv").read_bytes(), pairs, design)
    equality = verify_reference(daily, reference_rows(inputs, pairs), design, expected["tolerance"])
    require(summary["reference_comparison"] == equality, "reference-comparison receipt differs")
    paired, quantiles = comparison(daily, pairs, design)
    require((output / "paired.csv").read_bytes() == csv_bytes(paired), "saved per-pair ratios differ")
    require((output / "comparison.csv").read_bytes() == csv_bytes(quantiles), "saved quantile table differs")
    require(summary["comparison"] == quantiles, "summary quantiles differ")
    if pairs == design["pairs"]:
        compare_expected(quantiles, expected)
    return summary


def simulate(task):
    import numpy as np

    from avalanche_research.mechanisms import ACP285Ramp, ChainReward
    from avalanche_research.model.engine import run

    cell, key = task
    design = _DESIGN
    mechanism = ChainReward() if cell == design["cells"][0] else ACP285Ramp(
        activation=datetime.fromisoformat(design["activation"]), ramp_days=design["ramp_days"],
        target_min_rate=design["target_min_rate"])
    model = _BASE.with_settings(seed=key + 1, draws=_BASE.draws.iloc[[key]].reset_index(drop=True), mechanism=mechanism,
                                renewal_response=design["renewal_response"], entry_response=design["entry_response"],
                                outside_yield_pp=design["outside_yield_pp"],
                                fitted_outside_yield_pp=design["fitted_outside_yield_pp"])
    variables = ("active_validators", "active_validator_stake_navax", "supply_navax", "issued_navax")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        table = run(model)
    wide = table[table.variable.isin(variables)].pivot(index="timestep", columns="variable", values="value").sort_index()
    issued = np.asarray([int(v) for v in wide.issued_navax], dtype=float)
    days = np.asarray(wide.index, dtype=int)
    supply = design["realized_supply_at_origin_navax"] + (issued - design["burn_navax_per_day"] * (days > 0)).cumsum()
    total, rows = 0, []
    for position, (day, one) in enumerate(wide.iterrows()):
        total += int(one.issued_navax)
        rows.append({"cell": cell, "key": key, "seed": key + 1, "draw": key, "day": int(day),
                     "date": (date.fromisoformat(design["origin"]) + timedelta(days=int(day))).isoformat(),
                     "active_validators": int(one.active_validators), "validator_stake_navax": int(one.active_validator_stake_navax),
                     "supply_counter_navax": int(one.supply_navax), "issued_day_navax": int(one.issued_navax),
                     "cumulative_issued_navax": total, "realized_supply_navax": float(supply[position])})
    return rows


def worker(inputs, output, pairs):
    """Isolated process: import only the authenticated archived research package."""
    global _BASE, _DESIGN
    import multiprocessing
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    sys.dont_write_bytecode = True
    value = authenticate_inputs(inputs)
    source = (inputs / "model-source/src").resolve()
    sys.path.insert(0, str(source))
    import duckdb

    from avalanche_research.model import MODEL_VERSION
    from avalanche_research.model.variants import VARIANTS

    duckdb.execute("SET threads=1")
    design = _DESIGN = read_json(EXAMPLE / "config.json")
    expected = read_json(EXAMPLE / "expected.json")
    require(MODEL_VERSION == "0.8.0", "archived model version differs")
    clocks = clock_inputs(inputs, design)
    started = time.perf_counter()
    prepared = VARIANTS["v0.8.0"].prepare(str(inputs / "validators.parquet"), date.fromisoformat(design["origin"]),
                                              design["input_run"], draws=0)
    prepared.inputs["supply0_navax"] = design["supply0_navax"]
    point = VARIANTS["v0.8.0"].simulation(prepared, seed=1, timesteps=365, runs=1)
    fingerprint = hashlib.sha256(json.dumps(point.specification(), sort_keys=True, default=str).encode()).hexdigest()
    require(fingerprint == expected["prepared_specification_sha256"], "original prepared-state fingerprint differs")
    prepare_seconds = time.perf_counter() - started
    draws = duckdb.execute("SELECT * FROM read_parquet(?) LIMIT 50", [str(inputs / "draws.parquet")]).df()
    require(len(draws) == 50 and len(draws.columns) == 29 and not draws.isna().any().any(), "draw table shape differs")
    _BASE = VARIANTS["v0.8.0"].model(timesteps=365, runs=1, seed=0, **prepared.inputs, draws=draws)
    with ProcessPoolExecutor(max_workers=min(4, pairs * 2), mp_context=multiprocessing.get_context("fork")) as pool:
        frames = list(pool.map(simulate, [(cell, key) for cell in design["cells"] for key in range(pairs)]))
    rows = sorted([row for frame in frames for row in frame], key=lambda r: (r["cell"], r["key"], r["day"]))
    for name, module in tuple(sys.modules.items()):
        if name == "avalanche_research" or name.startswith("avalanche_research."):
            require(Path(module.__file__).resolve().is_relative_to(source), "model module loaded outside authenticated source")
    execution = {"model_source_commit": MODEL_SOURCE, "prepared_specification_sha256": fingerprint,
                 "clocks": clocks,
                 "original_execution_driver_identity": "unresolved", "prepare_seconds": prepare_seconds,
                 "fit_and_simulation_seconds": time.perf_counter() - started,
                 "worker_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 "environment": {"python": platform.python_version(), "platform": platform.platform(),
                                 "packages": {name: importlib.metadata.version(name)
                                              for name in ("numpy", "pandas", "scipy", "duckdb", "param", "cadCAD")}},
                 "archived_source_files": {name: item for name, item in value["members"].items()
                                           if name.startswith("model-source/")}}
    (output / "daily.csv").write_bytes(csv_bytes(rows))
    (output / "execution.json").write_bytes(canonical(execution))


def run_result(inputs, output, pilot=False):
    value = authenticate_inputs(inputs)
    design, expected = read_json(EXAMPLE / "config.json"), read_json(EXAMPLE / "expected.json")
    identities = producing_files()
    pairs = 1 if pilot else design["pairs"]
    require(not output.exists() and not output.is_symlink(), "result destination must be new")
    output.mkdir(parents=True)
    environment = {**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                   "PYTHONDONTWRITEBYTECODE": "1"}
    command = [sys.executable, str(Path(__file__).resolve()), "_worker", "--inputs", str(inputs.resolve()),
               "--output", str(output.resolve()), "--pairs", str(pairs)]
    child = subprocess.Popen(command, env=environment, start_new_session=True)
    try:
        require(child.wait(timeout=600) == 0, "model worker failed; no complete result was written")
    except BaseException:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        child.wait()
        raise
    authenticate_inputs(inputs)
    require(producing_files() == identities, "producing files changed during execution")
    daily = read_daily((output / "daily.csv").read_bytes(), pairs, design)
    equality = verify_reference(daily, reference_rows(inputs, pairs), design, expected["tolerance"])
    paired, quantiles = comparison(daily, pairs, design)
    if not pilot:
        compare_expected(quantiles, expected)
    for name, body in (("configuration.json", canonical(design)), ("paired.csv", csv_bytes(paired)),
                       ("comparison.csv", csv_bytes(quantiles))):
        (output / name).write_bytes(body)
    summary = {"schema": "report-reproduction-result/v1", "status": "complete", "mode": "pilot" if pilot else "full",
               "pair_count": pairs, "design": design, "inputs": value, "producing_files": identities,
               "tolerance": expected["tolerance"], "comparison": quantiles, "reference_comparison": equality,
               "observation_scheme": "p10/median/p90 of per-pair ratios across paired keys, linear quantiles",
               "artifacts": {name: record(output / name) for name in sorted(OUTPUTS)}}
    (output / "summary.json").write_bytes(canonical(summary))
    try:
        return check_result(inputs, output)
    except BaseException:
        (output / "summary.json").unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="download and authenticate the immutable input archive")
    fetch.add_argument("--output", required=True, type=Path)
    fetch.add_argument("--archive", type=Path, help="use a local copy instead of downloading")
    for name in ("run", "check", "_worker"):
        command = commands.add_parser(name)
        command.add_argument("--inputs", required=True, type=Path)
        command.add_argument("--output", required=True, type=Path)
        if name == "run":
            command.add_argument("--pilot", action="store_true", help="replay and compare key zero only")
        elif name == "_worker":
            command.add_argument("--pairs", required=True, type=int, choices=(1, 50))
    args = parser.parse_args(argv)
    try:
        if args.command == "fetch":
            fetch_inputs(args.output, args.archive)
            result = {"status": "pass", "command": "fetch"}
        elif args.command == "_worker":
            worker(args.inputs, args.output, args.pairs)
            return 0
        else:
            summary = run_result(args.inputs, args.output, args.pilot) if args.command == "run" else check_result(args.inputs, args.output)
            result = {"status": "pass", "command": args.command, "mode": summary["mode"],
                      "pair_count": summary["pair_count"], "reference_comparison": summary["reference_comparison"]}
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        parser.exit(1, f"FAIL | report reproduction | {error}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
