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
