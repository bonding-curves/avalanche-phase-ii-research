#!/usr/bin/env python3
"""Authenticate a paired M2 sweep and prepare shared analysis inputs.

Use --help for the explicit input bindings. Generated trajectories and caches
remain external inputs and are never downloaded or simulated by this command.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import duckdb
import numpy as np

from avalanche_research.analysis.m2_contract import BOOTSTRAP_SEED
from avalanche_research.analysis.m2_resampling import (
    draw_indices,
    indices_sha256,
    scope_draws,
)
from avalanche_research.analysis.m2_tables import analysis_table
from avalanche_research.analysis.paired_sweep import (
    control_checks,
    read_bundle,
    read_outputs,
)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def bootstrap_bundle(bundle, directory):
    """Generate once in declared scope order, before inspecting KPI values."""
    rng = np.random.default_rng(20261005)
    matrices = {f"{family}__{yield_pp}": indices
                for (family, yield_pp), indices in scope_draws(bundle.labels, rng).items()}
    labels = bundle.labels
    for yield_pp in sorted(labels.loc[labels.block.isin(("zero", "stress")), "yield_pp"].unique()):
        anchors = labels.loc[labels.block.isin(("zero", "stress")) & labels.yield_pp.eq(yield_pp)]
        units = sorted(anchors.i.unique())
        if units != list(range(64)):
            raise ValueError("complete original anchor units 0..63 required")
        matrices[f"anchor__{yield_pp}"] = draw_indices(len(units), rng)
    noise = labels.loc[labels.block.eq("noise")]
    for (family, yield_pp), scope in noise.groupby(["family", "yield_pp"], sort=True):
        if not scope.groupby("i").j.apply(lambda v: set(v) == set(range(8))).all():
            raise ValueError("all eight keys per noise point required")
        units = sorted(scope.i.unique())
        if units != list(range(64)):
            raise ValueError("complete original noise points 0..63 required")
        matrices[f"noise__{family}__{yield_pp}"] = draw_indices(len(units), rng)
    target = directory / "bootstrap.npz"
    if target.exists():
        with np.load(target, allow_pickle=False) as old:
            if set(old.files) != set(matrices) or any(not np.array_equal(old[k], v) for k, v in matrices.items()):
                raise ValueError("existing bootstrap differs from the frozen input design")
    else:
        np.savez_compressed(target, **matrices)
    manifest = {"seed": BOOTSTRAP_SEED, "replicates": 1000,
                "order": "Saltelli family/yield, shared anchors yield, noise family/yield; original numeric i",
                "file_sha256": digest(target),
                "matrices": {k: {"shape": list(v.shape), "sha256": indices_sha256(v)}
                             for k, v in matrices.items()}}
    (directory / "bootstrap-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--bindings", type=Path, required=True,
                        help="JSON: bundle_sha256 (all four files), code_commit, pin_sha256, receipt_sha256")
    parser.add_argument("--output", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--raw", type=Path, help="Original trajectory directory with receipt.json")
    source.add_argument("--absolute-cache", type=Path, help="Previously authenticated absolute.parquet")
    parser.add_argument("--acceptance", type=Path, help="Consumer receipt binding the absolute cache")
    parser.add_argument("--acceptance-sha256", help="Externally recorded consumer receipt digest")
    args = parser.parse_args()
    started = time.perf_counter()
    binding = json.loads(args.bindings.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    bundle = read_bundle(args.bundle, binding["bundle_sha256"])
    bootstrap = bootstrap_bundle(bundle, args.output)
    if args.raw:
        absolute, receipt, files = read_outputs(args.raw, bundle,
            code_commit=binding["code_commit"], pin_sha256=binding["pin_sha256"],
            receipt_sha256=binding["receipt_sha256"])
        (args.output / "raw-file-hashes.json").write_text(json.dumps(files, sort_keys=True) + "\n")
        consumer = {"receipt_id": receipt["receipt_id"], "receipt_sha256": binding["receipt_sha256"]}
    else:
        if not args.acceptance or not args.acceptance_sha256 or digest(args.acceptance) != args.acceptance_sha256:
            parser.error("cache requires an externally SHA256-bound consumer acceptance receipt")
        consumer = json.loads(args.acceptance.read_text())
        if consumer["files"]["absolute.parquet"]["sha256"] != digest(args.absolute_cache):
            raise ValueError("absolute cache digest differs")
        if consumer["producer"] != binding["code_commit"] or consumer["receipt_sha256"] != binding["receipt_sha256"]:
            raise ValueError("cache producer/receipt binding differs")
        absolute = duckdb.sql("SELECT * FROM read_parquet(?)", params=[str(args.absolute_cache)]).df()
    if len(bundle.rows) != 132800 or len(absolute) != 3718400:
        raise ValueError("full M2 source counts differ")
    controls = control_checks(absolute, bundle)
    if len(controls) != 1344 or not controls.passed.all():
        raise ValueError("full declared controls failed")
    wide = analysis_table(absolute, bundle)
    if len(wide) != 265600:
        raise ValueError("wide horizon/trajectory cardinality differs")
    target = args.output / "wide.parquet"
    connection = duckdb.connect()
    connection.register("wide", wide)
    temporary = args.output / "wide.pending.parquet"
    connection.execute("COPY wide TO ? (FORMAT PARQUET)", [str(temporary)])
    temporary.replace(target)
    controls.to_csv(args.output / "controls.csv", index=False)
    manifest = {"schema": "m2-analysis-inputs/v1", "bindings": binding,
                "consumer": consumer, "rows": len(wide), "absolute_cells": len(absolute),
                "relative_cells": 445056, "controls": len(controls),
                "wide_sha256": digest(target), "bootstrap": bootstrap,
                "prepare_source_sha256": digest(__file__),
                "elapsed_seconds": time.perf_counter() - started}
    (args.output / "inputs-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"rows": len(wide), "controls": len(controls), "wide_sha256": manifest["wide_sha256"]}), flush=True)


if __name__ == "__main__":
    main()
