"""Typed KPI transport on synthetic engine output, without running a model or fit."""

import hashlib
import json
import os
import pickle

import duckdb
import numpy as np
import pandas as pd
import pytest

from avalanche_research.experiments import sweep
from avalanche_research.experiments.sweep import KpiReducer
from avalanche_research.model import engine, kpis, runner

ORIGIN = "2024-06-30"
BIG = 2**53 + 1
DAILY_ISSUANCE = 10_000_000_001
INTEGER_CHANNELS = [
    "active_validators", "active_validator_stake_navax", "supply_navax", "issued_navax",
    "started_stake_navax", "started_stake_days_navax", "nakamoto_third_nodes",
]
MEASURES = {
    "issued_navax", "validator_stake_navax", "lowest_validator_stake_navax", "active_validators",
    "net_inflation", "validator_staking_ratio", "nakamoto_coefficient", "earned_rate", "return_margin",
    "stake_weighted_duration", "reward_rate_volatility", "stake_volatility", "worst_30_day_stake_fall",
    "issuance_half_life",
}


class SyntheticBase:
    runs = 1

    def __init__(self, amplitude=0.01, omit_rate=False):
        self.amplitude = amplitude
        self.omit_rate = omit_rate

    def with_settings(self, **values):
        return SyntheticBase(values.get("amplitude", self.amplitude), values.get("omit_rate", self.omit_rate))

    def specification_hash(self):
        return hashlib.sha256(json.dumps({"synthetic_amplitude": self.amplitude}).encode()).hexdigest()[:16]

    def state_variables(self):
        return INTEGER_CHANNELS

    def float_variables(self):
        return ["offered_rate_30d"]

    def settings(self):
        return {"dt": 1}


def synthetic_engine_table(model):
    """Use the real long-table conversion with declared integer and float channels."""
    days = np.arange(366)
    rates = 0.06 + model.amplitude * np.sin(days / 11)
    rates[0] = np.nan
    raw = pd.DataFrame({
        "simulation": 0, "run": 0, "timestep": days, "substep": 0,
        "active_validators": 100 + days % 3,
        "active_validator_stake_navax": BIG + days,
        "supply_navax": 450_000_000 * 10**9 + days * DAILY_ISSUANCE,
        "issued_navax": [0, BIG] + [DAILY_ISSUANCE] * 364,
        "started_stake_navax": 10**9 + 3,
        "started_stake_days_navax": 90 * (10**9 + 3) + 1,
        "nakamoto_third_nodes": 20 + days % 2,
        "offered_rate_30d": rates,
    })
    table = engine._long_table(raw, [model])
    return table.drop(columns="offered_rate_30d") if model.omit_rate else table


def synthetic_chain():
    days = pd.date_range(pd.Timestamp(ORIGIN) - pd.Timedelta(days=365), pd.Timestamp(ORIGIN))
    return pd.DataFrame({
        "active_validators": 100, "active_validator_stake_navax": BIG,
        "supply_counter_navax": 450_000_000 * 10**9, "issued_navax": DAILY_ISSUANCE,
        "started_stake_navax": 10**9 + 3, "started_stake_days_navax": 90 * (10**9 + 3) + 1,
        "nakamoto_third_nodes": 20, "offered_rate_30d": 0.06,
        "burned_navax": 1_000_000_001, "total_supply_navax": 440_000_000 * 10**9,
    }, index=days)


class IntegerAuditedReducer(KpiReducer):
    def __call__(self, table, row):
        for variable, expected in (("active_validator_stake_navax", BIG + 1), ("issued_navax", BIG)):
            value = table.loc[(table.variable == variable) & (table.timestep == 1), "value"].item()
            assert isinstance(value, (int, np.integer)) and int(value) == expected
        daily = kpis.run_daily_table(table, ORIGIN, self.chains[ORIGIN])
        assert daily.loc[pd.Timestamp(ORIGIN) + pd.Timedelta(days=1), "issued_navax"] == BIG
        result = super().__call__(table, row)
        result["integer_state_canary"] = BIG
        result["worker_pid_canary"] = os.getpid()
        return result


