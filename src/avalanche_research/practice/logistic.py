"""Logistic growth, UCLA Life Science 30A lectures 4.6, 5.2, 6.1, and 7.2: births in proportion to the
population, less crowding in proportion to its square. X' = b X - (b / K) X^2. Equilibria at 0, unstable,
and at K, stable."""

from __future__ import annotations

import param

from avalanche_research.model.engine import SimulationModel


def p_growth(params, substep, history, state):
    return {"delta_rabbits": params["b"] * state["rabbits"] * params["dt"]}


def p_crowding(params, substep, history, state):
    return {"delta_rabbits": -(params["b"] / params["K"]) * state["rabbits"] ** 2 * params["dt"]}


def s_rabbits(params, substep, history, state, signal):
    return "rabbits", state["rabbits"] + signal["delta_rabbits"]


class Logistic(SimulationModel):
    """A population limited by crowding, stepped by Euler's method."""

    b = param.Number(default=0.2, bounds=(0, None), doc="Birth rate, per year")
    K = param.Number(default=1000.0, bounds=(0, None), inclusive_bounds=(False, True), doc="Carrying capacity, rabbits")
    rabbits0 = param.Number(default=10.0, bounds=(0, None), doc="Rabbits at time zero")
    dt = param.Number(default=0.1, bounds=(0, None), inclusive_bounds=(False, True), doc="Years per timestep")
    timesteps = param.Integer(default=1000, bounds=(1, None), doc="Timesteps per run")

    def initial_state(self):
        return {"rabbits": self.rabbits0}

    def blocks(self):
        return [{"policies": {"growth": p_growth, "crowding": p_crowding}, "variables": {"rabbits": s_rabbits}}]

    def change(self, rabbits: float) -> float:
        """The change equation X' at a population, the lecture's change vector."""
        return self.b * rabbits * (1 - rabbits / self.K)

    def equilibria(self) -> dict[float, str]:
        """Each equilibrium and its stability, from the sign of dX'/dX there: +b at 0, -b at K."""
        return {0.0: "unstable", self.K: "stable"}
