"""The Milestone 2 sweep design: every row, its labels, the table of parameter draws, and the sweep's design file.

    python scripts/m2_sweep_design.py <variant> <out dir>

``variant`` names a model variant of ``avalanche_research.model.variants``, such as ``v0.8.0`` or ``v0.8-a``. Every
row runs that variant with one parameter draw per trajectory: a release such as ``v0.8.0`` reads draws under its own
name, and any other variant is run by the registry name with ``u`` added (``v0.8-a u``). The script writes five files
to ``out dir``:

- ``rows.json``: a JSON list of 132,800 rows, 74,176 design rows then 58,624 baselines under the chain's rule, each
  holding only ``seed``, ``draw``, ``origin``, ``model``, ``mechanism``, ``renewal_response``, ``entry_response``,
  ``outside_yield_pp`` and ``fitted_outside_yield_pp``.
- ``labels.csv``: each row's family, outside yield, block, indices, unit-cube Sobol coordinates and baseline, by row
  index.
- ``draws.parquet``: the variant's parameter draws, one per noise key. A row's ``draw`` is its row of this table.
- ``design.json``: the design file for ``avalanche model sweep``, with the two files' SHA-256 hashes.
- ``README.md``: every count, hash, seed and choice.

The design starts every run at one origin, 2025-11-18, the last day before the held-back period, for 365 days. It
compares four reward families, each in force from the origin for the whole run:

| Family | Mechanism | Inputs swept |
| --- | --- | --- |
| ``ramp`` | ``ACP285Ramp`` activated at 16:00 UTC on the origin day, a 90-day ramp, target U(0.05, 0.10) | target, both responses |
| ``before`` | The rule before ACP-285: ``ACP285Ramp`` whose target is that rule's own minimum rate, 10% | both responses |
| ``tenure`` | ``TenureBoost``, full boost U(0, 0.2) | boost, both responses |
| ``quadratic`` | ``QuadraticReward``, exponent U(1, 3) | exponent, both responses |

The renewal and entry responses are each U(0, 0.1) per percentage point. Each family runs at outside yields of 3%, 5%,
7% and 10% a year, against the fitting window's level: the mean 3-month Treasury bill rate (FRED's DTB3) over the year
before 2025-11-19, read from the pinned bill run.

For each family and yield, a Saltelli design with second-order terms takes N = 512 rows of each of two matrices A and
B, the first and last k columns of 512 scrambled Sobol points in 2k dimensions, scrambled from the model's ``design``
stream under its own seed. It adds AB^(j), A with column j from B, and BA^(j), B with column j from A, for N(2k + 2)
rows. Each trajectory carries one noise key, a ``(seed, draw)`` pair: A_i and B_i get independent keys, AB_i^(j)
inherits A_i's and BA_i^(j) inherits B_i's, so the first-order and total indices are estimated over the noise rather
than mixed with it. Every distinct key has its own seed and its own draw.

Beyond the Saltelli rows, at each yield: 8 independent keys at each of the first 64 points of A, to estimate the
noise's total effect; both responses at zero for each family, on 64 keys shared across the families; the three stress
settings (renewal response 0.3, entry response 0.3, both 0.3) at each family's middle setting, on the same 64 keys; and
seven implementation controls on 64 keys of their own. Every design row then pairs with a baseline row, the same key,
responses and yields under ``ChainReward``, so the KPIs relative to the chain's rule are measured on the same noise.
The README lists each count and choice.

The script refuses to write unless the pins verify and the counts are exact. Run twice, it writes identical bytes.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ORIGIN = date(2025, 11, 18)
ACTIVATION = "2025-11-18T16:00:00+00:00"
RAMP_DAYS = 90
RULE_BEFORE_ACP285_MIN_RATE = 0.10
TIMESTEPS = 365
HORIZONS = [365, 180]
N = 512
NOISE_POINTS, NOISE_KEYS = 64, 8
CONTROL_KEYS = 64
STRESS_RESPONSE = 0.3
CONTROL_RESPONSE = 0.05
YIELDS = (3.0, 5.0, 7.0, 10.0)
CONTROL_YIELD = 5.0
RESPONSE_BOUNDS = (0.0, 0.1)
PIN = "data/pins/p2-model-v0.8.json"
BILL_PIN = "data/pins/p4-opportunity-costs.json"
BILL_DATASET = "fred.tbill-3m-daily"
BILL_FROM, BILL_BEFORE = date(2024, 11, 19), date(2025, 11, 19)
DESIGN_NAME = "milestone-2-sweep"
DESIGN_ROWS, SALTELLI_ROWS, BASELINE_ROWS = 74_176, 61_440, 58_624
TOTAL_ROWS = DESIGN_ROWS + BASELINE_ROWS
BASELINE = {"name": "ChainReward"}
ROW_KEYS = ("seed", "draw", "origin", "model", "mechanism", "renewal_response", "entry_response", "outside_yield_pp",
            "fitted_outside_yield_pp")
LABEL_COLUMNS = ("index", "family", "yield_pp", "block", "i", "j", "u1", "u2", "u3", "baseline")
PAIRED = ("seed", "draw", "renewal_response", "entry_response", "outside_yield_pp", "fitted_outside_yield_pp")


@dataclass(frozen=True)
class Family:
    """A reward family: its code, the mechanism input it sweeps (none for the rule before ACP-285) with its bounds and
    middle, and how a value of that input becomes the row's mechanism."""

    code: str
    input_name: str | None
    bounds: tuple[float, float] | None
    middle: float | None
    mechanism: Callable[[float | None], dict]

    @property
    def inputs(self) -> tuple[str, ...]:
        return (*((self.input_name,) if self.input_name else ()), "renewal_response", "entry_response")

    @property
    def k(self) -> int:
        return len(self.inputs)

    def bounds_of(self, name: str) -> tuple[float, float]:
        return self.bounds if name == self.input_name else RESPONSE_BOUNDS


