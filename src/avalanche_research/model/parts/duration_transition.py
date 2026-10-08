"""The next commitment's duration for a node that renews or returns: a fitted transition between duration bands.

A node that starts another commitment chooses its duration band given the band of its last one, then the exact day
within that band. The bands are under 21 days, 21 to 45, 45 to 100, 100 to 200, and 200 to 365, each closed below
and open above. The band-to-band probabilities are fitted on the node moves before an origin. The exact day is drawn
from the band's own record of next durations in those moves, which keeps the heaps at 14, 15, 21, 28 to 31, 60, 90
and 365 days.

The fit is penalised likelihood under a Dirichlet prior centred on persistence, the forecast that the next band
repeats the last. Persistence is the benchmark the block must beat, so the prior makes the block equal to it when
there are no moves, and the data move each row away from it in proportion to how many moves that row has. The prior
weight, in moves per row, is the value on :data:`STRENGTH_GRID` with the highest marginal likelihood of the moves.

:func:`persistence_log_prob` scores the persistence forecast itself, with a floor so a change of band has a finite
log loss.

The fitted lifecycle reads the block through its ``durations`` setting. When set, a node that renews or returns
draws its next duration from it on the same keyed uniforms the continuation table reads, and its stake still comes
from the continuation table.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

import numpy as np
import pandas as pd
import param
from scipy import special

from avalanche_research.core.clock import LOCKBOX_START
from avalanche_research.model.parts.base import BehaviourBlock, behavioural

BAND_EDGES = (21, 45, 100, 200)
BANDS = ("d0_21", "d21_45", "d45_100", "d100_200", "d200_365")
BAND_LABELS = ("under 21 days", "21 to 45 days", "45 to 100 days", "100 to 200 days", "200 to 365 days")
# The day a band draws when the fitting window has no move into it: a whole number of weeks or months on the menu.
DEFAULT_DAYS = (14, 30, 90, 180, 365)
PERSISTENCE_FLOOR = 0.01
STRENGTH_GRID = (0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0, 3000.0)
LOCKBOX_US = int(LOCKBOX_START.timestamp() * 1_000_000)
US_PER_DAY = 86_400_000_000


def duration_band(days) -> np.ndarray:
    """The band of each duration in whole days: 0 is under 21 days, 4 is 200 days or more."""
    return np.digitize(np.asarray(days), BAND_EDGES)


def persistence_matrix(floor: float = PERSISTENCE_FLOOR) -> np.ndarray:
    """The persistence forecast as a transition matrix: the last band with probability ``1 - floor``, and the floor
    shared equally among the other four bands."""
    if not 0.0 < floor < 1.0:
        raise ValueError(f"the floor must lie strictly between 0 and 1, not {floor}")
    k = len(BANDS)
    return np.full((k, k), floor / (k - 1)) + np.eye(k) * (1.0 - floor - floor / (k - 1))


def persistence_log_prob(previous_days, next_days, floor: float = PERSISTENCE_FLOOR) -> float:
    """The log-likelihood of the next bands under persistence. With the default floor of 0.01, a repeated band scores
    log 0.99 and a change of band log 0.0025."""
    matrix = persistence_matrix(floor)
    return float(np.log(matrix[duration_band(previous_days), duration_band(next_days)]).sum())


def duration_moves(rows: pd.DataFrame, after_us: int, through_us: int) -> pd.DataFrame:
    """The node moves whose next commitment started after ``after_us`` and by ``through_us``.

    ``rows`` holds one commitment per row with its duration ``days``, end ``e`` and the node's next start ``next_s``
    and end ``next_e`` in microseconds, as the lifecycle's validator periods carry them. A commitment overlapped by the
    node's next one made no choice at its end and is left out. ``decided_us`` is the next commitment's start.
    """
    overlapped = rows["next_s"].notna() & (rows["next_s"] < rows["e"])
    moved = rows[rows["next_s"].notna() & ~overlapped & (rows["next_s"] > after_us) & (rows["next_s"] <= through_us)]
    return pd.DataFrame({
        "previous_days": moved["days"].to_numpy(dtype=np.int64),
        "next_days": ((moved["next_e"] - moved["next_s"]) / US_PER_DAY).round().clip(lower=1).to_numpy(dtype=np.int64),
        "decided_us": moved["next_s"].to_numpy(dtype=np.int64),
    })


def _dirichlet_evidence(counts: np.ndarray, prior: np.ndarray) -> float:
    """The log marginal likelihood of each row's counts under a Dirichlet prior with those pseudo-counts, summed."""
    return float((special.gammaln(prior.sum(axis=1)) - special.gammaln(counts.sum(axis=1) + prior.sum(axis=1))
                  + (special.gammaln(counts + prior) - special.gammaln(prior)).sum(axis=1)).sum())


