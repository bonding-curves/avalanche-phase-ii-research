#!/usr/bin/env python3
"""The held-back test of model v0.8.0: register it, rehearse it on development data, score it once.

    uv run --group model python scripts/heldback_test_v080.py register
    uv run --group model python scripts/heldback_test_v080.py rehearse <folder> [workers]
    uv run --group model python scripts/heldback_test_v080.py score [workers]

The specification is ``validation/heldback/specification.json`` and its reading ``specification.md``. ``register``
writes ``validation/heldback/manifest.json`` with the SHA-256 of this script, the specification, the pinned inputs and
the code commit, and refuses when scoring output exists. The manifest is committed and tagged
``heldback-registered-v0.8.0`` before any score exists.

``score`` builds a lockbox token from that tag on ``origin``, checks every manifest hash, fits v0.8.0 once at the fit
origin from rows before it, replaces only the observed state at each later origin, runs the registered ensemble, and
scores it against the six benchmarks of the development scores by scaled CRPS, with coverage, the ensemble mean's
scaled error and the agreement's path measures reported beside the verdict. It writes to
``results/model-v0.8.0-heldback`` and refuses when a verdict is already there.

``rehearse`` runs the same code on a window that ends before Granite, with no token, into a folder outside the
results, so the script is checked before registration without reading a held-back row.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import platform
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from avalanche_research.core import lockbox
from avalanche_research.core.clock import LOCKBOX_FIRST_DAY
from avalanche_research.core.hashing import canonical_bytes
from avalanche_research.core.lockbox import require
from avalanche_research.model import evaluation as ev
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_lifecycle import origin_state
from avalanche_research.model.lifecycle import actual_path
from avalanche_research.model.lockbox_evaluation import (
    _json,
    at_origin,
    contract_diagnostics,
    frozen_fingerprint,
    verified_inputs,
)
from avalanche_research.model.replay import EVENTS_SQL, REWARDS_SQL, US_PER_DAY, daily_events
from avalanche_research.model.variants import VARIANTS, Prepared

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_distribution_scores import binomial_range, normal_scores, point_scores  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "validation/heldback"
SPECIFICATION = FOLDER / "specification.json"
SPECIFICATION_TEXT = FOLDER / "specification.md"
MANIFEST = FOLDER / "manifest.json"
RESULTS = ROOT / "results/model-v0.8.0-heldback"
TAG = "heldback-registered-v0.8.0"
REMOTE = "origin"
VARIANT = "v0.8.0"
REFERENCE = "N1d"
POINT = ("N1", "N2", "N3")
DISTRIBUTION = ("N1d", "N2d", "N4")
BANDS = {"cov80": (0.60, 0.95), "cov50": (0.30, 0.70)}
REGISTERED = (Path("scripts/heldback_test_v080.py"), Path("validation/heldback/specification.json"),
              Path("validation/heldback/specification.md"))

# The parent reads every origin's state, then forks. Workers only simulate, so no worker opens a file or needs the token.
CANDIDATES: dict[str, Prepared] = {}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def specification() -> dict:
    return json.loads(SPECIFICATION.read_text())


def origins_by_rule(fit_origin: date, score_until: date, horizons: list[int]) -> list[date]:
    """The fit origin, then month starts while the shortest horizon ends before ``score_until``."""
    last = score_until - timedelta(days=min(horizons) + 1)
    start = (pd.Timestamp(fit_origin) + pd.offsets.MonthBegin(1)).date()
    return [fit_origin, *[x.date() for x in pd.date_range(start, last, freq="MS")]]


def cases_by_rule(origins: list[date], score_until: date, horizons: list[int]) -> dict[int, list[date]]:
    return {h: [o for o in origins if o + timedelta(days=h) < score_until] for h in horizons}


def check_design(spec: dict) -> tuple[date, date, list[date], list[int], dict[int, list[date]]]:
    """The registered design, checked against its own rule."""
    fit_origin, score_until = date.fromisoformat(spec["fit"]["origin"]), date.fromisoformat(spec["window"]["score_until"])
    horizons = [int(h) for h in spec["horizons_days"]]
    origins = origins_by_rule(fit_origin, score_until, horizons)
    if [o.isoformat() for o in origins] != spec["origins"]:
        raise ValueError("the specification's origins differ from its origin rule")
    cases = cases_by_rule(origins, score_until, horizons)
    if {str(h): [o.isoformat() for o in v] for h, v in cases.items()} != spec["cases"]:
        raise ValueError("the specification's cases differ from its rule")
    if fit_origin >= LOCKBOX_FIRST_DAY:
        raise ValueError("the fit origin must be before the held-back period")
    return fit_origin, score_until, origins, horizons, cases


def realized_series(periods: Path, through: date, token) -> pd.DataFrame:
    """Active validators and validator stake on every UTC day before ``through``, built as the development scores
    built them. A day from the held-back period needs the token."""
    require(datetime.combine(through, time(0), tzinfo=UTC) - timedelta(microseconds=1), token)
    if through <= LOCKBOX_FIRST_DAY:
        events = daily_events(str(periods), through)
    else:
        rows = duckdb.execute(EVENTS_SQL, [str(periods)]).fetchall()
        rewards = duckdb.execute(REWARDS_SQL, [str(periods)]).fetchall()
        first = min(min(r[0] for r in rows), min(r[0] for r in rewards))
        last = (pd.Timestamp(through) - pd.Timestamp(0)).days - 1
        columns = {name: np.zeros(last - first + 1, dtype=np.int64)
                   for name in ("d_validator_stake", "d_delegated_stake", "d_validators", "d_delegations", "rewards_paid")}
        for day, role, stake, n in rows:
            if first <= day <= last:
                prefix = "validator" if role == "validator" else "delegated"
                columns[f"d_{prefix}_stake"][day - first] += stake
                columns["d_validators" if role == "validator" else "d_delegations"][day - first] += n
        for day, amount in rewards:
            if first <= day <= last:
                columns["rewards_paid"][day - first] += amount
        dates = pd.to_datetime(np.arange(first, last + 1) * US_PER_DAY, unit="us").date
        events = pd.DataFrame({"date_utc": dates, **columns})
    actual = actual_path(events)
    actual.index = pd.to_datetime(actual.pop("date_utc"))
    return actual.astype(float)


def crosscheck(monetary: Path, actual: pd.DataFrame, cases: dict[int, list[date]], token) -> pd.DataFrame:
    """The monetary run's daily stocks against the realized series at every scored endpoint. Reported only."""
    endpoints = sorted({o + timedelta(days=h) for h, origins in cases.items() for o in origins})
    require(datetime.combine(max(endpoints), time(23, 59, 59), tzinfo=UTC), token)
    rows = duckdb.execute("SELECT date_utc, active_validator_stake_wei::VARCHAR, active_validators FROM read_parquet(?) "
                          "WHERE date_utc <= ? ORDER BY date_utc", [str(monetary), max(endpoints)]).fetchall()
    stocks = pd.DataFrame({"active_validator_stake_navax": [int(r[1]) / 10**9 for r in rows],
                           "active_validators": [float(r[2]) for r in rows]}, index=pd.DatetimeIndex([r[0] for r in rows]))
    out = []
    for when in endpoints:
        for variable in actual.columns:
            ours = float(actual.loc[pd.Timestamp(when), variable])
            theirs = float(stocks.loc[pd.Timestamp(when), variable]) if pd.Timestamp(when) in stocks.index else np.nan
            out.append({"date": when, "variable": variable, "realized": ours, "monetary_daily": theirs,
                        "relative_difference": (theirs - ours) / ours if ours else np.nan})
    return pd.DataFrame(out)