def _ramp(target: float | None) -> dict:
    return {"name": "ACP285Ramp", "activation": ACTIVATION, "ramp_days": RAMP_DAYS, "target_min_rate": target}


def _before(_: float | None) -> dict:
    # A target equal to the rule's own minimum rate leaves every stake's rate configuration unchanged, at any start.
    return {"name": "ACP285Ramp", "target_min_rate": RULE_BEFORE_ACP285_MIN_RATE}


def _tenure(boost: float | None) -> dict:
    # The boost sits on the rule before ACP-285 for the whole run, as every family's reward design does.
    return {"name": "TenureBoost", "boost_max": boost, "acp285": False}


def _quadratic(exponent: float | None) -> dict:
    return {"name": "QuadraticReward", "exponent": exponent, "acp285": False}


FAMILIES = (
    Family("ramp", "target_min_rate", (0.05, 0.10), 0.075, _ramp),
    Family("before", None, None, None, _before),
    Family("tenure", "boost_max", (0.0, 0.2), 0.1, _tenure),
    Family("quadratic", "exponent", (1.0, 3.0), 2.0, _quadratic),
)
BY_CODE = {family.code: family for family in FAMILIES}

STRESS = ((1, STRESS_RESPONSE, 0.0), (2, 0.0, STRESS_RESPONSE), (3, STRESS_RESPONSE, STRESS_RESPONSE))


def controls(fitted_yield: float) -> tuple[tuple[int, str, float, float, float, float], ...]:
    """The seven implementation controls: number, family, mechanism input, renewal and entry response, outside yield."""
    return (
        (1, "before", None, 0.0, 0.0, fitted_yield),
        (2, "before", None, 0.1, 0.0, fitted_yield),
        (3, "before", None, 0.0, 0.1, fitted_yield),
        (4, "ramp", 0.05, CONTROL_RESPONSE, CONTROL_RESPONSE, CONTROL_YIELD),
        (5, "ramp", 0.10, CONTROL_RESPONSE, CONTROL_RESPONSE, CONTROL_YIELD),
        (6, "tenure", 0.0, CONTROL_RESPONSE, CONTROL_RESPONSE, CONTROL_YIELD),
        (7, "tenure", 0.2, CONTROL_RESPONSE, CONTROL_RESPONSE, CONTROL_YIELD),
    )


def derived_seed(label: str) -> int:
    """A stable 31-bit seed from a label, so each seed is named by what it seeds."""
    return int.from_bytes(hashlib.blake2b(label.encode(), digest_size=8).digest(), "little") >> 33


def design_seed(family: str, yield_pp: float) -> int:
    return derived_seed(f"milestone 2 saltelli {family} {yield_pp:g}")


DRAW_SEED = derived_seed("milestone 2 parameter draws")


# Released versions are registered as their drawn build, so they read draws under their own name.
RELEASES_READING_DRAWS = ("v0.8.0",)


def model_variant(name: str) -> str:
    """The registry name of ``name`` with one parameter draw per run: ``name`` itself if it reads draws, else ``name u``."""
    from avalanche_research.model.variants import VARIANTS

    drawn = name if name.endswith(" u") or name in RELEASES_READING_DRAWS else f"{name} u"
    if drawn not in VARIANTS:
        raise ValueError(f"no variant {drawn!r} reads parameter draws; known: {', '.join(sorted(VARIANTS))}")
    return drawn


def sobol_matrices(family: Family, yield_pp: float):
    """The unit-cube matrices A and B, N rows and k columns each, from one scrambled Sobol sequence in 2k dimensions."""
    from scipy.stats import qmc

    from avalanche_research.model.streams import Streams

    k = family.k
    engine = qmc.Sobol(d=2 * k, scramble=True, rng=Streams(seed=design_seed(family.code, yield_pp), run=0).generator("design"))
    points = engine.random(N)
    return points[:, :k], points[:, k:]


