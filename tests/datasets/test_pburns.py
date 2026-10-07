"""P- and X-Chain daily burns from fake walks and a fake P-Chain block list."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from test_pblocks import BASE, FakeNode, delegator_tx, utxo

from avalanche_research.core.catalog import canonical_bytes, load_catalog, sha256
from avalanche_research.datasets.derived import pburns
from avalanche_research.sources import pblocks

DAY0 = 1_789_862_400  # 2026-09-20 00:00 UTC


def block(height: int, time: int, body: dict) -> dict:
    return {"id": f"B{height}", "parentID": f"B{height - 1}", "height": height, "time": time,
            "txs": [{"id": f"T{height}", "unsignedTx": body, "credentials": []}]}


def base_tx(spent: int, kept: int) -> dict:
    return {**BASE, "inputs": [utxo(spent, "input")], "outputs": [utxo(kept)]}


def make_list(root: Path, rows: list[tuple]) -> None:
    capture_dir, dataset_dir = root / "plist" / "capture", root / "plist" / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / "p-chain-block-list.parquet"
    values = ", ".join(f"({h}, 'H{h}', make_timestamp({t}::BIGINT * 1000000), make_timestamp({t}::BIGINT * 1000000)::DATE, 'BanffStandardBlock', 1, 474000000000000000, {n}, {a})" for h, t, n, a in rows)
    duckdb.connect().execute(f"COPY (SELECT * FROM (VALUES {values}) AS t(block_height, block_hash, block_timestamp, date_utc, block_type, transactions,"
                             f" current_supply_navax, active_l1_validators, l1_validators_accrued_fees_navax)) TO '{parquet}' (FORMAT PARQUET)")
    capture_id = "capture:test:plist"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({"schema_version": "test/v1", "capture_id": capture_id,
                                                                "dataset_id": "data-api.p-chain-block-list", "completed_at": "2026-09-29T00:00:00Z"}))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({"schema_version": "test/v1", "dataset_id": "data-api.p-chain-block-list",
                                                              "source_capture_id": capture_id, "completed_at": "2026-09-29T00:00:00Z", "summary": {"rows": len(rows)},
                                                              "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}]}))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    register = {**BASE, "inputs": [utxo(5_100_000_000, "input")], "outputs": [], "balance": "5000000000", "proofOfPossession": {}, "message": "0x"}
    p_chain = {
        100: block(100, DAY0, delegator_tx()),
        101: block(101, DAY0 + 43_200, register),
        102: block(102, DAY0 + 86_400 + 21_600, base_tx(2_000_000, 1_000_000)),
        103: block(103, DAY0 + 2 * 86_400 + 3_600, base_tx(2_000_000, 1_000_000)),
    }
    pblocks.capture(pblocks.DATASET_ID, runs / "pwalk" / "capture", parameters={"from_height": "100"}, request=FakeNode(p_chain))
    pblocks.build(pblocks.DATASET_ID, runs / "pwalk" / "capture", runs / "pwalk" / "dataset")
    x_chain = {10 + day: block(10 + day, DAY0 + day * 86_400, base_tx(1_001_000, 1_000_000)) for day in range(3)}
    pblocks.capture(pblocks.X_DATASET_ID, runs / "xwalk" / "capture", parameters={"from_height": "10"}, request=FakeNode(x_chain))
    pblocks.build(pblocks.X_DATASET_ID, runs / "xwalk" / "capture", runs / "xwalk" / "dataset")
    # Three L1 validators accrue 100 each by the first block of day 1, then two accrue 50 each by day 2.
    make_list(runs, [(99, DAY0 - 600, 3, 1_000), (100, DAY0, 3, 1_000), (102, DAY0 + 86_400 + 21_600, 2, 1_100), (103, DAY0 + 2 * 86_400 + 3_600, 2, 1_150)])
    return runs


def test_catalog_columns_equal_the_share():
    fields = next(item for item in load_catalog()["datasets"] if item["id"] == pburns.DATASET_ID)["fields"]
    assert [field["name"] for field in fields] == list(pburns.COLUMNS)


def test_daily_burns_deposits_and_l1_fees(root):
    output = root / "burns"
    pburns.derive(pburns.DATASET_ID, output, root=root)
    rows = duckdb.connect().execute(
        "SELECT date_utc::VARCHAR, chain, transactions, burned_navax, recorded_transactions, l1_balance_deposited_navax, l1_validator_fees_navax"
        " FROM read_parquet(?) ORDER BY 1, 2", [str(output / "dataset" / f"{pburns.TABLE}.parquet")]).fetchall()
    # Day 2 is the last day of the walks and is partial, so it is left out.
    assert rows == [
        ("2026-09-20", "P", 2, 1_000_000_000 + 100_000_000, 2, 5_000_000_000, 0),
        ("2026-09-20", "X", 1, 1_000, 1, 0, 0),
        ("2026-09-21", "P", 1, 1_000_000, 1, 0, 300),
        ("2026-09-21", "X", 1, 1_000, 1, 0, 0),
    ]
    assert pburns.check(output / "capture", output / "dataset", root=root)["status"] == "pass"
