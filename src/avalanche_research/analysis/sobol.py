"""MM3 synthetic structured first/total Sobol calculator. No I/O or design generation.

Binary64 arrays only. AB[i,j,:] replaces input j of A[i,:] by B[i,j].
Output hybrid yAB[i,j,k] must belong to that exact evaluation. Coordinate
checks and hash matches do not prove output provenance, independent draws,
input independence, distribution validity or a scientific design acceptance.
"""

import hashlib
import json
from dataclasses import dataclass

import numpy as np


class ContractError(ValueError):
    """Incomplete, incompatible or undefined analysis input."""


@dataclass(frozen=True)
class Coupling:
    mode: str  # deterministic | independent-ab-noise-a-hybrids
    provenance_sha256: str
    noise_a: tuple[str, ...] = ()
    noise_b: tuple[str, ...] = ()
    noise_ab: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class Receipt:
    abi: str
    input_names: tuple[str, ...]
    kpi_names: tuple[str, ...]
    base_ids: tuple[str, ...]
    design_sha256: str
    outputs_sha256: str
    model_sha256: str
    data_sha256: str
    kpi_sha256: str
    sampling_provenance_sha256: str
    scope: tuple[tuple[str, str], ...]
    coupling: Coupling


def _names(value, label):
    if (
        type(value) is not tuple
        or not value
        or any(type(x) is not str or not x.strip() for x in value)
        or len(set(value)) != len(value)
    ):
        raise ContractError(
            label + " must be a nonempty tuple of unique nonempty strings"
        )


def _reject_masked(value, label):
    """Inspect missingness before NumPy can strip/stringify masks.

    All-false/nomask arrays deliberately count as complete. Status lists/tuples
    and object arrays are inspected recursively before their accepted coercion.
    """
    if np.ma.isMaskedArray(value) and np.any(np.ma.getmaskarray(value)):
        raise ContractError(label + " contains masked missing entries")
    if isinstance(value, (list, tuple)):
        for item in value:
            _reject_masked(item, label)
    elif isinstance(value, np.ndarray) and value.dtype.kind == "O":
        for item in value.flat:
            _reject_masked(item, label)


def _array(value, label):
    _reject_masked(value, label)
    if not isinstance(value, np.ndarray):
        raise ContractError(
            label + " must be an explicit binary64 ndarray, without implicit coercion"
        )
    a = np.asarray(value)
    if a.dtype != np.dtype("float64") or not np.isfinite(a).all():
        raise ContractError(
            label + " must be finite binary64, without missing/bool/object values"
        )
    return np.array(a, copy=True, order="C")


def _sha(value, label):
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ContractError(label + " must be a lowercase SHA256")


