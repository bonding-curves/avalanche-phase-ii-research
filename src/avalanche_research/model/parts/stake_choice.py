"""Empirical stake hurdle and its discrete observable-cell score.

Synthetic candidate: the evidence label contract is proposed, not an accepted
source adapter. Labels bind ordered input rows, not their truth or origin.
Only fit tables construct a block. One supplied uniform serves each choice.
Float64 interpolation is bounded by fitted legal stake ratios (log 1500).
The score integrates the actual floor/clamp sampler by float64 bisection to
machine resolution. It is a cell probability, never a continuous density.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from types import MappingProxyType

import numpy as np
import pandas as pd

from avalanche_research.core.clock import LOCKBOX_START
from avalanche_research.model.parts.base import AVAX, BehaviourBlock
from avalanche_research.model.parts.continuation import MOVE_STAKE_EDGES
from avalanche_research.model.parts.duration_transition import duration_band

MIN_STAKE = 2_000 * AVAX
MAX_STAKE = 3_000_000 * AVAX
CONTEXTS = ("renewal", "return", "entry")
FIT_COLUMNS = ("previous_stake_navax", "next_days", "next_stake_navax", "decided_us")
LOG_EDGES = np.array([(k - 50) / 10.0 for k in range(101)], dtype=np.float64)
SCORE_FLOOR = 1e-12
US_PER_DAY = 86_400_000_000
LOCKBOX_US = int(LOCKBOX_START.timestamp()) * 1_000_000
_LABEL = re.compile(r"([^;\n]+); origin (\d{4}-\d{2}-\d{2}); 365 days; sha256 ([0-9a-f]{64})\Z")


def table_sha256(table: pd.DataFrame) -> str:
    """Proposed adapter encoding: compact UTF-8 JSON columns and ordered rows."""
    payload = {"columns": list(table.columns),
               "rows": [list(row) for row in table.itertuples(index=False, name=None)]}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, allow_nan=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def _has_bool(value):
    if isinstance(value, (bool, np.bool_)):
        return True
    if isinstance(value, (pd.Series, np.ndarray)):
        if value.dtype.kind == "b":
            return bool(value.size)
        if value.dtype.kind == "O":
            return any(_has_bool(v) for v in np.asarray(value).flat)
        return False
    return isinstance(value, (tuple, list)) and any(_has_bool(v) for v in value)


def _masked(value):
    if np.ma.isMaskedArray(value):
        return True
    return isinstance(value, (tuple, list)) and any(_masked(v) for v in value)


def _vector(value, name):
    if _has_bool(value):
        raise ValueError(f"{name}: Boolean values refused before coercion")
    if _masked(value):
        raise ValueError(f"{name}: masked arrays refused")
    try:
        a = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: one-dimensional numeric vector required") from exc
    if a.ndim != 1:
        raise ValueError(f"{name}: one-dimensional vector required")
    return a


def _integers(value, name):
    a = _vector(value, name)
    if a.size == 0:
        return np.empty(0, dtype=np.int64)
    if a.dtype.kind not in "iu" or (a.dtype.kind == "u" and (a > np.iinfo(np.int64).max).any()):
        raise ValueError(f"{name}: int64-compatible integer values required")
    return a.astype(np.int64, copy=False)


def _inputs(context, previous, days):
    previous = _integers(previous, "previous_stake_navax")
    days = _integers(days, "next_days")
    if len(previous) != len(days):
        raise ValueError("previous stake and next days need equal lengths")
    if isinstance(context, str):
        if context not in CONTEXTS:
            raise ValueError("context must be renewal, return or entry")
        contexts = np.full(len(days), context, dtype=object)
    else:
        contexts = _vector(context, "context")
        if len(contexts) != len(days) or any(not isinstance(c, str) or c not in CONTEXTS for c in contexts):
            raise ValueError("one legal context required per row")
    if ((days < 1) | (days > 365)).any():
        raise ValueError("next_days must be whole days in 1..365")
    entry = contexts == "entry"
    if (previous[entry] != 0).any() or ((previous[~entry] < MIN_STAKE) | (previous[~entry] > MAX_STAKE)).any():
        raise ValueError("previous stake must be 0 at entry and within legal bounds otherwise")
    return contexts, previous, days


def _stake_band(previous):
    return np.digitize(previous / AVAX, MOVE_STAKE_EDGES, right=True)


def _quantiles(knots, v):
    """Portable float64 interpolation, no extrapolation or FMA requirement."""
    if len(knots) == 1:
        return np.full(np.shape(v), knots[0], dtype=np.float64)
    position = np.asarray(v, dtype=np.float64) * (len(knots) - 1)
    left = np.minimum(position.astype(np.int64), len(knots) - 2)
    fraction = position - left
    a = np.asarray(knots, dtype=np.float64)
    return np.clip(a[left] + fraction * (a[left + 1] - a[left]), a[left], a[left + 1])


def _changed(knots, reference, v):
    # Legal ratios are bounded, so exp and the product cannot overflow.
    stake = np.floor(reference * np.exp(_quantiles(knots, v)))
    return np.clip(stake, MIN_STAKE, MAX_STAKE).astype(np.int64)


def _cell_ids(reference, stakes):
    ids = 1 + np.searchsorted(LOG_EDGES, np.log(stakes / reference), side="right")
    return np.where(stakes == reference, 0, ids).astype(np.int64)


def _integer_edges(reference):
    """First legal integer stake in each log bin, using the score's own log."""
    low = np.full(101, MIN_STAKE, dtype=np.int64)
    high = np.full(101, MAX_STAKE + 1, dtype=np.int64)
    while (low < high).any():
        mid = low + (high - low) // 2
        below = np.log(mid / reference) < LOG_EDGES
        active = low < high
        low = np.where(active & below, mid + 1, low)
        high = np.where(active & ~below, mid, high)
    return low


