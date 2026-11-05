"""Arrivals: how many nodes start their first-ever validator commitment each day, a negative binomial count.

The class default is a Poisson count.
"""

from __future__ import annotations

from math import lgamma

import numpy as np
from scipy import optimize, stats

from avalanche_research.model.parts.base import (
    RECORDED_MODULE,
    BehaviourBlock,
    behavioural,
)
from avalanche_research.model.parts.participation import (
    participation_scale,
    unstaked_share,
)
from avalanche_research.model.streams import KIND_ARRIVAL, node_keys


class Arrivals(BehaviourBlock):
    """How many nodes start their first-ever validator commitment each day: a negative binomial count.

    The variance is ``mean + mean**2 / dispersion``. A dispersion at its upper bound is a Poisson count.
    """

    # Specification hashes record a block's class by module and name. The class keeps the module it was defined in
    # before the blocks were split into parts, so runs made before and after the split share their hashes.
    __module__ = RECORDED_MODULE

    reads = ()
    writes = ("arrived_commitments",)
    decision = "arrive"

    mean_per_day = behavioural(
        2.0, (0.0, 100.0), "assumed", "Mean daily count of first-ever validator commitments", "Placeholder until fitted by Arrivals.fit",
    )
    dispersion = behavioural(
        1e6, (1e-3, 1e6), "assumed", "Negative binomial dispersion. 1e6 is a Poisson count", "Placeholder until fitted by Arrivals.fit",
    )

    MAX_MEAN_PER_DAY = 100.0

    def scaled_mean(self, scale: float = 1.0) -> float:
        """The day's mean after the entry response's scale, capped at 100 a day as v0.7 capped its entry rate. Drawing and
        scoring both read it, so ``sample``, ``count_from_uniform`` and ``log_prob`` share one definition."""
        scale = float(scale)
        if not np.isfinite(scale) or scale < 0.0:
            raise ValueError(f"an arrival scale must be finite and non-negative, not {scale}")
        return min(self.MAX_MEAN_PER_DAY, self.mean_per_day * scale)

    def sample(self, inputs, rng):
        mean = self.scaled_mean(inputs.get("scale", 1.0))
        if mean == 0.0:
            return 0
        k = self.dispersion
        return int(rng.negative_binomial(k, k / (k + mean)))

    def count_from_uniform(self, u: float, scale: float = 1.0) -> int:
        """The day's count by inversion of one uniform: the negative binomial quantile, or the Poisson quantile when the
        dispersion sits at its bound. Monotone in the mean, so a design with a higher mean never draws fewer."""
        mean = self.scaled_mean(scale)
        if mean == 0.0:
            return 0
        k = self.dispersion
        count = stats.poisson.ppf(u, mean) if k >= 1e6 else stats.nbinom.ppf(u, k, k / (k + mean))
        return max(0, int(count))

    def log_prob(self, inputs, decisions):
        counts = np.asarray(decisions)
        if counts.ndim != 1 or (counts < 0).any() or not np.equal(np.mod(counts, 1), 0).all():
            raise ValueError("decisions must be a one-dimensional array of non-negative whole counts")
        return _negative_binomial_log_prob(counts, self.scaled_mean(inputs.get("scale", 1.0)), self.dispersion)

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


def arrivals_stage(state, day, earlier) -> dict:
    """The daily arrivals stage: the count of first-ever nodes today, from one uniform keyed by the day with the entry
    response to the yield gap, the market's entry shift and the participation feedback on the unstaked share of supply,
    and their node keys."""
    settings = day.settings
    scale = float(np.exp(settings.entry_response * day.entry_gap + settings.market_entry_shift))
    scale *= participation_scale(unstaked_share(state), settings.unstaked_share0, settings.participation_elasticity)
    count = day.blocks.arrivals.count_from_uniform(float(day.draw.uniforms("arrivals", day.t)[0]), scale)
    return {"count": count, "node_key": node_keys(KIND_ARRIVAL, day.t, np.arange(count))}
