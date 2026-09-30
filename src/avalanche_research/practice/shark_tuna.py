"""Shark and tuna, UCLA Life Science 30A lectures 4.2, 4.4, 5.3: Lotka-Volterra predator and prey.

    T' = bT T - beta S T
    S' = m beta S T - dS S

With every parameter 1 the equilibrium (1, 1) is a neutral centre, so the cycle depends on the start, and
H = S - ln S + T - ln T is conserved by the exact flow. Euler's method does not conserve it, and the drift
shrinks with the step, which makes this model the step-size test.
"""

from __future__ import annotations

import math

import param

from avalanche_research.model.engine import SimulationModel


def p_tuna_births(params, substep, history, state):
    return {"delta_tuna": params["tuna_birth"] * state["tuna"] * params["dt"], "delta_sharks": 0.0}


def p_hunting(params, substep, history, state):
    eaten = params["hunting"] * state["sharks"] * state["tuna"] * params["dt"]
    return {"delta_tuna": -eaten, "delta_sharks": params["sharks_per_tuna"] * eaten}


def p_shark_deaths(params, substep, history, state):
    return {"delta_tuna": 0.0, "delta_sharks": -params["shark_death"] * state["sharks"] * params["dt"]}


def s_tuna(params, substep, history, state, signal):
    return "tuna", state["tuna"] + signal["delta_tuna"]


def s_sharks(params, substep, history, state, signal):
    return "sharks", state["sharks"] + signal["delta_sharks"]


class SharkTuna(SimulationModel):
    """Sharks and tuna, in the lecture's units, stepped by Euler's method."""

    tuna_birth = param.Number(default=1.0, bounds=(0, None), doc="Tuna births per tuna per unit time")
    hunting = param.Number(default=1.0, bounds=(0, None), doc="Tuna eaten per shark per tuna per unit time")
    sharks_per_tuna = param.Number(default=1.0, bounds=(0, None), doc="Sharks born per tuna eaten")
    shark_death = param.Number(default=1.0, bounds=(0, None), doc="Shark deaths per shark per unit time")
    sharks0 = param.Number(default=2.0, bounds=(0, None), doc="Sharks at time zero")
    tuna0 = param.Number(default=3.0, bounds=(0, None), doc="Tuna at time zero")
    dt = param.Number(default=0.1, bounds=(0, None), inclusive_bounds=(False, True), doc="Time per timestep")
    timesteps = param.Integer(default=500, bounds=(1, None), doc="Timesteps per run")

    def initial_state(self):
        return {"sharks": self.sharks0, "tuna": self.tuna0}

    def blocks(self):
        return [{
            "policies": {"tuna_births": p_tuna_births, "hunting": p_hunting, "shark_deaths": p_shark_deaths},
            "variables": {"tuna": s_tuna, "sharks": s_sharks},
        }]

    def invariants(self):
        return [("populations positive", lambda state: state["sharks"] > 0 and state["tuna"] > 0)]

    def conserved(self, sharks: float, tuna: float) -> float:
        """H, conserved by the exact flow when every parameter is 1."""
        return sharks - math.log(sharks) + tuna - math.log(tuna)
