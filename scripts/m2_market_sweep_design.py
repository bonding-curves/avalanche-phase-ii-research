"""The Milestone 2 supplementary sweep: governance settings and market conditions, with every row's label.

    python scripts/m2_market_sweep_design.py <Milestone 2 design folder> <out dir>

The Milestone 2 design folder holds that sweep's ``rows.json``, ``labels.csv``, ``draws.parquet`` and ``design.json``
as ``scripts/m2_sweep_design.py v0.8.0`` wrote them. This design reuses its draw table unchanged, so key number n is
still draw n and seed n + 1, and it copies 512 of its design rows, with their baselines, as a bridge that must
reproduce them. It writes ``rows.json``, ``labels.csv``, ``draws.parquet``, ``design.json`` and ``README.md`` to
``out dir``, and runs on model v0.8.0 from the same origin, 2025-11-18, for 365 days.

Four blocks of design rows, each paired with a baseline under ``ChainReward`` on the same key, responses, yields and
market shifts:

- ``S``: one Saltelli design with second-order terms, N = 2,048, over nine inputs: the minimum consumption rate
  U(0.05, 0.15), the gap to the maximum rate U(0, 0.08), the shortest commitment U(14, 90) days and the longest
  U(182, 365) days of :class:`~avalanche_research.mechanisms.GovernanceReward`, both responses U(0, 0.1), the market
  strength U(0, 1), the market condition (bear, neutral, bull, a third of the unit interval each) and the outside yield
  (3, 5, 7, 10%, a quarter each).
- ``F``: the four Milestone 2 families in each of the 12 markets and yields, on 128 keys per cell. A key's responses,
  strength and family inputs come from one scrambled Sobol point, and the four families share the key, so they share
  one baseline.
- ``X``: 512 Milestone 2 design rows and their baselines, copied byte for byte, on keys no other block uses.
- ``C``: four controls on 64 keys of their own: ``GovernanceReward`` at the rule before ACP-285 (10%, 12%, 14 and
  365 days), the ``before`` family, and the ``before`` family in a bull and a bear market at full strength.

A market condition shifts the log-odds of every renewal and the log of the first-ever arrival rate by its strength
times the difference between that market's windows and the range windows before the held-back period (``SHIFTS``).
"""

from __future__ import annotations

import csv
import io
import json
import math
import sys
from pathlib import Path

import m2_sweep_design as m2

DESIGN_NAME = "milestone-2-market-sweep"
MODEL = "v0.8.0"
N_S = 2048
F_KEYS = 128
CONTROL_KEYS = 64
BRIDGE_ROWS = 512
CONTROL_RESPONSE = 0.05
MARKETS = ("bear", "neutral", "bull")
YIELDS = m2.YIELDS
M2_DRAWS_SHA256 = "0e4a238778597b44e33b1be31a6179b715d67de0d2dd773ad6faca12331df75d"
M2_ROWS_SHA256 = "b8fc2b4f2dcb746a3ac54f56fc5247e88847876780c567589cd9e45e66b36b79"
M2_LABELS_SHA256 = "ac362934f53196d5ea06e92ed2a22ce4c3367f8c27a850116a3249e05651dd41"
M2_KEYS = 24_896

# Renewal decisions and first-ever commitments in the environment report's regimes (section 8), counted with the
# model's own definitions (fitted_lifecycle.validator_periods and renewal_endings) on staking periods
# staking-periods-2026-09-30, up to 2025-11-18. G1, the launch window, is left out: its first-ever count is the
# network's own start. G10 is cut at 2025-11-11, the last ending with seven days of follow-up before the origin.
REGIME_COUNTS = {
    "bull": {"G2": (3143, 2450, 686, 194), "G6": (6353, 5251, 912, 168), "G8": (3346, 2759, 383, 76)},
    "bear": {"G3": (4268, 3367, 988, 166), "G4": (5036, 3715, 473, 239), "G10": (754, 599, 61, 36)},
    "range": {"G5": (5501, 4302, 775, 288), "G7": (9954, 8264, 771, 219), "G9": (11082, 8567, 1013, 259)},
}
"""Per regime: renewal decisions, renewals, first-ever commitments, days."""


def _pooled(state: str) -> tuple[float, float]:
    endings, renewed, first, days = (sum(v[c] for v in REGIME_COUNTS[state].values()) for c in range(4))
    return renewed / endings, first / days


