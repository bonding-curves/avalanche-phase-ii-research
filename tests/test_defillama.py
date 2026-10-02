from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from avalanche_research import coingecko, defillama
from avalanche_research.catalog import DataError, load_catalog, source


SERIES_START = datetime(2020, 9, 22, tzinfo=timezone.utc)
CAPTURE_DAY = datetime(2021, 3, 1, tzinfo=timezone.utc)


def window_payload(start_unix: int, span: int, skip: set[int] = frozenset()) -> dict:
    points = []
    for index in range(span):
        stamp = datetime.fromtimestamp(start_unix, tz=timezone.utc) + timedelta(days=index, minutes=5)
        if stamp > CAPTURE_DAY or index in skip:
            continue
        day = (stamp - SERIES_START).days
        points.append({"timestamp": int(stamp.timestamp()), "price": 10 + math.sin(day / 7)})
    return {"coins": {defillama.COIN: {"symbol": "AVAX", "confidence": 0.99, "prices": points}}}


class Response:
    def __init__(self, value: dict):
        self.body = json.dumps(value, separators=(",", ":")).encode()
        self.status = 200
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self) -> bytes:
        return self.body


def opener(skip: set[int] = frozenset()):
    def open_request(request, timeout):
        query = parse_qs(urlparse(request.full_url).query)
        return Response(window_payload(int(query["start"][0]), int(query["span"][0]), skip))

    return open_request


def make_capture(tmp_path: Path, skip: set[int] = frozenset()) -> tuple[Path, dict]:
    path = tmp_path / "capture"
    receipt = defillama.capture(defillama.DATASET_ID, path, opener=opener(skip))
    return path, receipt


def test_catalog_declares_five_fixed_windows():
    catalog = load_catalog()
    endpoints = [item for item in source(catalog, "defillama")["endpoints"] if item["id"].startswith("avax-price-window")]
    starts = [int(parse_qs(urlparse(item["url"]).query)["start"][0]) for item in endpoints]
    assert starts[0] == int(SERIES_START.timestamp()) and all(b - a == 500 * 86_400 for a, b in zip(starts, starts[1:]))
    definition = next(item for item in catalog["datasets"] if item["id"] == defillama.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(defillama.TABLE_COLUMNS)


def test_capture_build_and_check_round_trip(tmp_path):
    capture_dir, receipt = make_capture(tmp_path)
    assert len(receipt["responses"]) == 5 and receipt["schema_version"] == "defillama-capture/v1"
    dataset_dir = tmp_path / "dataset"
    build = defillama.build(defillama.DATASET_ID, capture_dir, dataset_dir)
    assert build["summary"]["rows"] == 160 and build["summary"]["observed_from"] == "2020-09-22"
    assert build["summary"]["skipped_dates"] == 0 and build["summary"]["confidence_min"] == 0.99
    validation = defillama.check(capture_dir, dataset_dir)
    assert validation["status"] == "pass", validation["findings"]
    with pytest.raises(DataError, match="reference series"):
        defillama.check(capture_dir, dataset_dir, against=dataset_dir)


def test_check_reports_large_gaps_and_counts_small_ones(tmp_path):
    capture_dir, _ = make_capture(tmp_path, skip={10, 40, 41, 42, 43})
    validation = defillama.check(capture_dir)
    assert validation["summary"]["skipped_dates"] == 2
    assert validation["findings"] == ["1 rows follow a gap of more than three days"]


def test_coingecko_cross_check_against_reference(tmp_path):
    reference_capture, _ = make_capture(tmp_path / "reference")
    reference_dir = tmp_path / "reference" / "dataset"
    defillama.build(defillama.DATASET_ID, reference_capture, reference_dir)
    days = [(SERIES_START + timedelta(days=index)) for index in range(100, 140)]
    chart = {"prices": [], "market_caps": [], "total_volumes": []}
    for index, stamp in enumerate(days):
        ms = int(stamp.timestamp() * 1000)
        price = (10 + math.sin((stamp - SERIES_START).days / 7)) * (1.5 if index == 5 else 1.0)
        chart["prices"].append([ms, price]); chart["market_caps"].append([ms, price * 4e8]); chart["total_volumes"].append([ms, 1e8])

    class Response:
        status, headers = 200, {"Content-Type": "application/json"}
        body = json.dumps(chart).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return self.body

    capture_dir = tmp_path / "coingecko"
    coingecko.capture(coingecko.DATASET_ID, capture_dir, opener=lambda request, timeout: Response())
    validation = coingecko.check(capture_dir, against=reference_dir)
    assert validation["checked"][-1] == "reference price cross-check"
    assert validation["summary"]["cross_check_days"] == 40 and validation["summary"]["cross_check_days_beyond_tolerance"] == 1
    assert validation["findings"] == ["1 days differ from the reference price by more than 10%"]
