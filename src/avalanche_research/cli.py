"""Command-line interface for Avalanche Phase II research."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click

from . import __version__
from . import snowpeer


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
    catalog = snowpeer.load_catalog()
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
    catalog = snowpeer.load_catalog()
    records = [*catalog["sources"], *catalog["datasets"]]
    match = next((item for item in records if item["id"] == identity), None)
    if match is None:
        raise snowpeer.DataError(f"unknown source or dataset: {identity}")
    items = [f"authority: {match.get('authority', 'defined by source contract')}"]
    finish(envelope("data describe", "pass", {"text": identity}, items=items, record=match), as_json)


@data.command()
@click.argument("dataset_id")
@click.option("output", "--output", type=click.Path(path_type=Path), required=True)
@click.option("--preview", is_flag=True, help="Resolve requests and writes without network access.")
@click.option("--timeout", type=click.FloatRange(min=1, max=120), default=20, show_default=True)
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def fetch(dataset_id: str, output: Path, preview: bool, timeout: float, as_json: bool) -> None:
    """Fetch one immutable source capture into a new directory."""
    if preview:
        value = snowpeer.capture_preview(dataset_id, output)
        result = envelope("data fetch", "pass", {"text": f"preview {dataset_id}"}, preview=value)
    else:
        value = snowpeer.capture(dataset_id, output, timeout)
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
    """Build a normalized JSON and Parquet dataset from a capture."""
    if preview:
        value = snowpeer.build_preview(dataset_id, capture_dir, output)
        result = envelope("data build", "pass", {"text": f"preview {dataset_id}"}, preview=value)
    else:
        value = snowpeer.build(dataset_id, capture_dir, output)
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
    if dataset_id != snowpeer.DATASET_ID:
        raise snowpeer.DataError(f"unknown dataset: {dataset_id}")
    value = snowpeer.check(capture_dir, dataset_dir)
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
    catalog = snowpeer.load_catalog()
    records = [{
        "id": item["id"],
        "source_id": item["source_id"],
        "status": item["status"],
        "fields": item["fields"],
    } for item in catalog["datasets"]]
    items = [f"{item['id']} | {item['status']} | fields {len(item['fields'])}" for item in records]
    finish(envelope("data manifest", "pass", {"text": f"{len(records)} datasets"}, items=items, records=records), as_json)


def main() -> int:
    try:
        cli(standalone_mode=False)
    except snowpeer.DataError as error:
        click.echo(f"ERROR: {error}", err=True)
        return 2
    except click.ClickException as error:
        error.show(file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
