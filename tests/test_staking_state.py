"""Common snapshot support, reducers, units, filters, and render channels."""

from datetime import date

import holoviews as hv
import pandas as pd
import panel as pn
import pytest
from bokeh.document import Document
from bokeh.models import (
    BoxAnnotation,
    DateFormatter,
    GlyphRenderer,
    HoverTool,
    Line,
    NumberFormatter,
    Patch,
    Plot,
)

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
    assert "Complete days" not in row and "Observed days" not in row
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
    assert "Observed days" not in state.table()
    state.date_range = (date(2026, 9, 23), date(2026, 9, 23))
    assert state.table()["Delegated stake (AVAX)"].isna().all()


def test_rendering_and_stable_table_updates(state):
    panel = state.panel()
    table = panel[3]
    assert isinstance(table.formatters["Date (UTC)"], DateFormatter)
    assert isinstance(table.formatters["Validator stake (AVAX)"], NumberFormatter)
    state.quantity = "Staking ratio"
    state.population = "Validators"
    assert panel[3] is table
    assert "Validator staking ratio (%)" in table.value
    assert "Delegated staking ratio (%)" not in table.value
    figure = hv.render(state.plot())
    lines = [r.glyph for r in figure.select(GlyphRenderer) if isinstance(r.glyph, Line)]
    assert len(lines) == 1 and lines[0].line_color == staking_state.QUANTITY_COLORS["stake"]
    assert figure.yaxis[0].axis_label == "Staking ratio (%)"
    assert figure.title.text == "Mean staking ratio by week"
    assert figure.above and figure.select(BoxAnnotation)
    assert any(label == "Measure" for tool in figure.select(HoverTool) for label, _ in tool.tooltips)


def test_active_stake_stacks_components_and_keeps_coverage_out_of_display(state):
    figure = hv.render(state.plot())
    patches = [r for r in figure.select(GlyphRenderer) if isinstance(r.glyph, Patch)]
    assert len(patches) == 2
    assert not any(isinstance(r.glyph, Line) for r in figure.select(GlyphRenderer))
    sources = {r.data_source.data["Measure"][0]: r.data_source.data for r in patches}
    assert sources["Validator stake (AVAX)"]["y"].tolist() == [0, 40]
    assert sources["Delegated stake (AVAX)"]["y"].tolist() == [40, 65]
    assert sources["Delegated stake (AVAX)"]["Value"] == [25, 25]
    assert state.table()["Combined stake (AVAX)"].iloc[0] == 65
    for tool in figure.select(HoverTool):
        assert not any(label in {"Complete days", "Observed days"} for label, _ in tool.tooltips)


@pytest.mark.parametrize("quantity", ["Active stake", "Supply", "Staking ratio"])
def test_each_grouping_replaces_the_notebook_plot_and_retains_data(state, quantity):
    state.quantity = quantity
    view = state.panel()
    root = view.get_root(Document())
    previous = None
    previous_pane = None
    for grouping in ["Week", "Month", "Day", "Year", "Era", "Week", "Month"]:
        state.grouping = grouping
        figures = list(root.select({"type": Plot}))
        assert len(figures) == 1
        figure = figures[0]
        assert figure.title.text == f"Mean {quantity.lower()} by {grouping.lower()}"
        if previous is not None:
            assert figure.id != previous
            assert view[2]._pane is not previous_pane
        previous = figure.id
        previous_pane = view[2]._pane
        glyphs = [r for r in figure.select(GlyphRenderer) if isinstance(r.glyph, (Line, Patch))]
        assert glyphs
        for renderer in glyphs:
            assert len({len(column) for column in renderer.data_source.data.values()}) == 1
            field = renderer.glyph.y
            values = renderer.data_source.data[field if isinstance(field, str) else field.field]
            assert pd.Series(values).notna().any()
        assert "Complete days" not in view[3].value and "Observed days" not in view[3].value


def test_incomplete_only_window_has_an_explicit_empty_plot(state):
    view = state.panel()
    root = view.get_root(Document())
    state.date_range = (date(2026, 9, 23), date(2026, 9, 23))
    assert isinstance(state.plot(), pn.pane.Markdown)
    assert not list(root.select({"type": Plot}))
    state.date_range = state.param.date_range.bounds
    assert len(list(root.select({"type": Plot}))) == 1


def test_area_hover_preserves_an_internal_missing_day(monkeypatch, ledger):
    ledger.loc[1, "complete"] = False
    ledger.loc[2, ["complete", "total_supply_close_wei"]] = [True, 2000 * 10**18]
    monkeypatch.setattr(staking_state, "_state_data", lambda run: daily_state(ledger))
    hv.extension("bokeh")
    figure = hv.render(StakingState("gap-fixture", grouping="Day").plot())
    validator = next(r for r in figure.select(GlyphRenderer)
                     if isinstance(r.glyph, Patch) and r.data_source.data["Measure"][0].startswith("Validator"))
    values = validator.data_source.data["Value"]
    assert values[:2] == [20, 20] and values[-2:] == [999, 999]
    assert len(values) == 5 and pd.isna(values[2])
    assert len({len(column) for column in validator.data_source.data.values()}) == 1
