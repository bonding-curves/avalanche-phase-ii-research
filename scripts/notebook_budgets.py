"""Measure notebooks against their budgets: code cells, code lines, the largest cell, and with --execute, run time.

    uv run --group notebook python scripts/notebook_budgets.py [paths ...] [--execute] [--json]

Paths are notebooks or folders of notebooks, `notebooks/` by default. A notebook calls library functions and does not
define them, so a new notebook has at most 15 code lines per cell and 120 in all, and runs each cell in 20 s and the
whole in 60 s. An existing notebook may not grow past what it measures today. This is report mode, step `M0` of the
library restructure: it prints the table and marks what exceeds the new-notebook budgets, and always exits 0. Step
`M8` switches it to enforce. Code lines are the lines of each code cell's source, blank and comment lines included.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW_NOTEBOOK = {"cell_lines": 15, "notebook_lines": 120, "cell_seconds": 20.0, "notebook_seconds": 60.0}


@dataclass
class Measure:
    notebook: str
    code_cells: int
    code_lines: int
    largest_cell: int
    run_seconds: float | None = None
    slowest_cell_seconds: float | None = None
    over: list[str] = field(default_factory=list)


def notebooks(paths: list[Path]) -> list[Path]:
    found = []
    for path in paths:
        if path.is_dir():
            found.extend(sorted(p for p in path.glob("*.ipynb") if ".ipynb_checkpoints" not in p.parts))
        elif path.suffix == ".ipynb":
            found.append(path)
    return found


def code_sources(notebook: dict) -> list[str]:
    return ["".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
            for cell in notebook["cells"] if cell["cell_type"] == "code"]


def measure(path: Path, execute: bool = False) -> Measure:
    notebook = json.loads(path.read_text())
    lines = [len(source.splitlines()) for source in code_sources(notebook)]
    result = Measure(path.name, len(lines), sum(lines), max(lines, default=0))
    if execute:
        result.run_seconds, result.slowest_cell_seconds = run_times(path)
    over = []
    if result.largest_cell > NEW_NOTEBOOK["cell_lines"]:
        over.append("cell lines")
    if result.code_lines > NEW_NOTEBOOK["notebook_lines"]:
        over.append("notebook lines")
    if result.slowest_cell_seconds is not None and result.slowest_cell_seconds > NEW_NOTEBOOK["cell_seconds"]:
        over.append("cell time")
    if result.run_seconds is not None and result.run_seconds > NEW_NOTEBOOK["notebook_seconds"]:
        over.append("notebook time")
    result.over = over
    return result


def run_times(path: Path) -> tuple[float, float]:
    """Execute the notebook in a scratch copy, never in place, and time each code cell."""
    import nbformat
    from nbclient import NotebookClient

    notebook = nbformat.read(path, as_version=4)
    client = NotebookClient(notebook, timeout=1800, kernel_name="python3",
                            resources={"metadata": {"path": str(path.parent)}})
    started, slowest = time.perf_counter(), 0.0
    with client.setup_kernel():
        for index, cell in enumerate(notebook.cells):
            if cell.cell_type != "code":
                continue
            cell_started = time.perf_counter()
            client.execute_cell(cell, index)
            slowest = max(slowest, time.perf_counter() - cell_started)
    return round(time.perf_counter() - started, 1), round(slowest, 1)


def table(measures: list[Measure]) -> str:
    rows = ["| Notebook | Code cells | Code lines | Largest cell | Run time | Slowest cell | Over the new-notebook budget |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for m in measures:
        seconds = "" if m.run_seconds is None else f"{m.run_seconds} s"
        slowest = "" if m.slowest_cell_seconds is None else f"{m.slowest_cell_seconds} s"
        rows.append(f"| `{m.notebook}` | {m.code_cells} | {m.code_lines:,} | {m.largest_cell} | {seconds} | {slowest} | "
                    f"{', '.join(m.over) or 'within'} |")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", type=Path, default=[ROOT / "notebooks"])
    parser.add_argument("--execute", action="store_true", help="run each notebook in memory and time its cells")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a Markdown table")
    args = parser.parse_args(argv)
    measures = [measure(path, args.execute) for path in notebooks(args.paths)]
    print(json.dumps([asdict(m) for m in measures], indent=2) if args.json else table(measures))
    return 0


if __name__ == "__main__":
    sys.exit(main())
