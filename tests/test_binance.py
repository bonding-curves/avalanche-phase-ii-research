"""Binance archive captures use archive-shaped zip files and checksum files, not network access."""

from __future__ import annotations

import io
import math
import zipfile
from datetime import UTC, date, datetime, timedelta

import pytest

from avalanche_research import binance
from avalanche_research.catalog import DataError, load_catalog, sha256

END = date(2020, 11, 4)


def candle(day: date, close: float) -> str:
    stamp = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())
    opened = stamp * 1_000_000 if day.year >= 2025 else stamp * 1_000
    return f"{opened},{close - 0.1},{close + 0.2},{close - 0.3},{close},1000,{opened + 1},{close * 1000},42,500,{close * 500},0"


def archive(days: list[date], closes: dict[date, float]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as handle:
        handle.writestr("candles.csv", "\n".join(candle(day, closes[day]) for day in days) + "\n")
    return buffer.getvalue()


def fake_archive(end: date = END, skip: date | None = None, tamper: str | None = None):
    closes = {binance.FIRST_DAY + timedelta(days=offset): 5 + math.sin(offset) for offset in range((end - binance.FIRST_DAY).days)}
    bodies = {}
    for item in binance.files(end, load_catalog()):
        name = item["name"][len("AVAXUSDT-1d-"):-len(".zip")]
        if len(name) == 7:
            year, month = map(int, name.split("-"))
            days = [day for day in closes if (day.year, day.month) == (year, month)]
        else:
            days = [date.fromisoformat(name)]
        body = archive([day for day in days if day != skip], closes)
        bodies[item["url"]] = body
        published = sha256(body if item["name"] != tamper else b"other")
        bodies[item["url"] + ".CHECKSUM"] = f"{published}  {item['name']}\n".encode()
    return (lambda url, timeout: bodies[url]), closes


def test_catalog_declares_the_dataset():
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == binance.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(binance.COLUMNS)


def test_monthly_files_then_daily_files_of_the_open_month():
    names = [item["name"] for item in binance.files(END, load_catalog())]
    assert names == ["AVAXUSDT-1d-2020-09.zip", "AVAXUSDT-1d-2020-10.zip", "AVAXUSDT-1d-2020-11-01.zip", "AVAXUSDT-1d-2020-11-02.zip", "AVAXUSDT-1d-2020-11-03.zip"]


def test_capture_build_check_returns_and_volatility(tmp_path):
    download, closes = fake_archive()
    capture, dataset = tmp_path / "capture", tmp_path / "dataset"
    receipt = binance.capture(binance.DATASET_ID, capture, parameters={"end": END.isoformat()}, download=download)
    assert len(receipt["files"]) == 5
    built = binance.build(binance.DATASET_ID, capture, dataset)
    assert built["summary"] == {"rows": 43, "first_day": "2020-09-22", "last_day": "2020-11-03", "volatility_days": 13}
    assert binance.check(capture, dataset)["status"] == "pass"
    _, rows = binance.read_rows(capture)
    days = sorted(closes)
    assert rows[1][8] == pytest.approx(math.log(closes[days[1]] / closes[days[0]]))
    returns = [math.log(closes[days[i]] / closes[days[i - 1]]) for i in range(1, 31)]
    mean = sum(returns) / 30
    assert rows[30][9] == pytest.approx(math.sqrt(sum((r - mean) ** 2 for r in returns) / 29) * math.sqrt(365))
    assert rows[29][9] is None


def test_microsecond_open_times_from_2025():
    assert binance._candle_time("1785542400000000") == date(2026, 8, 1)
    assert binance._candle_time("1600732800000") == date(2020, 9, 22)


def test_a_file_whose_hash_differs_from_the_published_one_is_refused(tmp_path):
    download, _ = fake_archive(tamper="AVAXUSDT-1d-2020-10.zip")
    with pytest.raises(DataError, match="does not match its published SHA-256"):
        binance.capture(binance.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()}, download=download)
    assert not (tmp_path / "capture").exists()


def test_a_missing_day_is_refused(tmp_path):
    download, _ = fake_archive(skip=date(2020, 10, 7))
    binance.capture(binance.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()}, download=download)
    with pytest.raises(DataError, match="1 missing"):
        binance.read_rows(tmp_path / "capture")


@pytest.mark.parametrize("parameters", [{"end": "2020-09-01"}, {"end": "tomorrow"}, {"start": "2021-01-01"}])
def test_parameters_are_checked(parameters, tmp_path):
    with pytest.raises(DataError):
        binance.capture_preview(binance.DATASET_ID, tmp_path / "capture", parameters)


def test_the_usdt_open_is_checked_against_coingecko_usd_at_the_same_midnight(tmp_path):
    import duckdb

    download, closes = fake_archive()
    binance.capture(binance.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()}, download=download)
    reference = tmp_path / "coingecko"
    reference.mkdir()
    days = sorted(closes)
    # The fixture's day spans close - 0.3 to close + 0.2 with open close - 0.1. Day 5's reference is 3% above the open but
    # inside the range, a timing difference; day 6's is 30% above, outside it.
    moved = {days[5]: (closes[days[5]] - 0.1) * 1.03, days[6]: (closes[days[6]] - 0.1) * 1.3}
    values = ", ".join(f"(DATE '{day}', {moved.get(day, closes[day] - 0.1)}, FALSE)" for day in days[:10])
    duckdb.sql(f"COPY (SELECT * FROM (VALUES {values}) AS t(observation_date, price_usd, partial_day)) TO '{reference / 'avax-market-daily.parquet'}' (FORMAT PARQUET)")
    result = binance.check(tmp_path / "capture", against=reference)
    assert result["summary"]["cross_check_days"] == 10 and result["summary"]["cross_check_days_beyond_tolerance"] == 1
    assert result["findings"] == ["1 days differ from the reference price by more than 2%"]
