"""The bathtub, UCLA Life Science 30A lecture 4.1: a faucet fills the tub and the drain empties it in
proportion to the level. X' = inflow - k X. Its one equilibrium, inflow / k, is stable."""

from __future__ import annotations

import math

import param

from avalanche_research.model.engine import SimulationModel


def p_faucet(params, substep, history, state):
    return {"delta_water": params["inflow"] * params["dt"]}


def p_drain(params, substep, history, state):
    return {"delta_water": -params["k"] * state["water"] * params["dt"]}


def s_water(params, substep, history, state, signal):
    return "water", state["water"] + signal["delta_water"]


class Bathtub(SimulationModel):
    """Water in a tub, in gallons, stepped by Euler's method."""

    inflow = param.Number(default=10.0, bounds=(0, None), doc="Faucet inflow, gallons per minute")
    k = param.Number(default=0.2, bounds=(0, None), doc="Drain rate, per minute: the share of the water that leaves each minute")
    water0 = param.Number(default=0.0, bounds=(0, None), doc="Water at time zero, gallons")
    dt = param.Number(default=0.1, bounds=(0, None), inclusive_bounds=(False, True), doc="Minutes per timestep")
    timesteps = param.Integer(default=400, bounds=(1, None), doc="Timesteps per run")

    def initial_state(self):
        return {"water": self.water0}

    def blocks(self):
        return [{"policies": {"faucet": p_faucet, "drain": p_drain}, "variables": {"water": s_water}}]

    def equilibrium(self) -> float:
        return self.inflow / self.k

    def exact(self, time: float) -> float:
        """The exact solution the Euler steps approximate."""
        return self.equilibrium() + (self.water0 - self.equilibrium()) * math.exp(-self.k * time)
