"""Renewal boundaries, full follow-up, identity, and anomaly accounting."""

import pandas as pd
import pytest

from avalanche_research.staking_renewal import (
    LOCKBOX_START,
    renewal_events,
    renewal_summary,
)


def periods():
    return pd.DataFrame([
        ["a", "node-a", "2025-01-01", "2025-01-03", 100],
        ["b", "node-a", "2025-01-10", "2025-01-12", 300],
        ["c", "node-a", "2025-01-12", "2025-01-14", 400],
        ["d", "node-b", "2025-01-01", "2025-01-03", 900],
        ["e", "node-b", "2025-01-11", "2025-01-13", 900],
    ], columns=["transaction_hash", "node_id", "start_time", "end_time", "stake_avax"])


def test_same_node_unweighted_end_cohort_includes_exact_boundaries():
    events = renewal_events(periods().sample(frac=1, random_state=1))
    result = renewal_summary(events, "2025-01-01", "2025-01-14", "2025-02-01")
    assert result == {"cohort_ends": 4, "eligible_ends": 4, "renewed_ends": 2,
                      "censored_ends": 0, "overlapping_ends": 0, "renewal_share": 0.5}
    assert events.set_index("transaction_hash").gap_days.loc["a"] == 7
    assert events.set_index("transaction_hash").gap_days.loc["b"] == 0
    # Window sensitivity changes a statistic, not an identity or weighting.
    assert renewal_summary(events, "2025-01-01", "2025-01-14", "2025-02-01", 14)["renewed_ends"] == 3


def test_full_followup_excludes_known_positive_and_unknown_negative_equally():
    events = renewal_events(periods())
    result = renewal_summary(events, "2025-01-01", "2025-01-15", "2025-01-10")
    assert result["eligible_ends"] == 2 and result["censored_ends"] == 3
    assert result["renewed_ends"] == 1
    result = renewal_summary(events, "2025-01-01", "2025-01-15", "2025-01-09")
    assert result["eligible_ends"] == 0 and pd.isna(result["renewal_share"])


def test_negative_gaps_are_named_anomalies_not_renewals():
    rows = periods()
    rows.loc[rows.transaction_hash.eq("b"), "start_time"] = "2025-01-02"
    events = renewal_events(rows)
    result = renewal_summary(events, "2025-01-01", "2025-01-14", "2025-02-01")
    assert result["overlapping_ends"] == 1 and result["eligible_ends"] == 3
    assert result["cohort_ends"] == sum(result[key] for key in
                                        ("eligible_ends", "censored_ends", "overlapping_ends"))


@pytest.mark.parametrize("days", [0, -1, 7.5, True])
def test_invalid_followup_is_rejected(days):
    with pytest.raises(ValueError, match="positive integer"):
        renewal_summary(renewal_events(periods()), "2025-01-01", "2025-02-01", "2025-03-01", days)


def test_duplicate_missing_and_invalid_records_are_rejected():
    rows = periods()
    with pytest.raises(ValueError, match="unique"):
        renewal_events(pd.concat([rows, rows.iloc[:1]]))
    rows.loc[0, "node_id"] = None
    with pytest.raises(ValueError, match="complete"):
        renewal_events(rows)
    rows = periods()
    rows.loc[0, "end_time"] = rows.loc[0, "start_time"]
    with pytest.raises(ValueError, match="positive"):
        renewal_events(rows)


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize("missing", [None, pd.NaT, ""])
def test_missing_cohort_bounds_or_followup_cutoff_are_rejected(index, missing):
    bounds = ["2025-01-01", "2025-02-01", "2025-03-01"]
    bounds[index] = missing
    with pytest.raises(ValueError, match="timestamps must be present"):
        renewal_summary(renewal_events(periods()), *bounds)


@pytest.mark.parametrize("column", ["start_time", "end_time"])
def test_empty_source_timestamp_is_rejected_after_parsing(column):
    rows = periods()
    rows.loc[0, column] = ""
    with pytest.raises(ValueError, match="timestamps must be present"):
        renewal_events(rows)


@pytest.mark.parametrize("bound", ["end", "observed_through"])
@pytest.mark.parametrize("timestamp", ["2026-01-01", "2025-11-19T16:00:00.000000001Z"])
def test_cohort_and_followup_cannot_enter_lockbox(bound, timestamp):
    window = {"start": "2025-01-01", "end": LOCKBOX_START,
              "observed_through": LOCKBOX_START}
    window[bound] = timestamp
    with pytest.raises(ValueError, match="validation lockbox"):
        renewal_summary(renewal_events(periods()), **window)


def test_lockbox_boundary_excludes_endings_and_censors_followup_at_boundary():
    day, second = pd.Timedelta(1, unit="D"), pd.Timedelta(1, unit="s")
    rows = pd.DataFrame([
        ["a", "node-a", LOCKBOX_START - 14 * day - second, LOCKBOX_START - 7 * day - second, 100],
        ["a-next", "node-a", LOCKBOX_START - second, LOCKBOX_START + day, 100],
        ["b", "node-b", LOCKBOX_START - 14 * day, LOCKBOX_START - 7 * day, 100],
        ["b-next", "node-b", LOCKBOX_START, LOCKBOX_START + day, 100],
        ["c", "node-c", LOCKBOX_START - 14 * day, LOCKBOX_START, 100],
    ], columns=["transaction_hash", "node_id", "start_time", "end_time", "stake_avax"])
    # This offset timestamp is the same exact boundary in UTC. The known
    # successor at the first lockbox instant must not turn censored b positive.
    result = renewal_summary(renewal_events(rows), "2025-01-01",
                             "2025-11-19T08:00:00-08:00", LOCKBOX_START)
    assert result == {"cohort_ends": 2, "eligible_ends": 1, "renewed_ends": 1,
                      "censored_ends": 1, "overlapping_ends": 0, "renewal_share": 1.0}