class Keys:
    """Noise keys in order of first use. Key number ``n`` is draw ``n`` of the draw table and model seed ``n + 1``, so
    every distinct key has its own draw and its own seed."""

    def __init__(self):
        self.numbers: dict[tuple, int] = {}

    def __call__(self, name: tuple) -> tuple[int, int]:
        number = self.numbers.setdefault(name, len(self.numbers))
        return number + 1, number

    def __len__(self) -> int:
        return len(self.numbers)


def build(variant: str, fitted_yield: float) -> tuple[list[dict], list[dict], int]:
    """Every row, its label, and the number of distinct noise keys, for the draw-reading variant ``variant`` and the
    fitting window's outside yield ``fitted_yield`` in percent a year."""
    keys = Keys()
    rows: list[dict] = []
    labels: list[dict] = []

    def add(family: Family, value: float | None, renewal: float, entry: float, yield_pp: float, key: tuple,
            block: str, i: int, j: int | None = None, unit=None) -> None:
        seed, draw = keys(key)
        rows.append({
            "seed": seed, "draw": draw, "origin": ORIGIN.isoformat(), "model": variant,
            "mechanism": family.mechanism(value), "renewal_response": renewal, "entry_response": entry,
            "outside_yield_pp": yield_pp, "fitted_outside_yield_pp": fitted_yield,
        })
        coordinates = [float(u) for u in unit] if unit is not None else []
        labels.append({"index": len(labels), "family": family.code, "yield_pp": yield_pp, "block": block, "i": i,
                       "j": j, **{f"u{c + 1}": (coordinates[c] if c < len(coordinates) else None) for c in range(3)},
                       "baseline": None})

    def add_point(family: Family, unit, yield_pp: float, key: tuple, block: str, i: int, j: int | None = None) -> None:
        scaled = {name: family.bounds_of(name)[0] + float(u) * (family.bounds_of(name)[1] - family.bounds_of(name)[0])
                  for name, u in zip(family.inputs, unit)}
        add(family, scaled.get(family.input_name), scaled["renewal_response"], scaled["entry_response"], yield_pp, key,
            block, i, j, unit)

    matrices = {(f.code, y): sobol_matrices(f, y) for y in YIELDS for f in FAMILIES}
    for yield_pp in YIELDS:
        for family in FAMILIES:
            a, b = matrices[family.code, yield_pp]
            for i in range(N):
                add_point(family, a[i], yield_pp, ("A", family.code, yield_pp, i), "A", i)
            for i in range(N):
                add_point(family, b[i], yield_pp, ("B", family.code, yield_pp, i), "B", i)
            for j in range(family.k):
                for i in range(N):
                    hybrid = a[i].copy()
                    hybrid[j] = b[i, j]
                    add_point(family, hybrid, yield_pp, ("A", family.code, yield_pp, i), "AB", i, j + 1)
            for j in range(family.k):
                for i in range(N):
                    hybrid = b[i].copy()
                    hybrid[j] = a[i, j]
                    add_point(family, hybrid, yield_pp, ("B", family.code, yield_pp, i), "BA", i, j + 1)
    saltelli = len(rows)

    for yield_pp in YIELDS:
        for family in FAMILIES:
            a, _ = matrices[family.code, yield_pp]
            for i in range(NOISE_POINTS):
                for r in range(NOISE_KEYS):
                    add_point(family, a[i], yield_pp, ("noise", family.code, yield_pp, i, r), "noise", i, r)
    for yield_pp in YIELDS:
        for family in FAMILIES:
            for c in range(CONTROL_KEYS):
                add(family, family.middle, 0.0, 0.0, yield_pp, ("shared", yield_pp, c), "zero", c)
    for yield_pp in YIELDS:
        for setting, renewal, entry in STRESS:
            for family in FAMILIES:
                for c in range(CONTROL_KEYS):
                    add(family, family.middle, renewal, entry, yield_pp, ("shared", yield_pp, c), "stress", c, setting)
    for number, code, value, renewal, entry, yield_pp in controls(fitted_yield):
        for c in range(CONTROL_KEYS):
            add(BY_CODE[code], value, renewal, entry, yield_pp, ("control", c), "control", c, number)

    # Each design row's baseline is the same run under the chain's rule as it runs: its own key, responses and yields
    # with ChainReward. Rows that differ only in their mechanism share one baseline, numbered in order of first use.
    baselines: dict[tuple, int] = {}
    for label, row in zip(labels[:], rows[:]):
        paired = tuple(row[name] for name in PAIRED)
        if paired not in baselines:
            baselines[paired] = len(rows)
            rows.append({**row, "mechanism": dict(BASELINE)})
            labels.append({"index": len(labels), "family": "chain", "yield_pp": row["outside_yield_pp"],
                           "block": "baseline", "i": len(baselines) - 1, "j": None, "u1": None, "u2": None,
                           "u3": None, "baseline": None})
        label["baseline"] = baselines[paired]

    check(rows, labels, saltelli, len(keys))
    return rows, labels, len(keys)


