"""Design rows for a sweep: each row is one complete setting of the model, yielded whole, so a runner never needs to know
how rows were chosen.

A row holds the design's name, the row's index, every setting it changes, and ``seed``. Settings shared across rows,
such as the seed within one future, give every lever the same random numbers, so differences between rows come from the
settings. ``row_id`` hashes a row with the base model's specification hash, so it is known before the row runs and a
resumed sweep can skip finished rows without building a model.

| Generator | Design | Use |
| --- | --- | --- |
| ``cartesian`` | Every combination of listed levels | Levers crossed in full with futures |
| ``sobol`` | Scrambled Sobol points in given bounds | Sensitivity and any design that may grow: doubling ``m`` keeps the first rows |

``design_hash`` fixes a design before launch, ``check_cardinality`` refuses a design of the wrong size, and
``no_effect`` names any swept setting that moved no output in a pilot.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence

import numpy as np
import pandas as pd

from .streams import Streams

IDENTITY = ("design", "index")
# Keys that pick the base model rather than change one of its settings.
BASE_KEYS = ("origin", "model", "batch")


def row_id(row: Mapping, base_hash: str) -> str:
    """The row's identity: a hash of the base specification hash and the row, 16 hex digits."""
    text = json.dumps({"base": base_hash, **{k: v for k, v in row.items() if k != "row_id"}}, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def settings(row: Mapping) -> dict:
    """The model settings a row changes: everything but its identity and the keys that pick its base model."""
    return {k: v for k, v in row.items() if k not in (*IDENTITY, *BASE_KEYS, "row_id")}


def check_origins(rows: Iterable[Mapping]) -> None:
    """Refuse a design with an origin inside the validation lockbox, before any model is built."""
    from .replay import LOCKBOX_FIRST_DAY

    late = sorted({str(row["origin"]) for row in rows if "origin" in row and pd.Timestamp(row["origin"]).date() >= LOCKBOX_FIRST_DAY})
    if late:
        raise ValueError(f"origins inside the validation lockbox, which starts 2025-11-19 16:00 UTC: {', '.join(late)}")


def cartesian(levels: Mapping[str, Sequence], seed: int = 0, name: str = "cartesian") -> Iterator[dict]:
    """Every combination of ``levels``, in the order the keys are given."""
    keys = list(levels)
    for i, values in enumerate(itertools.product(*(levels[k] for k in keys))):
        yield {"design": name, "index": i, "seed": seed, **dict(zip(keys, values))}  # a swept seed overrides the base one


def sobol(bounds: Mapping[str, tuple[float, float]], m: int, design_seed: int, seed: int = 0, start: int = 0) -> Iterator[dict]:
    """``2**m`` scrambled Sobol rows in ``bounds``, from row ``start`` on. A design extended or resumed from ``start``
    yields the same rows as one generated whole."""
    from scipy.stats import qmc

    if not 0 <= start <= 2**m:
        raise ValueError(f"start {start} is outside the design's {2**m} rows")
    keys = list(bounds)
    engine = qmc.Sobol(d=len(keys), scramble=True, rng=Streams(seed=design_seed, run=0).generator("design"))
    if start:  # fast_forward(0) raises in SciPy
        engine.fast_forward(start)
    low = np.array([bounds[k][0] for k in keys], dtype=float)
    high = np.array([bounds[k][1] for k in keys], dtype=float)
    for i, point in enumerate(qmc.scale(engine.random(2**m - start), low, high), start=start):
        yield {"design": f"sobol-{design_seed}", "index": i, **{k: float(v) for k, v in zip(keys, point)}, "seed": seed}


def design_hash(rows: Iterable[Mapping], base_hash: str) -> str:
    """One hash of a whole design's row ids, in order, so the design can be reviewed and fixed before launch."""
    digest = hashlib.sha256(base_hash.encode())
    for row in rows:
        digest.update(row_id(row, base_hash).encode())
    return digest.hexdigest()[:16]


def check_cardinality(rows: Sequence[Mapping], expected: int) -> None:
    """Refuse a design with the wrong number of rows, or with two rows that are the same setting."""
    if len(rows) != expected:
        raise ValueError(f"the design has {len(rows)} rows, not {expected}")
    keys = [json.dumps({k: v for k, v in row.items() if k not in (*IDENTITY, "row_id")}, sort_keys=True, default=str) for row in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("the design repeats a setting")


def no_effect(results: pd.DataFrame, swept: Sequence[str], outcome: str = "value") -> list[str]:
    """The swept settings that moved no output in a pilot: holding every other setting fixed, every level gave the same
    ``outcome`` at every (variable, timestep, run). Under the chain's own reward rule both responses fail this, because
    the yield gap they multiply is zero."""
    idle = []
    for setting in swept:
        others = [s for s in swept if s != setting]
        keys = [k for k in (*others, "variable", "timestep", "run") if k in results.columns]
        spread = results.groupby(keys, dropna=False)[outcome].nunique()
        if results[setting].nunique() > 1 and (spread <= 1).all():
            idle.append(setting)
    return idle
