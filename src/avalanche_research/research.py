"""Read-only orientation from the checkout's file inventory, without research data imports."""

from __future__ import annotations

import json
import os
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import click

_SKIP = {
    ".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".ipynb_checkpoints", ".claude",
    ".codex", ".playwright-mcp", ".tmp", "runs",
}


def _git(root: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True,
            timeout=10, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        ).stdout
    except (OSError, subprocess.SubprocessError) as error:
        raise click.ClickException(
            "Orientation requires Git and an accessible Git checkout. "
            "Use --root with the Avalanche repository."
        ) from error


def _is_project(root: Path) -> bool:
    try:
        if (root / "pyproject.toml").is_symlink():
            return False
        with (root / "pyproject.toml").open("rb") as source:
            project = tomllib.loads(source.read(65536).decode("utf-8"))
        return (
            project.get("project", {}).get("name") == "avalanche-phase-ii-research"
            and (root / "content").is_dir()
            and (root / "src/avalanche_research").is_dir()
            and (root / "content").resolve().is_relative_to(root)
            and (root / "src/avalanche_research").resolve().is_relative_to(root)
        )
    except (OSError, ValueError):
        return False


def _find_root(explicit: Path | None) -> Path:
    if explicit is not None:
        root = explicit.resolve()
        if not _is_project(root):
            raise click.ClickException(
                f"Not an Avalanche research repository: {root}. "
                "Expected pyproject.toml, content/, and src/avalanche_research/."
            )
        return root
    for start in (Path.cwd().resolve(), Path(__file__).resolve().parent):
        for candidate in (start, *start.parents):
            if _is_project(candidate):
                return candidate
    raise click.ClickException("Cannot find the Avalanche research repository. Use --root PATH.")


def _inventory(root: Path, include_untracked: bool) -> tuple[list[str], int]:
    exclusions = [f":(exclude,glob)**/{name}/**" for name in sorted(_SKIP)]
    raw = _git(root, "ls-files", "-z", "--cached", "--", ".", *exclusions)
    if include_untracked:
        # Git prunes excluded directories during untracked enumeration.
        raw += _git(root, "ls-files", "-z", "--others", "--exclude-standard", "--", ".",
                    *exclusions, ":(exclude,glob)data/**")
    names = set(raw.decode("utf-8", errors="surrogateescape").split("\0")) - {""}
    present = []
    skipped = 0
    for name in sorted(names):
        parts = PurePosixPath(name).parts
        if not parts or parts[0] == "/" or ".." in parts or any(part in _SKIP for part in parts):
            skipped += 1
            continue
        path = root
        for part in parts:
            path = path / part
            if path.is_symlink():
                break
        else:
            if path.is_file():
                present.append(name)
                continue
        skipped += 1
    return present, skipped


def _title(path: Path) -> str:
    """Read a simple scalar YAML title, never the page body or a YAML object."""
    try:
        with path.open("rb") as source:
            first = source.readline(65536).decode("utf-8-sig").rstrip("\r\n")
            if first.strip() != "---":
                return path.stem
            lines = [first]
            remaining = 65536 - len(first.encode("utf-8"))
            while remaining > 0:
                raw = source.readline(remaining)
                if not raw:
                    break
                remaining -= len(raw)
                line = raw.decode("utf-8").rstrip("\r\n")
                lines.append(line)
                if line.strip() in {"---", "..."}:
                    break
    except (OSError, UnicodeError):
        return path.stem
    for line in lines[1:]:
        if line.strip() in {"---", "..."}:
            break
        if not line.startswith("title:"):
            continue
        value = line[6:].strip()
        if value.startswith('"'):
            try:
                decoded, _ = json.JSONDecoder().raw_decode(value)
                if isinstance(decoded, str):
                    return " ".join(decoded.split()) or path.stem
            except ValueError:
                pass
        elif value.startswith("'"):
            # YAML single quotes escape a quote by doubling it.
            index = 1
            result = ""
            while index < len(value):
                if value[index:index + 2] == "''":
                    result += "'"
                    index += 2
                elif value[index] == "'":
                    return " ".join(result.split()) or path.stem
                else:
                    result += value[index]
                    index += 1
        elif value and value[0] not in "|>![{&*":
            return value.split(" #", 1)[0].strip() or path.stem
        return path.stem
    return path.stem


@dataclass
class _Node:
    path: str
    title: str
    kind: str = "directory"
    children: dict[str, _Node] = field(default_factory=dict)

    @property
    def file_count(self) -> int:
        return int(self.kind in {"page", "file"}) + sum(child.file_count for child in self.children.values())


