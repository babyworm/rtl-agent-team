# LLM-assisted site setup

The user supplies the intended SSH execution host. Resolve existing project
configuration and named site profiles first. Discover missing facts with the
helper; do not ask the user to transcribe tool paths or author JSON. Keep SSH
credentials, jump hosts and connection options in the user's SSH configuration.
Never disable host-key checking or copy credentials into a profile.

Use the current project as PROJECT_ROOT and the installed plugin as PLUGIN_ROOT.
SITE_PROFILE is a named JSON file under the user's private plugin-data `sites/`
directory, outside the plugin repository. Store raw probe/qualification reports
in that private data directory too. Never copy real hostnames, connection settings
or environment reports into plugin source, docs, examples, tests or evals.
SSH_HOST comes from the user, not this reference.

```bash
"$RAT_PYTHON" "$PLUGIN_ROOT/scripts/eda_setup.py" discover --host "$SSH_HOST" --output "$SITE_PROFILE"
```

Pass `--env-script "$SETUP_SCRIPT" --env-shell tcsh` for a shared tcsh script on
the execution host. The shell defaults to bash. `--config "$PROJECT_ROOT/rat_config.json"`
preserves explicit paths and per-tool `env_source` overrides. The helper selects
remote Python >=3.9 and resolves known binaries in the sourced PATH.

Discovery automatically runs bounded startup checks and tiny simulations for
Xcelium and VCS. Each tool reports `setup_status` and any measured `probe`.
`command_passed` records startup evidence. `workload_passed` requires the task's
completion output. `probe.license_checked` applies only to the measured workload.
Use `--probe-timeout` to override the 8-second limit per check, or `--paths-only`
for inventory. SSH/LSF discovery measures the SSH host. Scheduler and signoff
qualification use their actual execution paths.

For a site-specific check, add `setup_check` to the tool's private configuration.
Set `args` to the tool's argument array and `expected_line` to its exact completion
output. Set `licensed` to `true` when the configured workload exercises the
license feature to be checked. Other tools without a known check report `unchecked`.

Choose the requested tools from the evidence and existing preferences. To
diagnose an individual tool, use its documented/site-verified arguments:

```bash
"$RAT_PYTHON" "$PLUGIN_ROOT/scripts/eda_setup.py" probe --profile "$SITE_PROFILE" --tool simulators.xrun --record --output "$PROBE_RESULT" -- -version
```

This Xcelium example is conditional on selecting Xcelium. Other tools use their
own verified arguments. Preserve failed diagnostics, including loader errors from
a launcher that exits zero. `--record` stores the probe in the profile; automatic
preference selection excludes that failed candidate. A successful version probe
remains command evidence with `license_checked: false`.

Prepare and apply the configuration within the user's authorized setup request:

```bash
"$RAT_PYTHON" "$PLUGIN_ROOT/scripts/eda_setup.py" configure --profile "$SITE_PROFILE" --root "$PROJECT_ROOT" --dry-run
"$RAT_PYTHON" "$PLUGIN_ROOT/scripts/eda_setup.py" configure --profile "$SITE_PROFILE" --root "$PROJECT_ROOT"
bash "$PLUGIN_ROOT/skills/rat-init-project/scripts/generate_config.sh" "$PROJECT_ROOT"
"$RAT_PYTHON" "$PLUGIN_ROOT/scripts/eda_runner.py" capabilities --root "$PROJECT_ROOT" --phase "$RAT_PHASE" --probe-remote
```

Use `--prefer simulator=xrun` (or another discovered suitable tool) for an intended
preference change. Existing explicit paths, environment commands, output selections,
technology values and preferences are preserved. A preserved override that differs
from discovery is not marked detected; probe that exact configuration before using
it. Conflicting existing site ownership needs a concrete decision before switching.

`--workspace` selects a known absolute project directory on the remote host. When
none is supplied, configure proposes a private per-project directory below the
measured remote home; its local-root hash prevents two projects sharing a basename
from overwriting each other. `--backend lsf` selects LSF with a verified scheduler/queue;
preserve the selected LSF backend rather than assuming every SSH host uses LSF.

Reuse the smoke result for basic simulator setup. When the requested framework or
phase still needs qualification, run the smallest relevant operation through the
installed wrapper and preserve its evidence. For synthesis/signoff, use the actual
technology library and constraints. Keep
missing libraries, unsupported tool versions, license failures and undefined
requirements open. Setup smoke evidence is not verification of the user's design.
Save the readiness scope and results, reuse them until an affected setting changes,
and report the configured site, working tools and remaining issues concisely.
