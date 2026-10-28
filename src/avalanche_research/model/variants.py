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

And it builds two models with delegations, outside the development scores:

* ``v0.8.1 stub``: :class:`~avalanche_research.model.delegated_lifecycle.DelegatedLifecycle` on v0.8's inputs, with
  the delegations open and scheduled at the origin, a Poisson flow of new delegations at the mean daily rate of the
  year before it and BENQI's share of that year, and the placeholder choice and BENQI allocation blocks. Its
  ``prepare`` needs ``delegations``: the origin's delegation tables, ``open``, ``validators`` and ``scheduled``, with
  ``flows``, and ``terms`` from :func:`~avalanche_research.model.delegated_lifecycle.delegation_terms`.
* ``v0.8.1 events``: v0.8.1 stub with the named operators known at the origin from the operator events
  (:mod:`~avalanche_research.model.operator_events`): each delegation's owner, new ones included, each named operator's
  delegated stake as a state variable, and the closing day of any operator whose shutdown was public by the origin,
  from which it makes no new delegation. Its ``prepare`` needs
  ``delegations`` as the stub's does, with ``starts``. ``operator_events`` and ``operator_attributions`` replace the
  files' rows when given.

And one candidate for v0.8.1 on the released base, outside the development scores:

* ``v0.8.1 candidate``: :class:`~avalanche_research.model.delegated_lifecycle.DelegatedStakeLifecycle`, the ``v0.8.0``
  build with the delegations open and scheduled at the origin, new delegations under the frozen v0.8.1 laws (the flow at
  the mean of the 28 days before the origin, the ordinary choice in proportion to own stake plus open delegated stake,
  BENQI's two-stage choice over its prior-use set, the containment choice set with each delegation placed on the room the
  one before left), the named operators known at the origin, and one operator type with no shift. Its ``prepare`` needs
  ``delegations`` as ``v0.8.1 events`` does, with ``benqi_choices`` from
  :func:`~avalanche_research.model.delegated_lifecycle.benqi_choices`.

And one candidate for v0.9 on the v0.8.1 candidate, outside the development scores:

* ``v0.9 holders``: :class:`~avalanche_research.model.holder_lifecycle.HolderStakeLifecycle`, the ``v0.8.1 candidate``
  with the holder rules of :mod:`~avalanche_research.model.parts.holders` available behind the ``holders`` setting, off
  by default. Its ``prepare`` takes the candidate's ``delegations`` and, optionally, ``funds``, the fund holdings table
  at the origin, and adds the renewal block fitted above the 1,000,000 AVAX line as a point estimate and BENQI's mean
  stake per start over the 28 days before the origin. With ``holders`` unset it runs as the candidate does.

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
    CONTAINMENT,
    DelegatedLifecycle,
    DelegatedStakeLifecycle,
    delegation_inputs,
    historical_flow,
    recent_flow,
)
from avalanche_research.model.delegation_blocks import BenqiTwoStage, ProportionalChoice
from avalanche_research.model.engine import SimulationModel
from avalanche_research.model.fitted_lifecycle import (
    FittedLifecycle,
    TrainingEvents,
    fit_blocks,
    fit_durations,
    fit_return_history,
    parameter_draws,
    renewal_inputs,
    split_at_line,
    stake_decisions,
    training_events,
    window_sd,
)
from avalanche_research.model.holder_lifecycle import (
    HolderStakeLifecycle,
    benqi_stake_per_start,
)
from avalanche_research.model.lifecycle import ValidatorLifecycle, origin_inputs
from avalanche_research.model.operator_events import named_operators
from avalanche_research.model.parts.operator_types import ClassShift
from avalanche_research.model.parts.renewal import RenewalLogit
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
        "delegation_terms": delegations["terms"].drop(columns="transaction_hash", errors="ignore"),
        "delegation_flow": historical_flow(delegations["flows"], origin),
    })


def _delegated_events(periods: str, origin: date, run: str, draws: int, draw_seed: int,
                      delegations: dict[str, pd.DataFrame] | None = None, operator_events: list[dict] | None = None,
                      operator_attributions: list[dict] | None = None) -> Prepared:
    if delegations is None or "starts" not in delegations or "terms" not in delegations:
        raise ValueError("v0.8.1 events needs the origin's delegation tables, with starts, and terms as delegations")
    named = named_operators(origin, operator_events, operator_attributions)
    events = training_events(periods, origin, run)
    # delegation_inputs returns the terms with each one's owner.
    return Prepared({
        **switched_inputs(events, V08), **delegation_inputs(delegations, periods, origin, events.state, named),
        "delegation_flow": historical_flow(delegations["flows"], origin),
    })


