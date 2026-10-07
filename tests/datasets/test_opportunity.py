from __future__ import annotations

from datetime import date

import duckdb
import pytest

from avalanche_research.core.catalog import load_catalog
from avalanche_research.datasets.derived import opportunity


def connection_with_inputs() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect()
    supply = 460_000_000 * 10**18
    connection.execute(
        f"""
        CREATE TABLE ledger AS SELECT * FROM (VALUES
          (DATE '2026-09-28', {supply}::DECIMAL(38,0)), (DATE '2026-09-29', {supply}::DECIMAL(38,0)),
          (DATE '2026-09-30', NULL::DECIMAL(38,0))) AS t(date_utc, total_supply_open_wei)
        """
    )
    connection.execute("CREATE TABLE tbill AS SELECT * FROM (VALUES (DATE '2026-09-28', 4.0), (DATE '2026-09-30', 4.1)) AS t(date_utc, discount_rate_pct)")
    connection.execute(
        "CREATE TABLE treasury AS SELECT * FROM (VALUES (DATE '2026-09-28', '1y', 0.039), (DATE '2026-09-28', '10y', 0.043)) "
        "AS t(observation_date, tenor, yield_rate)"
    )
    connection.execute(
        "CREATE TABLE pools AS SELECT * FROM (VALUES (DATE '2026-09-29', 'savax', 3.8), (DATE '2026-09-29', 'unknown', 9.0)) "
        "AS t(observation_date, label, apy)"
    )
    return connection


def test_catalog_declares_the_table():
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == opportunity.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(opportunity.COLUMNS)


def test_each_alternative_sits_beside_the_native_rate_of_its_day():
    connection = connection_with_inputs()
    opportunity.compute(connection)
    rows = {(day, series): (rate, native, spread) for day, series, rate, native, spread in connection.execute(
        "SELECT date_utc, series, rate_pct, native_14d_pct, spread_vs_14d_pp FROM result").fetchall()}
    native = rows[(date(2026, 9, 28), "native-14d")][0]
    # Helicon's ramp lowers the offered rate day by day.
    assert rows[(date(2026, 9, 29), "native-14d")][0] < native
    assert 5 < native < 6
    _, beside, spread = rows[(date(2026, 9, 28), "tbill-3m")]
    assert beside == native and spread == pytest.approx(4.0 - native)
    # The ledger has no supply on 09-30, so the bill keeps its rate without a native rate. Gaps stay gaps.
    assert rows[(date(2026, 9, 30), "tbill-3m")][1] is None
    # The Treasury feed stores fractions. Every rate in the table is percent.
    assert rows[(date(2026, 9, 28), "treasury-1y")][0] == pytest.approx(3.9)
    assert not any(series == "unknown" for _, series in rows)
    assert rows[(date(2026, 9, 29), "savax")][0] == 3.8
    assert opportunity.summarize(connection)["rows"] == len(rows)
