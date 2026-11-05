"""Binance AVAX perpetual funding from API-shaped pages and archive-shaped monthly files, no network."""

from __future__ import annotations

import io
import json
import math
import zipfile
from datetime import date, datetime, timedelta

import pytest

from avalanche_research.catalog import DataError, load_catalog, sha256
from avalanche_research.sources import binance_funding as funding
from avalanche_research.sources.public_market import NotPublished

END = date(2020, 11, 4)
HOUR = 3_600_000


def rates(end: date = END) -> dict[int, float]:
    """Events every 8 hours from 16:00 UTC on the listing day, the first stamped 4 ms late as Binance's is."""
    first = funding.millis(funding.FIRST_DAY) + 16 * HOUR
    count = (funding.millis(end) - first) // (8 * HOUR) + 1
    stamps = [first + 4 if index == 0 else first + index * 8 * HOUR for index in range(count)]
    return {stamp: round(0.0001 + 0.0003 * math.sin(index), 8) for index, stamp in enumerate(stamps) if stamp < funding.millis(end)}


def monthly(events: dict[int, float], month: date) -> bytes:
    lines = ["calc_time,funding_interval_hours,last_funding_rate"]
    lines += [f"{stamp},8,{rate:.8f}" for stamp, rate in sorted(events.items()) if funding.instant(stamp).date().replace(day=1) == month]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as handle:
        handle.writestr(f"AVAXUSDT-fundingRate-{month:%Y-%m}.csv", "\n".join(lines) + "\n")
    return buffer.getvalue()


def fake(events: dict[int, float], end: date = END, archive: dict[int, float] | None = None, unpublished: bool = False,
         limit: int = funding.API_LIMIT):
    """A download that answers the API in pages of ``limit`` rows and the archive from ``archive`` (default: the API)."""
    archive = events if archive is None else archive
    bodies = {}
    for position, item in enumerate(funding.archive_files(end, load_catalog())):
        if unpublished and position == len(funding.months(end)) - 1:
            continue
        body = monthly(archive, date.fromisoformat(item["name"][-11:-4] + "-01"))
        bodies[item["url"]] = body
        bodies[item["url"] + ".CHECKSUM"] = f"{sha256(body)}  {item['name']}\n".encode()
    stamps = sorted(events)

    def download(url: str, timeout: float) -> bytes:
        if url in bodies:
            return bodies[url]
        if "fundingRate-" in url:
            raise NotPublished(url)
        start = int(url.split("startTime=")[1].split("&")[0])
        page = [{"symbol": "AVAXUSDT", "fundingTime": stamp, "fundingRate": f"{events[stamp]:.8f}", "markPrice": ""}
                for stamp in stamps if stamp >= start][:limit]
        return json.dumps(page).encode()
    return download


def test_catalog_declares_the_dataset():
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == funding.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(funding.COLUMNS)


def test_capture_build_check_with_the_archive_as_record(tmp_path, monkeypatch):
    monkeypatch.setattr(funding, "API_LIMIT", 50)
    events = rates()
    receipt = funding.capture(funding.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()},
                              download=fake(events, limit=50))
    assert sum(item.get("endpoint_id") == funding.API_ID for item in receipt["files"]) == math.ceil(len(events) / 50)
    built = funding.build(funding.DATASET_ID, tmp_path / "capture", tmp_path / "dataset")
    summary = built["summary"]
    assert summary["rows"] == len(events) and summary["first_day"] == "2020-09-22" and summary["last_day"] == "2020-11-03"
    assert summary["archive_files"] == 2 and summary["archive_rows"] == summary["archive_rows_equal_to_api"]
    assert summary["api_rows_after_archive"] == 3 * 3
    result = funding.check(tmp_path / "capture", tmp_path / "dataset")
    assert result["status"] == "pass", result["findings"]


