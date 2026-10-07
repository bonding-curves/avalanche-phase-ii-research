#!/usr/bin/env python3
"""Model runs behind the experiment charts of the research report on staking model v0.7.

    uv run --group notebook python scripts/model_v07_report_runs.py OUT_DIR

The runs use the model exactly as tagged. The script exports tag ``model-v0.7.0`` with ``git archive`` to a temporary
folder and runs itself again with that folder's ``src`` first on the Python path, so every random draw matches the
tagged code and not later changes on ``main``. The packages come from the current environment.

Inputs are the two runs pinned in ``data/pins/p2-model-v0.8.json``: ``staking-periods-2026-09-30`` and
``avax-monetary-daily-2026-09-30``. Each is checked against its pin before use. Model inputs are measured only from
staking periods started by each origin, every origin is before the held-back period that starts 2025-11-19 16:00 UTC
(the model refuses any later origin), and every actual value comes from days before that boundary.

Day ``t`` of run ``r`` draws from a random stream seeded by the base seed, ``r`` and ``t``. Every run here uses base seed
0 and 20 runs, as the forecasts and the design sweep of 2 October 2026 did, so designs and settings compared within one
origin share the same random draws.

Writes four result tables with readable column names, and a receipt:

    fan.csv           Daily validator stake and active validators from Banff, Durango, Etna and Fortuna, 180 days:
                      percentiles of 20 runs beside the chain's actual value. fan-runs.csv holds every run's path.
    spread.csv        Each run's validator stake and active validators 90 days after each of the 19 development
                      origins, with the actual value where it falls before the held-back period.
    designs.csv       Five reward designs at three response strengths from Fortuna: validators after 180 days and
                      AVAX issued, with the chain's actual validator count 180 days after Fortuna.
    tornado.csv       One setting at a time moved from the Fortuna base, for the chain before ACP-285 and for
                      ACP-285 at 7.5%: change in validators after 180 days and in AVAX issued.
    model-v07-report-runs.json   The tag and its commit, the pinned runs with their sha256, seeds, settings,
                      the specification hash of every simulation, run times, and the sha256 of every output.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time as clock
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

TAG = "model-v0.7.0"
REPO = Path(__file__).resolve().parents[1]
PIN = REPO / "data" / "pins" / "p2-model-v0.8.json"
RUNS_ROOT = REPO / "data" / "runs"
PERIODS = ("derived.staking-periods", "staking-periods-2026-09-30")
LEDGER = ("derived.avax-monetary-daily", "avax-monetary-daily-2026-09-30")

SEED = 0
RUNS = 20
NAVAX_PER_MILLION_AVAX = 1e15
UPGRADES = {"Banff": date(2022, 10, 18), "Cortina": date(2023, 4, 25), "Durango": date(2024, 3, 6),
            "Etna": date(2024, 12, 16), "Fortuna": date(2025, 4, 8)}
QUARTERS = {f"{y}-{m:02d}-01": date(y, m, 1) for y in (2022, 2023, 2024, 2025) for m in (1, 4, 7, 10)
            if date(2022, 7, 1) <= date(y, m, 1) <= date(2025, 10, 1)}
FAN_ORIGINS = ("Banff", "Durango", "Etna", "Fortuna")
FAN_DAYS = 180
SPREAD_DAYS = 90
SWEEP_DAYS = 180
RESPONSES = (0.0, 0.1, 0.3)
BASE_RESPONSE = 0.1
CHAIN = "Chain before ACP-285"
ACP285 = "ACP-285 at 7.5%"
TENURE = "Tenure boost"
QUADRATIC = "Quadratic curve"
QUADRATIC_HELD = "Quadratic curve at the chain's issuance"
PERCENTILES = {"10th percentile": 0.1, "25th percentile": 0.25, "Median": 0.5, "75th percentile": 0.75,
               "90th percentile": 0.9}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# Outside the tag: export it and run again inside it -------------------------------------------------------------

def export_and_rerun(out: Path) -> None:
    """Export the tagged code to a temporary folder and run this script again with that code on the path."""
    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", f"{TAG}^{{commit}}"], check=True, capture_output=True,
                            text=True).stdout.strip()
    archive = subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar", TAG, "src", "data"], check=True,
                             capture_output=True).stdout
    with tempfile.TemporaryDirectory(prefix="model-v0.7.0-") as code:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(code, filter="data")
        env = {**os.environ, "PYTHONPATH": str(Path(code) / "src")}
        subprocess.run([sys.executable, str(Path(__file__).resolve()), str(out), "--code", code, "--commit", commit],
                       check=True, env=env)


# Inside the tag ------------------------------------------------------------------------------------------------

def check_inputs() -> dict:
    """Confirm the pinned runs are the ones named here and are unchanged, and return their records."""
    from avalanche_research import pins

    named = pins.runs(PIN)
    for dataset_id, run in (PERIODS, LEDGER):
        if named.get(dataset_id) != run:
            raise SystemExit(f"the pin names {named.get(dataset_id)} for {dataset_id}, not {run}")
    findings = pins.verify(PIN, RUNS_ROOT)
    if findings:
        raise SystemExit("pinned inputs changed: " + "; ".join(findings))
    pin = pins.read(PIN)
    return {"pin": pin["name"], "runs": {e["dataset_id"]: {"run": e["run"], "sha256": e["sha256"]} for e in pin["runs"]}}


def acp285(origin: date, label: str = ACP285):
    """ACP-285's ramp from 10% to 7.5% over 90 days, activated at 16:00 UTC on the origin day."""
    from avalanche_research.mechanisms import ACP285Ramp

    return ACP285Ramp(activation=datetime.combine(origin, datetime.min.time(), tzinfo=UTC).replace(hour=16), label=label)


