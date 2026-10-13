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

It also builds one candidate on v0.8 by a fourth switch, with and without parameter draws:

* ``v0.8 duration``: v0.8 in which a node that renews or returns draws its next duration from a fitted transition
  between five duration bands, :class:`~avalanche_research.model.parts.duration_transition.DurationTransition`, fitted
  on the moves of the 365 days before the origin. Its stake still comes from the continuation table. With parameter
  draws, each run refits the transition on its own node resample of the moves, the one its continuation table reads.

It builds three candidates on v0.8-a, each with one of the changes that v0.8-c, v0.8-e and v0.8 duration make, with
and without parameter draws:

* ``v0.8-a record``: v0.8-a with the node's own renewal record in the renewal logit.
* ``v0.8-a bands``: v0.8-a with the stake ratio drawn, still unweighted, within ten log-spaced stake bands.
* ``v0.8-a duration``: v0.8-a with the next duration drawn from the fitted duration band transition.

It builds one candidate on v0.8-a by a fifth switch, with and without parameter draws:

* ``v0.8-a return``: v0.8-a in which a node out of the set returns by the logit hazard on its own history,
  :class:`~avalanche_research.model.parts.return_hazard.ReturnLogitHazard`: six bins of days out, its stake band,
  whether it has returned before and whether the commitment that ended was its first, fitted on the same return spells
  as the return block. With parameter draws, each run refits it on its own node resample of those spells.

It builds one candidate on v0.8-a with two changes, the ten bands and the return hazard, with and without parameter
draws:

* ``v0.8-a bands return``: v0.8-a with the stake ratio drawn unweighted within ten log-spaced stake bands and the
  logit return hazard on the node's own history.


It builds one candidate on v0.8-a by the stake lifecycle's switch, with and without parameter draws:

* ``v0.8-a stake``: v0.8-a in which each renewing, returning or entering node takes its next stake from the fitted
  stake hurdle, :class:`~avalanche_research.model.parts.stake_choice.StakeChoice`, given the duration it has drawn,
  through :class:`~avalanche_research.model.stake_lifecycle.StakeLifecycle`. With parameter draws, every other block
  redraws per run and the hurdle stays at its fitted point estimate, labelled "stake hurdle not resampled".
* ``v0.8-a stake return``: v0.8-a stake with the logit return hazard on the node's own history as well.

``v0.8.0`` is the released model, the same build as ``v0.8-a stake return u``: candidate a with the stake hurdle and
the return hazard on the node's own history, every other fitted parameter drawn once per run.

And it builds one model with delegations, outside the development scores:

* ``v0.8.1 stub``: :class:`~avalanche_research.model.delegated_lifecycle.DelegatedLifecycle` on v0.8's inputs, with
  the delegations open and scheduled at the origin, a Poisson flow of new delegations at the mean daily rate of the
  year before it and BENQI's share of that year, and the placeholder choice and BENQI allocation blocks. Its
  ``prepare`` needs ``delegations``: the origin's delegation tables, ``open``, ``validators`` and ``scheduled``, with
  ``flows``, and ``terms`` from :func:`~avalanche_research.model.delegated_lifecycle.delegation_terms`.

A variant is built in two steps. :meth:`Variant.prepare` reads the staking periods once per origin and returns the
inputs every batch shares, with the draw table for a variant that reads draws. :meth:`Variant.simulation` builds one
batch from them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date

import pandas as pd

from avalanche_research.model.delegated_lifecycle import (
    DelegatedLifecycle,
    delegation_inputs,
    historical_flow,
)
from avalanche_research.model.engine import SimulationModel
from avalanche_research.model.fitted_lifecycle import (
    FittedLifecycle,
    TrainingEvents,
    fit_blocks,
    fit_durations,
    fit_return_history,
    parameter_draws,
    stake_decisions,
    training_events,
    window_sd,
)
from avalanche_research.model.lifecycle import ValidatorLifecycle, origin_inputs
from avalanche_research.model.stake_lifecycle import (
    StakeLifecycle,
    build_stake_candidate,
    fitted_stake_settings,
)

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
    build: Callable[..., Prepared]

    def prepare(self, periods: str, origin: date, run: str, draws: int = 0, draw_seed: int = 0, **tables) -> Prepared:
        """The inputs at ``origin``. ``tables`` passes any further input tables a variant reads, by name."""
        return self.build(periods, origin, run, draws, draw_seed, **tables)

    def simulation(self, prepared: Prepared, seed: int, timesteps: int, runs: int,
                   draws: pd.DataFrame | None = None) -> SimulationModel:
        """One batch: ``runs`` runs of ``timesteps`` days under base seed ``seed``, reading ``draws`` when given."""
        extra = {"draws": draws} if draws is not None else {}
        return self.model(timesteps=timesteps, runs=runs, seed=seed, **prepared.inputs, **extra)


