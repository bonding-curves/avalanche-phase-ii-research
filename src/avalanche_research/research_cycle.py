"""One bounded, preregistered research cycle using the portable first experiment.

JSON/JSONL hypotheses, experiment definitions, receipts and separate reflection
records preserve the distinction between execution and scientific assessment.
This module neither schedules work nor generates research prose.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import signal
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class CycleError(ValueError):
    """An invalid definition, incomplete execution or unauthenticated artifact."""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def fingerprint(value: Any) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise CycleError(f"cannot read JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise CycleError(f"expected an object: {path.name}")
    return value


def atomic(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def inside(root: Path, name: str, *, exists: bool = True) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise CycleError("paths must be relative and remain inside their root")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise CycleError("symlinks are not accepted as evidence")
    if not current.resolve().is_relative_to(root.resolve()):
        raise CycleError("path escapes its root")
    if exists and not current.is_file():
        raise CycleError(f"missing file: {name}")
    return current


@contextmanager
def lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / ".cycle.lock").is_symlink():
        raise CycleError("cycle lock must not be a symlink")
    with (directory / ".cycle.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise CycleError("another process owns this cycle") from error
        try:
            yield stream.fileno()
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CycleError("analysis requires finite numeric observations")
    return value


def at(document: dict, pointer: str) -> float:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise CycleError("metrics use JSON pointers beginning with /")
    value: Any = document
    try:
        for part in pointer[1:].split("/"):
            key = part.replace("~1", "/").replace("~0", "~")
            value = value[int(key)] if isinstance(value, list) else value[key]
    except (KeyError, ValueError, TypeError, IndexError) as error:
        raise CycleError(f"missing analysis metric: {pointer}") from error
    return number(value)


def predicate(value: float, criterion: dict) -> bool:
    threshold = number(criterion.get("value"))
    operations = {"lt": lambda: value < threshold, "le": lambda: value <= threshold,
                  "gt": lambda: value > threshold, "ge": lambda: value >= threshold,
                  "eq": lambda: value == threshold}
    if criterion.get("op") not in operations:
        raise CycleError("criterion operator must be lt, le, gt, ge or eq")
    return operations[criterion["op"]]()


def definition(root: Path, experiment_path: Path, hypotheses_path: Path) -> tuple[dict, dict, dict]:
    """Resolve one hypothesis and bind the complete delivered driver/input code."""
    experiment_path = inside(root, experiment_path.relative_to(root).as_posix())
    hypotheses_path = inside(root, hypotheses_path.relative_to(root).as_posix())
    experiment = load(experiment_path)
    if experiment.get("schema") != "research-cycle-experiment/v1":
        raise CycleError("unknown experiment schema")
    if experiment.get("driver") != "first-experiment":
        raise CycleError("only the bounded first-experiment driver is supported")
    if experiment.get("scope") != "development":
        raise CycleError("only declared development experiments are supported")
    if not isinstance(experiment.get("id"), str) or not experiment["id"]:
        raise CycleError("experiment needs an id")
    timeout = experiment.get("timeout_seconds", 120)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 900:
        raise CycleError("timeout_seconds must be between 1 and 900")
    try:
        hypotheses = [json.loads(line) for line in hypotheses_path.read_text().splitlines() if line.strip()]
        ids = [hypothesis["id"] for hypothesis in hypotheses]
    except (ValueError, KeyError, TypeError) as error:
        raise CycleError("invalid hypotheses.jsonl") from error
    if len(set(ids)) != len(ids) or len(experiment.get("hypotheses", [])) != 1:
        raise CycleError("use one uniquely identified hypothesis per bounded cycle")
    matches = [h for h in hypotheses if h["id"] == experiment["hypotheses"][0]]
    if len(matches) != 1:
        raise CycleError("experiment hypothesis does not resolve")
    hypothesis = matches[0]
    for field in ("question", "hypothesis", "continuation_question", "scope"):
        if not isinstance(hypothesis.get(field), str) or not hypothesis[field].strip():
            raise CycleError(f"hypothesis needs {field}")
    if not all(hypothesis.get("prediction", {}).get(field) for field in ("statement", "test")):
        raise CycleError("hypothesis needs its prediction and preregistered test")
    analysis = experiment.get("analysis", {})
    if analysis.get("source") != "summary.json":
        raise CycleError("first-experiment analysis reads summary.json")
    if not analysis.get("rules"):
        raise CycleError("experiment needs numeric analysis rules")
    for rule in analysis["rules"]:
        if not rule.get("id") or not rule.get("metric", "").startswith("/"):
            raise CycleError("each rule needs an id and metric pointer")
        predicate(0, rule.get("support", {}))
        predicate(0, rule.get("contradict", {}))
    if len({rule["id"] for rule in analysis["rules"]}) != len(analysis["rules"]):
        raise CycleError("analysis rule ids must be unique")
    minimum = analysis.get("minimum_observations", 1)
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1:
        raise CycleError("minimum_observations must be a positive integer")
    if not analysis.get("observations", "").startswith("/"):
        raise CycleError("analysis needs an observation-count pointer")
    names = {experiment_path.relative_to(root).as_posix(), hypotheses_path.relative_to(root).as_posix(),
             "scripts/first_experiment.py", "scripts/research_cycle.py", "pyproject.toml", "uv.lock"}
    if "driver_config" in experiment:
        config = inside(root, experiment["driver_config"])
        relative = config.relative_to(root)
        if relative.suffix != ".json" or not any(relative.is_relative_to(folder) for folder in
                ("examples/first-experiment", "examples/research-cycle")):
            raise CycleError("driver_config must be a JSON example definition")
        names.add(relative.as_posix())
    for folder in ("src/avalanche_research", "examples/first-experiment"):
        directory = root / folder
        if not directory.is_dir() or directory.is_symlink():
            raise CycleError(f"missing delivered driver directory: {folder}")
        for path in directory.rglob("*"):
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if path.is_symlink():
                raise CycleError("driver/input symlinks are not accepted")
            if path.is_file():
                names.add(path.relative_to(root).as_posix())
    bindings = {name: digest(inside(root, name)) for name in sorted(names)}
    revision = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    identity = {"experiment": experiment["id"], "hypothesis": hypothesis["id"],
                "experiment_file": experiment_path.relative_to(root).as_posix(),
                "hypotheses_file": hypotheses_path.relative_to(root).as_posix(),
                "checkout_base_commit": revision, "files_sha256": bindings,
                "source_identity": "Working-file hashes bind execution; the checkout base need not contain local additions.",
                "python": list(sys.version_info[:3])}
    return experiment, hypothesis, identity


def artifacts(directory: Path) -> dict[str, str]:
    found = {}
    size = 0
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise CycleError("output symlinks are not accepted")
        if path.is_file():
            size += path.stat().st_size
            if size > 64 * 1024 * 1024 or len(found) >= 256:
                raise CycleError("bounded output exceeds 64 MiB or 256 files")
            found[path.relative_to(directory).as_posix()] = digest(path)
    if not found:
        raise CycleError("experiment produced no output files")
    return found


def execute(command: list[str], root: Path, log: Path, timeout: int, lock_fd: int | None = None) -> None:
    with log.open("ab") as stream:
        process = subprocess.Popen(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True, pass_fds=() if lock_fd is None else (lock_fd,))
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise
    if code:
        raise CycleError(f"experiment command exited {code}; inspect attempt.log")


def evaluate(experiment: dict, summary: dict, source_sha256: str) -> dict:
    specification = experiment["analysis"]
    count = at(summary, specification["observations"])
    if count < 0 or int(count) != count:
        raise CycleError("observation count must be a nonnegative integer")
    rules = []
    for rule in specification["rules"]:
        value = at(summary, rule["metric"])
        support = predicate(value, rule["support"])
        contradict = predicate(value, rule["contradict"])
        if support and contradict:
            raise CycleError("support and contradiction criteria overlap at the measured value")
        rules.append({**rule, "value": value, "outcome": "supported" if support else
                      "contradicted" if contradict else "inconclusive"})
    if count < specification.get("minimum_observations", 1):
        outcome = "inconclusive"
    elif any(rule["outcome"] == "contradicted" for rule in rules):
        outcome = "contradicted"
    elif all(rule["outcome"] == "supported" for rule in rules):
        outcome = "supported"
    else:
        outcome = "inconclusive"
    return {"schema": "research-cycle-analysis/v1", "experiment": experiment["id"],
            "source": specification["source"], "source_sha256": source_sha256,
            "observations": count, "minimum_observations": specification.get("minimum_observations", 1),
            "rules": rules, "outcome": outcome}


def readback(output: Path) -> dict:
    receipt = load(output / "receipt.json")
    if receipt.get("schema") != "research-cycle-receipt/v1":
        raise CycleError("unknown receipt schema")
    if receipt.get("status") not in ("running", "completed", "failed", "interrupted"):
        raise CycleError("unknown operational status")
    if not isinstance(receipt.get("attempts"), list) or not receipt["attempts"]:
        raise CycleError("receipt needs execution attempts")
    for index, attempt in enumerate(receipt["attempts"], 1):
        if attempt.get("id") != index or attempt.get("directory") != f"attempts/{index:04d}":
            raise CycleError("attempt identity does not resolve")
    if fingerprint(receipt["identity"]) != receipt["contract_sha256"]:
        raise CycleError("receipt identity differs")
    required = {"experiment.json", "hypotheses.jsonl"}
    if receipt["status"] == "completed":
        required |= {"analysis.json", "insight.json"}
    if not required.issubset(receipt.get("artifacts_sha256", {})):
        raise CycleError("receipt omits required artifacts")
    for name, expected in receipt.get("artifacts_sha256", {}).items():
        if digest(inside(output, name)) != expected:
            raise CycleError(f"cycle artifact changed: {name}")
    for frozen, field in (("experiment.json", "experiment_file"), ("hypotheses.jsonl", "hypotheses_file")):
        if digest(output / frozen) != receipt["identity"]["files_sha256"][receipt["identity"][field]]:
            raise CycleError("frozen definition differs from its contract")
    for attempt in receipt["attempts"]:
        if "log_sha256" in attempt and digest(inside(output, attempt["directory"] + "/attempt.log")) != attempt["log_sha256"]:
            raise CycleError("attempt log changed")
        if "partial_outputs_sha256" in attempt:
            directory = inside(output, attempt["directory"] + "/experiment/placeholder", exists=False).parent
            if artifacts(directory) != attempt["partial_outputs_sha256"]:
                raise CycleError("failed attempt outputs changed")
    if receipt["status"] == "completed":
        attempt = receipt["attempts"][-1]
        actual = artifacts(inside(output, attempt["directory"] + "/experiment/" + attempt["summary_source"]).parent)
        if actual != attempt["outputs_sha256"]:
            raise CycleError("experiment outputs changed or are incomplete")
        analysis = load(output / "analysis.json")
        if analysis["outcome"] != receipt["scientific_outcome"]:
            raise CycleError("receipt and analysis outcomes differ")
        summary = inside(output, attempt["directory"] + "/experiment/summary.json")
        if evaluate(load(output / "experiment.json"), load(summary), digest(summary)) != analysis:
            raise CycleError("analysis does not match authenticated observations and criteria")
        insight = load(output / "insight.json")
        if insight["analysis_sha256"] != digest(output / "analysis.json") or insight["outcome"] != analysis["outcome"]:
            raise CycleError("insight does not resolve to this analysis")
    elif receipt.get("scientific_outcome") != "invalid" or (output / "insight.json").exists():
        raise CycleError("incomplete execution cannot contain a scientific insight")
    return receipt


def run(root: Path, experiment_path: Path, hypotheses_path: Path, output: Path, *, resume: bool = False) -> dict:
    root = root.resolve()
    experiment, hypothesis, identity = definition(root, experiment_path.resolve(), hypotheses_path.resolve())
    contract = fingerprint(identity)
    output = output.resolve()
    if output.is_relative_to(root / "src") or output.is_relative_to(root / "examples/first-experiment"):
        raise CycleError("output cannot overwrite source or the frozen first experiment")
    with lock(output) as lock_fd:
        receipt_path = output / "receipt.json"
        if receipt_path.exists():
            pending = load(receipt_path)
            if pending.get("contract_sha256") != contract or fingerprint(pending.get("identity")) != contract:
                raise CycleError("hypothesis, design, inputs, code or environment changed; use a new output directory")
            if resume and pending.get("status") == "running":
                # Holding flock proves that the previous writer has exited. Retain
                # any writes that preceded its final receipt as uncommitted evidence.
                prior = inside(output, pending["attempts"][-1]["directory"] + "/placeholder", exists=False).parent
                for name in ("analysis.json", "insight.json"):
                    path = output / name
                    if path.exists():
                        inside(output, name).replace(prior / ("uncommitted-" + name))
            receipt = readback(output)
            if receipt["contract_sha256"] != contract:
                raise CycleError("hypothesis, design, inputs, code or environment changed; use a new output directory")
            if receipt["status"] == "completed":
                return receipt
            if not resume:
                raise CycleError("incomplete cycle: use --resume for one new attempt")
            if receipt["attempts"] and receipt["attempts"][-1]["status"] == "running":
                receipt["attempts"][-1].update(status="interrupted", ended_at=now())
        else:
            present = {path.name for path in output.iterdir()} - {".cycle.lock"}
            interrupted_initialization = resume and present.issubset({"experiment.json", "hypotheses.jsonl"})
            if present and not interrupted_initialization:
                raise CycleError("new cycle output directory must be empty")
            if interrupted_initialization:
                for name, source in (("experiment.json", experiment_path), ("hypotheses.jsonl", hypotheses_path)):
                    if name in present and digest(inside(output, name)) != digest(source):
                        raise CycleError("interrupted initialization differs from the declared definition")
            receipt = {"schema": "research-cycle-receipt/v1", "contract_sha256": contract,
                       "identity": identity, "created_at": now(), "attempts": [], "artifacts_sha256": {}}
            for name, source in (("experiment.json", experiment_path), ("hypotheses.jsonl", hypotheses_path)):
                target = output / name
                target.write_bytes(source.read_bytes())
                receipt["artifacts_sha256"][name] = digest(target)
        attempt_name = f"attempts/{len(receipt['attempts']) + 1:04d}"
        attempt_directory = output / attempt_name
        attempt = {"id": len(receipt["attempts"]) + 1, "directory": attempt_name,
                   "status": "running", "started_at": now(), "summary_source": experiment["analysis"]["source"]}
        receipt["attempts"].append(attempt)
        receipt.update(status="running", scientific_outcome="invalid")
        atomic(receipt_path, receipt)
        try:
            attempt_directory.mkdir(parents=True)
            driver = root / "scripts/first_experiment.py"
            destination = attempt_directory / "experiment"
            destination_argument = destination.relative_to(root).as_posix() if destination.is_relative_to(root) else str(destination)
            command = [sys.executable, str(driver), "--output", destination_argument]
            if "driver_config" in experiment:
                command += ["--config", experiment["driver_config"]]
            attempt["driver"] = "scripts/first_experiment.py"
            attempt["arguments"] = {"output": attempt_name + "/experiment"}
            if "driver_config" in experiment:
                attempt["arguments"]["config"] = experiment["driver_config"]
            attempt["argument_path_basis"] = "Output is relative to this cycle directory; driver executes from checkout root."
            execute(command, root, attempt_directory / "attempt.log", experiment.get("timeout_seconds", 120), lock_fd)
            before_check = artifacts(destination)
            execute(command + ["--check"], root, attempt_directory / "attempt.log", 30, lock_fd)
            if before_check != artifacts(destination):
                raise CycleError("experiment check modified its evidence")
            if definition(root, experiment_path.resolve(), hypotheses_path.resolve())[2] != identity:
                raise CycleError("code, input or design changed during execution")
            summary_path = inside(destination, experiment["analysis"]["source"])
            analysis = evaluate(experiment, load(summary_path), digest(summary_path))
            atomic(output / "analysis.json", analysis)
            insight = {"schema": "research-cycle-insight/v1", "hypothesis": hypothesis["id"],
                       "experiment": experiment["id"], "attempt": attempt["id"],
                       "outcome": analysis["outcome"], "prediction": hypothesis["prediction"],
                       "analysis_sha256": digest(output / "analysis.json"), "scope": hypothesis["scope"],
                       "continuation_question": hypothesis["continuation_question"],
                       "interpretation": "Preregistered numeric assessment. Narrative interpretation is a separate authored task."}
            atomic(output / "insight.json", insight)
            attempt.update(status="completed", ended_at=now(), outputs_sha256=before_check,
                           log_sha256=digest(attempt_directory / "attempt.log"))
            receipt.update(status="completed", scientific_outcome=analysis["outcome"])
            receipt["artifacts_sha256"].update({name: digest(output / name) for name in ("analysis.json", "insight.json")})
        except BaseException as error:
            attempt.update(status="interrupted" if isinstance(error, (KeyboardInterrupt, SystemExit)) else "failed",
                           ended_at=now(), error_type=type(error).__name__)
            if (attempt_directory / "attempt.log").is_file():
                attempt["log_sha256"] = digest(attempt_directory / "attempt.log")
            partial = attempt_directory / "experiment"
            if partial.is_dir() and not partial.is_symlink():
                try:
                    attempt["partial_outputs_sha256"] = artifacts(partial)
                except CycleError:
                    attempt["partial_outputs_valid"] = False
            receipt.update(status=attempt["status"], scientific_outcome="invalid")
            # A crash between these atomic writes must never leave a usable insight.
            for name in ("analysis.json", "insight.json"):
                (output / name).unlink(missing_ok=True)
            atomic(receipt_path, receipt)
            raise
        atomic(receipt_path, receipt)
        return readback(output)


def reflect(output: Path, record_path: Path) -> dict:
    """Attach an explicit authored outer review of a completed inner cycle."""
    record = load(record_path)
    with lock(output):
        receipt = readback(output)
        if receipt["status"] != "completed":
            raise CycleError("reflection requires a completed, authenticated analysis")
        if record.get("schema") != "research-cycle-reflection/v1":
            raise CycleError("unknown reflection schema")
        if record.get("analysis_sha256") != digest(output / "analysis.json"):
            raise CycleError("reflection refers to a different analysis")
        if record.get("experiment") != receipt["identity"]["experiment"]:
            raise CycleError("reflection experiment does not resolve")
        for field in ("author", "method_assessment", "direction_assessment", "continuation_question"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise CycleError(f"authored reflection needs {field}")
        proposals = record.get("proposals", [])
        if not isinstance(proposals, list) or not 1 <= len(proposals) <= 5:
            raise CycleError("reflection needs one to five explicit proposals")
        for proposal in proposals:
            for field in ("id", "action", "owner", "expected_benefit", "success_check", "disposition"):
                if not isinstance(proposal.get(field), str) or not proposal[field].strip():
                    raise CycleError(f"reflection proposal needs {field}")
            if proposal["disposition"] not in ("proposed", "deferred", "rejected", "applied", "untested"):
                raise CycleError("invalid proposal disposition")
        if len({proposal["id"] for proposal in proposals}) != len(proposals):
            raise CycleError("reflection proposal ids must be unique")
        target = output / "reflection.json"
        if target.exists() and load(target) != record:
            raise CycleError("reflection already attached; preserve it and use a new revision")
        atomic(target, record)
        receipt["artifacts_sha256"]["reflection.json"] = digest(target)
        atomic(output / "receipt.json", receipt)
        return readback(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    running = commands.add_parser("run", help="Execute one bounded attempt, or authenticate completed output")
    running.add_argument("--experiment", type=Path, default=Path("examples/research-cycle/experiment.json"))
    running.add_argument("--hypotheses", type=Path, default=Path("examples/research-cycle/hypotheses.jsonl"))
    running.add_argument("--output", type=Path, required=True)
    running.add_argument("--resume", action="store_true")
    reading = commands.add_parser("read", help="Authenticate and read an existing cycle without executing")
    reading.add_argument("--output", type=Path, required=True)
    reflecting = commands.add_parser("reflect", help="Attach an explicit authored methodology/direction review")
    reflecting.add_argument("--output", type=Path, required=True)
    reflecting.add_argument("--record", type=Path, required=True)
    args = parser.parse_args(argv)
    def interrupted(signum, _frame):
        raise SystemExit(128 + signum)

    previous_sigterm = signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.command == "run":
            receipt = run(Path.cwd(), args.experiment, args.hypotheses, args.output, resume=args.resume)
        elif args.command == "reflect":
            receipt = reflect(args.output, args.record)
        else:
            receipt = readback(args.output)
        print(json.dumps({"status": receipt["status"], "scientific_outcome": receipt["scientific_outcome"],
                          "attempts": len(receipt["attempts"]), "contract_sha256": receipt["contract_sha256"],
                          "reflection": "reflection.json" in receipt["artifacts_sha256"]}, sort_keys=True))
    except (CycleError, OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"FAIL | research cycle | {error}\n")
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
    return 0
