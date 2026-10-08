"""The delegation blocks: how many delegations start each day, and which validator each one goes to.

* :class:`DelegationFlow`: the day's count of new delegations, a Poisson count, and the share of them made by
  BENQI's funding address, a binomial split.
* :class:`DelegatorChoice`: the validator a delegator other than BENQI chooses among the eligible ones, a conditional
  logit on the validator's delegation fee and the log of its remaining delegation capacity.
* :class:`BenqiAllocation`: the validator BENQI delegates to among the eligible validators of its own set, with
  probability proportional to remaining capacity raised to a power.

Each block offers ``sample`` for the simulator and ``log_prob`` for the estimator, as every block does, a ``fit``
class method that returns an instance whose every parameter is labelled ``fitted``, and an inversion method that
turns one keyed uniform into a decision, so the simulator draws only through ``model.streams``. The class defaults
are placeholders: no delegations, choices that ignore fee and capacity, and BENQI weighting by capacity.

A choice set is in long form: one row per eligible validator, ``choice_set`` naming the set each row belongs to,
and one chosen row per set. A single set may leave ``choice_set`` out.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from scipy import optimize, stats

from avalanche_research.model.blocks import BehaviourBlock, _outcomes, behavioural

AVAX = 10**9
SHARES_PER_UNIT = 1_000_000


class DelegationFlow(BehaviourBlock):
    """How many delegations start each day, and how many of them are BENQI's.

    ``sample`` draws one day as ``[count, benqi_count]``. ``log_prob`` scores days in that form: a Poisson count
    and a binomial BENQI split. ``scale`` in the inputs multiplies the mean, as a response would.
    """

    reads = ()
    writes = ("new_delegations",)
    decision = "delegate"

    mean_per_day = behavioural(
        0.0, (0.0, 100_000.0), "assumed", "Mean daily count of new delegations", "No delegations until fitted by DelegationFlow.fit",
    )
    benqi_share = behavioural(
        0.0, (0.0, 1.0), "assumed", "Share of new delegations made by BENQI's funding address",
        "No BENQI delegations until fitted by DelegationFlow.fit",
    )

    def scaled_mean(self, scale: float = 1.0) -> float:
        scale = float(scale)
        if not np.isfinite(scale) or scale < 0.0:
            raise ValueError(f"a flow scale must be finite and non-negative, not {scale}")
        return self.mean_per_day * scale

    def count_from_uniform(self, u: float, scale: float = 1.0) -> int:
        """The day's count by inversion of one uniform, monotone in the mean."""
        mean = self.scaled_mean(scale)
        return 0 if mean == 0.0 else max(0, int(stats.poisson.ppf(u, mean)))

    def benqi_from_uniforms(self, u: np.ndarray) -> np.ndarray:
        """Whether each new delegation is BENQI's, one uniform each."""
        return np.asarray(u, dtype=float) < self.benqi_share

    def sample(self, inputs, rng):
        count = self.count_from_uniform(rng.random(), inputs.get("scale", 1.0))
        return np.array([count, int(self.benqi_from_uniforms(rng.random(count)).sum())])

    def log_prob(self, inputs, decisions):
        days = np.asarray(decisions)
        if days.ndim != 2 or days.shape[1] != 2 or (days < 0).any() or (days[:, 1] > days[:, 0]).any():
            raise ValueError("decisions must be rows of [count, benqi_count] with 0 <= benqi_count <= count")
        mean = self.scaled_mean(inputs.get("scale", 1.0))
        counts, benqi = days[:, 0], days[:, 1]
        if mean == 0.0:
            count_part = float("-inf") if counts.any() else 0.0
        else:
            count_part = float(stats.poisson.logpmf(counts, mean).sum())
        return count_part + float(stats.binom.logpmf(benqi, counts, self.benqi_share).sum())

    @classmethod
    def fit(cls, counts: np.ndarray, benqi_counts: np.ndarray, evidence: str) -> DelegationFlow:
        """The sample mean and the pooled BENQI share, each its maximum-likelihood value."""
        counts, benqi = np.asarray(counts), np.asarray(benqi_counts)
        total = int(counts.sum())
        values = {"mean_per_day": float(counts.mean()), "benqi_share": float(benqi.sum() / total) if total else 0.0}
        provenance = {name: {"source": "fitted", "evidence": f"{evidence}; {total} delegations in {len(counts)} days", "value": value}
                      for name, value in values.items()}
        return cls(provenance=provenance, **values)


def _set_ids(inputs: Mapping[str, np.ndarray]) -> np.ndarray:
    n = len(inputs["remaining_navax"])
    sets = inputs.get("choice_set")
    return np.zeros(n, dtype=np.int64) if sets is None else np.unique(np.asarray(sets), return_inverse=True)[1]


def _group_log_softmax(utility: np.ndarray, sets: np.ndarray) -> np.ndarray:
    top = np.full(sets.max() + 1, -np.inf)
    np.maximum.at(top, sets, utility)
    shifted = utility - top[sets]
    total = np.zeros(len(top))
    np.add.at(total, sets, np.exp(shifted))
    return shifted - np.log(total[sets])


