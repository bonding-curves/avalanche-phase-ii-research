"""Synthetic witnesses for raw-row reductions, era clocks and matched support."""

import hashlib
import json
from datetime import timedelta
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from avalanche_research.core.catalog import DataError
from avalanche_research.datasets.derived.monetary import REWARD_ACCOUNTING_BASIS
from avalanche_research.staking_cohorts import (
    CANONICAL_ERA_FAMILIES,
    canonical_era_table,
)

PERIOD_TYPES = {
    "transaction_hash": "VARCHAR",
    "role": "VARCHAR",
    "node_id": "VARCHAR",
    "tx_type": "VARCHAR",
    "validator_transaction_hash": "VARCHAR",
    "accepted_at": "TIMESTAMP",
    "start_time": "TIMESTAMP",
    "end_time": "TIMESTAMP",
    "last_cycle_end_time": "TIMESTAMP",
    "stake_navax": "BIGINT",
    "duration_days": "DOUBLE",
    "delegation_fee_rate": "DOUBLE",
    "rewarded_at": "TIMESTAMP",
    "realized_reward_navax": "BIGINT",
    "rewarded": "BOOLEAN",
}
CYCLE_TYPES = {
    "validator_transaction_hash": "VARCHAR",
    "node_id": "VARCHAR",
    "cycle": "BIGINT",
    "start_time": "TIMESTAMP",
    "end_time": "TIMESTAMP",
    "weight_navax": "BIGINT",
    "reward_transaction_hash": "VARCHAR",
    "rewarded": "BOOLEAN",
    "restaked_validation_navax": "BIGINT",
    "restaked_delegatee_navax": "BIGINT",
    "withdrawn_validation_navax": "BIGINT",
    "withdrawn_delegatee_navax": "BIGINT",
}
LEDGER_TYPES = {
    "date_utc": "DATE",
    "complete": "BOOLEAN",
    "total_supply_close_wei": "DECIMAL(38,0)",
    "active_validator_stake_wei": "DECIMAL(38,0)",
    "active_delegated_stake_wei": "DECIMAL(38,0)",
    "issued_rewards_wei": "DECIMAL(38,0)",
    "burned_wei": "DECIMAL(38,0)",
}


def period(
    tx, node, accepted, *, stake=100, duration=1, role="validator", reward=None, **kw
):
    start = pd.Timestamp(accepted)
    return {
        "transaction_hash": tx,
        "role": role,
        "node_id": node,
        "tx_type": "AddValidatorTx",
        "accepted_at": accepted,
        "start_time": str(start),
        "end_time": str(start.to_pydatetime() + timedelta(days=duration)),
        "stake_navax": int(stake * 10**9),
        "duration_days": duration,
        "delegation_fee_rate": 0.02 if role == "validator" else None,
        "rewarded_at": str(start.to_pydatetime() + timedelta(days=duration))
        if reward is not None
        else None,
        "realized_reward_navax": int(reward * 10**9) if reward is not None else None,
        "rewarded": reward > 0 if reward is not None else None,
        **kw,
    }


