"""The data catalog: loading it, and each dataset's contract and its hash.

The error, hashing and clock helpers it used to define are in ``core.errors``, ``core.hashing`` and ``core.clock``, and
are imported here, so ``catalog.DataError`` and the others keep working.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from .clock import now  # noqa: F401  (re-exported: providers import it from the catalog)
from .errors import DataError
from .hashing import canonical_bytes, sha256

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
CATALOG = DATA_DIR / "data-catalog.json"
SCHEMA = DATA_DIR / "data-catalog.schema.json"


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
        kind = input_kind(provider)
        input_ids = [item["id"] for item in provider[kind]]
        if len(input_ids) != len(set(input_ids)):
            raise DataError(f"source has duplicate {kind[:-1]} IDs: {provider['id']}")
        if kind == "inputs":
            unknown = sorted({item["dataset_id"] for item in provider["inputs"]} - set(dataset_ids))
            if unknown:
                raise DataError(f"derived source names unknown datasets: {provider['id']}: {', '.join(unknown)}")
        wanted = definition.get(INPUT_ID_KEYS[kind])
        if wanted is None:
            raise DataError(f"dataset inputs do not match the source type: {definition['id']}")
        missing = sorted(set(wanted) - set(input_ids))
        if missing:
            raise DataError(f"dataset has unknown {kind}: {definition['id']}: {', '.join(missing)}")
    return catalog


INPUT_KEYS = ("id", "url", "request_json", "content", "response_fields", "sql", "relations", "parameters", "dataset_id", "role")
INPUT_ID_KEYS = {"endpoints": "endpoint_ids", "queries": "query_ids", "inputs": "input_ids"}


def input_kind(provider: dict[str, Any]) -> str:
    """``endpoints`` for a REST source, ``queries`` for a database share, ``inputs`` for a derived source."""
    for kind in INPUT_ID_KEYS:
        if kind in provider:
            return kind
    raise DataError(f"source declares no inputs: {provider['id']}")


def contract(catalog: dict[str, Any], dataset_id: str) -> dict[str, Any]:
    """The parts of the catalog a capture depends on: the dataset's inputs and its fields.

    Names, descriptions, statuses, consumer studies, provider notes, and observed semantics are documentation and
    may change without invalidating captures. The referenced endpoints or queries and the field list may not.
    """
    definition = dataset(catalog, dataset_id)
    provider = source(catalog, definition["source_id"])
    kind = input_kind(provider)
    wanted = set(definition[INPUT_ID_KEYS[kind]])
    inputs = [
        {key: item[key] for key in INPUT_KEYS if key in item}
        for item in provider[kind] if item["id"] in wanted
    ]
    return {
        "dataset_id": definition["id"],
        "source_id": provider["id"],
        "database": provider.get("database"),
        "schema": provider.get("schema"),
        "inputs": inputs,
        "fields": definition["fields"],
    }


def contract_hash(catalog: dict[str, Any], dataset_id: str) -> str:
    return sha256(canonical_bytes(contract(catalog, dataset_id)))


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
