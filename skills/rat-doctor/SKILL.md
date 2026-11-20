---
name: rat-doctor
description: "Check plugin and project settings in a ✓/?/✗ table and fix what is wrong. Triggers: 'rat doctor', 'diagnostics', 'plugin status', 'settings check'."
user-invocable: true
argument-hint: "[--offline]"
allowed-tools: Bash, Read, Edit, Glob, Grep, AskUserQuestion, Skill
---

<Purpose>
Show the effective plugin and project settings when something behaves oddly after
setup, mark each item, and help the user fix the wrong ones. Marks: ✓ verified,
? unverified or worth attention, ✗ wrong, – not applicable.
</Purpose>

<Use_When>
- The plugin or an EDA run behaves unexpectedly after setup
- The user asks for a doctor, diagnostics, plugin status or a settings check
</Use_When>

<Do_Not_Use_When>
- First-time tool setup: use /rtl-agent-team:rat-setup
- Creating the project layout: use /rtl-agent-team:rat-init-project
</Do_Not_Use_When>

## Steps

1. Run the checks from the project root. `--live` makes one SSH connection to the
   execution host and tests the remote library path; it never starts a licensed
   tool. Drop it when the user asks for an offline check.

```bash
root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/rat_doctor.py" --root "$root" --live
```

   Exit status 1 means at least one ✗.

2. Show the table as printed. Below it, list the ✗ items, then the ? items, one line
   each with what goes wrong if it is left alone.

3. If any listed item has a fix, ask once which fixes to apply (multi-select, one
   option per item). Change nothing before that answer. Apply only the chosen ones:
   - "restart Claude Code": tell the user; nothing else applies in this session.
   - `/rtl-agent-team:rat-setup` fixes: invoke that skill with the item as the goal,
     for example "run a licensed workload probe for xrun" or "measure site X again".
   - Legacy forwarders: remove exactly the listed paths, each only after
     `readlink -f` shows it resolves to `rat-ssh`.
   - Old settings folder: move `env-config.json` and `sites/` into the listed
     settings folder only when the target does not already have them.
   - Remote result landing: when the user wants another mode, ask which one
     (`experiment` default, `merge`, `sync`) and set `execution.results` in the
     project `rat_config.json`.
   - Project values such as `technology.db`: ask for the correct value and edit the
     project `rat_config.json`. Change a site profile only when the user says the
     value applies to every project on that site.

4. Run the checks again and show the new table. Report the remaining ? items with
   the step that would verify each, then stop.

The table shows host names and paths from private settings. Keep it in this
conversation; never copy it into project or plugin files.
