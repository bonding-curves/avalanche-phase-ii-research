"""The Coin Metrics Bitcoin price and its Binance BTC/USDT reference, from page- and archive-shaped fixtures, no network."""

from __future__ import annotations

import io
import json
import math
import zipfile
from datetime import UTC, date, datetime, timedelta

import pytest

from avalanche_research.catalog import DataError, load_catalog, sha256
from avalanche_research.sources import binance_btc, coinmetrics

END = date(2017, 10, 3)
FIRST = date(2017, 8, 1)


def prices(shift: int = 0, scale: float = 1.0, until: date = END) -> dict[date, float]:
    """A wandering price; ``shift`` moves every value one or more days later, ``scale`` multiplies the days before ``until``."""
    days = [FIRST + timedelta(days=offset) for offset in range((END - FIRST).days + 5)]
    base = {day: 4000 * math.exp(0.05 * math.sin(index * 1.7) + 0.002 * index) for index, day in enumerate(days)}
    moved = {day: base[day - timedelta(days=shift)] if day - timedelta(days=shift) in base else base[day] for day in days}
    return {day: moved[day] * (scale if day < until else 1.0) for day in days if day < END}


def coinmetrics_pages(values: dict[date, float], split: int = 40, skip: date | None = None):
    days = [day for day in sorted(values) if day != skip]
    points = [{"asset": "btc", "time": f"{day}T00:00:00.000000000Z", "PriceUSD": repr(values[day])} for day in days]
    first = coinmetrics._url(END, load_catalog())
    second = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?next_page_token=abc"
    bodies = {first: json.dumps({"data": points[:split], "next_page_url": second}).encode(),
              second: json.dumps({"data": points[split:]}).encode()}
    return lambda url, timeout: bodies[url]


def candle(day: date, close: float) -> str:
    stamp = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp()) * 1000
    return f"{stamp},{close * 0.99},{close * 1.01},{close * 0.98},{close},10,{stamp + 1},{close * 10},42,5,{close * 5},0"


def binance_archive(values: dict[date, float], tamper: str | None = None):
    bodies = {}
    for item in binance_btc.files(END, load_catalog()):
        label = item["name"][len("BTCUSDT-1d-"):-len(".zip")]
        days = [day for day in values if (f"{day:%Y-%m}" == label if len(label) == 7 else day.isoformat() == label)]
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as handle:
            handle.writestr("candles.csv", "\n".join(candle(day, values[day]) for day in sorted(days)) + "\n")
        body = buffer.getvalue()
        bodies[item["url"]] = body
        bodies[item["url"] + ".CHECKSUM"] = f"{sha256(body if item['name'] != tamper else b'x')}  {item['name']}\n".encode()
    return lambda url, timeout: bodies[url]


TESTED_FROM = date(2017, 9, 1)


@pytest.fixture
def reference(tmp_path, monkeypatch):
    """A built binance.btc-usdt-daily run whose closes are the unshifted prices; the check tests days from TESTED_FROM."""
    monkeypatch.setattr(coinmetrics, "CROSS_CHECK_START", TESTED_FROM)
    values = {day: price for day, price in prices().items() if day >= binance_btc.FIRST_DAY}
    binance_btc.capture(binance_btc.DATASET_ID, tmp_path / "bn" / "capture", parameters={"end": END.isoformat()},
                        download=binance_archive(values))
    binance_btc.build(binance_btc.DATASET_ID, tmp_path / "bn" / "capture", tmp_path / "bn" / "dataset")
    return tmp_path / "bn" / "dataset"


def test_catalog_declares_both_datasets():
    catalog = {item["id"]: item for item in load_catalog()["datasets"]}
    assert [field["name"] for field in catalog[coinmetrics.DATASET_ID]["fields"]] == list(coinmetrics.COLUMNS)
    assert [field["name"] for field in catalog[binance_btc.DATASET_ID]["fields"]] == list(binance_btc.COLUMNS)


def test_the_request_asks_for_every_day_before_end_from_the_start():
    url = coinmetrics._url(END, load_catalog())
    assert "assets=btc" in url and "metrics=PriceUSD" in url and "paging_from=start" in url
    assert url.endswith("&end_time=2017-10-02")


def test_capture_follows_pages_and_builds_one_row_per_day(tmp_path):
    values = prices()
    receipt = coinmetrics.capture(coinmetrics.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()},
                                  download=coinmetrics_pages(values))
    assert len(receipt["files"]) == 2
    built = coinmetrics.build(coinmetrics.DATASET_ID, tmp_path / "capture", tmp_path / "dataset")
    assert built["summary"] == {"rows": len(values), "first_day": "2017-08-01", "last_day": "2017-10-02"}
    _, rows = coinmetrics.read_rows(tmp_path / "capture")
    assert rows[0][2] is None
    assert rows[5][2] == pytest.approx(math.log(values[FIRST + timedelta(days=5)] / values[FIRST + timedelta(days=4)]))
    assert coinmetrics.check(tmp_path / "capture", tmp_path / "dataset")["status"] == "pass"


