"""The package's import contracts, in report mode: the list of broken imports may only shrink.

The contracts are ``[tool.importlinter]`` in pyproject.toml, ``K1`` to ``K5``. Each broken import is compared with
tests/architecture-baseline.txt. A violation that is not listed fails, and so does a listed one that no longer occurs,
so the baseline is kept exact. Line numbers are left out, because they move with unrelated edits.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = Path(__file__).with_name("architecture-baseline.txt")
IMPORT = re.compile(r"^-\s+(avalanche_research\S*) -> (avalanche_research\S*)")


def contract_ids() -> dict[str, str]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["importlinter"]
    return {contract["name"]: contract["id"] for contract in config["contracts"]}


def broken_imports(report: str, names: dict[str, str]) -> set[str]:
    """Each broken import in a lint-imports report, as 'contract importer -> imported'."""
    found, current = set(), None
    lines = report.splitlines()
    for line, following in zip(lines, lines[1:] + [""]):
        heading = " ".join(line.split())
        if heading in names and set(following.strip()) == {"-"}:
            current = names[heading]
            continue
        match = IMPORT.match(line.strip())
        if match and current:
            found.add(f"{current} {match.group(1)} -> {match.group(2)}")
    return found


def baseline() -> set[str]:
    return {line.strip() for line in BASELINE.read_text().splitlines() if line.strip() and not line.startswith("#")}


def test_the_broken_imports_are_exactly_the_baseline():
    pytest.importorskip("importlinter")
    command = shutil.which("lint-imports", path=str(Path(sys.executable).parent)) or shutil.which("lint-imports")
    if command is None:
        pytest.skip("lint-imports is not installed; it is in the dev dependency group")
    result = subprocess.run([command, "--no-cache"], cwd=ROOT, capture_output=True, text=True, check=False)
    report = result.stdout + result.stderr
    assert "Contracts:" in report, report[-2000:]
    names = contract_ids()
    found = broken_imports(report, names)
    expected = baseline()
    assert not found - expected, f"New broken imports, not in the baseline: {sorted(found - expected)}"
    assert not expected - found, f"Fixed imports still listed in the baseline, delete them: {sorted(expected - found)}"


def test_the_report_parser_reads_contracts_and_imports():
    names = {"The rules and the model run without the catalog": "K4"}
    report = """The rules and the model run without the catalog
-----------------------------------------------

avalanche_research.model is not allowed to import avalanche_research.catalog:

-   avalanche_research.model.backtest -> avalanche_research.catalog (l.11)
"""
    assert broken_imports(report, names) == {"K4 avalanche_research.model.backtest -> avalanche_research.catalog"}
