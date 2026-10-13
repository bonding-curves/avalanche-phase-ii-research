"""Score the stake hurdle on development decisions against its frozen cell benchmarks.

The score is conditional on observed context and next duration. It is not a
network forecast. The source guard checks pinned bytes and structural history.
Run with the project model dependencies and an explicit dataset directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from avalanche_research.model.fitted_lifecycle import (
    _day,
    _first_ever,
    _moved,
    checked_stake_decisions,
    decided_by_us,
    stake_decisions,
    validator_periods,
)
from avalanche_research.model.parts.stake_choice import (
    CONTEXTS,
    MIN_STAKE,
    StakeChoice,
    _cell_ids,
    table_sha256,
)

LOCKBOX = "2025-11-19 16:00:00"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def checked_source(dataset_directory, pin):
    """Refuse changed bytes or malformed history before any adapter call or fit.

    This certifies structural validity of the pinned file's development history.
    It does not independently certify completeness against the original chain.
    """
    directory = Path(dataset_directory).resolve(strict=True)
    path = directory / pin["parquet"]
    if directory.name != "dataset" or directory.parent.name != pin["run"]:
        raise ValueError("source directory does not match the pinned run")
    if digest(path) != pin["sha256"] or path.stat().st_size != pin["bytes"]:
        raise ValueError("source bytes do not match the pin")
    build = json.loads((directory / "build.json").read_text())
    check = json.loads((directory / "check.json").read_text())
    if (build["dataset_id"] != pin["dataset_id"] or check["dataset_id"] != pin["dataset_id"]
            or check["status"] != "pass" or check["findings"]
            or check["capture_id"] != pin["capture_id"]
            or build["source_capture_id"] != pin["capture_id"]):
        raise ValueError("source receipt identity or check differs from the pin")
    outputs = [o for o in build["outputs"] if o["path"] == pin["parquet"]]
    if len(outputs) != 1 or any(outputs[0][k] != pin[k] for k in ("bytes", "sha256")):
        raise ValueError("build output differs from pinned bytes")
    with duckdb.connect() as db:
        db.execute("SET threads=4")
        schema = {r[0]: r[1] for r in db.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()}
        expected = {"stake_navax": "BIGINT", "start_time": "TIMESTAMP",
                    "end_time": "TIMESTAMP", "accepted_at": "TIMESTAMP",
                    "node_id": "VARCHAR", "transaction_hash": "VARCHAR"}
        if any(schema.get(k) != v for k, v in expected.items()):
            raise ValueError("native source schema differs from adapter preconditions")
        # Null clocks must be found before start_time filtering can hide history.
        missing_clocks = db.execute("""SELECT count(*) FROM read_parquet(?)
            WHERE role='validator' AND (accepted_at IS NULL OR start_time IS NULL
              OR end_time IS NULL)""", [str(path)]).fetchone()[0]
        if missing_clocks:
            raise ValueError("validator source has missing historical clocks")
        db.read_parquet(str(path)).filter(
            f"role='validator' AND start_time<TIMESTAMP '{LOCKBOX}'").create_view("development")
        result = db.execute('''SELECT count(*) AS "rows",
            count(*) FILTER(WHERE accepted_at>start_time) late_acceptance,
            count(*) FILTER(WHERE stake_navax IS NULL) null_stake,
            count(*) FILTER(WHERE stake_navax<2000000000000 OR stake_navax>3000000000000000) illegal_stake,
            count(*) FILTER(WHERE node_id IS NULL OR node_id='') missing_node,
            count(*) FILTER(WHERE transaction_hash IS NULL OR transaction_hash='') missing_transaction,
            count(*)-count(DISTINCT transaction_hash) duplicate_transaction,
            count(*) FILTER(WHERE end_time<=start_time) nonpositive_duration,
            count(*) FILTER(WHERE epoch_us(end_time)-epoch_us(start_time)>365::BIGINT*86400000000) excessive_duration,
            count(*) FILTER(WHERE (epoch_us(end_time)-epoch_us(start_time))%86400000000!=0) fractional_duration
            FROM development''')
        counts = dict(zip([c[0] for c in result.description], result.fetchone()))
        violations = {k: v for k, v in counts.items()
                      if k not in ("rows", "fractional_duration") and v}
        if violations:
            raise ValueError(f"invalid development source history: {violations}")
        if not counts["rows"]:
            raise ValueError("development history is empty")
    return path, {"status": "PASS pinned file and declared development source preconditions",
                  "run": pin["run"], "dataset_id": pin["dataset_id"],
                  "parquet_sha256": pin["sha256"], "counts": counts,
                  "missing_validator_clocks": missing_clocks,
                  "build_sha256": digest(directory / "build.json"),
                  "check_sha256": digest(directory / "check.json"),
                  "duration_projection": "nearest whole day, ties to even, minimum one; inherited adapter rule",
                  "independent_chain_completeness_verified": False}


SOURCE_PIN = {'bytes': 692906576, 'capture_id': 'capture:derived:2026-09-30T17:25:46Z:e0b8a7f3be51', 'captured_at': '2026-09-30T17:25:46Z', 'check': 'pass', 'dataset_id': 'derived.staking-periods', 'parquet': 'staking-periods.parquet', 'run': 'staking-periods-2026-09-30', 'sha256': 'e8877bf5cbe1f45f124cd2f36993ecd1a35109eb67361634f6da31609df237c8'}
UPGRADES = {"Banff": date(2022, 10, 18), "Cortina": date(2023, 4, 25),
            "Durango": date(2024, 3, 6), "Etna": date(2024, 12, 16), "Fortuna": date(2025, 4, 8)}
QUARTERS = {f"{y}-{m:02d}-01": date(y, m, 1) for y in (2022, 2023, 2024, 2025)
            for m in (1, 4, 7, 10) if date(2022, 7, 1) <= date(y, m, 1) <= date(2025, 10, 1)}
BOOTSTRAPS, BOOTSTRAP_SEED = 2000, 20261005


def fit_part(tables, origin, run):
    """Check producer CSV provenance, then make separate JSON consumer labels."""
    for context in CONTEXTS:
        checked_stake_decisions(context, tables[context])
    labels = {c: f"{run}; origin {origin}; 365 days; sha256 {table_sha256(tables[c])}"
              for c in CONTEXTS}
    return StakeChoice.fit(*(tables[c] for c in CONTEXTS), labels)


def decision_metadata(periods, origin, tables):
    """Bind the unchanged adapter's positional indices to observed node histories."""
    known = validator_periods(periods, decided_by_us(origin))
    moved = _moved(known, decided_by_us(origin))
    first = _first_ever(known, _day(origin))
    result = {}
    for c in CONTEXTS:
        source = first if c == "entry" else moved
        selected = source.iloc[tables[c].index.to_numpy()]
        starts = selected["s" if c == "entry" else "next_s"].to_numpy(dtype=np.int64)
        np.testing.assert_array_equal(starts, tables[c].decided_us.to_numpy())
        after = selected["stake_navax" if c == "entry" else "next_stake"].to_numpy(dtype=np.int64)
        np.testing.assert_array_equal(after, tables[c].next_stake_navax.to_numpy())
        result[c] = pd.DataFrame({"node_id": selected.node_id.to_numpy(),
                                  "previous_start_us": selected.s.to_numpy(dtype=np.int64)},
                                 index=tables[c].index)
    return result