def test_a_missing_day_is_refused(tmp_path):
    coinmetrics.capture(coinmetrics.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()},
                        download=coinmetrics_pages(prices(), skip=date(2017, 9, 9)))
    with pytest.raises(DataError, match="1 missing"):
        coinmetrics.read_rows(tmp_path / "capture")


def test_a_next_page_off_the_api_host_is_refused(tmp_path):
    first = coinmetrics._url(END, load_catalog())
    body = json.dumps({"data": [], "next_page_url": "https://example.org/elsewhere"}).encode()
    with pytest.raises(DataError, match="outside the community API"):
        coinmetrics.capture(coinmetrics.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()},
                            download=lambda url, timeout: body if url == first else b"")
    assert not (tmp_path / "capture").exists()


def test_a_changed_page_is_refused(tmp_path):
    coinmetrics.capture(coinmetrics.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()},
                        download=coinmetrics_pages(prices()))
    (tmp_path / "capture" / "raw" / "page-00.json").write_bytes(b'{"data": []}')
    with pytest.raises(DataError, match="differs from its receipt"):
        coinmetrics.read_rows(tmp_path / "capture")


def test_the_binance_reference_refuses_a_file_that_differs_from_its_checksum(tmp_path):
    with pytest.raises(DataError, match="published SHA-256"):
        binance_btc.capture(binance_btc.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()},
                            download=binance_archive(prices(), tamper="BTCUSDT-1d-2017-09.zip"))


def test_the_binance_reference_lists_months_then_days(reference):
    names = [item["name"] for item in binance_btc.files(END, load_catalog())]
    assert names == ["BTCUSDT-1d-2017-08.zip", "BTCUSDT-1d-2017-09.zip", "BTCUSDT-1d-2017-10-01.zip", "BTCUSDT-1d-2017-10-02.zip"]
    assert binance_btc.check(reference.parent / "capture", reference)["summary"]["first_day"] == "2017-08-17"


def test_agreeing_prices_pass_the_cross_check(tmp_path, reference):
    coinmetrics.capture(coinmetrics.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()},
                        download=coinmetrics_pages(prices(scale=1.002)))
    result = coinmetrics.check(tmp_path / "capture", against=reference)
    assert result["status"] == "pass", result["findings"]
    assert result["summary"]["cross_check_days"] == (END - TESTED_FROM).days
    assert result["summary"]["full_overlap_days"] == (END - binance_btc.FIRST_DAY).days
    assert result["summary"]["cross_check_share_within_1pct"] == 1.0
    assert result["summary"]["cross_check_return_correlation"] == pytest.approx(1.0)


def test_prices_one_day_late_fail_the_return_correlation(tmp_path, reference):
    coinmetrics.capture(coinmetrics.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()},
                        download=coinmetrics_pages(prices(shift=1)))
    result = coinmetrics.check(tmp_path / "capture", against=reference)
    assert result["status"] == "attention"
    assert any("correlate" in finding for finding in result["findings"])


def test_prices_two_percent_high_fail_the_level_band(tmp_path, reference):
    coinmetrics.capture(coinmetrics.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()},
                        download=coinmetrics_pages(prices(scale=1.02)))
    result = coinmetrics.check(tmp_path / "capture", against=reference)
    assert result["summary"]["cross_check_share_within_1pct"] == 0.0
    assert any("within 1%" in finding for finding in result["findings"])


def test_a_reference_of_another_dataset_is_refused(tmp_path, reference):
    coinmetrics.capture(coinmetrics.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()},
                        download=coinmetrics_pages(prices()))
    coinmetrics.build(coinmetrics.DATASET_ID, tmp_path / "capture", tmp_path / "dataset")
    with pytest.raises(DataError, match="is a run of coinmetrics.btc-usd-daily"):
        coinmetrics.check(tmp_path / "capture", against=tmp_path / "dataset")


def test_disagreement_before_the_tested_window_is_reported_not_failed(tmp_path, reference):
    coinmetrics.capture(coinmetrics.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()},
                        download=coinmetrics_pages(prices(scale=1.02, until=TESTED_FROM)))
    result = coinmetrics.check(tmp_path / "capture", against=reference)
    assert result["status"] == "pass", result["findings"]
    assert result["summary"]["cross_check_share_within_1pct"] == 1.0
    assert result["summary"]["full_overlap_share_within_1pct"] < 0.99
