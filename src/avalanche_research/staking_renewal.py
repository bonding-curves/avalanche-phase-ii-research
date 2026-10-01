"""Same-node renewal of ended validator commitments, with explicit follow-up."""

from __future__ import annotations

import pandas as pd

RENEWAL_DAYS = 7
SECONDS_PER_DAY = 86_400
LOCKBOX_START = pd.Timestamp("2025-11-19 16:00:00", tz="UTC")


def renewal_events(commitments: pd.DataFrame) -> pd.DataFrame:
    """Pair successive commitments on each node before selecting an end cohort.

    Each ending commitment is one observation, not each distinct node. A
    negative successor gap is an overlapping-record anomaly, not renewal.
    The input contains validator commitments only, including future starts
    already observed in the source. No reward-address/operator inference occurs.
    """
    columns = ["transaction_hash", "node_id", "start_time", "end_time", "stake_avax"]
    rows = commitments[columns].copy()
    if rows[columns].isna().any().any() or rows.transaction_hash.duplicated().any():
        raise ValueError("renewal requires complete, unique validator commitments")
    rows["start_time"] = pd.to_datetime(rows.start_time, utc=True).dt.as_unit("ns")
    rows["end_time"] = pd.to_datetime(rows.end_time, utc=True).dt.as_unit("ns")
    if rows[["start_time", "end_time"]].isna().any().any():
        raise ValueError("commitment timestamps must be present")
    if (rows.end_time <= rows.start_time).any() or (rows.stake_avax <= 0).any():
        raise ValueError("commitment duration and stake must be positive")
    rows = rows.sort_values(["node_id", "start_time", "transaction_hash"])
    rows["next_start"] = rows.groupby("node_id", sort=False).start_time.shift(-1)
    rows["gap_days"] = (rows.next_start - rows.end_time).dt.total_seconds() / SECONDS_PER_DAY
    rows["overlapping_successor"] = rows.gap_days.lt(0)
    return rows.reset_index(drop=True)


def renewal_summary(events: pd.DataFrame, start, end, observed_through,
                    days: int = RENEWAL_DAYS) -> dict:
    """Unweighted renewal share for endings in [start, end), with full follow-up.

    Renewal means the next commitment on the same node starts between the
    previous end and that end plus ``days``, including both boundaries. Endings
    without the full window are censored, even when a successor is already
    known. Overlapping successors are excluded and counted separately.
    Cohort and observation bounds cannot extend into the validation lockbox.
    Full follow-up must finish strictly before its first timestamp.
    """
    if not isinstance(days, int) or isinstance(days, bool) or days <= 0:
        raise ValueError("renewal days must be a positive integer")
    start, end, cutoff = (pd.Timestamp(value).tz_convert("UTC")
                          if pd.Timestamp(value).tzinfo else pd.Timestamp(value).tz_localize("UTC")
                          for value in (start, end, observed_through))
    if any(pd.isna(value) for value in (start, end, cutoff)):
        raise ValueError("renewal window timestamps must be present")
    if end <= start:
        raise ValueError("renewal cohort end must follow its start")
    if end > LOCKBOX_START or cutoff > LOCKBOX_START:
        raise ValueError("renewal window reaches into the validation lockbox, which starts 2025-11-19 16:00 UTC")
    cohort = events.loc[events.end_time.ge(start) & events.end_time.lt(end)]
    followup_end = cohort.end_time.add(pd.Timedelta(days, unit="D"))
    complete = followup_end.le(cutoff) & followup_end.lt(LOCKBOX_START)
    eligible = cohort.loc[complete & ~cohort.overlapping_successor]
    renewed = eligible.gap_days.between(0, days, inclusive="both")
    return {
        "cohort_ends": len(cohort),
        "eligible_ends": len(eligible),
        "renewed_ends": int(renewed.sum()),
        "censored_ends": int((~complete).sum()),
        "overlapping_ends": int((complete & cohort.overlapping_successor).sum()),
        "renewal_share": float(renewed.mean()) if len(eligible) else float("nan"),
    }