def _shifts() -> dict[str, tuple[float, float]]:
    """Each market's full-strength shift in renewal log-odds and in log arrivals, against the range windows."""
    share0, rate0 = _pooled("range")
    logit = lambda p: math.log(p / (1 - p))  # noqa: E731
    out = {"neutral": (0.0, 0.0)}
    for market in ("bull", "bear"):
        share, rate = _pooled(market)
        out[market] = (logit(share) - logit(share0), math.log(rate / rate0))
    return out


SHIFTS = _shifts()

GOVERNANCE_INPUTS = ("min_rate", "rate_gap", "min_days", "max_days", "renewal_response", "entry_response",
                     "market_strength", "market", "yield")
GOVERNANCE_BOUNDS = {"min_rate": (0.05, 0.15), "rate_gap": (0.0, 0.08), "min_days": (14, 90), "max_days": (182, 365)}
F_INPUTS = ("renewal_response", "entry_response", "market_strength", "target_min_rate", "boost_max", "exponent")
ROW_KEYS = (*m2.ROW_KEYS, "market_renewal_shift", "market_entry_shift")
PAIRED = (*m2.PAIRED, "market_renewal_shift", "market_entry_shift")
LABEL_COLUMNS = ("index", "block", "family", "yield_pp", "market", "market_strength", "i", "j",
                 *(f"u{c}" for c in range(1, 10)), "baseline", "m2_index")


def s_seed() -> int:
    return m2.derived_seed("milestone 2 supplement saltelli governance")


def f_seed(market: str, yield_pp: float) -> int:
    return m2.derived_seed(f"milestone 2 supplement families {market} {yield_pp:g}")


def sobol(d: int, n: int, seed: int):
    from scipy.stats import qmc

    from avalanche_research.model.streams import Streams

    return qmc.Sobol(d=d, scramble=True, rng=Streams(seed=seed, run=0).generator("design")).random(n)


def pick(u: float, levels: tuple):
    return levels[min(int(u * len(levels)), len(levels) - 1)]


def scale(u: float, bounds: tuple[float, float]) -> float:
    return bounds[0] + float(u) * (bounds[1] - bounds[0])


def governance(min_rate: float, max_rate: float, min_days: int, max_days: int) -> dict:
    return {"name": "GovernanceReward", "min_rate": min_rate, "max_rate": max_rate, "min_days": min_days, "max_days": max_days}


def market_shifts(market: str, strength: float) -> tuple[float, float]:
    renewal, entry = SHIFTS[market]
    return renewal * strength, entry * strength


class NewKeys:
    """Key numbers from 0 in order of first use. Key n is draw n and seed n + 1, as in Milestone 2."""

    def __init__(self):
        self.numbers: dict[tuple, int] = {}

    def __call__(self, name: tuple) -> tuple[int, int]:
        number = self.numbers.setdefault(name, len(self.numbers))
        return number + 1, number


