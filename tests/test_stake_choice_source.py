"""Source refusals that close the adapter review's concrete witnesses."""
import importlib.util
import json
from pathlib import Path

import duckdb
import pytest

_SPEC = importlib.util.spec_from_file_location("stake_source_check", Path(__file__).parents[1] / "scripts/stake_choice_scores.py")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
checked_source, digest = _MODULE.checked_source, _MODULE.digest


def fixture(tmp_path, alteration=None, stake_type="BIGINT"):
    directory = tmp_path / "test-run" / "dataset"
    directory.mkdir(parents=True)
    path = directory / "staking-periods.parquet"
    with duckdb.connect() as db:
        db.execute(f"""CREATE TABLE periods(transaction_hash VARCHAR, role VARCHAR,
            node_id VARCHAR, stake_navax {stake_type}, start_time TIMESTAMP,
            end_time TIMESTAMP, accepted_at TIMESTAMP)""")
        db.execute("""INSERT INTO periods VALUES
            ('t1','validator','n1',2000000000000,'2022-01-01','2022-01-31','2021-12-31'),
            ('t2','validator','n1',4000000000000,'2022-02-01','2022-03-03','2022-01-31')""")
        if alteration:
            db.execute(alteration)
        db.table("periods").write_parquet(str(path))
    pin = {"run": "test-run", "parquet": path.name, "sha256": digest(path),
           "bytes": path.stat().st_size, "capture_id": "fixture-capture",
           "dataset_id": "derived.staking-periods"}
    build = {"dataset_id": pin["dataset_id"], "source_capture_id": pin["capture_id"],
             "outputs": [{"path": pin["parquet"], "sha256": pin["sha256"], "bytes": pin["bytes"]}]}
    check = {"dataset_id": pin["dataset_id"], "capture_id": pin["capture_id"],
             "status": "pass", "findings": []}
    (directory / "build.json").write_text(json.dumps(build))
    (directory / "check.json").write_text(json.dumps(check))
    return directory, pin


def test_valid_complete_history(tmp_path):
    directory, pin = fixture(tmp_path)
    _, audit = checked_source(directory, pin)
    assert audit["counts"]["rows"] == 2
    assert audit["independent_chain_completeness_verified"] is False


@pytest.mark.parametrize("alteration", [
    "UPDATE periods SET accepted_at=NULL WHERE transaction_hash='t1'",
    "UPDATE periods SET accepted_at=start_time+INTERVAL 1 MICROSECOND WHERE transaction_hash='t1'",
    "UPDATE periods SET accepted_at='2024-01-01' WHERE transaction_hash='t1'",
    "UPDATE periods SET stake_navax=NULL WHERE transaction_hash='t1'",
    "UPDATE periods SET stake_navax=1999999999999 WHERE transaction_hash='t1'",
    "UPDATE periods SET node_id=NULL WHERE transaction_hash='t1'",
    "UPDATE periods SET transaction_hash=NULL WHERE transaction_hash='t1'",
    "UPDATE periods SET transaction_hash='t1' WHERE transaction_hash='t2'",
    "UPDATE periods SET start_time=NULL WHERE transaction_hash='t1'",
    "UPDATE periods SET end_time=start_time WHERE transaction_hash='t1'",
    "UPDATE periods SET end_time=start_time-INTERVAL 1 MICROSECOND WHERE transaction_hash='t1'",
    "UPDATE periods SET end_time=start_time+INTERVAL 366 DAY WHERE transaction_hash='t1'",
])
def test_malformed_history_refuses_before_context_selection(tmp_path, alteration):
    directory, pin = fixture(tmp_path, alteration)
    with pytest.raises(ValueError):
        checked_source(directory, pin)


def test_double_stakes_refuse_before_int64_coercion(tmp_path):
    directory, pin = fixture(tmp_path, "UPDATE periods SET stake_navax=2000000000000.5", "DOUBLE")
    with pytest.raises(ValueError, match="native source schema"):
        checked_source(directory, pin)


def test_positive_fractional_duration_preserves_projection_policy(tmp_path):
    directory, pin = fixture(tmp_path, "UPDATE periods SET end_time=start_time+INTERVAL 60 HOUR")
    _, audit = checked_source(directory, pin)
    assert audit["counts"]["fractional_duration"] == 2


@pytest.mark.parametrize("field", ["sha256", "bytes", "run", "capture_id", "dataset_id"])
def test_unbound_run_hash_or_receipt_refuses(tmp_path, field):
    directory, pin = fixture(tmp_path)
    pin[field] = 0 if field == "bytes" else "wrong"
    with pytest.raises(ValueError):
        checked_source(directory, pin)


def test_changed_file_refuses(tmp_path):
    directory, pin = fixture(tmp_path)
    with (directory / pin["parquet"]).open("ab") as f:
        f.write(b"changed")
    with pytest.raises(ValueError, match="source bytes"):
        checked_source(directory, pin)


def test_failed_check_refuses(tmp_path):
    directory, pin = fixture(tmp_path)
    p = directory / "check.json"
    d = json.loads(p.read_text())
    d["status"] = "fail"
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        checked_source(directory, pin)
