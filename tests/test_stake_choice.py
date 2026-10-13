"""Synthetic contract fixtures. No source adapter, dataset or held-out score."""
import math
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from avalanche_research.model.parts import stake_choice as sc
from avalanche_research.model.parts.continuation import MOVE_STAKE_EDGES
from avalanche_research.model.parts.duration_transition import duration_band

M, X = sc.MIN_STAKE, sc.MAX_STAKE
C = int(datetime(2025, 10, 1, 23, 59, 59, tzinfo=UTC).timestamp()) * 10**6


def frame(context, previous=None, stakes=None, days=None, decided=None):
    stakes = [M] if stakes is None else stakes
    n = len(stakes)
    previous = ([0] if context == 'entry' else [M]) * n if previous is None else previous
    return pd.DataFrame(dict(zip(sc.FIT_COLUMNS, (
        np.asarray(previous, dtype=np.int64),
        np.asarray([30] * n if days is None else days, dtype=np.int64),
        np.asarray(stakes, dtype=np.int64),
        np.asarray([C] * n if decided is None else decided, dtype=np.int64),
    ))))


def tables():
    return {c: frame(c) for c in sc.CONTEXTS}


def evidence(ts, origin='2025-10-01', run='synthetic-fixture'):
    return {c: f'{run}; origin {origin}; 365 days; sha256 {sc.table_sha256(t)}' for c, t in ts.items()}


def fit(ts=None, labels=None):
    ts = tables() if ts is None else ts
    return sc.StakeChoice.fit(*(ts[c] for c in sc.CONTEXTS), evidence(ts) if labels is None else labels)


def test_hash_encoding_hand_computed():
    import hashlib
    t = frame('entry')
    payload = ('{"columns":["previous_stake_navax","next_days","next_stake_navax","decided_us"],'
               f'"rows":[[0,30,{M},{C}]]}}').encode()
    assert sc.table_sha256(t) == hashlib.sha256(payload).hexdigest()
    assert sc.table_sha256(t.iloc[::-1]) == sc.table_sha256(t)


def test_all_105_dispatch_cells_and_source_copy():
    b = fit()
    expected = {(c, d, s) for c in sc.CONTEXTS for d in range(5)
                for s in ([None] if c == 'entry' else range(10))}
    assert set(b._cells) == expected
    assert len(b.sources()) == 210
    for cell in b._cells.values():
        assert cell.p == (2 / 3 if cell.count else 1 / 2)
        assert cell.knots == (0.,)
        assert cell.knot_source == 'prior'
    sources = b.sources()
    sources.clear()
    assert len(b.sources()) == 210
    with pytest.raises(TypeError):
        b._cells[('entry', 0, None)] = None
    with pytest.raises(TypeError):
        sc.StakeChoice(cells=b._cells)
    with pytest.raises(TypeError):
        b.with_value('p', .1, 'assumed', 'manual')


@pytest.mark.parametrize('context', sc.CONTEXTS)
def test_no_change_all_atom_and_empty_runtime(context):
    b = fit()
    previous = 0 if context == 'entry' else M
    u = [0., 1 / 3, 2 / 3, .9, np.nextafter(1., 0.)]
    assert np.array_equal(b.stakes_from_uniforms(context, [previous] * 5, [30] * 5, u), [M] * 5)
    law = b.cell_probabilities(context, [previous], [30])[0]
    expected = np.full(103, 1e-12)
    expected[0] = 1.
    expected /= 1 + 102e-12
    np.testing.assert_allclose(law, expected, atol=1e-15, rtol=0)
    assert b.stakes_from_uniforms(context, [], [], []).dtype == np.int64
    assert b.log_prob(context, [], [], []).dtype == np.float64
    assert b.baseline_log_prob(context, [], [], []).dtype == np.float64
    assert b.cell_probabilities(context, [], []).shape == (0, 103)


