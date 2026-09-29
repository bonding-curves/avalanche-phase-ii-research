"""Acceptance-cohort table boundaries, rates, and reward coverage."""

import pandas as pd
import pytest
import duckdb
import param as pm

from avalanche_research.staking_cohorts import (
    StakingCohorts, cohort_table, denominator_options, distinct_identities, for_population, rates_per,
    selected_columns,
)


@pytest.fixture
def cohorts():
    daily = pd.DataFrame([
        {"accepted_day": "2026-09-21", "role": "validator", "era": "granite",
         "first_accepted": "2026-09-21 12:00:00", "commitments": 2, "stake_avax": 300,
         "stake_duration_avax_days": 900, "duration_days": 5,
         "observed_rewards_avax": 4, "reward_outcomes": 1},
        {"accepted_day": "2026-09-23", "role": "validator", "era": "helicon",
         "first_accepted": "2026-09-23 12:00:00", "commitments": 1, "stake_avax": 500,
         "stake_duration_avax_days": 1000, "duration_days": 2,
         "observed_rewards_avax": 0, "reward_outcomes": 0},
        {"accepted_day": "2026-09-21", "role": "delegator", "era": "granite",
         "first_accepted": "2026-09-21 10:00:00", "commitments": 1, "stake_avax": 100,
         "stake_duration_avax_days": 1400, "duration_days": 14,
         "observed_rewards_avax": 2, "reward_outcomes": 1},
    ])
    cutoffs = {"validator": pd.Timestamp("2026-09-24 12:00:00"),
               "delegator": pd.Timestamp("2026-09-22 00:00:00")}
    return daily, cutoffs


def test_all_keeps_roles_separate_and_reports_per_commitment_values(cohorts):
    table = cohort_table(*cohorts, "All").set_index("Role")
    assert table.loc["Validator", "Total Commitments"] == 3
    assert table.loc["Delegator", "Total Commitments"] == 1
    assert table.loc["Validator", "Total Stake (AVAX)"] == 800
    assert table.loc["Validator", "Total Stake-duration (AVAX-days)"] == 1900
    assert table.loc["Validator", "Stake / Commitment (AVAX)"] == pytest.approx(800 / 3)
    assert table.loc["Validator", "Duration / Commitment (days)"] == pytest.approx(7 / 3)
    assert table.loc["Validator", "Stake-duration / Commitment (AVAX-days)"] == pytest.approx(1900 / 3)
    assert table.loc["Validator", "Reward Outcomes"] == "1/3"
    assert table.loc["Validator", "Total Rewards (AVAX)"] == 4
    assert table.loc["Validator", "Rewards / Commitment (AVAX)"] == 4
    assert list(table.columns[:3]) == ["Reporting Interval", "Start (UTC)", "End (UTC)"]


def test_day_includes_zero_commitment_intervals_and_partial_day_rates(cohorts):
    table = cohort_table(*cohorts, "Day")
    empty = table[(table["Role"] == "Validator") & (table["Reporting Interval"] == "2026-09-22")].iloc[0]
    assert empty["Total Commitments"] == 0
    assert empty["Reward Outcomes"] == "0/0"
    assert pd.isna(empty["Duration / Commitment (days)"])
    first = table[(table["Role"] == "Validator") & (table["Reporting Interval"] == "2026-09-21")].iloc[0]
    assert first["Commitments / Day"] == pytest.approx(4)
    assert first["Stake / Day (AVAX)"] == pytest.approx(600)
    assert first["Rewards / Day (AVAX)"] == pytest.approx(8)


def test_era_uses_upgrade_instant_and_role_specific_cutoffs(cohorts):
    table = cohort_table(*cohorts, "Era")
    helicon = table[(table["Role"] == "Validator") & (table["Reporting Interval"] == "Helicon")].iloc[0]
    assert helicon["Start (UTC)"] == pd.Timestamp("2026-09-22 15:00:00")
    assert helicon["End (UTC)"] == pd.Timestamp("2026-09-24 12:00:00")
    assert helicon["Total Commitments"] == 1
    assert not ((table["Role"] == "Delegator") & (table["Reporting Interval"] == "Helicon")).any()


