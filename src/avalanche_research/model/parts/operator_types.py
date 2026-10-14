"""Operator types: latent classes of operator, each an intercept shift on the renewal logit.

The base is the lifecycle's own renewal logit. A node belongs to each of ``K`` classes with the posterior weights of
its operator, held fixed through the forecast, and its renewal probability is the mixture over classes of the base
logit shifted by the class's intercept: ``P = sum_k w_k expit(eta + shift_k)``. A node with no posterior takes the class
shares of the entrants of the year before the origin. With one class and no shift the stage is the plain renewal stage.

:meth:`ClassShift.fit` fits the shifts on training endings with the posteriors as weights, the maximum of the weighted
Bernoulli log-likelihood, one concave problem per class. It fits no class model and selects no ``K``: those come from
outside, with the posteriors.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
import param
from scipy import special

from avalanche_research.model.parts.base import BehaviourBlock
from avalanche_research.model.parts.renewal import ENDED

MAX_CLASSES = 4
SHIFT_CLIP = 20.0


def _shares(values, what: str) -> np.ndarray:
    shares = np.asarray(values, dtype=float)
    if shares.ndim != 1 or not len(shares) or (shares < 0).any() or not np.isfinite(shares).all() or abs(shares.sum() - 1.0) > 1e-9:
        raise ValueError(f"{what} must be non-negative shares that sum to one")
    return shares


class ClassShift(BehaviourBlock):
    """``K`` operator classes as intercept shifts on the renewal logit, with the class shares of new entrants.

    ``shifts`` holds one log-odds shift per class and ``entrant_shares`` the share of each class among new entrants,
    which a node without a posterior takes. One class with a zero shift, the default, leaves renewal unchanged.
    """

    reads = ("ending_commitments",)
    writes = ("renewed_commitments",)
    decision = "renewal shift by operator class"

    shifts = param.List(
        default=[0.0], item_type=float, bounds=(1, MAX_CLASSES), metadata={"source": "assumed", "evidence": "One class with no shift until fitted by ClassShift.fit"},
        doc="Log-odds shift of renewal for each class",
    )
    entrant_shares = param.List(
        default=[1.0], item_type=float, bounds=(1, MAX_CLASSES), metadata={"source": "assumed", "evidence": "One class until class shares of entrants are observed"},
        doc="Share of each class among the entrants of the year before the origin, taken by a node with no posterior",
    )

    def __init__(self, **params):
        super().__init__(**params)
        if len(self.shifts) != len(self.entrant_shares):
            raise ValueError("shifts and entrant_shares need one value per class")
        _shares(self.entrant_shares, "entrant_shares")
        if (np.abs(np.asarray(self.shifts, dtype=float)) > SHIFT_CLIP).any():
            raise ValueError(f"a class shift is held within ±{SHIFT_CLIP:g} log-odds")

    @property
    def classes(self) -> int:
        return len(self.shifts)

    def probability(self, eta: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """Each ending's renewal probability: the mixture over classes of the shifted base log-odds ``eta``, with the
        ending's class weights, one row per ending and one column per class."""
        eta, weights = np.asarray(eta, dtype=float), np.asarray(weights, dtype=float)
        if weights.shape != (len(eta), self.classes):
            raise ValueError(f"class weights must be {len(eta)} by {self.classes}, not {weights.shape}")
        return (weights * special.expit(eta[:, None] + np.asarray(self.shifts, dtype=float)[None, :])).sum(axis=1)

    def sample(self, inputs, rng):
        return rng.random(len(inputs["eta"])) < self.probability(inputs["eta"], inputs["weights"])

    def log_prob(self, inputs, decisions):
        p = self.probability(inputs["eta"], inputs["weights"])
        y = np.asarray(decisions, dtype=bool)
        if y.shape != p.shape:
            raise ValueError(f"expected {len(p)} decisions, not shape {y.shape}")
        with np.errstate(divide="ignore"):
            return float(np.where(y, np.log(p), np.log1p(-p)).sum())

    @classmethod
    def fit(cls, eta: np.ndarray, decisions: np.ndarray, weights: np.ndarray, evidence: str, entrant_shares=None) -> ClassShift:
        """The shifts that maximise the weighted Bernoulli log-likelihood of ``decisions`` given the base log-odds
        ``eta``, each ending weighted by its class posterior, one column per class. Each class is one concave problem in
        its shift, solved by Newton steps from zero and held within ±20. A class with no weight keeps a zero shift,
        labelled as the prior's. ``entrant_shares`` defaults to the mean posterior."""
        eta, weights = np.asarray(eta, dtype=float), np.asarray(weights, dtype=float)
        y = np.asarray(decisions, dtype=bool).astype(float)
        if weights.ndim != 2 or weights.shape[0] != len(eta) or len(y) != len(eta) or not len(eta):
            raise ValueError("fit needs one base log-odds, one decision and one row of class weights per ending")
        if (weights < 0).any():
            raise ValueError("class weights cannot be negative")
        k = weights.shape[1]
        shifts, provenance = [], {}
        for j in range(k):
            w = weights[:, j]
            if w.sum() == 0:
                shifts.append(0.0)
                continue
            delta = 0.0
            for _ in range(100):
                p = special.expit(eta + delta)
                gradient = float((w * (y - p)).sum())
                curvature = float((w * p * (1 - p)).sum())
                if curvature <= 0:
                    break
                step = gradient / curvature
                delta = float(np.clip(delta + step, -SHIFT_CLIP, SHIFT_CLIP))
                if abs(step) < 1e-10 or abs(delta) >= SHIFT_CLIP:
                    break
            shifts.append(delta)
        shares = _shares(entrant_shares if entrant_shares is not None else weights.mean(axis=0) / weights.mean(axis=0).sum(), "entrant_shares").tolist()
        provenance["shifts"] = {"source": "fitted", "value": shifts, "evidence": f"{evidence}; {len(y)} endings, {k} classes"}
        provenance["entrant_shares"] = {"source": "observed moment" if entrant_shares is not None else "fitted", "value": shares,
                                        "evidence": f"{evidence}; mean posterior over the endings" if entrant_shares is None else evidence}
        return cls(provenance=provenance, shifts=shifts, entrant_shares=shares)


