"""The evidence receipt of a model run: what ran, on which inputs, with which seeds, what it checked, and what it made.

v0, unreviewed. One JSON file per run or sweep, written beside the run's long table. It joins the model's
specification (class, run controls, and settings, with the engine's 16-hex specification hash), the pin file that
names each input run with its Parquet sha256, the seeds, the conservation checks, the table's row counts and sha256,
the code commit, and the timings. ``check`` recomputes what it can and refuses a receipt whose pins no longer pass
``pins.verify``, whose conservation checks failed, or whose table differs.

The receipt never imports the model: it reads the specification dicts a run hands it, so it stays below the engine's
callers and above the data it cites.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

from .. import __version__, pins
from ..catalog import DataError, canonical_bytes, now, sha256

SCHEMA = "avalanche-run-receipt/v1"
KEY = ["simulation", "run", "timestep", "variable"]


def specification_hash(specification: dict[str, Any]) -> str:
    """The engine's hash of a specification: sha256 of its sorted JSON, first 16 hex digits."""
    return hashlib.sha256(json.dumps(specification, sort_keys=True, default=str).encode()).hexdigest()[:16]


def table_sha256(table: pd.DataFrame) -> str:
    """A hash of the long table that does not depend on row order or on a file format: sorted rows as CSV."""
    ordered = table.sort_values([column for column in KEY if column in table.columns], kind="mergesort")
    return sha256(ordered[sorted(ordered.columns)].to_csv(index=False).encode())


def code_commit(directory: Path | None = None) -> dict[str, Any]:
    """The commit the code ran from, and whether tracked source files differed from it."""
    def git(*arguments: str) -> str:
        return subprocess.run(["git", *arguments], cwd=directory, check=True, capture_output=True, text=True).stdout.strip()
    try:
        return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain", "--untracked-files=no", "--", "src")),
                "package_version": __version__}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None, "package_version": __version__}


def build(table: pd.DataFrame, specifications: list[dict[str, Any]], pin_file: Path, seeds: list[int],
          conservation: list[dict[str, Any]], started_at: str, finished_at: str, seconds: float,
          code: dict[str, Any] | None = None, table_path: str | None = None) -> dict[str, Any]:
    """The receipt of one run or sweep. ``conservation`` holds one entry per check: name, passed, worst error, tolerance."""
    pinned = pins.read(pin_file)
    hashes = [specification_hash(item) for item in specifications]
    if "specification" in table.columns and sorted(set(table["specification"])) != sorted(set(hashes)):
        raise DataError("the table's specification column does not match the specifications given")
    receipt = {
        "schema_version": SCHEMA,
        "created_at": now(),
        "code": code if code is not None else code_commit(),
        "model": {"class": specifications[0].get("model") if specifications else None,
                  "specifications": [{"hash": digest, "settings": item} for digest, item in zip(hashes, specifications)]},
        "inputs": {"pin_name": pinned["name"], "pin_file": str(pin_file), "pin_file_sha256": sha256(pin_file.read_bytes()),
                   "runs": [{key: entry[key] for key in ("dataset_id", "run", "sha256")} for entry in pinned["runs"]]},
        "seeds": list(seeds),
        "conservation": conservation,
        "output": {"path": table_path, "rows": len(table), "columns": list(table.columns), "sha256": table_sha256(table),
                   "rows_by_variable": {str(key): int(value) for key, value in table.groupby("variable").size().items()} if "variable" in table else {}},
        "timings": {"started_at": started_at, "finished_at": finished_at, "seconds": round(seconds, 3)},
    }
    receipt["receipt_id"] = sha256(canonical_bytes(receipt))[:16]
    return receipt


def check(receipt: dict[str, Any], table: pd.DataFrame | None = None, root: Path | None = None) -> list[str]:
    """What makes the receipt unfit as evidence. An empty list means it stands."""
    findings = []
    if receipt.get("schema_version") != SCHEMA:
        return [f"not a run receipt: schema {receipt.get('schema_version')}"]
    body = {key: value for key, value in receipt.items() if key != "receipt_id"}
    if sha256(canonical_bytes(body))[:16] != receipt.get("receipt_id"):
        findings.append("the receipt was edited after it was written")
    for item in receipt["model"]["specifications"]:
        if specification_hash(item["settings"]) != item["hash"]:
            findings.append(f"specification {item['hash']} does not hash to its settings")
    pin_file = Path(receipt["inputs"]["pin_file"])
    if not pin_file.is_file():
        findings.append(f"pin file {pin_file} is missing")
    else:
        if sha256(pin_file.read_bytes()) != receipt["inputs"]["pin_file_sha256"]:
            findings.append(f"pin file {pin_file} changed since the run")
        findings.extend(f"pin: {finding}" for finding in pins.verify(pin_file, root))
    findings.extend(f"conservation check {item['name']} failed" for item in receipt["conservation"] if not item.get("passed"))
    if receipt["code"].get("commit") is None:
        findings.append("the code commit is unknown")
    elif receipt["code"].get("dirty"):
        findings.append(f"the code differed from commit {receipt['code']['commit'][:12]}")
    if table is not None and table_sha256(table) != receipt["output"]["sha256"]:
        findings.append("the table differs from the one the receipt describes")
    return findings


def write(receipt: dict[str, Any], path: Path, table: pd.DataFrame | None = None, root: Path | None = None) -> Path:
    """Write the receipt only if it stands. A receipt whose pins fail ``pin-check`` is refused."""
    findings = check(receipt, table, root)
    if findings:
        raise DataError("receipt refused: " + "; ".join(findings))
    if path.exists():
        raise DataError(f"receipt already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(receipt))
    return path