def designs_for(origin: date, inputs: dict) -> list:
    """The five designs of the 2 October sweep. The equal-issuance quadratic is scaled on the commitments open at the
    origin, each priced as starting at noon UTC the day after it."""
    from avalanche_research.mechanisms import ChainReward, QuadraticReward, TenureBoost

    start = datetime.combine(origin + timedelta(days=1), datetime.min.time(), tzinfo=UTC).replace(hour=12)
    stakes = pd.DataFrame({"stake_navax": inputs["initial_stakes"], "start": start,
                           "completed_periods": inputs["initial_periods_done"],
                           "duration_seconds": np.clip(inputs["initial_days_left"], 1, 365) * 86_400})
    held = QuadraticReward().at_equal_issuance(stakes, inputs["supply0_navax"])
    held.label = QUADRATIC_HELD
    return [ChainReward(label=CHAIN), acp285(origin), TenureBoost(label=TENURE), QuadraticReward(label=QUADRATIC), held]


def percentile_frame(table: pd.DataFrame) -> pd.DataFrame:
    """Percentiles of the runs by timestep and variable."""
    grouped = table.groupby(["timestep", "variable"]).value
    return pd.DataFrame({name: grouped.quantile(q) for name, q in PERCENTILES.items()}).reset_index()


def run_fan(periods: str, actual: pd.DataFrame, specs: list) -> tuple[pd.DataFrame, pd.DataFrame]:
    from avalanche_research.model.engine import run
    from avalanche_research.model.lifecycle import ValidatorLifecycle, origin_inputs

    wide_rows, run_rows = [], []
    for name in FAN_ORIGINS:
        origin = UPGRADES[name]
        model = ValidatorLifecycle(origin=origin, timesteps=FAN_DAYS, runs=RUNS, seed=SEED, inputs_source=PERIODS[1],
                                   **origin_inputs(periods, origin))
        specs.append({"experiment": "fan", "origin": name, "specification": model.specification_hash()})
        table = run(model)
        table = table[table.variable.isin(["active_validators", "active_validator_stake_navax"])].copy()
        table["value"] = table.value.astype(float)
        days = [origin + timedelta(days=t) for t in range(FAN_DAYS + 1)]
        truth = actual.loc[days]
        q = percentile_frame(table)
        stake = q[q.variable == "active_validator_stake_navax"].set_index("timestep")
        count = q[q.variable == "active_validators"].set_index("timestep")
        frame = pd.DataFrame({"Origin": name, "Origin date": origin.isoformat(), "Days after the origin": range(FAN_DAYS + 1),
                              "Date (UTC)": [d.isoformat() for d in days]})
        for label in PERCENTILES:
            frame[f"Validator stake, {label.lower()} (M AVAX)"] = (stake[label] / NAVAX_PER_MILLION_AVAX).round(4).to_numpy()
        frame["Validator stake, actual (M AVAX)"] = (truth.active_validator_stake_navax / NAVAX_PER_MILLION_AVAX).round(4).to_numpy()
        for label in PERCENTILES:
            frame[f"Active validators, {label.lower()}"] = count[label].round(2).to_numpy()
        frame["Active validators, actual"] = truth.active_validators.to_numpy()
        wide_rows.append(frame)
        paths = table.pivot_table(index=["run", "timestep"], columns="variable", values="value").reset_index()
        run_rows.append(pd.DataFrame({
            "Origin": name, "Run": paths.run, "Days after the origin": paths.timestep,
            "Validator stake (M AVAX)": (paths.active_validator_stake_navax / NAVAX_PER_MILLION_AVAX).round(4),
            "Active validators": paths.active_validators.astype(int)}))
    return pd.concat(wide_rows, ignore_index=True), pd.concat(run_rows, ignore_index=True)


