"""Small maximum-likelihood fits with robust covariances, written out so every step can be read.

Three estimators cover the behaviour study: a Poisson regression and a logit, both fitted by Newton's method,
and ordinary least squares. Each returns the coefficients with a sandwich covariance: clustered by a group
label when one is given, Newey-West when the rows are a time series, and heteroskedasticity-robust otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import expit, gammaln

Z95 = 1.959963984540054


@dataclass(frozen=True)
class Fit:
    """Coefficients, their covariance, and the log-likelihood (or the residual sum of squares for OLS)."""

    names: tuple[str, ...]
    coef: np.ndarray
    cov: np.ndarray
    loglik: float
    n: int
    converged: bool = True

    @property
    def se(self) -> np.ndarray:
        return np.sqrt(np.clip(np.diag(self.cov), 0.0, None))

    @property
    def ci95(self) -> np.ndarray:
        return np.column_stack([self.coef - Z95 * self.se, self.coef + Z95 * self.se])

    def table(self) -> dict[str, dict[str, float]]:
        ci = self.ci95
        return {
            name: {"estimate": float(self.coef[i]), "se": float(self.se[i]), "ci95": [float(ci[i, 0]), float(ci[i, 1])]}
            for i, name in enumerate(self.names)
        }


def cluster_meat(scores: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Sum of outer products of per-group score totals, with the G/(G-1) small-sample factor."""
    codes, inverse = np.unique(groups, return_inverse=True)
    totals = np.zeros((len(codes), scores.shape[1]))
    np.add.at(totals, inverse, scores)
    count = len(codes)
    factor = count / (count - 1) if count > 1 else 1.0
    return factor * totals.T @ totals


def newey_west_meat(scores: np.ndarray, lags: int) -> np.ndarray:
    """Bartlett-weighted long-run covariance of time-ordered score rows."""
    meat = scores.T @ scores
    for lag in range(1, lags + 1):
        weight = 1.0 - lag / (lags + 1.0)
        cross = scores[lag:].T @ scores[:-lag]
        meat += weight * (cross + cross.T)
    return meat


def sandwich(bread: np.ndarray, scores: np.ndarray, groups: np.ndarray | None, hac_lags: int) -> np.ndarray:
    if groups is not None:
        meat = cluster_meat(scores, groups)
    elif hac_lags > 0:
        meat = newey_west_meat(scores, hac_lags)
    else:
        meat = scores.T @ scores
    return bread @ meat @ bread


def _newton(gradient_hessian, start: np.ndarray, max_iter: int = 200, tol: float = 1e-9):
    """Newton's method with step halving on a concave log-likelihood.

    Stops when the Newton decrement, grad' (-H)^-1 grad, falls below ``tol``.
    """
    beta = start.astype(float).copy()
    value, grad, hess = gradient_hessian(beta)
    for iteration in range(max_iter):
        step = np.linalg.solve(-hess, grad)
        if grad @ step < tol:
            return beta, value, grad, hess, True, iteration
        scale = 1.0
        while True:
            candidate = beta + scale * step
            new_value, new_grad, new_hess = gradient_hessian(candidate)
            if np.isfinite(new_value) and new_value >= value:
                break
            scale /= 2.0
            if scale < 1e-12:
                return beta, value, grad, hess, False, iteration
        beta, value, grad, hess = candidate, new_value, new_grad, new_hess
    return beta, value, grad, hess, False, max_iter


def poisson(
    y: np.ndarray,
    X: np.ndarray,
    names: tuple[str, ...],
    offset: np.ndarray | None = None,
    groups: np.ndarray | None = None,
    hac_lags: int = 0,
) -> Fit:
    """Poisson regression, log link: E[y] = exp(offset + X b)."""
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    offset = np.zeros(len(y)) if offset is None else np.asarray(offset, dtype=float)

    def gradient_hessian(beta):
        eta = offset + X @ beta
        mu = np.exp(eta)
        value = float(np.sum(y * eta - mu - gammaln(y + 1.0)))
        return value, X.T @ (y - mu), -(X * mu[:, None]).T @ X

    start = np.zeros(X.shape[1])
    beta, value, _, hess, converged, _ = _newton(gradient_hessian, start)
    mu = np.exp(offset + X @ beta)
    bread = np.linalg.inv(-hess)
    cov = sandwich(bread, X * (y - mu)[:, None], groups, hac_lags)
    return Fit(names, beta, cov, value, len(y), converged)


def poisson_loglik(y: np.ndarray, X: np.ndarray, beta: np.ndarray, offset: np.ndarray | None = None) -> float:
    offset = np.zeros(len(y)) if offset is None else offset
    eta = offset + np.asarray(X, dtype=float) @ beta
    return float(np.sum(y * eta - np.exp(eta) - gammaln(np.asarray(y, dtype=float) + 1.0)))


def logit(y: np.ndarray, X: np.ndarray, names: tuple[str, ...], groups: np.ndarray | None = None, hac_lags: int = 0) -> Fit:
    """Binary logit: P(y = 1) = 1 / (1 + exp(-X b))."""
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)

    def gradient_hessian(beta):
        eta = X @ beta
        value = float(np.sum(y * eta - np.logaddexp(0.0, eta)))
        p = expit(eta)
        return value, X.T @ (y - p), -(X * (p * (1.0 - p))[:, None]).T @ X

    beta, value, _, hess, converged, _ = _newton(gradient_hessian, np.zeros(X.shape[1]))
    p = expit(X @ beta)
    cov = sandwich(np.linalg.inv(-hess), X * (y - p)[:, None], groups, hac_lags)
    return Fit(names, beta, cov, value, len(y), converged)


def logit_loglik(y: np.ndarray, X: np.ndarray, beta: np.ndarray) -> float:
    eta = np.asarray(X, dtype=float) @ beta
    return float(np.sum(np.asarray(y, dtype=float) * eta - np.logaddexp(0.0, eta)))


def ols(y: np.ndarray, X: np.ndarray, names: tuple[str, ...], hac_lags: int = 0) -> Fit:
    """Least squares with a Newey-West (or White) covariance. ``loglik`` holds the residual sum of squares."""
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    residual = y - X @ beta
    bread = np.linalg.inv(X.T @ X)
    cov = sandwich(bread, X * residual[:, None], None, hac_lags)
    return Fit(names, beta, cov, float(residual @ residual), len(y))
