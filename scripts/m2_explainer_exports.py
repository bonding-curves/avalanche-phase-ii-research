#!/usr/bin/env python3
"""Export additive explainer tables from authenticated saved M2 results.

Replay from a delivery checkout with the model dependencies installed::

    python scripts/m2_explainer_exports.py --inputs INPUT_CACHE \
      --inputs-sha256 INPUT_MANIFEST_SHA --decisions DECISION_RESULTS \
      --report FROZEN_REPORT --report-sha256 REPORT_RECEIPT_SHA --output NEW_DIR

No simulation, fit, random draw, bootstrap or selected-box re-evaluation occurs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from pathlib import Path

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import duckdb
import pandas as pd

from avalanche_research.analysis.explainer_pairs import (
    matched_natural_units,
    units_metadata,
)
from avalanche_research.analysis.explainer_tiers import tier_cell_detail

DECISION_TABLES = (
    "range-confirmations.csv", "point-estimates.csv",
    "baseline-comparison-cells.csv", "pass-shares.csv",
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(2**20), b""):
            digest.update(part)
    return digest.hexdigest()


def authenticate_outputs(directory, bindings):
    if not bindings:
        raise ValueError("empty source artifact bindings")
    for name, digest in bindings.items():
        if Path(name).name != name or name in (".", ".."):
            raise ValueError("source artifact names must be flat relative filenames")
        if sha(directory / name) != digest:
            raise ValueError(f"changed source artifact: {name}")


def authenticate(inputs, inputs_sha256, decisions, report, report_sha256):
    if sha(inputs / "inputs-manifest.json") != inputs_sha256:
        raise ValueError("input manifest differs from external hash")
    if sha(report / "analysis-receipt.json") != report_sha256:
        raise ValueError("report receipt differs from external hash")
    manifest = json.loads((inputs / "inputs-manifest.json").read_text())
    parent = json.loads((report / "analysis-receipt.json").read_text())
    if manifest != parent["inputs"]:
        raise ValueError("input cache differs from frozen report inputs")
    if sha(inputs / "wide.parquet") != manifest["wide_sha256"]:
        raise ValueError("changed saved wide cache")
    authenticate_outputs(report, parent["outputs"])
    if sha(decisions / "decisions-receipt.json") != parent["decisions_receipt_sha256"]:
        raise ValueError("changed saved decisions receipt")
    decision_receipt = json.loads((decisions / "decisions-receipt.json").read_text())
    if decision_receipt["outputs"] != parent["decision_inputs"]:
        raise ValueError("decision artifact bindings differ from frozen report")
    authenticate_outputs(decisions, decision_receipt["outputs"])
    if not set(DECISION_TABLES) <= set(decision_receipt["outputs"]):
        raise ValueError("missing saved decision tables")
    return manifest, parent, decision_receipt


def points_with_set(frame):
    """Retain every DR5 field/row and alias the existing A/B Role as Set."""
    required = {"First input", "Second input", "Role"}
    if not required <= set(frame):
        raise ValueError("DR5 requires explicit input names and A/B roles")
    if not set(frame.Role) == {"A", "B"}:
        raise ValueError("DR5 Role must contain discovery A and confirmation B")
    if frame[["First input", "Second input"]].isna().any().any() or frame[["First input", "Second input"]].eq("").any().any():
        raise ValueError("DR5 input names must be present")
    if "Set" in frame and not frame.Set.equals(frame.Role):
        raise ValueError("existing Set differs from Role")
    return frame.assign(Set=frame.Role)


def export(inputs, inputs_sha256, decisions, report, report_sha256, output):
    inputs, decisions, report, output = map(Path, (inputs, decisions, report, output))
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("use a new empty export directory")
    for source in (inputs, decisions, report):
        if output.resolve().is_relative_to(source.resolve()) or source.resolve().is_relative_to(output.resolve()):
            raise ValueError("output must be separate from saved source directories")
    manifest, parent, decision_receipt = authenticate(inputs, inputs_sha256, decisions, report, report_sha256)
    with duckdb.connect(config={"threads": 1}) as connection:
        wide = connection.execute("SELECT * FROM read_parquet(?)", [str(inputs / "wide.parquet")]).df()
    if len(wide) != manifest["rows"] or len(wide) != 265600:
        raise ValueError("complete saved 132800-trajectory input cache required")
    paired = matched_natural_units(wide)
    if len(paired) != 148352 or paired["index"].nunique() != 74176:
        raise ValueError("complete 74176-design, two-horizon export required")
    if paired.duplicated(["index", "horizon_days"]).any() or not paired.groupby("index").horizon_days.agg(lambda values: set(values) == {180, 365}).all():
        raise ValueError("each design requires exactly 180 and 365 days")
    tables = [pd.read_csv(decisions / name, float_precision="round_trip", low_memory=False) for name in DECISION_TABLES]
    tiers = tier_cell_detail(*tables)
    if len(tables[0]) != 9504 or len(tables[1]) != 288 or len(tiers) != 127296:
        raise ValueError("saved recommendation inventory differs")
    # Strings retain original CSV values, including Boolean and numerical text.
    points = pd.read_csv(report / "figure-5-points.csv", dtype=str, keep_default_na=False)
    revised_points = points_with_set(points)
    units = units_metadata()
    units["tier_cell_detail"] = {
        "MG9": "partial against full cross-cell recommendation schema",
        "recommendation": "Only source-cell statistics are saved. Other cells are unsupported/null with reasons.",
        "family_context": "Whole family population, never evidence for a selected point or box.",
        "family_context_mean": "Paired ratio minus reference: issuance_saved minus 0; retained ratios minus 1. Dimensionless.",
        "recommendation_mean": "Saved goal_mean (issuance_saved) or observed A-point issuance_saved, relative to zero; no joint-goal effect.",
        "sign": "Arithmetic sign of the saved mean, not significance, causal direction or recommendation reversal.",
        "intervals": "Existing conditional-design 95% intervals copied without recalculation; observed points have no validated interval.",
        "pass_share": "fraction meeting source target, alternative and cost; family and recommendation populations remain separate.",
        "source_data_row_zero_based": "Ordinal after CSV header, before bound expansion, in hash-bound source_artifact.",
        "scope": "Nine response-band cells, zero and three individually identified stress settings per recommendation. Tiers remain provisional until QB19.",
    }
    units["figure_5_points"] = {"Set": "Exact alias of original Role. A discovery, B confirmation.", "other_columns": "Original names, row order and CSV cell text retained."}
    output.mkdir(parents=True, exist_ok=True)
    paired.to_csv(output / "matched-natural-units.csv", index=False)
    tiers.to_csv(output / "tier-cell-detail.csv", index=False)
    revised_points.to_csv(output / "figure-5-points.csv", index=False)
    (output / "units.json").write_text(json.dumps(units, indent=2, allow_nan=False) + "\n")
    # Recheck frozen bytes after export. No receipt is issued on source mutation.
    authenticate(inputs, inputs_sha256, decisions, report, report_sha256)
    root = Path(__file__).resolve().parents[1]
    source_paths = [Path(__file__).resolve(), root / "src/avalanche_research/analysis/explainer_pairs.py", root / "src/avalanche_research/analysis/explainer_tiers.py"]
    receipt = {
        "schema": "m2-explainer-exports/v1", "status": "exported_pending_independent_review",
        "scope": {"MG8": "complete saved paired rows and algebraic units export", "MG9": "partial: source-cell recommendation evidence plus separate 13-cell family context", "MG10": "Set alias; existing input names retained"},
        "inputs_manifest_sha256": inputs_sha256, "wide_sha256": manifest["wide_sha256"],
        "parent_report_receipt_sha256": report_sha256,
        "parent_report_outputs": parent["outputs"],
        "decisions_receipt_sha256": parent["decisions_receipt_sha256"],
        "decision_inputs": decision_receipt["outputs"],
        "outputs": {name: sha(output / name) for name in ("matched-natural-units.csv", "tier-cell-detail.csv", "figure-5-points.csv", "units.json")},
        "rows": {"matched-natural-units.csv": len(paired), "tier-cell-detail.csv": len(tiers), "figure-5-points.csv": len(revised_points)},
        "recommendations": {"source_records": len(tables[0]) + len(tables[1]), "cells_per_record": 13, "source_cell_rows": int(tiers.recommendation_evidence_scope.eq("source cell only").sum()), "unsupported_cross_cell_rows": int(tiers.recommendation_evidence_scope.eq("unsupported cross-cell").sum())},
        "source_sha256": {str(path.relative_to(root)): sha(path) for path in source_paths},
        "python": platform.python_version(),
        "limitations": ["No cross-cell selected-recommendation validation", "No validated observed-point intervals", "Tiers provisional until QB19", "Float64 algebraic W8 recovery, not exact daily-state replay", "No new scientific estimation or simulation"],
    }
    (output / "v10-receipt.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "decisions", "report", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("inputs-sha256", "report-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    receipt = export(args.inputs, args.inputs_sha256, args.decisions, args.report, args.report_sha256, args.output)
    print(json.dumps({"rows": receipt["rows"], "scope": receipt["scope"]}), flush=True)


if __name__ == "__main__":
    main()