def expected_calibration_error(p, y):
    """Ten quantile bins, weighted by count, including a constant forecast."""
    p, y = np.asarray(p), np.asarray(y)
    if not len(p) or p.shape != y.shape or not np.isfinite(p).all():
        raise ValueError("calibration needs matching finite nonempty vectors")
    if np.unique(p).size == 1:
        return float(abs(p[0] - y.mean()))
    bins = pd.qcut(pd.Series(p), 10, duplicates="drop")
    frame = pd.DataFrame({"p": p, "y": y, "bin": bins})
    grouped = frame.groupby("bin", observed=True).agg(n=("y", "size"), o=("y", "mean"), q=("p", "mean"))
    return float((grouped.n * (grouped.o - grouped.q).abs()).sum() / len(p))


def calibration(laws, outcome):
    """Report each observable cell and the atom separately, retaining the full vector."""
    values = [expected_calibration_error(laws[:, k], outcome == k) for k in range(103)]
    return {"mean_cell_ece": float(np.mean(values)), "atom_ece": values[0],
            "maximum_cell_ece": max(values), "cell_ece": values}


def paired_bootstrap(events):
    """Existing development convention: paired origins, then nodes within origins."""
    if events.empty or not np.isfinite(events.delta).all():
        raise ValueError("bootstrap requires finite nonempty paired losses")
    nodes = events.groupby(["origin", "node_id"]).delta.agg(["sum", "size"])
    groups = [(g["sum"].to_numpy(), g["size"].to_numpy()) for _, g in nodes.groupby(level="origin")]
    rng, differences = np.random.default_rng(20261005), np.empty(BOOTSTRAPS)
    for i in range(BOOTSTRAPS):
        total = count = 0.0
        for j in rng.integers(0, len(groups), len(groups)):
            sums, sizes = groups[j]
            picked = rng.integers(0, len(sums), len(sums))
            total += sums[picked].sum()
            count += sizes[picked].sum()
        differences[i] = total / count
    return {"p_no_better": float((differences >= 0).mean()),
            "delta_nll_interval95": [float(x) for x in np.quantile(differences, [.025, .975])],
            "replicates": BOOTSTRAPS, "seed": BOOTSTRAP_SEED,
            "unit": "origins then nodes within origins; overlapping origins remain dependent"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    path, audit = checked_source(args.dataset_directory, SOURCE_PIN)
    args.output_directory.mkdir(parents=True, exist_ok=False)
    frames, laws, cells, receipts, excluded = [], {c: [] for c in CONTEXTS}, {c: [] for c in CONTEXTS}, [], []
    for name, origin in sorted({**UPGRADES, **QUARTERS}.items(), key=lambda item: item[1]):
        train = stake_decisions(str(path), origin, SOURCE_PIN["run"])
        part = fit_part(train, origin, SOURCE_PIN["run"])
        before = json.dumps(part.sources(), sort_keys=True)
        receipts.append({"origin": name, "date": origin.isoformat(),
                         "fit_counts": {c: len(t) for c, t in train.items()},
                         "producer_csv_provenance": {c: dict(t.attrs) for c, t in train.items()},
                         "fitted_values_sha256": hashlib.sha256(before.encode()).hexdigest()})
        end = origin + timedelta(days=90)
        if end >= date(2025, 11, 19):
            excluded.append({"origin": name, "reason": "complete90day window reaches lockbox; no score read"})
            continue
        tables = stake_decisions(str(path), end, SOURCE_PIN["run"])
        metadata = decision_metadata(str(path), end, tables)
        for c, full in tables.items():
            t = full.loc[full.decided_us > decided_by_us(origin)]
            if t.empty:
                raise ValueError(f"empty scoring context {name}/{c}")
            previous, days, stakes = (t[k].to_numpy() for k in
                                      ("previous_stake_navax", "next_days", "next_stake_navax"))
            law = part.cell_probabilities(c, previous, days)
            ids = _cell_ids(np.full(len(t), MIN_STAKE) if c == "entry" else previous, stakes)
            logp = np.log(law[np.arange(len(t)), ids])
            baseline = part.baseline_log_prob(c, previous, days, stakes)
            if not (np.isfinite(logp).all() and np.isfinite(baseline).all()):
                raise ValueError("nonfinite event score")
            m = metadata[c].loc[t.index]
            frames.append(pd.DataFrame({"origin": name, "date": origin.isoformat(), "context": c,
                                        "node_id": m.node_id.to_numpy(), "decided_us": t.decided_us.to_numpy(),
                                        "known_previous_at_origin": m.previous_start_us.to_numpy() <= decided_by_us(origin),
                                        "loss_candidate": -logp, "loss_baseline": -baseline,
                                        "delta": baseline - logp, "outcome_cell": ids}))
            laws[c].append(law)
            cells[c].append(ids)
        if before != json.dumps(part.sources(), sort_keys=True):
            raise AssertionError("scoring mutated fitted part")
        print(name, "event scores checked", flush=True)
    events = pd.concat(frames, ignore_index=True)
    summaries = []
    for c in CONTEXTS:
        e = events.loc[events.context == c]
        per_origin = e.groupby("origin").delta.mean()
        known = e.loc[e.known_previous_at_origin] if c != "entry" else e.iloc[:0]
        summaries.append({"context": c, "events": len(e), "unique_node_decisions": len(e.drop_duplicates(["node_id", "decided_us"])),
                          "candidate_nll": float(e.loss_candidate.mean()), "baseline_nll": float(e.loss_baseline.mean()),
                          "origins_lower": int((per_origin < 0).sum()), "origins_scored": len(per_origin),
                          "bootstrap": paired_bootstrap(e), "calibration": calibration(np.concatenate(laws[c]), np.concatenate(cells[c])),
                          "known_previous_at_origin_events": len(known),
                          "known_previous_at_origin_delta": None if known.empty else float(known.delta.mean()),
                          "adoption_verdict": "with Modeling; conditional event metrics only"})
    events.to_csv(args.output_directory / "events.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    events.groupby(["context", "origin", "date"], sort=True).agg(events=("delta", "size"),
                       candidate_nll=("loss_candidate", "mean"), baseline_nll=("loss_baseline", "mean"), delta_nll=("delta", "mean")).to_csv(args.output_directory / "by-origin.csv")
    result = {"source_audit": audit, "source_script_sha256": digest(__file__), "fits": receipts,
              "excluded_score_origins": excluded, "contexts": summaries,
              "conditional_on": ["observed renewal/return/entry", "observed next duration", "previous stake at decision"],
              "scientific_adoption": False, "system_score": False, "protected_fit_or_score": False}
    (args.output_directory / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"contexts": [{k: v for k, v in s.items() if k != "calibration"} for s in summaries]}), flush=True)


if __name__ == "__main__":
    main()
