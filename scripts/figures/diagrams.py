#!/usr/bin/env python3
"""Generated structure diagrams.

    uv run python scripts/figures/diagrams.py data_path <folder> [staking-periods run] [ledger run]

`data_path` reads the run receipts of the staking-period log and the daily monetary ledger, by default runs
`staking-periods-2026-09-30` and `avax-monetary-daily-2026-09-30`, and writes two versions of the data path, each as
DOT, SVG, PNG at 288 dpi, and a JSON manifest: `data-path` at memo width, one box per source with its datasets, and
`data-path-full`, one node per dataset with a tooltip naming its run and capture.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from avalanche_research.views import diagrams
from avalanche_research.views.diagrams import lineage


def source_commit() -> dict[str, object]:
    """The client commit the diagram was built from, and whether its tracked source differed from it."""
    here = Path(__file__).resolve().parent

    def git(*arguments: str) -> str:
        return subprocess.run(["git", *arguments], cwd=here, check=True, capture_output=True, text=True).stdout.strip()

    return {"source_commit": git("rev-parse", "HEAD"), "source_dirty": bool(git("status", "--porcelain", "--untracked-files=no", "--", "src", "scripts"))}


def data_path(folder: Path, periods_run: str | None = None, ledger_run: str | None = None) -> None:
    runs = dict(lineage.DEFAULT_RUNS)
    if periods_run:
        runs[lineage.PERIODS] = periods_run
    if ledger_run:
        runs[lineage.LEDGER] = ledger_run
    record = {**lineage.manifest(runs), **source_commit()}
    for name, diagram in (("data-path", lineage.build_memo(runs)), ("data-path-full", lineage.build(runs))):
        paths = diagrams.save(diagram, folder, name, record)
        print(" ".join(str(path) for path in paths.values()))


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] != "data_path":
        raise SystemExit(__doc__)
    data_path(Path(sys.argv[2]), *sys.argv[3:5])


if __name__ == "__main__":
    main()
