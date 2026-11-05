"""The label link to stake: each P-Chain address that an entity-labelled C-Chain address paid by an export to the
P-Chain, or that paid one by an import from it, with the label and when the link first appears.

AVAX reaches staking on the P-Chain through atomic exports from the C-Chain, and leaves through imports. An export names
its C-Chain sender and the owner addresses of its P-Chain outputs, and an import its P-Chain sender and C-Chain
recipient (``allium.p-chain-atomic-transactions``). Where the C-Chain address carries an entity label in
``allium.identity-labels-atomic``, the P-Chain address is linked to that entity. A row is one P-Chain address, one
labelled C-Chain address and one direction. The Foundation's mapping in ``af.address-mapping-atomic`` is joined beside
the label; for these addresses it is sourced from the same labels, so it confirms nothing on its own.

``owner_class`` groups Allium's category: an exchange, a custodian, a payment or financial service, an MEV bot, wallet
software, decentralised finance, or other. Wallet software, such as MetaMask user, is a heuristic on how an address
behaves and names the software, not the owner.

The held-back cut is 2025-11-19 00:00 UTC. Counts, amounts and last times read only transactions before it, and a link
whose first transaction is on or after it is kept with ``held_back`` true and zero counts, so the check can require
the same rows from inputs cut at that instant. The labels are one current snapshot, with Allium's attribution time in
``label_attributed_at``; a consumer dating a score at an origin before the cut uses links whose ``first_at`` is before
the origin, and may also require the attribution to be. Addresses stay in model tables. Client outputs report linked
stake as counts and shares by class, never an address, and nothing joins an address to any identity outside the chain.

The summary gives the coverage the data plan asks for first: the validator stake and the delegated stake active at the
origin 2025-11-18 00:00 UTC, by the class of the links its reward addresses (validators) or its funding address
(delegations) had before the origin. A stake with links of several classes takes the first of ``CLASS_ORDER``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from ...core.catalog import DataError, contract_hash, load_catalog
from . import derived_runs as runs

DATASET_ID = "derived.stake-owner-types"
DATASET_IDS = (DATASET_ID,)
TABLE = "stake-owner-types"
INPUTS = {
    "p-chain-atomic-transactions": "allium.p-chain-atomic-transactions",
    "identity-labels-atomic": "allium.identity-labels-atomic",
    "address-mapping-atomic": "af.address-mapping-atomic",
    "seamed-validator-stakes": "derived.seamed-validator-stakes",
    "seamed-delegator-stakes": "derived.seamed-delegator-stakes",
}
CUT_SQL = "TIMESTAMP '2025-11-19 00:00:00'"
ORIGIN_SQL = "TIMESTAMP '2025-11-18 00:00:00'"
SETTINGS = "SET threads = 1; SET memory_limit = '6GB'"
CLASSES = {
    "exchange": "exchange", "centralized_exchange": "exchange", "custody": "custodian",
    "payment_services": "financial_service", "financial_services": "financial_service", "mev": "mev_bot",
    "non_custodial_wallet": "wallet_software", "decentralized_finance": "defi", "liquid_staking": "defi", "bridge": "defi",
}
CLASS_ORDER = ("exchange", "custodian", "financial_service", "defi", "mev_bot", "wallet_software", "other")
ENTITY_CLASSES = ("exchange", "custodian", "financial_service")
TABLE_COLUMNS = {
    "p_chain_address": "VARCHAR", "c_chain_address": "VARCHAR", "link": "VARCHAR", "first_at": "TIMESTAMP",
    "held_back": "BOOLEAN", "last_before_cut_at": "TIMESTAMP", "transactions_before_cut": "BIGINT",
    "avax_before_cut": "DOUBLE", "owner_class": "VARCHAR", "label_entity": "VARCHAR", "label_category": "VARCHAR",
    "label_source_system": "VARCHAR", "label_priority": "INTEGER", "label_attributed_at": "TIMESTAMP",
    "mapping_entity": "VARCHAR", "mapping_category": "VARCHAR", "mapping_sector": "VARCHAR",
}


def _reject(dataset_id: str) -> None:
    if dataset_id != DATASET_ID:
        raise DataError(f"{dataset_id} is not a derived dataset of this module")


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    _reject(dataset_id)
    runs.reject_fetch(DATASET_ID)


def capture(dataset_id: str, output: Path, timeout: float = 20, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    return capture_preview(dataset_id, output, parameters)


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    _reject(dataset_id)
    runs.reject_fetch(DATASET_ID)


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    return build_preview(dataset_id, capture_dir, output)


def load_inputs(connection: Any, inputs: list[dict[str, Any]], cut_inputs: bool = False) -> None:
    """One view per input; with ``cut_inputs`` the atomic transactions stop at the held-back instant."""
    for item in inputs:
        name = item["input_id"].replace("-", "_")
        where = f" WHERE block_timestamp < {CUT_SQL}" if cut_inputs and item["input_id"] == "p-chain-atomic-transactions" else ""
        connection.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{runs.quoted(item['path'])}'){where}")


def compute(connection: Any, name: str = "result") -> None:
    classes = " ".join(f"WHEN '{category}' THEN '{owner}'" for category, owner in CLASSES.items())
    connection.execute(f"""
        CREATE OR REPLACE TABLE {name} AS
        WITH moves AS (
            SELECT unnest(string_split(output_addresses, ',')) AS p_chain_address, c_chain_address, 'export' AS link,
                   block_timestamp, amount_navax
            FROM p_chain_atomic_transactions WHERE direction = 'export'
            UNION ALL
            SELECT p_chain_address, c_chain_address, 'import', block_timestamp, amount_navax
            FROM p_chain_atomic_transactions WHERE direction = 'import' AND p_chain_address IS NOT NULL),
        linked AS (
            SELECT m.p_chain_address, m.c_chain_address, m.link, min(m.block_timestamp) AS first_at,
                   max(m.block_timestamp) FILTER (WHERE m.block_timestamp < {CUT_SQL}) AS last_before_cut_at,
                   count(*) FILTER (WHERE m.block_timestamp < {CUT_SQL}) AS transactions_before_cut,
                   coalesce(sum(m.amount_navax) FILTER (WHERE m.block_timestamp < {CUT_SQL}), 0) / 1e9 AS avax_before_cut
            FROM moves m JOIN identity_labels_atomic l ON l.address = m.c_chain_address
            GROUP BY 1, 2, 3)
        SELECT k.p_chain_address, k.c_chain_address, k.link, k.first_at, k.first_at >= {CUT_SQL} AS held_back,
               k.last_before_cut_at, k.transactions_before_cut, k.avax_before_cut::DOUBLE AS avax_before_cut,
               CASE l.primary_category {classes} ELSE 'other' END AS owner_class,
               l.primary_entity AS label_entity, l.primary_category AS label_category,
               l.source_system AS label_source_system, l.source_priority AS label_priority,
               l.attribution_date AS label_attributed_at,
               a.entity AS mapping_entity, a.category AS mapping_category, a.sector AS mapping_sector
        FROM linked k JOIN identity_labels_atomic l ON l.address = k.c_chain_address
        LEFT JOIN address_mapping_atomic a ON a.address = k.c_chain_address
        ORDER BY k.p_chain_address, k.c_chain_address, k.link""")


def coverage(connection: Any, table: str = "result", attributed: bool = False) -> dict[str, Any]:
    """Validator and delegated stake active at the origin by the class of its links first seen before the origin."""
    order = ", ".join(f"'{name}'" for name in CLASS_ORDER)
    when = f" AND l.label_attributed_at < {ORIGIN_SQL}" if attributed else ""
    result = {}
    for role, stakes, address in (
            ("validator", "seamed_validator_stakes", "unnest(from_json(reward_addresses, '[\"VARCHAR\"]'))"),
            ("delegator", "seamed_delegator_stakes", "delegator_address")):
        rows = connection.execute(f"""
            WITH s AS (SELECT transaction_hash, stake_navax, {address} AS address FROM {stakes}
                       WHERE start_time <= {ORIGIN_SQL} AND end_time > {ORIGIN_SQL}),
                 m AS (SELECT s.transaction_hash, any_value(s.stake_navax) AS stake_navax,
                              min(list_position([{order}], l.owner_class)) AS rank
                       FROM s LEFT JOIN {table} l ON l.p_chain_address = s.address AND l.first_at < {ORIGIN_SQL}{when}
                       GROUP BY 1)
            SELECT coalesce([{order}][rank], 'unlinked'), count(*), sum(stake_navax) FROM m GROUP BY 1 ORDER BY 3 DESC""").fetchall()
        total = sum(stake for _, _, stake in rows)
        entity = sum(stake for owner, _, stake in rows if owner in ENTITY_CLASSES)
        result[role] = {
            "stakes": sum(count for _, count, _ in rows), "avax": round(total / 1e9, 3),
            "entity_share": round(entity / total, 6) if total else None,
            "by_class": {owner: {"stakes": count, "avax": round(stake / 1e9, 3), "share": round(stake / total, 6)}
                         for owner, count, stake in rows},
        }
    return result


def summarize(connection: Any, table: str = "result") -> dict[str, Any]:
    rows, addresses, labelled, late = connection.execute(
        f"SELECT count(*), count(DISTINCT p_chain_address), count(DISTINCT c_chain_address), count_if(held_back) FROM {table}").fetchone()
    return {
        "rows": rows, "p_chain_addresses": addresses, "labelled_c_chain_addresses": labelled, "held_back_links": late,
        "by_class": {f"{owner} {link}": {"links": count, "p_chain_addresses": distinct} for owner, link, count, distinct in connection.execute(
            f"SELECT owner_class, link, count(*), count(DISTINCT p_chain_address) FROM {table} GROUP BY 1, 2 ORDER BY 1, 2").fetchall()},
        "mapping_disagreements": connection.execute(f"""
            SELECT count(DISTINCT c_chain_address) FROM {table}
            WHERE mapping_entity IS NULL OR lower(replace(mapping_entity, ' ', '_')) <> lower(replace(label_entity, ' ', '_'))""").fetchone()[0],
        "origin": "2025-11-18T00:00:00Z",
        "coverage_at_origin": coverage(connection, table),
        "coverage_at_origin_attributed_before": coverage(connection, table, attributed=True),
    }


def parameters() -> dict[str, Any]:
    return {"held_back_cut": "2025-11-19T00:00:00Z", "origin": "2025-11-18T00:00:00Z", "classes": CLASSES,
            "class_order": list(CLASS_ORDER), "entity_classes": list(ENTITY_CLASSES)}


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    """Build the table into a new run directory holding ``capture/`` and ``dataset/``."""
    _reject(dataset_id)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    inputs = runs.select_inputs(DATASET_ID, INPUTS, pinned, root)

    def fill(connection: Any) -> None:
        connection.execute(SETTINGS)
        load_inputs(connection, inputs)
        compute(connection)

    return runs.write_run(DATASET_ID, TABLE, output, inputs, parameters(), fill, summarize)


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """Verify the input runs and the contract, and, given the build: one row per address pair and direction, the same
    rows from a rebuild, and the same rows from a rebuild with the atomic transactions cut at the held-back instant."""
    if against is not None:
        raise DataError(f"{DATASET_ID} takes no --against directory")
    receipt = runs.read_capture(capture_dir, DATASET_ID)
    findings: list[str] = []
    checked = ["input run hashes", "catalog contract"]
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), DATASET_ID):
        findings.append("catalog contract changed since the capture")
    inputs = runs.verified_inputs(receipt, root, findings)
    summary: dict[str, Any] = {"inputs": len(receipt.get("inputs", []))}
    if dataset_dir is not None:
        checked.extend(["build hashes", "columns", "one row per address pair and direction", "rebuild from inputs",
                        "rebuild from atomic transactions cut at the held-back instant"])
        connection = duckdb.connect()
        try:
            connection.execute(SETTINGS)
            build_receipt, found = runs.built_findings(connection, DATASET_ID, receipt, dataset_dir, TABLE, TABLE_COLUMNS)
            findings.extend(found)
            rows, distinct, counted_late = connection.execute("""
                SELECT count(*), count(DISTINCT (p_chain_address, c_chain_address, link)),
                       count_if(held_back AND (transactions_before_cut <> 0 OR avax_before_cut <> 0 OR last_before_cut_at IS NOT NULL))
                FROM built""").fetchone()
            if rows != distinct:
                findings.append(f"{rows - distinct} rows repeat an address pair and direction")
            if counted_late:
                findings.append(f"{counted_late} held-back links count transactions before the cut")
            if len(inputs) == len(INPUTS):
                load_inputs(connection, inputs)
                compute(connection)
                if runs.differ(connection, "built", "result"):
                    findings.append("a rebuild from the recorded inputs differs")
                load_inputs(connection, inputs, cut_inputs=True)
                compute(connection, "result_cut")
                changed = runs.differ(connection, "(SELECT * FROM built WHERE NOT held_back)", "result_cut")
                if changed:
                    findings.append(f"{changed} rows change when the atomic transactions are cut at the held-back instant")
            summary.update(build_receipt.get("summary", {}))
        except (OSError, KeyError, TypeError, ValueError, duckdb.Error) as error:
            findings.append(f"invalid dataset output: {error}")
        finally:
            connection.close()
    return {"dataset_id": DATASET_ID, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}