def prepare(periods: Path, fit_origin: date, run_name: str, spec: dict) -> Prepared:
    ensemble = spec["ensemble"]
    draws = len(ensemble["batch_seeds"]) * int(ensemble["runs_per_batch"])
    prepared = VARIANTS[VARIANT].prepare(str(periods), fit_origin, run_name, draws=draws, draw_seed=int(ensemble["draw_seed"]))
    if prepared.draws is None or len(prepared.draws) != draws:
        raise ValueError("the fit must carry exactly the registered draws")
    return prepared


def origin_runs(task: tuple[str, int, list[int], int]) -> tuple[pd.DataFrame, list[dict]]:
    """Every run's value on every day for one origin: state replaced, fit kept, the registered ensemble."""
    origin, timesteps, seeds, batch_runs = task
    candidate = CANDIDATES[origin]
    parts, receipts = [], []
    for batch, seed in enumerate(seeds):
        draws = candidate.draws.iloc[batch * batch_runs:(batch + 1) * batch_runs].reset_index(drop=True)
        model = VARIANTS[VARIANT].simulation(candidate, seed=seed, timesteps=timesteps, runs=batch_runs, draws=draws)
        receipts.append({"origin": origin, "batch_seed": seed, "specification": model.specification_hash()})
        table = run(model)
        table = table[table.variable.isin(("active_validator_stake_navax", "active_validators"))]
        parts.append(pd.DataFrame({"origin": origin, "batch_seed": seed, "run": table.run.to_numpy(),
                                   "variable": table.variable.to_numpy(), "timestep": table.timestep.to_numpy(),
                                   "value": table.value.astype(float).to_numpy()}))
    return pd.concat(parts, ignore_index=True), receipts