def _whole_days(days, what: str) -> np.ndarray:
    """Durations as whole days from 1 to 365. Anything else is refused rather than truncated or kept."""
    values = np.asarray(days)
    if values.size and not (np.isfinite(values.astype(float)).all() and (values == np.round(values)).all()
                            and (values >= 1).all() and (values <= 365).all()):
        raise ValueError(f"{what} must be whole days from 1 to 365")
    return values.astype(np.int64)


class DurationTransition(BehaviourBlock):
    """The next duration band given the last, then the exact day from the band's own record.

    Each cell ``<from>_to_<to>`` is the probability of a move from one band to another. A row is normalised to sum to
    one when it is read, so a cell changed by ``with_value`` keeps the others in proportion. The class defaults are
    persistence at a floor of 0.01.
    """

    reads = ("continuing_nodes",)
    writes = ("next_durations",)
    decision = "duration band of the next commitment"

    # One parameter per cell of the transition matrix, declared in a loop over the bands.
    for _i, _a in enumerate(BANDS):
        for _j, _b in enumerate(BANDS):
            vars()[f"{_a}_to_{_b}"] = behavioural(
                float(persistence_matrix()[_i, _j]), (0.0, 1.0), "assumed",
                f"Probability that a node whose last commitment ran {BAND_LABELS[_i]} next commits {BAND_LABELS[_j]}",
                "Persistence with 1% spread over the other bands, until fitted by DurationTransition.fit",
            )
    del _i, _a, _j, _b

    prior_strength = behavioural(
        0.0, (0.0, 1e12), "assumed", "Moves' worth of weight on persistence in each row of the transition matrix",
        "No fit yet: the matrix is persistence itself",
    )
    floor = behavioural(
        PERSISTENCE_FLOOR, (1e-9, 0.5), "assumed", "Probability persistence spreads over the four bands a node did not last choose",
        "Small enough to leave persistence's forecast intact, large enough that a change of band has a finite log loss",
    )
    day_record = param.Array(default=None, allow_None=True, precedence=-1, doc="Next durations in whole days of the moves fitted on, sorted. None draws each band's default day")
    day_record_evidence = param.String(default="Each band's default day", doc="Where the day record came from")

    def matrix(self) -> np.ndarray:
        cells = np.array([[getattr(self, f"{a}_to_{b}") for b in BANDS] for a in BANDS], dtype=float)
        totals = cells.sum(axis=1, keepdims=True)
        if not (np.isfinite(totals).all() and (totals > 0).all()):
            raise ValueError("each band's transition row needs a positive, finite total")
        return cells / totals

    def probability(self, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        """One row of band probabilities per node, from its last duration ``previous_days``."""
        return self.matrix()[duration_band(inputs["previous_days"])]

    def bands_from_uniforms(self, previous_days, u) -> np.ndarray:
        """The next band by inversion of one uniform per node through its row's cumulative probabilities."""
        cumulative = np.cumsum(self.matrix(), axis=1)[duration_band(previous_days)]
        u = np.asarray(u, dtype=float)
        return np.minimum((u[:, None] >= cumulative).sum(axis=1), len(BANDS) - 1)

    def days_from_uniforms(self, previous_days, u) -> np.ndarray:
        """The next duration in whole days from one uniform per node: the band by inversion, then the uniform's
        position within that band's share picks the day from the band's sorted record. One uniform serves both, so
        the map from uniform to day never decreases, and a band with no record draws its default day."""
        u = np.asarray(u, dtype=float)
        rows = duration_band(previous_days)
        cumulative = np.cumsum(self.matrix(), axis=1)[rows]
        band = np.minimum((u[:, None] >= cumulative).sum(axis=1), len(BANDS) - 1)
        upper = cumulative[np.arange(len(u)), band]
        lower = upper - self.matrix()[rows, band]
        within = np.clip((u - lower) / np.maximum(upper - lower, 1e-300), 0.0, np.nextafter(1.0, 0.0))
        record = np.zeros(0, dtype=np.int64) if self.day_record is None else np.asarray(self.day_record, dtype=np.int64)
        record_band = duration_band(record)
        out = np.empty(len(u), dtype=np.int64)
        for b in np.unique(band):
            picked = band == b
            days = record[record_band == b]
            if len(days) == 0:
                out[picked] = DEFAULT_DAYS[b]
            else:
                out[picked] = days[np.minimum((within[picked] * len(days)).astype(np.int64), len(days) - 1)]
        return out

    def sample(self, inputs, rng):
        """Next durations in whole days, from one uniform per node drawn from ``rng``."""
        previous = np.asarray(inputs["previous_days"])
        return self.days_from_uniforms(previous, rng.random(len(previous)))

    def log_prob(self, inputs, decisions):
        """The log-likelihood of the observed next durations' bands. The exact day within a band is not scored."""
        previous = np.asarray(inputs["previous_days"])
        following = np.asarray(decisions)
        if following.ndim != 1 or len(following) != len(previous):
            raise ValueError(f"expected {len(previous)} next durations, one per input row, not shape {following.shape}")
        with np.errstate(divide="ignore"):
            return float(np.log(self.matrix()[duration_band(previous), duration_band(following)]).sum())

    @classmethod
    def fit(cls, previous_days, next_days, decided_us, evidence: str, prior_strength: float | None = None,
            floor: float = PERSISTENCE_FLOOR) -> DurationTransition:
        """The posterior mean of each row under a Dirichlet prior of ``prior_strength`` moves centred on persistence.

        Each row is its move counts plus ``prior_strength`` times persistence's row, over the row's moves plus
        ``prior_strength``: the mean of the Dirichlet posterior whose concentration is the counts plus the prior. With ``prior_strength`` None it is the value on :data:`STRENGTH_GRID` whose
        Dirichlet prior gives the moves the highest marginal likelihood. ``decided_us`` is when each move's next
        commitment started, in microseconds, and a move at or after 2025-11-19 16:00 UTC is refused.
        """
        previous, following = _whole_days(previous_days, "previous_days"), _whole_days(next_days, "next_days")
        decided = np.asarray(decided_us, dtype=np.int64)
        digest = hashlib.sha256(b"".join(a.tobytes() for a in (previous, following, decided))).hexdigest()
        evidence = f"{evidence}; inputs sha256 {digest}"
        if not len(previous) == len(following) == len(decided):
            raise ValueError("previous_days, next_days and decided_us need one value per move")
        if (decided >= LOCKBOX_US).any():
            raise ValueError("a move decided at or after 2025-11-19 16:00 UTC is in the held-back period and cannot be fitted on")
        k = len(BANDS)
        counts = np.zeros((k, k))
        np.add.at(counts, (duration_band(previous), duration_band(following)), 1)
        prior = persistence_matrix(floor)
        if prior_strength is None:
            strength = max(STRENGTH_GRID, key=lambda s: _dirichlet_evidence(counts, s * prior))
            strength_label = {"source": "fitted", "evidence": f"{evidence}; the highest marginal likelihood on {STRENGTH_GRID}"}
        else:
            strength = float(prior_strength)
            strength_label = {"source": "assumed", "evidence": f"Set by the caller of DurationTransition.fit on {evidence}"}
        matrix = (counts + strength * prior) / (counts.sum(axis=1, keepdims=True) + strength)
        values, provenance = {}, {}
        for i, a in enumerate(BANDS):
            for j, b in enumerate(BANDS):
                name, value = f"{a}_to_{b}", float(matrix[i, j])
                values[name] = value
                provenance[name] = {
                    "source": "fitted", "value": value,
                    "evidence": f"{evidence}; {int(counts[i, j])} of {int(counts[i].sum())} moves from {BAND_LABELS[i]}, "
                                f"with {strength:g} moves of prior weight on persistence at a floor of {floor:g}",
                }
        values |= {"prior_strength": float(strength), "floor": float(floor)}
        provenance["prior_strength"] = {**strength_label, "value": float(strength)}
        provenance["floor"] = {"source": "assumed", "value": float(floor), "evidence": f"Set by the caller of DurationTransition.fit on {evidence}"}
        return cls(provenance=provenance, day_record=np.sort(following), day_record_evidence=f"{evidence}; {len(following)} next durations", **values)

    def with_record(self, next_days=None, evidence: str = "Each band's default day") -> DurationTransition:
        """A copy with the same band probabilities whose day record is ``next_days``, sorted. None leaves it without
        one, so each band draws its default day."""
        current = {k: v for k, v in self.param.values().items() if k not in ("name", "day_record", "day_record_evidence")}
        record = None if next_days is None else np.sort(_whole_days(next_days, "a day record"))
        return type(self)(provenance=self._provenance, day_record=record, day_record_evidence=evidence, **current)


def fit_moves(moves: pd.DataFrame, decided_by_us: int, evidence: str) -> DurationTransition:
    """The transition fitted on a moves table with ``previous_days`` and ``next_days``, every move of which started by
    ``decided_by_us``, so a table that reaches 2025-11-19 16:00 UTC is refused. The block holds no day record: the
    fitted lifecycle draws the exact day from the moves of its own run."""
    decided = np.full(len(moves), decided_by_us, dtype=np.int64)
    return DurationTransition.fit(moves["previous_days"], moves["next_days"], decided, evidence).with_record()
