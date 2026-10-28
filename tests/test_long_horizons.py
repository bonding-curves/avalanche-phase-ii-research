"""Longer runs: a run of N days measured at every listed horizon, with the defaults unchanged.

The reproduction hashes were recorded at tag ``model-v0.8.0`` (commit b18a4a2) on 2026-10-28 from the fitted
reference scenario of ``test_fitted_lifecycle.model`` with renewals and arrivals, run for 365 days. The long
table's hash leaves out the ``time`` and ``dt`` columns and is taken over the rows in a fixed order, so it reads every
state variable, every float variable and every setting column of every run and day.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cadCAD")
pytest.importorskip("scipy")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import m2_sweep_design as m2  # noqa: E402
from test_fitted_lifecycle import model  # noqa: E402
from test_kpis import AVAX, COSTS, ORIGIN, full_table, table  # noqa: E402

from avalanche_research.experiments import sweep  # noqa: E402
from avalanche_research.model import kpis  # noqa: E402
from avalanche_research.model.engine import run  # noqa: E402
from avalanche_research.model.fitted_blocks import Arrivals, RenewalLogit  # noqa: E402

RECORDED = ("c40b8413b4cf8c8f", "4708890cca7c55f4d4dee8c16154919fde1edd3078fe0894ad9d1cfc71c4f4dd")
"""The fitted reference scenario at 365 days: its specification hash and its long table's SHA-256 at the tag."""


def reference(timesteps: int):
    return model(renewal=RenewalLogit(intercept=0.5), arrivals=Arrivals(mean_per_day=2.0), timesteps=timesteps, runs=2, seed=11)


def table_sha256(long: pd.DataFrame) -> str:
    kept = long.drop(columns=[c for c in ("time", "dt") if c in long.columns])
    body = kept.sort_values(["simulation", "run", "timestep", "variable"]).reset_index(drop=True).to_csv(index=False, float_format="%.12g")
    return hashlib.sha256(body.encode()).hexdigest()


def ordered(long: pd.DataFrame) -> pd.DataFrame:
    kept = long.drop(columns=[c for c in ("time", "dt", "timesteps", "specification") if c in long.columns])
    return kept.sort_values(["simulation", "run", "timestep", "variable"]).reset_index(drop=True)


# The defaults reproduce the tag.

def test_a_one_year_run_reproduces_the_tag_specification_and_table_byte_for_byte():
    built = reference(365)
    assert built.specification_hash() == RECORDED[0]
    assert table_sha256(run(built)) == RECORDED[1]


def test_the_design_script_defaults_are_the_milestone_2_timesteps_and_horizons():
    assert horizon_settings_of([]) == (365, [365, 180])
    assert horizon_settings_of(["--timesteps", "1825", "--horizons", "180,365,730,1825"]) == (1825, [180, 365, 730, 1825])
    assert horizon_settings_of(["--timesteps", "3650", "--horizons", "365,730,1825,3650"]) == (3650, [365, 730, 1825, 3650])
    with pytest.raises(ValueError, match="past the run's 365 timesteps"):
        horizon_settings_of(["--horizons", "180,730"])
    with pytest.raises(ValueError, match="no horizon repeated"):
        horizon_settings_of(["--horizons", "365,365"])
    with pytest.raises(ValueError, match="needs a value"):
        horizon_settings_of(["--timesteps"])


def horizon_settings_of(flags: list[str]) -> tuple[int, list[int]]:
    positional, timesteps, horizons = m2.horizon_settings(["v0.8.0", "out", *flags])
    assert positional == ["v0.8.0", "out"]
    return timesteps, horizons


# A longer run changes nothing before the old horizon.

def test_the_first_year_of_a_longer_run_equals_the_one_year_run_day_for_day():
    year, longer = run(reference(365)), run(reference(400))
    first = longer[longer["timestep"] <= year["timestep"].max()]
    pd.testing.assert_frame_equal(ordered(year), ordered(first))


def test_extra_horizons_leave_the_values_at_the_existing_horizons_unchanged():
    daily = full_table(days_after=1830)
    index = ["measure", "horizon_days", "cost_level"]
    old = kpis.kpi_table(daily, ORIGIN, [365, 180], baseline=daily, competing_yield=0.04, operating_costs=COSTS).set_index(index)["value"]
    new = kpis.kpi_table(daily, ORIGIN, [180, 365, 730, 1825], baseline=daily, competing_yield=0.04, operating_costs=COSTS).set_index(index)["value"]
    assert set(new.index.get_level_values("horizon_days")) == {180, 365, 730, 1825}
    pd.testing.assert_series_equal(new.loc[old.index], old)
    assert np.isfinite(new.to_numpy(dtype=float)).all()


def test_the_kpi_reducer_accepts_every_horizon_within_the_run_and_refuses_one_past_it():
    design = {"timesteps": 1825, "reducer": {"kind": "kpis", "horizons": [180, 365, 730, 1825], "competing_yield": 0.04,
                                               "operating_costs": {"zero": 0.0}}}
    assert max(design["reducer"]["horizons"]) <= design["timesteps"]
    with pytest.raises(ValueError, match="past the run's 1825 timesteps"):
        sweep.kpi_reducer({**design, "reducer": {**design["reducer"], "horizons": [365, 3650]}}, Path("unused"), "unused")


# The earned rate past four years.

def test_the_earned_rate_does_not_wrap_when_365_times_the_issuance_passes_2_to_the_63():
    days = 1830
    issued_per_day = 30_000 * AVAX  # 3e13 nAVAX, so 365 times five years of it is about 2e19, past 2**63
    stake_days_per_day = 1_000 * AVAX * 60  # small enough that its own five-year sum stays within 64 bits
    daily = table(ORIGIN, {"issued_navax": [issued_per_day] * (days + 1), "started_stake_days_navax": [stake_days_per_day] * (days + 1)})
    assert daily["issued_navax"].dtype == np.int64
    assert 365 * issued_per_day * 1825 > 2**63
    rate = kpis.earned_rate(daily, ORIGIN, 1825)
    assert rate == pytest.approx(365 * issued_per_day / stake_days_per_day, rel=1e-12)
    # Within four years the value is the one the 64-bit product converts to.
    short = kpis.earned_rate(daily, ORIGIN, 365)
    assert short == float(np.int64(365) * np.int64(issued_per_day * 365) / np.int64(stake_days_per_day * 365))
