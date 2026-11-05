"""Bybit AVAX perpetual funding from API-shaped pages, and its check against a built Binance run, no network."""

from __future__ import annotations

import json
import math
from datetime import date

import pytest

from avalanche_research.catalog import DataError, load_catalog
from avalanche_research.sources import binance_funding, bybit
from test_binance_funding import fake as binance_fake
from test_binance_funding import rates as binance_rates

HOUR = 3_600_000
END = date(2021, 11, 20)
LAUNCH = bybit.millis(bybit.FIRST_DAY)


def rates(offset: float = 0.0, end: date = END) -> dict[int, float]:
    """Events every 8 hours from 16:00 UTC on launch day; ``offset`` adds a rate per 8 hours to every event."""
    first = LAUNCH + 16 * HOUR
    stamps = range(first, bybit.millis(end), 8 * HOUR)
    return {stamp: round(0.0001 + 0.0002 * math.sin(index / 5) + offset, 8) for index, stamp in enumerate(stamps)}


def fake(events: dict[int, float], interval: int = 480, limit: int = bybit.PAGE_LIMIT):
    instrument = json.dumps({"retCode": 0, "result": {"list": [
        {"symbol": "AVAXUSDT", "launchTime": str(LAUNCH), "fundingInterval": interval}]}}).encode()
    newest_first = sorted(events, reverse=True)

    def download(url: str, timeout: float) -> bytes:
        if "instruments-info" in url:
            return instrument
        before = int(url.split("endTime=")[1])
        page = [{"symbol": "AVAXUSDT", "fundingRate": f"{events[stamp]:.8f}", "fundingRateTimestamp": str(stamp)}
                for stamp in newest_first if stamp <= before][:limit]
        return json.dumps({"retCode": 0, "retMsg": "OK", "result": {"category": "linear", "list": page}}).encode()
    return download


def binance_run(tmp_path, offset: float = 0.0):
    """A built Binance run from its listing to END, whose rates over Bybit's window are Bybit's less ``offset``."""
    events = binance_rates(END)
    events.update({stamp: round(rate - offset, 8) for stamp, rate in rates().items()})
    capture = tmp_path / "binance" / "capture"
    binance_funding.capture(binance_funding.DATASET_ID, capture, parameters={"end": END.isoformat()},
                            download=binance_fake(events, end=END))
    binance_funding.build(binance_funding.DATASET_ID, capture, tmp_path / "binance" / "dataset")
    return tmp_path / "binance" / "dataset"


def test_catalog_declares_the_dataset_with_binance_columns():
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == bybit.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(bybit.COLUMNS)
    assert list(bybit.COLUMNS) == list(binance_funding.COLUMNS)[:-1]


def test_capture_walks_back_to_launch_and_builds(tmp_path):
    events = rates()
    receipt = bybit.capture(bybit.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()}, download=fake(events))
    pages = [item for item in receipt["files"] if item["endpoint_id"] == bybit.HISTORY_ID]
    assert len(pages) == math.ceil(len(events) / bybit.PAGE_LIMIT)
    assert pages[0]["url"].endswith(f"&endTime={bybit.millis(END) - 1}")
    built = bybit.build(bybit.DATASET_ID, tmp_path / "capture", tmp_path / "dataset")
    assert built["summary"]["rows"] == len(events) and built["summary"]["first_day"] == "2021-09-15"
    assert built["summary"]["last_day"] == "2021-11-19" and built["summary"]["history_pages"] == len(pages)
    assert bybit.check(tmp_path / "capture", tmp_path / "dataset")["status"] == "pass"


def test_an_interval_other_than_8_hours_is_refused(tmp_path):
    bybit.capture(bybit.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()}, download=fake(rates(), interval=240))
    with pytest.raises(DataError, match="funding interval is 240 minutes"):
        bybit.read_rows(tmp_path / "capture")


def test_a_failed_answer_is_refused(tmp_path):
    body = json.dumps({"retCode": 10006, "retMsg": "Too many visits"}).encode()
    with pytest.raises(DataError, match="not a successful answer"):
        bybit.capture(bybit.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()}, download=lambda url, timeout: body)
    assert not (tmp_path / "capture").exists()


def test_close_30_day_means_pass_the_venue_check(tmp_path):
    reference = binance_run(tmp_path, offset=0.00001)  # 1.1 points a year apart
    bybit.capture(bybit.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()}, download=fake(rates()))
    result = bybit.check(tmp_path / "capture", against=reference)
    assert result["status"] == "pass", result["findings"]
    summary = result["summary"]
    assert summary["cross_check_days"] == (END - bybit.FIRST_DAY).days - 29
    assert summary["cross_check_share_within_5_points"] == 1.0
    assert summary["cross_check_median_gap_points"] == pytest.approx(1.095, abs=0.01)


def test_30_day_means_6_points_apart_fail_the_venue_check(tmp_path):
    reference = binance_run(tmp_path, offset=0.0000548)  # 6.0 points a year apart
    bybit.capture(bybit.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()}, download=fake(rates()))
    result = bybit.check(tmp_path / "capture", against=reference)
    assert result["status"] == "attention"
    assert result["summary"]["cross_check_share_within_5_points"] == 0.0
    assert "at least 80% is required" in result["findings"][0]


def test_a_reference_of_another_dataset_is_refused(tmp_path):
    bybit.capture(bybit.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()}, download=fake(rates()))
    bybit.build(bybit.DATASET_ID, tmp_path / "capture", tmp_path / "dataset")
    with pytest.raises(DataError, match="is a run of bybit.avax-usdt-perp-funding"):
        bybit.check(tmp_path / "capture", against=tmp_path / "dataset")
