"""Data catalog loading, hashing, and shared helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CATALOG = DATA_DIR / "data-catalog.json"
SCHEMA = DATA_DIR / "data-catalog.schema.json"


class DataError(RuntimeError):
    """The requested data operation could not complete safely."""


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_catalog(path: Path = CATALOG, schema_path: Path = SCHEMA) -> dict[str, Any]:
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(catalog)
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError) as error:
        raise DataError(f"invalid data catalog: {error}") from error
    source_ids = [item["id"] for item in catalog["sources"]]
    dataset_ids = [item["id"] for item in catalog["datasets"]]
    if len(source_ids) != len(set(source_ids)) or len(dataset_ids) != len(set(dataset_ids)):
        raise DataError("data catalog contains duplicate source or dataset IDs")
    for definition in catalog["datasets"]:
        if definition["source_id"] not in source_ids:
            raise DataError(f"dataset has unknown source: {definition['id']}")
        provider = source(catalog, definition["source_id"])
        kind = "endpoints" if "endpoints" in provider else "queries"
        input_ids = [item["id"] for item in provider[kind]]
        if len(input_ids) != len(set(input_ids)):
            raise DataError(f"source has duplicate {kind[:-1]} IDs: {provider['id']}")
        wanted = definition.get("endpoint_ids" if kind == "endpoints" else "query_ids")
        if wanted is None:
            raise DataError(f"dataset inputs do not match the source type: {definition['id']}")
        missing = sorted(set(wanted) - set(input_ids))
        if missing:
            raise DataError(f"dataset has unknown {kind}: {definition['id']}: {', '.join(missing)}")
    return catalog


def contract_hash(catalog: dict[str, Any], dataset_id: str) -> str:
    """Hash the records that define one dataset: its source and its dataset entry."""
    definition = dataset(catalog, dataset_id)
    return sha256(canonical_bytes({"source": source(catalog, definition["source_id"]), "dataset": definition}))


def source(catalog: dict[str, Any], source_id: str) -> dict[str, Any]:
    for item in catalog["sources"]:
        if item["id"] == source_id:
            return item
    raise DataError(f"unknown source: {source_id}")


def dataset(catalog: dict[str, Any], dataset_id: str) -> dict[str, Any]:
    for item in catalog["datasets"]:
        if item["id"] == dataset_id:
            return item
    raise DataError(f"unknown dataset: {dataset_id}")
