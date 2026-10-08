import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import milestone_pages

CATALOG = {
    "sources": [
        {"id": "src", "name": "Test source", "source_type": "rest_api", "authority": "Test source | pipes", "authentication": "none", "endpoints": [{"id": "e1", "url": "https://x.test/a?b=1", "response_fields": ["r"]}]},
        {"id": "share", "name": "Share", "source_type": "database_share", "authority": "Share", "authentication": "key", "queries": [{"id": "q1", "sql": "queries/q1.sql"}]},
    ],
    "datasets": [
        {"id": "snowflake.primary-staking-rewards", "source_id": "src", "endpoint_ids": ["e1"], "fields": [{"name": "a"}], "contract_quantities": ["rewards"], "studies": ["Study A"], "name": "Rewards"},
        {"id": "snowflake.primary-validator-stakes", "source_id": "share", "query_ids": ["q1"], "fields": [{"name": "a"}, {"name": "b"}], "contract_quantities": ["validator flows", "durations"], "studies": ["Study A", "Study B"], "name": "Validator stakes"},
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
            write_run(runs, "one-1", "snowflake.primary-staking-rewards", {"rows": 5, "observed_from": "2021-01-01", "observed_to": "2021-01-05", "skipped_dates": 2}, {"status": "attention", "checked": ["a", "b"], "findings": ["1 rows follow a gap"]})
            write_run(runs, "one-2", "snowflake.primary-staking-rewards", {"rows": 9, "observed_from": "2021-01-01", "observed_to": "2021-01-09", "skipped_dates": 0}, {"status": "pass", "checked": ["a", "b"], "findings": []})
            latest = milestone_pages.latest_runs(runs)
            self.assertEqual(latest["snowflake.primary-staking-rewards"]["run"], "one-2")
            self.assertEqual(milestone_pages.latest_runs(runs, as_of="2026-09-18"), {})
            pins = {"snowflake.primary-staking-rewards": [("p1-test", "one-2")]}
            pages = milestone_pages.render(CATALOG, latest, pins)
            row = milestone_pages.PRIMARY["Rewards"][1]
            self.assertIn(f"| Rewards | `snowflake.primary-staking-rewards` | {row} | 2021-01-01 to 2021-01-09 | 9 | all 2 passed |", pages["ingestion"])
            self.assertIn("| Validator flows | `snowflake.primary-validator-stakes` |", pages["ingestion"])
            self.assertIn("| no built run | not counted | not checked |", pages["ingestion"])
            self.assertIn("built on or before 19 September 2026", pages["ingestion"])
            self.assertIn("`queries/q1.sql`", pages["manifest"])
            self.assertIn("Test source \\| pipes", pages["manifest"])
            self.assertIn("| `snowflake.primary-validator-stakes` | no built run |", pages["manifest"])
            self.assertIn("`p1-test` (one-2, this run)", pages["manifest"])
            self.assertIn("| `snowflake.primary-staking-rewards` | 9 | 2021-01-01 to 2021-01-09 | all 2 passed | none | none |", pages["manifest"])
            targets = {name: content / name / path.name for name, path in milestone_pages.PAGES.items()}
            for name, text in pages.items():
                targets[name].parent.mkdir(parents=True)
                targets[name].write_text(text)
            self.assertEqual(milestone_pages.validate(CATALOG, targets), [])
            targets["manifest"].write_text("# Hand written\n")
            problems = milestone_pages.validate(CATALOG, targets)
            self.assertTrue(any("generated marker" in problem for problem in problems))

    def test_counts_and_check_text(self):
        record = {"build": {"summary": {"rows": 3, "rows_without_staked_utxo": 2, "skipped_dates": 0}}, "check": {"findings": ["1 rows repeat a hash"], "checked": ["x"], "status": "attention"}, "capture": {}, "run": "r"}
        self.assertEqual(milestone_pages.build_counts(record), ["rows without a staked output: 2"])
        self.assertEqual(milestone_pages.checks(record), "1 finding from 1 checks")

    def test_command_result_checks_are_read_from_their_validation(self):
        nested = {"status": "pass", "findings": [], "validation": {"checked": ["a", "b", "c"], "findings": [], "status": "pass", "summary": {}}}
        record = {"build": {"summary": {}}, "check": milestone_pages.flat_check(nested), "capture": {}, "run": "r"}
        self.assertEqual(milestone_pages.checks(record), "all 3 passed")

    def test_coverage_reads_date_pairs_and_capture_windows(self):
        self.assertEqual(milestone_pages.coverage({"first_date": "2021-02-01", "last_date": "2021-03-01"}), "2021-02-01 to 2021-03-01")
        self.assertEqual(milestone_pages.coverage({}, {"window": {"start": "2020-09-10", "end": "2026-10-08"}}), "2020-09-10 to 2026-10-08")
        self.assertEqual(milestone_pages.coverage({"observed_at": "2026-10-08T00:15:01Z"}), "snapshot 2026-10-08 00:15")
        self.assertEqual(milestone_pages.coverage({}), "not dated")


if __name__ == "__main__":
    unittest.main()
