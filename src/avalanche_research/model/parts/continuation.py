"""Continuation: the next duration and stake of a node that renews or returns.

Both are drawn from the node moves observed before the origin. They are tables, not fitted parameters.
"""

from __future__ import annotations

import numpy as np

from avalanche_research.model.parts.base import AVAX, DURATION_EDGES

# Log-spaced from 2,100 to 2,000,000 AVAX: the stake bands within which a moving node draws its stake ratio.
MOVE_STAKE_EDGES = tuple(float(x) for x in np.exp(np.linspace(np.log(2_100), np.log(2_000_000), 9)))


class Continuation:
    """The next duration and stake of a node that renews or returns, drawn from the same node moves before the origin.

    Durations come from a transition table: the next duration is drawn among moves whose previous duration fell in
    the same bin (up to 20, 21 to 40, 41 to 100, over 100 days), which keeps a node's habit. The stake is the
    previous stake times a ratio drawn among moves in the same stake band, one of nine log-spaced bands from 2,100 to
    2,000,000 AVAX, each move weighted by its previous stake, kept within the protocol's validator bounds of 2,000 and
    3,000,000 AVAX. On the training moves of the 19 development origins, with the bounds applied, this design puts the
    expected stake after a move a mean absolute 1.2% from the actual, against 1.8% for three bands unweighted and 4.3%
    for three bands weighted.
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
