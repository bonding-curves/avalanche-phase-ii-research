"""Orientation uses current tracked files, with no data or model work."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys

import pytest
from click.testing import CliRunner

from avalanche_research import research as module


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "research"
    root.mkdir()
    git(root, "init", "--quiet")
    write(root, "pyproject.toml", '[project]\nname = "avalanche-phase-ii-research"\n')
    write(root, "src/avalanche_research/__init__.py", "")
    write(root, "src/avalanche_research/demo.py", "# example\n")
    write(root, "README.md", "# Read me\n")
    write(root, ".gitignore", "ignored/\n*.secret\n")
    write(root, "content/index.md", '---\ntitle: "Research: map"\n---\n# Repeated heading\n')
    write(root, "content/Phase II/index.md", "---\ntitle: 'Phase II''s pages' # note\n---\n")
    write(root, "content/Phase II/Reference/Topic.md", "---\ntitle: Topic title # note\n---\n")
    write(root, "content/Phase II/Reference/Untitled.md", "# Heading alone\n")
    write(root, "data/pins/manifest.json", "{}\n")
    git(root, "add", ".")
    git(root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "-m", "Fixture")
    return root


def invoke(root, *args):
    result = CliRunner().invoke(module.research, ["tree", *args, "--root", str(root)])
    assert result.exit_code == 0, result.output
    return result.output


def document(root, *args):
    return json.loads(invoke(root, *args, "--json"))


def walk(node):
    yield node
    for child in node["children"]:
        yield from walk(child)


def nodes(document, view):
    return list(walk(document["views"][view]["tree"]))


def test_inventory_changes_when_a_page_is_tracked_or_deleted(checkout):
    new = "content/Phase II/New.md"
    write(checkout, new, "---\ntitle: Newly tracked\n---\n")
    write(checkout, "content/ignored.secret", "private")
    write(checkout, "ignored/private.md", "private")
    assert new not in {node["path"] for node in nodes(document(checkout, "wiki"), "wiki")}
    git(checkout, "add", new)
    assert new in {node["path"] for node in nodes(document(checkout, "wiki"), "wiki")}
    (checkout / new).unlink()
    result = document(checkout, "wiki")
    assert new not in {node["path"] for node in nodes(result, "wiki")}
    assert result["skipped_entries"] == 1
    assert not any("private" in node["path"] or "secret" in node["path"] for node in nodes(result, "wiki"))


def test_untracked_is_explicit_and_keeps_tracked_data_inventory(checkout):
    write(checkout, "content/New.md", "---\ntitle: Optional page\n---\n")
    write(checkout, "content/ignored.secret", "secret")
    write(checkout, "ignored/private.md", "secret")
    for directory in ("data", "runs", "node_modules", ".venv", ".claude", ".tmp"):
        write(checkout, f"{directory}/never.md", "secret")
    result = document(checkout, "both", "--depth", "5", "--include-untracked")
    paths = {node["path"] for node in nodes(result, "repo")}
    assert "content/New.md" in paths
    assert "data/pins/manifest.json" in paths
    assert not any("never.md" in path or "secret" in path or "private.md" in path for path in paths)
    assert result["inventory_scope"] == "tracked-plus-untracked"


def test_titles_index_pages_and_actual_child_paths(checkout):
    result = document(checkout, "wiki")
    by_path = {node["path"]: node for node in nodes(result, "wiki")}
    assert by_path["content/index.md"]["title"] == "Research: map"
    assert by_path["content/Phase II/index.md"]["title"] == "Phase II's pages"
    assert by_path["content/Phase II/Reference/Topic.md"]["title"] == "Topic title"
    assert by_path["content/Phase II/Reference/Untitled.md"]["title"] == "Untitled"
    assert by_path["content/Phase II/Reference"]["kind"] == "directory"
    assert result["views"]["wiki"]["tree"]["file_count"] == 4
    text = invoke(checkout, "wiki")
    assert text.count("Phase II's pages") == 1
    assert "content/Phase II/index.md" not in text
    assert "Research: map\n└── Phase II's pages\n    └── Reference\n        ├── Topic title\n        └── Untitled" in text
    assert "Repeated heading" not in text
    assert "├──" in text and "└──" in text
    write(checkout, "content/Phase II/index.md", '---\ntitle: "Updated title"\n---\n')
    assert "└── Updated title\n    └── Reference" in invoke(checkout, "wiki")


def test_depth_and_repo_defaults_explain_hidden_files(checkout):
    default = document(checkout)
    assert default["views"]["wiki"]["depth"] == 4
    assert default["views"]["repo"]["depth"] == 2
    assert "README.md" in {node["path"] for node in nodes(default, "repo")}
    assert "src/avalanche_research/demo.py" not in {node["path"] for node in nodes(default, "repo")}
    assert sum(node["omitted_files"] for node in nodes(default, "repo")) > 0
    expanded = document(checkout, "repo", "--depth", "3")
    assert "src/avalanche_research/demo.py" in {node["path"] for node in nodes(expanded, "repo")}
    zero = document(checkout, "wiki", "--depth", "0")["views"]["wiki"]["tree"]
    assert zero["children"] == [] and zero["omitted_files"] == 3
    assert zero["file_count"] == 4
    assert "Research: map (3 files omitted)" in invoke(checkout, "wiki", "--depth", "0")
    assert "pins (1 file omitted)" in invoke(checkout, "repo", "--depth", "2")


def test_text_and_json_share_hierarchy_titles_counts_and_provenance(checkout):
    args = ("both", "--depth", "2")
    result = document(checkout, *args)
    text = invoke(checkout, *args)
    assert result["checkout"] == str(checkout)
    assert result["revision"] == git(checkout, "rev-parse", "HEAD").strip()
    assert result["revision"] in text and "Inventory: tracked;" in text
    assert "Research: map\n└── Phase II's pages\n    └── Reference (2 files omitted)" in text
    assert "├── data\n│   └── pins (1 file omitted)" in text
    for view in ("wiki", "repo"):
        for node in nodes(result, view):
            assert node["title"] in text
            if "/" in node["path"]:
                assert node["path"] not in text
            if node["omitted_files"]:
                count = node["omitted_files"]
                assert f"({count} {'file' if count == 1 else 'files'} omitted)" in text


@pytest.mark.parametrize("depth", [0, 1, 2, 4])
def test_every_inventory_file_is_visible_or_counted_as_hidden(checkout, depth):
    result = document(checkout, "both", "--depth", str(depth))
    for view in ("wiki", "repo"):
        visible = nodes(result, view)
        accounted = sum(node["kind"] in {"file", "page"} for node in visible)
        accounted += sum(node["omitted_files"] for node in visible)
        assert accounted == result["views"][view]["tree"]["file_count"]


def test_relocation_nested_cwd_and_package_checkout_discovery(checkout, tmp_path, monkeypatch):
    moved = tmp_path / "elsewhere" / "renamed-project"
    moved.parent.mkdir()
    shutil.move(checkout, moved)
    monkeypatch.chdir(moved / "src/avalanche_research")
    result = CliRunner().invoke(module.research, ["tree", "wiki", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["checkout"] == str(moved)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "__file__", str(moved / "src/avalanche_research/research.py"))
    result = CliRunner().invoke(module.research, ["tree", "wiki", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["checkout"] == str(moved)


@pytest.mark.parametrize("args", [("--depth", "-1"), ("--depth", "21"), ("--depth", "wrong"), ("unknown",)])
def test_invalid_depth_and_view_are_usage_errors(checkout, args):
    result = CliRunner().invoke(module.research, ["tree", *args, "--root", str(checkout)])
    assert result.exit_code == 2


def test_invalid_project_and_missing_git_have_helpful_errors(checkout, tmp_path, monkeypatch):
    result = CliRunner().invoke(module.research, ["tree", "--root", str(tmp_path)])
    assert result.exit_code == 1 and "Not an Avalanche research repository" in result.output
    def unavailable(*args, **kwargs):
        raise FileNotFoundError("git")
    monkeypatch.setattr(module.subprocess, "run", unavailable)
    result = CliRunner().invoke(module.research, ["tree", "--root", str(checkout)])
    assert result.exit_code == 1 and "requires Git" in result.output


def test_no_writes_and_no_symlink_escape(checkout, tmp_path):
    outside = write(tmp_path, "outside.md", "---\ntitle: Outside secret\n---\n")
    (checkout / "content/Escape.md").symlink_to(outside)
    (checkout / "content/EscapeDirectory").symlink_to(tmp_path, target_is_directory=True)
    git(checkout, "add", "content/Escape.md", "content/EscapeDirectory")
    def snapshot():
        return {str(path.relative_to(checkout)): (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
                for path in checkout.rglob("*") if path.is_file() and not path.is_symlink()}
    before = snapshot()
    result = document(checkout, "both", "--include-untracked", "--depth", "6")
    assert snapshot() == before
    assert "Outside secret" not in json.dumps(result)
    assert not any("Escape" in node["path"] for node in nodes(result, "repo"))
    assert result["skipped_entries"] == 2


def test_standalone_group_imports_no_model_data_or_figure_modules():
    code = """
import sys
from avalanche_research.research import research
assert not any(name.startswith(('avalanche_research.model', 'avalanche_research.catalog',
                               'avalanche_research.datasets', 'avalanche_research.views'))
               for name in sys.modules)
assert 'duckdb' not in sys.modules and 'pandas' not in sys.modules
"""
    result = subprocess.run([sys.executable, "-c", code], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