def run_spread(periods: str, actual: pd.DataFrame, last_day: date, specs: list) -> pd.DataFrame:
    from avalanche_research.model.engine import run
    from avalanche_research.model.lifecycle import ValidatorLifecycle, origin_inputs

    frames = []
    for name, origin in {**UPGRADES, **QUARTERS}.items():
        model = ValidatorLifecycle(origin=origin, timesteps=SPREAD_DAYS, runs=RUNS, seed=SEED, inputs_source=PERIODS[1],
                                   **origin_inputs(periods, origin))
        specs.append({"experiment": "spread", "origin": name, "specification": model.specification_hash()})
        table = run(model)
        end = table[table.timestep == SPREAD_DAYS].pivot_table(index="run", columns="variable", values="value").reset_index()
        horizon = origin + timedelta(days=SPREAD_DAYS)
        seen = horizon <= last_day
        frames.append(pd.DataFrame({
            "Origin": name, "Origin date": origin.isoformat(),
            "Origin type": "Network upgrade" if name in UPGRADES else "Start of quarter", "Run": end.run.astype(int),
            "Validator stake after 90 days (M AVAX)": (end.active_validator_stake_navax.astype(float) / NAVAX_PER_MILLION_AVAX).round(4),
            "Active validators after 90 days": end.active_validators.astype(int),
            "Actual validator stake after 90 days (M AVAX)": round(float(actual.loc[horizon, "active_validator_stake_navax"]) / NAVAX_PER_MILLION_AVAX, 4) if seen else None,
            "Actual active validators after 90 days": int(actual.loc[horizon, "active_validators"]) if seen else None}))
    out = pd.concat(frames, ignore_index=True)
    out["Actual active validators after 90 days"] = out["Actual active validators after 90 days"].astype("Int64")
    return out.sort_values(["Origin date", "Run"]).reset_index(drop=True)


def sweep_summary(table: pd.DataFrame, days: int) -> pd.DataFrame:
    """Validators after ``days`` and AVAX issued in the run, by design and run."""
    last = table[(table.timestep == days) & (table.variable == "active_validators")]
    validators = last.groupby(["mechanism", "run"]).value.first().astype(float)
    issued = table[table.variable == "issued_navax"].groupby(["mechanism", "run"]).value.sum().astype(float) / NAVAX_PER_MILLION_AVAX
    return pd.DataFrame({"validators": validators, "issued": issued}).reset_index()


def run_designs(periods: str, actual: pd.DataFrame, specs: list) -> pd.DataFrame:
    from avalanche_research.model.engine import sweep
    from avalanche_research.model.lifecycle import ValidatorLifecycle, origin_inputs

    origin = UPGRADES["Fortuna"]
    inputs = origin_inputs(periods, origin)
    designs = designs_for(origin, inputs)
    model = ValidatorLifecycle(origin=origin, timesteps=SWEEP_DAYS, runs=RUNS, seed=SEED, inputs_source=PERIODS[1], **inputs)
    after = origin + timedelta(days=SWEEP_DAYS)
    on_chain = int(actual.loc[after, "active_validators"])
    rows = []
    for response in RESPONSES:
        table = sweep(model, {"mechanism": designs, "renewal_response": [response], "entry_response": [response]})
        specs.extend({"experiment": "designs", "response": response, "design": m, "specification": s}
                     for m, s in table[["mechanism", "specification"]].drop_duplicates().itertuples(index=False))
        per_run = sweep_summary(table, SWEEP_DAYS)
        chain = per_run[per_run.mechanism == CHAIN].set_index("run")
        for design in [d.label for d in designs]:
            part = per_run[per_run.mechanism == design].set_index("run")
            change = (part.validators - chain.validators) / chain.validators.mean() * 100
            rows.append({
                "Response strength": response, "Design": design,
                "Validators after 180 days, mean": round(part.validators.mean(), 2),
                "Validators after 180 days, 10th percentile": round(part.validators.quantile(0.1), 2),
                "Validators after 180 days, 90th percentile": round(part.validators.quantile(0.9), 2),
                "AVAX issued in 180 days (M)": round(part.issued.mean(), 4),
                f"Validator change from {CHAIN} (%)": round(change.mean(), 2),
                "Standard error of the change (%)": round(change.std(ddof=1) / np.sqrt(len(change)), 2),
                f"Issuance change from {CHAIN} (%)": round((part.issued.mean() / chain.issued.mean() - 1) * 100, 2),
                "Active validators on the chain 180 days after Fortuna": on_chain,
            })
    return pd.DataFrame(rows)


