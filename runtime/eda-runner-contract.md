# EDA execution contract

This supplies the execution contract for v1.0.0.
Runtime instructions describe goals and consume these results; they do not invent
PASS verdicts or repeat a successful review.

## Configuration

`eda_runner.py get --root <project> --key <key>` reads effective settings without
initializing a project. An existing project `rat_config.json` owns its execution
settings. Otherwise the runner reads `env-config.json` under the user's plugin
data directory. A selected `default_site` uses that site's measured tools,
environment and libraries. Query only the settings needed by the task, such as
`preferences.simulator`, `preferences.synthesis` or `technology.db`.
Before initialization, run records (evidence index, tool logs, shims) go to the
plugin data folder under `projects/<folder>-<hash>/`, so a run never creates `.rat/`
and the folder stays an ordinary directory. Generated outputs still use the project.
Remote execution mirrors the whole project root. Without `rat_config.json` that root
must be a Git work tree or be named with `RAT_PROJECT_ROOT`; home and hidden home
folders are refused.

`rat_config.json.execution` selects `backend`: `auto`, `local`, `docker`, `ssh`, or
`lsf`. An absent setting uses `auto`, local execution with the Docker fallback.
`timeout_seconds` bounds wall time (default 1800); `stall_seconds` is optional
output-inactivity detection (default 0, disabled for tools that work silently).
Both limits apply to the process group. A timeout is not a successful run.

`tools.<category>.<key>.path` is an executable override. `env_source` is a trusted
user/site command, evaluated by the explicitly chosen `env_shell` (`bash` or
`csh` or `tcsh`). A failed environment setup fails execution. Runtime consumes these
settings, not only setup-time detection. Credentials stay in SSH or site tooling,
never in prompts or recorded environment dumps.

Remote execution additionally needs `execution.host`, an absolute
`execution.workspace`, and `execution.outputs` (project-relative paths). LSF uses
the same SSH host and accepts an optional `execution.queue`. Missing remote
settings are errors; the runner never silently falls back to a local tool.

## Execution

`run_tool` is the command execution entry point. Wrappers export RAT_PROJECT_ROOT
and delegate their whole invocation to SSH/LSF before local tool discovery.
Transport sends inputs, not outputs. In a Git work tree it sends the Git-visible
files (tracked plus untracked files that no ignore rule covers), the files the
filelists resolve, and `execution.inputs`: project-relative glob patterns for
ignored files the run still needs, such as test vectors or a prebuilt model.
Build outputs stay local. A folder outside Git is mirrored whole, which also
copies its build outputs. The runner prints the file count and size before sending.
It installs the wrapper and runtime helpers in a private remote runtime directory,
runs from the remote workspace, and retrieves only declared outputs. A file an
earlier dispatch sent and this one no longer sends, such as a header deleted
locally, is deleted from the reused remote workspace; build outputs were never sent
and stay. A folder outside Git is mirrored without deletion. When a bundled wrapper's
named filelist cannot be resolved, dispatch stops with the parser's reason; for a
project runner it warns which inputs were not sent and skips that deletion.
When the SSH channel closes, the remote runner stops the tool it started and
records `DISCONNECTED` (exit 129). The runner also cancels its LSF job when the
`bsub -K` waiter does not come back: the time limit, a lost SSH connection, or
SIGHUP, SIGINT, or SIGTERM delivered to the dispatcher (those are exits 129, 130,
and 143, because the waiter is in its own session). A cancel that fails or times
out is logged, and the job's status file is still read.

Each wrapper uses its matching runtime shim and helpers. Bundled wrappers use
bundled helpers; installed project wrappers use the managed project library;
remote wrappers use their private runtime bundle. Mixing a new wrapper with an
older project helper is not an accepted fallback.

Inputs and outputs for remote wrappers must belong to the synchronized project.
Absolute CLI arguments inside the project are mapped to the remote workspace.
External absolute source paths in filelists are rejected with a diagnostic;
project-relative filelists remain portable. A tool installation path is interpreted
on the execution host. SSH uses an explicit sh/bash command even when the login
shell is tcsh; per-tool tcsh setup is applied by the runtime adapter.

Docker mounts the project at the same absolute path and preserves the wrapper's
working directory. It runs as the caller's uid/gid with a writable HOME, mounts
external runtime helpers read-only, and runs nested commands locally in the
container rather than dispatching Docker again.

LSF writes a unique exit-status artifact from the job. Submission success is not
job success. A missing status artifact is INCONCLUSIVE. The runner records the
submission output and cancels its own uniquely named job when that waiter does not come back.

## Results

`execution.results` selects where remote results land. The default `experiment`
keeps them only in `experiment/<id>/`, never over the project's files; a run
without `RAT_EXPERIMENT_ID` gets a generated ID, printed as `Experiment ID: <id>`.
Outputs keep their usual relative paths inside that folder, so read
`experiment/<id>/sim/...` where a local run writes `sim/...`, and reuse one ID for
steps that share outputs. `merge` brings results to their usual project paths and
keeps other local files; `sync` also removes local files in the fetched output
folders that the run no longer produced. Both need a Git work tree, run without an
ID in the shared remote workspace, and never overwrite or delete a sent file. Waveforms and compiled databases stay on the execution
host; logs, reports and evidence come back. Pull a remaining file into the same
folder with `eda_runner.py fetch --root <project> --experiment <id> <path>`.
Read results from `experiment/<id>/`, pass that path to report readers, and fix
sources, testbenches and scripts in the project. For a large regression, collect
the findings first, fix them in one batch, then run again with a new ID.
Experiment folders stay on the execution host until cleanup, so that results can
still be pulled. When the user asks to clean up experiments or worktrees, remove
the remote folders in the same step with
`eda_runner.py clean --root <project> --all --local` (or `--experiment <id>`);
experiments that are still running are kept. A reservation older than the exit
status of its experiment's latest run is removed only when no local dispatcher
still holds that experiment's lock. The lock is held through the result fetch,
so a finished job whose results are still coming back is kept. A crash after the
job wrote its status drops the lock, and that experiment is removed.

