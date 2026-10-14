#!/usr/bin/env python3
"""Replay decision summaries from a hash-bound wide cache and bootstrap NPZ.

No simulation, random-number construction or source-output discovery occurs.
The cache must already have passed producer and paired-consumer authentication.
All observations remain conditional on the declared design distributions.
"""

from __future__ import annotations

# Thread limits must precede native numerical imports.
import argparse
import hashlib
import json
import os
import resource
import sys
import time
from pathlib import Path

for _variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_variable] = "1"

import duckdb
import numpy as np
import pandas as pd

from avalanche_research.analysis import decision_summary as ds
from avalanche_research.analysis import m2_contract
from avalanche_research.analysis.m2_contract import CHAIN_INFLATION, FAMILY_INPUTS
from avalanche_research.analysis.prim import discover_confirm

RELATIVE = ("issuance_saved", "validator_stake_retained", "active_validators_retained")
MARGINS = {
    "zero": "return_margin",
    **{cost: f"return_margin_{cost}" for cost in ("low", "mid", "high")},
    **{
        f"{cost}_fitting_price": f"return_margin_{cost}_fitting_price"
        for cost in ("low", "mid", "high")
    },
}
SCOPE = ("family", "yield_pp", "horizon_days")
STRESS = (1, 2, 3)
ANCHOR_CELLS = (
    *ds.GRID,
    ("zero", "zero"),
    *((f"stress_{j}", f"stress_{j}") for j in STRESS),
)


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(2**20), b""):
            digest.update(part)
    return digest.hexdigest()


def _atomic_csv(frame, path):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def _conditions(frame):
    """Each alternative is explicit; reported-only measures get no targets."""
    yield "issuance_saved", "primary", "not_cost_sensitive", frame.issuance_saved > 0
    yield (
        "validator_stake_retained",
        "primary",
        "not_cost_sensitive",
        frame.validator_stake_retained >= 1 - frame.issuance_saved,
    )
    yield (
        "validator_stake_retained",
        "no_stake_loss",
        "not_cost_sensitive",
        frame.validator_stake_retained >= 1,
    )
    yield "net_inflation", "primary", "not_cost_sensitive", frame.net_inflation <= 0.05
    yield (
        "net_inflation",
        "trailing_year",
        "not_cost_sensitive",
        frame.net_inflation <= CHAIN_INFLATION,
    )
    for cost, name in MARGINS.items():
        yield "return_margin", "primary", cost, frame[name] >= 0


def _populations(frame):
    ab = frame[frame.block.isin(["A", "B"])]
    yield "all", "all", "all", ab
    for r, e in ds.GRID:
        yield "grid", r, e, ab[ab.renewal_band.eq(r) & ab.entry_band.eq(e)]
    yield "zero", "zero", "zero", frame[frame.block.eq("zero")]
    for setting in STRESS:
        label = f"stress_{setting}"
        yield label, label, label, frame[frame.block.eq("stress") & frame.j.eq(setting)]
    yield "noise", "all", "all", frame[frame.block.eq("noise")]


def _draws(bootstrap, key, replicates):
    if key not in bootstrap:
        raise ds.ContractError(f"Missing bootstrap scope: {key}")
    array = np.asarray(bootstrap[key])
    if (
        array.ndim != 2
        or array.shape[0] != replicates
        or array.dtype.kind not in "iu"
        or not array.shape[1]
    ):
        raise ds.ContractError("Wrong bootstrap count, type or scope shape")
    if (array < 0).any() or (array >= array.shape[1]).any():
        raise ds.ContractError("Bootstrap position outside scope")
    return array


