"""The ledger by upgrade period, over three fake days around the Helicon activation of 2026-09-22 15:00 UTC."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pytest

from avalanche_research.core.catalog import canonical_bytes, load_catalog, sha256
from avalanche_research.datasets.derived import monetary_periods

WEI = 10**18


def utc(*parts: int) -> datetime:
    """Naive UTC, as the tables store their timestamps."""
    return datetime(*parts, tzinfo=UTC).replace(tzinfo=None)


def make_run(root: Path, run: str, dataset_id: str, columns: dict[str, str], rows: list[tuple], inputs: list[dict] | None = None) -> dict:
    capture_dir, dataset_dir = root / run / "capture", root / run / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / "table.parquet"
    connection = duckdb.connect()
    connection.execute(f"CREATE TABLE t({', '.join(f'{name} {kind}' for name, kind in columns.items())})")
    connection.executemany(f"INSERT INTO t VALUES ({', '.join('?' for _ in columns)})", rows)
    connection.execute("COPY t TO ? (FORMAT PARQUET)", [str(parquet)])
    capture_id = f"capture:test:{run}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({"schema_version": "test/v1", "capture_id": capture_id, "dataset_id": dataset_id,
                                                                "completed_at": "2026-09-29T00:00:00Z", "inputs": inputs or []}))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({"schema_version": "test/v1", "dataset_id": dataset_id, "source_capture_id": capture_id,
                                                              "completed_at": "2026-09-29T00:00:00Z", "summary": {"rows": len(rows)},
                                                              "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}]}))
    return {"parquet": parquet.name, "sha256": sha256(body)}


@pytest.fixture
def root(tmp_path: Path, monkeypatch) -> Path:
    runs = tmp_path / "runs"
    # Only granite and helicon: the ledger starts the day before Helicon.
    monkeypatch.setattr(monetary_periods, "periods", lambda: [("granite", "2025-11-19 16:00:00"), ("helicon", "2026-09-22 15:00:00")])
    rewards = make_run(runs, "rewards", "derived.seamed-staking-rewards", {"rewarded_at": "TIMESTAMP", "realized_reward_navax": "BIGINT"},
                       [(utc(2026, 9, 22, 14, 59), 10 * 10**9), (utc(2026, 9, 22, 15, 0), 20 * 10**9), (utc(2026, 9, 23, 12), 40 * 10**9)])
    columns = {"date_utc": "DATE", "issued_rewards_wei": "DECIMAL(38,0)", "burned_p_wei": "DECIMAL(38,0)", "burned_x_wei": "DECIMAL(38,0)",
               "burned_c_evm_wei": "DECIMAL(38,0)", "burned_c_evm_gap_wei": "DECIMAL(38,0)", "burned_c_atomic_wei": "DECIMAL(38,0)",
               "burned_wei": "DECIMAL(38,0)", "total_supply_close_wei": "DECIMAL(38,0)", "active_validator_stake_wei": "DECIMAL(38,0)",
               "active_delegated_stake_wei": "DECIMAL(38,0)"}
    days = [(date(2026, 9, 21), 0, 1), (date(2026, 9, 22), 30, 2), (date(2026, 9, 23), 40, 3)]
    make_run(runs, "ledger", "derived.avax-monetary-daily", columns,
             [(day, issued * WEI, burn * WEI, 0, 0, 0, 0, burn * WEI, 100 * WEI, 40 * WEI, 10 * WEI) for day, issued, burn in days],
             inputs=[{"input_id": "staking-rewards", "dataset_id": "derived.seamed-staking-rewards", "run": "rewards", **rewards}])
    return runs


def test_catalog_declares_the_columns():
    fields = next(item for item in load_catalog()["datasets"] if item["id"] == monetary_periods.DATASET_ID)["fields"]
    assert [field["name"] for field in fields] == list(monetary_periods.TABLE_COLUMNS)


def test_issuance_splits_at_the_instant_and_days_follow_their_close(root):
    output = root / "periods"
    monetary_periods.derive(monetary_periods.DATASET_ID, output, root=root)
    rows = duckdb.connect().execute("SELECT regime, days_observed, days_in_period, issued_avax, burned_avax, activation_day_burned_avax, mean_validator_ratio"
                                    " FROM read_parquet(?) ORDER BY starts_at", [str(output / "dataset" / f"{monetary_periods.TABLE}.parquet")]).fetchall()
    # The reward at 14:59 is granite's, the one at 15:00 Helicon's. The 22nd closes after the activation, so its burn is Helicon's.
    assert rows[1][:6] == ("helicon", 2, 2, 60.0, 5.0, 2.0)
    assert rows[0][3] == 10.0 and rows[0][4] == 1.0 and rows[1][6] == pytest.approx(0.4)
    assert monetary_periods.check(output / "capture", output / "dataset", root=root)["status"] == "pass"