def test_duration_and_stake_dispatch_boundary_uses_owners():
    b = fit()
    days = np.array([1, 20, 21, 44, 45, 99, 100, 199, 200, 365], dtype=np.int64)
    previous = np.full(len(days), M)
    assert [k[1] for k in b._dispatch(np.full(len(days), 'renewal'), previous, days)] == list(duration_band(days))
    for edge in MOVE_STAKE_EDGES:
        p = np.array([math.floor(edge * 10**9) - 1, math.floor(edge * 10**9),
                      math.floor(edge * 10**9) + 1], dtype=np.int64)
        assert [k[2] for k in b._dispatch(np.full(3, 'renewal'), p, np.full(3, 30))] == list(np.digitize(p / 10**9, MOVE_STAKE_EDGES, right=True))


def test_mixed_context_vector_and_hurdle_reuses_original_uniform():
    ts = tables()
    ts['renewal'] = frame('renewal', [4 * M, 4 * M], [4 * M, M])
    b = fit(ts)
    # p=(one keep+1)/(two decisions+2)=1/2. Changed singleton=M.
    assert list(b.stakes_from_uniforms(['renewal', 'renewal', 'entry'], [4*M, 4*M, 0], [30]*3, [.49, .5, .9])) == [4*M, M, M]
    # The full hurdle map drops at p, so it must never be integrated as monotone.
    law = b.cell_probabilities('renewal', [4*M], [30])[0]
    assert law[0] == pytest.approx(.5 / (1+101e-12), abs=1e-12)
    assert law[sc._cell_ids(4*M, M)] == pytest.approx(.5 / (1+101e-12), abs=1e-12)


def test_pooling_49_50_cell_duration_and_context():
    ts = tables()
    # 50 changes at duration band 1, split between two stake bands.
    ts['renewal'] = frame('renewal', [M]*49 + [10*M], [2*M]*49 + [20*M], days=[30]*50)
    b = fit(ts)
    cell0 = b._cells[('renewal', 1, 0)]
    assert (cell0.scope, cell0.knot_count, cell0.p) == ('duration', 50, 1/51)
    assert b._cells[('renewal', 0, 0)].scope == 'context'
    ts['renewal'] = frame('renewal', [M]*50 + [10*M], [2*M]*50 + [30*M], days=[30]*51)
    b = fit(ts)
    assert b._cells[('renewal', 1, 0)].scope == 'cell'
    assert b._cells[('renewal', 1, 0)].knots == (math.log(2),)*50
    assert b._cells[('return', 1, 0)].knots == (0.,)


def test_entry_pooling_and_add_one_is_cell_share():
    ts = tables()
    ts['entry'] = frame('entry', stakes=[M]*3 + [2*M]*50, days=[30]*53)
    b = fit(ts)
    c = b._cells[('entry', 1, None)]
    assert (c.p, c.scope, c.knot_count) == (4/55, 'cell', 50)
    assert b._cells[('entry', 0, None)].p == .5
    assert b._cells[('entry', 0, None)].scope == 'context'


def test_portable_quantile_exact_fixtures_ties_and_singleton():
    np.testing.assert_array_equal(sc._quantiles((0., 2.), np.array([0., .25, .5, .75, 1.])), [0, .5, 1, 1.5, 2])
    np.testing.assert_array_equal(sc._quantiles((0., 0., 2.), np.array([0., .25, .5, .75, 1.])), [0, 0, 0, 1, 2])
    np.testing.assert_array_equal(sc._quantiles((.25,), np.array([0., .9, 1.])), [.25]*3)


def test_uniform_log_segment_hand_computed_probability_fixture():
    # Segment log ratio [0,1]. At reference=M, thresholds e^.1 etc give
    # .1-wide masses, apart from <1e-12 integer floor effects.
    knots = (0., 1.)
    thresholds = np.array([M, M+1, math.ceil(M*math.exp(.1)), math.ceil(M*math.exp(.5)), X+1])
    cdf = sc._cdf_stake(knots, M, thresholds)
    np.testing.assert_allclose(cdf, [0., math.log((M+1)/M), .1, .5, 1.], atol=1e-12, rtol=0)


