"""The notebook budget script counts code cells and lines the way the restructure note measured them."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "notebook_budgets.py"
spec = importlib.util.spec_from_file_location("notebook_budgets", SCRIPT)
budgets = importlib.util.module_from_spec(spec)
sys.modules["notebook_budgets"] = budgets  # dataclasses look their module up while the file loads
spec.loader.exec_module(budgets)


def notebook(tmp_path: Path, cells: list[tuple[str, str]]) -> Path:
    path = tmp_path / "example.ipynb"
    path.write_text(json.dumps({"cells": [{"cell_type": kind, "source": source, "metadata": {}}
                                          for kind, source in cells], "metadata": {}, "nbformat": 4,
                                "nbformat_minor": 5}))
    return path


def test_lines_are_counted_per_code_cell_with_blanks_and_comments(tmp_path):
    path = notebook(tmp_path, [("markdown", "# Title\ntext"), ("code", "import x\n\n# note\ny = 1"),
                               ("code", ["a = 1\n", "b = 2"])])
    m = budgets.measure(path)
    assert (m.code_cells, m.code_lines, m.largest_cell, m.over) == (2, 6, 4, [])


def test_a_notebook_over_the_new_budget_is_reported_not_refused(tmp_path, capsys):
    path = notebook(tmp_path, [("code", "\n".join(f"x{i} = {i}" for i in range(20)))])
    assert budgets.measure(path).over == ["cell lines"]
    assert budgets.main([str(tmp_path)]) == 0
    assert "| `example.ipynb` | 1 | 20 | 20 |" in capsys.readouterr().out
