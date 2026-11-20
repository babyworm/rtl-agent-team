---
name: codex-cross-review
description: "One independent Codex review of completed phase artifacts when requested or enabled for the project."
user-invocable: true
argument-hint: "[phase number or auto]"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Task, AskUserQuestion
---

Review the named phase. Use the current deliverables to identify the phase if
omitted; ask once if more than one phase fits. Pipeline calls follow
`{plugin_root}/runtime/phase-dispatch.md`.

Follow `{plugin_root}/runtime/model-selection.md` to delegate the reviewer role
on the current host, or use the bundled role in this session if delegation is unavailable. The
independent review itself runs in a fresh, read-only Codex CLI session on every
host. Forward any explicit reviewer model choice.

```
Task(subagent_type="rtl-agent-team:codex-cross-reviewer",
     prompt="Review phase {N} in {project_root}. Scope: {request}. Artifacts: {paths}.")
```

Return the findings, any decisions still needed, and the phase-scoped
`.rat/cross-review/phase-{N}/cross-review-report.md`.
