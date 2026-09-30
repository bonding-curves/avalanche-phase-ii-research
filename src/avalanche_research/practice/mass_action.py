"""Mass action chemistry, UCLA Life Science 30A lecture 4.7: the reversible reaction X + Y <-> Z.

    x' = kb z - kf x y
    y' = kb z - kf x y
    z' = kf x y - kb z

The forward reaction runs in proportion to how often X meets Y, and the back reaction in proportion to Z.
x + z and y + z are conserved, and at equilibrium z / (x y) = kf / kb.
"""

from __future__ import annotations

import param

from avalanche_research.model.engine import SimulationModel


def p_forward(params, substep, history, state):
    rate = params["kf"] * state["x"] * state["y"] * params["dt"]
    return {"delta_x": -rate, "delta_y": -rate, "delta_z": rate}


def p_backward(params, substep, history, state):
    rate = params["kb"] * state["z"] * params["dt"]
    return {"delta_x": rate, "delta_y": rate, "delta_z": -rate}


def s_add(name):
    return lambda params, substep, history, state, signal: (name, state[name] + signal[f"delta_{name}"])


class MassAction(SimulationModel):
    """Concentrations of X, Y, and Z, as fractions of volume, stepped by Euler's method."""

    kf = param.Number(default=2.0, bounds=(0, None), doc="Forward rate constant, per unit concentration per unit time")
    kb = param.Number(default=0.5, bounds=(0, None), doc="Back rate constant, per unit time")
    x0 = param.Number(default=0.6, bounds=(0, 1), doc="Concentration of X at time zero")
    y0 = param.Number(default=0.4, bounds=(0, 1), doc="Concentration of Y at time zero")
    z0 = param.Number(default=0.0, bounds=(0, 1), doc="Concentration of Z at time zero")
    dt = param.Number(default=0.01, bounds=(0, None), inclusive_bounds=(False, True), doc="Time per timestep")
    timesteps = param.Integer(default=3000, bounds=(1, None), doc="Timesteps per run")

    def initial_state(self):
        return {"x": self.x0, "y": self.y0, "z": self.z0}

    def blocks(self):
        return [{"policies": {"forward": p_forward, "backward": p_backward}, "variables": {name: s_add(name) for name in ("x", "y", "z")}}]

    def invariants(self):
        tolerance = 1e-9
        return [
            ("x + z conserved", lambda state: abs(state["x"] + state["z"] - (self.x0 + self.z0)) < tolerance),
            ("y + z conserved", lambda state: abs(state["y"] + state["z"] - (self.y0 + self.z0)) < tolerance),
        ]
