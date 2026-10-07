"""v0.8's behaviour blocks, each fitted by likelihood on its own decision events before an origin (review note RD1).

* :class:`RenewalLogit`: whether an ending commitment renews on the same node within seven days, as a logit on
  tenure, the previous outcome, the commitment's duration and its stake (RD2).
* :class:`Arrivals`: how many first-ever nodes start a commitment each day, a negative binomial count (RD4).
* :class:`ReturnHazard`: whether a node that did not renew returns, a daily hazard by days since its end and its
  stake band, for up to 365 days (RD4).

Each block offers ``sample`` for the simulator and ``log_prob`` for the estimator, as every block does, and a ``fit``
class method that returns an instance whose every parameter is labelled ``fitted`` with the events it was fitted on.
The class defaults are placeholders: one constant renewal probability, a Poisson count, and no returns.

The empirical draws for a continuing node's next duration and stake are tables, not parameters: :class:`Continuation`.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import lgamma

import numpy as np
from scipy import optimize, special, stats

from avalanche_research.model.blocks import BehaviourBlock, _outcomes, behavioural

AVAX = 10**9
RENEWAL_DAYS = 7
RETURN_DAYS = 365

# Ranges in whole days and AVAX. A value equal to a bound falls in the lower bin.
TENURE_BINS = ("1", "2", "3 to 6", "7 to 9", "10 or more")
DURATION_EDGES = (20, 40, 100)
RENEWAL_STAKE_EDGES = (2_100, 100_000, 1_000_000)
RETURN_STAKE_EDGES = (2_100, 100_000)
# Log-spaced from 2,100 to 2,000,000 AVAX: the stake bands within which a moving node draws its stake ratio.
MOVE_STAKE_EDGES = tuple(float(x) for x in np.exp(np.linspace(np.log(2_100), np.log(2_000_000), 9)))
RETURN_DAY_EDGES = (30, 90)

RENEWAL_TERMS = (
    "intercept", "tenure_2", "tenure_3_6", "tenure_7_9", "tenure_10_plus", "after_return",
    "days_21_40", "days_41_100", "days_over_100", "stake_2k_100k", "stake_100k_1m", "stake_over_1m", "node_record",
)
NODE_PRIOR_GRID = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0)
RETURN_CELLS = tuple(
    f"{stake}_{days}" for stake in ("minimum", "mid", "large") for days in ("8_30", "31_90", "91_365")
)


def tenure_bin(done: np.ndarray) -> np.ndarray:
    """The tenure bin of a commitment from the node's completed commitments before it: 0 is a first commitment."""
    done = np.asarray(done)
    return np.select([done == 0, done == 1, done <= 5, done <= 8], [0, 1, 2, 3], 4)


def renewal_design(done, after_return, days, stake_navax, returns=None, prior_strength: float = 5.0, prior_share: float = 0.8) -> np.ndarray:
    """One row per ending commitment, one column per term of :data:`RENEWAL_TERMS`.

    ``returns`` counts the node's commitments, this one included, that began more than seven days after the one
    before, so the node renewed ``done - returns`` of its ``done`` earlier endings. The node record is the log-odds of
    that share shrunk toward ``prior_share`` with the weight of ``prior_strength`` endings, less the log-odds of
    ``prior_share``. It is zero for a first commitment, and zero for every row when ``returns`` is not given.
    """
    done, days = np.asarray(done), np.asarray(days)
    stake = np.asarray(stake_navax, dtype=float) / AVAX
    tenure = tenure_bin(done)
    duration = np.digitize(days, DURATION_EDGES, right=True)
    band = np.digitize(stake, RENEWAL_STAKE_EDGES, right=True)
    columns = [np.ones(len(done))]
    columns += [tenure == k for k in (1, 2, 3, 4)]
    columns += [np.asarray(after_return, dtype=bool) & (done > 0)]
    columns += [duration == k for k in (1, 2, 3)]
    columns += [band == k for k in (1, 2, 3)]
    if returns is None:
        columns += [np.zeros(len(done))]
    else:
        renewed = done - np.asarray(returns)
        shrunk = (renewed + prior_strength * prior_share) / (done + prior_strength)
        columns += [special.logit(shrunk) - special.logit(prior_share)]
    return np.column_stack(columns).astype(float)


def _coefficient(name: str, default: float) -> object:
    source, evidence = ("observed moment", "AM2, 30,578 of 38,149 endings in 2021 to 2024, staking-periods-2026-09-30") if name == "intercept" else (
        "assumed", "No effect until fitted by RenewalLogit.fit")
    return behavioural(default, (-20.0, 20.0), source, f"Log-odds term {name} of renewing within seven days", evidence)


