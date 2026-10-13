"""Authenticate paired sweep outputs and reconstruct their relative KPIs.

The caller supplies the frozen bundle hashes, code commit and pin hash. This
module does not fit models or select scientific thresholds. Baseline sharing is
retained explicitly so downstream methods can use the declared resampling law.
"""
from __future__ import annotations

import io
import json
import math
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from ..core.hashing import canonical_bytes, sha256
from ..model.designs import design_hash, row_id

BUNDLE_FILES = ("design.json", "rows.json", "labels.csv", "draws.parquet")
FAMILIES = {"ramp": 3, "before": 2, "tenure": 3, "quadratic": 3}
FAMILY_INPUTS = {"ramp": "target_min_rate", "before": None, "tenure": "boost_max", "quadratic": "exponent"}
PRIMITIVES = ("issued_navax", "validator_stake_navax", "active_validators")
MEASURES = (*PRIMITIVES, "lowest_validator_stake_navax", "net_inflation",
            "validator_staking_ratio", "nakamoto_coefficient", "earned_rate",
            "stake_weighted_duration", "reward_rate_volatility", "stake_volatility",
            "worst_30_day_stake_fall", "issuance_half_life")
CELL = ("index", "run", "measure", "horizon_days", "cost_level")


class ContractError(ValueError):
    """An input differs from the caller's complete, frozen analysis contract."""


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def _integer(value, name):
    _require(isinstance(value, str) and re.fullmatch(r"\d+", value) is not None, f"invalid {name}")
    return int(value)


@dataclass(frozen=True)
class Bundle:
    design: dict
    rows: tuple[dict, ...]
    labels: pd.DataFrame
    hashes: dict[str, str]
    draws: int


def _mechanism(family, value=None):
    if family == "ramp":
        return {"name": "ACP285Ramp", "activation": "2025-11-18T16:00:00+00:00",
                "ramp_days": 90, "target_min_rate": value}
    if family == "before":
        return {"name": "ACP285Ramp", "target_min_rate": 0.1}
    if family == "tenure":
        return {"name": "TenureBoost", "boost_max": value, "acp285": False}
    return {"name": "QuadraticReward", "exponent": value, "acp285": False}


def _control_metadata(rows, labels):
    for _, group in labels.loc[labels.block == "zero"].groupby(["yield_pp", "i"]):
        _require(set(group.family) == set(FAMILIES) and len(group) == 4, "incomplete response-zero family set")
        keys = set()
        for label in group.to_dict("records"):
            row = rows[label["index"]]
            _require((row["renewal_response"], row["entry_response"]) == (0.0, 0.0),
                     "response-zero control has nonzero responses")
            middle = {"ramp": 0.075, "before": None, "tenure": 0.1, "quadratic": 2.0}[label["family"]]
            _require(row["mechanism"] == _mechanism(label["family"], middle), "response-zero mechanism differs")
            keys.add((row["seed"], row["draw"], row["model"], row["origin"], row["fitted_outside_yield_pp"]))
        _require(len(keys) == 1, "response-zero controls do not share noise and base settings")
    for _, group in labels.loc[labels.block == "control"].groupby("i"):
        by_j = group.set_index("j")["index"].to_dict()
        _require(set(by_j) == set(range(1, 8)) and len(group) == 7, "incomplete implementation controls")
        expected = {1: ("before", None, 0.0, 0.0), 2: ("before", None, 0.1, 0.0),
                    3: ("before", None, 0.0, 0.1), 4: ("ramp", 0.05, 0.05, 0.05),
                    5: ("ramp", 0.1, 0.05, 0.05), 6: ("tenure", 0.0, 0.05, 0.05),
                    7: ("tenure", 0.2, 0.05, 0.05)}
        keys = set()
        for j, index in by_j.items():
            family, value, renewal, entry = expected[j]
            row, label = rows[index], labels.iloc[index]
            _require(label["family"] == family and row["mechanism"] == _mechanism(family, value) and
                     (row["renewal_response"], row["entry_response"]) == (renewal, entry),
                     f"implementation control {j} settings differ")
            yield_pp = row["fitted_outside_yield_pp"] if j <= 3 else 5.0
            _require(row["outside_yield_pp"] == yield_pp, f"implementation control {j} yield differs")
            keys.add((row["seed"], row["draw"], row["model"], row["origin"], row["fitted_outside_yield_pp"]))
        _require(len(keys) == 1, "implementation controls do not share noise and base settings")


