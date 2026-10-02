"""A reference cohort of real stakes, grouped so every mechanism can reprice it quickly.

Rewards are linear in stake, so stakes that share a role, a whole-day duration, and a tenure are summed
into one row. The default window is the year before Granite, 2024-11-19 to 2025-11-19 16:00 UTC, so the
cohort reads no data from the validation lockbox.
"""

from __future__ import annotations

from datetime import UTC, datetime

import duckdb
import pandas as pd

from avalanche_research.model.types import SECONDS_PER_DAY

LOCKBOX_START = datetime(2025, 11, 19, 16, tzinfo=UTC)
DEFAULT_WINDOW = (datetime(2024, 11, 19, tzinfo=UTC), LOCKBOX_START)
MAX_TENURE = 20


def with_tenure(periods: pd.DataFrame, window: tuple[datetime, datetime] = DEFAULT_WINDOW) -> pd.DataFrame:
    """Staking periods accepted inside ``window``, each with its tenure and whole-day duration.

    ``periods`` needs ``role``, ``node_id``, ``start_time``, ``accepted_at``, ``duration_days``, and
    ``stake_navax``. Tenure is a validator's completed periods on the same node before this one, counted
    over all earlier history and capped at 20. Delegations carry tenure 0.
    """
    if window[1] > LOCKBOX_START:
        raise ValueError("the window reaches into the validation lockbox, which starts 2025-11-19 16:00 UTC")
    frame = periods.sort_values("start_time").copy()
    frame["completed_periods"] = 0
    validators = frame["role"] == "validator"
    frame.loc[validators, "completed_periods"] = frame[validators].groupby("node_id").cumcount().clip(upper=MAX_TENURE)
    accepted = pd.to_datetime(frame["accepted_at"], utc=True)
    inside = (accepted >= window[0]) & (accepted < window[1])
    frame = frame[inside]
    frame["duration_whole_days"] = frame["duration_days"].round().clip(lower=1).astype(int)
    frame["duration_seconds"] = frame["duration_whole_days"] * SECONDS_PER_DAY
    return frame


def validator_periods(periods: pd.DataFrame, window: tuple[datetime, datetime] = DEFAULT_WINDOW) -> pd.DataFrame:
    """Individual validator periods inside ``window``, for rules that judge each stake on its own."""
    frame = with_tenure(periods, window)
    frame = frame[frame["role"] == "validator"]
    return frame[["stake_navax", "duration_seconds", "duration_whole_days", "completed_periods"]].reset_index(drop=True)


def group_stakes(periods: pd.DataFrame, window: tuple[datetime, datetime] = DEFAULT_WINDOW) -> pd.DataFrame:
    """Periods inside ``window`` summed by role, whole-day duration, and tenure, for rules linear in stake."""
    frame = with_tenure(periods, window)
    grouped = (
        frame.groupby(["role", "duration_whole_days", "completed_periods"], as_index=False)
        .agg(stake_navax=("stake_navax", "sum"), periods=("stake_navax", "size"))
    )
    grouped["duration_seconds"] = grouped["duration_whole_days"] * SECONDS_PER_DAY
    return grouped


def load_periods(parquet_path: str) -> pd.DataFrame:
    """The columns ``group_stakes`` needs, read from a built ``derived.staking-periods`` file."""
    query = """
        SELECT role, node_id, start_time, accepted_at, duration_days, stake_navax
        FROM read_parquet(?)
        WHERE accepted_at < TIMESTAMP '2025-11-19 16:00:00'
        ORDER BY start_time, node_id, role, stake_navax
    """
    return duckdb.execute(query, [parquet_path]).df()