class RenewalLogit(BehaviourBlock):
    """Renewal within seven days on the same node: logit P = intercept + tenure + after a return + duration + stake.

    The previous outcome is whether the ending commitment itself began more than seven days after the node's last
    one ended, a return, rather than as a renewal. A first commitment has no previous outcome, so the tenure term
    carries it. ``shift`` in the inputs adds to every log-odds, as the renewal response to a yield gap does.
    """

    reads = ("ending_commitments",)
    writes = ("renewed_commitments",)
    decision = "renew within seven days"

    intercept = _coefficient("intercept", float(special.logit(0.801541)))
    tenure_2 = _coefficient("tenure_2", 0.0)
    tenure_3_6 = _coefficient("tenure_3_6", 0.0)
    tenure_7_9 = _coefficient("tenure_7_9", 0.0)
    tenure_10_plus = _coefficient("tenure_10_plus", 0.0)
    after_return = _coefficient("after_return", 0.0)
    days_21_40 = _coefficient("days_21_40", 0.0)
    days_41_100 = _coefficient("days_41_100", 0.0)
    days_over_100 = _coefficient("days_over_100", 0.0)
    stake_2k_100k = _coefficient("stake_2k_100k", 0.0)
    stake_100k_1m = _coefficient("stake_100k_1m", 0.0)
    stake_over_1m = _coefficient("stake_over_1m", 0.0)
    node_record = _coefficient("node_record", 0.0)
    node_prior_strength = behavioural(
        5.0, (0.01, 1000.0), "assumed", "Endings' worth of weight on the population share in a node's own renewal record",
        "Placeholder until fitted by RenewalLogit.fit",
    )
    node_prior_share = behavioural(
        0.801541, (0.001, 0.999), "observed moment", "The population renewal share a node's own record is shrunk toward",
        "AM2, 30,578 of 38,149 endings in 2021 to 2024, staking-periods-2026-09-30",
    )

    def design(self, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        return renewal_design(inputs["done"], inputs["after_return"], inputs["days"], inputs["stake_navax"],
                              inputs.get("returns"), self.node_prior_strength, self.node_prior_share)

    def coefficients(self) -> np.ndarray:
        return np.array([getattr(self, term) for term in RENEWAL_TERMS])

    def probability(self, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        return special.expit(self.design(inputs) @ self.coefficients() + inputs.get("shift", 0.0))

    def sample(self, inputs, rng):
        p = self.probability(inputs)
        return rng.random(len(p)) < p

    def log_prob(self, inputs, decisions):
        decisions = _outcomes(decisions, len(inputs["done"]))
        eta = self.design(inputs) @ self.coefficients() + inputs.get("shift", 0.0)
        return float(-np.logaddexp(0.0, np.where(decisions, -eta, eta)).sum())

    @classmethod
    def fit(cls, inputs: Mapping[str, np.ndarray], decisions: np.ndarray, evidence: str, ridge: float = 1.0) -> RenewalLogit:
        """The posterior mode under a normal prior with variance ``1 / ridge`` on every term but the intercept.

        The prior keeps a term whose cell is empty in a short window at zero instead of at infinity. Newton steps
        on the penalized log-likelihood, which is concave, until the step is below 1e-10. With ``returns`` in the
        inputs, the node record's prior share is the share renewed, and its prior strength is the value on
        :data:`NODE_PRIOR_GRID` with the highest penalized log-likelihood. Without it, the node record stays at zero.
        """
        y = _outcomes(decisions, len(inputs["done"])).astype(float)
        share = float(np.clip(y.mean(), 1e-3, 1 - 1e-3))
        if inputs.get("returns") is None:
            design = renewal_design(inputs["done"], inputs["after_return"], inputs["days"], inputs["stake_navax"])[:, :-1]
            beta, _ = _newton(design, y, ridge)
            fitted, extra = [*beta, 0.0], {}
        else:
            best = None
            for strength in NODE_PRIOR_GRID:
                design = renewal_design(inputs["done"], inputs["after_return"], inputs["days"], inputs["stake_navax"],
                                        inputs["returns"], strength, share)
                beta, objective = _newton(design, y, ridge)
                if best is None or objective > best[2]:
                    best = (beta, strength, objective)
            fitted, extra = list(best[0]), {"node_prior_strength": best[1], "node_prior_share": share}
        values = {term: float(np.clip(b, -20.0, 20.0)) for term, b in zip(RENEWAL_TERMS, fitted)} | extra
        provenance = {term: {"source": "fitted", "evidence": evidence, "value": value} for term, value in values.items()}
        return cls(provenance=provenance, **values)


def _newton(design: np.ndarray, y: np.ndarray, ridge: float) -> tuple[np.ndarray, float]:
    """The penalized logit's mode and its penalized log-likelihood. The intercept, column 0, is not penalized."""
    penalty = np.full(design.shape[1], float(ridge))
    penalty[0] = 0.0
    beta = np.zeros(design.shape[1])
    beta[0] = special.logit(np.clip(y.mean(), 1e-6, 1 - 1e-6))
    for _ in range(100):
        p = special.expit(design @ beta)
        gradient = design.T @ (y - p) - penalty * beta
        hessian = (design * (p * (1 - p))[:, None]).T @ design + np.diag(penalty)
        step = np.linalg.solve(hessian, gradient)
        beta += step
        if np.abs(step).max() < 1e-10:
            break
    else:
        raise RuntimeError("the renewal logit did not converge in 100 Newton steps")
    eta = design @ beta
    return beta, float(-np.logaddexp(0.0, np.where(y > 0, -eta, eta)).sum() - 0.5 * (penalty * beta**2).sum())


class Arrivals(BehaviourBlock):
    """How many nodes start their first-ever validator commitment each day: a negative binomial count.

    The variance is ``mean + mean**2 / dispersion``. A dispersion at its upper bound is a Poisson count.
    """

    reads = ()
    writes = ("arrived_commitments",)
    decision = "arrive"

    mean_per_day = behavioural(
        2.0, (0.0, 100.0), "assumed", "Mean daily count of first-ever validator commitments", "Placeholder until fitted by Arrivals.fit",
    )
    dispersion = behavioural(
        1e6, (1e-3, 1e6), "assumed", "Negative binomial dispersion. 1e6 is a Poisson count", "Placeholder until fitted by Arrivals.fit",
    )

    def sample(self, inputs, rng):
        mean = self.mean_per_day * float(inputs.get("scale", 1.0))
        if mean == 0.0:
            return 0
        k = self.dispersion
        return int(rng.negative_binomial(k, k / (k + mean)))

    def count_from_uniform(self, u: float, scale: float = 1.0) -> int:
        """The day's count by inversion of one uniform: the negative binomial quantile, or the Poisson quantile when the
        dispersion sits at its bound. Monotone in the mean, so a design with a higher mean never draws fewer."""
        mean = self.mean_per_day * float(scale)
        if mean == 0.0:
            return 0
        k = self.dispersion
        count = stats.poisson.ppf(u, mean) if k >= 1e6 else stats.nbinom.ppf(u, k, k / (k + mean))
        return max(0, int(count))

    def log_prob(self, inputs, decisions):
        counts = np.asarray(decisions)
        if counts.ndim != 1 or (counts < 0).any() or not np.equal(np.mod(counts, 1), 0).all():
            raise ValueError("decisions must be a one-dimensional array of non-negative whole counts")
        return _negative_binomial_log_prob(counts, self.mean_per_day, self.dispersion)

    @classmethod
    def fit(cls, counts: np.ndarray, evidence: str) -> Arrivals:
        """The mean is the sample mean, which is its maximum-likelihood value. The dispersion maximizes the
        likelihood on a log scale within its bounds."""
        counts = np.asarray(counts)
        mean = float(counts.mean())
        if mean == 0.0 or counts.var() <= mean:
            k = 1e6
        else:
            result = optimize.minimize_scalar(
                lambda log_k: -_negative_binomial_log_prob(counts, mean, float(np.exp(log_k))),
                bounds=(np.log(1e-3), np.log(1e6)), method="bounded",
            )
            k = float(np.exp(result.x))
        values = {"mean_per_day": min(mean, 100.0), "dispersion": k}
        provenance = {name: {"source": "fitted", "evidence": evidence, "value": value} for name, value in values.items()}
        return cls(provenance=provenance, **values)


def _negative_binomial_log_prob(counts: np.ndarray, mean: float, k: float) -> float:
    if mean == 0.0:
        return float("-inf") if counts.any() else 0.0
    log_p, log_q = np.log(k / (k + mean)), np.log(mean / (k + mean))
    return float(sum(lgamma(c + k) - lgamma(k) - lgamma(c + 1) + k * log_p + c * log_q for c in counts))


def return_cell(stake_navax, days_since_end) -> np.ndarray:
    """The hazard cell of each node out of the set: stake band times days since its last commitment ended.

    Nodes fewer than eight days out are still inside the renewal window and get -1, as do nodes past 365 days.
    """
    stake = np.asarray(stake_navax, dtype=float) / AVAX
    days = np.asarray(days_since_end)
    band = np.digitize(stake, RETURN_STAKE_EDGES, right=True)
    period = np.digitize(days, RETURN_DAY_EDGES, right=True)
    cell = band * 3 + period
    return np.where((days > RENEWAL_DAYS) & (days <= RETURN_DAYS), cell, -1)


def _hazard(name: str) -> object:
    stake, start, end = name.split("_")
    return behavioural(
        0.0, (0.0, 1.0), "assumed",
        f"Daily probability that a node with a {stake} stake returns between {start} and {end} days after its last commitment ended",
        "No returns until fitted by ReturnHazard.fit",
    )


class ReturnHazard(BehaviourBlock):
    """Whether a node that did not renew starts a new commitment today, after more than seven days out.

    Stake bands are the minimum (up to 2,100 AVAX), mid (to 100,000) and large. A node out for more than 365 days
    leaves the model, which bounds the set of nodes that can return (review note RD4's invariant).
    """

    reads = ("returning_nodes",)
    writes = ("returned_commitments",)
    decision = "return after more than seven days"

    minimum_8_30 = _hazard("minimum_8_30")
    minimum_31_90 = _hazard("minimum_31_90")
    minimum_91_365 = _hazard("minimum_91_365")
    mid_8_30 = _hazard("mid_8_30")
    mid_31_90 = _hazard("mid_31_90")
    mid_91_365 = _hazard("mid_91_365")
    large_8_30 = _hazard("large_8_30")
    large_31_90 = _hazard("large_31_90")
    large_91_365 = _hazard("large_91_365")

    def hazards(self) -> np.ndarray:
        return np.array([getattr(self, cell) for cell in RETURN_CELLS])

    def probability(self, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        cell = return_cell(inputs["stake_navax"], inputs["days_since_end"])
        return np.where(cell >= 0, self.hazards()[np.maximum(cell, 0)], 0.0)

    def sample(self, inputs, rng):
        p = self.probability(inputs)
        return rng.random(len(p)) < p

    def log_prob(self, inputs, decisions):
        decisions = _outcomes(decisions, len(inputs["stake_navax"]))
        p = self.probability(inputs)
        if (decisions & (p == 0)).any() or (~decisions & (p == 1)).any():
            return float("-inf")
        with np.errstate(divide="ignore"):
            return float(np.where(decisions, np.log(p), np.log1p(-p)).sum())

    @classmethod
    def fit(cls, stake_navax, days_out, returned, evidence: str) -> ReturnHazard:
        """Returns over node-days at risk in each cell, the maximum-likelihood daily hazard.

        ``days_out`` is how many days after its end each node was last seen out: the day it returned, or the day
        observation stopped. A node is at risk from day 8 to that day, capped at 365. A return after day 365 is a node
        that stayed out for the whole window, censored at 365, as the simulator drops it then.
        """
        stake = np.asarray(stake_navax)
        seen = np.asarray(days_out, dtype=np.int64)
        returned = np.asarray(returned, dtype=bool) & (seen <= RETURN_DAYS)
        days_out = np.minimum(seen, RETURN_DAYS)
        at_risk = np.zeros(len(RETURN_CELLS))
        events = np.zeros(len(RETURN_CELLS))
        band = np.digitize(np.asarray(stake, dtype=float) / AVAX, RETURN_STAKE_EDGES, right=True)
        for period, (low, high) in enumerate(((RENEWAL_DAYS, 30), (30, 90), (90, RETURN_DAYS))):
            exposure = np.clip(days_out - low, 0, high - low)
            np.add.at(at_risk, band * 3 + period, exposure)
            hit = returned & (days_out > low) & (days_out <= high)
            np.add.at(events, band * 3 + period, hit)
        rates = np.divide(events, at_risk, out=np.zeros_like(events), where=at_risk > 0)
        values = {cell: float(rate) for cell, rate in zip(RETURN_CELLS, rates)}
        provenance = {
            cell: {"source": "fitted", "evidence": f"{evidence}; {int(events[i])} returns in {int(at_risk[i])} node-days", "value": value}
            for i, (cell, value) in enumerate(values.items())
        }
        return cls(provenance=provenance, **values)


class Continuation:
    """The next duration and stake of a node that renews or returns, drawn from the same node moves before the origin.

    Durations come from a transition table: the next duration is drawn among moves whose previous duration fell in
    the same bin (up to 20, 21 to 40, 41 to 100, over 100 days), which keeps a node's habit. The stake is the
    previous stake times a ratio drawn among moves in the same stake band, one of nine log-spaced bands from 2,100 to
    2,000,000 AVAX, each move weighted by its previous stake, kept within the protocol's validator bounds of 2,000 and
    3,000,000 AVAX. On the training moves of the 19 development origins, with the bounds applied, this design puts the
    expected stake after a move a mean absolute 1.2% from the actual, against 1.8% for three bands unweighted and 4.3%
    for three bands weighted (review RV-20261005-03).
    """

    MIN_STAKE_NAVAX = 2_000 * AVAX
    MAX_STAKE_NAVAX = 3_000_000 * AVAX

    def __init__(self, previous_days, next_days, previous_stake_navax, next_stake_navax):
        self.previous_bin = np.digitize(np.asarray(previous_days), DURATION_EDGES, right=True)
        self.next_days = np.asarray(next_days, dtype=np.int64)
        previous_stake = np.asarray(previous_stake_navax, dtype=float)
        self.stake_band = np.digitize(previous_stake / AVAX, MOVE_STAKE_EDGES, right=True)
        self.ratio = np.asarray(next_stake_navax, dtype=float) / previous_stake
        self.weight = previous_stake
        if len(self.next_days) == 0:
            raise ValueError("a continuation table needs at least one observed move")

    def _draw(self, keys: np.ndarray, table_keys: np.ndarray, values: np.ndarray, rng, weights: np.ndarray | None = None) -> np.ndarray:
        out = np.empty(len(keys), dtype=values.dtype)
        for key in np.unique(keys):
            rows = keys == key
            match = table_keys == key if (table_keys == key).any() else np.ones(len(values), bool)
            p = None if weights is None else weights[match] / weights[match].sum()
            out[rows] = rng.choice(values[match], size=int(rows.sum()), p=p)
        return out

    def durations(self, previous_days: np.ndarray, rng) -> np.ndarray:
        keys = np.digitize(np.asarray(previous_days), DURATION_EDGES, right=True)
        return self._draw(keys, self.previous_bin, self.next_days, rng)

    def stakes(self, previous_stake_navax: np.ndarray, rng) -> np.ndarray:
        previous = np.asarray(previous_stake_navax, dtype=np.int64)
        keys = np.digitize(previous / AVAX, MOVE_STAKE_EDGES, right=True)
        ratio = self._draw(keys, self.stake_band, self.ratio, rng, self.weight)
        return np.clip(np.round(previous * ratio), self.MIN_STAKE_NAVAX, self.MAX_STAKE_NAVAX).astype(np.int64)

    def _pick(self, keys: np.ndarray, table_keys: np.ndarray, u: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
        """Table rows by inversion: for each uniform, the first row of its key's matches whose cumulative weight passes it."""
        n = len(table_keys)
        out = np.empty(len(keys), dtype=np.int64)
        for key in np.unique(keys):
            rows = keys == key
            match = np.flatnonzero(table_keys == key) if (table_keys == key).any() else np.arange(n)
            if weights is None:
                index = np.minimum((u[rows] * len(match)).astype(np.int64), len(match) - 1)
            else:
                cumulative = np.cumsum(weights[match])
                index = np.minimum(np.searchsorted(cumulative, u[rows] * cumulative[-1], side="right"), len(match) - 1)
            out[rows] = match[index]
        return out

    def durations_from_uniforms(self, previous_days: np.ndarray, u: np.ndarray) -> np.ndarray:
        """:meth:`durations` by inversion of one uniform per node, for keyed streams."""
        keys = np.digitize(np.asarray(previous_days), DURATION_EDGES, right=True)
        return self.next_days[self._pick(keys, self.previous_bin, np.asarray(u, dtype=float))]

    def stakes_from_uniforms(self, previous_stake_navax: np.ndarray, u: np.ndarray) -> np.ndarray:
        """:meth:`stakes` by inversion of one uniform per node, for keyed streams."""
        previous = np.asarray(previous_stake_navax, dtype=np.int64)
        keys = np.digitize(previous / AVAX, MOVE_STAKE_EDGES, right=True)
        ratio = self.ratio[self._pick(keys, self.stake_band, np.asarray(u, dtype=float), self.weight)]
        return np.clip(np.round(previous * ratio), self.MIN_STAKE_NAVAX, self.MAX_STAKE_NAVAX).astype(np.int64)
