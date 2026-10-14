"""Cell evidence must not turn family context into recommendation validation."""

import json

import pandas as pd
import pytest

from avalanche_research.analysis.explainer_tiers import tier_cell_detail


def sources():
    context = {"family": "ramp", "yield_pp": 5., "horizon_days": 365}
    cells = [("grid", r, e, None, None) for r in ("low", "middle", "high") for e in ("low", "middle", "high")]
    cells += [("zero", "zero", "zero", 0., 0.), ("stress_1", "stress_1", "stress_1", .3, 0.), ("stress_2", "stress_2", "stress_2", 0., .3), ("stress_3", "stress_3", "stress_3", .3, .3)]
    comparisons, passes = [], []
    for pop, r, e, rv, ev in cells:
        cell = context | {"population": pop, "renewal_band": r, "entry_band": e, "renewal_response": rv, "entry_response": ev}
        comparisons.append(cell | {"measure": "issuance_saved", "input": "family_against_matched_baseline", "method": "mean_difference", "coefficient": -.2, "ci_low": -.3, "ci_high": -.1, "status": "assessable", "interval_status": "assessable", "reason": None, "bootstrap_sha256": "family-mean"})
        passes.append(cell | {"measure": "issuance_saved", "threshold_alternative": "primary", "cost_level": "not_cost_sensitive", "pass_share": .6, "ci_low": .4, "ci_high": .8, "status": "assessable", "reason": None, "bootstrap_sha256": "family-pass", "interval_interpretation": "conditional design cluster bootstrap"})
    original = context | {"population": "grid", "renewal_band": "low", "entry_band": "low", "status": "found", "reason": None, "provisional": True, "excluded_from_tiers": False}
    ranges = pd.DataFrame([original | {"target": "issuance_saved", "threshold_alternative": "primary", "cost_level": "not_cost_sensitive", "candidate": "A-selected", "bounds": '[{"input":"target_min_rate","lower":0.01,"upper":0.02}]', "tier": "per-goal range", "goal_column": "issuance_saved", "goal_mean": .1, "goal_ci_low": .01, "goal_ci_high": .2, "goal_interval_status": "assessable", "pass_share": .95, "ci_low": .9, "ci_high": 1., "eligible_for_recommendation": True}])
    points = pd.DataFrame([original | {"input": "target_min_rate", "value": .015, "source_index": 9, "issuance_saved": .3, "status": "assessable"}])
    return ranges, points, pd.DataFrame(comparisons), pd.DataFrame(passes)


def test_source_cell_is_distinct_from_family_and_cross_cell():
    result = tier_cell_detail(*sources())
    assert len(result) == 26
    assert result.recommendation_id.nunique() == 2
    own = result[result.recommendation_kind.eq("range") & result.recommendation_evidence_scope.eq("source cell only")].iloc[0]
    assert own.recommendation_mean == .1
    assert own.recommendation_ci_low == .01
    assert own.recommendation_pass_share == .95
    assert own.family_context_mean == -.2
    assert own.family_context_sign == "negative"
    assert own.recommendation_sign == "positive"
    assert own.family_context_pass_share == .6
    other = result[result.recommendation_evidence_scope.eq("unsupported cross-cell")]
    assert len(other) == 24
    assert other[["recommendation_mean", "recommendation_ci_low", "recommendation_pass_share", "recommendation_pass_ci_low", "recommendation_sign"]].isna().all().all()
    assert other.recommendation_evidence_reason.str.contains("not evaluated").all()
    assert other.family_context_mean.eq(-.2).all()
    assert json.loads(own.source_selector)["candidate"] == "A-selected"


def test_points_never_borrow_family_intervals():
    result = tier_cell_detail(*sources())
    point = result[result.recommendation_kind.eq("point") & result.recommendation_evidence_scope.eq("source cell only")].iloc[0]
    assert point.recommendation_mean == .3
    assert point.recommendation_sign == "positive"
    assert pd.isna(point.recommendation_ci_low)
    assert pd.isna(point.recommendation_pass_share)
    assert "no validated" in point.recommendation_interval_reason


def test_stress_settings_remain_three_distinct_cells():
    result = tier_cell_detail(*sources())
    stress = result[result.population.str.startswith("stress")].drop_duplicates("population")
    assert set(zip(stress.renewal_response, stress.entry_response, strict=True)) == {(.3, 0.), (0., .3), (.3, .3)}


@pytest.mark.parametrize("fault", ["duplicate_mean", "duplicate_pass", "missing_stress", "mixed_method", "duplicate_recommendation"])
def test_ambiguous_or_incomplete_context_refuses(fault):
    r, p, m, s = sources()
    if fault == "duplicate_mean":
        m = pd.concat([m, m.iloc[[0]]])
    elif fault == "duplicate_pass":
        s = pd.concat([s, s.iloc[[0]]])
    elif fault == "missing_stress":
        m = m[m.population.ne("stress_2")]
    elif fault == "mixed_method":
        m.loc[0, "method"] = "spearman"
    else:
        r = pd.concat([r, r])
    with pytest.raises(ValueError):
        tier_cell_detail(r, p, m, s)


def test_unsupported_targets_and_constant_diagnostics_remain_explicit():
    r, p, m, s = sources()
    m.loc[0, ["coefficient", "ci_low", "ci_high"]] = 0.
    m.loc[0, "status"] = "unassessable"
    m.loc[0, "reason"] = "constant_kpi"
    r.loc[0, "target"] = "all_joint"
    r.loc[0, ["goal_mean", "goal_ci_low", "goal_ci_high"]] = None
    result = tier_cell_detail(r, p, m, s)
    joint = result[result.recommendation_kind.eq("range")]
    assert joint.family_context_mean.isna().all()
    assert joint.family_context_pass_share.isna().all()
    assert joint.recommendation_sign.isna().all()
    point = result[result.recommendation_kind.eq("point") & result.renewal_band.eq("low") & result.entry_band.eq("low")].iloc[0]
    assert point.family_context_mean == 0
    assert point.family_context_status == "unassessable"
    assert point.family_context_reason == "constant_kpi"