def build(fitted_yield: float, m2_rows: list[dict], m2_labels: list[dict]) -> tuple[list[dict], list[dict], int, list[dict]]:
    """Every row, its label, the number of new keys, and the Saltelli points that repeat a row (``aliases``)."""
    aliases: list[dict] = []
    keys = NewKeys()
    rows: list[dict] = []
    labels: list[dict] = []
    seen: dict[str, int] = {}

    def add(mechanism: dict, renewal: float, entry: float, yield_pp: float, market: str, strength: float, key: tuple,
            block: str, family: str, i: int, j=None, unit=()) -> None:
        seed, draw = keys(key)
        shift_r, shift_e = market_shifts(market, strength)
        row = {"seed": seed, "draw": draw, "origin": m2.ORIGIN.isoformat(), "model": MODEL, "mechanism": mechanism,
               "renewal_response": renewal, "entry_response": entry, "outside_yield_pp": yield_pp,
               "fitted_outside_yield_pp": fitted_yield, "market_renewal_shift": shift_r, "market_entry_shift": shift_e}
        coordinates = [float(u) for u in unit]
        label = {"index": len(labels), "block": block, "family": family, "yield_pp": yield_pp, "market": market,
                 "market_strength": strength, "i": i, "j": j,
                 **{f"u{c + 1}": (coordinates[c] if c < len(coordinates) else None) for c in range(9)},
                 "baseline": None, "m2_index": None}
        text = json.dumps(row, sort_keys=True)
        if text in seen:
            # A Saltelli hybrid whose swapped column lands on the same market, yield or whole day as its own row runs
            # exactly that row, so it is listed in aliases.csv instead of run twice.
            aliases.append({"block": block, "i": i, "j": j, "index": seen[text]})
            return
        seen[text] = len(rows)
        rows.append(row)
        labels.append(label)

    # S: Saltelli over the governance settings, responses, market and yield.
    points = sobol(2 * len(GOVERNANCE_INPUTS), N_S, s_seed())
    a, b = points[:, :len(GOVERNANCE_INPUTS)], points[:, len(GOVERNANCE_INPUTS):]

    def add_s(unit, key, block, i, j=None):
        v = dict(zip(GOVERNANCE_INPUTS, (float(u) for u in unit)))
        min_rate = scale(v["min_rate"], GOVERNANCE_BOUNDS["min_rate"])
        max_rate = min_rate + scale(v["rate_gap"], GOVERNANCE_BOUNDS["rate_gap"])
        min_days = round(scale(v["min_days"], GOVERNANCE_BOUNDS["min_days"]))
        max_days = round(scale(v["max_days"], GOVERNANCE_BOUNDS["max_days"]))
        add(governance(min_rate, max_rate, min_days, max_days), scale(v["renewal_response"], m2.RESPONSE_BOUNDS),
            scale(v["entry_response"], m2.RESPONSE_BOUNDS), pick(v["yield"], YIELDS), pick(v["market"], MARKETS),
            v["market_strength"], key, block, "governance", i, j, unit)

    for i in range(N_S):
        add_s(a[i], ("S", "A", i), "A", i)
    for i in range(N_S):
        add_s(b[i], ("S", "B", i), "B", i)
    for j in range(len(GOVERNANCE_INPUTS)):
        for i in range(N_S):
            hybrid = a[i].copy()
            hybrid[j] = b[i, j]
            add_s(hybrid, ("S", "A", i), "AB", i, j + 1)
    for j in range(len(GOVERNANCE_INPUTS)):
        for i in range(N_S):
            hybrid = b[i].copy()
            hybrid[j] = a[i, j]
            add_s(hybrid, ("S", "B", i), "BA", i, j + 1)

    # F: the four Milestone 2 families in every market and yield, sharing each key.
    for market in MARKETS:
        for yield_pp in YIELDS:
            cell = sobol(len(F_INPUTS), F_KEYS, f_seed(market, yield_pp))
            for i in range(F_KEYS):
                v = dict(zip(F_INPUTS, (float(u) for u in cell[i])))
                renewal, entry = scale(v["renewal_response"], m2.RESPONSE_BOUNDS), scale(v["entry_response"], m2.RESPONSE_BOUNDS)
                for family in m2.FAMILIES:
                    value = scale(v[family.input_name], family.bounds) if family.input_name else None
                    add(family.mechanism(value), renewal, entry, yield_pp, market, v["market_strength"],
                        ("F", market, yield_pp, i), "F", family.code, i, None, cell[i])

    # C: controls on keys of their own.
    controls = (
        (1, governance(0.10, 0.12, 14, 365), "governance", "neutral", 0.0),
        (2, m2.BY_CODE["before"].mechanism(None), "before", "neutral", 0.0),
        (3, m2.BY_CODE["before"].mechanism(None), "before", "bull", 1.0),
        (4, m2.BY_CODE["before"].mechanism(None), "before", "bear", 1.0),
    )
    for number, mechanism, family, market, strength in controls:
        for c in range(CONTROL_KEYS):
            add(mechanism, CONTROL_RESPONSE, CONTROL_RESPONSE, fitted_yield, market, strength, ("C", c), "C", family, c, number)

    new_keys = len(keys.numbers)
    # Baselines for the new rows: one per distinct key, responses, yields and market shifts.
    baselines: dict[tuple, int] = {}
    for label, row in zip(labels[:], rows[:]):
        paired = tuple(row[name] for name in PAIRED)
        if paired not in baselines:
            baselines[paired] = len(rows)
            rows.append({**row, "mechanism": dict(m2.BASELINE)})
            labels.append({**label, "index": len(labels), "block": "baseline", "family": "chain", "i": len(baselines) - 1,
                           "j": None, **{f"u{c}": None for c in range(1, 10)}, "baseline": None})
        label["baseline"] = baselines[paired]

    # X: Milestone 2 design rows on keys this design does not use, evenly spaced, with their own baselines.
    eligible = [k for k in range(m2.DESIGN_ROWS) if m2_rows[k]["draw"] >= new_keys]
    chosen = [eligible[round(t * (len(eligible) - 1) / (BRIDGE_ROWS - 1))] for t in range(BRIDGE_ROWS)]
    copied: dict[int, int] = {}

    def copy(k: int) -> int:
        if k not in copied:
            copied[k] = len(rows)
            m2_label = m2_labels[k]
            rows.append(dict(m2_rows[k]))
            labels.append({"index": len(labels), "block": "X" if m2_label["block"] != "baseline" else "X-baseline",
                           "family": m2_label["family"], "yield_pp": m2_rows[k]["outside_yield_pp"], "market": "neutral",
                           "market_strength": 0.0, "i": len(copied) - 1, "j": None,
                           **{f"u{c}": None for c in range(1, 10)}, "baseline": None, "m2_index": k})
        return copied[k]

    for k in chosen:
        position = copy(k)
        labels[position]["baseline"] = copy(int(m2_labels[k]["baseline"]))

    check(rows, labels, new_keys, m2_rows, aliases)
    return rows, labels, new_keys, aliases


