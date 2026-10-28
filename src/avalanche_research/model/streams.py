"""Keyed random numbers: every draw a pure function of (seed, run, purpose, keys).

A per-node decision reads one uniform keyed by the node and its decision count, so two designs run on the same seed
share every draw except where a decision itself differs, and one more renewal in one design moves no other node's
draws. Draws that are not per-node decisions use a whole ``numpy.random.Generator`` keyed the same way.

Purpose ids are hashes of declared names, so declaring a new purpose moves no existing purpose's draws. Each kind
of seed list starts with its own tag and has a fixed length, because ``SeedSequence`` ignores trailing zero words.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

TAG_KEYED, TAG_GENERATOR = 0x4B455944, 0x47454E52
MAX_GENERATOR_KEYS = 4

PURPOSES = {
    "renewal": "renew or leave at a commitment's end",
    "renewal_large": "the same, for a commitment above the large-holder line",
    "returns": "a node out of the set returns today",
    "arrivals": "the count of first-ever nodes today",
    "first_stake": "a first-ever node's stake",
    "first_days": "a first-ever node's duration",
    "renew_stake": "the stake after a renewal",
    "renew_days": "the duration after a renewal",
    "return_stake": "the stake after a return",
    "return_days": "the duration after a return",
    "parameter_draw": "one run's draw of fitted parameters",
    "continuation_resample": "one run's node resample of the continuation and first-commitment tables",
    "failure": "an uptime failure at a commitment's end",
    "large_path": "the large-holder cohort path",
    "design": "the scramble of a sweep design's Sobol points",
    "delegations": "the count of new delegations today",
    "delegation_benqi": "whether a new delegation is BENQI's",
    "delegation_terms": "a new delegation's stake and duration",
    "delegator_choice": "the validator a delegator other than BENQI chooses",
    "benqi_allocation": "the validator BENQI delegates to",
    "holder_days": "the duration of a fund's validator commitment, within the fund's band",
}

KIND_OPEN, KIND_OUT, KIND_SCHEDULED, KIND_ARRIVAL = 0, 1, 2, 3
_FIELD = 1 << 24


def purpose_id(name: str) -> int:
    """A stable 63-bit id from a declared purpose's name. Order-free."""
    if name not in PURPOSES:
        raise KeyError(f"undeclared random purpose {name!r}")
    return int.from_bytes(hashlib.blake2b(name.encode(), digest_size=8).digest(), "little") >> 1


def _splitmix(x: np.ndarray) -> np.ndarray:
    with np.errstate(over="ignore"):
        x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return x ^ (x >> np.uint64(31))


def node_keys(kind: int, t: int, index: np.ndarray) -> np.ndarray:
    """int64 node keys ``kind << 48 | t << 24 | index``. Kind 0 is open at the origin, 1 out of the set, 2 scheduled,
    3 a first-ever arrival on day ``t``."""
    index = np.asarray(index, dtype=np.int64)
    if t >= _FIELD or (index.size and int(index.max()) >= _FIELD) or kind > 0x7FFF:
        raise ValueError("node key field overflow")
    return (np.int64(kind) << np.int64(48)) | (np.int64(t) << np.int64(24)) | index


@dataclass(frozen=True)
class Streams:
    """All randomness of one run. Plain data, so it pickles to any worker and replays anywhere."""

    seed: int
    run: int

    def uniforms(self, purpose: str, *keys) -> np.ndarray:
        """One uniform in [0, 1) per row. Keys are ints or int arrays of one common length."""
        sizes = [np.size(k) for k in keys if np.ndim(k) > 0]
        n = sizes[0] if sizes else 1
        if n == 0:
            return np.zeros(0)
        root = np.random.SeedSequence([TAG_KEYED, purpose_id(purpose), self.run, self.seed]).generate_state(1, np.uint64)[0]
        h = np.full(n, root, dtype=np.uint64)
        with np.errstate(over="ignore"):
            for k in keys:
                k = np.broadcast_to(np.asarray(k, dtype=np.int64), (n,)).astype(np.uint64)
                h = _splitmix(h ^ (k + np.uint64(0x9E3779B97F4A7C15)))
        return (h >> np.uint64(11)).astype(np.float64) * (1.0 / 2**53)

    def generator(self, purpose: str, *keys: int) -> np.random.Generator:
        """A whole Generator for draws that are not per-node decisions, from a fixed-length tagged seed list."""
        if len(keys) > MAX_GENERATOR_KEYS:
            raise ValueError(f"at most {MAX_GENERATOR_KEYS} generator keys")
        padded = [*keys, *([0] * (MAX_GENERATOR_KEYS - len(keys)))]
        return np.random.default_rng(np.random.SeedSequence([TAG_GENERATOR, purpose_id(purpose), len(keys), *padded, self.run, self.seed]))
