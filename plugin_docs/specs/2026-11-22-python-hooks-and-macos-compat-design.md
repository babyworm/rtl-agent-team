# Python hook logic, Python compatibility floor and macOS compatibility — design

Status: Implemented (2.0.0-pre14) · Date: 2026-11-22

## Decisions

- Hook entry points stay POSIX `sh` launchers (`hooks.json` runs `sh "<hook>"`). Logic that
  parses JSON, evidence or Markdown moves to Python modules under `hooks/lib/*.py`. A launcher
  must stay safe without Python: the verify gate blocks, the SessionStart inject emits the
  minimal envelope plus one notice.
- Python floor: 3.9 (macOS system `python3` is 3.9.6; RHEL 9 ships 3.9). Python 2 is not
  supported; `rat_select_python` rejects it by the version probe.
- The stop budget (`hooks/lib/stop-budget-util.sh`) stays the single implementation shared by
  every Stop gate. The verify gate's launcher keeps the budget calls; Python supplies inputs.

## 0. Compatibility policy

- `hooks/lib/python-util.sh`: `RAT_PYTHON_MIN=3.9` drives `rat_select_python`.
  `scripts/rat_compat.py`: `MIN_PYTHON = (3, 9)`, `TESTED = ((3, 9), (3, 14))`,
  `level(version) -> "unsupported" | "eol" | "supported" | "untested"`, `require()`.
  A unit test keeps both floors equal.
- CI test matrix: 3.9, 3.12, 3.14.
- Contract test over every plugin `.py`: parses with `ast.parse(feature_version=(3, 9))`;
  a module with PEP 604 (`X | Y`) annotations imports `from __future__ import annotations`;
  no names introduced after 3.9 from a curated list (`tomllib`, `datetime.UTC`,
  `zip(strict=)`, `itertools.batched`, `typing.Self`, `contextlib.chdir`, `ExceptionGroup`).
- Install-time check: `scripts/post-install.sh` and `rat-setup` print the selected interpreter,
  version and level; `rat-doctor` adds a Python row (FAIL below 3.9, WARN for an EOL or
  untested version) and selects its own interpreter with `rat_select_python`.

## 1. macOS compatibility

Root causes of the 21 local failures: bash 3.2 lacks `exec {var}>` (`tool-runner.sh`) and fails
on empty-array expansion under `set -u` (`run_lint.sh`, `run_regression*.sh`); macOS openrsync
lacks `--protect-args`; one eda_setup probe times out on macOS (root cause to be found).
Fixes keep Linux behavior unchanged. A contract test rejects bash 4+ constructs and unguarded
empty-array expansions in bundled bash scripts.

## 2. Verify gate

`hooks/rtl-verify-stop-gate.sh`: input root, team skip, `stopu_chain_active`, background yield,
the no-tracking fast path, Python selection, then `eval` of shell-quoted assignments printed by
`hooks/lib/verify_gate.py`, then the unchanged budget ladder. Without Python it blocks with a
message that names the missing interpreter.

`verify_gate.py`: tracking aggregation (solo, session, fallback; dedupe; project-relative),
`verification.stop_gate`, evidence via `verify_evidence` functions, cleanup on verified or
waived, messages, progress, receipt state, simulator presence. When records with
`origin: verify-run` clear the pending files, the gate lets Claude stop with
`Info> Rule 5 cleared for N RTL file(s) by verify-run: <runner> [on <host>].`

## 3. SessionStart inject

`hooks/rtl-orchestrator-inject.sh`: marker check in sh (no marker → minimal envelope, no
Python); with a marker, `hooks/lib/session_inject.py` reads the export block of
`skills/rtl-orchestrate/SKILL.md` at runtime and prints the envelope. Without Python: minimal
envelope plus a `systemMessage` naming rat-doctor. `scripts/sync_orchestrator_inject.sh` is
removed; tests compare the runtime output with the SSOT block.

## Verification

Full unit suite green on this macOS host (bash 3.2, openrsync) and under Python 3.9; existing
verify-gate behavior tests unchanged; CI matrix green; one independent review.

## Changes from the independent review

- Data loss in the new openrsync path: an output written `sim/out/` fetched from `sim/` and, in
  `results: sync`, `--delete` removed unprotected files there. Older code also accepted `./`,
  `./.` and `.//` as outputs, which syncs the whole workspace onto the project. `relative_output`
  now returns the normal form, refuses root and reserved (`.git`, `.claude`, `.rat`,
  `.rtl-agent-team`) values, and merge/sync fetches exclude nested `.git`/`.claude`. Tests cover
  every rsync variant with forced features and run `fetch` through the host's real rsync.
- One floor, checked everywhere: `test_every_copy_of_the_floor_is_the_floor` compares each
  version comparison and "Python >= X.Y" message in code with `MIN_PYTHON`; the CI matrix must
  contain the floor; 3.10 is marked end of life; the CI test job is pinned to ubuntu-24.04 so a
  3.9 build stays available.
- Gate hardening: helpers run with `python -I`; a malformed configuration or evidence index no
  longer crashes the helper; blank tracking files are removed; the cleared notice is computed
  before cleanup and resolves the runner path against a resolved root; the no-Python path lets
  a blank tracking file through and puts file content in its progress.
- The SessionStart fallback names whether Python is missing or the helper failed.
- `test_bash_portability.py` also rejects `declare -g/-l/-u`, `[[ -v ]]`, negative array indices,
  `${x@Q}` and globstar, and recognizes every `set ... nounset` form.
- The edit tracker's PPA scope check uses `rat_select_python`; a regression test covers both the
  in-scope and the no-Python path.

Not changed: a fetch that fails may leave the empty parent folder it created; `run_sim.sh`
still takes `RAT_PYTHON` or `python3` (its floor literal is checked); no macOS CI job.

