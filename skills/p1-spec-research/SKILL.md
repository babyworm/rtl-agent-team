---
name: p1-spec-research
description: "Phase 1 spec research, sequential or team. Triggers: 'research', 'spec analysis', 'Phase 1', 'research team', 'parallel research'."
user-invocable: true
argument-hint: "[spec-file or project-description | team]"
allowed-tools: Read, Write, Edit, Task, Grep, Glob, AskUserQuestion, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate
---

Turn the supplied specification or idea into requirements and I/O definitions for P2.
Use `domain-consult` for a standalone domain question.

## Mode

Team mode when `$ARGUMENTS` contains the word `team`, or the user asked for a team, parallel workers, or `rtl-p1-research-team`. Otherwise sequential.
Use the host's delegation and model selection from `{plugin_root}/runtime/model-selection.md`.
Forward the request and its cross-review choice per `{plugin_root}/runtime/phase-dispatch.md`.

<Phase_Workflow>
Use the supplied specification or seed directly when its intended behavior is
settled. Invoke goal-clarifier only for material unanswered questions about behavior,
interfaces, constraints, or expected verification results. Length and keywords do
not determine whether a spec is complete. Produce iron/open requirements and ask
one focused question when an actual user decision is missing.
</Phase_Workflow>

<Assets>
| Path | Role |
|------|------|
| `scripts/score_ambiguity.py` | Pure stdlib helper for 4-dimension scoring + ambiguity %. Goal-clarifier calls it once. |
| `templates/goal.md` | Output skeleton for `docs/phase-1-research/goal.md`. |
| `references/goal-dimensions.md` | 4-dimension scoring rubric + question seeds + anti-patterns. |
</Assets>

## Prerequisites

None — this is the first phase entry point.
Specification documents should be available in `specs/` directory.

## Sequential

Task(subagent_type="rtl-agent-team:p1-research-orchestrator",
     prompt="Execute Phase 1 spec research. User input: $ARGUMENTS")

## Team mode

Read `{plugin_root}/runtime/workflows/team-leader.md` from the plugin installation.
Use team `p1-research`, phase `p1`, and coordinator `rtl-agent-team:p1-research-orchestrator`.
Pass `$ARGUMENTS` through. On Claude Code, the leader session for the spawn manifest is `${CLAUDE_SESSION_ID}`.

## Output Artifacts

- `docs/phase-1-research/iron-requirements.json` — settled functional/performance requirements (REQ-F-*, REQ-P-*)
- `docs/phase-1-research/open-requirements.json` — research topics deferred to Phase 2 (OPEN-1-*)
- `docs/phase-1-research/io_definition.json` — I/O interface definitions
- Classification verification step confirms each requirement is tagged as either iron (acceptance_criteria defined) or open (research_needed).
