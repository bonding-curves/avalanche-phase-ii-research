"""The stylised-fact tests SF1 to SF10: the record passes its own facts, each negative control fails the fact it breaks,
and a model run becomes the paths the tests read, with its required facts failing when they cannot run.

Every control is the record with one behaviour replaced, so a failure points at that behaviour alone. The record is the
Avalanche daily panel from 23 September 2020 to 18 November 2025, the day before the held-back period: price, staked
AVAX, active validators, validator endings and renewals within 7 days, first-ever starts, the one-year reward rate and
the Aave v3 WAVAX supply rate from 8 August 2022. The panel carries a price or rate forward over a gap of up to 7 days.
"""
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from test_fitted_lifecycle import model as small_model

from avalanche_research.model.engine import run
from avalanche_research.model.fitted_blocks import Arrivals, RenewalLogit
from avalanche_research.model.stylised_facts import BANDS, evaluate, ms2_fit
from avalanche_research.model.stylised_paths import REPORTED, REQUIRED, check, paths_from_table, required_failures

RECORD = Path(__file__).resolve().parent / "data" / "stylised_facts_record.csv.gz"
MS_START = "2020-10-01"
CLASSES = [("bull", "2021-05-12", "2021-11-21"), ("bear", "2021-11-22", "2022-05-06"), ("bear", "2022-05-07", "2022-12-31"),
           ("range", "2023-01-01", "2023-10-15"), ("bull", "2023-10-16", "2024-03-31"), ("range", "2024-04-01", "2024-11-05"),
           ("bull", "2024-11-06", "2025-01-20"), ("range", "2025-01-21", "2025-10-06"), ("bear", "2025-10-07", "2025-11-18")]
"""The record's dated market windows. The launch window to 11 May 2021 carries no class."""


def load_record(labelled: bool) -> pd.DataFrame:
    path = pd.read_csv(RECORD, parse_dates=["day"]).set_index("day")
    path.index.name = None
    if labelled:
        path["regime"] = None
        for cls, start, end in CLASSES:
            path.loc[start:end, "regime"] = cls
    return path


@pytest.fixture(scope="module")
def record():
    return load_record(labelled=False)


def result(paths, code, part):
    r = evaluate(paths, ms_start=MS_START)
    return r[(r.code == code) & (r.part == part)].iloc[0]


def failed(paths, code, part):
    return result(paths, code, part).passed == False  # noqa: E712  (numpy bool)


def test_record_passes_every_fact():
    for labelled in (True, False):
        r = evaluate([load_record(labelled)], ms_start=MS_START)
        ran = r[r.passed.notna()]
        assert len(ran) == len(BANDS)
        assert ran.passed.all(), ran[~ran.passed.astype(bool)]


def test_record_reproduces_the_record_study():
    r = evaluate([load_record(True)], ms_start=MS_START).set_index(["code", "part"]).value
    assert r["SF2", "calm_days"] == pytest.approx(39.5, abs=0.5)
    assert r["SF2", "turbulent_days"] == pytest.approx(13.1, abs=0.3)
    assert r["SF3", "swings_30"] == 41 and r["SF3", "swings_50"] == 17
    assert r["SF4", "staked_26w"] == pytest.approx(0.004, abs=0.002)
    assert r["SF6", "validators_26w"] == pytest.approx(0.147, abs=0.002)
    assert r["SF6", "validators_13w"] == pytest.approx(0.111, abs=0.002)
    assert r["SF8", "turbulent_logodds"] == pytest.approx(-0.21, abs=0.02)
    assert r["SF9", "bull_arrivals_log"] == pytest.approx(0.39, abs=0.01)
    assert r["SF10", "lending_bear_minus_bull_pp"] == pytest.approx(3.26 - 1.70, abs=0.02)


def test_stake_that_follows_price_fails_sf4_and_sf5(record):
    p = record.assign(staked_avax=record.staked_avax.iloc[0] * record.price_usd / record.price_usd.iloc[0])
    assert failed([p], "SF4", "staked_26w")
    assert failed([p], "SF5", "staked_through_fall")


def test_flat_validator_count_fails_sf6(record):
    p = record.assign(active_validators=1000.0)
    assert failed([p], "SF6", "validators_26w")
    assert failed([p], "SF6", "validators_13w")


def test_renewal_blind_to_price_fails_sf7(record):
    p = record.assign(renewed=(0.8 * record.endings).round())
    assert failed([p], "SF7", "renewal_pp_per_log_move")


def test_renewal_higher_when_turbulent_fails_sf8(record):
    lp = np.log(record.price_usd[record.index >= MS_START])
    r = lp.diff().dropna()
    turb = pd.Series(ms2_fit(r.values[None, :])["turbulent_prob"][0] > 0.5, index=r.index).reindex(record.index, fill_value=False)
    p = record.assign(renewed=(np.where(turb, 0.88, 0.78) * record.endings).round())
    assert failed([p], "SF8", "turbulent_logodds")


def test_arrivals_blind_to_market_fail_sf9(record):
    assert failed([record.assign(first_ever=5.0)], "SF9", "bull_arrivals_log")


def test_reward_rate_four_times_too_high_fails_sf10(record):
    assert failed([record.assign(reward_rate_pct_pa=4 * record.reward_rate_pct_pa)], "SF10", "usd_max")


def test_lending_yield_higher_in_bulls_fails_sf10(record):
    assert failed([record.assign(lending_yield_pct_pa=6 - record.lending_yield_pct_pa)], "SF10", "lending_bear_minus_bull_pp")


