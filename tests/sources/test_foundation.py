"""The Foundation's Snowflake captures with a fake connection: hourly prices, the exchange price and the gas fees."""

from __future__ import annotations

import json
import sys

import pytest
from click.testing import CliRunner

from avalanche_research import cli
from avalanche_research.core.catalog import DataError, load_catalog
from avalanche_research.sources import foundation
from avalanche_research.sources.capture import snowflake as client

SAVAX = "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be"


def price_rows(hours=6, wavax_gap=None, spike=None, extra=()):
    rows = []
    for hour in range(hours):
        stamp = f"2024-03-01T{hour:02d}:00:00Z"
        price = 40 + hour * 0.1
        rows.append({"chain": "avalanche", "id": "avalanche-2", "symbol": "AVAX", "address": foundation.NATIVE_AVAX,
                     "decimals": 18, "hour_utc": stamp, "price_text": f"{price:.10f}", "created_at": "2025-03-10T11:36:13Z"})
        if hour != wavax_gap:
            wavax = price * (1.5 if hour == spike else 1.0005)
            rows.append({"chain": "avalanche", "id": "wrapped-avax", "symbol": "WAVAX", "address": foundation.WAVAX,
                         "decimals": 18, "hour_utc": stamp, "price_text": f"{wavax:.10f}", "created_at": "2025-03-10T11:36:13Z"})
        if hour % 2 == 0:
            rows.append({"chain": "avalanche", "id": "benqi-liquid-staked-avax", "symbol": "savax", "address": SAVAX,
                         "decimals": 18, "hour_utc": stamp, "price_text": f"{price * 1.2:.10f}", "created_at": "2025-03-10T11:36:13Z"})
    return rows + list(extra)


def dex_rows(hours=6, skip=(), scale=1.0):
    return [{"chain": "avalanche", "address": foundation.WAVAX, "symbol": "WAVAX", "hour_utc": f"2024-03-01T{hour:02d}:00:00Z",
             "price": (40 + hour * 0.1) * scale, "median_price": 40.0, "median_safe_price": 40.0, "usd_trading_volume": 1e5,
             "traders": 10, "trade_count": 20} for hour in range(hours) if hour not in skip]


GAS_ROWS = [{"date_utc": day, "gas_used_avax": 100.5, "gas_used_usd": None, "gas_used_usd_ref": 3622.65, "gas_used_avax_ref": 100.5}
            for day in ("2020-09-23", "2020-09-25", "2020-09-26")]


class FakeCursor:
    def __init__(self, rows, columns, calls):
        self.rows, self.columns, self.calls = rows, columns, calls
        self.sfqid, self.description, self.pending = "01c8-fixture", [], []

    def execute(self, sql, params=None):
        if sql == client.SESSION_SQL:
            self.description = [("CURRENT_ROLE()",)]
            self.pending = [("FIXTURE_READER", "FIXTURE_WH", None, None, "10.40.102")]
            return
        assert "%(start)s" in sql and "%(end)s" in sql and set(params) == {"start", "end"}
        self.calls.append(params)
        self.description = [(name.upper(),) for name in self.columns]
        self.pending = [tuple(row[name] for name in self.columns) for row in self.rows]

    def fetchall(self):
        rows, self.pending = self.pending, []
        return rows

    def fetchmany(self, size):
        batch, self.pending = self.pending[:size], self.pending[size:]
        return batch

    def close(self):
        pass


def connector(rows, spec, calls=None):
    calls = [] if calls is None else calls

    class Connection:
        def cursor(self):
            return FakeCursor(rows, tuple(spec.raw_types), calls)

        def close(self):
            pass

    def connect(name, timeout):
        assert name == "foundation" and 1 <= timeout <= 600
        return Connection()

    return connect


def capture(tmp_path, spec, rows, name="run", parameters=None):
    run = tmp_path / name
    receipt = foundation.capture(spec.dataset_id, run / "capture", parameters=parameters or {"start": "2024-03-01", "end": "2024-03-02"},
                                 connector=connector(rows, spec))
    return run, receipt


