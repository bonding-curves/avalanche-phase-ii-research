"""Behaviour blocks: one Param class per decision, with a shared interface.

A block declares what it reads and writes, the source of every parameter, and the range of inputs seen
in the data. It offers ``sample``, which draws decisions for the simulator, and ``log_prob``, which scores
observed decisions for the estimator, so both use one definition. Swapping a fixed rate for a fitted model
or an interview range means swapping one class.

Every behavioural parameter carries a source from one list: fitted, prior, interview, assumed, or
observed moment. A parameter without one cannot be declared.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np
import param

SOURCES = ("fitted", "prior", "interview", "assumed", "observed moment")


def behavioural(default: float, bounds: tuple[float, float], source: str, doc: str, evidence: str) -> param.Number:
    """A behavioural parameter with its source and evidence in the Param metadata."""
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}, not {source!r}")
    if not evidence:
        raise ValueError("a behavioural parameter needs its evidence: a run, a commit, a paper, or an interview")
    return param.Number(default=default, bounds=bounds, doc=doc, metadata={"source": source, "evidence": evidence})


class BehaviourBlock(param.Parameterized):
    """One decision of one kind of agent."""

    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    decision = "abstract"

    def sources(self) -> dict[str, dict[str, Any]]:
        """Each behavioural parameter with its value, bounds, source, and evidence."""
        out = {}
        for name, parameter in self.param.objects().items():
            meta = getattr(parameter, "metadata", None) or {}
            if "source" in meta:
                out[name] = {"value": getattr(self, name), "bounds": parameter.bounds, **meta}
        return out

    def observed_range(self) -> Mapping[str, tuple[float, float]]:
        """The range of each input seen in the data. Inputs outside it are logged by ``outside_observed``."""
        return {}

    def outside_observed(self, inputs: Mapping[str, np.ndarray]) -> dict[str, int]:
        """How many decisions were made with an input outside its observed range, by input."""
        counts = {}
        for name, (low, high) in self.observed_range().items():
            values = np.asarray(inputs[name])
            counts[name] = int(((values < low) | (values > high)).sum())
        return counts

    def sample(self, inputs: Mapping[str, np.ndarray], rng: np.random.Generator) -> np.ndarray:
        raise NotImplementedError

    def log_prob(self, inputs: Mapping[str, np.ndarray], decisions: np.ndarray) -> float:
        raise NotImplementedError


class Renewal(BehaviourBlock):
    """Whether a validator commitment that ends is followed by a new one on the same node within seven days.

    The baseline is one probability per ending, the observed moment ``AM2``. A fitted hazard by tenure and
    era replaces it through the same interface.
    """

    reads = ("ending_commitments",)
    writes = ("renewed_commitments",)
    decision = "renew within seven days"

    probability = behavioural(
        0.801541,
        (0.0, 1.0),
        "observed moment",
        "Share of ending validator commitments renewed on the same node within seven days",
        "AM2, 30,578 of 38,149 endings in 2021 to 2024, staking-periods-2026-09-30, client 7ca051e",
    )

    def sample(self, inputs, rng):
        return rng.random(len(inputs["ending_commitments"])) < self.probability

    def log_prob(self, inputs, decisions):
        decisions = np.asarray(decisions, dtype=bool)
        p = min(max(self.probability, 1e-12), 1 - 1e-12)
        return float(decisions.sum() * np.log(p) + (~decisions).sum() * np.log1p(-p))


def check_writers(blocks: Iterable[BehaviourBlock]) -> None:
    """Refuse a set of blocks in which two write the same state variable."""
    counts = Counter(variable for block in blocks for variable in block.writes)
    shared = sorted(variable for variable, n in counts.items() if n > 1)
    if shared:
        raise ValueError(f"more than one block writes {shared}")


def check_sources(blocks: Iterable[BehaviourBlock]) -> None:
    """Refuse a block with a numeric parameter that has no declared source."""
    for block in blocks:
        for name, parameter in block.param.objects().items():
            if isinstance(parameter, param.Number) and name not in block.sources():
                raise ValueError(f"{type(block).__name__}.{name} has no declared source")
