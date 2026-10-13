"""Returns on the node's own history: a daily logit hazard that a node out of the set starts a new commitment.

The hazard is set by the days since the node's last commitment ended, in six bins from day 8 to day 365, the node's
stake band, and two facts of its own record known when it left: whether it has returned before, and whether the
commitment that ended was its first. The class default is no returns.

Why this form. Six narrower day bins let the hazard change faster with time out than the return block's three wide
bins, in which exposure weighted toward a bin's early days sets one rate for the whole bin. The two record terms let
a node's own history shift its hazard. The stake bands are the return block's three. Whether this form forecasts
better is a held-out question, settled outside the code.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from scipy import special

from avalanche_research.model.parts.base import (
    AVAX,
    RENEWAL_DAYS,
    RETURN_DAYS,
    BehaviourBlock,
    _outcomes,
    behavioural,
)
from avalanche_research.model.parts.returns import RETURN_STAKE_EDGES

# Ranges in whole days. A value equal to a bound falls in the lower bin: 8 to 14, 15 to 30, 31 to 60, 61 to 90,
# 91 to 180 and 181 to 365 days since the node's last commitment ended.
RETURN_BIN_EDGES = (14, 30, 60, 90, 180)
DAY_TERMS = ("days_15_30", "days_31_60", "days_61_90", "days_91_180", "days_181_365")
RETURN_LOGIT_TERMS = ("intercept", *DAY_TERMS, "stake_mid", "stake_large", "returned_before", "first_only")

# The fit's priors: a random walk with this SD on the log-odds between adjacent day bins, and a normal prior with
# variance 1 / RIDGE on the stake and record terms. The intercept has none.
RANDOM_WALK_SD = 0.5
RIDGE = 1.0
LOG_ODDS_CLIP = 20.0


def return_design(stake_navax, days_since_end, done, returns) -> np.ndarray:
    """One row per node-day, one column per term of :data:`RETURN_LOGIT_TERMS`.

    ``done`` counts the node's completed commitments, the one that ended included, and ``returns`` how many of them
    began more than seven days after the one before. A node has returned before when ``returns`` is above zero. Its
    only commitment has ended when ``done`` is 1. A node that has only ever renewed is in neither group.
    """
    days = np.asarray(days_since_end)
    period = np.digitize(days, RETURN_BIN_EDGES, right=True)
    band = np.digitize(np.asarray(stake_navax, dtype=float) / AVAX, RETURN_STAKE_EDGES, right=True)
    returned = np.asarray(returns) > 0
    first = (np.asarray(done) == 1) & ~returned
    columns = [np.ones(len(days))]
    columns += [period == k for k in range(1, len(RETURN_BIN_EDGES) + 1)]
    columns += [band == 1, band == 2, returned, first]
    return np.column_stack(columns).astype(float)


def _penalty() -> np.ndarray:
    """The priors as a penalty matrix on the terms: the random walk on the day bins, the ridge on the rest."""
    k = len(RETURN_LOGIT_TERMS)
    penalty = np.zeros((k, k))
    n = len(DAY_TERMS)
    # Row j is the step from day bin j to day bin j + 1, the first bin's effect being zero.
    steps = np.eye(n) - np.eye(n, k=-1)
    penalty[1:1 + n, 1:1 + n] = steps.T @ steps / RANDOM_WALK_SD**2
    rest = np.arange(1 + n, k)
    penalty[rest, rest] = RIDGE
    return penalty


def _coefficient(name: str) -> object:
    default, words = (-LOG_ODDS_CLIP, "Log-odds of returning on a day 8 to 14 days out, for a node with a minimum stake that has only renewed") \
        if name == "intercept" else (0.0, f"Log-odds term {name} of returning on a day")
    return behavioural(default, (-LOG_ODDS_CLIP, LOG_ODDS_CLIP), "assumed", words, "No returns until fitted by ReturnLogitHazard.fit")


class ReturnLogitHazard(BehaviourBlock):
    """Whether a node that did not renew starts a new commitment today, after more than seven days out.

    logit h = intercept + day bin + stake band + returned before + first commitment only. Stake bands are the minimum
    (up to 2,100 AVAX), mid (to 100,000) and large. A node out for more than 365 days leaves the model, as with
    :class:`~avalanche_research.model.parts.returns.ReturnHazard`.
    """

    reads = ("returning_nodes",)
    writes = ("returned_commitments",)
    decision = "return after more than seven days"

    intercept = _coefficient("intercept")
    days_15_30 = _coefficient("days_15_30")
    days_31_60 = _coefficient("days_31_60")
    days_61_90 = _coefficient("days_61_90")
    days_91_180 = _coefficient("days_91_180")
    days_181_365 = _coefficient("days_181_365")
    stake_mid = _coefficient("stake_mid")
    stake_large = _coefficient("stake_large")
    returned_before = _coefficient("returned_before")
    first_only = _coefficient("first_only")

    def coefficients(self) -> np.ndarray:
        return np.array([getattr(self, term) for term in RETURN_LOGIT_TERMS])

    def probability(self, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        """The daily hazard of each node: zero inside its renewal week and after 365 days out."""
        days = np.asarray(inputs["days_since_end"])
        design = return_design(inputs["stake_navax"], days, inputs["done"], inputs["returns"])
        hazard = special.expit(design @ self.coefficients())
        return np.where((days > RENEWAL_DAYS) & (days <= RETURN_DAYS), hazard, 0.0)

    def sample(self, inputs, rng):
        p = self.probability(inputs)
        return rng.random(len(p)) < p

    def log_prob(self, inputs, decisions):
        decisions = _outcomes(decisions, len(inputs["stake_navax"]))
        p = self.probability(inputs)
        if (decisions & (p == 0)).any():
            return float("-inf")
        with np.errstate(divide="ignore"):
            return float(np.where(decisions, np.log(p), np.log1p(-p)).sum())

    @classmethod
    def fit(cls, stake_navax, days_out, returned, done, returns, evidence: str) -> ReturnLogitHazard:
        """The posterior mode over node-days at risk, under the random-walk prior on the day bins and the normal
        prior on the stake and record terms.

        ``days_out`` is how many days after its end each node was last seen out: the day it returned, or the day
        observation stopped. A node is at risk from day 8 to that day, capped at 365. A return after day 365 is a node
        that stayed out for the whole window, censored at 365, as the simulator drops it then. ``done`` and
        ``returns`` are the node's record when it left, as :func:`return_design` reads them.

        Node-days are counted by covariate pattern and day bin, and Newton steps, halved while they lower the
        penalized log-likelihood, run on those binomial counts until the step is below 1e-10. A term whose column has
        no node-days stays where its prior puts it and is labelled by the prior: zero for a stake or record term, the
        neighbouring bin's value for a day bin. With no returns, or no node-days at risk, the intercept is held at
        the lower clip and every other term at zero, and with a return on every node-day at risk at the upper clip.
        """
        stake = np.asarray(stake_navax, dtype=float)
        seen = np.asarray(days_out, dtype=np.int64)
        came_back = np.asarray(returned, dtype=bool) & (seen <= RETURN_DAYS)
        seen = np.minimum(seen, RETURN_DAYS)
        record = return_design(stake, np.full(len(seen), RENEWAL_DAYS + 1), done, returns)[:, len(DAY_TERMS) + 1:]
        patterns, pattern = np.unique(record, axis=0, return_inverse=True)
        pattern = pattern.ravel()
        lows = (RENEWAL_DAYS, *RETURN_BIN_EDGES)
        highs = (*RETURN_BIN_EDGES, RETURN_DAYS)
        trials = np.zeros((len(patterns), len(lows)))
        events = np.zeros((len(patterns), len(lows)))
        for period, (low, high) in enumerate(zip(lows, highs)):
            np.add.at(trials[:, period], pattern, np.clip(seen - low, 0, high - low))
            np.add.at(events[:, period], pattern, came_back & (seen > low) & (seen <= high))
        rows, periods = np.nonzero(trials)
        design = np.zeros((len(rows), len(RETURN_LOGIT_TERMS)))
        design[:, 0] = 1.0
        for k in range(1, len(lows)):
            design[:, k] = periods == k
        design[:, len(lows):] = patterns[rows]
        n, y = trials[rows, periods], events[rows, periods]
        at_risk, back = float(n.sum()), float(y.sum())
        exposure = (design * n[:, None]).sum(axis=0)

        beta = np.zeros(len(RETURN_LOGIT_TERMS))
        # With no returns the intercept's mode is at minus infinity, and with a return on every node-day at risk at
        # plus infinity, so Newton steps would run it off.
        held = back == 0 or back == at_risk
        if held:
            beta[0] = LOG_ODDS_CLIP if back else -LOG_ODDS_CLIP
        else:
            beta = _newton(design, n, y, _penalty())
        values = {term: float(np.clip(b, -LOG_ODDS_CLIP, LOG_ODDS_CLIP)) for term, b in zip(RETURN_LOGIT_TERMS, beta)}
        counted = f"{evidence}; {int(back)} returns in {int(at_risk)} node-days"
        priors = f"random-walk prior SD {RANDOM_WALK_SD} between adjacent day bins, normal prior SD {RIDGE ** -0.5:g} on stake and record terms"
        provenance = {term: {"source": "fitted", "evidence": f"{counted}; {priors}", "value": value} for term, value in values.items()}
        words = "no node-days at risk" if not at_risk else "no returns" if not back else "a return on every node-day at risk"
        for i, term in enumerate(RETURN_LOGIT_TERMS[1:], start=1):
            if held:
                provenance[term] = {"source": "prior", "value": values[term], "evidence": f"{counted}; {words}, so this term stays at zero"}
            elif not exposure[i]:
                where = "its neighbouring day bin's value" if term in DAY_TERMS else "zero"
                provenance[term] = {"source": "prior", "value": values[term],
                                    "evidence": f"{counted}; no node-days in this term's cell, so the prior sets it to {where}"}
        if held:
            provenance["intercept"] = {"source": "fitted", "value": values["intercept"],
                                       "evidence": f"{counted}; {words}, so the intercept is held at the clip"}
        return cls(provenance=provenance, **values)


def _objective(design: np.ndarray, n: np.ndarray, y: np.ndarray, beta: np.ndarray, penalty: np.ndarray) -> float:
    """The binomial log-likelihood of ``y`` returns in ``n`` node-days at ``beta``, less the priors' penalty."""
    eta = design @ beta
    return float((y * eta - n * np.logaddexp(0.0, eta)).sum() - 0.5 * beta @ penalty @ beta)


def _newton(design: np.ndarray, n: np.ndarray, y: np.ndarray, penalty: np.ndarray) -> np.ndarray:
    """The penalized binomial logit's mode by Newton steps, each halved until it does not lower the objective."""
    beta = np.zeros(design.shape[1])
    beta[0] = special.logit(np.clip(y.sum() / n.sum(), 1e-9, 1 - 1e-9))
    objective = _objective(design, n, y, beta, penalty)
    for _ in range(100):
        p = special.expit(design @ beta)
        gradient = design.T @ (y - n * p) - penalty @ beta
        hessian = (design * (n * p * (1 - p))[:, None]).T @ design + penalty
        step = np.linalg.solve(hessian, gradient)
        size = 1.0
        while size > 1e-6:
            trial = _objective(design, n, y, beta + size * step, penalty)
            if trial >= objective - 1e-12 * abs(objective):
                break
            size /= 2
        beta = beta + size * step
        objective = _objective(design, n, y, beta, penalty)
        if np.abs(size * step).max() < 1e-10:
            return beta
    raise RuntimeError("the return logit did not converge in 100 Newton steps")