@pytest.mark.parametrize("spec", list(foundation.SPECS.values()))
def test_catalog_declares_each_dataset_with_its_query_and_fields(spec):
    catalog = load_catalog()
    query = foundation.query_definition(catalog, spec.dataset_id)
    sql = client.read_sql(query)
    assert query["relations"] and "%(start)s" in sql and "%(end)s" in sql
    definition = next(item for item in catalog["datasets"] if item["id"] == spec.dataset_id)
    assert [field["name"] for field in definition["fields"]] == list(spec.table_columns)
    assert definition["source_id"] == foundation.SOURCE_ID
    provider = next(item for item in catalog["sources"] if item["id"] == foundation.SOURCE_ID)
    assert "read-only" in provider["authentication"] and "agreement" in provider["reuse_status"]


def test_capture_records_query_session_and_every_row(tmp_path):
    run, receipt = capture(tmp_path, foundation.PRICES_HOURLY, price_rows())
    record = receipt["queries"][0]
    assert receipt["source_id"] == foundation.SOURCE_ID and "account" not in receipt
    assert receipt["session"] == {"role": "FIXTURE_READER", "warehouse": "FIXTURE_WH", "database": None, "schema": None,
                                  "server_version": "10.40.102"}
    assert record["snowflake_query_id"] == "01c8-fixture" and record["rows"] == 6 + 6 + 3
    assert record["parameters"] == {"start": "2024-03-01", "end": "2024-03-02"}
    assert (run / "capture" / record["sql_path"]).read_text() == client.read_sql(
        foundation.query_definition(load_catalog(), foundation.PRICES_HOURLY.dataset_id))
    assert "foundation" not in json.dumps(receipt["session"])
    with pytest.raises(DataError, match="already exists"):
        capture(tmp_path, foundation.PRICES_HOURLY, price_rows())


def test_default_window_starts_at_the_table_and_ends_after_the_capture_day():
    resolved = foundation.resolve_parameters(foundation.DEX_PRICES_HOURLY, None)
    assert resolved["start"] == "2021-02-02" and resolved["end"] > "2026-01-01"
    with pytest.raises(DataError, match="unknown parameters"):
        foundation.resolve_parameters(foundation.DEX_PRICES_HOURLY, {"limit": "5"})
    with pytest.raises(DataError, match="precede"):
        foundation.resolve_parameters(foundation.DEX_PRICES_HOURLY, {"start": "2024-02-01", "end": "2024-01-01"})


def test_prices_build_and_check_pass_and_report_gaps_without_failing(tmp_path):
    run, _ = capture(tmp_path, foundation.PRICES_HOURLY, price_rows(wavax_gap=3))
    built = foundation.build(foundation.PRICES_HOURLY.dataset_id, run / "capture", run / "dataset")
    coverage = built["summary"]["coverage"]
    assert coverage["WAVAX"]["missing_hours"] == 1 and coverage["WAVAX"]["longest_gap_after"] == "2024-03-01T02:00:00Z"
    assert coverage["sAVAX"]["missing_hours"] == 2 and coverage["AVAX"]["missing_hours"] == 0
    result = foundation.check(run / "capture", run / "dataset")
    assert result["status"] == "pass", result["findings"]
    assert result["summary"]["avax_wavax"]["hours"] == 5


def test_prices_check_finds_repeats_non_positive_prices_and_disagreeing_wavax(tmp_path):
    repeat = dict(price_rows()[0])
    bad = {**price_rows()[0], "hour_utc": "2024-03-01T07:00:00Z", "price_text": "0"}
    run, _ = capture(tmp_path, foundation.PRICES_HOURLY, price_rows(spike=1, extra=(repeat, bad)))
    findings = foundation.check(run / "capture")["findings"]
    assert any("repeat a key" in item for item in findings)
    assert any("non-positive price" in item for item in findings)
    assert any("of WAVAX" in item for item in findings)