def expected_keys() -> int:
    """Distinct noise keys: A and B per Saltelli point, the noise replicates, the shared response-zero and stress keys,
    and the control keys."""
    families, yields = len(FAMILIES), len(YIELDS)
    return 2 * N * families * yields + NOISE_POINTS * NOISE_KEYS * families * yields + CONTROL_KEYS * yields + CONTROL_KEYS


def check(rows: list[dict], labels: list[dict], saltelli: int, key_count: int) -> None:
    """Refuse a design whose counts, keys or settings are not as specified."""
    from avalanche_research.model.designs import check_cardinality, check_origins

    if saltelli != SALTELLI_ROWS or sum(N * (2 * f.k + 2) for f in FAMILIES) * len(YIELDS) != SALTELLI_ROWS:
        raise ValueError(f"the design has {saltelli} Saltelli rows, not {SALTELLI_ROWS}")
    check_cardinality(rows, TOTAL_ROWS)
    blocks = [label["block"] for label in labels]
    if blocks.count("baseline") != BASELINE_ROWS or "baseline" in blocks[:DESIGN_ROWS] or set(blocks[DESIGN_ROWS:]) != {"baseline"}:
        raise ValueError(f"the design needs its {DESIGN_ROWS:,} design rows first, then exactly {BASELINE_ROWS:,} baseline rows")
    if {label["baseline"] for label in labels[:DESIGN_ROWS]} != set(range(DESIGN_ROWS, TOTAL_ROWS)):
        raise ValueError("every baseline row must pair with at least one design row")
    check_origins(rows)
    if key_count != expected_keys():
        raise ValueError(f"the design has {key_count} noise keys, not {expected_keys()}")
    pairs = {(row["seed"], row["draw"]) for row in rows}
    if len(pairs) != key_count or len({s for s, _ in pairs}) != key_count or sorted(d for _, d in pairs) != list(range(key_count)):
        raise ValueError("every noise key must have its own seed and its own draw, numbered from draw 0")
    if any(not (type(seed) is int and type(draw) is int and seed == draw + 1) for seed, draw in pairs):
        raise ValueError("key number n must be draw n and seed n + 1")
    if len(labels) != len(rows):
        raise ValueError("every row needs one label")
    if len({row["model"] for row in rows}) != 1:
        raise ValueError("every row, baselines included, must run the same model")
    fitted = {row["fitted_outside_yield_pp"] for row in rows}
    if len(fitted) != 1 or not all(math.isfinite(value) for value in fitted):
        raise ValueError("every row must carry the same finite fitted outside yield")
    allowed_yields = {*YIELDS, *fitted}
    families, yields = len(FAMILIES), len(YIELDS)
    expected_blocks = {
        "A": N * families * yields, "B": N * families * yields,
        "AB": N * sum(f.k for f in FAMILIES) * yields, "BA": N * sum(f.k for f in FAMILIES) * yields,
        "noise": NOISE_POINTS * NOISE_KEYS * families * yields, "zero": CONTROL_KEYS * families * yields,
        "stress": CONTROL_KEYS * len(STRESS) * families * yields, "control": CONTROL_KEYS * 7, "baseline": BASELINE_ROWS,
    }
    if counts(labels) != expected_blocks:
        raise ValueError(f"the design's blocks hold {counts(labels)}, not {expected_blocks}")
    stress = {setting: (renewal, entry) for setting, renewal, entry in STRESS}
    check_points(rows, labels)
    for position, (row, label) in enumerate(zip(rows, labels)):
        if label["index"] != position:
            raise ValueError(f"label {position} names index {label['index']}")
        responses = (row["renewal_response"], row["entry_response"])
        block = label["block"]
        if block in ("A", "B", "AB", "BA", "noise") and not (
                all(RESPONSE_BOUNDS[0] <= r <= RESPONSE_BOUNDS[1] for r in responses) and row["outside_yield_pp"] in YIELDS):
            raise ValueError(f"{block} row {position} needs responses in {RESPONSE_BOUNDS} and a scenario yield")
        if block == "zero" and responses != (0.0, 0.0):
            raise ValueError(f"response-zero row {position} has responses {responses}")
        if block == "stress" and responses != stress.get(label["j"]):
            raise ValueError(f"stress row {position} has responses {responses}, not setting {label['j']}'s")
        i, j, family = label["i"], label["j"], BY_CODE.get(label["family"])
        ranges = {"A": (N, None), "B": (N, None), "AB": (N, range(1, family.k + 1) if family else ()),
                  "BA": (N, range(1, family.k + 1) if family else ()), "noise": (NOISE_POINTS, range(NOISE_KEYS)),
                  "zero": (CONTROL_KEYS, None), "stress": (CONTROL_KEYS, stress), "control": (CONTROL_KEYS, range(1, 8)),
                  "baseline": (BASELINE_ROWS, None)}
        limit, allowed = ranges[block]
        if not (isinstance(i, int) and 0 <= i < limit and (j is None if allowed is None else j in allowed)):
            raise ValueError(f"{block} row {position} has indices i={i!r}, j={j!r}")
        if block == "baseline" and i != position - DESIGN_ROWS:
            raise ValueError(f"baseline row {position} has ordinal {i}, not {position - DESIGN_ROWS}")
        if block in ("zero", "stress") and family and family.input_name and row["mechanism"].get(family.input_name) != family.middle:
            raise ValueError(f"{block} row {position} must hold the {family.code} family's middle setting")
        if block == "control":
            number, code, value, renewal, entry, yield_pp = controls(next(iter(fitted)))[j - 1]
            if (label["family"], *responses, row["outside_yield_pp"]) != (code, renewal, entry, yield_pp) or (
                    BY_CODE[code].input_name and row["mechanism"].get(BY_CODE[code].input_name) != value):
                raise ValueError(f"control row {position} is not control {number}")
        if tuple(row) != ROW_KEYS:
            raise ValueError(f"a row holds {sorted(row)}, not exactly {list(ROW_KEYS)}")
        if row["origin"] != ORIGIN.isoformat():
            raise ValueError(f"every row starts at {ORIGIN.isoformat()}, not {row['origin']}")
        for name in ("renewal_response", "entry_response"):
            if not (math.isfinite(row[name]) and 0.0 <= row[name] <= STRESS_RESPONSE):
                raise ValueError(f"{name} must lie in [0, {STRESS_RESPONSE}], not {row[name]}")
        if row["outside_yield_pp"] not in allowed_yields:
            raise ValueError(f"outside yield {row['outside_yield_pp']} is neither a scenario nor the fitted level")
        if label["block"] == "baseline":
            if label["family"] != "chain" or row["mechanism"] != BASELINE or label["baseline"] is not None:
                raise ValueError(f"baseline row {label['index']} must run ChainReward and name no baseline of its own")
            continue
        partner = label["baseline"]
        if not (isinstance(partner, int) and DESIGN_ROWS <= partner < len(rows) and labels[partner]["block"] == "baseline"
                and rows[partner] == {**row, "mechanism": BASELINE}):
            raise ValueError(f"row {label['index']} must name a baseline row that differs from it only in its mechanism")
        family = BY_CODE.get(label["family"])
        if family is None:
            raise ValueError(f"unknown family label {label['family']!r}")
        value = row["mechanism"].get(family.input_name) if family.input_name else None
        if family.input_name and not (isinstance(value, float) and family.bounds[0] <= value <= family.bounds[1]):
            raise ValueError(f"{family.code} {family.input_name} must lie in {family.bounds}, not {value!r}")
        if row["mechanism"] != family.mechanism(value):
            raise ValueError(f"row mechanism {row['mechanism']} is not the {family.code} family's")


