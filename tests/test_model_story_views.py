"""The model v0.7 memo figures: structure traced from code, and each plot non-empty on small inputs."""

from datetime import UTC, date, datetime

import holoviews as hv
import pandas as pd

from avalanche_research.mechanisms import ChainReward, QuadraticReward
from avalanche_research.model.versions import VERSIONS
from avalanche_research.views import model_results as mr
from avalanche_research.views.model_structure import (
    lifecycle_dot,
    tiny_lifecycle,
    trace,
)


def test_trace_matches_the_model_blocks():
    model = tiny_lifecycle()
    t = trace(model)
    assert set(t.state) == set(model.initial_state())
    assert set(t.updates) == set(model.blocks()[0]["variables"])
    assert t.policies["lifecycle"]["reads"] == ["days_left", "stakes", "periods_done", "supply_navax"]
    assert t.updates["supply_navax"] == {"writes": ["supply_navax"], "reads_state": ["supply_navax"], "reads_signal": ["issued_navax"]}


def test_structure_diagram_draws_every_state_variable_and_nothing_else():
    model = tiny_lifecycle()
    dot = lifecycle_dot(model)
    drawn = {line.split('"')[1].removeprefix("state:") for line in dot.splitlines() if line.strip().startswith('"state:') and "->" not in line}
    assert drawn == set(model.initial_state())
    assert all(name in dot for name, _check in model.invariants())


def test_versions_run_in_call_order_and_v07_is_released():
    calls = [v.call for v in VERSIONS]
    assert calls == sorted(calls)
    v07 = next(v for v in VERSIONS if v.name == "v0.7")
    assert v07.call == date(2026, 10, 2) and v07.released


def test_each_plot_returns_a_nonempty_holoviews_object():
    supply = 465_000_000 * 10**9
    priced = datetime(2026, 12, 22, tzinfo=UTC)
    curves = mr.mechanism_table([ChainReward(), QuadraticReward()], supply, priced)
    issuance = pd.DataFrame({"mechanism": ["Chain today", "Quadratic curve"], "issuance_avax": [1e7, 9e6], "change_vs_chain": [0.0, -0.1]})
    sweep = pd.DataFrame({"response": [0.0, 0.0, 0.3, 0.3], "mechanism": ["Chain today", "Tenure boost"] * 2,
                          "validators_mean": [1300, 1310, 1300, 1400], "validators_p10": [1290, 1300, 1290, 1380],
                          "validators_p90": [1310, 1320, 1310, 1420], "issuance_million_avax": [5.2, 5.5, 5.2, 5.9]})
    scores = pd.DataFrame({"variable": ["active_validators", "active_validator_stake_navax"] * 2, "horizon_days": [30, 30, 90, 90],
                           "actual": [1000.0, 2e17, 1010.0, 2.1e17], "model_mean": [990.0, 1.9e17, 1000.0, 2e17],
                           "model_p10": [980.0, 1.8e17, 990.0, 1.9e17], "model_p90": [1005.0, 2.05e17, 1020.0, 2.2e17],
                           "model_abs_error": [10.0, 1e16, 10.0, 1e16], "persistence_abs_error": [5.0, 2e16, 20.0, 5e15],
                           "origin": ["Banff"] * 4, "origin_date": [date(2022, 10, 18)] * 4})
    plots = [mr.mechanism_plot(curves, issuance), mr.sweep_plot(sweep), mr.score_plot(scores), mr.roadmap_plot(today=date(2026, 10, 1))]
    for plot in plots:
        assert isinstance(plot, hv.core.dimension.ViewableTree | hv.Overlay)
        assert len(plot) > 0
    assert len(curves) > 0 and set(curves.mechanism) == {"Chain today", "Quadratic curve"}


def test_display_names_reach_the_legends_and_keep_the_colors():
    supply = 465_000_000 * 10**9
    curves = mr.mechanism_table([ChainReward(), QuadraticReward()], supply, datetime(2026, 12, 22, tzinfo=UTC))
    issuance = pd.DataFrame({"mechanism": ["Chain today", "Quadratic curve"], "issuance_avax": [1e7, 9e6], "change_vs_chain": [0.0, -0.1]})
    names = {"Chain today": "the chain at its 7.5% floor"}
    left = mr.mechanism_plot(curves, issuance, names=names)[0]
    assert {c.label for c in left} == {"the chain at its 7.5% floor", "Quadratic curve"}
    sweep = pd.DataFrame({"response": [0.0], "mechanism": ["Chain today"], "validators_mean": [1300], "validators_p10": [1290],
                          "validators_p90": [1310], "issuance_million_avax": [5.2]})
    panel = mr.sweep_plot(sweep, names={"Chain today": "Chain before ACP-285"})[0]
    assert "Chain before ACP-285" in {layer.label for layer in panel}


def test_the_development_score_plot_draws_each_model_and_simple_forecast_once():
    rows = [{"variable": "active_validator_stake_navax", "horizon_days": h, "model": m, "benchmark": b,
             "model_mase": h / 10 + (m == "v0.7"), "benchmark_mase": h / 20 + int(b[1])}
            for h in (30, 90, 180) for m in ("v0.7", "v0.8") for b in ("N1", "N2", "N3")]
    overlay = mr.development_score_plot(pd.DataFrame(rows))
    labels = {element.label for element in overlay if isinstance(element, hv.Scatter)}
    assert labels == {"Model v0.7", "Model v0.8", "Hold the origin value", "180-day trend", "Weekly AR(1)"}
    v07 = next(e for e in overlay if isinstance(e, hv.Scatter) and e.label == "Model v0.7")
    assert v07.dframe()["scaled error"].tolist() == [4.0, 10.0, 19.0]