def _range(a, b, scope, target, alternative, cost, passed_a, passed_b, draws):
    context = {
        **scope,
        "target": target,
        "threshold_alternative": alternative,
        "cost_level": cost,
        "tier": "global range" if target == "all_joint" else "per-goal range",
        "eligible_for_recommendation": cost != "zero"
        and not scope.get("excluded_from_tiers", False),
    }
    if scope["family"] == "before":
        return {
            **context,
            "status": "not_applicable",
            "reason": "no_mechanism_input",
            "provisional": True,
        }, None
    features = list(FAMILY_INPUTS[scope["family"]])
    # Empty B is an accepted discovery-only API. No real B value is used here.
    search = discover_confirm(
        a[features].to_numpy(float),
        np.asarray(passed_a, dtype=bool),
        np.empty((0, len(features))),
        np.empty(0, dtype=bool),
        feature_names=features,
        scope={
            "family": scope["family"],
            "competing_yield_pp": float(scope["yield_pp"]),
            "horizon_days": int(scope["horizon_days"]),
        },
        sample_ids_A=[str(v) for v in a["index"]],
        sample_ids_B=[],
    )
    selected = search["selected_box"]
    if selected is None:
        return {
            **context,
            "status": "not_found" if len(a) else "unassessable",
            "reason": "no_A_qualified_PASS_box" if len(a) else "no_A_rows",
            "provisional": True,
        }, {
            **context,
            "positive_target": "PASS",
            "selected_box": None,
            "discovery_reason": search["reason"],
        }
    candidates = pd.DataFrame(
        [
            {
                "candidate": "A_selected_PASS_box",
                "input": bound["feature"],
                "lower": bound["lower"],
                "upper": bound["upper"],
                "discovery_score": 1.0,
            }
            for bound in selected["bounds"]
        ]
    )
    confirmed = b.copy()
    confirmed["_passed"] = np.asarray(passed_b, dtype=bool)
    result = ds.select_and_confirm(
        a,
        confirmed,
        candidates,
        pass_column="_passed",
        unit_column="i",
        bootstrap_indices=draws,
        unit_order=list(range(draws.shape[1])),
        family=scope["family"],
        goal_column="issuance_saved"
        if target in ("issuance_saved", "all_joint")
        else None,
    )
    result["bounds"] = json.dumps(result["bounds"], sort_keys=True)
    result.update(context)
    result["discovery_PASS_coverage"] = selected["discovery"]["coverage"]
    result["discovery_PASS_density"] = selected["discovery"]["density"]
    result["discovery_PASS_runs"] = selected["discovery"]["failing_in_box"]
    result["tier"] = "global range" if target == "all_joint" else "per-goal range"
    return result, {
        **context,
        "positive_target": "PASS",
        "selected_box": selected,
        "field_note": "Verbatim PRIM discovery failing/failed field names count PASS targets here; no real B was supplied to discovery",
    }


