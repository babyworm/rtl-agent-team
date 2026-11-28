# Verify gate modes and `verify-run` — implementation plan

Status: Historical (executed for 2.0.0-pre13) · Date: 2026-11-22 · Spec: `plugin_docs/specs/2026-11-22-verify-gate-modes-and-verify-run-design.md`

**Goal:** `verification.stop_gate` (block | notify | off) for Rule 5, and `eda_runner.py verify-run`,
which wraps a project's own runner and records content-bound evidence (optionally hashing the
inputs on the execution host after the run).

**Architecture:** `verify-run` reuses `begin`/`finish` from `scripts/verify_evidence.py` and
`execute()` from `scripts/eda_runner.py`, so it writes the record shape the gate already reads.
The gate reads its mode through `eda_runner.py get`, the same lookup it uses for the simulator.

**Tech stack:** POSIX sh hook, Python 3.9+ helpers, pytest.

Scope note: the spec carries the code-level contract (flags, verdict precedence, record fields).
This plan is the execution order; each task is test-first and runs `pytest tests/unit/ -x -q`
before the release commit (CLAUDE.md rule 12).

## Tasks

- [x] **1. Evidence helper hooks** (`scripts/verify_evidence.py`)
  - `begin_record(args) -> Path`; `begin(args)` prints it (CLI and `regression_evidence.py` unchanged).
  - `finish(args)`: optional `unbound` (forces INCONCLUSIVE over PASS/COMPILED, recorded as
    `unbound_reason`) and `extra` (merged into the record). CLI namespaces lack both → no change.
  - Bump `rat-version`.
- [x] **2. `verify-run`** (`scripts/eda_runner.py`, tests in `tests/unit/test_eda_runner.py`)
  - Tests first: local PASS satisfies `unverified` and the real hook; FAIL signature, nonzero
    exit and missing summary; `--log` not rewritten → INCONCLUSIVE; `--log` overwritten later
    keeps evidence (copy); local edit during the run → INCONCLUSIVE; remote copy equal → PASS,
    differs / missing → INCONCLUSIVE naming files; runner failure → no remote step; live run →
    `pending` exit 0; invalid requests → exit 2 with no RUNNING record.
  - Implement: validation before `begin`, ctime change detection for `--log`, `execute()`,
    `remote_input_mismatches()` (ssh + `remote_shell_command`, `sha256sum`/`shasum` fallback),
    `git_state()` metadata, `finish()` with `unbound`/`extra`. Bump `rat-version`.
- [x] **3. Machine fallback** (`scripts/eda_setup.py`): `user_configuration()` passes `verification`
  through in both branches; test via `eda_runner.py get`. Bump `rat-version`.
- [x] **4. Gate modes** (`hooks/rtl-verify-stop-gate.sh`, tests in `tests/unit/test_hooks.py`)
  - Tests first: default block names `verify-run`; notify → one `Info>` line, no block, verified
    files cleared; off → silent, tracking kept, block resumes; unknown value → block naming it;
    machine fallback; project config wins.
  - Implement: mode read after the empty-tracking exit, `off` exit, `notify` hand-over before the
    simulator check, block message route to `verify-run`.
- [x] **5. Docs**: SSOT `skills/rtl-orchestrate/SKILL.md` (Rule 5 lines) → `sh scripts/sync_orchestrator_inject.sh`;
  `skills/rat-init-project/templates/rules/rtl-verification-gate.md`; `runtime/eda-runner-contract.md`
  ("Project runners"); `plugin_docs/hook-development-guide.md`; CLAUDE.md Rule 5 row; CHANGELOG.
- [x] **6. Release prep**: `python3 scripts/template_catalog.py --write`; `scripts/bump-version.sh 2.0.0-pre13`
  (keep README tables at the published version, as pre08–pre12 did); CHANGELOG `[2.0.0-pre13]`.
- [x] **7. Verify and ship** — Ran `pytest tests/unit/ -x -q`, addressed the independent review findings, and pushed the fixes to the prerelease branch.
