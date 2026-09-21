from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from avalanche_research import dataapi, rest
from avalanche_research.catalog import DataError, load_catalog


SUPPLY = {
    "totalSupply": "467830368.0079407050144372577", "circulatingSupply": "467830368.0079407050144372577",
    "totalPBurned": "18729.96063226210197027199722", "totalCBurned": "5064620.868420472463447438865", "totalXBurned": "45617.39339562919279742943955",
    "totalStaked": "206037251.613009", "totalLocked": "28010508.70762238795743059860", "totalRewards": "112959336.2303890687726523980",
    "lastUpdated": "2026-09-19T10:45:15.866Z", "genesisUnlock": "360000000", "l1ValidatorFees": "17951.12135116800001048319636",
}


class Response:
    def __init__(self, value: dict):
        self.body, self.status, self.headers = json.dumps(value).encode(), 200, {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self) -> bytes:
        return self.body


def make_capture(tmp_path: Path, value: dict = SUPPLY) -> Path:
    path = tmp_path / "capture"
    dataapi.capture(dataapi.DATASET_ID, path, opener=lambda request, timeout: Response(value))
    return path


def test_catalog_declares_the_supply_snapshot():
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == dataapi.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(dataapi.TABLE_COLUMNS)


def test_build_check_and_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(rest, "_now", lambda: "2026-09-19T10:45:15Z")
    capture_dir = make_capture(tmp_path)
    dataset_dir = tmp_path / "dataset"
    build = dataapi.build(dataapi.DATASET_ID, capture_dir, dataset_dir)
    assert build["summary"]["observed_at"] == "2026-09-19T10:45:15Z" and abs(build["summary"]["supply_identity_gap_avax"]) < 1
    validation = dataapi.check(capture_dir, dataset_dir)
    assert validation["status"] == "pass", validation["findings"]
    stale = dataapi.check(make_capture(tmp_path / "stale", {**SUPPLY, "lastUpdated": "2026-09-01T00:00:00.000Z"}))
    assert stale["findings"] == ["1 rows were last updated more than a day before the capture"]
    reference = tmp_path / "reference"; reference.mkdir()
    duckdb.connect().execute(f"COPY (SELECT 474234765378278279::BIGINT AS block_supply_navax, TIMESTAMP '2026-09-14 07:56:35' AS accepted_at) TO '{reference / 'primary-staking-supply.parquet'}' (FORMAT PARQUET)")
    validation = dataapi.check(capture_dir, against=reference)
    assert validation["summary"]["counter_minus_api_avax"] == pytest.approx(474234765.378 - 472959336.230, abs=0.01)


def test_identity_break_and_bad_shape_are_reported(tmp_path):
    broken = {**SUPPLY, "totalRewards": "100000000"}
    validation = dataapi.check(make_capture(tmp_path / "broken", broken))
    assert "1 rows break the supply identity by more than one AVAX" in validation["findings"]
    with pytest.raises(DataError, match="misses or mistypes"):
        dataapi.check(make_capture(tmp_path / "bad", {**SUPPLY, "totalStaked": "n/a"}))