def pinned(
    tmp_path,
    periods=None,
    cycles=None,
    ledger=None,
    cutoff="2026-09-25T12:00:00Z",
    addresses=None,
    basis=None,
):
    periods = (
        periods
        if periods is not None
        else [
            period("before", "n1", "2026-09-22 14:59:59", stake=100, reward=0.01),
            period("exact", "n1", "2026-09-22 15:00:00", stake=1, duration=100),
            period("after", "n2", "2026-09-23 15:00:00", stake=1, duration=50),
            period(
                "delegation",
                "n1",
                "2026-09-23 12:00:00",
                stake=5,
                duration=14,
                role="delegator",
            ),
        ]
    )
    ledger = (
        ledger
        if ledger is not None
        else [
            {
                "date_utc": "2026-09-22",
                "complete": True,
                "total_supply_close_wei": 1000 * 10**18,
                "active_validator_stake_wei": 101 * 10**18,
                "active_delegated_stake_wei": 0,
                "issued_rewards_wei": 10**16,
                "burned_wei": 10**15,
            },
            {
                "date_utc": "2026-09-23",
                "complete": True,
                "total_supply_close_wei": 1000 * 10**18,
                "active_validator_stake_wei": 2 * 10**18,
                "active_delegated_stake_wei": 5 * 10**18,
                "issued_rewards_wei": 2 * 10**16,
                "burned_wei": 10**15,
            },
            {
                "date_utc": "2026-09-24",
                "complete": False,
                "total_supply_close_wei": None,
                "active_validator_stake_wei": None,
                "active_delegated_stake_wei": None,
                "issued_rewards_wei": None,
                "burned_wei": None,
            },
        ]
    )
    root = tmp_path / "runs"
    entries = []
    captures = {}
    defs = {
        "derived.staking-periods": ("periods", PERIOD_TYPES, periods),
        "derived.avax-monetary-daily": ("ledger", LEDGER_TYPES, ledger),
        "derived.seamed-validator-stakes": (
            "validators",
            {
                "transaction_hash": "VARCHAR",
                "node_id": "VARCHAR",
                "accepted_at": "TIMESTAMP",
                "reward_addresses": "VARCHAR",
            },
            [
                {k: r[k] for k in ("transaction_hash", "node_id", "accepted_at")}
                | {
                    "reward_addresses": json.dumps(
                        (addresses or {}).get(r["transaction_hash"], [r["node_id"]])
                    )
                }
                for r in periods
                if r["role"] == "validator"
            ],
        ),
        "derived.seamed-delegator-stakes": (
            "delegators",
            {"transaction_hash": "VARCHAR"},
            [
                {"transaction_hash": r["transaction_hash"]}
                for r in periods
                if r["role"] == "delegator"
            ],
        ),
        "derived.p-chain-staking-cycles": ("cycles", CYCLE_TYPES, cycles or []),
    }
    for dataset, (name, types, rows) in defs.items():
        run = root / name
        (run / "dataset").mkdir(parents=True)
        (run / "capture").mkdir()
        path = run / "dataset" / (name + ".parquet")
        with duckdb.connect() as db:
            db.execute(
                "CREATE TABLE records("
                + ",".join(f"{k} {t}" for k, t in types.items())
                + ")"
            )
            if rows:
                db.executemany(
                    "INSERT INTO records VALUES (" + ",".join("?" for _ in types) + ")",
                    [[r.get(k) for k in types] for r in rows],
                )
            db.execute("COPY records TO ? (FORMAT PARQUET)", [str(path)])
        capture = {
            "dataset_id": dataset,
            "capture_id": "capture:" + name,
            "completed_at": cutoff,
            "inputs": [],
        }
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entry = {
            "dataset_id": dataset,
            "run": name,
            "parquet": path.name,
            "bytes": path.stat().st_size,
            "sha256": digest,
            "check": "pass",
            "capture_id": capture["capture_id"],
            "captured_at": cutoff,
        }
        build = {
            "dataset_id": dataset,
            "source_capture_id": capture["capture_id"],
            "outputs": [{"path": path.name, "bytes": entry["bytes"], "sha256": digest}],
        }
        for relative, value in (
            ("dataset/build.json", build),
            ("dataset/check.json", {"status": "pass"}),
        ):
            (run / relative).write_text(json.dumps(value))
        captures[dataset] = capture
        entries.append(entry)
    periods_capture = captures["derived.staking-periods"]
    for entry in entries:
        source = {
            "derived.seamed-validator-stakes": "validator-stakes",
            "derived.seamed-delegator-stakes": "delegator-stakes",
            "derived.p-chain-staking-cycles": "p-staking-cycles",
        }.get(entry["dataset_id"])
        if source:
            periods_capture["inputs"].append({**entry, "input_id": source})
    captures["derived.avax-monetary-daily"]["inputs"] = [
        {**entries[0], "input_id": "staking-periods"}
    ]
    periods_capture["inputs"].append(
        {
            "dataset_id": "derived.seamed-staking-rewards",
            "input_id": "staking-rewards",
            "captured_at": cutoff,
        }
    )
    if basis is not None:
        captures["derived.avax-monetary-daily"]["reward_accounting_basis"] = basis
    if basis == REWARD_ACCOUNTING_BASIS:
        cycle_entry = next(e for e in entries if e["dataset_id"] == "derived.p-chain-staking-cycles")
        block_reference = {"input_id": "blocks", "dataset_id": "p-chain-rpc.blocks", "run": "block-walk",
                           "parquet": "blocks.parquet", "bytes": 7, "sha256": "a"*64, "capture_id": "capture:blocks"}
        captures["derived.p-chain-staking-cycles"]["inputs"] = [block_reference]
        captures["derived.avax-monetary-daily"]["inputs"].extend([
            {**cycle_entry, "input_id": "staking-cycles"}, {**block_reference, "input_id": "cycle-blocks"}])
        companion = root / "ledger/dataset/cycle-accounting-events.parquet"
        with duckdb.connect() as db:
            db.execute("CREATE TABLE events(validator_transaction_hash VARCHAR,node_id VARCHAR,cycle BIGINT,reward_transaction_hash VARCHAR,rewarded_at TIMESTAMP,rewarded BOOLEAN,recognised_reward_navax DECIMAL(38,0))")
            rows = [[c['validator_transaction_hash'],c['node_id'],c['cycle'],c['reward_transaction_hash'],c['end_time'],c['rewarded'],
                     sum(c[k] for k in ('restaked_validation_navax','restaked_delegatee_navax','withdrawn_validation_navax','withdrawn_delegatee_navax'))]
                    for c in (cycles or []) if c['rewarded'] is not None]
            if rows:
                db.executemany("INSERT INTO events VALUES (?,?,?,?,?,?,?)", rows)
            db.execute("COPY events TO ? (FORMAT PARQUET)", [str(companion)])
        build_path = companion.parent / "build.json"
        build = json.loads(build_path.read_text())
        build["outputs"].append({"path": companion.name, "bytes": companion.stat().st_size, "sha256": hashlib.sha256(companion.read_bytes()).hexdigest()})
        build_path.write_text(json.dumps(build))
    for entry in entries:
        (root / entry["run"] / "capture/capture.json").write_text(
            json.dumps(captures[entry["dataset_id"]])
        )
    pin = tmp_path / "pin.json"
    pin.write_text(
        json.dumps(
            {
                "schema_version": "avalanche-pins/v1",
                "name": "synthetic",
                "runs": entries,
            }
        )
    )
    return pin, root