def simulate(periods: Path, prepared: Prepared, fit_origin: date, origins: list[date], cases: dict[int, list[date]],
             spec: dict, workers: int, token) -> tuple[pd.DataFrame, list[dict]]:
    """Each origin's state is read in the parent, under the token; the ensembles run in forked workers."""
    seeds, batch_runs = [int(s) for s in spec["ensemble"]["batch_seeds"]], int(spec["ensemble"]["runs_per_batch"])
    tasks = []
    CANDIDATES.clear()
    for origin in origins:
        eligible = [h for h, listed in cases.items() if origin in listed]
        if eligible:
            state = origin_state(str(periods), origin, token)
            CANDIDATES[origin.isoformat()] = at_origin(prepared, state, origin, fit_origin)
            tasks.append((origin.isoformat(), max(eligible), seeds, batch_runs))
    with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("fork")) as pool:
        results = list(pool.map(origin_runs, tasks))
    trajectories = pd.concat([t for t, _ in results], ignore_index=True)
    receipts = [r for _, rs in results for r in rs]
    return trajectories, receipts


def score_cells(trajectories: pd.DataFrame, actual: pd.DataFrame, cases: dict[int, list[date]], spec: dict) -> pd.DataFrame:
    """One row per origin, variable, horizon and forecast: scaled CRPS, PIT, coverage, width and the scaled error."""
    expected = len(spec["ensemble"]["batch_seeds"]) * int(spec["ensemble"]["runs_per_batch"])
    rows = []
    for h, origins in cases.items():
        for origin in origins:
            at = trajectories[(trajectories.origin == origin.isoformat()) & (trajectories.timestep == h)]
            for variable in spec["variables"]:
                series = actual[variable]
                scale, realized = ev.mase_scale(series, origin), ev.actual_at(series, origin, h)
                draws = at.loc[at.variable == variable, "value"].to_numpy(dtype=float)
                if len(draws) != expected:
                    raise ValueError(f"incomplete ensemble at {origin} {variable} {h}: {len(draws)} of {expected}")
                n1d = ev.dressed(series, origin, h, "N1")
                scored = {"model": {**ev.distribution_scores(draws, realized, scale),
                                    "mase": ev.scaled_error(float(np.mean(draws)), realized, scale),
                                    "point": float(np.mean(draws))},
                          "N1d": {**ev.distribution_scores(n1d, realized, scale), "point": float(np.mean(n1d))},
                          "N2d": ev.distribution_scores(ev.dressed(series, origin, h, "N2"), realized, scale),
                          "N4": normal_scores(*ev.local_level(series, origin, h), realized, scale)}
                for name, rule in ev.BENCHMARKS.items():
                    value = rule(series, origin, h)
                    scored[name] = {**point_scores(value, realized, scale), "mase": ev.scaled_error(value, realized, scale),
                                    "point": value}
                for forecast, s in scored.items():
                    rows.append({"origin": origin.isoformat(), "variable": variable, "horizon_days": h, "forecast": forecast,
                                 **s, "scale": scale, "actual": realized})
    return pd.DataFrame(rows)


