"""Behaviour blocks: one Param class per decision, with a shared interface.

A block declares what it reads and writes, the source of every parameter, and the range of inputs seen
in the data. It offers ``sample``, which draws decisions for the simulator, and ``log_prob``, which scores
observed decisions for the estimator, so both use one definition. Swapping a fixed rate for a fitted model
or an interview range means swapping one class.

Every behavioural parameter carries a source from one list: fitted, prior, interview, assumed, or
observed moment. A parameter without one cannot be declared. The class declares the source of its
default. A value set on an instance needs its own source and evidence, given through ``with_value``; an
instance value without one is reported as unlabelled and refused by ``check_sources``.
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

    def __init__(self, provenance: Mapping[str, Mapping[str, str]] | None = None, **params: Any):
        super().__init__(**params)
        self._provenance = {name: dict(meta) for name, meta in (provenance or {}).items()}
        for meta in self._provenance.values():
            if meta.get("source") not in SOURCES or not meta.get("evidence") or "value" not in meta:
                raise ValueError(f"provenance needs a source from {SOURCES}, its evidence, and the value it labels, not {meta}")

    def with_value(self, name: str, value: float, source: str, evidence: str) -> BehaviourBlock:
        """A copy with one parameter set, carrying that value's own source and evidence."""
        current = {k: v for k, v in self.param.values().items() if k != "name"}
        provenance = {**self._provenance, name: {"source": source, "evidence": evidence, "value": value}}
        return type(self)(provenance=provenance, **{**current, name: value})

    def sources(self) -> dict[str, dict[str, Any]]:
        """Each behavioural parameter with its value, bounds, source, and evidence.

        The class metadata describes the default only. An instance value is labelled by ``with_value``, and
        the label holds only while the value is the one it was given for. A value set any other way, or
        changed after labelling, is reported with source ``unlabelled``.
        """
        out = {}
        for name, parameter in self.param.objects().items():
            meta = getattr(parameter, "metadata", None) or {}
            if "source" not in meta:
                continue
            value = getattr(self, name)
            labelled = self._provenance.get(name)
            if labelled is not None and labelled["value"] == value:
                label = {"source": labelled["source"], "evidence": labelled["evidence"]}
            elif value == parameter.default:
                label = meta
            else:
                label = {"source": "unlabelled", "evidence": ""}
            out[name] = {"value": value, "bounds": parameter.bounds, **label}
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
        """The exact Bernoulli log-likelihood, minus infinity for an outcome the probability rules out."""
        decisions = _outcomes(decisions, len(inputs["ending_commitments"]))
        renewed = int(decisions.sum())
        left = len(decisions) - renewed
        p = self.probability
        if (p == 0.0 and renewed) or (p == 1.0 and left):
            return float("-inf")
        return float((renewed * np.log(p) if renewed else 0.0) + (left * np.log1p(-p) if left else 0.0))


def _outcomes(decisions: Any, expected: int) -> np.ndarray:
    """Observed yes or no decisions, one per input row. Anything else is refused."""
    values = np.asarray(decisions)
    if values.ndim != 1 or len(values) != expected:
        raise ValueError(f"expected {expected} decisions, one per input row, not shape {values.shape}")
    if values.dtype != bool and not np.isin(values, (0, 1)).all():
        raise ValueError("decisions must be booleans or 0 and 1")
    return values.astype(bool)


def check_writers(blocks: Iterable[BehaviourBlock]) -> None:
    """Refuse a set of blocks in which two write the same state variable."""
    counts = Counter(variable for block in blocks for variable in block.writes)
    shared = sorted(variable for variable, n in counts.items() if n > 1)
    if shared:
        raise ValueError(f"more than one block writes {shared}")


def check_sources(blocks: Iterable[BehaviourBlock]) -> None:
    """Refuse a block with a numeric parameter that has no declared source, or an unlabelled instance value."""
    for block in blocks:
        sources = block.sources()
        for name, parameter in block.param.objects().items():
            if isinstance(parameter, param.Number) and name not in sources:
                raise ValueError(f"{type(block).__name__}.{name} has no declared source")
            if name in sources and sources[name]["source"] not in SOURCES:
                raise ValueError(f"{type(block).__name__}.{name} = {sources[name]['value']} has no source for that value")
