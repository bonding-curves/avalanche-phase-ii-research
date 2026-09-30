"""The measure registry, v0: declarations are checked, a measure reads a chain table and a run table the same way."""

from __future__ import annotations

from dataclasses import replace

import duckdb
import pytest

from avalanche_research import measures
from avalanche_research.catalog import DataError, load_catalog

EXAMPLE = measures.STAKED_SHARE_DAILY


def ledger(connection: duckdb.DuckDBPyConnection, name: str, extra: str = "") -> None:
    connection.execute(f"""CREATE TABLE "{name}" AS SELECT * FROM (VALUES
        (DATE '2026-09-01', 150::BIGINT, 50::BIGINT, 400::BIGINT{extra}),
        (DATE '2026-09-02', 160::BIGINT, 40::BIGINT, 500::BIGINT{extra}),
        (DATE '2026-09-03', 0::BIGINT, 0::BIGINT, NULL::BIGINT{extra}))
        AS t(date_utc, active_validator_stake_wei, active_delegated_stake_wei, total_supply_close_wei{", run_id" if extra else ""})""")


def test_the_example_is_registered_once_and_matches_the_catalog():
    assert measures.REGISTRY["staked-share-daily"] is EXAMPLE
    assert measures.check_datasets(EXAMPLE, load_catalog()) == []
    with pytest.raises(DataError, match="already registered"):
        measures.register(EXAMPLE)


def test_a_bad_declaration_names_each_problem():
    bad = replace(EXAMPLE, id="Staked Share", unit="ratio", owner="anyone", datasets=(), sql="SELECT 1")
    assert bad.problems() == [
        "id 'Staked Share' is not lowercase words joined by hyphens", f"unit 'ratio' is not one of {', '.join(measures.UNITS)}",
        "owner 'anyone' is not one of data-science, modeling, data-engineering", "a measure applied to chain data names the datasets it reads",
        "the SQL reads the relation named source"]


def test_a_chain_table_and_a_run_table_give_the_same_answer():
    connection = duckdb.connect()
    ledger(connection, "chain")
    ledger(connection, "run", ", 'run-1'")
    chain = measures.compute(EXAMPLE, connection, "chain").fetchall()
    assert [(str(day), value) for day, value in chain] == [("2026-09-01", 0.5), ("2026-09-02", 0.4)]
    assert measures.compute(EXAMPLE, connection, "run").fetchall() == chain


def test_a_missing_column_a_wrong_type_or_a_repeated_grain_is_refused():
    connection = duckdb.connect()
    connection.execute("CREATE TABLE short AS SELECT DATE '2026-09-01' AS date_utc")
    with pytest.raises(DataError, match="has no column active_validator_stake_wei"):
        measures.compute(EXAMPLE, connection, "short")
    connection.execute("CREATE TABLE text AS SELECT DATE '2026-09-01' AS date_utc, 'a' AS active_validator_stake_wei, 1 AS active_delegated_stake_wei, 2 AS total_supply_close_wei")
    with pytest.raises(DataError, match="is VARCHAR, the measure reads integer"):
        measures.compute(EXAMPLE, connection, "text")
    ledger(connection, "twice")
    connection.execute("INSERT INTO twice SELECT * FROM twice")
    with pytest.raises(DataError, match="rows repeat a grain"):
        measures.compute(EXAMPLE, connection, "twice")


def test_a_dataset_without_the_columns_is_reported():
    wrong = replace(EXAMPLE, datasets=("derived.gci-monthly", "no.such-dataset"))
    found = measures.check_datasets(wrong, load_catalog())
    assert "derived.gci-monthly has no column active_validator_stake_wei" in found and any("no.such-dataset" in item for item in found)
