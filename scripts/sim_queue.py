"""The simulation queue: lanes submit sweep jobs, one host runs them in priority order, never past its memory.

    python scripts/sim_queue.py submit JOB.json --root QUEUE
    python scripts/sim_queue.py run --root QUEUE [--once]
    python scripts/sim_queue.py status --root QUEUE

A job is a JSON file: ``lane``, ``priority`` (P0 contract runs, P1 development scoring and regressions, P2 exploration on
data before Granite), ``design`` (a sweep design for ``avalanche model sweep``, with ``workers`` set), ``per_worker_mib``
and ``expected_hours`` from a measured pilot, and an optional ``code_commit``. Jobs wait in ``incoming/``, run from
``running/`` and end in ``done/`` or ``failed/``, each with its output folder under ``out/``. The runner is single-file:
P0 before P1 before P2, oldest first within a class. A job starts only when its workers, the parent and the machine's
reserve fit in available memory. A job that would still be running when the host's nightly data run starts at 19:30 also
needs that run's measured 6 GB. Nothing is pre-empted mid-run. A job left in ``running/`` by a stop or reboot is run
again first, and the sweep runner skips its finished rows, so it resumes exactly. ``status.json`` holds the queue, the
running job and the last finished ones. When available memory falls under the reserve, or free disk under the queue
root under 50 GB, a line goes to ``alerts.jsonl``, at most once an hour for each kind, for the data engineer's wakes
to post to the team's threads.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

PRIORITIES = ("P0", "P1", "P2")
PARENT_MIB = 1024.0
RESERVE_MIB = 4096.0
NIGHTLY_MIB = 6144.0
NIGHTLY = (19, 30)
REQUIRED = ("lane", "priority", "design", "per_worker_mib", "expected_hours")
FOLDERS = ("incoming", "running", "done", "failed", "out")
DISK_FLOOR_GIB = 50.0
ALERT_EVERY = timedelta(hours=1)


def now() -> datetime:
    return datetime.now(UTC)


def check_job(job: dict) -> None:
    missing = [key for key in REQUIRED if key not in job]
    if missing:
        raise ValueError(f"job is missing {', '.join(missing)}")
    if job["priority"] not in PRIORITIES:
        raise ValueError(f"priority {job['priority']} is not one of {', '.join(PRIORITIES)}")
    workers = job["design"].get("workers")
    if not isinstance(workers, int) or workers < 1:
        raise ValueError("the design must set workers to a whole number, since the queue sizes memory from it")
    if any(isinstance(job[key], bool) or not isinstance(job[key], (int, float)) for key in ("per_worker_mib", "expected_hours")):
        raise ValueError("per_worker_mib and expected_hours must be numbers")
    if job["per_worker_mib"] <= 0 or job["expected_hours"] <= 0:
        raise ValueError("per_worker_mib and expected_hours come from a measured pilot and must be positive")


def submit(job: dict, root: Path, at: datetime | None = None) -> Path:
    check_job(job)
    at = at or now()
    job = {**job, "job_id": job.get("job_id") or f"{at:%Y%m%dT%H%M%SZ}-{job['lane']}", "submitted_at": at.isoformat()}
    for folder in FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)
    path = root / "incoming" / f"{job['priority']}-{at:%Y%m%dT%H%M%S}-{job['job_id']}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(job, indent=1))
    os.replace(temporary, path)
    return path


def need_mib(job: dict) -> float:
    return job["design"]["workers"] * job["per_worker_mib"] + PARENT_MIB + RESERVE_MIB


def crosses_nightly(start: datetime, hours: float) -> bool:
    """Whether a job started at ``start``, an aware local time, is still running at the host's next 19:30."""
    nightly = start.replace(hour=NIGHTLY[0], minute=NIGHTLY[1], second=0, microsecond=0)
    if nightly <= start:
        nightly += timedelta(days=1)
    return start + timedelta(hours=hours) > nightly


def fits(job: dict, available_mib: float, local_now: datetime) -> bool:
    extra = NIGHTLY_MIB if crosses_nightly(local_now, job["expected_hours"]) else 0.0
    return need_mib(job) + extra <= available_mib


def next_job(root: Path) -> Path | None:
    """A job left running comes first, then the highest priority, oldest first. File names sort that way."""
    running = sorted((root / "running").glob("*.json"))
    if running:
        return running[0]
    waiting = sorted((root / "incoming").glob("*.json"))
    return waiting[0] if waiting else None


