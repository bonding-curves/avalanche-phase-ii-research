"""Command-line interface for Avalanche Phase II research."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import click

from . import __version__
from . import atomic
from . import attributions
from . import binance
from . import catx
from . import builderhub
from . import uptime_hourly
from . import cblocks
from . import cchain_rpc
from . import clist
from . import clist_daily
from . import coingecko
from . import dataapi
from . import datasets
from . import defillama
from . import derived
from . import etf
from . import freshness
from . import gci
from . import gci_monthly
from . import helicon
from . import metrics
from . import monetary
from . import monetary_periods
from . import nodes
from . import operators
from . import opportunity
from . import pblocks
from . import pburns
from . import pchain
from . import pool_history
from . import pins
from . import pstakers
from . import pstaking
from . import ptx
from . import seam
from . import snowflake
from . import snowpeer
from . import subnets
from . import treasury
from . import validators_api
from . import weeks
from . import yields
from .catalog import DataError, canonical_bytes, load_catalog, now
from .model import MODEL_VERSION, RELEASED_MODEL, protocol
from .model import backtest as model_backtest
from .model.types import ModelError, NAVAX_PER_AVAX, SECONDS_PER_DAY, as_utc


MODULES = {
    atomic.DATASET_ID: atomic,
    binance.DATASET_ID: binance,
    cblocks.DATASET_ID: cblocks,
    cblocks.RPC_DATASET_ID: cblocks,
    cchain_rpc.DATASET_ID: cchain_rpc,
    snowpeer.DATASET_ID: snowpeer,
    coingecko.DATASET_ID: coingecko,
    dataapi.DATASET_ID: dataapi,
    defillama.DATASET_ID: defillama,
    pchain.DATASET_ID: pchain,
    ptx.DATASET_ID: ptx,
    **{dataset_id: pblocks for dataset_id in pblocks.DATASET_IDS},
    **{dataset_id: pstakers for dataset_id in pstakers.DATASET_IDS},
    **{dataset_id: pstaking for dataset_id in pstaking.DATASET_IDS},
    **{dataset_id: clist for dataset_id in clist.DATASET_IDS},
    **{dataset_id: clist_daily for dataset_id in clist_daily.DATASET_IDS},
    pburns.DATASET_ID: pburns,
    **{dataset_id: gci for dataset_id in gci.DATASET_IDS},
    **{dataset_id: gci_monthly for dataset_id in gci_monthly.DATASET_IDS},
    **{dataset_id: seam for dataset_id in seam.DATASET_IDS},
    catx.DATASET_ID: catx,
    yields.DATASET_ID: yields,
    **{dataset_id: pool_history for dataset_id in pool_history.DATASET_IDS},
    treasury.DATASET_ID: treasury,
    derived.DATASET_ID: derived,
    nodes.DATASET_ID: nodes,
    helicon.DATASET_ID: helicon,
    subnets.DATASET_ID: subnets,
    operators.DATASET_ID: operators,
    opportunity.DATASET_ID: opportunity,
    attributions.DATASET_ID: attributions,
    monetary.DATASET_ID: monetary,
    monetary_periods.DATASET_ID: monetary_periods,
    **{dataset_id: metrics for dataset_id in metrics.DATASET_IDS},
    **{dataset_id: snowflake for dataset_id in snowflake.DATASET_IDS},
    **{dataset_id: validators_api for dataset_id in validators_api.DATASET_IDS},
    **{dataset_id: builderhub for dataset_id in builderhub.DATASET_IDS},
    **{dataset_id: uptime_hourly for dataset_id in uptime_hourly.DATASET_IDS},
    **{dataset_id: weeks for dataset_id in weeks.DATASET_IDS},
    **{dataset_id: etf for dataset_id in etf.DATASET_IDS},
}


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


def code_commit() -> str:
    """The commit of the git checkout this package's source is tracked in, marked when tracked files under src differ
    from it, or "unknown" outside a checkout."""
    package = Path(__file__).resolve().parent

    def git(*arguments: str) -> str:
        return subprocess.run(["git", *arguments], cwd=package, check=True, capture_output=True, text=True,
                              timeout=5).stdout.strip()
    try:
        git("ls-files", "--error-unmatch", "--", Path(__file__).name)
        commit = git("rev-parse", "HEAD")
        modified = git("status", "--porcelain", "--untracked-files=no", "--", ":/src")
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return f"{commit} (modified)" if modified else commit


def show_version(context: click.Context, parameter: click.Parameter, value: bool) -> None:
    if not value or context.resilient_parsing:
        return
    click.echo(f"avalanche-phase-ii-research {__version__}")
    click.echo(f"released model {RELEASED_MODEL} (model version {MODEL_VERSION})")
    click.echo(f"code commit {code_commit()}")
    context.exit()


@click.group()
@click.option("--version", is_flag=True, expose_value=False, is_eager=True, callback=show_version,
              help="Show the package version, the released model and the code commit, then exit.")
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
    # A capture that names a built run in a parameter gets that run resolved here, so it imports no dataset code.
    extra = ({"readings": datasets.readings(module.READS, parameters, defaults=getattr(module, "READ_DEFAULTS", None))}
             if hasattr(module, "READS") else {})
    if preview:
        value = module.capture_preview(dataset_id, output, parameters, **extra)
        result = envelope("data fetch", "pass", {"text": f"preview {dataset_id}"}, preview=value)
    else:
        value = module.capture(dataset_id, output, timeout, parameters, **extra)
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


@data.command()
@click.argument("dataset_id")
@click.option("output", "--output", type=click.Path(path_type=Path), required=True)
@click.option("inputs", "--input", multiple=True, metavar="DATASET_ID=RUN", help="Pin an input run; the newest built run of each input is used otherwise.")
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def derive(dataset_id: str, output: Path, inputs: tuple[str, ...], as_json: bool) -> None:
    """Build a derived dataset from built runs into a new run directory with capture and dataset receipts."""
    module = module_for(dataset_id)
    if not hasattr(module, "derive"):
        raise DataError(f"{dataset_id} is captured from a provider; use `avalanche data fetch` and `build`")
    value = module.derive(dataset_id, output, parse_parameters(inputs) or None)
    result = envelope(
        "data derive", "pass", {"text": value["capture"]["capture_id"]},
        capture=value["capture"], build=value["build"], output=str(output),
    )
    finish(result, as_json)


@data.command("check")
@click.argument("dataset_id")
@click.option("capture_dir", "--capture", type=click.Path(path_type=Path), required=True)
@click.option("dataset_dir", "--dataset", type=click.Path(path_type=Path))
@click.option("against", "--against", type=click.Path(path_type=Path), multiple=True, help="Built reference dataset directory for a cross-check; repeatable where a check takes several.")
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def check_data(dataset_id: str, capture_dir: Path, dataset_dir: Path | None, against: tuple[Path, ...], as_json: bool) -> None:
    """Check capture integrity, optional built output, and an optional reference cross-check."""
    module = module_for(dataset_id)
    if module is metrics or module is builderhub and dataset_id == builderhub.DATASET_ID:
        reference: Any = against or None
    elif len(against) > 1:
        raise DataError(f"{dataset_id} takes at most one --against directory")
    else:
        reference = against[0] if against else None
    value = module.check(capture_dir, dataset_dir, reference)
    if value["dataset_id"] != dataset_id:
        raise DataError(f"capture belongs to {value['dataset_id']}, not {dataset_id}")
    if dataset_dir is not None:
        record = {"schema_version": "avalanche-check/v1", "checked_at": now(), "tool_version": __version__, **value}
        (dataset_dir / "check.json").write_bytes(canonical_bytes(record))
    result = envelope(
        "data check", value["status"],
        {"text": f"{dataset_id}; {len(value['checked'])} checks; {len(value['findings'])} findings"},
        validation=value, findings=value["findings"],
    )
    finish(result, as_json)


@data.command("freshness")
@click.option("--timeout", type=click.FloatRange(min=1, max=600), default=60, show_default=True, help="Request and statement timeout in seconds.")
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def data_freshness(timeout: float, as_json: bool) -> None:
    """Read the newest record of each source live; any older than 36 hours, or unreadable, is a finding."""
    value = freshness.measure(freshness.probes(timeout))
    items = [f"{row['status']} | {row['source']} | newest {row['newest'] or '-'} | {row['age_hours'] if row['age_hours'] is not None else '-'} h"
             + (f" | {row['error']}" if row.get("error") else "") for row in value["sources"]]
    findings = [f"{row['source']} is {row['status']}" for row in value["sources"] if row["status"] != "fresh"]
    fresh = sum(row["status"] == "fresh" for row in value["sources"])
    finish(envelope("data freshness", value["status"], {"text": f"{fresh} of {len(value['sources'])} sources fresh"},
                    items=items, findings=findings, freshness=value), as_json)


@data.command("runs")
@click.argument("dataset_id", required=False)
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def list_runs(dataset_id: str | None, as_json: bool) -> None:
    """List built runs under data/runs for one dataset or for every dataset."""
    records = datasets.runs(dataset_id)
    items = [f"{item['dataset_id']} | {item['run']} | captured {item['captured_at']} | rows {item['rows']}" for item in records]
    serializable = [{key: (str(value) if isinstance(value, Path) else value) for key, value in item.items()} for item in records]
    finish(envelope("data runs", "pass", {"text": f"{len(records)} runs"}, items=items, records=serializable), as_json)


@data.command("pin")
@click.argument("name")
@click.argument("dataset_ids", nargs=-1, required=True)
@click.option("--run", "chosen", multiple=True, metavar="DATASET=RUN", help="Pin this run instead of the newest; repeatable.")
@click.option("--code-commit", help="The client commit the pinned results were made with.")
@click.option("--code-ref", help="A tag or branch that must point at --code-commit, such as model-v0.7.0.")
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def data_pin(name: str, dataset_ids: tuple[str, ...], chosen: tuple[str, ...], code_commit: str | None, code_ref: str | None,
             as_json: bool) -> None:
    """Write data/pins/NAME.json: one checked run per dataset, with its capture ID and Parquet hash."""
    runs_by_dataset = dict(item.split("=", 1) for item in chosen)
    value = pins.pin(name, list(dataset_ids), runs_by_dataset, code_commit=code_commit, code_ref=code_ref)
    items = [f"{entry['dataset_id']} | {entry['run']} | {entry['sha256'][:12]}" for entry in value["runs"]]
    finish(envelope("data pin", "pass", {"text": f"{name}: {len(value['runs'])} runs pinned"}, items=items, pins=value), as_json)


@data.command("pin-check")
@click.argument("path", type=click.Path(path_type=Path))
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def data_pin_check(path: Path, as_json: bool) -> None:
    """Confirm every run a pin file names still exists, is unchanged, and still passes its check."""
    findings = pins.verify(path)
    count = len(pins.read(path)["runs"])
    finish(envelope("data pin-check", "pass" if not findings else "attention", {"text": f"{path.name}: {count} runs; {len(findings)} findings"},
                    findings=findings), as_json)


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
    """Run, inspect and check the staking model and its source-linked protocol rules."""


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


@model.command("sweep")
@click.argument("design", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("out", type=click.Path(file_okay=False, path_type=Path))
@click.option("pin", "--pin", type=click.Path(exists=True, dir_okay=False, path_type=Path), help="Pin file replacing the design's.")
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def model_sweep(design: Path, out: Path, pin: Path | None, as_json: bool) -> None:
    """Run a sweep design file: one Parquet file per row under OUT, and the sweep's receipt beside them.

    Each name in the design's models must be a registered model variant, such as v0.8.0, the released model."""
    from .experiments import sweep

    made = sweep.run(design, out, pin=pin)
    text = f"{made['sweep']['rows_written']} rows written, {made['sweep']['rows_skipped']} skipped, receipt {made['receipt_id']}"
    finish(envelope("model sweep", "pass", {"text": text}, receipt=made), as_json)