def expected_points(family: Family, block: str) -> set[tuple]:
    """The (i, j) pairs a block holds for one family and yield."""
    if block in ("A", "B"):
        return {(i, None) for i in range(N)}
    if block in ("AB", "BA"):
        return {(i, j) for i in range(N) for j in range(1, family.k + 1)}
    if block == "noise":
        return {(i, r) for i in range(NOISE_POINTS) for r in range(NOISE_KEYS)}
    if block == "zero":
        return {(c, None) for c in range(CONTROL_KEYS)}
    return {(c, setting) for c in range(CONTROL_KEYS) for setting, _, _ in STRESS}


def check_points(rows: list[dict], labels: list[dict]) -> None:
    """Refuse a design in which a block repeats or omits a point, a label's yield is not its row's, or a Saltelli or
    noise row's unit coordinates and inputs are not those of its point in the family's scrambled Sobol matrices."""
    groups: dict[tuple, list[tuple]] = {}
    for row, label in zip(rows, labels):
        if label["yield_pp"] != row["outside_yield_pp"]:
            raise ValueError(f"row {label['index']} is labelled yield {label['yield_pp']}, not {row['outside_yield_pp']}")
        place = (label["family"], label["yield_pp"], label["block"]) if label["block"] not in ("control", "baseline") else (label["block"],)
        groups.setdefault(place, []).append((label["i"], label["j"]))
    for place, points in groups.items():
        if place == ("control",):
            expected = {(c, number) for c in range(CONTROL_KEYS) for number in range(1, 8)}
        elif place == ("baseline",):
            expected = {(i, None) for i in range(BASELINE_ROWS)}
        else:
            expected = expected_points(BY_CODE[place[0]], place[2]) if place[0] in BY_CODE and place[1] in YIELDS else set()
        if len(points) != len(set(points)) or set(points) != expected:
            raise ValueError(f"block {' '.join(map(str, place))} repeats or omits a point")
    if len(groups) != len(FAMILIES) * len(YIELDS) * 7 + 2:
        raise ValueError("the design does not hold every block for every family and yield")
    # Keys: AB_i^(j) has A_i's and BA_i^(j) B_i's; the response-zero and stress rows share one key per yield and c,
    # the controls one per c; no key is shared across these groups.
    owner: dict[tuple, tuple] = {}
    for row, label in zip(rows, labels):
        block = label["block"]
        if block == "baseline":
            continue
        if block in ("A", "AB"):
            group = ("A", label["family"], label["yield_pp"], label["i"])
        elif block in ("B", "BA"):
            group = ("B", label["family"], label["yield_pp"], label["i"])
        elif block == "noise":
            group = ("noise", label["family"], label["yield_pp"], label["i"], label["j"])
        elif block in ("zero", "stress"):
            group = ("shared", label["yield_pp"], label["i"])
        else:
            group = ("control", label["i"])
        if owner.setdefault((row["seed"], row["draw"]), group) != group:
            raise ValueError(f"row {label['index']} shares its key with another group of rows")
    if len(set(owner.values())) != len(owner):
        raise ValueError("a group of rows that must share one key holds more than one")
    matrices = {(f.code, y): sobol_matrices(f, y) for f in FAMILIES for y in YIELDS}
    for row, label in zip(rows, labels):
        block = label["block"]
        if block not in ("A", "B", "AB", "BA", "noise"):
            if any(label[f"u{c}"] is not None for c in (1, 2, 3)):
                raise ValueError(f"{block} row {label['index']} carries unit coordinates")
            continue
        family = BY_CODE[label["family"]]
        a, b = matrices[family.code, label["yield_pp"]]
        i, j = label["i"], label["j"]
        unit = (b if block in ("B", "BA") else a)[i].copy()
        if block in ("AB", "BA"):
            unit[j - 1] = (a if block == "BA" else b)[i, j - 1]
        expected = [float(u) for u in unit] + [None] * (3 - family.k)
        if [label[f"u{c}"] for c in (1, 2, 3)] != expected:
            raise ValueError(f"row {label['index']} has unit coordinates other than its Sobol point's")
        scaled = {name: family.bounds_of(name)[0] + float(u) * (family.bounds_of(name)[1] - family.bounds_of(name)[0])
                  for name, u in zip(family.inputs, unit)}
        held = {"renewal_response": row["renewal_response"], "entry_response": row["entry_response"],
                **({family.input_name: row["mechanism"].get(family.input_name)} if family.input_name else {})}
        if held != scaled:
            raise ValueError(f"row {label['index']} holds inputs other than its Sobol point's")


