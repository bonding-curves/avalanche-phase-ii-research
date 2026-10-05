from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from avalanche_research import pool_history
from avalanche_research.catalog import DataError, load_catalog


class Response:
    def __init__(self, value):
        self.body = json.dumps(value).encode()
        self.status = 200
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self) -> bytes:
        return self.body


def point(timestamp: str, apy: float, tvl: float = 1e6) -> dict:
    return {"timestamp": timestamp, "tvlUsd": tvl, "apy": apy, "apyBase": apy, "apyReward": None, "il7d": None, "apyBase7d": None,
            "pricePerShare": None}


def chart(url: str) -> dict:
    # sAVAX reports twice on 2024-07-05 and skips 2024-07-06. Every other pool has two clean days.
    if url.endswith(pool_history.POOLS["savax"][0]):
        points = [point("2024-07-04T23:01:00.193Z", 5.0), point("2024-07-05T01:00:00.000Z", 5.1),
                  point("2024-07-05T23:00:00.000Z", 5.2), point("2024-07-07T23:00:00.000Z", 5.3)]
    else:
        points = [point("2024-07-04T00:00:00.000Z", 1.0), point("2024-07-05T00:00:00.000Z", 1.5)]
    return {"status": "success", "data": points}


POOLS = {"status": "success", "data": [
    {"pool": "l1", "chain": "Avalanche", "project": "aave-v3", "symbol": "WAVAX", "apy": 0.7, "apyBase": 0.7, "apyReward": None},
    {"pool": "l2", "chain": "Avalanche", "project": "benqi-lending", "symbol": "USDC", "apy": 5.9, "apyBase": 4.0, "apyReward": 1.9},
    {"pool": "e1", "chain": "Ethereum", "project": "aave-v3", "symbol": "WETH", "apy": 2.0, "apyBase": 2.0, "apyReward": None},
]}
LENDING = [
    {"pool": "l1", "apyBaseBorrow": 2.1, "apyRewardBorrow": None, "totalSupplyUsd": 1.3e8, "totalBorrowUsd": 4e7, "debtCeilingUsd": None,
     "ltv": 0.6, "borrowable": True, "mintedCoin": None, "rewardTokens": None, "underlyingTokens": ["0xaa"], "borrowFactor": None},
    {"pool": "l2", "apyBaseBorrow": 7.0, "apyRewardBorrow": 0.5, "totalSupplyUsd": 1.6e6, "totalBorrowUsd": 1e6, "debtCeilingUsd": None,
     "ltv": 0.8, "borrowable": True, "mintedCoin": None, "rewardTokens": None, "underlyingTokens": ["0xbb"], "borrowFactor": 1.0},
    {"pool": "e1", "apyBaseBorrow": 3.0, "apyRewardBorrow": None, "totalSupplyUsd": 1e9, "totalBorrowUsd": 5e8, "debtCeilingUsd": None,
     "ltv": 0.8, "borrowable": True, "mintedCoin": None, "rewardTokens": None, "underlyingTokens": ["0xcc"], "borrowFactor": None},
]


def opener(request, timeout):
    url = request.full_url
    if url.endswith("/pools"):
        return Response(POOLS)
    if url.endswith("/lendBorrow"):
        return Response(LENDING)
    return Response(chart(url))


def make_capture(tmp_path: Path, dataset_id: str) -> Path:
    path = tmp_path / dataset_id
    pool_history.capture(dataset_id, path, opener=opener)
    return path


@pytest.mark.parametrize("dataset_id", pool_history.DATASET_IDS)
def test_catalog_declares_each_dataset(dataset_id):
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == dataset_id)
    assert [field["name"] for field in definition["fields"]] == list(pool_history.COLUMNS[dataset_id])


def test_catalog_declares_one_chart_endpoint_per_pool():
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == pool_history.HISTORY_ID)
    assert definition["endpoint_ids"] == [f"pool-chart-{label}" for label in pool_history.POOLS]


def test_history_keeps_the_last_point_of_a_day_and_leaves_gaps(tmp_path):
    capture_dir = make_capture(tmp_path, pool_history.HISTORY_ID)
    dataset_dir = tmp_path / "dataset"
    build = pool_history.build(pool_history.HISTORY_ID, capture_dir, dataset_dir)
    savax = build["summary"]["pools"]["savax"]
    assert savax == {"days": 3, "first": "2024-07-04", "last": "2024-07-07", "missing_days": 1}
    assert build["summary"]["rows"] == 3 + 2 * (len(pool_history.POOLS) - 1)
    rows = duckdb.sql(
        f"SELECT observation_date::VARCHAR, apy FROM read_parquet('{dataset_dir / 'pool-history.parquet'}') WHERE label = 'savax'"
    ).fetchall()
    assert rows == [("2024-07-04", 5.0), ("2024-07-05", 5.2), ("2024-07-07", 5.3)]
    validation = pool_history.check(capture_dir, dataset_dir)
    assert validation["status"] == "pass", validation["findings"]


def test_history_rebuilds_byte_identical(tmp_path):
    capture_dir = make_capture(tmp_path, pool_history.HISTORY_ID)
    first = pool_history.build(pool_history.HISTORY_ID, capture_dir, tmp_path / "a")
    second = pool_history.build(pool_history.HISTORY_ID, capture_dir, tmp_path / "b")
    assert first["outputs"] == second["outputs"]


def test_lend_borrow_keeps_avalanche_pools_with_both_rates(tmp_path):
    capture_dir = make_capture(tmp_path, pool_history.LEND_BORROW_ID)
    dataset_dir = tmp_path / "dataset"
    build = pool_history.build(pool_history.LEND_BORROW_ID, capture_dir, dataset_dir)
    assert build["summary"]["rows"] == 2 and build["summary"]["distinct_projects"] == 2
    rows = duckdb.sql(
        f"SELECT symbol, apy_supply, apy_base_borrow FROM read_parquet('{dataset_dir / 'lend-borrow.parquet'}') ORDER BY symbol"
    ).fetchall()
    assert rows == [("USDC", 5.9, 7.0), ("WAVAX", 0.7, 2.1)]
    assert pool_history.check(capture_dir, dataset_dir)["status"] == "pass"


def test_an_empty_pool_history_is_refused(tmp_path):
    def empty(request, timeout):
        return Response({"status": "success", "data": []})

    capture_dir = tmp_path / "capture"
    pool_history.capture(pool_history.HISTORY_ID, capture_dir, opener=empty)
    with pytest.raises(DataError, match="returned no history"):
        pool_history.build(pool_history.HISTORY_ID, capture_dir, tmp_path / "dataset")
