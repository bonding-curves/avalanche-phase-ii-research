"""Backtest of the engine on 2025 (deliverables 1.5 and 2.4): simulate from the observed state and score the fit.

The protocol below was fixed before the first run. Nothing in it is changed after seeing a result.

- Start: ``state.observed_state(con, "2025-01-01")``, the ledger close of 2024-12-31.
- Environment: ``scenario.observed(con, "2025-01-01", 365)``, the Binance AVAXUSDT close and the 3-month Treasury
  par yield (stored as a fraction), each carried forward over missing days.
- Parameters: ``Params()`` (mainnet protocol values) with ``BehaviourParams.from_json`` of the behaviour file.
  The primary run uses every point estimate in the file, identified or not. The variant ``unidentified_zero``
  sets every spread elasticity and the flow sensitivity to 0 and keeps the base rates. Both are declared here
  before any run. Pass or fail is stated for the primary run only.
- Seeds 0 to 4. The simulated series is the mean over seeds of each day's value.
- Observed series from ``avax_monetary_daily``, 2025-01-01 to 2025-12-31: staking ratio = (active validator stake
  + active delegated stake) / total supply at close, all in wei, and ``active_validators``. Days not marked
  ``complete`` are left out of every measure and counted.
- Measures, each on the days both series have:
  - ``pearson_r``: Pearson correlation of the daily levels.
  - ``rmse``: root mean squared difference of the daily levels. For the staking ratio it is in percentage points.
  - ``direction_accuracy``: share of days t >= 7 where the 7-day change x[t] - x[t-7] has the same sign in both
    series (a zero change is its own sign). ``direction_accuracy_1d`` is the same on 1-day changes, a diagnostic.
  - ``phase_lag_days``: the lag L in [-30, 30] that maximises the Pearson correlation between the simulated 7-day
    change on day t and the observed 7-day change on day t + L. A positive L means the simulation moves first.
- Targets (proposal v2.5 goodness-of-fit protocol, contract deliverable 2.4): r > 0.90, RMSE < 2 percentage points
  (staking ratio only), direction accuracy > 85%, |phase lag| <= 7 days.
- Benchmark: persistence, which holds the observed 2025-01-01 close for the whole year (the first observed day).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..catalog import ROOT, canonical_bytes, sha256
from . import invariants, scenario, state
from .behaviour import BehaviourParams
from .engine import run
from .params import Params

RUN_ID = "backtest-2025-v0"
START = "2025-01-01"
END = "2025-12-31"
DAYS = 365
SEEDS = (0, 1, 2, 3, 4)
BEHAVIOUR_PATH = ROOT / "data" / "model" / "behaviour-v0.json"
DIRECTION_WINDOW = 7
MAX_LAG = 30
TARGETS = {"pearson_r": 0.90, "rmse_pp": 2.0, "direction_accuracy": 0.85, "phase_lag_days": 7}
UNIDENTIFIED = ("entry_spread_elasticity", "duration_spread_elasticity", "renewal_spread_elasticity", "delegation_sensitivity")
# The datasets the backtest reads, by view name.
INPUT_VIEWS = ("staking_periods", "avax_monetary_daily", "avax_usdt_daily", "par_yield_daily")

OBSERVED_SQL = """
SELECT date_utc,
       CAST(active_validator_stake_wei AS HUGEINT) + CAST(active_delegated_stake_wei AS HUGEINT) AS staked_wei,
       CAST(total_supply_close_wei AS HUGEINT) AS supply_wei,
       active_validators,
       complete
