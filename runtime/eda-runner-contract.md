# EDA execution contract

This supplies the execution contract missing from the original v2 roadmap.
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
Transport synchronizes the project once, excluding Git, agent worktrees, audit
data, and local execution state. It installs the wrapper and runtime helpers in a
private remote runtime directory, runs from the remote workspace, and retrieves
only declared outputs. No rsync deletion is used.

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
submission output and cancels its own uniquely named job on timeout.

## Results

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

## Validation boundary

Unit tests exercise process exit propagation, timeouts, log verdicts, source
freshness, tool/environment overrides, path mapping, and remote job status using
controlled fixtures. Real Verilator checks cover functional PASS, mismatches,
empty tests and cycle timeout. Real remote/commercial qualification is scoped to
the user's site and does not establish all tool, foundry or signoff capabilities.
Keep real hostnames, connection settings and raw qualification reports outside the
plugin repository; public examples and fixtures use synthetic site data only.