class _ConditionalChoice(BehaviourBlock):
    """A conditional logit over one choice set per decision: utility is ``design(inputs) @ coefficients``."""

    reads = ("eligible_validators",)
    terms: tuple[str, ...] = ()

    def design(self, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        raise NotImplementedError

    def coefficients(self) -> np.ndarray:
        return np.array([getattr(self, term) for term in self.terms], dtype=float)

    def probabilities(self, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        """Each row's probability of being chosen within its set."""
        return np.exp(_group_log_softmax(self.design(inputs) @ self.coefficients(), _set_ids(inputs)))

    def choose_from_uniform(self, inputs: Mapping[str, np.ndarray], u: float) -> int:
        """The chosen row of a single set by inversion of one uniform: the first whose cumulative probability passes it."""
        cumulative = np.cumsum(self.probabilities(inputs))
        return int(min(np.searchsorted(cumulative, u * cumulative[-1], side="right"), len(cumulative) - 1))

    def sample(self, inputs, rng):
        sets = _set_ids(inputs)
        p = self.probabilities(inputs)
        chosen = np.zeros(len(sets), dtype=bool)
        for s in range(sets.max() + 1):
            rows = np.flatnonzero(sets == s)
            cumulative = np.cumsum(p[rows])
            chosen[rows[min(np.searchsorted(cumulative, rng.random() * cumulative[-1], side="right"), len(rows) - 1)]] = True
        return chosen

    def log_prob(self, inputs, decisions):
        sets = _set_ids(inputs)
        chosen = _outcomes(decisions, len(sets))
        if np.bincount(sets[chosen], minlength=sets.max() + 1).tolist() != [1] * (sets.max() + 1):
            raise ValueError("each choice set needs exactly one chosen row")
        return float(_group_log_softmax(self.design(inputs) @ self.coefficients(), sets)[chosen].sum())

    @classmethod
    def fit(cls, inputs: Mapping[str, np.ndarray], decisions: np.ndarray, evidence: str):
        """The maximum-likelihood coefficients, by BFGS on the concave log-likelihood with its exact gradient."""
        sets = _set_ids(inputs)
        chosen = _outcomes(decisions, len(sets))
        x = cls().design(inputs)

        def negative(beta):
            log_p = _group_log_softmax(x @ beta, sets)
            expected = np.zeros((sets.max() + 1, x.shape[1]))
            np.add.at(expected, sets, np.exp(log_p)[:, None] * x)
            return -float(log_p[chosen].sum()), -(x[chosen].sum(axis=0) - expected.sum(axis=0))

        result = optimize.minimize(negative, np.zeros(x.shape[1]), jac=True, method="BFGS")
        values = {}
        for term, b in zip(cls.terms, result.x):
            low, high = cls.param[term].bounds
            values[term] = float(np.clip(b, low, high))
        provenance = {term: {"source": "fitted", "evidence": f"{evidence}; {sets.max() + 1} choices over {len(sets)} rows", "value": value}
                      for term, value in values.items()}
        return cls(provenance=provenance, **values)


def _log_capacity(inputs: Mapping[str, np.ndarray]) -> np.ndarray:
    remaining = np.asarray(inputs["remaining_navax"], dtype=float) / AVAX
    if (remaining <= 0).any():
        raise ValueError("every eligible validator needs positive remaining capacity")
    return np.log(remaining)


class DelegatorChoice(_ConditionalChoice):
    """The validator a delegator other than BENQI chooses: utility = fee * fee share + log_capacity * log capacity.

    The inputs are each eligible validator's delegation fee in millionths, ``fee_shares``, and its remaining
    capacity in nAVAX, ``remaining_navax``: the most it can still take before its delegation limit.
    """

    writes = ("delegations",)
    decision = "choose a validator to delegate to"
    terms = ("fee", "log_capacity")

    fee = behavioural(
        0.0, (-1_000.0, 1_000.0), "assumed", "Utility per unit of delegation fee as a share of the reward (0.02 is 2%)",
        "No effect until fitted by DelegatorChoice.fit",
    )
    log_capacity = behavioural(
        0.0, (-50.0, 50.0), "assumed", "Utility per unit of the log of remaining delegation capacity in AVAX",
        "No effect until fitted by DelegatorChoice.fit",
    )

    def design(self, inputs):
        fee = np.asarray(inputs["fee_shares"], dtype=float) / SHARES_PER_UNIT
        return np.column_stack([fee, _log_capacity(inputs)])


class BenqiAllocation(_ConditionalChoice):
    """The validator BENQI delegates to among the eligible ones of its set: probability proportional to remaining
    capacity to the power ``capacity_power``. The inputs are ``remaining_navax`` for each eligible validator."""

    writes = ("benqi_delegations",)
    decision = "allocate a BENQI delegation"
    terms = ("capacity_power",)

    capacity_power = behavioural(
        1.0, (-50.0, 50.0), "assumed", "Power of remaining capacity in BENQI's allocation weights. 1 weights by capacity",
        "Placeholder, weighting by capacity, until fitted by BenqiAllocation.fit",
    )

    def design(self, inputs):
        return _log_capacity(inputs)[:, None]

