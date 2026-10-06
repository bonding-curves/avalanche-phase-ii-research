"""``EF3``: each entity's effect shrunk toward a prior estimated from all entities, by empirical Bayes.

Families, one per kind of decision:

| ``family`` | Effect | Model |
| --- | --- | --- |
| ``beta-binomial`` | A binary label, such as ``renewed`` | Each entity's rate is Beta(a, b); a and b maximize the beta-binomial marginal likelihood |
| ``dirichlet-multinomial`` | A class, such as the next duration class | Each entity's shares are Dirichlet(alpha); alpha maximizes the Dirichlet-multinomial marginal likelihood |
| ``normal`` | A value on a log scale, such as ``stake_change_log`` | Values are Normal(theta, sigma); each theta is Normal(mu, tau); mu, tau and sigma maximize the marginal likelihood |

``prior="pooled"`` fits one prior over every entity. ``by=<column>`` fits one per stratum, each entity in the stratum of its
latest decision, and an unseen entity takes the pooled prior. A type-mixture prior waits for the type model (``ML6``).
With no decisions an entity's estimate is the prior; with many it approaches its own raw rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import optimize, special

FAMILIES = ("beta-binomial", "dirichlet-multinomial", "normal")


@dataclass(frozen=True)
class EffectFit:
    family: str
    effect: str
    rows: pd.DataFrame
    prior: pd.DataFrame
    hyperparameters: dict = field(default_factory=dict)


def _beta_binomial(k: np.ndarray, n: np.ndarray) -> tuple[float, float]:
    def loss(params):
        a, b = np.exp(params)
        return -np.sum(special.betaln(k + a, n - k + b) - special.betaln(a, b))
    mean = k.sum() / max(n.sum(), 1)
    start = np.log([max(mean, 1e-3) * 10, max(1 - mean, 1e-3) * 10])
    result = optimize.minimize(loss, start, method="Nelder-Mead", options={"xatol": 1e-8, "fatol": 1e-10, "maxiter": 4000})
    a, b = np.exp(result.x)
    return float(a), float(b)


def _dirichlet_multinomial(counts: np.ndarray) -> np.ndarray:
    n = counts.sum(1)

    def loss(params):
        alpha = np.exp(params)
        total = alpha.sum()
        return -np.sum(special.gammaln(total) - special.gammaln(n + total)
                       + np.sum(special.gammaln(counts + alpha) - special.gammaln(alpha), axis=1))
    shares = (counts.sum(0) + 0.5) / (counts.sum() + 0.5 * counts.shape[1])
    result = optimize.minimize(loss, np.log(shares * 5), method="L-BFGS-B")
    return np.exp(result.x)


def _normal(groups: list[np.ndarray]) -> tuple[float, float, float]:
    n = np.array([len(g) for g in groups], dtype=float)
    mean = np.array([g.mean() for g in groups])
    within = np.array([((g - g.mean()) ** 2).sum() for g in groups])

    def loss(params):
        mu, log_tau, log_sigma = params
        tau2, sigma2 = np.exp(2 * log_tau), np.exp(2 * log_sigma)
        between = tau2 + sigma2 / n
        return -np.sum(-0.5 * (n - 1) * np.log(2 * np.pi * sigma2) - within / (2 * sigma2) - 0.5 * np.log(n)
                       - 0.5 * np.log(2 * np.pi * between) - (mean - mu) ** 2 / (2 * between))
    pooled = np.concatenate(groups)
    start = [pooled.mean(), np.log(max(mean.std(), 1e-3)), np.log(max(pooled.std(), 1e-3))]
    result = optimize.minimize(loss, start, method="Nelder-Mead", options={"xatol": 1e-9, "fatol": 1e-10, "maxiter": 6000})
    mu, log_tau, log_sigma = result.x
    return float(mu), float(np.exp(log_tau)), float(np.exp(log_sigma))


def _fit(history: pd.DataFrame, effect: str, family: str, prior_id: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    grouped = history.groupby("entity_id", sort=True)[effect]
    if family == "beta-binomial":
        k, n = grouped.sum().astype(float), grouped.count().astype(float)
        a, b = _beta_binomial(k.to_numpy(), n.to_numpy())
        post_a, post_b = a + k, b + n - k
        rows = pd.DataFrame({"entity_id": k.index.to_numpy(), "effect_id": effect,
                             "estimate": (post_a / (post_a + post_b)).to_numpy(),
                             "sd": np.sqrt(post_a * post_b / ((post_a + post_b) ** 2 * (post_a + post_b + 1))).to_numpy(),
                             "n": n.astype(int).to_numpy()})
        prior = pd.DataFrame({"effect_id": [effect], "estimate": [a / (a + b)],
                              "sd": [np.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))], "n": [0]})
        hyper = {"a": a, "b": b}
    elif family == "dirichlet-multinomial":
        counts = pd.crosstab(history.entity_id, history[effect]).sort_index()
        alpha = _dirichlet_multinomial(counts.to_numpy(dtype=float))
        post = counts.to_numpy(dtype=float) + alpha
        share = post / post.sum(1, keepdims=True)
        sd = np.sqrt(share * (1 - share) / (post.sum(1, keepdims=True) + 1))
        frames = [pd.DataFrame({"entity_id": counts.index.to_numpy(), "effect_id": f"{effect}={category}", "estimate": share[:, i],
                                "sd": sd[:, i], "n": counts.sum(1).to_numpy()}) for i, category in enumerate(counts.columns)]
        rows = pd.concat(frames, ignore_index=True)
        prior_share = alpha / alpha.sum()
        prior = pd.DataFrame({"effect_id": [f"{effect}={c}" for c in counts.columns], "estimate": prior_share,
                              "sd": np.sqrt(prior_share * (1 - prior_share) / (alpha.sum() + 1)), "n": 0})
        hyper = {"alpha": dict(zip(map(str, counts.columns), alpha.tolist()))}
    elif family == "normal":
        values = history[["entity_id", effect]].dropna()
        groups = [g.to_numpy(dtype=float) for _, g in values.groupby("entity_id", sort=True)[effect]]
        ids = sorted(values.entity_id.unique())
        mu, tau, sigma = _normal(groups)
        n = np.array([len(g) for g in groups], dtype=float)
        mean = np.array([g.mean() for g in groups])
        weight = tau ** 2 / (tau ** 2 + sigma ** 2 / n)
        rows = pd.DataFrame({"entity_id": ids, "effect_id": effect, "estimate": mu + weight * (mean - mu),
                             "sd": np.sqrt(1 / (1 / tau ** 2 + n / sigma ** 2)), "n": n.astype(int)})
        prior = pd.DataFrame({"effect_id": [effect], "estimate": [mu], "sd": [tau], "n": [0]})
        hyper = {"mu": mu, "tau": tau, "sigma": sigma}
    else:
        raise ValueError(f"family must be one of {FAMILIES}")
    return rows.assign(prior_id=prior_id), prior.assign(prior_id=prior_id), hyper


def shrink(history: pd.DataFrame, effect: str, *, family: str, prior: str = "pooled", by: str | None = None) -> EffectFit:
    """Shrunk effects of every entity in ``history`` (``entities.entity_history``), with the prior an unseen entity takes."""
    if prior == "mixture":
        raise NotImplementedError("the type-mixture prior lands with the type model (ML6)")
    if prior != "pooled":
        raise ValueError("prior must be 'pooled' or 'mixture'")
    if effect not in history or history.empty:
        raise ValueError(f"history has no decisions with {effect!r}")
    history = history.loc[history[effect].notna()]
    pooled_rows, pooled_prior, pooled_hyper = _fit(history, effect, family, "pooled")
    if by is None:
        return EffectFit(family, effect, pooled_rows, pooled_prior, {"pooled": pooled_hyper})
    stratum = history.sort_values("end_time").groupby("entity_id")[by].last()
    rows, hyper = [], {"pooled": pooled_hyper}
    for value, entities in stratum.groupby(stratum):
        part = history.loc[history.entity_id.isin(entities.index)]
        part_rows, _, part_hyper = _fit(part, effect, family, f"{by}={value}")
        rows.append(part_rows)
        hyper[f"{by}={value}"] = part_hyper
    return EffectFit(family, effect, pd.concat(rows, ignore_index=True), pooled_prior, hyper)
