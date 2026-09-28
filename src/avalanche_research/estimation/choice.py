"""Delegator choice among the validators offered at each Monday cutoff.

Each week is a market (``SD2``). The rows are the node-weeks offered at the cutoff (``SD4``, ``RD9``), the outcome
is the number of delegations each node received during the week, and the features are known at the cutoff
(``SD7``). The model is a Poisson regression of the count on the features with one fixed effect per week:

    E[count_iw] = exp(alpha_w + x_iw' b)

Concentrating out alpha_w leaves, week by week, the multinomial log-likelihood of the observed delegations over
the offered nodes with probabilities softmax(x_iw' b). That is the conditional logit, so the two fits give the
same b. There is no outside option and no grid of unchosen durations (``SD5``, ``SD6``). Standard errors are
clustered by week.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from ._stats import Z95, Fit, cluster_meat

FEATURES = ("log_net_apy_14d", "delegation_fee_rate", "log_capacity_left_avax", "node_age_weeks", "completed_periods")
CONCENTRATED_ADDRESS = "avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy"
# Outcome column per stratum. ``concentrated_only`` is a diagnostic: Eric says the address delegates at random,
# which is the hypothesis b = 0 for that stratum.
STRATA = {
    "all": "delegations_all",
    "excl_concentrated": "delegations_excl_concentrated",
    "concentrated_only": "delegations_concentrated",
}
PRIMARY_STRATUM = "excl_concentrated"


@dataclass(frozen=True)
class ChoiceFit:
    fit: Fit
    weeks: int
    rows: int
    events: int
    iterations: int
    feature_mean: np.ndarray
    feature_sd: np.ndarray


def _group_index(groups: np.ndarray) -> tuple[np.ndarray, int]:
    _, inverse = np.unique(groups, return_inverse=True)
    return inverse, int(inverse.max()) + 1 if len(inverse) else 0


def _softmax_by_group(eta: np.ndarray, index: np.ndarray, count: int) -> np.ndarray:
    peak = np.full(count, -np.inf)
    np.maximum.at(peak, index, eta)
    weight = np.exp(eta - peak[index])
    total = np.bincount(index, weights=weight, minlength=count)
    return weight / total[index]


def conditional_loglik(y: np.ndarray, X: np.ndarray, groups: np.ndarray, beta: np.ndarray) -> float:
    """Sum over rows of y * log p, where p is the within-group softmax of X b. Multinomial constants are omitted."""
    index, count = _group_index(groups)
    p = _softmax_by_group(np.asarray(X, dtype=float) @ beta, index, count)
    positive = y > 0
    return float(np.sum(y[positive] * np.log(p[positive])))


def uniform_loglik(y: np.ndarray, groups: np.ndarray) -> float:
    """The null: every offered row in a group is equally likely."""
    index, count = _group_index(groups)
    size = np.bincount(index, minlength=count)
    return float(-np.sum(y * np.log(size[index])))


def fit_conditional_logit(
    y: np.ndarray,
    X: np.ndarray,
    groups: np.ndarray,
    names: tuple[str, ...],
    max_iter: int = 200,
    tol: float = 1e-9,
    standardize: bool = True,
) -> ChoiceFit:
    """Poisson regression with group fixed effects, fitted as the conditional logit by Newton's method.

    Features are standardized inside the fit for conditioning and the coefficients and covariance are mapped
    back to the original units. The covariance is clustered by group with the G/(G-1) factor.
    """
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    groups = np.asarray(groups)
    index, count = _group_index(groups)
    mean = X.mean(axis=0) if standardize else np.zeros(X.shape[1])
    sd = X.std(axis=0) if standardize else np.ones(X.shape[1])
    sd = np.where(sd > 0, sd, 1.0)
    Z = (X - mean) / sd
    n_group = np.bincount(index, weights=y, minlength=count)

    def evaluate(beta):
        p = _softmax_by_group(Z @ beta, index, count)
        positive = y > 0
        value = float(np.sum(y[positive] * np.log(p[positive])))
        weighted = np.zeros((count, Z.shape[1]))
        np.add.at(weighted, index, p[:, None] * Z)
        grad = y @ Z - n_group @ weighted
        mu = n_group[index] * p
        hess = -(Z * mu[:, None]).T @ Z + (weighted * n_group[:, None]).T @ weighted
        return value, grad, hess, p

    beta = np.zeros(Z.shape[1])
    value, grad, hess, p = evaluate(beta)
    converged, iterations = False, 0
    for iterations in range(1, max_iter + 1):
        step = np.linalg.solve(-hess, grad)
        if grad @ step < tol:
            converged = True
            break
        scale = 1.0
        while True:
            candidate = beta + scale * step
            new = evaluate(candidate)
            if np.isfinite(new[0]) and new[0] >= value:
                break
            scale /= 2.0
            if scale < 1e-12:
                break
        if scale < 1e-12:
            break
        beta = candidate
        value, grad, hess, p = new
    mu = n_group[index] * p
    scores = Z * (y - mu)[:, None]
    bread = np.linalg.inv(-hess)
    cov_z = bread @ cluster_meat(scores, index) @ bread
    coef = beta / sd
    cov = cov_z / np.outer(sd, sd)
    fit = Fit(tuple(names), coef, cov, value, len(y), converged)
    return ChoiceFit(fit, count, len(y), int(y.sum()), iterations, mean, sd)


def choice_panel(con: Any, start: str, end: str) -> pd.DataFrame:
    """Offered node-weeks with a week start in [start, end), their features, and weekly counts by stratum.

    Rows whose net yield is zero (a 100% fee) have no log yield and are dropped here and counted by
    ``panel_coverage``.
    """
    return con.execute(
        """
        SELECT week_start_utc, node_id, log_net_apy_14d, delegation_fee_rate,
               ln(capacity_left_avax) AS log_capacity_left_avax, node_age_weeks,
               completed_periods::DOUBLE AS completed_periods,
               delegations_all, delegations_excl_concentrated,
               delegations_all - delegations_excl_concentrated AS delegations_concentrated
        FROM validator_weeks
        WHERE offered_at_week_start AND log_net_apy_14d IS NOT NULL AND capacity_left_avax > 0
          AND week_start_utc >= ?::TIMESTAMP AND week_start_utc < ?::TIMESTAMP
        ORDER BY week_start_utc, node_id
        """,
        [start, end],
    ).df()


def panel_coverage(con: Any, start: str, end: str) -> dict[str, int]:
    """How many delegations the offered, feature-complete rows hold, and how many fall outside them."""
    row = con.execute(
        """
        SELECT
          sum(delegations_all) AS all_delegations,
          sum(delegations_all) FILTER (WHERE offered_at_week_start AND log_net_apy_14d IS NOT NULL AND capacity_left_avax > 0) AS in_panel,
          sum(delegations_all) FILTER (WHERE NOT offered_at_week_start) AS to_not_offered_rows,
          sum(delegations_all) FILTER (WHERE offered_at_week_start AND log_net_apy_14d IS NULL) AS to_full_fee_rows,
          sum(delegations_excl_concentrated) AS excl_all,
          sum(delegations_excl_concentrated) FILTER (WHERE offered_at_week_start AND log_net_apy_14d IS NOT NULL AND capacity_left_avax > 0) AS excl_in_panel,
          count(*) FILTER (WHERE offered_at_week_start) AS offered_rows,
          count(*) FILTER (WHERE offered_at_week_start AND log_net_apy_14d IS NULL) AS full_fee_rows
        FROM validator_weeks
        WHERE week_start_utc >= ?::TIMESTAMP AND week_start_utc < ?::TIMESTAMP
        """,
        [start, end],
    ).df().iloc[0]
    observed = con.execute(
        "SELECT count(*) FROM observed_delegations WHERE week_start_utc >= ?::TIMESTAMP AND week_start_utc < ?::TIMESTAMP",
        [start, end],
    ).fetchone()[0]
    result = {key: int(value) if pd.notna(value) else 0 for key, value in row.items()}
    result["observed_delegations"] = int(observed)
    return result


def within_week_correlation(panel: pd.DataFrame) -> dict[str, float]:
    """Correlations of the features after removing week means, the variation the fit actually uses."""
    demeaned = panel[list(FEATURES)] - panel.groupby("week_start_utc")[list(FEATURES)].transform("mean")
    corr = demeaned.corr()
    return {f"{a}~{b}": float(corr.loc[a, b]) for i, a in enumerate(FEATURES) for b in FEATURES[i + 1:]}


def fit_strata(fit_panel: pd.DataFrame, holdout_panel: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Fit every stratum on ``fit_panel`` and score it on ``holdout_panel`` against the uniform null."""
    results: dict[str, dict[str, Any]] = {}
    X_fit = fit_panel[list(FEATURES)].to_numpy(float)
    X_out = holdout_panel[list(FEATURES)].to_numpy(float)
    g_fit = fit_panel["week_start_utc"].to_numpy()
    g_out = holdout_panel["week_start_utc"].to_numpy()
    for stratum, column in STRATA.items():
        y_fit = fit_panel[column].to_numpy(float)
        y_out = holdout_panel[column].to_numpy(float)
        result = fit_conditional_logit(y_fit, X_fit, g_fit, FEATURES)
        events_out = float(y_out.sum())
        ll_out = conditional_loglik(y_out, X_out, g_out, result.fit.coef)
        ll_null = uniform_loglik(y_out, g_out)
        ll_fit_null = uniform_loglik(y_fit, g_fit)
        reduced_names = tuple(name for name in FEATURES if name != "delegation_fee_rate")
        reduced = fit_conditional_logit(y_fit, fit_panel[list(reduced_names)].to_numpy(float), g_fit, reduced_names)
        results[stratum] = {
            "outcome": column,
            "coefficients": {name: float(v) for name, v in zip(FEATURES, result.fit.coef)},
            "se": {name: float(v) for name, v in zip(FEATURES, result.fit.se)},
            "ci95": {name: [float(lo), float(hi)] for name, (lo, hi) in zip(FEATURES, result.fit.ci95)},
            "converged": result.fit.converged,
            "fit": {
                "weeks": result.weeks, "rows": result.rows, "delegations": result.events,
                "loglik": result.fit.loglik, "loglik_uniform": ll_fit_null,
                "loglik_gain_per_delegation": (result.fit.loglik - ll_fit_null) / max(result.events, 1),
            },
            "holdout": {
                "weeks": len(np.unique(g_out)), "rows": len(y_out), "delegations": int(events_out),
                "loglik": ll_out, "loglik_uniform": ll_null,
                "loglik_gain_per_delegation": (ll_out - ll_null) / max(events_out, 1.0),
            },
            "fee_effect": fee_effect(result.fit),
            "reduced_without_fee": reduced.fit.table(),
        }
    return results


