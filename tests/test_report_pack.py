"""The report pack on a small synthetic sweep: the manifest, PSuU scoring, heat maps, trees, grids, recommendations
and the index page."""

from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("matplotlib")
pytest.importorskip("sklearn")

import duckdb  # noqa: E402

from avalanche_research.report import manifest, pack, psuu, recommend, trees  # noqa: E402

SPEC = {
    "schema": "psuu-utility-spec/v1",
    "name": "synthetic",
    "regions": {"utility_tolerance": 0.01, "pass_share": 0.9, "min_runs_per_cell": 10},
    "goals": [
        {"id": "G1", "name": "Stake holds", "weight": 1, "metrics": [
            {"id": "G1.stake", "label": "Stake retained", "expr": "stake_retained",
             "threshold": {"op": ">=", "value": 0.95}, "utility": {"type": "linear", "floor": 0.85, "target": 1.0}},
            {"id": "G1.fall", "label": "Worst fall against the baseline", "expr": "fall - baseline__fall",
             "threshold": {"op": ">=", "value": -0.02}, "utility": {"type": "linear", "floor": -0.05, "target": 0}},
        ]},
        {"id": "G2", "name": "Less issued", "weight": 1, "metrics": [
            {"id": "G2.saved", "label": "Issuance saved", "expr": "issuance_saved",
             "threshold": {"op": ">", "value": 0.0}, "utility": {"type": "linear", "floor": 0.0, "target": 0.2}},
        ]},
    ],
}


def synthetic_wide(seed=7, n=240):
    """Designs knob (one setting), duo (two settings) and fixed (none), with a chain baseline for each run.

    Stake retained falls as knob rises past 0.5, so G1 passes only below it, and issuance saved rises with knob."""
    rng = np.random.default_rng(seed)
    rows, base = [], []
    for fam in ("knob", "duo", "fixed"):
        for k in range(n):
            s = int(rng.integers(0, 10**9))
            y = float(rng.choice([3.0, 7.0]))
            a = float(rng.uniform(0, 1)) if fam in ("knob", "duo") else np.nan
            b = float(rng.uniform(0, 2)) if fam == "duo" else np.nan
            r = float(rng.normal())
            for h in (180, 365):
                rid, bid = f"{fam}-{k}-{h}", f"chain-{fam}-{k}"
                x = 0.0 if np.isnan(a) else a
                rows.append({"family": fam, "block": "A" if k % 2 else "B", "horizon_days": h, "seed": s,
                             "row_id": rid, "baseline_row_id": bid, "yield_pp": y, "knob": a,
                             "spread": b, "renewal_response": r,
                             "stake_retained": 1.0 - 0.12 * max(x - 0.5, 0) * 2 + 0.005 * rng.normal(),
                             "issuance_saved": 0.25 * x - 0.02 + 0.01 * rng.normal() + 0.01 * (0 if np.isnan(b) else b),
                             "fall": -0.01 * rng.random()})
                base.append({"family": "chain", "block": "baseline", "horizon_days": h, "seed": s, "row_id": bid,
                             "baseline_row_id": None, "yield_pp": y, "knob": np.nan, "spread": np.nan,
                             "renewal_response": r, "stake_retained": 1.0, "issuance_saved": 0.0,
                             "fall": -0.005})
    return pd.DataFrame(rows + base)


MANIFEST = {
    "schema": manifest.SCHEMA, "family_column": "family", "horizon_column": "horizon_days", "block_column": "block",
    "split_group": "seed", "pair": {"row": "row_id", "baseline_row": "baseline_row_id"},
    "baseline": {"families": ["chain"], "blocks": ["baseline"]}, "analysis_blocks": ["A", "B"],
    "columns": [{"name": c, "role": r} for c, r in [
        ("family", "id"), ("block", "id"), ("horizon_days", "id"), ("seed", "id"), ("row_id", "id"),
        ("baseline_row_id", "id"), ("yield_pp", "scenario"), ("knob", "setting"), ("spread", "setting"),
        ("renewal_response", "behaviour"), ("stake_retained", "kpi"), ("issuance_saved", "kpi"), ("fall", "kpi")]],
}


@pytest.fixture(scope="module")
def sweep(tmp_path_factory):
    folder = tmp_path_factory.mktemp("sweep")
    wide = folder / "wide.parquet"
    frame = synthetic_wide()
    con = duckdb.connect()
    con.register("frame", frame)
    con.execute(f"COPY frame TO '{wide}' (FORMAT parquet)")
    (folder / "spec.json").write_text(json.dumps(SPEC))
    manifest.write(MANIFEST, folder / "sweep-manifest.json")
    return folder


@pytest.fixture(scope="module")
def built(sweep, tmp_path_factory):
    out = tmp_path_factory.mktemp("pack")
    receipt = pack.build(sweep / "wide.parquet", sweep / "sweep-manifest.json", sweep / "spec.json", out,
                         version="synthetic", trees_n=20, repeats=2, jobs=1, sample=50, log=lambda *_: None)
    return out, receipt


def test_the_manifest_must_list_every_column(sweep):
    bad = {**MANIFEST, "columns": [c for c in MANIFEST["columns"] if c["name"] != "spread"]}
    with pytest.raises(manifest.ManifestError, match="spread"):
        manifest.check_table(bad, synthetic_wide().columns)
    with pytest.raises(manifest.ManifestError, match="unknown role"):
        manifest.check_shape({**MANIFEST, "columns": [{"name": "x", "role": "knob"}]})


