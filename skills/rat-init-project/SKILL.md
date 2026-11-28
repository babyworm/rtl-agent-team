---
name: rat-init-project
description: "Initialize or update an RTL project: directories, rules, guides, configuration, and runner templates. Use for project setup or template updates."
user-invocable: true
argument-hint: "[--update | --dry-run]"
---

# Initialize or update the project

Prepare the user's project workspace for the RTL pipeline. Preserve user content.
An explicit initialization or update request authorizes this work; do not ask again.
If another skill discovered missing setup and the user has not authorized project
initialization, explain the proposed changes before installing them.

## Inputs and boundaries

Run commands from the user's project root. Claude Code substitutes the installed
skill path for `${CLAUDE_SKILL_DIR}` in the commands below. On other hosts, set
`RAT_INIT_SKILL_DIR` to the absolute directory of the discovered SKILL.md in
each shell call. Quote the resolved path, including spaces.
The scripts locate all other bundled resources relative to themselves.

Non-destructive installation creates missing templates. `--update` replaces only
an unchanged managed copy with an older version. User-modified or unrecognized
copies remain intact; proposed replacements go to `.rat/template-updates/`.
`--dry-run` lists proposed template changes without writing project files.

## Template installation

First preview the requested operation:

```bash
bash "${RAT_INIT_SKILL_DIR:-${CLAUDE_SKILL_DIR}}/scripts/install_project_templates.sh" --dry-run "$PWD"
```

For an authorized new setup, install:

```bash
bash "${RAT_INIT_SKILL_DIR:-${CLAUDE_SKILL_DIR}}/scripts/install_project_templates.sh" "$PWD"
```

For a template update, pass `--update` to both preview and install. When the user
requested only `--dry-run`, stop after the preview without modifying the project.
The installer owns scripts, the root Makefile, rules, and directory CLAUDE.md guides.
Hooks do not install these files. Do not repeat the copying steps manually.

## Project structure and configuration

For a new setup, create missing directories for specs/, refc/, bfm/, rtl/, sim/,
lint/, syn/, docs/, reviews/, .rat/state/, and .rat/scratch/. Phase artifacts belong
in `docs/phase-N-*/` and `reviews/phase-N-*/`; source and test module directories are
created when the design defines them. Do not generate dummy RTL or invent a module
partition merely to populate an empty directory.

Create or refresh the managed project configuration:

```bash
skill_dir="${RAT_INIT_SKILL_DIR:-${CLAUDE_SKILL_DIR}}"
bash "$skill_dir/scripts/inject_claude_md.sh" .
bash "$skill_dir/scripts/generate_config.sh" . "$(basename "$PWD")"
```

`inject_claude_md.sh` changes only the RAT block in root CLAUDE.md. The configuration
generator refreshes tool detection and config.mk while preserving user configuration
and usable explicit tool paths. `rat_config.json` holds tool preferences, trusted
per-tool environment setup, technology libraries, coverage targets, and waivers.
Report missing settings that affect the requested phase; do not fabricate them.
When the user named an SSH host or reusable site profile, use the site discovery
and configuration flow in `/rtl-agent-team:rat-setup` before claiming tool readiness.
Reuse known host facts; ask only for a choice that remains unresolved.

Use the bundled filelist, cocotb Makefile, and Phase 6 PDF Makefile templates only
where the corresponding project file is missing. On a remote site, remote results
land in `experiment/<id>/` unless the user asks for `execution.results` merge or sync. The installer provides a Git
ignore rule under `experiment/` for generated runs. Preserve existing filelists.
The installer skips a local rule when the same rule exists in `~/.claude/rules/`.
If `<markdown_diagram_rule>` is absent from `~/.claude/CLAUDE.md`, keep the document
figure policy from the installed docs/ and reviews/ guides; do not add a duplicate
universal drawing tutorial.

To enable Codex review at phase handoffs, set `review.codex_cross_review` to true in the project-root `rat_config.json`. It defaults to false.

## Tool readiness and completion

On Claude Code, `${CLAUDE_PLUGIN_DATA}/.setup-complete` records plugin
setup. A missing marker is advisory: recommend `/rtl-agent-team:rat-setup` when tools
need installation, and continue project initialization with the available tools.

Report what was created, updated, preserved, or staged for review, and any missing
phase prerequisites. Cite installer/configuration results. Completion means the
requested workspace artifacts exist, user content is preserved, and unresolved
configuration is stated. Do not run design reviews or repeated readiness checks.

Treat an existing rat_config.json as trusted project input. Refresh only stale or unusable detection paths; preserve explicit remote-host paths, preferences, and
user-entered technology values.
