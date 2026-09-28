import json
import time
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from avalanche_research.model.protocol import potential_reward
from avalanche_research.model.types import NAVAX_PER_AVAX, SECONDS_PER_DAY
from avalanche_research.psuu import (
    analysis,
    design,
    goals,
    kpis,
    mechanisms,
    risk,
    runner,
    sensitivity,
    stub,
)

CALIBRATION = design.PriceCalibration(
    start_price_usd=37.78, sigma_annual=0.97, drift_log_annual={"bull": 0.82, "neutral": 0.0, "bear": -0.66},
    window=("2022-01-01", "2024-12-31"), source="test",
)
THRESHOLDS = goals.Thresholds(decentralization_min=0.99, apr_volatility_max=0.002, staking_volatility_max=0.01, basis="test")


@pytest.mark.parametrize("days", [14, 90, 200, 365])
def test_linear_curve_equals_protocol_reward(days):
    supply = 441_323_311
    expected = potential_reward(2_000 * NAVAX_PER_AVAX, days * SECONDS_PER_DAY, supply * NAVAX_PER_AVAX) / NAVAX_PER_AVAX
    got = float(mechanisms.reward_avax(2_000, days, supply, stub.Params(), {"staking_ratio": 0.45}))
    assert got == pytest.approx(expected, rel=1e-9, abs=1e-9)


def test_builtin_curves():
    params = stub.Params(mechanism="piecewise", max_stake_days=400)
    assert float(mechanisms.consumption_rate(100, params, {})) == pytest.approx(0.10 + 0.02 * 0.6)
    params = stub.Params(mechanism="state_dependent")
    low = float(mechanisms.consumption_rate(365, params, {"staking_ratio": 0.40}))
    mid = float(mechanisms.consumption_rate(365, params, {"staking_ratio": 0.55}))
    high = float(mechanisms.consumption_rate(365, params, {"staking_ratio": 0.70}))
    assert (low, mid, high) == pytest.approx((0.12 + 0.05, 0.12, 0.12 - 0.05))
    params = stub.Params(mechanism="node_age")
    rates = mechanisms.consumption_rate(np.array([365.0, 365.0]), params, {"node_age_days": np.array([0.0, 730.0])})
    assert rates == pytest.approx([0.12, 0.12 * 1.10])
    with pytest.raises(mechanisms.MechanismError):
        mechanisms.consumption_rate(30, stub.Params(mechanism="missing"), {})


def test_sim_adapter_matches_protocol():
    policies = pytest.importorskip("avalanche_research.sim.policies")
    supply = 441_323_311.0
    context = policies.MechanismContext(params=stub.Params(), supply_counter_avax=supply, staking_ratio=0.45)
    durations = np.array([14.0, 90.0, 365.0])
    got = mechanisms.as_sim_reward("linear")(np.full(3, 2_000.0), durations, context)
    expected = [potential_reward(2_000 * NAVAX_PER_AVAX, int(d) * SECONDS_PER_DAY, int(supply) * NAVAX_PER_AVAX) / NAVAX_PER_AVAX for d in durations]
    assert got == pytest.approx(expected, rel=1e-8)
    assert policies.linear(np.full(3, 2_000.0), durations, context) == pytest.approx(got, rel=1e-12)


def _engines():
    engines = [("stub", stub.run, stub.Params, stub.Scenario)]
    try:
        run, params, scenario = runner.load_engine("sim")
    except ImportError:
        return engines
    return engines + [("sim", run, params, scenario)]


@pytest.mark.parametrize("name,run,params_type,scenario_type", _engines())
def test_new_mechanism_needs_no_engine_change(name, run, params_type, scenario_type):
    def double_max(duration_days, params, state):
        return np.full_like(np.asarray(duration_days, dtype=float), 2 * params.max_consumption_rate)

    days = 30
    scenario = scenario_type(name="flat", price_usd=np.full(days, 30.0), external_yield=np.full(days, 0.04), start_date="2025-01-01")
    mechanisms.register("test_double_max", double_max)
    try:
        if name == "sim":
            mechanisms.install_into_sim(("linear", "test_double_max"))
        base = run(params_type(), scenario, seed=1, days=days)
        swapped = run(params_type(mechanism="test_double_max"), scenario, seed=1, days=days)
    finally:
        mechanisms.REGISTRY.pop("test_double_max")
        if name == "sim":
            from avalanche_research.sim.policies import REWARD_MECHANISMS

            REWARD_MECHANISMS.pop("test_double_max", None)
    assert set(kpis.FRAME_COLUMNS) <= set(swapped.columns)
    assert swapped["rewards_paid_avax"].sum() > base["rewards_paid_avax"].sum()