@dataclass(frozen=True)
class Switches:
    """The choices the v0.8 candidates differ in. The defaults are v0.8.

    ``node_record`` fits the renewal logit with the node's own renewal record (``fit_blocks``). ``move_stake_bands``
    and ``move_stake_weighted`` set the settings of the same names on :class:`FittedLifecycle`: the stake bands within
    which a moving node draws its stake ratio, and whether each move is weighted by its previous stake.
    ``duration_transition`` sets its ``durations`` to the duration band transition fitted before the origin.
    ``return_history`` sets its ``returns`` to the logit return hazard on the node's own history fitted before the
    origin, in place of the hazard by stake band and days out.
    """

    node_record: bool = True
    move_stake_bands: str = "ten log-spaced"
    move_stake_weighted: bool = True
    duration_transition: bool = False
    return_history: bool = False

    def settings(self) -> dict:
        """The model settings these switches set."""
        return {"move_stake_bands": self.move_stake_bands, "move_stake_weighted": self.move_stake_weighted}


V08 = Switches()

CANDIDATES: dict[str, Switches] = {
    "v0.8-a": Switches(node_record=False, move_stake_bands="three", move_stake_weighted=False),
    "v0.8-c": Switches(node_record=True, move_stake_bands="three", move_stake_weighted=True),
    "v0.8-e": V08,
}

DURATION = Switches(duration_transition=True)

_A = CANDIDATES["v0.8-a"]
ON_A: dict[str, Switches] = {
    "v0.8-a record": replace(_A, node_record=True),
    "v0.8-a bands": replace(_A, move_stake_bands="ten log-spaced"),
    "v0.8-a duration": replace(_A, duration_transition=True),
}

RETURN_HISTORY = replace(_A, return_history=True)

COMBINED_ON_A: dict[str, Switches] = {
    "v0.8-a bands return": replace(_A, move_stake_bands="ten log-spaced", return_history=True),
}


def switched_inputs(events: TrainingEvents, switches: Switches, large_above_avax: float | None = None) -> dict:
    """Every input of a v0.8 run fitted on ``events`` under ``switches``."""
    durations = {"durations": fit_durations(events)} if switches.duration_transition else {}
    returns = {"returns": fit_return_history(events)} if switches.return_history else {}
    return {**fit_blocks(events, large_above_avax, switches.node_record), **switches.settings(), **durations, **returns}


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
        table = parameter_draws(events, draws, draw_seed, tau, node_record=switches.node_record,
                                return_history=switches.return_history)
        return Prepared(inputs, table, tau, source)
    return build


def _stake_point(periods: str, origin: date, run: str, draws: int, draw_seed: int) -> Prepared:
    return build_stake_candidate(periods, origin, run, 0, draw_seed)


def _stake_on(switches: Switches, with_draws: bool) -> Callable[..., Prepared]:
    """The stake hurdle on the blocks ``switches`` fit. With draws, every other block redraws per run under the same
    switches and the hurdle stays at its point estimate, as ``v0.8-a stake u`` does."""
    def build(periods: str, origin: date, run: str, draws: int, draw_seed: int) -> Prepared:
        events = training_events(periods, origin, run)
        inputs = switched_inputs(events, switches)
        stake = fitted_stake_settings(stake_decisions(periods, origin, run), origin, run)
        if not with_draws:
            return Prepared({**inputs, **stake})
        inputs |= {"moves": events.moves, "first_commitments": events.first_commitments}
        tau, source = window_sd(periods, origin, inputs["renewal"])
        table = parameter_draws(events, draws, draw_seed, tau, node_record=switches.node_record,
                                return_history=switches.return_history)
        return Prepared({**inputs, **stake, "stake_point_estimate": True}, table, tau, source)
    return build


