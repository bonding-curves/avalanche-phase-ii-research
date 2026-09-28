"""Tests for rendered Quartz link validation."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "check_links", Path(__file__).resolve().parents[1] / "scripts" / "check_links.py"
)
assert SPEC and SPEC.loader
check_links = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_links)


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


if __name__ == "__main__":
    unittest.main()
