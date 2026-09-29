"""Tests for rendered Quartz link validation."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "check_links", Path(__file__).resolve().parents[1] / "scripts" / "check_links.py"
)
assert SPEC and SPEC.loader
check_links = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_links)
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_links.py"


class CheckLinksTests(unittest.TestCase):
    def test_local_routes_and_fragments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            public = Path(directory)
            (public / "index.html").write_text(
                '<a href="/notes/#result">Good</a><a href="https://example.org">External</a>'
            )
            (public / "notes").mkdir()
            (public / "notes" / "index.html").write_text(
                '<h2 id="result">Result</h2><a href="../missing">Bad</a>'
                '<a href="#absent">Bad fragment</a>'
            )
            result = check_links.check(public)
            self.assertEqual(result["pages"], 2)
            self.assertEqual(result["local_links_checked"], 3)
            self.assertEqual(result["external_links_skipped"], 1)
            self.assertEqual(
                [item["reason"] for item in result["broken_links"]],
                ["missing target", "missing fragment"],
            )

    def test_relative_markdown_projection_path_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            public = Path(directory)
            (public / "index.html").write_text("<h1>Home</h1>")
            page = public / "Wiki" / "BCRG" / "Journal" / "weeks" / "2026-W37"
            page.mkdir(parents=True)
            (page / "index.html").write_text(
                '<a href="../../../requirements/2026-04/grant-proposal-v2.5">Proposal</a>'
            )
            result = check_links.check(public)
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["broken_links"][0]["reason"], "missing target")

    def test_dotted_page_name_resolves_without_losing_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            public = Path(directory)
            (public / "index.html").write_text('<a href="/proposal-v2.5">Proposal</a>')
            (public / "proposal-v2.5.html").write_text("<h1>Proposal</h1>")
            self.assertEqual(check_links.check(public)["status"], "pass")

    def test_groups_by_destination_and_attributes_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / "public"
            content = root / "content"
            (public / "Notes").mkdir(parents=True)
            (public / "index.html").write_text("<h1>Home</h1>")
            (content / "Notes").mkdir(parents=True)
            (content / "Notes" / "index.md").write_text("# Notes\n")
            (public / "Notes" / "index.html").write_text(
                '<body data-slug="Notes/index"><article><a href="/missing">One</a>'
                '<a href="../missing">Two</a><a href="/empty/">Empty index</a>'
                '<pre><code>&lt;a href="/example"&gt;</code></pre></article></body>'
            )
            (public / "empty").mkdir()
            result = check_links.check(public, content=content, site="test")
            self.assertEqual(result["site"], "test")
            self.assertEqual(result["affected_pages"], 1)
            self.assertEqual(result["failing_destinations"], 2)
            self.assertEqual(result["groups"][0]["destination"], "/missing")
            self.assertEqual(result["groups"][0]["occurrences"], 2)
            self.assertEqual(result["broken_links"][0]["source"], "Notes/index.md")
            self.assertEqual(result["broken_links"][2]["reason"], "missing index")
            self.assertEqual(result["build_sha256"], check_links.check(public)["build_sha256"])

    def test_incomplete_build_is_not_a_link_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "build is incomplete"):
                check_links.check(Path(directory))

    def test_baseline_rejects_replacement_failure_even_at_same_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            public = Path(directory)
            index = public / "index.html"
            index.write_text('<a href="/old">Old</a>')
            baseline = check_links.make_baseline(check_links.check(public, site="client"), "abc123")
            self.assertEqual(len(baseline["known"]), 1)
            self.assertEqual(
                check_links.compare_baseline(check_links.check(public, site="client"), baseline)["status"],
                "pass",
            )

            index.write_text('<a href="/new">New</a>')
            comparison = check_links.compare_baseline(check_links.check(public, site="client"), baseline)
            self.assertEqual(comparison["status"], "fail")
            self.assertEqual(comparison["new"], [["/", "/new", "missing target", 1]])
            self.assertEqual(comparison["resolved"], 1)

            index.write_text("<h1>Home</h1>")
            comparison = check_links.compare_baseline(check_links.check(public, site="client"), baseline)
            self.assertEqual(comparison["status"], "pass")
            self.assertEqual(comparison["resolved"], 1)
            with self.assertRaisesRegex(ValueError, "site does not match"):
                check_links.compare_baseline(check_links.check(public, site="bcrg"), baseline)

            index.write_text('<a href="/old">One</a><a href="/old">Two</a>')
            comparison = check_links.compare_baseline(check_links.check(public, site="client"), baseline)
            self.assertEqual(comparison["new"], [["/", "/old", "missing target", 1]])

    def test_cli_baseline_gate_checks_the_built_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            public = Path(directory) / "public"
            public.mkdir()
            index = public / "index.html"
            index.write_text('<a href="/known">Known</a>')
            baseline_path = Path(directory) / "baseline.json"
            baseline_path.write_text(json.dumps(
                check_links.make_baseline(check_links.check(public, site="client"), "abc123")
            ))
            command = [sys.executable, str(SCRIPT), str(public), "--site", "client", "--baseline", str(baseline_path)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            index.write_text('<a href="/new">New</a>')
            failed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(failed.returncode, 1)
            self.assertIn("NEW /: /new", failed.stdout)


if __name__ == "__main__":
    unittest.main()