def test_ties_singleton_atom_and_clamps_hand_computed():
    # Half v-space is the repeated zero knot. Its floor lands on atom M.
    np.testing.assert_allclose(sc._cdf_stake((0., 0., math.log(2)), M, [M, M+1, 2*M+1]),
                               [0., .5 + .5*math.log((M+1)/M)/math.log(2), 1.], atol=1e-12, rtol=0)
    # Singleton q=0 reconstructs its reference exactly, including integer neighbors.
    for reference in [M, M+1, X-1, X]:
        np.testing.assert_array_equal(sc._changed((0.,), reference, np.array([0., .3, .9])), [reference]*3)
        np.testing.assert_array_equal(sc._cdf_stake((0.,), reference, [reference, reference+1]), [0., 1.])
    # A fully lower-clamped / upper-clamped branch is a point mass.
    np.testing.assert_array_equal(sc._changed((-math.log(1500),), M, np.array([0., .9])), [M]*2)
    np.testing.assert_array_equal(sc._changed((math.log(1500),), X, np.array([0., .9])), [X]*2)
    np.testing.assert_array_equal(sc._cdf_stake((-math.log(1500),), M, [M, M+1]), [0., 1.])
    np.testing.assert_array_equal(sc._cdf_stake((math.log(1500),), X, [X, X+1]), [0., 1.])


def test_fitted_singleton_clamp_collision_and_score_atom_priority():
    ts = tables()
    # Changed ratio 1/2 pooled to a runtime previous=M, hence every changed
    # draw lower-clamps to M, which is the runtime atom. Hurdle p=.5 in empty cell.
    ts['renewal'] = frame('renewal', [2*M], [M])
    b = fit(ts)
    law = b.cell_probabilities('renewal', [M], [365])[0]
    expected = np.full(103, 1e-12); expected[0] = 1.; expected /= 1 + 102e-12
    np.testing.assert_allclose(law, expected, atol=1e-15, rtol=0)
    assert b.log_prob('renewal', [M], [365], [M])[0] == pytest.approx(math.log(expected[0]), abs=1e-12)
    # Upper clamp is a non-atom when runtime reference is below maximum.
    ts['renewal'] = frame('renewal', [M], [X])
    b = fit(ts)
    reference = X-1
    law = b.cell_probabilities('renewal', [reference], [365])[0]
    assert law[0] == pytest.approx(.5 / (1+101e-12), abs=1e-12)
    assert law[sc._cell_ids(reference, X)] == pytest.approx(.5 / (1+101e-12), abs=1e-12)


def test_large_reference_neighbor_knots_floor_probability_fixture():
    # At large references there are only a handful of float64 products
    # between neighboring integer stakes. Analytic q=0 singleton still has
    # exactly unit atom measure. Two fitted adjacent stakes must score the
    # very integer outputs of their own floating sampler, not an ideal density.
    ts = tables()
    reference = X-10
    ts['renewal'] = frame('renewal', [reference]*2, [reference+1, reference+2])
    b = fit(ts)
    cell = b._cells[('renewal', 1, 9)]
    assert len(cell.knots) == 2
    actual = b.stakes_from_uniforms('renewal', [reference]*4, [30]*4, [0., .25, .5, np.nextafter(1.,0.)])
    assert actual[0] == reference
    assert (np.abs(actual-reference) <= 3).all()
    law = b.cell_probabilities('renewal', [reference], [30])[0]
    assert np.isfinite(law).all() and law.sum() == pytest.approx(1., abs=1e-15)
    # All non-atom stakes here lie in [0,.1), so there are exactly two masses.
    assert law[0] == pytest.approx(.25 / (1+101e-12), abs=1e-12)
    assert law[52] == pytest.approx(.75 / (1+101e-12), abs=1e-12)


