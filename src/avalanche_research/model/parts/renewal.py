"""Renewal: whether an ending commitment renews on the same node within seven days.

A logit on the node's tenure, whether the ending commitment followed a return, the commitment's duration, its stake
and the node's own renewal record. The class default is one constant renewal probability.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from scipy import special

from avalanche_research.model.parts.base import (
    AVAX,
    DURATION_EDGES,
    RECORDED_MODULE,
    BehaviourBlock,
    _outcomes,
    behavioural,
)

# Ranges in whole days and AVAX. A value equal to a bound falls in the lower bin.
TENURE_BINS = ("1", "2", "3 to 6", "7 to 9", "10 or more")
RENEWAL_STAKE_EDGES = (2_100, 100_000, 1_000_000)

RENEWAL_TERMS = (
    "intercept", "tenure_2", "tenure_3_6", "tenure_7_9", "tenure_10_plus", "after_return",
    "days_21_40", "days_41_100", "days_over_100", "stake_2k_100k", "stake_100k_1m", "stake_over_1m", "node_record",
)
NODE_PRIOR_GRID = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0)


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

    # Specification hashes record a block's class by module and name. The class keeps the module it was defined in
    # before the blocks were split into parts, so runs made before and after the split share their hashes.
    __module__ = RECORDED_MODULE

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


ENDED = ("stakes", "done", "after_return", "days", "returns", "node_key")


def renewal_stage(state, day, earlier) -> dict:
    """The daily renewal stage: the commitments that end today, and which of them renew on the same node.

    A commitment handed on to its node's scheduled one makes no decision. Each decision inverts one uniform keyed by
    the node and its decision count through the renewal block, or through the large-holder block for a stake above
    the line, so a decision that differs between two designs moves no other node's draws.
    """
    blocks, settings = day.blocks, day.settings
    days_left = state["days_left"] - 1
    ending = days_left <= 0
    decide = ending & ~state["handed_on"]
    ended = {name: state[name][decide] for name in ENDED}
    decision_inputs = {
        "done": ended["done"], "after_return": ended["after_return"], "days": ended["days"],
        "stake_navax": ended["stakes"], "returns": ended["returns"],
        "shift": settings.renewal_response * day.renewal_gap + blocks.renewal_shift,
    }
    renews = day.draw.uniforms("renewal", ended["node_key"], ended["done"]) < blocks.renewal.probability(decision_inputs)
    if settings.large_navax is not None:
        large = ended["stakes"] > settings.large_navax
        large_inputs = {k: (v[large] if isinstance(v, np.ndarray) else v) for k, v in decision_inputs.items()}
        renews[large] = day.draw.uniforms("renewal_large", ended["node_key"][large], ended["done"][large]) < blocks.renewal_large.probability(large_inputs)
    return {"days_left": days_left, "ending": ending, "ended": ended, "renews": renews}
