"""The behaviour package: event labels, the lockbox, point-in-time features, forward folds, and the learners' guards."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from avalanche_research.behaviour import events as ev
from avalanche_research.behaviour import features as ft
from avalanche_research.behaviour import lifetimes as lt
from avalanche_research.behaviour import supervised as sv
from avalanche_research.behaviour import unsupervised as un
from avalanche_research.behaviour.inputs import (
    LOCKBOX_START,
    Inputs,
    check_cutoff,
    regime_at,
    registered_actors,
)

T0 = pd.Timestamp("2023-01-01")
DAY = pd.Timedelta(days=1)


def period(tx, node, start, days, stake=2000.0, fee=0.02, rewarded=True, address="addr-a"):
    begin = T0 + start * DAY
    return {"transaction_hash": tx, "node_id": node, "accepted_at": begin, "start_time": begin,
            "end_time": begin + days * DAY, "duration_days": float(days), "stake_avax": stake, "fee_rate": fee,
            "potential_reward_avax": stake * 0.07 * days / 365, "rewarded": rewarded, "regime": "durango",
            "start_kind": "immediate", "reward_address": address}


@pytest.fixture
def periods() -> pd.DataFrame:
    return pd.DataFrame([
        # Node A renews at once, returns after 40 days, then leaves.
        period("a1", "A", 0, 30), period("a2", "A", 32, 28, stake=3000), period("a3", "A", 100, 30, fee=0.05),
        # Node B ends 590 days in: at a cut of 600 days its outcome is censored, but its 7-day label is known.
        period("b1", "B", 500, 90, address="addr-a"),
        # Node C's next period was accepted before the cut but starts after it: it must not count yet.
        period("c1", "C", 400, 180, address="addr-c"), period("c2", "C", 605, 30, address="addr-c"),
    ]).assign(accepted_at=lambda f: f.accepted_at.where(f.transaction_hash.ne("c2"), T0 + 590 * DAY))


def daily_frame(days: int = 900) -> pd.DataFrame:
    dates = pd.date_range(T0 - 200 * DAY, periods=days, freq="D")
    n = len(dates)
    return pd.DataFrame({"date": dates, "supply_avax": np.linspace(4e8, 4.5e8, n),
                         "validator_stake_avax": np.linspace(1.6e8, 1.7e8, n),
                         "delegated_stake_avax": np.linspace(4e7, 5e7, n), "active_validators": 1300,
                         "price_usd": 20 + np.sin(np.arange(n) / 30), "volatility_30d": 0.8, "tbill_pct": 4.0})


def inputs_for(periods, cutoff) -> Inputs:
    known = periods.loc[periods.accepted_at.lt(cutoff)]
    delegations = pd.DataFrame({"transaction_hash": ["a2"], "delegations": [3], "delegators": [2],
                                "delegated_avax": [600.0], "largest_delegator_avax": [300.0],
                                "median_delegation_avax": [200.0], "max_delegation_avax": [300.0],
                                "delegator_gross_reward_avax": [4.0]})
    daily = daily_frame()
    return Inputs(periods=known, delegations=delegations, daily=daily.loc[daily.date.lt(cutoff)],
                  nodes=pd.DataFrame(columns=["named_agent"]), observed_through=cutoff)


def test_outcomes_follow_the_next_start_on_the_same_node(periods):
    events = ev.decision_events(periods, observed_through=T0 + 600 * DAY).set_index("transaction_hash")
    assert events.loc["a1", "outcome"] == "renew" and events.loc["a1", "renewed"] == 1
    assert events.loc["a2", "outcome"] == "return" and events.loc["a2", "renewed"] == 0
    assert events.loc["a2", "next_stake_avax"] == 2000 and events.loc["a2", "fee_change"] == pytest.approx(0.03)
    assert events.loc["a3", "outcome"] == "leave"
    assert events.loc["b1", "outcome"] == "censored" and events.loc["b1", "renewed"] == 0
    # c2 starts after the cut, so c1 has no next period yet and its horizon has not passed.
    assert events.loc["c1", "outcome"] == "censored" and np.isnan(events.loc["c1", "next_duration_days"])


def test_the_lockbox_is_refused_unless_asked_for(periods):
    with pytest.raises(ValueError, match="lockbox"):
        check_cutoff(LOCKBOX_START + DAY)
    with pytest.raises(ValueError, match="lockbox"):
        ev.decision_events(periods, observed_through="2026-01-01")
    assert check_cutoff(LOCKBOX_START + DAY, allow_lockbox=True) > LOCKBOX_START


def test_features_do_not_change_when_later_data_arrives(periods):
    early, late = T0 + 140 * DAY, T0 + 700 * DAY
    built = {}
    for cut in (early, late):
        events = ev.decision_events(periods, observed_through=cut)
        built[cut] = ft.build(events, inputs_for(periods, cut)).set_index(events.transaction_hash)
    before = built[early]
    after = built[late].loc[before.index]
    numeric = [c for c in before.columns if c not in ft.CATEGORICAL]
    pd.testing.assert_frame_equal(before[numeric], after[numeric])


def test_the_registry_is_the_feature_contract(periods):
    events = ev.decision_events(periods, observed_through=T0 + 600 * DAY)
    features = ft.build(events, inputs_for(periods, T0 + 600 * DAY))
    assert list(features.columns) == list(ft.NAMES)
    assert ft.registry_frame().name.is_unique
    row = features.set_index(events.transaction_hash).loc["a2"]
    assert row.delegation_ratio == pytest.approx(0.2) and row.largest_delegator_share == pytest.approx(0.5)
    assert row.prior_renew_share == 1 and row.stake_change_prev_log == pytest.approx(np.log(1.5))
    # b1 shares a1's reward address, which node A first used on day 0.
    assert features.set_index(events.transaction_hash).loc["b1", "operator_nodes_to_date"] == 2


def test_forward_folds_train_only_on_labels_known_at_the_fold_start():
    ends = pd.date_range("2022-06-01", "2025-11-01", freq="5D")
    meta = pd.DataFrame({"end_time": ends})
    folds = sv.forward_folds(meta, "renewed")
    assert folds and folds[-1].end == LOCKBOX_START
    for fold in folds:
        assert (meta.end_time.iloc[fold.train] + 7 * DAY).max() <= fold.start
        tested = meta.end_time.iloc[fold.test]
        assert tested.min() >= fold.start and tested.max() < fold.end
        assert (tested + 7 * DAY).max() <= LOCKBOX_START


def test_the_node_history_benchmark_shrinks_toward_the_base_rate():
    X = pd.DataFrame({"period_number": [1, 3, 11], "prior_renew_share": [np.nan, 1.0, 0.0]})
    model = sv.NodeHistory(strength=2).fit(X, np.array([1, 1, 0, 0]))
    p = model.predict_proba(X)[:, 1]
    assert p[0] == pytest.approx(0.5) and p[1] == pytest.approx((2 + 1) / 4) and p[2] == pytest.approx(1 / 12)


def test_lifetimes_and_the_null_sample():
    rng = np.random.default_rng(0)
    rows = []
    for n in range(40):
        for k in range(int(rng.integers(2, 6))):
            rows.append(period(f"{n}-{k}", f"N{n}", 40 * k + n, 30, stake=2000 + 100 * n, address=f"addr-{n % 5}"))
    periods = pd.DataFrame(rows)
    cut = T0 + 700 * DAY
    events = ev.decision_events(periods, observed_through=cut)
    life = lt.build(events, ft.build(events, inputs_for(periods, cut)))
    assert len(life) == 40 and list(life.columns) == list(lt.BEHAVIOUR + lt.CONTEXT)
    x = un.matrix(life, lt.BEHAVIOUR)
    agreement = un.stability(x, "kmeans", 3, rounds=3)
    assert agreement.between(-1, 1).all()


def test_the_null_sample_keeps_marginals_and_correlations():
    rng = np.random.default_rng(1)
    base = rng.multivariate_normal([0, 0, 0], [[1, 0.8, 0], [0.8, 1, 0.3], [0, 0.3, 1]], size=4000)
    x = pd.DataFrame(base, columns=["a", "b", "c"])
    x["tied"] = np.where(base[:, 0] > 1, base[:, 0], 0.0)  # mostly one value, as many shares are
    null = un.null_sample(x)
    assert null.shape == x.shape and null.index.equals(x.index)
    assert abs(null.tied.eq(0).mean() - x.tied.eq(0).mean()) < 0.03
    assert np.allclose(null[["a", "b", "c"]].corr().to_numpy(), x[["a", "b", "c"]].corr().to_numpy(), atol=0.08)


def test_the_trailing_year_benchmark_uses_only_the_year_before_the_origin():
    origin = pd.Timestamp("2024-01-01")
    end_time = pd.to_datetime(["2022-03-01", "2022-06-01", "2023-03-01", "2023-09-01"])
    model = sv.TrailingYear().fit(pd.DataFrame(index=range(4)), np.array([0, 0, 1, 1]), end_time=end_time,
                                  origin=origin)
    assert model.predict_proba(pd.DataFrame(index=range(2)))[:, 1] == pytest.approx([1.0, 1.0])


def test_expected_calibration_error():
    rng = np.random.default_rng(0)
    p = rng.uniform(size=20000)
    assert sv.expected_calibration_error(rng.uniform(size=20000) < p, p) < 0.02
    assert sv.expected_calibration_error(np.zeros(100), np.full(100, 0.9)) == pytest.approx(0.9)


def test_row_losses_average_to_the_fold_score():
    rng = np.random.default_rng(1)
    n = 400
    X = pd.DataFrame({"period_number": rng.integers(1, 5, n), "prior_renew_share": rng.uniform(size=n),
                      "duration_days": rng.uniform(14, 365, n)})
    y = pd.Series((rng.uniform(size=n) < 0.7).astype(float))
    meta = pd.DataFrame({"end_time": pd.date_range("2023-01-01", periods=n, freq="D")})
    folds = [sv.Fold("f", pd.Timestamp("2023-11-01"), pd.Timestamp("2024-02-05"),
                     np.arange(0, 290), np.arange(304, 400))]
    candidates = {"prior": sv.models()["prior"], "trailing_year": sv.TrailingYear()}
    scores, predictions = sv.evaluate(X, y, meta, folds, candidates)
    mean_rows = predictions.groupby("model").log_loss.mean()
    assert mean_rows.to_dict() == pytest.approx(scores.set_index("model").log_loss.to_dict())
    assert scores.ece.notna().all()


def test_early_stopping_holds_out_the_latest_training_rows():
    from sklearn.ensemble import HistGradientBoostingClassifier

    seen = {}

    class Spy(HistGradientBoostingClassifier):
        def fit(self, X, y, **kwargs):
            seen["fit"], seen["val"] = X.index, kwargs["X_val"].index
            return super().fit(X, y, **kwargs)

    rng = np.random.default_rng(2)
    n = 400
    X = pd.DataFrame({"a": rng.normal(size=n)}, index=rng.permutation(n))
    y = pd.Series((rng.uniform(size=n) < 0.6).astype(float), index=X.index)
    meta = pd.DataFrame({"end_time": pd.Timestamp("2023-01-01") + pd.to_timedelta(X.index, unit="D")}, index=X.index)
    folds = [sv.Fold("f", pd.Timestamp("2024-01-01"), pd.Timestamp("2024-03-01"),
                     np.arange(0, 300), np.arange(300, 400))]
    sv.evaluate(X, y, meta, folds, {"boosted": Spy(early_stopping=True, validation_fraction=0.15, max_iter=20)})
    train_days = X.index[:300]
    assert len(seen["val"]) == 45
    assert seen["val"].min() > seen["fit"].max()
    assert set(seen["val"]) == set(np.sort(train_days)[-45:])


def test_a_feature_unobserved_in_the_fitted_rows_is_left_out_of_that_fit():
    # At the earliest origins the 90-day price return has no value on any training row. The boosted model's binning
    # refuses such a column, so a fold fits without it. Before the fix this raised "window shape cannot be larger".
    from sklearn.ensemble import HistGradientBoostingClassifier

    seen = {}

    class Spy(HistGradientBoostingClassifier):
        def fit(self, X, y, **kwargs):
            seen["columns"] = list(X.columns)
            return super().fit(X, y, **kwargs)

    rng = np.random.default_rng(3)
    n = 400
    X = pd.DataFrame({"a": rng.normal(size=n), "late": np.r_[np.full(300, np.nan), rng.normal(size=100)]})
    y = pd.Series((rng.uniform(size=n) < 0.6).astype(float))
    meta = pd.DataFrame({"end_time": pd.Timestamp("2023-01-01") + pd.to_timedelta(np.arange(n), unit="D")})
    folds = [sv.Fold("f", pd.Timestamp("2024-01-01"), pd.Timestamp("2024-03-01"), np.arange(0, 300), np.arange(300, 400))]
    scores, _ = sv.evaluate(X, y, meta, folds, {"boosted": Spy(early_stopping=True, validation_fraction=0.15, max_iter=20)})
    assert seen["columns"] == ["a"] and len(scores) == 1


def test_the_protocol_origins_are_the_upgrades_and_quarter_starts():
    origins = sv.protocol_origins()
    assert len(origins) == 19
    assert origins.is_monotonic_increasing
    assert origins["durango"] == pd.Timestamp("2024-03-06 16:00")
    assert origins["fortuna"] == pd.Timestamp("2025-04-08 15:00")
    assert origins["2022-Q1"] == pd.Timestamp("2022-01-01") and origins["2025-Q2"] == pd.Timestamp("2025-04-01")


def test_protocol_folds_train_on_what_is_known_and_test_inside_the_horizon():
    meta = pd.DataFrame({"end_time": pd.date_range("2021-01-01", "2025-11-30", freq="12h")})
    folds = sv.protocol_folds(meta, "renewed")
    follow = 7 * DAY
    cutoff = pd.Timestamp("2025-11-19 16:00")
    assert {f.name for f in folds} >= {"banff+30d", "fortuna+180d", "2025-Q2+180d"}
    assert len(folds) == 19 * 3
    for fold in folds:
        train, test = meta.end_time.iloc[fold.train], meta.end_time.iloc[fold.test]
        assert (train + follow).le(fold.start).all()
        assert test.ge(fold.start).all() and test.lt(fold.end).all() and (test + follow).le(cutoff).all()
        assert fold.end <= cutoff


def test_the_duration_benchmark_is_a_transition_table():
    X = pd.DataFrame({"duration_days": [14, 14, 14, 90, 90]})
    y = np.array(["up to 3 weeks", "up to 3 weeks", "3 to 6 weeks", "6 weeks to 3 months", "6 weeks to 3 months"])
    model = sv.DurationTransition(smoothing=0).fit(X, y)
    p = pd.DataFrame(model.predict_proba(pd.DataFrame({"duration_days": [14, 90]})), columns=model.classes_)
    assert p.loc[0, "up to 3 weeks"] == pytest.approx(2 / 3) and p.loc[1, "6 weeks to 3 months"] == 1


def test_the_renewal_label_is_the_registered_measure(periods):
    from avalanche_research import staking_renewal

    cut = T0 + 600 * DAY
    events = ev.decision_events(periods, observed_through=cut)
    mine = events.loc[events.renewed.notna() & (events.end_time + 7 * DAY).le(cut), "renewed"].mean()
    measure = staking_renewal.renewal_summary(staking_renewal.renewal_events(periods), T0, cut, cut)
    assert mine == pytest.approx(measure["renewal_share"])


def test_an_ending_inside_the_renewal_window_is_never_labelled():
    cut = T0 + 100 * DAY
    near = pd.DataFrame([period("n1", "x", 67, 30), period("n2", "x", 99, 30),
                         period("m1", "y", 66, 30)])
    events = ev.decision_events(near, observed_through=cut).set_index("transaction_hash")
    # n1 ended 3 days before the cut and renewed 1 day before it; m1 ended 4 days before and has not. Neither is known.
    assert events.loc[["n1", "m1"], "renewed"].isna().all()
    assert events.loc["n1", "outcome"] == "renew"


def test_the_principal_flow_conserves_stake(periods):
    cut = T0 + 600 * DAY
    events = ev.decision_events(periods, observed_through=cut)
    flows = ev.principal_flow(events, periods.loc[periods.start_time.lt(cut)], T0, cut)
    inflow = flows.groupby("target").avax.sum()
    outflow = flows.groupby("source").avax.sum()
    for node in ("Renewed in place", "Fresh principal"):
        assert inflow[node] == pytest.approx(outflow[node])
    # a1 renews into a2 (2,000 to 3,000 AVAX); a3 returns after 40 days; nodes A, B and C start fresh.
    by = flows.set_index(["source", "target"]).avax
    assert by["Added at renewal", "Renewed in place"] == 1000
    assert by["Returned within a year", "Fresh principal"] == 2000
    assert by["First period of a new node", "Fresh principal"] == 6000


def boundary_period(tx, node, end):
    # One 14-day period that ends at ``end``, in the shape of data science's DS3 fixtures.
    begin = end - 14 * DAY
    return {**period(tx, node, 0, 14), "accepted_at": begin, "start_time": begin, "end_time": end}


def test_nothing_touching_the_lockbox_is_an_event_or_a_label():
    # DS3 F1: a follow-up window that ends at the lockbox's first instant is not complete, and an ending there is not
    # an event. The cutoff is the first instant not observed.
    cut = LOCKBOX_START
    touch = ev.decision_events(pd.DataFrame([boundary_period("touch", "A", cut - 7 * DAY)]), observed_through=cut)
    assert touch.renewed.isna().all()
    assert ev.decision_events(pd.DataFrame([boundary_period("at", "A", cut)]), observed_through=cut).empty
    inside = ev.decision_events(pd.DataFrame([boundary_period("in", "A", cut - 7 * DAY - pd.Timedelta(seconds=1))]),
                                observed_through=cut)
    assert inside.renewed.tolist() == [0.0]


def test_both_fold_schemes_leave_out_a_follow_up_that_reaches_the_lockbox():
    cut = LOCKBOX_START
    origin = cut - 30 * DAY
    meta = pd.DataFrame({"end_time": [origin - 8 * DAY, cut - 7 * DAY]})
    protocol = sv.protocol_folds(meta, "renewed", origins=pd.Series({"o": origin}), horizons=(30,), observed_through=cut)
    assert all(1 not in fold.test for fold in protocol)
    forward = sv.forward_folds(meta, "renewed", first=str(origin), observed_through=cut)
    assert all(1 not in fold.test for fold in forward)


@pytest.mark.parametrize("change", ["duplicate", "node", "end", "start", "transaction"])
def test_periods_that_cannot_be_keyed_are_refused(change):
    # DS3 F2.
    base = pd.DataFrame([boundary_period("valid", "A", LOCKBOX_START - 40 * DAY)])
    bad = {
        "duplicate": pd.concat([base, base], ignore_index=True),
        "node": base.assign(node_id=None),
        "end": base.assign(end_time=pd.NaT),
        "start": base.assign(start_time=pd.NaT),
        "transaction": base.assign(transaction_hash=None),
    }[change]
    with pytest.raises(ValueError):
        ev.decision_events(bad, observed_through=LOCKBOX_START)


@pytest.mark.parametrize("value", [None, pd.NaT, float("nan")])
def test_a_missing_cutoff_is_refused(value):
    with pytest.raises(ValueError, match="required"):
        check_cutoff(value)


def test_the_regime_is_the_upgrade_in_force_when_the_period_ends():
    # EX14: the rule set of a decision is the one in force at its end, not at the ended period's acceptance.
    times = pd.Series([pd.Timestamp(t) for t in ("2020-09-15", "2025-11-19 15:59:59", "2025-11-19 16:00:00", "2026-10-01")])
    assert regime_at(times).tolist() == ["genesis", "fortuna", "granite", "helicon"]


def attribution(identifier, subject, tier, kind_class, name):
    return {"attribution_id": identifier, "subject_kind": "reward-address", "subject": subject, "name": name,
            "statement": "fixture", "tier": tier, "class": kind_class, "source": "https://example.org", "supporting_sources": [],
            "captured_on": "2026-10-05", "data_run": None, "agent": "data-engineer", "replaces": None}


def test_a_period_is_set_apart_by_its_own_address_from_the_evidence_date(tmp_path):
    # EX13 and MV7: the period's own reward address, not the node's latest, and only from the evidence date on. An
    # inferred label never selects rows, and a registry row with no evidence date stays pooled.
    path = tmp_path / "attributions.json"
    path.write_text(json.dumps({"schema_version": "operator-attributions/v1", "description": "fixture", "attributions": [
        attribution("OA1", "addr-gg", "AS1", "EVIDENCE", "GoGoPool"),
        attribution("OA3", "addr-inferred", "AS4", "INFERENCE", "Someone"),
        attribution("OA10", "addr-undated", "AS1", "EVIDENCE", "Undated"),
    ]}))
    periods = pd.DataFrame({
        "node_id": ["A", "A", "B", "C"],
        "reward_address": ["addr-other", "addr-gg", "addr-inferred", "addr-undated"],
        "end_time": pd.to_datetime(["2023-05-01", "2023-06-01", "2024-01-01", "2024-01-01"]),
    })
    before = periods.assign(end_time=pd.to_datetime(["2023-03-01", "2023-04-01", "2024-01-01", "2024-01-01"]))
    assert registered_actors(periods, path).where(lambda v: v.notna(), None).tolist() == [None, "GoGoPool", None, None]
    assert registered_actors(before, path).isna().all()
