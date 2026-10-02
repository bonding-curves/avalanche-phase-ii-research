"""Restructure step M1: the catalog, errors, hashing, units and the clock in ``core``, and the old names as aliases.

The pinned hashes were computed by the code before the move, from the catalog written in this test. A change to how a
contract is cut from the catalog, or to the canonical bytes, changes every receipt's contract hash, so it fails here.
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta, timezone

from avalanche_research.core import catalog, clock, errors, hashing, units

CATALOG = {
    "sources": [
        {"id": "rest-source", "name": "A REST source", "endpoints": [
            {"id": "list", "url": "https://example.org/v1/list", "notes": "documentation only"},
            {"id": "detail", "url": "https://example.org/v1/detail", "request_json": {"page": 1}}]},
        {"id": "derived-source", "name": "Derived", "inputs": [
            {"id": "list-table", "dataset_id": "rest.list", "role": "rows"}]},
    ],
    "datasets": [
        {"id": "rest.list", "source_id": "rest-source", "endpoint_ids": ["list"], "status": "active",
         "fields": [{"name": "id", "type": "string"}, {"name": "value", "type": "double"}]},
        {"id": "derived.table", "source_id": "derived-source", "input_ids": ["list-table"],
         "fields": [{"name": "id", "type": "string"}]},
    ],
}


def test_contract_hashes_are_those_before_the_move():
    assert catalog.contract_hash(CATALOG, "rest.list") == "37324e6ad287ed09d487e618c627bfa1ea863c80a63d96830c74d5a5c29a3a9e"
    assert catalog.contract_hash(CATALOG, "derived.table") == (
        "2b7077345c5dbe008fa3d92f6f8964e3fb28178cd1f69a6c542b2eeca9d92934")
    value = {"b": [1, "é"], "a": None}
    assert hashing.sha256(hashing.canonical_bytes(value)) == (
        "e6ad52b780b314ebf4b8cfe44556189598dc133cb06fdb5cc6268b3a4d01d64d")


def test_documentation_does_not_change_a_contract():
    edited = {**CATALOG, "sources": [{**CATALOG["sources"][0], "name": "Renamed"}, CATALOG["sources"][1]]}
    assert catalog.contract_hash(edited, "rest.list") == catalog.contract_hash(CATALOG, "rest.list")


def test_the_data_directory_holds_the_catalog():
    assert (catalog.DATA_DIR / "data-catalog.json").is_file()
    assert catalog.CATALOG.parent == catalog.DATA_DIR == catalog.ROOT / "data"


def test_the_old_names_are_the_new_modules(monkeypatch):
    old = importlib.import_module("avalanche_research.catalog")
    assert old is catalog
    from avalanche_research.catalog import DataError, canonical_bytes, now, sha256
    assert (DataError, canonical_bytes, now, sha256) == (errors.DataError, hashing.canonical_bytes, clock.now,
                                                         hashing.sha256)
    monkeypatch.setattr(old, "DATA_DIR", catalog.ROOT / "elsewhere")
    assert catalog.DATA_DIR == catalog.ROOT / "elsewhere"
    types = importlib.import_module("avalanche_research.model.types")
    assert types.ModelError is errors.ModelError and types.as_utc is clock.as_utc
    assert (types.NAVAX_PER_AVAX, types.SECONDS_PER_DAY, types.PERCENT_DENOMINATOR) == (
        units.NAVAX_PER_AVAX, units.SECONDS_PER_DAY, units.PERCENT_DENOMINATOR)


def test_the_clock_reads_utc():
    assert clock.now().endswith("Z")
    naive = datetime(2026, 10, 1, 12)  # noqa: DTZ001  (the naive input is the case under test)
    assert clock.as_utc(naive) == datetime(2026, 10, 1, 12, tzinfo=UTC)
    pacific = datetime(2026, 10, 1, 5, tzinfo=timezone(timedelta(hours=-7)))
    assert clock.as_utc(pacific) == datetime(2026, 10, 1, 12, tzinfo=UTC)
