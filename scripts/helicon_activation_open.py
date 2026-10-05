"""The validator commitments open when Helicon activated, 2026-09-22 15:00 UTC, with a receipt (WK4).

A commitment is open at activation when its validator period was accepted before activation, started at or before
it, and ends after it. The rows come from the staking-period log. The first validator-set snapshot after activation
checks them: every open commitment still running at the snapshot must be in it with the same node, stake and end, and
every snapshot row not in the list must have started after activation.

    uv run python scripts/helicon_activation_open.py --out data/evidence/helicon-activation-open-2026-09-22

Writes ``open-commitments.csv`` (one row per commitment, ordered by node) and ``receipt.json`` (input runs with
hashes, counts, and the reconciliation). Two runs on the same inputs write the same bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import duckdb

from avalanche_research import datasets
from avalanche_research.model.protocol import MAINNET_UPGRADES

PERIODS = "derived.staking-periods"
SNAPSHOT = "p-chain-rpc.current-validators"
COLUMNS = ("node_id", "transaction_hash", "accepted_at", "start_time", "end_time", "duration_days", "stake_navax",
           "delegation_fee_rate", "regime", "start_kind")


def activation() -> str:
    moment = next(upgrade.activated_at for upgrade in MAINNET_UPGRADES.upgrades if upgrade.name.lower() == "helicon")
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def run(periods_run: str, snapshot_run: str, out: Path) -> dict:
    at = activation()
    periods = datasets.parquet_path(PERIODS, periods_run)
    snapshot = datasets.parquet_path(SNAPSHOT, snapshot_run)
    con = duckdb.connect()
    con.execute(
        f"""
        CREATE TABLE open AS SELECT {", ".join(COLUMNS)} FROM read_parquet(?)
        WHERE role = 'validator' AND accepted_at < TIMESTAMP '{at}' AND start_time <= TIMESTAMP '{at}'
          AND end_time > TIMESTAMP '{at}'
        ORDER BY node_id, transaction_hash
        """,
        [str(periods)],
    )
    con.execute("CREATE TABLE snap AS SELECT * FROM read_parquet(?)", [str(snapshot)])
    observed_at = con.execute("SELECT strftime(max(observed_at), '%Y-%m-%d %H:%M:%S') FROM snap").fetchone()[0]
    rows, nodes, stake_navax, repeated = con.execute(
        "SELECT count(*), count(DISTINCT node_id), sum(stake_navax)::BIGINT, count(*) - count(DISTINCT transaction_hash) FROM open"
    ).fetchone()
    ended_before_snapshot, missing_from_snapshot, differing, started_after, snapshot_not_explained = con.execute(
        f"""
        SELECT
          (SELECT count(*) FROM open WHERE end_time <= TIMESTAMP '{observed_at}'),
          (SELECT count(*) FROM open o WHERE end_time > TIMESTAMP '{observed_at}'
             AND NOT EXISTS (SELECT 1 FROM snap s WHERE s.transaction_hash = o.transaction_hash)),
          (SELECT count(*) FROM open o JOIN snap s USING (transaction_hash)
             WHERE o.node_id <> s.node_id OR o.stake_navax <> s.stake_navax OR o.end_time <> s.end_time),
          (SELECT count(*) FROM snap s WHERE s.start_time > TIMESTAMP '{at}'
             AND NOT EXISTS (SELECT 1 FROM open o WHERE o.transaction_hash = s.transaction_hash)),
          (SELECT count(*) FROM snap s WHERE s.start_time <= TIMESTAMP '{at}'
             AND NOT EXISTS (SELECT 1 FROM open o WHERE o.transaction_hash = s.transaction_hash))
        """
    ).fetchone()
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "open-commitments.csv"
    con.execute(
        "COPY (SELECT node_id, transaction_hash, strftime(accepted_at, '%Y-%m-%dT%H:%M:%SZ') AS accepted_at, "
        "strftime(start_time, '%Y-%m-%dT%H:%M:%SZ') AS start_time, strftime(end_time, '%Y-%m-%dT%H:%M:%SZ') AS end_time, "
        "round(duration_days, 6) AS duration_days, stake_navax, delegation_fee_rate, regime, start_kind FROM open "
        "ORDER BY node_id, transaction_hash) TO ? (HEADER, DELIMITER ',')",
        [str(csv_path)],
    )
    con.close()
    reconciled = repeated == 0 and missing_from_snapshot == 0 and differing == 0 and snapshot_not_explained == 0

    def describe(dataset_id: str, name: str, path: Path) -> dict:
        record = datasets.receipt(dataset_id, name)
        return {"dataset_id": dataset_id, "run": name, "capture_id": record["capture"]["capture_id"],
                "parquet_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    receipt = {
        "schema": "helicon-activation-open/v1",
        "activation_utc": at.replace(" ", "T") + "Z",
        "rule": "validator period accepted before activation, started at or before it, ending after it",
        "inputs": [describe(PERIODS, periods_run, periods), describe(SNAPSHOT, snapshot_run, snapshot)],
        "open_commitments": rows,
        "nodes": nodes,
        "stake_navax": stake_navax,
        "reconciliation": {
            "snapshot_observed_at_utc": observed_at.replace(" ", "T") + "Z",
            "ended_between_activation_and_snapshot": ended_before_snapshot,
            "open_and_running_but_missing_from_snapshot": missing_from_snapshot,
            "node_stake_or_end_differs": differing,
            "snapshot_rows_started_after_activation": started_after,
            "snapshot_rows_started_before_activation_not_in_list": snapshot_not_explained,
            "repeated_transactions": repeated,
            "passed": reconciled,
        },
        "outputs": [{"path": csv_path.name, "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest()}],
    }
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--periods", default="staking-periods-2026-10-02")
    parser.add_argument("--snapshot", default="current-validators-2026-09-22")
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    receipt = run(arguments.periods, arguments.snapshot, arguments.out)
    print(json.dumps({key: receipt[key] for key in ("open_commitments", "nodes", "stake_navax", "reconciliation")}, indent=2))
    if not receipt["reconciliation"]["passed"]:
        raise SystemExit("the open commitments do not reconcile with the snapshot")


if __name__ == "__main__":
    main()
