"""Generated diagrams: the data path is read from run receipts, its DOT is deterministic, and Graphviz draws it cleanly."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from avalanche_research.catalog import canonical_bytes
from avalanche_research.views import diagrams
from avalanche_research.views.diagrams import lineage


def make_run(root: Path, run: str, dataset_id: str, inputs: list[tuple[str, str]] = (), rows: int = 5, extra: dict | None = None,
             summary: dict | None = None) -> None:
    capture_dir, dataset_dir = root / run / "capture", root / run / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    capture_id = f"capture:test:{run}"
    capture = {"capture_id": capture_id, "dataset_id": dataset_id, "completed_at": "2026-09-30T00:00:00Z",
               "inputs": [{"dataset_id": d, "run": r} for d, r in inputs], **(extra or {})}
    (capture_dir / "capture.json").write_bytes(canonical_bytes(capture))
    (dataset_dir / "build.json").write_bytes(canonical_bytes({
        "dataset_id": dataset_id, "source_capture_id": capture_id, "completed_at": "2026-09-30T00:00:00Z",
        "summary": {"rows": rows, **(summary or {})}, "outputs": [{"path": "table.parquet", "bytes": 0, "sha256": ""}]}))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    make_run(runs, "share-validators", "snowflake.primary-validator-stakes", rows=100)
    make_run(runs, "walk", "p-chain-rpc.blocks", rows=50)
    make_run(runs, "records", "data-api.p-chain-staking-transactions", rows=7, extra={"blocks_run": "walk"})
    make_run(runs, "backup-validators", "derived.p-chain-validator-stakes", [("p-chain-rpc.blocks", "walk"),
                                                                           ("data-api.p-chain-staking-transactions", "records")], rows=3)
    make_run(runs, "seamed-validators", "derived.seamed-validator-stakes",
             [("snowflake.primary-validator-stakes", "share-validators"), ("derived.p-chain-validator-stakes", "backup-validators")], rows=101,
             summary={"overlap": {"seam": "2026-09-22 07:37:02", "rows_compared": 2, "differing_by_column": {}, "share_rows_missing_in_backup": 0}})
    make_run(runs, "periods", "derived.staking-periods", [("derived.seamed-validator-stakes", "seamed-validators")], rows=101)
    make_run(runs, "burns-2020", "snowflake.c-chain-evm-burn-daily", rows=9)
    make_run(runs, "burns-2021", "snowflake.c-chain-evm-burn-daily", rows=9)
    make_run(runs, "supply", "data-api.avax-supply", rows=1)
    make_run(runs, "ledger", "derived.avax-monetary-daily", [("derived.staking-periods", "periods"), ("snowflake.c-chain-evm-burn-daily", "burns-2020"),
                                                             ("snowflake.c-chain-evm-burn-daily", "burns-2021"), ("data-api.avax-supply", "supply")], rows=30)
    return runs


RUNS = {lineage.PERIODS: "periods", lineage.LEDGER: "ledger"}


def test_the_full_path_follows_every_receipt(root):
    diagram = lineage.build(RUNS, root)
    edges = diagram.edges
    # A derived table's inputs, and a capture's walk named in blocks_run.
    assert ("p-chain-rpc.blocks", "data-api.p-chain-staking-transactions") in edges
    assert ("derived.p-chain-validator-stakes", "derived.seamed-validator-stakes") in edges
    assert ("snowflake.primary-validator-stakes", "derived.seamed-validator-stakes") in edges
    # The burn branch is one node with its run count; the supply snapshots stay their own node.
    assert diagram.nodes[lineage.BURNS].label.endswith("1 datasets, 2 runs") and ("burn-record", lineage.LEDGER) in edges
    assert ("data-api.avax-supply", lineage.LEDGER) in edges
    # Rows and the seam come from the receipts.
    assert "101 rows" in diagram.nodes[lineage.PERIODS].label
    assert "2 rows compared, 0 differ" in diagram.nodes["derived.seamed-validator-stakes"].label
    # The model's reads come from its code.
    assert {(lineage.PERIODS, "model:Replay"), (lineage.LEDGER, "model:Replay"), (lineage.PERIODS, "model:ValidatorLifecycle")} <= edges
    assert ("provider:avalanche-snowflake", "snowflake.primary-validator-stakes") in edges


def test_the_memo_version_groups_by_box_and_keeps_every_receipt_edge_between_boxes(root):
    diagram = lineage.build_memo(RUNS, root)
    assert {"provider:avalanche-snowflake", "provider:avalanche-p-chain-rpc", "provider:avalanche-data-api", "walk", "seamed"} <= set(diagram.nodes)
    assert {("walk", "seamed"), ("provider:avalanche-snowflake", "seamed"), ("seamed", lineage.PERIODS),
            ("provider:avalanche-p-chain-rpc", "provider:avalanche-data-api")} <= diagram.edges
    assert "0 differ" in diagram.nodes["seamed"].label and "100 rows" in diagram.nodes["provider:avalanche-snowflake"].label


def test_the_dot_is_deterministic_and_carries_no_plan_codes(root):
    first, second = diagrams.to_dot(lineage.build_memo(RUNS, root)), diagrams.to_dot(lineage.build_memo(RUNS, root))
    assert first == second
    labels = " ".join(re.findall(r'label=("[^"]*"|<.*?>\]?;)', first))
    assert not re.search(r"\b[A-Z]{1,3}\d+\b", labels)
    # The legend lists only the roles drawn.
    legend = next(line for line in first.splitlines() if line.startswith('  "~legend" [shape=plaintext'))
    assert "Provider" not in legend and "Captured dataset" in legend and "Model" in legend


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz is a system package")
def test_graphviz_draws_both_versions_without_a_warning(root, tmp_path):
    for name, diagram in (("memo", lineage.build_memo(RUNS, root)), ("full", lineage.build(RUNS, root))):
        paths = diagrams.save(diagram, tmp_path / "out", name, lineage.manifest(RUNS, root))
        assert all(path.stat().st_size > 0 for path in paths.values())
        record = json.loads(paths["json"].read_text())
        assert record["graphviz"].startswith("dot - graphviz version") and "derived.staking-periods periods" in record["runs"]