def fee_effect(fit: Fit, fees: tuple[float, ...] = (0.02, 0.05, 0.10)) -> dict[str, dict[str, Any]]:
    """Total effect of the fee on a node's utility, d/d(fee) = b_fee - b_log_net_apy / (1 - fee), with a delta-method interval.

    Within a week the gross 14-day rate is the same for every node, so ``log_net_apy_14d`` is ln(1 - fee) plus a
    week constant. The fee therefore enters through both features, and only this sum is interpretable.
    """
    i_apy, i_fee = FEATURES.index("log_net_apy_14d"), FEATURES.index("delegation_fee_rate")
    effects = {}
    for fee in fees:
        gradient = np.zeros(len(FEATURES))
        gradient[i_fee], gradient[i_apy] = 1.0, -1.0 / (1.0 - fee)
        estimate = float(gradient @ fit.coef)
        se = float(np.sqrt(gradient @ fit.cov @ gradient))
        effects[f"{fee:.2f}"] = {"estimate": estimate, "se": se, "ci95": [estimate - Z95 * se, estimate + Z95 * se]}
    return effects


def identified(strata: dict[str, dict[str, Any]], first: str = "all", second: str = "excl_concentrated") -> dict[str, bool]:
    """A coefficient is identified when its sign agrees across the two strata and neither 95% interval spans zero.

    The rule was fixed before the estimates were seen.
    """
    flags = {}
    for name in FEATURES:
        a, b = strata[first], strata[second]
        same_sign = np.sign(a["coefficients"][name]) == np.sign(b["coefficients"][name])
        excludes_zero = all(s["ci95"][name][0] > 0 or s["ci95"][name][1] < 0 for s in (a, b))
        flags[name] = bool(same_sign and excludes_zero)
    return flags


__all__ = [
    "CONCENTRATED_ADDRESS", "FEATURES", "PRIMARY_STRATUM", "STRATA", "Z95", "ChoiceFit", "choice_panel",
    "conditional_loglik", "fee_effect", "fit_conditional_logit", "fit_strata", "identified", "panel_coverage",
    "uniform_loglik", "within_week_correlation",
]
