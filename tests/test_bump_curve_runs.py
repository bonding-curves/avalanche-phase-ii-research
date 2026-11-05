import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def runs():
    spec = importlib.util.spec_from_file_location("bump_curve_runs", ROOT / "scripts" / "bump_curve_runs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def long_table(bands: bool) -> pd.DataFrame:
    """Two days of a run in the engine's long form, with or without the duration-band recorder's state."""
    names = ["active_validators", "active_validator_stake_navax", "supply_navax", "issued_navax", "started_stake_navax"]
    if bands:
        names += ["started_stake_d0_21_navax", "started_stake_d45_100_navax"]
    rows = [{"timestep": day, "variable": name, "value": 10 * (day + 1), "offered_rate_30d": 0.07,
             "yield_gap_pp": 1.0, "started_stake_days_navax": 300.0 * (day + 1)} for day in (0, 1) for name in names]
    return pd.DataFrame(rows)


CELLS = {"chain@zero": {"formula": "chain", "response": "zero", "renewal_response": 0.0, "entry_response": 0.0,
                        "duration_response": None, "twin": None}}


def test_absent_duration_bands_stay_unmeasured():
    module = runs()
    wide = module.wide_table(long_table(bands=False), "chain@zero", 1, 0, "spec")
    for name in ("started_stake_d0_21_navax", "started_stake_d45_100_navax"):
        assert wide[name].isna().all()
        assert wide[f"cumulative_{name}"].isna().all()
    out = module.horizons_table(wide, CELLS, [1])
    assert out["started_share_d0_21"].isna().all()
    assert out["started_share_d45_100"].isna().all()
    assert (out["cumulative_issued_navax"] == 30).all()


def test_recorded_duration_bands_give_their_shares():
    module = runs()
    wide = module.wide_table(long_table(bands=True), "chain@zero", 1, 0, "spec")
    assert wide["cumulative_started_stake_d0_21_navax"].dtype == "int64"
    out = module.horizons_table(wide, CELLS, [1])
    assert (out["started_share_d0_21"] == 1.0).all()
    assert (out["started_share_d45_100"] == 1.0).all()