def cell(frame, family, statistic=None, role="validator", era="All", weight=None):
    f = frame[
        (frame.measure_family == family) & (frame.role == role) & (frame.era == era)
    ]
    if statistic is not None:
        f = f[f.statistic == statistic]
    if weight is not None:
        f = f[f.weight == weight]
    assert len(f) == 1
    return f.iloc[0]


def test_all_nine_eras_boundary_partial_and_additive_closure(tmp_path):
    pin, root = pinned(tmp_path)
    f = canonical_era_table(pin, root=root)
    assert (
        set(f.measure_family) == set(CANONICAL_ERA_FAMILIES)
        and len(CANONICAL_ERA_FAMILIES) == 29
    )
    assert f.groupby("role").era.nunique().to_dict() == {
        "validator": 10,
        "delegator": 10,
    }
    assert cell(f, "Commitments", "transactions", era="Granite").value == 1
    assert cell(f, "Commitments", "transactions", era="Helicon").value == 2
    assert (
        cell(f, "Nodes", "distinct nodes").value == 2
    )  # repeated node does not add across eras
    eras = f[
        (f.role == "validator")
        & (f.era != "All")
        & (f.measure_family == "Gross stake committed")
        & (f.statistic == "total entry flow")
    ]
    assert (
        eras.value.sum() == cell(f, "Gross stake committed", "total entry flow").value
    )
    h = cell(f, "Window", era="Helicon")
    assert h.fractional_days == pytest.approx(2.875)
    assert h.window_start_utc == "2026-09-22T15:00:00Z" and h.partial
    assert cell(f, "Window", era="Apricot").scheduled_end_utc == "2022-10-18T16:00:00Z"


def test_raw_medians_and_weighted_medians_recomputed_for_all(tmp_path):
    pin, root = pinned(
        tmp_path,
        periods=[
            period("a", "n1", "2026-09-21", stake=100, duration=1),
            period("b", "n2", "2026-09-22 16:00", stake=1, duration=50),
            period("c", "n3", "2026-09-22 16:01", stake=1, duration=100),
        ],
    )
    f = canonical_era_table(pin, root=root)
    assert cell(f, "Stake per commitment", "median").value == 1
    assert cell(f, "Stake-weighted median stake", "median").value == 100
    assert cell(f, "Duration", "median").value == 50
    assert cell(f, "Stake-weighted duration", "median").value == 1
    assert cell(f, "Stake-weighted duration", "mean").value == pytest.approx(250 / 102)
    assert cell(f, "Nodes", "new nodes").value == 3


