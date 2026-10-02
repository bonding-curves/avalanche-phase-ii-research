"""Supervised learning on decision events: targets, forward-in-time folds, models, scores, and receipts.

Validation moves forward in time. Each fold trains on decisions whose label was already known when the fold starts
and tests on the six months after it, so a model never learns from an outcome it could not have seen. The last fold
ends at the validation lockbox. Every model is compared with two benchmarks: the overall rate (``prior``) and the node's
own record (``history``), which predicts that a node keeps doing what it did before. For the next duration the
benchmark is ``persistence``, the training frequency of each next duration given the current one. A model that does
not beat these has learned nothing a lookup table does not already know.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
import sklearn
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, QuantileTransformer

from ..model.protocol import MAINNET_UPGRADES
from . import features as feature_registry
from .events import duration_class
from .inputs import LOCKBOX_START

SEED = 20261001
DAY = pd.Timedelta(days=1)


@dataclass(frozen=True)
class Target:
    name: str
    column: str
    description: str
    follow_up_days: int
    rows: str = "all"


TARGETS = {
    "renewed": Target("renewed", "renewed", "The node starts its next period within 7 days of this end", 7),
    "outcome": Target("outcome", "outcome", "Renew within 7 days, return within 365, or leave", 365),
    "next_duration": Target("next_duration", "next_duration_class",
                            "Duration class of the next period, when the node stakes again within 365 days", 365,
                            rows="next"),
}


def dataset(events: pd.DataFrame, features: pd.DataFrame, target: str, columns=None):
    """X, y and meta for one target, keeping only rows whose label is observed."""
    spec = TARGETS[target]
    columns = list(columns or feature_registry.NAMES)
    y = events[spec.column]
    if target == "outcome":
        keep = y.isin(["renew", "return", "leave"])
        y = y.astype(str)
    elif target == "next_duration":
        keep = events.outcome.isin(["renew", "return"]) & y.notna()
        y = y.astype(str)
    else:
        keep = y.notna()
    meta = events.loc[keep, ["transaction_hash", "node_id", "end_time", "stake_avax", "period_number"]]
    return features.loc[keep, columns], y[keep], meta


@dataclass(frozen=True)
class Fold:
    name: str
    start: pd.Timestamp
    end: pd.Timestamp
    train: np.ndarray
    test: np.ndarray


def forward_folds(meta: pd.DataFrame, target: str, first: str = "2022-11-19 16:00", months: int = 6,
                  observed_through=LOCKBOX_START) -> list[Fold]:
    """Six-month test windows from ``first`` to the lockbox, each trained on labels known by its start."""
    follow = TARGETS[target].follow_up_days * DAY
    cutoff = pd.Timestamp(observed_through)
    folds, start = [], pd.Timestamp(first)
    while start < cutoff:
        end = min(start + pd.DateOffset(months=months), cutoff)
        train = np.flatnonzero((meta.end_time + follow).le(start).to_numpy())
        test = np.flatnonzero((meta.end_time.ge(start) & meta.end_time.lt(end)
                               & (meta.end_time + follow).le(cutoff)).to_numpy())
        if len(test):
            folds.append(Fold(f"{start:%Y-%m}", start, end, train, test))
        start = end
    return folds


UPGRADE_ORIGINS = ("banff", "cortina", "durango", "etna", "fortuna")
HORIZONS = (30, 90, 180)


def protocol_origins(first_quarter: str = "2022-01-01", last_quarter: str = "2025-04-01") -> pd.Series:
    """The validation protocol's origins: the five upgrade activations and every quarter start, in time order."""
    upgrades = {u.name: pd.Timestamp(u.activated_at).tz_localize(None) for u in MAINNET_UPGRADES.upgrades
                if u.name in UPGRADE_ORIGINS}
    quarters = {f"{q:%Y}-Q{(q.month - 1) // 3 + 1}": q for q in pd.date_range(first_quarter, last_quarter, freq="QS")}
    return pd.Series({**upgrades, **quarters}).sort_values()


