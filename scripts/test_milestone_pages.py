import contextlib
import io
import json
import sys
from unittest.mock import patch
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

    def test_unchecked_run_is_reported_as_unchecked(self):
        unchecked = {"run": "unchecked-new", "build": {"completed_at": "2026-10-08T00:00:00Z", "summary": {"rows": 5}}, "capture": {}, "check": None}
        passed = {"run": "passed-new", "build": {"completed_at": "2026-10-08T00:00:00Z", "summary": {"rows": 9}}, "capture": {},
                  "check": {"status": "pass", "checked": ["a"], "findings": []}}
        manifest = milestone_pages.render(CATALOG, {"snowflake.primary-validator-stakes": unchecked}, as_of="2026-10-08")["manifest"]
        self.assertNotIn("Every built run passed", manifest)
        self.assertIn("1 of 2 datasets have a built run. 0 passed every check, and 1 has not been checked: `snowflake.primary-validator-stakes`.", manifest)
        self.assertIn("| `snowflake.primary-validator-stakes` | 5 | not dated | not checked | none | none |", manifest)
        both = {"snowflake.primary-validator-stakes": unchecked, "snowflake.primary-staking-rewards": passed}
        manifest = milestone_pages.render(CATALOG, both, as_of="2026-10-08")["manifest"]
        self.assertIn("2 of 2 datasets have a built run. 1 passed every check, and 1 has not been checked:", manifest)
        manifest = milestone_pages.render(CATALOG, {"snowflake.primary-staking-rewards": passed}, as_of="2026-10-08")["manifest"]
        self.assertIn("1 of 2 datasets have a built run. Every built run passed its checks.", manifest)

    def test_build_without_runs_refuses_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog, runs, content = root / "catalog.json", root / "runs", root / "content"
            catalog.write_text(json.dumps(CATALOG))
            runs.mkdir()
            argv = ["build", "--catalog", str(catalog), "--runs", str(runs), "--pins", str(root / "pins"), "--content", str(content), "--as-of", "2026-10-08"]
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(milestone_pages.main(argv), 1)
            self.assertIn("found 0 built runs", out.getvalue())
            self.assertIn("data/README.md", out.getvalue())
            self.assertFalse(content.exists())
            write_run(runs, "one-1", "snowflake.primary-staking-rewards", {"rows": 5}, {"status": "pass", "checked": ["a"], "findings": []})
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(milestone_pages.main(argv), 1)
            self.assertIn("found 1 built runs", out.getvalue())
            self.assertFalse(content.exists())

    def test_stale_names_pages_that_differ_from_a_fresh_render(self):
        with tempfile.TemporaryDirectory() as directory:
            pages = {name: Path(directory) / name / "index.md" for name in milestone_pages.PAGES}
            rendered = milestone_pages.render(CATALOG, {}, as_of="2026-10-08")
            for name, text in rendered.items():
                pages[name].parent.mkdir()
                pages[name].write_text(text)
            self.assertEqual(milestone_pages.stale(rendered, pages), [])
            self.assertEqual(milestone_pages.stated_as_of(pages), "2026-10-08")
            pages["manifest"].write_text(rendered["manifest"] + "\nedited by hand\n")
            self.assertEqual(len(milestone_pages.stale(rendered, pages)), 1)

    def test_instant_excludes_later_same_day_build_and_normalizes_offsets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, stamp in (("early-1", "2026-10-08T18:32:40Z"),
                                ("later-2", "2026-10-08T21:08:06Z")):
                write_run(root, name, "dataset", {"rows": 1}, None)
                path = root / name / "dataset/build.json"
                receipt = json.loads(path.read_text())
                receipt["completed_at"] = stamp
                path.write_text(json.dumps(receipt))
            for cutoff in ("2026-10-08T18:32:40Z", "2026-10-08T11:32:40-07:00"):
                self.assertEqual(milestone_pages.latest_runs(root, cutoff)["dataset"]["run"], "early-1")
            self.assertEqual(milestone_pages.latest_runs(root, "2026-10-08")["dataset"]["run"], "later-2")
            self.assertEqual(milestone_pages.latest_runs(root, "2026-10-08T18:32:39.999999Z"), {})
            with self.assertRaises(ValueError):
                milestone_pages.latest_runs(root, "2026-10-08T18:32:40")

    def test_pin_membership_uses_same_instant(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, stamp in (("before", "2026-10-08T18:32:40Z"), ("after", "2026-10-08T19:16:58Z")):
                (root / (name + ".json")).write_text(json.dumps({
                    "name": name, "pinned_at": stamp, "runs": [{"dataset_id": "dataset", "run": name}]}))
            self.assertEqual(milestone_pages.load_pins(root, "2026-10-08T18:32:40Z"), {"dataset": [("before", "before")]})
            self.assertEqual(len(milestone_pages.load_pins(root, "2026-10-08")["dataset"]), 2)

    def test_build_and_check_preserve_cutoff_after_later_run_and_pin_arrive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs, pins, content = root / "runs", root / "pins", root / "content"
            pins.mkdir()
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps(CATALOG))
            dataset = "snowflake.primary-staking-rewards"
            write_run(runs, "early-1", dataset, {"rows": 5}, None)
            stamp = runs / "early-1/dataset/build.json"
            data = json.loads(stamp.read_text()); data["completed_at"] = "2026-10-08T18:32:40Z"
            stamp.write_text(json.dumps(data))
            common = ["--catalog", str(catalog), "--runs", str(runs), "--pins", str(pins), "--content", str(content)]
            with patch.object(milestone_pages, "missing_quantities", return_value=[]), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(milestone_pages.main(["build", *common, "--as-of", "2026-10-08T18:32:40Z"]), 0)
                targets = {name: content / path.parent.name / path.name for name, path in milestone_pages.PAGES.items()}
                self.assertEqual(milestone_pages.stated_as_of(targets), "2026-10-08T18:32:40Z")
                original = {name: path.read_bytes() for name, path in targets.items()}
                write_run(runs, "later-2", dataset, {"rows": 999}, None)
                stamp = runs / "later-2/dataset/build.json"
                data = json.loads(stamp.read_text()); data["completed_at"] = "2026-10-08T21:08:06Z"
                stamp.write_text(json.dumps(data))
                (pins / "late.json").write_text(json.dumps({"name": "late", "pinned_at": "2026-10-08T19:16:58Z",
                                                           "runs": [{"dataset_id": dataset, "run": "early-1"}]}))
                self.assertEqual(milestone_pages.main(["check", *common]), 0)
                self.assertEqual(milestone_pages.main(["build", *common, "--as-of", "2026-10-08T18:32:40Z"]), 0)
                self.assertEqual({name: path.read_bytes() for name, path in targets.items()}, original)

    def test_default_render_records_exact_cutoff_and_missing_timezone_refuses(self):
        record = {"run": "early", "build": {"completed_at": "2026-10-08T18:32:40Z", "summary": {}}, "check": None, "capture": {}}
        rendered = milestone_pages.render(CATALOG, {"dataset": record})
        self.assertIn("build --as-of 2026-10-08T18:32:40Z", rendered["manifest"])
        self.assertIn("8 October 2026 at 18:32:40 UTC", rendered["manifest"])
        with self.assertRaises(ValueError):
            milestone_pages.as_of_value("2026-10-08T18:32:40")

    def test_frozen_selection_refuses_missing_or_malformed_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_run(root / "runs", "early-1", "dataset", {}, None)
            path = root / "runs/early-1/dataset/build.json"
            original = json.loads(path.read_text())
            pins = root / "pins"
            pins.mkdir()
            for stamp in (None, "not-a-date", "2026-10-08T18:32:40"):
                receipt = dict(original)
                if stamp is None:
                    receipt.pop("completed_at")
                else:
                    receipt["completed_at"] = stamp
                path.write_text(json.dumps(receipt))
                with self.subTest(build_timestamp=stamp), self.assertRaises(ValueError):
                    milestone_pages.latest_runs(root / "runs", "2026-10-08T18:32:40Z")
                pin = {"name": "legacy", "runs": [{"dataset_id": "dataset", "run": "early-1"}]}
                if stamp is not None:
                    pin["pinned_at"] = stamp
                (pins / "legacy.json").write_text(json.dumps(pin))
                with self.subTest(pin_timestamp=stamp), self.assertRaises(ValueError):
                    milestone_pages.load_pins(pins, "2026-10-08T18:32:40Z")

    def test_coverage_reads_date_pairs_and_capture_windows(self):
        self.assertEqual(milestone_pages.coverage({"first_date": "2021-02-01", "last_date": "2021-03-01"}), "2021-02-01 to 2021-03-01")
        self.assertEqual(milestone_pages.coverage({}, {"window": {"start": "2020-09-10", "end": "2026-10-08"}}), "2020-09-10 to 2026-10-08")
        self.assertEqual(milestone_pages.coverage({"observed_at": "2026-10-08T00:15:01Z"}), "snapshot 2026-10-08 00:15")
        self.assertEqual(milestone_pages.coverage({}), "not dated")


if __name__ == "__main__":
    unittest.main()
