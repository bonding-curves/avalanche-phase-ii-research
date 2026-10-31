"""Failure-oriented checks for the bounded cycle, using an explicit test driver.

The fake driver exercises orchestration only. It is never research evidence.
"""

import json
import os
import signal
import subprocess
import sys
import time

import pytest

from avalanche_research import research_cycle as cycle

DRIVER = '''import argparse, json, os, pathlib, sys, time
p=argparse.ArgumentParser()
p.add_argument('--output',type=pathlib.Path,required=True)
p.add_argument('--check',action='store_true')
p.add_argument('--config',type=pathlib.Path,default=pathlib.Path('examples/first-experiment/config.json'))
a=p.parse_args()
config=json.loads(a.config.read_text())
mode=config.get('mode','success')
if a.check:
    if mode=='check-fails': sys.exit(3)
    assert json.loads((a.output/'summary.json').read_text())['pair_count'] >= 0
    sys.exit(0)
a.output.mkdir()
if mode=='fail-once' and a.output.parent.name=='0001':
    (a.output/'partial.json').write_text('partial')
    sys.exit(2)
if mode=='timeout':
    (a.output/'partial.json').write_text('partial')
    (a.output/'pid.txt').write_text(str(os.getpid()))
    time.sleep(30)
metric=config['baseline']-config['candidate']
summary={'pair_count':config.get('pairs',2),'metrics':{'rewards_saved_avax':metric}}
if mode=='missing': summary['metrics']={}
if mode=='nonfinite': summary['metrics']['rewards_saved_avax']=float('nan')
(a.output/'summary.json').write_text(json.dumps(summary))
'''


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()
    for name in ("scripts/research_cycle.py", "src/avalanche_research/example.py", "pyproject.toml", "uv.lock"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# unit-test fixture\n")
    (root / "scripts/first_experiment.py").write_text(DRIVER)
    write(root / "examples/first-experiment/config.json", {"baseline": 10, "candidate": 8})
    experiment = {"schema": "research-cycle-experiment/v1", "id": "E-test", "hypotheses": ["H-test"],
                  "driver": "first-experiment", "scope": "development", "timeout_seconds": 3,
                  "analysis": {"source": "summary.json", "observations": "/pair_count", "minimum_observations": 2,
                               "rules": [{"id": "lower-reward", "metric": "/metrics/rewards_saved_avax",
                                          "support": {"op": "gt", "value": 0},
                                          "contradict": {"op": "lt", "value": 0}}]}}
    hypothesis = {"id": "H-test", "question": "Does the test driver lower its numeric reward?",
                  "hypothesis": "The fixture arithmetic is positive.",
                  "prediction": {"statement": "Difference exceeds zero.", "test": "Preregistered sign check."},
                  "scope": "Unit-test fixture, not scientific evidence.",
                  "continuation_question": "Is a real scientific experiment available?"}
    write(root / "examples/research-cycle/experiment.json", experiment)
    write(root / "examples/research-cycle/hypotheses.jsonl", hypothesis)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.test",
                    "commit", "-qm", "Fixture"], check=True)
    return root, tmp_path / "output"


def run(project, **kwargs):
    root, output = project
    return cycle.run(root, root / "examples/research-cycle/experiment.json",
                     root / "examples/research-cycle/hypotheses.jsonl", output, **kwargs)


def configure(project, **kwargs):
    path = project[0] / "examples/first-experiment/config.json"
    config = json.loads(path.read_text())
    config.update(kwargs)
    write(path, config)


def test_complete_cycle_and_idempotence(project, monkeypatch):
    receipt = run(project)
    assert receipt["status"] == "completed" and receipt["scientific_outcome"] == "supported"
    analysis = cycle.load(project[1] / "analysis.json")
    assert analysis["rules"][0]["value"] == 2
    assert analysis["observations"] == 2
    assert cycle.load(project[1] / "insight.json")["analysis_sha256"] == cycle.digest(project[1] / "analysis.json")
    assert "examples/first-experiment/config.json" in receipt["identity"]["files_sha256"]
    monkeypatch.setattr(cycle, "execute", lambda *args: pytest.fail("completed cycles must not execute again"))
    assert run(project) == receipt
    assert len(list((project[1] / "attempts").iterdir())) == 1