For parallel experiments, the coordinating agent assigns each independent
experiment a distinct `RAT_EXPERIMENT_ID` and passes it to its workers. The
coordinator manages the batch on the selected server and reuses the site's
SSH session when available. For example,
`RAT_EXPERIMENT_ID=baseline-42 bash "$PLUGIN_ROOT/scripts/run_sim.sh" --top tb -f sim/files.f`
puts generated outputs under `experiment/baseline-42/`. Keep seeds of the same
regression in one invocation when the wrapper supports it. Bound concurrency
by the site's available licenses. Keep inputs, run recipes and accepted design
decisions in Git. The experiment directory holds reproducible builds, logs,
waveforms and raw results.
Reuse an ID for sequential steps such as compile-only followed by run-only.
Concurrent use of the same ID is rejected. After a lost connection, check
whether the previous job is still running before releasing its remote reservation.
When running a custom Makefile or vendor command directly, the agent must set
its working and output directories inside the experiment. The bundled wrappers
resolve their own output directories.

Each executed command records argv, tool, timestamps, exit status, log path, and
termination reason. Execution success is a process result, not proof of a design.
Functional PASS additionally requires a recognized testbench completion result,
no failure signature, and unchanged source dependencies. Compile-only is COMPILED.
A zero exit without completion evidence is INCONCLUSIVE. Explicit timeout/hang/
stall evidence takes precedence over completion text; other nonzero exits and
failure signatures are FAIL. Preserve the log for the original diagnostics.

Evidence binds source/filelist/include hashes, build artifacts and options, and
the combined and runtime logs. Compiler output cannot supply runtime completion.
Run-only rejects changed inputs, options or build bytes. Recursive `-f`/`-F`,
include/define paths, configured `verification.include_dirs`, and UVM include
roots are resolved in the selected tool environment. This is not a full vendor
preprocessor; unsupported or unresolved filelist syntax fails with a diagnostic.
RUNNING evidence identifies the host/process and its start identity; a live local
run does not expire solely because it has exceeded an arbitrary freshness window.

Regression results are published atomically. Missing seed results and failed
coverage merges prevent PASS. Make-based source snapshots use the expanded
simulation inputs; merely completing transport does not establish verification.

Commercial goal-based tools also require goal-summary evidence. A completed Tcl
script alone does not prove that its goals passed. Unknown report formats are
INCONCLUSIVE and need a site-specific parser/pattern, not an LLM's reassurance.

License waiting is bounded by the same wall-time limit. Use a site's configured
license wait argument list; do not guess vendor flags or retry indefinitely.

## Project runners

A project's own runner (a regression script, a Makefile target, or a script that reaches
a remote simulator through rsync and SSH, LSF or a site bridge) records the same evidence
through `eda_runner.py verify-run --root <project> -f <filelist> [--source <file>]
[--log <summary file>] [--remote-host <host> --remote-root <dir>] -- <runner>`.
The runner itself is unchanged. `verify-run` hashes the inputs that `-f`/`--source`
resolve (relative paths resolve against the project root, filelist entries against the
filelist and then the root, as for every evidence record), plus the runner script itself,
so editing the runner afterwards voids the evidence. It runs the command from the project
root with the configured time limits and judges the console output. With `--log`, it
judges that summary file instead: the run must write it (its ctime changes), its mtime
must not be older than the start by more than 120 seconds (a stale copy fetched with
`rsync -a` or `cp -p` keeps its old time), and the evidence keeps a copy. Failure
signatures in either log win. Only `RAT_SIM_PASS` at the start of a line or
`TESTS=<n> PASS=<n> FAIL=0` count as completion; a bare `PASS` line or a zero exit is
INCONCLUSIVE. Commands that only print (`echo`, `printf`, `true`, ...) are refused.

When the runner executes elsewhere, `--remote-host`/`--remote-root` hash the same
project-relative inputs on that host after a successful run (`sha256sum`, else
`shasum -a 256`; no remote Python; the script goes over `ssh -o BatchMode=yes … sh -s`).
Filelists must then name project-relative paths without environment variables, as for
`dispatch`. UVM library headers under `$UVM_HOME/src` stay bound locally only, because
each host has its own installation. A missing or different file, or a failed SSH step,
makes the result INCONCLUSIVE and names the files. The transport stays the runner's;
`verify-run` neither sends files nor deletes any. The record carries `origin:
verify-run`, the command, the host and directory, the manifest hash and the local Git
commit as metadata. A commit hash names a revision; it does not prove what the remote
copy held. A plain `ssh <host> '<command>'` is a runner too.

`verification.stop_gate` selects how Rule 5 reacts to pending files: `block` (default),
`notify` (a notice, no block) or `off`. Changing it is the user's decision, like a waiver. A project `rat_config.json` owns it; without one,
the machine `env-config.json` applies. A hand-written `rat_config.json` replaces the
machine configuration as a whole, so create it with rat-init-project.

## Validation boundary

Unit tests exercise process exit propagation, timeouts, log verdicts, source
freshness, tool/environment overrides, path mapping, and remote job status using
controlled fixtures. Real Verilator checks cover functional PASS, mismatches,
empty tests and cycle timeout. Real remote/commercial qualification is scoped to
the user's site and does not establish all tool, foundry or signoff capabilities.
Keep real hostnames, connection settings and raw qualification reports outside the
plugin repository; public examples and fixtures use synthetic site data only.