def run_tornado(periods: str, specs: list) -> tuple[pd.DataFrame, dict]:
    from avalanche_research.mechanisms import ChainReward
    from avalanche_research.model.engine import sweep
    from avalanche_research.model.lifecycle import ValidatorLifecycle, origin_inputs

    origin = UPGRADES["Fortuna"]
    inputs = origin_inputs(periods, origin)
    base = ValidatorLifecycle(origin=origin, timesteps=SWEEP_DAYS, runs=RUNS, seed=SEED, inputs_source=PERIODS[1],
                              renewal_response=BASE_RESPONSE, entry_response=BASE_RESPONSE, **inputs)
    p, rate = base.renewal_probability, base.entry_rate_per_day
    settings = [
        ("Renewal response", "renewal_response", BASE_RESPONSE, 0.0, 0.3),
        ("Entry response", "entry_response", BASE_RESPONSE, 0.0, 0.3),
        ("Renewal probability", "renewal_probability", p, p * 0.9, p * 1.1),
        ("New validators a day", "entry_rate_per_day", rate, rate * 0.9, rate * 1.1),
    ]
    designs = [ChainReward(label=CHAIN), acp285(origin)]

    def outcome(model) -> pd.DataFrame:
        table = sweep(model, {"mechanism": designs})
        specs.extend({"experiment": "tornado", "design": m, "specification": s, **{k: getattr(model, k) for _, k, *_ in settings}}
                     for m, s in table[["mechanism", "specification"]].drop_duplicates().itertuples(index=False))
        return sweep_summary(table, SWEEP_DAYS).groupby("mechanism")[["validators", "issued"]].mean()

    at_base = outcome(base)
    rows = []
    for label, key, middle, low, high in settings:
        lo, hi = outcome(base.with_settings(**{key: low})), outcome(base.with_settings(**{key: high}))
        for design in (CHAIN, ACP285):
            b = at_base.loc[design]
            rows.append({
                "Design": design, "Setting": label, "Base value": round(middle, 4), "Low value": round(low, 4),
                "High value": round(high, 4),
                "Validators after 180 days at base": round(b.validators, 2),
                "Validators at low (% from base)": round((lo.loc[design].validators / b.validators - 1) * 100, 2),
                "Validators at high (% from base)": round((hi.loc[design].validators / b.validators - 1) * 100, 2),
                "AVAX issued at base (M)": round(b.issued, 4),
                "Issuance at low (% from base)": round((lo.loc[design].issued / b.issued - 1) * 100, 2),
                "Issuance at high (% from base)": round((hi.loc[design].issued / b.issued - 1) * 100, 2),
            })
    base_settings = {"renewal_response": BASE_RESPONSE, "entry_response": BASE_RESPONSE, "renewal_probability": p,
                     "entry_rate_per_day": rate, "renewal_tenure": base.renewal_tenure}
    return pd.DataFrame(rows), base_settings


def ledger_check(ledger: str, actual: pd.DataFrame, days: list[date]) -> dict:
    """The replayed actual series against the recorded ledger on the days these results use."""
    import duckdb

    rows = duckdb.execute(
        "SELECT date_utc, complete, active_validators, active_validator_stake_wei::VARCHAR AS wei FROM read_parquet(?)",
        [ledger]).df()
    rows["date_utc"] = pd.to_datetime(rows.date_utc).dt.date
    rows = rows.set_index("date_utc").loc[sorted(set(days))]
    differ = [str(d) for d, r in rows.iterrows()
              if not r.complete or int(r.active_validators) != int(actual.loc[d, "active_validators"])
              or int(r.wei) != int(actual.loc[d, "active_validator_stake_navax"]) * 10**9]
    return {"days_compared": len(rows), "days_that_differ": differ}