def test_full_design_shape():
    full = design.build_design(CALIBRATION)
    assert full.n_trajectories == 50_000 and full.days == 365 and full.start_date == "2025-01-01"
    table = full.parameters
    for name, (low, high) in design.PARAMETER_RANGES.items():
        assert table[name].between(low, high).all()
    assert (table["max_consumption_rate"] >= table["min_consumption_rate"]).all()
    assert table["mechanism"].value_counts().to_dict() == {name: 125 for name in design.MECHANISMS}
    kinds = pd.Series([spec.kind for spec in full.scenarios]).value_counts().to_dict()
    assert kinds == {"base": 12, "shock": 4, "stress": 4}
    seen = {full.trajectory(index) for index in range(0, 50_000, 7)}
    assert len(seen) == len(range(0, 50_000, 7))
    assert full.trajectory(49_999) == (499, 19, 4)
    assert design.build_design(CALIBRATION).digest() == full.digest()


def test_shock_and_stress_paths():
    specs = design.scenario_specs()
    shock = next(spec for spec in specs if spec.kind == "shock")
    calm = replace(shock, shock_drop=0.0, shock_day=None)
    ratio = design.price_path(shock, CALIBRATION, 3, 365) / design.price_path(calm, CALIBRATION, 3, 365)
    assert ratio[:90] == pytest.approx(1.0)
    assert ratio[96:] == pytest.approx(0.5)
    stress = next(spec for spec in specs if spec.kind == "stress")
    path = design.yield_path(stress, 365)
    assert path[0] == stress.yield_start and path[-1] == pytest.approx(stress.yield_start + 0.03 * 364 / 365)


def test_kpis_of_known_frame():
    days = np.arange(4)
    frame = pd.DataFrame({
        "day": days, "date": pd.date_range("2025-01-01", periods=4).date, "supply_avax": 100.0,
        "validator_stake_avax": 40.0, "delegated_stake_avax": 10.0, "staking_ratio": [0.50, 0.52, 0.51, 0.55],
        "validator_count": [900, 950, 1000, 1001], "rewards_paid_avax": 1.0, "reward_apr": [0.07, 0.08, 0.07, 0.08],
        "hhi": [0.01, 0.01, 0.02, 0.02], "net_inflation_annual": [0.04, 0.035, 0.03, 0.025],
        "validator_profit_usd_month": [10.0, -5.0, 0.0, 15.0],
    })
    result = kpis.kpis(frame)
    assert result["staking_ratio_final"] == 0.55 and result["validator_count_final"] == 1001
    assert result["decentralization_mean"] == pytest.approx(0.985)
    assert result["net_inflation_decreasing"] and result["net_inflation_slope"] == pytest.approx(-0.005 * 365)
    assert result["val_profitability_mean"] == pytest.approx(5.0)
    assert result["apr_volatility"] == pytest.approx(np.std([0.07, 0.08, 0.07, 0.08], ddof=1))
    assert result["staking_volatility"] == pytest.approx(np.std([0.02, -0.01, 0.04], ddof=1))
    evaluated = goals.evaluate(pd.DataFrame([result]), THRESHOLDS)
    assert evaluated.loc[0, "pass_STAKING_RATIO"] and evaluated.loc[0, "pass_VALIDATOR_COUNT"]
    assert not evaluated.loc[0, "pass_DECENTRALIZATION"] and not evaluated.loc[0, "pass_APR_VOLATILITY"]
    assert not evaluated.loc[0, "pass_G1"] and not evaluated.loc[0, "pass_all"]