def test_rows_carry_8_hour_and_annual_units_and_daily_figures(tmp_path):
    events = rates()
    funding.capture(funding.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()}, download=fake(events))
    _, rows, _ = funding.read_rows(tmp_path / "capture")
    first = rows[0]
    assert first[0] == datetime(2020, 9, 22, 16, 0, 0, 4000) and first[1] == date(2020, 9, 22)
    assert first[3] == pytest.approx(first[2] * 3 * 365 * 100)
    assert first[4] == 1 and first[5] == pytest.approx(first[3])
    day = [row for row in rows if row[1] == date(2020, 10, 1)]
    assert [row[4] for row in day] == [3, 3, 3]
    assert day[0][5] == pytest.approx(sum(row[2] for row in day) * 365 * 100)
    daily = {row[1]: row[5] for row in rows}
    days = sorted(daily)
    assert all(row[6] is None for row in rows if row[1] < days[29])
    assert [row[6] for row in rows if row[1] == days[40]] == [pytest.approx(sum(daily[d] for d in days[11:41]) / 30)] * 3
    assert all(row[7] for row in rows if row[1] < date(2020, 11, 1)) and not any(row[7] for row in rows if row[1] >= date(2020, 11, 1))


def test_an_api_rate_that_differs_from_the_archive_is_refused(tmp_path):
    events = rates()
    archive = dict(events)
    changed = sorted(archive)[100]
    archive[changed] += 0.00000001
    funding.capture(funding.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()},
                    download=fake(events, archive=archive))
    with pytest.raises(DataError, match="1 API rates differ from the archive"):
        funding.read_rows(tmp_path / "capture")


def test_an_archived_rate_missing_from_the_api_is_refused(tmp_path):
    events = rates()
    api = dict(events)
    del api[sorted(api)[20]]
    with pytest.raises(DataError, match="missing from the API"):
        funding.capture(funding.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()},
                        download=fake(api, archive=events))
        funding.read_rows(tmp_path / "capture")


def test_an_irregular_interval_is_refused():
    events = rates()
    stamp = sorted(events)[10]
    events[stamp + 4 * HOUR] = 0.0001
    with pytest.raises(DataError, match="intervals are not 8 hours"):
        funding.funding_rows(events)


def test_an_unpublished_newest_month_leaves_its_rates_unconfirmed(tmp_path):
    events = rates()
    receipt = funding.capture(funding.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()},
                              download=fake(events, unpublished=True))
    assert receipt["unpublished_archive_files"] == ["AVAXUSDT-fundingRate-2020-10.zip"]
    _, rows, comparison = funding.read_rows(tmp_path / "capture")
    assert comparison["archive_last_month"] == "2020-09"
    assert not any(row[7] for row in rows if row[1] >= date(2020, 10, 1))


def test_an_unpublished_older_month_is_refused(tmp_path):
    events = rates()
    download = fake(events)

    def missing_september(url: str, timeout: float) -> bytes:
        if url.endswith("AVAXUSDT-fundingRate-2020-09.zip"):
            raise NotPublished(url)
        return download(url, timeout)
    with pytest.raises(NotPublished):
        funding.capture(funding.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()}, download=missing_september)
    assert not (tmp_path / "capture").exists()


def test_the_check_takes_no_reference(tmp_path):
    funding.capture(funding.DATASET_ID, tmp_path / "capture", parameters={"end": END.isoformat()}, download=fake(rates()))
    with pytest.raises(DataError, match="no --against"):
        funding.check(tmp_path / "capture", against=tmp_path)


def test_the_api_window_ends_a_millisecond_before_end():
    url = funding.api_url(funding.millis(funding.FIRST_DAY), END, load_catalog())
    assert url.startswith("https://fapi.binance.com/fapi/v1/fundingRate?symbol=AVAXUSDT&limit=1000&startTime=1600732800000")
    assert url.endswith(f"&endTime={funding.millis(END) - 1}")
    assert funding.millis(END) - funding.millis(END - timedelta(days=1)) == 24 * HOUR
