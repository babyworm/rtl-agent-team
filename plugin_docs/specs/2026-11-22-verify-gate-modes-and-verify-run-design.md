# Verify gate modes and `verify-run` — design

Status: Implemented (2.0.0-pre13) · Date: 2026-11-22

## Problem

`hooks/rtl-verify-stop-gate.sh` (Rule 5) accepts only `verify-evidence.json` records written by
the bundled wrappers (`scripts/run_sim.sh`, `run_regression*.sh`), locally or through
`eda_runner.py dispatch` with `execution.backend = ssh|lsf`.

Field report (synthetic names): a project's own regression runner passed 23 / 23 on a remote
simulator host after the last RTL commit. The runner runs **locally** and does its own transport:
rsync to the host, then `ssh <host> bash -s` through a project-defined `RAT_SSH` bridge. The
project has no `rat_config.json` with an SSH backend, and the local host has no simulator.
No path could turn that run into evidence, so the gate blocked until the user waived it.

Two gaps follow:

1. A run made by a project-owned runner (any transport) cannot become content-bound evidence.
2. A project cannot choose a softer gate when the user accepts that trade-off.

## Goals

- A: a per-project (machine fallback) setting that selects how the gate reacts.
- B: one command that wraps an existing project runner, unchanged, and records evidence bound to
  the inputs. When the runner executes elsewhere, the inputs are also hashed on that host.
- Keep `unverified()` and every existing evidence consumer unchanged: B writes the same record
  shape as `begin`/`finish`.

## Non-goals

- Syncing files to a remote host (`dispatch` owns managed transport).
- Accepting a manifest, a log or a PASS pattern supplied on the command line after the fact.
  Any of these would let the agent declare its own PASS; a waiver is the honest form of that.
- A `verification.pass_pattern` setting. The runner prints a recognized summary instead
  (`RAT_SIM_PASS`, `TESTS=<n> PASS=<n> FAIL=0`).
- Site-profile-level gate settings; detached (nohup) remote runs.

## A. `verification.stop_gate`

| Value | Behavior |
|---|---|
| `block` (default) | Current behavior. Unknown values and an unreadable setting also mean `block`; the block message names the unknown value. |
| `notify` | Never blocks. Evidence is still checked, verified files are still cleared, and one line per content state is shown: `Info> Functional verification is pending for N RTL file(s) (verification.stop_gate=notify).` |
| `off` | Silent. The tracking files stay, so pending files resurface when the project returns to `block`. |

Resolution: `eda_runner.py get --root <project> --key verification.stop_gate`. A project
`rat_config.json` owns the value (existing whole-file semantics). Without one, the machine
`env-config.json` applies: `user_configuration()` passes `verification` through in both the
plain and the `default_site` branch. Caveat to document: a hand-written `rat_config.json` replaces
the machine configuration as a whole, so create it with `rat-init-project`, not by hand.

The gate reads the mode only after it found tracked files, so a Stop without RTL edits costs no
extra Python start. Placement in the hook:

1. After the "no tracked files" exit: read the mode. `off` → `emit_post_continue`.
2. Evidence check unchanged (verified → cleanup → continue).
3. Before the simulator-presence check: `notify` → `save_receipt info` and
   `stopu_gate … "$NOTIFY_NOTICE" 0` (the existing hand-over path; the receipt keeps it to one
   line per content state).
4. `block` continues as today. Its message adds the `verify-run` route (absolute plugin path).

## B. `eda_runner.py verify-run`

```
eda_runner.py verify-run --root <project> [-f <filelist>] [--source <file>]... \
    [--log <runner summary file>] [--tool <name>] [--timeout <s>] [--stall <s>] \
    [--remote-host <host> --remote-root <absolute dir>] -- <runner command...>
```

Steps:

1. **Inputs**: at least one of `-f` (one filelist, as `begin`) or `--source`. `source_paths()` resolves sources, includes and filelists (recursive `-f`/`-F`,
   `+incdir+`, configured `verification.include_dirs`). With `--remote-*`, every input must lie
   inside the project; inputs with a backslash or control character are rejected (manifest parsing
   stays unambiguous).
2. **begin**: reuse `begin()` (refactored to return the record path). `runner_pid` is the
   verify-run process, so `pending_run()` lets a Stop through while a background run is alive.
   `outdir` = `<state root>/tool-runs/verify-run-<uuid>/`; console log = `outdir/console.log`.
3. **Run**: `execute(argv, …)` — process group, `timeout_seconds` / `stall_seconds` from
   `execution` (CLI overrides), output teed to the console log. The command runs locally as given;
   its own transport (rsync, `RAT_SSH`, LSF wrapper, plain `ssh host '…'`) is untouched.
   `RAT_PROJECT_ROOT` is exported. The backend setting is not consulted.
4. **Summary file** (`--log`): must exist and its ctime must differ from the value seen just
   before the run, or the file must be new (`rsync -a` copies mtime but cannot set ctime, and no
   clock is compared, so host clock skew does not matter). It is copied to `outdir/summary-<name>` and the copy is the
   runtime log, so a later overwrite of the project file does not invalidate the evidence.