def test_reward_rate_matches_closed_rows_and_never_turns_unknown_into_zero(tmp_path):
    pin, root = pinned(tmp_path)
    f = canonical_era_table(pin, root=root)
    rate = cell(f, "Cohort earned rate")
    assert rate.value == pytest.approx(3.65)
    assert rate.denominator_value == 100 and rate.support_count == 1
    assert rate.closed_count_below_95_percent and not rate.closed_stake_below_95_percent
    assert pd.isna(
        cell(
            f,
            "Realized rewards of the cohort",
            "closed-known total including restaked cycle rewards",
            era="Helicon",
        ).value
    )
    assert cell(
        f, "Closed share", "closed-known coverage", weight="count"
    ).value == pytest.approx(100 / 3)


def test_ledger_support_has_separate_day_count_and_matched_calendar_denominator(
    tmp_path,
):
    pin, root = pinned(tmp_path)
    f = canonical_era_table(pin, root=root)
    h = cell(f, "Calendar earned rate", era="Helicon")
    assert h.ledger_complete_days == 2 and h.ledger_eligible_days == 3
    assert h.ledger_missing_or_incomplete_days == 1
    assert h.denominator_value == 108 and h.value == pytest.approx(36500 * 0.03 / 108)
    assert cell(f, "Net inflation", era="Helicon").value == pytest.approx(
        36500 * 0.028 / (1000 * 2)
    )
    assert pd.isna(cell(f, "Issued in the window", era="Genesis").value)
    assert h.support_status == "Missing or incomplete ledger support"


def test_cycles_retain_transaction_count_weights_abort_and_unresolved_outcomes(
    tmp_path,
):
    p = period(
        "auto",
        "n1",
        "2026-09-22 18:00",
        stake=100,
        duration=1,
        tx_type="AddAutoRenewedValidatorTx",
        last_cycle_end_time="2026-09-25 18:00",
    )
    cycles = [
        {
            "validator_transaction_hash": "auto",
            "node_id": "n1",
            "cycle": i,
            "start_time": f"2026-09-{21 + i} 18:00",
            "end_time": f"2026-09-{22 + i} 18:00",
            "weight_navax": int(weight * 1e9),
            "reward_transaction_hash": f"r{i}" if i < 3 else None,
            "rewarded": i == 1 if i < 3 else None,
            "restaked_validation_navax": int(2 * 1e9)
            if i == 1
            else 0
            if i == 2
            else None,
            "restaked_delegatee_navax": 0 if i < 3 else None,
            "withdrawn_validation_navax": 0 if i < 3 else None,
            "withdrawn_delegatee_navax": 0 if i < 3 else None,
        }
        for i, weight in ((1, 100), (2, 102), (3, 102))
    ]
    pin, root = pinned(tmp_path, periods=[p], cycles=cycles)
    f = canonical_era_table(pin, root=root)
    assert cell(f, "Commitments", "commitments including cycles").value == 3
    assert cell(f, "Commitments", "transactions").value == 1
    assert cell(f, "Gross stake committed", "total entry flow").value == 304
    assert (
        cell(f, "Failed share", "failed among closed-known", weight="count").value == 50
    )
    assert (
        cell(
            f,
            "Realized rewards of the cohort",
            "closed-known total including restaked cycle rewards",
        ).value
        == 2
    )
    assert "payment-day" in f.attrs["metadata"]["cycle_reward_basis"]
    assert "Original transaction stake" in f.attrs["metadata"]["ledger_stock_basis"]


