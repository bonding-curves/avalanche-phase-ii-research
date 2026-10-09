"""The one code path that scores the lockbox: guards, then the lock, then the score, then the receipt, then output.

    python scripts/unseal_lockbox.py rehearse --commit C
    python scripts/unseal_lockbox.py unseal --commit C --bundle-hash H --runner NAME --witness PATH --rehearsal PATH \\
        --registry-unsealed-at none

The pre-registration is the folder ``validation/lockbox/``, committed once. Its ``manifest.json`` names the model entry
point (``module:function``), the specification's author, the hash of ``uv.lock``, the pin files, the rehearsal's
boundary and window, and the record of the Foundation's answer on what "better" means. The entry point is called as
``function(token, fit_until=..., score_until=...)`` and returns a JSON-serialisable mapping of result tables.

``rehearse`` fits to the rehearsal boundary and scores to its window end on development data only, with no token, and
writes a rehearsal record. ``unseal`` checks guards G1 to G8, then pushes the annotated tag ``lockbox-unsealed`` before it
reads one lockbox row. The push is the lock: a remote that already has the tag refuses it, and a crash after it still
counts as the unseal. Then it builds the token, calls the entry point, writes the receipt and the filled report,
commits them to branch ``lockbox/receipt`` and pushes, and only then prints anything.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import secrets
import socket
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

from avalanche_research.core import lockbox
from avalanche_research.core.clock import LOCKBOX_FIRST_DAY
from avalanche_research.core.hashing import canonical_bytes, sha256

FOLDER = Path("validation/lockbox")
OUTPUTS = {"receipt.json", "report.md"}
WINDOW_END = date(2026, 9, 22)
RECEIPT_BRANCH = "lockbox/receipt"
COMMIT_ID = re.compile(r"^[0-9a-f]{40}$")
# Window ends are exclusive UTC dates: fit_until 2024-12-16 fits on data dated before 16 December 2024. A development
# window must end on or before the lockbox's first day, 2025-11-19, so it reads nothing from the boundary's day on.


class GuardFailed(RuntimeError):
    pass


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def bundle_hash(folder: Path) -> str:
    """SHA-256 over canonical bytes of each file's path and hash, outputs excluded."""
    files = {str(path.relative_to(folder)): sha256(path.read_bytes())
             for path in sorted(folder.rglob("*")) if path.is_file() and path.name not in OUTPUTS}
    return sha256(canonical_bytes(files))


def script_hash() -> str:
    return sha256(Path(__file__).read_bytes())


def manifest(repo: Path) -> dict:
    return json.loads((repo / FOLDER / "manifest.json").read_text())


def guards(repo: Path, args: argparse.Namespace) -> dict[str, str]:
    """Check G1 to G8 and return what each checked. Raise GuardFailed with the first failure."""
    spec = manifest(repo)
    checked: dict[str, str] = {}

    def need(code: str, ok: bool, why: str) -> None:
        if not ok:
            raise GuardFailed(f"{code}: {why}")
        checked[code] = why

    head = git(repo, "rev-parse", "HEAD")
    git(repo, "fetch", "-q", "origin", "main")
    on_main = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", args.commit, "origin/main"],
                             check=False).returncode == 0
    need("G1", head.startswith(args.commit) and on_main and bundle_hash(repo / FOLDER) == args.bundle_hash,
         f"commit {args.commit} checked out, on origin/main, folder hash {args.bundle_hash}")
    need("G2", git(repo, "status", "--porcelain") == "" and sha256((repo / "uv.lock").read_bytes()) == spec["uv_lock_sha256"],
         "clean checkout, uv.lock matches the manifest")
    from avalanche_research.datasets import pins

    findings = [finding for pin in spec["pins"] for finding in pins.verify(repo / pin)]
    need("G3", bool(spec["pins"]) and not findings,
         f"{len(spec['pins'])} pin files verify" if spec["pins"] and not findings else "; ".join(findings) or "the manifest names no pin")
    need("G4", lockbox.remote_tag(repo) is None and not (repo / FOLDER / "receipt.json").exists() and args.registry_unsealed_at == "none",
         "no unseal tag on the remote, no receipt, registry unsealed_at is none")
    need("G5", Path(args.witness).is_file(), f"witness record {args.witness}")
    need("G6", bool(args.runner) and args.runner != spec["author"], f"runner {args.runner}, author {spec['author']}")
    record = json.loads(Path(args.rehearsal).read_text()) if Path(args.rehearsal).is_file() else {}
    window = spec["rehearsal"]
    complete = {"commit", "script_sha256", "bundle_hash", "fit_until", "score_until", "results_sha256", "passed", "at"} <= set(record)
    need("G7", complete and record["passed"] is True and bool(COMMIT_ID.match(str(record["commit"]))) and record["commit"] == head
         and record["script_sha256"] == script_hash() and record["bundle_hash"] == args.bundle_hash
         and record["fit_until"] == window["fit_until"] and record["score_until"] == window["score_until"]
         and bool(re.match(r"^[0-9a-f]{64}$", str(record["results_sha256"]))),
         f"a complete rehearsal record at {record.get('commit')}, this script, this bundle and the manifest's window")
    answer = spec.get("foundation_answer", {})
    need("G8", answer.get("recorded") is True or answer.get("default_used") is True, "the Foundation's answer, or the default used, is recorded")
    return checked


