"""The Gross Chain Income inputs and monthly table, against a fake chain, a fake FRED, and a fake DefiLlama."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from avalanche_research import gci_monthly
from avalanche_research.catalog import DataError, canonical_bytes, load_catalog, sha256
from avalanche_research.sources import gci

START = int(datetime(2024, 1, 1, tzinfo=UTC).timestamp())
DAY = 86_400


class FakeChain:
    """One block every six hours from 2024-01-01. USDT's supply grows by one million a month; savUSD's share price by 1%."""

    def __init__(self):
        self.head = 4 * 100

    def __call__(self, url, timeout, body_json=None, content="json"):
        method, params = body_json["method"], body_json["params"]
        if method == "eth_blockNumber":
            result = hex(self.head)
        elif method == "eth_getBlockByNumber":
            result = {"timestamp": hex(START + int(params[0], 16) * 6 * 3600)}
        else:
            block = int(params[1], 16)
            months = (block * 6 * 3600) // (31 * DAY)
            token = next(name for name, spec in gci.TOKENS.items() if spec[0] == params[0]["to"])
            selector = params[0]["data"]
            if token not in ("USDT", "savUSD"):
                result = "0x"
            elif selector == gci.SELECTORS["decimals"]:
                result = hex(6 if token == "USDT" else 18)
            elif token == "USDT":
                result = hex((1_000 + months) * 10**6 * 10**6)
            elif selector == gci.SELECTORS["totalSupply"]:
                result = hex(100 * 10**18)
            else:
                result = hex(int(100 * 10**18 * (1.01 ** months)))
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode(), {}


def fred(url, timeout, body_json=None, content="json"):
    if url.endswith("DTB3"):
        lines = ["observation_date,DTB3"] + [f"2024-{month:02d}-{day:02d},{5.0 + month / 10:.2f}" for month in (1, 2, 3) for day in (2, 3)]
        lines.append("2024-02-19,.")
    else:
        lines = ["observation_date,TB3MS"] + [f"2024-{month:02d}-01,{5.0 + month / 10:.2f}" for month in (1, 2, 3)]
    return "\n".join(lines).encode(), {}


def llama(url, timeout, body_json=None, content="json"):
    value = 10.0 if "dailyFees" in url else 1.0
    return json.dumps({"totalDataChart": [[START + day * DAY, value] for day in range(91)]}).encode(), {}


def make_run(root: Path, run: str, dataset_id: str, columns: dict[str, str], rows: list[tuple]) -> None:
    capture_dir, dataset_dir = root / run / "capture", root / run / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / "table.parquet"
    connection = duckdb.connect()
    connection.execute(f"CREATE TABLE t({', '.join(f'{name} {kind}' for name, kind in columns.items())})")
    connection.executemany(f"INSERT INTO t VALUES ({', '.join('?' for _ in columns)})", rows)
    connection.execute("COPY t TO ? (FORMAT PARQUET)", [str(parquet)])
    capture_id = f"capture:test:{run}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({"schema_version": "test/v1", "capture_id": capture_id, "dataset_id": dataset_id, "completed_at": "2026-09-29T00:00:00Z"}))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({"schema_version": "test/v1", "dataset_id": dataset_id, "source_capture_id": capture_id,
                                                              "completed_at": "2026-09-29T00:00:00Z", "summary": {"rows": len(rows)},
                                                              "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}]}))


@pytest.fixture
def runs(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(gci, "PAUSE_SECONDS", 0)
    root = tmp_path / "runs"
    for dataset_id, run, request, parameters in ((gci.SUPPLY_ID, "supply", FakeChain(), {"from_month": "2024-01", "to_month": "2024-03"}),
                                                 (gci.RATE_ID, "rate", fred, None), (gci.FEES_ID, "fees", llama, None)):
        gci.capture(dataset_id, root / run / "capture", parameters=parameters, request=request)
        gci.build(dataset_id, root / run / "capture", root / run / "dataset")
    days = [datetime.fromtimestamp(START + day * DAY, UTC).date() for day in range(91)]
    make_run(root, "ledger", "derived.avax-monetary-daily", {"date_utc": "DATE", "burned_c_evm_wei": "DECIMAL(38,0)"}, [(day, 2 * 10**18) for day in days])
    make_run(root, "price", "binance.avax-usdt-daily", {"observation_date": "DATE", "close_usdt": "DOUBLE"}, [(day, 20.0) for day in days])
    return root


def test_catalog_declares_every_table():
    catalog = {item["id"]: item for item in load_catalog()["datasets"]}
    for dataset_id, columns in {**gci.COLUMNS, **gci_monthly.COLUMNS}.items():
        assert [field["name"] for field in catalog[dataset_id]["fields"]] == list(columns)


def test_the_month_end_block_is_the_months_last(runs):
    _, rows = gci.read_rows(runs / "supply" / "capture")
    # Blocks every six hours from 2024-01-01 00:00: January's last is at 2024-01-31 18:00, block 123.
    usdt = [row for row in rows if row[3] == "USDT"]
    assert [(str(row[0]), row[1], str(row[2])) for row in usdt] == [("2024-01-01", 123, "2024-01-31 18:00:00"), ("2024-02-01", 239, "2024-02-29 18:00:00"),
                                                                   ("2024-03-01", 363, "2024-03-31 18:00:00")]
    assert all(not row[7] for row in rows if row[3] == "BUIDL")
    assert gci.check(runs / "supply" / "capture", runs / "supply" / "dataset")["status"] == "pass"


def test_the_bill_rate_check_compares_monthly_means_with_tb3ms(runs):
    checked = gci.check(runs / "rate" / "capture", runs / "rate" / "dataset")
    assert checked["status"] == "pass" and checked["summary"]["months_compared"] == 3


def test_the_monthly_table_joins_issuer_vault_fees_and_burn(runs):
    output = runs / "monthly"
    gci_monthly.derive(gci_monthly.MONTHLY_ID, output, root=runs)
    rows = duckdb.connect().execute(
        "SELECT month::VARCHAR, tether_float_usd, bill_rate_pct, issuer_income_usd, savusd_income_usd, fees_usd, burn_c_evm_avax, burn_c_evm_usd"
        " FROM read_parquet(?) ORDER BY month", [str(output / "dataset" / "gci-monthly.parquet")]).fetchall()
    january, february = rows[0], rows[1]
    assert january[0] == "2024-01-01" and january[2] == pytest.approx(5.1)
    assert january[3] == pytest.approx(january[1] * 5.1 / 1200)
    assert january[4] is None and february[4] == pytest.approx(1.0, rel=1e-6)
    assert january[5] == 310 and january[6] == 62 and january[7] == pytest.approx(1240)
    assert gci_monthly.check(output / "capture", output / "dataset", root=runs)["status"] == "pass"


def test_a_month_range_is_validated(tmp_path):
    with pytest.raises(DataError):
        gci.capture_preview(gci.SUPPLY_ID, tmp_path / "x", {"from_month": "2024-05", "to_month": "2024-01"})