def test_roles_come_from_the_manifest_not_the_names(sweep):
    spec = psuu.load_spec(sweep / "spec.json")
    layout = psuu.layout_from_manifest(duckdb.connect(), str(sweep / "wide.parquet"), spec, MANIFEST)
    assert layout["parameters"] == ["knob", "spread"]
    assert layout["scenarios"] == ["yield_pp"] and layout["behaviour"] == ["renewal_response"]
    assert layout["paired"] == ["fall"]
    drafted = manifest.draft(sweep / "wide.parquet")
    assert "knob" in manifest.names(drafted, "setting") and "spread" in manifest.names(drafted, "setting")


def test_scoring_reads_the_paired_baseline(sweep):
    scored = psuu.load_scored(sweep / "wide.parquet", sweep / "sweep-manifest.json", sweep / "spec.json",
                              log=lambda *_: None)
    runs = scored.runs
    assert len(runs) == 3 * 240 * 2
    assert np.allclose(runs["metric__G1.fall"], runs.fall - (-0.005))
    expected = np.clip((runs.stake_retained - 0.85) / 0.15, 0, 1)
    assert np.allclose(runs["util__G1.stake"], expected)
    assert (runs.goalpass__combined == (runs.goalpass__G1 & runs.goalpass__G2)).all()


def test_the_index_lists_every_output_and_every_link_exists(built):
    out, receipt = built
    index = (out / "index.md").read_text()
    links = re.findall(r"\]\(([^)]+)\)", index)
    assert links and all((out / link).exists() for link in links), [k for k in links if not (out / k).exists()]
    pngs = {p.relative_to(out).as_posix() for p in (out / "figures").glob("*.png")}
    assert pngs == {link for link in links if link.endswith(".png")}
    assert len(pngs) == len(receipt["figures"])
    for kind in ("heatmap-sorted-365", "heatmap-scenario-knob-knob-365", "heatmap-pair-duo-knob-spread-365",
                 "tree-knob-G1-365", "grid-knob-365", "grid-fixed-365", "overview-yield_pp-365"):
        assert f"figures/{kind}.png" in pngs, kind


def test_the_sorted_heat_map_puts_the_best_cell_first(built):
    out, _ = built
    table = pd.read_csv(out / "figures" / "heatmap-sorted-365.csv")
    assert table.utility_combined.is_monotonic_decreasing
    assert "fixed design" in set(table.cell)


def test_trees_find_the_threshold_out_of_fold(built):
    out, _ = built
    fit = pd.read_csv(out / "tables" / "tree-fit.csv")
    g1 = fit[(fit.mechanism == "knob") & (fit.target == "goalpass__G1") & (fit.horizon == 365)].iloc[0]
    assert g1.status == "fitted"
    assert g1.oof_accuracy > 0.9 and g1.oof_accuracy > g1.majority_accuracy
    leaves = pd.read_csv(out / "tables" / "tree-leaves.csv")
    assert leaves.conditions.str.contains("knob").any()


def test_recommendations_and_sign_matrix(built):
    out, _ = built
    rec = pd.read_csv(out / "recommendations" / "recommendations.csv")
    g1 = rec[(rec.mechanism == "knob") & (rec.horizon == 365) & (rec.scenario == "all") & (rec.goal == "G1")]
    assert g1.iloc[0]["range"].startswith("knob 0 to 0.")
    assert set(rec.kind) >= {"point", "goal range", "global range", "fixed"}
    sig = pd.read_csv(out / "recommendations" / "sign-confidence.csv", keep_default_na=False)
    cell = sig[(sig.mechanism == "knob") & (sig.horizon == 365) & (sig.input == "knob") & (sig.target == "G2.saved")]
    assert cell.iloc[0].symbol == "++"
    assert "| Input |" in (out / "recommendations" / "sign-confidence.md").read_text()
    assert "Point estimate" in (out / "recommendations" / "recommendations.md").read_text()


def test_confidence_rules():
    assert recommend.wilson_lower(1.0, 100) == pytest.approx(0.963, abs=1e-3)
    assert recommend.symbol(0.5, 0.4, 0.6) == "++"
    assert recommend.symbol(-0.2, -0.3, -0.1) == "-"
    assert recommend.symbol(0.05, 0.01, 0.09) == "(+)"
    assert recommend.symbol(0.05, -0.01, 0.09) == "0"
    assert recommend.level(0.85) == "high" and recommend.level(0.6) == "medium" and recommend.level(0.2) == "low"


def test_tree_targets_cover_every_goal_and_kpi():
    names = [t for t, _, _ in trees.tree_targets(SPEC)]
    assert names == ["goalpass__G1", "goalpass__G2", "goalpass__combined", "pass__G1.stake", "pass__G1.fall",
                     "pass__G2.saved"]


def test_ranges_merge_repeated_and_touching_bins():
    assert psuu.contiguous_ranges([0.0, 0.2, 0.2, 0.6], [0.2, 0.4, 0.4, 0.8]) == [[0.0, 0.4], [0.6, 0.8]]
