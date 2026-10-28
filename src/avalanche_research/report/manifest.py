"""The sweep manifest: the declared role of every column of a sweep's wide table.

A wide table has one row per simulated run and horizon. The manifest, `sweep-manifest.json`, gives each column one
role, so the report reads settings, scenarios and KPIs from a declaration and never from a column's name:

- ``setting``: a design setting the Foundation could choose, swept within a mechanism family;
- ``scenario``: an outside condition the Foundation does not choose, such as the outside yield;
- ``behaviour``: a validator response the model draws per run, such as the renewal response;
- ``kpi``: a measure of the run, read by the utility specification;
- ``id``: everything else, such as keys, seeds, blocks and draws.

Beside the roles, the manifest names the family, horizon, block and pairing columns, the rows that hold the paired
baseline runs, the blocks to analyse and the column that groups runs sharing their random draws. Every column of the
table must be listed, so a new setting with a new name stops the report instead of being read as something else.

`draft` writes a first manifest from a table's column names and types, for a person to check before use.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

SCHEMA = "sweep-manifest/v1"
ROLES = ("setting", "scenario", "behaviour", "kpi", "id")


class ManifestError(ValueError):
    """The manifest does not describe the wide table."""


def load(path: Path | str) -> dict:
    manifest = json.loads(Path(path).expanduser().read_text())
    check_shape(manifest)
    return manifest


def check_shape(manifest: dict) -> None:
    if manifest.get("schema") != SCHEMA:
        raise ManifestError(f"manifest schema must be {SCHEMA}, found {manifest.get('schema')!r}")
    columns = manifest.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ManifestError("manifest has no columns")
    seen = set()
    for c in columns:
        if not isinstance(c, dict) or "name" not in c or "role" not in c:
            raise ManifestError(f"each column needs a name and a role: {c!r}")
        if c["role"] not in ROLES:
            raise ManifestError(f"column {c['name']}: unknown role {c['role']!r}, expected one of {', '.join(ROLES)}")
        if c["name"] in seen:
            raise ManifestError(f"column {c['name']} is listed twice")
        seen.add(c["name"])
    family = manifest.get("family_column")
    if not family:
        raise ManifestError("manifest names no family_column")
    for key in ("family_column", "horizon_column", "block_column", "split_group"):
        name = manifest.get(key)
        if name and name not in seen:
            raise ManifestError(f"{key} {name} is not a listed column")
        if name and role_of(manifest, name) != "id":
            raise ManifestError(f"{key} {name} must have the role id")
    pair = manifest.get("pair") or {}
    for key in ("row", "baseline_row"):
        if pair.get(key) and pair[key] not in seen:
            raise ManifestError(f"pair.{key} {pair[key]} is not a listed column")


def role_of(manifest: dict, name: str) -> str | None:
    return next((c["role"] for c in manifest["columns"] if c["name"] == name), None)


def names(manifest: dict, role: str) -> list[str]:
    """The columns of one role, in the manifest's order."""
    return [c["name"] for c in manifest["columns"] if c["role"] == role]


def labels(manifest: dict) -> dict:
    """Display labels the manifest gives its columns: {column: {label, unit, scale}}."""
    return {c["name"]: {k: c[k] for k in ("label", "unit", "scale") if k in c}
            for c in manifest["columns"] if any(k in c for k in ("label", "unit", "scale"))}


def check_table(manifest: dict, columns: list[str] | set[str]) -> None:
    """Every column of the table is listed and every listed column is in the table."""
    listed = {c["name"] for c in manifest["columns"]}
    present = set(columns)
    unlisted, absent = sorted(present - listed), sorted(listed - present)
    problems = []
    if unlisted:
        problems.append(f"columns without a role in the manifest: {unlisted}")
    if absent:
        problems.append(f"manifest columns missing from the table: {absent}")
    if problems:
        raise ManifestError("; ".join(problems))


# Drafting --------------------------------------------------------------------------------------------------------

