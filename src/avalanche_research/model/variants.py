"""The model variants the development scores run, by name, and how each is built at an origin.

* ``v0.7``: :class:`~avalanche_research.model.lifecycle.ValidatorLifecycle` with the inputs of ``origin_inputs``: one
  renewal probability and one entry rate observed before the origin.
* ``v0.8``: :class:`~avalanche_research.model.fitted_lifecycle.FittedLifecycle` with every block fitted before the
  origin by ``fitted_inputs``.
* ``v0.8 separate``: v0.8 with its renewal block fitted separately for commitments above 1M AVAX and at or below it.
* ``v0.8 u``: v0.8 with one draw of every fitted parameter per run, from ``parameter_draws``, with the renewal shift's
  SD from ``window_sd``. Its continuation and first-commitment tables keep their node codes, so each run resamples them.

A variant is built in two steps. :meth:`Variant.prepare` reads the staking periods once per origin and returns the
inputs every batch shares, with the draw table for a variant that reads draws. :meth:`Variant.simulation` builds one
batch from them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import pandas as pd

from avalanche_research.model.engine import SimulationModel
from avalanche_research.model.fitted_lifecycle import (
    FittedLifecycle,
    fit_blocks,
    fitted_inputs,
    parameter_draws,
    training_events,
    window_sd,
)
from avalanche_research.model.lifecycle import ValidatorLifecycle, origin_inputs

LARGE_ABOVE_AVAX = 1_000_000


@dataclass(frozen=True, eq=False)
class Prepared:
    """A variant's inputs at one origin: the model's settings and input tables, and for a variant that reads draws,
    its draw table, the renewal shift's SD and that SD's source."""

    inputs: dict
    draws: pd.DataFrame | None = None
    tau: float | None = None
    tau_source: str | None = None


@dataclass(frozen=True, eq=False)
class Variant:
    """A named model variant: its model class, what it is, and how its inputs are built at an origin from the staking
    periods, the name of the run they came from, the number of draws and the draw seed."""

    name: str
    model: type[SimulationModel]
    description: str
    build: Callable[[str, date, str, int, int], Prepared]

    def prepare(self, periods: str, origin: date, run: str, draws: int = 0, draw_seed: int = 0) -> Prepared:
        return self.build(periods, origin, run, draws, draw_seed)

    def simulation(self, prepared: Prepared, seed: int, timesteps: int, runs: int,
                   draws: pd.DataFrame | None = None) -> SimulationModel:
        """One batch: ``runs`` runs of ``timesteps`` days under base seed ``seed``, reading ``draws`` when given."""
        extra = {"draws": draws} if draws is not None else {}
        return self.model(timesteps=timesteps, runs=runs, seed=seed, **prepared.inputs, **extra)


def _chain_inputs(periods: str, origin: date, run: str, draws: int, draw_seed: int) -> Prepared:
    return Prepared({"origin": origin, "inputs_source": run, **origin_inputs(periods, origin)})


def _fitted(periods: str, origin: date, run: str, draws: int, draw_seed: int) -> Prepared:
    return Prepared(fitted_inputs(periods, origin, run))


def _fitted_separate(periods: str, origin: date, run: str, draws: int, draw_seed: int) -> Prepared:
    return Prepared(fitted_inputs(periods, origin, run, LARGE_ABOVE_AVAX))


def _fitted_with_draws(periods: str, origin: date, run: str, draws: int, draw_seed: int) -> Prepared:
    events = training_events(periods, origin, run)
    inputs = {**fit_blocks(events), "moves": events.moves, "first_commitments": events.first_commitments}
    tau, source = window_sd(periods, origin, inputs["renewal"])
    return Prepared(inputs, parameter_draws(events, draws, draw_seed, tau), tau, source)


VARIANTS: dict[str, Variant] = {
    variant.name: variant for variant in (
        Variant("v0.7", ValidatorLifecycle, "the validator lifecycle with one renewal probability and one entry rate observed before the origin",
                _chain_inputs),
        Variant("v0.8", FittedLifecycle, "the lifecycle with every behaviour block fitted before the origin", _fitted),
        Variant("v0.8 separate", FittedLifecycle,
                f"v0.8 with renewal fitted separately above and at or below {LARGE_ABOVE_AVAX:,} AVAX", _fitted_separate),
        Variant("v0.8 u", FittedLifecycle, "v0.8 with one draw of every fitted parameter per run", _fitted_with_draws),
    )
}
