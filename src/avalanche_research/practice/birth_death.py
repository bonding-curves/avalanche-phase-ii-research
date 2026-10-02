"""Birth and death, UCLA Life Science 30A lectures 4.2, 4.3, and 4.6: X' = b X - d X = (b - d) X.

Births and deaths are two policies, each a rate per unit time times the population. The net rate b - d
sets exponential growth or decay, and the equilibrium at zero is unstable when b > d.
"""

from __future__ import annotations

import math

import param

from avalanche_research.model.engine import SimulationModel


def p_births(params, substep, history, state):
    return {"delta_animals": params["birth_rate"] * state["animals"] * params["dt"]}


def p_deaths(params, substep, history, state):
    return {"delta_animals": -params["death_rate"] * state["animals"] * params["dt"]}


def s_animals(params, substep, history, state, signal):
    return "animals", state["animals"] + signal["delta_animals"]


class BirthDeath(SimulationModel):
    """A population with constant per-capita birth and death rates, stepped by Euler's method."""

    birth_rate = param.Number(default=0.2, bounds=(0, None), doc="Births per animal per unit time")
    death_rate = param.Number(default=0.1, bounds=(0, None), doc="Deaths per animal per unit time")
    animals0 = param.Number(default=10.0, bounds=(0, None), doc="Animals at time zero")
    dt = param.Number(default=0.01, bounds=(0, None), inclusive_bounds=(False, True), doc="Time per timestep")
    timesteps = param.Integer(default=1000, bounds=(1, None), doc="Timesteps per run")

    def initial_state(self):
        return {"animals": self.animals0}

    def blocks(self):
        return [{"policies": {"births": p_births, "deaths": p_deaths}, "variables": {"animals": s_animals}}]

    def change(self, animals: float) -> float:
        """The change vector X' at a population."""
        return (self.birth_rate - self.death_rate) * animals

    def doubling_time(self) -> float:
        """ln 2 over the net rate, for growth."""
        return math.log(2) / (self.birth_rate - self.death_rate)

    def euler(self, steps: int) -> float:
        """The exact value of the Euler iteration, X0 (1 + r dt)^n, which the simulation must equal."""
        return self.animals0 * (1 + (self.birth_rate - self.death_rate) * self.dt) ** steps