def counts(labels: list[dict]) -> dict[str, int]:
    table: dict[str, int] = {}
    for label in labels:
        table[label["block"]] = table.get(label["block"], 0) + 1
    return table


def check(rows: list[dict], labels: list[dict], new_keys: int, m2_rows: list[dict], aliases: list[dict]) -> None:
    """Refuse a design whose counts, keys, pairing, bounds or bridge are not as specified."""
    from avalanche_research.model.designs import check_cardinality, check_origins

    from avalanche_research import mechanisms

    k = len(GOVERNANCE_INPUTS)
    blocks = counts(labels)
    expected = {"A": N_S, "B": N_S, "AB": N_S * k, "BA": N_S * k, "F": len(MARKETS) * len(YIELDS) * F_KEYS * len(m2.FAMILIES),
                "C": 4 * CONTROL_KEYS}
    for alias in aliases:
        blocks[alias["block"]] = blocks.get(alias["block"], 0) + 1
        if alias["block"] not in ("AB", "BA") or labels[alias["index"]]["i"] != alias["i"]:
            raise ValueError(f"only a Saltelli hybrid may repeat its own point's row, not {alias}")
    for block, n in expected.items():
        if blocks.get(block) != n:
            raise ValueError(f"block {block} holds {blocks.get(block)} rows, not {n}")
    if blocks.get("X") != BRIDGE_ROWS:
        raise ValueError(f"the bridge holds {blocks.get('X')} design rows, not {BRIDGE_ROWS}")
    if new_keys != 2 * N_S + len(MARKETS) * len(YIELDS) * F_KEYS + CONTROL_KEYS or new_keys > M2_KEYS:
        raise ValueError(f"the design uses {new_keys} new keys")
    check_cardinality(rows, len(rows))
    check_origins(rows)
    for row in rows:
        if not (type(row["seed"]) is int and type(row["draw"]) is int and row["seed"] == row["draw"] + 1 and 0 <= row["draw"] < M2_KEYS):
            raise ValueError("key number n must be draw n and seed n + 1, within the Milestone 2 draw table")
    owner: dict[tuple, str] = {}
    for row, label in zip(rows, labels):
        group = "X" if label["block"].startswith("X") else "new"
        if owner.setdefault((row["seed"], row["draw"]), group) != group:
            raise ValueError(f"row {label['index']} shares its key across the bridge and the new blocks")
    m2_by_index = {}
    for position, (row, label) in enumerate(zip(rows, labels)):
        if label["index"] != position:
            raise ValueError(f"label {position} names index {label['index']}")
        if label["block"].startswith("X"):
            if row != m2_rows[label["m2_index"]]:
                raise ValueError(f"bridge row {position} is not Milestone 2 row {label['m2_index']}")
            m2_by_index[label["m2_index"]] = position
            continue
        if tuple(row) != ROW_KEYS:
            raise ValueError(f"row {position} holds {list(row)}, not {list(ROW_KEYS)}")
        if row["model"] != MODEL or row["origin"] != m2.ORIGIN.isoformat():
            raise ValueError(f"row {position} must run {MODEL} from {m2.ORIGIN}")
        expected_shifts = market_shifts(label["market"], label["market_strength"])
        if (row["market_renewal_shift"], row["market_entry_shift"]) != expected_shifts:
            raise ValueError(f"row {position} has market shifts other than its market and strength give")
        if not 0.0 <= label["market_strength"] <= 1.0:
            raise ValueError(f"row {position} has market strength {label['market_strength']}")
        mechanism = row["mechanism"]
        cls = getattr(mechanisms, mechanism["name"])
        cls(**{key: value for key, value in mechanism.items() if key not in ("name", "activation")})  # bounds and order
        if mechanism["name"] == "GovernanceReward" and label["block"] in ("A", "B", "AB", "BA"):
            lo_r, hi_r = GOVERNANCE_BOUNDS["min_rate"]
            if not (lo_r <= mechanism["min_rate"] <= hi_r and 0.0 <= mechanism["max_rate"] - mechanism["min_rate"] <= 0.08 + 1e-12
                    and 14 <= mechanism["min_days"] <= 90 and 182 <= mechanism["max_days"] <= 365
                    and row["outside_yield_pp"] in YIELDS):
                raise ValueError(f"governance row {position} is outside the design's bounds")
        if label["block"] == "baseline":
            if mechanism != m2.BASELINE or label["baseline"] is not None:
                raise ValueError(f"baseline row {position} must run ChainReward")
            continue
        partner = label["baseline"]
        if not (isinstance(partner, int) and labels[partner]["block"] == "baseline" and rows[partner] == {**row, "mechanism": m2.BASELINE}):
            raise ValueError(f"row {position} must name a baseline that differs from it only in its mechanism")
    for k, position in m2_by_index.items():
        label = labels[position]
        if label["block"] == "X":
            partner = labels[label["baseline"]]
            if partner["block"] != "X-baseline" or rows[label["baseline"]] != {**rows[position], "mechanism": m2.BASELINE}:
                raise ValueError(f"bridge row {position} must name its Milestone 2 baseline")