def summarise(scores: pd.DataFrame, origins: list[date]) -> pd.DataFrame:
    """Per variable, horizon and forecast: mean scaled CRPS, coverage with ranges, tails, width, skill and the test."""
    dates = {o.isoformat(): o for o in origins}
    out = []
    for (variable, h), part in scores.groupby(["variable", "horizon_days"]):
        crps = part.pivot(index="origin", columns="forecast", values="crps")
        crps = crps.loc[ev.chronological(crps.index, dates)]
        lags = ev.dm_horizon(int(h), [dates[o] for o in crps.index])
        for forecast, g in part.groupby("forecast"):
            n = int(g.in80.notna().sum())
            row = {"variable": variable, "horizon_days": int(h), "forecast": forecast, "origins": len(g),
                   "crps": float(g.crps.mean()), "skill_vs_N1d": float(1 - g.crps.mean() / crps[REFERENCE].mean())}
            for level in ("50", "80"):
                hits = g[f"in{level}"].sum()
                lower, upper = binomial_range(hits, n)
                row |= {f"cov{level}": hits / n if n else np.nan, f"cov{level}_low": lower, f"cov{level}_high": upper}
            row |= {"pit_below_10": int((g.pit < 0.1).sum()), "pit_above_90": int((g.pit > 0.9).sum()),
                    "width80": float(g.width80.mean()), "dm_horizon": lags,
                    "closer_than_N1d": np.nan, "dm_statistic": np.nan, "p_better_than_N1d": np.nan, "dm_note": ""}
            if forecast != REFERENCE:
                row["closer_than_N1d"] = int((crps[forecast] < crps[REFERENCE]).sum())
                try:
                    test = ev.diebold_mariano(crps[forecast], crps[REFERENCE], horizon=lags)
                    row |= {"dm_statistic": test["statistic"], "p_better_than_N1d": test["p_less"], "dm_note": test["variance"]}
                except ValueError as error:
                    row["dm_note"] = str(error)
            out.append(row)
    return pd.DataFrame(out)


def point_comparisons(scores: pd.DataFrame, origins: list[date]) -> pd.DataFrame:
    """The ensemble mean's scaled absolute error against N1, N2 and N3, the 26 October proposal's rule, as a secondary."""
    dates = {o.isoformat(): o for o in origins}
    out = []
    for (variable, h), part in scores.groupby(["variable", "horizon_days"]):
        mase = part[part.forecast.isin(("model", *POINT))].pivot(index="origin", columns="forecast", values="mase")
        mase = mase.loc[ev.chronological(mase.index, dates)]
        lags = ev.dm_horizon(int(h), [dates[o] for o in mase.index])
        for benchmark in POINT:
            row = {"variable": variable, "horizon_days": int(h), "benchmark": benchmark, "origins": len(mase),
                   "model_mase": float(mase["model"].mean()), "benchmark_mase": float(mase[benchmark].mean()),
                   "model_closer": int((mase["model"] < mase[benchmark]).sum()), "dm_horizon": lags,
                   "dm_statistic": np.nan, "p_model_better": np.nan, "dm_note": ""}
            try:
                test = ev.diebold_mariano(mase["model"], mase[benchmark], horizon=lags)
                row |= {"dm_statistic": test["statistic"], "p_model_better": test["p_less"], "dm_note": test["variance"]}
            except ValueError as error:
                row["dm_note"] = str(error)
            out.append(row)
    return pd.DataFrame(out)


