"""The model's versions as the Foundation sees them: one capability per version, each shown on one call.

v0.6 was the July behaviour work, shown as 0.6.0-alpha.1 on 2026-08-28. v0.7 is the lifecycle model on the
cadCAD and Param engine, tagged ``model-v0.7.0``. Later rows are the planned ladder, on the compressed schedule Shawn approved on 2026-10-01. A version is released
when it is tagged ``model-vX.Y.Z`` on this repository, and ``MODEL_VERSION`` then names it.
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
    Version("v0.8", date(2026, 10, 30), "Validator behaviour fitted to the chain: renewal by tenure, entry, operators", False),
    Version("v0.8.1", date(2026, 10, 30), "Delegations, with BENQI as its own block", False),
    Version("v0.9", date(2026, 10, 30), "Reward and admission designs compared on one yardstick", False),
    Version("v0.10", date(2026, 11, 13), "Sensitivity and where staking incentives hold", False),
    Version("v1.0", date(2026, 11, 27), "The recommendations, as a model the Foundation runs itself", False),
)

EVENTS: tuple[tuple[date, str], ...] = (
    (date(2026, 9, 22), "Helicon"),
    (date(2026, 11, 27), "Milestone 2 sign-off"),
    (date(2026, 12, 14), "Release tagged"),
    (date(2026, 12, 21), "ACP-285 ramp ends"),
    (date(2027, 1, 8), "Final report"),
)
