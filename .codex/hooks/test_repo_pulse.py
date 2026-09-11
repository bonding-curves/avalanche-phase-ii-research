#!/usr/bin/env python3
"""Tests for the read-only repository pulse snapshot."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

import repo_pulse


def git(repo: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True)


class RepositoryPulseTests(unittest.TestCase):
    def create_repository(self, name: str = "repo") -> Path:
        root = Path(self.temporary_directory.name) / name
        root.mkdir()
        git(root, "init", "--quiet")
        git(root, "config", "user.name", "Repository Pulse Test")
        git(root, "config", "user.email", "repo-pulse@example.invalid")
        return root

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_unborn_repository_is_clean_and_explicit(self) -> None:
        root = self.create_repository()

        snapshot = repo_pulse.snapshot_repository(root)

        self.assertTrue(snapshot["clean"])
        self.assertIsNone(snapshot["branch"]["head"])
        self.assertEqual(snapshot["counts"], {"staged": 0, "modified": 0, "untracked": 0, "conflicts": 0})

    def test_exact_snapshot_preserves_staged_modified_and_special_paths(self) -> None:
        root = self.create_repository()
        tracked = root / "tracked.md"
        tracked.write_text("initial\n", encoding="utf-8")
        git(root, "add", "tracked.md")
        git(root, "commit", "--quiet", "-m", "test: establish fixture")
        tracked.write_text("staged\n", encoding="utf-8")
        git(root, "add", "tracked.md")
        tracked.write_text("unstaged\n", encoding="utf-8")
        special = root / "notes" / "résumé with space.md"
        special.parent.mkdir()
        special.write_text("evidence\n", encoding="utf-8")

        snapshot = repo_pulse.snapshot_repository(root, exact=True)

        self.assertFalse(snapshot["clean"])
        self.assertEqual(snapshot["counts"], {"staged": 1, "modified": 1, "untracked": 1, "conflicts": 0})
        self.assertEqual(
            [entry["path"] for entry in snapshot["entries"]],
            ["notes/résumé with space.md", "tracked.md"],
        )

    def test_quick_snapshot_collapses_an_untracked_directory(self) -> None:
        root = self.create_repository()
        nested = root / "many" / "nested"
        nested.mkdir(parents=True)
        (nested / "one.md").write_text("one\n", encoding="utf-8")
        (nested / "two.md").write_text("two\n", encoding="utf-8")

        snapshot = repo_pulse.snapshot_repository(root)

        self.assertEqual(snapshot["scan"], "quick")
        self.assertEqual(snapshot["counts"]["untracked"], 1)
        self.assertEqual(snapshot["entries"][0]["path"], "many/")

    def test_text_output_limits_paths_and_reports_omissions(self) -> None:
        root = self.create_repository()
        for index in range(3):
            (root / f"note-{index}.md").write_text("note\n", encoding="utf-8")
        snapshot = repo_pulse.snapshot_repository(root, exact=True)

        output = repo_pulse._render_text(
            {"schema_version": 1, "captured_at": "unused", "repositories": [snapshot]},
            max_paths=1,
        )

        self.assertEqual(output.count("  ?? "), 1)
        self.assertIn("... 2 more paths", output)

    def test_repeated_snapshot_has_a_stable_fingerprint(self) -> None:
        root = self.create_repository()

        first = repo_pulse.snapshot_repository(root)
        second = repo_pulse.snapshot_repository(root)

        self.assertEqual(first["fingerprint"], second["fingerprint"])

    def test_text_output_distinguishes_revision_and_pulse_fingerprint(self) -> None:
        root = self.create_repository()
        tracked = root / "tracked.md"
        tracked.write_text("initial\n", encoding="utf-8")
        git(root, "add", "tracked.md")
        git(root, "commit", "--quiet", "-m", "test: establish fixture")
        snapshot, failed = repo_pulse.build_snapshot([root])

        output = repo_pulse._render_text(snapshot)

        self.assertFalse(failed)
        self.assertIn(snapshot["repositories"][0]["branch"]["head"][:12], output)
        self.assertIn(f"pulse {snapshot['repositories'][0]['fingerprint'][:12]}", output)

    def test_invalid_repository_is_reported_without_hiding_valid_results(self) -> None:
        valid = self.create_repository("valid")
        invalid = Path(self.temporary_directory.name) / "not-a-repository"
        invalid.mkdir()

        snapshot, failed = repo_pulse.build_snapshot([valid, invalid])

        self.assertTrue(failed)
        self.assertNotIn("error", snapshot["repositories"][0])
        self.assertIn("error", snapshot["repositories"][1])


if __name__ == "__main__":
    unittest.main()
