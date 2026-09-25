#!/usr/bin/env python3
"""Check that the notebooks can run here: the data release is in place, every run matches its receipt, and each notebook executes.

Run from the repository root after `uv sync --locked --group notebook` and extracting the data release into data/runs/:

    uv run --group notebook python scripts/verify_notebooks.py

Prints one PASS or FAIL line per check and exits non-zero on any failure. The notebooks are executed into a temporary
folder, so the saved copies in notebooks/ are never changed.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ("validator-rewards-article.ipynb", "staking-periods.ipynb")

# The runs in the data release: the dataset each one builds and its run folder under data/runs/.
RELEASE_RUNS = {
    "staking-periods-2026-09-22": "derived.staking-periods",
    "node-table-2026-09-22b": "derived.node-table",
    "validator-stakes-2026-09-22": "snowflake.primary-validator-stakes",
    "validator-stakes-2026-09-19": "snowflake.primary-validator-stakes",
    "avax-price-helicon-baseline-early": "defillama.avax-price-daily",
    "avax-market-helicon-baseline-early": "coingecko.avax-market-daily",
    "monetary-daily-2026-09-24-interim": "derived.avax-monetary-daily",
}


def report(ok: bool, check: str, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  {check}{'  ' + detail if detail else ''}", flush=True)
    return ok


def check_runs() -> bool:
    from avalanche_research import datasets

    ok = True
    for run, dataset_id in RELEASE_RUNS.items():
        try:
            datasets.parquet_path(dataset_id, run)
            ok &= report(True, f"data run {run}")
        except Exception as error:  # a missing folder or a file that differs from its receipt
            ok &= report(False, f"data run {run}", f"{type(error).__name__}: {error}. Extract the data release into data/runs/, see SETUP.md step 4")
    return ok


def check_notebook(name: str) -> bool:
    import nbformat
    from nbconvert.preprocessors import CellExecutionError, ExecutePreprocessor

    notebook = nbformat.read(ROOT / "notebooks" / name, as_version=4)
    with tempfile.TemporaryDirectory() as scratch:
        try:
            ExecutePreprocessor(timeout=900, kernel_name="python3").preprocess(notebook, {"metadata": {"path": str(ROOT / "notebooks")}})
        except CellExecutionError as error:
            return report(False, f"notebook {name}", str(error).strip().splitlines()[-1])
        nbformat.write(notebook, Path(scratch) / name)
    cells = sum(cell.cell_type == "code" for cell in notebook.cells)
    return report(True, f"notebook {name}", f"{cells} code cells ran")


def main() -> int:
    ok = check_runs()
    if ok:
        for name in NOTEBOOKS:
            ok &= check_notebook(name)
    print("All checks passed." if ok else "Some checks failed.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