5. **Remote manifest** (`--remote-*`, only when the command exited 0): one SSH session
   (`ssh [execution.ssh_options] <host> <remote_shell_command(script)>`, host checked by
   `validate_host`) runs `cd -- <root>` and `sha256sum -- <relative inputs…>`, falling back to
   `shasum -a 256`; no remote Python is needed. Output is saved to `outdir/remote-manifest.txt`.
   Every input must appear with the local digest.
6. **finish**: reuse `finish()` with an optional `unbound` reason. Verdict precedence:

| Condition | Verdict |
|---|---|
| exit 124 / RAT_TIMEOUT, RAT_STALL, RAT_HANG | TIMEOUT / STALL / HANG |
| failure signature in console or summary, nonzero exit | FAIL |
| `--log` missing or not written during the run | INCONCLUSIVE |
| remote input missing, digest differs, SSH or hash tool failed | INCONCLUSIVE (lists the files) |
| local inputs changed during the run | INCONCLUSIVE (existing `sources_fresh`) |
| recognized completion in the runtime log (summary, else console) | PASS |
| otherwise | INCONCLUSIVE |

Record additions (all other fields as `begin`/`finish`): `origin: "verify-run"`, `argv`,
`remote_host`, `remote_root`, `remote_manifest_sha256`, `unbound_reason`, `git_head`,
`git_dirty` (metadata only — the remote copy is not a Git checkout, so a commit hash proves
nothing about its contents). Exit status mirrors `finish`: the command's nonzero status, else 0
for PASS and 3 otherwise.

## Failure handling

- Missing or invalid flags (`--remote-host` without `--remote-root`, relative remote root,
  no inputs) → exit 2 before the command runs; no RUNNING record is left.
- Interrupt or timeout → `execute()` kills the process group; the record is finished with the
  matching verdict. A remote job started by the runner may outlive a timeout; the message says so.
- SSH failure in the manifest step → INCONCLUSIVE with the SSH status; the console log is kept.

## Documentation

- Gate header comment and block message; `runtime/eda-runner-contract.md` (new "Project runners"
  section); `skills/rtl-orchestrate/SKILL.md` Rule 5 lines 297/434/558/659 →
  `sh scripts/sync_orchestrator_inject.sh`; `skills/rat-init-project/templates/rules/rtl-verification-gate.md`;
  `plugin_docs/hook-development-guide.md` (RTL Stop behavior); CLAUDE.md Rule 5 row; CHANGELOG `[Unreleased]`.

## Tests

- `tests/unit/test_hooks.py`: `block` default, `notify` (no block, one notice per content state,
  verified files still cleared), `off` (silent, tracking kept), unknown value → block naming it,
  machine `env-config.json` fallback without `rat_config.json`.
- `tests/unit/test_eda_runner.py` (fake `ssh` from the `remote_project` fixture): local runner PASS
  → gate allows; FAIL log; missing recognized summary → INCONCLUSIVE; `--log` not rewritten →
  INCONCLUSIVE; `--log` overwritten later → evidence still valid (copy); remote digest mismatch and
  missing remote file → INCONCLUSIVE listing them; local edit during the run → INCONCLUSIVE;
  running record lets the gate pass (`pending`); inputs outside the project rejected with
  `--remote-*`; no remote step when the command failed.

## Changes from the independent review

The review found two ways to a PASS without a real run on the current inputs and several
robustness gaps. The implementation differs from the sections above as follows:

- The runner script (and the script an interpreter runs) is hashed as a dependency, so editing
  it afterwards voids the evidence. Commands that only print (`echo`, `printf`, `true`, `cat`,
  ...) are refused. Only `RAT_SIM_PASS` at line start and `TESTS=<n> PASS=<n> FAIL=0` count as
  completion (`finish(pass_pattern=...)`); a bare `PASS` line is INCONCLUSIVE.
- `--log` additionally requires `mtime >= start - 120 s`: `rsync -a`/`cp -p` of a stale summary
  sets a new ctime but keeps the old mtime.
- The command runs from the project root; `--log`, `-f`, `--source` and a relative runner path
  all resolve against it.
- Every failure after the run (SSH client missing, copy errors) becomes an `unbound` reason and
  the record is always finished; it never stays RUNNING.
- The remote step sends its script on stdin (`ssh -o BatchMode=yes [ssh_options] -- host sh -s`),
  so large input sets fit; exit 1 with no output is a failed step, not "all files missing".
  Remote names must be printable and backslash-free; output is split on `\n` only.
- With `--remote-*`, filelists must be project-relative without `$VAR` (shared
  `require_relative_filelists`, as `dispatch`). Headers under `$UVM_HOME/src` stay local-only.
- `notify` writes its own receipt, so returning to `block` still requests verification. The
  echoed unknown value keeps printable ASCII only. Docs state that changing the mode is the
  user's decision.
- `eda_runner.py` imports `begin_record`/`finish` inside `verify_run`, so an older project
  `verify_evidence.py` cannot break other subcommands.

Not changed: `--timeout` may still raise the configured limit, consistent with `run`.

## Open items

- The field project needs one runner line that prints a recognized summary.
- Threat model: the gate guards against a mistaken or hurried agent. An agent that writes a
  runner which only prints the token can still pass, as it can with a fake testbench under
  `run_sim.sh`; the record keeps the argv so the user can see what cleared the gate.