def _build(root: Path, paths: list[str], wiki: bool) -> _Node:
    tree = _Node("content" if wiki else ".", "Wiki" if wiki else "Repository")
    for name in paths:
        parts = PurePosixPath(name).parts
        if wiki:
            if parts[0] != "content" or not name.lower().endswith(".md"):
                continue
            parts = parts[1:]
        node = tree
        for index, part in enumerate(parts[:-1]):
            directory = "/".join(("content", *parts[:index + 1]) if wiki else parts[:index + 1])
            node = node.children.setdefault(part, _Node(directory, part))
        if wiki and parts[-1].lower() == "index.md":
            node.path = name
            title = _title(root / name)
            node.title = title if title != "index" else node.title
            node.kind = "page"
        else:
            node.children[parts[-1]] = _Node(name, _title(root / name) if wiki else parts[-1],
                                            "page" if wiki else "file")
    return tree


def _visible(node: _Node, depth: int, *, nested_files: bool, level: int = 0) -> dict:
    children = []
    omitted = 0
    for child in sorted(node.children.values(), key=lambda item: (item.kind == "file", item.path.casefold(), item.path)):
        if level >= depth or (not nested_files and level > 0 and child.kind == "file"):
            omitted += child.file_count
        else:
            children.append(_visible(child, depth, nested_files=nested_files, level=level + 1))
    return {
        "path": node.path, "title": node.title, "kind": node.kind,
        "file_count": node.file_count, "omitted_files": omitted, "children": children,
    }


def _label(node: dict) -> str:
    label = node["title"]
    omitted = node["omitted_files"]
    if omitted:
        label += f" ({omitted} {'file' if omitted == 1 else 'files'} omitted)"
    return label


def _lines(node: dict, prefix: str = "", *, root: bool = True, last: bool = True):
    yield prefix + ("" if root else "└── " if last else "├── ") + _label(node)
    child_prefix = prefix + ("" if root else "    " if last else "│   ")
    for index, child in enumerate(node["children"]):
        yield from _lines(child, child_prefix, root=False, last=index == len(node["children"]) - 1)


@click.group()
def research() -> None:
    """Orient in the wiki and source checkout without loading research data."""


@research.command("tree")
@click.argument("view", type=click.Choice(["wiki", "repo", "both"]), default="both")
@click.option("--root", type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Avalanche repository root. Default: discover from cwd, then package checkout.")
@click.option("--depth", type=click.IntRange(0, 20),
              help="Edges below the root (0: root only). Defaults: wiki 4, repo 2; explicit depth shows nested files.")
@click.option("--include-untracked", is_flag=True,
              help="Also inventory nonignored untracked files, excluding data, runtime and private cache directories.")
@click.option("--json", "as_json", is_flag=True, help="Emit the same bounded tree as JSON with checkout provenance.")
def tree(view: str, root: Path | None, depth: int | None, include_untracked: bool, as_json: bool) -> None:
    """Print tracked wiki pages, repository structure, or both (the default).

    Titles are simple frontmatter scalars. Nodes describe files, not delivery status.
    Missing files and symlinks are excluded. No data contents or network are read.
    """
    root = _find_root(root)
    git_root = Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
    if git_root != root:
        raise click.ClickException("The Avalanche project must be the Git checkout root. Use --root PATH.")
    paths, skipped = _inventory(root, include_untracked)
    revision = os.fsdecode(_git(root, "rev-parse", "--verify", "HEAD")).strip()
    views = {}
    for name in (["wiki", "repo"] if view == "both" else [view]):
        limit = depth if depth is not None else 4 if name == "wiki" else 2
        views[name] = {"depth": limit, "tree": _visible(_build(root, paths, name == "wiki"), limit,
                                                       nested_files=name == "wiki" or depth is not None)}
    result = {
        "schema_version": "avalanche-research-tree/v1",
        "checkout": str(root), "revision": revision,
        "inventory_scope": "tracked-plus-untracked" if include_untracked else "tracked",
        "source": "Git index paths; existing working-tree files and current frontmatter",
        "excluded": "missing files, symlinks, runtime and private cache directories",
        "skipped_entries": skipped, "inventory_files": len(paths), "views": views,
    }
    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        click.echo(f"Checkout: {root}\nHEAD: {revision}\nInventory: {result['inventory_scope']}; {result['source']}")
        click.echo(f"Excluded: {result['excluded']} ({skipped} additional entries skipped)")
        for name, item in views.items():
            click.echo(f"\n{name.upper()} (depth {item['depth']}; {item['tree']['file_count']} files)")
            click.echo("\n".join(_lines(item["tree"])))