def inside(out: Path, code: Path, commit: str) -> None:
    import avalanche_research
    from avalanche_research import datasets
    from avalanche_research.model import MODEL_VERSION
    from avalanche_research.model.lifecycle import actual_path
    from avalanche_research.model.replay import LOCKBOX_FIRST_DAY, daily_events

    if not Path(avalanche_research.__file__).resolve().is_relative_to(code.resolve()) or MODEL_VERSION != "0.7.0":
        raise SystemExit(f"expected model 0.7.0 from the exported tag, found {MODEL_VERSION} at {avalanche_research.__file__}")
    out.mkdir(parents=True, exist_ok=True)
    inputs = check_inputs()
    periods = str(datasets.parquet_path(*PERIODS, root=RUNS_ROOT))
    ledger = str(datasets.parquet_path(*LEDGER, root=RUNS_ROOT))
    actual = actual_path(daily_events(periods)).set_index("date_utc")
    last_day = LOCKBOX_FIRST_DAY - timedelta(days=1)
    specs: list[dict] = []
    seconds = {}

    started = clock.perf_counter()
    fan, fan_runs = run_fan(periods, actual, specs)
    seconds["fan"] = round(clock.perf_counter() - started, 1)
    started = clock.perf_counter()
    spread = run_spread(periods, actual, last_day, specs)
    seconds["spread"] = round(clock.perf_counter() - started, 1)
    started = clock.perf_counter()
    designs = run_designs(periods, actual, specs)
    seconds["designs"] = round(clock.perf_counter() - started, 1)
    started = clock.perf_counter()
    tornado, tornado_base = run_tornado(periods, specs)
    seconds["tornado"] = round(clock.perf_counter() - started, 1)

    outputs = {"fan.csv": fan, "fan-runs.csv": fan_runs, "spread.csv": spread, "designs.csv": designs, "tornado.csv": tornado}
    for name, frame in outputs.items():
        frame.to_csv(out / name, index=False)
    fortuna_after = UPGRADES["Fortuna"] + timedelta(days=SWEEP_DAYS)
    checked_days = [pd.Timestamp(d).date() for d in fan["Date (UTC)"]] + [fortuna_after]
    receipt = {
        "script": "scripts/model_v07_report_runs.py",
        "model": {"version": MODEL_VERSION, "tag": TAG, "commit": commit},
        "inputs": inputs,
        "held_back_from": "2025-11-19T16:00:00Z",
        "actual_series": f"replay of {PERIODS[1]} through {last_day.isoformat()}, checked against {LEDGER[1]}",
        "actual_against_ledger": ledger_check(ledger, actual, checked_days),
        "seeds": {"base_seed": SEED, "runs": RUNS, "stream": "day t of run r draws from numpy default_rng([base seed, r, t])"},
        "settings": {
            "fan": {"origins": {n: UPGRADES[n].isoformat() for n in FAN_ORIGINS}, "days": FAN_DAYS,
                    "design": "the chain's reward", "responses": 0.0, "percentiles": list(PERCENTILES.values())},
            "spread": {"origins": {n: d.isoformat() for n, d in {**UPGRADES, **QUARTERS}.items()}, "days": SPREAD_DAYS,
                       "design": "the chain's reward", "responses": 0.0},
            "designs": {"origin": UPGRADES["Fortuna"].isoformat(), "days": SWEEP_DAYS, "responses": list(RESPONSES),
                        "designs": [CHAIN, ACP285, TENURE, QUADRATIC, QUADRATIC_HELD],
                        "renewal and entry responses": "set equal in each sweep",
                        "chain validators after 180 days": {"date": fortuna_after.isoformat(),
                                                            "active_validators": int(actual.loc[fortuna_after, "active_validators"])}},
            "tornado": {"origin": UPGRADES["Fortuna"].isoformat(), "days": SWEEP_DAYS, "designs": [CHAIN, ACP285],
                        "base": tornado_base, "low and high": "responses 0 and 0.3 one at a time with the other at 0.1; "
                        "renewal probability and new validators a day at 90% and 110% of the base"},
        },
        "specifications": specs,
        "run_seconds": seconds,
        "outputs": {name: sha256_file(out / name) for name in outputs},
    }
    (out / "model-v07-report-runs.json").write_text(json.dumps(receipt, indent=1, default=str) + "\n")
    print(json.dumps({"run_seconds": seconds, "outputs": list(outputs)}, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path, help="folder for the result tables and the receipt")
    parser.add_argument("--code", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--commit", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.code is None:
        export_and_rerun(args.out.resolve())
    else:
        inside(args.out, args.code, args.commit)


if __name__ == "__main__":
    main()