@pytest.mark.parametrize("filename", ["examples/first-experiment/config.json", "examples/research-cycle/experiment.json",
                                     "examples/research-cycle/hypotheses.jsonl", "src/avalanche_research/example.py"])
def test_changed_input_design_hypothesis_or_code_rejected(project, filename):
    run(project)
    path = project[0] / filename
    path.write_text(path.read_text() + "\n")
    before = cycle.digest(project[1] / "receipt.json")
    with pytest.raises(cycle.CycleError, match="changed"):
        run(project, resume=True)
    assert cycle.digest(project[1] / "receipt.json") == before


@pytest.mark.parametrize(("candidate", "expected"), [(12, "contradicted"), (10, "inconclusive")])
def test_real_numeric_output_can_contradict_or_leave_inconclusive(project, candidate, expected):
    configure(project, candidate=candidate)
    assert run(project)["scientific_outcome"] == expected


def test_insufficient_observations_are_inconclusive(project):
    configure(project, pairs=1)
    assert run(project)["scientific_outcome"] == "inconclusive"


@pytest.mark.parametrize("mode", ["missing", "nonfinite", "check-fails"])
def test_invalid_analysis_or_driver_check_creates_no_insight(project, mode):
    configure(project, mode=mode)
    with pytest.raises(cycle.CycleError):
        run(project)
    receipt = cycle.readback(project[1])
    assert receipt["status"] == "failed" and receipt["scientific_outcome"] == "invalid"
    assert not (project[1] / "insight.json").exists()


def test_failed_execution_requires_manual_resume_and_preserves_attempt(project):
    configure(project, mode="fail-once")
    with pytest.raises(cycle.CycleError, match="exited 2"):
        run(project)
    assert not (project[1] / "insight.json").exists()
    with pytest.raises(cycle.CycleError, match="--resume"):
        run(project)
    receipt = run(project, resume=True)
    assert [attempt["status"] for attempt in receipt["attempts"]] == ["failed", "completed"]
    assert (project[1] / "attempts/0001/experiment/partial.json").read_text() == "partial"


def test_timeout_is_invalid_not_a_scientific_finding(project):
    configure(project, mode="timeout")
    path = project[0] / "examples/research-cycle/experiment.json"
    experiment = cycle.load(path)
    experiment["timeout_seconds"] = 1
    write(path, experiment)
    with pytest.raises(subprocess.TimeoutExpired):
        run(project)
    assert cycle.readback(project[1])["scientific_outcome"] == "invalid"
    assert not (project[1] / "insight.json").exists()


