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

    def test_rejects_unknown_deliverable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            _, problems = self.render(PAGE.replace('["1.3"]', '["9.9"]'), Path(temporary))
            self.assertIn("unknown deliverable 9.9", problems)

    def topic_problems(self, tags_line: str) -> list[str]:
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            page = Path(temporary) / "memo.md"
            page.write_text(f"---\ntitle: A memo\n{tags_line}\n---\n\nText.\n")
            return overview_tables.topic_problems(page)

    def test_topics_are_checked_on_any_page(self):
        self.assertEqual(self.topic_problems('tags: ["security-budget"]'), [])
        self.assertIn("unknown topic astrology", self.topic_problems('tags: ["astrology"]'))
        self.assertTrue(self.topic_problems("tags:\n  - security-budget")[0].startswith("tags must be an inline list"))
        five = '", "'.join(list(overview_tables.TOPICS)[:5])
        self.assertIn("5 topics, a page carries one to four", self.topic_problems(f'tags: ["{five}"]'))

    def test_routes_and_page_types(self):
        content = overview_tables.CONTENT
        memo = content / "Phase II" / "Wiki" / "Memos" / "drafts" / "2026-09-29-x" / "index.md"
        paper = content / "Phase II" / "Wiki" / "Collections" / "Supplementary Research Papers" / "1987 Bus Engines.md"
        deliverable = content / "Phase II" / "Milestones" / "Milestone 1" / "1-3 Staking Model Spec" / "index.md"
        self.assertEqual(overview_tables.route(memo), "/Phase-II/Wiki/Memos/drafts/2026-09-29-x/")
        self.assertEqual(overview_tables.route(paper), "/Phase-II/Wiki/Collections/Supplementary-Research-Papers/1987-Bus-Engines")
        self.assertEqual(overview_tables.page_type(memo), "Memos")
        self.assertEqual(overview_tables.page_type(paper), "Research papers")
        self.assertEqual(overview_tables.page_type(deliverable), "Deliverables")
        self.assertEqual(overview_tables.page_type(content / "Phase II" / "Milestones" / "Milestone 0" / "Proposal" / "index.md"), "Contract")

    def test_topic_page_groups_pages_by_type(self):
        content = overview_tables.CONTENT
        memo = content / "Phase II" / "Wiki" / "Memos" / "m" / "index.md"
        paper = content / "Phase II" / "Wiki" / "Collections" / "Supplementary Research Papers" / "p.md"
        text = overview_tables.topic_page("security-budget", [
            ("Research papers", paper, {"title": "A | paper", "authors": ["Tarun Chitra"], "published": "2020-11-30", "description": "Why."}),
            ("Memos", memo, {"title": "A memo", "date": "2026-09-29", "description": "What."}),
        ])
        self.assertLess(text.index("## Memos"), text.index("## Research papers"))
        self.assertIn("| [A \\| paper](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/p) | Tarun Chitra | November 30, 2020 | Why. |", text)
        self.assertIn("| [A memo](/Phase-II/Wiki/Memos/m/) | BCRG | September 29, 2026 | What. |", text)
        self.assertEqual(overview_tables.page_authors({"authors": ["A", "B", "C", "D"]}, "Research papers"), "A et al.")
        self.assertIn("see validator economics", text)

    def test_partial_dates(self):
        self.assertEqual(overview_tables.published("2020-11"), "November 2020")
        self.assertEqual(overview_tables.published("1973"), "1973")


if __name__ == "__main__":
    unittest.main()
