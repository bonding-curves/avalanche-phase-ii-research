"""The Allee effect, UCLA Life Science 30A lectures 6.1, 7.2, and 11.2: X' = b X (1 - X/K) (X/A - 1).

Below the minimum viable population A the population dies out, and above it the population grows to the
carrying capacity K. So 0 and K are stable and A is unstable, with slopes -b, b (1 - A/K), and b (1 - K/A)
of X' at the three equilibria. The staking analogue, our inference: a validator set, or an L1's, needs a
minimum stake to cover fixed costs, and below that threshold it shrinks to zero.
"""

from __future__ import annotations

import param

from avalanche_research.model.engine import SimulationModel


def p_growth(params, substep, history, state):
    x = state["animals"]
    change = params["b"] * x * (1 - x / params["K"]) * (x / params["A"] - 1)
    return {"delta_animals": change * params["dt"]}


def s_animals(params, substep, history, state, signal):
    return "animals", state["animals"] + signal["delta_animals"]


class Allee(SimulationModel):
    """A population with a minimum viable size, stepped by Euler's method."""

    b = param.Number(default=0.1, bounds=(0, None), doc="Growth rate, per unit time, from lecture 11.2")
    A = param.Number(default=20.0, bounds=(0, None), inclusive_bounds=(False, True), doc="Minimum viable population. Not spoken in the lectures, our choice")
    K = param.Number(default=100.0, bounds=(0, None), inclusive_bounds=(False, True), doc="Carrying capacity. Not spoken in the lectures, our choice")
    animals0 = param.Number(default=25.0, bounds=(0, None), doc="Animals at time zero")
    dt = param.Number(default=0.05, bounds=(0, None), inclusive_bounds=(False, True), doc="Time per timestep")
    timesteps = param.Integer(default=10_000, bounds=(1, None), doc="Timesteps per run")

    def initial_state(self):
        return {"animals": self.animals0}

    def blocks(self):
        return [{"policies": {"growth": p_growth}, "variables": {"animals": s_animals}}]

    def slope(self, x: float) -> float:
        """dX'/dX at x, whose sign gives each equilibrium's stability."""
        b, a, k = self.b, self.A, self.K
        return b * ((1 - 2 * x / k) * (x / a - 1) + (x - x * x / k) / a)
