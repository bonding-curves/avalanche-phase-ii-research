"""Fitted stake hurdle behind an explicit lifecycle switch.

This point-estimate candidate changes only stakes of new validator commitments.
The existing continuation supplies duration first. Scheduled commitments retain
accepted stakes. The explicit stake_point_estimate setting permits other-block
and duration bootstrap draws while labelling the stake hurdle as not resampled.
Without that setting, node-resample draws require a per-run stake refit and refuse.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import param

from avalanche_research.model.fitted_lifecycle import (
    FittedLifecycle,
    checked_stake_decisions,
    stake_decisions,
    training_events,
)
from avalanche_research.model.parts.participation import cap_started
from avalanche_research.model.parts.stake_choice import (
    CONTEXTS,
    StakeChoice,
    table_sha256,
)

if TYPE_CHECKING:
    from avalanche_research.model.variants import Prepared


def _sha256(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def stake_law_record(block: StakeChoice) -> dict:
    """Every fitted value and source, including the historical entry-score law.

    StakeChoice stores cells outside Param. Serializing only its Param settings
    therefore misses the actual fitted law. Its public sources expose cell
    probabilities and quantile knots. The entry baseline is separately included.
    """
    return {"class": f"{type(block).__module__}.{type(block).__qualname__}",
            "sources": block.sources(), "entry_baseline_stakes_navax": block._entry_stakes}


def fitted_stake_settings(tables: Mapping[str, pd.DataFrame], origin: date, run: str) -> dict:
    """Fit checked producer tables without changing their original CSV attrs.

    The producer's SHA is a CSV digest. StakeChoice uses ordered JSON rows, so
    its proposed labels are generated separately and both encodings are bound
    in the model receipt. This verifies byte identity, not source authenticity.
    """
    if set(tables) != set(CONTEXTS):
        raise ValueError("stake decisions must contain exactly renewal, return and entry")
    labels, receipts, copied = {}, {}, {}
    for context in CONTEXTS:
        table = checked_stake_decisions(context, tables[context])
        expected = {"context": context, "run": run, "origin": origin.isoformat()}
        if any(table.attrs.get(key) != value for key, value in expected.items()):
            raise ValueError(f"{context}: stake producer context, run and origin attrs must agree")
        csv_sha = hashlib.sha256(table.to_csv(index=False).encode()).hexdigest()
        if table.attrs.get("sha256") != csv_sha:
            raise ValueError(f"{context}: current producer CSV SHA-256 is required")
        expected_source = f"{run}; origin {origin.isoformat()}; 365 days; sha256 {csv_sha}"
        if table.attrs.get("source") != expected_source or not table.attrs.get("window"):
            raise ValueError(f"{context}: producer source label and window attrs are required")
        json_sha = table_sha256(table)
        labels[context] = f"{run}; origin {origin.isoformat()}; 365 days; sha256 {json_sha}"
        receipts[context] = {"rows": len(table), "producer_csv_sha256": csv_sha,
                             "ordered_json_sha256": json_sha, "producer_attrs": dict(table.attrs),
                             "stake_choice_evidence": labels[context]}
        copied[context] = table.copy(deep=True)
    block = StakeChoice.fit(*(copied[context] for context in CONTEXTS), evidence=labels)
    receipt = {"origin": origin.isoformat(), "run": run, "contexts": receipts,
               "stake_parameter_uncertainty": "absent: fixed point-estimate stake law"}
    binding = _sha256({"law": stake_law_record(block), "receipt": receipt})
    return {"fitted_stake": True, "stake_choice": block,
            "stake_fit_receipt": receipt, "stake_fit_sha256": binding}


class StakeLifecycle(FittedLifecycle):
    """FittedLifecycle with a duration-conditioned stake law explicitly enabled.

    At fitted_stake=False, settings, specification and simulation output are
    identical to FittedLifecycle. With it enabled, the full stake law and both
    source encodings participate in the specification digest.
    """
    fitted_stake = param.Boolean(default=False, constant=True, metadata={"omit_at_default": True})
    stake_point_estimate = param.Boolean(
        default=False, constant=True, metadata={"omit_at_default": True},
        doc="Allow other-block and duration bootstrap draws while the stake hurdle stays fixed, labelled stake hurdle not resampled",
    )
    stake_choice = param.ClassSelector(class_=StakeChoice, default=None, allow_None=True, constant=True)
    stake_fit_receipt = param.Dict(default=None, allow_None=True, constant=True)
    stake_fit_sha256 = param.String(default="", constant=True)

    def __init__(self, **params):
        super().__init__(**params)
        if self.fitted_stake:
            self._check_stake_binding()
            self.stages = tuple((name, self._stake_continuation if name == "continuation" else stage)
                                for name, stage in FittedLifecycle.stages)
        elif (self.stake_point_estimate or any(value is not None for value in (self.stake_choice, self.stake_fit_receipt))
              or self.stake_fit_sha256):
            raise ValueError("give stake fit inputs only with fitted_stake=True")

    def _check_stake_binding(self):
        if self.stake_choice is None or self.stake_fit_receipt is None:
            raise ValueError("fitted_stake=True needs the checked fitted stake law and receipt")
        if self.stake_fit_receipt.get("origin") != self.origin.isoformat():
            raise ValueError("stake fit origin differs from the lifecycle origin")
        if self.stake_fit_receipt.get("run") != self.inputs_source:
            raise ValueError("stake fit run differs from lifecycle inputs_source")
        current = _sha256({"law": stake_law_record(self.stake_choice), "receipt": self.stake_fit_receipt})
        if current != self.stake_fit_sha256:
            raise ValueError("stake law or source receipt changed after its fit: SHA-256 mismatch")
        if self.draws is not None and "resample_seed" in self.draws.columns and not self.stake_point_estimate:
            raise ValueError("fitted stake does not yet support resample_seed: refit the stake law on each run's same node resample")

    def settings(self):
        settings = super().settings()
        # The full fitted law is bound in specification, its digest is a small
        # stable table setting. Internal fit objects need not become table cells.
        for key in ("stake_choice", "stake_fit_receipt"):
            settings.pop(key, None)
        if not self.fitted_stake:
            settings.pop("stake_fit_sha256", None)
        else:
            self._check_stake_binding()
        return settings

    def specification(self):
        specification = super().specification()
        if not self.fitted_stake:
            for key in ("stake_choice", "stake_fit_receipt", "stake_fit_sha256"):
                specification.pop(key, None)
            specification["model"] = f"{FittedLifecycle.__module__}.{FittedLifecycle.__qualname__}"
        else:
            self._check_stake_binding()
            specification["stake_choice"] = stake_law_record(self.stake_choice)
            if self.stake_point_estimate:
                specification["stake_uncertainty"] = "stake hurdle not resampled"
        return specification

    def blocks(self):
        if self.fitted_stake:
            self._check_stake_binding()
        return super().blocks()

    def _stake_continuation(self, state, day, earlier):
        """Draw duration first, then stake on the same keyed uniforms as before, then fund the stakes from the
        unstaked supply (parts.participation)."""
        blocks, draw = day.blocks, day.draw
        renewal, returns, arrivals = earlier["renewal"], earlier["returns"], earlier["arrivals"]
        ended, renews, comes_back = renewal["ended"], renewal["renews"], returns["comes_back"]
        new_key, n_new = arrivals["node_key"], arrivals["count"]
        renewed_key, renewed_done = ended["node_key"][renews], ended["done"][renews]
        back_key, back_done = state["out_node_key"][comes_back], state["out_done"][comes_back]
        next_days = (blocks.continuation.durations_from_uniforms if blocks.durations is None
                     else blocks.durations.days_from_uniforms)
        entry_u = draw.uniforms("first_days", new_key)
        entry_days = blocks.first_days[np.minimum((entry_u * len(blocks.first_days)).astype(np.int64),
                                                   len(blocks.first_days) - 1)] if n_new else np.zeros(0, dtype=np.int64)
        durations = (
            next_days(ended["days"][renews], draw.uniforms("renew_days", renewed_key, renewed_done)),
            next_days(state["out_last_days"][comes_back], draw.uniforms("return_days", back_key, back_done)),
            entry_days,
        )
        previous = (ended["stakes"][renews], state["out_stakes"][comes_back], np.zeros(n_new, dtype=np.int64))
        uniforms = (draw.uniforms("renew_stake", renewed_key, renewed_done),
                    draw.uniforms("return_stake", back_key, back_done), draw.uniforms("first_stake", new_key))
        stakes = [self.stake_choice.stakes_from_uniforms(context, before, days, u)
                  for context, before, days, u in zip(CONTEXTS, previous, durations, uniforms)]
        started = {
            "stakes": np.concatenate(stakes), "days": np.concatenate(durations),
            "node_key": np.concatenate([renewed_key, back_key, new_key]),
            "done": np.concatenate([renewed_done + 1, back_done, np.zeros(n_new, dtype=np.int64)]),
            "after_return": np.concatenate([np.zeros(int(renews.sum()), bool), np.ones(int(comes_back.sum()), bool), np.zeros(n_new, bool)]),
            "returns": np.concatenate([ended["returns"][renews], state["out_returns"][comes_back] + 1, np.zeros(n_new, dtype=np.int64)]),
        }
        return cap_started(state, day, earlier, started, int(renews.sum()), int(comes_back.sum()))


def build_stake_candidate(periods: str, origin: date, run: str, draws: int = 0, draw_seed: int = 0) -> Prepared:
    """Variant build callable: candidate-a inputs plus the checked stake law.

    With requested draws, every other block and the continuation duration tables
    follow the standard bootstrap. The stake hurdle stays at its fitted point
    estimate under an explicit specification setting. Registry ownership remains
    with the caller.
    """
    from avalanche_research.model.variants import CANDIDATES, Prepared, switched_inputs

    events = training_events(periods, origin, run)
    inputs = switched_inputs(events, CANDIDATES["v0.8-a"])
    stake = fitted_stake_settings(stake_decisions(periods, origin, run), origin, run)
    if not draws:
        return Prepared({**inputs, **stake})
    from avalanche_research.model.fitted_lifecycle import parameter_draws, window_sd

    inputs |= {"moves": events.moves, "first_commitments": events.first_commitments}
    tau, source = window_sd(periods, origin, inputs["renewal"])
    return Prepared({**inputs, **stake, "stake_point_estimate": True},
                    parameter_draws(events, draws, draw_seed, tau, node_record=False), tau, source)