def validate_pairing(rows, labels):
    """Check every declared baseline, including its seed, draw and responses."""
    _require(len(rows) == len(labels) > 0, "one label is required for every row")
    _require(list(labels["index"]) == list(range(len(rows))), "labels must preserve row order")
    used = set()
    for i, (row, label) in enumerate(zip(rows, labels.to_dict("records"))):
        _require(label["yield_pp"] == row["outside_yield_pp"], f"yield label differs at {i}")
        partner = label["baseline"]
        if label["block"] == "baseline":
            _require(label["family"] == "chain" and partner is None and
                     row["mechanism"] == {"name": "ChainReward"}, f"invalid baseline row {i}")
        else:
            _require(label["family"] in FAMILIES, f"unknown family at {i}")
            family, mechanism = label["family"], row["mechanism"]
            field = FAMILY_INPUTS[family]
            value = mechanism.get(field) if field else None
            if field:
                low, high = {"ramp": (0.05, 0.1), "tenure": (0.0, 0.2), "quadratic": (1.0, 3.0)}[family]
                _require(isinstance(value, (int, float)) and not isinstance(value, bool) and
                         math.isfinite(value) and low <= value <= high, f"invalid family input at {i}")
            _require(mechanism == _mechanism(family, value), f"family mechanism differs at {i}")
            _require(type(partner) is int and 0 <= partner < len(rows) and partner != i,
                     f"invalid baseline reference at {i}")
            _require(labels.iloc[partner]["block"] == "baseline", f"wrong baseline role at {i}")
            _require(rows[partner] == {**row, "mechanism": {"name": "ChainReward"}},
                     f"baseline settings differ at {i}")
            used.add(partner)
    expected = set(labels.loc[labels.block == "baseline", "index"])
    _require(used == expected, "unreferenced or omitted baseline")
    _control_metadata(rows, labels)


def read_bundle(directory: Path, expected_hashes: dict[str, str]) -> Bundle:
    """Read exactly the four externally pinned files before parsing their contents."""
    _require(set(expected_hashes) == set(BUNDLE_FILES), "declare all four bundle hashes")
    bodies = {name: (directory / name).read_bytes() for name in BUNDLE_FILES}
    for name, body in bodies.items():
        _require(sha256(body) == expected_hashes[name], f"changed bundle bytes: {name}")
    design = json.loads(bodies["design.json"])
    rows = json.loads(bodies["rows.json"])
    _require(design["generator"] == "explicit" and design["runs"] == 1,
             "explicit single-trajectory design required")
    _require(len(design["models"]) == len(design["origins"]) == 1, "one model and origin required")
    _require(str(design["origins"][0]) < "2025-11-19", "origin reaches protected period")
    _require(design["rows"] == len(rows) and len(rows) > 0, "design cardinality differs")
    _require(design["rows_sha256"] == expected_hashes["rows.json"] and
             design["draws_sha256"] == expected_hashes["draws.parquet"], "design input hashes differ")
    labels = pd.read_csv(io.BytesIO(bodies["labels.csv"]), dtype=str, keep_default_na=False)
    _require({"index", "family", "yield_pp", "block", "i", "j", "baseline"} <= set(labels),
             "label schema incomplete")
    for name in ("index", "i"):
        labels[name] = labels[name].map(lambda v, key=name: _integer(v, key))
    for name in ("j", "baseline"):
        labels[name] = pd.Series([None if v == "" else _integer(v, name) for v in labels[name]], dtype=object)
    labels["yield_pp"] = labels["yield_pp"].astype(float)
    with tempfile.TemporaryDirectory(prefix="paired-draw-snapshot-") as scratch:
        path = Path(scratch) / "draws.parquet"
        path.write_bytes(bodies["draws.parquet"])
        draws = duckdb.sql("SELECT count(*) FROM read_parquet(?)", params=[str(path)]).fetchone()[0]
    for i, row in enumerate(rows):
        _require(type(row["seed"]) is int and row["seed"] >= 0 and
                 type(row["draw"]) is int and 0 <= row["draw"] < draws, f"invalid noise key at {i}")
        _require(row["model"] == design["models"][0] and row["origin"] == design["origins"][0],
                 f"mixed origin or model at {i}")
        _require(all(not isinstance(row[k], bool) and math.isfinite(row[k]) for k in
                     ("renewal_response", "entry_response", "outside_yield_pp", "fitted_outside_yield_pp")),
                 f"nonfinite response or yield at {i}")
    validate_pairing(rows, labels)
    return Bundle(design, tuple(rows), labels, dict(expected_hashes), draws)


