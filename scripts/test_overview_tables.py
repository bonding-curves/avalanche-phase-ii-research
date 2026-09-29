import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent / "overview_tables.py"
SPEC = importlib.util.spec_from_file_location("overview_tables", MODULE_PATH)
assert SPEC and SPEC.loader
overview_tables = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(overview_tables)

PAGE = """---
title: "A paper"
authors: ["Ada Lovelace", "Charles Babbage"]
published: 2020-11-30
venue: "*A Journal*"
url: "https://doi.org/10.1/x"
tags: ["security-budget"]
key_terms: ["commitment", "phase transition"]
deliverables: ["1.3"]
---

One sentence.

Background.
"""
ROUTES = {"1.3": "/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/"}


class OverviewTableTest(unittest.TestCase):
    def render(self, text: str, tmp: Path) -> tuple[str, list[str]]:
        page = tmp / "page.md"
        page.write_text(text)
        return overview_tables.render(page, ROUTES, {"commitment"})

    def test_table_sits_under_the_first_paragraph_and_is_stable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            text, problems = self.render(PAGE, Path(temporary))
            self.assertEqual(problems, [])
            self.assertLess(text.index("One sentence."), text.index(overview_tables.START))
            self.assertLess(text.index(overview_tables.END), text.index("Background."))
            self.assertIn("| **Published** | November 30, 2020 |", text)
            self.assertIn("[commitment](/Phase-II/Wiki/Reference/Glossary-and-Notation), phase transition", text)
            self.assertIn("[security budget](/tags/security-budget)", text)
            again, _ = self.render(text, Path(temporary))
            self.assertEqual(again, text)

    def test_rejects_unknown_topic_and_deliverable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            bad = PAGE.replace('["security-budget"]', '["astrology"]').replace('["1.3"]', '["9.9"]')
            _, problems = self.render(bad, Path(temporary))
            self.assertIn("unknown topic astrology", problems)
            self.assertIn("unknown deliverable 9.9", problems)

    def test_partial_dates(self):
        self.assertEqual(overview_tables.published("2020-11"), "November 2020")
        self.assertEqual(overview_tables.published("1973"), "1973")


if __name__ == "__main__":
    unittest.main()
