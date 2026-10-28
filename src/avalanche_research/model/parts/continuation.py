"""Continuation: the next duration and stake of a node that renews or returns.

Both are drawn from the node moves observed before the origin. They are tables, not fitted parameters.
"""

from __future__ import annotations

import numpy as np

from avalanche_research.model.parts.base import AVAX, DURATION_EDGES
from avalanche_research.model.parts.participation import cap_started
from avalanche_research.model.parts.returns import RETURN_STAKE_EDGES

# Log-spaced from 2,100 to 2,000,000 AVAX: the stake bands within which a moving node draws its stake ratio.
MOVE_STAKE_EDGES = tuple(float(x) for x in np.exp(np.linspace(np.log(2_100), np.log(2_000_000), 9)))

# The stake band sets a moving node can draw its stake ratio within, by name: the ten bands of MOVE_STAKE_EDGES, and
# the return block's three bands, up to 2,100 AVAX, to 100,000 AVAX and above it.
STAKE_BANDS = {"ten log-spaced": MOVE_STAKE_EDGES, "three": RETURN_STAKE_EDGES}


class Continuation:
    """The next duration and stake of a node that renews or returns, drawn from the same node moves before the origin.

    Durations come from a transition table: the next duration is drawn among moves whose previous duration fell in
    the same bin (up to 20, 21 to 40, 41 to 100, over 100 days), which keeps a node's habit. The stake is the
    previous stake times a ratio drawn among moves in the same stake band, one of ten bands split at nine log-spaced
    edges from 2,100 to 2,000,000 AVAX, each move weighted by its previous stake, kept within the protocol's validator
    bounds of 2,000 and 3,000,000 AVAX. On the training moves of the 19 development origins, with the bounds applied,
    this design puts the expected stake after a move a mean absolute 1.2% from the actual, against 1.8% for three bands
    unweighted and 4.3% for three bands weighted.

    ``stake_edges`` and ``stake_weighted`` choose those bands and that weight. Their defaults are the design above.
    """

    MIN_STAKE_NAVAX = 2_000 * AVAX
    MAX_STAKE_NAVAX = 3_000_000 * AVAX

    def __init__(self, previous_days, next_days, previous_stake_navax, next_stake_navax,
                 stake_edges: tuple[float, ...] = MOVE_STAKE_EDGES, stake_weighted: bool = True):
        self.previous_bin = np.digitize(np.asarray(previous_days), DURATION_EDGES, right=True)
        self.next_days = np.asarray(next_days, dtype=np.int64)
        previous_stake = np.asarray(previous_stake_navax, dtype=float)
        self.stake_edges = tuple(stake_edges)
        self.stake_band = np.digitize(previous_stake / AVAX, self.stake_edges, right=True)
        self.ratio = np.asarray(next_stake_navax, dtype=float) / previous_stake
        self.weight = previous_stake if stake_weighted else None
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
        keys = np.digitize(previous / AVAX, self.stake_edges, right=True)
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
        keys = np.digitize(previous / AVAX, self.stake_edges, right=True)
        ratio = self.ratio[self._pick(keys, self.stake_band, np.asarray(u, dtype=float), self.weight)]
        return np.clip(np.round(previous * ratio), self.MIN_STAKE_NAVAX, self.MAX_STAKE_NAVAX).astype(np.int64)


def continuation_stage(state, day, earlier) -> dict:
    """The daily continuation stage: every commitment that starts today, in the order renewed, returned, arrived.

    A renewed or returned node draws its next duration and stake from the continuation table, a first-ever node from
    the first-ever commitments, each by one uniform keyed by the node and its decision count. When the run has a
    duration transition, a renewed or returned node draws its next duration from it on the same uniforms instead.
    The started commitments then take their stake from the unstaked supply (parts.participation), which returns the
    renewal and return decisions the supply limit changed beside them.
    """
    blocks, draw = day.blocks, day.draw
    renewal, returns, arrivals = earlier["renewal"], earlier["returns"], earlier["arrivals"]
    ended, renews, comes_back = renewal["ended"], renewal["renews"], returns["comes_back"]
    n_new, new_key = arrivals["count"], arrivals["node_key"]
    continuation = blocks.continuation
    next_days = continuation.durations_from_uniforms if blocks.durations is None else blocks.durations.days_from_uniforms
    renewed_key, renewed_done = ended["node_key"][renews], ended["done"][renews]
    back_key, back_done = state["out_node_key"][comes_back], state["out_done"][comes_back]

    def pick(table: np.ndarray, purpose: str) -> np.ndarray:
        if not n_new:
            return np.zeros(0, dtype=np.int64)
        u = draw.uniforms(purpose, new_key)
        return table[np.minimum((u * len(table)).astype(np.int64), len(table) - 1)]

    started = {
        "stakes": np.concatenate([
            continuation.stakes_from_uniforms(ended["stakes"][renews], draw.uniforms("renew_stake", renewed_key, renewed_done)),
            continuation.stakes_from_uniforms(state["out_stakes"][comes_back], draw.uniforms("return_stake", back_key, back_done)),
            pick(blocks.first_stakes, "first_stake"),
        ]),
        "days": np.concatenate([
            next_days(ended["days"][renews], draw.uniforms("renew_days", renewed_key, renewed_done)),
            next_days(state["out_last_days"][comes_back], draw.uniforms("return_days", back_key, back_done)),
            pick(blocks.first_days, "first_days"),
        ]),
        "node_key": np.concatenate([renewed_key, back_key, new_key]),
        "done": np.concatenate([ended["done"][renews] + 1, state["out_done"][comes_back], np.zeros(n_new, dtype=np.int64)]),
        "after_return": np.concatenate([np.zeros(int(renews.sum()), bool), np.ones(int(comes_back.sum()), bool), np.zeros(n_new, bool)]),
        "returns": np.concatenate([ended["returns"][renews], state["out_returns"][comes_back] + 1, np.zeros(n_new, dtype=np.int64)]),
    }
    return cap_started(state, day, earlier, started, int(renews.sum()), int(comes_back.sum()))
