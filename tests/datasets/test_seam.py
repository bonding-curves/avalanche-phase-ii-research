"""The seam between the share and its backups, on small synthetic runs."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pytest

from avalanche_research.core.catalog import (
    DataError,
    canonical_bytes,
    load_catalog,
    sha256,
)
from avalanche_research.datasets.derived import seam
from avalanche_research.sources.snowflake import SPECS

# Naive UTC, as the share stores its timestamps.
T = [datetime(2026, 9, 22, hour, tzinfo=UTC).replace(tzinfo=None) for hour in range(4, 10)]


def make_run(root: Path, run: str, dataset_id: str, columns: dict[str, str], rows: list[dict]) -> None:
    capture_dir, dataset_dir = root / run / "capture", root / run / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / "table.parquet"
    connection = duckdb.connect()
    connection.execute(f"CREATE TABLE rows({', '.join(f'{name} {kind}' for name, kind in columns.items())})")
    if rows:
        connection.executemany(f"INSERT INTO rows VALUES ({', '.join('?' for _ in columns)})", [[row.get(name) for name in columns] for row in rows])
    connection.execute("COPY rows TO ? (FORMAT PARQUET)", [str(parquet)])
    capture_id = f"capture:test:{run}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({"schema_version": "test/v1", "capture_id": capture_id, "dataset_id": dataset_id,
                                                                "completed_at": "2026-09-29T00:00:00Z"}))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({"schema_version": "test/v1", "dataset_id": dataset_id, "source_capture_id": capture_id,
                                                              "completed_at": "2026-09-29T00:00:00Z", "summary": {"rows": len(rows)},
                                                              "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}]}))


def stake(hour: int, utxos: int = 1) -> dict:
    return {"transaction_hash": f"V{hour}", "accepted_at": T[hour], "block_height": hour, "tx_type": "AddPermissionlessValidatorTx",
            "node_id": "NodeID-A", "stake_navax": 2_000_000_000_000, "staked_utxo_count": utxos, "potential_reward_navax": 7}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    specs = {dataset_id: spec.table_columns for dataset_id, spec in SPECS.items()}
    # The share's last hour lacks the staked outputs of V3: the seam is T[3].
    make_run(runs, "share-validators", "snowflake.primary-validator-stakes", specs["snowflake.primary-validator-stakes"], [stake(0), stake(1), stake(2), stake(3, 0)])
    make_run(runs, "share-delegators", "snowflake.primary-delegator-stakes", specs["snowflake.primary-delegator-stakes"], [])
    make_run(runs, "share-rewards", "snowflake.primary-staking-rewards", specs["snowflake.primary-staking-rewards"],
             [{"reward_transaction_hash": "R5", "rewarded_at": T[5]}])
    make_run(runs, "share-supply", "snowflake.primary-staking-supply", specs["snowflake.primary-staking-supply"],
             [{"transaction_hash": f"V{hour}", "accepted_at": T[hour], "block_height": hour, "previous_block_supply_navax": 1, "block_supply_navax": 2} for hour in range(4)])
    backup_columns = specs["snowflake.primary-validator-stakes"]
    make_run(runs, "backup-validators", "derived.p-chain-validator-stakes", backup_columns, [stake(1), stake(2), stake(3), stake(4)])
    return runs


def test_catalog_columns_are_the_share_and_a_source():
    catalog = {item["id"]: item for item in load_catalog()["datasets"]}
    for dataset_id in seam.DATASET_IDS:
        assert [field["name"] for field in catalog[dataset_id]["fields"]] == list(seam.columns(dataset_id))


def test_share_before_the_seam_and_backup_from_it(root):
    output = root / "seamed"
    result = seam.derive("derived.seamed-validator-stakes", output, root=root)
    assert result["capture"]["seam"] == "2026-09-22 07:00:00"
    assert result["build"]["summary"]["overlap"]["rows_compared"] == 2
    rows = duckdb.connect().execute("SELECT transaction_hash, source, staked_utxo_count FROM read_parquet(?) ORDER BY accepted_at",
                                    [str(output / "dataset" / "seamed-validator-stakes.parquet")]).fetchall()
    assert rows == [("V0", "snowflake", 1), ("V1", "snowflake", 1), ("V2", "snowflake", 1), ("V3", "backup", 1), ("V4", "backup", 1)]
    assert seam.check(output / "capture", output / "dataset", root=root)["status"] == "pass"


def test_a_backup_that_differs_before_the_seam_is_refused(root, tmp_path):
    runs = root
    other = dict(stake(2))
    other["potential_reward_navax"] = 8
    make_run(runs, "backup-validators-2", "derived.p-chain-validator-stakes", SPECS["snowflake.primary-validator-stakes"].table_columns,
             [stake(1), other, stake(3)])
    with pytest.raises(DataError, match="differs from the share before the seam"):
        seam.derive("derived.seamed-validator-stakes", tmp_path / "out", {"derived.p-chain-validator-stakes": "backup-validators-2"}, root=runs)


def test_the_share_last_date_comes_from_the_backup(tmp_path):
    runs = tmp_path / "runs"
    columns = SPECS["snowflake.c-chain-evm-burn-daily"].table_columns
    day = [date(2026, 9, 19 + offset) for offset in range(4)]
    complete = {"absent_blocks": 0, "short_blocks": 0}
    make_run(runs, "share", "snowflake.c-chain-evm-burn-daily", columns,
             [{"date_utc": day[0], "burned_wei": 5, **complete}, {"date_utc": day[1], "burned_wei": 3, **complete}])
    make_run(runs, "backup", "derived.c-chain-evm-burn-daily", columns,
             [{"date_utc": day[0], "burned_wei": 5, **complete}, {"date_utc": day[1], "burned_wei": 6, **complete}, {"date_utc": day[2], "burned_wei": 7, **complete}])
    output = runs / "seamed"
    seam.derive("derived.seamed-c-chain-evm-burn-daily", output, root=runs)
    rows = duckdb.connect().execute("SELECT date_utc::VARCHAR, burned_wei::BIGINT, source FROM read_parquet(?) ORDER BY 1",
                                    [str(output / "dataset" / "seamed-c-chain-evm-burn-daily.parquet")]).fetchall()
    assert rows == [("2026-09-19", 5, "snowflake"), ("2026-09-20", 6, "backup"), ("2026-09-21", 7, "backup")]


def test_downstream_reads_the_seamed_table_unless_the_share_is_pinned(root):
    share = "snowflake.primary-validator-stakes"
    assert seam.resolve(share, None, root) == (share, None)
    seam.derive("derived.seamed-validator-stakes", root / "seamed", root=root)
    assert seam.resolve(share, None, root) == ("derived.seamed-validator-stakes", None)
    assert seam.resolve(share, {share: "share-validators"}, root) == (share, "share-validators")


def test_a_share_day_that_declares_itself_incomplete_is_kept_but_not_compared(tmp_path):
    runs = tmp_path / "runs"
    columns = SPECS["snowflake.c-chain-evm-burn-daily"].table_columns
    day = [date(2026, 9, 19 + offset) for offset in range(3)]
    make_run(runs, "share", "snowflake.c-chain-evm-burn-daily", columns,
             [{"date_utc": day[0], "burned_wei": 5, "absent_blocks": 1, "short_blocks": 0}, {"date_utc": day[1], "burned_wei": 3, "absent_blocks": 0, "short_blocks": 0},
              {"date_utc": day[2], "burned_wei": 1, "absent_blocks": 0, "short_blocks": 0}])
    make_run(runs, "backup", "derived.c-chain-evm-burn-daily", columns,
             [{"date_utc": day[0], "burned_wei": 9, "absent_blocks": 0, "short_blocks": 0}, {"date_utc": day[1], "burned_wei": 3, "absent_blocks": 0, "short_blocks": 0},
              {"date_utc": day[2], "burned_wei": 4, "absent_blocks": 0, "short_blocks": 0}])
    overlap = seam.derive("derived.seamed-c-chain-evm-burn-daily", runs / "seamed", root=runs)["build"]["summary"]["overlap"]
    assert (overlap["rows_compared"], overlap["share_rows_incomplete_not_compared"]) == (1, 1)
    rows = duckdb.connect().execute("SELECT burned_wei::BIGINT, source FROM read_parquet(?) ORDER BY date_utc",
                                    [str(runs / "seamed" / "dataset" / "seamed-c-chain-evm-burn-daily.parquet")]).fetchall()
    assert rows == [(5, "snowflake"), (3, "snowflake"), (4, "backup")]