def bill_mean(pin: Path) -> tuple[float, int, str]:
    """The mean 3-month bill rate over the year before 2025-11-19 from the pinned run, the days it averages, and the run."""
    import duckdb

    from avalanche_research.datasets import parquet_path, pins

    findings = pins.verify(pin)
    if findings:
        raise ValueError(f"pin {pin} does not verify: " + "; ".join(findings))
    run = pins.runs(pin)[BILL_DATASET]
    mean, days = duckdb.execute(
        "SELECT avg(discount_rate_pct), count(discount_rate_pct) FROM read_parquet(?) WHERE date_utc >= ? AND date_utc < ?",
        [str(parquet_path(BILL_DATASET, run)), BILL_FROM, BILL_BEFORE],
    ).fetchone()
    return float(mean), int(days), run


def pinned_periods(pin: Path) -> tuple[str, str]:
    from avalanche_research.datasets import parquet_path, pins

    findings = pins.verify(pin)
    if findings:
        raise ValueError(f"pin {pin} does not verify: " + "; ".join(findings))
    run = pins.runs(pin)["derived.staking-periods"]
    return str(parquet_path("derived.staking-periods", run)), run


def rows_bytes(rows: list[dict]) -> bytes:
    """The rows as a JSON list, one row per line, keys sorted."""
    return ("[\n" + ",\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n]\n").encode()