def test_smoke_sweep_end_to_end(tmp_path):
    started = time.perf_counter()
    small = design.build_design(CALIBRATION, n_parameter_sets=10, seeds=(0,), days=365,
                                scenarios=design.scenario_specs()[::4])
    assert small.n_trajectories == 50
    out = tmp_path / "psuu-smoke"
    manifest = runner.run_sweep(small, out, engine="stub", workers=2, batch_size=10)
    assert manifest["status"] == "complete" and manifest["trajectories_written"] == 50
    receipt = json.loads((out / "receipt.json").read_text())
    assert receipt["rows"] == 50 and len(receipt["files"]) == 5
    assert json.loads((out / "manifest.json").read_text())["design"]["counts"]["trajectories"] == 50

    again = runner.run_sweep(small, out, engine="stub", workers=1, batch_size=10)
    assert again["batches"]["skipped_existing"] == 5 and again["batches"]["run"] == 0
    assert [item["sha256"] for item in again["receipt"]["files"]] == [item["sha256"] for item in receipt["files"]]
    other = design.build_design(CALIBRATION, n_parameter_sets=11, seeds=(0,), days=120, scenarios=design.scenario_specs()[::4])
    with pytest.raises(runner.SweepError):
        runner.run_sweep(other, out, engine="stub", workers=1, batch_size=10)

    results = runner.load_results(out)
    assert list(results["trajectory_id"]) == list(range(50))
    assert set(kpis.KPI_COLUMNS) <= set(results.columns)
    evaluated = goals.evaluate(results, THRESHOLDS)
    summary, importances = sensitivity.trees(evaluated)
    assert set(summary["target"]) == set(sensitivity.TARGETS)
    fitted = summary[summary["status"] == "fitted"]
    assert fitted["test_accuracy"].between(0, 1).all()
    for _, group in importances.groupby("target"):
        assert group["importance"].sum() == pytest.approx(1.0) or group["importance"].sum() == 0
    correlation = sensitivity.spearman(results)
    assert correlation.shape == (len(design.PARAMETER_RANGES), len(kpis.KPI_COLUMNS))
    advice = sensitivity.recommendations(evaluated)
    assert advice["point_estimate"]["param_id"] in set(results["param_id"])
    assert set(advice["per_goal"]) == set(goals.GROUPS)
    surface = risk.surface(evaluated)
    assert set(zip(surface["param_x"], surface["param_y"])) == {
        (a, b) for i, a in enumerate(design.CONTROLLABLE) for b in design.CONTROLLABLE[i + 1:]
    }
    assert (surface.groupby(["param_x", "param_y"])["trajectories"].sum() == 50).all()
    regions = risk.failure_regions(surface)
    assert (regions["fail_share"] > 0.5).all()

    baseline = {"decentralization_mean": 0.99, "apr_volatility": 0.002, "staking_volatility": 0.01}
    reduced = analysis.analyse(out, None, observed=baseline)
    assert reduced["trajectories"] == 50
    assert set(reduced["files"]) == {path.name for path in (out / "analysis").iterdir()} - {"manifest.json"}
    assert time.perf_counter() - started < 60


def test_smoke_sweep_on_the_sim_engine(tmp_path):
    pytest.importorskip("avalanche_research.sim.engine")
    from avalanche_research.catalog import ROOT

    behaviour = ROOT / "data" / "model" / "behaviour-v0.json"
    small = design.build_design(CALIBRATION, n_parameter_sets=8, seeds=(0,), days=120, scenarios=design.scenario_specs()[::5])
    manifest = runner.run_sweep(small, tmp_path / "sim-smoke", engine="sim", workers=1, batch_size=8,
                                behaviour_path=behaviour if behaviour.is_file() else None)
    assert manifest["status"] == "complete" and manifest["trajectories_written"] == small.n_trajectories == 32
    results = runner.load_results(tmp_path / "sim-smoke")
    assert results["invariants_hold"].all()
    assert set(results["mechanism"]) <= set(design.MECHANISMS)
    assert results["staking_ratio_final"].between(0, 1).all()


def test_observed_kpis_from_ledger():
    import duckdb

    from avalanche_research import datasets
    from avalanche_research.catalog import DataError

    try:
        con = datasets.connect()
        con.execute("SET memory_limit='5GB'; SET threads=6;")
        frame = kpis.observed_daily(con, "2025-01-01", "2025-01-14")
    except (DataError, duckdb.Error, ValueError) as error:  # built datasets are not part of a clean checkout
        pytest.skip(f"ledger datasets unavailable: {error}")
    assert list(frame.columns) == list(kpis.FRAME_COLUMNS) and len(frame) == 14
    ledger = con.execute(
        """SELECT (active_validator_stake_wei + active_delegated_stake_wei) / total_supply_close_wei
           FROM avax_monetary_daily WHERE date_utc BETWEEN '2025-01-01' AND '2025-01-14' ORDER BY date_utc"""
    ).fetchall()
    assert frame["staking_ratio"].to_numpy() == pytest.approx([float(row[0]) for row in ledger], rel=1e-12)
    assert frame["hhi"].between(0, 1).all() and frame["reward_apr"].between(0.05, 0.12).all()
    assert set(kpis.kpis(frame)) == set(kpis.KPI_COLUMNS)
