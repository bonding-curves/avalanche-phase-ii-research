"""Returns: whether a node that did not renew starts a new commitment, a daily hazard after more than seven days out.

The hazard is set by the node's stake band and the days since its last commitment ended, for up to 365 days. The
class default is no returns.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from avalanche_research.model.parts.base import (
    AVAX,
    RECORDED_MODULE,
    RENEWAL_DAYS,
    RETURN_DAYS,
    BehaviourBlock,
    _outcomes,
    behavioural,
)

# Ranges in whole days and AVAX. A value equal to a bound falls in the lower bin.
RETURN_STAKE_EDGES = (2_100, 100_000)
RETURN_DAY_EDGES = (30, 90)
RETURN_CELLS = tuple(
    f"{stake}_{days}" for stake in ("minimum", "mid", "large") for days in ("8_30", "31_90", "91_365")
)


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

    # Specification hashes record a block's class by module and name. The class keeps the module it was defined in
    # before the blocks were split into parts, so runs made before and after the split share their hashes.
    __module__ = RECORDED_MODULE

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


def returns_stage(state, day, earlier) -> dict:
    """The daily returns stage: one more day out for every node out of the set, and which of them return today, each
    by one uniform keyed by the node and the day. The return block reads each node's stake and days out, and may read
    its record: its completed commitments and how many of them were returns."""
    out_days = state["out_days"] + 1
    hazard = day.blocks.returns.probability({"stake_navax": state["out_stakes"], "days_since_end": out_days,
                                             "done": state["out_done"], "returns": state["out_returns"]})
    comes_back = day.draw.uniforms("returns", state["out_node_key"], day.t) < hazard
    return {"out_days": out_days, "comes_back": comes_back}