def labels_bytes(labels: list[dict]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(LABEL_COLUMNS)
    for label in labels:
        writer.writerow(["" if label[c] is None else repr(label[c]) if isinstance(label[c], float) else label[c] for c in LABEL_COLUMNS])
    return out.getvalue().encode()


def write_parquet(frame, path: Path) -> None:
    """``frame`` as Parquet, written by DuckDB on one thread so the bytes repeat."""
    import duckdb

    connection = duckdb.connect()
    try:
        connection.execute("SET threads TO 1")
        connection.register("frame", frame)
        quoted = str(path).replace("'", "''")  # a quote in the folder name stays inside the SQL string
        connection.execute(f"COPY (SELECT * FROM frame) TO '{quoted}' (FORMAT parquet)")
    finally:
        connection.close()


def file_fields(out: Path) -> dict[str, str]:
    """The design's row and draw files, named relative to the design file's own folder, with their hashes. Relative
    names keep ``design.json`` identical wherever the design is written; the sweep reads them from that folder."""
    return {"rows_file": "rows.json", "rows_sha256": sha256(out / "rows.json"),
            "draws_file": "draws.parquet", "draws_sha256": sha256(out / "draws.parquet")}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counts(labels: list[dict]) -> dict[str, int]:
    table: dict[str, int] = {}
    for label in labels:
        table[label["block"]] = table.get(label["block"], 0) + 1
    return table


def readme(variant: str, base: str, fitted: tuple[float, int, str], periods_run: str, key_count: int, tau: float,
           tau_source: str, labels: list[dict], hashes: dict[str, str], draw_columns: list[str]) -> str:
    fitted_yield, bill_days, bill_run = fitted
    blocks = counts(labels)
    per_family = "\n".join(
        f"| `{f.code}` | {f.k} | {N * (2 * f.k + 2):,} | {N * (2 * f.k + 2) * len(YIELDS):,} | "
        f"{design_seed(f.code, YIELDS[0])}, {design_seed(f.code, YIELDS[1])}, {design_seed(f.code, YIELDS[2])}, "
        f"{design_seed(f.code, YIELDS[3])} |" for f in FAMILIES)
    return f"""# Milestone 2 sweep design

Written by `scripts/m2_sweep_design.py {base} <out dir>`. Running it again writes identical bytes.

## Files

| File | SHA-256 |
| --- | --- |
| `rows.json` | `{hashes["rows.json"]}` |
| `labels.csv` | `{hashes["labels.csv"]}` |
| `draws.parquet` | `{hashes["draws.parquet"]}` |
| `design.json` | `{hashes["design.json"]}` |

## Model, origin and inputs

- Model: `{variant}`, {"the released model, which reads one parameter draw per trajectory under its own name" if variant == base
  else f"the variant `{base}` with one parameter draw per trajectory. Its base `{base}` builds its moves and first-commitment tables without node codes, so it refuses a draw table with resample seeds. The variant `{variant}` keeps them"}.
- Origin 2025-11-18, 365 timesteps, one run per row. KPI horizons 365 and 180 days.
- Staking periods and monetary ledger: pin `{PIN}`, staking periods run `{periods_run}`.
- Fitting window's outside yield: {fitted_yield!r}% a year, the mean of FRED's 3-month bill rate (DTB3, a discount rate)
  over the {bill_days} days with a value from 2024-11-19 to 2025-11-18, run `{bill_run}` of pin `{BILL_PIN}`.

| Family | Mechanism in `rows.json` | Swept |
| --- | --- | --- |
| `ramp` | `ACP285Ramp`, `activation` {ACTIVATION}, `ramp_days` {RAMP_DAYS}, `target_min_rate` | target U(0.05, 0.10), both responses |
| `before` | `ACP285Ramp` with `target_min_rate` 0.10, the rule before ACP-285 at every start | both responses |
| `tenure` | `TenureBoost`, `boost_max` | boost U(0, 0.2), both responses |
| `quadratic` | `QuadraticReward`, `exponent` | exponent U(1, 3), both responses |

Both responses are U(0, 0.1). Outside yields are 3, 5, 7 and 10% a year.

## Counts

| Family | k | Saltelli rows per yield | Four yields | Design seeds at 3, 5, 7, 10% |
| --- | --- | --- | --- | --- |
{per_family}

| Block | Rows |
| --- | --- |
| A | {blocks["A"]:,} |
| B | {blocks["B"]:,} |
| AB | {blocks["AB"]:,} |
| BA | {blocks["BA"]:,} |
| **Saltelli** | **{SALTELLI_ROWS:,}** |
| Noise replicates, 4 families x 64 points x 8 keys x 4 yields | {blocks["noise"]:,} |
| Both responses zero, 4 families x 64 keys x 4 yields | {blocks["zero"]:,} |
| Stress, 3 settings x 4 families x 64 keys x 4 yields | {blocks["stress"]:,} |
| Implementation controls, 7 settings x 64 keys | {blocks["control"]:,} |
| **Design rows** | **{DESIGN_ROWS:,}** |
| Baselines under the chain's rule, one per distinct key, responses and yields | {blocks["baseline"]:,} |
| **All rows** | **{TOTAL_ROWS:,}** |

Distinct noise keys: {key_count:,}. Key number n is draw n and seed n + 1, so each key has its own draw and seed.

## Noise keys and pairing

- A_i and B_i have independent keys for each family and yield. AB_i^(j) has A_i's key and BA_i^(j) has B_i's.
- The noise replicates use the first 64 points of A, the first 2^6 points of the scrambled sequence, each with 8 new keys.
- The response-zero rows share 64 keys across the four families at each yield, keyed by yield and control index c.
- The stress rows reuse those same 64 keys at each yield, across all three settings and all four families, so every
  stress row is paired with the response-zero rows and with the other stress settings.
- The seven implementation controls share one set of 64 keys of their own, keyed by control index c, so each check
  (the three `before` settings, `ramp` at 5% against 10%, `tenure` at 0 against 0.2) compares runs on the same keys.
- Every design row has a baseline: the same key, responses and yields under `ChainReward`, the chain's rule as it
  runs, with ACP-285 from Helicon on 2026-09-22. The baselines follow the design rows in `rows.json`, and `labels.csv`
  column `baseline` gives each design row's baseline index. Rows that differ only in their mechanism, such as A_i and
  AB_i^(j) for the mechanism column, share one baseline. Against the chain's rule, issuance saved is one minus the
  row's `issued_navax` over its baseline's, and validator stake and active validators retained are the row's
  `validator_stake_navax` and `active_validators` over its baseline's.
- Middle settings, for the response-zero and stress rows: `ramp` target 0.075 (ACP-285's), `tenure` boost 0.1, `quadratic` exponent 2.

## Controls

| c | Family | Mechanism input | Renewal, entry response | Outside yield |
| --- | --- | --- | --- | --- |
""" + "\n".join(f"| {n} | `{code}` | {'' if value is None else value} | {renewal}, {entry} | {y!r} |"
                for n, code, value, renewal, entry, y in controls(fitted_yield)) + f"""

## Draws

`draws.parquet` is `parameter_draws` from the variant's own preparation, `{variant}`.prepare with {key_count:,} draws
under draw seed {DRAW_SEED}. Renewal shift SD {tau!r}, {tau_source}. Columns: {", ".join(f"`{c}`" for c in draw_columns)}.

## labels.csv

`index` is the row's position in `rows.json` and the sweep's row index. `i` is the Saltelli point, noise base point or
control index c, or the baseline's ordinal. `j` is the 1-based column for AB and BA, the replicate 0 to 7 for noise rows, the stress setting
(1 renewal 0.3, 2 entry 0.3, 3 both) or the control number. `u1` to `u3` are the row's unit-cube Sobol coordinates in
the family's input order: the mechanism input first, then the renewal and entry responses. `baseline` is the index of
the design row's baseline row, empty on the baselines, whose `family` is `chain` and `block` is `baseline`.

## The rule under each design

`TenureBoost` and `QuadraticReward` rows set `acp285` false, so every stake in the run, including those started after
Helicon on 2026-09-22, is priced on the rule before ACP-285. No row mixes two rules.
"""


def main(argv: list[str]) -> int:
    import pandas as pd

    from avalanche_research.model.variants import VARIANTS

    if len(argv) != 2:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    base, out = argv[0], Path(argv[1])
    variant = model_variant(base)
    fitted = bill_mean(Path(BILL_PIN))
    periods, periods_run = pinned_periods(Path(PIN))
    rows, labels, key_count = build(variant, fitted[0])
    prepared = VARIANTS[variant].prepare(periods, ORIGIN, periods_run, draws=key_count, draw_seed=DRAW_SEED)
    draws: pd.DataFrame = prepared.draws
    if len(draws) != key_count:
        raise ValueError(f"the draw table has {len(draws)} rows for {key_count} keys")
    out.mkdir(parents=True, exist_ok=True)
    (out / "rows.json").write_bytes(rows_bytes(rows))
    (out / "labels.csv").write_bytes(labels_bytes(labels))
    write_parquet(draws, out / "draws.parquet")
    design = {
        "name": DESIGN_NAME, "generator": "explicit",
        **file_fields(out),
        "origins": [ORIGIN.isoformat()], "models": [variant], "rows": TOTAL_ROWS, "pin": PIN,
        "runs": 1, "timesteps": TIMESTEPS, "workers": "auto",
        # Every row sets its own outside yield, which the reducer reads as its competing yield. The return margin is
        # linear in the operating cost, so it is kept at a cost of zero and any cost level is subtracted afterwards.
        "reducer": {"kind": "kpis", "horizons": HORIZONS, "competing_yield": fitted[0] / 100, "operating_costs": {"zero": 0.0}},
        "provenance": {
            "variant": base, "fitted_outside_yield_pp": fitted[0], "fitted_outside_yield_days": fitted[1],
            "fitted_outside_yield_run": fitted[2], "fitted_outside_yield_pin": BILL_PIN, "draw_seed": DRAW_SEED,
            "draws": key_count, "renewal_shift_sd": prepared.tau, "renewal_shift_sd_source": prepared.tau_source,
            "design_seeds": {f"{f.code} {y:g}": design_seed(f.code, y) for f in FAMILIES for y in YIELDS},
        },
    }
    (out / "design.json").write_text(json.dumps(design, indent=1, sort_keys=True) + "\n")
    hashes = {name: sha256(out / name) for name in ("rows.json", "labels.csv", "draws.parquet", "design.json")}
    (out / "README.md").write_text(readme(variant, base, fitted, periods_run, key_count, prepared.tau, prepared.tau_source,
                                          labels, hashes, list(draws.columns)))
    print(json.dumps({"rows": len(rows), "keys": key_count, "fitted_outside_yield_pp": fitted[0], **hashes}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