def posterior_lookup(table: pd.DataFrame | None, types: ClassShift) -> tuple[np.ndarray, np.ndarray]:
    """``(keys, weights)``: the node keys of ``table`` sorted, and each one's class weights, one row per key, checked
    to be shares over ``types.classes`` classes. An empty table gives empty arrays, so every node takes the entrant
    shares."""
    columns = [f"w_{j}" for j in range(types.classes)]
    if table is None or not len(table):
        return np.zeros(0, dtype=np.int64), np.zeros((0, types.classes))
    missing = [c for c in ["node_key", *columns] if c not in table]
    if missing:
        raise ValueError(f"type_posteriors need the columns {', '.join(missing)}")
    keys = np.asarray(table["node_key"], dtype=np.int64)
    if len(set(keys.tolist())) != len(keys):
        raise ValueError("each node has one row of type_posteriors")
    weights = table[columns].to_numpy(dtype=float)
    if (weights < 0).any() or (np.abs(weights.sum(axis=1) - 1.0) > 1e-9).any():
        raise ValueError("each row of type_posteriors must be non-negative shares that sum to one")
    order = np.argsort(keys, kind="stable")
    return keys[order], weights[order]


def class_weights(node_keys: np.ndarray, posteriors: tuple[np.ndarray, np.ndarray], types: ClassShift) -> np.ndarray:
    """Each node's class weights: its row of the posteriors when it has one, else the entrant shares."""
    keys, weights = posteriors
    out = np.tile(np.asarray(types.entrant_shares, dtype=float), (len(node_keys), 1))
    if len(keys) and len(node_keys):
        at = np.minimum(np.searchsorted(keys, node_keys), len(keys) - 1)
        found = keys[at] == node_keys
        out[found] = weights[at[found]]
    return out


def typed_renewal_stage(state, day, earlier, *, types: ClassShift, posteriors: tuple[np.ndarray, np.ndarray]) -> dict:
    """The renewal stage with each ending node's log-odds shifted by its operator class: the base block's log-odds,
    the yield-gap response and the run's renewal shift as in the plain stage, then the class mixture. The same keyed
    uniform decides, so with one class and no shift the decisions are the plain stage's."""
    blocks, settings = day.blocks, day.settings
    days_left = state["days_left"] - 1
    ending = days_left <= 0
    decide = ending & ~state["handed_on"]
    ended = {name: state[name][decide] for name in ENDED}
    inputs = {"done": ended["done"], "after_return": ended["after_return"], "days": ended["days"],
              "stake_navax": ended["stakes"], "returns": ended["returns"]}
    shift = settings.renewal_response * day.renewal_gap + blocks.renewal_shift
    weights = class_weights(ended["node_key"], posteriors, types)

    def probability(block, rows):
        picked = {k: v[rows] for k, v in inputs.items()}
        eta = block.design(picked) @ block.coefficients() + shift
        return types.probability(eta, weights[rows])

    everyone = np.ones(len(ended["done"]), dtype=bool)
    renews = day.draw.uniforms("renewal", ended["node_key"], ended["done"]) < probability(blocks.renewal, everyone)
    if settings.large_navax is not None:
        large = ended["stakes"] > settings.large_navax
        renews[large] = day.draw.uniforms("renewal_large", ended["node_key"][large], ended["done"][large]) < probability(blocks.renewal_large, large)
    return {"days_left": days_left, "ending": ending, "ended": ended, "renews": renews}


def eta_of(block, inputs: Mapping[str, np.ndarray], shift: float = 0.0) -> np.ndarray:
    """The base log-odds a renewal block gives ``inputs``, as the typed stage reads them, for fitting the shifts."""
    return block.design(inputs) @ block.coefficients() + shift
