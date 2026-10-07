"""Operator attributions: one row per name or role attached to a reward address, a funding address, or a node.

The rows are curated in ``data/operator-attributions.json`` under BCRG's attribution standard: each carries its evidence
tier (``AS1`` a protocol or contract registry to ``AS5`` our own clustering), its class (EVIDENCE, INFERENCE, NOT
DETERMINED), its source, and the row it corrects, if any. This table joins them to ``derived.operators``, so each
attribution of a reward address shows the operator's nodes and fleets. The file is hashed into the receipt, so a run
names the exact attributions it holds. ``derived.operators`` reads its named agents from the same file.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from ... import __version__, datasets
from ...core.catalog import (
    DATA_DIR,
    DataError,
    canonical_bytes,
    contract_hash,
    dataset,
    load_catalog,
    now,
    sha256,
)

DATASET_ID = "derived.operator-attributions"
DATASET_IDS = (DATASET_ID,)
SOURCE_ID = "derived"
TABLE = "operator-attributions"
ATTRIBUTIONS = DATA_DIR / "operator-attributions.json"
INPUTS = {"operators": "derived.operators"}
TIERS = ("AS1", "AS2", "AS3", "AS4", "AS5")
CLASSES = ("EVIDENCE", "INFERENCE", "NOT DETERMINED")
SUBJECT_KINDS = ("reward-address", "funding-address", "node")
FIELDS = ("attribution_id", "subject_kind", "subject", "name", "statement", "tier", "class", "source", "supporting_sources",
          "captured_on", "data_run", "agent", "replaces")
TABLE_COLUMNS = {
    "attribution_id": "VARCHAR", "subject_kind": "VARCHAR", "subject": "VARCHAR", "name": "VARCHAR", "statement": "VARCHAR",
    "tier": "VARCHAR", "class": "VARCHAR", "source": "VARCHAR", "supporting_sources": "VARCHAR", "captured_on": "DATE",
    "data_run": "VARCHAR", "agent": "VARCHAR", "replaces": "VARCHAR",
    "operator_id": "VARCHAR", "operator_nodes": "BIGINT", "active_nodes": "BIGINT", "fleets": "BIGINT", "fleets_shared_with_other_operators": "BIGINT",
}


def load_attributions(path: Path = ATTRIBUTIONS) -> tuple[list[dict[str, Any]], str]:
    """The curated rows and the file's hash, after the standard's rules: known tiers, classes, and subject kinds, one row
    per ID, a correction that names an existing row, and no EVIDENCE on an AS4 label or AS5 clustering alone."""
    try:
        body = path.read_bytes()
        value = json.loads(body)
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"unreadable attribution file: {error}") from error
    if value.get("schema_version") != "operator-attributions/v1":
        raise DataError("unsupported attribution file")
    rows = value["attributions"]
    ids = [row["attribution_id"] for row in rows]
    problems = []
    if len(ids) != len(set(ids)):
        problems.append("an attribution ID repeats")
    for row in rows:
        if set(row) != set(FIELDS):
            problems.append(f"{row.get('attribution_id')} does not have exactly the standard's fields")
            continue
        if row["tier"] not in TIERS or row["class"] not in CLASSES or row["subject_kind"] not in SUBJECT_KINDS:
            problems.append(f"{row['attribution_id']} has an unknown tier, class, or subject kind")
        if row["class"] == "EVIDENCE" and row["tier"] in ("AS4", "AS5"):
            problems.append(f"{row['attribution_id']} is EVIDENCE on an {row['tier']} source alone")
        if row["class"] != "NOT DETERMINED" and not row["name"]:
            problems.append(f"{row['attribution_id']} attributes no name but is not NOT DETERMINED")
        if row["replaces"] is not None and row["replaces"] not in ids:
            problems.append(f"{row['attribution_id']} replaces an unknown row")
        if not str(row["source"]).startswith("https://"):
            problems.append(f"{row['attribution_id']} cites no public source")
    if problems:
        raise DataError("; ".join(problems))
    return rows, sha256(body)


def named_agents(path: Path = ATTRIBUTIONS) -> dict[str, tuple[str, str]]:
    """Reward address to (name, evidence) for ``derived.operators``: the address's named row that no later row replaces,
    or "unnamed operator" when every row about it leaves the name open."""
    rows, _ = load_attributions(path)
    replaced = {row["replaces"] for row in rows if row["replaces"]}
    agents: dict[str, tuple[str, str]] = {}
    for row in rows:
        if row["subject_kind"] != "reward-address" or row["attribution_id"] in replaced:
            continue
        evidence = f"{row['attribution_id']} {row['tier']} {row['class']}: {row['source']}"
        if row["name"]:
            agents[row["subject"]] = (row["name"], evidence)
        else:
            agents.setdefault(row["subject"], ("unnamed operator", evidence))
    return agents


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    raise DataError(f"{dataset_id} is derived; use `avalanche data derive`")


capture = build_preview = build = capture_preview


def _input(pinned: dict[str, str] | None, root: Path | None) -> dict[str, Any]:
    pinned = pinned or {}
    if set(pinned) - set(INPUTS.values()):
        raise DataError(f"the only input of {DATASET_ID} is derived.operators")
    record = datasets.receipt("derived.operators", pinned.get("derived.operators"), root)
    parquet = datasets.parquet_path("derived.operators", record["run"], root)
    body = parquet.read_bytes()
    return {"input_id": "operators", "dataset_id": "derived.operators", "run": record["run"], "capture_id": record["capture"]["capture_id"],
            "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet}


def compute(rows: list[dict[str, Any]], operators: Path) -> list[tuple[Any, ...]]:
    connection = duckdb.connect()
    try:
        connection.execute("CREATE TABLE a(" + ", ".join(f'"{name}" {TABLE_COLUMNS[name]}' for name in FIELDS) + ")")
        connection.executemany(f"INSERT INTO a VALUES ({', '.join('?' for _ in FIELDS)})",
                               [[json.dumps(row[name]) if name == "supporting_sources" else row[name] for name in FIELDS] for row in rows])
        quoted = str(operators).replace("'", "''")
        connection.execute(f"CREATE VIEW o AS SELECT * FROM read_parquet('{quoted}')")
        return connection.execute("""
            WITH fleets AS (SELECT fleet_id, count(DISTINCT operator_id) AS operators FROM o GROUP BY 1),
                 by_operator AS (
                     SELECT o.operator_id, count(*) AS nodes, count(*) FILTER (WHERE o.active) AS active,
                            count(DISTINCT o.fleet_id) AS fleets, count(DISTINCT o.fleet_id) FILTER (WHERE f.operators > 1) AS shared
                     FROM o JOIN fleets f USING (fleet_id) GROUP BY 1)
            SELECT a.*, b.operator_id, b.nodes, b.active, b.fleets, b.shared
            FROM a LEFT JOIN by_operator b ON a.subject_kind = 'reward-address' AND b.operator_id = a.subject
            ORDER BY a.attribution_id""").fetchall()
    finally:
        connection.close()


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    rows, file_sha = load_attributions()
    item = _input(pinned, root)
    table = compute(rows, item["path"])
    completed_at = now()
    record = {key: value for key, value in item.items() if key != "path"}
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": [record], "attributions": file_sha}))
    capture_receipt = {
        "schema_version": "derived-capture/v1", "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
        "dataset_id": DATASET_ID, "source_id": SOURCE_ID, "completed_at": completed_at, "contract_sha256": contract_hash(catalog, DATASET_ID),
        "tool": f"avalanche-research@{__version__}", "inputs": [record],
        "parameters": {"attributions_file": "data/operator-attributions.json", "attributions_sha256": file_sha},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "capture").mkdir()
        (temporary / "dataset").mkdir()
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet = temporary / "dataset" / f"{TABLE}.parquet"
        connection = duckdb.connect()
        try:
            connection.execute(f"CREATE TABLE rows({', '.join(f'{chr(34)}{name}{chr(34)} {kind}' for name, kind in TABLE_COLUMNS.items())})")
            connection.executemany(f"INSERT INTO rows VALUES ({', '.join('?' for _ in TABLE_COLUMNS)})", table)
            connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
        finally:
            connection.close()
        classes = {name: sum(row[6] == name for row in table) for name in CLASSES}
        build_receipt = {
            "schema_version": "derived-build/v1", "dataset_id": DATASET_ID, "dataset_schema": dataset(catalog, DATASET_ID)["fields"],
            "source_capture_id": capture_receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": {"rows": len(table), "rows_by_class": classes, "reward_addresses": len({row[2] for row in table if row[1] == "reward-address"}),
                        "attributed_nodes": sum(row[14] or 0 for row in {row[13]: row for row in table if row[13]}.values())},
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "dataset" / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"capture": capture_receipt, "build": build_receipt}


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """The file still hashes as recorded, every named agent of the operator table has a classed row, every attributed
    reward address is an operator, and a rebuild gives the same rows."""
    if against is not None:
        raise DataError(f"{DATASET_ID} takes no --against directory")
    receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    if receipt.get("dataset_id") != DATASET_ID:
        raise DataError(f"not a {DATASET_ID} capture: {capture_dir}")
    findings: list[str] = []
    rows, file_sha = load_attributions()
    if file_sha != receipt["parameters"]["attributions_sha256"]:
        findings.append("the attribution file changed since the capture")
    item = receipt["inputs"][0]
    parquet_in = (datasets.RUNS if root is None else root) / item["run"] / "dataset" / item["parquet"]
    if not parquet_in.is_file() or sha256(parquet_in.read_bytes()) != item["sha256"]:
        findings.append(f"input run missing or changed: {item['run']}")
    summary: dict[str, Any] = {}
    if dataset_dir is not None and not findings:
        connection = duckdb.connect()
        try:
            built = connection.execute("SELECT * FROM read_parquet(?) ORDER BY attribution_id", [str(dataset_dir / f"{TABLE}.parquet")]).fetchall()
            named = {row[0] for row in connection.execute("SELECT DISTINCT operator_id FROM read_parquet(?) WHERE named_agent IS NOT NULL",
                                                          [str(parquet_in)]).fetchall()}
        finally:
            connection.close()
        if [tuple(map(str, row)) for row in built] != [tuple(map(str, row)) for row in compute(rows, parquet_in)]:
            findings.append("a rebuild from the recorded inputs differs")
        attributed = {row[2] for row in built if row[1] == "reward-address"}
        if named - attributed:
            findings.append(f"{len(named - attributed)} named agents of the operator table have no attribution row")
        orphans = [row[0] for row in built if row[1] == "reward-address" and row[13] is None]
        if orphans:
            findings.append(f"attributed reward addresses that are no operator: {', '.join(orphans)}")
        summary = {"rows": len(built), "named_agents": len(named), "orphans": len(orphans)}
    return {"dataset_id": DATASET_ID, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": ["attribution file hash", "attribution standard rules", "input run hash", "named agents attributed", "rebuild"],
            "summary": summary, "findings": findings}
