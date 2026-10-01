"""Unsupervised learning on node lifetimes: scale, embed, cluster, test stability, and describe.

The validator population may be a continuum rather than a set of natural types, as the predecessor's work found, so
every clustering here comes with the evidence to judge it: an information criterion over the number of groups, the
agreement of the grouping with itself on resampled data, and the groups' profiles in plain units. A grouping that is
not stable under resampling is reported as such and is not a validator type.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import HDBSCAN, AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import QuantileTransformer, StandardScaler

SEED = 20261001


def preprocessor(n_rows: int, method: str = "quantile") -> Pipeline:
    """Median imputation, then a rank-based map to a normal shape, which tames heavy tails without choosing a log."""
    if method == "quantile":
        scale = QuantileTransformer(output_distribution="normal", n_quantiles=min(1000, n_rows), random_state=SEED)
    elif method == "standard":
        scale = StandardScaler()
    else:
        raise ValueError(f"unknown scaling {method!r}")
    return Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", scale)]).set_output(transform="pandas")


def matrix(lifetimes: pd.DataFrame, columns, method: str = "quantile") -> pd.DataFrame:
    return preprocessor(len(lifetimes), method).fit_transform(lifetimes[list(columns)])


@dataclass
class Embedding:
    coordinates: pd.DataFrame
    explained: pd.Series
    loadings: pd.DataFrame


def embed(x: pd.DataFrame, components: int = 5) -> Embedding:
    pca = PCA(n_components=components, random_state=SEED).fit(x)
    names = [f"PC{i + 1}" for i in range(components)]
    coordinates = pd.DataFrame(pca.transform(x), index=x.index, columns=names)
    return Embedding(coordinates, pd.Series(pca.explained_variance_ratio_, index=names),
                     pd.DataFrame(pca.components_.T, index=x.columns, columns=names))


def gmm_scan(x: pd.DataFrame, ks=range(1, 11), covariance: str = "full") -> pd.DataFrame:
    """Bayesian information criterion of a Gaussian mixture for each number of groups. Lower is better."""
    rows = []
    for k in ks:
        model = GaussianMixture(k, covariance_type=covariance, n_init=3, random_state=SEED).fit(x)
        rows.append({"k": k, "bic": model.bic(x), "aic": model.aic(x)})
    table = pd.DataFrame(rows)
    table["delta_bic"] = table.bic - table.bic.min()
    return table


def estimator(method: str, k: int | None = None, min_cluster_size: int = 50):
    if method == "kmeans":
        return KMeans(k, n_init=10, random_state=SEED)
    if method == "gmm":
        return GaussianMixture(k, covariance_type="full", n_init=3, random_state=SEED)
    if method == "ward":
        return AgglomerativeClustering(k, linkage="ward")
    if method == "hdbscan":
        return HDBSCAN(min_cluster_size=min_cluster_size, min_samples=10, copy=True)
    raise ValueError(f"unknown method {method!r}")


def fit_labels(x: pd.DataFrame, method: str, k: int | None = None, **options) -> pd.Series:
    model = estimator(method, k, **options)
    labels = model.fit_predict(x)
    return pd.Series(labels, index=x.index, name=f"{method}{k or ''}")


def scores(x: pd.DataFrame, labels: pd.Series, sample: int = 5000) -> dict[str, float]:
    keep = labels.ge(0)
    if labels[keep].nunique() < 2:
        return {"silhouette": float("nan"), "noise_share": float((~keep).mean())}
    return {"silhouette": float(silhouette_score(x[keep], labels[keep], sample_size=min(sample, int(keep.sum())),
                                                 random_state=SEED)),
            "noise_share": float((~keep).mean())}


def stability(x: pd.DataFrame, method: str, k: int | None = None, rounds: int = 20, fraction: float = 0.8,
              **options) -> pd.Series:
    """Adjusted Rand agreement between the full-data labels and labels refitted on random subsamples.

    1 means the same grouping every time. Values near 0 mean the grouping is an artefact of the sample.
    """
    reference = fit_labels(x, method, k, **options)
    rng = np.random.default_rng(SEED)
    agreement = []
    for _ in range(rounds):
        rows = rng.choice(len(x), size=int(fraction * len(x)), replace=False)
        sub = x.iloc[np.sort(rows)]
        labels = fit_labels(sub, method, k, **options)
        agreement.append(adjusted_rand_score(reference.loc[sub.index], labels))
    return pd.Series(agreement, name=f"{method}{k or ''}")


def compare(x: pd.DataFrame, methods: dict[str, dict], rounds: int = 10) -> pd.DataFrame:
    """One row per configuration: size of the largest group, internal score, and resampling stability."""
    rows = []
    for name, config in methods.items():
        labels = fit_labels(x, **config)
        stab = stability(x, rounds=rounds, **config)
        rows.append({"configuration": name, "groups": int(labels[labels.ge(0)].nunique()),
                     "largest_group_share": float(labels.value_counts(normalize=True).max()),
                     **scores(x, labels), "stability_mean": float(stab.mean()), "stability_min": float(stab.min())})
    return pd.DataFrame(rows).set_index("configuration")


def profile(lifetimes: pd.DataFrame, labels: pd.Series, columns) -> pd.DataFrame:
    """Median of each column by group, with group size and its share of stake-days, in the columns' own units."""
    frame = lifetimes.assign(group=labels)
    table = frame.groupby("group")[list(columns)].median()
    table.insert(0, "nodes", frame.groupby("group").size())
    table.insert(1, "stake_days_share", frame.groupby("group").stake_avax_days.sum() / frame.stake_avax_days.sum())
    return table


def null_sample(x: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """Data with the same marginals and correlations as ``x`` but one Gaussian blob, so no groups by construction.

    After the quantile map every column is standard normal, so a multivariate normal with the observed covariance
    keeps both. A score that the real data does not beat on this sample is not evidence of groups.
    """
    rng = np.random.default_rng(seed)
    draw = rng.multivariate_normal(x.mean().to_numpy(), np.cov(x.to_numpy(), rowvar=False), size=len(x))
    return pd.DataFrame(draw, index=x.index, columns=x.columns)


def against_null(x: pd.DataFrame, method: str, ks=range(2, 9), replicates: int = 5) -> pd.DataFrame:
    """Silhouette of the real data and of null samples for each number of groups."""
    rows = []
    for k in ks:
        real = scores(x, fit_labels(x, method, k))["silhouette"]
        null = [scores(n, fit_labels(n, method, k))["silhouette"]
                for n in (null_sample(x, SEED + r) for r in range(replicates))]
        rows.append({"k": k, "silhouette": real, "null_mean": float(np.mean(null)), "null_max": float(np.max(null))})
    table = pd.DataFrame(rows)
    table["beats_null"] = table.silhouette > table.null_max
    return table


def outliers(x: pd.DataFrame, contamination: float = 0.01) -> pd.Series:
    """Isolation-forest anomaly score: higher is more unusual. The top ``contamination`` share is flagged."""
    model = IsolationForest(contamination=contamination, random_state=SEED).fit(x)
    return pd.Series(-model.score_samples(x), index=x.index, name="anomaly_score")