FROM avax_monetary_daily
WHERE date_utc BETWEEN ?::DATE AND ?::DATE
ORDER BY date_utc
"""


def observed(con: Any, start: str = START, end: str = END) -> pd.DataFrame:
    """Daily observed staking ratio and validator count. The ratio is formed from integer wei."""
    rows = con.execute(OBSERVED_SQL, [start, end]).fetchall()
    return pd.DataFrame(
        [(day, int(staked) / int(supply), int(validators), bool(complete)) for day, staked, supply, validators, complete in rows],
        columns=["date", "staking_ratio", "validator_count", "complete"],
    )


def _change(values: np.ndarray, window: int) -> np.ndarray:
    return values[window:] - values[:-window]


def direction_accuracy(simulated: np.ndarray, actual: np.ndarray, window: int) -> float:
    """Share of days where the ``window``-day change has the same sign in both series. NaN days are skipped."""
    a, b = _change(simulated, window), _change(actual, window)
    keep = np.isfinite(a) & np.isfinite(b)
    return float((np.sign(a[keep]) == np.sign(b[keep])).mean()) if keep.any() else float("nan")


def phase_lag(simulated: np.ndarray, actual: np.ndarray, window: int = DIRECTION_WINDOW, max_lag: int = MAX_LAG) -> tuple[int, float]:
    """(lag, correlation) maximising corr(simulated change[t], actual change[t + lag]) over |lag| <= max_lag."""
    a, b = _change(simulated, window), _change(actual, window)
    best = (0, -np.inf)
    for lag in range(-max_lag, max_lag + 1):
        x, y = (a[: len(a) - lag], b[lag:]) if lag >= 0 else (a[-lag:], b[: len(b) + lag])
        keep = np.isfinite(x) & np.isfinite(y)
        if keep.sum() < 3 or np.std(x[keep]) == 0 or np.std(y[keep]) == 0:
            continue
        value = float(np.corrcoef(x[keep], y[keep])[0, 1])
        if value > best[1]:
            best = (lag, value)
    return best[0], (best[1] if np.isfinite(best[1]) else float("nan"))


def fit_measures(simulated: np.ndarray, actual: np.ndarray, scale: float = 1.0) -> dict[str, Any]:
    """The protocol's measures. ``scale`` multiplies the RMSE (100 turns a ratio into percentage points).
    Days where either series is NaN are left out of the level measures and break the change series."""
    simulated, actual = np.asarray(simulated, dtype=float), np.asarray(actual, dtype=float)
    keep = np.isfinite(simulated) & np.isfinite(actual)
    s, o = simulated[keep], actual[keep]
    r = float(np.corrcoef(s, o)[0, 1]) if np.std(s) > 0 and np.std(o) > 0 else float("nan")
    lag, lag_r = phase_lag(simulated, actual)
    return {
        "days": int(keep.sum()),
        "pearson_r": r,
        "rmse": float(np.sqrt(np.mean((s - o) ** 2)) * scale),
        "mean_error": float(np.mean(s - o) * scale),
        "direction_accuracy": direction_accuracy(simulated, actual, DIRECTION_WINDOW),
        "direction_accuracy_1d": direction_accuracy(simulated, actual, 1),
        "phase_lag_days": lag,
        "phase_lag_correlation": lag_r,
        "simulated_first_last": [float(s[0]), float(s[-1])],
        "observed_first_last": [float(o[0]), float(o[-1])],
    }


def verdict(measures: dict[str, Any], rmse_target: float | None) -> dict[str, bool | None]:
    return {
        "pearson_r": bool(measures["pearson_r"] > TARGETS["pearson_r"]),
        "rmse": None if rmse_target is None else bool(measures["rmse"] < rmse_target),
        "direction_accuracy": bool(measures["direction_accuracy"] > TARGETS["direction_accuracy"]),
        "phase_lag_days": bool(abs(measures["phase_lag_days"]) <= TARGETS["phase_lag_days"]),
    }


def simulate(params: Params, environment: scenario.Scenario, start_state: state.State, seeds: tuple[int, ...] = SEEDS) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Per-seed frames stacked with a ``seed`` column, and the invariant check of each seed."""
    frames, checks = [], []
    for seed in seeds:
        frame = run(params, environment, seed=seed, days=environment.days, initial_state=start_state.copy())
        checks.append({"seed": seed, **invariants.check_frame(frame, params.supply_cap_avax)})
        frames.append(frame.assign(seed=seed))
    return pd.concat(frames, ignore_index=True), checks


