"""Consumer-facing summaries of saved results, without fitting or inference."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd


def selector(record, names):
    """Serialize an explicit source-row predicate without inventing missing data."""
    values = {}
    for name in names:
        value = record.get(name)
        if isinstance(value, np.generic):
            value = value.item()
        values[name] = None if value is None or pd.isna(value) else value
    return json.dumps(values, sort_keys=True, allow_nan=False)


def paired_margin_fields(result):
    """DR3's margin is the paired difference bound, never a difference of bounds."""
    paired = result.get("paired_difference_interval95") or [None, None]
    margin = result.get("margin")
    if margin is not None and (paired[0] is None or not math.isclose(margin, paired[0], abs_tol=1e-12, rel_tol=1e-12)):
        raise ValueError("saved margin differs from paired lower bound")
    return {"Margin low (95%)": paired[0]}


def found_label(result):
    status = result["status"]
    expected = {"found": True, "not_found": False, "unassessable": None}
    if status not in expected:
        raise ValueError("unsupported PRIM result status")
    if status != "unassessable" and result["found"] is not expected[status]:
        raise ValueError("PRIM status and found flag disagree")
    return {"found": "found", "not_found": "not found", "unassessable": "unassessable"}[status]


def tree_top_input(result):
    """Descriptive final-tree importance, distinct from held-out prediction skill."""
    final = result.get("final_tree") or {}
    importance = final.get("impurity_importance", {})
    finite = {name: float(value) for name, value in importance.items() if value is not None and math.isfinite(value)}
    if result["status"] == "unassessable" or not final:
        value, weight, status = None, None, "unassessable"
    elif not finite or max(finite.values()) <= 0:
        value, weight, status = None, None, "no split"
    else:
        weight = max(finite.values())
        # Export ties explicitly rather than choosing one input by dictionary order.
        value = "; ".join(sorted(name for name, score in finite.items() if score == weight))
        status = "descriptive"
    return {"Descriptive top input": value, "Descriptive top input importance": weight,
            "Top input status": status,
            "Top input basis": "All-data final-tree impurity importance; descriptive, not an independently validated effect or causal ranking"}


def recommendation_reversal_fields(record, *, point):
    """A sign-change grid does not identify reversal of an optimum or fixed box."""
    identity = ["family", "yield_pp", "horizon_days", "population", "renewal_band", "entry_band"]
    identity += ["input", "source_index"] if point else ["target", "threshold_alternative", "cost_level", "candidate"]
    return {
        "Response value that reverses it": "not determined",
        "Reversal status": "not determined",
        "Reversal reason": "Saved association/paired-mean sign changes do not estimate reversal of this selected point or confirmed box",
        "Recommendation source artifact": "point-estimates.csv" if point else "range-confirmations.csv",
        "Recommendation source selector": selector(record, identity),
    }


def contract_dispositions():
    return {
        code: {"status": "pending owner verdict", "owner": "Modeling and Project Manager",
               "reason": reason}
        for code, reason in {
            "2.5": "Saved relationship analyses available; scientific qualification and contract acceptance not supplied",
            "2.6": "Saved region analyses available; scientific qualification and contract acceptance not supplied",
            "2.8": "Recommendation tiers provisional until QB19 fresh-seed validation; MM7 timed evaluation and contract acceptance owner-pending",
        }.items()
    }


def correction_summary_rows(accuracy, points, ranking):
    """Materialize DR11 cells with explicit source scopes and unsupported states."""
    rows = []

    def append(key, value, unit, artifact, scope, **extra):
        rows.append({"Summary key": key, "Value": value, "Unit": unit,
                     "Display value": str(value), "Source artifact": artifact,
                     "Source scope": scope, **extra})

    cart_scope = ["Design family", "Competing yield (%)", "Horizon (days)",
                  "Target type", "Measure", "Threshold alternative", "Cost level"]
    if accuracy.duplicated(cart_scope).any():
        raise ValueError("repeated CART summary target")
    for record in accuracy.to_dict("records"):
        scope = selector(record, cart_scope)
        key = "MM2.top-input." + ".".join(str(record.get(k)) for k in cart_scope)
        value = record["Descriptive top input"]
        if value is None or pd.isna(value):
            value = record["Top input status"]
        append(key, value, "input", "table-10-tree-accuracy.csv", scope,
               Status=record["Top input status"], Qualification=record["Top input basis"],
               **{"Source selector": scope, "Descriptive importance": record["Descriptive top input importance"]})

    point_key = ["family", "yield_pp", "horizon_days", "population", "renewal_band", "entry_band", "input"]
    if points.duplicated(point_key).any():
        raise ValueError("repeated point-estimate identity")
    if not set(points.status) <= {"assessable", "not_applicable", "unassessable"}:
        raise ValueError("unsupported point-estimate state")
    for scope, group in points.groupby(["family", "yield_pp", "horizon_days"], dropna=False):
        for status in ("assessable", "not_applicable", "unassessable"):
            predicate = dict(zip(["Design family", "Competing yield (%)", "Horizon (days)"], scope, strict=True))
            predicate |= {"Recommendation": "point estimate", "status": status}
            source_selector = selector(predicate, predicate.keys())
            append("tiers.point-estimate." + status + "." + ".".join(map(str, scope)),
                   int(group.status.eq(status).sum()), "distinct response-cell point records",
                   "table-13-recommendations.csv", source_selector, Status=status,
                   Qualification="Observed A-only points; provisional, no validated point interval",
                   **{"Source selector": source_selector})
    for code, disposition in contract_dispositions().items():
        append("contract." + code, disposition["status"], "verdict", "analysis-receipt.json",
               "contract " + code, Status=disposition["status"], Qualification=disposition["reason"],
               **{"Source selector": "contract_dispositions." + code, "Owner": disposition["owner"]})

    # DR7 already publishes this statistic. Expose a direct selector, not a new calculation.
    rank_scope = ["Design", "Competing yield (%)", "Horizon (days)",
                  "Renewal response", "Entry response", "Measure"]
    if ranking.duplicated(rank_scope).any():
        raise ValueError("repeated design-ranking identity")
    for record in ranking.to_dict("records"):
        scope = selector(record, rank_scope)
        flag = record["Order same at every yield"]
        append("ranking.order-same-at-every-yield." + ".".join(str(record.get(k)) for k in rank_scope),
               "unassessable" if pd.isna(flag) else "yes" if flag else "no", "verdict",
               "figure-6-designs.csv", scope,
               Status="unassessable" if pd.isna(flag) else "reported",
               Qualification="Direct selector of saved DR7 statistic; original before/180 exclusions retained",
               **{"Source selector": scope})
    return rows
