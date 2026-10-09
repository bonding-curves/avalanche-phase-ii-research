"""The simulation queue's order, memory gate, nightly rule and resume. Runs under unittest, as the client check does."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
