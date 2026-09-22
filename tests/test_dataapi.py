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


PAGES = [
    {"validators": [{"txHash": "a"}, {"txHash": "b"}], "nextPageToken": "t1"},
    {"validators": [{"txHash": "c"}], "nextPageToken": "t2"},
    {"validators": []},
]


def paged_opener(pages=PAGES, seen=None):
    def opener(request, timeout):
        url = request.full_url
        token = url.split("pageToken=")[1] if "pageToken=" in url else None
        index = 0 if token is None else int(token[1:])
        if seen is not None:
            seen.append(url)
        return Response(pages[index])
    return opener


def test_paged_endpoint_is_followed_and_read_back(tmp_path, monkeypatch):
    catalog = json.loads(json.dumps(load_catalog()))
    provider = next(item for item in catalog["sources"] if item["id"] == "avalanche-data-api")
    provider["endpoints"].append({"id": "paged-test", "url": "https://example.test/v1/validators?pageSize=2", "response_fields": ["validators"],
                                  "page": {"token_field": "nextPageToken", "token_parameter": "pageToken", "max_pages": 10}})
    definition = next(item for item in catalog["datasets"] if item["id"] == dataapi.DATASET_ID)
    definition["endpoint_ids"] = ["paged-test"]
    seen: list[str] = []
    receipt = rest.capture(dataapi.DATASET_ID, tmp_path / "capture", catalog=catalog, opener=paged_opener(seen=seen))
    record = receipt["responses"][0]
    assert record["pages"] == 3 and record["path"] == "raw/paged-test.jsonl"
    assert seen == ["https://example.test/v1/validators?pageSize=2", "https://example.test/v1/validators?pageSize=2&pageToken=t1", "https://example.test/v1/validators?pageSize=2&pageToken=t2"]
    _, values = rest.read_capture(tmp_path / "capture", catalog=catalog)
    assert [row["txHash"] for page in values["paged-test"] for row in page["validators"]] == ["a", "b", "c"]


def test_paged_endpoint_stops_at_the_page_cap(tmp_path):
    catalog = json.loads(json.dumps(load_catalog()))
    provider = next(item for item in catalog["sources"] if item["id"] == "avalanche-data-api")
    provider["endpoints"].append({"id": "paged-test", "url": "https://example.test/v1/validators", "response_fields": ["validators"],
                                  "page": {"token_field": "nextPageToken", "token_parameter": "pageToken", "max_pages": 2}})
    next(item for item in catalog["datasets"] if item["id"] == dataapi.DATASET_ID)["endpoint_ids"] = ["paged-test"]
    with pytest.raises(DataError, match="exceeded 2 pages"):
        rest.capture(dataapi.DATASET_ID, tmp_path / "capture", catalog=catalog, opener=paged_opener())


def test_paged_capture_keeps_fetched_pages_when_a_later_page_fails(tmp_path):
    catalog = json.loads(json.dumps(load_catalog()))
    provider = next(item for item in catalog["sources"] if item["id"] == "avalanche-data-api")
    provider["endpoints"].append({"id": "paged-test", "url": "https://example.test/v1/validators", "response_fields": ["validators"],
                                  "page": {"token_field": "nextPageToken", "token_parameter": "pageToken", "max_pages": 10}})
    next(item for item in catalog["datasets"] if item["id"] == dataapi.DATASET_ID)["endpoint_ids"] = ["paged-test"]

    def flaky(request, timeout):
        if "pageToken=t2" in request.full_url:
            raise OSError("connection reset")
        return paged_opener()(request, timeout)

    with pytest.raises(DataError, match="request failed"):
        rest.capture(dataapi.DATASET_ID, tmp_path / "capture", catalog=catalog, opener=flaky)
    kept = list(tmp_path.glob(".capture.*/raw/paged-test.jsonl"))
    assert len(kept) == 1 and len(kept[0].read_text().splitlines()) == 2