def test_each_grain_preserves_population(cohorts):
    for grain in ("Day", "Week", "Year", "Era", "All"):
        table = cohort_table(*cohorts, grain)
        assert table.groupby("Role")["Total Commitments"].sum().to_dict() == {"Delegator": 1, "Validator": 3}


def test_periodic_denominator_changes_rates_not_totals(cohorts):
    daily = cohort_table(*cohorts, "All")
    validator = daily[daily["Role"] == "Validator"].iloc[0]
    weekly = rates_per(daily, "Week")
    annual = rates_per(daily, "Year")
    assert weekly.loc[validator.name, "Commitments / Week"] == pytest.approx(validator["Commitments / Day"] * 7)
    assert annual.loc[validator.name, "Rewards / Year (AVAX)"] == pytest.approx(
        validator["Rewards / Day (AVAX)"] * 365.2425
    )
    assert weekly["Total Commitments"].equals(daily["Total Commitments"])
    assert weekly["Total Rewards (AVAX)"].equals(daily["Total Rewards (AVAX)"])


def test_identity_counts_deduplicate_within_each_interval(tmp_path):
    records = {
        "periods": [
            ("validator", "n1", "2026-09-21 12:00:00", "granite"),
            ("validator", "n2", "2026-09-21 13:00:00", "granite"),
            ("validator", "n1", "2026-09-23 12:00:00", "helicon"),
            ("delegator", "n1", "2026-09-21 12:00:00", "granite"),
            ("delegator", "n1", "2026-09-23 12:00:00", "helicon"),
        ],
        "validators": [
            ("2026-09-21 12:00:00", '["A", "B"]'),
            ("2026-09-21 13:00:00", '["B"]'),
            ("2026-09-23 12:00:00", '["C"]'),
        ],
        "delegators": [
            ("2026-09-21 12:00:00", "X"),
            ("2026-09-23 12:00:00", "X"),
        ],
    }
    columns = {
        "periods": ["role", "node_id", "accepted_at", "regime"],
        "validators": ["accepted_at", "reward_addresses"],
        "delegators": ["accepted_at", "delegator_address"],
    }
    paths = {}
    with duckdb.connect() as db:
        for name, values in records.items():
            rows = pd.DataFrame(values, columns=columns[name])
            rows["accepted_at"] = pd.to_datetime(rows["accepted_at"])
            db.register("rows", rows)
            paths[name] = tmp_path / f"{name}.parquet"
            db.execute(f"COPY rows TO '{paths[name]}' (FORMAT PARQUET)")
            db.unregister("rows")
    counts = distinct_identities(*(str(paths[name]) for name in records))
    all_rows = counts[counts.grain.eq("All")].set_index("role")
    assert all_rows.loc["validator", "Total Nodes"] == 2
    assert all_rows.loc["validator", "Total Validator Reward Addresses"] == 3
    assert all_rows.loc["delegator", "Total Nodes"] == 1
    assert all_rows.loc["delegator", "Total Delegator Funding Addresses"] == 1
    day = counts[(counts.grain.eq("Day")) & (counts.role.eq("validator"))].set_index("bucket")
    assert day.loc["2026-09-21", "Total Validator Reward Addresses"] == 2
    assert day.loc["2026-09-23", "Total Nodes"] == 1


