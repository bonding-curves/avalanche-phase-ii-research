"""Command-line interface for Avalanche Phase II research."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click

from . import __version__
from . import coingecko
from . import snowflake
from . import snowpeer
from .catalog import DataError, load_catalog
from .model import backtest as model_backtest
from .model import protocol
from .model.types import ModelError, NAVAX_PER_AVAX, SECONDS_PER_DAY, as_utc


MODULES = {snowpeer.DATASET_ID: snowpeer, coingecko.DATASET_ID: coingecko, **{dataset_id: snowflake for dataset_id in snowflake.DATASET_IDS}}


def module_for(dataset_id: str) -> Any:
    try:
        return MODULES[dataset_id]
    except KeyError:
        raise DataError(f"unknown dataset: {dataset_id}") from None


def parse_parameters(values: tuple[str, ...]) -> dict[str, str]:
    parameters: dict[str, str] = {}
    for item in values:
        key, separator, value = item.partition("=")
        if not separator or not key:
            raise DataError(f"parameters must look like key=value: {item}")
        parameters[key] = value
    return parameters


def envelope(command: str, status: str, summary: dict[str, Any], **values: Any) -> dict[str, Any]:
    return {
        "schema_version": "avalanche-cli-result/v1",
        "system": "avalanche-phase-ii-research",
        "command": command,
        "tool_version": __version__,
        "status": status,
        "summary": summary,
        **values,
    }


def emit(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return
    click.echo(f"{result['status'].upper()} | {result['command']} | {result['summary']['text']}")
    for item in result.get("items", []):
        click.echo(f"- {item}")
    for finding in result.get("findings", []):
        click.echo(f"ATTENTION: {finding}")


def finish(result: dict[str, Any], as_json: bool) -> None:
    emit(result, as_json)
    if result["status"] != "pass":
        raise click.exceptions.Exit(1)


@click.group()
@click.version_option(__version__)
def cli() -> None:
    """Inspect and reproduce Avalanche Phase II research."""


@cli.group()
def data() -> None:
    """Inspect, retrieve, build, and check research data."""


@data.command("list")
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def list_data(as_json: bool) -> None:
    """List implemented sources and datasets."""
    catalog = load_catalog()
    items = [
        *(f"source {item['id']}: {item['name']}" for item in catalog["sources"]),
        *(f"dataset {item['id']}: {item['name']}" for item in catalog["datasets"]),
    ]
    finish(envelope("data list", "pass", {"text": f"{len(items)} records"}, items=items, records=catalog), as_json)


@data.command()
@click.argument("identity")
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def describe(identity: str, as_json: bool) -> None:
    """Describe one source or dataset ID."""
    catalog = load_catalog()
    records = [*catalog["sources"], *catalog["datasets"]]
    match = next((item for item in records if item["id"] == identity), None)
    if match is None:
        raise DataError(f"unknown source or dataset: {identity}")
    items = [f"authority: {match.get('authority', 'defined by source contract')}"]
    finish(envelope("data describe", "pass", {"text": identity}, items=items, record=match), as_json)


@data.command()
@click.argument("dataset_id")
@click.option("output", "--output", type=click.Path(path_type=Path), required=True)
@click.option("params", "--param", multiple=True, metavar="KEY=VALUE", help="Bound a parameterized query.")
@click.option("--preview", is_flag=True, help="Resolve requests and writes without network access.")
@click.option("--timeout", type=click.FloatRange(min=1, max=600), default=20, show_default=True, help="Request and statement timeout in seconds.")
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def fetch(dataset_id: str, output: Path, params: tuple[str, ...], preview: bool, timeout: float, as_json: bool) -> None:
    """Fetch one immutable source capture into a new directory."""
    module = module_for(dataset_id)
    parameters = parse_parameters(params)
    if preview:
        value = module.capture_preview(dataset_id, output, parameters)
        result = envelope("data fetch", "pass", {"text": f"preview {dataset_id}"}, preview=value)
    else:
        value = module.capture(dataset_id, output, timeout, parameters)
        result = envelope(
            "data fetch", "pass", {"text": value["capture_id"]},
            capture=value, output=str(output),
        )
    finish(result, as_json)


@data.command()
@click.argument("dataset_id")
@click.option("capture_dir", "--from", type=click.Path(path_type=Path), required=True)
@click.option("output", "--output", type=click.Path(path_type=Path), required=True)
@click.option("--preview", is_flag=True, help="Resolve inputs and writes without creating output.")
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def build(dataset_id: str, capture_dir: Path, output: Path, preview: bool, as_json: bool) -> None:
    """Build a normalized Parquet dataset from a capture."""
    module = module_for(dataset_id)
    if preview:
        value = module.build_preview(dataset_id, capture_dir, output)
        result = envelope("data build", "pass", {"text": f"preview {dataset_id}"}, preview=value)
    else:
        value = module.build(dataset_id, capture_dir, output)
        result = envelope(
            "data build", "pass", {"text": dataset_id}, build=value, output=str(output)
        )
    finish(result, as_json)


@data.command("check")
@click.argument("dataset_id")
@click.option("capture_dir", "--capture", type=click.Path(path_type=Path), required=True)
@click.option("dataset_dir", "--dataset", type=click.Path(path_type=Path))
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def check_data(dataset_id: str, capture_dir: Path, dataset_dir: Path | None, as_json: bool) -> None:
    """Check capture integrity and optional built output."""
    value = module_for(dataset_id).check(capture_dir, dataset_dir)
    if value["dataset_id"] != dataset_id:
        raise DataError(f"capture belongs to {value['dataset_id']}, not {dataset_id}")
    result = envelope(
        "data check", value["status"],
        {"text": f"{dataset_id}; {len(value['checked'])} checks; {len(value['findings'])} findings"},
        validation=value, findings=value["findings"],
    )
    finish(result, as_json)


@data.command()
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def manifest(as_json: bool) -> None:
    """Show the declared dataset manifest."""
    catalog = load_catalog()
    records = [{
        "id": item["id"],
        "source_id": item["source_id"],
        "status": item["status"],
        "fields": item["fields"],
    } for item in catalog["datasets"]]
    items = [f"{item['id']} | {item['status']} | fields {len(item['fields'])}" for item in records]
    finish(envelope("data manifest", "pass", {"text": f"{len(records)} datasets"}, items=items, records=records), as_json)


@cli.group()
def model() -> None:
    """Inspect and check the source-linked protocol staking model."""


@model.command("describe")
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def describe_model(as_json: bool) -> None:
    """Show the mainnet staking parameters, upgrade schedule, and mechanism sources."""
    value = protocol.describe()
    items = [
        *(f"{key}: {item}" for key, item in value["reward"].items()),
        *(f"{item['acp']}: {item['name']} | upgrade {item['upgrade'] or 'none'} | keyed by {item['keyed_by']}" for item in value["mechanisms"]),
    ]
    finish(envelope("model describe", "pass", {"text": f"{len(value['mechanisms'])} mechanisms"}, items=items, model=value), as_json)


@model.command("reward")
@click.option("stake_avax", "--stake", type=click.FloatRange(min=0), required=True, help="Staked amount in AVAX.")
@click.option("duration_days", "--duration", type=click.FloatRange(min=0), required=True, help="Staking duration in days.")
@click.option("start", "--start", type=click.DateTime(), required=True, help="Stake start time, UTC.")
@click.option("supply_avax", "--supply", type=click.FloatRange(min=0), required=True, help="Current AVAX supply at the stake start.")
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def model_reward(stake_avax: float, duration_days: float, start: Any, supply_avax: float, as_json: bool) -> None:
    """Compute the Primary Network potential reward for one stake."""
    stake = round(stake_avax * NAVAX_PER_AVAX)
    duration = round(duration_days * SECONDS_PER_DAY)
    supply = round(supply_avax * NAVAX_PER_AVAX)
    start_utc = as_utc(start)
    config = protocol.reward_config_for_stake_start(start_utc)
    reward = protocol.primary_network_reward(start_utc, duration, stake, supply)
    value = {
        "stake_navax": stake,
        "duration_seconds": duration,
        "stake_start": start_utc.isoformat().replace("+00:00", "Z"),
        "current_supply_navax": supply,
        "regime": protocol.MAINNET_UPGRADES.regime(start_utc),
        "min_consumption_rate": config.min_consumption_rate,
        "potential_reward_navax": reward,
        "potential_reward_avax": reward / NAVAX_PER_AVAX,
        "annualized_reward_rate": protocol.annualized_reward_rate(start_utc, duration, stake, supply) if stake and duration else None,
    }
    items = [f"{key}: {item}" for key, item in value.items()]
    finish(envelope("model reward", "pass", {"text": f"{value['potential_reward_avax']:.9f} AVAX"}, items=items, reward=value), as_json)


@model.command("check")
@click.option("validators", "--validators", type=click.Path(path_type=Path), required=True, help="Built primary-validator-stakes dataset directory.")
@click.option("delegators", "--delegators", type=click.Path(path_type=Path), required=True, help="Built primary-delegator-stakes dataset directory.")
@click.option("supply", "--supply", type=click.Path(path_type=Path), required=True, help="Built primary-staking-supply dataset directory.")
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def check_model(validators: Path, delegators: Path, supply: Path, as_json: bool) -> None:
    """Recompute every captured potential reward from the formula and report disagreement by regime."""
    value = model_backtest.backtest(validators, delegators, supply)
    items = [
        f"{name} | rows {bucket['rows']} | immediate {bucket['immediate_matched']}/{bucket['immediate_matched'] + bucket['immediate_mismatched']}"
        f" | pending {bucket['pending_matched']}/{bucket['pending_matched'] + bucket['pending_mismatched']} | best candidate {bucket['best_candidate']}"
        for name, bucket in value["regimes"].items()
    ]
    summary = value["summary"]
    result = envelope(
        "model check", value["status"],
        {"text": f"immediate {summary['immediate_matched']}/{summary['immediate_rows']} reproduced; pending {summary['pending_rows']} rows; {len(value['findings'])} findings"},
        validation=value, items=items, findings=value["findings"],
    )
    finish(result, as_json)


def main() -> int:
    try:
        code = cli(standalone_mode=False)
    except (DataError, ModelError) as error:
        click.echo(f"ERROR: {error}", err=True)
        return 2
    except click.ClickException as error:
        error.show(file=sys.stderr)
        return error.exit_code
    return code if isinstance(code, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
