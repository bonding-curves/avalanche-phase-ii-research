"""Synthetic whole-unit adapter controls and independent expanded-rank references."""

import json
from itertools import product

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from avalanche_research.analysis import m2_associations as m
from avalanche_research.analysis.rank_associations import _point


def design(n=32, family="ramp", yield_pp=5.0, offset=0, points=None):
    """Complete synthetic Saltelli metadata, with independent parent key labels."""
    inputs = m.FAMILY_INPUTS[family]
    d = len(inputs)
    if points is None:
        points = stats.qmc.Sobol(2 * d, scramble=True, seed=37).random_base2(
            int(np.log2(n))
        )
    n = len(points)
    a, b = points[:, :d], points[:, d:]
    records = []
    for block in ("A", "B", "AB", "BA"):
        for j in range(d) if block in ("AB", "BA") else [None]:
            for i in range(n):
                own = a[i] if block in ("A", "AB") else b[i]
                unit = own.copy()
                if j is not None:
                    unit[j] = (b if block == "AB" else a)[i, j]
                key = offset + i + (0 if block in ("A", "AB") else n)
                physical = {
                    name: m.BOUNDS[name][0]
                    + float(u) * (m.BOUNDS[name][1] - m.BOUNDS[name][0])
                    for name, u in zip(inputs, unit)
                }
                records.append(
                    {
                        "index": offset + len(records),
                        "family": family,
                        "yield_pp": yield_pp,
                        "block": block,
                        "i": i,
                        "j": None if j is None else j + 1,
                        **{
                            f"u{q + 1}": float(unit[q]) if q < d else np.nan
                            for q in range(3)
                        },
                        "baseline": offset + 100000 + len(records),
                        "seed": key + 1,
                        "draw": key,
                        **physical,
                        "y": unit[0] + 2 * unit[1] + unit[-1] * unit[0],
                        "tied": int(unit[0] * 4),
                        "horizon_days": 365,
                    }
                )
    return pd.DataFrame(records)


def draws(n, replicates=24):
    return np.random.default_rng(811).integers(0, n, size=(replicates, n))


def run(table, *, reps=24, measures=("y",), ix=None, **kwargs):
    mapping = {} if ix is None else ix
    if ix is None:
        for (f, y), scope in table.groupby(["family", "yield_pp"]):
            mapping[f, float(y)] = draws(int((scope.block == "A").sum()), reps)
    return m.analyze_associations(
        table,
        measures=measures,
        bootstrap_indices=mapping,
        bootstrap_replicates=reps,
        **kwargs,
    )


def test_weighted_batch_matches_explicit_expansion_with_ties_and_large_integers():
    rng = np.random.default_rng(13)
    table = pd.DataFrame(
        {
            "x": rng.integers(0, 5, 40),
            "z": rng.integers(0, 9, 40),
            "huge": np.arange(40, dtype=np.int64) + 2**60,
            "y": rng.integers(-3, 8, 40),
            "other": rng.normal(size=40),
        }
    )
    specs = [m._rank_spec(table[c].to_numpy()) for c in table]
    counts = rng.integers(0, 4, size=(5, 40))
    result = m._batch(specs, counts, 3, ("spearman", "prcc"))
    for b, weights in enumerate(counts):
        expanded = table.iloc[np.repeat(np.arange(len(table)), weights)]
        for method in ("spearman", "prcc"):
            for j, name in enumerate(("x", "z", "huge")):
                for k, measure in enumerate(("y", "other")):
                    expected = _point(
                        expanded, ("x", "z", "huge"), measure, name, method
                    )
                    assert expected["status"] == "assessable"
                    assert result[method][1][b, j, k] == ""
                    assert result[method][0][b, j, k] == pytest.approx(
                        expected["coefficient"], abs=2e-13
                    )


