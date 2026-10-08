"""The simulation queue's order, memory gate, nightly rule and resume."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim_queue

LOCAL = ZoneInfo("America/Los_Angeles")


def job(priority: str = "P1", workers: int = 2, per_worker: float = 2200.0, hours: float = 1.0, lane: str = "data-engineering") -> dict:
    return {"lane": lane, "priority": priority, "design": {"workers": workers, "runs": 10}, "per_worker_mib": per_worker,
            "expected_hours": hours}


def test_a_job_without_its_measured_size_is_refused():
    with pytest.raises(ValueError, match="missing per_worker_mib"):
        sim_queue.check_job({k: v for k, v in job().items() if k != "per_worker_mib"})
    with pytest.raises(ValueError, match="priority"):
        sim_queue.check_job(job(priority="P9"))
    with pytest.raises(ValueError, match="workers"):
        sim_queue.check_job({**job(), "design": {"runs": 10}})


def test_priority_comes_first_then_age(tmp_path):
    sim_queue.submit(job("P2"), tmp_path, datetime(2026, 10, 8, 12, tzinfo=UTC))
    late_p0 = sim_queue.submit(job("P0"), tmp_path, datetime(2026, 10, 8, 13, tzinfo=UTC))
    sim_queue.submit(job("P0"), tmp_path, datetime(2026, 10, 8, 14, tzinfo=UTC))
    assert sim_queue.next_job(tmp_path) == late_p0


def test_a_job_left_running_is_resumed_before_any_waiting_job(tmp_path):
    sim_queue.submit(job("P0"), tmp_path)
    (tmp_path / "running" / "P2-old.json").write_text(json.dumps(job("P2")))
    assert sim_queue.next_job(tmp_path).name == "P2-old.json"


def test_memory_gate_counts_workers_parent_reserve_and_the_nightly_run():
    eight = job(workers=8, per_worker=2300.0, hours=8.2)
    need = 8 * 2300 + sim_queue.PARENT_MIB + sim_queue.RESERVE_MIB
    morning = datetime(2026, 10, 14, 10, 0, tzinfo=LOCAL)
    assert sim_queue.need_mib(eight) == need
    assert sim_queue.fits(eight, need, morning)
    assert not sim_queue.fits(eight, need - 1, morning)
    afternoon = datetime(2026, 10, 14, 13, 0, tzinfo=LOCAL)
    assert sim_queue.crosses_nightly(afternoon, 8.2) and not sim_queue.fits(eight, need, afternoon)
    assert sim_queue.fits(eight, need + sim_queue.NIGHTLY_MIB, afternoon)
    assert not sim_queue.crosses_nightly(datetime(2026, 10, 14, 21, 0, tzinfo=LOCAL), 8.2)