def rehearsal_selection(bundle: Bundle) -> dict:
    """Propose the declared small subset, preserving original and local indices."""
    labels = bundle.labels
    selected = labels.loc[(labels.block.isin(["A", "B", "AB", "BA"]) & (labels.i < 16)) |
                          ((labels.block == "noise") & (labels.i == 0)) |
                          (labels.block.isin(["zero", "stress", "control"]) & (labels.i < 2)), "index"]
    selected = sorted(set(selected) | {labels.iloc[i]["baseline"] for i in selected})
    mapping = {original: local for local, original in enumerate(selected)}
    subset = labels.iloc[selected].copy()
    subset.insert(0, "original_index", subset["index"])
    subset["index"] = range(len(subset))
    subset["baseline"] = pd.Series([None if v is None else mapping[v] for v in subset.baseline],
                                   index=subset.index, dtype=object)
    validate_pairing([bundle.rows[i] for i in selected], subset.reset_index(drop=True))
    return {"schema": "paired-rehearsal-selection/v1", "source_hashes": bundle.hashes,
            "original_indices": selected, "rows": len(selected),
            "design_rows": int((subset.block != "baseline").sum()),
            "baseline_rows": int((subset.block == "baseline").sum()),
            "coverage": subset.groupby(["family", "yield_pp", "block"], dropna=False).size().reset_index(name="rows").to_dict("records"),
            "labels": subset.to_dict("records"), "simulation_executed": False}


def expected_cells(design):
    spec = design["reducer"]
    _require(spec["kind"] == "kpis", "KPI reducer required")
    horizons = spec["horizons"]
    _require(len(set(horizons)) == len(horizons) and set(horizons) == {180, 365},
             "both declared horizons required")
    cells = {(m, h, "") for m in MEASURES for h in horizons}
    cells.update(("return_margin", h, level) for level in spec["operating_costs"] for h in horizons)
    return cells