@model.command("run")
@click.argument("pin", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("out", type=click.Path(file_okay=False, path_type=Path))
@click.option("--origin", required=True, help="Model origin day, before the validation lockbox.")
@click.option("model_name", "--model", default=RELEASED_MODEL, show_default=True,
              help="Model variant name, as in a design's models. The default is the released model; v0.7, v0.8 and the other registered variants also run.")
@click.option("--runs", type=click.IntRange(min=1), default=20, show_default=True, help="Monte Carlo runs of the scenario.")
@click.option("--timesteps", type=click.IntRange(min=1), default=180, show_default=True, help="Days simulated.")
@click.option("--seed", type=click.IntRange(min=0), default=0, show_default=True, help="Base random seed of the runs.")
@click.option("--workers", default="auto", show_default=True, help="A number, or auto to size from free memory.")
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def model_run(pin: Path, out: Path, origin: str, model_name: str, runs: int, timesteps: int, seed: int, workers: str, as_json: bool) -> None:
    """Run one scenario from a pin file: one origin, model and seed, written as a one-row sweep under OUT."""
    from .experiments import sweep

    count = workers if workers == "auto" else int(workers)
    made = sweep.run(sweep.scenario(pin, origin, model_name, runs, timesteps, seed, count), out)
    text = f"{made['sweep']['rows_written']} row written, receipt {made['receipt_id']}"
    finish(envelope("model run", "pass", {"text": text}, receipt=made), as_json)


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


@cli.group()
def report() -> None:
    """Standard outputs of a sweep: PSuU scoring, heat maps, trees, grids and recommendation tables.

    These commands need the report dependency group: uv sync --group report."""


SWEEP_OPTIONS = [
    click.option("--wide", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path),
                 help="The sweep's wide table, one row per run and horizon, as Parquet."),
    click.option("--manifest", "manifest_path", required=True,
                 type=click.Path(exists=True, dir_okay=False, path_type=Path),
                 help="The sweep manifest that gives every column of the wide table its role."),
    click.option("--spec", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path),
                 help="The goal and utility specification."),
    click.option("--out", required=True, type=click.Path(file_okay=False, path_type=Path), help="Output folder."),
    click.option("--trees", type=click.IntRange(min=1), default=300, show_default=True,
                 help="Trees in each random forest."),
    click.option("--repeats", type=click.IntRange(min=1), default=10, show_default=True,
                 help="Permutation repeats of each forest importance."),
    click.option("--jobs", type=click.IntRange(min=1), default=8, show_default=True,
                 help="Parallel jobs for fitting forests."),
    click.option("--seed", type=click.IntRange(min=0), default=20261027, show_default=True,
                 help="Seed of every split, sample and resample."),
    click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON."),
]


