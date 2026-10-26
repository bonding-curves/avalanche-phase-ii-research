"""Fixed-fit evaluation of the released validator model, with separate state and label clocks.

``score(token, *, fit_until, score_until)`` is the callable used by the one-shot script.
Dates are exclusive UTC cuts. Development calls use no token and cannot reach protected
support. Configuration under validation/lockbox remains draft until scientific review.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb
import numpy as np
import pandas as pd

from avalanche_research.core.clock import LOCKBOX_FIRST_DAY, LOCKBOX_START
from avalanche_research.core.hashing import canonical_bytes
from avalanche_research.core.lockbox import Unseal, require
from avalanche_research.model import evaluation as ev
from avalanche_research.model.engine import _digest, _plain, run
from avalanche_research.model.fitted_lifecycle import (
    decided_by_us,
    origin_state,
    renewal_inputs,
    validator_periods,
)
from avalanche_research.model.parts.base import DURATION_EDGES
from avalanche_research.model.variants import VARIANTS, Prepared

ROOT = Path(__file__).resolve().parents[3]
VARIABLES = {"active_validator_stake_navax": ("AVAX", 10**9), "active_validators": ("validators", 1)}
PROJECTION = ("role", "transaction_hash", "node_id", "accepted_at", "start_time", "end_time",
              "stake_navax", "supply_before_navax")


def _hash_file(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _json(value):
    """Strict JSON values, retaining undefined/infinite metrics as explicit nulls."""
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, np.ndarray)):
        return [_json(v) for v in value]
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return _json(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def request_window(fit_until: date, score_until: date, token: Unseal | None) -> tuple[date, datetime]:
    """Validate all requested support before reading any input file or constructing a fit."""
    if type(fit_until) is not date or type(score_until) is not date:
        raise ValueError("fit_until and score_until must be exclusive UTC dates")
    if not fit_until < score_until or fit_until > LOCKBOX_FIRST_DAY:
        raise ValueError("the fixed fit cut must precede scoring and may not enter the lockbox")
    end = datetime.combine(score_until, time(0), tzinfo=UTC)
    # Daily support excludes Helicon's partial day; event labels retain its exact end.
    if score_until == date(2026, 9, 22):
        end = end.replace(hour=15)
    require(end - timedelta(microseconds=1), token)
    return fit_until - timedelta(days=1), end


def monthly_origins(fit_origin: date, score_until: date, minimum_horizon: int) -> list[date]:
    last = score_until - timedelta(days=minimum_horizon + 1)
    start = (pd.Timestamp(fit_origin) + pd.offsets.MonthBegin(1)).date()
    return [fit_origin, *[x.date() for x in pd.date_range(start, last, freq="MS")]]


def verified_inputs(root: Path, pin_path: str) -> dict[str, Path]:
    """Verify declared immutable files and producer metadata, without selecting a newest run."""
    pin = json.loads((root / pin_path).read_text())
    if pin.get("schema_version") != "avalanche-pins/v1":
        raise ValueError("unsupported input pin schema")
    inputs = {}
    for item in pin["runs"]:
        if item["dataset_id"] in inputs:
            raise ValueError("a pin must name one run per dataset")
        folder = root / "data/runs" / item["run"] / "dataset"
        path = folder / item["parquet"]
        if path.stat().st_size != item["bytes"] or _hash_file(path) != item["sha256"]:
            raise ValueError(f"pinned bytes differ: {item['dataset_id']}")
        build, check = (json.loads((folder / name).read_text()) for name in ("build.json", "check.json"))
        if (build.get("dataset_id") != item["dataset_id"]
                or build.get("source_capture_id") != item["capture_id"] or check.get("status") != "pass"):
            raise ValueError(f"pinned producer metadata differs: {item['dataset_id']}")
        inputs[item["dataset_id"]] = path
    return inputs


def matching_training_slices(training: Path, scoring: Path, fit_origin: date) -> dict:
    """Compare keyed public schedules using exact integers/timestamps, including accepted future starts."""
    cutoff = decided_by_us(fit_origin)
    columns = ("role, transaction_hash, node_id, epoch_us(accepted_at), epoch_us(start_time), epoch_us(end_time), "
               f"stake_navax::VARCHAR, CASE WHEN start_time <= make_timestamp({cutoff}) "
               "THEN supply_before_navax::VARCHAR ELSE NULL END")
    sql = (f"SELECT {columns} FROM read_parquet(?) WHERE accepted_at <= make_timestamp(?) "
           "ORDER BY role, transaction_hash")
    # Each backend has an isolated spill directory, and projections run sequentially.
    # Do not hold two large independent sorts in DuckDB's shared default directory.
    def projection(path):
        digest, count, previous = hashlib.sha256(), 0, None
        with TemporaryDirectory(prefix="validator-slice-") as temporary, duckdb.connect(
            config={"temp_directory": temporary, "memory_limit": "512MB", "threads": 2},
        ) as connection:
            connection.execute(sql, [str(path), cutoff])
            while True:
                rows = connection.fetchmany(4096)
                if not rows:
                    break
                for row in rows:
                    key = row[0], row[1]
                    if row[1] is None or key == previous:
                        raise ValueError("training projection requires unique non-null role/transaction identities")
                    previous = key
                count += len(rows)
                digest.update(canonical_bytes(rows))
        return count, digest.hexdigest()

    count, digest = projection(training)
    identical_file = training.samefile(scoring)
    if not identical_file and projection(scoring) != (count, digest):
        raise ValueError("pre-fit public schedule slices differ between training and scoring runs")
    return {"status": "PASS", "rows": count, "columns": list(PROJECTION), "timestamp_unit": "UTC microseconds",
            "accepted_through_us": cutoff, "sha256": digest,
            "comparison": "same verified file and queried projection" if identical_file else "two independently queried projection digests",
            "digest_convention": "canonical JSON chunks of4096 sorted rows; native integer text, UTC microseconds"}



def validate_training_information(path: Path, fit_origin: date) -> dict:
    """Refuse fit-eligible rows whose public clock is missing or later than the frozen cut.

    Released estimators filter started commitments. Prove their acceptance clocks before
    invoking them rather than assuming the separate slice comparison establishes fitness.
    """
    cutoff = decided_by_us(fit_origin)
    invalid = duckdb.execute(
        "SELECT count(*) FROM read_parquet(?) WHERE "
        "(role='validator' AND (start_time <= make_timestamp(?) OR accepted_at <= make_timestamp(?)) AND "
        "(accepted_at IS NULL OR (start_time <= make_timestamp(?) AND accepted_at > make_timestamp(?)) "
        "OR transaction_hash IS NULL OR node_id IS NULL OR stake_navax IS NULL OR start_time IS NULL "
        "OR end_time IS NULL OR end_time <= start_time)) OR "
        "(start_time <= make_timestamp(?) AND supply_before_navax IS NOT NULL "
        "AND (accepted_at IS NULL OR accepted_at > make_timestamp(?)))",
        [str(path), *([cutoff] * 6)],
    ).fetchone()[0]
    if invalid:
        raise ValueError("fit-eligible schedules/counters lack public-at-fit information or required fields")
    return {"status": "PASS", "fit_origin": fit_origin.isoformat(), "accepted_through_us": cutoff}


def realized_daily(path: Path, score_until: date, token: Unseal | None = None) -> pd.DataFrame:
    """Only complete observed validator stocks before the exclusive daily end; no reward labels."""
    require(datetime.combine(score_until, time(0), tzinfo=UTC) - timedelta(microseconds=1), token)
    rows = duckdb.execute(
        "SELECT date_utc, complete, active_validator_stake_wei::VARCHAR, active_validators "
        "FROM read_parquet(?) WHERE date_utc < ? ORDER BY date_utc", [str(path), score_until],
    ).fetchall()
    if not rows or len({x[0] for x in rows}) != len(rows):
        raise ValueError("realized daily dates must be nonempty and unique")
    if any(not x[1] or x[2] is None or x[3] is None for x in rows):
        raise ValueError("realized daily stocks require complete, non-null observations")
    index = pd.DatetimeIndex([x[0] for x in rows])
    if not index.equals(pd.date_range(index[0], index[-1], freq="D")):
        raise ValueError("realized daily support has missing dates")
    values = pd.DataFrame({"active_validator_stake_navax": [int(x[2]) / 10**18 for x in rows],
                           "active_validators": [int(x[3]) for x in rows]}, index=index)
    if not np.isfinite(values.to_numpy()).all() or (values < 0).any().any():
        raise ValueError("realized stocks must be finite and nonnegative")
    return values


def frozen_fingerprint(prepared: Prepared) -> str:
    fixed = {k: (_digest(v) if isinstance(v, pd.DataFrame) else _plain(v)) for k, v in prepared.inputs.items()
             if k not in ("initial", "out_of_set", "scheduled", "supply0_navax", "origin")}
    fixed["draws"] = _digest(prepared.draws)
    return hashlib.sha256(canonical_bytes(_json(fixed))).hexdigest()


def at_origin(prepared: Prepared, state: dict, origin: date, fit_origin: date) -> Prepared:
    """Replace state only. Preserve source receipts, fitted tables, blocks and bootstrap rows."""
    allowed = ("initial", "out_of_set", "scheduled", "supply0_navax")
    return replace(prepared, inputs={**prepared.inputs, **{k: state[k] for k in allowed},
                                     "origin": origin, "stake_fit_origin": fit_origin})


def configured_fit_binding(specification: dict, fit_origin: date, *, required: bool) -> dict | None:
    """Validate the declared numerical identity before any input is opened.

    A Granite binding does not apply to an earlier development rehearsal cut.
    Protected scoring and the pre-marker preflight require an adopted matching binding.
    """
    binding = specification.get("frozen_fit")
    if binding is None:
        if required:
            raise ValueError("an adopted frozen fit binding is required")
        return None
    if (not isinstance(binding, dict) or not isinstance(binding.get("status"), str)
            or binding["status"] not in {"candidate", "adopted"}):
        raise ValueError("invalid frozen fit binding status")
    for key in ("fit_sha256", "draws_sha256", "artifact_manifest_sha256"):
        value = binding.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"frozen fit binding needs a SHA-256 for {key}")
    try:
        origin = date.fromisoformat(binding["fit_origin"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("frozen fit binding needs an ISO fit origin") from error
    if origin >= LOCKBOX_FIRST_DAY:
        raise ValueError("frozen fit binding origin must precede the protected daily boundary")
    if origin != fit_origin:
        if required:
            raise ValueError("frozen fit binding origin differs from the requested fit cut")
        return None
    if required and binding["status"] != "adopted":
        raise ValueError("an adopted frozen fit binding is required")
    return binding


def verify_frozen_fit(prepared: Prepared, fit_origin: date, binding: dict | None) -> dict:
    """Check exact reconstructed fit/draw bytes before any realized or later-state read."""
    if prepared.inputs["origin"] != fit_origin:
        raise ValueError("prepared fit origin differs from the numerical binding")
    if prepared.draws is None or len(prepared.draws) != 200:
        raise ValueError("frozen fit verification requires exactly 200 parameter draws")
    if not np.isfinite(prepared.draws.select_dtypes("number").to_numpy()).all():
        raise ValueError("frozen parameter draws must be finite")
    fingerprint = frozen_fingerprint(prepared)
    draws_sha = hashlib.sha256(canonical_bytes(_json(prepared.draws.to_dict("records")))).hexdigest()
    if binding is not None:
        if fingerprint != binding["fit_sha256"]:
            raise ValueError("reconstructed fit fingerprint differs from the frozen fit binding")
        if draws_sha != binding["draws_sha256"]:
            raise ValueError("reconstructed parameter draws differ from the frozen fit binding")
    return {"status": "UNBOUND_DEVELOPMENT_ONLY" if binding is None else "MATCH_" + binding["status"].upper(),
            "fit_origin": fit_origin.isoformat(), "fit_sha256": fingerprint, "draws_sha256": draws_sha,
            "artifact_manifest_sha256": None if binding is None else binding["artifact_manifest_sha256"],
            "artifact_manifest_check": "declared hash; artifact bytes are verified separately during package review"}


def cell_scores(draws, actual: float, series: pd.Series, origin: date, horizon: int) -> list[dict]:
    """Score one admitted case against every declared point and dressed benchmark."""
    scale, scale_reason = None, None
    try:
        scale = ev.mase_scale(series, origin)
    except ValueError as error:
        scale_reason = str(error)
    rows = []
    for name, function in {"model": lambda *_: float(np.mean(draws)), **ev.BENCHMARKS}.items():
        point, reason = None, scale_reason
        try:
            point = function(series, origin, horizon)
        except ValueError as error:
            reason = str(error)
        measured = scale is not None and point is not None
        row = {"forecast": name, "point": point, "mase": ev.scaled_error(point, actual, scale) if measured else None,
               "crps": (ev.crps_ensemble(draws, actual) if name == "model" else abs(point - actual)) / scale if measured else None,
               "undefined_reason": reason}
        if name == "model":
            row["draws"] = list(draws)
            if measured:
                row.update(ev.distribution_scores(draws, actual, scale))
        rows.append(row)
    for name in ("N1", "N2"):
        try:
            sample = ev.dressed(series, origin, horizon, rule=name)
            rows.append({"forecast": name + "d", "point": float(np.mean(sample)),
                         **(ev.distribution_scores(sample, actual, scale) if scale is not None else {"crps": None}),
                         "undefined_reason": scale_reason})
        except ValueError as error:
            rows.append({"forecast": name + "d", "point": None, "crps": None, "undefined_reason": str(error)})
    for row in rows:
        row.update(actual=actual, scale=scale, origin=origin, horizon_days=horizon,
                   status="undefined" if row.get("undefined_reason") else "measured")
    return rows


def primary_verdict(cells: list[dict], primary_variables: list[str], horizon: int = 90,
                    expected_origins: list[date] | None = None) -> tuple[str, list[dict]]:
    """Existing point-loss/significance rule, with undefined inference stated explicitly."""
    problems = []
    for variable in primary_variables:
        part = [x for x in cells if x["variable"] == variable and x["horizon_days"] == horizon]
        expected = set(expected_origins) if expected_origins is not None else {x["origin"] for x in part}
        for forecast in ("model", "N1", "N2", "N3"):
            origins = [x["origin"] for x in part if x["forecast"] == forecast]
            if len(origins) != len(set(origins)) or set(origins) != expected:
                problems.append(f"{variable}/{forecast}: duplicate or missing expected origin rows")
    if problems:
        return "INCONCLUSIVE", [{"variable": v, "benchmark": b, "origins": 0, "model_mase": None,
                                  "benchmark_mase": None, "dm": None, "undefined_reason": "; ".join(problems)}
                                 for v in primary_variables for b in ("N1", "N2", "N3")]
    comparisons, any_fail, all_pass = [], False, True
    for variable in primary_variables:
        part = [x for x in cells if x["variable"] == variable and x["horizon_days"] == horizon]
        for benchmark in ("N1", "N2", "N3"):
            by_forecast = {f: {x["origin"]: x for x in part if x["forecast"] == f} for f in ("model", benchmark)}
            origins = sorted(set(by_forecast["model"]) & set(by_forecast[benchmark]))
            model = [by_forecast["model"][o]["mase"] for o in origins]
            naive = [by_forecast[benchmark][o]["mase"] for o in origins]
            if not origins or any(x is None for x in model + naive):
                all_pass = False
                comparisons.append({"variable": variable, "benchmark": benchmark, "origins": len(origins),
                                    "model_mase": None, "benchmark_mase": None, "dm": None,
                                    "undefined_reason": "missing eligible cases or undefined per-case scaled loss"})
                continue
            point_better = bool(origins) and float(np.mean(model)) < float(np.mean(naive))
            test, reason = None, None
            overlap = ev.dm_horizon(horizon, origins)
            try:
                test = ev.diebold_mariano(model, naive, horizon=overlap)
            except ValueError as error:
                reason = str(error)
            any_fail |= bool(origins) and not point_better
            significant = test is not None and test["p_less"] < 0.05
            all_pass &= point_better and significant
            comparisons.append({"variable": variable, "benchmark": benchmark, "origins": len(origins),
                                "model_mase": float(np.mean(model)) if origins else None,
                                "benchmark_mase": float(np.mean(naive)) if origins else None,
                                "dm": test, "dm_horizon": overlap,
                                "undefined_reason": reason or ("no eligible cases" if not origins else None)})
    return "FAIL" if any_fail else "PASS" if all_pass and comparisons else "INCONCLUSIVE", comparisons


def contract_diagnostics(predicted, actual) -> dict:
    """Reported own-stake/count diagnostics; never relabel these as total bonded AVAX."""
    x, y = np.asarray(predicted, dtype=float), np.asarray(actual, dtype=float)
    if len(x) != len(y) or not len(x) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("diagnostics need finite, aligned daily paths")

    def correlation(a, b):
        return float(np.corrcoef(a, b)[0, 1]) if len(a) > 1 and np.ptp(a) and np.ptp(b) else None

    x7, y7 = x[7:] - x[:-7], y[7:] - y[:-7]
    lags = []
    for lag in range(-30, 31):
        a = x7[max(0, -lag):len(x7) - max(0, lag)]
        b = y7[max(0, lag):len(y7) - max(0, -lag)]
        r = correlation(a, b) if len(a) == len(b) else None
        if r is not None:
            lags.append((r, lag))
    return {"pearson_levels": correlation(x, y), "pearson_first_differences": correlation(np.diff(x), np.diff(y)),
            "rmse": float(np.sqrt(np.mean((x - y)**2))),
            "direction_7d": float(np.mean(np.sign(x7) == np.sign(y7))) if len(x7) else None,
            "phase_lag_days": max(lags, key=lambda z: (z[0], -abs(z[1])))[1] if lags else None,
            "undefined_reason": "constant or insufficient daily variation" if not np.ptp(x) or not np.ptp(y) or len(x) < 9 else None}


def distribution_comparisons(cells: list[dict]) -> list[dict]:
    """Supplementary CRPS skill and dependence-aware comparisons, never a replacement verdict."""
    results = []
    for variable, horizon in sorted({(x["variable"], x["horizon_days"]) for x in cells}):
        part = [x for x in cells if x["variable"] == variable and x["horizon_days"] == horizon]
        model_rows = [x for x in part if x["forecast"] == "model"]
        model = {x["origin"]: x["crps"] for x in model_rows}
        expected = {x["origin"] for x in part}
        for benchmark in ("N1d", "N2d"):
            naive_rows = [x for x in part if x["forecast"] == benchmark]
            naive = {x["origin"]: x["crps"] for x in naive_rows}
            origins = sorted(model)
            reason, test, skill, m, n = None, None, None, None, None
            overlap = ev.dm_horizon(horizon, origins)
            if (set(model) != expected or set(naive) != expected or len(model_rows) != len(model)
                    or len(naive_rows) != len(naive) or not origins
                    or any(model[o] is None or naive[o] is None for o in origins)):
                reason = "incomplete, duplicate or undefined per-case CRPS"
            else:
                a, b = [model[o] for o in origins], [naive[o] for o in origins]
                m, n = float(np.mean(a)), float(np.mean(b))
                skill = 1 - m / n if n != 0 else None
                try:
                    test = ev.diebold_mariano(a, b, horizon=overlap)
                except ValueError as error:
                    reason = str(error)
                if n == 0:
                    reason = "zero benchmark mean CRPS; skill undefined" + ("; " + reason if reason else "")
            results.append({"variable": variable, "horizon_days": horizon, "benchmark": benchmark,
                            "origins": len(origins), "model_crps": m, "benchmark_crps": n,
                            "skill": skill, "dm": test, "dm_horizon": overlap,
                            "undefined_reason": reason, "role": "supplementary"})
    return results


def binary_loss(probabilities, labels) -> dict:
    p, y = np.asarray(probabilities, dtype=float), np.asarray(labels, dtype=bool)
    if not len(y):
        return {"events": 0, "log_loss": None, "brier": None, "undefined_reason": "no matured eligible events"}
    if len(p) != len(y) or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("invalid binary predictive probabilities")
    q = np.where(y, p, 1 - p)
    return {"events": len(y), "log_loss": float(-np.log(q).mean()) if (q > 0).all() else None,
            "brier": float(np.mean((p - y)**2)),
            "undefined_reason": "infinite log loss: zero probability for observed outcome" if not (q > 0).all() else None}


def behaviour_table(prepared: Prepared, training: Path, scoring: Path, fit_origin: date,
                    event_start: datetime, event_end: datetime, token: Unseal | None) -> list[dict]:
    """Frozen point-block renewal and conditional return checks, with matured labels and fixed baselines.

    These event diagnostics do not decide the primary verdict. Parameter draws are represented
    in the system table; this table explicitly scores the frozen point behaviour blocks.
    """
    require(event_end - timedelta(microseconds=1), token)
    fit_us = decided_by_us(fit_origin)
    end_us, start_us = (int(x.timestamp()) * 1_000_000 for x in (event_end, event_start))
    source = validator_periods(str(scoring), end_us - 1, accepted_by_us=end_us - 1)
    history = validator_periods(str(training), fit_us, accepted_by_us=fit_us)
    day = 86_400_000_000
    table = []
    for target, maturity in (("renewal_7d", 7), ("return_8_90d_given_no_7d_renewal", 90)):
        def cohort(rows, lower, upper, maturity=maturity):
            eligible = rows[(rows["e"] >= lower) & (rows["e"] + maturity * day < upper)]
            eligible = eligible[eligible["next_s"].isna() | (eligible["next_s"] >= eligible["e"])]
            if maturity == 90:
                eligible = eligible[~eligible["renewed"]]
            labels = eligible["next_s"].notna() & (eligible["next_s"] <= eligible["e"] + maturity * day)
            return eligible, labels

        observed, labels = cohort(source, start_us, end_us)
        past, past_labels = cohort(history, fit_us - 365 * day, fit_us + 1)
        if maturity == 7:
            predicted = prepared.inputs["renewal"].probability(renewal_inputs(observed, node_record=False))
        else:
            survival = np.ones(len(observed))
            for age in range(8, 91):
                probability = prepared.inputs["returns"].probability({
                    "stake_navax": observed["stake_navax"].to_numpy(),
                    "days_since_end": np.full(len(observed), age),
                    "done": observed["done"].to_numpy() + 1, "returns": observed["returns"].to_numpy()})
                survival *= 1 - probability
            predicted = 1 - survival
        table.append({"target": target, "forecast": "model_point_blocks", "maturity_days": maturity,
                      **binary_loss(predicted, labels)})
        if len(past):
            prior = float(past_labels.mean())
            grouped = past.assign(label=past_labels.to_numpy()).groupby("node_id")["label"]
            for name, values in (("prior", np.full(len(observed), prior)),
                                 ("history", observed.node_id.map(grouped.mean()).fillna(prior).to_numpy()),
                                 ("persistence", observed.node_id.map(grouped.last()).fillna(prior).to_numpy())):
                table.append({"target": target, "forecast": name, "maturity_days": maturity, **binary_loss(values, labels)})
        else:
            table.extend({"target": target, "forecast": name, "events": 0, "log_loss": None, "brier": None,
                          "undefined_reason": "no fully matured baseline cohort before frozen fit"}
                         for name in ("prior", "history", "persistence"))
    table.append({"target": "leave_365d", "forecast": "model", "events": 0,
                  "undefined_reason": "deferred by protocol: window endings lack 365-day follow-up at window end"})
    moves = prepared.inputs["moves"]
    eligible = source[(source["e"] >= start_us) & source["next_s"].notna()
                      & (source["next_s"] >= source["e"]) & (source["next_s"] < end_us)]
    labels = np.maximum(1, np.rint((eligible["next_e"] - eligible["next_s"]) / day)).astype(np.int64)
    previous_bins = np.digitize(moves["previous_days"], DURATION_EDGES, right=True)
    node_durations = history[history["next_s"].notna() & (history["next_s"] >= history["e"])].copy()
    node_durations["label"] = np.maximum(1, np.rint((node_durations.next_e - node_durations.next_s) / day))
    node_groups = node_durations.groupby("node_id")["label"]
    duration_losses = {name: [] for name in ("model_point_tables", "prior", "history", "persistence")}
    for (_, row), label in zip(eligible.iterrows(), labels, strict=True):
        mask = previous_bins == np.digitize(row["days"], DURATION_EDGES, right=True)
        conditional = moves.loc[mask if mask.any() else np.ones(len(moves), bool), "next_days"].to_numpy()
        pooled = moves["next_days"].to_numpy()
        individual = node_groups.get_group(row.node_id).to_numpy() if row.node_id in node_groups.groups else pooled
        for name, sample in (("model_point_tables", conditional), ("prior", pooled),
                             ("history", individual), ("persistence", individual[-1:])):
            # Exact empirical categorical probabilities, without smoothing an impossible label.
            probability = float(np.mean(sample == label))
            squared_mass = sum((n / len(sample))**2 for n in np.unique(sample, return_counts=True)[1])
            duration_losses[name].append((probability, float(squared_mass - 2 * probability + 1)))
    for name, losses in duration_losses.items():
        probabilities = np.asarray([x[0] for x in losses])
        finite = len(losses) > 0 and (probabilities > 0).all()
        table.append({"target": "next_duration_days", "forecast": name, "events": len(losses),
                      "log_loss": float(-np.log(probabilities).mean()) if finite else None,
                      "brier": float(np.mean([x[1] for x in losses])) if losses else None,
                      "undefined_reason": None if finite else "no eligible events or infinite log loss from zero predictive mass"})
    return table


def evaluate(prepared: Prepared, *, periods: Path, monetary: Path, training: Path, fit_until: date,
             score_until: date, specification: dict, token: Unseal | None = None) -> dict:
    """Evaluate an already-frozen released preparation. No fit occurs at a later state origin."""
    fit_origin, event_end = request_window(fit_until, score_until, token)
    if token is not None and specification.get("status") != "frozen":
        raise ValueError("protected scoring requires a frozen scientific specification")
    if token is not None:
        binding = configured_fit_binding(specification, fit_origin, required=True)
        verify_frozen_fit(prepared, fit_origin, binding)
    if prepared.inputs["origin"] != fit_origin:
        raise ValueError("prepared fit origin differs from the declared exclusive fit cut")
    fingerprint = frozen_fingerprint(prepared)
    actual = realized_daily(monetary, score_until, token)
    cells, diagnostics, paths, simulation_receipts = [], [], [], []
    horizons = tuple(specification["horizons_days"])
    seeds, batch_runs = specification["batch_seeds"], specification["runs_per_batch"]
    if prepared.draws is None or len(prepared.draws) != len(seeds) * batch_runs:
        raise ValueError("the frozen draw table must match the declared batch design")
    origins = monthly_origins(fit_origin, score_until, min(horizons))
    for origin in origins:
        eligible = [h for h in horizons if origin + timedelta(days=h) < score_until]
        if not eligible:
            continue
        # Validate realized endpoints and every benchmark before running this origin.
        for variable in VARIABLES:
            for h in eligible:
                ev.actual_at(actual[variable], origin, h)
        state = origin_state(str(periods), origin, token)
        candidate = at_origin(prepared, state, origin, fit_origin)
        parts = []
        for batch, seed in enumerate(seeds):
            draws = prepared.draws.iloc[batch * batch_runs:(batch + 1) * batch_runs].reset_index(drop=True)
            model = VARIANTS["v0.8.0"].simulation(candidate, seed=seed, timesteps=max(eligible), runs=batch_runs, draws=draws)
            simulation_receipts.append({"origin": origin, "batch_seed": seed, "specification": model.specification_hash()})
            part = run(model)
            parts.append(part[part.variable.isin(VARIABLES)].assign(batch_seed=seed))
        trajectories = pd.concat(parts, ignore_index=True)
        for variable, (unit, divisor) in VARIABLES.items():
            part = trajectories[trajectories.variable == variable]
            means = part.groupby("timestep").value.apply(lambda x, divisor=divisor: np.mean([int(v) / divisor for v in x]))
            dates = pd.DatetimeIndex([origin + timedelta(days=int(t)) for t in means.index])
            observed = actual.loc[dates, variable].to_numpy()
            diagnostics.append({"origin": origin, "variable": variable, "unit": unit,
                                "role": "reported diagnostic, not total-bonded contract acceptance",
                                **contract_diagnostics(means.to_numpy(), observed)})
            paths.extend({"origin": origin, "variable": variable, "date": d.date(), "ensemble_mean": float(x),
                          "actual": float(y)} for d, x, y in zip(dates, means, observed, strict=True))
            for h in eligible:
                sample = np.asarray([int(x) / divisor for x in part.loc[part.timestep == h, "value"]])
                if len(sample) != len(seeds) * batch_runs:
                    raise ValueError("incomplete forecast ensemble")
                rows = cell_scores(sample, ev.actual_at(actual[variable], origin, h), actual[variable], origin, h)
                cells.extend({**x, "variable": variable, "unit": unit, "scaled_loss_unit": "dimensionless"} for x in rows)
        if frozen_fingerprint(prepared) != fingerprint:
            raise ValueError("frozen fit or distribution tables changed during evaluation")
    expected_primary_origins = [o for o in origins if o + timedelta(days=90) < score_until]
    verdict, comparisons = primary_verdict(cells, specification["primary_variables"], expected_origins=expected_primary_origins)
    event_start = LOCKBOX_START if fit_until == LOCKBOX_FIRST_DAY else datetime.combine(fit_until, time(0), tzinfo=UTC)
    result = {"schema": "validator-evaluation/v1", "mode": "development" if token is None else "protected",
              "specification_status": specification["status"], "verdict": verdict, "fit_origin": fit_origin,
              "fit_until": fit_until, "score_until": score_until, "event_start": event_start, "event_end": event_end,
              "frozen_fit_sha256": fingerprint, "model_fit_receipt": prepared.inputs.get("stake_fit_receipt"),
              "simulation_receipts": simulation_receipts, "S": cells, "primary_comparisons": comparisons,
              "distribution_comparisons": distribution_comparisons(cells),
              "B": behaviour_table(prepared, training, periods, fit_origin, event_start, event_end, token),
              "contract_diagnostics": diagnostics, "daily_mean_paths": paths,
              "unresolved_specification_choices": specification.get("unresolved", []),
              "crps_convention": "existing distribution_scores: fair correction below100 draws; ordinary sample score at registered200",
              "behaviour_loss_units": {"log_loss": "nats per event", "brier": "dimensionless"},
              "not_measured": [{"target": "total_bonded_avax", "reason": "released model has no delegated-principal forecast"},
                               {"target": "staking_ratio", "reason": "released model has no delegated-principal forecast"}],
              "foundation_acceptance": "unresolved; these are scientific diagnostics"}
    result = _json(result)
    result["report_markdown"] = report(result)
    json.dumps(result, allow_nan=False)
    return result


def report(result: dict) -> str:
    def number(value):
        return "undefined" if value is None else f"{value:.5g}" if isinstance(value, float) else str(value)

    lines = ["# Fixed-fit validator evaluation", "", f"Scientific verdict: {result['verdict']}.", "",
             f"Mode: {result['mode']}. Specification: {result['specification_status']}.", "",
             "This result does not establish Foundation acceptance of deliverable 2.4.", "",
             "| Series | Benchmark | Origins | Model MASE | Benchmark MASE | One-sided DM p |",
             "| --- | --- | --- | --- | --- | --- |"]
    for row in result["primary_comparisons"]:
        p = number(row["dm"]["p_less"]) if row["dm"] else "undefined: " + str(row["undefined_reason"])
        lines.append(f"| {row['variable']} | {row['benchmark']} | {row['origins']} | {number(row['model_mase'])} | {number(row['benchmark_mase'])} | {p} |")
    lines += ["", "## Distribution and coverage", "",
              "CRPS and coverage are supplementary. Primary comparisons above use unrounded values.", "",
              "| Series | Horizon | Forecast | Cases | Mean scaled CRPS | 50% coverage | 80% coverage |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    groups = {}
    for row in result["S"]:
        if row["forecast"] in ("model", "N1d", "N2d"):
            groups.setdefault((row["variable"], row["horizon_days"], row["forecast"]), []).append(row)
    for (variable, horizon, forecast), rows in sorted(groups.items()):
        def mean(key, rows=rows):
            values = [x[key] for x in rows if x.get(key) is not None]
            return float(np.mean(values)) if len(values) == len(rows) else None
        lines.append(f"| {variable} | {horizon} | {forecast} | {len(rows)} | {number(mean('crps'))} | {number(mean('in50'))} | {number(mean('in80'))} |")
    lines += ["", "| Series | Horizon | Dressed benchmark | CRPS skill | One-sided DM p | Qualification |",
              "| --- | --- | --- | --- | --- | --- |"]
    for row in result["distribution_comparisons"]:
        p = row["dm"]["p_less"] if row["dm"] else None
        lines.append(f"| {row['variable']} | {row['horizon_days']} | {row['benchmark']} | {number(row['skill'])} | {number(p)} | {row['undefined_reason'] or ''} |")
    lines += ["", "## Behaviour diagnostics", "",
              "Frozen point blocks and duration tables are scored separately from the system's bootstrap ensemble.", "",
              "| Target | Forecast | Events | Mean log loss | Brier loss | Qualification |",
              "| --- | --- | --- | --- | --- | --- |"]
    for row in result["B"]:
        lines.append(f"| {row['target']} | {row['forecast']} | {row['events']} | {number(row.get('log_loss'))} | {number(row.get('brier'))} | {row.get('undefined_reason') or ''} |")
    lines += ["", "## Reported path diagnostics", "",
              "RMSE uses each row's stated unit. These validator-only paths do not supply total-bonded contract correlation.", "",
              "| Origin | Series | Unit | Pearson levels | Pearson differences | RMSE | 7-day direction | Phase lag days | Qualification |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in result["contract_diagnostics"]:
        lines.append(f"| {row['origin']} | {row['variable']} | {row['unit']} | {number(row['pearson_levels'])} | {number(row['pearson_first_differences'])} | {number(row['rmse'])} | {number(row['direction_7d'])} | {number(row['phase_lag_days'])} | {row['undefined_reason'] or ''} |")
    lines += ["", "## Unmeasured targets and unresolved decisions", ""]
    lines += [f"- {row['target']}: {row['reason']}." for row in result["not_measured"]]
    lines += [f"- Proposed decision: {item}." for item in result["unresolved_specification_choices"]]
    lines += ["", "All per-origin scores, undefined-metric reasons and ensemble-mean paths are retained in the JSON result.",
              "Validator own stake is not total bonded AVAX."]
    return "\n".join(lines)


def evaluation_specification(*, protected: bool) -> dict:
    """Read the declared design without opening data or constructing a fit."""
    specification = json.loads((ROOT / "validation/lockbox/specification.json").read_text())
    if specification.get("variant") != "v0.8.0":
        raise ValueError("this evaluation prepares released v0.8.0 only")
    if protected and specification.get("status") != "frozen":
        raise ValueError("protected scoring requires a frozen scientific specification")
    if (specification["batch_seeds"] != list(range(10)) or specification["runs_per_batch"] != 20
            or specification["draw_seed"] != 0 or specification["horizons_days"] != [30, 90]):
        raise ValueError("entrypoint requires the released 10x20 keyed-stream design and declared 30/90-day horizons")
    return specification


def prepare_fixed_fit(specification: dict, fit_origin: date) -> tuple[Prepared, dict]:
    """Shared pre-boundary-only preparation for scoring and the pre-marker preflight."""
    if type(fit_origin) is not date or fit_origin >= LOCKBOX_FIRST_DAY:
        raise ValueError("fit preparation requires a pre-boundary calendar origin")
    training = verified_inputs(ROOT, specification["training_pin"])
    scoring = verified_inputs(ROOT, specification["scoring_pin"])
    original_pin_hashes = {name: _hash_file(ROOT / specification[name]) for name in ("training_pin", "scoring_pin")}
    training_periods, periods = (x["derived.staking-periods"] for x in (training, scoring))
    information = validate_training_information(training_periods, fit_origin)
    slices = matching_training_slices(training_periods, periods, fit_origin)
    pin = json.loads((ROOT / specification["training_pin"]).read_text())
    source = next(x["run"] for x in pin["runs"] if x["dataset_id"] == "derived.staking-periods")
    prepared = VARIANTS["v0.8.0"].prepare(str(training_periods), fit_origin, source, draws=200, draw_seed=0)
    return prepared, {"training": training, "scoring": scoring, "information": information,
                      "slices": slices, "pin_hashes": original_pin_hashes, "training_pin": pin}


def verify_input_pins_unchanged(specification: dict, hashes: dict) -> None:
    for name, expected in hashes.items():
        if _hash_file(ROOT / specification[name]) != expected:
            raise ValueError("input pin changed during the evaluation")
        verified_inputs(ROOT, specification[name])


def preflight_fit(*, fit_until: date) -> dict:
    """Verify an adopted fit on the runner before its one-shot marker, without a token or labels.

    This reconstructs the declared pre-boundary fit once. It performs no simulation and does
    not authorize protected scoring. Missing/unadopted bindings refuse before opening inputs.
    """
    if type(fit_until) is not date or fit_until > LOCKBOX_FIRST_DAY:
        raise ValueError("fit preflight requires an exclusive pre-boundary UTC date cut")
    fit_origin = fit_until - timedelta(days=1)
    specification = evaluation_specification(protected=True)
    binding = configured_fit_binding(specification, fit_origin, required=True)
    prepared, context = prepare_fixed_fit(specification, fit_origin)
    receipt = verify_frozen_fit(prepared, fit_origin, binding)
    verify_input_pins_unchanged(specification, context["pin_hashes"])
    return {"schema": "validator-fit-preflight/v1", "fit_until_exclusive": fit_until.isoformat(),
            "fit_binding": receipt, "training_information": context["information"],
            "training_slice_equality": context["slices"], "input_pin_hashes": context["pin_hashes"],
            "fitting_operation": True, "protected_labels_read": False, "forecast_executed": False,
            "entrypoint_sha256": _hash_file(Path(__file__))}


def score(token: Unseal | None, *, fit_until: date, score_until: date) -> dict:
    """Single manifest entrypoint. Verify the frozen fit before state or realized-label access."""
    fit_origin, _ = request_window(fit_until, score_until, token)
    specification = evaluation_specification(protected=token is not None)
    binding = configured_fit_binding(specification, fit_origin, required=token is not None)
    prepared, context = prepare_fixed_fit(specification, fit_origin)
    fit_check = verify_frozen_fit(prepared, fit_origin, binding)
    training_periods = context["training"]["derived.staking-periods"]
    periods = context["scoring"]["derived.staking-periods"]
    scoring, pin, original_pin_hashes = context["scoring"], context["training_pin"], context["pin_hashes"]
    result = evaluate(prepared, periods=periods, monetary=scoring["derived.avax-monetary-daily"], training=training_periods,
                      fit_until=fit_until, score_until=score_until, specification=specification, token=token)
    result["fit_binding"] = fit_check
    result["training_slice_equality"] = context["slices"]
    result["training_information"] = context["information"]
    verify_input_pins_unchanged(specification, original_pin_hashes)
    result["input_pins"] = {name: {"path": specification[name], "sha256": original_pin_hashes[name]}
                            for name in ("training_pin", "scoring_pin")}
    result["input_runs"] = {"training": pin["runs"],
                            "scoring": json.loads((ROOT / specification["scoring_pin"]).read_text())["runs"]}
    fit_model = VARIANTS["v0.8.0"].simulation(prepared, seed=0, timesteps=1, runs=20,
                                            draws=prepared.draws.iloc[:20].reset_index(drop=True))
    result["fit_provenance"] = _json({
        "fitting_operation": True, "fit_origin": fit_origin, "fit_until_exclusive": fit_until,
        "purpose": "development reconstruction of released fitting law; not final coefficient adoption",
        "parameter_identity_to_released_values": "not verified against stored released parameter values",
        "draw_seed": 0, "batch_seeds": list(range(10)), "runs_per_batch": 20,
        "model_specification": fit_model.specification(), "parameter_draws": prepared.draws.to_dict("records"),
        "tau": prepared.tau, "tau_source": prepared.tau_source,
    })
    result["entrypoint_sha256"] = _hash_file(Path(__file__))
    json.dumps(result, allow_nan=False)
    return result