def _cdf_stake(knots, reference, thresholds):
    """Measure of v whose floored/clamped changed stake is below thresholds.

    Only the changed branch is monotone. Endpoints, ties and singletons use
    the sampler itself. Sixty bisections leave at most float64 spacing error.
    """
    thresholds = np.asarray(thresholds, dtype=np.int64)
    low = np.zeros(len(thresholds), dtype=np.float64)
    high = np.ones(len(thresholds), dtype=np.float64)
    for _ in range(60):
        mid = low + (high - low) * 0.5
        below = _changed(knots, reference, mid) < thresholds
        low = np.where(below, mid, low)
        high = np.where(below, high, mid)
    result = (low + high) * 0.5
    first = _changed(knots, reference, np.array([0.]))[0]
    last = _changed(knots, reference, np.array([np.nextafter(1., 0.)]))[0]
    return np.where(thresholds <= first, 0., np.where(thresholds > last, 1., result))


def _smooth(mass):
    mass = np.where(mass > 0.0, mass, SCORE_FLOOR)
    return mass / math.fsum(float(x) for x in mass)


@dataclass(frozen=True)
class _Cell:
    p: float
    knots: tuple[float, ...]
    scope: str
    count: int
    changes: int
    knot_count: int
    label: str
    knot_source: str


