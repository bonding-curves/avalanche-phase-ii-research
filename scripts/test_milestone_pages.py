import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import milestone_pages


CATALOG = {
    "sources": [
        {"id": "src", "authority": "Test source | pipes", "authentication": "none", "endpoints": [{"id": "e1", "url": "https://x.test/a?b=1", "response_fields": ["r"]}]},
        {"id": "share", "authority": "Share", "authentication": "key", "queries": [{"id": "q1", "sql": "queries/q1.sql"}]},
    ],
    "datasets": [
        {"id": "src.one", "source_id": "src", "endpoint_ids": ["e1"], "fields": [{"name": "a"}], "contract_quantities": ["rewards"], "studies": ["Study A"]},
        {"id": "share.two", "source_id": "share", "query_ids": ["q1"], "fields": [{"name": "a"}, {"name": "b"}], "contract_quantities": ["validator flows", "durations"], "studies": ["Study A", "Study B"]},
    ],
}


def write_run(root: Path, name: str, dataset_id: str, summary: dict, check: dict | None) -> None:
    (root / name / "capture").mkdir(parents=True), (root / name / "dataset").mkdir(parents=True)
    capture_id = f"capture:test:{name}"
    (root / name / "capture" / "capture.json").write_text(json.dumps({"capture_id": capture_id, "dataset_id": dataset_id, "completed_at": "2026-09-19T10:00:00Z", "responses": [{"sha256": "a" * 64}]}))
    (root / name / "dataset" / "build.json").write_text(json.dumps({"dataset_id": dataset_id, "source_capture_id": capture_id, "completed_at": f"2026-09-19T10:0{name[-1]}:00Z", "summary": summary}))
    if check is not None:
        (root / name / "dataset" / "check.json").write_text(json.dumps(check))


class MilestonePagesTest(unittest.TestCase):
    def test_build_renders_latest_runs_and_check_validates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs, content = root / "runs", root / "content"
            write_run(runs, "one-1", "src.one", {"rows": 5, "observed_from": "2021-01-01", "observed_to": "2021-01-05", "skipped_dates": 2}, {"status": "attention", "checked": ["a", "b"], "findings": ["1 rows follow a gap"]})
            write_run(runs, "one-2", "src.one", {"rows": 9, "observed_from": "2021-01-01", "observed_to": "2021-01-09", "skipped_dates": 0}, {"status": "pass", "checked": ["a", "b"], "findings": []})
            latest = milestone_pages.latest_runs(runs)
            self.assertEqual(latest["src.one"]["run"], "one-2")
            pages = milestone_pages.render(CATALOG, latest)
            self.assertIn("| rewards | `src.one` | 2021-01-01 to 2021-01-09 | 9 | pass, 2 checks, 0 findings |", pages["ingestion"])
            self.assertIn("| validator flows | `share.two` | n/a | n/a | not checked |", pages["ingestion"])
            self.assertIn("`queries/q1.sql`", pages["manifest"])
            self.assertIn("Test source \\| pipes", pages["manifest"])
            self.assertIn("| `share.two` | no built run |", pages["manifest"])
            content.mkdir()
            for name, text in pages.items():
                (content / milestone_pages.PAGES[name].name).write_text(text)
            targets = {name: content / path.name for name, path in milestone_pages.PAGES.items()}
            self.assertEqual(milestone_pages.validate(CATALOG, targets), [])
            targets["manifest"].write_text("# Hand written\n")
            problems = milestone_pages.validate(CATALOG, targets)
            self.assertTrue(any("generated marker" in problem for problem in problems))

    def test_gap_text_reports_findings_and_gap_counts(self):
        record = {"build": {"summary": {"rows": 3, "rows_without_staked_utxo": 2, "skipped_dates": 0}}, "check": {"findings": ["1 rows repeat a hash"], "checked": ["x"], "status": "attention"}, "capture": {}, "run": "r"}
        self.assertEqual(milestone_pages.gaps(record), "1 rows repeat a hash; rows without staked utxo: 2")
        self.assertEqual(milestone_pages.gaps(None), "no built run")


if __name__ == "__main__":
    unittest.main()