def test_moving_and_entry_baseline_same_cells():
    ts = tables(); ts['entry'] = frame('entry', stakes=[M, M, 2*M])
    b = fit(ts)
    np.testing.assert_allclose(b.baseline_log_prob('renewal', [M]*2, [30]*2, [M, 2*M]),
                               [math.log(.99), math.log(.01/102)], atol=1e-12, rtol=0)
    np.testing.assert_allclose(np.exp(b.baseline_log_prob('entry', [0]*2, [30]*2, [M, 2*M])),
                               [(2/3)/(1+101e-12), (1/3)/(1+101e-12)], atol=1e-12, rtol=0)


@pytest.mark.parametrize('column', sc.FIT_COLUMNS)
@pytest.mark.parametrize('dtype', ['float64', 'object', 'bool', 'Int64', 'int32', 'uint64'])
def test_fit_refuses_non_native_int64_without_coercion(column, dtype):
    ts = tables(); labels = evidence(ts)
    ts['renewal'][column] = ts['renewal'][column].astype(dtype)
    with pytest.raises(ValueError, match='int64'):
        fit(ts, labels)


@pytest.mark.parametrize('context', sc.CONTEXTS)
def test_fit_refuses_empty_context_named(context):
    ts = tables(); ts[context] = ts[context].iloc[:0]
    with pytest.raises(ValueError, match=context):
        fit(ts)


@pytest.mark.parametrize('column,value', [('previous_stake_navax', M-1), ('previous_stake_navax', X+1),
                                         ('next_stake_navax', M-1), ('next_stake_navax', X+1),
                                         ('next_days', 0), ('next_days', 366),
                                         ('decided_us', C+1), ('decided_us', C-365*sc.US_PER_DAY),
                                         ('decided_us', sc.LOCKBOX_US)])
def test_fit_refuses_invalid_row(column, value):
    ts = tables(); ts['renewal'].loc[0, column] = value
    with pytest.raises(ValueError):
        fit(ts)


def test_fit_accepts_window_inner_edges_and_rejects_entry_previous():
    ts = tables(); ts['renewal'] = frame('renewal', [M]*2, [M]*2, decided=[C-365*sc.US_PER_DAY+1, C])
    fit(ts)
    ts['entry'].loc[0, 'previous_stake_navax'] = M
    with pytest.raises(ValueError, match='previous'):
        fit(ts)


@pytest.mark.parametrize('mutation', ['hash', 'origin', 'run', 'keys', 'shape', 'nonstring', 'lockbox', 'order'])
def test_evidence_refusals(mutation):
    ts = tables(); labels = evidence(ts)
    if mutation == 'hash': labels['renewal'] = labels['renewal'][:-1] + ('0' if labels['renewal'][-1] != '0' else '1')
    if mutation == 'origin': labels['renewal'] = labels['renewal'].replace('2025-10-01', '2025-09-30')
    if mutation == 'run': labels['renewal'] = labels['renewal'].replace('synthetic-fixture', 'other-run')
    if mutation == 'keys': labels['other'] = labels.pop('return')
    if mutation == 'shape': labels['renewal'] += '; extra'
    if mutation == 'nonstring': labels['renewal'] = {'source': labels['renewal']}
    if mutation == 'lockbox': labels = evidence(ts, origin='2025-11-19')
    if mutation == 'order': ts['renewal'] = ts['renewal'][list(reversed(sc.FIT_COLUMNS))]
    with pytest.raises(ValueError): fit(ts, labels)


@pytest.mark.parametrize('which,value', [('previous', [True, M]), ('days', [True, 30]), ('u', [True, .5]),
                                        ('days', [0, 30]), ('days', [366, 30]), ('days', [1.5, 30]),
                                        ('previous', [M-1, M]), ('previous', [X+1, M]),
                                        ('u', [-.1, .5]), ('u', [1., .5]), ('u', [np.nan, .5]),
                                        ('u', [np.inf, .5]), ('u', ['.2', '.5']), ('days', [[30], [30]])])