class StakeChoice(BehaviourBlock):
    """Fit-only empirical hurdle, with 50-change pooling within each context.

    Evidence is exactly context -> '<run>; origin YYYY-MM-DD; 365 days;
    sha256 <table hash>'. The three labels must share run and origin. Origin
    ends at 23:59:59 UTC, matching the established training clock. This label
    schema is provisional. It does not authenticate source rows.
    """
    reads = ("continuing_nodes", "next_durations")
    writes = ("next_stakes",)
    decision = "stake of the next commitment"

    def __init__(self, renewals, returns, entries, evidence):
        # Construction always repeats schema/evidence/fit validation. Manual
        # p/knots/cells and BehaviourBlock.with_value cannot bypass this path.
        super().__init__()
        tables = dict(zip(CONTEXTS, (renewals, returns, entries)))
        if not isinstance(evidence, Mapping) or set(evidence) != set(CONTEXTS):
            raise ValueError("evidence must map exactly renewal, return and entry to labels")
        identity = None
        cells = {}
        for context, table in tables.items():
            if not isinstance(table, pd.DataFrame) or tuple(table.columns) != FIT_COLUMNS:
                raise ValueError(f"{context}: exactly the four ordered fit columns required")
            if any(not isinstance(table[c].dtype, np.dtype) or table[c].dtype != np.dtype("int64") for c in FIT_COLUMNS):
                raise ValueError(f"{context}: every fit column must be native int64, without coercion")
            if not len(table):
                raise ValueError(f"{context}: context has no decisions")
            label = evidence[context]
            match = _LABEL.fullmatch(label) if isinstance(label, str) else None
            if match is None or not match[1].strip() or match[1] != match[1].strip():
                raise ValueError(f"{context}: malformed proposed source label")
            try:
                origin = date.fromisoformat(match[2])
            except ValueError as exc:
                raise ValueError(f"{context}: invalid evidence origin") from exc
            this_identity = (match[1], origin)
            if identity is not None and identity != this_identity:
                raise ValueError("all contexts must share run and origin")
            identity = this_identity
            if origin >= LOCKBOX_START.date():
                raise ValueError("origin is inside the held-back period")
            cutoff = int(datetime.combine(origin, time(23, 59, 59), UTC).timestamp()) * 1_000_000
            previous = table[FIT_COLUMNS[0]].to_numpy(copy=True)
            days = table[FIT_COLUMNS[1]].to_numpy(copy=True)
            stakes = table[FIT_COLUMNS[2]].to_numpy(copy=True)
            decided = table[FIT_COLUMNS[3]].to_numpy(copy=True)
            _inputs(context, previous, days)
            if ((stakes < MIN_STAKE) | (stakes > MAX_STAKE)).any():
                raise ValueError(f"{context}: next stake outside legal bounds")
            if ((decided <= cutoff - 365 * US_PER_DAY) | (decided > cutoff) | (decided >= LOCKBOX_US)).any():
                raise ValueError(f"{context}: decided_us outside (C-365d,C] or inside lockbox")
            if table_sha256(table) != match[3]:
                raise ValueError(f"{context}: table SHA-256 mismatch")
            reference = np.full(len(table), MIN_STAKE, dtype=np.int64) if context == "entry" else previous
            changed = stakes != reference
            ratios = np.log(stakes / reference)
            db = duration_band(days)
            sb = np.zeros(len(table), dtype=np.int64) if context == "entry" else _stake_band(previous)
            context_sample = ratios[changed]
            for d in range(5):
                for s in ([None] if context == "entry" else range(10)):
                    mask = (db == d) & (True if s is None else sb == s)
                    count, changes = int(mask.sum()), int((mask & changed).sum())
                    p = (count - changes + 1) / (count + 2)
                    cell_sample = ratios[mask & changed]
                    band_sample = ratios[(db == d) & changed]
                    if len(cell_sample) >= 50:
                        sample, scope = cell_sample, "cell"
                    elif len(band_sample) >= 50:
                        sample, scope = band_sample, "duration"
                    else:
                        sample, scope = context_sample, "context"
                    source = "fitted"
                    if not len(sample):
                        sample, scope, source = np.array([0.0]), "context", "prior"
                    cells[(context, d, s)] = _Cell(p, tuple(np.sort(sample)), scope, count, changes,
                                                  len(sample), label, source)
            if context == "entry":
                self._entry_stakes = tuple(int(x) for x in stakes)
        self._cells = MappingProxyType(cells)
        self._labels = MappingProxyType(dict(evidence))

    def __getstate__(self):
        # A read-only mapping does not pickle, and the sweep runner pickles each base model for its workers.
        state = super().__getstate__()
        state["_cells"], state["_labels"] = dict(self._cells), dict(self._labels)
        return state

    def __setstate__(self, state):
        state = {**state, "_cells": MappingProxyType(state["_cells"]), "_labels": MappingProxyType(state["_labels"])}
        super().__setstate__(state)

    @classmethod
    def fit(cls, renewals, returns, entries, evidence):
        return cls(renewals, returns, entries, evidence)

    def sources(self):
        out = {}
        for (context, d, s), cell in self._cells.items():
            key = f"{context}/d{d}/s{s}"
            out[key + "/p"] = {"source": "fitted", "value": cell.p, "bounds": (0., 1.),
                               "evidence": f"{cell.label}; cell {cell.count} decisions, {cell.changes} changes; add-one keep/change"}
            reason = ("no changed stakes in the window" if cell.knot_source == "prior" else
                      f"{cell.scope} pool; {cell.knot_count} changed ratios")
            out[key + "/knots"] = {"source": cell.knot_source, "value": cell.knots,
                                   "evidence": f"{cell.label}; {reason}"}
        return out

    def _dispatch(self, contexts, previous, days):
        d = duration_band(days)
        s = _stake_band(previous)
        return [(c, int(b), None if c == "entry" else int(t)) for c, b, t in zip(contexts, d, s)]

    def stakes_from_uniforms(self, context, previous_stake_navax, next_days, u):
        contexts, previous, days = _inputs(context, previous_stake_navax, next_days)
        uniforms = _vector(u, "u")
        if uniforms.dtype.kind not in "iuf" or len(uniforms) != len(days):
            raise ValueError("u requires one real uniform per row")
        uniforms = uniforms.astype(np.float64)
        if not (np.isfinite(uniforms).all() and ((uniforms >= 0) & (uniforms < 1)).all()):
            raise ValueError("u must be finite in [0,1)")
        out = np.empty(len(days), dtype=np.int64)
        keys = self._dispatch(contexts, previous, days)
        for key in dict.fromkeys(keys):
            indices = np.array([i for i, k in enumerate(keys) if k == key], dtype=np.int64)
            cell = self._cells[key]
            reference = np.full(len(indices), MIN_STAKE, dtype=np.int64) if key[0] == "entry" else previous[indices]
            keep = uniforms[indices] < cell.p
            out[indices] = reference
            if (~keep).any():
                v = np.minimum((uniforms[indices][~keep] - cell.p) / (1 - cell.p), np.nextafter(1., 0.))
                out[indices[~keep]] = _changed(cell.knots, reference[~keep], v)
        return out

    def cell_probabilities(self, context, previous_stake_navax, next_days):
        """Rows of 103 probabilities: atom, below -5, 100 bins, above +5."""
        contexts, previous, days = _inputs(context, previous_stake_navax, next_days)
        out = np.empty((len(days), 103), dtype=np.float64)
        cache = {}
        for i, key in enumerate(self._dispatch(contexts, previous, days)):
            reference = MIN_STAKE if key[0] == "entry" else int(previous[i])
            cached_key = (key, reference)
            if cached_key not in cache:
                cell = self._cells[key]
                edges = _integer_edges(reference)
                thresholds = np.concatenate(([MIN_STAKE], edges, [MAX_STAKE + 1, reference, reference + 1]))
                cdf = _cdf_stake(cell.knots, reference, thresholds)
                bins = np.maximum(np.diff(cdf[:103]), 0.)
                atom = max(0., cdf[-1] - cdf[-2])
                atom_bin = int(1 + np.searchsorted(LOG_EDGES, 0., side="right"))
                bins[atom_bin - 1] = max(0., bins[atom_bin - 1] - atom)
                mass = np.concatenate(([cell.p + (1 - cell.p) * atom], (1 - cell.p) * bins))
                cache[cached_key] = _smooth(mass)
            out[i] = cache[cached_key]
        return out

    def log_prob(self, context, previous_stake_navax, next_days, next_stake_navax):
        contexts, previous, days = _inputs(context, previous_stake_navax, next_days)
        stakes = _integers(next_stake_navax, "next_stake_navax")
        if len(stakes) != len(days):
            raise ValueError("one next stake required per row")
        valid = (stakes >= MIN_STAKE) & (stakes <= MAX_STAKE)
        out = np.full(len(days), -np.inf, dtype=np.float64)
        if valid.any():
            law = self.cell_probabilities(contexts[valid], previous[valid], days[valid])
            references = np.where(contexts[valid] == "entry", MIN_STAKE, previous[valid])
            ids = _cell_ids(references, stakes[valid])
            out[valid] = np.log(law[np.arange(valid.sum()), ids])
        return out

    def baseline_log_prob(self, context, previous_stake_navax, next_days, next_stake_navax):
        """Moving 0.99 atom law, or context-wide observed past-year entrants.

        Both baselines score the same 103 observable cells and smooth only
        zeros. Entry uses the validated fit window's observed stakes.
        """
        contexts, previous, days = _inputs(context, previous_stake_navax, next_days)
        stakes = _integers(next_stake_navax, "next_stake_navax")
        if len(stakes) != len(days):
            raise ValueError("one next stake required per row")
        moving = np.full(103, .01 / 102)
        moving[0] = .99
        entry = _smooth(np.bincount(_cell_ids(MIN_STAKE, np.asarray(self._entry_stakes)), minlength=103).astype(float) / len(self._entry_stakes))
        out = np.full(len(days), -np.inf, dtype=np.float64)
        for i, (c, prior, stake) in enumerate(zip(contexts, previous, stakes)):
            if MIN_STAKE <= stake <= MAX_STAKE:
                reference = MIN_STAKE if c == "entry" else prior
                cell_id = int(_cell_ids(reference, stake))
                out[i] = np.log((entry if c == "entry" else moving)[cell_id])
        return out