def protocol_folds(meta: pd.DataFrame, target: str, origins: pd.Series | None = None, horizons=HORIZONS,
                   observed_through=LOCKBOX_START) -> list[Fold]:
    """One fold per origin and horizon: trained on every label known by the origin, tested on the endings in the
    ``horizon`` days after it. A horizon that would reach past ``observed_through`` is left out."""
    follow = TARGETS[target].follow_up_days * DAY
    cutoff = pd.Timestamp(observed_through)
    origins = protocol_origins() if origins is None else origins
    end_time = meta.end_time
    folds = []
    for name, origin in origins.items():
        train = np.flatnonzero((end_time + follow).le(origin).to_numpy())
        for days in horizons:
            stop = origin + days * DAY
            if stop > cutoff:
                continue
            inside = end_time.ge(origin) & end_time.lt(stop) & (end_time + follow).le(cutoff)
            test = np.flatnonzero(inside.to_numpy())
            if len(train) and len(test):
                folds.append(Fold(f"{name}+{days}d", origin, stop, train, test))
    return folds


class NodeHistory(ClassifierMixin, BaseEstimator):
    """The node's own record: its earlier renewal share, shrunk toward the training rate by ``strength`` decisions."""

    def __init__(self, strength: float = 2.0):
        self.strength = strength

    def fit(self, X, y):
        self.classes_ = np.array([0.0, 1.0])
        self.base_ = float(np.mean(y))
        return self

    def predict_proba(self, X):
        earlier = (X["period_number"].to_numpy() - 1).astype(float)
        share = np.nan_to_num(X["prior_renew_share"].to_numpy(), nan=0.0)
        p = (share * earlier + self.strength * self.base_) / (earlier + self.strength)
        return np.column_stack([1 - p, p])

    def predict(self, X):
        return self.classes_[(self.predict_proba(X)[:, 1] >= 0.5).astype(int)]


class TrailingYear(ClassifierMixin, BaseEstimator):
    """v0.7's renewal block: the rate among training labels that ended in the ``days`` before the fold origin."""

    def __init__(self, days: int = 365):
        self.days = days

    def fit(self, X, y, end_time=None, origin=None):
        y = np.asarray(y, dtype=float)
        self.classes_ = np.array([0.0, 1.0])
        recent = np.ones(len(y), dtype=bool)
        if end_time is not None and origin is not None:
            start = pd.Timestamp(origin) - self.days * DAY
            recent = pd.Series(pd.to_datetime(end_time)).ge(start).to_numpy()
        self.rate_ = float(np.mean(y[recent])) if recent.any() else float(np.mean(y))
        return self

    def predict_proba(self, X):
        return np.tile([1 - self.rate_, self.rate_], (len(X), 1))

    def predict(self, X):
        return self.classes_[(self.predict_proba(X)[:, 1] >= 0.5).astype(int)]


def expected_calibration_error(y_true, p, bins: int = 10) -> float:
    """Gap between predicted and observed rates over equal-count bins of ``p``, weighted by bin size."""
    frame = pd.DataFrame({"y": np.asarray(y_true, dtype=float), "p": np.asarray(p, dtype=float)})
    frame["bin"] = pd.qcut(frame.p.rank(method="first"), q=min(bins, len(frame)), labels=False)
    table = frame.groupby("bin").agg(y=("y", "mean"), p=("p", "mean"), n=("y", "size"))
    return float(np.sum(table.n * (table.y - table.p).abs()) / table.n.sum())


class DurationTransition(ClassifierMixin, BaseEstimator):
    """Persistence for duration: the training frequency of each next class given the current period's class."""

    def __init__(self, smoothing: float = 1.0):
        self.smoothing = smoothing

    def fit(self, X, y):
        current = duration_class(X["duration_days"]).astype(str)
        counts = pd.crosstab(current, np.asarray(y)) + self.smoothing
        self.classes_ = np.array(sorted(set(np.asarray(y))))
        self.table_ = counts.reindex(columns=self.classes_, fill_value=self.smoothing)
        self.table_ = self.table_.div(self.table_.sum(axis=1), axis=0)
        self.fallback_ = pd.Series(np.asarray(y)).value_counts(normalize=True).reindex(self.classes_).fillna(0)
        return self

    def predict_proba(self, X):
        current = duration_class(X["duration_days"]).astype(str)
        rows = self.table_.reindex(current.to_numpy())
        rows = rows.fillna(dict(self.fallback_))
        return rows.to_numpy()

    def predict(self, X):
        return self.classes_[self.predict_proba(X).argmax(1)]