def available_mib(meminfo: Path = Path("/proc/meminfo")) -> float:
    for line in meminfo.read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024
    raise OSError(f"no MemAvailable in {meminfo}")


def head_commit(clone: Path) -> str:
    return subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def alerts(root: Path, available: float, free_gib: float, at: datetime | None = None) -> list[dict]:
    """Append an alert for memory under the reserve or disk under the floor, unless the same kind was raised within the
    last hour. Returns the alerts written."""
    at = at or now()
    log = root / "alerts.jsonl"
    last: dict[str, datetime] = {}
    if log.is_file():
        for line in log.read_text().splitlines():
            row = json.loads(line)
            last[row["kind"]] = datetime.fromisoformat(row["at"])
    found = []
    if available < RESERVE_MIB:
        found.append({"kind": "memory", "detail": f"{available:.0f} MiB available, under the {RESERVE_MIB:.0f} MiB reserve"})
    if free_gib < DISK_FLOOR_GIB:
        found.append({"kind": "disk", "detail": f"{free_gib:.1f} GiB free under {root}, under {DISK_FLOOR_GIB:.0f} GiB"})
    written = [{"at": at.isoformat(), **item} for item in found if item["kind"] not in last or at - last[item["kind"]] >= ALERT_EVERY]
    with log.open("a") as handle:
        for item in written:
            handle.write(json.dumps(item) + "\n")
    return written


def write_status(root: Path, running: dict | None, note: str) -> None:
    def names(folder: str) -> list[str]:
        return [path.stem for path in sorted((root / folder).glob("*.json"))]

    available, free_gib = available_mib(), shutil.disk_usage(root).free / 2**30
    alerts(root, available, free_gib)
    status = {"at": now().isoformat(), "note": note, "available_mib": round(available, 1), "free_gib": round(free_gib, 1), "running": running,
              "incoming": names("incoming"), "done": names("done")[-20:], "failed": names("failed")[-20:]}
    temporary = root / "status.json.tmp"
    temporary.write_text(json.dumps(status, indent=1))
    os.replace(temporary, root / "status.json")


def run_one(path: Path, root: Path, clone: Path) -> bool:
    job = json.loads(path.read_text())
    if path.parent.name == "incoming":
        moved = root / "running" / path.name
        os.replace(path, moved)
        path = moved
    out = root / "out" / job["job_id"]
    out.mkdir(parents=True, exist_ok=True)
    design_path = out / "design-file.json"
    design_path.write_text(json.dumps(job["design"], indent=1))
    commit = head_commit(clone)
    if job.get("code_commit") and not commit.startswith(job["code_commit"]):
        result = {"ok": False, "reason": f"the runner clone is at {commit[:12]}, not the job's {job['code_commit']}"}
    else:
        write_status(root, {**job, "started_at": now().isoformat(), "code_commit": commit}, "running")
        with (out / "log.txt").open("a") as log:
            proc = subprocess.run(["uv", "run", "-q", "avalanche", "model", "sweep", str(design_path), str(out / "rows")],
                                  cwd=clone, stdout=log, stderr=subprocess.STDOUT, check=False)
        result = {"ok": proc.returncode == 0, "returncode": proc.returncode}
    finished = {**job, "code_commit": commit, "finished_at": now().isoformat(), **result}
    receipt = out / "rows" / "receipt.json"
    if receipt.is_file():
        finished["receipt_id"] = json.loads(receipt.read_text()).get("receipt_id")
    (root / ("done" if result["ok"] else "failed") / path.name).write_text(json.dumps(finished, indent=1))
    path.unlink()
    return result["ok"]


def run(root: Path, clone: Path, once: bool = False, poll_seconds: int = 60) -> None:
    for folder in FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)
    while True:
        path = next_job(root)
        if path is None:
            write_status(root, None, "idle")
        else:
            job = json.loads(path.read_text())
            available = available_mib()
            if path.parent.name == "running" or fits(job, available, datetime.now().astimezone()):
                run_one(path, root, clone)
                continue
            write_status(root, None, f"waiting: {job['job_id']} needs {need_mib(job):.0f} MiB, {available:.0f} available")
        if once:
            return
        time.sleep(poll_seconds)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("submit", "run", "status"))
    parser.add_argument("job", nargs="?")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--clone", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "submit":
        print(submit(json.loads(Path(args.job).read_text()), args.root))
    elif args.command == "run":
        run(args.root, args.clone, once=args.once)
    else:
        print((args.root / "status.json").read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
