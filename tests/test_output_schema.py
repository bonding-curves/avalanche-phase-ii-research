"""The output schema lists every output of the engine's long table and of the KPI table, with a unit, and its
Markdown rendering is the committed ``OUTPUTS.md``.

Small runs of each group check the schema against what the engine writes: the plain fitted lifecycle, the delegated
v0.8.1 candidate from its pin with a price path, turnover and the dollar margin, a revenue-funded run and the holder
model. The pinned case is skipped while the pin or its runs are absent.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cadCAD")
pytest.importorskip("scipy")

from test_fitted_lifecycle import model as fitted_model
from test_holders import FLAT, FUNDS, holder_model
from test_revenue_funding import NEED_AVAX_PA, SHARED

from avalanche_research.catalog import DataError
from avalanche_research.mechanisms import RevenueFunded
from avalanche_research.model import kpis, schema
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_blocks import AVAX

PIN = Path("data/pins/p2-model-v0.8.1.json")
OUTPUTS_MD = Path(schema.__file__).with_name("OUTPUTS.md")


def pinned_candidate():
    from avalanche_research.experiments.v081_inputs import CANDIDATE, prepare_candidate
    from avalanche_research.model.variants import VARIANTS

    try:
        prepared = prepare_candidate(PIN, date(2022, 7, 1))
    except (DataError, FileNotFoundError) as error:
        pytest.skip(f"the candidate's pin is not usable in this checkout: {error}")
    built = VARIANTS[CANDIDATE].simulation(prepared, seed=0, timesteps=3, runs=1)
    return built.with_settings(price0_usd=20.0, price_drift_pa=0.0, price_volatility_pa=0.5, record_turnover=True,
                               margin_response=0.2)


CASES = {
    "fitted": (lambda: fitted_model(), {"always"}),
    "candidate": (pinned_candidate, {"always", "delegations", "price", "turnover"}),
    "revenue": (lambda: fitted_model(**SHARED, mechanism=RevenueFunded(revenue_share=0.5), revenue_avax_pa=NEED_AVAX_PA),
                {"always", "revenue"}),
    "holders": (lambda: holder_model(FLAT, fund_holdings=FUNDS, benqi_stake_per_start_navax=25 * AVAX, timesteps=4, runs=1),
                {"always", "delegations", "holders"}),
}


@pytest.fixture(scope="module", params=list(CASES))
def case(request):
    build, wanted = CASES[request.param]
    built = build()
    return built, wanted, run(built)


def test_each_configuration_carries_exactly_the_outputs_the_schema_lists_for_its_groups(case):
    built, wanted, table = case
    assert schema.groups(built) == wanted
    expected = schema.expected(built)
    settings = set(schema.setting_names(built))
    columns = [c for c in table.columns if c not in settings]
    variables = sorted(table["variable"].unique())
    for name in variables:
        found = schema.lookup(name, "variable")
        assert found is not None and found.group in wanted, name
    for name in columns:
        found = schema.lookup(name, "identifier") or schema.lookup(name, "float")
        assert found is not None and found.group in wanted, name
    assert set(variables) == set(expected["variable"])
    assert set(columns) == set(expected["identifier"]) | set(expected["float"])


def test_each_output_has_the_dtype_the_schema_gives(case):
    built, _, table = case
    expected = schema.expected(built)
    for name, output in {**expected["identifier"], **expected["float"]}.items():
        assert str(table[name].dtype) == output.dtype.split(" ")[0], name


def test_every_entry_has_a_unit_a_description_a_known_placement_and_a_known_group():
    for output in schema.OUTPUTS:
        assert output.unit.strip() and output.description.strip(), output.name
        assert output.placement in schema.PLACEMENTS and output.group in schema.GROUPS, output.name
    assert len({(o.name, o.placement) for o in schema.OUTPUTS}) == len(schema.OUTPUTS)


def full_daily_table() -> tuple[pd.DataFrame, pd.Timestamp]:
    """A daily table with every column any KPI reads, 450 days long, so every measure of ``kpi_table`` is computed."""
    days = pd.date_range("2021-01-01", periods=450, freq="D")
    n = len(days)
    step = np.arange(n, dtype=np.int64)
    daily = pd.DataFrame({
        "active_validators": 1_000 + step % 7,
        "active_validator_stake_navax": (200_000_000 + 10_000 * step) * AVAX,
        "supply_counter_navax": (430_000_000 + 30_000 * step) * AVAX,
        "issued_navax": np.full(n, 30_000 * AVAX),
        "started_stake_navax": np.full(n, 3_000_000 * AVAX),
        "started_stake_days_navax": np.full(n, 3_000_000 * AVAX * 60.0),
        "offered_rate_30d": 0.07 + 0.001 * (step % 3),
        "nakamoto_third_nodes": np.full(n, 29),
        "burned_navax": np.full(n, 1_000.0 * AVAX),
        "total_supply_navax": (420_000_000.0 + 29_000 * step) * AVAX,
        "active_delegated_stake_navax": np.full(n, 25_000_000 * AVAX),
        "rewards_paid_navax": np.full(n, 25_000.0 * AVAX),
        "price_usd": np.full(n, 20.0),
        "liquid_staking_stake_navax": np.full(n, 3_000_000 * AVAX),
        "nakamoto_third_operators": np.full(n, 25),
        "effective_operators": np.full(n, 300.0),
    }, index=days)
    return daily, days[400]


def test_every_measure_the_kpi_table_produces_is_listed_and_every_listed_measure_is_produced():
    daily, origin = full_daily_table()
    table = kpis.kpi_table(daily, origin, horizons=(30,), competing_yield=0.04, operating_costs={"low": 0.01},
                           baseline=daily, secured_value_usd=1e9)
    produced = set(table["measure"])
    listed = {o.name for o in schema.entries("kpi")}
    assert produced == listed
    assert str(table["value"].dtype) == "float64"
    assert set(kpis.KPIS) | set(kpis.CONCENTRATION_KPIS) <= listed


def test_outputs_md_equals_the_rendering_of_the_schema():
    assert OUTPUTS_MD.read_text() == schema.render()