def test_interruption_records_invalid_attempt_then_resumes(project, monkeypatch):
    original = cycle.execute
    monkeypatch.setattr(cycle, "execute", lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        run(project)
    assert cycle.readback(project[1])["status"] == "interrupted"
    assert not (project[1] / "insight.json").exists()
    monkeypatch.setattr(cycle, "execute", original)
    receipt = run(project, resume=True)
    assert [attempt["status"] for attempt in receipt["attempts"]] == ["interrupted", "completed"]


def test_hard_interruption_uncommitted_insight_is_quarantined(project):
    # Reconstruct the precise persisted state before the final atomic receipt.
    run(project)
    output = project[1]
    receipt = cycle.load(output / "receipt.json")
    receipt.update(status="running", scientific_outcome="invalid")
    receipt["attempts"][-1]["status"] = "running"
    for name in ("analysis.json", "insight.json"):
        receipt["artifacts_sha256"].pop(name)
    cycle.atomic(output / "receipt.json", receipt)
    with pytest.raises(cycle.CycleError, match="cannot contain"):
        cycle.readback(output)
    resumed = run(project, resume=True)
    assert resumed["scientific_outcome"] == "supported"
    assert (output / "attempts/0001/uncommitted-insight.json").is_file()
    assert [attempt["status"] for attempt in resumed["attempts"]] == ["interrupted", "completed"]


@pytest.mark.parametrize("change", ["modified", "extra", "deleted"])
def test_readback_rejects_modified_incomplete_and_extra_output(project, change):
    run(project)
    directory = project[1] / "attempts/0001/experiment"
    if change == "modified":
        (directory / "summary.json").write_text('{"pair_count":2}')
    elif change == "extra":
        (directory / "unexpected.txt").write_text("unrecorded")
    else:
        (directory / "summary.json").unlink()
    with pytest.raises(cycle.CycleError):
        cycle.readback(project[1])
    with pytest.raises(cycle.CycleError):
        run(project, resume=True)


def test_live_lock_rejects_duplicate_execution(project):
    with cycle.lock(project[1]), pytest.raises(cycle.CycleError, match="another process"):
        run(project)
    assert not (project[1] / "attempts").exists()


def reflection(project):
    return {"schema": "research-cycle-reflection/v1", "experiment": "E-test", "author": "Test fixture",
            "analysis_sha256": cycle.digest(project[1] / "analysis.json"),
            "method_assessment": "This checks orchestration, not a scientific model.",
            "direction_assessment": "Use genuine model evidence before a research claim.",
            "continuation_question": "Does the real bounded driver reproduce?",
            "proposals": [{"id": "P1", "action": "Exercise the real driver separately.", "owner": "researcher",
                           "expected_benefit": "Separate fixture checks from research evidence.",
                           "success_check": "A genuine, authenticated model output exists.", "disposition": "proposed"}]}


def test_outer_reflection_is_explicit_separate_and_hash_bound(project):
    run(project)
    path = project[1].parent / "authored-reflection.json"
    write(path, reflection(project))
    receipt = cycle.reflect(project[1], path)
    assert "reflection.json" in receipt["artifacts_sha256"]
    assert cycle.reflect(project[1], path) == receipt
    record = reflection(project)
    record["direction_assessment"] = "A different revision"
    write(path, record)
    with pytest.raises(cycle.CycleError, match="already attached"):
        cycle.reflect(project[1], path)


def test_reflection_rejects_other_analysis_and_missing_direction(project):
    run(project)
    path = project[1].parent / "authored-reflection.json"
    record = reflection(project)
    record["analysis_sha256"] = "0" * 64
    write(path, record)
    with pytest.raises(cycle.CycleError, match="different analysis"):
        cycle.reflect(project[1], path)
    record = reflection(project)
    del record["direction_assessment"]
    write(path, record)
    with pytest.raises(cycle.CycleError, match="direction_assessment"):
        cycle.reflect(project[1], path)


def test_readback_is_portable_and_read_only(project):
    receipt = run(project)
    before = {p.relative_to(project[1]): (p.stat().st_mtime_ns, cycle.digest(p))
              for p in project[1].rglob("*") if p.is_file()}
    project[0].rename(project[0].with_name("moved-checkout"))
    assert cycle.readback(project[1]) == receipt
    after = {p.relative_to(project[1]): (p.stat().st_mtime_ns, cycle.digest(p))
             for p in project[1].rglob("*") if p.is_file()}
    assert after == before
    assert str(project[0]) not in (project[1] / "receipt.json").read_text()


def test_missing_reference_and_protected_scope_fail_before_execution(project):
    path = project[0] / "examples/research-cycle/experiment.json"
    original = cycle.load(path)
    write(path, {**original, "hypotheses": ["H-absent"]})
    with pytest.raises(cycle.CycleError, match="does not resolve"):
        run(project)
    write(path, {**original, "scope": "protected"})
    with pytest.raises(cycle.CycleError, match="development"):
        run(project)
    assert not project[1].exists()


def test_input_changed_during_execution_invalidates_attempt(project, monkeypatch):
    original = cycle.execute
    calls = 0

    def execute(*args):
        nonlocal calls
        original(*args)
        calls += 1
        if calls == 1:
            path = project[0] / "src/avalanche_research/example.py"
            path.write_text("# changed while executing\n")

    monkeypatch.setattr(cycle, "execute", execute)
    with pytest.raises(cycle.CycleError, match="changed during execution"):
        run(project)
    assert cycle.readback(project[1])["scientific_outcome"] == "invalid"
    assert not (project[1] / "insight.json").exists()


def test_resume_recovers_interrupted_definition_copy(project):
    project[1].mkdir()
    source = project[0] / "examples/research-cycle/experiment.json"
    (project[1] / "experiment.json").write_bytes(source.read_bytes())
    with pytest.raises(cycle.CycleError, match="must be empty"):
        run(project)
    assert run(project, resume=True)["status"] == "completed"


def test_resume_recovers_reserved_attempt_before_directory_creation(project, monkeypatch):
    original = cycle.atomic

    def interrupted(path, value):
        original(path, value)
        if path.name == "receipt.json" and value["status"] == "running":
            raise KeyboardInterrupt()

    monkeypatch.setattr(cycle, "atomic", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run(project)
    assert not (project[1] / "attempts/0001").exists()
    monkeypatch.setattr(cycle, "atomic", original)
    receipt = run(project, resume=True)
    assert [attempt["status"] for attempt in receipt["attempts"]] == ["interrupted", "completed"]


def test_unresolved_partial_output_is_not_adopted_as_a_cycle(project):
    project[1].mkdir()
    (project[1] / "summary.json").write_text('{"pair_count":2}')
    with pytest.raises(cycle.CycleError, match="must be empty"):
        run(project, resume=True)


def test_symlinked_driver_input_is_rejected_before_execution(project, tmp_path):
    path = project[0] / "examples/first-experiment/config.json"
    target = tmp_path / "outside.json"
    target.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(cycle.CycleError, match="symlinks"):
        run(project)
    assert not project[1].exists()


def test_cli_read_reports_result_and_never_executes(project, capsys):
    run(project)
    assert cycle.main(["read", "--output", str(project[1])]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["attempts"] == 1 and response["scientific_outcome"] == "supported"


def test_explicit_bounded_driver_config_is_bound_and_used(project):
    root, _ = project
    write(root / "examples/research-cycle/alternative.json", {"baseline": 10, "candidate": 12})
    path = root / "examples/research-cycle/experiment.json"
    definition = cycle.load(path)
    definition["driver_config"] = "examples/research-cycle/alternative.json"
    write(path, definition)
    receipt = run(project)
    assert receipt["scientific_outcome"] == "contradicted"
    assert "examples/research-cycle/alternative.json" in receipt["identity"]["files_sha256"]
    assert cycle.load(root / "examples/first-experiment/config.json")["candidate"] == 8


@pytest.mark.parametrize("parent_signal", [signal.SIGTERM, signal.SIGKILL])
def test_actual_process_interruption_cannot_duplicate_a_live_attempt(project, parent_signal):
    root, output = project
    configure(project, mode="timeout")
    process = subprocess.Popen([sys.executable, "-c", "from avalanche_research.research_cycle import main; main()",
                                "run", "--output", str(output)], cwd=root,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    child_pid = None
    try:
        pid_file = output / "attempts/0001/experiment/pid.txt"
        deadline = time.monotonic() + 5
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert pid_file.exists(), process.communicate(timeout=1)
        child_pid = int(pid_file.read_text())
        process.send_signal(parent_signal)
        process.wait(timeout=5)
        if parent_signal == signal.SIGKILL:
            # The still-running child retains the writer lock even after its
            # parent cannot clean up. Resume must refuse a duplicate attempt.
            with pytest.raises(cycle.CycleError, match="another process"):
                run(project, resume=True)
            os.kill(child_pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while True:
            try:
                with cycle.lock(output):
                    break
            except cycle.CycleError:
                assert time.monotonic() < deadline
                time.sleep(0.01)
        receipt = cycle.readback(output)
        assert receipt["scientific_outcome"] == "invalid"
        if parent_signal == signal.SIGTERM:
            assert receipt["status"] == "interrupted"
        assert not (output / "insight.json").exists()
        assert len(receipt["attempts"]) == 1
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        process.communicate(timeout=5)
