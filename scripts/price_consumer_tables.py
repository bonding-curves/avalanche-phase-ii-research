"""Build three named engineering price projections from explicit frozen inputs.

Run in the client Python environment with --pin, --runs-root and a new external
--out. No provider, outcome, model, fit, score or weekly-panel derive is
called. Legacy comparisons hold qualified inputs fixed and change clocks only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

REQUIRED_SOURCES = (
    "src/avalanche_research/datasets/derived/observed_quotes.py",
    "src/avalanche_research/datasets/derived/market_layer.py",
    "src/avalanche_research/datasets/derived/scenario_inputs.py",
    "src/avalanche_research/datasets/derived/weeks.py",
)
PRICE = "defillama.avax-price-daily"
OPPORTUNITY = "derived.opportunity-costs-daily"
LEDGER = "derived.avax-monetary-daily"
PERIODS = "derived.staking-periods"
WEEKLY = "derived.market-weeks"
TBILL = "fred.tbill-3m-daily"
FEES = "defillama.avalanche-fees-daily"
DECISION_CUTOFF = "2025-11-19 16:00:00"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def git(project, *arguments):
    """Optional provenance for installed clients and source archives without Git metadata."""
    try:
        result = subprocess.run(["git", *arguments], cwd=project, capture_output=True, text=True, check=False)
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def safe_component(value):
    if not isinstance(value, str) or not value or Path(value).name != value or value in (".", "..") or "\\" in value:
        raise ValueError("unsafe input component")
    return value


def fingerprint(frame):
    def atom(value):
        if value is None or pd.isna(value):
            return None
        if isinstance(value, float):
            return {"float64_hex": value.hex()}
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if hasattr(value, "item"):
            return atom(value.item())
        return value

    digest = hashlib.sha256()
    digest.update(json.dumps({"columns": list(frame), "dtypes": {c: str(frame[c].dtype) for c in frame}}, sort_keys=True).encode() + b"\n")
    for row in frame.itertuples(index=False, name=None):
        digest.update(json.dumps([atom(v) for v in row], sort_keys=True, separators=(",", ":")).encode() + b"\n")
    return digest.hexdigest()


def compare(legacy, successor, key):
    a, b = (f.sort_values(key).reset_index(drop=True) for f in (legacy, successor))
    if a[key].duplicated().any() or b[key].duplicated().any() or not a[key].equals(b[key]):
        raise ValueError("consumer keyset changed")
    common = [c for c in a if c in b]
    changed_rows = pd.Series(False, index=a.index)
    fields = {}
    for name in common:
        missing_a, missing_b = a[name].isna(), b[name].isna()
        changed = ~(a[name].eq(b[name]) | (missing_a & missing_b)).fillna(False)
        changed_rows |= changed
        fields[name] = {"changed": int(changed.sum()), "legacy_null": int(missing_a.sum()), "successor_null": int(missing_b.sum()),
                        "present_to_null": int((~missing_a & missing_b).sum()), "null_to_present": int((missing_a & ~missing_b).sum())}
    return {"rows": len(a), "same_unique_keys": True, "changed_rows_in_common_columns": int(changed_rows.sum()),
            "changed_common_columns": [c for c in common if fields[c]["changed"]], "fields": fields,
            "added_successor_columns": [c for c in b if c not in a],
            "legacy_dataframe_sha256": fingerprint(a), "successor_dataframe_sha256": fingerprint(b),
            "comparison_scope": "Exact equality and paired NULL equality in common columns; same qualified inputs, clock policy only"}


def quote_summary(frame, *, prefix="", price="price_usd", volatility="volatility_30d", cutoff="price_cutoff_at", max_age=None):
    field = lambda name: prefix + name
    observed = pd.to_datetime(frame[field("price_observed_at")], utc=True)
    anchor = pd.to_datetime(frame[cutoff], utc=True)
    age = frame[field("price_age_at_cutoff_seconds")]
    status = frame[field("price_quote_status")]
    candidate = observed.notna()
    if not observed[candidate].lt(anchor[candidate]).all():
        raise ValueError("quote fails strict earlier-than-cutoff rule")
    expected_age = (anchor - observed).dt.total_seconds()
    if not (age.eq(expected_age) | (age.isna() & expected_age.isna())).all():
        raise ValueError("quote age does not match clocks")
    stale = status.eq("stale")
    if max_age is not None and not stale.equals(age.gt(max_age)):
        raise ValueError("stale status differs from declared age cap")
    if not (frame.loc[stale, [price, volatility]].isna().all().all() and candidate[stale].all() and age[stale].notna().all()):
        raise ValueError("stale values/provenance violate contract")
    if not frame[field("price_source_sha256")].eq(frame.attrs["selected_price_sha256"]).all():
        raise ValueError("quote source SHA differs")
    valid = age.dropna()
    return {"rows": len(frame), "status_counts": {str(k): int(v) for k, v in status.value_counts(dropna=False).items()},
            "price_null": int(frame[price].isna().sum()), "volatility_null": int(frame[volatility].isna().sum()),
            "selected_latest_null_price": int((status.eq("selected") & frame[price].isna()).sum()),
            "age_at_cutoff_seconds": None if valid.empty else {"min": float(valid.min()), "median": float(valid.median()), "max": float(valid.max())},
            "strict_clock_pass": True, "stale_candidate_provenance_retained": True, "max_age_seconds": max_age}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pin", required=True, type=Path)
    parser.add_argument("--runs-root", required=True, type=Path)
    parser.add_argument("--project", type=Path, help="Optional checkout import root; otherwise use the installed client")
    parser.add_argument("--source-freeze", type=Path, help="Optional independently reviewed source hash map")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise ValueError("output already exists")
    if args.project is not None:
        sys.path.insert(0, str(args.project.resolve() / "src"))
    import avalanche_research
    project = Path(avalanche_research.__file__).resolve().parents[2]
    if args.project is not None and project != args.project.resolve():
        raise ValueError("consumer imported from wrong checkout")
    freeze = (json.loads(args.source_freeze.read_text()) if args.source_freeze else
              {"files": {name: sha(project/name) for name in REQUIRED_SOURCES}})
    if set(REQUIRED_SOURCES) != set(freeze["files"]):
        raise ValueError("source freeze must name exactly the four consumers/helpers")
    for name, expected in freeze["files"].items():
        if sha(project / name) != expected:
            raise ValueError("source differs from frozen review: " + name)
    from avalanche_research.datasets.derived import market_layer, scenario_inputs, weeks

    if not Path(market_layer.__file__).resolve().is_relative_to(project / "src"):
        raise ValueError("consumer imported from wrong checkout")
    runs, authenticated, captures = args.runs_root.resolve(), {}, {}
    pin_value = json.loads(args.pin.read_text())
    required = {PERIODS, LEDGER, PRICE, TBILL, FEES, OPPORTUNITY, WEEKLY}
    if len(pin_value['runs']) != len(required) or {r['dataset_id'] for r in pin_value['runs']} != required:
        raise ValueError("pin must contain exactly the seven price-consumer datasets")
    selected = {r['dataset_id']: r for r in pin_value['runs']}
    pin_bindings = [{"path": args.pin.name, "sha256": sha(args.pin)}]

    def get(entry):
        run = safe_component(entry['run'])
        if run in authenticated:
            if authenticated[run]['sha256'] != entry['sha256']:
                raise ValueError("same run requested with conflicting identity")
            return str(runs / run / "dataset" / entry["parquet"])
        directory = runs / run
        path = directory / "dataset" / safe_component(entry['parquet'])
        receipts = {n: directory/n for n in ("capture/capture.json", "dataset/build.json", "dataset/check.json")}
        receipt_hashes = {n: sha(p) for n, p in receipts.items()}
        cap, build, check = [json.loads(p.read_text()) for p in receipts.values()]
        validation = check.get('validation') if check.get('schema_version') == 'avalanche-cli-result/v1' else check
        if not isinstance(validation, dict):
            raise TypeError("input check lacks its declared validation payload: " + run)
        if cap['dataset_id'] != entry['dataset_id'] or build['dataset_id'] != entry['dataset_id'] or validation.get('dataset_id') != entry['dataset_id'] or cap['capture_id'] != entry['capture_id'] or build['source_capture_id'] != entry['capture_id'] or validation.get('capture_id') != entry['capture_id'] or cap['completed_at'] != entry['captured_at'] or check['status'] != 'pass' or validation.get('status') != 'pass' or entry['check'] != 'pass':
            raise ValueError("input receipt identity/check differs: " + run)
        if not isinstance(entry.get('receipt_hashes'), dict) or set(entry['receipt_hashes']) != set(receipts):
            raise ValueError("qualified input pin must bind exactly capture/build/check receipt hashes: " + run)
        for name, expected in entry['receipt_hashes'].items():
            if receipt_hashes.get(name) != expected:
                raise ValueError("pin receipt hash differs: " + run)
        outputs = {}
        for output in build['outputs']:
            name = safe_component(output['path'])
            if name in outputs:
                raise ValueError("duplicate build output")
            output_path = directory/'dataset'/name
            if output_path.stat().st_size != output['bytes'] or sha(output_path) != output['sha256']:
                raise ValueError("build output bytes differ: " + run)
            outputs[name] = output
        if outputs[path.name]['sha256'] != entry['sha256'] or outputs[path.name]['bytes'] != entry['bytes']:
            raise ValueError("pin output differs: " + run)
        authenticated[run] = {**entry, "receipt_hashes": receipt_hashes, "outputs": list(outputs.values())}
        captures[run] = cap
        print("authenticated", run, flush=True)
        return str(path)

    price, opportunity, bill = get(selected[PRICE]), get(selected[OPPORTUNITY]), get(selected[TBILL])
    ledger, periods, fees = get(selected[LEDGER]), get(selected[PERIODS]), get(selected[FEES])
    for parent, input_id, expected in ((selected[LEDGER], 'staking-periods', selected[PERIODS]),):
        references = [i for i in captures[parent['run']]['inputs'] if i['input_id'] == input_id]
        if len(references) != 1 or any(references[0].get(k) != expected.get(k) for k in ('dataset_id','run','parquet','bytes','sha256','capture_id')):
            raise ValueError("consumer source lineage differs")
    weekly_path = get(selected[WEEKLY])
    native_references = [i for i in captures[selected[OPPORTUNITY]['run']]['inputs'] if i.get('input_id') == 'ledger']
    if len(native_references) != 1:
        raise ValueError('native opportunity lacks exact declared supply lineage')
    consumer_inputs = {
        'market': {name: selected[name]['run'] for name in (PERIODS, PRICE, TBILL, LEDGER)},
        'scenario': {name: selected[name]['run'] for name in (LEDGER, PRICE, FEES, OPPORTUNITY)},
        'weekly': {name: selected[name]['run'] for name in (WEEKLY, PRICE)},
    }
    ancestor = out.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    if subprocess.run(['git','-C',str(ancestor),'rev-parse','--show-toplevel'],capture_output=True,check=False).returncode == 0:
        raise ValueError('output must be outside a Git checkout')
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='A7-consumers-', dir=out.parent) as temporary:
        stage = Path(temporary)
        with duckdb.connect(config={'threads': '2', 'memory_limit': '2GB', 'TimeZone': 'UTC', 'temp_directory': str(stage/'spill')}) as db:
            sql = f"SELECT transaction_hash,accepted_at FROM read_parquet(?) WHERE role='validator' AND accepted_at<TIMESTAMP '{DECISION_CUTOFF}' ORDER BY transaction_hash"
            decisions = db.execute(sql, [periods]).df()
            weekly_original = db.execute('SELECT * FROM read_parquet(?) ORDER BY week_start_utc', [weekly_path]).df()
        if weekly_original.week_start_utc.isna().any() or weekly_original.week_start_utc.duplicated().any() or decisions.transaction_hash.duplicated().any():
            raise ValueError('unexpected weekly grain or duplicate decision key')
        market_legacy = market_layer.as_of(decisions, price, bill, ledger)
        market_new = market_layer.as_of(decisions, price, bill, ledger, price_clock=market_layer.OBSERVED_PRICE_CLOCK)
        market_metadata = dict(market_new.attrs)
        market_new = market_new.merge(decisions, on='transaction_hash', validate='one_to_one')
        market_new.attrs = market_metadata
        scenario_legacy = scenario_inputs.build(ledger, price, fees, opportunity)
        scenario_new = scenario_inputs.build(ledger, price, fees, opportunity, price_clock=scenario_inputs.OBSERVED_CLOSE_CLOCK)
        weekly_new = weeks.with_observed_market_prices(weekly_original, price)
        preserved = [c for c in weekly_original if c not in ('price_usd_defillama','volatility_30d_defillama')]
        pd.testing.assert_frame_equal(weekly_original[preserved].sort_values('week_start_utc').reset_index(drop=True),
                                      weekly_new[preserved].sort_values('week_start_utc').reset_index(drop=True), check_exact=True)
        summaries = {}
        for name, frame, options in (
            ('market', market_new, {}),
            ('scenario', scenario_new, {'price': 'avax_price_usd', 'volatility': 'realized_volatility_30d'}),
            ('weekly', weekly_new, {'prefix': 'defillama_', 'price': 'price_usd_defillama', 'volatility': 'volatility_30d_defillama', 'cutoff': 'defillama_price_cutoff_at', 'max_age': 86400}),
        ):
            frame.attrs['selected_price_sha256'] = selected[PRICE]['sha256']
            summaries[name] = {'quotes': quote_summary(frame, **options), 'null_counts': {c: int(frame[c].isna().sum()) for c in frame}, 'attrs': dict(frame.attrs)}
        comparisons = {'market': compare(market_legacy, market_new, 'transaction_hash'),
                       'scenario': compare(scenario_legacy, scenario_new, 'date_utc'), 'weekly': compare(weekly_original, weekly_new, 'week_start_utc')}
        outputs = []
        for name, frame, key in (
            ('market-completed-day-observed', market_new, 'transaction_hash'), ('market-legacy-clock-same-inputs', market_legacy, 'transaction_hash'),
            ('scenario-daily-close-observed', scenario_new, 'date_utc'), ('scenario-legacy-clock-same-inputs', scenario_legacy, 'date_utc'),
            ('market-weeks-observed-24h', weekly_new, 'week_start_utc'), ('market-weeks-original-28sep', weekly_original, 'week_start_utc'),
        ):
            path = stage/(name+'.csv')
            ordered = frame.sort_values(key).reset_index(drop=True)
            ordered.to_csv(path, index=False, float_format='%.17g')
            outputs.append({'path': path.name, 'bytes': path.stat().st_size, 'sha256': sha(path), 'rows': len(ordered),
                            'dataframe_sha256': fingerprint(ordered), 'columns': list(ordered), 'dtypes': {c: str(ordered[c].dtype) for c in ordered}})
        for name, expected in freeze['files'].items():
            if sha(project/name) != expected:
                raise ValueError('source changed during build')
        if sha(args.pin) != pin_bindings[0]['sha256']:
            raise ValueError('pin changed during build')
        for run, entry in authenticated.items():
            for name, expected in entry['receipt_hashes'].items():
                if sha(runs/run/name) != expected:
                    raise ValueError('input receipt changed during build')
        selection = {'pins': pin_bindings, 'runs': list(authenticated.values()), 'consumer_input_maps': consumer_inputs, 'consumer_source_freeze': freeze,
                     'source_freeze_sha256': sha(args.source_freeze) if args.source_freeze else None, 'builder_sha256': sha(Path(__file__))}
        write_json(stage/'input-selection.json', selection)
        report = {'schema_version': 'named-price-consumer-readback/v1', 'status': 'ENGINEERING_PROJECTIONS_COMPLETE',
                  'created_at_utc': datetime.now(UTC).isoformat(), 'client_commit': git(project, 'rev-parse', 'HEAD'),
                  'client_tracked_changes': git(project, 'status', '--short', '--untracked-files=no'),
                  'versions': {'python': platform.python_version(), 'duckdb': duckdb.__version__, 'pandas': pd.__version__},
                  'market_keys': {'sql': sql, 'rows': len(decisions), 'sha256': fingerprint(decisions), 'columns': list(decisions), 'outcomes_read': False,
                                  'first_accepted_at': str(decisions.accepted_at.min()), 'last_accepted_at': str(decisions.accepted_at.max())},
                  'summaries': summaries, 'legacy_clock_comparisons': comparisons, 'weekly_non_price_columns_exact': True,
                  'consumer_input_maps': consumer_inputs,
                  'native_opportunity_supply': {**native_references[0], 'basis': captures[selected[OPPORTUNITY]['run']]['parameters']['native_supply_basis'],
                                                'binding': 'Declared upstream in authenticated opportunity capture; not an eighth consumer input',
                                                'distinct_from_scenario_ledger': native_references[0]['sha256'] != selected[LEDGER]['sha256']},
                  'scenario_ledger': selected[LEDGER],
                  'input_selection_sha256': sha(stage/'input-selection.json'), 'outputs': outputs,
                  'scientific_adoption': False, 'provider_calls': 0, 'fits_or_scores': 0, 'full_weekly_panel_rebuilt': False,
                  'limits': ['Retrospective observed-time proxies; historical publication/revision availability is unverified.',
                             'Market is a pre-Granite key/acceptance-clock projection only, with no outcome fields or menu/build/fit/score calls.',
                             'Weekly successor changes only DefiLlama price/volatility and adds lineage; all other historical fields remain exact and retain their original accounting lineage.',
                             'Scenario is descriptive daily-close valuation, not a prediction-time feature or transaction-weighted intraday USD flow.',
                             'Native opportunity yields retain their declared upstream realised-ledger opening supply, separately from scenario stock/issuance. They are not exact protocol-counter offers.',
                             'No adoption into P0-P3 or fit-for-use scientific acceptance is implied.']}
        write_json(stage/'report.json', report)
        receipt = {'schema_version': 'named-price-consumer-export/v1', 'status': report['status'], 'builder_sha256': selection['builder_sha256'],
                   'source_freeze_sha256': selection['source_freeze_sha256'], 'input_selection_sha256': report['input_selection_sha256'], 'report_sha256': sha(stage/'report.json'),
                   'outputs': outputs, 'scientific_adoption': False}
        write_json(stage/'receipt.json', receipt)
        import shutil
        shutil.rmtree(stage/'spill', ignore_errors=True)
        stage.rename(out)
    print(json.dumps({'out': str(out), 'receipt_sha256': sha(out/'receipt.json'), 'rows': {k:v['quotes']['rows'] for k,v in summaries.items()}}, indent=2), flush=True)


if __name__ == '__main__':
    main()
