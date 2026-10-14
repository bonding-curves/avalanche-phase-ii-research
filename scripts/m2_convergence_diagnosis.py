"""Diagnose authenticated saved M2 Sobol convergence without new model runs.

Example: m2_convergence_diagnosis.py --inputs INPUT_DIR --numerics NUMERICS_DIR
--report REPORT_DIR --output NEW_DIR --inputs-sha256 SHA --report-sha256 SHA.
The two external receipt hashes must be supplied by the caller. Output is new
and contains every old index row, individual movement and propagated group flags.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

for _variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_variable] = "1"

import duckdb
import numpy as np
import pandas as pd

FAMILY_INPUTS = {
    "before": ("renewal_response", "entry_response"),
    "quadratic": ("exponent", "renewal_response", "entry_response"),
    "ramp": ("target_min_rate", "renewal_response", "entry_response"),
    "tenure": ("boost_max", "renewal_response", "entry_response"),
}
BOUNDS = {
    "renewal_response": (0.0, 0.1),
    "entry_response": (0.0, 0.1),
    "target_min_rate": (0.05, 0.1),
    "exponent": (1.0, 3.0),
    "boost_max": (0.0, 0.2),
}
MARGINS = (
    "return_margin",
    "return_margin_low",
    "return_margin_mid",
    "return_margin_high",
    "return_margin_low_fitting_price",
    "return_margin_mid_fitting_price",
    "return_margin_high_fitting_price",
)
RELATIVE = ("issuance_saved", "validator_stake_retained", "active_validators_retained")
KEYS = ["family", "yield_pp", "horizon_days", "measure", "input"]
SCOPE = KEYS[:3]
ATOL = 1e-10


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _bound(directory, name):
    root = Path(directory).resolve()
    path = (root / name).resolve()
    _require(
        path.is_relative_to(root) and path.is_file(),
        "binding escapes input directory or is absent",
    )
    return path


def authenticate(inputs, numerics, report, inputs_sha256, report_sha256):
    """External pins bind manifests, tables, intervals and original source hashes."""
    input_path, report_path = (
        inputs / "inputs-manifest.json",
        report / "analysis-receipt.json",
    )
    _require(digest(input_path) == inputs_sha256, "input manifest external SHA differs")
    _require(
        digest(report_path) == report_sha256, "report receipt external SHA differs"
    )
    im, rm = json.loads(input_path.read_text()), json.loads(report_path.read_text())
    _require(
        im["schema"] == "m2-analysis-inputs/v1"
        and rm["schema"] == "m2-report-analysis/v1",
        "unsupported receipt schema",
    )
    _require(rm["inputs"] == im, "report and input manifests differ")
    for name, expected in (
        ("wide.parquet", im["wide_sha256"]),
        ("bootstrap.npz", im["bootstrap"]["file_sha256"]),
    ):
        _require(digest(_bound(inputs, name)) == expected, name + " bytes differ")
    for name, expected in rm["outputs"].items():
        _require(
            digest(_bound(report, name)) == expected,
            "report output bytes differ: " + name,
        )
    nm_path = numerics / "numerics-manifest.json"
    _require(
        digest(nm_path) == rm["numerics_receipt_sha256"],
        "numerics manifest differs from report binding",
    )
    nm = json.loads(nm_path.read_text())
    contract = nm["contract"]
    _require(nm["complete"] and not nm["failures"], "original numerics incomplete")
    _require(
        contract["inputs_manifest_sha256"] == inputs_sha256
        and contract["wide_sha256"] == im["wide_sha256"]
        and contract["bootstrap_sha256"] == im["bootstrap"]["file_sha256"],
        "numerics input binding differs",
    )
    config = contract["configuration"]
    _require(
        config["convergence_sizes"] == [256, 512]
        and config["maximum_index_movement"] == 0.02,
        "original movement policy differs",
    )
    _require(
        len(contract["measures"]) == len(set(contract["measures"])) == 23,
        "original unique23 measure inventory differs",
    )
    for scope in nm["scopes"].values():
        for binding in scope["outputs"].values():
            _require(
                digest(_bound(numerics, binding["path"])) == binding["sha256"],
                "saved numerical scope bytes differ",
            )
    with np.load(inputs / "bootstrap.npz", allow_pickle=False) as saved:
        _require(
            set(saved.files) == set(im["bootstrap"]["matrices"]),
            "bootstrap inventory differs",
        )
        for key, binding in im["bootstrap"]["matrices"].items():
            values = saved[key]
            _require(
                values.dtype.kind in "iu" and list(values.shape) == binding["shape"],
                "bootstrap shape/type differs",
            )
            _require(
                hashlib.sha256(np.asarray(values, dtype="<i8").tobytes()).hexdigest()
                == binding["sha256"],
                "bootstrap canonical bytes differ",
            )
    return im, nm, rm


def reference_indices(a, b, ab):
    """Independent extended-precision equations, one measure, no shipped kernel.

    AB[:,j] replaces input j of A by B. Center on pooled A/B, use ddof0
    pooled variance, centered-B first and Jansen total. Constant outcomes are
    undefined. Values remain unclipped. Extended precision limits cancellation.
    """
    a, b, ab = (np.asarray(x, dtype=np.longdouble) for x in (a, b, ab))
    _require(
        a.ndim == b.ndim == 1
        and a.shape == b.shape
        and ab.ndim == 2
        and ab.shape[0] == len(a),
        "incompatible reference shapes",
    )
    _require(
        all(np.isfinite(x).all() for x in (a, b, ab)), "nonfinite reference outcome"
    )
    center = (np.sum(a) + np.sum(b)) / (2 * len(a))
    variance = (np.sum((a - center) ** 2) + np.sum((b - center) ** 2)) / (2 * len(a))
    if variance <= 0:
        return np.full(ab.shape[1], np.nan), np.full(ab.shape[1], np.nan)
    first = np.sum((b - center)[:, None] * (ab - a[:, None]), axis=0) / (
        len(a) * variance
    )
    total = np.sum((a[:, None] - ab) ** 2, axis=0) / (2 * len(a) * variance)
    _require(
        np.isfinite(first).all() and np.isfinite(total).all(),
        "nonfinite reference index",
    )
    return np.asarray(first, dtype=float), np.asarray(total, dtype=float)


def ordered_blocks(frame, family, n):
    """Check original i, hybrid geometry and stochastic identities before slicing."""
    names = FAMILY_INPUTS[family]
    d = len(names)
    _require(
        set(frame.block) == {"A", "B", "AB", "BA"} and len(frame) == n * (2 * d + 2),
        "incomplete Saltelli block inventory",
    )
    _require(not frame["index"].duplicated().any(), "repeated trajectory index")
    blocks = {}
    for role in ("A", "B"):
        part = frame[frame.block.eq(role)].sort_values("i")
        _require(
            len(part) == n and np.array_equal(part.i, np.arange(n)),
            "missing or repeated original base i",
        )
        for key in ("seed", "draw"):
            _require(
                part[key].notna().all() and part[key].nunique() == n,
                "A/B key repeats or is absent",
            )
        blocks[role] = part
    for key in ("seed", "draw"):
        _require(
            set(blocks["A"][key]).isdisjoint(blocks["B"][key]),
            "independent A/B keys collide",
        )
    coords = [f"u{j + 1}" for j in range(d)]
    for role, parent, donor in (("AB", "A", "B"), ("BA", "B", "A")):
        blocks[role] = []
        for j in range(d):
            part = frame[frame.block.eq(role) & frame.j.eq(j + 1)].sort_values("i")
            _require(
                len(part) == n and np.array_equal(part.i, np.arange(n)),
                "missing or repeated hybrid base i",
            )
            expected = blocks[parent][coords].to_numpy().copy()
            expected[:, j] = blocks[donor][coords].to_numpy()[:, j]
            _require(
                np.array_equal(part[coords], expected),
                "hybrid coordinate replacement differs",
            )
            for key in ("seed", "draw"):
                _require(
                    np.array_equal(part[key], blocks[parent][key]),
                    "hybrid parent seed/draw differs",
                )
            blocks[role].append(part)
    for part in [blocks["A"], blocks["B"], *blocks["AB"], *blocks["BA"]]:
        _require(part.baseline.notna().all(), "matched baseline identity absent")
        for j, name in enumerate(names):
            lo, hi = BOUNDS[name]
            _require(
                np.array_equal(part[name], lo + part[f"u{j + 1}"] * (hi - lo)),
                "physical coordinate scaling differs",
            )
    return blocks


def diagnose_scope(frame, saved, family, *, sizes=(256, 512), threshold=0.02):
    """Reconcile all original rows and expose per-input versus group movement."""
    small, large = sizes
    _require(large == 2 * small and small >= 2, "nested doubled sample sizes required")
    blocks = ordered_blocks(frame, family, large)
    _require(
        not saved.duplicated(["measure", "input"]).any(), "repeated saved index row"
    )
    measures = list(saved.measure.unique())
    _require(
        set(saved.input) == set(FAMILY_INPUTS[family])
        and len(saved) == len(measures) * len(FAMILY_INPUTS[family]),
        "saved measure/input inventory incomplete",
    )
    result = []
    for measure in measures:
        a, b = (blocks[k][measure].to_numpy() for k in ("A", "B"))
        ab = np.column_stack([part[measure] for part in blocks["AB"]])
        low = reference_indices(a[:small], b[:small], ab[:small])
        high = reference_indices(a, b, ab)
        change = np.maximum(np.abs(high[0] - low[0]), np.abs(high[1] - low[1]))
        maximum = float(np.max(change))
        for j, name in enumerate(FAMILY_INPUTS[family]):
            original = saved[(saved.measure == measure) & (saved.input == name)].iloc[0]
            for key, expected in (
                ("first", high[0][j]),
                ("total", high[1][j]),
                ("max_change", maximum),
            ):
                actual = float(original[key])
                _require(
                    (np.isnan(actual) and np.isnan(expected))
                    or np.isclose(actual, expected, atol=ATOL, rtol=ATOL),
                    "saved " + key + " does not reconcile",
                )
            expected_flag = None if not np.isfinite(maximum) else maximum <= threshold
            actual_flag = original.converged
            _require(
                (pd.isna(actual_flag) and expected_flag is None)
                or (
                    expected_flag is not None
                    and str(actual_flag).lower() == str(expected_flag).lower()
                ),
                "saved group convergence flag differs",
            )
            row = original.to_dict()
            row.update(
                {
                    "canonical_measure": "earned_rate"
                    if measure in MARGINS
                    else measure,
                    "affine_margin_alias": measure in MARGINS,
                    "first_256": low[0][j],
                    "total_256": low[1][j],
                    "pooled_AB_variance_256": float(
                        np.var(
                            np.concatenate((a[:small], b[:small])).astype(np.longdouble)
                        )
                    ),
                    "pooled_AB_variance_512": float(
                        np.var(np.concatenate((a, b)).astype(np.longdouble))
                    ),
                    "first_512_recomputed": high[0][j],
                    "total_512_recomputed": high[1][j],
                    "first_change": abs(high[0][j] - low[0][j]),
                    "total_change": abs(high[1][j] - low[1][j]),
                    "individual_max_change": change[j],
                    "recomputed_group_max_change": maximum,
                    "individual_converged": pd.NA
                    if not np.isfinite(change[j])
                    else change[j] <= threshold,
                    "propagated_failure_only": bool(
                        expected_flag is False and change[j] <= threshold
                    ),
                    "saved_first_abs_error": abs(float(original["first"]) - high[0][j]),
                    "saved_total_abs_error": abs(float(original["total"]) - high[1][j]),
                    "saved_max_change_abs_error": abs(
                        float(original["max_change"]) - maximum
                    ),
                    "first_interval_width": original.first_high - original.first_low,
                    "total_interval_width": original.total_high - original.total_low,
                }
            )
            result.append(row)
    return pd.DataFrame(result)


def extension_counts(scopes, extra_n=512):
    """Arithmetic plan only. Three-input mechanism-only hybrids share baselines."""
    design = sum(extra_n * (2 * len(FAMILY_INPUTS[family]) + 2) for family, _ in scopes)
    baseline = sum(extra_n * 6 for _ in scopes)
    return {
        "scope_count": len(scopes),
        "new_saltelli_design_rows": design,
        "new_matched_baseline_rows": baseline,
        "new_trajectories": design + baseline,
        "new_independent_seed_draw_pairs": 2 * extra_n * len(scopes),
        "new_noise_diagnostic_rows": 0,
        "new_control_or_anchor_rows": 0,
    }


def summarize(frame, group_keys):
    records = []
    for values, group in frame.groupby(group_keys, dropna=False, sort=True):
        if not isinstance(values, tuple):
            values = (values,)
        known = group.converged.notna()
        individual = group.individual_converged.notna()
        records.append(
            dict(zip(group_keys, values, strict=True))
            | {
                "original_rows": len(group),
                "group_flag_true": int(
                    group.loc[known, "converged"]
                    .astype(str)
                    .str.lower()
                    .eq("true")
                    .sum()
                ),
                "group_flag_false": int(
                    group.loc[known, "converged"]
                    .astype(str)
                    .str.lower()
                    .eq("false")
                    .sum()
                ),
                "undefined_rows": int((~known).sum()),
                "individual_true": int(
                    group.loc[individual, "individual_converged"].astype(bool).sum()
                ),
                "individual_false": int(
                    (~group.loc[individual, "individual_converged"].astype(bool)).sum()
                ),
                "propagated_failure_only": int(group.propagated_failure_only.sum()),
                "largest_individual_change": group.individual_max_change.max(),
                "largest_group_change": group.recomputed_group_max_change.max(),
                "max_first_interval_width": group.first_interval_width.max(),
                "max_total_interval_width": group.total_interval_width.max(),
            }
        )
    return pd.DataFrame(records)


def runtime_proposal(handoff_path, expected_sha256, report_receipt, new_trajectories):
    """Use authenticated observed wall throughput, never mislabel it CPU cost."""
    _require(
        expected_sha256 is not None and digest(handoff_path) == expected_sha256,
        "timing handoff external SHA differs",
    )
    handoff = json.loads(handoff_path.read_text())
    _require(
        handoff["custody"]["receipt_sha256"]
        == report_receipt["inputs"]["bindings"]["receipt_sha256"],
        "timing producer receipt differs",
    )
    n, seconds, workers = (
        handoff["counts"]["completed"],
        handoff["producer_timings"]["seconds"],
        handoff["host"]["workers"],
    )
    _require(n > 0 and seconds > 0 and workers > 0, "invalid measured runtime")
    normalized = seconds / n
    return {
        "timing_handoff_sha256": expected_sha256,
        "measured_trajectories": n,
        "measured_elapsed_seconds": seconds,
        "measured_workers": workers,
        "observed_wall_seconds_per_trajectory_at_measured_workers": normalized,
        "same_worker_throughput_hours": new_trajectories * normalized / 3600,
        "planning_allowance_1_5x_hours": new_trajectories * normalized * 1.5 / 3600,
        "observed_peak_worker_MiB": handoff["host"]["observed_worker_peak_mib"],
        "assumptions": [
            "Reuse measured machine/worker count and comparable trajectory mix. Setup, fit, transfer, audit and rerun time excluded.",
            "1.5x is an explicit planning allowance, not an observed bound or confidence interval. No standalone CPU cost or linear worker scaling claim.",
            "No monetary/energy cost measured. This diagnosis authorizes no new run or reservation.",
        ],
    }


def execute(
    inputs,
    numerics,
    report,
    output,
    *,
    inputs_sha256,
    report_sha256,
    timing_handoff=None,
    timing_handoff_sha256=None,
):
    started = time.perf_counter()
    _require(
        not output.exists() or not any(output.iterdir()),
        "use a new empty diagnosis output directory",
    )
    _im, nm, rm = authenticate(inputs, numerics, report, inputs_sha256, report_sha256)
    measures = nm["contract"]["measures"]
    saved_parts = [
        pd.read_csv(
            numerics / scope["outputs"]["csv"]["path"], float_precision="round_trip"
        )
        for key, scope in nm["scopes"].items()
        if key.startswith("mm3/")
    ]
    saved = pd.concat(saved_parts, ignore_index=True)
    _require(
        len(saved) == 2024 and not saved.duplicated(KEYS).any(),
        "original2024 index inventory differs",
    )
    report_sobol = pd.read_csv(
        report / "figure-4-sobol.csv", float_precision="round_trip"
    ).rename(
        columns={
            "Design family": "family",
            "Competing yield (%)": "yield_pp",
            "Horizon (days)": "horizon_days",
            "Measure": "measure",
            "Input": "input",
            "First-order index": "first",
            "Total-order index": "total",
            "Converged": "converged",
        }
    )
    _require(
        set(map(tuple, saved[KEYS].to_numpy()))
        == set(map(tuple, report_sobol[KEYS].to_numpy())),
        "report Sobol row inventory differs",
    )
    joined = saved.merge(
        report_sobol[KEYS + ["first", "total", "converged"]],
        on=KEYS,
        suffixes=("", "_report"),
        validate="one_to_one",
    )
    for key in ("first", "total"):
        _require(
            np.array_equal(joined[key], joined[key + "_report"], equal_nan=True),
            "report Sobol scalar differs",
        )
    _require(
        joined.converged.fillna("undefined")
        .astype(str)
        .str.lower()
        .equals(joined.converged_report.fillna("undefined").astype(str).str.lower()),
        "report convergence flags differ",
    )
    _require(
        saved.groupby(SCOPE).size().shape[0] == 32,
        "all32 family/yield/horizon scopes required",
    )
    parts, affine_errors = [], []
    db = duckdb.connect(config={"threads": 1, "memory_limit": "512MB"})
    for (family, yield_pp, horizon), old in saved.groupby(SCOPE, sort=True):
        _require(set(old.measure) == set(measures), "scope measure inventory differs")
        frame = db.execute(
            "SELECT * FROM read_parquet(?) WHERE family=? AND yield_pp=? AND horizon_days=? AND block IN ('A','B','AB','BA')",
            [str(inputs / "wide.parquet"), family, float(yield_pp), int(horizon)],
        ).df()
        _require(
            len(frame) == (6 if family == "before" else 8) * 512,
            "scope Saltelli row count differs",
        )
        for measure in MARGINS:
            differences = frame["earned_rate"] - frame[measure]
            error = float((differences - differences.iloc[0]).abs().max())
            _require(
                error <= 1e-14, "margin column is not a constant shift of earned_rate"
            )
            affine_errors.append(error)
        parts.append(diagnose_scope(frame, old, family))
    db.close()
    full = pd.concat(parts, ignore_index=True)
    unique = full.loc[~full.affine_margin_alias].copy()
    _require(
        len(unique) == 1408 and unique.canonical_measure.nunique() == 16,
        "unique base-measure count differs",
    )
    noise = pd.read_csv(
        report / "noise-variance-share.csv", float_precision="round_trip"
    ).rename(
        columns={
            "Design family": "family",
            "Competing yield (%)": "yield_pp",
            "Horizon (days)": "horizon_days",
            "Measure": "measure",
        }
    )
    _require(
        len(noise) == 736 and not noise.duplicated(SCOPE + ["measure"]).any(),
        "noise diagnostic inventory differs",
    )
    mapped = full.merge(
        noise[
            SCOPE
            + [
                "measure",
                "noise_share",
                "ci_low",
                "ci_high",
                "between_truncated",
                "status",
            ]
        ],
        on=SCOPE + ["measure"],
        how="left",
        validate="many_to_one",
        suffixes=("", "_noise"),
    )
    mapped["relative_policy_kpi"] = mapped.measure.isin(RELATIVE)
    important = mapped.loc[mapped.measure.isin((*RELATIVE, "earned_rate"))].copy()
    important["rank_total_within_measure"] = important.groupby(SCOPE + ["measure"])[
        "total"
    ].rank(ascending=False, method="min")
    group_keys = SCOPE + ["measure"]
    groups = summarize(full, group_keys)
    unique_groups = summarize(unique, group_keys)
    scopes = sorted(
        {
            (row.family, float(row.yield_pp))
            for row in unique.itertuples()
            if str(row.converged).lower() == "false"
        }
    )
    proposal = {
        "status": "proposal_only_no_generation_or_execution",
        "current_base_n": 512,
        "next_base_n": 1024,
        "next_check": [512, 1024],
        "maximum_index_movement": 0.02,
        "smallest_next_step_reason": "One further power-of-two doubling supplies an assessable nested check; observed256/512 instability cannot justify assuming any final sufficient N.",
        "scopes_with_any_unique_measure_failure": [list(scope) for scope in scopes],
        "extension": extension_counts(scopes),
        "all16_scope_extension": extension_counts(
            [(f, y) for f in FAMILY_INPUTS for y in (3.0, 5.0, 7.0, 10.0)]
        ),
        "full_inventory_if_all16_scopes_extended": {
            "total_trajectories": 243392,
            "design_rows": 135616,
            "matched_baselines": 107776,
            "saltelli_design_rows": 122880,
            "independent_seed_draw_pairs": 41280,
            "retained_noise_rows": 8192,
            "retained_zero_rows": 1024,
            "retained_stress_rows": 3072,
            "retained_implementation_control_rows": 448,
            "retained_consumer_control_checks": 1344,
        },
        "conditions": [
            "Authenticate and retain original row IDs, values, source/model/input pins and all old seed/draw assignments. A naive rebuild with N changed reallocates sequential keys and cannot be claimed as an extension.",
            "Continue each original scrambled2k-dimensional Sobol sequence, original scramble seed and input order, append i512..1023; byte-verify the original512 coordinate prefix before any execution.",
            "Allocate distinct fresh A/B seed AND parameter-draw identities per new i without changing old identities. AB inherits A; BA inherits B. Retain all2k+2 roles and complete original i units.",
            "Pair every new row with ChainReward under identical seed/draw, responses and both yields; deduplicate baselines only when the complete paired identity agrees. Expected6 new baselines per i per scope assumes3-input mechanism-only hybrids share their parent baseline and2-input families have no such sharing.",
            "Retain both180/365 horizons from each365-day trajectory. Measure/cost aliases do not create trajectories. Freeze complete eligible scope/measure inventory and conditional resampling plan prospectively.",
            "Retain existing64 noise points x8 keys,64 shared anchors and seven64-key controls byte-for-byte, count them once and explicitly label them retained diagnostics. Fresh-noise validation or expanded noise points needs its own prospective design and additional budget.",
            "Preserve independent A/B noise, parent-key hybrids, fitted-parameter-draw meaning and all original baselines. Parameter/noise uncertainty remains mixed as designed; no causal or empirical QMC coverage conclusion follows.",
            "Keep finite negative/>1 indices and undefined constants. Apply the original max across every input first/total within each measure, retain individual diagnostics, stop or plan another prospective step if1024 fails. Do not claim convergence merely from higherN.",
            "The current generator/consumer hard-code512 and132800. A prospective new design/consumer contract must validate the new inventory and retained-row mapping; do not mutate or relabel the old bundle. Define an extension/union ordering that retains old row IDs and makes all new baseline references explicit.",
            "Retain the original24896 parameter-draw rows byte-for-byte and append16384 new distinct draws only after qualifying prefix preservation and source pins. Freeze new1000-by1024 whole-i bootstrap arrays prospectively, jointly across measures/costs/horizons; the saved1000-by512 arrays are not the extended plan.",
        ],
        "runtime": "No runtime promise without an authenticated measured trajectory-cost input; saved analysis timing is not simulation cost.",
    }
    canonical = full.loc[
        full.measure.eq("earned_rate"), SCOPE + ["input", "first", "total", "converged"]
    ]
    aliases = full.loc[full.affine_margin_alias].merge(
        canonical,
        on=SCOPE + ["input"],
        suffixes=("", "_canonical"),
        validate="many_to_one",
    )
    _require(
        np.allclose(aliases["first"], aliases.first_canonical, atol=ATOL, rtol=ATOL)
        and np.allclose(aliases.total, aliases.total_canonical, atol=ATOL, rtol=ATOL),
        "affine alias index invariance fails",
    )
    _require(
        aliases.converged.astype(str)
        .str.lower()
        .equals(aliases.converged_canonical.astype(str).str.lower()),
        "affine alias convergence differs",
    )
    if timing_handoff is not None:
        proposal["runtime"] = runtime_proposal(
            timing_handoff,
            timing_handoff_sha256,
            rm,
            proposal["extension"]["new_trajectories"],
        )
    else:
        _require(
            timing_handoff_sha256 is None, "timing hash supplied without timing handoff"
        )
    output.mkdir(parents=True, exist_ok=True)
    outputs = {
        "index-diagnosis.csv": full,
        "measure-summary.csv": groups,
        "unique-measure-summary.csv": unique_groups,
        "scope-summary.csv": summarize(full, SCOPE),
        "unique-scope-summary.csv": summarize(unique, SCOPE),
        "measure-totals.csv": summarize(full, ["measure"]),
        "unique-measure-totals.csv": summarize(unique, ["canonical_measure"]),
        "relative-kpi-noise-context.csv": important,
    }
    for name, table in outputs.items():
        table.to_csv(output / name, index=False)
    (output / "higher-n-proposal.json").write_text(
        json.dumps(proposal, indent=2, allow_nan=False) + "\n"
    )
    counts = (
        summarize(full.assign(inventory="display23"), ["inventory"]).iloc[0].to_dict()
    )
    unique_counts = (
        summarize(unique.assign(inventory="unique16"), ["inventory"]).iloc[0].to_dict()
    )
    receipt = {
        "schema": "m2-convergence-diagnosis/v1",
        "status": "diagnosed_saved_results_only",
        "input_manifest_sha256": inputs_sha256,
        "report_receipt_sha256": report_sha256,
        "numerics_manifest_sha256": digest(numerics / "numerics-manifest.json"),
        "frozen_delivery_revision": rm["analysis_delivery_revision"],
        "original_method_source_sha256": nm["contract"]["source_sha256"],
        "diagnosis_source_sha256": digest(Path(__file__)),
        "counts": counts,
        "unique_counts": unique_counts,
        "max_affine_value_residual": max(affine_errors),
        "margin_aliases": list(MARGINS),
        "canonical_margin_base": "earned_rate",
        "affine_alias_count": len(aliases),
        "affine_alias_indices_and_flags_reconciled": True,
        "largest_reconciliation_errors": {
            key: float(full[key].max())
            for key in (
                "saved_first_abs_error",
                "saved_total_abs_error",
                "saved_max_change_abs_error",
            )
        },
        "reference_precision": "independent np.longdouble equations; comparison absolute and relative1e-10, no source-kernel calls",
        "outputs": {
            name: digest(output / name) for name in [*outputs, "higher-n-proposal.json"]
        },
        "elapsed_seconds": time.perf_counter() - started,
        "limits": [
            "Intervals/noise diagnostics are authenticated retained values, not recalculated interval coverage or causal attribution.",
            "Group-max flags deliberately repeat across inputs; affine margin aliases are retained in original display accounting but excluded from unique-measure accounting.",
            "HigherN is a proposal requiring generator/runner inventory and nesting qualification; no new coordinates, RNG draws, simulation or fitting executed.",
        ],
    }
    (output / "diagnosis-receipt.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    )
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "numerics", "report", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--inputs-sha256", required=True)
    parser.add_argument("--report-sha256", required=True)
    parser.add_argument("--timing-handoff", type=Path)
    parser.add_argument("--timing-handoff-sha256")
    args = parser.parse_args()
    receipt = execute(**vars(args))
    print(
        json.dumps(
            {
                key: receipt[key]
                for key in ("status", "counts", "unique_counts", "elapsed_seconds")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