def test_process_reducer_parquet_keeps_fractional_rate_effects_and_exact_integer_state(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "run", synthetic_engine_table)
    base = SyntheticBase()
    base_path = tmp_path / "base.pickle"
    base_path.write_bytes(pickle.dumps(base))
    rows = [
        {"design": "typed-transport", "index": index, "seed": 0, "origin": ORIGIN, "amplitude": amplitude}
        for index, amplitude in enumerate((0.01, 0.02))
    ]
    reducer = IntegerAuditedReducer({ORIGIN: synthetic_chain()}, [180, 365], 0.04, {"mid": 0.005}, missing="raise")
    out = tmp_path / "rows"
    stats = runner._run_pickled(base_path, base.specification_hash(), rows, out, (),
                               workers=1, in_flight=1, stop_after=None, reducer=reducer)
    assert stats["written"] == 2
    result = duckdb.sql("SELECT * FROM read_parquet(?)", params=[str(out / "*.parquet")]).df()
    assert set(result.integer_state_canary) == {BIG}
    assert os.getpid() not in set(result.worker_pid_canary)
    for index, amplitude in enumerate((0.01, 0.02)):
        one = result[result["index"] == index]
        assert len(one) == 28
        for horizon in (180, 365):
            values = one[one.horizon_days == horizon].set_index("measure")["value"]
            assert set(values.index) == MEASURES
            expected_volatility = 100 * np.std(0.06 + amplitude * np.sin(np.arange(1, horizon + 1) / 11), ddof=1)
            assert values["reward_rate_volatility"] == pytest.approx(expected_volatility, rel=1e-12)
            assert values["issued_navax"] == float(BIG + (horizon - 1) * DAILY_ISSUANCE)
    volatility = result[result.measure == "reward_rate_volatility"].pivot(index="horizon_days", columns="index", values="value")
    np.testing.assert_allclose(volatility[1], 2 * volatility[0], rtol=1e-12)


@pytest.mark.parametrize("channel,measure", [
    ("offered_rate_30d", "reward_rate_volatility"),
    ("started_stake_navax", "stake_weighted_duration"),
    ("started_stake_days_navax", "earned_rate"),
    ("nakamoto_third_nodes", "nakamoto_coefficient"),
])
@pytest.mark.parametrize("missing", ["raise", "skip", None])
def test_missing_required_channels_refuse_in_strict_mode_and_keep_legacy_skip(channel, measure, missing):
    table = synthetic_engine_table(SyntheticBase())
    table = table.drop(columns=channel) if channel in table.columns else table[table.variable != channel]
    options = {} if missing is None else {"missing": missing}
    reducer = KpiReducer({ORIGIN: synthetic_chain()}, [180, 365], 0.04, {"mid": 0.005}, **options)
    if missing == "raise":
        with pytest.raises(kpis.MissingColumn, match=channel):
            reducer(table, {"origin": ORIGIN})
    else:
        result = reducer(table, {"origin": ORIGIN})
        assert measure not in set(result.measure)
        assert set(result.horizon_days) == {180, 365}


@pytest.mark.parametrize("missing", ["raise", None])
def test_operational_design_missing_policy_reaches_actual_reducer(monkeypatch, missing):
    monkeypatch.setattr(sweep.pins, "runs", lambda _: {"derived.avax-monetary-daily": "synthetic"})
    monkeypatch.setattr(sweep, "parquet_path", lambda *args: "synthetic-ledger")
    monkeypatch.setattr(kpis, "chain_daily_table", lambda *args: synthetic_chain())
    specification = {"kind": "kpis", "horizons": [180, 365], "competing_yield": 0.04, "operating_costs": {"mid": 0.005}}
    if missing is not None:
        specification["missing"] = missing
    reducer = sweep.kpi_reducer({"timesteps": 365, "origins": [ORIGIN], "reducer": specification}, "synthetic-pin", "synthetic-periods")
    missing_rate = synthetic_engine_table(SyntheticBase()).drop(columns="offered_rate_30d")
    if missing == "raise":
        with pytest.raises(kpis.MissingColumn, match="offered_rate_30d"):
            reducer(missing_rate, {"origin": ORIGIN})
    else:
        assert "reward_rate_volatility" not in set(reducer(missing_rate, {"origin": ORIGIN}).measure)


def test_strict_process_reducer_refuses_missing_rate_without_writing_a_completed_row(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "run", synthetic_engine_table)
    base = SyntheticBase()
    base_path = tmp_path / "base.pickle"
    base_path.write_bytes(pickle.dumps(base))
    row = {"design": "missing-transport", "index": 0, "seed": 0, "origin": ORIGIN, "omit_rate": True}
    reducer = KpiReducer({ORIGIN: synthetic_chain()}, [180, 365], 0.04, {"mid": 0.005}, missing="raise")
    out = tmp_path / "rows"
    with pytest.raises(kpis.MissingColumn, match="offered_rate_30d"):
        runner._run_pickled(base_path, base.specification_hash(), [row], out, (),
                           workers=1, in_flight=1, stop_after=None, reducer=reducer)
    assert not list(out.glob("*.parquet"))
    assert not list(out.glob("*.sha256"))


def test_reducer_refuses_an_unknown_missing_column_policy():
    with pytest.raises(ValueError, match="missing is 'raise' or 'skip'"):
        KpiReducer({}, [180, 365], 0.04, {}, missing="zero")
