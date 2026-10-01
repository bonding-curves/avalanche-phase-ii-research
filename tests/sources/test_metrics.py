from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import duckdb
import pytest

from avalanche_research.sources import metrics
from avalanche_research.catalog import DataError, load_catalog


FIRST = date(2021, 2, 28)
CAPTURE_DAY = date(2021, 3, 20)
BASE = {"validatorCount": 800, "delegatorCount": 5000, "validatorWeight": 240 * 10**15, "delegatorWeight": 40 * 10**15,
        "activeAddresses": 4000, "txCount": 13000, "gasUsed": 1_500_000_000, "feesPaid": 750.5, "avgGasPrice": 225.0}


def payload(metric: str, start: int, end: int, incomplete: bool = False, skip: date | None = None) -> dict:
    results = []
    day = max(FIRST, datetime.fromtimestamp(start, tz=timezone.utc).date())
    while day <= CAPTURE_DAY and datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).timestamp() < end:
        if day != skip:
            stamp = int(datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).timestamp())
            base = BASE[metric]
            results.append({"value": base + (day - FIRST).days * (1 if isinstance(base, int) else 0.5), "timestamp": stamp})
        day += timedelta(days=1)
    results.reverse()
    body = {"results": results}
    if incomplete:
        body["nextPageToken"] = "abc"
    return body


class Response:
    def __init__(self, value: dict):
        self.body = json.dumps(value).encode()
        self.status, self.headers = 200, {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self) -> bytes:
        return self.body


def opener(incomplete: bool = False, skip: date | None = None):
    def open_request(request, timeout):
        parsed = urlparse(request.full_url); query = parse_qs(parsed.query)
        metric = parsed.path.rsplit("/", 1)[1]
        return Response(payload(metric, int(query["startTimestamp"][0]), int(query["endTimestamp"][0]), incomplete, skip))

    return open_request


def make_capture(tmp_path: Path, spec=metrics.STAKING, **kwargs) -> Path:
    path = tmp_path / "capture"
    metrics.capture(spec.dataset_id, path, opener=opener(**kwargs))
    return path


@pytest.mark.parametrize("spec", [metrics.STAKING, metrics.ACTIVITY])
def test_catalog_declares_three_windows_per_metric(spec):
    catalog = load_catalog()
    definition = next(item for item in catalog["datasets"] if item["id"] == spec.dataset_id)
    assert len(definition["endpoint_ids"]) == 3 * len(spec.metrics)
    assert [field["name"] for field in definition["fields"]] == list(spec.table_columns)


def test_staking_build_check_and_reconciliation(tmp_path):
    capture_dir = make_capture(tmp_path)
    dataset_dir = tmp_path / "dataset"
    build = metrics.build(metrics.STAKING.dataset_id, capture_dir, dataset_dir)
    assert build["summary"]["rows"] == 21 and build["summary"]["observed_from"] == "2021-02-28" and build["summary"]["latest_validator_count"] == 820
    assert metrics.check(capture_dir, dataset_dir)["status"] == "pass"
    reference = tmp_path / "reference"; reference.mkdir()
    duckdb.connect().execute(f"""
        COPY (SELECT 'v' || i AS transaction_hash, TIMESTAMP '2021-02-27 12:00:00' + INTERVAL (i) DAY AS start_time,
                     TIMESTAMP '2021-06-01 00:00:00' AS end_time, 300000000000000::BIGINT AS stake_navax
              FROM range(1, 830) t(i)) TO '{reference / "primary-validator-stakes.parquet"}' (FORMAT PARQUET)
    """)
    validation = metrics.check(capture_dir, dataset_dir, (reference,))
    assert validation["checked"][-1] == "Snowflake staking reconciliation"
    assert validation["summary"]["validator_days_compared"] == 21 and validation["summary"]["validator_count_days_beyond_tolerance"] > 0
    assert validation["findings"] == ["21 of 21 days differ from the Snowflake validator count by more than 2%", "21 of 21 days differ from the Snowflake validator weight by more than 2%"]
    with pytest.raises(DataError, match="only the staking series"):
        metrics.check(make_capture(tmp_path / "activity", metrics.ACTIVITY), against=(reference,))


def test_activity_build_and_gap_finding(tmp_path):
    capture_dir = make_capture(tmp_path, metrics.ACTIVITY, skip=date(2021, 3, 10))
    build = metrics.build(metrics.ACTIVITY.dataset_id, capture_dir, tmp_path / "dataset")
    assert build["summary"]["rows"] == 20 and build["summary"]["skipped_dates"] == 1
    assert metrics.check(capture_dir)["findings"] == ["1 rows follow a gap of more than one day"]


def test_incomplete_page_is_rejected(tmp_path):
    with pytest.raises(DataError, match="incomplete pages"):
        metrics.check(make_capture(tmp_path, incomplete=True))
