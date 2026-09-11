# Repository pulse

This directory contains the client-facing prototype for a read-only Git state signal. It gives engineers and agents the same compact answer to three questions: which revision is checked out, what changed, and whether the result is an exact or reduced scan.

The prototype is deliberately an explicit command, not an enabled agent hook. This keeps the Git inspection contract testable before session cursors, assignment ownership, or model-context injection are added.

## Modules

- `repo_pulse.py` inspects one or more repositories with Git's stable porcelain v2 format and emits text or JSON.
- `test_repo_pulse.py` exercises clean, unborn, staged, unstaged, untracked, special-path, quick-scan, fingerprint, and partial-failure behavior.

## Usage

The prototype requires Git and [uv](https://docs.astral.sh/uv/). It has no third-party Python package dependency.

Run a quick scan of the current repository:

```bash
uv run .codex/hooks/repo_pulse.py
```

Inspect several repositories or request machine-readable output:

```bash
uv run .codex/hooks/repo_pulse.py --repo . --repo ../another-project --format json
```

The quick default collapses each untracked directory into one entry, so it does not provide an exact untracked-file count. Use `--exact` before mutation, staging, or commit validation. Text output shows at most 20 paths per repository; use `--max-paths` for a deliberate expansion or JSON for software processing.

Run the tests:

```bash
uv run .codex/hooks/test_repo_pulse.py
```

## Safety contract

The command:

- uses `git --no-optional-locks` so background inspection does not perform optional index refresh writes;
- does not stage, commit, checkout, reset, clean, stash, merge, rebase, fetch, or contact a remote;
- reads paths from Git's NUL-delimited porcelain output so spaces and other path characters remain unambiguous;
- returns exit status `2` and an explicit error record when any requested repository cannot be inspected; and
- omits absolute repository paths and remote URLs from successful output.

Repository names must be unique within one invocation. Inspect same-named repositories separately until explicit local labels are implemented.

## Planned hook boundary

The future hook adapter should compare the snapshot fingerprint with a per-session cursor and remain silent when state has not changed. Mutable cursors and assignment leases belong in Git-local state, not tracked project files. Hook configuration should call this module through a thin adapter and must not make background inspection a correctness gate.

Before activation, the adapter needs tests for concurrent Git operations, history rewrites, overlapping assignments, stale leases, output limits, hook bypass, and clean-checkout delivery. No hook configuration is enabled by this prototype.
