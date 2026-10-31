"""Run a small paired development experiment using the delivered pre-boundary inputs.

    uv run --frozen --group model --group notebook python scripts/first_experiment.py --output OUTPUT
    uv run --frozen --group model --group notebook python scripts/first_experiment.py --output OUTPUT --check

The released v0.8.0 estimator fits this example's validator-only history, then runs
four paired 30-day paths by default. The counterfactual moves an ACP-285-style
ramp to November 2025. Response coefficients are declared assumptions. This is a
new worked example, not a replay of a historical report or a protected score.
Output is exclusive. A failed execution has no completed summary. Check mode
authenticates inputs and outputs and recalculates summaries without simulation.
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
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
EXAMPLE = PROJECT / "examples/first-experiment"
ORIGIN = "2025-11-18"
CUTOFF = "2025-11-18 23:59:59"
INPUTS = {
    "validators.parquet": "c84e2e9ba33cb1178bcc66d2d3a3b093c023dd8d8c3609868ea51b4fdc6e7d31",
    "counter.csv": "f1bd24ba14895684d78b57e0c05c753a7a47268e898eff263ed8bea282f2ae5a",
}
INPUT_MANIFEST_SHA256 = "782f3cbdea62214c8ce046d52d9ad2778eb55efa11529c1ed1377e2fcce06458"
CASES = ("baseline", "ramp_neutral", "candidate")
VARIABLES = ("active_validators", "active_validator_stake_navax", "supply_navax", "issued_navax")
DRAW_COLUMNS = (
    "renewal.intercept", "renewal.tenure_2", "renewal.tenure_3_6", "renewal.tenure_7_9", "renewal.tenure_10_plus",
    "renewal.after_return", "renewal.days_21_40", "renewal.days_41_100", "renewal.days_over_100",
    "renewal.stake_2k_100k", "renewal.stake_100k_1m", "renewal.stake_over_1m", "renewal.node_record",
    "renewal.node_prior_strength", "renewal.node_prior_share", "returns.intercept", "returns.days_15_30",
    "returns.days_31_60", "returns.days_61_90", "returns.days_91_180", "returns.days_181_365",
    "returns.stake_mid", "returns.stake_large", "returns.returned_before", "returns.first_only",
    "arrivals.mean_per_day", "arrivals.dispersion", "renewal_shift", "resample_seed",
)
METRICS = (
    "baseline_promised_rewards_avax", "candidate_promised_rewards_avax", "rewards_saved_avax",
    "baseline_final_stake_avax", "candidate_final_stake_avax", "stake_retained_ratio",
)
MODEL_CLASS = "avalanche_research.model.stake_lifecycle.StakeLifecycle"
CONTROLS = {"neutral_response_stake_paths_equal": True, "protocol_counter_conservation": True,
            "paired_seed_and_parameter_rows": True}
# Declared before freezing the worked result. AVAX comparisons allow 1,000 nAVAX
# absolute or 1e-8 relative numerical differences across supported fit runtimes.
REL_TOL, ABS_TOL = 1e-8, 1e-6
TOLERANCE = {"relative": REL_TOL, "absolute_avax": ABS_TOL, "absolute_ratio": 1e-10}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def read_json(path):
    def reject(value):
        raise ValueError(f"nonfinite JSON constant: {value}")
    return json.loads(path.read_bytes(), parse_constant=reject)


def configuration(path):
    return validate_configuration(read_json(path))


def validate_configuration(value):
    default = read_json(EXAMPLE / "config.json")
    require(set(value) == set(default), "configuration fields differ from the supported schema")
    for key in ("schema", "origin", "activation", "counter_observed_at_utc", "counter_basis"):
        require(value[key] == default[key], f"fixed example configuration changed: {key}")
    require(value["origin"] == ORIGIN, "only the delivered pre-boundary origin is supported")
    for key, low, high in (("runs", 2, 8), ("timesteps", 1, 60), ("seed", 0, 2**32 - 1),
                           ("draw_seed", 0, 2**32 - 1), ("ramp_days", 1, 90)):
        require(type(value[key]) is int and low <= value[key] <= high, f"{key} must be an integer in [{low}, {high}]")
    for key, low, high in (("renewal_response", -2, 2), ("entry_response", -2, 2), ("target_min_rate", 0, 0.12)):
        require(type(value[key]) in (int, float) and math.isfinite(value[key]) and low <= value[key] <= high,
                f"{key} must be finite and in [{low}, {high}]")
    return value


def authenticate_inputs():
    import duckdb

    records = {}
    manifest = (EXAMPLE / "input-manifest.json").read_bytes()
    require(sha(manifest) == INPUT_MANIFEST_SHA256, "changed input manifest")
    records["input-manifest.json"] = {"sha256": INPUT_MANIFEST_SHA256, "bytes": len(manifest)}
    for name, expected in INPUTS.items():
        path = EXAMPLE / "inputs" / name
        require(path.is_file() and not path.is_symlink(), f"missing or symlinked example input: {name}")
        body = path.read_bytes()
        require(sha(body) == expected, f"changed input: {name}")
        records[name] = {"sha256": expected, "bytes": len(body)}
    periods = EXAMPLE / "inputs/validators.parquet"
    with duckdb.connect() as db:
        db.execute("SET threads=1")
        schema = db.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(periods)]).fetchall()
        expected = ["transaction_hash", "role", "node_id", "accepted_at", "start_time", "end_time",
                    "stake_navax", "supply_before_navax"]
        require([r[0] for r in schema] == expected, "snapshot columns differ")
        count, unique, invalid, pending = db.execute(
            "SELECT count(*),count(DISTINCT transaction_hash),count(*) FILTER(WHERE role!='validator' "
            "OR transaction_hash IS NULL OR node_id IS NULL OR accepted_at IS NULL OR start_time IS NULL "
            "OR end_time IS NULL OR stake_navax IS NULL OR accepted_at>CAST(? AS TIMESTAMP) "
            "OR end_time<=start_time OR start_time<accepted_at),count(*) FILTER(WHERE start_time>CAST(? AS TIMESTAMP)) "
            "FROM read_parquet(?)", [CUTOFF, CUTOFF, str(periods)],
        ).fetchone()
        require(count == unique == 52934 and invalid == 0 and pending == 0, "snapshot row, key or information-cut checks failed")
    with (EXAMPLE / "inputs/counter.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == 1 and rows[0]["start_time"] == "2025-11-18 23:56:46"
            and rows[0]["accepted_at"] == rows[0]["start_time"], "counter observation clock differs")
    require(int(rows[0]["supply_before_navax"]) == 465370216397635557, "counter value differs")
    return records, int(rows[0]["supply_before_navax"])


def csv_bytes(rows):
    require(bool(rows), "cannot write an empty table")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def read_daily(body, design):
    rows = list(csv.DictReader(io.StringIO(body.decode())))
    expected = {(case, run, day) for case in CASES for run in range(1, design["runs"] + 1)
                for day in range(design["timesteps"] + 1)}
    keys = []
    for row in rows:
        require(set(row) == {"case", "run", "day", *VARIABLES}, "daily columns differ")
        for key in ("run", "day", *VARIABLES):
            row[key] = int(row[key])
        keys.append((row["case"], row["run"], row["day"]))
        require(all(row[key] >= 0 for key in VARIABLES), "negative state or reward quantity")
    require(len(keys) == len(expected) and set(keys) == expected, "daily keys are missing, repeated or unexpected")
    return rows


def check_draws(body, runs):
    """Run r consumes the complete finite parameter row at position r - 1."""
    reader = csv.DictReader(io.StringIO(body.decode()))
    require(reader.fieldnames == list(DRAW_COLUMNS), "parameter draw columns differ from released v0.8.0 schema")
    rows = list(reader)
    require(len(rows) == runs, "parameter draw rows do not cover exactly the configured runs")
    for row in rows:
        require(set(row) == set(DRAW_COLUMNS) and all(value is not None for value in row.values()),
                "parameter draw row has missing or extra cells")
        try:
            finite = all(math.isfinite(float(value)) for value in row.values())
        except (ValueError, TypeError) as error:
            raise ValueError("parameter draw values must be finite numbers") from error
        require(finite, "parameter draw values must be finite numbers")
        try:
            seed = int(row["resample_seed"])
        except ValueError as error:
            raise ValueError("parameter draw resample seeds must be nonnegative int64 values") from error
        require(str(seed) == row["resample_seed"] and 0 <= seed < 2**63,
                "parameter draw resample seeds must be nonnegative int64 values")


def comparison(daily, design):
    indexed = {(row["case"], row["run"], row["day"]): row for row in daily}
    pairs = []
    for run in range(1, design["runs"] + 1):
        totals = {case: sum(indexed[case, run, day]["issued_navax"]
                           for day in range(1, design["timesteps"] + 1)) / 1e9 for case in CASES}
        ends = {case: indexed[case, run, design["timesteps"]]["active_validator_stake_navax"] / 1e9 for case in CASES}
        neutral_equal = all(indexed["baseline", run, day][key] == indexed["ramp_neutral", run, day][key]
                            for day in range(design["timesteps"] + 1)
                            for key in ("active_validators", "active_validator_stake_navax"))
        require(neutral_equal, "neutral-response paired stake control failed")
        for case in CASES:
            start = indexed[case, run, 0]["supply_navax"]
            for day in range(1, design["timesteps"] + 1):
                today, yesterday = indexed[case, run, day], indexed[case, run, day - 1]
                require(today["supply_navax"] - yesterday["supply_navax"] == today["issued_navax"],
                        "protocol-counter conservation failed")
            require(start == 465370216397635557, "configured starting counter differs")
        pair = {"run": run, "baseline_promised_rewards_avax": totals["baseline"],
                "candidate_promised_rewards_avax": totals["candidate"],
                "rewards_saved_avax": totals["baseline"] - totals["candidate"],
                "baseline_final_stake_avax": ends["baseline"], "candidate_final_stake_avax": ends["candidate"],
                "stake_retained_ratio": ends["candidate"] / ends["baseline"], "neutral_stake_path_equal": neutral_equal}
        require(all(math.isfinite(pair[key]) for key in METRICS), "nonfinite comparison")
        pairs.append(pair)
    metrics = {key: math.fsum(pair[key] for pair in pairs) / len(pairs) for key in METRICS}
    return pairs, metrics


def compare_expected(pairs, metrics, design):
    if design != read_json(EXAMPLE / "config.json"):
        return "custom_configuration_no_frozen_expected_result"
    path = EXAMPLE / "expected.json"
    require(path.is_file(), "missing frozen expected result")
    expected = read_json(path)
    require(expected["design"] == design and expected["pair_count"] == len(pairs), "expected design differs")
    require(expected["tolerance"] == TOLERANCE, "expected tolerance differs")
    require(len(expected["pairs"]) == len(pairs), "expected pair count differs")
    for actual, target in [(metrics, expected["metrics"]), *zip(pairs, expected["pairs"])]:
        require(set(actual) == set(target), "expected comparison fields differ")
        for key, value in target.items():
            if key in ("run", "neutral_stake_path_equal"):
                require(actual[key] == value, f"expected pair identity/control differs: {key}")
            else:
                absolute = TOLERANCE["absolute_ratio"] if key == "stake_retained_ratio" else ABS_TOL
                require(math.isclose(actual[key], value, rel_tol=REL_TOL, abs_tol=absolute),
                        f"expected numerical result differs: {key}")
    return "matches_frozen_example_with_declared_tolerance"


def figure_html(daily, design):
    from bokeh.embed import file_html
    from bokeh.plotting import figure
    from bokeh.resources import INLINE

    plot = figure(title="Cumulative validator reward promises: hypothetical early ramp", width=900, height=460,
                  x_axis_label=f"Days after {ORIGIN}", y_axis_label="Promised rewards (AVAX, mean)")
    for case, color, label in (("baseline", "#2563eb", "Historical chain formula"),
                               ("ramp_neutral", "#64748b", "Early ramp, neutral response"),
                               ("candidate", "#d97706", "Early ramp, assumed response")):
        total = 0
        values = []
        for day in range(design["timesteps"] + 1):
            total += sum(row["issued_navax"] for row in daily if row["case"] == case and row["day"] == day)
            values.append(total / design["runs"] / 1e9)
        plot.line(list(range(len(values))), values, color=color, line_width=3, legend_label=label)
    plot.legend.location = "top_left"
    return file_html(plot, INLINE, title="First staking experiment").encode()


def source_hashes():
    files = {"scripts/first_experiment.py": sha(Path(__file__).read_bytes())}
    for name, module in tuple(sys.modules.items()):
        if name == "avalanche_research" or name.startswith("avalanche_research."):
            path = Path(module.__file__).resolve()
            require(path.is_relative_to(PROJECT / "src"), f"project module loaded outside checkout: {name}")
            files[path.relative_to(PROJECT).as_posix()] = sha(path.read_bytes())
    return dict(sorted(files.items()))


def execute(design):
    from avalanche_research.mechanisms import ACP285Ramp, ChainReward
    from avalanche_research.model import MODEL_VERSION, RELEASED_MODEL
    from avalanche_research.model.engine import run
    from avalanche_research.model.variants import VARIANTS

    records, counter = authenticate_inputs()
    require(MODEL_VERSION == "0.8.0" and RELEASED_MODEL == "v0.8.0", "worked example requires the released v0.8.0 model")
    started = time.perf_counter()
    prepared = VARIANTS[RELEASED_MODEL].prepare(str(EXAMPLE / "inputs/validators.parquet"), date.fromisoformat(ORIGIN),
                                             "first-experiment-2025-11-18", draws=design["runs"], draw_seed=design["draw_seed"])
    # The estimator's validator-only query would use the last validator counter.
    # Use the separately frozen observation immediately before the 23:56:46
    # commitment. It predates the cutoff by 193 seconds and is not asserted to
    # be a complete end-of-day counter.
    prepared.inputs["supply0_navax"] = counter
    prepared_seconds = time.perf_counter() - started
    rows, specifications = [], {}
    for case in CASES:
        ramp = ACP285Ramp(activation=datetime.fromisoformat(design["activation"]),
                          target_min_rate=design["target_min_rate"], ramp_days=design["ramp_days"])
        model = VARIANTS[RELEASED_MODEL].simulation(prepared, seed=design["seed"], timesteps=design["timesteps"],
                                                   runs=design["runs"], draws=prepared.draws)
        model = model.with_settings(mechanism=ChainReward() if case == "baseline" else ramp,
                                    renewal_response=design["renewal_response"] if case == "candidate" else 0.0,
                                    entry_response=design["entry_response"] if case == "candidate" else 0.0)
        specifications[case] = model.specification_hash()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            table = run(model)
        selected = table[table.variable.isin(VARIABLES)]
        wide = selected.pivot(index=["run", "timestep"], columns="variable", values="value").reset_index()
        rows.extend({"case": case, "run": int(row["run"]), "day": int(row["timestep"]),
                     **{key: int(row[key]) for key in VARIABLES}} for row in wide.to_dict("records"))
    return rows, records, {"version": MODEL_VERSION, "variant": RELEASED_MODEL,
                           "class": MODEL_CLASS,
                           "specification_hashes": specifications}, prepared.draws.to_csv(index=False).encode(), {
                               "prepare_seconds": round(prepared_seconds, 4),
                               "fit_and_simulation_seconds": round(time.perf_counter() - started, 4)}


def check(output):
    require((output / "summary.json").is_file() and not (output / "summary.json").is_symlink(), "missing complete result summary")
    summary = read_json(output / "summary.json")
    require(summary["schema"] == "first-experiment-result/v1" and summary["status"] == "complete", "incomplete result")
    design = validate_configuration(summary["design"])
    inputs, _ = authenticate_inputs()
    require(summary["inputs"] == inputs, "result input bindings differ")
    require(summary["pair_count"] == design["runs"], "result pair count differs")
    require(summary["model"]["version"] == "0.8.0" and summary["model"]["variant"] == "v0.8.0"
            and summary["model"]["class"] == MODEL_CLASS, "result model identity differs")
    require(summary["controls"] == CONTROLS and summary["tolerance"] == TOLERANCE,
            "result controls or declared tolerance differ")
    expected_files = {"summary.json", "configuration.json", "daily.csv", "comparison.csv", "figure.html", "parameter-draws.csv"}
    require({p.name for p in output.iterdir()} == expected_files, "result is missing files or contains unexpected entries")
    for name, record in summary["artifacts"].items():
        path = output / name
        require(name in expected_files - {"summary.json"} and path.is_file() and not path.is_symlink(), "unsafe result artifact")
        body = path.read_bytes()
        require(sha(body) == record["sha256"] and len(body) == record["bytes"], f"changed result artifact: {name}")
    require(set(summary["artifacts"]) == expected_files - {"summary.json"}, "result artifact inventory differs")
    require(read_json(output / "configuration.json") == design, "saved configuration differs")
    for name, expected in summary["source_sha256"].items():
        relative = Path(name)
        path = (PROJECT / relative).resolve()
        require(not relative.is_absolute() and ".." not in relative.parts and path.is_relative_to(PROJECT), "unsafe source path")
        require(sha(path.read_bytes()) == expected, f"changed execution source: {name}")
    require("scripts/first_experiment.py" in summary["source_sha256"], "missing driver binding")
    check_draws((output / "parameter-draws.csv").read_bytes(), design["runs"])
    daily = read_daily((output / "daily.csv").read_bytes(), design)
    pairs, metrics = comparison(daily, design)
    require((output / "comparison.csv").read_bytes() == csv_bytes(pairs), "comparison does not follow daily data")
    require(summary["metrics"] == metrics, "summary metrics do not follow paired comparisons")
    require(summary["expected_result"] == compare_expected(pairs, metrics, design), "expected-result status differs")
    return summary


def run(output, config):
    design = configuration(config)
    authenticate_inputs()
    require(not output.exists(), "output must be a new directory")
    output.mkdir(parents=True, exist_ok=False)
    daily, inputs, model, draws, timing = execute(design)
    daily_body = csv_bytes(daily)
    daily = read_daily(daily_body, design)
    pairs, metrics = comparison(daily, design)
    expected_status = compare_expected(pairs, metrics, design)
    artifacts = {"configuration.json": canonical(design), "daily.csv": daily_body,
                 "comparison.csv": csv_bytes(pairs), "figure.html": figure_html(daily, design), "parameter-draws.csv": draws}
    for name, body in artifacts.items():
        (output / name).write_bytes(body)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip()
    summary = {"schema": "first-experiment-result/v1", "status": "complete", "design": design,
               "model": model, "inputs": inputs, "pair_count": design["runs"], "metrics": metrics,
               "observation_scheme": "arithmetic means of per-pair summaries; ratio is mean of per-pair candidate/baseline final stake",
               "scope": "new simulated validator-own-stake experiment; pre-boundary fitting only; no observed post-origin outcomes",
               "reward_measure": "sum of full promised rewards for commitments begun during the horizon, not rewards paid within it",
               "controls": CONTROLS,
               "expected_result": expected_status, "tolerance": TOLERANCE,
               "artifacts": {name: {"sha256": sha(body), "bytes": len(body)} for name, body in artifacts.items()},
               "source_sha256": source_hashes(), "checkout_commit": commit, "timing": timing,
               "environment": {"python": platform.python_version(), **{name: importlib.metadata.version(name)
                   for name in ("numpy", "scipy", "pandas", "cadCAD", "param", "duckdb", "bokeh")}}}
    (output / "summary.json").write_bytes(canonical(summary))
    try:
        return check(output)
    except Exception:
        (output / "summary.json").unlink()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=EXAMPLE / "config.json")
    parser.add_argument("--check", action="store_true", help="Verify complete results without fitting or simulation")
    args = parser.parse_args()
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    sys.path.insert(0, str(PROJECT / "src"))
    try:
        summary = check(args.output) if args.check else run(args.output, args.config)
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"FAIL | first experiment | {error}\n")
    print(json.dumps({"status": "pass", "output": str(args.output), "pair_count": summary["pair_count"],
                      "metrics": summary["metrics"], "expected_result": summary["expected_result"]}, sort_keys=True))


if __name__ == "__main__":
    main()