def test_full_adapter_point_and_whole_base_interval_match_existing_kernel():
    table = design(32)
    ix = draws(32)
    output, meta = run(table, ix={("ramp", 5.0): ix}, pooled=False)
    full = output.query("renewal_band == 'all' and entry_band == 'all'")
    a = table.query("block == 'A'").sort_values("i")
    b = table.query("block == 'B'").sort_values("i")
    inputs = m.FAMILY_INPUTS["ramp"]
    for row in full.itertuples():
        expected = _point(pd.concat([a, b]), inputs, row.measure, row.input, row.method)
        assert row.coefficient == pytest.approx(expected["coefficient"], abs=2e-13)
        samples = [
            _point(
                pd.concat([a.iloc[v], b.iloc[v]]),
                inputs,
                row.measure,
                row.input,
                row.method,
            )["coefficient"]
            for v in ix
        ]
        assert [row.ci_low, row.ci_high] == pytest.approx(
            np.quantile(samples, [0.025, 0.975]), abs=2e-13
        )
    assert len(output) == 10 * 3 * 2
    assert meta["scopes"][0]["bootstrap_indices_sha256"] == m._digest(ix)
    assert output.pvalue.isna().all() and output.starred.isna().all()


def test_nine_bands_exact_edges_empty_cells_and_invalid_draws_stay_visible():
    table = design(8, family="before")
    ab = table.block.isin(["A", "B"])
    r = np.array(
        [
            0.0,
            np.nextafter(1 / 3, 0),
            1 / 3,
            np.nextafter(2 / 3, 0),
            2 / 3,
            1.0,
            0.1,
            0.9,
        ]
        * 2
    )
    table.loc[ab, "u1"] = r
    table.loc[ab, "renewal_response"] = r * 0.1
    table.loc[ab, "u2"] = 0.0
    table.loc[ab, "entry_response"] = 0.0
    table.loc[ab, "y"] = 1.0
    out, _ = run(table, pooled=False)
    assert len(out) == 10 * 2 * 2
    members = out.query("method=='spearman' and input=='renewal_response'").set_index(
        ["renewal_band", "entry_band"]
    )
    assert members.loc[("low", "low"), "rows"] == 6
    assert members.loc[("middle", "low"), "rows"] == 4
    assert members.loc[("high", "low"), "rows"] == 6
    assert members.loc[("low", "middle"), "rows"] == 0
    assert out.status.eq("unassessable").all()
    assert out.ci_low.isna().all()


def test_pooled_spearman_is_separate_and_stratifies_yield_draws():
    table = pd.concat(
        [design(16), design(16, yield_pp=10.0, offset=1000)], ignore_index=True
    )
    original = table.copy(deep=True)
    out, _ = run(table)
    pooled = out.loc[out.yield_pp == "pooled"]
    assert set(pooled.method) == {"spearman"}
    assert set(pooled.renewal_band) == {"all"}
    assert set(out.loc[out.yield_pp != "pooled", "yield_pp"]) == {5.0, 10.0}
    pd.testing.assert_frame_equal(table, original)
    shuffled, _ = run(table.sample(frac=1, random_state=12))
    pd.testing.assert_frame_equal(out, shuffled)


def test_huge_integer_measure_ranks_preserve_adjacent_values():
    table = design(16, family="before")
    table["huge"] = np.arange(len(table), dtype=np.int64) + 2**60
    out, _ = run(table, measures=("huge",), pooled=False)
    rows = table.loc[table.block.isin(["A", "B"])]
    row = out.query(
        "renewal_band=='all' and input=='renewal_response' and method=='spearman'"
    ).iloc[0]
    expected = stats.pearsonr(
        stats.rankdata(rows.renewal_response), stats.rankdata(rows.huge)
    ).statistic
    assert row.coefficient == pytest.approx(expected)