def _digest(metadata, arrays):
    h = hashlib.sha256(
        json.dumps(
            metadata, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )
    for a in arrays:
        h.update(json.dumps(a.shape).encode())
        h.update(np.asarray(a, dtype="<f8", order="C").tobytes())
    return h.hexdigest()


def design_hash(a, b, ab, input_names, base_ids):
    """Pin normalized binary64 structured coordinates and declared row/column order."""
    return _digest([input_names, base_ids], [_array(x, "design") for x in (a, b, ab)])


def outputs_hash(a, b, ab, statuses, kpi_names, base_ids):
    """Pin all paired outputs plus statuses; this is integrity, not provenance proof."""
    _reject_masked(statuses, "statuses")
    return _digest(
        [kpi_names, base_ids, np.asarray(statuses).tolist()],
        [_array(x, "outputs") for x in (a, b, ab)],
    )


def _validate(a, b, ab, ya, yb, yab, statuses, r):
    if type(r) is not Receipt or type(r.coupling) is not Coupling:
        raise ContractError("frozen Receipt and Coupling required")
    if r.abi != "structured-first-v1":
        raise ContractError(
            "only explicit first-order structured ABI accepted, no flat/BA/second-order layout"
        )
    for value, label in (
        (r.input_names, "input_names"),
        (r.kpi_names, "kpi_names"),
        (r.base_ids, "base_ids"),
    ):
        _names(value, label)
    if (
        type(r.scope) is not tuple
        or not r.scope
        or any(
            type(x) is not tuple
            or len(x) != 2
            or any(type(y) is not str or not y.strip() for y in x)
            for x in r.scope
        )
        or len({x[0] for x in r.scope}) != len(r.scope)
    ):
        raise ContractError("immutable nonempty unique scope key/value tuples required")
    for name in (
        "design_sha256",
        "outputs_sha256",
        "model_sha256",
        "data_sha256",
        "kpi_sha256",
        "sampling_provenance_sha256",
    ):
        _sha(getattr(r, name), name)
    _sha(r.coupling.provenance_sha256, "coupling provenance")
    a, b, ab, ya, yb, yab = [
        _array(x, label)
        for x, label in zip(
            (a, b, ab, ya, yb, yab), ("A", "B", "AB", "yA", "yB", "yAB")
        )
    ]
    n, d, k = len(r.base_ids), len(r.input_names), len(r.kpi_names)
    if n < 2 or a.shape != (n, d) or b.shape != (n, d) or ab.shape != (n, d, d):
        raise ContractError("design shapes must be A/B (N,D), AB (N,D,D), N>=2")
    if ya.shape != (n, k) or yb.shape != (n, k) or yab.shape != (n, d, k):
        raise ContractError("complete output shapes yA/yB (N,K), yAB (N,D,K) required")
    _reject_masked(statuses, "statuses")
    st = np.asarray(statuses)
    if (
        st.shape != (n, d + 2)
        or st.dtype.kind not in "US"
        or not np.all(st == "success")
    ):
        raise ContractError(
            "every A/AB/B evaluation must explicitly be success; no failed/missing row drops"
        )
    for j in range(d):
        expected = a.copy()
        expected[:, j] = b[:, j]
        if not np.array_equal(ab[:, j, :], expected):
            raise ContractError(
                "AB coordinates/order inconsistent with A replacing column j from B"
            )
    if design_hash(a, b, ab, r.input_names, r.base_ids) != r.design_sha256:
        raise ContractError("design pin mismatch")
    if outputs_hash(ya, yb, yab, st, r.kpi_names, r.base_ids) != r.outputs_sha256:
        raise ContractError("outputs/status pin mismatch")
    c = r.coupling
    if any(type(x) is not tuple for x in (c.noise_a, c.noise_b, c.noise_ab)):
        raise ContractError("noise identities must be immutable tuples")
    if c.mode == "deterministic":
        if c.noise_a or c.noise_b or c.noise_ab:
            raise ContractError("deterministic mode requires empty noise identities")
    elif c.mode == "independent-ab-noise-a-hybrids":
        _names(c.noise_a, "noise_a")
        _names(c.noise_b, "noise_b")
        if (
            len(c.noise_a) != n
            or len(c.noise_b) != n
            or set(c.noise_a) & set(c.noise_b)
        ):
            raise ContractError(
                "A/B noise identities must be distinct, unique and complete"
            )
        if (
            type(c.noise_ab) is not tuple
            or len(c.noise_ab) != n
            or any(
                type(row) is not tuple or row != (c.noise_a[i],) * d
                for i, row in enumerate(c.noise_ab)
            )
        ):
            raise ContractError("every AB hybrid must retain its A base noise identity")
    else:
        raise ContractError(
            "unsupported stochastic estimand/coupling; shared A/B noise refused"
        )
    # Canonical base-ID order makes same-seed bootstrap insensitive to joint row reorder.
    order = np.argsort(np.asarray(r.base_ids), kind="stable")
    return ya[order], yb[order], yab[order], tuple(r.base_ids[i] for i in order)


def _indices(a, b, ab):
    """Pooled A/B ddof=0 variance, centered B Saltelli first and Jansen total.

    Scaling by max abs output avoids avoidable square overflow. Pooled A/B mean
    centering is recomputed for each bootstrap draw. No clipping or eps-to-zero.
    """
    scale = np.maximum.reduce(
        [
            np.max(np.abs(a), axis=0),
            np.max(np.abs(b), axis=0),
            np.max(np.abs(ab), axis=(0, 1)),
        ]
    )
    scale = np.where(scale == 0, 1.0, scale)
    a = a / scale
    b = b / scale
    ab = ab / scale
    center = np.mean(np.concatenate((a, b)), axis=0)
    a = a - center
    b = b - center
    ab = ab - center
    variance = np.var(np.concatenate((a, b)), axis=0, ddof=0)
    valid = np.isfinite(variance) & (variance > 0)
    first = np.full((ab.shape[1], a.shape[1]), np.nan)
    total = first.copy()
    with np.errstate(divide="ignore", invalid="ignore", over="ignore", under="ignore"):
        first[:, valid] = (
            np.mean(b[:, None, valid] * (ab[:, :, valid] - a[:, None, valid]), axis=0)
            / variance[valid]
        )
        total[:, valid] = (
            0.5
            * np.mean((a[:, None, valid] - ab[:, :, valid]) ** 2, axis=0)
            / variance[valid]
        )
    valid &= np.isfinite(first).all(axis=0) & np.isfinite(total).all(axis=0)
    return first, total, valid


def analyze(
    a,
    b,
    ab,
    ya,
    yb,
    yab,
    statuses,
    receipt,
    *,
    n_bootstrap=200,
    seed=0,
    confidence=0.95,
):
    """First/total indices and percentile base-block intervals per input/KPI.

    Resampling assumes independent/exchangeable complete base rows. Sobol QMC
    sequence dependence, repeated/shared seeds, clustered scenarios or dependent
    inputs require a separately justified uncertainty design. A tag/hash cannot
    establish those assumptions. One call is one declared response/variant scope.
    All KPI/hybrid values use the same resampled base indices. Any undefined draw
    makes that KPI's CI unassessable, with explicit counts; no draws silently drop.
    """
    if type(n_bootstrap) is not int or n_bootstrap < 2:
        raise ContractError("n_bootstrap must be an integer >=2, not bool")
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ContractError("seed must be an integer in [0,2**64), not bool")
    if (
        type(confidence) not in (int, float)
        or isinstance(confidence, bool)
        or not np.isfinite(confidence)
        or not 0 < confidence < 1
    ):
        raise ContractError("confidence must be finite and strictly between 0 and 1")
    a, b, ab, ids = _validate(a, b, ab, ya, yb, yab, statuses, receipt)
    first, total, valid = _indices(a, b, ab)
    if not valid.all():
        raise ContractError(
            "zero variance or numerically unassessable KPI: "
            + ", ".join(name for name, ok in zip(receipt.kpi_names, valid) if not ok)
        )
    rng = np.random.Generator(np.random.PCG64(seed))
    n = len(ids)
    d, k = first.shape
    fs = np.empty((n_bootstrap, d, k))
    ts = np.empty_like(fs)
    ok = np.empty((n_bootstrap, k), dtype=bool)
    draws_hash = hashlib.sha256()
    for z in range(n_bootstrap):
        ix = rng.integers(0, n, size=n)
        draws_hash.update(ix.astype("<i8").tobytes())
        fs[z], ts[z], ok[z] = _indices(a[ix], b[ix], ab[ix])
    rows = []
    alpha = (1 - float(confidence)) / 2
    for j, name in enumerate(receipt.input_names):
        for q, kpi in enumerate(receipt.kpi_names):
            assessable = bool(ok[:, q].all())
            rows.append(
                {
                    "input": name,
                    "kpi": kpi,
                    "first": float(first[j, q]),
                    "total": float(total[j, q]),
                    "ci_status": "assessable"
                    if assessable
                    else "unassessable_invalid_bootstrap_draw",
                    "first_ci": np.quantile(
                        fs[:, j, q], [alpha, 1 - alpha], method="linear"
                    ).tolist()
                    if assessable
                    else None,
                    "total_ci": np.quantile(
                        ts[:, j, q], [alpha, 1 - alpha], method="linear"
                    ).tolist()
                    if assessable
                    else None,
                    "bootstrap_valid": int(ok[:, q].sum()),
                    "bootstrap_invalid": int((~ok[:, q]).sum()),
                }
            )
    return {
        "rows": rows,
        "n_base": n,
        "n_inputs": d,
        "n_kpis": k,
        "n_bootstrap": n_bootstrap,
        "seed": seed,
        "confidence": float(confidence),
        "bootstrap_unit": "complete A/B/all-AB base row jointly across KPIs",
        "bootstrap_base_ids": ids,
        "bootstrap_indices_sha256": draws_hash.hexdigest(),
        "invalid_draws": [
            {
                "draw": i,
                "kpis": [name for name, v in zip(receipt.kpi_names, ok[i]) if not v],
            }
            for i in range(n_bootstrap)
            if not ok[i].all()
        ],
        "source_receipt_sha256": hashlib.sha256(
            json.dumps(
                receipt,
                default=lambda x: x.__dict__,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
        "design_sha256": receipt.design_sha256,
        "outputs_sha256": receipt.outputs_sha256,
        "scientific_acceptance": False,
        "interpretation": "Sampling uncertainty conditional on declared design and external dependence/provenance gates; not empirical forecast coverage.",
    }
