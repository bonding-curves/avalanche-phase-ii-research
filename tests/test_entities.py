"""The entity layer: as-of history (EF1), the forward-fold splitter (FS1), shrinkage (EF3) and the effect table (EF4)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("scipy")

from avalanche_research.behaviour import entities as en
from avalanche_research.behaviour import shrink as sh
from avalanche_research.behaviour.inputs import LOCKBOX_START

DAY = pd.Timedelta(days=1)
T0 = pd.Timestamp("2023-01-01")


def decisions(n_nodes: int = 30, per_node: int = 12, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for j in range(n_nodes):
        p = rng.beta(4, 2)
        for i in range(per_node):
            end = T0 + (j % 5 + i * 20) * DAY
            rows.append({"transaction_hash": f"t{j}-{i}", "node_id": f"N{j}", "end_time": end,
                         "renewed": float(rng.uniform() < p), "stratum": "large" if j % 2 else "small"})
    return pd.DataFrame(rows)


def test_a_label_enters_history_only_once_observable_before_as_of():
    frame = pd.DataFrame({"transaction_hash": ["six", "eight"], "node_id": ["A", "A"], "renewed": [1.0, 0.0],
                          "end_time": [pd.Timestamp("2024-01-25"), pd.Timestamp("2024-01-23")]})
    history = en.entity_history(frame, en.node_members(frame), pd.Timestamp("2024-01-31"))
    assert history.transaction_hash.tolist() == ["eight"]


def test_history_as_of_a_cut_ignores_everything_after_it():
    # TS1 at three cuts: changing or dropping decisions after the cut leaves the history identical.
    frame = decisions()
    members = en.node_members(frame)
    for cut in (T0 + 60 * DAY, T0 + 120 * DAY, T0 + 200 * DAY):
        later = frame.end_time.add(7 * DAY).ge(cut)
        altered = frame.assign(renewed=np.where(later, 1 - frame.renewed, frame.renewed))
        assert en.entity_history(frame, members, cut).equals(en.entity_history(altered, members, cut))
        assert en.entity_history(frame, members, cut).equals(en.entity_history(frame.loc[~later], members, cut))


def test_the_lockbox_is_refused_unless_asked_for():
    frame = decisions()
    # The cut is the first instant not observed, so the lockbox's first instant is allowed and anything later is not.
    assert len(en.entity_history(frame, en.node_members(frame), LOCKBOX_START)) == len(frame)
    with pytest.raises(ValueError, match="lockbox"):
        en.entity_history(frame, en.node_members(frame), LOCKBOX_START + DAY)
    assert len(en.entity_history(frame, en.node_members(frame), LOCKBOX_START + DAY, allow_lockbox=True)) == len(frame)


def test_each_fold_carries_the_history_of_its_own_origin():
    frame = decisions(per_node=40)
    origins = pd.Series({"q1": T0 + 300 * DAY, "q2": T0 + 500 * DAY})
    folds = en.entity_folds(frame, en.node_members(frame), origins=origins, horizons=(90,))
    assert [f.fold.name for f in folds] == ["q1+90d", "q2+90d"]
    for item in folds:
        assert item.history.end_time.add(7 * DAY).lt(item.fold.start).all()
        assert set(frame.iloc[item.fold.train].transaction_hash) == set(item.history.transaction_hash)


def test_shrinkage_recovers_known_hyperparameters_and_respects_its_limits():
    rng = np.random.default_rng(1)
    rows = []
    for j in range(600):
        p, n = rng.beta(4, 12), rng.integers(5, 40)
        rows += [{"entity_id": f"e{j}", "renewed": float(rng.uniform() < p), "end_time": T0} for _ in range(n)]
    fit = sh.shrink(pd.DataFrame(rows), "renewed", family="beta-binomial")
    a, b = fit.hyperparameters["pooled"]["a"], fit.hyperparameters["pooled"]["b"]
    assert abs(a / (a + b) - 0.25) < 0.02 and 12 < a + b < 20
    # With many decisions an entity's estimate approaches its own rate.
    rows += [{"entity_id": "big", "renewed": 1.0, "end_time": T0}] * 5000
    big = sh.shrink(pd.DataFrame(rows), "renewed", family="beta-binomial").rows.set_index("entity_id").loc["big"]
    assert big.estimate > 0.995 and big.n == 5000


@pytest.mark.parametrize(("family", "make", "check"), [
    ("normal", lambda rng: [{"entity_id": f"e{j}", "x": th + rng.normal(0, 0.5), "end_time": T0}
                            for j, th in enumerate(rng.normal(0.1, 0.3, 500)) for _ in range(rng.integers(3, 20))],
     lambda h: abs(h["mu"] - 0.1) < 0.05 and abs(h["tau"] - 0.3) < 0.06 and abs(h["sigma"] - 0.5) < 0.03),
    ("dirichlet-multinomial", lambda rng: [{"entity_id": f"e{j}", "x": "abc"[c], "end_time": T0} for j in range(500)
                                           for c in rng.choice(3, size=rng.integers(5, 30), p=rng.dirichlet([2, 3, 5]))],
     lambda h: abs(h["alpha"]["a"] / sum(h["alpha"].values()) - 0.2) < 0.03),
])
def test_every_family_recovers_its_prior(family, make, check):
    fit = sh.shrink(pd.DataFrame(make(np.random.default_rng(2))), "x", family=family)
    assert check(fit.hyperparameters["pooled"])


def test_a_stratified_prior_fits_each_stratum_and_the_mixture_waits_for_the_type_model():
    history = decisions().rename(columns={"node_id": "entity_id"})
    fit = sh.shrink(history, "renewed", family="beta-binomial", by="stratum")
    assert set(fit.hyperparameters) == {"pooled", "stratum=large", "stratum=small"}
    assert set(fit.rows.prior_id) == {"stratum=large", "stratum=small"}
    with pytest.raises(NotImplementedError):
        sh.shrink(history, "renewed", family="beta-binomial", prior="mixture")


def test_the_effect_table_refuses_the_past_and_gives_an_unseen_entity_the_prior():
    frame = decisions()
    as_of = T0 + 200 * DAY
    history = en.entity_history(frame, en.node_members(frame), as_of)
    fit = sh.shrink(history, "renewed", family="beta-binomial")
    table = en.effects(fit, as_of)
    with pytest.raises(ValueError, match="earlier"):
        table.at(["N1"], as_of - DAY)
    looked = table.at(["N1", "unseen"], as_of).set_index("entity_id")
    assert looked.loc["unseen", "n"] == 0 and looked.loc["unseen", "estimate"] == pytest.approx(table.prior.estimate.item())
    assert looked.loc["N1", "n"] > 0
    assert en.effects(fit, as_of).receipt_id == table.receipt_id
    with pytest.raises(ValueError, match="lockbox"):
        en.effects(fit, LOCKBOX_START + DAY)


# Data science's entity contract review of 0f1889a, EC4 to EC14 and EV1, one test per repaired contract.
ORIGIN = pd.Timestamp("2024-01-01")


def panel(ends, **columns):
    return pd.DataFrame({"transaction_hash": [f"t{i}" for i in range(len(ends))], "node_id": "A",
                         "end_time": pd.to_datetime(ends), "renewed": 1.0, **columns})


def cut_history(frame, as_of=ORIGIN, **kw):
    return en.entity_history(frame, en.node_members(frame), as_of, **kw)


def test_ec4_training_rows_and_history_share_the_strict_cut():
    frame = panel([ORIGIN - 8 * DAY, ORIGIN - 7 * DAY, ORIGIN + DAY])
    fold = en.entity_folds(frame, en.node_members(frame), origins=pd.Series({"o": ORIGIN}), horizons=(30,))[0]
    assert frame.iloc[fold.fold.train].transaction_hash.tolist() == fold.history.transaction_hash.tolist() == ["t0"]


@pytest.mark.parametrize(("target", "column"), [("outcome", "outcome"), ("next_duration", "next_duration_class")])
def test_ec5_ec6_each_target_reads_its_own_column_and_365_day_maturity(target, column):
    frame = panel([ORIGIN - 400 * DAY, ORIGIN - 30 * DAY, ORIGIN + DAY], **{column: ["a", "b", "c"]})
    fold = en.entity_folds(frame, en.node_members(frame), target, origins=pd.Series({"o": ORIGIN}), horizons=(30,))[0]
    assert fold.history.transaction_hash.tolist() == frame.iloc[fold.fold.train].transaction_hash.tolist() == ["t0"]
    assert fold.history.attrs["follow_up_days"] == 365 and fold.history.attrs["label"] == column
    with pytest.raises(ValueError, match="unknown target"):
        en.entity_folds(frame, en.node_members(frame), "next_duration_class", origins=pd.Series({"o": ORIGIN}))


def test_ec10_a_fit_cannot_be_stamped_before_its_own_cut_nor_carry_a_false_cut():
    frame = panel([ORIGIN + DAY, ORIGIN + 2 * DAY])
    later = cut_history(frame, ORIGIN + 20 * DAY)
    fit = sh.shrink(later, "renewed", family="beta-binomial")
    assert fit.as_of == str(ORIGIN + 20 * DAY) and fit.support["pooled"]["rows"] == 2
    with pytest.raises(ValueError, match="cannot be stamped earlier"):
        en.effects(fit, ORIGIN)
    assert en.effects(fit, ORIGIN + 20 * DAY).as_of == ORIGIN + 20 * DAY
    forged = later.copy()
    forged.attrs["as_of"] = str(ORIGIN)
    with pytest.raises(ValueError, match="not observable before"):
        sh.shrink(forged, "renewed", family="beta-binomial")
    uncut = sh.shrink(pd.DataFrame({"entity_id": ["A", "B"], "renewed": [0.0, 1.0]}), "renewed", family="beta-binomial")
    with pytest.raises(ValueError, match="no as-of cut"):
        en.effects(uncut, ORIGIN)


def strata_history(values, effect, strata=("cold", "warm"), per=None):
    per = per or len(values)
    rows = [{"transaction_hash": f"{s}{i}", "entity_id": s.upper(), "end_time": ORIGIN - 20 * DAY, "stratum": s, effect: v}
            for s in strata for i, v in enumerate(values[:per])]
    history = pd.DataFrame(rows)
    history.attrs.update(as_of=str(ORIGIN), follow_up_days=7, label=effect)
    return history


def test_ec11_constant_normal_data_give_finite_output_at_the_constant_with_diagnostics():
    fit = sh.shrink(strata_history([0.4, 0.4], "x", strata=("a", "b", "c")), "x", family="normal")
    values = np.r_[fit.rows[["estimate", "sd"]].to_numpy().ravel(), fit.prior[["estimate", "sd"]].to_numpy().ravel()]
    assert np.isfinite(values).all() and fit.prior.estimate.item() == pytest.approx(0.4)
    assert fit.diagnostics["pooled"]["converged"] and set(fit.diagnostics["pooled"]["at_bound"]) <= {"tau", "sigma"}
    single = sh.shrink(strata_history([0.1, 0.5], "x", per=1), "x", family="normal")
    assert single.diagnostics["pooled"]["identified"] is False


def test_ec11_a_stratum_too_small_to_fit_takes_the_pooled_prior_and_says_so():
    history = strata_history([1.0, 0.0], "renewed", strata=("cold", "warm", "warm2"))
    history.loc[history.stratum == "warm2", "stratum"] = "warm"
    fit = sh.shrink(history, "renewed", family="beta-binomial", by="stratum")
    assert fit.rows.set_index("entity_id").prior_id.to_dict() == {"COLD": "pooled", "WARM": "stratum=warm", "WARM2": "stratum=warm"}
    assert "too few entities" in fit.support["stratum=cold"]["prior"]


def test_ec12_every_stratum_and_an_unseen_entity_share_one_category_vocabulary():
    history = strata_history(["short", "short"], "kind", strata=("a", "b"))
    history = pd.concat([history, strata_history(["long", "long"], "kind", strata=("c", "d"))], ignore_index=True)
    history.attrs.update(as_of=str(ORIGIN), follow_up_days=7, label="kind")
    history["stratum"] = history.entity_id.map({"A": "one", "B": "one", "C": "two", "D": "two"})
    fit = sh.shrink(history, "kind", family="dirichlet-multinomial", by="stratum")
    table = en.effects(fit, ORIGIN)
    vocabulary = {"kind=long", "kind=short"}
    assert set(table.at(["A"], ORIGIN).effect_id) == set(table.at(["NEW"], ORIGIN).effect_id) == vocabulary
    assert np.isfinite(fit.rows.estimate).all() and fit.categories == ("long", "short")
    with pytest.raises(ValueError, match="outside the declared vocabulary"):
        sh.shrink(history, "kind", family="dirichlet-multinomial", categories=("short",))
    wider = sh.shrink(history, "kind", family="dirichlet-multinomial", categories=("long", "medium", "short"))
    assert set(wider.prior.effect_id) == {"kind=long", "kind=medium", "kind=short"}


def test_ec13_an_entity_with_no_stratum_keeps_its_support_through_the_pooled_prior():
    history = strata_history([0.0, 1.0], "renewed", strata=("a", "b", "c"))
    history.loc[history.entity_id == "A", "stratum"] = None
    history["stratum"] = history.stratum.where(history.entity_id == "A", "known")
    fit = sh.shrink(history, "renewed", family="beta-binomial", by="stratum")
    assert set(fit.rows.entity_id) == {"A", "B", "C"}
    assert fit.rows.set_index("entity_id").loc["A", "prior_id"] == "pooled" and fit.support["unknown"]["entities"] == 1


def test_ec14_a_history_with_no_known_label_is_refused_by_name():
    history = strata_history([np.nan, np.nan], "x")
    with pytest.raises(ValueError, match="no decisions with a known 'x'"):
        sh.shrink(history, "x", family="normal")


def test_ev1_the_calendar_separates_publication_from_effect_and_refuses_unsourced_rows_for_a_forecast():
    from avalanche_research.behaviour import rules

    table = rules.calendar()
    assert {"available_at", "availability"} <= set(table.columns)
    assert set(table.loc[table.kind == "activation", "availability"]) == {"unsourced"}
    with pytest.raises(ValueError, match="no sourced publication time"):
        rules.calendar(ORIGIN)
    past = rules.calendar(ORIGIN, retrospective=True)
    assert past.event_time.lt(ORIGIN).all() and len(past) < len(table)


# Data science's rereview of 8b24529: F2 cut-guard witnesses, F3 latest missing stratum, F4 fold support.
def test_f2_a_cut_without_its_row_clock_or_follow_up_is_refused():
    history = cut_history(panel([ORIGIN - 30 * DAY, ORIGIN - 20 * DAY]))
    for broken in (history.drop(columns="end_time"), history.copy()):
        if "end_time" in broken:
            broken.attrs = {k: v for k, v in history.attrs.items() if k != "follow_up_days"}
        with pytest.raises(ValueError, match="must carry end_time"):
            sh.shrink(broken, "renewed", family="beta-binomial")


def test_f2_a_history_cut_for_a_short_label_cannot_fit_a_longer_target():
    frame = panel([ORIGIN - 30 * DAY, ORIGIN - 20 * DAY], next_duration_class=["short", "long"], unregistered=[0.1, 0.2])
    seven_day = cut_history(frame)
    with pytest.raises(ValueError, match="needs its own history"):
        sh.shrink(seven_day, "next_duration_class", family="dirichlet-multinomial")
    with pytest.raises(ValueError, match="needs its own history"):
        sh.shrink(seven_day, "unregistered", family="normal")
    year = cut_history(panel([ORIGIN - 400 * DAY, ORIGIN - 380 * DAY], next_duration_class=["short", "long"]),
                       label="next_duration_class", follow_up_days=365)
    assert sh.shrink(year, "next_duration_class", family="dirichlet-multinomial").as_of == str(ORIGIN)


def test_f3_a_missing_latest_stratum_takes_the_unknown_path():
    history = strata_history([0.0, 1.0], "renewed", strata=("a", "b", "c"))
    history["stratum"] = "known"
    history["end_time"] = ORIGIN - 30 * DAY
    later = history[history.entity_id == "A"].head(1).assign(end_time=ORIGIN - 20 * DAY, stratum=None, transaction_hash="late")
    history = pd.concat([history, later], ignore_index=True)
    history.attrs.update(as_of=str(ORIGIN), follow_up_days=7, label="renewed")
    fit = sh.shrink(history, "renewed", family="beta-binomial", by="stratum")
    assert fit.rows.set_index("entity_id").loc["A", "prior_id"] == "pooled" and fit.support["unknown"]["entities"] == 1


def test_f4_each_fold_names_the_training_rows_its_history_leaves_out():
    frame = panel([ORIGIN - 30 * DAY, ORIGIN - 20 * DAY, ORIGIN - 15 * DAY, ORIGIN + DAY])
    frame.loc[1, "renewed"] = np.nan
    frame.loc[2, "node_id"] = "UNMAPPED"
    members = en.node_members(frame[frame.node_id == "A"])
    fold = en.entity_folds(frame, members, origins=pd.Series({"o": ORIGIN}), horizons=(30,))[0]
    assert fold.support["train_rows"] == 3 and fold.support["history_rows"] == 1
    assert fold.support["unlabelled"] == ["t1"] and fold.support["unmapped"] == ["t2"]