def test_dated_groups_do_not_read_later_addresses_and_delegator_owners_unsupported(
    tmp_path,
):
    rows = [
        period("old", "n1", "2026-09-21", duration=100),
        period("other", "n2", "2026-09-21 00:01", duration=100),
        period("future", "n1", "2026-09-23", duration=100),
    ]
    pin, root = pinned(
        tmp_path,
        periods=rows,
        addresses={"old": ["shared"], "other": ["shared"], "future": ["changed"]},
    )
    f = canonical_era_table(pin, root=root)
    assert cell(f, "Operators", era="Granite").value == 1
    assert (
        cell(f, "Operators", era="Helicon").value == 1
    )  # only n1 accepted, grouped as of later cutoff
    assert cell(f, "Operators").value == 2
    assert pd.isna(cell(f, "Operators", role="delegator").value)
    assert (
        cell(f, "Operators", role="delegator").support_status
        == "Unsupported delegator ownership"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_input",
        "duplicate_input",
        "corrupt_bytes",
        "failed_check",
        "missing_cycle",
        "duplicate_ledger",
    ],
)
def test_input_or_grain_mutation_refused(tmp_path, mutation):
    periods = (
        [period("auto", "n1", "2026-09-22 18:00", tx_type="AddAutoRenewedValidatorTx")]
        if mutation == "missing_cycle"
        else None
    )
    pin, root = pinned(tmp_path, periods=periods)
    j = json.loads(pin.read_text())
    if mutation == "missing_input":
        j["runs"].pop()
        pin.write_text(json.dumps(j))
    elif mutation == "duplicate_input":
        j["runs"][-1] = j["runs"][0]
        pin.write_text(json.dumps(j))
    elif mutation == "corrupt_bytes":
        (root / "periods/dataset/periods.parquet").write_bytes(b"corrupt")
    elif mutation == "failed_check":
        (root / "periods/dataset/check.json").write_text('{"status":"fail"}')
    elif mutation == "duplicate_ledger":
        path = root / "ledger/dataset/ledger.parquet"
        with duckdb.connect() as db:
            db.execute("CREATE TABLE d AS SELECT * FROM read_parquet(?)", [str(path)])
            db.execute("INSERT INTO d SELECT * FROM d LIMIT 1")
            db.execute("COPY d TO ? (FORMAT PARQUET)", [str(path)])
        e = next(
            e for e in j["runs"] if e["dataset_id"] == "derived.avax-monetary-daily"
        )
        e.update(
            bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        build = json.loads((path.parent / "build.json").read_text())
        build["outputs"][0].update(bytes=e["bytes"], sha256=e["sha256"])
        (path.parent / "build.json").write_text(json.dumps(build))
        pin.write_text(json.dumps(j))
    with pytest.raises(DataError):
        canonical_era_table(pin, root=root)


def test_exporter_writes_bound_external_csv_and_refuses_reuse(tmp_path):
    import runpy

    export_table = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/staking_record_tables.py")
    )["export_table"]
    pin, root = pinned(tmp_path)
    out = tmp_path / "export"
    receipt = export_table(pin, out, runs_root=root, threads=2, memory_limit="256MB")
    assert receipt["measure_families"] == 29 and receipt["role_era_pairs"] == 20
    assert receipt["scientific_acceptance"] is False
    for output in receipt["outputs"]:
        assert (
            hashlib.sha256((out / output["path"]).read_bytes()).hexdigest()
            == output["sha256"]
        )
    metadata = json.loads((out / "metadata.json").read_text())
    assert metadata["pin_sha256"] == hashlib.sha256(pin.read_bytes()).hexdigest()
    assert not (out / "spill").exists()
    assert pd.read_csv(out / "era-table.csv").measure_family.nunique() == 29
    with pytest.raises(DataError, match="already exists"):
        export_table(pin, out, runs_root=root)


def test_export_refusal_leaves_no_partial_result(tmp_path):
    import runpy

    export_table = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/staking_record_tables.py")
    )["export_table"]
    pin, root = pinned(tmp_path)
    (root / "periods/dataset/periods.parquet").write_bytes(b"corrupt")
    out = tmp_path / "export"
    with pytest.raises(DataError):
        export_table(pin, out, runs_root=root)
    assert not out.exists() and not list(tmp_path.glob("staking-era-*"))


@pytest.mark.parametrize(
    "grain,field",
    [
        ("period", "role"),
        ("period", "duration_days"),
        ("cycle", "node_id"),
        ("cycle", "start_time"),
        ("cycle", "end_time"),
    ],
)
def test_required_nulls_are_refused_even_with_authentic_byte_pin(
    tmp_path, grain, field
):
    if grain == "period":
        rows = [period("bad", "n1", "2026-09-23", **{field: None})]
        pin, root = pinned(tmp_path, periods=rows)
    else:
        rows = [period("auto", "n1", "2026-09-23", tx_type="AddAutoRenewedValidatorTx")]
        cycle = {
            "validator_transaction_hash": "auto",
            "node_id": "n1",
            "cycle": 1,
            "start_time": "2026-09-23",
            "end_time": "2026-09-24",
            "weight_navax": 100 * 10**9,
            field: None,
        }
        pin, root = pinned(tmp_path, periods=rows, cycles=[cycle])
    with pytest.raises(DataError, match="invalid or duplicate"):
        canonical_era_table(pin, root=root)


