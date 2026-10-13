"""The simulation queue's order, memory gate, nightly rule and resume. Runs under unittest, as the client check does."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim_queue

LOCAL = ZoneInfo("America/Los_Angeles")


def job(priority: str = "P1", workers: int = 2, per_worker: float = 2200.0, hours: float = 1.0, lane: str = "data-engineering") -> dict:
    return {"lane": lane, "priority": priority, "design": {"workers": workers, "runs": 10}, "per_worker_mib": per_worker,
            "expected_hours": hours}


class SimQueueTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)

    def test_a_job_without_its_measured_size_is_refused(self):
        with self.assertRaisesRegex(ValueError, "missing per_worker_mib"):
            sim_queue.check_job({k: v for k, v in job().items() if k != "per_worker_mib"})
        with self.assertRaisesRegex(ValueError, "priority"):
            sim_queue.check_job(job(priority="P9"))
        with self.assertRaisesRegex(ValueError, "workers"):
            sim_queue.check_job({**job(), "design": {"runs": 10}})

    def test_a_job_whose_measured_size_is_not_a_finite_number_is_refused(self):
        for key, value in (("per_worker_mib", "1600"), ("expected_hours", True), ("expected_hours", float("nan")),
                           ("per_worker_mib", float("inf"))):
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, "must be finite numbers"):
                sim_queue.check_job({**job(), key: value})

    def test_priority_comes_first_then_age(self):
        sim_queue.submit(job("P2"), self.root, datetime(2026, 10, 8, 12, tzinfo=UTC))
        late_p0 = sim_queue.submit(job("P0"), self.root, datetime(2026, 10, 8, 13, tzinfo=UTC))
        sim_queue.submit(job("P0"), self.root, datetime(2026, 10, 8, 14, tzinfo=UTC))
        self.assertEqual(sim_queue.next_job(self.root), late_p0)

    def test_a_job_left_running_is_resumed_before_any_waiting_job(self):
        sim_queue.submit(job("P0"), self.root)
        (self.root / "running" / "P2-old.json").write_text(json.dumps(job("P2")))
        self.assertEqual(sim_queue.next_job(self.root).name, "P2-old.json")

    def test_memory_gate_counts_workers_parent_reserve_and_the_nightly_run(self):
        eight = job(workers=8, per_worker=2300.0, hours=8.2)
        need = 8 * 2300 + sim_queue.PARENT_MIB + sim_queue.RESERVE_MIB
        morning = datetime(2026, 10, 14, 10, 0, tzinfo=LOCAL)
        self.assertEqual(sim_queue.need_mib(eight), need)
        self.assertTrue(sim_queue.fits(eight, need, morning))
        self.assertFalse(sim_queue.fits(eight, need - 1, morning))
        afternoon = datetime(2026, 10, 14, 13, 0, tzinfo=LOCAL)
        self.assertTrue(sim_queue.crosses_nightly(afternoon, 8.2))
        self.assertFalse(sim_queue.fits(eight, need, afternoon))
        self.assertTrue(sim_queue.fits(eight, need + sim_queue.NIGHTLY_MIB, afternoon))
        self.assertFalse(sim_queue.crosses_nightly(datetime(2026, 10, 14, 21, 0, tzinfo=LOCAL), 8.2))

    def test_alerts_fire_under_the_reserve_or_disk_floor_at_most_hourly(self):
        at = datetime(2026, 10, 8, 12, tzinfo=UTC)
        self.assertEqual(sim_queue.alerts(self.root, sim_queue.RESERVE_MIB + 1, 100.0, at), [])
        first = sim_queue.alerts(self.root, 1000.0, 10.0, at)
        self.assertEqual([row["kind"] for row in first], ["memory", "disk"])
        self.assertEqual(sim_queue.alerts(self.root, 1000.0, 10.0, at + timedelta(minutes=30)), [])
        self.assertEqual(len(sim_queue.alerts(self.root, 1000.0, 100.0, at + timedelta(hours=1))), 1)

    def bundle_job(self):
        bundle = self.root / "bundle"
        bundle.mkdir()
        design = {"workers": 1, "runs": 1}
        for stem, filename, body in (("rows", "nested/rows.json", b'[{"seed": 1}]'),
                                     ("draws", "draws.csv", b"x\n0.25\n")):
            source = bundle / filename
            source.parent.mkdir(exist_ok=True)
            source.write_bytes(body)
            design[f"{stem}_file"] = filename
            design[f"{stem}_sha256"] = hashlib.sha256(body).hexdigest()
        return {**job(workers=1), "design": design, "input_root": str(bundle)}

    def test_queued_design_stages_exact_inputs_from_another_directory(self):
        frozen = self.bundle_job()
        incoming = sim_queue.submit(frozen, self.root)
        clone = self.root / "different-clone"
        clone.mkdir()
        (clone / "draws.csv").write_bytes(b"wrong working-directory data")

        def consumer(command, **options):
            copied = Path(command[-2])
            design = json.loads(copied.read_text())
            for stem in ("rows", "draws"):
                data = (copied.parent / design[f"{stem}_file"]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), design[f"{stem}_sha256"])
            self.assertEqual(options["cwd"], clone)
            return __import__("subprocess").CompletedProcess(command, 0)

        with patch.object(sim_queue, "head_commit", return_value="abc"), patch.object(sim_queue.subprocess, "run", side_effect=consumer):
            self.assertTrue(sim_queue.run_one(incoming, self.root, clone))

    def test_missing_or_changed_bundle_inputs_fail_before_execution(self):
        for mode in ("missing", "changed", "unbound", "escape", "malformed"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                original_root, self.root = self.root, Path(temporary)
                try:
                    frozen = self.bundle_job()
                    source = Path(frozen["input_root"]) / frozen["design"]["draws_file"]
                    if mode == "missing":
                        source.unlink()
                    elif mode == "changed":
                        source.write_bytes(b"changed")
                    elif mode == "unbound":
                        frozen.pop("input_root")
                    elif mode == "escape":
                        frozen["design"]["draws_file"] = "../draws.csv"
                    else:
                        frozen["design"]["draws_file"] = 123
                    incoming = sim_queue.submit(frozen, self.root)
                    with patch.object(sim_queue, "head_commit", return_value="abc"), patch.object(sim_queue.subprocess, "run") as execute:
                        self.assertFalse(sim_queue.run_one(incoming, self.root, self.root))
                        execute.assert_not_called()
                    failed = json.loads(next((self.root / "failed").glob("*.json")).read_text())
                    self.assertFalse(failed["ok"])
                    self.assertIn("reason", failed)
                finally:
                    self.root = original_root

    def test_retry_keeps_frozen_inputs_and_refuses_staged_corruption(self):
        frozen = self.bundle_job()
        out = self.root / "relocated-output"
        out.mkdir()
        copied = sim_queue.stage_design(frozen, out)
        original = copied.read_bytes()
        before = (out / "draws.csv").stat().st_mtime_ns
        self.assertEqual(sim_queue.stage_design(frozen, out), copied)
        self.assertEqual(copied.read_bytes(), original)
        self.assertEqual((out / "draws.csv").stat().st_mtime_ns, before)
        (out / "draws.csv").write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "staged draws_file changed"):
            sim_queue.stage_design(frozen, out)
        (out / "draws.csv").write_bytes((Path(frozen["input_root"]) / "draws.csv").read_bytes())
        copied.write_text(json.dumps({**frozen["design"], "runs": 2}))
        with self.assertRaisesRegex(ValueError, "staged design differs"):
            sim_queue.stage_design(frozen, out)

    def test_staging_never_follows_a_predictable_temporary_symlink(self):
        frozen = self.bundle_job()
        out = self.root / "output"
        out.mkdir()
        canary = self.root / "canary"
        canary.write_bytes(b"keep")
        (out / "draws.csv.tmp").symlink_to(canary)
        sim_queue.stage_design(frozen, out)
        self.assertEqual(canary.read_bytes(), b"keep")
        self.assertFalse((out / "draws.csv").is_symlink())
        self.assertEqual((out / "draws.csv").read_bytes(), b"x\n0.25\n")

    def test_an_input_named_like_the_old_design_temporary_file_is_preserved(self):
        frozen = self.bundle_job()
        source = Path(frozen["input_root"]) / frozen["design"]["rows_file"]
        frozen["design"]["rows_file"] = "design-file.tmp"
        (Path(frozen["input_root"]) / "design-file.tmp").write_bytes(source.read_bytes())
        out = self.root / "output"
        out.mkdir()
        copied = sim_queue.stage_design(frozen, out)
        self.assertEqual(json.loads(copied.read_text()), frozen["design"])
        self.assertEqual((out / "design-file.tmp").read_bytes(), source.read_bytes())

    def test_completed_retry_uses_real_receipt_and_raw_row_checks_without_execution(self):
        try:
            import pandas as pd

            from avalanche_research.experiments import receipt
            from avalanche_research.model import runner
        except ImportError:
            self.skipTest("completed-row checks require the model environment")

        for damage in (None, "row", "receipt", "source", "design", "truncated", "null", "bad-code", "no-row-id"):
            with self.subTest(damage=damage), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                frozen = {**job(workers=1), "job_id": "completed", "design": {"workers": 1, "runs": 1, "rows": 1}}
                incoming = sim_queue.submit(frozen, root)
                clone = root / "clone"
                clone.mkdir()
                out = root / "out/completed"
                rows = out / "rows"
                rows.mkdir(parents=True)
                spec = {"model": "synthetic"}
                spec_hash = receipt.specification_hash(spec)
                frame = pd.DataFrame({"row_id": ["one"], "base_specification": [spec_hash], "value": [2**53 + 1]})
                parquet = runner._write(frame, rows)
                pin = clone / "pin.json"
                pin.write_text('{"schema_version": "avalanche-pins/v1", "name": "empty", "runs": []}')
                made = receipt.build_sweep(rows, [spec], "design-hash", 1, {"written": 1}, pin, [1], "start", "end",
                                           code={"commit": "abc", "dirty": False})
                made["sweep"]["design_file"] = frozen["design"]
                if damage == "source":
                    made["code"]["commit"] = "other"
                elif damage == "design":
                    made["sweep"]["design_file"] = {**frozen["design"], "runs": 2}
                made["receipt_id"] = receipt.sha256(receipt.canonical_bytes({k: v for k, v in made.items() if k != "receipt_id"}))[:16]
                receipt.write(made, rows / "receipt.json")
                (rows / "design.json").write_text(json.dumps({"row_ids": ["one"], "design_hash": "design-hash"}))
                if damage == "row":
                    parquet.write_bytes(parquet.read_bytes() + b"changed")
                elif damage == "receipt":
                    made["seeds"] = [2]
                    (rows / "receipt.json").write_text(json.dumps(made))
                elif damage == "truncated":
                    (rows / "receipt.json").write_text('{"receipt_id":')
                elif damage == "null":
                    (rows / "receipt.json").write_text('null')
                elif damage == "bad-code":
                    made["code"] = None
                    (rows / "receipt.json").write_text(json.dumps(made))
                elif damage == "no-row-id":
                    connection = __import__("duckdb").connect()
                    connection.register("frame", frame.drop(columns="row_id"))
                    connection.execute("COPY frame TO ? (FORMAT parquet)", [str(parquet)])
                    connection.close()
                    parquet.with_suffix(".sha256").write_text(hashlib.sha256(parquet.read_bytes()).hexdigest())
                    made["sweep"]["files"]["one"] = receipt.row_file_sha256(parquet)
                    made["output"]["sha256"] = receipt.sha256(receipt.canonical_bytes(made["sweep"]["files"]))
                    made["receipt_id"] = receipt.sha256(receipt.canonical_bytes({k: v for k, v in made.items() if k != "receipt_id"}))[:16]
                    self.assertEqual(receipt.check(made), [])
                    (rows / "receipt.json").write_text(json.dumps(made))
                before = (rows / "receipt.json").read_bytes()
                stamp = parquet.stat().st_mtime_ns
                with patch.object(sim_queue, "head_commit", return_value="abc"), patch.object(sim_queue.subprocess, "run") as execute:
                    self.assertEqual(sim_queue.run_one(incoming, root, clone), damage is None)
                    execute.assert_not_called()
                self.assertEqual((rows / "receipt.json").read_bytes(), before)
                self.assertEqual(parquet.stat().st_mtime_ns, stamp)
                archive = root / ("done" if damage is None else "failed") / incoming.name
                result = json.loads(archive.read_text())
                self.assertEqual(result.get("already_complete"), True if damage is None else None)
                if damage == "no-row-id":
                    self.assertEqual(result["verification_error_type"], "BinderException")


if __name__ == "__main__":
    unittest.main()
