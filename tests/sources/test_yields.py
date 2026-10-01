from __future__ import annotations

import json
from pathlib import Path

import pytest

from avalanche_research.sources import yields
from avalanche_research.catalog import DataError, load_catalog


def pool(pool_id: str, chain: str, project: str, apy: float = 5.0, tvl: float = 1e6, outlier: bool = False) -> dict:
    return {
        "chain": chain, "project": project, "symbol": "X", "tvlUsd": tvl, "apyBase": apy, "apyReward": None, "apy": apy,
        "rewardTokens": ["0xaa"], "pool": pool_id, "apyPct1D": 0, "apyPct7D": 0, "apyPct30D": 0, "stablecoin": False, "ilRisk": "no",
        "exposure": "single", "predictions": {"predictedClass": "Stable/Up"}, "poolMeta": None, "mu": apy, "sigma": 0.1, "count": 10,
        "outlier": outlier, "underlyingTokens": ["0xbb", "0xcc"], "il7d": None, "apyBase7d": None, "apyMean30d": apy, "volumeUsd1d": None,
        "volumeUsd7d": None, "apyBaseInception": None,
    }


POOLS = [pool("a1", "Avalanche", "benqi-lending"), pool("a2", "Avalanche", "benqi-staked-avax", 6.1), pool("e1", "Ethereum", "lido", 3.2, 2e10),
         pool("e2", "Ethereum", "uniswap-v3", 40.0), pool("s1", "Solana", "jito", 7.5, outlier=True)]


class Response:
    def __init__(self, data: list[dict]):
        self.body = json.dumps({"status": "success", "data": data}).encode()
        self.status = 200
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self) -> bytes:
        return self.body


def make_capture(tmp_path: Path, data=POOLS) -> Path:
    path = tmp_path / "capture"
    yields.capture(yields.DATASET_ID, path, opener=lambda request, timeout: Response(data))
    return path


def test_catalog_declares_the_pool_dataset():
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == yields.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(yields.TABLE_COLUMNS)


def test_build_keeps_avalanche_and_proof_of_stake_pools_only(tmp_path):
    capture_dir = make_capture(tmp_path)
    dataset_dir = tmp_path / "dataset"
    build = yields.build(yields.DATASET_ID, capture_dir, dataset_dir)
    assert build["summary"]["rows"] == 4 and build["summary"]["avalanche_pools"] == 2 and build["summary"]["proof_of_stake_pools"] == 2
    assert build["summary"]["pools_flagged_outlier"] == 1
    validation = yields.check(capture_dir, dataset_dir)
    assert validation["status"] == "pass", validation["findings"]
    import duckdb
    rows = duckdb.connect().execute(f"SELECT pool_id, selection, horizon_days, liquidity_usd, underlying_tokens FROM '{dataset_dir / 'pool-yields.parquet'}' ORDER BY pool_id").fetchall()
    assert rows[0] == ("a1", "avalanche", None, 1e6, "0xbb,0xcc") and rows[2][1] == "proof-of-stake"


def test_check_reports_duplicates_and_empty_selection(tmp_path):
    capture_dir = make_capture(tmp_path, [pool("a1", "Avalanche", "benqi-lending", tvl=-5.0), pool("a1", "Avalanche", "benqi-lending")])
    validation = yields.check(capture_dir)
    assert validation["findings"] == ["1 rows repeat a pool identifier", "1 rows selections are empty", "1 rows have a negative TVL or yield"]
    with pytest.raises(DataError, match="no selected pools"):
        yields.check(make_capture(tmp_path / "none", [pool("e2", "Ethereum", "uniswap-v3")]))
