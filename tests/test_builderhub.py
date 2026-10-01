"""Builder Hub uptime captures use a fake route, not network access."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from avalanche_research import builderhub, datasets
from avalanche_research.catalog import DataError, load_catalog

LIST = "https://build.avax.network/api/validators"
# Hours before the capture time, which is the real clock: a bucket after the capture is a BC3 finding.
END = (datetime.now(UTC) - timedelta(days=10)).replace(tzinfo=None, minute=0, second=0, microsecond=0)


def hours(end: datetime, count: int, value: float = 100.0, changed: dict[datetime, float] | None = None) -> list[dict]:
    points = []
    for step in range(count):
        bucket = end - timedelta(hours=count - 1 - step)
        points.append({"bucket": bucket.strftime("%Y-%m-%dT%H:00:00Z"), "p50_uptime": (changed or {}).get(bucket, value)})
    return points


def detail(node: str, end: datetime, count: int = 48, changed: dict | None = None) -> dict:
    return {"node_id": node, "current_p50_uptime": 99.5, "bench_observers": 3, "weight": 2_000_000_000_000, "delegator_weight": 0, "delegator_count": 0,
            "delegation_fee": 2, "potential_reward": 8_000_000_000, "version": "avalanchego/1.15.0", "public_ip": "192.0.2.1:9651", "days_left": 6,
            "miss_rate_14d": 0, "missed_14d": 0, "proposed_14d": 4,
            "uptime_details": {"count": 1000, "min": 90.0, "max": 100, "avg": 99.8, "p50": 100, "p95": 100},
            "uptime": hours(end, count, changed=changed), "bench": [{"bucket": end.strftime("%Y-%m-%d"), "bench_total": 0}],
            "blocks": [{"hour": end.strftime("%Y-%m-%d %H:00:00"), "proposed": 1, "missed": 0}], "slots": [{"slot": 0, "cnt": 5}]}


class FakeHub:
    def __init__(self, nodes: list[str], end: datetime, count: int = 48, fail: set[str] | None = None, changed: dict | None = None):
        self.nodes, self.end, self.count, self.fail, self.changed = nodes, end, count, fail or set(), changed
        self.calls: list[str] = []

    def __call__(self, url: str, timeout: float):
        self.calls.append(url)
        if url == LIST:
            return json.dumps([{"node_id": node, "p50_uptime": 99.0} for node in self.nodes]).encode(), {"http_status": 200, "x_data_source": "absent"}
        node = url.rsplit("/", 1)[1]
        if node in self.fail:
            raise DataError(f"request failed for {url}: HTTP Error 500")
        source = "error-fallback-cache" if node.endswith("fallback") else "fresh"
        return json.dumps(detail(node, self.end, self.count, self.changed)).encode(), {"http_status": 200, "x_data_source": source}


def run(root: Path, name: str, hub: FakeHub, **parameters: str) -> Path:
    directory = root / name
    builderhub.capture(builderhub.DATASET_ID, directory / "capture", 5, {"previous": "none", **parameters}, request=hub, sleep=lambda _: None)
    builderhub.build(builderhub.DATASET_ID, directory / "capture", directory / "dataset")
    return directory


def test_catalog_declares_both_datasets():
    catalog = load_catalog()
    ids = {item["id"] for item in catalog["datasets"]}
    assert {builderhub.DATASET_ID, builderhub.DERIVED_ID} <= ids


def test_capture_build_and_check(tmp_path):
    end = END
    directory = run(tmp_path, "day1", FakeHub(["NodeID-a", "NodeID-b"], end))
    receipt = json.loads((directory / "capture" / "capture.json").read_text())
    assert receipt["nodes_listed"] == 2 and receipt["details"] == 2 and receipt["fallback_answers"] == 0
    rows = duckdb.sql(f"SELECT count(*), min(bucket_utc), max(bucket_utc) FROM read_parquet('{directory / 'dataset' / 'uptime-hourly.parquet'}')").fetchone()
    assert rows == (96, end - timedelta(hours=47), end)
    assert duckdb.sql(f"SELECT count(*) FROM read_parquet('{directory / 'dataset' / 'validators.parquet'}')").fetchone()[0] == 2
    result = builderhub.check(directory / "capture", directory / "dataset")
    assert result["status"] == "pass", result["findings"]


def test_a_failed_capture_keeps_its_lines_and_resumes(tmp_path):
    end = END
    hub = FakeHub(["NodeID-a", "NodeID-b", "NodeID-c"], end, fail={"NodeID-c"})
    output = tmp_path / "day1" / "capture"
    with pytest.raises(DataError, match="resumes"):
        builderhub.capture(builderhub.DATASET_ID, output, 5, {"previous": "none", "workers": "1", "unavailable_limit": "0"}, request=hub,
                           sleep=lambda _: None)
    partial = tmp_path / "day1" / ".capture.partial"
    assert len((partial / builderhub.DETAIL_RAW).read_bytes().splitlines()) == 2
    hub.fail.clear()
    hub.calls.clear()
    builderhub.capture(builderhub.DATASET_ID, output, 5, {"previous": "none", "unavailable_limit": "0"}, request=hub, sleep=lambda _: None)
    assert hub.calls == [f"{LIST}/NodeID-c"]
    assert json.loads((output / "capture.json").read_text())["details"] == 3
    assert not partial.exists()


def test_ended_nodes_are_asked_again_and_fallback_is_flagged(tmp_path):
    end = END
    run(tmp_path, "day1", FakeHub(["NodeID-a", "NodeID-gone"], end))
    hub = FakeHub(["NodeID-a", "NodeID-fallback"], end + timedelta(hours=24))
    directory = tmp_path / "day2"
    builderhub.capture(builderhub.DATASET_ID, directory / "capture", 5, {}, request=hub,
                       readings=datasets.readings(builderhub.READS, {}, tmp_path, builderhub.READ_DEFAULTS), sleep=lambda _: None)
    builderhub.build(builderhub.DATASET_ID, directory / "capture", directory / "dataset")
    receipt = json.loads((directory / "capture" / "capture.json").read_text())
    assert receipt["previous"]["run"] == "day1" and receipt["nodes_ended_requested"] == 1
    assert f"{LIST}/NodeID-gone" in hub.calls
    result = builderhub.check(directory / "capture", directory / "dataset", tmp_path / "day1" / "dataset")
    assert [finding[:3] for finding in result["findings"]] == ["BC4"]
    assert result["summary"]["shared_node_hours"] > 0


def test_a_gap_between_captures_is_a_bc5_finding(tmp_path):
    end = END
    run(tmp_path, "day1", FakeHub(["NodeID-a"], end))
    later = run(tmp_path, "day9", FakeHub(["NodeID-a"], end + timedelta(days=8)))
    result = builderhub.check(later / "capture", later / "dataset", tmp_path / "day1" / "dataset")
    assert any(finding.startswith("BC5") for finding in result["findings"])


def test_derived_merges_captures_and_marks_revisions(tmp_path):
    end = END
    run(tmp_path, "day1", FakeHub(["NodeID-a"], end))
    revised_hour = end - timedelta(hours=10)
    run(tmp_path, "day2", FakeHub(["NodeID-a"], end + timedelta(hours=24), changed={revised_hour: 97.5}))
    output = tmp_path / "hourly"
    value = builderhub.derive(builderhub.DERIVED_ID, output, None, tmp_path)
    assert value["build"]["summary"]["rows"] == 72 and value["build"]["summary"]["captures"] == 2
    row = duckdb.sql(f"SELECT p50_uptime_pct, captures, revised FROM read_parquet('{output / 'dataset' / 'validator-uptime-hourly.parquet'}') WHERE bucket_utc = '{revised_hour}'").fetchone()
    assert row == (97.5, 2, True)
    result = builderhub.check(output / "capture", output / "dataset")
    assert result["dataset_id"] == builderhub.DERIVED_ID and result["status"] == "pass", result["findings"]


def test_import_wraps_the_preservation_copy(tmp_path):
    # The preserved receipt completed at a fixed time, so the series ends before it, not relative to today.
    end = datetime(2026, 9, 24, 8)
    source = tmp_path / "preserved"
    source.mkdir()
    (source / "validators.json").write_text(json.dumps([{"node_id": "NodeID-a"}]))
    (source / "validator-details.jsonl").write_text(json.dumps({"node_id": "NodeID-a", "body": detail("NodeID-a", end)}) + "\n")
    (source / "receipt.json").write_text(json.dumps({"started_at": "2026-09-24T08:05:32+00:00", "completed_at": "2026-09-24T08:11:47+00:00", "nodes": 1, "failed": []}))
    output = tmp_path / "imported" / "capture"
    receipt = builderhub.capture(builderhub.DATASET_ID, output, 5, {"import": str(source)}, request=None)
    assert receipt["completed_at"] == "2026-09-24T08:11:47+00:00" and receipt["import"]["imported_from"] == str(source)
    builderhub.build(builderhub.DATASET_ID, output, tmp_path / "imported" / "dataset")
    assert builderhub.check(output, tmp_path / "imported" / "dataset")["status"] == "pass"


def test_one_check_runs_continuity_and_the_node_set(tmp_path):
    run(tmp_path, "day1", FakeHub(["NodeID-a", "NodeID-b"], END))
    day2 = run(tmp_path, "day2", FakeHub(["NodeID-a", "NodeID-b"], END + timedelta(hours=24)))
    rpc = tmp_path / "rpc" / "dataset"
    rpc.mkdir(parents=True)
    duckdb.sql(f"COPY (SELECT * FROM (VALUES ('NodeID-a'), ('NodeID-z')) t(node_id)) TO '{rpc / 'current-validators.parquet'}' (FORMAT PARQUET)")
    (rpc / "build.json").write_text(json.dumps({"dataset_id": "p-chain-rpc.current-validators", "outputs": [{"path": "current-validators.parquet"}]}))
    result = builderhub.check(day2 / "capture", day2 / "dataset", [tmp_path / "day1" / "dataset", rpc])
    assert {"BC6 agreement", "BC7 node set"} <= set(result["checked"])
    assert [finding[:3] for finding in result["findings"]] == ["BC7"]
    assert (result["summary"]["only_rpc"], result["summary"]["only_builder_hub"]) == (1, 1)


def test_a_node_the_source_cannot_serve_does_not_stop_the_day(tmp_path):
    hub = FakeHub(["NodeID-a", "NodeID-b", "NodeID-broken"], END, fail={"NodeID-broken"})
    directory = run(tmp_path, "day1", hub, workers="1")
    receipt = json.loads((directory / "capture" / "capture.json").read_text())
    assert receipt["details"] == 2 and [item["node_id"] for item in receipt["unavailable"]] == ["NodeID-broken"]
    result = builderhub.check(directory / "capture", directory / "dataset")
    # BC9 is attention, not the lost history of BC1.
    assert [finding[:3] for finding in result["findings"]] == ["BC9"]


def test_ended_nodes_the_source_cannot_serve_never_count_as_an_outage(tmp_path):
    run(tmp_path, "day1", FakeHub(["NodeID-a"] + [f"NodeID-gone{index}" for index in range(5)], END))
    hub = FakeHub(["NodeID-a"], END + timedelta(hours=24), fail={f"NodeID-gone{index}" for index in range(5)})
    directory = tmp_path / "day2"
    receipt = builderhub.capture(builderhub.DATASET_ID, directory / "capture", 5, {"workers": "1"}, request=hub,
                                 readings=datasets.readings(builderhub.READS, {"workers": "1"}, tmp_path, builderhub.READ_DEFAULTS), sleep=lambda _: None)
    assert receipt["details"] == 1 and len(receipt["unavailable"]) == 5
    assert {item["requested_because"] for item in receipt["unavailable"]} == {"ended-since-previous"}


def test_the_previous_capture_is_resolved_by_the_command_line(tmp_path):
    """IB4: auto with no built run means no previous capture. A named run the command line did not resolve is refused."""
    assert datasets.readings(builderhub.READS, {}, tmp_path, builderhub.READ_DEFAULTS) == {}
    assert builderhub._previous("auto", {}) is None and builderhub._previous("none", None) is None
    with pytest.raises(DataError, match="not resolved"):
        builderhub._previous("day1", {})
    run(tmp_path, "day1", FakeHub(["NodeID-a"], END))
    reading = datasets.readings(builderhub.READS, {}, tmp_path, builderhub.READ_DEFAULTS)["previous"]
    assert reading["run"] == "day1" and builderhub._previous("auto", {"previous": reading})["nodes"] == ["NodeID-a"]
    with pytest.raises(DataError, match="not resolved"):
        builderhub._previous("day0", {"previous": reading})
