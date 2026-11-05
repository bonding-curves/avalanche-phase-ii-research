"""The Foundation's Snowflake captures with a fake connection: hourly prices, the exchange price and the gas fees."""

from __future__ import annotations

import json
import sys

import duckdb
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


def lending_rows():
    base = {"project": "aave", "protocol": "aave_v3", "market_address": "0xpool", "token_address": foundation.WAVAX,
            "token_symbol": "WAVAX", "block_number": 1, "variable_borrow_apy": 3.0, "stable_borrow_apy": 0.0,
            "supplied_amount": 1e6, "supplied_amount_usd": 3e7, "outstanding_loans": 5e5, "usd_exchange_rate": 30.0}
    rows = [{**base, "block_timestamp": f"2024-03-01T0{hour}:00:00Z", "unique_id": f"u{hour}", "supply_apy": 2.0 + hour / 10}
            for hour in range(3)]
    rows.append({**base, "project": "benqi", "protocol": "compound_v2", "token_symbol": "AVAX", "block_timestamp": "2024-03-01T05:00:00Z",
                 "unique_id": "b1", "supply_apy": None, "variable_borrow_apy": 0.6})
    return rows


def test_lending_rates_count_markets_and_refuse_repeats_or_negative_rates(tmp_path):
    run, _ = capture(tmp_path, foundation.LENDING_INTEREST_RATES, lending_rows())
    built = foundation.build(foundation.LENDING_INTEREST_RATES.dataset_id, run / "capture", run / "dataset")
    by_market = built["summary"]["by_market"]
    assert by_market["aave/aave_v3/WAVAX"]["updates"] == 3 and by_market["benqi/compound_v2/AVAX"]["with_supply_rate"] == 0
    assert "coverage" not in built["summary"]
    assert foundation.check(run / "capture", run / "dataset")["status"] == "pass"
    bad = [*lending_rows(), {**lending_rows()[0]}, {**lending_rows()[1], "unique_id": "neg", "supply_apy": -1.0}]
    run, _ = capture(tmp_path, foundation.LENDING_INTEREST_RATES, bad, name="bad")
    findings = foundation.check(run / "capture")["findings"]
    assert any("repeat a key (unique_id)" in item for item in findings) and any("negative rate" in item for item in findings)


def test_benchmark_rates_check_against_fred(tmp_path):
    rows = [{"date_utc": "2024-01-01", "rate_id": "DTB3", "rate_annual": 0.0522, "source": "FRED DTB3 bfill"},
            {"date_utc": "2024-01-02", "rate_id": "DTB3", "rate_annual": 0.0522, "source": "FRED DTB3"},
            {"date_utc": "2024-01-03", "rate_id": "DTB3", "rate_annual": 0.0521, "source": "FRED DTB3"},
            {"date_utc": "2024-01-04", "rate_id": "DTB3", "rate_annual": 0.0521, "source": "FRED DTB3 ffill"}]
    run, _ = capture(tmp_path, foundation.BENCHMARK_RATES_DAILY, rows, parameters={"start": "2024-01-01", "end": "2024-01-05"})
    built = foundation.build(foundation.BENCHMARK_RATES_DAILY.dataset_id, run / "capture", run / "dataset")
    assert built["summary"]["rows_by_source"] == {"DTB3 FRED DTB3": 2, "DTB3 FRED DTB3 bfill": 1, "DTB3 FRED DTB3 ffill": 1}

    def fred(name, values):
        reference = tmp_path / name
        reference.mkdir()
        parquet = reference / "tbill-3m-daily.parquet"
        duckdb.connect().execute(f"COPY (SELECT * FROM (VALUES {values}) AS t(date_utc, discount_rate_pct)) TO '{parquet}' (FORMAT PARQUET)")
        body = parquet.read_bytes()
        (reference / "build.json").write_text(json.dumps({"dataset_id": "fred.tbill-3m-daily", "outputs": [
            {"path": parquet.name, "bytes": len(body), "sha256": foundation.sha256(body)}]}))
        return reference

    same = fred("same", "(DATE '2024-01-02', 5.22), (DATE '2024-01-03', 5.21)")
    result = foundation.check(run / "capture", run / "dataset", same)
    assert result["status"] == "pass" and result["summary"]["fred_days"] == 2
    other = fred("other", "(DATE '2024-01-02', 5.22), (DATE '2024-01-03', 5.25)")
    assert any("differ from FRED" in item for item in foundation.check(run / "capture", None, other)["findings"])


def atomic_rows():
    """An export in nAVAX to two owners written as owner.addresses, an export in wei written as addresses, an import, and
    an import without a P-Chain sender."""
    owner = json.dumps([{"amount": "2000000000", "owner": {"addresses": ["P-avax1bbb", "P-avax1aaa"]}}])
    plain = json.dumps([{"addresses": ["avax1ccc"], "amount": "1500000000"}])
    return [
        {"hash": "tx1", "source_chain": "c-chain", "destination_chain": "p-chain", "from_address": "0xexchange",
         "to_address": "avax1aaa", "amount_navax_text": "2000000000", "amount_avax": 2.0, "fees_avax": 0.001,
         "output_json": owner, "block_timestamp": "2024-03-01T01:00:00Z", "block_number": 10},
        {"hash": "tx2", "source_chain": "c-chain", "destination_chain": "p-chain", "from_address": "0xwallet",
         "to_address": "avax1ccc", "amount_navax_text": "1500000000000000000", "amount_avax": 1.5, "fees_avax": 0.001,
         "output_json": plain, "block_timestamp": "2024-03-01T02:00:00Z", "block_number": 11},
        {"hash": "tx3", "source_chain": "p-chain", "destination_chain": "c-chain", "from_address": "avax1aaa",
         "to_address": "0xexchange", "amount_navax_text": "700000000", "amount_avax": 0.7, "fees_avax": 0.001,
         "output_json": None, "block_timestamp": "2024-03-01T03:00:00Z", "block_number": 12},
        {"hash": "tx4", "source_chain": "p-chain", "destination_chain": "c-chain", "from_address": None,
         "to_address": "0xother", "amount_navax_text": "100000000", "amount_avax": 0.1, "fees_avax": 0.001,
         "output_json": None, "block_timestamp": "2024-03-01T04:00:00Z", "block_number": 13},
    ]


