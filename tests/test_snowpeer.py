from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from avalanche_research import cli, snowpeer
from avalanche_research.catalog import source


RESPONSES = {
    "total-market-cap": {"mcap": 3_554_983_119},
    "general-stats": {"activeL1Count": 65, "l1ValidatorCount": 595},
    "primary-validator-count": {
        "count": 590,
        "subnetID": "11111111111111111111111111111111LpoYY",
    },
    "average-tps-30d": {"dailyAvgTps": 26.7384},
    "average-daily-transactions-30d": {"dailyTxCount": 2_310_198},
    "average-daily-icm-30d": {"dailyIcmCount": 1_953},
}


class Response:
    def __init__(self, value: dict, status: int = 200):
        self.body = json.dumps(value, separators=(",", ":")).encode()
        self.status = status
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self) -> bytes:
        return self.body


def opener(catalog: dict, fail_at: str | None = None):
    endpoints = {
        item["url"]: item["id"]
        for item in source(catalog, "snowpeer")["endpoints"]
    }

    def open_request(request, timeout):
        assert 1 <= timeout <= 120
        endpoint_id = endpoints[request.full_url]
        if endpoint_id == fail_at:
            raise OSError("fixture failure")
        return Response(RESPONSES[endpoint_id])

    return open_request


def make_capture(tmp_path: Path) -> tuple[Path, dict]:
    catalog = snowpeer.load_catalog()
    path = tmp_path / "capture"
    receipt = snowpeer.capture(
        snowpeer.DATASET_ID, path, catalog=catalog, opener=opener(catalog)
    )
    return path, receipt


def test_catalog_schema_and_references_are_valid():
    catalog = snowpeer.load_catalog()
    assert [item["id"] for item in catalog["sources"]] == ["snowpeer", "coingecko", "binance-public-data", "defillama", "avalanche-metrics-api", "avalanche-data-api", "us-treasury", "avalanche-p-chain-rpc", "avalanche-c-chain-rpc", "tenderly-c-chain-rpc", "avalanche-snowflake", "avalanche-builder-hub", "derived", "etf-issuers"]
    assert [item["id"] for item in catalog["datasets"]] == [
        "snowpeer.network-summary",
        "snowflake.primary-validator-stakes",
        "snowflake.primary-delegator-stakes",
        "snowflake.primary-staking-rewards",
        "snowflake.primary-staking-supply",
        "snowflake.primary-burn-events",
        "snowflake.c-chain-evm-burn-daily",
        "snowflake.primary-burn-daily",
        "snowflake.c-chain-block-gaps",
        "snowflake.subnet-validator-transactions",
        "coingecko.avax-market-daily",
        "binance.avax-usdt-daily",
        "defillama.avax-price-daily",
        "c-chain-rpc.receipt-gap-repairs",
        "p-chain-rpc.current-validators",
        "p-chain-rpc.transactions",
        "p-chain-rpc.blocks",
        "data-api.p-chain-staking-transactions",
        "p-chain-rpc.reward-utxos",
        "data-api.c-chain-block-list",
        "data-api.p-chain-block-list",
        "c-chain-rpc.atomic-transactions",
        "defillama.pool-yields",
        "us-treasury.par-yield-daily",
        "metrics-api.primary-staking-daily",
        "metrics-api.c-chain-activity-daily",
        "data-api.avax-supply",
        "data-api.validators-active",
        "data-api.validators-completed",
        "data-api.validators-completed-recent",
        "data-api.c-chain-atomic-burn",
        "data-api.c-chain-block-fees",
        "c-chain-rpc.block-receipt-fees",
        "derived.staking-periods",
        "derived.node-table",
        "derived.validator-weeks",
        "derived.observed-delegations",
        "derived.market-weeks",
        "derived.avax-monetary-daily",
        "builder-hub.validator-uptime",
        "derived.validator-uptime-hourly",
        "derived.helicon-commitments",
        "etf-issuers.avax-fund-snapshot",
        "etf-issuers.avax-fund-history",
        "derived.subnet-validation",
        "derived.operators",
        "derived.p-chain-validator-stakes",
        "derived.p-chain-delegator-stakes",
        "derived.p-chain-staking-rewards",
        "derived.p-chain-staking-supply",
        "derived.c-chain-evm-burn-daily",
    ]


def test_capture_preserves_raw_bytes_and_receipt(tmp_path):
    path, receipt = make_capture(tmp_path)
    assert receipt["dataset_id"] == snowpeer.DATASET_ID
    assert len(receipt["responses"]) == 6
    observed, values = snowpeer.read_capture(path)
    assert observed == receipt
    assert values["general-stats"] == RESPONSES["general-stats"]


def test_failed_capture_does_not_publish_partial_output(tmp_path):
    catalog = snowpeer.load_catalog()
    path = tmp_path / "capture"
    with pytest.raises(snowpeer.DataError, match="fixture failure"):
        snowpeer.capture(
            snowpeer.DATASET_ID,
            path,
            catalog=catalog,
            opener=opener(catalog, fail_at="average-tps-30d"),
        )
    assert not path.exists()


def test_build_and_check_round_trip_json_and_parquet(tmp_path):
    capture_dir, _ = make_capture(tmp_path)
    dataset_dir = tmp_path / "dataset"
    receipt = snowpeer.build(snowpeer.DATASET_ID, capture_dir, dataset_dir)
    assert receipt["dataset_id"] == snowpeer.DATASET_ID
    validation = snowpeer.check(capture_dir, dataset_dir)
    assert validation["status"] == "pass"
    assert validation["row"] == {
        "observed_at": validation["row"]["observed_at"],
        "market_cap_usd": 3_554_983_119,
        "l1_count": 66,
        "validator_count": 1_185,
        "average_tps_30d": 26.7384,
        "average_daily_transactions_30d": 2_310_198,
        "average_daily_icm_messages_30d": 1_953,
    }


def test_tampered_capture_is_rejected(tmp_path):
    capture_dir, _ = make_capture(tmp_path)
    target = capture_dir / "raw/general-stats.json"
    target.write_text('{"activeL1Count":0,"l1ValidatorCount":0}')
    with pytest.raises(snowpeer.DataError, match="hash or size differs"):
        snowpeer.read_capture(capture_dir)


def test_cli_preview_and_manifest_do_not_write(tmp_path):
    runner = CliRunner()
    output = tmp_path / "capture"
    preview = runner.invoke(
        cli.cli,
        ["data", "fetch", snowpeer.DATASET_ID, "--output", str(output), "--preview", "--json"],
    )
    assert preview.exit_code == 0, preview.output
    assert not output.exists()
    value = json.loads(preview.output)
    assert len(value["preview"]["requests"]) == 6
    manifest = runner.invoke(cli.cli, ["data", "manifest", "--json"])
    assert manifest.exit_code == 0, manifest.output
    assert json.loads(manifest.output)["records"][0]["id"] == snowpeer.DATASET_ID


def test_cli_main_maps_data_error_to_exit_two(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["avalanche", "data", "describe", "missing"])
    assert cli.main() == 2
    assert "unknown source or dataset" in capsys.readouterr().err