def validate_outputs(table: pd.DataFrame, bundle: Bundle, receipt: dict):
    """Validate complete cell accounting and exact producer row identities."""
    required = {*CELL, "row_id", "value", "base_specification", "specification", "design",
                *set(bundle.rows[0])}
    _require(required <= set(table) and not table.empty, "output schema incomplete")
    _require(not table[list(required)].isna().any().any() and not table.duplicated(list(CELL)).any(),
             "null or duplicate output cell")
    _require(not any(isinstance(v, (bool, np.bool_)) or not math.isfinite(v) for v in table.value),
             "nonfinite or boolean KPI")
    _require(all(pd.api.types.is_integer_dtype(table[k]) and not pd.api.types.is_bool_dtype(table[k])
                 for k in ("index", "run", "horizon_days", "seed", "draw")), "integer metadata required")
    _require(set(table["index"]) == set(range(len(bundle.rows))) and set(table.run) == {1},
             "missing, extra or repeated trajectory")
    _require(len(receipt["model"]["specifications"]) == 1, "one base specification required")
    base = receipt["model"]["specifications"][0]
    _require(sha256(json.dumps(base["settings"], sort_keys=True, default=str).encode())[:16] == base["hash"],
             "base specification hash differs")
    cells, identities = expected_cells(bundle.design), []
    groups = dict(tuple(table.groupby("index", sort=False)))
    for i, settings in enumerate(bundle.rows):
        row = {"design": bundle.design.get("name", "explicit"), **settings, "index": i,
               "origin": bundle.design["origins"][0], "model": bundle.design["models"][0]}
        identity = row_id(row, base["hash"])
        identities.append(identity)
        one = groups[i]
        _require(set(one.row_id) == {identity} and set(one.base_specification) == {base["hash"]},
                 f"row/base identity differs at {i}")
        _require(one.specification.nunique() == 1, f"mixed row specifications at {i}")
        for name, value in row.items():
            actual = json.dumps(value, sort_keys=True) if isinstance(value, dict) else value
            _require((one[name] == actual).all(), f"changed setting {name} at {i}")
        _require(set(one[["measure", "horizon_days", "cost_level"]].itertuples(index=False, name=None)) == cells,
                 f"incomplete or extra KPI cells at {i}")
    _require(set(identities) == set(receipt["sweep"]["files"]), "receipt row identities differ")
    _require(design_hash([{"identity": i} for i in identities], "design") == receipt["sweep"]["design_hash"],
             "ordered design identity differs")
    _require(len(table) == receipt["output"]["rows"], "output record count differs")
    return table.sort_values(list(CELL), kind="stable").reset_index(drop=True)


def read_outputs(directory: Path, bundle: Bundle, *, code_commit: str, pin_sha256: str, receipt_sha256: str):
    """Authenticate a complete receipt and hash-checked Parquet snapshots."""
    receipt_bytes = (directory / "receipt.json").read_bytes()
    _require(sha256(receipt_bytes) == receipt_sha256, "receipt differs from external freeze")
    receipt = json.loads(receipt_bytes)
    _require(receipt["schema_version"] == "avalanche-run-receipt/v1", "unsupported run receipt schema")
    body = {k: v for k, v in receipt.items() if k != "receipt_id"}
    _require(sha256(canonical_bytes(body))[:16] == receipt["receipt_id"], "changed receipt")
    _require(receipt["code"]["commit"] == code_commit and receipt["code"]["dirty"] is False,
             "unaccepted or dirty producer code")
    _require(receipt["inputs"]["pin_file_sha256"] == pin_sha256, "pin differs from freeze")
    sweep = receipt["sweep"]
    _require(sweep["complete"] is True and sweep["rows_planned"] == len(bundle.rows), "incomplete sweep")
    _require(sweep["rows_written"] + sweep["rows_skipped"] == len(bundle.rows), "run accounting differs")
    _require(all(item.get("passed") is True for item in receipt["conservation"]), "failed conservation check")
    for key in ("rows_sha256", "draws_sha256", "models", "origins", "runs", "timesteps", "reducer"):
        _require(sweep["design_file"][key] == bundle.design[key], f"receipt design differs: {key}")
    _require(sha256(canonical_bytes(sweep["files"])) == receipt["output"]["sha256"], "output inventory hash differs")
    paths = {p.stem: p for p in directory.glob("*.parquet")}
    _require(set(paths) == set(sweep["files"]), "missing or extra output file")
    frames, raw_hashes = [], {}
    with tempfile.TemporaryDirectory(prefix="paired-output-snapshot-") as scratch:
        for identity, path in sorted(paths.items()):
            _require(re.fullmatch(r"[0-9a-f]{16}", identity) is not None, "invalid output identity")
            data = path.read_bytes()
            raw_hashes[identity] = sha256(data)
            snapshot = Path(scratch) / f"{identity}.parquet"
            snapshot.write_bytes(data)
            frame = duckdb.sql("SELECT * FROM read_parquet(?)", params=[str(snapshot)]).df()
            values = frame.drop(columns=["worker_peak_mib"], errors="ignore")
            values = values[sorted(values.columns)].sort_values(sorted(values.columns), kind="mergesort")
            _require(sha256(values.to_csv(index=False).encode()) == sweep["files"][identity],
                     f"changed output contents: {identity}")
            _require(set(frame.row_id) == {identity}, "file contains another row")
            frames.append(frame)
    return validate_outputs(pd.concat(frames, ignore_index=True), bundle, receipt), receipt, raw_hashes


