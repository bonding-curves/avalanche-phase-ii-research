"""Acceptance-cohort table boundaries, rates, and reward coverage."""

import pandas as pd
import pytest
import duckdb
import holoviews as hv
import panel as pn
import param as pm
from bokeh.models import BoxAnnotation, HoverTool, Line

import avalanche_research.staking_cohorts as staking_cohorts
from avalanche_research.staking_cohorts import (
    StakingCohorts, cohort_table, denominator_options, display_columns, distinct_identities, for_population, rates_per,
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
    assert pd.isna(empty["Commitments / Address"])
    assert pd.isna(empty["Addresses per Node"])
    assert pd.isna(empty["Nodes per Address"])
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


def test_date_window_recomputes_partial_intervals_and_keeps_empty_roles(cohorts):
    daily, cutoffs = cohorts
    cutoffs = {**cutoffs, "delegator": pd.Timestamp("2026-09-24")}
    window = (pd.Timestamp("2026-09-22"), pd.Timestamp("2026-09-24"))
    all_rows = cohort_table(daily, cutoffs, "All", window=window).set_index("Role")
    assert all_rows.loc["Validator", "Total Commitments"] == 1
    assert all_rows.loc["Validator", "Total Stake (AVAX)"] == 500
    assert all_rows.loc["Validator", "Start (UTC)"] == window[0]
    assert all_rows.loc["Validator", "End (UTC)"] == window[1]
    assert all_rows.loc["Validator", "Commitments / Day"] == pytest.approx(0.5)
    assert all_rows.loc["Delegator", "Total Commitments"] == 0
    eras = cohort_table(daily, cutoffs, "Era", window=window)
    validator_eras = eras[eras["Role"].eq("Validator")].set_index("Reporting Interval")
    assert validator_eras.loc["Helicon", "Total Commitments"] == 1
    assert validator_eras.loc["Granite", "Total Commitments"] == 0


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


def test_stake_duration_units_follow_rate_unit(cohorts):
    daily = cohort_table(*cohorts, "All").set_index("Role")
    weekly = rates_per(daily, "Week")
    yearly = rates_per(daily, "Year")
    assert weekly.loc["Validator", "Total Stake-duration (AVAX-weeks)"] == pytest.approx(1900 / 7)
    assert yearly.loc["Validator", "Total Stake-duration (AVAX-years)"] == pytest.approx(1900 / 365.2425)
    assert weekly.loc["Validator", "Stake-duration / Commitment (AVAX-weeks)"] == pytest.approx(1900 / 3 / 7)
    assert weekly.loc["Validator", "Stake-duration / Week (AVAX-weeks/week)"] == pytest.approx(
        daily.loc["Validator", "Stake-duration / Day (AVAX-days/day)"],
    )
    visible = selected_columns(weekly, ["Stake-duration"], ["Total", "Per Calendar Unit"], "Week")
    assert visible.columns[-2:].tolist() == [
        "Total Stake-duration (AVAX-weeks)", "Stake-duration / Week (AVAX-weeks/week)",
    ]


def test_identity_counts_deduplicate_within_each_interval(tmp_path):
    records = {
        "periods": [
            ("validator", "n1", "2026-09-21 12:00:00", "granite"),
            ("validator", "n2", "2026-09-21 13:00:00", "granite"),
            ("validator", "n3", "2026-09-21 14:00:00", "granite"),
            ("validator", "n1", "2026-09-23 12:00:00", "helicon"),
            ("delegator", "n1", "2026-09-21 12:00:00", "granite"),
            ("delegator", "n1", "2026-09-23 12:00:00", "helicon"),
        ],
        "validators": [
            ("n1", "2026-09-21 12:00:00", '["A", "B"]'),
            ("n2", "2026-09-21 13:00:00", '["B"]'),
            ("n3", "2026-09-21 14:00:00", None),
            ("n1", "2026-09-23 12:00:00", '["C"]'),
        ],
        "delegators": [
            ("n1", "2026-09-21 12:00:00", "X"),
            ("n1", "2026-09-23 12:00:00", "X"),
        ],
    }
    columns = {
        "periods": ["role", "node_id", "accepted_at", "regime"],
        "validators": ["node_id", "accepted_at", "reward_addresses"],
        "delegators": ["node_id", "accepted_at", "delegator_address"],
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
    counts = distinct_identities(str(paths["validators"]), str(paths["delegators"]))
    all_rows = counts[counts.grain.eq("All")].set_index("role")
    assert all_rows.loc["validator", "Total Nodes"] == 3
    assert all_rows.loc["validator", "Total Validator Reward Addresses"] == 3
    assert all_rows.loc["validator", "Validator Node-address Pairs"] == 4
    assert all_rows.loc["validator", "Validator Nodes with Addresses"] == 2
    assert all_rows.loc["delegator", "Total Nodes"] == 1
    assert all_rows.loc["delegator", "Total Delegator Funding Addresses"] == 1
    assert all_rows.loc["delegator", "Delegator Node-address Pairs"] == 1
    day = counts[(counts.grain.eq("Day")) & (counts.role.eq("validator"))].set_index("bucket")
    assert day.loc["2026-09-21", "Total Validator Reward Addresses"] == 2
    assert day.loc["2026-09-21", "Validator Node-address Pairs"] == 3
    assert day.loc["2026-09-23", "Total Nodes"] == 1
    selected = distinct_identities(str(paths["validators"]), str(paths["delegators"]),
                                   pd.Timestamp("2026-09-23"), pd.Timestamp("2026-09-24"))
    only = selected[selected.grain.eq("All")].set_index("role")
    assert only.loc["validator", "Total Nodes"] == 1
    assert only.loc["validator", "Total Validator Reward Addresses"] == 1
    assert only.loc["delegator", "Total Delegator Funding Addresses"] == 1
    for grain in ("Day", "Week", "Year", "Era", "All"):
        one_grain = distinct_identities(str(paths["validators"]), str(paths["delegators"]),
                                        pd.Timestamp("2026-09-23"), pd.Timestamp("2026-09-24"), grain)
        pd.testing.assert_frame_equal(
            one_grain.sort_values("role").reset_index(drop=True),
            selected[selected.grain.eq(grain)].sort_values("role").reset_index(drop=True),
        )


def test_address_links_do_not_treat_missing_addresses_as_zero(cohorts):
    identities = pd.DataFrame([{
        "role": "validator", "grain": "All", "bucket": "All", "Total Nodes": 3,
        "Total Validator Reward Addresses": 3, "Total Delegator Funding Addresses": float("nan"),
        "Validator Node-address Pairs": 4,
        "Validator Nodes with Addresses": 2,
    }])
    validator = cohort_table(*cohorts, "All", identities).set_index("Role").loc["Validator"]
    assert validator["Addresses per Node"] == 2
    assert validator["Nodes per Address"] == pytest.approx(4 / 3)


def test_node_and_time_denominators(cohorts):
    identities = pd.DataFrame([
        {"role": "validator", "grain": "All", "bucket": "All", "Total Nodes": 2,
         "Total Validator Reward Addresses": 3, "Validator Node-address Pairs": 4,
         "Validator Nodes with Addresses": 2},
        {"role": "delegator", "grain": "All", "bucket": "All", "Total Nodes": 1,
         "Total Delegator Funding Addresses": 1, "Delegator Node-address Pairs": 1,
         "Delegator Nodes with Addresses": 1},
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
    assert validator["Commitments / Address"] == 1
    assert validator["Stake / Address (AVAX)"] == pytest.approx(800 / 3)
    assert validator["Rewards / Address (AVAX)"] == pytest.approx(4 / 3)
    assert validator["Addresses per Node"] == 2
    assert validator["Nodes per Address"] == pytest.approx(4 / 3)
    assert table.loc["Delegator", "Commitments / Address"] == 1
    assert pd.isna(validator["Total Delegator Funding Addresses"])
    weekly = rates_per(table, "Week")
    assert weekly.loc["Validator", "Total Weeks"] == pytest.approx(3 / 7)
    assert weekly.loc["Validator", "Commitments / Node / Week"] == pytest.approx(3.5)
    assert weekly.loc["Validator", "Committed Duration / Week (commitment-days/week)"] == pytest.approx(49 / 3)
    assert weekly.loc["Validator", "Commitments / Address / Week"] == pytest.approx(7 / 3)
    assert weekly.loc["Validator", "Stake / Address / Week (AVAX)"] == pytest.approx(800 * 7 / 9)
    visible = selected_columns(weekly, ["Nodes", "Addresses"], ["Per Address", "Per Node"], "Week")
    assert visible.columns[-2:].tolist() == ["Addresses per Node", "Nodes per Address"]


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
        "Reporting Interval", "Start (UTC)", "End (UTC)", "Role", "Total Weeks",
        "Total Committed Duration (commitment-days)",
        "Total Rewards (AVAX)",
        "Committed Duration / Node / Week (commitment-days/node/week)",
        "Rewards / Node / Week (AVAX)", "Reward Outcomes",
    ]
    context = selected_columns(table, [], [], "Week")
    assert context.columns.tolist() == visible.columns.tolist()[:5]


def test_count_quantities_control_existing_columns(cohorts):
    table = rates_per(for_population(cohort_table(*cohorts, "All"), "Validators"), "Week")
    visible = selected_columns(table, ["Nodes", "Addresses", "Commitments"],
                               ["Total", "Per Calendar Unit"], "Week")
    assert visible.columns.tolist() == [
        "Reporting Interval", "Start (UTC)", "End (UTC)", "Role", "Total Weeks", "Total Nodes",
        "Total Validator Reward Addresses", "Total Commitments", "Commitments / Week",
    ]
    assert "Total Nodes" not in selected_columns(table, ["Commitments"], [], "Week")
    assert "Total Commitments" not in selected_columns(table, ["Nodes"], [], "Week")
    without_totals = selected_columns(table, ["Nodes", "Addresses", "Commitments", "Stake"],
                                      ["Per Calendar Unit"], "Week")
    assert {"Total Nodes", "Total Validator Reward Addresses", "Total Commitments",
            "Total Stake (AVAX)"}.isdisjoint(without_totals.columns)
    assert "Commitments / Week" in without_totals
    assert "Stake / Week (AVAX)" in without_totals


def test_chart_uses_table_controls_and_only_per_measures(cohorts, monkeypatch):
    daily, cutoffs = cohorts
    tables = {grain: cohort_table(daily, cutoffs, grain)
              for grain in StakingCohorts.param.time_grain.objects}
    monkeypatch.setattr(staking_cohorts, "_cohort_data",
                        lambda run: (tables, cutoffs, pd.Timestamp("2026-09-24"), daily, ()))
    pn.extension()
    explorer = StakingCohorts("fixture", time_grain="Day", metrics=["Stake"],
                              views=["Total", "Per Commitment"], normalization="Mean")
    chart = explorer.chart()
    assert chart is explorer.chart()
    group_by_widget = explorer.panel()[0][0][0][0]
    group_by_widget.value = "Week"
    assert explorer.time_grain == "Week"
    chart_group_by_widget = chart[0][0][0][0]
    assert chart_group_by_widget.value == "Week"
    chart_group_by_widget.value = "Day"
    assert group_by_widget.value == "Day"
    assert explorer.date_range == (pd.Timestamp("2026-09-21").date(), pd.Timestamp("2026-09-24").date())
    assert chart[0][1].value == explorer.panel()[0][1].value
    assert isinstance(chart[0][1], pn.widgets.DateRangeSlider)
    frame = explorer._plot_frame()
    assert frame["Measure"].unique().tolist() == ["Stake per Commitment (AVAX)"]
    assert frame["Index"].mean() == pytest.approx(1)
    assert "Stake per Commitment (AVAX)" in explorer._frame()
    assert "Total Stake (AVAX)" in explorer._frame()
    figure = hv.render(explorer.plot())
    assert figure.x_range.start == frame["Date"].min()
    assert figure.x_range.end == frame["Date"].max()
    assert figure.above[0].major_label_overrides
    curves = [renderer.glyph for renderer in figure.renderers
              if isinstance(getattr(renderer, "glyph", None), Line)]
    assert curves and all(curve.line_width == 4 and curve.line_alpha == 0.75 for curve in curves)
    assert figure.legend[0].location == "top_right"
    assert figure.legend[0].click_policy == "mute"
    hover = next(tool for tool in figure.tools if isinstance(tool, HoverTool))
    assert hover.tooltips[0] == ("Measure", "@{Title}")
    assert hover.tooltips[2] == ("Value", "@{DisplayValue}")
    assert hover.formatters["@Date"] == "datetime"

    window = (pd.Timestamp("2026-09-23"), pd.Timestamp("2026-09-24"))
    filtered = {grain: cohort_table(daily, cutoffs, grain, window=window)
                for grain in StakingCohorts.param.time_grain.objects}
    monkeypatch.setattr(staking_cohorts, "_window_table", lambda run, start, end, grain: filtered[grain])
    slider = chart[0][1]
    slider.value = (window[0].date(), window[0].date())
    assert explorer.date_range == (window[0].date(), window[0].date())
    assert explorer.panel()[0][1].value == explorer.date_range
    assert explorer._selected_table()["Total Commitments"].sum() == 1
    assert explorer.panel()[1].value["Total Stake (AVAX)"].tolist() == [500]
    assert len(explorer._plot_frame()) == 1
    explorer.date_range = explorer.param.date_range.bounds

    explorer.population = "Delegators"
    assert explorer._plot_frame()["Role"].unique().tolist() == ["Delegator"]
    explorer.views = ["Total"]
    assert explorer._plot_frame().empty
    assert isinstance(explorer.plot(), pn.pane.Markdown)
    explorer.views = ["Per Commitment"]
    explorer.time_grain = "All"
    assert len(explorer._plot_frame()) == 1
    assert isinstance(explorer.plot(), hv.Overlay)
    explorer.normalization = "None"
    raw = explorer._plot_frame().iloc[0]
    assert raw["Index"] == raw["Value"]
    explorer.time_grain = "Era"
    assert hv.render(explorer.plot()).select(BoxAnnotation)


@pytest.mark.parametrize("period", ["Day", "Week", "Year"])
def test_quantity_colors_cover_every_supported_column(cohorts, period):
    from avalanche_research.palette import QUANTITY_COLORS

    table = rates_per(for_population(cohort_table(*cohorts, "All"), "Both"), period)
    colors = staking_cohorts.quantity_colors(period)
    for quantity in staking_cohorts.QUANTITIES:
        selected = display_columns(selected_columns(table, [quantity], list(staking_cohorts.VIEWS), period))
        measures = [name for name in selected if name not in (*staking_cohorts.CONTEXT_COLUMNS,
                    f"Total {period}s", "Reward Outcomes")]
        assert measures
        assert {colors[name] for name in measures} == {
            QUANTITY_COLORS[quantity.lower().replace("-", "_")],
        }


def test_quantity_colors_survive_controls_and_selection_order(cohorts, monkeypatch):
    from avalanche_research.palette import QUANTITY_COLORS

    hv.extension("bokeh")
    daily, cutoffs = cohorts
    tables = {grain: cohort_table(daily, cutoffs, grain)
              for grain in StakingCohorts.param.time_grain.objects}
    monkeypatch.setattr(staking_cohorts, "_cohort_data",
                        lambda run: (tables, cutoffs, pd.Timestamp("2026-09-24"), daily, ()))
    explorer = StakingCohorts("fixture", metrics=["Stake", "Duration", "Rewards"],
                              views=["Per Calendar Unit", "Per Commitment"])
    for grain, period, population, normalization in (
        ("Day", "Day", "Validators", "Mean"),
        ("Week", "Week", "Delegators", "Median"),
        ("Era", "Year", "Both", "First nonzero"),
        ("All", "Day", "Validators", "None"),
    ):
        explorer.param.update(time_grain=grain, periodic_denominator=period,
                              population=population, normalization=normalization)
        explorer.metrics = list(reversed(explorer.metrics))
        for element in explorer.plot():
            if isinstance(element, (hv.Curve, hv.Scatter)):
                label = element.label.split(": ")[-1]
                quantity = label.split(" per ")[0].replace("Committed ", "").lower().replace("-", "_")
                assert hv.Store.lookup_options("bokeh", element, "style").kwargs["color"] == QUANTITY_COLORS[quantity]
    # A filtered subset retains the same hue as the multi-series chart.
    explorer.metrics = ["Stake"]
    explorer.time_grain = "Day"
    explorer.date_range = (pd.Timestamp("2026-09-23").date(), pd.Timestamp("2026-09-23").date())
    monkeypatch.setattr(staking_cohorts, "_window_table", lambda *args: cohort_table(
        daily, cutoffs, "Day", window=(pd.Timestamp("2026-09-23"), pd.Timestamp("2026-09-24")),
    ))
    assert all(hv.Store.lookup_options("bokeh", element, "style").kwargs["color"] == QUANTITY_COLORS["stake"]
               for element in explorer.plot() if isinstance(element, (hv.Curve, hv.Scatter)))


def test_address_denominators_follow_population_and_rate_unit(cohorts):
    identities = pd.DataFrame([
        {"role": "validator", "grain": "All", "bucket": "All", "Total Nodes": 2,
         "Total Validator Reward Addresses": 3},
        {"role": "delegator", "grain": "All", "bucket": "All", "Total Nodes": 1,
         "Total Delegator Funding Addresses": 1},
    ])
    table = cohort_table(*cohorts, "All", identities)
    weekly = rates_per(for_population(table, "Both"), "Week")
    visible = selected_columns(weekly, ["Commitments", "Stake"],
                               ["Per Address", "Per Address per Calendar Unit"], "Week")
    assert visible.columns.tolist()[-4:] == [
        "Commitments / Address", "Stake / Address (AVAX)",
        "Commitments / Address / Week", "Stake / Address / Week (AVAX)",
    ]
    assert weekly.set_index("Role")["Total Addresses"].to_dict() == {"Validator": 3, "Delegator": 1}


def test_denominator_labels_follow_rate_unit_without_changing_view_keys():
    daily = denominator_options("Day")
    weekly = denominator_options("Week")
    assert list(daily.values()) == list(weekly.values())
    assert "Per Day" in daily and "Per Node per Day" in daily
    assert weekly["Per Week"] == "Per Calendar Unit"
    assert weekly["Per Node per Week"] == "Per Node per Calendar Unit"
    assert weekly["Per Address"] == "Per Address"
    assert weekly["Per Address per Week"] == "Per Address per Calendar Unit"


def test_display_headings_use_per_without_changing_values_or_selection_order(cohorts):
    table = rates_per(for_population(cohort_table(*cohorts, "All"), "Validators"), "Week")
    selected = selected_columns(table, ["Commitments", "Stake"],
                                ["Total", "Per Calendar Unit", "Per Commitment"], "Week")
    displayed = display_columns(selected)
    assert displayed.columns.tolist() == [
        "Reporting Interval", "Start (UTC)", "End (UTC)", "Role", "Total Weeks",
        "Total Commitments", "Total Stake (AVAX)",
        "Commitments per Week", "Stake per Week (AVAX)",
        "Stake per Commitment (AVAX)",
    ]
    assert displayed.iloc[0, -1] == selected.iloc[0, -1]


def test_pinned_run_data_is_reused_across_explorers(monkeypatch):
    calls = []
    capture = {"inputs": [
        {"input_id": "validator-stakes", "dataset_id": "validators", "run": "source",
         "captured_at": "2026-09-22T00:00:00Z"},
        {"input_id": "delegator-stakes", "dataset_id": "delegators", "run": "source",
         "captured_at": "2026-09-22T00:00:00Z"},
        {"input_id": "staking-rewards", "captured_at": "2026-09-22T00:00:00Z"},
    ]}

    def receipt(dataset, run):
        calls.append((dataset, run))
        return {"capture": capture}

    monkeypatch.setattr(staking_cohorts.datasets, "receipt", receipt)
    monkeypatch.setattr(staking_cohorts.datasets, "parquet_path", lambda dataset, run: f"{dataset}/{run}")
    monkeypatch.setattr(staking_cohorts, "accepted_commitments", lambda path: pd.DataFrame({
        "first_accepted": [pd.Timestamp("2026-09-10")],
    }))
    monkeypatch.setattr(staking_cohorts, "distinct_identities", lambda *paths: pd.DataFrame())
    monkeypatch.setattr(staking_cohorts, "cohort_table", lambda *args: pd.DataFrame())

    first = StakingCohorts("fixture-cohort-cache")
    second = StakingCohorts("fixture-cohort-cache")
    assert calls == [("derived.staking-periods", "fixture-cohort-cache")]
    assert first is not second
    assert first._tables is second._tables


def test_panel_keeps_one_table_when_selections_change(monkeypatch):
    explorer = StakingCohorts.__new__(StakingCohorts)
    pm.Parameterized.__init__(explorer)
    explorer.run = "fixture"
    explorer._cutoffs = {"validator": pd.Timestamp("2026-09-24")}
    explorer._reward_cutoff = pd.Timestamp("2026-09-24")
    explorer.param.date_range.bounds = (pd.Timestamp("2026-09-21").date(), pd.Timestamp("2026-09-24").date())
    explorer.date_range = explorer.param.date_range.bounds
    frame = pd.DataFrame({"Nodes": [1], "Stake": [2]})
    monkeypatch.setattr(StakingCohorts, "_full_frame", lambda self: frame)
    monkeypatch.setattr(StakingCohorts, "_frame",
                        lambda self: frame[["Nodes"] if "Nodes" in self.metrics else ["Stake"]])

    panel = explorer.panel()
    assert explorer.panel() is panel
    table = panel[1]
    original_value = table.value
    assert table.value.columns.tolist() == ["Nodes", "Stake"]
    assert table.hidden_columns == ["Stake"]
    explorer.metrics = ["Stake"]
    assert panel[1] is table
    assert table.value is original_value
    assert table.hidden_columns == ["Nodes"]