def entry_point(spec: dict, repo: Path):
    """The pre-registered callable, loaded from a file inside the checked repository, never from elsewhere on the path."""
    module, _, function = spec["entry_point"].partition(":")
    relative = Path(*module.split("."))
    for base in (repo / "src", repo):
        for candidate in (base / relative.with_suffix(".py"), base / relative / "__init__.py"):
            if candidate.is_file():
                loaded = importlib.util.spec_from_file_location(module, candidate)
                instance = importlib.util.module_from_spec(loaded)
                sys.modules[module] = instance
                writing, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # keep the checked checkout clean
                try:
                    loaded.loader.exec_module(instance)
                finally:
                    sys.dont_write_bytecode = writing
                return getattr(instance, function)
    raise GuardFailed(f"entry point {spec['entry_point']} is not a file inside {repo}")


def development_window(fit_until: date, score_until: date) -> None:
    """Refuse a rehearsal window that is unordered or reaches the lockbox, before any model code is imported."""
    if not fit_until < score_until:
        raise GuardFailed(f"the rehearsal fits to {fit_until} and scores to {score_until}: the fit must end before the score window ends")
    if score_until > LOCKBOX_FIRST_DAY:
        raise GuardFailed(f"the rehearsal ends at {score_until}, after the lockbox's first day {LOCKBOX_FIRST_DAY}; it must use development data only")


def rehearse(repo: Path, args: argparse.Namespace) -> Path:
    spec = manifest(repo)
    rehearsal = spec["rehearsal"]
    fit_until, score_until = date.fromisoformat(rehearsal["fit_until"]), date.fromisoformat(rehearsal["score_until"])
    development_window(fit_until, score_until)
    if git(repo, "status", "--porcelain"):
        raise GuardFailed("the rehearsal runs only from a clean checkout")
    results = entry_point(spec, repo)(None, fit_until=fit_until, score_until=score_until)
    record = {"commit": git(repo, "rev-parse", "HEAD"), "script_sha256": script_hash(), "bundle_hash": bundle_hash(repo / FOLDER),
              "fit_until": str(fit_until), "score_until": str(score_until), "results_sha256": sha256(canonical_bytes(results)),
              "passed": True, "at": datetime.now(UTC).isoformat(timespec="seconds")}
    out = Path(args.out or "lockbox-rehearsal.json")
    out.write_text(json.dumps(record, indent=1) + "\n")
    return out


def acquire(repo: Path, args: argparse.Namespace, started: str) -> str:
    """Push a tag object no other contender can make, then confirm the remote holds exactly it. Only that holder scores.

    The nonce, host and process make each contender's annotated tag object distinct, so a second push meets a different
    object on the remote and is refused, and an identical-object push cannot pass as "already up to date"."""
    nonce = secrets.token_hex(16)
    git(repo, "tag", "-a", lockbox.TAG, args.commit, "-m",
        f"lockbox unsealing by {args.runner} at {started}\nnonce {nonce} host {socket.gethostname()} pid {os.getpid()}")
    mine = git(repo, "rev-parse", f"refs/tags/{lockbox.TAG}")
    try:
        git(repo, "push", "origin", f"refs/tags/{lockbox.TAG}")
    except subprocess.CalledProcessError as error:
        git(repo, "tag", "-d", lockbox.TAG)
        raise GuardFailed(f"G4: another runner holds the lock: {error.stderr.strip()[-200:]}") from error
    held = lockbox.remote_tag(repo)
    if held != mine:
        raise GuardFailed(f"G4: the remote lock is {held}, not this runner's {mine}; nothing was scored")
    return mine


def render_report(template: str, results: dict) -> tuple[str, str | None]:
    """The report from the pre-registered template, or a plain fallback with the formatting error when the template
    cannot be filled, such as a number format applied to a value the scorer never produced."""
    flat = defaultdict(lambda: "(not computed)", {k: v for k, v in results.items() if not isinstance(v, (dict, list))})
    try:
        return template.format_map(flat), None
    except Exception as error:  # noqa: BLE001  any template failure falls back; the receipt never depends on the report
        reason = f"{type(error).__name__}: {error}"
        lines = ["# Lockbox result", "", f"The pre-registered report template could not be filled ({reason}).",
                 "The receipt beside this file holds the results exactly. Each top-level result:", ""]
        lines += [f"- {key}: {value!r}" for key, value in sorted(results.items())]
        return "\n".join(lines) + "\n", reason


WRITE_ATTEMPTS = 3


def recovery(repo: Path) -> str:
    return (f"The unseal happened and must not run again. Commit {FOLDER}/receipt.json and report.md on branch "
            f"{RECEIPT_BRANCH} in {repo} and push it by hand: git -C {repo} push origin {RECEIPT_BRANCH}")