def test_prices_capture_refuses_an_unreadable_price_or_an_unknown_token(tmp_path):
    run, _ = capture(tmp_path, foundation.PRICES_HOURLY, price_rows(extra=({**price_rows()[0], "price_text": "n/a"},)))
    with pytest.raises(DataError, match="not numbers"):
        foundation.build(foundation.PRICES_HOURLY.dataset_id, run / "capture", run / "dataset")
    run, _ = capture(tmp_path, foundation.PRICES_HOURLY, price_rows(extra=({**price_rows()[0], "address": "0xother"},)), name="other")
    with pytest.raises(DataError, match="outside the query"):
        foundation.check(run / "capture")


def test_dex_check_against_the_price_service(tmp_path):
    prices, _ = capture(tmp_path, foundation.PRICES_HOURLY, price_rows(), name="prices")
    foundation.build(foundation.PRICES_HOURLY.dataset_id, prices / "capture", prices / "dataset")
    run, _ = capture(tmp_path, foundation.DEX_PRICES_HOURLY, dex_rows(skip=(4,)), name="dex")
    foundation.build(foundation.DEX_PRICES_HOURLY.dataset_id, run / "capture", run / "dataset")
    result = foundation.check(run / "capture", run / "dataset", prices / "dataset")
    assert result["status"] == "pass", result["findings"]
    assert result["summary"]["coverage"]["WAVAX"]["missing_hours"] == 1 and result["summary"]["reference_days"] == 1
    far, _ = capture(tmp_path, foundation.DEX_PRICES_HOURLY, dex_rows(scale=1.1), name="far")
    assert any("within 3%" in item for item in foundation.check(far / "capture", None, prices / "dataset")["findings"])
    with pytest.raises(DataError, match="no reference dataset"):
        foundation.check(prices / "capture", None, run / "dataset")


def test_gas_fees_report_missing_days_and_refuse_a_repeated_date(tmp_path):
    run, _ = capture(tmp_path, foundation.ECONOMY_GAS_FEES_DAILY, GAS_ROWS, parameters={"start": "2020-09-23", "end": "2020-09-27"})
    built = foundation.build(foundation.ECONOMY_GAS_FEES_DAILY.dataset_id, run / "capture", run / "dataset")
    assert built["summary"]["coverage"]["all"]["missing_days"] == 1 and built["summary"]["rows_without_usd"] == 3
    assert foundation.check(run / "capture", run / "dataset")["status"] == "pass"
    run, _ = capture(tmp_path, foundation.ECONOMY_GAS_FEES_DAILY, [*GAS_ROWS, {**GAS_ROWS[0], "gas_used_avax": -1.0}],
                     name="repeat", parameters={"start": "2020-09-23", "end": "2020-09-27"})
    findings = foundation.check(run / "capture")["findings"]
    assert any("repeat a key (date_utc)" in item for item in findings) and any("non-positive burn" in item for item in findings)


def test_a_changed_capture_is_refused(tmp_path):
    run, receipt = capture(tmp_path, foundation.ECONOMY_GAS_FEES_DAILY, GAS_ROWS, parameters={"start": "2020-09-23", "end": "2020-09-27"})
    (run / "capture" / receipt["queries"][0]["path"]).write_bytes(b"changed")
    with pytest.raises(DataError, match="hash or size differs"):
        foundation.read_capture(run / "capture")


def test_the_named_connection_defaults_to_foundation_and_follows_its_variable(monkeypatch):
    monkeypatch.delenv(foundation.CONNECTION_VARIABLE, raising=False)
    assert foundation.connection_name() == "foundation"
    monkeypatch.setenv(foundation.CONNECTION_VARIABLE, "other")
    assert foundation.connection_name() == "other"
    assert foundation.capture_preview(foundation.PRICES_HOURLY.dataset_id, foundation.Path("x"))["connection"] == "other"


def test_cli_previews_a_capture_without_connecting(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["avalanche"])
    output = tmp_path / "preview"
    result = CliRunner().invoke(cli.cli, ["data", "fetch", "allium.prices-hourly", "--output", str(output), "--preview", "--json"])
    assert result.exit_code == 0, result.output
    value = json.loads(result.output)["preview"]
    assert value["source_id"] == foundation.SOURCE_ID and value["parameters"]["start"] == "2022-06-01"
    assert value["sql"] == "queries/allium-prices-hourly.sql" and not output.exists()