def restaking_pin(tmp_path, *, effective=True):
    """Twelve independent owners: principal1200, then effective1210. Ten AVAX restakes once."""
    rows = [period(f"v{i}", f"n{i}", "2026-09-22 18:00", duration=100) for i in range(11)]
    rows += [period("auto", "auto-node", "2026-09-22 18:00", tx_type="AddAutoRenewedValidatorTx",
                    last_cycle_end_time="2026-09-25 18:00"),
             period("d", "n0", "2026-09-22 18:00", role="delegator", stake=50, duration=100)]
    cycles = [
        {"validator_transaction_hash": "auto", "node_id": "auto-node", "cycle": 1,
         "start_time": "2026-09-22 18:00", "end_time": "2026-09-23 18:00", "weight_navax": 100*10**9,
         "reward_transaction_hash": "reward-auto", "rewarded": True, "restaked_validation_navax": 10*10**9,
         "restaked_delegatee_navax": 0, "withdrawn_validation_navax": 0, "withdrawn_delegatee_navax": 0},
        {"validator_transaction_hash": "auto", "node_id": "auto-node", "cycle": 2,
         "start_time": "2026-09-23 18:00", "end_time": "2026-09-25 18:00", "weight_navax": 110*10**9,
         "reward_transaction_hash": None, "rewarded": None, "restaked_validation_navax": None,
         "restaked_delegatee_navax": None, "withdrawn_validation_navax": None, "withdrawn_delegatee_navax": None},
    ]
    ledger = [{"date_utc": f"2026-09-{day}", "complete": True, "total_supply_close_wei": 10000*10**18,
               "active_validator_stake_wei": (1200+(10 if effective and day==23 else 0))*10**18,
               "active_delegated_stake_wei": 50*10**18, "issued_rewards_wei": (10 if day==23 else 0)*10**18,
               "burned_wei": 0} for day in (22, 23)]
    return pinned(tmp_path, periods=rows, cycles=cycles, ledger=ledger, basis=REWARD_ACCOUNTING_BASIS if effective else None)


def test_effective_ledger_stock_is_used_once_with_principal_identity_and_exact_denominators(tmp_path):
    pin, root = restaking_pin(tmp_path)
    f = canonical_era_table(pin, root=root, threads=2, memory_limit="256MB")
    assert cell(f, "Mean active stake", "validator transaction-base stock").value == 1200
    assert cell(f, "Mean active stake", "validator cycle-weight stock including restaking").value == 1205
    assert cell(f, "Mean active stake", "active restaked reward increment").value == 5
    assert cell(f, "Calendar AVAX-days", "role stock").value == 2410
    assert cell(f, "Calendar AVAX-days", "combined stock").value == 2510
    assert cell(f, "Staking ratio", "validator").value == pytest.approx(12.05)
    assert cell(f, "Staking ratio", "combined validator and delegated").value == pytest.approx(12.55)
    concentration = cell(f, "Concentration")
    assert concentration.value == pytest.approx(100*10/12) and concentration.support_count == 2
    assert concentration.support_status == "Complete dated identity support"
    rate = cell(f, "Calendar earned rate")
    assert rate.denominator_value == 2510 and rate.numerator_value == 10
    assert rate.value == pytest.approx(36500*10/2510)
    assert cell(f, "Issued in the window").statistic == "recognised issuance"
    metadata = f.attrs['metadata']
    assert metadata['ledger_reward_accounting_basis'] == REWARD_ACCOUNTING_BASIS
    assert metadata['daily_stock_oracle']['complete_days'] == 2
    assert metadata['ledger_cycle_event_companion']['path'] == 'cycle-accounting-events.parquet'


def test_legacy_report_retains_principal_calendar_basis_and_separate_cycle_mean(tmp_path):
    pin, root = restaking_pin(tmp_path, effective=False)
    f = canonical_era_table(pin, root=root)
    assert cell(f, "Mean active stake", "validator transaction-base stock").value == 1200
    assert cell(f, "Mean active stake", "validator cycle-weight stock including restaking").value == 1205
    assert cell(f, "Calendar AVAX-days", "combined stock").value == 2500
    assert cell(f, "Staking ratio", "validator").value == 12
    assert cell(f, "Issued in the window").statistic == "paid issuance"
    assert cell(f, "Calendar earned rate").statistic == "combined role rate"
    assert 'Original transaction stake' in f.attrs['metadata']['ledger_stock_basis']
    assert 'daily_stock_oracle' not in f.attrs['metadata']