def persist(folder: Path, receipt: dict) -> str | None:
    """Write the local receipt, trying up to WRITE_ATTEMPTS times. Returns None once written, or the last error."""
    error = None
    for _ in range(WRITE_ATTEMPTS):
        try:
            (folder / "receipt.json").write_bytes(canonical_bytes(receipt))
            return None
        except OSError as failure:
            error = f"{type(failure).__name__}: {failure}"
    return error


def remote_receipt(repo: Path) -> bytes | None:
    """The receipt as the remote receipt branch holds it, fetched fresh, or None when it cannot be read."""
    try:
        git(repo, "fetch", "-q", "origin", RECEIPT_BRANCH)
        return subprocess.run(["git", "-C", str(repo), "show", f"FETCH_HEAD:{FOLDER}/receipt.json"], capture_output=True,
                              check=True).stdout
    except subprocess.CalledProcessError:
        return None


def publish(repo: Path, args: argparse.Namespace, receipt: dict, results: dict) -> dict:
    """Write the receipt with its recovery steps first, then the report, then commit and push both, and confirm the
    remote branch holds the committed receipt. The receipt never depends on the report: a template that cannot be filled
    gives a fallback report and records why. Any failure from here is recorded in the local receipt with the recovery
    steps, the script exits non-zero, and nothing is scored again. When the local receipt cannot be written after
    WRITE_ATTEMPTS tries, the receipt and its recovery are printed instead. A storage or power loss that also stops the
    output cannot be recorded here; the remote lock still forbids a second run."""
    folder = repo / FOLDER
    receipt.update(published=False, recovery=recovery(repo))
    unwritten = persist(folder, receipt)
    if unwritten:
        receipt.update(persisted=False, publish_error=f"the local receipt could not be written: {unwritten}")
        print(json.dumps(receipt, indent=1, default=str), flush=True)
        return receipt
    written = [str(FOLDER / "receipt.json")]
    try:
        template = folder / "template.md"
        if template.is_file():
            report, receipt["report_error"] = render_report(template.read_text(), results)
            (folder / "report.md").write_text(report)
            written.append(str(FOLDER / "report.md"))
        committed = {key: value for key, value in receipt.items() if key != "recovery"} | {"published": True}
        (folder / "receipt.json").write_bytes(canonical_bytes(committed))
        git(repo, "switch", "-q", "-c", RECEIPT_BRANCH)
        git(repo, "add", *written)
        git(repo, "commit", "-q", "-m", f"lockbox: receipt of the unseal by {args.runner}")
        git(repo, "push", "-q", "origin", RECEIPT_BRANCH)
        if remote_receipt(repo) != canonical_bytes(committed):
            raise RuntimeError("the remote receipt branch does not hold the committed receipt")
        receipt.clear()
        receipt.update(committed)
    except Exception as error:  # noqa: BLE001  after the lock every failure is recorded with its recovery, never retried
        stderr = getattr(error, "stderr", None)
        receipt.update(published=False, recovery=recovery(repo),
                       publish_error=(stderr.strip() if isinstance(stderr, str) and stderr.strip() else f"{type(error).__name__}: {error}")[-300:])
        unwritten = persist(folder, receipt)
        if unwritten:
            receipt.update(persisted=False)
            print(json.dumps(receipt, indent=1, default=str), flush=True)
    return receipt


def unseal(repo: Path, args: argparse.Namespace) -> dict:
    checked = guards(repo, args)
    started = datetime.now(UTC).isoformat(timespec="seconds")
    tag_object = acquire(repo, args, started)
    # From here the unseal has happened. Every failure is recorded and published, and nothing is scored twice.
    try:
        token = lockbox.issue(repo)
        results = entry_point(manifest(repo), repo)(token, fit_until=LOCKBOX_FIRST_DAY, score_until=WINDOW_END)
        if not isinstance(results, dict):
            results = {"error": f"the entry point returned {type(results).__name__}, not a mapping"}
    except Exception as error:  # noqa: BLE001  the unseal has happened, so a failure is recorded, not retried
        results = {"error": f"{type(error).__name__}: {error}"}
    try:
        digest = sha256(canonical_bytes(results))
    except (TypeError, ValueError) as error:
        results, digest = {"error": f"results are not serialisable: {error}"}, ""
    receipt = {"commit": args.commit, "bundle_hash": args.bundle_hash, "runner": args.runner, "tag_object": tag_object,
               "guards": checked, "started_at": started, "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
               "fit_until": str(LOCKBOX_FIRST_DAY), "score_until": str(WINDOW_END), "results": results, "results_sha256": digest}
    return publish(repo, args, receipt, results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("rehearse", "unseal"))
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--commit", required=True)
    parser.add_argument("--bundle-hash")
    parser.add_argument("--runner")
    parser.add_argument("--witness")
    parser.add_argument("--rehearsal")
    parser.add_argument("--registry-unsealed-at")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        if args.command == "rehearse":
            print(rehearse(args.repo, args))
        else:
            receipt = unseal(args.repo, args)
            print(json.dumps({key: receipt.get(key) for key in ("commit", "runner", "tag_object", "results_sha256", "published", "recovery")}, indent=1))
            if not receipt.get("published"):
                return 3
    except GuardFailed as error:
        print(f"REFUSED | {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