def test_constant_volatility_paths_fail_sf2():
    rng = np.random.default_rng(7)
    idx = pd.date_range("2020-09-23", periods=1883, freq="D")
    paths = [pd.DataFrame({"price_usd": 10 * np.exp(np.cumsum(rng.normal(0, 1.1 / np.sqrt(365), len(idx))))}, index=idx)
             for _ in range(8)]
    r = evaluate(paths).set_index(["code", "part"])
    assert not r.loc[("SF2", "turbulent_share"), "passed"] or not r.loc[("SF2", "turbulent_days"), "passed"] \
        or not r.loc[("SF2", "calm_days"), "passed"]


def test_price_only_path_runs_sf1_to_sf3_and_skips_the_rest(record):
    r = evaluate([record[["price_usd"]]], ms_start=MS_START)
    assert r[r.code.isin(["SF1", "SF2", "SF3"]) & r.lo.notna()].passed.all()
    assert r[~r.code.isin(["SF1", "SF2", "SF3"])].passed.isna().all()


def test_short_path_is_not_applicable(record):
    r = evaluate([record.iloc[:365]])
    assert r[r.code.isin(["SF2", "SF3", "SF4", "SF6", "SF10"])].passed.isna().all()


def test_gaps_in_days_are_refused(record):
    with pytest.raises(ValueError):
        evaluate([record.drop(record.index[100])])


def test_every_fact_is_required_or_reported_with_a_reason():
    codes = {band.code for band in BANDS.values()}
    for name, required in REQUIRED.items():
        assert codes == set(required) | set(REPORTED[name])
        assert not set(required) & set(REPORTED[name])


def test_a_required_fact_that_cannot_run_counts_as_a_failure(record):
    # A path without renewals cannot run SF7, and the loops model requires it.
    results, failing = check([record.drop(columns=["renewed"])], "v0.9.0 loops")
    assert set(failing.code) == {"SF7"} and failing.passed.isna().all()
    assert required_failures(evaluate([record]), "v0.9.0 loops").empty
    assert required_failures(evaluate([record.drop(columns=["renewed"])]), "v0.9.0 defaults").empty


def test_a_run_records_its_turnover_only_when_asked():
    plain = run(small_model())
    assert not {"ended_validators", "renewed_validators", "first_ever_validators"} & set(plain["variable"])
    assert small_model(record_turnover=True).specification_hash() != small_model().specification_hash()


def test_turnover_counts_endings_renewals_and_first_ever_starts():
    def series(table, variable):
        rows = table[(table["variable"] == variable) & (table["run"] == 1)].sort_values("timestep")
        return rows["value"].tolist()

    leaving = run(small_model(record_turnover=True))
    assert series(leaving, "ended_validators") == [0, 1, 1, 1, 0, 0]
    assert set(series(leaving, "renewed_validators")) == {0}
    staying = run(small_model(record_turnover=True, renewal=RenewalLogit(intercept=20.0)))
    assert series(staying, "renewed_validators") == series(staying, "ended_validators")
    assert sum(series(staying, "renewed_validators")) > 0
    arriving = run(small_model(record_turnover=True, arrivals=Arrivals(mean_per_day=3.0)))
    assert sum(series(arriving, "first_ever_validators")) > 0
    assert set(series(leaving, "first_ever_validators")) == {0}


def test_a_run_becomes_one_path_per_run_with_its_turnover():
    table = run(small_model(record_turnover=True, renewal=RenewalLogit(intercept=20.0)))
    paths = paths_from_table(table, date(2024, 1, 1))
    assert len(paths) == 2
    first = paths[0]
    assert first.index[0] == pd.Timestamp("2024-01-01") and len(first) == 6
    assert {"staked_avax", "active_validators", "endings", "renewed", "first_ever"} <= set(first.columns)
    assert "price_usd" not in first.columns
    assert first["staked_avax"].iloc[0] == pytest.approx(100_000)


def test_a_first_commitment_accepted_before_the_origin_counts_as_first_ever_on_its_start_day():
    # RV10 F1: a scheduled row due on day 1 with no earlier commitment is a first-ever start.
    avax = 10**9
    settings = {"initial": pd.DataFrame({"stakes": [10_000 * avax], "days_left": [100], "done": [1], "after_return": [False],
                                         "days": [100], "handed_on": [False]}),
                "scheduled": pd.DataFrame({"start_day": [1, 1], "stakes": [2_000 * avax, 3_000 * avax], "days": [14, 14],
                                           "done": [0, 2], "after_return": [False, False], "returns": [0, 0]}),
                "timesteps": 1, "runs": 1}

    def series(table, variable):
        return table[table["variable"] == variable].sort_values("timestep")["value"].tolist()

    on = run(small_model(**settings, record_turnover=True))
    assert series(on, "active_validators") == [1, 3]
    assert series(on, "first_ever_validators") == [0, 1]
    off = run(small_model(**settings))
    assert small_model(**settings, record_turnover=False).specification_hash() == small_model(**settings).specification_hash()
    columns = ["simulation", "run", "timestep", "variable", "value"]
    kept = on[~on["variable"].isin(["ended_validators", "renewed_validators", "first_ever_validators"])]
    pd.testing.assert_frame_equal(off[columns].sort_values(columns[:4]).reset_index(drop=True),
                                  kept[columns].sort_values(columns[:4]).reset_index(drop=True))
