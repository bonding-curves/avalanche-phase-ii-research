"""The contract-rate liquid staking yield, built from small synthetic runs."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from avalanche_research.core.catalog import DataError, canonical_bytes, dataset, load_catalog, sha256
from avalanche_research.datasets.derived import savax_yield as yields

DAYS = (yields.HELD_BACK_CUT - yields.STATE_START).days + 5


def make_run(root: Path, name: str, dataset_id: str, table: str, sql: str) -> None:
    capture_dir, dataset_dir = root / name / "capture", root / name / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / f"{table}.parquet"
    duckdb.connect().execute(f"COPY ({sql}) TO '{parquet}' (FORMAT PARQUET)")
    capture_id = f"capture:test:{name}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({
        "schema_version": "test-capture/v1", "capture_id": capture_id, "dataset_id": dataset_id,
        "completed_at": "2026-11-05T00:00:00Z", "contract_sha256": "0" * 64, "queries": [],
    }))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({
        "schema_version": "test-build/v1", "dataset_id": dataset_id, "source_capture_id": capture_id,
        "completed_at": "2026-11-05T00:00:00Z", "summary": {"rows": 1},
        "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}],
    }))


def runs(root: Path) -> dict[str, str]:
    """A rate growing 5% a year and a price ratio 0.3% below it, held-back days included, and a price-ratio yield."""
    start = yields.STATE_START
    make_run(root, "state", "c-chain-rpc.savax-state-daily", "savax-state-daily", f"""
        SELECT (DATE '{start}' + INTERVAL (k) DAY)::DATE AS date_utc,
               (DATE '{start}' + INTERVAL (k) DAY + INTERVAL 86398 SECOND)::TIMESTAMP AS block_timestamp,
               power(1.05, k / 365.0) AS avax_per_savax, 1000.0 + k AS savax_supply
        FROM range({DAYS}) t(k)""")
    make_run(root, "prices", "allium.prices-hourly", "prices-hourly", f"""
        SELECT a.address, (DATE '{start}' + INTERVAL (k + 1) DAY)::TIMESTAMP AS hour_utc,
               CASE WHEN a.address = '{yields.SAVAX}' THEN 40 * power(1.05, k / 365.0) * 0.997 ELSE 40.0 END AS price_usd
        FROM range({DAYS}) t(k), (VALUES ('{yields.SAVAX}'), ('{yields.NATIVE_AVAX}')) a(address)""")
    make_run(root, "outside", "derived.outside-yields-daily", "outside-yields-daily", f"""
        SELECT (DATE '2022-07-02' + INTERVAL (k) DAY)::DATE AS date_utc, 5.0 + (k % 7) AS savax_growth_30d_pct,
               5.0 + (k % 5) AS savax_median_7d_pct
        FROM range(100) t(k)""")
    return {"c-chain-rpc.savax-state-daily": "state", "allium.prices-hourly": "prices", "derived.outside-yields-daily": "outside"}


def test_catalog_fields_match_the_table():
    definition = dataset(load_catalog(), yields.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(yields.TABLE_COLUMNS)
    assert definition["input_ids"] == list(yields.INPUTS)


def test_yield_reads_the_day_before_and_keeps_the_discount_apart(tmp_path):
    pinned = runs(tmp_path)
    output = tmp_path / "out"
    result = yields.derive(yields.DATASET_ID, output, pinned, tmp_path)
    summary = result["build"]["summary"]
    assert summary["first_day"] == "2022-01-28" and summary["last_day"] == "2025-11-18"
    assert summary["yield_first_day"] == "2022-02-27" and summary["median_first_day"] == "2022-03-02"
    assert summary["latest_state_block"] == "2025-11-17 23:59:58" and summary["yield_negative_days"] == 0
    rows = duckdb.connect().execute(f"""
        SELECT rate_day, savax_growth_30d_pct, market_discount_pct FROM read_parquet('{output / 'dataset' / 'savax-yield-daily.parquet'}')
        WHERE date_utc = DATE '2023-01-01'""").fetchone()
    assert rows[0] == date(2022, 12, 31)
    assert rows[1] == pytest.approx(5.0, abs=1e-9) and rows[2] == pytest.approx(-0.3, abs=1e-9)
    assert summary["against_price_ratio_yield"]["days"] == 100


def test_check_passes_and_refuses_a_changed_build(tmp_path):
    pinned = runs(tmp_path)
    output = tmp_path / "out"
    yields.derive(yields.DATASET_ID, output, pinned, tmp_path)
    assert yields.check(output / "capture", output / "dataset", root=tmp_path)["status"] == "pass"
    parquet = output / "dataset" / "savax-yield-daily.parquet"
    connection = duckdb.connect()
    connection.execute(f"CREATE TABLE t AS SELECT * FROM read_parquet('{parquet}')")
    connection.execute("UPDATE t SET state_block_timestamp = TIMESTAMP '2025-11-19 00:00:01' WHERE date_utc = DATE '2025-11-18'")
    connection.execute(f"COPY t TO '{parquet}' (FORMAT PARQUET)")
    findings = yields.check(output / "capture", output / "dataset", root=tmp_path)["findings"]
    assert "1 rows read a state at a block on or after the held-back instant" in findings


def test_fetch_is_refused(tmp_path):
    with pytest.raises(DataError, match="avalanche data derive"):
        yields.capture(yields.DATASET_ID, tmp_path / "x")
    assert (yields.HELD_BACK_CUT - timedelta(days=1)).isoformat() == "2025-11-18"