def path_diagnostics(trajectories: pd.DataFrame, actual: pd.DataFrame, spec: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The agreement's measures on each origin's daily ensemble-mean path, and the paths themselves."""
    diagnostics, paths = [], []
    for (origin, variable), part in trajectories.groupby(["origin", "variable"]):
        means = part.groupby("timestep").value.mean()
        dates = pd.DatetimeIndex([date.fromisoformat(origin) + timedelta(days=int(t)) for t in means.index])
        observed = actual.loc[dates, variable].to_numpy(dtype=float)
        diagnostics.append({"origin": origin, "variable": variable, "days": len(means),
                            **contract_diagnostics(means.to_numpy(dtype=float), observed)})
        paths.extend({"origin": origin, "variable": variable, "date": d.date().isoformat(), "ensemble_mean": float(x),
                      "actual": float(y)} for d, x, y in zip(dates, means, observed, strict=True))
    return pd.DataFrame(diagnostics), pd.DataFrame(paths)


def verdict(summary: pd.DataFrame, spec: dict) -> dict:
    """The registered rule at the primary cell. Coverage states are reported beside it."""
    primary = spec["primary"]
    cell = summary[(summary.variable == primary["variable"]) & (summary.horizon_days == int(primary["horizon_days"]))]
    by = {row.forecast: row for row in cell.itertuples(index=False)}
    benchmarks = (*POINT, *DISTRIBUTION)
    reasons = []
    if "model" not in by or any(b not in by for b in benchmarks):
        reasons.append("missing forecast rows at the primary cell")
    elif by["model"].origins != int(primary["origins"]) or any(by[b].origins != int(primary["origins"]) for b in benchmarks):
        reasons.append("the primary cell does not hold the registered number of origins")
    elif not np.isfinite([by["model"].crps, *[by[b].crps for b in benchmarks]]).all():
        reasons.append("an undefined mean scaled CRPS at the primary cell")
    comparisons, result, p = [], None, None
    if not reasons:
        model = float(by["model"].crps)
        comparisons = [{"benchmark": b, "benchmark_crps": float(by[b].crps), "model_crps": model, "model_below": model < float(by[b].crps)}
                       for b in benchmarks]
        p = by["model"].p_better_than_N1d
        if not all(c["model_below"] for c in comparisons):
            result = "FAIL"
        elif p is not None and np.isfinite(p) and p < float(primary["alpha"]):
            result = "PASS"
        else:
            result = "INCONCLUSIVE"
            reasons.append("below all six benchmarks, but the one-sided p against N1d is not under 0.05"
                           if p is not None and np.isfinite(p) else f"the test against N1d is undefined: {by['model'].dm_note}")
    else:
        result = "INCONCLUSIVE"
    coverage = []
    for row in summary[summary.forecast == "model"].itertuples(index=False):
        for level, (low, high) in BANDS.items():
            value = getattr(row, level)
            coverage.append({"variable": row.variable, "horizon_days": int(row.horizon_days), "interval": level,
                             "coverage": None if pd.isna(value) else float(value), "band": [low, high],
                             "state": "not measured" if pd.isna(value) else "pass" if low <= value <= high else "fail",
                             "origins": int(row.origins)})
    return {"verdict": result, "primary": primary, "reasons": reasons, "comparisons": comparisons,
            "p_better_than_N1d": None if p is None or not np.isfinite(p) else float(p),
            "dm_horizon": None if not comparisons else int(by["model"].dm_horizon), "coverage": coverage}


def environment() -> dict:
    import numpy
    import pandas
    import scipy
    return {"python": platform.python_version(), "numpy": numpy.__version__, "pandas": pandas.__version__,
            "scipy": scipy.__version__, "duckdb": duckdb.__version__, "machine": platform.machine(),
            "node": platform.node(), "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS")}


def registered_hashes(spec: dict) -> dict:
    pin = json.loads((ROOT / spec["inputs"]["pin"]).read_text())
    inputs = verified_inputs(ROOT, spec["inputs"]["pin"])
    return {"files": {str(p): sha256_file(ROOT / p) for p in REGISTERED},
            "pin": {"path": spec["inputs"]["pin"], "sha256": sha256_file(ROOT / spec["inputs"]["pin"]),
                    "runs": [{"dataset_id": r["dataset_id"], "run": r["run"], "bytes": r["bytes"], "sha256": r["sha256"],
                              "path": str(inputs[r["dataset_id"]].relative_to(ROOT))} for r in pin["runs"]]},
            "uv_lock_sha256": sha256_file(ROOT / "uv.lock")}


def register() -> int:
    spec = specification()
    check_design(spec)
    if RESULTS.exists():
        raise SystemExit(f"{RESULTS.relative_to(ROOT)} exists: no registration after scoring output")
    if MANIFEST.exists():
        raise SystemExit(f"{MANIFEST.relative_to(ROOT)} exists: the test is already registered")
    dirty = git("status", "--porcelain", "--", "src", "data/pins", "uv.lock")
    if dirty:
        raise SystemExit("src, data/pins or uv.lock has uncommitted changes:\n" + dirty)
    model_tag = git("rev-list", "-n", "1", spec["model"]["tag"])
    if model_tag != spec["model"]["commit"]:
        raise SystemExit(f"tag {spec['model']['tag']} is {model_tag}, not the specification's commit")
    manifest = {"schema": "heldback-registration/v1", "status": "registered", "tag": TAG,
                "registered_at": datetime.now(UTC).isoformat(timespec="seconds"), "registered_by": "modeling-lead",
                "model": spec["model"], "code_commit": git("rev-parse", "HEAD"),
                "code_commit_note": "The commit this manifest was built on. The registration commit adds this folder and the script to it and is the commit the tag names.",
                **registered_hashes(spec),
                "scoring_output": "none at registration",
                "supersedes": "validation/lockbox, the draft of 27 October whose manifest stayed pending",
                "entry_point": "scripts/heldback_test_v080.py score"}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


def check_registration(spec: dict) -> dict:
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get("status") != "registered" or manifest.get("tag") != TAG:
        raise SystemExit("the manifest is not a registration")
    current = registered_hashes(spec)
    for path, expected in manifest["files"].items():
        if current["files"].get(path) != expected:
            raise SystemExit(f"{path} differs from its registered hash")
    if current["pin"] != manifest["pin"] or current["uv_lock_sha256"] != manifest["uv_lock_sha256"]:
        raise SystemExit("the pinned inputs or uv.lock differ from their registered hashes")
    tag_commit = git("rev-list", "-n", "1", TAG)
    for path in (*manifest["files"], "validation/heldback/manifest.json"):
        blob = subprocess.run(["git", "-C", str(ROOT), "show", f"{tag_commit}:{path}"], capture_output=True, check=True).stdout
        if hashlib.sha256(blob).hexdigest() != sha256_file(ROOT / path):
            raise SystemExit(f"{path} differs from the tagged registration")
    return {**manifest, "registration_commit": tag_commit}


def write_outputs(folder: Path, *, spec: dict, trajectories: pd.DataFrame, receipts: list[dict], scores: pd.DataFrame,
                  summary: pd.DataFrame, points: pd.DataFrame, diagnostics: pd.DataFrame, paths: pd.DataFrame,
                  checks: pd.DataFrame, result: dict, receipt: dict, cases: dict[int, list[date]]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    gzip = {"method": "gzip", "mtime": 0}
    horizons = trajectories[trajectories.timestep.isin(list(cases))]
    horizons.rename(columns={"timestep": "horizon_days"}).to_csv(folder / "runs.csv.gz", index=False, compression=gzip)
    scores.to_csv(folder / "scores.csv", index=False)
    summary.to_csv(folder / "summary.csv", index=False)
    points.to_csv(folder / "point-comparisons.csv", index=False)
    diagnostics.to_csv(folder / "contract-diagnostics.csv", index=False)
    paths.to_csv(folder / "daily-paths.csv.gz", index=False, compression=gzip)
    checks.to_csv(folder / "realized-crosscheck.csv", index=False)
    pd.DataFrame(receipts).to_csv(folder / "specifications.csv", index=False)
    (folder / "verdict.json").write_text(json.dumps(_json(result), indent=2) + "\n")
    outputs = sorted(p.name for p in folder.iterdir() if p.name not in ("receipt.json", "README.md"))
    receipt["outputs"] = {name: sha256_file(folder / name) for name in outputs}
    (folder / "receipt.json").write_text(json.dumps(_json(receipt), indent=2) + "\n")


def evaluate(spec: dict, folder: Path, workers: int, token, *, fit_origin: date, score_until: date,
             origins: list[date], cases: dict[int, list[date]], receipt: dict) -> dict:
    started = datetime.now(UTC)
    inputs = verified_inputs(ROOT, spec["inputs"]["pin"])
    periods, monetary = inputs["derived.staking-periods"], inputs["derived.avax-monetary-daily"]
    prepared = prepare(periods, fit_origin, spec["inputs"]["run"], spec)
    fit = {"fit_origin": fit_origin.isoformat(), "fit_sha256": frozen_fingerprint(prepared),
           "draws_sha256": hashlib.sha256(canonical_bytes(_json(prepared.draws.to_dict("records")))).hexdigest(),
           "tau": prepared.tau, "tau_source": prepared.tau_source, "draws": len(prepared.draws)}
    actual = realized_series(periods, score_until, token)
    for h, listed in cases.items():
        for origin in listed:
            for variable in spec["variables"]:
                ev.actual_at(actual[variable], origin, h)
    trajectories, receipts = simulate(periods, prepared, fit_origin, origins, cases, spec, workers, token)
    if frozen_fingerprint(prepared) != fit["fit_sha256"]:
        raise ValueError("the fit changed during the simulation")
    scores = score_cells(trajectories, actual, cases, spec)
    summary = summarise(scores, origins)
    points = point_comparisons(scores, origins)
    diagnostics, paths = path_diagnostics(trajectories, actual, spec)
    checks = crosscheck(monetary, actual, cases, token)
    result = verdict(summary, spec)
    result.update(fit_origin=fit_origin.isoformat(), score_until=score_until.isoformat(),
                  origins=[o.isoformat() for o in origins], cases={str(h): [o.isoformat() for o in v] for h, v in cases.items()})
    receipt.update(fit=fit, environment=environment(), started_at=started.isoformat(timespec="seconds"),
                   finished_at=datetime.now(UTC).isoformat(timespec="seconds"), workers=workers,
                   simulation_specifications=len(receipts), runs=int(trajectories.groupby(["origin", "batch_seed", "run"]).ngroups))
    write_outputs(folder, spec=spec, trajectories=trajectories, receipts=receipts, scores=scores, summary=summary,
                  points=points, diagnostics=diagnostics, paths=paths, checks=checks, result=result, receipt=receipt, cases=cases)
    return result


def score(workers: int) -> int:
    spec = specification()
    fit_origin, score_until, origins, horizons, cases = check_design(spec)
    if (RESULTS / "verdict.json").exists():
        raise SystemExit("a verdict exists: the held-back test is scored once")
    registration = check_registration(spec)
    token = lockbox.issue(ROOT, REMOTE, TAG)
    receipt = {"schema": "heldback-receipt/v1", "mode": "held-back", "tag": TAG, "tag_object": token.tag_object,
               "registration_commit": registration["registration_commit"], "code_commit": git("rev-parse", "HEAD"),
               "manifest": registration, "command": " ".join(sys.argv)}
    result = evaluate(spec, RESULTS, workers, token, fit_origin=fit_origin, score_until=score_until, origins=origins,
                      cases=cases, receipt=receipt)
    print(json.dumps(_json(result), indent=2))
    return 0


def rehearse(folder: Path, workers: int, fit_origin: date = date(2025, 3, 31)) -> int:
    """The same code on development data: fit at ``fit_origin``, score through the day before Granite, no token."""
    spec = specification()
    check_design(spec)
    if folder.resolve().is_relative_to(RESULTS.resolve()):
        raise SystemExit("a rehearsal never writes into the results folder")
    score_until = LOCKBOX_FIRST_DAY
    horizons = [int(h) for h in spec["horizons_days"]]
    origins = origins_by_rule(fit_origin, score_until, horizons)
    cases = cases_by_rule(origins, score_until, horizons)
    rehearsal = {**spec, "primary": {**spec["primary"], "origins": len(cases[int(spec["primary"]["horizon_days"])])}}
    receipt = {"schema": "heldback-receipt/v1", "mode": "rehearsal", "code_commit": git("rev-parse", "HEAD"),
               "command": " ".join(sys.argv)}
    result = evaluate(rehearsal, folder, workers, None, fit_origin=fit_origin, score_until=score_until, origins=origins,
                      cases=cases, receipt=receipt)
    print(json.dumps(_json(result), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    command, rest = argv[0], argv[1:]
    if command == "register":
        return register()
    if command == "score":
        return score(int(rest[0]) if rest else 4)
    if command == "rehearse":
        return rehearse(Path(rest[0]), int(rest[1]) if len(rest) > 1 else 4)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
