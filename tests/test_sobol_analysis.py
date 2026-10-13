"""Small synthetic controls only, no stochastic model invocation or real design."""

import hashlib
from dataclasses import FrozenInstanceError, replace
from itertools import product

import numpy as np
import pytest

from avalanche_research.analysis import sobol as s

H = "1" * 64


def coordinates(a, b):
    ab = np.repeat(a[:, None, :], a.shape[1], axis=1)
    for j in range(a.shape[1]):
        ab[:, j, j] = b[:, j]
    return ab


def packet(fun=lambda x: x[:, 0] + 2 * x[:, 1], d=3, noise=False):
    # Full finite enumeration provides exact independent Rademacher A/B oracle.
    pairs = np.asarray(list(product((-1.0, 1.0), repeat=2 * d)), dtype=np.float64)
    a = pairs[:, :d]
    b = pairs[:, d:]
    ab = coordinates(a, b)
    if noise:
        # Independent A/B noise axis is enumerated, without parameter-noise hybrids.
        expanded = np.asarray(list(product(range(len(a)), (-1.0, 1.0), (-1.0, 1.0))))
        ix = expanded[:, 0].astype(int)
        a = a[ix]
        b = b[ix]
        ab = ab[ix]
        wa = expanded[:, 1]
        wb = expanded[:, 2]
        ya = (a[:, 0] * wa)[:, None]
        yb = (b[:, 0] * wb)[:, None]
        yab = (ab[:, :, 0] * wa[:, None])[:, :, None]
    else:
        ya = np.asarray(fun(a))
        yb = np.asarray(fun(b))
        yab = np.stack([fun(ab[:, j, :]) for j in range(d)], axis=1)
        if ya.ndim == 1:
            ya = ya[:, None]
            yb = yb[:, None]
            yab = yab[:, :, None]
    n = len(a)
    k = ya.shape[1]
    names = tuple("x" + str(j) for j in range(d))
    kpis = tuple("toy" + str(j) for j in range(k))
    ids = tuple(f"base{i:04d}" for i in range(n))
    status = np.full((n, d + 2), "success")
    if noise:
        na = tuple("A-noise" + str(i) for i in range(n))
        nb = tuple("B-noise" + str(i) for i in range(n))
        coupling = s.Coupling(
            "independent-ab-noise-a-hybrids", H, na, nb, tuple((x,) * d for x in na)
        )
    else:
        coupling = s.Coupling("deterministic", H)
    r = s.Receipt(
        "structured-first-v1",
        names,
        kpis,
        ids,
        s.design_hash(a, b, ab, names, ids),
        s.outputs_hash(ya, yb, yab, status, kpis, ids),
        H,
        H,
        H,
        H,
        (("family", "synthetic"), ("response", "fixture")),
        coupling,
    )
    return [a, b, ab, ya, yb, yab, status, r]


def run(p, **kw):
    return s.analyze(
        *p, n_bootstrap=kw.pop("n_bootstrap", 40), seed=kw.pop("seed", 0), **kw
    )


def point(r, key):
    return np.array([x[key] for x in r["rows"]])


def repin(p):
    p = list(p)
    r = p[-1]
    p[-1] = replace(
        r,
        design_sha256=s.design_hash(*p[:3], r.input_names, r.base_ids),
        outputs_sha256=s.outputs_hash(*p[3:7], r.kpi_names, r.base_ids),
    )
    return p


def test_additive_inactive_exact_analytic():
    r = run(packet())
    np.testing.assert_allclose(point(r, "first"), [0.2, 0.8, 0], atol=1e-15)
    np.testing.assert_allclose(point(r, "total"), [0.2, 0.8, 0], atol=1e-15)
    assert all(x["ci_status"] == "assessable" for x in r["rows"])


def test_interaction_exact_analytic():
    r = run(packet(lambda x: x[:, 0] * x[:, 1]))
    np.testing.assert_allclose(point(r, "first"), [0, 0, 0], atol=1e-15)
    np.testing.assert_allclose(point(r, "total"), [1, 1, 0], atol=1e-15)


def test_single_parameter_and_two_kpis():
    r = run(packet(lambda x: np.column_stack((x[:, 0], -2 * x[:, 0])), d=1))
    np.testing.assert_allclose(point(r, "first"), [1, 1])
    np.testing.assert_allclose(point(r, "total"), [1, 1])
    assert r["n_kpis"] == 2


