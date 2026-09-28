"""Behavioural parameters: validator entry, duration choice, renewal, exit, and net delegation flow.

``BehaviourParams.from_json`` reads the file the behaviour calibration writes (``data/model/behaviour-v0.json``).
Without that file the defaults below apply. Every default is an assumption, not an estimate: the 2024 observed
average of the quantity, with no response to the spread. They were computed on 2026-09-28 from
``derived.staking-periods`` run ``staking-periods-2026-09-22`` over periods starting (or ending) in calendar 2024:

- entry 7.33 validators per day: 2,682 validator periods started in 2024 whose node had no period ending in the
  7 days before the start, divided by 366.
- entrant self stake 135,622 AVAX: mean stake of those 2,682 periods.
- duration menu probabilities 0.6326, 0.2449, 0.0881, 0.0161, 0.0183: the 16,327 validator periods started in 2024
  assigned to the nearest of 14, 30, 90, 180, 365 days.
- renewal 0.827: share of the 16,514 validator periods ending in 2024 whose node started a new period between one
  day before and seven days after the end.
- delegation duration 34 days: stake-weighted mean duration of the 3,053,179 delegations started in 2024 (33.68).
- reward pass rates 0.9874 (validators) and 0.9927 (delegations): rewarded share of potential rewards of periods
  ending in 2024.
- validator fee share 0.0667: validator fee transfers over potential rewards of rewarded delegations ending in 2024.

"Spread" is the annualized staking reward rate minus the external yield, both as fractions. The functional forms
the engine applies are in ``policies.py``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

DEFAULT_SOURCE = "default assumptions: 2024 observed averages from staking-periods-2026-09-22, no response to the spread"
# Fields the behaviour file does not carry; they are always assumptions of the engine.
ENGINE_ASSUMPTIONS = (
    "entry_stake_avax", "delegation_duration_days", "quote_duration_days",
    "validator_reward_pass_rate", "delegated_reward_pass_rate", "validator_fee_share",
)


@dataclass(frozen=True)
class BehaviourParams:
    version: str = "default"
    source: str = DEFAULT_SOURCE
    entry_base_per_day: float = 7.33
    entry_spread_elasticity: float = 0.0
    duration_menu_days: tuple[int, ...] = (14, 30, 90, 180, 365)
    duration_probabilities: tuple[float, ...] = (0.6326, 0.2449, 0.0881, 0.0161, 0.0183)
    duration_spread_elasticity: float = 0.0
    renewal_probability: float = 0.827
    renewal_spread_elasticity: float = 0.0
    exit_base_per_day: float = 0.0
    delegation_sensitivity: float = 0.0
    entry_stake_avax: float = 135_622.0
    delegation_duration_days: int = 34
    quote_duration_days: int = 14
    validator_reward_pass_rate: float = 0.9874
    delegated_reward_pass_rate: float = 0.9927
    validator_fee_share: float = 0.0667
    identified: tuple[tuple[str, bool], ...] = ()
    assumptions: tuple[str, ...] = field(default=tuple(
        ["entry_base_per_day", "entry_spread_elasticity", "duration_probabilities", "duration_spread_elasticity",
         "renewal_probability", "renewal_spread_elasticity", "exit_base_per_day", "delegation_sensitivity"]
        + list(ENGINE_ASSUMPTIONS)))
    raw: Any = field(default=None, compare=False, hash=False, repr=False)

    def __post_init__(self) -> None:
        if len(self.duration_menu_days) != len(self.duration_probabilities) or not self.duration_menu_days:
            raise ValueError("duration menu and probabilities must have the same, non-zero length")
        if any(p < 0 for p in self.duration_probabilities) or abs(sum(self.duration_probabilities) - 1) > 1e-3:
            raise ValueError("duration probabilities must be non-negative and sum to 1")
        if not 0 <= self.renewal_probability <= 1 or self.entry_base_per_day < 0 or self.exit_base_per_day < 0:
            raise ValueError("renewal must be a probability and rates non-negative")
        if self.delegation_duration_days < 1 or self.quote_duration_days < 1 or self.entry_stake_avax <= 0:
            raise ValueError("durations and entrant stake must be positive")

    def replace(self, **changes: Any) -> BehaviourParams:
        values = {item.name: getattr(self, item.name) for item in fields(self)}
        values.update(changes)
        return BehaviourParams(**values)

    @classmethod
    def from_json(cls, path: str | Path, **engine_assumptions: Any) -> BehaviourParams:
        """Read the behaviour file. Blocks it omits keep the default and stay listed as assumptions.

        A block whose ``identified`` is false still supplies its point estimate, and its name is listed in
        ``assumptions`` so a sweep treats it as a swept assumption. Keyword arguments override the engine
        assumptions the file does not carry (``ENGINE_ASSUMPTIONS``).
        """
        path = Path(path)
        document = json.loads(path.read_text(encoding="utf-8"))
        default = cls()
        values: dict[str, Any] = {"version": str(document.get("version", "unknown")), "source": f"{path.name} {json.dumps(document.get('inputs', {}), sort_keys=True)}"}
        assumptions = set(ENGINE_ASSUMPTIONS)
        identified: dict[str, bool] = {}
        mapping = {
            "validator_entry": {"base_per_day": "entry_base_per_day", "spread_elasticity": "entry_spread_elasticity"},
            "validator_duration": {"menu_days": "duration_menu_days", "probabilities": "duration_probabilities", "spread_elasticity": "duration_spread_elasticity"},
            "validator_renewal": {"probability": "renewal_probability", "spread_elasticity": "renewal_spread_elasticity"},
            "validator_exit": {"base_per_day": "exit_base_per_day"},
            "delegation_flow": {"sensitivity": "delegation_sensitivity"},
        }
        for block, keys in mapping.items():
            item = document.get(block)
            if not isinstance(item, dict):
                assumptions.update(keys.values())
                continue
            identified[block] = bool(item.get("identified", False))
            for key, name in keys.items():
                if item.get(key) is None:
                    assumptions.add(name)
                    continue
                value = item[key]
                values[name] = tuple(value) if isinstance(value, list) else value
                if not identified[block]:
                    assumptions.add(name)
        if "duration_menu_days" in values:
            values["duration_menu_days"] = tuple(int(day) for day in values["duration_menu_days"])
        if "duration_probabilities" in values:
            total = sum(values["duration_probabilities"])
            values["duration_probabilities"] = tuple(float(p) / total for p in values["duration_probabilities"])
        for name in ENGINE_ASSUMPTIONS:
            values[name] = engine_assumptions.pop(name, getattr(default, name))
        if engine_assumptions:
            raise ValueError(f"unknown engine assumptions: {sorted(engine_assumptions)}")
        values["identified"] = tuple(sorted(identified.items()))
        values["assumptions"] = tuple(sorted(assumptions))
        values["raw"] = document
        return cls(**values)
