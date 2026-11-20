---
name: rtl-p4-implement
description: "Phase 4 RTL from uarch with lint, review, and unit tests. Sequential or team. Use for 'implement RTL', 'write RTL', 'Phase 4 team'."
user-invocable: true
argument-hint: "[module-list or --all | team]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate
---

Implement the requested modules from the P3 microarchitecture. Use
`rtl-p4s-bugfix` for a single bug and `rtl-p4-rapid-impl` for a rapid sanity check.

## Mode

Team mode when `$ARGUMENTS` contains the word `team`, or the user asked for a team, parallel workers, or `rtl-p4-implement-team`. Otherwise sequential.
Use the host's delegation and model selection from `{plugin_root}/runtime/model-selection.md`.
Forward the request and its cross-review choice per `{plugin_root}/runtime/phase-dispatch.md`.

## Prerequisites

Phase 3 completion required:
- At least one μArch spec in `docs/phase-3-uarch/` must exist

If prerequisite is missing: WARNING — recommend running `/rtl-agent-team:rtl-p3-uarch-design`.
Proceed with available artifacts — orchestrator will adapt scope.

## Sequential

Task(subagent_type="rtl-agent-team:p4-implement-orchestrator",
     prompt="Execute Phase 4 RTL implementation. User input: $ARGUMENTS")

## Team mode

Read `{plugin_root}/runtime/workflows/team-leader.md` from the plugin installation.
Use team `p4-implement`, phase `p4`, and coordinator `rtl-agent-team:p4-implement-orchestrator`.
Pass `$ARGUMENTS` through. On Claude Code, the leader session for the spawn manifest is `${CLAUDE_SESSION_ID}`.

## Compliance Notes

Derive module test expectations from the uArch spec. At handoff, trace lint, functional
unit results, synthesizability and applicable integration checks to P1–P3 iron requirements.

## Output

- `rtl/*/*.sv` — lint-clean SystemVerilog modules
- `sim/*/tb_*.sv` — per-module unit test testbenches
- `docs/phase-4-rtl/` — Stream B design documents and implementation summary
- `reviews/phase-4-rtl/` — lint reports, code review reports, and gate results