def models(binary: bool = True, target: str | None = None) -> dict[str, object]:
    numeric = make_column_selector(dtype_include=np.number)
    categorical = make_column_selector(dtype_include="category")
    linear = Pipeline([
        ("columns", ColumnTransformer([
            # A rank map to a normal shape bounds every value, so a feature that trends over time cannot push a test
            # row fifty standard deviations past the training range, as a plain standard scaler did.
            ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")),
                                  ("scale", QuantileTransformer(output_distribution="normal", random_state=SEED))]),
             numeric),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical)])),
        ("model", LogisticRegression(max_iter=3000, C=1.0))])
    boosted = HistGradientBoostingClassifier(learning_rate=0.05, max_iter=400, max_leaf_nodes=31,
                                             l2_regularization=1.0, categorical_features="from_dtype",
                                             early_stopping=True, validation_fraction=0.15, random_state=SEED)
    chosen = {"prior": DummyClassifier(strategy="prior")}
    if binary:
        chosen["trailing_year"] = TrailingYear()
        chosen["history"] = NodeHistory()
    if target == "next_duration":
        chosen["persistence"] = DurationTransition()
    chosen.update({"logistic": linear, "boosted": boosted})
    return chosen


def _scores(y_true, proba, classes) -> dict[str, float]:
    labels = list(classes)
    out = {"log_loss": log_loss(y_true, proba, labels=labels),
           "accuracy": accuracy_score(y_true, np.asarray(labels)[proba.argmax(1)])}
    onehot = (np.asarray(y_true)[:, None] == np.asarray(labels)[None, :]).astype(float)
    out["brier"] = float(np.mean(np.sum((proba - onehot) ** 2, axis=1)))
    if len(labels) == 2:
        out["roc_auc"] = roc_auc_score(onehot[:, 1], proba[:, 1]) if onehot[:, 1].std() > 0 else float("nan")
        # The minority class, not renewing, is the one worth ranking, so precision is measured for it.
        out["average_precision_not_renewed"] = average_precision_score(onehot[:, 0], proba[:, 0])
        out["ece"] = expected_calibration_error(onehot[:, 1], proba[:, 1])
    else:
        present = onehot.sum(0) > 0
        out["roc_auc"] = roc_auc_score(onehot[:, present], proba[:, present], average="macro") if present.sum() > 1 \
            else float("nan")
    return out


def _latest_held_out(X: pd.DataFrame, y: pd.Series, end_time: pd.Series, fraction: float):
    """Early stopping on the latest ``fraction`` of the training window in time, not a random sample of it."""
    order = np.argsort(end_time.to_numpy(), kind="stable")
    cut = len(order) - max(1, int(round(len(order) * fraction)))
    fit, held = order[:cut], order[cut:]
    return X.iloc[fit], y.iloc[fit], {"X_val": X.iloc[held], "y_val": y.iloc[held]}


def evaluate(X: pd.DataFrame, y: pd.Series, meta: pd.DataFrame, folds: list[Fold], candidates: dict[str, object]):
    """Fit every candidate on every fold. Returns per-fold scores and the test predictions."""
    from sklearn.base import clone
    rows, predictions = [], []
    for fold in folds:
        Xtr, ytr, Xte, yte = X.iloc[fold.train], y.iloc[fold.train], X.iloc[fold.test], y.iloc[fold.test]
        for name, candidate in candidates.items():
            fit_X, fit_y, extra = Xtr, ytr, {}
            if isinstance(candidate, TrailingYear):
                extra = {"end_time": meta.end_time.iloc[fold.train].to_numpy(), "origin": fold.start}
            elif isinstance(candidate, HistGradientBoostingClassifier) and candidate.early_stopping:
                fit_X, fit_y, extra = _latest_held_out(Xtr, ytr, meta.end_time.iloc[fold.train],
                                                       candidate.validation_fraction)
            model = clone(candidate).fit(fit_X, fit_y, **extra)
            proba = model.predict_proba(Xte)
            classes = list(model.classes_)
            rows.append({"fold": fold.name, "model": name, "train": len(fold.train), "test": len(fold.test),
                         **_scores(yte.to_numpy(), proba, classes)})
            frame = pd.DataFrame(proba, columns=[f"p_{c}" for c in classes], index=Xte.index)
            # Per-row loss, so a paired test against a benchmark can resample rows by operator and origin.
            truth = np.searchsorted(np.asarray(classes), yte.to_numpy())
            frame["log_loss"] = -np.log(np.clip(proba[np.arange(len(proba)), truth], 1e-15, 1))
            predictions.append(frame.assign(fold=fold.name, model=name, y=yte.to_numpy(),
                                            end_time=meta.end_time.iloc[fold.test].to_numpy()))
    scores = pd.DataFrame(rows)
    prior = scores.loc[scores.model.eq("prior")].set_index("fold").log_loss
    scores["skill_vs_prior"] = 1 - scores.log_loss / scores.fold.map(prior)
    return scores, pd.concat(predictions)