def _delegated_stub(periods: str, origin: date, run: str, draws: int, draw_seed: int,
                    delegations: dict[str, pd.DataFrame] | None = None) -> Prepared:
    if delegations is None:
        raise ValueError("v0.8.1 stub needs the origin's delegation tables and terms as delegations")
    events = training_events(periods, origin, run)
    return Prepared({
        **switched_inputs(events, V08), **delegation_inputs(delegations, periods, origin, events.state),
        "delegation_terms": delegations["terms"], "delegation_flow": historical_flow(delegations["flows"], origin),
    })


_CANDIDATE_DESCRIPTIONS = {
    "v0.8-a": "v0.8 without the node's own renewal record, with the stake ratio drawn unweighted within three stake bands",
    "v0.8-c": "v0.8-a with the node's own renewal record and the stake ratio weighted by previous stake",
    "v0.8-e": "v0.8-c with the stake ratio drawn within ten log-spaced stake bands, the same model as v0.8",
    "v0.8-a record": "v0.8-a with the node's own renewal record in the renewal logit",
    "v0.8-a bands": "v0.8-a with the stake ratio drawn unweighted within ten log-spaced stake bands",
    "v0.8-a duration": "v0.8-a with the next duration of a renewing or returning node drawn from a fitted transition between duration bands",
    "v0.8-a bands return": "v0.8-a with the stake ratio drawn unweighted within ten log-spaced stake bands and the return hazard on the node's own history",
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
        *(variant for name, switches in {**CANDIDATES, **ON_A, **COMBINED_ON_A}.items() for variant in (
            Variant(name, FittedLifecycle, _CANDIDATE_DESCRIPTIONS[name], _fitted(switches)),
            Variant(f"{name} u", FittedLifecycle, f"{name} with one draw of every fitted parameter per run", _fitted_with_draws(switches)),
        )),
        Variant("v0.8 duration", FittedLifecycle,
                "v0.8 with the next duration of a renewing or returning node drawn from a fitted transition between duration bands",
                _fitted(DURATION)),
        Variant("v0.8 duration u", FittedLifecycle, "v0.8 duration with one draw of every fitted parameter per run",
                _fitted_with_draws(DURATION)),
        Variant("v0.8-a return", FittedLifecycle,
                "v0.8-a with returns by a logit hazard on the node's own history: days out, stake band, returned before, first commitment only",
                _fitted(RETURN_HISTORY)),
        Variant("v0.8-a return u", FittedLifecycle, "v0.8-a return with one draw of every fitted parameter per run",
                _fitted_with_draws(RETURN_HISTORY)),
        Variant("v0.8-a stake", StakeLifecycle,
                "v0.8-a with each new commitment's stake from the fitted stake hurdle, given its duration",
                _stake_point),
        Variant("v0.8-a stake u", StakeLifecycle,
                "v0.8-a stake with one draw of every other fitted parameter per run; the stake hurdle is not resampled",
                build_stake_candidate),
        Variant("v0.8-a stake return", StakeLifecycle,
                "v0.8-a with the stake hurdle and the logit return hazard on the node's own history",
                _stake_on(RETURN_HISTORY, with_draws=False)),
        Variant("v0.8-a stake return u", StakeLifecycle,
                "v0.8-a stake return with one draw of every other fitted parameter per run; the stake hurdle is not resampled",
                _stake_on(RETURN_HISTORY, with_draws=True)),
        Variant("v0.8.0", StakeLifecycle,
                "the released v0.8.0: v0.8-a stake return with one draw of every other fitted parameter per run",
                _stake_on(RETURN_HISTORY, with_draws=True)),
        Variant("v0.8.1 stub", DelegatedLifecycle,
                "v0.8 with delegations: the open and scheduled ones at the origin, a flow at the year's rate, and placeholder choices",
                _delegated_stub),
    )
}

# The variants the development scores run, as before the candidates were registered.
DEVELOPMENT_MODELS: tuple[str, ...] = ("v0.7", "v0.8", "v0.8 separate", "v0.8 u")