def score(frames: pd.DataFrame, actual: pd.DataFrame) -> dict[str, Any]:
    mean = frames.groupby("day")[["staking_ratio", "validator_count"]].mean().sort_index()
    ok = actual["complete"].to_numpy()
    ratio_obs = np.where(ok, actual["staking_ratio"].to_numpy(dtype=float), np.nan)
    count_obs = np.where(ok, actual["validator_count"].to_numpy(dtype=float), np.nan)
    ratio = fit_measures(mean["staking_ratio"].to_numpy(), ratio_obs, scale=100.0)
    count = fit_measures(mean["validator_count"].to_numpy(), count_obs)
    per_seed = [
        {"seed": int(seed), "staking_ratio": fit_measures(group.sort_values("day")["staking_ratio"].to_numpy(), ratio_obs, 100.0),
         "validator_count": fit_measures(group.sort_values("day")["validator_count"].to_numpy(), count_obs)}
        for seed, group in frames.groupby("seed")
    ]
    return {
        "staking_ratio": {**ratio, "rmse_unit": "percentage points", "pass": verdict(ratio, TARGETS["rmse_pp"])},
        "validator_count": {**count, "rmse_unit": "validators", "pass": verdict(count, None)},
        "per_seed": per_seed,
    }


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_bytes(canonical_bytes(value))
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Backtest the engine on 2025 into data/runs/<run id>/.")
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--behaviour", type=Path, default=BEHAVIOUR_PATH)
    args = parser.parse_args(argv)
    from .. import datasets

    started = time.perf_counter()
    selected = datasets.views()
    con = datasets.connect()
    con.execute("SET memory_limit='5GB'; SET threads=6;")
    start_state = state.observed_state(con, START)
    environment = scenario.observed(con, START, DAYS)
    actual = observed(con)
    con.close()
    if len(actual) != DAYS:
        raise ValueError(f"avax_monetary_daily has {len(actual)} of {DAYS} days in {START} to {END}")

    behaviour = BehaviourParams.from_json(args.behaviour)
    variants = {
        "primary": behaviour,
        "unidentified_zero": behaviour.replace(**dict.fromkeys(UNIDENTIFIED, 0.0)),
    }
    results: dict[str, Any] = {}
    daily = []
    for name, variant in variants.items():
        frames, checks = simulate(Params(behaviour=variant), environment, start_state)
        results[name] = {**score(frames, actual), "invariants": checks}
        mean = frames.groupby("day")[["staking_ratio", "validator_count", "validator_stake_avax", "delegated_stake_avax", "supply_avax"]].mean()
        daily.append(mean.add_prefix(f"{name}_"))
    persistence = actual.assign(
        staking_ratio=float(actual["staking_ratio"].iloc[0]), validator_count=float(actual["validator_count"].iloc[0]),
    )
    ok = actual["complete"].to_numpy()
    results["benchmark_persistence"] = {
        "staking_ratio": fit_measures(persistence["staking_ratio"].to_numpy(), np.where(ok, actual["staking_ratio"], np.nan), 100.0)
        | {"note": "a constant series has no correlation or direction; only rmse and mean_error apply"},
        "validator_count": fit_measures(persistence["validator_count"].to_numpy(), np.where(ok, actual["validator_count"], np.nan))
        | {"note": "a constant series has no correlation or direction; only rmse and mean_error apply"},
    }

    out_dir = ROOT / "data" / "runs" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    table = pd.concat(daily, axis=1).reset_index()
    table.insert(1, "date", actual["date"].astype(str).to_numpy())
    table["observed_staking_ratio"] = actual["staking_ratio"].to_numpy()
    table["observed_validator_count"] = actual["validator_count"].to_numpy()
    table["observed_complete"] = actual["complete"].to_numpy()
    daily_path = out_dir / "daily.csv"
    table.to_csv(daily_path, index=False, float_format="%.10g")
    results_doc = {
        "run_id": args.run_id, "status": "v0, unreviewed", "window": [START, END], "seeds": list(SEEDS),
        "targets": TARGETS, "incomplete_days_excluded": int((~actual["complete"]).sum()), **results,
    }
    _write_json(out_dir / "results.json", results_doc)
    behaviour_bytes = Path(args.behaviour).read_bytes()
    manifest = {
        "run_id": args.run_id,
        "status": "v0, unreviewed",
        "written_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": "uv run python -m avalanche_research.sim.backtest",
        "code_revision": {"commit": _git("rev-parse", "HEAD"), "source_changed": bool(_git("status", "--porcelain", "--", "src"))},
        "inputs": {name: {"dataset_id": selected[name]["dataset_id"], "run": selected[name]["run"]} for name in INPUT_VIEWS},
        "behaviour": {"path": f"data/model/{Path(args.behaviour).name}", "sha256": sha256(behaviour_bytes),
                      "version": behaviour.version, "generated_at": behaviour.raw.get("generated_at")},
        "params": "sim.params.Params() mainnet defaults, mechanism linear",
        "variants": {"primary": "every point estimate in the behaviour file",
                     "unidentified_zero": f"{', '.join(UNIDENTIFIED)} set to 0"},
        "seeds": list(SEEDS),
        "initial_state": f"sim.state.observed_state(con, '{START}')",
        "scenario": f"sim.scenario.observed(con, '{START}', {DAYS})",
        "wall_seconds": time.perf_counter() - started,
        "files": {path.name: sha256(path.read_bytes()) for path in (daily_path, out_dir / "results.json")},
    }
    _write_json(out_dir / "manifest.json", manifest)
    return results_doc


if __name__ == "__main__":
    document = main()
    for name in ("primary", "unidentified_zero"):
        for series in ("staking_ratio", "validator_count"):
            item = document[name][series]
            print(name, series, {key: item[key] for key in ("pearson_r", "rmse", "direction_accuracy", "phase_lag_days", "pass")})