def test_joint_noise_exact_oracle_not_common_ab_bias():
    r = run(packet(d=1, noise=True))
    np.testing.assert_allclose(point(r, "first"), [0], atol=1e-15)
    np.testing.assert_allclose(point(r, "total"), [1], atol=1e-15)
    assert r["scientific_acceptance"] is False


def test_shift_scale_invariance():
    p = packet()
    q = list(p)
    for ix in (3, 4, 5):
        q[ix] = -8 * p[ix] + 32
    q = repin(q)
    for key in ("first", "total"):
        np.testing.assert_allclose(point(run(p), key), point(run(q), key), atol=1e-15)


def test_seed_zero_reproducible_and_different_seed_changes_intervals():
    p = packet()
    a = run(p, seed=0)
    b = run(p, seed=0)
    c = run(p, seed=1)
    assert a == b and a["bootstrap_indices_sha256"] != c["bootstrap_indices_sha256"]
    assert a["rows"][0]["first_ci"] != c["rows"][0]["first_ci"]


def test_joint_reorder_identical_after_repin():
    p = packet()
    ix = np.arange(len(p[0]))[::-1]
    q = [x[ix] if i < 7 else x for i, x in enumerate(p)]
    q[-1] = replace(p[-1], base_ids=tuple(p[-1].base_ids[i] for i in ix))
    q = repin(q)
    a = run(p)
    b = run(q)
    for key in (
        "rows",
        "bootstrap_base_ids",
        "bootstrap_indices_sha256",
        "invalid_draws",
    ):
        assert a[key] == b[key]


@pytest.mark.parametrize("ix", [0, 1, 2, 3, 4, 5])
def test_nonfinite_refuses(ix):
    p = packet()
    p[ix] = p[ix].copy()
    p[ix].flat[0] = np.inf
    with pytest.raises(s.ContractError, match="finite binary64"):
        run(p)


@pytest.mark.parametrize("ix", [0, 1, 2, 3, 4, 5])
def test_incomplete_shapes_refuse(ix):
    p = packet()
    p[ix] = p[ix][:-1]
    with pytest.raises(s.ContractError, match="shapes"):
        run(p)


@pytest.mark.parametrize("bad", ["failed", "missing", "cancelled"])
def test_failed_missing_rows_never_drop(bad):
    p = packet()
    p[6] = p[6].astype("U20")
    p[6][0, 1] = bad
    with pytest.raises(s.ContractError, match="every A/AB/B"):
        run(p)


def test_missing_status_row_refuses():
    p = packet()
    p[6] = p[6][:-1]
    with pytest.raises(s.ContractError, match="every A/AB/B"):
        run(p)


def test_constant_refuses_not_zero_indices():
    p = packet(lambda x: np.ones(len(x)))
    with pytest.raises(s.ContractError, match="zero variance"):
        run(p)


def test_incompatible_grid_and_wrong_hybrid_column_refuse_even_repin():
    p = packet()
    p[2] = np.repeat(p[0][:, None, :], 3, axis=1)
    p = repin(p)
    with pytest.raises(s.ContractError, match="AB coordinates/order"):
        run(p)
    p = packet()
    p[2] = p[2][:, ::-1, :].copy()
    p = repin(p)
    with pytest.raises(s.ContractError, match="AB coordinates/order"):
        run(p)


def test_flat_second_order_layout_refused():
    p = packet()
    p[-1] = replace(p[-1], abi="saltelli-second-order")
    with pytest.raises(s.ContractError, match="only explicit first-order"):
        run(p)
    p = packet()
    p[5] = p[5].reshape(-1)
    with pytest.raises(s.ContractError, match="shapes"):
        run(p)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("input_names", ()),
        ("input_names", ("x", "x", "z")),
        ("input_names", ("x", " ", "z")),
        ("base_ids", ("a", "a")),
        ("kpi_names", ()),
        ("input_names", ["x", "y", "z"]),
        ("scope", (("family", "x"), ("family", "y"))),
        ("scope", []),
    ],
)
def test_names_scope_immutable_unique(field, bad):
    p = packet()
    p[-1] = replace(p[-1], **{field: bad})
    with pytest.raises(s.ContractError):
        run(p)


