"""The model's versions as the Foundation sees them: one capability per version, each shown on one call.

v0.6 was the July behaviour work, shown as 0.6.0-alpha.1 on 2026-08-28. v0.7 is the lifecycle model on the cadCAD and
Param engine, tagged ``model-v0.7.0``. v0.8 fits the model's behaviour to the chain, tagged ``model-v0.8.0``. Later rows
are the planned ladder. A version is released when it is tagged ``model-vX.Y.Z`` on this repository, and
``MODEL_VERSION`` then names it. The calls run every two weeks from 2026-10-16: 10-16, 10-30, 11-13, 11-27 and 12-11,
with 12-25 unconfirmed. v0.8.1 is shown on 10-16 if it is tagged by then, otherwise on 10-30. The sensitivity layer once
planned as v0.10 is the Milestone 2 analysis on v0.8.0, so v0.10 is not a version.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Version:
    name: str
    call: date
    capability: str
    released: bool


VERSIONS: tuple[Version, ...] = (
    Version("v0.6", date(2026, 8, 28), "Renewal, entry and duration choice in one commitment ledger", True),
    Version("v0.7", date(2026, 10, 2), "The model on the chain: exact ledger replay, validator lifecycle, mechanisms", True),
    Version("v0.8", date(2026, 10, 16),
            "Validator behaviour fitted to the chain: renewal, returns on each node's history, stake by duration, entry", True),
    Version("v0.8.1", date(2026, 10, 16), "Delegations, with BENQI and the named operators", False),
    Version("v0.9", date(2026, 10, 30), "Reward and admission designs compared on one yardstick", False),
    Version("v1.0", date(2026, 11, 27), "The recommendations, as a model the Foundation runs itself", False),
)

EVENTS: tuple[tuple[date, str], ...] = (
    (date(2026, 9, 22), "Helicon"),
    (date(2026, 12, 21), "ACP-285 ramp ends"),
    (date(2027, 1, 8), "Final report"),
)
