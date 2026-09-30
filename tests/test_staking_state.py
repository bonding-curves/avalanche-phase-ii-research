"""Common snapshot support, reducers, units, filters, and render channels."""

from datetime import date

import holoviews as hv
import pandas as pd
import pytest
from bokeh.models import BoxAnnotation, GlyphRenderer, HoverTool, Line

from avalanche_research import staking_state
from avalanche_research.staking_state import StakingState, daily_state, summarize_state


@pytest.fixture
def ledger():
    return pd.DataFrame({
        "date_utc": ["2026-09-21", "2026-09-22", "2026-09-23"],
        "active_validator_stake_wei": [20 * 10**18, 60 * 10**18, 999 * 10**18],
        "active_delegated_stake_wei": [10 * 10**18, 40 * 10**18, 999 * 10**18],
        "total_supply_close_wei": [100 * 10**18, 200 * 10**18, None],
        "complete": [True, True, False],
    })


@pytest.fixture
def state(monkeypatch, ledger):
    hv.extension("bokeh")
    monkeypatch.setattr(staking_state, "_state_data", lambda run: daily_state(ledger))
    return StakingState("state-fixture")


def test_common_support_does_not_leak_an_incomplete_stake_reading(ledger):
    daily = daily_state(ledger)
    values = daily.drop(columns=["Date (UTC)", "Complete days", "Observed days"])
    assert values.iloc[-1].isna().all()
    assert daily["Complete days"].tolist() == [1, 1, 0]
    assert daily["Combined stake (AVAX)"].iloc[0] == 30
    assert daily["Combined staking ratio (%)"].iloc[0] == 30


def test_time_mean_of_ratios_is_not_ratio_of_time_means(state):
    state.quantity = "Staking ratio"
    row = state.table().iloc[0]
    assert row["Validator staking ratio (%)"] == pytest.approx((20 + 30) / 2)
    assert row["Complete days"] == 2 and row["Observed days"] == 3
    state.quantity = "Active stake"
    assert state.table()["Validator stake (AVAX)"].iloc[0] == 40
    state.quantity = "Supply"
    assert state.table()["Realized total supply (AVAX)"].iloc[0] == 150


def test_stock_reducers_never_sum_snapshots_and_keep_empty_gaps(ledger):
    daily = daily_state(ledger)
    for statistic, expected in [("Last", 60), ("Mean", 40), ("Median", 40), ("Last minus first", 40)]:
        assert summarize_state(daily, "Week", statistic)["Validator stake (AVAX)"].iloc[0] == expected
    daily_summary = summarize_state(daily, "Day", "Last")
    assert pd.isna(daily_summary["Validator stake (AVAX)"].iloc[-1])
    assert daily_summary["Complete days"].tolist() == [1, 1, 0]
    with pytest.raises(ValueError, match="unique"):
        daily_state(pd.concat([ledger, ledger.iloc[:1]]))


def test_filters_population_and_era_boundary(state):
    state.date_range = (date(2026, 9, 22), date(2026, 9, 22))
    state.population = "Delegators"
    assert state.columns() == ["Delegated stake (AVAX)"]
    assert state.table()["Delegated stake (AVAX)"].iloc[0] == 40
    state.date_range = state.param.date_range.bounds
    state.grouping = "Era"
    # Day-close observations on activation day belong to Helicon.
    assert len(state.table()) == 2
    assert state.table()["Observed days"].tolist() == [1, 2]
    state.date_range = (date(2026, 9, 23), date(2026, 9, 23))
    assert state.table()["Delegated stake (AVAX)"].isna().all()


def test_rendering_and_stable_table_updates(state):
    panel = state.panel()
    table = panel[3]
    state.quantity = "Staking ratio"
    state.population = "Validators"
    assert panel[3] is table
    assert "Validator staking ratio (%)" in table.value
    assert "Delegated staking ratio (%)" not in table.value
    figure = hv.render(state.plot())
    lines = [r.glyph for r in figure.select(GlyphRenderer) if isinstance(r.glyph, Line)]
    assert len(lines) == 1 and lines[0].line_color == staking_state.QUANTITY_COLORS["stake"]
    assert figure.yaxis[0].axis_label == "Staking ratio (%)"
    assert figure.above and figure.select(BoxAnnotation)
    assert any(label == "Measure" for tool in figure.select(HoverTool) for label, _ in tool.tooltips)