@pytest.mark.parametrize("seed", [True, None, -1, 1.2, 2**64])
def test_invalid_seed(seed):
    with pytest.raises(s.ContractError, match="seed"):
        run(packet(), seed=seed)


@pytest.mark.parametrize("n", [True, 0, 1, -1, 2.5])
def test_invalid_bootstrap(n):
    with pytest.raises(s.ContractError, match="n_bootstrap"):
        run(packet(), n_bootstrap=n)


@pytest.mark.parametrize("v", [True, 0.0, 1.0, np.nan, np.inf, "0.95"])
def test_invalid_confidence(v):
    with pytest.raises(s.ContractError, match="confidence"):
        run(packet(), confidence=v)


def test_pin_mutations_refuse():
    for ix in (0, 3):
        p = packet()
        p[ix] = p[ix].copy()
        p[ix].flat[0] += 0.1
        with pytest.raises(s.ContractError):
            run(p)
    p = packet()
    p[-1] = replace(p[-1], model_sha256="broken")
    with pytest.raises(s.ContractError, match="SHA256"):
        run(p)


def test_noise_receipt_structural_refusals():
    p = packet(d=1, noise=True)
    c = p[-1].coupling
    for bad in (
        replace(c, mode="shared-base-noise"),
        replace(c, noise_b=c.noise_a),
        replace(c, noise_ab=tuple((x,) for x in c.noise_b)),
        replace(c, noise_a=list(c.noise_a)),
    ):
        q = list(p)
        q[-1] = replace(p[-1], coupling=bad)
        with pytest.raises(s.ContractError):
            run(q)
    p = packet()
    p[-1] = replace(p[-1], coupling=s.Coupling("deterministic", H, noise_a=[]))
    with pytest.raises(s.ContractError, match="immutable"):
        run(p)


def test_receipt_cannot_assign():
    p = packet()
    with pytest.raises(FrozenInstanceError):
        p[-1].abi = "other"


def test_invalid_bootstrap_draws_explicit_no_selected_interval():
    # Only base rows with +/-1 identical A=B: point variance positive; drawing one
    # row twice makes denominator zero. Such draws must make CI unassessable.
    a = np.array([[-1.0], [1.0]])
    p = packet(lambda x: x[:, 0], d=1)
    p[:3] = [a, a.copy(), coordinates(a, a)]
    p[3:6] = [a.copy(), a.copy(), a[:, None, :].copy()]
    p[6] = np.full((2, 3), "success")
    p[-1] = replace(p[-1], base_ids=("a", "b"))
    p = repin(p)
    r = run(p, n_bootstrap=40)
    assert r["rows"][0]["bootstrap_invalid"] > 0 and r["invalid_draws"]
    assert (
        r["rows"][0]["ci_status"] == "unassessable_invalid_bootstrap_draw"
        and r["rows"][0]["first_ci"] is None
        and r["rows"][0]["total_ci"] is None
    )


def test_finite_estimates_are_not_clipped():
    p = packet(lambda x: x[:, 0], d=1)
    p[5] = 3 * p[5]
    p = repin(p)
    r = run(p)
    assert r["rows"][0]["first"] > 1 and r["rows"][0]["total"] > 1
    p = packet(lambda x: x[:, 0], d=1)
    p[5] = -p[5]
    p = repin(p)
    r = run(p)
    assert r["rows"][0]["first"] < 0


def test_multi_kpi_complete_blocks_shared_rng_oracle():
    p = packet(lambda x: np.column_stack((x[:, 0] + 2 * x[:, 1], x[:, 0] * x[:, 1])))
    r = run(p, n_bootstrap=20, seed=9)
    rng = np.random.Generator(np.random.PCG64(9))
    h = hashlib.sha256()
    for _ in range(20):
        h.update(rng.integers(0, len(p[0]), size=len(p[0])).astype("<i8").tobytes())
    assert r["bootstrap_indices_sha256"] == h.hexdigest()
    # Same full base draw applies to every KPI and every parameter. Independently
    # evaluate the first KPI's statistic on those draws and compare percentile CI.
    rng = np.random.Generator(np.random.PCG64(9))
    vals = []
    for _ in range(20):
        ix = rng.integers(0, len(p[0]), size=len(p[0]))
        a = p[3][ix, 0]
        b = p[4][ix, 0]
        ab = p[5][ix, 0, 0]
        v = np.var(np.r_[a, b])
        m = np.mean(np.r_[a, b])
        vals.append(np.mean((b - m) * (ab - a)) / v)
    np.testing.assert_allclose(
        r["rows"][0]["first_ci"], np.quantile(vals, [0.025, 0.975]), atol=1e-14
    )


