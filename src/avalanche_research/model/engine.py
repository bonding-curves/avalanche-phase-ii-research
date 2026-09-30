"""Run a cadCAD model whose settings are Param declarations, and return one long table.

A model is a :class:`SimulationModel` subclass. It declares its settings as Param parameters with bounds
and documentation, and defines ``initial_state`` and ``blocks``. Block functions are ordinary cadCAD
policies and state updates: they receive the settings as the plain ``params`` dict.

``run`` executes one model. ``sweep`` executes one model per combination of setting values. Both return
the same long table, one row per setting combination, run, timestep, and state variable, with the
settings as columns, so a plot can group or facet by any of them.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd
import param

RUN_CONTROLS = ("name", "timesteps", "runs")


class InvariantError(RuntimeError):
    """A state broke one of its model's invariants."""
INDEX = ["simulation", "run", "timestep"]


class SimulationModel(param.Parameterized):
    """A cadCAD model described by Param settings, an initial state, and partial state update blocks."""

    dt = param.Number(default=1.0, bounds=(0, None), inclusive_bounds=(False, True), doc="Model time per timestep")
    timesteps = param.Integer(default=100, bounds=(1, None), doc="Timesteps per run")
    runs = param.Integer(default=1, bounds=(1, None), doc="Monte Carlo runs per setting combination")

    def settings(self) -> dict[str, Any]:
        """The values block functions read, without the run controls or input tables.

        A parameter with negative precedence is an input, such as a table of exogenous events. Blocks read
        it from the model instance, and a companion string setting names its source.
        """
        return {key: value for key, value in self.param.values().items() if key not in RUN_CONTROLS and not self._is_input(key)}

    def _is_input(self, key: str) -> bool:
        precedence = self.param[key].precedence
        return precedence is not None and precedence < 0

    def initial_state(self) -> dict[str, float]:
        raise NotImplementedError

    def blocks(self) -> list[dict[str, dict]]:
        raise NotImplementedError

    def state_variables(self) -> list[str]:
        return list(self.initial_state())

    def invariants(self) -> list[tuple[str, Any]]:
        """Named checks on each new state. The engine stops the run at the first one that fails."""
        return []

    def checked_blocks(self) -> list[dict[str, dict]]:
        """The model's blocks, followed by one that checks every invariant on the state they produced."""
        checks = self.invariants()
        if not checks:
            return self.blocks()

        def p_invariants(params, substep, history, state):
            for name, holds in checks:
                if not holds(state):
                    raise InvariantError(f"invariant {name} fails at timestep {state['timestep']}")
            return {}

        return [*self.blocks(), {"policies": {"invariants": p_invariants}, "variables": {}}]

    def specification(self) -> dict[str, Any]:
        """Everything that decides the result: the model class, run controls, and settings."""
        values = {key: value for key, value in self.param.values().items() if key != "name" and not self._is_input(key)}
        return {"model": f"{type(self).__module__}.{type(self).__qualname__}", **values}

    def specification_hash(self) -> str:
        text = json.dumps(self.specification(), sort_keys=True, default=str)
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def with_settings(self, **values: Any) -> SimulationModel:
        """A new instance with some settings changed. Param validates every value on construction."""
        current = {key: value for key, value in self.param.values().items() if key != "name"}
        return type(self)(**{**current, **values})


def _execute(models: list[SimulationModel]) -> pd.DataFrame:
    from cadCAD.configuration import Experiment
    from cadCAD.configuration.utils import config_sim
    from cadCAD.engine import ExecutionContext, ExecutionMode, Executor

    experiment = Experiment()
    for model in models:
        experiment.append_configs(
            initial_state=model.initial_state(),
            partial_state_update_blocks=model.checked_blocks(),
            sim_configs=config_sim({
                "N": model.runs,
                "T": range(model.timesteps),
                "M": {key: [value] for key, value in model.settings().items()},
            }),
        )
    mode = ExecutionMode().local_mode if len(models) > 1 else ExecutionMode().single_mode
    raw, _tensor, _sessions = Executor(exec_context=ExecutionContext(mode), configs=experiment.configs).execute()
    return pd.DataFrame(raw)


def _long_table(raw: pd.DataFrame, models: list[SimulationModel]) -> pd.DataFrame:
    last = raw.groupby(INDEX)["substep"].transform("max")
    rows = raw[raw["substep"] == last]
    variables = models[0].state_variables()
    table = rows.melt(id_vars=INDEX, value_vars=variables, var_name="variable", value_name="value")
    settings = pd.DataFrame([{**model.settings(), "specification": model.specification_hash()} for model in models])
    settings.index.name = "simulation"
    table = table.merge(settings.reset_index(), on="simulation", how="left")
    table["time"] = table["timestep"] * table["dt"]
    front = ["simulation", "run", "timestep", "time", "variable", "value"]
    return table[front + [column for column in table.columns if column not in front]].reset_index(drop=True)


def run(model: SimulationModel) -> pd.DataFrame:
    """Execute one model and return its long table."""
    return _long_table(_execute([model]), [model])


def sweep(model: SimulationModel, grid: Mapping[str, Iterable[Any]]) -> pd.DataFrame:
    """Execute the model once for every combination of the values in ``grid``.

    Each combination builds a new validated instance, so a value outside a setting's bounds raises
    before any simulation starts.
    """
    keys = list(grid)
    models = [model.with_settings(**dict(zip(keys, values))) for values in itertools.product(*(grid[key] for key in keys))]
    return _long_table(_execute(models), models)
