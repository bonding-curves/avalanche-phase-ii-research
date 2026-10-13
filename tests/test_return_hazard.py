"""The logit return hazard on the node's own history, and the candidate v0.8-a return that reads it.

The block is a daily logit on six bins of days out, the stake band, whether the node has returned before and whether
the commitment that ended was its first. It must recover known hazards under censoring, see the composition of the
nodes out of the set that the hazard by stake band and days out misses, keep an empty day bin off zero, read nothing
after the origin, and reach the simulator through the returns stage. The candidate changes only the return block of
v0.8-a, and at its default the switch leaves every existing variant as it was.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import numpy as np
import pytest
from scipy import special

pytest.importorskip("cadCAD")

from test_variant_switches import differing, events_with_state

from avalanche_research.model import variants
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_blocks import AVAX, ReturnHazard
from avalanche_research.model.fitted_lifecycle import (
    FittedLifecycle,
    fit_return_history,
    parameter_draws,
    training_events,
)
from avalanche_research.model.parts.return_hazard import (
    RETURN_LOGIT_TERMS,
    ReturnLogitHazard,
    return_design,
)
from avalanche_research.model.parts.returns import returns_stage
from avalanche_research.model.parts.stages import Day, RunBlocks
from avalanche_research.model.streams import Streams
from avalanche_research.model.variants import (
    CANDIDATES,
    DEVELOPMENT_MODELS,
    RETURN_HISTORY,
    VARIANTS,
    Switches,
)


def with_record(events, seed: int = 3):
    """Training events whose return spells carry a node record, drawn from their own generator so the events'
    other tables keep their values."""
    rng = np.random.default_rng(seed)
    lapsed = events.lapsed
    done = rng.integers(1, 6, len(lapsed))
    returns = np.minimum(rng.integers(0, 3, len(lapsed)), done - 1)
    return replace(events, lapsed=lapsed.assign(done=done, returns=returns))


def simulate_spells(rng, n, truth: ReturnLogitHazard, stake, done, returns, censor):
    """Days out of each spell under ``truth``, day by day from day 8, censored at ``censor`` and at 365."""
    days_out = np.full(n, 365)
    returned = np.zeros(n, bool)
    open_ = np.ones(n, bool)
    for day in range(8, 366):
        h = truth.probability({"stake_navax": stake, "days_since_end": np.full(n, day), "done": done, "returns": returns})
        hit = open_ & (day <= censor) & (rng.random(n) < h)
        days_out[hit], returned[hit] = day, True
        stop = open_ & (day >= censor) & ~hit
        days_out[stop] = np.minimum(censor[stop], 365)
        open_ &= ~hit & ~stop
    return days_out, returned


TRUTH = {"intercept": -3.0, "days_15_30": -0.5, "days_31_60": -1.2, "days_61_90": -1.8, "days_91_180": -2.4,
         "days_181_365": -3.0, "stake_mid": 0.3, "stake_large": 0.6, "returned_before": 1.0, "first_only": -1.0}


def test_the_fit_recovers_known_daily_hazards_under_censoring():
    rng = np.random.default_rng(5)
    n = 60_000
    truth = ReturnLogitHazard(**TRUTH)
    stake = rng.choice([2_000, 50_000, 500_000], n) * AVAX
    done = rng.integers(1, 8, n)
    returns = np.where(done > 1, rng.integers(0, 3, n), 0)
    censor = rng.integers(8, 500, n)
    days_out, returned = simulate_spells(rng, n, truth, stake, done, returns, censor)
    fitted = ReturnLogitHazard.fit(stake, days_out, returned, done, returns, "synthetic")
    for term, value in TRUTH.items():
        assert getattr(fitted, term) == pytest.approx(value, abs=0.12), term
    assert {meta["source"] for meta in fitted.sources().values()} == {"fitted"}


def test_the_fit_is_the_mode_of_the_node_day_likelihood_under_its_priors():
    """Counting node-days by pattern gives the same mode as scoring every node-day: the gradient of the node-day
    log-likelihood less the penalty is zero at the fit."""
    rng = np.random.default_rng(9)
    n = 3_000
    stake = rng.choice([2_000, 50_000], n) * AVAX
    done = rng.integers(1, 4, n)
    returns = np.where(done > 1, rng.integers(0, 2, n), 0)
    days_out, returned = simulate_spells(rng, n, ReturnLogitHazard(**TRUTH), stake, done, returns, rng.integers(8, 400, n))
    fitted = ReturnLogitHazard.fit(stake, days_out, returned, done, returns, "synthetic")
    spell = np.repeat(np.arange(n), np.maximum(np.minimum(days_out, 365) - 7, 0))
    day = np.concatenate([np.arange(8, d + 1) for d in np.minimum(days_out, 365)])
    y = returned[spell] & (day == days_out[spell])
    design = return_design(stake[spell], day, done[spell], returns[spell])
    from avalanche_research.model.parts.return_hazard import _penalty

    beta = fitted.coefficients()
    gradient = design.T @ (y - special.expit(design @ beta)) - _penalty() @ beta
    assert np.abs(gradient).max() < 1e-6
    inputs = {"stake_navax": stake[spell], "days_since_end": day, "done": done[spell], "returns": returns[spell]}
    p = fitted.probability(inputs)
    assert fitted.log_prob(inputs, y) == pytest.approx(float(np.where(y, np.log(p), np.log1p(-p)).sum()))


def test_with_two_kinds_of_node_the_record_sees_the_stock_the_cell_hazard_misses():
    """Nodes that returned before come back fast, nodes whose first commitment ended rarely. The nodes still out at
    the origin are mostly the slow kind, so the hazard by stake band and days out, which pools them, over-predicts
    their returns, here by more than 8%. The record hazard is within 2% of the truth."""
    rng = np.random.default_rng(21)
    n = 40_000
    truth = ReturnLogitHazard(intercept=float(special.logit(0.01)), returned_before=float(special.logit(0.15) - special.logit(0.01)),
                              first_only=float(special.logit(0.001) - special.logit(0.01)))
    stake = np.full(n, 2_000 * AVAX)
    kind = rng.random(n) < 0.5
    done = np.where(kind, 3, 1)
    returns = np.where(kind, 1, 0)
    ended = rng.integers(0, 730, n)
    days_out, returned = simulate_spells(rng, n, truth, stake, done, returns, ended)
    cells = ReturnHazard.fit(stake, days_out, returned, "synthetic")
    record = ReturnLogitHazard.fit(stake, days_out, returned, done, returns, "synthetic")
    out = ~returned & (ended < 365)

    def expected(block) -> float:
        stay, back = np.ones(out.sum()), np.zeros(out.sum())
        for d in range(1, 91):
            h = block.probability({"stake_navax": stake[out], "days_since_end": ended[out] + d, "done": done[out], "returns": returns[out]})
            back += stay * h
            stay *= 1 - h
        return float(back.sum())

    true, by_cells, by_record = expected(truth), expected(cells), expected(record)
    assert by_cells > 1.08 * true
    assert by_record == pytest.approx(true, rel=0.02)


def test_a_day_bin_without_returns_gets_a_positive_hazard_below_its_neighbours():
    """Nodes return only in their second week or after day 30. The random walk keeps the 15 to 30 day bin off zero."""
    n = 2_000
    days = np.concatenate([np.full(n // 2, 10), np.full(n // 4, 40), np.full(n // 4, 365)])
    returned = days < 365
    ones = np.ones(len(days), dtype=np.int64)
    fitted = ReturnLogitHazard.fit(np.full(len(days), 2_000 * AVAX), days, returned, ones * 2, ones * 0, "synthetic")
    h = fitted.probability({"stake_navax": np.full(3, 2_000 * AVAX), "days_since_end": np.array([10, 20, 40]),
                            "done": np.full(3, 2), "returns": np.zeros(3)})
    assert 0 < h[1] < min(h[0], h[2])
    assert h[1] > 1e-4


def test_a_term_with_no_node_days_stays_at_its_prior_and_is_labelled_by_it():
    days = np.array([10, 20, 40, 200, 365, 365])
    ones = np.ones(len(days), dtype=np.int64)
    fitted = ReturnLogitHazard.fit(np.full(len(days), 2_000 * AVAX), days, days < 365, ones, ones * 0, "synthetic")
    sources = fitted.sources()
    for term in ("stake_mid", "stake_large", "returned_before"):
        assert getattr(fitted, term) == 0.0 and sources[term]["source"] == "prior"
    assert sources["first_only"]["source"] == "fitted" and sources["days_181_365"]["source"] == "fitted"


@pytest.mark.parametrize(("returned", "intercept", "words"), [(False, -20.0, "no returns"), (True, 20.0, "a return on every node-day")])
def test_spells_with_one_outcome_hold_the_intercept_at_the_clip(returned, intercept, words):
    fitted = ReturnLogitHazard.fit([2_000 * AVAX], [8], [returned], [1], [0], "synthetic")
    assert fitted.intercept == intercept
    assert all(getattr(fitted, term) == 0.0 for term in RETURN_LOGIT_TERMS[1:])
    assert words in fitted.sources()["intercept"]["evidence"]


def test_the_class_default_has_no_returns_and_none_in_the_renewal_week_or_after_a_year():
    inputs = {"stake_navax": np.full(4, 2_000 * AVAX), "days_since_end": np.array([7, 8, 365, 366]), "done": np.full(4, 2),
              "returns": np.ones(4)}
    assert (ReturnLogitHazard().probability(inputs) < 1e-8).all()
    always = ReturnLogitHazard(intercept=20.0)
    assert always.probability(inputs).round(6).tolist() == [0, 1, 1, 0]
    assert ReturnLogitHazard().log_prob(inputs, np.array([True, False, False, False])) == float("-inf")


def stage(returns_block, out_done, out_returns):
    state = {"out_days": np.array([10, 10, 10]), "out_stakes": np.full(3, 2_000 * AVAX), "out_done": np.array(out_done),
             "out_returns": np.array(out_returns), "out_node_key": np.array([1, 2, 3])}
    blocks = RunBlocks(None, None, None, returns_block, 0.0, None, np.zeros(0), np.zeros(0))
    day = Day(t=0, start=datetime(2024, 3, 7, 12, tzinfo=UTC), draw=Streams(1, 1), blocks=blocks, renewal_gap=0.0,
              entry_gap=0.0, settings=None)
    return returns_stage(state, day, {})


def test_the_returns_stage_passes_each_nodes_record_to_the_block():
    """Only a node whose first commitment ended can return under this block, and only a node that returned before
    under the other."""
    first = ReturnLogitHazard(intercept=-10.0, first_only=20.0)
    again = ReturnLogitHazard(intercept=-10.0, returned_before=20.0)
    assert stage(first, [1, 3, 3], [0, 1, 0])["comes_back"].tolist() == [True, False, False]
    assert stage(again, [1, 3, 3], [0, 1, 0])["comes_back"].tolist() == [False, True, False]


def test_the_cell_hazard_reads_no_record_so_the_stage_is_unchanged_for_it():
    cells = ReturnHazard(**{name: 0.5 for name in ReturnHazard().sources()})
    a, b = stage(cells, [1, 3, 3], [0, 1, 0]), stage(cells, [9, 9, 9], [5, 5, 5])
    assert a["comes_back"].tolist() == b["comes_back"].tolist() and a["out_days"].tolist() == [11, 11, 11]


@pytest.fixture
def synthetic_periods(monkeypatch):
    monkeypatch.setattr(variants, "training_events", lambda periods, origin, run: with_record(events_with_state()))
    monkeypatch.setattr(variants, "window_sd", lambda periods, origin, renewal: (0.3, "synthetic"))


def test_the_candidate_is_v08a_with_the_return_switch_outside_the_development_scores():
    assert RETURN_HISTORY == replace(CANDIDATES["v0.8-a"], return_history=True)
    assert Switches().return_history is False
    assert {"v0.8-a return", "v0.8-a return u"} <= set(VARIANTS)
    assert not {"v0.8-a return", "v0.8-a return u"} & set(DEVELOPMENT_MODELS)


@pytest.mark.parametrize(("today", "candidate"), [("v0.8-a", "v0.8-a return"), ("v0.8-a u", "v0.8-a return u")])
def test_the_candidate_variant_changes_only_the_return_block(synthetic_periods, today, candidate):
    built, prepared = [], []
    for name in (today, candidate):
        variant = VARIANTS[name]
        prepared.append(variant.prepare("synthetic.parquet", date(2024, 3, 6), "synthetic", draws=3, draw_seed=4))
        built.append(variant.simulation(prepared[-1], seed=2, timesteps=20, runs=3, draws=prepared[-1].draws))
    spec = [b.specification() for b in built]
    expected = {"returns"} if prepared[0].draws is None else {"returns", "inputs_sha256"}
    assert differing(*spec) == expected
    if prepared[0].draws is not None:
        assert differing(spec[0]["inputs_sha256"], spec[1]["inputs_sha256"]) == {"draws"}
        old, new = prepared[0].draws, prepared[1].draws
        shared = [c for c in old.columns if not c.startswith("returns.")]
        assert new[shared].equals(old[shared])
        assert {c for c in new.columns if c.startswith("returns.")} == {f"returns.{t}" for t in RETURN_LOGIT_TERMS}
    events = with_record(events_with_state())
    assert isinstance(built[1].returns, ReturnLogitHazard)
    assert np.array_equal(built[1].returns.coefficients(), fit_return_history(events).coefficients())
    assert run(built[1]).equals(run(built[1]))


def test_with_draws_each_run_reads_its_own_refit_of_the_record_hazard():
    events = with_record(events_with_state())
    draws = parameter_draws(events, n=3, seed=4, tau=0.3, return_history=True)
    plain = parameter_draws(events, n=3, seed=4, tau=0.3)
    shared = [c for c in plain.columns if not c.startswith("returns.")]
    assert draws[shared].equals(plain[shared])
    assert draws["returns.intercept"].nunique() == 3
    inputs = {**variants.switched_inputs(events, RETURN_HISTORY), "moves": events.moves, "first_commitments": events.first_commitments}
    model = FittedLifecycle(**inputs, runs=3, timesteps=5, draws=draws)
    blocks_for = model._blocks_by_run()
    for r in (1, 2, 3):
        block = blocks_for(r).returns
        assert block.intercept == draws["returns.intercept"].iloc[r - 1]
        assert block.sources()["intercept"]["evidence"].startswith(f"bootstrap draw {r}")


def test_the_record_hazard_and_its_draws_read_nothing_after_the_origin(tmp_path):
    """The fit and its draws from a periods file cut at the origin's end equal those from the full file, and the
    spells carry the record each node had when it left."""
    import duckdb

    from avalanche_research import datasets
    from avalanche_research.catalog import DataError
    from avalanche_research.model.fitted_lifecycle import INSTANT_US, US_PER_DAY, _day

    try:
        full = str(datasets.parquet_path("derived.staking-periods"))
    except (DataError, StopIteration, FileNotFoundError):
        pytest.skip("no built staking-periods run in this checkout")
    origin = date(2024, 3, 6)
    cutoff = _day(origin) * US_PER_DAY + INSTANT_US
    cut = str(tmp_path / "cut.parquet")
    duckdb.execute(f"COPY (SELECT * FROM read_parquet(?) WHERE accepted_at <= make_timestamp({cutoff})) TO '{cut}' (FORMAT parquet)", [full])
    fits = {}
    for name, path in (("full", full), ("cut", cut)):
        events = training_events(path, origin)
        fits[name] = (fit_return_history(events).coefficients(), parameter_draws(events, n=2, seed=0, tau=0.2, return_history=True))
        lapsed = events.lapsed
        assert (lapsed["done"] >= 1).all() and (lapsed["returns"] <= lapsed["done"]).all()
        assert (lapsed.loc[lapsed["done"] == 1, "returns"] == 0).all()
    assert np.array_equal(fits["full"][0], fits["cut"][0])
    assert fits["full"][1].equals(fits["cut"][1])
