"""The label link to stake, built from small synthetic runs."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from avalanche_research.core.catalog import DataError, canonical_bytes, dataset, load_catalog, sha256
from avalanche_research.datasets.derived import stake_owner_types as owners


def make_run(root: Path, name: str, dataset_id: str, table: str, sql: str) -> None:
    capture_dir, dataset_dir = root / name / "capture", root / name / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / f"{table}.parquet"
    duckdb.connect().execute(f"COPY ({sql}) TO '{parquet}' (FORMAT PARQUET)")
    capture_id = f"capture:test:{name}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({
        "schema_version": "test-capture/v1", "capture_id": capture_id, "dataset_id": dataset_id,
        "completed_at": "2026-11-05T00:00:00Z", "contract_sha256": "0" * 64, "queries": [],
    }))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({
        "schema_version": "test-build/v1", "dataset_id": dataset_id, "source_capture_id": capture_id,
        "completed_at": "2026-11-05T00:00:00Z", "summary": {"rows": 1},
        "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}],
    }))


ATOMIC = """SELECT * FROM (VALUES
    ('e1', 'export', '0xexchange', 'avax1val', 'avax1val', 1000000000000, 1000.0, 0.001, NULL, TIMESTAMP '2024-01-05 00:00:00', 1),
    ('e2', 'export', '0xexchange', 'avax1val', 'avax1val', 500000000000, 500.0, 0.001, NULL, TIMESTAMP '2025-12-01 00:00:00', 2),
    ('e3', 'export', '0xwallet', 'avax1del', 'avax1del,avax1two', 30000000000, 30.0, 0.001, NULL, TIMESTAMP '2024-02-01 00:00:00', 3),
    ('e4', 'export', '0xunlabelled', 'avax1x', 'avax1x', 5000000000, 5.0, 0.001, NULL, TIMESTAMP '2024-02-01 00:00:00', 4),
    ('i1', 'import', '0xexchange', 'avax1late', 'avax1late', 9000000000, 9.0, 0.001, NULL, TIMESTAMP '2025-12-02 00:00:00', 5),
    ('i2', 'import', '0xcustody', 'avax1del', 'avax1del', 2000000000, 2.0, 0.001, NULL, TIMESTAMP '2025-12-03 00:00:00', 6)
  ) AS t(transaction_hash, direction, c_chain_address, p_chain_address, output_addresses, amount_navax, amount_avax,
         fees_avax, output_json, block_timestamp, block_number)"""
LABELS = """SELECT * FROM (VALUES
    ('0xexchange', 'Exchange 1', 'exchange_one', 'exchange', '[]', 1.0, TIMESTAMP '2024-01-01 00:00:00', 'x', 'manual', 100, 1, TIMESTAMP '2024-01-05 00:00:00'),
    ('0xwallet', 'Wallet user', 'wallet app user', 'non_custodial_wallet', '[]', 0.5, TIMESTAMP '2026-01-01 00:00:00', 'x', 'heuristic', 60, 1, TIMESTAMP '2024-02-01 00:00:00'),
    ('0xcustody', 'Custody 1', 'custody_one', 'custody', '[]', 1.0, TIMESTAMP '2024-01-01 00:00:00', 'x', 'manual', 100, 1, TIMESTAMP '2025-12-03 00:00:00')
  ) AS t(address, primary_label, primary_entity, primary_category, subcategory_json, confidence, attribution_date,
         source_type, source_system, source_priority, entity_ranking, first_atomic_at)"""
MAPPING = """SELECT * FROM (VALUES
    ('0xexchange', 'exchange_one', NULL, 'cex', 'institutional', 'identity_labels', 2, TIMESTAMP '2024-01-05 00:00:00')
  ) AS t(address, entity, sub_entity, category, sector, source, priority, first_atomic_at)"""
VALIDATORS = """SELECT * FROM (VALUES
    ('v1', '["avax1val"]', 600000000000000::BIGINT, TIMESTAMP '2025-06-01 00:00:00', TIMESTAMP '2026-06-01 00:00:00'),
    ('v2', '["avax1other","avax1x"]', 400000000000000::BIGINT, TIMESTAMP '2025-06-01 00:00:00', TIMESTAMP '2026-06-01 00:00:00'),
    ('v3', '["avax1val"]', 100000000000000::BIGINT, TIMESTAMP '2024-01-01 00:00:00', TIMESTAMP '2024-06-01 00:00:00')
  ) AS t(transaction_hash, reward_addresses, stake_navax, start_time, end_time)"""
DELEGATORS = """SELECT * FROM (VALUES
    ('d1', 'avax1del', 25000000000::BIGINT, TIMESTAMP '2025-10-01 00:00:00', TIMESTAMP '2026-01-01 00:00:00'),
    ('d2', 'avax1late', 75000000000::BIGINT, TIMESTAMP '2025-10-01 00:00:00', TIMESTAMP '2026-01-01 00:00:00')
  ) AS t(transaction_hash, delegator_address, stake_navax, start_time, end_time)"""


def runs(root: Path, atomic: str = ATOMIC) -> Path:
    make_run(root, "atomic", "allium.p-chain-atomic-transactions", "p-chain-atomic-transactions", atomic)
    make_run(root, "labels", "allium.identity-labels-atomic", "identity-labels-atomic", LABELS)
    make_run(root, "mapping", "af.address-mapping-atomic", "address-mapping-atomic", MAPPING)
    make_run(root, "validators", "derived.seamed-validator-stakes", "seamed-validator-stakes", VALIDATORS)
    make_run(root, "delegators", "derived.seamed-delegator-stakes", "seamed-delegator-stakes", DELEGATORS)
    return root


PINNED = {"allium.p-chain-atomic-transactions": "atomic", "allium.identity-labels-atomic": "labels",
          "af.address-mapping-atomic": "mapping", "derived.seamed-validator-stakes": "validators",
          "derived.seamed-delegator-stakes": "delegators"}


def derive(root: Path, name: str = "out") -> tuple[Path, dict]:
    output = root / name
    return output, owners.derive(owners.DATASET_ID, output, PINNED, root)


def test_catalog_fields_match_the_table():
    definition = dataset(load_catalog(), owners.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(owners.TABLE_COLUMNS)
    assert definition["input_ids"] == list(owners.INPUTS)


def test_links_count_only_transactions_before_the_cut_and_keep_later_links_as_held_back(tmp_path):
    root = runs(tmp_path)
    output, result = derive(root)
    rows = duckdb.connect().execute(f"""
        SELECT p_chain_address, c_chain_address, link, held_back, transactions_before_cut, avax_before_cut, owner_class,
               mapping_entity
        FROM read_parquet('{output / 'dataset' / 'stake-owner-types.parquet'}') ORDER BY 1, 2, 3""").fetchall()
    assert rows == [
        ("avax1del", "0xcustody", "import", True, 0, 0.0, "custodian", None),
        ("avax1del", "0xwallet", "export", False, 1, 30.0, "wallet_software", None),
        ("avax1late", "0xexchange", "import", True, 0, 0.0, "exchange", "exchange_one"),
        ("avax1two", "0xwallet", "export", False, 1, 30.0, "wallet_software", None),
        ("avax1val", "0xexchange", "export", False, 1, 1000.0, "exchange", "exchange_one"),
    ]
    summary = result["build"]["summary"]
    assert summary["held_back_links"] == 2 and summary["mapping_disagreements"] == 2


def test_coverage_at_the_origin_reads_links_before_it_and_ranks_classes(tmp_path):
    root = runs(tmp_path)
    _, result = derive(root)
    coverage = result["build"]["summary"]["coverage_at_origin"]
    validator, delegator = coverage["validator"], coverage["delegator"]
    assert validator["stakes"] == 2 and validator["avax"] == 1_000_000.0 and validator["entity_share"] == 0.6
    assert validator["by_class"]["exchange"]["avax"] == 600_000.0 and validator["by_class"]["unlinked"]["stakes"] == 1
    assert delegator["entity_share"] == 0.0 and delegator["by_class"]["wallet_software"]["avax"] == 25.0
    assert delegator["by_class"]["unlinked"]["avax"] == 75.0
    attributed = result["build"]["summary"]["coverage_at_origin_attributed_before"]
    assert attributed["delegator"]["by_class"] == {"unlinked": {"stakes": 2, "avax": 100.0, "share": 1.0}}


def test_check_passes_and_finds_a_changed_build(tmp_path):
    root = runs(tmp_path)
    output, _ = derive(root)
    result = owners.check(output / "capture", output / "dataset", root=root)
    assert result["status"] == "pass", result["findings"]
    parquet = output / "dataset" / "stake-owner-types.parquet"
    connection = duckdb.connect()
    connection.execute(f"CREATE TABLE t AS SELECT * FROM read_parquet('{parquet}')")
    connection.execute("UPDATE t SET transactions_before_cut = 7 WHERE held_back")
    connection.execute(f"COPY t TO '{parquet}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    findings = owners.check(output / "capture", output / "dataset", root=root)["findings"]
    assert "output hash or size differs: stake-owner-types.parquet" in findings
    assert "2 held-back links count transactions before the cut" in findings


def test_fetch_and_build_are_refused(tmp_path):
    with pytest.raises(DataError, match="avalanche data derive"):
        owners.capture(owners.DATASET_ID, tmp_path / "x")
    with pytest.raises(DataError, match="not a derived dataset"):
        owners.build_preview("derived.other", tmp_path / "c", tmp_path / "x")