@pytest.mark.parametrize(
    "mutation",
    [
        "mixed_horizon",
        "physical",
        "key",
        "missing_base",
        "bool_measure",
        "missing_value",
    ],
)
def test_structural_or_missing_mutations_refuse(mutation):
    table = design(16)
    if mutation == "mixed_horizon":
        table.loc[0, "horizon_days"] = 180
    elif mutation == "physical":
        table.loc[0, "renewal_response"] += 0.001
    elif mutation == "key":
        table.loc[1, "seed"] = table.loc[0, "seed"]
    elif mutation == "missing_base":
        table = table.drop(0)
    elif mutation == "bool_measure":
        table["y"] = True
    else:
        table.loc[0, "y"] = np.nan
    with pytest.raises(m.ContractError):
        run(table)


def test_bootstrap_positions_are_explicit_and_strict():
    table = design(8)
    for ix in (
        {},
        {("ramp", 5.0): np.zeros((24, 8), dtype=bool)},
        {("ramp", 5.0): np.full((24, 8), 8, dtype=int)},
        {("ramp", 5.0): np.zeros((23, 8), dtype=int)},
    ):
        with pytest.raises(m.ContractError):
            run(table, ix=ix)


def test_rank_deficiency_and_exact_residual_relation_are_unassessable():
    table = pd.DataFrame(
        {"x": np.arange(10), "z": np.arange(10), "w": np.arange(10), "y": np.arange(10)}
    )
    result = m._batch(
        [m._rank_spec(table[c]) for c in table], np.ones((1, 10)), 3, ("prcc",)
    )
    assert (result["prcc"][1] == "rank_deficient_controls").all()
    assert np.isnan(result["prcc"][0]).all()
    two = m._batch(
        [m._rank_spec(table[c]) for c in ("x", "z", "y")],
        np.ones((1, 10)),
        2,
        ("prcc",),
    )
    assert (two["prcc"][1] == "unresolved_parameter_residual").all()


def test_bh_actual_pvalue_reference_and_undefined_slot_count():
    p = np.array([0.01, 0.04, 1.0])
    np.testing.assert_allclose(
        m.benjamini_hochberg(
            p, method="prospectively qualified fixture", qualified=True
        ),
        [0.03, 0.06, 1.0],
    )
    table = design(32, family="before")
    table["constant"] = 7.0
    out, meta = run(
        table,
        measures=("y", "constant"),
        pooled=False,
        pvalue_method=m.PERCENTILE_INVERSION,
    )
    full = out.query("renewal_band=='all'")
    finite = np.isfinite(full.pvalue)
    expected = stats.false_discovery_control(
        np.where(finite, full.pvalue, 1.0), method="bh"
    )
    np.testing.assert_allclose(full.loc[finite, "adjusted_p"], expected[finite])
    assert full.loc[~finite, "adjusted_p"].isna().all()
    assert full.loc[~finite, "starred"].isna().all()
    assert full.loc[~finite, "bh_nonreject_slot"].all()
    assert meta["BH_matrices"][0]["relationships"] == 4


def test_percentile_inversion_uses_all_ordered_tails_and_inclusive_zero_ties():
    table = design(16, family="before")
    ix = draws(16, 1000)
    out, _ = run(
        table,
        reps=1000,
        ix={("before", 5.0): ix},
        pooled=False,
        pvalue_method=m.PERCENTILE_INVERSION,
    )
    row = out.query(
        "renewal_band=='all' and method=='spearman' and input=='renewal_response'"
    ).iloc[0]
    a, b = (table.loc[table.block == role].sort_values("i") for role in ("A", "B"))
    samples = np.array(
        [
            stats.spearmanr(
                pd.concat([a.iloc[v], b.iloc[v]]).renewal_response,
                pd.concat([a.iloc[v], b.iloc[v]]).y,
            ).statistic
            for v in ix
        ]
    )
    expected = min(
        1.0, 2 * (1 + min((samples <= 0).sum(), (samples >= 0).sum())) / 1001
    )
    assert row.pvalue == expected
    # An exactly monotone relationship has the conservative 2/(B+1) floor.
    table["y"] = table.renewal_response
    monotone, _ = run(
        table,
        reps=1000,
        ix={("before", 5.0): ix},
        pooled=False,
        pvalue_method=m.PERCENTILE_INVERSION,
    )
    assert (
        monotone.query(
            "renewal_band=='all' and method=='spearman' and input=='renewal_response'"
        )
        .iloc[0]
        .pvalue
        == 2 / 1001
    )
    points = np.array(list(product((0.0, 1.0), repeat=4)))
    table = design(family="before", points=points)
    table["y"] = table.entry_response
    identity = np.tile(np.arange(16), (24, 1))
    zero, _ = run(
        table,
        ix={("before", 5.0): identity},
        pooled=False,
        pvalue_method=m.PERCENTILE_INVERSION,
    )
    assert (
        zero.query(
            "renewal_band=='all' and method=='spearman' and input=='renewal_response'"
        )
        .iloc[0]
        .pvalue
        == 1.0
    )