def relative_kpis(table: pd.DataFrame, bundle: Bundle) -> pd.DataFrame:
    """Reconstruct each design row's three ratios from its matched baseline."""
    validate_pairing(bundle.rows, bundle.labels)
    primitive = table.loc[table.measure.isin(PRIMITIVES)]
    _require(not primitive.duplicated(["index", "run", "horizon_days", "measure"]).any(),
             "duplicate absolute primitive")
    lookup = primitive.set_index(["index", "run", "horizon_days", "measure"])["value"]
    names = {"issued_navax": "issuance_saved", "validator_stake_navax": "validator_stake_retained",
             "active_validators": "active_validators_retained"}
    result = []
    for label in bundle.labels.to_dict("records"):
        if label["block"] == "baseline":
            continue
        for horizon in bundle.design["reducer"]["horizons"]:
            for measure in PRIMITIVES:
                key = (label["index"], 1, horizon, measure)
                base_key = (label["baseline"], 1, horizon, measure)
                _require(key in lookup and base_key in lookup, "missing paired primitive")
                value, denominator = lookup[key], lookup[base_key]
                _require(math.isfinite(value) and math.isfinite(denominator) and denominator > 0,
                         "nonfinite or nonpositive paired denominator")
                ratio = float(value) / float(denominator)
                _require(math.isfinite(ratio), "nonfinite derived paired ratio")
                result.append({"index": label["index"], "baseline": label["baseline"], "run": 1,
                               "measure": names[measure], "horizon_days": horizon, "cost_level": "",
                               "value": 1 - ratio if measure == "issued_navax" else ratio})
    return pd.DataFrame(result)


def control_checks(table: pd.DataFrame, bundle: Bundle) -> pd.DataFrame:
    """Apply only the E2 zero and active controls present in the frozen subset."""
    validate_pairing(bundle.rows, bundle.labels)
    _require(all(not isinstance(v, (bool, np.bool_)) and math.isfinite(v) for v in table.value),
             "nonfinite or boolean control output")
    wide = table.pivot(index="index", columns=["measure", "horizon_days", "cost_level"], values="value")
    labels, checks = bundle.labels, []
    for (yield_pp, i), group in labels.loc[labels.block == "zero"].groupby(["yield_pp", "i"]):
        _require(set(group.family) == set(FAMILIES) and len(group) == 4, "incomplete response-zero family set")
        for measure in ("active_validators", "validator_stake_navax"):
            for horizon in bundle.design["reducer"]["horizons"]:
                values = wide.loc[group["index"], (measure, horizon, "")]
                checks.append({"control": "response-zero", "yield_pp": yield_pp, "i": i,
                               "measure": measure, "horizon_days": horizon, "passed": values.nunique() == 1})
    controls = labels.loc[labels.block == "control"]
    for i, group in controls.groupby("i"):
        by_j = group.set_index("j")["index"].to_dict()
        _require(set(by_j) == set(range(1, 8)), "incomplete implementation controls")
        fb = wide.loc[[by_j[j] for j in (1, 2, 3)]]
        checks.append({"control": "fitted-yield-before", "i": i, "passed": bool((fb.nunique() == 1).all())})
        for name, low, high in (("ramp-active", 4, 5), ("tenure-active", 6, 7)):
            for horizon in bundle.design["reducer"]["horizons"]:
                col = ("issued_navax", horizon, "")
                checks.append({"control": name, "i": i, "horizon_days": horizon,
                               "passed": bool(wide.loc[by_j[low], col] != wide.loc[by_j[high], col])})
    _require(checks, "no declared controls present")
    return pd.DataFrame(checks)
