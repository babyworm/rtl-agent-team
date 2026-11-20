---
name: rat-setup
description: "Verify phase-specific EDA capabilities and configure local, Docker, SSH or LSF tools. Triggers: 'setup tools', 'EDA setup', 'install tools'."
user-invocable: true
---

Set up the capabilities required by the requested phase. Use the current project
configuration and the user's chosen execution host. Do not require every known tool
or an open-source replacement for a working commercial tool.

## Execution site

Use the user's named host and existing project/site configuration before local
detection. A request naming an SSH host is enough to start bounded SSH
discovery and prepare that site's configuration; do not ask for already supplied
information. If the execution target cannot be inferred, ask only that question
and continue independent setup work.

For SSH/LSF setup, read `references/remote-site-setup.md`. The discovery/configure
CLI handles measured host facts and safe JSON updates; use judgment for the desired
tools, site environment and unresolved choices. Keep named reusable profiles under
`${CLAUDE_PLUGIN_DATA}/sites/`. Select a profile for
each project; never make one user's host a plugin-wide default.
Keep real site profiles, connection details and raw probe reports outside the
plugin repository. Never copy them into plugin docs, examples, tests or evals;
use synthetic site data in reusable sources.

Use `eda_setup.py discover` for automatic PATH and bounded tool checks. Pass the
user's setup script with `--env-script` and its shell with `--env-shell`. Report
each tool's `setup_status` and `probe.license_checked` from the private profile.
Refresh a path-only profile when it has no execution results. Reuse measured
results during setup. Complete phase-specific qualification for the requested flow.

## Discovery and readiness

Resolve plugin_root from the skill location. Select Python >=3.9 using
`{plugin_root}/hooks/lib/python-util.sh` (`rat_select_python`); honor RAT_PYTHON.
Generate or refresh project detection while preserving user configuration:

```bash
source "$PLUGIN_ROOT/hooks/lib/python-util.sh"
RAT_PYTHON=$(rat_select_python)
export RAT_PYTHON
bash "$PLUGIN_ROOT/skills/rat-init-project/scripts/generate_config.sh" "$PROJECT_ROOT"
"$RAT_PYTHON" "$PLUGIN_ROOT/scripts/eda_runner.py" capabilities --root "$PROJECT_ROOT" --phase "$RAT_PHASE"
```

On a local host, use the same discovery/configure commands as the remote setup
reference, omitting `--host`. For Docker, measure within the selected image.

Phases: p1 needs no EDA tools; p2/p3 need a C/C++ build toolchain; p4/p5a need a
simulator and linter; p5b needs synthesis. `--phase all` checks that combined set.
Add `--bfm` when the requested SystemC/TLM BFM needs SystemC, `--multiclock` for
CDC analysis, and `--signoff` for PrimeTime plus technology.db. Use `--framework
cocotb` or `--framework uvm` when specified; auto requires cocotb only for the
open-source functional path. An SV-only testbench can select `--framework sv`
for framework-independent simulator readiness.

Report the requested scope, measured capabilities, and missing dependencies.
A locally detected binary does not establish remote readiness, a license, or a
successful signoff run. Remote capabilities stay `remote_unprobed` unless
`--probe-remote` measures the configured host. That measures paths/frameworks,
not license checkout or signoff. Docker CLI presence is transport availability only; run
probes inside the selected image before declaring container tool readiness.

Read only the relevant reference:
- `references/tool-check-commands.md` for additional vendor/version probes.
- `references/install-commands.md` for a missing dependency the user wants installed.
- `references/docker-environment.md` when Docker is selected.

## Configuration

`rat_config.json` is consumed by the execution runner. Each tools category entry
supports `path`, `env_source`, `env_shell` (`bash`, `csh`, `tcsh`), and an explicit
`license_wait_args` array. Use the site's verified vendor arguments; do not guess
universal license-wait flags. The runner's timeout bounds the complete invocation.

Preferences choose one suitable simulator, synthesis, lint, formal, CDC and
equivalence tool. Functional verification uses UVM with commercial simulators and
cocotb with the selected open-source simulator, unless the user chooses otherwise.
STA is configured under `tools.sta.pt_shell`; power under tools.power (pwr_shell,
joules, voltus, powerpro). technology.saif records the simulation activity handoff.
technology.liberty is the text library, technology.db is the compiled DC/PrimeTime
library. Preserve explicit nand2_area_um2; derive it only when unset.

For Python packages, use a dedicated RAT_EDA_VENV rather than system pip; the exact installation commands are in `references/install-commands.md`.

Machine defaults live at `${CLAUDE_PLUGIN_DATA}/env-config.json`. Bash commands see
this plugin data folder as `$RAT_DATA_DIR`; never store settings elsewhere.
The project overrides them. Remote host paths are not replaced by local detection.
When the user names a default execution site, set `default_site` there to its
profile name. Without a project config, the bundled runner reads the private
settings directly. Agents can query individual keys with `eda_runner.py get
--root <project> --key preferences.simulator` before project initialization.
A profile's `technology` values fill unset fields during project configuration.
Use execution.backend local/docker/ssh/lsf and the execution contract in
`{plugin_root}/runtime/eda-runner-contract.md` for site setup.

## Remediation and completion

Complete any installation/configuration already authorized by the user. Otherwise
present the concrete missing capability and available remediation before making
machine-level changes. Use a user-local environment by default. Preserve existing
configuration and do not edit global agent instructions as part of EDA setup.

Recheck only affected capabilities after a change. Save the readiness scope and
actual result under `.rat/state/setup-capabilities.json`; mark project setup
complete only for that scope. Report unavailable remote or licensed checks as
unmeasured. Do not run another successful check merely to increase confidence.
