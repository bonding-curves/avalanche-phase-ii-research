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
import importlib
import json
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from avalanche_research.core import lockbox
from avalanche_research.core.clock import LOCKBOX_FIRST_DAY
from avalanche_research.core.hashing import canonical_bytes, sha256

FOLDER = Path("validation/lockbox")
OUTPUTS = {"receipt.json", "report.md"}
WINDOW_END = date(2026, 9, 22)
RECEIPT_BRANCH = "lockbox/receipt"


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
    need("G3", not findings, f"{len(spec['pins'])} pin files verify" if not findings else "; ".join(findings))
    need("G4", lockbox.remote_tag(repo) is None and not (repo / FOLDER / "receipt.json").exists() and args.registry_unsealed_at == "none",
         "no unseal tag on the remote, no receipt, registry unsealed_at is none")
    need("G5", Path(args.witness).is_file(), f"witness record {args.witness}")
    need("G6", bool(args.runner) and args.runner != spec["author"], f"runner {args.runner}, author {spec['author']}")
    record = json.loads(Path(args.rehearsal).read_text()) if Path(args.rehearsal).is_file() else {}
    need("G7", record.get("passed") is True and head.startswith(record.get("commit", "-")) and record.get("script_sha256") == script_hash(),
         f"rehearsal at {record.get('commit')} with this script")
    answer = spec.get("foundation_answer", {})
    need("G8", answer.get("recorded") is True or answer.get("default_used") is True, "the Foundation's answer, or the default used, is recorded")
    return checked


def entry_point(spec: dict):
    module, _, function = spec["entry_point"].partition(":")
    return getattr(importlib.import_module(module), function)


def rehearse(repo: Path, args: argparse.Namespace) -> Path:
    spec = manifest(repo)
    rehearsal = spec["rehearsal"]
    fit_until, score_until = date.fromisoformat(rehearsal["fit_until"]), date.fromisoformat(rehearsal["score_until"])
    if score_until > LOCKBOX_FIRST_DAY:
        raise GuardFailed(f"the rehearsal scores to {score_until}, past the lockbox's first day; it must use development data only")
    results = entry_point(spec)(None, fit_until=fit_until, score_until=score_until)
    record = {"commit": git(repo, "rev-parse", "HEAD"), "script_sha256": script_hash(), "fit_until": str(fit_until),
              "score_until": str(score_until), "results_sha256": sha256(canonical_bytes(results)), "passed": True,
              "at": datetime.now(UTC).isoformat(timespec="seconds")}
    out = Path(args.out or "lockbox-rehearsal.json")
    out.write_text(json.dumps(record, indent=1) + "\n")
    return out


def unseal(repo: Path, args: argparse.Namespace) -> dict:
    checked = guards(repo, args)
    started = datetime.now(UTC).isoformat(timespec="seconds")
    git(repo, "tag", "-a", lockbox.TAG, args.commit, "-m", f"lockbox unsealing by {args.runner} at {started}")
    git(repo, "push", "origin", f"refs/tags/{lockbox.TAG}")
    token = lockbox.issue(repo)
    try:
        results = entry_point(manifest(repo))(token, fit_until=LOCKBOX_FIRST_DAY, score_until=WINDOW_END)
    except Exception as error:  # noqa: BLE001  the unseal has happened, so a failure is recorded, not retried
        results = {"error": f"{type(error).__name__}: {error}"}
    receipt = {"commit": args.commit, "bundle_hash": args.bundle_hash, "runner": args.runner, "tag_object": token.tag_object,
               "guards": checked, "started_at": started, "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
               "fit_until": str(LOCKBOX_FIRST_DAY), "score_until": str(WINDOW_END), "results": results,
               "results_sha256": sha256(canonical_bytes(results))}
    git(repo, "switch", "-q", "-c", RECEIPT_BRANCH)
    (repo / FOLDER / "receipt.json").write_bytes(canonical_bytes(receipt))
    template = repo / FOLDER / "template.md"
    written = [str(FOLDER / "receipt.json")]
    if template.is_file():
        flat = {key: value for key, value in results.items() if not isinstance(value, (dict, list))}
        (repo / FOLDER / "report.md").write_text(template.read_text().format_map(flat))
        written.append(str(FOLDER / "report.md"))
    git(repo, "add", *written)
    git(repo, "commit", "-q", "-m", f"lockbox: receipt of the unseal by {args.runner}")
    git(repo, "push", "-q", "origin", RECEIPT_BRANCH)
    return receipt


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
            print(json.dumps({key: receipt[key] for key in ("commit", "runner", "tag_object", "results_sha256")}, indent=1))
    except GuardFailed as error:
        print(f"REFUSED | {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
