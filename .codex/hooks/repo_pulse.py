#!/usr/bin/env python3
"""Create a deterministic, read-only snapshot of one or more Git repositories."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Sequence


SCHEMA_VERSION = 1


class SnapshotError(RuntimeError):
    """A repository could not be inspected safely."""


def _decode(value: bytes) -> str:
    return value.decode("utf-8", errors="surrogateescape")


def _run_git(repo: Path, *arguments: str) -> bytes:
    command = ["git", "--no-optional-locks", "-C", os.fspath(repo), *arguments]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as error:
        raise SnapshotError("Git is not installed or is not available on PATH.") from error

    if result.returncode != 0:
        message = _decode(result.stderr).strip() or "Git returned a non-zero status."
        raise SnapshotError(message)
    return result.stdout


def _repository_root(repo: Path) -> Path:
    output = _run_git(repo, "rev-parse", "--show-toplevel")
    return Path(_decode(output).strip()).resolve()


def _status_arguments(exact: bool) -> list[str]:
    untracked_mode = "all" if exact else "normal"
    return [
        "status",
        "--porcelain=v2",
        "--branch",
        "--show-stash",
        "-z",
        f"--untracked-files={untracked_mode}",
    ]


def _parse_header(record: str, branch: dict[str, Any]) -> None:
    key, _, value = record[2:].partition(" ")
    if key == "branch.oid":
        branch["head"] = None if value == "(initial)" else value
    elif key == "branch.head":
        branch["name"] = None if value == "(detached)" else value
        branch["detached"] = value == "(detached)"
    elif key == "branch.upstream":
        branch["upstream"] = value
    elif key == "branch.ab":
        ahead, behind = value.split(" ", maxsplit=1)
        branch["ahead"] = int(ahead.removeprefix("+"))
        branch["behind"] = int(behind.removeprefix("-"))
    elif key == "stash":
        branch["stash_count"] = int(value)


def _tracked_entry(record: str, kind: str) -> dict[str, Any]:
    maxsplit = 8 if kind == "ordinary" else 9
    fields = record.split(" ", maxsplit=maxsplit)
    path_index = 8 if kind == "ordinary" else 9
    if len(fields) <= path_index:
        raise SnapshotError(f"Malformed Git status {kind} record.")
    return {
        "kind": kind,
        "path": fields[path_index],
        "index": fields[1][0],
        "worktree": fields[1][1],
    }


def _parse_status(output: bytes) -> dict[str, Any]:
    records = [_decode(record) for record in output.split(b"\0") if record]
    branch: dict[str, Any] = {
        "head": None,
        "name": None,
        "detached": False,
        "upstream": None,
        "ahead": None,
        "behind": None,
        "stash_count": 0,
    }
    entries: list[dict[str, Any]] = []
    index = 0

    while index < len(records):
        record = records[index]
        if record.startswith("# "):
            _parse_header(record, branch)
        elif record.startswith("1 "):
            entries.append(_tracked_entry(record, "ordinary"))
        elif record.startswith("2 "):
            entry = _tracked_entry(record, "renamed")
            index += 1
            if index >= len(records):
                raise SnapshotError("Malformed Git status rename record.")
            entry["original_path"] = records[index]
            entries.append(entry)
        elif record.startswith("u "):
            fields = record.split(" ", maxsplit=10)
            if len(fields) <= 10:
                raise SnapshotError("Malformed Git status conflict record.")
            entries.append(
                {
                    "kind": "conflict",
                    "path": fields[10],
                    "index": fields[1][0],
                    "worktree": fields[1][1],
                }
            )
        elif record.startswith("? "):
            entries.append(
                {"kind": "untracked", "path": record[2:], "index": "?", "worktree": "?"}
            )
        elif not record.startswith("! "):
            raise SnapshotError("Git status returned an unsupported record type.")
        index += 1

    entries.sort(key=lambda item: (item["path"], item["kind"]))
    counts = {
        "staged": sum(
            entry["kind"] != "conflict" and entry["index"] not in {".", "?"}
            for entry in entries
        ),
        "modified": sum(
            entry["kind"] != "conflict" and entry["worktree"] not in {".", "?"}
            for entry in entries
        ),
        "untracked": sum(entry["kind"] == "untracked" for entry in entries),
        "conflicts": sum(entry["kind"] == "conflict" for entry in entries),
    }
    return {
        "branch": branch,
        "clean": not entries,
        "counts": counts,
        "entries": entries,
    }


def snapshot_repository(repo: Path, exact: bool = False) -> dict[str, Any]:
    started = time.monotonic()
    root = _repository_root(repo)
    status = _parse_status(_run_git(root, *_status_arguments(exact)))
    result = {
        "repository": root.name,
        "scan": "exact" if exact else "quick",
        **status,
    }
    canonical = json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    result["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    result["duration_ms"] = round((time.monotonic() - started) * 1000, 3)
    return result


def build_snapshot(repositories: Sequence[Path], exact: bool = False) -> tuple[dict[str, Any], bool]:
    results: list[dict[str, Any]] = []
    failed = False
    names: set[str] = set()

    for repo in repositories:
        try:
            result = snapshot_repository(repo, exact=exact)
            if result["repository"] in names:
                raise SnapshotError(
                    f"Repository label {result['repository']!r} is ambiguous; inspect repositories separately."
                )
            names.add(result["repository"])
        except SnapshotError as error:
            failed = True
            result = {
                "repository": repo.name or ".",
                "scan": "exact" if exact else "quick",
                "error": str(error),
            }
        results.append(result)

    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "repositories": results,
    }
    return snapshot, failed


def _render_text(snapshot: dict[str, Any], max_paths: int = 20) -> str:
    lines: list[str] = []
    for repo in snapshot["repositories"]:
        name = repo["repository"]
        if "error" in repo:
            lines.append(f"{name}: ERROR: {repo['error']}")
            continue
        branch = repo["branch"]
        branch_name = branch["name"] or ("detached" if branch["head"] else "unborn")
        head = branch["head"][:12] if branch["head"] else "unborn"
        counts = repo["counts"]
        lines.append(
            f"{name}: {branch_name}@{head} | pulse {repo['fingerprint'][:12]} | "
            f"staged {counts['staged']}, modified {counts['modified']}, "
            f"untracked {counts['untracked']}, conflicts {counts['conflicts']}"
        )
        if branch["upstream"]:
            lines.append(
                f"  upstream {branch['upstream']} | ahead {branch['ahead']}, "
                f"behind {branch['behind']}, stashes {branch['stash_count']}"
            )
        for entry in repo["entries"][:max_paths]:
            state = "??" if entry["kind"] == "untracked" else entry["index"] + entry["worktree"]
            path = json.dumps(entry["path"], ensure_ascii=False)
            lines.append(f"  {state} {path}")
        omitted = len(repo["entries"]) - max_paths
        if omitted > 0:
            lines.append(
                f"  ... {omitted} more paths; use --max-paths or --format json only when needed"
            )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        action="append",
        type=Path,
        dest="repositories",
        help="repository to inspect; repeat for multiple repositories (default: current directory)",
    )
    parser.add_argument(
        "--exact",
        action="store_true",
        help="enumerate every untracked file; the default quick scan collapses untracked directories",
    )
    parser.add_argument(
        "--max-paths",
        type=int,
        default=20,
        help="maximum paths per repository in text output (default: 20)",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    if arguments.max_paths < 0:
        parser.error("--max-paths must be zero or greater")
    repositories = arguments.repositories or [Path.cwd()]
    snapshot, failed = build_snapshot(repositories, exact=arguments.exact)
    if arguments.format == "json":
        print(json.dumps(snapshot, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(_render_text(snapshot, max_paths=arguments.max_paths))
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