@pytest.mark.parametrize('mutation', ['unknown-basis', 'ledger-cycle', 'period-cycle', 'ledger-period', 'blocks', 'companion'])
def test_new_basis_requires_exact_lineage_and_companion(tmp_path, mutation):
    pin, root = restaking_pin(tmp_path)
    path = root / ('periods' if mutation == 'period-cycle' else 'ledger') / 'capture/capture.json'
    capture = json.loads(path.read_text())
    if mutation == 'unknown-basis':
        capture['reward_accounting_basis'] = 'unknown/v1'
    elif mutation == 'companion':
        (root / 'ledger/dataset/cycle-accounting-events.parquet').unlink()
    else:
        input_id = {'ledger-cycle':'staking-cycles', 'period-cycle':'p-staking-cycles', 'ledger-period':'staking-periods', 'blocks':'cycle-blocks'}[mutation]
        next(i for i in capture['inputs'] if i['input_id'] == input_id)['bytes'] += 1
    path.write_text(json.dumps(capture))
    with pytest.raises(DataError, match='basis|lineage|companion'):
        canonical_era_table(pin, root=root)


def rewrite_bound_table(pin, root, name, expression):
    path = root / name / 'dataset' / (name+'.parquet')
    with duckdb.connect() as db:
        db.execute(f'CREATE TABLE replacement AS {expression}', [str(path)])
        db.execute('COPY replacement TO ? (FORMAT PARQUET)', [str(path)])
    receipt_path = path.parent / 'build.json'
    build = json.loads(receipt_path.read_text())
    changed = {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    next(o for o in build['outputs'] if o['path'] == path.name).update(changed)
    receipt_path.write_text(json.dumps(build))
    value = json.loads(pin.read_text())
    entry = next(e for e in value['runs'] if e['run'] == name)
    entry.update(changed)
    pin.write_text(json.dumps(value))
    for capture_path in root.glob('*/capture/capture.json'):
        capture = json.loads(capture_path.read_text())
        for item in capture['inputs']:
            if item.get('run') == name:
                item.update(changed)
        capture_path.write_text(json.dumps(capture))


@pytest.mark.parametrize('name,expression,reason', [
    ('ledger', "SELECT * REPLACE (active_validator_stake_wei+1000000000 AS active_validator_stake_wei) FROM read_parquet(?)", 'daily interval oracle'),
    ('ledger', "SELECT * REPLACE (1200*1000000000000000000::DECIMAL(38,0) AS active_validator_stake_wei) FROM read_parquet(?)", 'daily interval oracle'),
    ('cycles', "SELECT * REPLACE (CASE WHEN cycle=2 THEN weight_navax+1 ELSE weight_navax END AS weight_navax) FROM read_parquet(?)", 'stock intervals'),
    ('cycles', "SELECT * REPLACE (CASE WHEN cycle=2 THEN start_time+INTERVAL 1 HOUR ELSE start_time END AS start_time) FROM read_parquet(?)", 'stock intervals'),
])
def test_malformed_or_wrong_basis_stock_refuses_despite_coherent_byte_pin(tmp_path, name, expression, reason):
    pin, root = restaking_pin(tmp_path)
    rewrite_bound_table(pin, root, name, expression)
    with pytest.raises(DataError, match=reason):
        canonical_era_table(pin, root=root)


@pytest.mark.parametrize('mutation', ['clock', 'duplicate'])
def test_rehashed_companion_must_agree_with_selected_cycle_outcomes(tmp_path, mutation):
    pin, root = restaking_pin(tmp_path)
    path = root / 'ledger/dataset/cycle-accounting-events.parquet'
    query = ("SELECT * REPLACE (rewarded_at+INTERVAL 1 HOUR AS rewarded_at) FROM read_parquet(?)" if mutation == 'clock' else
             "SELECT * FROM read_parquet(?) UNION ALL SELECT * FROM read_parquet(?)")
    with duckdb.connect() as db:
        db.execute('CREATE TABLE replacement AS '+query, [str(path)] * (1 if mutation == 'clock' else 2))
        db.execute('COPY replacement TO ? (FORMAT PARQUET)', [str(path)])
    build_path = path.parent / 'build.json'
    build = json.loads(build_path.read_text())
    next(o for o in build['outputs'] if o['path'] == path.name).update(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    build_path.write_text(json.dumps(build))
    with pytest.raises(DataError, match='companion differs'):
        canonical_era_table(pin, root=root)
