"""Reference inspection must be safe and detect source/interface drift."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

import click
import pytest

SPEC = importlib.util.spec_from_file_location("manual_reference", Path(__file__).resolve().parents[1] / "scripts/manual_reference.py")
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)
command_inventory, module_inventory, run = reference.command_inventory, reference.module_inventory, reference.run


def test_click_inventory_never_runs_callbacks_and_detects_nested_option_changes():
    @click.group()
    def root():
        raise AssertionError("group callback executed")

    @root.command()
    @click.option("--count", default=3, type=click.IntRange(min=1), multiple=True)
    def execute(count):
        raise AssertionError("command callback executed")

    before = command_inventory(root)
    option = next(p for p in before[1]["parameters"] if p["name"] == "count")
    assert option["multiple"] is True
    assert option["type"]["min"] == 1
    assert option["effective_default"] == 3
    execute.params[0].default = 4
    assert command_inventory(root) != before


def test_module_inventory_parses_without_importing(tmp_path):
    package = tmp_path / "src/avalanche_research"
    package.mkdir(parents=True)
    source = package / "unsafe_to_import.py"
    source.write_text('"""A fixture with an import side effect."""\nraise RuntimeError("executed")\n'
                      'def transform():\n    """Explain the transform."""\n    return 1\n')
    inventory = module_inventory(tmp_path)
    assert inventory[0]["symbols"][0]["name"] == "transform"
    original_hash = inventory[0]["sha256"]
    source.write_text(source.read_text().replace("return 1", "return 2"))
    assert module_inventory(tmp_path)[0]["sha256"] != original_hash


def test_check_refuses_changed_export_without_rewriting(tmp_path):
    relative = Path("reference.md")
    with patch.object(reference, "build", return_value={relative: b"expected"}):
        run(tmp_path)
        (tmp_path / relative).write_bytes(b"changed")
        with pytest.raises(ValueError, match="Reference differs"):
            run(tmp_path, check=True)
        assert (tmp_path / relative).read_bytes() == b"changed"