KNOWN_SETTINGS = [
    "target_min_rate", "boost_max", "exponent", "ramp_days", "min_rate", "max_rate", "min_stake_duration",
    "max_stake_duration", "min_lockup_days", "max_lockup_days", "lockup_days", "consumption_rate", "target_yield",
    "yield_target", "delegation_fee", "min_delegation_fee",
]
KNOWN_SCENARIOS = [
    "yield_pp", "outside_yield_pp", "market_condition", "market", "price_path", "price_scenario", "avax_price_path",
    "price_regime", "network_growth", "growth_scenario", "growth", "scenario",
]
KNOWN_BEHAVIOUR = ["renewal_response", "entry_response"]
KNOWN_IDS = {
    "index", "block", "i", "j", "baseline", "seed", "draw", "model", "origin", "renewal_band", "entry_band",
    "unit_id", "row_id", "baseline_row_id", "horizon", "horizon_days", "family", "run_id", "subset", "simulation",
    "timestep", "substep",
} | {f"u{k}" for k in range(1, 10)}
FLOAT_TYPES = ("DOUBLE", "FLOAT", "DECIMAL", "REAL")
CATEGORY_TYPES = ("VARCHAR", "BOOLEAN", "INT", "BIGINT", "SMALLINT", "TINYINT", "UBIGINT", "UINTEGER")


def draft(wide: Path | str, baseline_families=("chain",), baseline_blocks=("baseline",),
          excluded_blocks=("control",)) -> dict:
    """A first manifest for a wide table, from its column names and types. A person checks every role before use."""
    wide = str(Path(wide).expanduser().resolve())
    con = duckdb.connect()
    schema = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [wide]).df()
    types = dict(zip(schema.column_name, schema.column_type))
    cols = list(types)
    if "family" not in types:
        raise ManifestError("the table has no family column, so the draft cannot tell designs apart")
    base_where = f"(family IN ({','.join(repr(f) for f in baseline_families)})"
    base_where += f" OR block IN ({','.join(repr(b) for b in baseline_blocks)}))" if "block" in types else ")"
    design_where = f"NOT {base_where}"
    blocks = None
    if "block" in types:
        present = set(con.execute("SELECT DISTINCT block FROM read_parquet(?)", [wide]).df().block)
        blocks = ["A", "B"] if {"A", "B"} <= present else sorted(present - set(excluded_blocks) - set(baseline_blocks))
        design_where += f" AND block IN ({','.join(repr(b) for b in blocks)})"
    role = {}
    for c in cols:
        if c in KNOWN_IDS:
            role[c] = "id"
        elif c in KNOWN_SETTINGS:
            role[c] = "setting"
        elif c in KNOWN_SCENARIOS:
            role[c] = "scenario"
        elif c in KNOWN_BEHAVIOUR:
            role[c] = "behaviour"
    for c in cols:
        if c in role:
            continue
        t = types[c].upper()
        if t.startswith(FLOAT_TYPES):
            per = con.execute(f'SELECT family, count("{c}") nn, count(DISTINCT "{c}") d FROM read_parquet(?) '
                              f"WHERE {design_where} GROUP BY 1", [wide]).df()
            role[c] = "setting" if (per.nn == 0).any() and ((per.nn > 0) & (per.d > 1)).any() else "kpi"
        elif t.startswith(CATEGORY_TYPES):
            n = con.execute(f'SELECT count(DISTINCT "{c}") FROM read_parquet(?) WHERE {design_where}',
                            [wide]).fetchone()[0]
            role[c] = "scenario" if 2 <= n <= 20 else "id"
        else:
            role[c] = "id"
    manifest = {
        "schema": SCHEMA,
        "status": "Drafted from column names and types. Check every role before use.",
        "family_column": "family",
        "horizon_column": "horizon_days" if "horizon_days" in types else None,
        "block_column": "block" if "block" in types else None,
        "split_group": "seed" if "seed" in types else None,
        "pair": {"row": "row_id", "baseline_row": "baseline_row_id"}
        if {"row_id", "baseline_row_id"} <= set(cols) else None,
        "baseline": {"families": list(baseline_families),
                     "blocks": list(baseline_blocks) if "block" in types else []},
        "analysis_blocks": blocks,
        "columns": [{"name": c, "role": role[c]} for c in cols],
    }
    check_shape(manifest)
    return manifest


def write(manifest: dict, path: Path | str) -> Path:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=1) + "\n")
    return path
