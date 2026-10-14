"""Expose saved recommendation evidence and separately scoped family context.

This adapter selects existing cells. It never evaluates a selected box or point
on another response population and never constructs an interval.
"""

from __future__ import annotations

import hashlib
import json

import pandas as pd

SCOPE = ["family", "yield_pp", "horizon_days"]
CELL = ["population", "renewal_band", "entry_band"]
RELATIVE = {"issuance_saved", "validator_stake_retained", "active_validators_retained"}
CROSS_CELL_REASON = "Selected recommendation was not evaluated on this response cell in saved results"


def _sign(value):
    if pd.isna(value):
        return None
    return "positive" if value > 0 else "negative" if value < 0 else "zero"


def _index(frame, keys, name):
    if frame.duplicated(keys).any():
        raise ValueError(f"duplicate {name} identity")
    return {tuple(record[key] for key in keys): record for record in frame.to_dict("records")}


def _recommendations(ranges, points):
    result = []
    for artifact, frame, kind in (
        ("range-confirmations.csv", ranges, "range"),
        ("point-estimates.csv", points, "point"),
    ):
        keys = SCOPE + CELL + (["target", "threshold_alternative", "cost_level", "candidate"] if kind == "range" else ["input"])
        _index(frame.fillna(""), keys, "recommendation source")
        for ordinal, record in enumerate(frame.to_dict("records")):
            # An ordinal identifies a data row before bound expansion. Artifact
            # bytes are authenticated by the caller and bound in the receipt.
            identity = f"{artifact}:{ordinal}"
            source = {key: None if pd.isna(record[key]) else record[key] for key in keys}
            result.append(record | {
                "recommendation_id": hashlib.sha256(identity.encode()).hexdigest(),
                "recommendation_kind": kind,
                "source_artifact": artifact,
                "source_data_row_zero_based": ordinal,
                "source_selector": json.dumps(source, sort_keys=True),
                "target": record.get("target", "issuance_saved"),
                "threshold_alternative": record.get("threshold_alternative", "primary"),
                "cost_level": record.get("cost_level", "not_cost_sensitive"),
            })
    return result


