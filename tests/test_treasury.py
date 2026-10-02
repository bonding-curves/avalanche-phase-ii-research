from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from avalanche_research import treasury
from avalanche_research.catalog import DataError, load_catalog


def feed(year: int, days: list[tuple[str, dict[str, str]]]) -> bytes:
    entries = "".join(
        f'<entry><content type="application/xml"><m:properties><d:NEW_DATE>{date}T00:00:00</d:NEW_DATE>'
        + "".join(f"<d:{field}>{value}</d:{field}>" for field, value in values.items())
        + "</m:properties></content></entry>"
        for date, values in days
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices" '
        'xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">' + entries + "</feed>"
    ).encode()


FEEDS = {year: [] for year in range(2020, 2027)}
FEEDS[2020] = [("2020-09-22", {"BC_1MONTH": "0.09", "BC_3MONTH": "0.10", "BC_1YEAR": "0.13", "BC_10YEAR": "0.67", "BC_1_5MONTH": ""}),
               ("2020-09-23", {"BC_1MONTH": "0.08", "BC_3MONTH": "0.10", "BC_1YEAR": "0.12", "BC_10YEAR": "0.68"})]
FEEDS[2026] = [("2026-09-14", {"BC_1MONTH": "3.94", "BC_3MONTH": "4.11", "BC_1YEAR": "4.37", "BC_10YEAR": "4.97", "BC_30YEARDISPLAY": "5.6"})]


class Response:
    def __init__(self, body: bytes):
        self.body, self.status, self.headers = body, 200, {"Content-Type": "text/xml"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self) -> bytes:
        return self.body


def opener(feeds=FEEDS):
    def open_request(request, timeout):
        assert request.get_method() == "GET"
        year = int(parse_qs(urlparse(request.full_url).query)["field_tdr_date_value"][0])
        return Response(feed(year, feeds[year]))

    return open_request


def make_capture(tmp_path: Path, feeds=FEEDS) -> Path:
    path = tmp_path / "capture"
    treasury.capture(treasury.DATASET_ID, path, opener=opener(feeds))
    return path


def test_catalog_declares_seven_yearly_xml_feeds():
    catalog = load_catalog()
    definition = next(item for item in catalog["datasets"] if item["id"] == treasury.DATASET_ID)
    assert len(definition["endpoint_ids"]) == 7 and [field["name"] for field in definition["fields"]] == list(treasury.TABLE_COLUMNS)
    preview = treasury.capture_preview(treasury.DATASET_ID, Path("x"))
    assert {item["content"] for item in preview["requests"]} == {"xml"}


def test_capture_build_and_check_round_trip(tmp_path):
    capture_dir = make_capture(tmp_path)
    assert (capture_dir / "raw" / "daily-yield-curve-2020.xml").is_file()
    dataset_dir = tmp_path / "dataset"
    build = treasury.build(treasury.DATASET_ID, capture_dir, dataset_dir)
    assert build["summary"] == pytest.approx({
        "rows": 12, "observed_from": "2020-09-22", "observed_to": "2026-09-14", "observation_dates": 3, "tenors": 4,
        "three_month_yield_median": 0.001, "one_year_yield_median": 0.0013, "yield_rate_min": 0.0008, "yield_rate_max": 0.0497,
    })
    validation = treasury.check(capture_dir, dataset_dir)
    assert validation["status"] == "attention"
    assert validation["findings"] == ["1 dates follow a gap of more than a week"]


def test_malformed_feed_values_are_rejected(tmp_path):
    feeds = {year: [] for year in range(2020, 2027)}
    feeds[2021] = [("2021-01-04", {"BC_3MONTH": "n/a"})]
    with pytest.raises(DataError, match="non-numeric yield"):
        treasury.check(make_capture(tmp_path, feeds))