@dataclass
class Run:
    target: str
    X: pd.DataFrame
    y: pd.Series
    meta: pd.DataFrame
    folds: list[Fold]
    scores: pd.DataFrame
    predictions: pd.DataFrame


def run(events: pd.DataFrame, features: pd.DataFrame, target: str, keep: pd.Series | None = None, columns=None,
        scheme: str = "protocol") -> Run:
    """One target end to end: the rows whose label is observed, optionally only those ``keep`` marks, every model,
    every fold of ``scheme``: the protocol's origins and horizons, or the v0 ``six_month`` windows."""
    X, y, meta = dataset(events, features, target, columns)
    if keep is not None:
        mask = keep.loc[X.index].to_numpy(dtype=bool)
        X, y, meta = X[mask], y[mask], meta[mask]
    folds = protocol_folds(meta, target) if scheme == "protocol" else forward_folds(meta, target)
    scores, predictions = evaluate(X, y, meta, folds, models(binary=target == "renewed", target=target))
    return Run(target, X, y, meta, folds, scores, predictions)


def summarise(scores: pd.DataFrame) -> pd.DataFrame:
    """Mean of each score over folds, weighted by test size, with the last fold before the lockbox beside it."""
    numeric = [c for c in ("log_loss", "brier", "roc_auc", "average_precision_not_renewed", "ece", "accuracy",
                           "skill_vs_prior") if c in scores]
    weighted = scores.groupby("model").apply(
        lambda g: pd.Series({c: np.average(g[c], weights=g.test) for c in numeric}), include_groups=False)
    last = scores.loc[scores.fold.eq(scores.fold.max())].set_index("model")[numeric].add_prefix("last_fold_")
    return weighted.join(last).sort_values("log_loss")


def calibration(predictions: pd.DataFrame, model: str, positive: str = "p_1.0", bins: int = 10) -> pd.DataFrame:
    p = predictions.loc[predictions.model.eq(model)]
    edges = np.linspace(0, 1, bins + 1)
    bucket = pd.cut(p[positive], edges, include_lowest=True)
    table = p.groupby(bucket, observed=True).agg(predicted=(positive, "mean"), observed=("y", "mean"),
                                                 decisions=("y", "size"))
    return table.reset_index(drop=True)


def importance(model, X: pd.DataFrame, y: pd.Series, repeats: int = 5, sample: int = 6000) -> pd.DataFrame:
    """Permutation importance on held-out rows, as the rise in log loss when one feature is shuffled."""
    if len(X) > sample:
        keep = X.sample(sample, random_state=SEED).index
        X, y = X.loc[keep], y.loc[keep]
    result = permutation_importance(model, X, y, scoring="neg_log_loss", n_repeats=repeats, random_state=SEED)
    family = {f.name: f.family for f in feature_registry.REGISTRY}
    return (pd.DataFrame({"feature": X.columns, "family": [family.get(c, "") for c in X.columns],
                          "importance": result.importances_mean, "spread": result.importances_std})
            .sort_values("importance", ascending=False).reset_index(drop=True))


def fit_on(model, X: pd.DataFrame, y: pd.Series, rows: np.ndarray):
    from sklearn.base import clone
    return clone(model).fit(X.iloc[rows], y.iloc[rows])


def receipt(inputs_receipt: dict, target: str, columns, folds: list[Fold], summary: pd.DataFrame) -> dict:
    columns = list(columns)
    return {
        "target": target, "target_definition": TARGETS[target].description,
        "data_kind": "observed", "claim": "exploratory, v0, unreviewed",
        "inputs": inputs_receipt,
        "features": columns,
        "features_sha256": hashlib.sha256(json.dumps(columns).encode()).hexdigest(),
        "folds": [{"name": f.name, "start": str(f.start), "end": str(f.end), "train": len(f.train),
                   "test": len(f.test)} for f in folds],
        "scores": json.loads(summary.round(6).to_json(orient="index")),
        "sklearn": sklearn.__version__, "seed": SEED,
    }