def test_node_and_time_denominators(cohorts):
    identities = pd.DataFrame([
        {"role": "validator", "grain": "All", "bucket": "All", "Total Nodes": 2,
         "Total Validator Reward Addresses": 3},
        {"role": "delegator", "grain": "All", "bucket": "All", "Total Nodes": 1,
         "Total Delegator Funding Addresses": 1},
    ])
    table = cohort_table(*cohorts, "All", identities).set_index("Role")
    validator = table.loc["Validator"]
    assert validator["Total Days"] == 3
    assert validator["Commitments / Node"] == pytest.approx(1.5)
    assert validator["Commitments / Node / Day"] == pytest.approx(0.5)
    assert validator["Total Committed Duration (commitment-days)"] == 7
    assert validator["Committed Duration / Day (commitment-days/day)"] == pytest.approx(7 / 3)
    assert validator["Committed Duration / Node (commitment-days/node)"] == pytest.approx(7 / 2)
    assert validator["Committed Duration / Node / Day (commitment-days/node/day)"] == pytest.approx(7 / 6)
    assert validator["Stake / Node (AVAX)"] == 400
    assert validator["Rewards / Node (AVAX)"] == 2
    assert pd.isna(validator["Total Delegator Funding Addresses"])
    weekly = rates_per(table, "Week")
    assert weekly.loc["Validator", "Total Weeks"] == pytest.approx(3 / 7)
    assert weekly.loc["Validator", "Commitments / Node / Week"] == pytest.approx(3.5)
    assert weekly.loc["Validator", "Committed Duration / Week (commitment-days/week)"] == pytest.approx(49 / 3)


def test_population_selection_shows_only_applicable_address_count():
    table = pd.DataFrame({
        "Role": ["Validator", "Delegator"],
        "Total Validator Reward Addresses": [3, float("nan")],
        "Total Delegator Funding Addresses": [float("nan"), 2],
    })
    validators = for_population(table, "Validators")
    delegators = for_population(table, "Delegators")
    both = for_population(table, "Both")
    assert validators.columns.tolist() == ["Role", "Total Validator Reward Addresses"]
    assert delegators.columns.tolist() == ["Role", "Total Delegator Funding Addresses"]
    assert both.columns.tolist() == ["Role", "Total Addresses"]
    assert both["Total Addresses"].tolist() == [3, 2]


def test_metric_and_view_selections_keep_context_and_filter_families(cohorts):
    table = rates_per(for_population(cohort_table(*cohorts, "All"), "Validators"), "Week")
    visible = selected_columns(table, ["Duration", "Rewards"], ["Total", "Per Node per Calendar Unit"], "Week")
    assert visible.columns.tolist() == [
        "Reporting Interval", "Start (UTC)", "End (UTC)", "Role", "Total Weeks", "Total Nodes",
        "Total Validator Reward Addresses", "Total Commitments", "Commitments / Node / Week",
        "Total Committed Duration (commitment-days)",
        "Committed Duration / Node / Week (commitment-days/node/week)",
        "Total Rewards (AVAX)", "Rewards / Node / Week (AVAX)", "Reward Outcomes",
    ]
    context = selected_columns(table, [], [], "Week")
    assert context.columns.tolist() == visible.columns.tolist()[:8]


def test_denominator_labels_follow_rate_unit_without_changing_view_keys():
    daily = denominator_options("Day")
    weekly = denominator_options("Week")
    assert list(daily.values()) == list(weekly.values())
    assert "Per Day" in daily and "Per Node per Day" in daily
    assert weekly["Per Week"] == "Per Calendar Unit"
    assert weekly["Per Node per Week"] == "Per Node per Calendar Unit"


def test_panel_keeps_one_table_when_selections_change(monkeypatch):
    explorer = StakingCohorts.__new__(StakingCohorts)
    pm.Parameterized.__init__(explorer)
    explorer.run = "fixture"
    explorer._cutoffs = {"validator": pd.Timestamp("2026-09-24")}
    explorer._reward_cutoff = pd.Timestamp("2026-09-24")
    monkeypatch.setattr(StakingCohorts, "_frame", lambda self: pd.DataFrame({"Quantity count": [len(self.metrics)]}))

    panel = explorer.panel()
    table = panel[1]
    assert table.value.loc[0, "Quantity count"] == 4
    explorer.metrics = ["Stake"]
    assert panel[1] is table
    assert table.value.loc[0, "Quantity count"] == 1
