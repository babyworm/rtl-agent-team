---
name: p2-arch-design
description: "Phase 2 architecture, sequential or team. Use for 'architecture design', 'Phase 2', 'block design', 'arch team', 'parallel architecture'."
user-invocable: true
argument-hint: "[--resume | architecture-focus | team]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate
---

Design the block architecture and a runnable C reference model from P1 requirements.
Use `arch-review` for an existing architecture, `rat-dse` for requested design exploration,
or `ref-model` for the reference model alone.

## Mode

Team mode when `$ARGUMENTS` contains the word `team`, or the user asked for a team, parallel workers, or `rtl-p2-arch-team`. Otherwise sequential. `--resume` stays sequential unless team mode also applies.
Use the host's delegation and model selection from `{plugin_root}/runtime/model-selection.md`.
Forward the request and its cross-review choice per `{plugin_root}/runtime/phase-dispatch.md`.

## Prerequisites

Phase 1 completion required:
- `docs/phase-1-research/iron-requirements.json` must exist
- `docs/phase-1-research/open-requirements.json` (optional — absent if P1 had no open items)
- `docs/phase-1-research/io_definition.json` must exist

If prerequisites are missing: WARNING — recommend running `/rtl-agent-team:p1-spec-research`.
Proceed with available artifacts — orchestrator will adapt scope.

## Sequential

Task(subagent_type="rtl-agent-team:p2-arch-orchestrator",
     prompt="Execute Phase 2 architecture design. With --resume, continue from docs/phase-2-architecture/ and reviews/phase-2-architecture/. User input: $ARGUMENTS")

## Team mode

Read `{plugin_root}/runtime/workflows/team-leader.md` from the plugin installation.
Use team `p2-arch`, phase `p2`, and coordinator `rtl-agent-team:p2-arch-orchestrator`.
Pass `$ARGUMENTS` through. On Claude Code, the leader session for the spawn manifest is `${CLAUDE_SESSION_ID}`.

## Workflow Notes

- Open Resolution: resolve all OPEN-1-* items from Phase 1 `open-requirements.json`
- Compliance Check: verify REQ-A-* architecture requirements against P1 iron requirements
- Exit gate includes `open-resolved`, `compliance-pass`, and `ambiguity-pass`
