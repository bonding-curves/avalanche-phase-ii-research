"""The model variants the development scores run, by name, and how each is built at an origin.

* ``v0.7``: :class:`~avalanche_research.model.lifecycle.ValidatorLifecycle` with the inputs of ``origin_inputs``: one
  renewal probability and one entry rate observed before the origin.
* ``v0.8``: :class:`~avalanche_research.model.fitted_lifecycle.FittedLifecycle` with every block fitted before the
  origin by ``fitted_inputs``.
* ``v0.8 separate``: v0.8 with its renewal block fitted separately for commitments above 1M AVAX and at or below it.
* ``v0.8 u``: v0.8 with one draw of every fitted parameter per run, from ``parameter_draws``, with the renewal shift's
  SD from ``window_sd``. Its continuation and first-commitment tables keep their node codes, so each run resamples them.

The development scores run those four, :data:`DEVELOPMENT_MODELS`. The registry also builds the three v0.8 candidates
the adoption rule chose among, each on today's code by three :class:`Switches`, and each with one parameter draw per
run under the same name with ``u`` added:

* ``v0.8-a``: renewal without the node's own renewal record, and a moving node's stake ratio drawn with every move
  weighted the same within the return block's three stake bands.
* ``v0.8-c``: v0.8-a with the node's own renewal record in the renewal logit and each move weighted by its previous
  stake.
* ``v0.8-e``: v0.8-c with the stake ratio drawn within ten log-spaced stake bands. It is v0.8.

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
    TrainingEvents,
    fit_blocks,
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


@dataclass(frozen=True)
class Switches:
    """The three choices the v0.8 candidates differ in. The defaults are v0.8.

    ``node_record`` fits the renewal logit with the node's own renewal record (``fit_blocks``). ``move_stake_bands``
    and ``move_stake_weighted`` set the settings of the same names on :class:`FittedLifecycle`: the stake bands within
    which a moving node draws its stake ratio, and whether each move is weighted by its previous stake.
    """

    node_record: bool = True
    move_stake_bands: str = "ten log-spaced"
    move_stake_weighted: bool = True

    def settings(self) -> dict:
        """The model settings these switches set."""
        return {"move_stake_bands": self.move_stake_bands, "move_stake_weighted": self.move_stake_weighted}


V08 = Switches()

CANDIDATES: dict[str, Switches] = {
    "v0.8-a": Switches(node_record=False, move_stake_bands="three", move_stake_weighted=False),
    "v0.8-c": Switches(node_record=True, move_stake_bands="three", move_stake_weighted=True),
    "v0.8-e": V08,
}


def switched_inputs(events: TrainingEvents, switches: Switches, large_above_avax: float | None = None) -> dict:
    """Every input of a v0.8 run fitted on ``events`` under ``switches``."""
    return {**fit_blocks(events, large_above_avax, switches.node_record), **switches.settings()}


def _chain_inputs(periods: str, origin: date, run: str, draws: int, draw_seed: int) -> Prepared:
    return Prepared({"origin": origin, "inputs_source": run, **origin_inputs(periods, origin)})


def _fitted(switches: Switches = V08, large_above_avax: float | None = None) -> Callable[..., Prepared]:
    def build(periods: str, origin: date, run: str, draws: int, draw_seed: int) -> Prepared:
        return Prepared(switched_inputs(training_events(periods, origin, run), switches, large_above_avax))
    return build


def _fitted_with_draws(switches: Switches = V08) -> Callable[..., Prepared]:
    def build(periods: str, origin: date, run: str, draws: int, draw_seed: int) -> Prepared:
        events = training_events(periods, origin, run)
        inputs = {**switched_inputs(events, switches), "moves": events.moves, "first_commitments": events.first_commitments}
        tau, source = window_sd(periods, origin, inputs["renewal"])
        return Prepared(inputs, parameter_draws(events, draws, draw_seed, tau, node_record=switches.node_record), tau, source)
    return build


_CANDIDATE_DESCRIPTIONS = {
    "v0.8-a": "v0.8 without the node's own renewal record, with the stake ratio drawn unweighted within three stake bands",
    "v0.8-c": "v0.8-a with the node's own renewal record and the stake ratio weighted by previous stake",
    "v0.8-e": "v0.8-c with the stake ratio drawn within ten log-spaced stake bands, the same model as v0.8",
}

VARIANTS: dict[str, Variant] = {
    variant.name: variant for variant in (
        Variant("v0.7", ValidatorLifecycle, "the validator lifecycle with one renewal probability and one entry rate observed before the origin",
                _chain_inputs),
        Variant("v0.8", FittedLifecycle, "the lifecycle with every behaviour block fitted before the origin", _fitted()),
        Variant("v0.8 separate", FittedLifecycle,
                f"v0.8 with renewal fitted separately above and at or below {LARGE_ABOVE_AVAX:,} AVAX",
                _fitted(large_above_avax=LARGE_ABOVE_AVAX)),
        Variant("v0.8 u", FittedLifecycle, "v0.8 with one draw of every fitted parameter per run", _fitted_with_draws()),
        *(variant for name, switches in CANDIDATES.items() for variant in (
            Variant(name, FittedLifecycle, _CANDIDATE_DESCRIPTIONS[name], _fitted(switches)),
            Variant(f"{name} u", FittedLifecycle, f"{name} with one draw of every fitted parameter per run", _fitted_with_draws(switches)),
        )),
    )
}

# The variants the development scores run, as before the candidates were registered.
DEVELOPMENT_MODELS: tuple[str, ...] = ("v0.7", "v0.8", "v0.8 separate", "v0.8 u")
