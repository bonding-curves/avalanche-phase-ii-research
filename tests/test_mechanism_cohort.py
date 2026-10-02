"""The reference cohort: tenure counting, grouping, and the lockbox guard."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from avalanche_research.mechanisms import ChainReward
from avalanche_research.mechanisms.cohort import group_stakes, validator_periods

AVAX = 10**9


def periods():
    t = pd.Timestamp
    return pd.DataFrame({
        "role": ["validator", "validator", "validator", "delegator", "delegator"],
        "node_id": ["A", "A", "B", "A", "A"],
        "start_time": [t("2024-01-01"), t("2025-01-01"), t("2025-02-01"), t("2025-01-02"), t("2025-01-03")],
        "accepted_at": [t("2024-01-01"), t("2025-01-01"), t("2025-02-01"), t("2025-01-02"), t("2025-01-03")],
        "duration_days": [14.2, 30.0, 14.0, 14.4, 13.6],
        "stake_navax": [2_000 * AVAX, 3_000 * AVAX, 2_000 * AVAX, 100 * AVAX, 50 * AVAX],
    })


def test_tenure_counts_earlier_periods_on_the_same_node_even_outside_the_window():
    table = validator_periods(periods())
    assert sorted(table["completed_periods"]) == [0, 1]
    assert len(table) == 2


def test_grouping_sums_stake_by_role_duration_and_tenure():
    grouped = group_stakes(periods())
    delegations = grouped[grouped["role"] == "delegator"]
    assert delegations["stake_navax"].sum() == 150 * AVAX
    assert delegations["periods"].sum() == 2
    assert set(delegations["duration_whole_days"]) == {14}


def test_grouped_issuance_equals_the_sum_over_periods_within_rounding():
    start = datetime(2026, 12, 21, tzinfo=UTC)
    supply = 465_000_000 * AVAX
    grouped = group_stakes(periods()).assign(start=start)
    single = validator_periods(periods()).assign(start=start)
    chain = ChainReward()
    validators_grouped = grouped[grouped["role"] == "validator"]
    assert chain.issuance_navax(validators_grouped, supply) == pytest.approx(chain.issuance_navax(single, supply), abs=2)


def test_a_window_into_the_lockbox_is_refused():
    with pytest.raises(ValueError):
        group_stakes(periods(), (datetime(2025, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)))
