from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from avalanche_research import cli, coingecko
from avalanche_research.catalog import DataError, load_catalog


START = datetime(2025, 9, 15, tzinfo=timezone.utc)


def chart(days: int = 40, gap_at: int | None = None, partial_last: bool = True) -> dict:
    prices, caps, volumes = [], [], []
    for index in range(days):
        if index == gap_at:
            continue
        stamp = START + timedelta(days=index)
        if partial_last and index == days - 1:
            stamp += timedelta(hours=23, minutes=5)
        ms = int(stamp.timestamp() * 1000)
        price = 20 + math.sin(index / 3)
        prices.append([ms, price])
        caps.append([ms, price * 4.2e8])
        volumes.append([ms, 3e8 + index * 1e6])
    return {"prices": prices, "market_caps": caps, "total_volumes": volumes}


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


def opener(value: dict):
    def open_request(request, timeout):
        assert "avalanche-2/market_chart" in request.full_url and 1 <= timeout <= 600
        return Response(value)

    return open_request


def make_capture(tmp_path: Path, value: dict | None = None) -> tuple[Path, dict]:
    path = tmp_path / "capture"
    receipt = coingecko.capture(coingecko.DATASET_ID, path, opener=opener(value or chart()))
    return path, receipt


def test_catalog_declares_the_coingecko_dataset():
    catalog = load_catalog()
    definition = next(item for item in catalog["datasets"] if item["id"] == coingecko.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(coingecko.TABLE_COLUMNS)


def test_capture_build_and_check_round_trip(tmp_path):
    capture_dir, receipt = make_capture(tmp_path)
    assert receipt["schema_version"] == "coingecko-capture/v1" and receipt["capture_id"].startswith("capture:coingecko:")
    dataset_dir = tmp_path / "dataset"
    build = coingecko.build(coingecko.DATASET_ID, capture_dir, dataset_dir)
    assert build["summary"]["rows"] == 40 and build["summary"]["partial_day_rows"] == 1
    assert build["summary"]["observed_from"] == "2025-09-15" and build["summary"]["rows_without_volatility"] == 30
    validation = coingecko.check(capture_dir, dataset_dir)
    assert validation["status"] == "pass", validation["findings"]
    with pytest.raises(DataError, match="unknown dataset"):
        coingecko.build("snowpeer.network-summary", capture_dir, tmp_path / "wrong")


def test_check_reports_gaps_and_partial_days(tmp_path):
    value = chart(gap_at=5)
    for key in ("prices", "market_caps", "total_volumes"):
        value[key][3][0] += 3_600_000
    capture_dir, _ = make_capture(tmp_path, value)
    validation = coingecko.check(capture_dir)
    assert validation["findings"] == [
        "1 rows follow a gap of more than one day",
        "1 rows are partial days before the final observation",
    ]


def test_malformed_response_is_rejected(tmp_path):
    capture_dir, _ = make_capture(tmp_path, {"prices": [[1, -1.0]], "market_caps": [[1, 1.0]], "total_volumes": [[1, 1.0]]})
    with pytest.raises(DataError, match="non-positive price"):
        coingecko.check(capture_dir)


def test_cli_preview_and_parameters(tmp_path):
    runner = CliRunner()
    output = tmp_path / "capture"
    preview = runner.invoke(cli.cli, ["data", "fetch", coingecko.DATASET_ID, "--output", str(output), "--preview", "--json"])
    assert preview.exit_code == 0, preview.output
    assert json.loads(preview.output)["preview"]["requests"][0]["endpoint_id"] == "avax-market-chart"
    rejected = runner.invoke(cli.cli, ["data", "fetch", coingecko.DATASET_ID, "--output", str(output), "--param", "days=30", "--preview"])
    assert rejected.exit_code != 0 and "accepts no parameters" in str(rejected.exception)