def test_bool_and_numeric_strings_not_binary64():
    for dtype in (bool, "U10", np.int64):
        p = packet()
        p[3] = p[3].astype(dtype)
        with pytest.raises(s.ContractError, match="binary64"):
            run(p)


def test_one_basepoint_refuses():
    p = packet(lambda x: x[:, 0], d=1)
    p = [x[:1] if i < 7 else x for i, x in enumerate(p)]
    p[-1] = replace(p[-1], base_ids=("only",))
    p = repin(p)
    with pytest.raises(s.ContractError, match="N>=2"):
        run(p)


def test_mixed_bool_list_not_coerced_to_float():
    p = packet()
    p[3] = p[3].tolist()
    p[3][0][0] = True
    with pytest.raises(s.ContractError, match="explicit binary64 ndarray"):
        run(p)


@pytest.mark.parametrize("ix", range(6))
@pytest.mark.parametrize("mask_kind", ["one", "all"])
def test_masked_coordinate_or_output_refuses_before_original_pin_can_pass(
    ix, mask_kind
):
    p = packet()
    mask = np.zeros(p[ix].shape, dtype=bool)
    if mask_kind == "one":
        mask.flat[0] = True
    else:
        mask[:] = True
    p[ix] = np.ma.array(p[ix], mask=mask)
    # Backing bytes and original receipt are unchanged. The prior code stripped
    # this mask, passed those original pins and returned its unmasked result.
    with pytest.raises(s.ContractError, match="masked missing entries"):
        run(p)


@pytest.mark.parametrize("ix", range(6))
def test_masked_hash_inputs_refuse(ix):
    p = packet()
    mask = np.zeros(p[ix].shape, dtype=bool)
    mask.flat[0] = True
    p[ix] = np.ma.array(p[ix], mask=mask)
    r = p[-1]
    with pytest.raises(s.ContractError, match="masked missing entries"):
        if ix < 3:
            s.design_hash(*p[:3], r.input_names, r.base_ids)
        else:
            s.outputs_hash(*p[3:7], r.kpi_names, r.base_ids)


@pytest.mark.parametrize(
    "kind", ["one", "all", "nested-list", "nested-tuple", "object-array"]
)
def test_masked_statuses_refuse_analysis_and_hash_before_coercion(kind):
    p = packet()
    status = p[6]
    if kind in ("one", "all"):
        mask = np.zeros(status.shape, dtype=bool)
        if kind == "one":
            mask.flat[0] = True
        else:
            mask[:] = True
        status = np.ma.array(status, mask=mask)
    elif kind in ("nested-list", "nested-tuple"):
        status = status.tolist()
        status[0][0] = np.ma.masked
        if kind == "nested-tuple":
            status = tuple(tuple(row) for row in status)
    else:
        status = status.astype(object)
        status[0, 0] = np.ma.masked
    p[6] = status
    r = p[-1]
    with pytest.raises(s.ContractError, match="masked missing entries"):
        run(p)
    with pytest.raises(s.ContractError, match="masked missing entries"):
        s.outputs_hash(*p[3:7], r.kpi_names, r.base_ids)


@pytest.mark.parametrize("mask_kind", ["false", "nomask"])
def test_complete_masks_deliberately_match_unmasked_result_and_pins(mask_kind):
    p = packet()
    expected = run(p)
    q = list(p)
    for ix in range(7):
        q[ix] = np.ma.array(p[ix], mask=False if mask_kind == "false" else np.ma.nomask)
    assert run(q) == expected
    assert (
        s.design_hash(*q[:3], q[-1].input_names, q[-1].base_ids) == q[-1].design_sha256
    )
    assert (
        s.outputs_hash(*q[3:7], q[-1].kpi_names, q[-1].base_ids) == q[-1].outputs_sha256
    )


def test_nested_complete_masked_status_rows_deliberately_accepted():
    p = packet()
    expected = run(p)
    p[6] = [np.ma.array(row, mask=False) for row in p[6]]
    assert run(p) == expected