def _delegated_candidate(periods: str, origin: date, run: str, draws: int, draw_seed: int,
                         delegations: dict[str, pd.DataFrame] | None = None, operator_events: list[dict] | None = None,
                         operator_attributions: list[dict] | None = None) -> Prepared:
    """The v0.8.1 candidate's inputs: the released build's, with parameter draws when asked, plus the delegations under
    the frozen laws, the named operators and one operator type. The delegation tables are passed built as
    ``delegations``; ``experiments.v081_inputs`` builds them from the runs a verified pin names."""
    needed = ("open", "validators", "scheduled", "flows", "starts", "terms", "benqi_choices")
    if delegations is None or any(name not in delegations for name in needed):
        raise ValueError(f"v0.8.1 candidate needs the origin's delegation tables as delegations: {', '.join(needed)}")
    named = named_operators(origin, operator_events, operator_attributions)
    base = _stake_on(RETURN_HISTORY, with_draws=bool(draws))(periods, origin, run, draws, draw_seed)
    events = training_events(periods, origin, run)
    inputs = {
        **base.inputs,
        **delegation_inputs(delegations, periods, origin, events.state, named, prior_use=True),
        "delegation_flow": recent_flow(delegations["flows"], origin),
        "delegator_choice": ProportionalChoice(),
        "benqi_allocation": BenqiTwoStage.observed(delegations["benqi_choices"]["new"].to_numpy(dtype=bool),
                                                   f"{run or 'staking periods'}, BENQI's choices in the 365 days to {origin}"),
        "placement_rule": CONTAINMENT,
        "placement_batch": 1,
        "operator_types": ClassShift(),
        # Every unstaked AVAX carries the same hazard of being staked for the first time (parts.participation).
        "participation_elasticity": 1.0,
    }
    return Prepared(inputs, base.draws, base.tau, base.tau_source)


def _holders_candidate(periods: str, origin: date, run: str, draws: int, draw_seed: int,
                       delegations: dict[str, pd.DataFrame] | None = None, operator_events: list[dict] | None = None,
                       operator_attributions: list[dict] | None = None, funds: pd.DataFrame | None = None) -> Prepared:
    """The v0.9 holders variant's inputs: the v0.8.1 candidate's, plus the renewal block fitted on the endings above the
    large-holder line (a point estimate the draws do not resample), BENQI's mean stake per start over the 28 days before
    the origin, and the fund holdings table when given."""
    base = _delegated_candidate(periods, origin, run, draws, draw_seed, delegations, operator_events, operator_attributions)
    events = training_events(periods, origin, run)
    # The institutional renewal block, fitted as candidate a fits its renewal block (no node record), above the line.
    _, large = split_at_line(events.endings, LARGE_ABOVE_AVAX, events.window)
    large_block = RenewalLogit.fit(renewal_inputs(large, False), large["renewed"].to_numpy(),
                                   f"{events.window}, above {LARGE_ABOVE_AVAX:,.0f} AVAX: {len(large)} endings, node record left out, "
                                   "point estimate not resampled")
    inputs = {**base.inputs, "benqi_stake_per_start_navax": benqi_stake_per_start(delegations.get("starts"), origin),
              "holder_renewal_large": large_block}
    if funds is not None:
        inputs["fund_holdings"] = funds
    return Prepared(inputs, base.draws, base.tau, base.tau_source)


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
        Variant("v0.8.1 events", DelegatedLifecycle,
                "v0.8.1 stub with the named operators known at the origin, their delegations tracked and their closures scheduled",
                _delegated_events),
        Variant("v0.8.1 candidate", DelegatedStakeLifecycle,
                "v0.8.0 with delegations under the frozen v0.8.1 laws, the named operators known at the origin, one operator type "
                "and the arrival rate in proportion to the unstaked share of supply",
                _delegated_candidate),
        Variant("v0.9 holders", HolderStakeLifecycle,
                "the v0.8.1 candidate with the holder rules available behind the holders setting: liquid staking, funds, "
                "institutional and small operators, and delegators; off by default",
                _holders_candidate),
    )
}

# The variants the development scores run, as before the candidates were registered.
DEVELOPMENT_MODELS: tuple[str, ...] = ("v0.7", "v0.8", "v0.8 separate", "v0.8 u")