def test_atomic_transactions_read_both_owner_forms_and_both_amount_units(tmp_path):
    run, _ = capture(tmp_path, foundation.P_CHAIN_ATOMIC, atomic_rows())
    built = foundation.build(foundation.P_CHAIN_ATOMIC.dataset_id, run / "capture", run / "dataset")
    summary = built["summary"]
    assert summary["by_direction"]["export"]["transactions"] == 2 and summary["by_direction"]["export"]["avax"] == 3.5
    assert summary["exports_paying_another_address"] == 1 and summary["imports_without_p_chain_sender"] == 1
    assert summary["amounts_in_wei"] == 1
    rows = duckdb.connect().execute(
        f"SELECT transaction_hash, direction, p_chain_address, output_addresses, amount_navax FROM "
        f"read_parquet('{run / 'dataset' / 'p-chain-atomic-transactions.parquet'}') ORDER BY 1").fetchall()
    assert rows == [("tx1", "export", "avax1aaa", "avax1aaa,avax1bbb", 2_000_000_000),
                    ("tx2", "export", "avax1ccc", "avax1ccc", 1_500_000_000),
                    ("tx3", "import", "avax1aaa", "avax1aaa", 700_000_000),
                    ("tx4", "import", None, None, 100_000_000)]
    assert foundation.check(run / "capture", run / "dataset")["status"] == "pass"


def test_atomic_transactions_refuse_an_amount_in_neither_unit_or_an_export_without_owner(tmp_path):
    rows = atomic_rows()
    rows[0] = {**rows[0], "amount_navax_text": "123"}
    rows[1] = {**rows[1], "output_json": "[]"}
    run, _ = capture(tmp_path, foundation.P_CHAIN_ATOMIC, rows)
    findings = foundation.check(run / "capture")["findings"]
    assert findings == ["2 rows miss a direction, a C-Chain address, a positive nAVAX amount or an export's P-Chain owner"]


def test_labels_and_mapping_count_categories_and_refuse_a_repeated_address(tmp_path):
    label = {"address": "0xexchange", "primary_label": "Exchange 1", "primary_entity": "exchange_one",
             "primary_category": "exchange", "subcategory_json": "[]", "confidence": 1.0,
             "attribution_date": "2024-01-01T00:00:00Z", "source_type": "x", "source_system": "manual",
             "source_priority": 100, "entity_ranking": 1, "first_atomic_at": "2024-03-01T01:00:00Z"}
    run, _ = capture(tmp_path, foundation.IDENTITY_LABELS_ATOMIC, [label, {**label, "address": "0xwallet",
                     "primary_category": "non_custodial_wallet"}])
    built = foundation.build(foundation.IDENTITY_LABELS_ATOMIC.dataset_id, run / "capture", run / "dataset")
    assert built["summary"]["by_category"] == {"exchange": 1, "non_custodial_wallet": 1}
    run, _ = capture(tmp_path, foundation.IDENTITY_LABELS_ATOMIC, [label, label], name="repeat")
    assert any("repeat a key (address)" in item for item in foundation.check(run / "capture")["findings"])
    mapping = {"address": "0xexchange", "entity": "exchange_one", "sub_entity": None, "category": "cex",
               "sector": "institutional", "source": "identity_labels", "priority": 2, "first_atomic_at": "2024-03-01T01:00:00Z"}
    run, _ = capture(tmp_path, foundation.ADDRESS_MAPPING_ATOMIC, [mapping, {**mapping, "address": "0xnone", "entity": None}], name="map")
    assert foundation.check(run / "capture")["findings"] == ["1 rows name no entity"]


@pytest.mark.parametrize("broken, finding", [
    (None, None),
    ("gap", "1 days do not start at the height after the previous day's last block"),
    ("skip", "1 rows miss a hash, skip a block height or end on another day"),
])
def test_daily_last_blocks_check(tmp_path, broken, finding):
    def day(d, first, last, blocks=None):
        return {"date_utc": d, "last_block_number": last, "last_block_hash": f"0x{last}", "last_block_timestamp": f"{d}T23:59:58Z",
                "first_block_number": first, "blocks": blocks if blocks is not None else last - first + 1}

    rows = [day("2024-03-01", 1, 10), day("2024-03-02", 11, 20), day("2024-03-03", 21, 30)]
    if broken == "gap":
        rows[2] = day("2024-03-03", 22, 30)
    if broken == "skip":
        rows[1] = day("2024-03-02", 11, 20, blocks=9)
    run, _ = capture(tmp_path, foundation.C_CHAIN_DAILY_LAST_BLOCKS, rows, parameters={"start": "2024-03-01", "end": "2024-03-04"})
    result = foundation.check(run / "capture")
    assert result["findings"] == ([] if finding is None else [finding])