def summarize_decisions(
    wide, bootstrap, *, associations=None, replicates=1000, include_ranges=True
):
    """Pure cache adapter; actual file reads belong to the explicit CLI below."""
    required = {
        "index",
        "family",
        "yield_pp",
        "horizon_days",
        "block",
        "i",
        "j",
        "renewal_band",
        "entry_band",
        "renewal_response",
        "entry_response",
        "net_inflation",
        *RELATIVE,
        *MARGINS.values(),
    }
    if required - set(wide):
        raise ds.ContractError(f"Wide cache missing {sorted(required - set(wide))}")
    design = wide[wide.block.isin(["A", "B", "zero", "stress", "noise"])].copy()
    if design.duplicated(["index", "horizon_days"]).any():
        raise ds.ContractError("Duplicate trajectory/horizon identity")
    numeric = [*RELATIVE, "net_inflation", *MARGINS.values()]
    if not np.isfinite(design[numeric].to_numpy(float)).all():
        raise ds.ContractError("Decision populations require complete finite outcomes")
    rankings = ds.design_rankings(
        design, RELATIVE, higher_is_better={name: True for name in RELATIVE}
    )
    passes, differences, points, ranges, candidates = [], [], [], [], []
    for key, frame in design.groupby(list(SCOPE), sort=True):
        scope = {
            "family": str(key[0]),
            "yield_pp": float(key[1]),
            "horizon_days": int(key[2]),
        }
        family, yield_pp, _ = key
        saltelli = _draws(bootstrap, f"{family}__{float(yield_pp)}", replicates)
        anchor = _draws(bootstrap, f"anchor__{float(yield_pp)}", replicates)
        noise = _draws(bootstrap, f"noise__{family}__{float(yield_pp)}", replicates)
        expected = set(range(saltelli.shape[1]))
        for role in ("A", "B"):
            members = frame[frame.block.eq(role)]
            if len(members) != len(expected) or set(members.i) != expected:
                raise ds.ContractError("Incomplete A/B whole-unit membership")
        for population, renewal, entry, members in _populations(frame):
            draws = (
                noise
                if population == "noise"
                else anchor
                if population == "zero" or population.startswith("stress_")
                else saltelli
            )
            order = list(range(draws.shape[1]))
            context = {
                **scope,
                "population": population,
                "renewal_band": renewal,
                "entry_band": entry,
                "excluded_from_tiers": family == "before"
                and scope["horizon_days"] == 180,
            }
            if population.startswith("stress_") or population == "zero":
                context["renewal_response"] = (
                    None if members.empty else float(members.renewal_response.iloc[0])
                )
                context["entry_response"] = (
                    None if members.empty else float(members.entry_response.iloc[0])
                )
            for measure, alternative, cost, passed in _conditions(members):
                summary = ds.clustered_pass_share(
                    passed.to_numpy(bool), members.i.tolist(), draws, unit_order=order
                )
                passes.append(
                    {
                        **context,
                        "measure": measure,
                        "threshold_alternative": alternative,
                        "cost_level": cost,
                        **summary,
                        **ds.pass_share_flags(summary["pass_share"]),
                        "QB5_se_at_most_5pp": None
                        if summary["bootstrap_se"] is None
                        else summary["bootstrap_se"] <= 0.05,
                    }
                )
            if population != "all" and population != "noise":
                for measure in RELATIVE:
                    values = members[measure].to_numpy(float) - (
                        0.0 if measure == "issuance_saved" else 1.0
                    )
                    summary = ds.clustered_mean_interval(
                        values, members.i.tolist(), draws, unit_order=order
                    )
                    constant = len(values) > 0 and np.ptp(values) == 0
                    differences.append(
                        {
                            **context,
                            "measure": measure,
                            "input": "family_against_matched_baseline",
                            "method": "mean_difference",
                            "coefficient": summary["mean"],
                            "ci_low": summary["ci_low"],
                            "ci_high": summary["ci_high"],
                            "status": "unassessable" if constant else summary["status"],
                            "interval_status": summary["status"],
                            "reason": "constant_kpi" if constant else summary["reason"],
                            "rows": len(values),
                            "bootstrap_sha256": summary["bootstrap_sha256"],
                        }
                    )
            if population != "grid":
                continue
            features = FAMILY_INPUTS[family]
            observed = ds.point_estimates(
                members, input_column=features[0], group_columns=SCOPE
            )
            if observed.empty:
                points.append(
                    {
                        **context,
                        "status": "not_found",
                        "reason": "no_A_rows",
                        "provisional": True,
                    }
                )
            else:
                points.extend(
                    {**context, **record} for record in observed.to_dict("records")
                )
            if not include_ranges:
                continue
            a, b = members[members.block.eq("A")], members[members.block.eq("B")]
            conditions_a, conditions_b = list(_conditions(a)), list(_conditions(b))
            for left, right in zip(conditions_a, conditions_b, strict=True):
                measure, alternative, cost, passed_a = left
                result, candidate = _range(
                    a,
                    b,
                    context,
                    measure,
                    alternative,
                    cost,
                    passed_a,
                    right[3],
                    saltelli,
                )
                ranges.append(result)
                if candidate is not None:
                    candidates.append(candidate)
            # Joint primary and each named alternative are separate scenarios.
            for cost, margin in MARGINS.items():
                for alternative in ("primary", "no_stake_loss", "trailing_year"):
                    flags = []
                    for rows in (a, b):
                        stake_floor = (
                            1.0
                            if alternative == "no_stake_loss"
                            else 1 - rows.issuance_saved
                        )
                        inflation = (
                            CHAIN_INFLATION if alternative == "trailing_year" else 0.05
                        )
                        flags.append(
                            (rows.issuance_saved > 0)
                            & (rows.validator_stake_retained >= stake_floor)
                            & (rows.net_inflation <= inflation)
                            & (rows[margin] >= 0)
                        )
                    result, candidate = _range(
                        a, b, context, "all_joint", alternative, cost, *flags, saltelli
                    )
                    ranges.append(result)
                    if candidate is not None:
                        candidates.append(candidate)
    difference_frame = pd.DataFrame(differences)
    grid_differences = difference_frame[
        difference_frame.renewal_band.isin(ds.BANDS)
        & difference_frame.entry_band.isin(ds.BANDS)
    ]
    ratings = [ds.confidence_ratings(difference_frame, expected_cells=ANCHOR_CELLS)]
    reversals = [ds.sign_reversals(grid_differences)]
    if associations is not None:
        grid = associations[
            associations.renewal_band.isin(ds.BANDS)
            & associations.entry_band.isin(ds.BANDS)
        ]
        ratings.append(ds.confidence_ratings(grid))
        reversals.append(ds.sign_reversals(grid))
    pass_frame = pd.DataFrame(passes)
    return {
        "design-rankings.csv": rankings,
        "point-estimates.csv": pd.DataFrame(points),
        "pass-shares.csv": pass_frame,
        "limit-screen.csv": pass_frame[pass_frame.measure.ne("issuance_saved")].copy(),
        "noise-qb5.csv": pass_frame[pass_frame.population.eq("noise")].copy(),
        "baseline-comparison-cells.csv": difference_frame,
        "confidence-ratings.csv": pd.concat(ratings, ignore_index=True),
        "sign-changes.csv": pd.concat(reversals, ignore_index=True),
        "range-confirmations.csv": pd.DataFrame(ranges),
        "A-PASS-selected-boxes.json": candidates,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wide", type=Path, required=True)
    parser.add_argument("--bootstrap", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--associations", type=Path)
    parser.add_argument(
        "--associations-sha256",
        help="Optional externally accepted association byte digest",
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--no-ranges",
        action="store_true",
        help="Explicit partial pass: leave range outputs uncomputed",
    )
    args = parser.parse_args(argv)
    start = time.monotonic()
    source_paths = [
        Path(__file__),
        Path(ds.__file__),
        Path(m2_contract.__file__),
        Path(discover_confirm.__code__.co_filename),
    ]
    source_hashes = {path.name: _sha(path) for path in source_paths}
    manifest_path = args.manifest or args.wide.parent / "inputs-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    associations_sha = None if args.associations is None else _sha(args.associations)
    if (
        args.associations_sha256 is not None
        and associations_sha != args.associations_sha256
    ):
        raise ds.ContractError("Association bytes differ from accepted digest")
    if (
        _sha(args.wide) != manifest["wide_sha256"]
        or _sha(args.bootstrap) != manifest["bootstrap"]["file_sha256"]
    ):
        raise ds.ContractError(
            "Wide/bootstrap bytes differ from authenticated manifest"
        )
    with np.load(args.bootstrap, allow_pickle=False) as bootstrap:
        for key, expected in manifest["bootstrap"]["matrices"].items():
            array = bootstrap[key]
            if (
                list(array.shape) != expected["shape"]
                or hashlib.sha256(np.asarray(array, dtype="<i8").tobytes()).hexdigest()
                != expected["sha256"]
            ):
                raise ds.ContractError("Bootstrap shape/canonical hash differs")
        connection = duckdb.connect(config={"threads": 1, "memory_limit": "512MB"})
        columns = [
            "index",
            "family",
            "yield_pp",
            "horizon_days",
            "block",
            "i",
            "j",
            "renewal_band",
            "entry_band",
            "renewal_response",
            "entry_response",
            "net_inflation",
            *RELATIVE,
            *MARGINS.values(),
            "target_min_rate",
            "boost_max",
            "exponent",
        ]
        projection = ", ".join(f'"{name}"' for name in columns)
        wide = connection.execute(
            f"SELECT {projection} FROM read_parquet(?) WHERE block IN ('A','B','zero','stress','noise')",
            [str(args.wide)],
        ).fetchdf()
        connection.close()
        associations = (
            None
            if args.associations is None
            else pd.read_csv(args.associations, float_precision="round_trip")
        )
        results = summarize_decisions(
            wide,
            bootstrap,
            associations=associations,
            include_ranges=not args.no_ranges,
        )
    if source_hashes != {path.name: _sha(path) for path in source_paths}:
        raise ds.ContractError("Analysis source changed during execution")
    if args.associations is not None and _sha(args.associations) != associations_sha:
        raise ds.ContractError("Association input changed during execution")
    args.output.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for name, value in results.items():
        path = args.output / name
        if isinstance(value, pd.DataFrame):
            _atomic_csv(value, path)
        else:
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
            temporary.replace(path)
        outputs[name] = _sha(path)
    receipt = {
        "status": "partial"
        if args.no_ranges or args.associations is None
        else "computed_pending_review",
        "inputs": {
            "wide_sha256": manifest["wide_sha256"],
            "bootstrap_sha256": manifest["bootstrap"]["file_sha256"],
            "manifest_sha256": _sha(manifest_path),
            "associations_sha256": associations_sha,
        },
        "outputs": outputs,
        "wall_seconds": time.monotonic() - start,
        "peak_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        * (1 if sys.platform == "darwin" else 1024),
        "source_sha256": source_hashes,
        "source_unchanged_at_end": True,
        "threads": 1,
        "duckdb_memory_limit": "512MB",
        "associations": "not_supplied" if args.associations is None else "supplied",
        "ranges": "not_run" if args.no_ranges else "computed",
        "limits": [
            "provisional until fresh-seed reruns",
            "conditional design intervals, not predictive coverage",
            "ranges describe sampled support in A-selected fixed boxes",
            "all-response pass screens are separate from nine-cell recommendations",
            "no Bonferroni or invented p-values/stars",
        ],
    }
    path = args.output / "decisions-receipt.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)
    print(
        json.dumps(
            {
                "receipt": str(path),
                "wall_seconds": receipt["wall_seconds"],
                "status": receipt["status"],
            }
        )
    )


if __name__ == "__main__":
    main()
