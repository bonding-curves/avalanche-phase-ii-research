"""``EF3``: each entity's effect shrunk toward a prior estimated from all entities, by empirical Bayes.

Families, one per kind of decision:

| ``family`` | Effect | Model |
| --- | --- | --- |
| ``beta-binomial`` | A binary label, such as ``renewed`` | Each entity's rate is Beta(a, b); a and b maximize the beta-binomial marginal likelihood |
| ``dirichlet-multinomial`` | A class, such as the next duration class | Each entity's shares are Dirichlet(alpha); alpha maximizes the Dirichlet-multinomial marginal likelihood |
| ``normal`` | A value on a log scale, such as ``stake_change_log`` | Values are Normal(theta, sigma); each theta is Normal(mu, tau); mu, tau and sigma maximize the marginal likelihood |

``prior="pooled"`` fits one prior over every entity. ``by=<column>`` fits one per stratum, each entity in the stratum of its
latest decision. Two cases take the pooled prior instead, each named in ``prior_id`` and counted in ``support``: an
entity whose latest stratum is missing (``unknown``), and a stratum with fewer than ``MIN_STRATUM_ENTITIES`` entities,
whose prior cannot be estimated. A type-mixture prior waits for the type model (``ML6``).

Every fit carries where its data came from. ``as_of`` is the cut of the history it was fitted on, read from
``entities.entity_history`` and checked against the rows: a decision whose end plus follow-up is not before the cut is
refused. ``entities.effects`` refuses to stamp a table earlier than that cut. ``support`` counts the
rows and entities used, with a hash of their decision IDs. ``diagnostics`` reports, per prior, whether the optimizer
converged, which parameters sit at a bound, and whether the variance split is identified.

A Dirichlet fit uses one declared category vocabulary, by default every category in the history, in every stratum and
for an unseen entity. Parameters are bounded, so constant data give finite output: a bound reached is reported, not hidden.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import optimize, special

FAMILIES = ("beta-binomial", "dirichlet-multinomial", "normal")
MIN_STRATUM_ENTITIES = 2
LOG_BOUND = (np.log(1e-4), np.log(1e4))  # a, b and every alpha
SCALE_FLOOR = 1e-6  # tau and sigma, relative to the data's spread (or 1 when the data are constant)


@dataclass(frozen=True)
class EffectFit:
    family: str
    effect: str
    rows: pd.DataFrame
    prior: pd.DataFrame
    hyperparameters: dict = field(default_factory=dict)
    as_of: str | None = None
    support: dict = field(default_factory=dict)
    diagnostics: dict = field(default_factory=dict)
    categories: tuple = ()


def _at_bound(values, bounds, names) -> list[str]:
    return [name for name, value, (low, high) in zip(names, values, bounds) if np.isclose(value, low) or np.isclose(value, high)]


def _beta_binomial(k: np.ndarray, n: np.ndarray) -> tuple[float, float, dict]:
    def loss(params):
        a, b = np.exp(params)
        return -np.sum(special.betaln(k + a, n - k + b) - special.betaln(a, b))
    mean = k.sum() / max(n.sum(), 1)
    start = np.clip(np.log([max(mean, 1e-3) * 10, max(1 - mean, 1e-3) * 10]), *LOG_BOUND)
    bounds = [LOG_BOUND, LOG_BOUND]
    result = optimize.minimize(loss, start, method="L-BFGS-B", bounds=bounds)
    a, b = np.exp(result.x)
    return float(a), float(b), {"converged": bool(result.success), "at_bound": _at_bound(result.x, bounds, ["a", "b"]),
                                "identified": len(k) >= 2}


def _dirichlet_multinomial(counts: np.ndarray) -> tuple[np.ndarray, dict]:
    n = counts.sum(1)

    def loss(params):
        alpha = np.exp(params)
        total = alpha.sum()
        return -np.sum(special.gammaln(total) - special.gammaln(n + total)
                       + np.sum(special.gammaln(counts + alpha) - special.gammaln(alpha), axis=1))
    shares = (counts.sum(0) + 0.5) / (counts.sum() + 0.5 * counts.shape[1])
    bounds = [LOG_BOUND] * counts.shape[1]
    result = optimize.minimize(loss, np.clip(np.log(shares * 5), *LOG_BOUND), method="L-BFGS-B", bounds=bounds)
    return np.exp(result.x), {"converged": bool(result.success),
                              "at_bound": _at_bound(result.x, bounds, [f"alpha[{i}]" for i in range(counts.shape[1])]),
                              "identified": counts.shape[0] >= 2}


def _normal(groups: list[np.ndarray]) -> tuple[float, float, float, dict]:
    n = np.array([len(g) for g in groups], dtype=float)
    mean = np.array([g.mean() for g in groups])
    within = np.array([((g - g.mean()) ** 2).sum() for g in groups])
    pooled = np.concatenate(groups)
    spread = float(pooled.std()) or 1.0
    floor = np.log(SCALE_FLOOR * spread)
    ceiling = np.log(1e3 * spread)

    def loss(params):
        mu, log_tau, log_sigma = params
        tau2, sigma2 = np.exp(2 * log_tau), np.exp(2 * log_sigma)
        between = tau2 + sigma2 / n
        return -np.sum(-0.5 * (n - 1) * np.log(2 * np.pi * sigma2) - within / (2 * sigma2) - 0.5 * np.log(n)
                       - 0.5 * np.log(2 * np.pi * between) - (mean - mu) ** 2 / (2 * between))
    start = [pooled.mean(), np.clip(np.log(max(mean.std(), 1e-3 * spread)), floor, ceiling),
             np.clip(np.log(max(pooled.std(), 1e-3 * spread)), floor, ceiling)]
    bounds = [(pooled.min() - spread, pooled.max() + spread), (floor, ceiling), (floor, ceiling)]
    result = optimize.minimize(loss, start, method="L-BFGS-B", bounds=bounds)
    mu, log_tau, log_sigma = result.x
    # Within-entity variance needs an entity with two values; between-entity variance needs two entities.
    identified = bool((n >= 2).any() and len(groups) >= 2)
    return float(mu), float(np.exp(log_tau)), float(np.exp(log_sigma)), {
        "converged": bool(result.success), "at_bound": _at_bound(result.x[1:], bounds[1:], ["tau", "sigma"]),
        "identified": identified}


def _fit(history: pd.DataFrame, effect: str, family: str, prior_id: str,
         categories: tuple) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    grouped = history.groupby("entity_id", sort=True)[effect]
    if family == "beta-binomial":
        k, n = grouped.sum().astype(float), grouped.count().astype(float)
        a, b, diagnostics = _beta_binomial(k.to_numpy(), n.to_numpy())
        post_a, post_b = a + k, b + n - k
        rows = pd.DataFrame({"entity_id": k.index.to_numpy(), "effect_id": effect,
                             "estimate": (post_a / (post_a + post_b)).to_numpy(),
                             "sd": np.sqrt(post_a * post_b / ((post_a + post_b) ** 2 * (post_a + post_b + 1))).to_numpy(),
                             "n": n.astype(int).to_numpy()})
        prior = pd.DataFrame({"effect_id": [effect], "estimate": [a / (a + b)],
                              "sd": [np.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))], "n": [0]})
        hyper = {"a": a, "b": b}
    elif family == "dirichlet-multinomial":
        counts = pd.crosstab(history.entity_id, history[effect]).reindex(columns=list(categories), fill_value=0).sort_index()
        alpha, diagnostics = _dirichlet_multinomial(counts.to_numpy(dtype=float))
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
        values = history[["entity_id", effect]]
        groups = [g.to_numpy(dtype=float) for _, g in values.groupby("entity_id", sort=True)[effect]]
        ids = sorted(values.entity_id.unique())
        mu, tau, sigma, diagnostics = _normal(groups)
        n = np.array([len(g) for g in groups], dtype=float)
        mean = np.array([g.mean() for g in groups])
        weight = tau ** 2 / (tau ** 2 + sigma ** 2 / n)
        rows = pd.DataFrame({"entity_id": ids, "effect_id": effect, "estimate": mu + weight * (mean - mu),
                             "sd": np.sqrt(1 / (1 / tau ** 2 + n / sigma ** 2)), "n": n.astype(int)})
        prior = pd.DataFrame({"effect_id": [effect], "estimate": [mu], "sd": [tau], "n": [0]})
        hyper = {"mu": mu, "tau": tau, "sigma": sigma}
    else:
        raise ValueError(f"family must be one of {FAMILIES}")
    diagnostics.update(entities=int(history.entity_id.nunique()), rows=len(history))
    return rows.assign(prior_id=prior_id), prior.assign(prior_id=prior_id), hyper, diagnostics


def _support(history: pd.DataFrame) -> dict:
    ids = history["transaction_hash"].astype(str).sort_values() if "transaction_hash" in history else pd.Series(dtype=str)
    return {"rows": len(history), "entities": int(history.entity_id.nunique()),
            "decisions_sha256": hashlib.sha256("\n".join(ids).encode()).hexdigest() if len(ids) else None}


def shrink(history: pd.DataFrame, effect: str, *, family: str, prior: str = "pooled", by: str | None = None,
           categories=None) -> EffectFit:
    """Shrunk effects of every entity in ``history`` (``entities.entity_history``), with the prior an unseen entity takes.

    ``categories`` declares the Dirichlet vocabulary; a category in the history outside it is refused."""
    if prior == "mixture":
        raise NotImplementedError("the type-mixture prior lands with the type model (ML6)")
    if prior != "pooled":
        raise ValueError("prior must be 'pooled' or 'mixture'")
    if family not in FAMILIES:
        raise ValueError(f"family must be one of {FAMILIES}")
    if effect not in history:
        raise ValueError(f"history has no column {effect!r}")
    as_of = history.attrs.get("as_of")
    if as_of is not None and "end_time" in history:
        # The cut is checked against the data, not trusted: every decision's label must have been observable before it.
        follow = pd.Timedelta(days=history.attrs.get("follow_up_days", 0))
        late = history.end_time.add(follow).ge(pd.Timestamp(as_of))
        if late.any():
            raise ValueError(f"{int(late.sum())} decisions were not observable before the history's cut {as_of}")
    history = history.loc[history[effect].notna()]
    if history.empty:
        raise ValueError(f"history has no decisions with a known {effect!r}")
    if family == "dirichlet-multinomial":
        seen = sorted(history[effect].unique())
        categories = tuple(seen if categories is None else categories)
        outside = sorted(set(seen) - set(categories))
        if outside:
            raise ValueError(f"categories outside the declared vocabulary: {outside}")
    else:
        categories = ()
    pooled_rows, pooled_prior, pooled_hyper, pooled_diag = _fit(history, effect, family, "pooled", categories)
    support = {"pooled": _support(history)}
    common = {"as_of": as_of, "categories": categories}
    if by is None:
        return EffectFit(family, effect, pooled_rows, pooled_prior, {"pooled": pooled_hyper}, support=support,
                         diagnostics={"pooled": pooled_diag}, **common)
    stratum = history.sort_values("end_time").groupby("entity_id")[by].last()
    rows, hyper, diagnostics = [], {"pooled": pooled_hyper}, {"pooled": pooled_diag}
    pooled_for = set(stratum.index[stratum.isna()])
    support["unknown"] = {"entities": len(pooled_for), "prior": "pooled"}
    for value, entities in stratum.dropna().groupby(stratum.dropna()):
        key = f"{by}={value}"
        if len(entities) < MIN_STRATUM_ENTITIES:
            pooled_for |= set(entities.index)
            support[key] = {"entities": len(entities), "prior": "pooled, too few entities to estimate a stratum prior"}
            continue
        part = history.loc[history.entity_id.isin(entities.index)]
        part_rows, _, part_hyper, part_diag = _fit(part, effect, family, key, categories)
        rows.append(part_rows)
        hyper[key], diagnostics[key], support[key] = part_hyper, part_diag, _support(part)
    rows.append(pooled_rows.loc[pooled_rows.entity_id.isin(pooled_for)])
    return EffectFit(family, effect, pd.concat(rows, ignore_index=True).sort_values(["entity_id", "effect_id"]).reset_index(drop=True),
                     pooled_prior, hyper, support=support, diagnostics=diagnostics, **common)
