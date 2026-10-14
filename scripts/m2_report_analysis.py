#!/usr/bin/env python3
"""Export the completed M2 numerical caches as DR1–DR12 report artifacts.

Prepare inputs with m2_analysis_prepare.py, then run m2_numerics.py,
m2_cart_prim.py and m2_decisions.py. All paths are explicit external inputs.
This command exports computed results. Independent scientific review and MM7's
timed evaluation remain separate acceptance steps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import tempfile
from html import escape
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from avalanche_research.analysis import report_figures as figures
from avalanche_research.analysis.m2_contract import CHAIN_INFLATION, COSTS, PRICE_FACTOR
from avalanche_research.analysis.m2_resampling import replicated_noise_share
from avalanche_research.model.kpis import kpi_table

CONTEXT = {"family": "Design family", "yield_pp": "Competing yield (%)",
           "competing_yield_pp": "Competing yield (%)", "horizon_days": "Horizon (days)",
           "renewal_band": "Renewal response", "entry_band": "Entry response",
           "measure": "Measure", "input": "Input", "cost_level": "Cost level",
           "threshold_alternative": "Threshold alternative"}
ASSOCIATIONS = {"method": "Coefficient (Spearman or partial rank)",
                "coefficient": "Coefficient value", "ci_low": "Interval low (95%)",
                "ci_high": "Interval high (95%)", "rows": "Trajectories",
                "starred": "Starred (Benjamini-Hochberg 5%)"}
SOBOL = {"first": "First-order index", "first_low": "First-order low (95%)",
         "first_high": "First-order high (95%)", "total": "Total-order index",
         "total_low": "Total-order low (95%)", "total_high": "Total-order high (95%)",
         "base_n": "Base sample size", "max_change": "Largest change when the sample size doubled",
         "converged": "Converged"}


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()



def read_csv(path):
    return pd.read_csv(path, float_precision="round_trip", low_memory=False)


def csv(frame, path):
    temporary = path.with_suffix(path.suffix + ".pending")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def headers(frame, extra=None):
    return frame.rename(columns=CONTEXT | (extra or {}))


def _failure(frame, scope):
    measure, alternative, cost = scope["measure"], scope.get("threshold_alternative", "primary"), scope.get("cost_level", "zero")
    if measure == "issuance_saved":
        return frame.issuance_saved <= 0
    if measure == "validator_stake_retained":
        return frame.validator_stake_retained < (1.0 if alternative == "stake_ge_1" else 1 - frame.issuance_saved)
    if measure == "net_inflation":
        return frame.net_inflation > (CHAIN_INFLATION if alternative == "chain_trailing_year" else .05)
    if measure == "return_margin":
        column = "return_margin" if cost == "zero" else "return_margin_" + cost
        return frame[column] < 0
    raise ValueError("unknown frozen failure label")


def cart_tables(directory, wide):
    accuracies, nodes, boxes, points, bindings = [], [], [], [], {}
    configuration = json.loads((directory / "configuration.json").read_text())
    scopes = sorted(directory.glob("*__scope-receipt.json"))
    if len(scopes) != 32:
        raise ValueError("all 32 CART/PRIM family/yield/horizon scopes required")
    for receipt_path in scopes:
        receipt = json.loads(receipt_path.read_text())
        for task in receipt["tasks"]:
            path = directory / task["path"]
            if sha(path) != task["sha256"]:
                raise ValueError("changed CART/PRIM task bytes")
            task_record = json.loads(path.read_text())
            if task_record["run_key"] != configuration["run_key"]:
                raise ValueError("mixed CART/PRIM producer configuration")
            result = task_record["result"]
            encoded = json.dumps(result, allow_nan=False, sort_keys=True).encode()
            if hashlib.sha256(encoded).hexdigest() != task_record["result_sha256"]:
                raise ValueError("changed CART/PRIM result")
            bindings[path.name] = task["sha256"]
            scope = result["scope"]
            context = headers(pd.DataFrame([scope])).iloc[0].to_dict()
            context.update({"Renewal response": "varying inputs", "Entry response": "varying inputs"})
            if "__prim__" in path.name:
                confirmation = result.get("confirmation") or {}
                shared = context | {"Failure condition": scope["measure"] + ":" + scope["threshold_alternative"],
                    "Found": result["found"], "Meets both standards": result["found"],
                    "Coverage": confirmation.get("coverage"), "Density": confirmation.get("density"),
                    "Runs in box": confirmation.get("runs_in_box"), "Failing runs in box": confirmation.get("failing_in_box"),
                    "status": result["status"], "reason": result["reason"], "Box": "A-selected, B-confirmed"}
                selected = result.get("selected_box")
                if selected:
                    for bound in selected["bounds"]:
                        boxes.append(shared | {"Input": bound["feature"], "Lower bound": bound["lower"], "Upper bound": bound["upper"]})
                else:
                    boxes.append(shared | {"Input": None, "Lower bound": None, "Upper bound": None})
                data = wide[(wide.family == scope["family"]) & (wide.yield_pp == scope["competing_yield_pp"]) & (wide.horizon_days == scope["horizon_days"]) & wide.block.isin(["A", "B"])].copy()
                features = ["renewal_response", "entry_response"]
                inside = np.zeros(len(data), dtype=bool)
                if selected:
                    inside[:] = True
                    for bound in selected["bounds"]:
                        inside &= data[bound["feature"]].between(bound["lower"], bound["upper"]).to_numpy()
                failed = _failure(data, scope)
                for row, failure, membership in zip(data.itertuples(), failed, inside, strict=True):
                    points.append(context | {"Failure condition": shared["Failure condition"], "Run": row.row_id,
                        "Role": row.block, "First input": features[0], "Second input": features[1],
                        "First input value": row.renewal_response, "Second input value": row.entry_response,
                        "Failed": bool(failure), "Inside box": bool(membership), "Found": result["found"]})
                continue
            final = result.get("final_tree") or {}
            interval = result.get("accuracy_interval95") or [None, None]
            paired = result.get("paired_difference_interval95") or [None, None]
            accuracy = result.get("held_out_metrics", {}).get("raw_accuracy")
            majority = result.get("held_out_majority_baseline", {}).get("raw_accuracy")
            accuracies.append(context | {"Target type": result["target_type"],
                "Cross-validated accuracy": accuracy, "Share with no splits": majority,
                "Accuracy low (95%)": interval[0], "Accuracy high (95%)": interval[1],
                "Margin": result.get("margin"), "Informative": result.get("informative"),
                "Paired difference low (95%)": paired[0], "Paired difference high (95%)": paired[1],
                "Accuracy-low minus OOF training-majority display": result.get("raw_accuracy_low_minus_majority_display"),
                "Depth": final.get("depth"), "Leaves": final.get("leaves"), "Folds": 10,
                "OOF MSE": result.get("held_out_mse"), "OOF R2": result.get("held_out_r2"),
                "Training-mean baseline MSE": result.get("training_mean_baseline_mse"),
                "status": result["status"], "reason": result.get("reason", result.get("informative_reason", "")),
                "Source task": path.name})
            parents = {}
            for node in final.get("nodes", []):
                if not node["leaf"]:
                    parents[node["left"]] = (node["node"], "left: <=")
                    parents[node["right"]] = (node["node"], "right: >")
            for node in final.get("nodes", []):
                parent, side = parents.get(node["node"], (None, "root"))
                nodes.append(context | {"Target type": result["target_type"], "Node": node["node"],
                    "Parent node": parent, "Split input": node.get("feature", ""), "Split value": node.get("threshold"),
                    "Side of split": side, "Runs at node": node["n"], "Share meeting threshold": node.get("share_met"),
                    "Node mean target": node.get("mean"), "Leaf": node["leaf"]})
    return pd.DataFrame(accuracies), pd.DataFrame(nodes), pd.DataFrame(boxes), pd.DataFrame(points), bindings


def recommendation_rows(directory):
    source = read_csv(directory / "range-confirmations.csv")
    points = read_csv(directory / "point-estimates.csv")
    rows = []
    for record in source.to_dict("records"):
        bounds = record.get("bounds")
        bounds = json.loads(bounds) if isinstance(bounds, str) else [{"input": None, "lower": None, "upper": None}]
        eligible = record.get("eligible_for_recommendation") is True
        requested = record.get("tier", "global range" if record["target"] == "all_joint" else "per-goal range")
        granted = requested if record["status"] == "found" and eligible else "diagnostic only" if not eligible and record["cost_level"] == "zero" else record["status"]
        for bound in bounds:
            rows.append(record | {"input": bound["input"], "Value or range": f"[{bound['lower']}, {bound['upper']}]" if record["status"] == "found" else None,
                "Recommendation": requested, "Requested tier": requested, "Tier": granted,
                "Evidence": "A-selected bounds and unchanged B confirmation; provisional until QB19 reruns"})
    for record in points.to_dict("records"):
        rows.append(record | {"Recommendation": "point estimate", "Tier": "point estimate" if record["status"] == "assessable" else record["status"], "target": "issuance_saved",
                              "Value or range": record.get("value"), "Evidence": "Observed A point; no validated point interval"})
    result = pd.DataFrame(rows)
    ratings = read_csv(directory / "confidence-ratings.csv")
    lookup = ratings[ratings.input.eq("family_against_matched_baseline")].set_index(["family", "yield_pp", "horizon_days", "measure"]).confidence_rating.to_dict()
    result["Confidence rating"] = [lookup.get((r["family"], r["yield_pp"], r["horizon_days"], r.get("target")), "not rated") for r in rows]
    result["Confidence basis"] = "Family against matched baseline across nine cells, zero and three stress settings; other goals not rated by this comparison"
    result["Response value that reverses it"] = "See table-sign-changes.csv at response-band resolution"
    result["Competing yields where it holds"] = result.yield_pp
    return headers(result, {"target": "Goal", "pass_share": "Pass share", "ci_low": "Pass share low (95%)",
        "ci_high": "Pass share high (95%)", "meets_90": "Meets at 90%", "meets_70": "Meets at 70%", "meets_50": "Meets at 50%"})


def cost_checks(wide):
    """All consumed A/B rows plus strict kpi_table reference on synthetic days."""
    records = []
    for (family, yield_pp, horizon), group in wide.groupby(["family", "yield_pp", "horizon_days"], sort=True):
        for cost, value in COSTS.items():
            for price, factor in (("primary", 1.), ("fitting_price", PRICE_FACTOR)):
                column = "return_margin" if cost == "zero" else "return_margin_" + cost + ("_fitting_price" if price == "fitting_price" else "")
                direct = group.earned_rate - yield_pp / 100 - value * factor
                error = float(np.max(np.abs(group[column] - direct)))
                if error != 0:
                    raise ValueError("actual affine rescore differs from public KPI expression")
                records.append({"Design family": family, "Competing yield (%)": yield_pp, "Horizon (days)": horizon,
                    "Cost level": cost, "Cost fraction": value, "Price basis": price, "Effective cost": value * factor,
                    "Runs": len(group), "Maximum absolute difference": error, "Passed": True,
                    "Reference": "Consumed earned_rate minus competing yield minus operating cost, exact return_margin expression"})
    origin = pd.Timestamp("2024-06-30")
    days = pd.date_range(origin - pd.Timedelta(days=365), origin + pd.Timedelta(days=365))
    t = np.arange(len(days))
    daily = pd.DataFrame({"active_validators": 1000 + t % 7,
        "active_validator_stake_navax": 1e9 * (1000 + 50 * np.sin(t / 9)),
        "issued_navax": 3e13 + 1e12 * (t % 5), "started_stake_navax": 1e13 + 1e11 * (t % 3),
        "started_stake_days_navax": 3e14 + 1e12 * (t % 11), "offered_rate_30d": .06 - 1e-5 * t,
        "nakamoto_third_nodes": 20 + t % 4, "burned_navax": 5e12 + 1e10 * (t % 13),
        "total_supply_navax": 4.4e17 + t * 2.5e13, "supply_counter_navax": 4.5e17 + t * 3e13}, index=days)
    for yield_pp in (3., 5., 7., 10.):
        direct = kpi_table(daily, origin, [180, 365], competing_yield=yield_pp / 100, operating_costs=COSTS)
        margin = direct[direct.measure.eq("return_margin")].set_index(["horizon_days", "cost_level"]).value
        for horizon in (180, 365):
            for cost, value in COSTS.items():
                difference = float(abs(margin[horizon, cost] - (margin[horizon, "zero"] - value)))
                if difference != 0:
                    raise ValueError("strict kpi_table cost qualification failed")
                records.append({"Design family": "synthetic reference", "Competing yield (%)": yield_pp,
                    "Horizon (days)": horizon, "Cost level": cost, "Cost fraction": value, "Price basis": "primary",
                    "Effective cost": value, "Runs": 1, "Maximum absolute difference": difference,
                    "Passed": True, "Reference": "Strict complete kpi_table on synthetic daily table; qualification fixture"})
    return pd.DataFrame(records)


def primary(frame, *, family=True, grid=False, measure=None):
    """Predeclared static view, selected by inputs rather than result values."""
    mask = pd.to_numeric(frame["Competing yield (%)"], errors="coerce").eq(5) & frame["Horizon (days)"].eq(365)
    if family:
        mask &= frame["Design family"].eq("ramp")
    if measure:
        mask &= frame["Measure"].eq(measure)
    if "Renewal response" in frame:
        label = "middle" if grid else "all"
        if label in set(frame["Renewal response"]):
            mask &= frame["Renewal response"].eq(label) & frame["Entry response"].eq(label)
    return frame.loc[mask].copy()


def noise_checks(directory, measures):
    noise = duckdb.sql("SELECT * FROM read_parquet(?) WHERE block='noise' ORDER BY family,yield_pp,horizon_days,i,j", params=[str(directory / "wide.parquet")]).df()
    records = []
    with np.load(directory / "bootstrap.npz", allow_pickle=False) as bootstrap:
        for (family, yield_pp, horizon), scope in noise.groupby(["family", "yield_pp", "horizon_days"], sort=True):
            expected = [(i, j) for i in range(64) for j in range(8)]
            if list(zip(scope.i, scope.j, strict=True)) != expected:
                raise ValueError("all eight keys at all 64 original noise points required")
            for measure in measures:
                result = replicated_noise_share(scope[measure].to_numpy().reshape(64, 8), bootstrap[f"noise__{family}__{float(yield_pp)}"])
                records.append({"family": family, "yield_pp": yield_pp, "horizon_days": horizon, "measure": measure, **result})
    return headers(pd.DataFrame(records))


def screenshot(layout, target, chrome, *, height, scope):
    """Render one prescribed panel with local headless Chromium, no server."""
    layout.children[0].text += "<p><strong>Static view:</strong> " + escape(scope) + "</p>"
    with tempfile.TemporaryDirectory(prefix="m2-report-capture-") as scratch:
        directory = Path(scratch)
        page = directory / "panel.html"
        figures.write_standalone_html(layout, page, title=target.stem)
        command = [str(chrome.resolve()), "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--hide-scrollbars", "--no-first-run",
            "--allow-file-access-from-files", "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=5000", f"--window-size=1450,{height}",
            "--user-data-dir=" + str(directory / "profile"),
            "--screenshot=" + str(target.resolve()), page.as_uri()]
        result = subprocess.run(command, capture_output=True, text=True, timeout=45, check=False)
        if result.returncode or not target.exists() or target.stat().st_size < 1000:
            raise RuntimeError("headless PNG export failed: " + result.stderr[-1000:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "numerics", "cart-prim", "decisions", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--chrome", type=Path, required=True, help="Local headless Chromium executable for PNG exports")
    parser.add_argument("--analysis-revision", default="uncommitted-source-bound-by-sha256", help="Delivery revision containing the exact hashed analysis sources")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    inputs = json.loads((args.inputs / "inputs-manifest.json").read_text())
    if sha(args.inputs / "wide.parquet") != inputs["wide_sha256"]:
        raise ValueError("changed wide input cache")
    if sha(args.inputs / "bootstrap.npz") != inputs["bootstrap"]["file_sha256"]:
        raise ValueError("changed shared bootstrap file")
    numerics = json.loads((args.numerics / "numerics-manifest.json").read_text())
    if not numerics["complete"]:
        raise ValueError("numerical methods incomplete")
    decisions = json.loads((args.decisions / "decisions-receipt.json").read_text())
    if decisions["status"] != "computed_pending_review":
        raise ValueError("decision methods incomplete")
    for name, digest in decisions["outputs"].items():
        if sha(args.decisions / name) != digest:
            raise ValueError("changed decision output")
    association_parts, sensitivity_parts = [], []
    for key, scope in numerics["scopes"].items():
        binding = scope["outputs"]["csv"]
        path = args.numerics / binding["path"]
        if sha(path) != binding["sha256"]:
            raise ValueError("changed numerical output")
        (association_parts if key.startswith("mm1/") else sensitivity_parts).append(read_csv(path))
    associations, sensitivity = pd.concat(association_parts, ignore_index=True), pd.concat(sensitivity_parts, ignore_index=True)
    if len(associations) != 40986 or len(sensitivity) != 2024:
        raise ValueError("full declared numerical row inventories differ")
    associations["starred"] = associations.starred.map(lambda v: pd.NA if pd.isna(v) else v if isinstance(v, (bool, np.bool_)) else {"True": True, "False": False}[v])
    correlated = headers(associations, ASSOCIATIONS)
    correlated["Interval excludes zero"] = ((correlated["Interval low (95%)"] > 0) | (correlated["Interval high (95%)"] < 0)).where(correlated["Interval low (95%)"].notna())
    sobol = headers(sensitivity, SOBOL)
    wide = duckdb.sql("SELECT * FROM read_parquet(?) WHERE block IN ('A','B')", params=[str(args.inputs / "wide.parquet")]).df()
    accuracy, nodes, boxes, points, task_bindings = cart_tables(args.cart_prim, wide)
    ranking = headers(read_csv(args.decisions / "design-rankings.csv"), {"family": "Design", "mean": "Mean", "p10": "10th percentile", "p90": "90th percentile", "rank": "Rank", "runs": "Runs", "order_same_at_every_yield": "Order same at every yield"})
    ranking["Design family"] = ranking.Design
    recommendations = recommendation_rows(args.decisions)
    reversals = headers(read_csv(args.decisions / "sign-changes.csv"), {"sign_changes": "Sign changes", "band_boundary": "Response value that reverses it"})
    # A boundary denotes two adjacent response bands, never an exact crossing.
    reversals["Response value that reverses it"] = reversals["Response value that reverses it"].where(reversals["Sign changes"].eq(True))
    limits = headers(read_csv(args.decisions / "limit-screen.csv"), {"pass_share": "Pass share", "flagged": "Flagged"})
    limits["Threshold"] = limits.apply(lambda r: ">= 1" if r["Measure"] == "validator_stake_retained" and r["Threshold alternative"] == "no_stake_loss" else ">= 1 - issuance_saved" if r["Measure"] == "validator_stake_retained" else "<= " + str(CHAIN_INFLATION if r["Threshold alternative"] == "trailing_year" else .05) if r["Measure"] == "net_inflation" else ">= 0", axis=1)
    tables = {"figure-2-correlations.csv": correlated, "figure-3-tree-nodes.csv": nodes,
        "table-10-tree-accuracy.csv": accuracy, "figure-4-sobol.csv": sobol, "table-11-boxes.csv": boxes,
        "figure-5-points.csv": points, "table-sign-changes.csv": reversals, "figure-6-designs.csv": ranking,
        "table-13-recommendations.csv": recommendations, "table-limit-screen.csv": limits,
        "cost-rescore-check.csv": cost_checks(wide), "noise-variance-share.csv": noise_checks(args.inputs, sensitivity.measure.unique()),
        "table-confidence-ratings.csv": headers(read_csv(args.decisions / "confidence-ratings.csv"))}
    for name, frame in tables.items():
        csv(frame, args.output / name)
    # The static panel scope is prescribed before inspecting any results.
    provenance = {"sweep_id": "cd70f232764c616c", "model_version": "model-v0.8.0", "code_sha": inputs["bindings"]["code_commit"], "producer": inputs["bindings"]["code_commit"], "wide SHA256": inputs["wide_sha256"],
                  "uncertainty": "1000 whole-unit design resamples; conditional inference", "review": "pending independent review"}
    facets = (*figures.CONTEXT, "Target type")
    layouts = {"figure-2-correlations": figures.correlation_heatmap(correlated, provenance=provenance),
        "figure-3-trees": figures.tree_figure(nodes, provenance=provenance, facets=(*facets, "Measure")),
        "figure-4-sobol": figures.sobol_figure(sobol, provenance=provenance),
        "figure-5-regions": figures.region_figure(points, boxes, provenance=provenance, x_input="renewal_response", y_input="entry_response", facets=(*facets, "Failure condition")),
        "figure-6-designs": figures.design_ranking_figure(ranking, provenance=provenance, facets=tuple(k for k in figures.CONTEXT if k != "Design family") + ("Measure",)),
        "table-13-recommendations": figures.recommendation_table(recommendations, provenance=provenance)}
    for name, layout in layouts.items():
        figures.write_standalone_html(layout, args.output / (name + ".html"), title=name)
    matrix_panel = primary(correlated)
    matrix_panel = matrix_panel[matrix_panel["Coefficient (Spearman or partial rank)"].eq("spearman")]
    tree_panel = primary(nodes, measure="issuance_saved")
    tree_panel = tree_panel[tree_panel["Target type"].eq("classification") & tree_panel["Threshold alternative"].eq("primary")]
    point_panel = primary(points)
    point_panel = point_panel[point_panel["Failure condition"].eq("issuance_saved:primary")]
    box_panel = primary(boxes)
    box_panel = box_panel[box_panel["Failure condition"].eq("issuance_saved:primary")]
    recommendation_panel = primary(recommendations, grid=True)
    recommendation_panel = recommendation_panel[(recommendation_panel.Goal.eq("all_joint") & recommendation_panel["Cost level"].eq("mid") & recommendation_panel["Threshold alternative"].eq("primary")) | recommendation_panel.Recommendation.eq("point estimate")]
    recommendation_panel = recommendation_panel[["Recommendation", "Goal", "Input", "Tier", "Value or range", "Confidence rating", "Evidence"]]
    recommendation_panel["Input"] = recommendation_panel.Input.fillna("no confirmed range")
    recommendation_panel["Value or range"] = recommendation_panel["Value or range"].fillna("not found")
    recommendation_panel["Evidence"] = np.where(recommendation_panel.Tier.eq("point estimate"), "Observed A point.", np.where(recommendation_panel.Tier.eq("global range"), "Confirmed fixed A box.", "No confirmed range."))
    captures = {
        "figure-2-correlations": (figures.correlation_heatmap(matrix_panel, provenance=provenance), 1550, "Ramp, 5% competing yield, 365 days. Spearman on full A+B response distribution. Stars use supplied BH 5% values. All 23 measures shown."),
        "figure-3-trees": (figures.tree_figure(tree_panel, provenance=provenance, facets=(*facets, "Measure")), 650, "Ramp, 5% competing yield, 365 days. Target: issuance saved > 0. Responses vary as inputs. Descriptive classification tree; OOF validation is in Table 10."),
        "figure-4-sobol": (figures.sobol_figure(primary(sobol, measure="issuance_saved"), provenance=provenance), 520, "Ramp, 5% competing yield, 365 days. Issuance saved. N=512 original Saltelli units, 1000 shared bootstrap draws. See CSV for convergence status."),
        "figure-5-regions": (figures.region_figure(point_panel, box_panel, provenance=provenance, x_input="renewal_response", y_input="entry_response", facets=(*facets, "Failure condition")), 780, "Ramp, 5% competing yield, 365 days. Failure: issuance saved <= 0. Points show A discovery and B confirmation roles; full box membership can depend on target_min_rate."),
        "figure-6-designs": (figures.design_ranking_figure(primary(ranking, family=False, grid=True, measure="issuance_saved"), provenance=provenance), 580, "5% competing yield, 365 days. Both responses in middle band [0.0333,0.0667). Issuance saved relative to each matched baseline. Vertical bars are 10th–90th percentile run spread."),
        "table-13-recommendations": (figures.recommendation_table(recommendation_panel, provenance=provenance), 450, "Ramp, 5% competing yield, 365 days. Both responses in middle band. Global range uses 1.5% annual operating cost, main stake/inflation limits and 90% pass share. Point value is a fraction; all tiers provisional.")}
    for name, (layout, height, scope) in captures.items():
        screenshot(layout, args.output / (name + ".png"), args.chrome, height=height, scope=scope)
    scalar_rows = []
    def scalar(key, value, unit, source, scope):
        scalar_rows.append({"Summary key": key, "Value": value, "Unit": unit, "Display value": str(value), "Source artifact": source, "Source scope": scope})
    for method, values, column in (("MM1", associations, "coefficient"), ("MM3", sensitivity, "total")):
        selected = values[(values.renewal_band.eq("all") if "renewal_band" in values else np.ones(len(values), bool)) & values.status.eq("assessable") & values[column].notna()]
        for scope, group in selected.groupby(["family", "yield_pp", "horizon_days", "measure"] + (["method"] if method == "MM1" else []), dropna=False):
            best = group.loc[group[column].abs().idxmax()]
            scalar(method + ".top-input." + ".".join(map(str, scope)), best["input"], "input", "figure-2-correlations.csv" if method == "MM1" else "figure-4-sobol.csv", str(scope))
    ratings = read_csv(args.decisions / "confidence-ratings.csv")
    for scope, group in ratings.groupby(["family", "yield_pp", "horizon_days", "method"], dropna=False):
        prefix = ".".join(map(str, scope))
        rated = group.confidence_rating.ne("not rated")
        scalar("relationships.rated." + prefix, int(rated.sum()), "relationships", "table-confidence-ratings.csv", str(scope))
        for rating in ("High", "Medium", "Low", "not rated"):
            scalar("relationships." + rating + "." + prefix, int(group.confidence_rating.eq(rating).sum()), "relationships", "table-confidence-ratings.csv", str(scope))
        scalar("relationships.nominal-5pct-reference." + prefix, .05 * int(rated.sum()), "arithmetic reference .05*N; not estimated actual false High count or empirical FDR", "table-confidence-ratings.csv", str(scope))
    scenario = ["Design family", "Competing yield (%)", "Horizon (days)", "Cost level", "Threshold alternative", "Failure condition"]
    region_cases = boxes.drop_duplicates(scenario)
    for scope, group in region_cases.groupby(scenario[:-1], dropna=False):
        for outcome in ("found", "not_found", "unassessable"):
            scalar("regions." + outcome + "." + ".".join(map(str, scope)), int(group.status.eq(outcome).sum()), "failure conditions", "table-11-boxes.csv", str(scope))
    range_source = read_csv(args.decisions / "range-confirmations.csv")
    range_scope = ["family", "yield_pp", "horizon_days", "renewal_band", "entry_band", "target", "threshold_alternative", "cost_level", "candidate"]
    range_source = range_source.drop_duplicates(range_scope)
    for scope, group in range_source.groupby(["family", "yield_pp", "horizon_days", "cost_level", "threshold_alternative", "tier"], dropna=False):
        eligible = group.status.eq("found") & group.eligible_for_recommendation.eq(True)
        scalar("tiers.eligible-found." + ".".join(map(str, scope)), int(eligible.sum()), "distinct fixed A-selected boxes confirmed on B; not bound rows", "table-13-recommendations.csv", str(scope))
    for state in (True, False):
        scalar("Sobol.converged." + str(state), int(sensitivity.converged.eq(state).sum()), "input/measure rows", "figure-4-sobol.csv", "all declared family/yield/horizon cells, no new simulation")
    for state in (True, False):
        scalar("CART.informative." + str(state), int(accuracy.Informative.eq(state).sum()), "classification targets", "table-10-tree-accuracy.csv", "all declared family/yield/horizon/threshold/cost cells")
    scalar("CART.unassessable", int(accuracy.status.eq("unassessable").sum()), "targets", "table-10-tree-accuracy.csv", "every unsupported target retained")
    scalar("MM7.timed-evaluation", "pending owner timed record", "verdict", "analysis-receipt.json", "contract 2.8")
    scalar("scientific-acceptance", "pending independent review", "verdict", "analysis-receipt.json", "N1-N3")
    csv(pd.DataFrame(scalar_rows), args.output / "summary.csv")
    outputs = {p.name: sha(p) for p in sorted(args.output.iterdir()) if p.is_file() and p.name != "analysis-receipt.json"}
    receipt = {"schema": "m2-report-analysis/v1", "status": "computed_pending_review", "outputs": outputs,
        "inputs": inputs, "numerics_receipt_sha256": sha(args.numerics / "numerics-manifest.json"),
        "decisions_receipt_sha256": sha(args.decisions / "decisions-receipt.json"), "cart_tasks": task_bindings,
        "export_source_sha256": sha(__file__), "python": platform.python_version(), "analysis_delivery_revision": args.analysis_revision,
        "analysis_source_sha256": {str(p.relative_to(Path(__file__).resolve().parents[1])): sha(p) for p in sorted((Path(__file__).resolve().parents[1] / "src/avalanche_research/analysis").glob("*.py"))},
        "model_tag": "model-v0.8.0", "model_tag_target": "b18a4a2",
        "noise_diagnostic": {"method": "nonnegative balanced one-way random-effects moments, whole-point bootstrap", "reference": "https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/onewayan.htm", "qualification": "conditional design diagnostic; no empirical QMC coverage claim"},
        "PNG_scope": {"family": "ramp", "yield_pp": 5., "horizon_days": 365, "response": "all", "method": "spearman", "failure": "issuance_saved"},
        "limitations": ["independent review pending", "tiers provisional until QB19 fresh-seed reruns", "MM7 timed evaluation remains owner-supplied", "no independent conservation proof in producer receipt", "float64 KPI outputs, not integer daily replay", "BH uses conditional bootstrap interval inversion; empirical QMC FDR not established"]}
    (args.output / "analysis-receipt.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"outputs": len(outputs), "status": receipt["status"]}), flush=True)


if __name__ == "__main__":
    main()
