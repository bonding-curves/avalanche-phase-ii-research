"""Check the quantities plotted for the reported central-case comparison."""

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("matplotlib")

SOURCE = Path(__file__).resolve().parents[1] / "scripts/figures/central_case_reproduction.py"
SPEC = importlib.util.spec_from_file_location("central_case_figure", SOURCE)
figure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(figure)


@pytest.fixture(scope="module")
def paths():
    dates = [(date(2025, 11, 18) + timedelta(days=day)).isoformat() for day in range(366)]
    return pd.DataFrame([
        {"cell": cell, "key": key, "day": day,
         "date": dates[day],
         "validator_stake_navax": (1 if key < 45 else 101) * 10**9,
         "active_validators": key + 1, "realized_supply_navax": 450_000_000 * 10**9}
        for cell in ("chain-central", "ramp-7.5-central") for key in range(50) for day in range(366)
    ])


def test_skewed_paths_use_percentiles_in_avax_instead_of_a_mean(paths):
    values = figure.trajectory_quantiles(paths)
    stake = values[values.measure == "validator_stake_avax"]
    assert len(values) == 2 * 366 * 3
    assert (stake.paths == 50).all()
    assert (stake["median"] == 1).all()
    assert (stake.p10 == 1).all()
    assert stake.p90.to_numpy() == pytest.approx(11)


@pytest.mark.parametrize("damage", ["missing", "duplicate"])
def test_missing_or_repeated_path_state_is_rejected(paths, damage):
    malformed = paths.iloc[1:] if damage == "missing" else pd.concat([paths.iloc[:-1], paths.iloc[:1]])
    with pytest.raises(ValueError, match="100 original paths"):
        figure.trajectory_quantiles(malformed)


def test_post_origin_record_cannot_silently_enter_the_figure(tmp_path):
    dates = pd.date_range("2020-09-22", "2025-11-19")
    frame = pd.DataFrame({"date": dates, "validator_stake_avax": 1,
                          "active_validators": 1, "total_supply_avax": 450_000_000})
    path = tmp_path / "record.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="no later observations"):
        figure.read_record(path)