def sweep_options(function):
    for option in reversed(SWEEP_OPTIONS):
        function = option(function)
    return function


@report.command("manifest")
@click.option("--wide", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="The sweep's wide table, as Parquet.")
@click.option("--out", required=True, type=click.Path(dir_okay=False, path_type=Path),
              help="Where to write the drafted sweep-manifest.json.")
@click.option("as_json", "--json", is_flag=True, help="Emit the complete result as JSON.")
def report_manifest(wide: Path, out: Path, as_json: bool) -> None:
    """Draft a sweep manifest from a wide table's column names and types. Check every role before use."""
    from .report import manifest as sweep_manifest

    drafted = sweep_manifest.draft(wide)
    sweep_manifest.write(drafted, out)
    roles = {role: sweep_manifest.names(drafted, role) for role in sweep_manifest.ROLES}
    items = [f"{role}: {', '.join(names) or 'none'}" for role, names in roles.items() if role != "id"]
    finish(envelope("report manifest", "pass", {"text": f"drafted {out}; check every role"}, items=items,
                    manifest=drafted), as_json)


@report.command("psuu")
@sweep_options
def report_psuu(wide: Path, manifest_path: Path, spec: Path, out: Path, trees: int, repeats: int, jobs: int, seed: int,
                as_json: bool) -> None:
    """Score a sweep against a utility specification and write the PSuU tables and figures."""
    from .report import psuu

    scored = psuu.load_scored(wide, manifest_path, spec, log=lambda text: click.echo(text, err=True))
    made = psuu.run(scored, out, trees, repeats, jobs, seed, log=lambda text: click.echo(text, err=True))
    text = f"{len(scored.runs):,} runs scored, {len(made['titles'])} figures in {out}"
    finish(envelope("report psuu", "pass", {"text": text}, items=list(made["titles"].values())), as_json)


@report.command("pack")
@sweep_options
@click.option("--model-version", "version", help="The model version the sweep ran, named on the index page.")
@click.option("--sample", type=click.IntRange(min=10), default=600, show_default=True,
              help="Runs drawn as points per design in the parameter grids.")
def report_pack(wide: Path, manifest_path: Path, spec: Path, out: Path, trees: int, repeats: int, jobs: int, seed: int,
                as_json: bool, version: str | None, sample: int) -> None:
    """Write the whole output pack of a sweep into one folder: PSuU tables and figures, heat maps, trees, parameter
    grids and recommendation tables, with an index.md that lists each output."""
    from .report import pack

    receipt = pack.build(wide, manifest_path, spec, out, version, trees, repeats, jobs, seed, sample,
                         log=lambda text: click.echo(text, err=True))
    text = f"{len(receipt['figures'])} figures and the index in {out}, {receipt['seconds']} s"
    finish(envelope("report pack", "pass", {"text": text}, receipt=receipt), as_json)


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
