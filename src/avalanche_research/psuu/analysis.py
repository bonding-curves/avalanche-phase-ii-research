"""Reduce a finished sweep run: goals, sensitivity, and the risk surface, saved beside the run.

``python -m avalanche_research.psuu.analysis <run_id>`` reads ``data/runs/<run_id>/batch-*.parquet`` and writes
``data/runs/<run_id>/analysis/``:

- ``observed_baseline.json``: ``kpis.observed_kpis`` on the ledger over ``goals.BASELINE_PERIOD`` and the
  thresholds taken from it.
- ``pass_shares.csv``: per parameter set, the share of its trajectories passing each KPI, goal group, and all goals.
- ``pass_by_scenario.csv``: per scenario, the share of trajectories passing each KPI, goal group, and all goals.
- ``tree_summary.csv``, ``tree_importances.csv``: ``sensitivity.trees``.
- ``spearman.csv``: ``sensitivity.spearman``.
- ``recommendations.json``: ``sensitivity.recommendations``.
- ``risk_surface.csv``, ``failure_regions.csv``: ``risk.surface`` and ``risk.failure_regions`` for all goals.
- ``manifest.json``: the run's receipt hash, the input datasets' runs, and the SHA-256 of every file above.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..catalog import canonical_bytes, now, sha256
from . import goals, kpis, risk, runner, sensitivity

BASELINE_VIEWS = ("avax_monetary_daily", "avax_usdt_daily", "staking_periods")


def analyse(run_dir: Path, con: Any, baseline_views: dict[str, str] | None = None,
            observed: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write the analysis tables. ``observed`` replaces the ledger baseline (tests pass one and no connection)."""
    run_dir = Path(run_dir)
    receipt = run_dir / "receipt.json"
    if not receipt.is_file():
        raise runner.SweepError(f"{run_dir} has no receipt; the sweep is not complete")
    out = run_dir / "analysis"
    out.mkdir(exist_ok=True)
    results = runner.load_results(run_dir)
    if observed is None:
        observed = kpis.observed_kpis(con, *goals.BASELINE_PERIOD)
    thresholds = goals.thresholds_from_observed(observed)
    evaluated = goals.evaluate(results, thresholds)
    pass_columns = [column for column in evaluated.columns if column.startswith("pass_")]

    files: dict[str, bytes] = {
        "observed_baseline.json": canonical_bytes({"period": list(goals.BASELINE_PERIOD), "kpis": observed,
                                                   "thresholds": thresholds.to_dict()}),
        "pass_shares.csv": goals.pass_shares(evaluated).reset_index().to_csv(index=False).encode(),
        "pass_by_scenario.csv": evaluated.groupby(["scenario_id", "scenario_name", "scenario_kind", "market", "yield_start"])[pass_columns]
        .mean().rename(columns=lambda name: name.replace("pass_", "share_")).reset_index().to_csv(index=False).encode(),
    }
    summary, importances = sensitivity.trees(evaluated)
    files["tree_summary.csv"] = summary.to_csv(index=False).encode()
    files["tree_importances.csv"] = importances.to_csv(index=False).encode()
    files["spearman.csv"] = sensitivity.spearman(results).to_csv(index_label="parameter").encode()
    files["recommendations.json"] = canonical_bytes(sensitivity.recommendations(evaluated))
    surface = risk.surface(evaluated)
    files["risk_surface.csv"] = surface.to_csv(index=False).encode()
    files["failure_regions.csv"] = risk.failure_regions(surface).to_csv(index=False).encode()
    for name, data in files.items():
        (out / name).write_bytes(data)
    invariant_columns = [column for column in results.columns if column.startswith("invariant_")]
    manifest = {
        "run_id": run_dir.name, "written_at": now(), "status": "v0, unreviewed",
        "command": f"uv run python -m avalanche_research.psuu.analysis {run_dir.name}",
        "receipt_sha256": sha256(receipt.read_bytes()), "trajectories": len(results),
        "baseline_inputs": baseline_views or {},
        "invariants": {
            "trajectories_checked": int(results["invariants_hold"].notna().sum()) if "invariants_hold" in results else 0,
            "trajectories_failing": int((~results["invariants_hold"].astype(bool)).sum()) if "invariants_hold" in results else None,
            "failing_days_by_invariant": {column: int(results[column].sum()) for column in invariant_columns if column.endswith("_days")},
        },
        "pass_share_overall": {column.replace("pass_", ""): float(evaluated[column].mean()) for column in pass_columns},
        "files": {name: sha256(data) for name, data in files.items()},
    }
    (out / "manifest.json").write_bytes(canonical_bytes(manifest))
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Reduce a finished sweep run into goal, sensitivity, and risk tables.")
    parser.add_argument("run_id")
    args = parser.parse_args(argv)
    from .. import datasets

    selected = datasets.views()
    con = datasets.connect()
    con.execute("SET memory_limit='5GB'; SET threads=6;")
    try:
        manifest = analyse(runner.default_run_dir(args.run_id), con,
                           {name: selected[name]["run"] for name in BASELINE_VIEWS if name in selected})
    finally:
        con.close()
    print(json.dumps({key: manifest[key] for key in ("run_id", "trajectories", "invariants", "pass_share_overall")}, indent=1))


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    main()
