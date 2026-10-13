"""Read an explicitly frozen paired sweep and write reproducible analysis tables.

python scripts/m2_sweep_analysis.py BUNDLE OUTPUTS FREEZE DESTINATION
FREEZE names bundle_sha256, code_commit, pin_sha256 and receipt_sha256. The producer retains
the run receipt. This command starts no simulations, fits or external services.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from avalanche_research.analysis.paired_sweep import (
    control_checks,
    read_bundle,
    read_outputs,
    relative_kpis,
)
from avalanche_research.core.hashing import canonical_bytes, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "outputs", "freeze", "destination"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    freeze_bytes = args.freeze.read_bytes()
    frozen = json.loads(freeze_bytes)
    bundle = read_bundle(args.bundle, frozen["bundle_sha256"])
    table, receipt, raw_hashes = read_outputs(args.outputs, bundle, code_commit=frozen["code_commit"],
                                            pin_sha256=frozen["pin_sha256"], receipt_sha256=frozen["receipt_sha256"])
    ratios = relative_kpis(table, bundle)
    controls = control_checks(table, bundle)
    args.destination.mkdir(parents=True, exist_ok=False)
    table.to_csv(args.destination / "absolute-kpis.csv", index=False)
    ratios.to_csv(args.destination / "relative-kpis.csv", index=False)
    controls.to_csv(args.destination / "controls.csv", index=False)
    report = {"schema": "paired-sweep-analysis/v1", "run_receipt": receipt["receipt_id"],
              "code_commit": frozen["code_commit"], "freeze_sha256": sha256(freeze_bytes),
              "bundle_sha256": bundle.hashes, "output_parquet_sha256": raw_hashes,
              "expected_trajectories": len(bundle.rows), "observed_trajectories": int(table.row_id.nunique()),
              "absolute_cells": len(table), "relative_cells": len(ratios),
              "controls_pass": bool(controls.passed.all()),
              "scientific_scope": "paired KPI and declared control consumption; no final sensitivity convergence or adoption",
              "generated_files_sha256": {p.name: sha256(p.read_bytes()) for p in args.destination.glob("*.csv")}}
    (args.destination / "analysis-receipt.json").write_bytes(canonical_bytes(report))
    print(json.dumps({k: report[k] for k in ("run_receipt", "observed_trajectories", "controls_pass")}))
    return 0 if report["controls_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
