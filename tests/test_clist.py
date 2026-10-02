"""The C-Chain block list capture and its daily burn, against a fake Data API."""

from __future__ import annotations

import json
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from avalanche_research import clist
from avalanche_research.catalog import DataError, canonical_bytes, load_catalog, sha256

DAY = 86_400
START = int(datetime(2026, 9, 14, tzinfo=UTC).timestamp())
# Five blocks a day from 2026-09-14 to 2026-09-17 at hours 0, 5, 10, 15, 20, each paying its height in wei.
BLOCKS = [(1000 + index, START + (index // 5) * DAY + (index % 5) * 5 * 3600) for index in range(20)]


def fake(url, timeout):
    token = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("pageToken", ["0"])[0]
    newest_first = sorted(BLOCKS, reverse=True)
    start = int(token)
    page = newest_first[start: start + 3]
    blocks = [{"blockNumber": str(height), "blockHash": f"0x{height}", "blockTimestamp": stamp, "txCount": 2, "gasUsed": "10",
               "baseFee": "1", "feesSpent": str(height)} for height, stamp in page]
    following = start + 3
    return json.dumps({"blocks": blocks, **({"nextPageToken": str(following)} if following < len(newest_first) else {})}).encode(), {}


def test_catalog_declares_both_tables():
    catalog = {item["id"]: item for item in load_catalog()["datasets"]}
    assert [field["name"] for field in catalog[clist.DATASET_ID]["fields"]] == list(clist.COLUMNS)
    assert [field["name"] for field in catalog[clist.DAILY_ID]["fields"]] == list(clist.DAILY_COLUMNS)


def test_pages_back_to_the_date_and_sums_complete_days(tmp_path):
    runs = tmp_path / "runs"
    receipt = clist.capture(clist.DATASET_ID, runs / "list" / "capture", parameters={"from_date": "2026-09-15"}, request=fake)
    # Paging stops at the first page reaching before 2026-09-15.
    assert len(receipt["pages"]) == 6
    clist.build(clist.DATASET_ID, runs / "list" / "capture", runs / "list" / "dataset")
    assert clist.check(runs / "list" / "capture")["status"] == "pass"
    clist.derive(clist.DAILY_ID, runs / "daily", root=runs)
    rows = duckdb.connect().execute("SELECT date_utc::VARCHAR, burned_wei, block_count, first_block, previous_last_block, next_first_block, expected_receipts"
                                    " FROM read_parquet(?) ORDER BY 1", [str(runs / "daily" / "dataset" / f"{clist.DAILY_TABLE}.parquet")]).fetchall()
    # 2026-09-15 is the first listed day and 2026-09-17 the last, both partial, so only 2026-09-16 is complete.
    assert rows == [("2026-09-16", sum(range(1010, 1015)), 5, 1010, 1009, 1015, 10)]
    assert clist.check(runs / "daily" / "capture", runs / "daily" / "dataset", root=runs)["status"] == "pass"


def test_the_overlap_check_compares_complete_share_days(tmp_path):
    runs = tmp_path / "runs"
    clist.capture(clist.DATASET_ID, runs / "list" / "capture", parameters={"from_date": "2026-09-14"}, request=fake)
    clist.build(clist.DATASET_ID, runs / "list" / "capture", runs / "list" / "dataset")
    clist.derive(clist.DAILY_ID, runs / "daily", root=runs)
    share = tmp_path / "share"
    share.mkdir()
    duckdb.connect().execute(f"COPY (SELECT DATE '2026-09-15' AS date_utc, 99::DECIMAL(38,0) AS burned_wei, 0 AS absent_blocks, 0 AS short_blocks"
                             f" UNION ALL SELECT DATE '2026-09-16', {sum(range(1010, 1015))}::DECIMAL(38,0), 0, 0) TO '{share / 's.parquet'}' (FORMAT PARQUET)")
    checked = clist.check(runs / "daily" / "capture", runs / "daily" / "dataset", against=share, root=runs)
    assert checked["summary"]["overlap"]["differing_days"] == ["2026-09-15"]


def test_a_broken_token_chain_is_refused(tmp_path):
    clist.capture(clist.DATASET_ID, tmp_path / "capture", parameters={"from_date": "2026-09-15"}, request=fake)
    receipt = json.loads((tmp_path / "capture" / "capture.json").read_text())
    lines = (tmp_path / "capture" / "raw" / "pages.jsonl").read_bytes().splitlines()
    page = json.loads(lines[1])
    page["page_token"] = "elsewhere"
    lines[1] = json.dumps(page, separators=(",", ":"), sort_keys=True).encode()
    body = b"".join(line + b"\n" for line in lines)
    (tmp_path / "capture" / "raw" / "pages.jsonl").write_bytes(body)
    receipt["pages"][1]["sha256"] = sha256(lines[1])
    receipt["responses"][0].update({"bytes": len(body), "sha256": sha256(body)})
    (tmp_path / "capture" / "capture.json").write_bytes(canonical_bytes(receipt))
    with pytest.raises(DataError, match="token"):
        clist.read_rows(tmp_path / "capture")
    assert Path(tmp_path / "capture").is_dir()


def fake_p(url, timeout):
    body, metadata = fake(url, timeout)
    value = json.loads(body)
    for item in value["blocks"]:
        height = int(item["blockNumber"])
        item.update({"blockType": "BanffStandardBlock", "currentSupply": str(474 * 10**15 + height), "activeL1Validators": 583,
                     "l1ValidatorsAccruedFees": 28_833_000_000 + height})
    return json.dumps(value).encode(), metadata


def test_the_p_chain_list_keeps_the_supply_and_l1_counters(tmp_path):
    clist.capture(clist.P_LIST_ID, tmp_path / "capture", parameters={"from_date": "2026-09-16"}, request=fake_p)
    clist.build(clist.P_LIST_ID, tmp_path / "capture", tmp_path / "dataset")
    assert clist.check(tmp_path / "capture")["status"] == "pass"
    rows = duckdb.connect().execute("SELECT block_height, current_supply_navax, active_l1_validators FROM read_parquet(?) ORDER BY 1",
                                    [str(tmp_path / "dataset" / "p-chain-block-list.parquet")]).fetchall()
    assert rows[0] == (1010, 474 * 10**15 + 1010, 583) and len(rows) == 10


def test_the_daily_table_reads_every_block_list_run_once(tmp_path):
    runs = tmp_path / "runs"
    for name, first in (("early", "2026-09-14"), ("late", "2026-09-16")):
        clist.capture(clist.DATASET_ID, runs / name / "capture", parameters={"from_date": first}, request=fake)
        clist.build(clist.DATASET_ID, runs / name / "capture", runs / name / "dataset")
    result = clist.derive(clist.DAILY_ID, runs / "daily", root=runs)
    assert result["build"]["summary"]["block_list_runs"] == 2 and result["build"]["summary"]["missing_heights"] == 0
    assert result["build"]["summary"]["first_date"] == "2026-09-15" and result["build"]["summary"]["last_date"] == "2026-09-16"
    assert clist.check(runs / "daily" / "capture", runs / "daily" / "dataset", root=runs)["status"] == "pass"