def tier_cell_detail(ranges, points, comparisons, passes):
    """Return 13 explicitly qualified cells per saved recommendation record.

    ``recommendation_*`` statistics belong only to the selected recommendation's
    original response cell. ``family_context_*`` statistics describe the whole
    family population and are never substituted into recommendation columns.
    Unavailable cells remain empty with reasons. Constant-measure diagnostics
    retain their supplied estimates, intervals, statuses and causes.
    """
    if set(comparisons.input) != {"family_against_matched_baseline"} or set(comparisons.method) != {"mean_difference"}:
        raise ValueError("family context must be saved paired mean differences")
    means = _index(comparisons, SCOPE + CELL + ["measure"], "family comparison")
    selected_passes = passes[passes.population.isin(["grid", "zero", "stress_1", "stress_2", "stress_3"])]
    shares = _index(selected_passes, SCOPE + CELL + ["measure", "threshold_alternative", "cost_level"], "family pass share")
    descriptors = comparisons[SCOPE + CELL + ["renewal_response", "entry_response"]].drop_duplicates()
    _index(descriptors, SCOPE + CELL, "response cell")
    cells_by_scope = {}
    expected = {("grid", r, e) for r in ("low", "middle", "high") for e in ("low", "middle", "high")}
    expected |= {(x, x, x) for x in ("zero", "stress_1", "stress_2", "stress_3")}
    for scope, group in descriptors.groupby(SCOPE, sort=False):
        if set(group[CELL].itertuples(index=False, name=None)) != expected:
            raise ValueError("each family scope requires nine grid, zero and three distinct stress cells")
        cells_by_scope[scope] = group.to_dict("records")
    rows = []
    for rec in _recommendations(ranges, points):
        scope = tuple(rec[key] for key in SCOPE)
        if scope not in cells_by_scope:
            raise ValueError("recommendation has no family response context")
        original_cell = tuple(rec[key] for key in CELL)
        if original_cell not in expected:
            raise ValueError("unsupported recommendation source cell")
        is_point = rec["recommendation_kind"] == "point"
        for cell in cells_by_scope[scope]:
            cell_identity = tuple(cell[key] for key in CELL)
            own = original_cell == cell_identity
            base = scope + cell_identity
            mean = means.get(base + (rec["target"],))
            share = shares.get(base + (rec["target"], rec["threshold_alternative"], rec["cost_level"]))
            goal_value = rec.get("issuance_saved") if is_point else rec.get("goal_mean")
            goal_measure = "issuance_saved" if is_point else rec.get("goal_column")
            goal_interval = not is_point and pd.notna(rec.get("goal_ci_low")) and pd.notna(rec.get("goal_ci_high"))
            row = {**cell, **{key: rec[key] for key in (
                "recommendation_id", "recommendation_kind", "source_artifact",
                "source_data_row_zero_based", "source_selector", "target",
                "threshold_alternative", "cost_level",
            )}, "source_population": rec["population"],
                "source_renewal_band": rec["renewal_band"], "source_entry_band": rec["entry_band"],
                "source_status": rec["status"], "source_reason": rec.get("reason"),
                "source_tier": rec.get("tier", "point estimate"),
                "source_candidate": rec.get("candidate"), "source_bounds": rec.get("bounds"),
                "source_input": rec.get("input"), "source_value": rec.get("value"),
                "source_index": rec.get("source_index"),
                "provisional": rec.get("provisional"),
                "source_eligible_for_recommendation": rec.get("eligible_for_recommendation"),
                "source_excluded_from_tiers": rec.get("excluded_from_tiers"),
                "recommendation_evidence_scope": "source cell only" if own else "unsupported cross-cell",
                "recommendation_evidence_status": rec["status"] if own else "unsupported",
                "recommendation_evidence_reason": rec.get("reason") if own else CROSS_CELL_REASON,
                "recommendation_mean": goal_value if own else None,
                "recommendation_sign_measure": goal_measure if own else None,
                "recommendation_sign_reference": 0 if own and pd.notna(goal_measure) else None,
                "recommendation_sign": _sign(goal_value) if own else None,
                "recommendation_sign_reason": (
                    CROSS_CELL_REASON if not own else
                    "Saved source has no recommendation goal mean" if pd.isna(goal_value) else
                    "Observed A point; no validated point interval" if is_point else
                    "Sign of saved goal mean relative to zero; not a joint-goal effect"
                ),
                "recommendation_ci_low": rec.get("goal_ci_low") if own and not is_point else None,
                "recommendation_ci_high": rec.get("goal_ci_high") if own and not is_point else None,
                "recommendation_interval_status": rec.get("goal_interval_status") if own and goal_interval else "unsupported",
                "recommendation_interval_reason": (
                    CROSS_CELL_REASON if not own else
                    "Observed A point; no validated point interval" if is_point else
                    "No saved recommendation goal interval for this target/status" if not goal_interval else rec.get("goal_reason")
                ),
                "recommendation_pass_share": rec.get("pass_share") if own and not is_point else None,
                "recommendation_pass_ci_low": rec.get("ci_low") if own and not is_point else None,
                "recommendation_pass_ci_high": rec.get("ci_high") if own and not is_point else None,
                "recommendation_pass_reason": CROSS_CELL_REASON if not own else "Observed point has no validated pass-share interval" if is_point else rec.get("reason"),
                "recommendation_interval_interpretation": rec.get("interval_interpretation") if own and not is_point else None,
                "recommendation_goal_bootstrap_sha256": rec.get("goal_bootstrap_sha256") if own and not is_point else None,
                "recommendation_pass_bootstrap_sha256": rec.get("bootstrap_sha256") if own and not is_point else None,
                "family_context_scope": "whole family response population; not the selected recommendation",
                "family_context_measure": rec["target"],
                "family_context_mean": mean["coefficient"] if mean else None,
                "family_context_sign": _sign(mean["coefficient"]) if mean else None,
                "family_context_sign_reference": 0 if mean else None,
                "family_context_ci_low": mean["ci_low"] if mean else None,
                "family_context_ci_high": mean["ci_high"] if mean else None,
                "family_context_status": mean["status"] if mean else "unsupported",
                "family_context_interval_status": mean["interval_status"] if mean else "unsupported",
                "family_context_reason": mean.get("reason") if mean else "No saved paired family comparison for this target",
                "family_context_mean_bootstrap_sha256": mean.get("bootstrap_sha256") if mean else None,
                "family_context_pass_share": share["pass_share"] if share else None,
                "family_context_pass_ci_low": share["ci_low"] if share else None,
                "family_context_pass_ci_high": share["ci_high"] if share else None,
                "family_context_pass_status": share["status"] if share else "unsupported",
                "family_context_pass_reason": share.get("reason") if share else "No saved family pass share for this target/alternative/cost",
                "family_context_pass_bootstrap_sha256": share.get("bootstrap_sha256") if share else None,
                "family_context_interval_interpretation": share.get("interval_interpretation") if share else None,
                "MG9_status": "partial: source-cell evidence and separately scoped family context",
            }
            rows.append(row)
    result = pd.DataFrame(rows)
    if result.duplicated(["recommendation_id"] + CELL).any():
        raise ValueError("repeated recommendation/cell identity")
    return result