def labels_bytes(labels: list[dict]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(LABEL_COLUMNS)
    for label in labels:
        writer.writerow(["" if label[c] is None else repr(label[c]) if isinstance(label[c], float) else label[c] for c in LABEL_COLUMNS])
    return out.getvalue().encode()


def read_m2(folder: Path) -> tuple[list[dict], list[dict], dict]:
    hashes = {name: m2.sha256(folder / name) for name in ("rows.json", "labels.csv", "draws.parquet")}
    if hashes != {"rows.json": M2_ROWS_SHA256, "labels.csv": M2_LABELS_SHA256, "draws.parquet": M2_DRAWS_SHA256}:
        raise ValueError(f"the Milestone 2 design files in {folder} are not the launched ones: {hashes}")
    rows = json.loads((folder / "rows.json").read_text())
    with (folder / "labels.csv").open() as stream:
        labels = list(csv.DictReader(stream))
    return rows, labels, json.loads((folder / "design.json").read_text())


def readme(fitted_yield: float, labels: list[dict], hashes: dict[str, str], new_keys: int, rows: int) -> str:
    blocks = counts(labels)
    shift_rows = "\n".join(f"| {market} | {SHIFTS[market][0]:+.4f} | {SHIFTS[market][1]:+.4f} |" for market in MARKETS)
    regimes = "\n".join(
        f"| {state} | {code} | {e:,} | {r:,} | {r / e:.4f} | {f:,} | {d} | {f / d:.3f} |"
        for state, table in REGIME_COUNTS.items() for code, (e, r, f, d) in table.items())
    block_rows = "\n".join(f"| {block} | {n:,} |" for block, n in blocks.items())
    return f"""# Milestone 2 supplementary sweep design

Written by `scripts/m2_market_sweep_design.py <Milestone 2 design folder> <out dir>`. Running it again writes
identical bytes.

## Files

| File | SHA-256 |
| --- | --- |
| `rows.json` | `{hashes["rows.json"]}` |
| `labels.csv` | `{hashes["labels.csv"]}` |
| `aliases.csv` | `{hashes["aliases.csv"]}`, Saltelli hybrids that repeat a row, with that row's index |
| `draws.parquet` | `{hashes["draws.parquet"]}`, the Milestone 2 draw table unchanged |
| `design.json` | `{hashes["design.json"]}` |

## Model and inputs

- Model `{MODEL}`, origin 2025-11-18, 365 timesteps, one run per row, KPI horizons 365 and 180 days, return margin at
  a cost of zero, as in Milestone 2. Fitting window's outside yield {fitted_yield!r}% a year.
- New keys: {new_keys:,}, numbered from 0, so key n is draw n and seed n + 1 of the Milestone 2 draw table. Those
  keys carry the same noise as Milestone 2's keys 0 to {new_keys - 1:,}. The bridge rows keep their own Milestone 2
  keys, all at or above {new_keys:,}, so no key is shared between the bridge and the new blocks.
- Saltelli seed {s_seed()}. Family cell seeds: {", ".join(f"{m} {y:g}: {f_seed(m, y)}" for m in MARKETS for y in YIELDS)}.

## Market shifts at full strength

A row's shifts are its market strength times these. Neutral is the range windows, which the fitted year mostly is.

| Market | Renewal log-odds | Log arrivals |
| --- | ---: | ---: |
{shift_rows}

| State | Regime | Renewal decisions | Renewals | Share | First-ever | Days | Per day |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
{regimes}

## Counts

| Block | Rows |
| --- | ---: |
{block_rows}
| **All rows** | **{rows:,}** |

## labels.csv

`index` is the row's position in `rows.json`. `block` is A, B, AB, BA (Saltelli over the governance settings), F (the
Milestone 2 families), C (controls, `j` the control number), baseline (the chain's rule), X and X-baseline (copied
Milestone 2 rows, `m2_index` their Milestone 2 index). `u1` to `u9` are the unit coordinates in the order
{", ".join(GOVERNANCE_INPUTS)} for S rows and {", ".join(F_INPUTS)} for F rows. `baseline` is the design row's baseline.
"""


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    source, out = Path(argv[0]), Path(argv[1])
    m2_rows, m2_labels, m2_design = read_m2(source)
    fitted = m2.bill_mean(Path(m2.BILL_PIN))
    if fitted[0] != m2_design["provenance"]["fitted_outside_yield_pp"]:
        raise ValueError(f"the fitted outside yield {fitted[0]} differs from Milestone 2's")
    rows, labels, new_keys, aliases = build(fitted[0], m2_rows, m2_labels)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rows.json").write_bytes(m2.rows_bytes(rows))
    (out / "labels.csv").write_bytes(labels_bytes(labels))
    (out / "draws.parquet").write_bytes((source / "draws.parquet").read_bytes())
    (out / "aliases.csv").write_text("block,i,j,index\n" + "".join(f"{a['block']},{a['i']},{a['j']},{a['index']}\n" for a in aliases))
    design = {
        "name": DESIGN_NAME, "generator": "explicit", **m2.file_fields(out),
        "origins": [m2.ORIGIN.isoformat()], "models": [MODEL], "rows": len(rows), "pin": m2.PIN,
        "runs": 1, "timesteps": m2.TIMESTEPS, "workers": 4,
        "reducer": m2_design["reducer"],
        "provenance": {"variant": MODEL, "fitted_outside_yield_pp": fitted[0], "new_keys": new_keys,
                       "milestone_2_rows_sha256": M2_ROWS_SHA256, "milestone_2_draws_sha256": M2_DRAWS_SHA256,
                       "saltelli_seed": s_seed(), "family_seeds": {f"{m} {y:g}": f_seed(m, y) for m in MARKETS for y in YIELDS},
                       "market_shifts": {m: list(SHIFTS[m]) for m in MARKETS}},
    }
    (out / "design.json").write_text(json.dumps(design, indent=1, sort_keys=True) + "\n")
    hashes = {name: m2.sha256(out / name) for name in ("rows.json", "labels.csv", "aliases.csv", "draws.parquet", "design.json")}
    (out / "README.md").write_text(readme(fitted[0], labels, hashes, new_keys, len(rows)))
    print(json.dumps({"rows": len(rows), "new_keys": new_keys, "blocks": counts(labels), **hashes}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
