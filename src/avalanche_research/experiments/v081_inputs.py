"""The v0.8.1 candidate's inputs from a pin: the two built runs it reads, verified, and the delegation tables built from them.

The model package never imports data code, so the pin is resolved here. :func:`pinned_inputs` reads a pin file as
``pins.pin`` writes it and refuses one that is missing, does not verify, or names no run of the staking periods or of
the seamed delegator stakes (each delegation's funding address, which sets BENQI's apart). Nothing selects a newer build
in their place. :func:`candidate_tables` builds every delegation table the variant's ``prepare`` takes as
``delegations``, and :func:`prepare_candidate` does both and prepares the variant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from avalanche_research import datasets
from avalanche_research.core.catalog import DataError, sha256
from avalanche_research.datasets import pins
from avalanche_research.datasets.derived import delegation_inputs as di
from avalanche_research.model.delegated_lifecycle import benqi_choices, delegation_terms
from avalanche_research.model.variants import VARIANTS, Prepared

CANDIDATE = "v0.8.1 candidate"
PERIODS_DATASET, DELEGATORS_DATASET = "derived.staking-periods", "derived.seamed-delegator-stakes"


@dataclass(frozen=True)
class PinnedInputs:
    """The two built runs the candidate reads, named by a verified pin, each with its run name, Parquet path and SHA-256."""

    pin: Path
    periods_run: str
    periods: Path
    periods_sha256: str
    delegators_run: str
    delegators: Path
    delegators_sha256: str


def pinned_inputs(pin: Path, root: Path | None = None) -> PinnedInputs:
    """The candidate's input runs from ``pin``. The pin must exist, verify (every pinned run present, unchanged and passing
    its check) and name a run of both datasets. ``root`` is the runs directory, the project's by default."""
    pin = Path(pin)
    if not pin.is_file():
        raise DataError(f"the candidate's pin file is missing: {pin}")
    findings = pins.verify(pin, root)
    if findings:
        raise DataError(f"the candidate's pin {pin} does not verify: " + "; ".join(findings))
    named = pins.runs(pin)
    missing = [dataset for dataset in (PERIODS_DATASET, DELEGATORS_DATASET) if dataset not in named]
    if missing:
        raise DataError(f"the candidate's pin {pin} names no run of {', '.join(missing)}")
    periods = datasets.parquet_path(PERIODS_DATASET, named[PERIODS_DATASET], root)
    delegators = datasets.parquet_path(DELEGATORS_DATASET, named[DELEGATORS_DATASET], root)
    return PinnedInputs(pin, named[PERIODS_DATASET], periods, sha256(periods.read_bytes()),
                        named[DELEGATORS_DATASET], delegators, sha256(delegators.read_bytes()))


def candidate_tables(periods: str, delegators: str, origin: date) -> dict[str, pd.DataFrame]:
    """Every delegation table the candidate's ``prepare`` needs at ``origin``: the origin's delegation tables, the year's
    terms and BENQI's choices, from the two Parquet files."""
    return {**di.build(periods, delegators, origin),
            "terms": delegation_terms(periods, delegators, origin, di.BENQI_FUNDING, di.BENQI_EVIDENCE),
            "benqi_choices": benqi_choices(periods, delegators, origin, di.BENQI_FUNDING, di.BENQI_EVIDENCE)}


def prepare_candidate(pin: Path, origin: date, draws: int = 0, draw_seed: int = 0, root: Path | None = None, **tables) -> Prepared:
    """The candidate prepared at ``origin`` from the runs ``pin`` names, and nothing else."""
    inputs = pinned_inputs(pin, root)
    return VARIANTS[CANDIDATE].prepare(str(inputs.periods), origin, inputs.periods_run, draws, draw_seed,
                                       delegations=candidate_tables(str(inputs.periods), str(inputs.delegators), origin), **tables)