def test_invalid_bootstrap_never_discards_draw_for_interval_or_pvalue():
    table = design(16, family="before")
    table.loc[(table.i == 0) & table.block.isin(["A", "B"]), "y"] = 0.0
    ix = draws(16)
    ix[0] = 0
    out, _ = run(
        table,
        ix={("before", 5.0): ix},
        pooled=False,
        pvalue_method=m.PERCENTILE_INVERSION,
    )
    full = out.query("renewal_band=='all'")
    assert full.pvalue.isna().all() and full.ci_low.isna().all()
    assert (full.bootstrap_valid < 24).all()
    assert full.bootstrap_invalid_reasons.map(bool).all()


def test_single_unit_cell_has_point_but_no_interval_or_pvalue():
    points = np.array([[0.1, 0.1, 0.2, 0.2], [0.6, 0.6, 0.8, 0.8]])
    table = design(family="before", points=points)
    identity = np.tile(np.arange(2), (24, 1))
    out, _ = run(
        table,
        ix={("before", 5.0): identity},
        pooled=False,
        pvalue_method=m.PERCENTILE_INVERSION,
    )
    row = out.query(
        "renewal_band=='low' and entry_band=='low' and method=='spearman'"
    ).iloc[0]
    assert row.status == "assessable" and row.independent_units == 1
    assert np.isnan(row.ci_low) and np.isnan(row.pvalue)


@pytest.mark.parametrize("p", [[0.2, np.nan], [-0.1], [1.1], [True], []])
def test_bh_refuses_incomplete_nonpvalue_inputs(p):
    with pytest.raises(m.ContractError):
        m.benjamini_hochberg(p, method="fixed", qualified=True)


def test_bh_requires_declared_qualified_method_and_no_global_rng_changes():
    with pytest.raises(m.ContractError):
        m.benjamini_hochberg([0.1], method="fixed")
    with pytest.raises(m.ContractError):
        run(design(8), pvalue_method="CI excludes zero")
    before = np.random.get_state()
    run(design(8), pooled=False)
    after = np.random.get_state()
    assert before[0] == after[0]
    np.testing.assert_array_equal(before[1], after[1])
    assert before[2:] == after[2:]


@pytest.mark.parametrize("horizon_present", [False, True])
def test_metadata_is_strict_json_with_or_without_external_horizon(horizon_present):
    table = design(8)
    if not horizon_present:
        table = table.drop(columns="horizon_days")
    _, meta = run(table, pooled=False)
    json.dumps(meta, allow_nan=False)


def test_nullable_native_identities_and_absent_baseline_ratios_are_accepted():
    table = design(8)
    table["baseline"] = table.baseline.astype(object)
    table["j"] = pd.Series(
        [None if pd.isna(v) else int(v) for v in table.j], dtype=object
    )
    original, _ = run(table, pooled=False)
    baseline = table.iloc[[0]].copy()
    baseline["index"] += 1000000
    baseline["block"] = "baseline"
    baseline["baseline"] = None
    baseline["y"] = np.nan
    actual, _ = run(pd.concat([table, baseline], ignore_index=True), pooled=False)
    pd.testing.assert_frame_equal(actual, original)
