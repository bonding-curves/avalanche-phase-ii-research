"""The ledger by upgrade period, over three fake days around the Helicon activation of 2026-09-22 15:00 UTC."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pytest
import test_monetary as ledger_fixtures

from avalanche_research.core.catalog import (
    DataError,
    canonical_bytes,
    load_catalog,
    sha256,
)
from avalanche_research.datasets.derived import monetary, monetary_periods

WEI = 10**18
cycle_root = ledger_fixtures.root


def utc(*parts: int) -> datetime:
    """Naive UTC, as the tables store their timestamps."""
    return datetime(*parts, tzinfo=UTC).replace(tzinfo=None)


def make_run(root: Path, run: str, dataset_id: str, columns: dict[str, str], rows: list[tuple], inputs: list[dict] | None = None) -> dict:
    capture_dir, dataset_dir = root / run / "capture", root / run / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / "table.parquet"
    connection = duckdb.connect()
    connection.execute(f"CREATE TABLE t({', '.join(f'{name} {kind}' for name, kind in columns.items())})")
    connection.executemany(f"INSERT INTO t VALUES ({', '.join('?' for _ in columns)})", rows)
    connection.execute("COPY t TO ? (FORMAT PARQUET)", [str(parquet)])
    capture_id = f"capture:test:{run}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({"schema_version": "test/v1", "capture_id": capture_id, "dataset_id": dataset_id,
                                                                "completed_at": "2026-09-29T00:00:00Z", "inputs": inputs or []}))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({"schema_version": "test/v1", "dataset_id": dataset_id, "source_capture_id": capture_id,
                                                              "completed_at": "2026-09-29T00:00:00Z", "summary": {"rows": len(rows)},
                                                              "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}]}))
    return {"parquet": parquet.name, "sha256": sha256(body)}


@pytest.fixture
def root(tmp_path: Path, monkeypatch) -> Path:
    runs = tmp_path / "runs"
    # Only granite and helicon: the ledger starts the day before Helicon.
    monkeypatch.setattr(monetary_periods, "periods", lambda: [("granite", "2025-11-19 16:00:00"), ("helicon", "2026-09-22 15:00:00")])
    rewards = make_run(runs, "rewards", "derived.seamed-staking-rewards", {"rewarded_at": "TIMESTAMP", "realized_reward_navax": "BIGINT"},
                       [(utc(2026, 9, 22, 14, 59), 10 * 10**9), (utc(2026, 9, 22, 15, 0), 20 * 10**9), (utc(2026, 9, 23, 12), 40 * 10**9)])
    columns = {"date_utc": "DATE", "issued_rewards_wei": "DECIMAL(38,0)", "burned_p_wei": "DECIMAL(38,0)", "burned_x_wei": "DECIMAL(38,0)",
               "burned_c_evm_wei": "DECIMAL(38,0)", "burned_c_evm_gap_wei": "DECIMAL(38,0)", "burned_c_atomic_wei": "DECIMAL(38,0)",
               "burned_wei": "DECIMAL(38,0)", "total_supply_close_wei": "DECIMAL(38,0)", "active_validator_stake_wei": "DECIMAL(38,0)",
               "active_delegated_stake_wei": "DECIMAL(38,0)"}
    days = [(date(2026, 9, 21), 0, 1), (date(2026, 9, 22), 30, 2), (date(2026, 9, 23), 40, 3)]
    make_run(runs, "ledger", "derived.avax-monetary-daily", columns,
             [(day, issued * WEI, burn * WEI, 0, 0, 0, 0, burn * WEI, 100 * WEI, 40 * WEI, 10 * WEI) for day, issued, burn in days],
             inputs=[{"input_id": "staking-rewards", "dataset_id": "derived.seamed-staking-rewards", "run": "rewards", **rewards}])
    return runs


def test_catalog_declares_the_columns():
    fields = next(item for item in load_catalog()["datasets"] if item["id"] == monetary_periods.DATASET_ID)["fields"]
    assert [field["name"] for field in fields] == list(monetary_periods.TABLE_COLUMNS)


def test_issuance_splits_at_the_instant_and_days_follow_their_close(root):
    output = root / "periods"
    monetary_periods.derive(monetary_periods.DATASET_ID, output, root=root)
    rows = duckdb.connect().execute("SELECT regime, days_observed, days_in_period, issued_avax, burned_avax, activation_day_burned_avax, mean_validator_ratio"
                                    " FROM read_parquet(?) ORDER BY starts_at", [str(output / "dataset" / f"{monetary_periods.TABLE}.parquet")]).fetchall()
    # The reward at 14:59 is granite's, the one at 15:00 Helicon's. The 22nd closes after the activation, so its burn is Helicon's.
    assert rows[1][:6] == ("helicon", 2, 2, 60.0, 5.0, 2.0)
    assert rows[0][3] == 10.0 and rows[0][4] == 1.0 and rows[1][6] == pytest.approx(0.4)
    assert monetary_periods.check(output / "capture", output / "dataset", root=root)["status"] == "pass"


def rewrite_parquet(path, sql):
    """Keep byte integrity valid so the consumer must detect the accounting defect itself."""
    with duckdb.connect() as connection:
        connection.execute(f"CREATE TABLE replacement AS {sql}", [str(path)])
        connection.execute("COPY replacement TO ? (FORMAT PARQUET)", [str(path)])
        count = connection.execute("SELECT count(*) FROM replacement").fetchone()[0]
    build_path = path.parent / "build.json"
    build = json.loads(build_path.read_text())
    body = path.read_bytes()
    build["outputs"][0].update(bytes=len(body), sha256=sha256(body))
    build["summary"]["rows"] = count
    build_path.write_bytes(canonical_bytes(build))


def test_positive_gap_is_already_included_in_period_evm_burn(root):
    ledger = root / "ledger" / "dataset" / "table.parquet"
    # One complete day's 6.75 AVAX consists of P=1, X=2, EVM=3.5 (including gap=0.5), atomic=0.25.
    replacements = {"burned_p_wei": WEI, "burned_x_wei": 2 * WEI, "burned_c_evm_wei": 35 * WEI // 10,
                    "burned_c_evm_gap_wei": WEI // 2, "burned_c_atomic_wei": WEI // 4, "burned_wei": 675 * WEI // 100}
    terms = ", ".join(f"CASE WHEN date_utc=DATE '2026-09-23' THEN {value}::DECIMAL(38,0) ELSE {column} END AS {column}"
                      for column, value in replacements.items())
    rewrite_parquet(ledger, f"SELECT * REPLACE ({terms}) FROM read_parquet(?)")
    output = root / "periods"
    monetary_periods.derive(monetary_periods.DATASET_ID, output, root=root)
    with duckdb.connect() as connection:
        row = connection.execute("SELECT burned_p_avax,burned_x_avax,burned_c_evm_avax,burned_c_atomic_avax,burned_avax FROM read_parquet(?) WHERE regime='helicon'",
                                 [str(output / "dataset" / "monetary-periods.parquet")]).fetchone()
    # Helicon also includes the prior activation day's 2 AVAX of P burn.
    assert row == (3.0, 2.0, 3.5, 0.25, 8.75)
    assert sum(row[:4]) == row[4]
    checked = monetary_periods.check(output / "capture", output / "dataset", root=root)
    assert checked["status"] == "pass", checked["findings"]


def test_invalid_ledger_components_refuse_a_period_build(root):
    ledger = root / "ledger" / "dataset" / "table.parquet"
    rewrite_parquet(ledger, f"SELECT * REPLACE (burned_c_evm_wei + {WEI}::DECIMAL(38,0) AS burned_c_evm_wei) FROM read_parquet(?)")
    with pytest.raises(DataError, match="burn components that do not sum"):
        monetary_periods.derive(monetary_periods.DATASET_ID, root / "periods", root=root)
    assert not (root / "periods").exists()


@pytest.mark.parametrize("component", ["burned_c_evm_avax+0.5", "NULL::DOUBLE"])
def test_mutated_period_component_fails_without_a_changed_total(root, component):
    output = root / "periods"
    monetary_periods.derive(monetary_periods.DATASET_ID, output, root=root)
    parquet = output / "dataset" / "monetary-periods.parquet"
    rewrite_parquet(parquet, f"SELECT * REPLACE ({component} AS burned_c_evm_avax) FROM read_parquet(?)")
    checked = monetary_periods.check(output / "capture", output / "dataset", root=root)
    assert checked["status"] == "attention"
    assert "period burn components do not sum to total burn" in checked["findings"]


@pytest.fixture
def cycle_ledger(cycle_root, monkeypatch):
    ledger_fixtures.add_auto_cycles(cycle_root)
    monetary.derive(monetary.DATASET_ID, cycle_root / "ledger", root=cycle_root)
    # Place an activation exactly on the first cycle's option time, preserving both ordinary and cycle timestamps.
    monkeypatch.setattr(monetary_periods, "periods", lambda: [("before", "2020-09-10 00:00:00"), ("after", "2020-09-12 00:00:00")])
    return cycle_root


def test_cycle_companion_and_ordinary_events_split_exactly_and_conserve_issuance(cycle_ledger):
    output = cycle_ledger / "by-era"
    result = monetary_periods.derive(monetary_periods.DATASET_ID, output, root=cycle_ledger)
    with duckdb.connect() as c:
        rows = c.execute("SELECT regime,issued_avax FROM read_parquet(?) ORDER BY starts_at", [str(output / "dataset/monetary-periods.parquet")]).fetchall()
    # The ordinary 50 AVAX payment is before activation. At/after it: 19 AVAX ordinary,
    # 24 nAVAX delegator net and 36 nAVAX current cycle recognition. The 6 nAVAX prior
    # accrual released at termination and the deliberately false 999 nAVAX parent cash row are excluded.
    assert rows == [("before", 50.0), ("after", 19.00000006)]
    assert result["capture"]["parameters"]["reward_accounting_basis"] == monetary.REWARD_ACCOUNTING_BASIS
    companion = next(i for i in result["capture"]["inputs"] if i["input_id"] == "cycle-events")
    assert companion["parquet"] == monetary.CYCLE_EVENTS_FILE
    checked = monetary_periods.check(output / "capture", output / "dataset", root=cycle_ledger)
    assert checked["status"] == "pass", checked["findings"]


@pytest.mark.parametrize("mutation", ["missing", "changed", "rehashed"])
def test_new_basis_requires_its_exact_cycle_companion(cycle_ledger, mutation):
    path = cycle_ledger / "ledger/dataset" / monetary.CYCLE_EVENTS_FILE
    if mutation == "missing":
        path.unlink()
    elif mutation == "changed":
        path.write_bytes(path.read_bytes() + b"changed")
    else:
        with duckdb.connect() as c:
            c.execute("CREATE TABLE changed AS SELECT * REPLACE (recognised_reward_navax+1 AS recognised_reward_navax) FROM read_parquet(?)", [str(path)])
            c.execute("COPY changed TO ? (FORMAT PARQUET)", [str(path)])
        build_path = path.parent / "build.json"
        build = json.loads(build_path.read_text())
        entry = next(i for i in build["outputs"] if i["path"] == monetary.CYCLE_EVENTS_FILE)
        entry.update(bytes=path.stat().st_size, sha256=sha256(path.read_bytes()))
        build_path.write_bytes(canonical_bytes(build))
    with pytest.raises(DataError, match="companion|projection does not equal|parent ledger validation failed"):
        monetary_periods.derive(monetary_periods.DATASET_ID, cycle_ledger / "by-era", root=cycle_ledger)
    assert not (cycle_ledger / "by-era").exists()


def test_cycle_aware_periods_refuse_a_different_explicit_ordinary_reward_pin(cycle_ledger):
    with pytest.raises(DataError, match="reward pin differs"):
        monetary_periods.derive(monetary_periods.DATASET_ID, cycle_ledger / "by-era",
                                {"snowflake.primary-staking-rewards": "rewards"}, root=cycle_ledger)
    result = monetary_periods.derive(monetary_periods.DATASET_ID, cycle_ledger / "by-era",
                                     {"snowflake.primary-staking-rewards": "rewards-auto"}, root=cycle_ledger)
    assert next(i for i in result["capture"]["inputs"] if i["input_id"] == "rewards")["run"] == "rewards-auto"


@pytest.mark.parametrize("strip_basis", [False, True])
def test_recorded_new_basis_cannot_fall_back_when_companion_is_omitted(cycle_ledger, strip_basis):
    output = cycle_ledger / "by-era"
    monetary_periods.derive(monetary_periods.DATASET_ID, output, root=cycle_ledger)
    path = output / "capture/capture.json"
    capture = json.loads(path.read_text())
    capture["inputs"] = [i for i in capture["inputs"] if i["input_id"] != "cycle-events"]
    if strip_basis:
        next(i for i in capture["inputs"] if i["input_id"] == "ledger").pop("reward_accounting_basis")
    path.write_bytes(canonical_bytes(capture))
    checked = monetary_periods.check(output / "capture", output / "dataset", root=cycle_ledger)
    assert checked["status"] == "attention"
    assert ("period input accounting basis differs from the parent ledger" if strip_basis else
            "cycle-aware ledger requires its supported event companion") in checked["findings"]


def shift_and_rehash_cycle_event(root):
    """Move the first event across a same-day activation while keeping every daily amount and byte binding coherent."""
    path = root / "ledger/dataset" / monetary.CYCLE_EVENTS_FILE
    with duckdb.connect() as c:
        c.execute("CREATE TABLE changed AS SELECT * REPLACE (CASE WHEN cycle=1 THEN rewarded_at+INTERVAL 1 HOUR ELSE rewarded_at END AS rewarded_at) FROM read_parquet(?)", [str(path)])
        c.execute("COPY changed TO ? (FORMAT PARQUET)", [str(path)])
    build_path = path.parent / "build.json"
    build = json.loads(build_path.read_text())
    entry = next(i for i in build["outputs"] if i["path"] == monetary.CYCLE_EVENTS_FILE)
    entry.update(bytes=path.stat().st_size, sha256=sha256(path.read_bytes()))
    build_path.write_bytes(canonical_bytes(build))
    return entry


@pytest.mark.parametrize("existing", [False, True])
def test_rehashed_same_day_event_shift_across_activation_refuses_derive_and_check(cycle_ledger, monkeypatch, existing):
    monkeypatch.setattr(monetary_periods, "periods", lambda: [("before", "2020-09-10 00:00:00"), ("after", "2020-09-12 00:30:00")])
    output = cycle_ledger / "by-era"
    if existing:
        monetary_periods.derive(monetary_periods.DATASET_ID, output, root=cycle_ledger)
    entry = shift_and_rehash_cycle_event(cycle_ledger)
    # The original source ledger detects the altered intraday clock despite valid output hashes.
    ledger_check = monetary.check(cycle_ledger / "ledger/capture", cycle_ledger / "ledger/dataset", root=cycle_ledger)
    assert "cycle_events differs from the recorded accounting projection" in ledger_check["findings"]
    if existing:
        capture_path = output / "capture/capture.json"
        capture = json.loads(capture_path.read_text())
        next(i for i in capture["inputs"] if i["input_id"] == "cycle-events").update(bytes=entry["bytes"], sha256=entry["sha256"])
        capture_path.write_bytes(canonical_bytes(capture))
        # Make the existing period output match the corrupted event's wrong allocation too.
        # A rebuild/daily-total check alone would accept this fully rehashed result.
        unchecked = monetary_periods.compute([{**i, "path": cycle_ledger / i["run"] / "dataset" / i["parquet"]} for i in capture["inputs"]])
        assert [(r[0], r[10]) for r in unchecked] == [("before", 50.000000008), ("after", 19.000000052)]
        rewrite_parquet(output / "dataset/monetary-periods.parquet",
                        "SELECT * REPLACE (CASE WHEN regime='before' THEN 50.000000008 ELSE 19.000000052 END::DOUBLE AS issued_avax) FROM read_parquet(?)")
        checked = monetary_periods.check(output / "capture", output / "dataset", root=cycle_ledger)
        assert checked["status"] == "attention"
        assert any("parent ledger validation failed" in f and "cycle_events differs" in f for f in checked["findings"])
    else:
        with pytest.raises(DataError, match="parent ledger validation failed: cycle_events differs"):
            monetary_periods.derive(monetary_periods.DATASET_ID, output, root=cycle_ledger)
        assert not output.exists()
