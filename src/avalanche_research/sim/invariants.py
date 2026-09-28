"""Accounting invariants of a trajectory, checked on every day.

I1 realized supply never exceeds the cap, and neither does the supply counter.
I2 realized supply increases only by rewards paid: supply[t] - supply[t-1] = rewards_paid[t] >= 0.
I3 validator stake, delegated stake, and validator count are never negative.
I4 delegated stake never exceeds the delegation capacity of the active validators.
I5 rewards paid never exceed the rewards due that day.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# Relative tolerance for float accounting in AVAX: 1e-9 of the supply is under 1 AVAX.
RELATIVE_TOLERANCE = 1e-9


class InvariantError(AssertionError):
    pass


def check_step(row: dict[str, float], previous_supply: float, cap: float) -> None:
    """Check one day's values; raise InvariantError naming the first invariant that fails."""
    tolerance = RELATIVE_TOLERANCE * max(cap, 1.0)
    if row["supply_avax"] > cap + tolerance or row["supply_counter_avax"] > cap + tolerance:
        raise InvariantError(f"I1 day {row['day']}: supply {row['supply_avax']} or counter {row['supply_counter_avax']} above cap {cap}")
    if abs(row["supply_avax"] - previous_supply - row["rewards_paid_avax"]) > tolerance or row["rewards_paid_avax"] < -tolerance:
        raise InvariantError(f"I2 day {row['day']}: supply moved {row['supply_avax'] - previous_supply} but rewards paid {row['rewards_paid_avax']}")
    if min(row["validator_stake_avax"], row["delegated_stake_avax"], row["validator_count"]) < -tolerance:
        raise InvariantError(f"I3 day {row['day']}: negative stake or count")
    if row["delegated_stake_avax"] > row["delegation_capacity_avax"] + tolerance:
        raise InvariantError(f"I4 day {row['day']}: delegated {row['delegated_stake_avax']} above capacity {row['delegation_capacity_avax']}")
    if row["rewards_paid_avax"] > row["rewards_due_avax"] + tolerance:
        raise InvariantError(f"I5 day {row['day']}: paid {row['rewards_paid_avax']} above due {row['rewards_due_avax']}")


def check_frame(frame: pd.DataFrame, cap: float, initial_supply: float | None = None) -> dict[str, Any]:
    """Check every day of an engine output. Returns the count of failing days per invariant (all zero when it holds)."""
    tolerance = RELATIVE_TOLERANCE * max(cap, 1.0)
    supply = frame["supply_avax"].to_numpy()
    start = frame.attrs.get("initial_supply_avax") if initial_supply is None else initial_supply
    previous = np.concatenate([[start], supply[:-1]])
    paid = frame["rewards_paid_avax"].to_numpy()
    failures = {
        "I1": int(((supply > cap + tolerance) | (frame["supply_counter_avax"].to_numpy() > cap + tolerance)).sum()),
        "I2": int(((np.abs(supply - previous - paid) > tolerance) | (paid < -tolerance)).sum()),
        "I3": int((frame[["validator_stake_avax", "delegated_stake_avax", "validator_count"]].to_numpy() < -tolerance).any(axis=1).sum()),
        "I4": int((frame["delegated_stake_avax"].to_numpy() > frame["delegation_capacity_avax"].to_numpy() + tolerance).sum()),
        "I5": int((paid > frame["rewards_due_avax"].to_numpy() + tolerance).sum()),
    }
    return {"days": len(frame), "failures": failures, "holds": not any(failures.values())}
