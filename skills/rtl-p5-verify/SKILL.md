---
name: rtl-p5-verify
description: "Phase 5 legacy bundled verification, sequential or team. Triggers 'verify', 'Phase 5', 'verify team'. New flows: prefer split P5A/P5B."
user-invocable: true
argument-hint: "[--module=name | --stage=N | --resume | team]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate
---

Run bundled P5 module, integration and final compliance checks. For a new split flow,
use `rtl-p5a-functional-closure` followed by `rtl-p5b-silicon-validation`.
For functional regression alone, use `rtl-p5s-func-verify`.

## Mode

Team mode when `$ARGUMENTS` contains the word `team`, or the user asked for a team, parallel workers, or `rtl-p5-verify-team`. Otherwise sequential.
Use the host's delegation and model selection from `{plugin_root}/runtime/model-selection.md`.
Forward the request and its cross-review choice per `{plugin_root}/runtime/phase-dispatch.md`.

## Prerequisites

Phase 4 completion required:
- `rtl/**/*.sv` files must exist
- One of the following completion proofs must exist:
  - `reviews/phase-4-rtl/lint-report.md` (full `rtl-p4-implement` path)
  - `.rat/state/p4-state.json` with `gates.p4_exit.verdict` = `pass` (rapid `rtl-p4-rapid-impl` path)

If prerequisites are missing: WARNING — recommend running `/rtl-agent-team:rtl-p4-rapid-impl`
or `/rtl-agent-team:rtl-p4-implement`. Proceed with available artifacts — orchestrator will adapt scope.

## Sequential

Task(subagent_type="rtl-agent-team:p5-verify-orchestrator",
     prompt="Execute Phase 5 verification. User input: $ARGUMENTS")

## Team mode

Read `{plugin_root}/runtime/workflows/team-leader.md` from the plugin installation.
Use team `p5-verify`, phase `p5`, and coordinator `rtl-agent-team:p5-verify-orchestrator`.
Pass `$ARGUMENTS` through. On Claude Code, the leader session for the spawn manifest is `${CLAUDE_SESSION_ID}`.

## Compliance Notes

- Verification must confirm all iron requirement `acceptance_criteria` are met.
  When structured acceptance_criteria (with ac_id) exist from P3, verification
  tracks compliance at the individual criterion level (ac_id granularity).
  When acceptance_criteria is in string-array format (P1/P2), verification
  operates at REQ level.
- Final compliance check compares test results against P1+P2+P3 `acceptance_criteria`
- Phase 5 PASS requires zero unmet iron requirements across all verification categories

## Output

- `reviews/phase-5-verify/` — reports for applicable verification categories (lint, formal, CDC, protocol, functional, coverage, performance, synthesis, code review)
- `reviews/phase-5-verify/final-compliance.md` — overall PASS/FAIL verdict with requirement traceability