def test_runtime_refusals_before_coercion(which, value):
    b = fit(); args = {'context': 'renewal', 'previous_stake_navax': [M, M], 'next_days': [30,30], 'u': [.2,.5]}
    args[{'previous': 'previous_stake_navax', 'days': 'next_days', 'u': 'u'}[which]] = value
    with pytest.raises(ValueError): b.stakes_from_uniforms(**args)


@pytest.mark.parametrize('context', ['other', ['renewal'], ['renewal', 'bad'], [True, 'entry']])
def test_context_refusal(context):
    with pytest.raises(ValueError): fit().stakes_from_uniforms(context, [M,M], [30,30], [.2,.5])


def test_score_outside_support_and_bad_inputs():
    b = fit()
    for score in [b.log_prob, b.baseline_log_prob]:
        values = score('renewal', [M]*4, [30]*4, [M-1, M, X, X+1])
        assert np.isneginf(values[[0,3]]).all()
        assert np.isfinite(values[[1,2]]).all()
        with pytest.raises(ValueError): score('renewal', [M], [30], [True])
        with pytest.raises(ValueError): score('renewal', [M], [30], [M,M])


def test_precision_boundaries_independent_decimal_reference():
    from decimal import Decimal, localcontext
    # Decimal is test-only. Runtime stays float64 on legal fitted ratios.
    qs = [-math.log(1500), -1., -1e-12, 0., 1e-12, 1., math.log(1500)]
    for reference in [M, M+1, 17*M, X-1, X]:
        actual = sc._changed(tuple(qs), reference, np.linspace(0, 1, 97))
        with localcontext() as ctx:
            ctx.prec = 70
            for i, v in enumerate(np.linspace(0, 1, 97)):
                pos = Decimal.from_float(float(v)) * (len(qs)-1)
                left = min(int(pos), len(qs)-2)
                f = pos-left
                q = Decimal.from_float(qs[left])*(1-f) + Decimal.from_float(qs[left+1])*f
                expected = min(X, max(M, int(Decimal(reference)*q.exp())))
                assert abs(int(actual[i])-expected) / expected < 1e-9


def test_full_law_hand_computed_interpolated_fixture():
    ts = tables(); ts['renewal'] = frame('renewal', [M, M], [2*M, 4*M])
    b = fit(ts)
    law = b.cell_probabilities('renewal', [M], [30])[0]
    # p=1/4, q uniform on [log2,log4]. Bins [.6,.7) through [1.3,1.4).
    # Integer threshold effects are below 1e-12 at reference M.
    expected = np.full(103, 1e-12)
    expected[0] = .25
    expected[58:66] = .75 / math.log(2) * np.array([.7-math.log(2), .1, .1, .1, .1, .1, .1, math.log(4)-1.3])
    expected /= 1+94e-12
    np.testing.assert_allclose(law, expected, atol=1e-12, rtol=0)


def test_every_dispatch_cell_fits_and_draws_its_own_sample():
    days_by_band = [1, 21, 45, 100, 200]
    boundaries = [M] + [min(X, math.floor(e*10**9)+1) for e in MOVE_STAKE_EDGES]
    ts = {}
    expected = []
    contexts, previous, days = [], [], []
    for c in sc.CONTEXTS:
        rows = []
        for d, day in enumerate(days_by_band):
            for s in ([None] if c == 'entry' else range(10)):
                prior = 0 if s is None else boundaries[s]
                stake = M + (d*10+(s or 0)+1)*10**9
                if stake == prior:
                    stake += 10**9
                rows.extend([(prior, day, stake, C)]*50)
                contexts.append(c); previous.append(prior); days.append(day); expected.append(stake)
        ts[c] = pd.DataFrame(rows, columns=sc.FIT_COLUMNS, dtype='int64')
    b = fit(ts)
    assert all((c.count, c.changes, c.scope, c.p) == (50,50,'cell',1/52) for c in b._cells.values())
    actual = b.stakes_from_uniforms(contexts, previous, days, [.5]*105)
    np.testing.assert_allclose(actual, expected, atol=0, rtol=1e-9)
    assert [k[1:] for k in b._dispatch(np.asarray(contexts), np.asarray(previous), np.asarray(days))] == [(d,s) for c in sc.CONTEXTS for d in range(5) for s in ([None] if c=='entry' else range(10))]


