"""Run MM1/MM3 on SHA-bound wide inputs and supplied joint bootstrap arrays.

No simulation, sampling, model fit or network access. Each family/horizon scope
writes atomic CSV/JSON results and a resumable manifest. Missing or changed
completed bytes refuse reuse. Method/source/input hashes bind every checkpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import time
from pathlib import Path

import duckdb
import numpy as np

from avalanche_research.analysis import (
    m2_associations,
    m2_sensitivity,
    paired_sweep,
    rank_associations,
    sobol,
)
from avalanche_research.analysis.paired_sweep import MEASURES as ABSOLUTE_MEASURES

MEASURES = (
    *ABSOLUTE_MEASURES,
    "return_margin",
    "issuance_saved",
    "validator_stake_retained",
    "active_validators_retained",
    "return_margin_low",
    "return_margin_mid",
    "return_margin_high",
    "return_margin_low_fitting_price",
    "return_margin_mid_fitting_price",
    "return_margin_high_fitting_price",
)
METHOD_CONFIGURATION = {
    "bootstrap_replicates": 1000,
    "bootstrap_seed_declared_by_prepare": 20261005,
    "confidence": 0.95,
    "convergence_sizes": [256, 512],
    "maximum_index_movement": 0.02,
    "pvalue_method": m2_associations.PERCENTILE_INVERSION,
    "BH_matrix_keys": [
        "family",
        "yield_pp",
        "horizon_days",
        "renewal_band",
        "entry_band",
        "method",
    ],
    "undefined_BH_slots": "p=1 bookkeeping only; exported p/q/star stay unknown",
    "MM1_roles": ["A", "B"],
    "MM1_population": "full plus nine response cells; separate pooled-yield Spearman",
    "MM3_roles": ["A", "B", "AB", "BA"],
    "batch_size": 32,
    "interval_interpretation": "conditional design bootstrap; no empirical FDR/coverage or causal guarantee",
}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as source:
        for part in iter(lambda: source.read(1024 * 1024), b""):
            result.update(part)
    return result.hexdigest()


def source_digests():
    modules = [m2_associations, m2_sensitivity, rank_associations, sobol, paired_sweep]
    return {
        **{module.__name__: digest(module.__file__) for module in modules},
        "m2_numerics.py": digest(__file__),
    }


def atomic_json(path, value):
    pending = path.with_name(path.name + ".pending")
    pending.write_text(
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    )
    pending.replace(path)


def _output_binding(path, directory):
    return {
        "path": str(path.relative_to(directory)),
        "sha256": digest(path),
        "bytes": path.stat().st_size,
    }


def execute(wide, bootstrap, manifest_path, output, *, manifest_sha256):
    """Consume the root-prepared m2-analysis-inputs/v1 schema, never raw outputs."""
    if digest(manifest_path) != manifest_sha256:
        raise ValueError("input manifest differs from external SHA freeze")
    inputs = json.loads(manifest_path.read_text())
    if inputs.get("schema") != "m2-analysis-inputs/v1":
        raise ValueError("supported prepared input manifest required")
    expected_wide, expected_bootstrap = (
        inputs["wide_sha256"],
        inputs["bootstrap"]["file_sha256"],
    )
    if digest(wide) != expected_wide or digest(bootstrap) != expected_bootstrap:
        raise ValueError("wide/bootstrap bytes differ from externally pinned manifest")
    if (
        inputs["bootstrap"]["seed"] != 20261005
        or inputs["bootstrap"]["replicates"] != 1000
    ):
        raise ValueError("frozen bootstrap seed/count required")
    if len(MEASURES) != 23:
        raise ValueError("frozen 23-measure inventory differs")
    pinned_sources = source_digests()
    contract = {
        "schema": "m2-numerics-contract/v1",
        "inputs_manifest_sha256": manifest_sha256,
        "wide_sha256": expected_wide,
        "bootstrap_sha256": expected_bootstrap,
        "source_sha256": pinned_sources,
        "configuration": METHOD_CONFIGURATION,
        "measures": list(MEASURES),
    }
    output.mkdir(parents=True, exist_ok=True)
    receipt_path = output / "numerics-manifest.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt.get("contract") != contract:
            raise ValueError(
                "resume contract/source/input differs; preserve old output and use a new directory"
            )
        for scope in receipt["scopes"].values():
            for binding in scope["outputs"].values():
                if digest(output / binding["path"]) != binding["sha256"]:
                    raise ValueError(
                        "completed result bytes changed; no stale cache reuse"
                    )
    else:
        if any(output.iterdir()):
            raise ValueError("nonempty output directory lacks its resumable manifest")
        receipt = {
            "schema": "m2-numerics-run/v1",
            "contract": contract,
            "scopes": {},
            "complete": False,
            "scientific_acceptance": False,
            "failures": [],
        }
        atomic_json(receipt_path, receipt)
    with np.load(bootstrap, allow_pickle=False) as saved:
        if set(saved.files) != set(inputs["bootstrap"]["matrices"]):
            raise ValueError("bootstrap matrix inventory differs")
        for key, binding in inputs["bootstrap"]["matrices"].items():
            matrix = saved[key]
            if (
                matrix.dtype.kind not in "iu"
                or list(matrix.shape) != binding["shape"]
                or m2_associations._digest(matrix) != binding["sha256"]
            ):
                raise ValueError("bootstrap matrix shape/bytes differ")
        db = duckdb.connect(config={"threads": 1, "memory_limit": "512MB"})
        discovered = db.execute(
            "SELECT DISTINCT family,horizon_days,yield_pp FROM read_parquet(?) WHERE block='A' ORDER BY family,horizon_days,yield_pp",
            [str(wide)],
        ).fetchall()
        if not discovered:
            raise ValueError("wide cache contains no method scopes")
        families = sorted({row[0] for row in discovered})
        horizons = sorted({int(row[1]) for row in discovered})
        if not set(families) <= set(m2_associations.FAMILY_INPUTS) or not set(
            horizons
        ) <= {180, 365}:
            raise ValueError("unknown family or horizon in prepared cache")
        planned = [(f, horizon) for f in families for horizon in horizons]
        receipt["requested_family_horizon_scopes"] = [[f, h] for f, h in planned]
        receipt["full_four_family_two_horizon_yield_inventory"] = (
            set(families) == set(m2_associations.FAMILY_INPUTS)
            and horizons == [180, 365]
            and all(
                {float(y) for f, h, y in discovered if f == family and h == horizon}
                == {3.0, 5.0, 7.0, 10.0}
                for family, horizon in planned
            )
        )
        atomic_json(receipt_path, receipt)
        for family, horizon in planned:
            needed = [
                method
                for method in ("mm1", "mm3")
                if f"{method}/{family}/{horizon}" not in receipt["scopes"]
            ]
            if not needed:
                continue
            frame = db.execute(
                "SELECT * FROM read_parquet(?) WHERE family=? AND horizon_days=? AND block IN ('A','B','AB','BA')",
                [str(wide), family, horizon],
            ).df()
            if frame.empty:
                raise ValueError("expected family/horizon population is absent")
            scope_draws = {}
            for yield_pp in sorted(frame.yield_pp.unique()):
                key = f"{family}__{float(yield_pp)}"
                if key not in saved.files:
                    raise ValueError("family/yield bootstrap matrix absent")
                scope_draws[family, float(yield_pp)] = saved[key]
            for method in needed:
                name = f"{method}/{family}/{horizon}"
                started, cpu_started = time.perf_counter(), time.process_time()
                try:
                    if source_digests() != pinned_sources:
                        raise ValueError("method source changed during execution")
                    if method == "mm1":
                        values, metadata = m2_associations.analyze_associations(
                            frame,
                            measures=MEASURES,
                            bootstrap_indices=scope_draws,
                            pvalue_method=m2_associations.PERCENTILE_INVERSION,
                        )
                    else:
                        values, metadata = m2_sensitivity.analyze_sensitivity(
                            frame, measures=MEASURES, bootstrap_indices=scope_draws
                        )
                    if source_digests() != pinned_sources:
                        raise ValueError("method source changed during execution")
                    stem = f"{method}__{family}__{horizon}"
                    csv_path, metadata_path = (
                        output / (stem + ".csv"),
                        output / (stem + ".json"),
                    )
                    pending = csv_path.with_name(csv_path.name + ".pending")
                    values.to_csv(pending, index=False)
                    pending.replace(csv_path)
                    atomic_json(metadata_path, metadata)
                    receipt["scopes"][name] = {
                        "rows": len(values),
                        "seconds": time.perf_counter() - started,
                        "cpu_seconds": time.process_time() - cpu_started,
                        "peak_process_RSS_MiB": resource.getrusage(
                            resource.RUSAGE_SELF
                        ).ru_maxrss
                        / 1024,
                        "outputs": {
                            "csv": _output_binding(csv_path, output),
                            "metadata": _output_binding(metadata_path, output),
                        },
                    }
                    atomic_json(receipt_path, receipt)
                    print(
                        json.dumps(
                            {
                                "scope": name,
                                "rows": len(values),
                                "seconds": receipt["scopes"][name]["seconds"],
                            }
                        ),
                        flush=True,
                    )
                except Exception as error:
                    receipt["failures"].append(
                        {
                            "scope": name,
                            "error": type(error).__name__,
                            "message": str(error),
                        }
                    )
                    atomic_json(receipt_path, receipt)
                    raise
        db.close()
    if digest(wide) != expected_wide or digest(bootstrap) != expected_bootstrap:
        raise ValueError(
            "prepared inputs changed during execution; results remain incomplete"
        )
    receipt["complete"] = len(receipt["scopes"]) == 2 * len(planned)
    receipt["outputs"] = {
        b["path"]: b["sha256"]
        for scope in receipt["scopes"].values()
        for b in scope["outputs"].values()
    }
    atomic_json(receipt_path, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("wide", "bootstrap", "manifest", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument(
        "--manifest-sha256",
        required=True,
        help="External SHA256 of the prepare manifest",
    )
    args = parser.parse_args()
    # Set before subprocess launch as well. Refuse accidental multithreaded runs.
    for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        if os.environ.get(variable) != "1":
            parser.error(variable + "=1 is required for the declared one-thread budget")
    execute(
        args.wide,
        args.bootstrap,
        args.manifest,
        args.output,
        manifest_sha256=args.manifest_sha256,
    )


if __name__ == "__main__":
    main()