def test_hash_is_order_sensitive_and_label_detects_changed_rows():
    ts = tables(); ts['renewal'] = frame('renewal', [M,M], [M,2*M])
    labels = evidence(ts)
    ts['renewal'] = ts['renewal'].iloc[::-1]
    assert sc.table_sha256(ts['renewal']) not in labels['renewal']
    with pytest.raises(ValueError, match='SHA-256'): fit(ts, labels)


@pytest.mark.parametrize('value', [[True,30], np.array([True,30], dtype=object), [False,30]])
def test_mixed_boolean_fit_input_refused_without_coercion(value):
    ts = tables(); ts['renewal'] = frame('renewal', [M,M], [M,M]); labels=evidence(ts)
    ts['renewal']['next_days'] = pd.Series(value, dtype=object)
    with pytest.raises(ValueError, match='int64'): fit(ts, labels)


def test_masked_uniform_refused():
    with pytest.raises(ValueError, match='masked'):
        fit().stakes_from_uniforms('renewal', [M], [30], np.ma.array([.5], mask=[True]))


def test_fit_input_copies_are_stable_after_caller_mutation():
    ts = tables(); labels=evidence(ts); b=fit(ts,labels)
    ts['renewal'].loc[0,'next_stake_navax'] = X
    labels['renewal'] = 'changed'
    assert b._cells[('renewal',1,0)].knots == (0.,)
    assert 'synthetic-fixture;' in b.sources()['renewal/d1/s0/p']['evidence']


def test_fitted_floor_collision_into_atom_away_from_clamps():
    ts = tables(); ts['renewal'] = frame('renewal', [X-2], [X-1])
    b = fit(ts)
    reference = M+10
    # The changed ratio is about 1+1/(3e15). At reference about 2e12,
    # its increment is <.001 nAVAX, so floor sends all changed mass to
    # the exact previous stake. Neither clamp is active.
    np.testing.assert_array_equal(b.stakes_from_uniforms('renewal', [reference]*3, [365]*3, [0.,.5,.99]), [reference]*3)
    law = b.cell_probabilities('renewal', [reference], [365])[0]
    expected = np.full(103, 1e-12); expected[0] = 1.; expected /= 1+102e-12
    np.testing.assert_allclose(law, expected, atol=1e-12, rtol=0)


def test_nested_masked_scalar_refused_before_coercion():
    with pytest.raises(ValueError, match='masked'):
        fit().stakes_from_uniforms('renewal', [M], [30], [np.ma.array(.5, mask=True)])


def test_canonical_decimal_log_edges():
    assert sc.LOG_EDGES[0] == -5.
    assert sc.LOG_EDGES[50] == 0.
    assert sc.LOG_EDGES[51] == .1
    assert sc.LOG_EDGES[-1] == 5.


@pytest.mark.parametrize('previous,following,tail', [(M,X,102), (X,M,1)])
def test_fitted_lower_and_upper_overflow_bins(previous, following, tail):
    ts=tables(); ts['renewal']=frame('renewal', [previous], [following])
    b=fit(ts)
    law=b.cell_probabilities('renewal', [previous], [30])[0]
    expected=np.full(103, 1e-12); expected[0]=1/3; expected[tail]=2/3; expected /= 1+101e-12
    np.testing.assert_allclose(law, expected, atol=1e-12, rtol=0)
    assert b.log_prob('renewal', [previous], [30], [following])[0] == pytest.approx(math.log(expected[tail]), abs=1e-12)
