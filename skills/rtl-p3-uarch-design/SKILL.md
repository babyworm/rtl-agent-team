---
name: rtl-p3-uarch-design
description: "Phase 3 uArch, sequential or team: clock domains, FSM/SRAM, BFM. Use for 'uarch', 'microarchitecture', 'Phase 3', 'uarch team'."
user-invocable: true
argument-hint: "[--resume | uarch-focus | team]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate
---

Translate the accepted P2 architecture into implementable module specifications
and validate the BFM against the C reference model. Use `bfm-develop` for BFM-only work.

## Mode

Team mode when `$ARGUMENTS` contains the word `team`, or the user asked for a team, parallel workers, or `rtl-p3-uarch-team`. Otherwise sequential.
Use the host's delegation and model selection from `{plugin_root}/runtime/model-selection.md`.
Forward the request and its cross-review choice per `{plugin_root}/runtime/phase-dispatch.md`.

## Prerequisites

Phase 2 completion required:
- `docs/phase-2-architecture/architecture.md` must exist
- `refc/` directory with C reference model must exist

If prerequisites are missing: WARNING — recommend running `/rtl-agent-team:p2-arch-design`.
Proceed with available artifacts — orchestrator will adapt scope.

## Sequential

Task(subagent_type="rtl-agent-team:p3-uarch-orchestrator",
     prompt="Execute Phase 3 uArch design. User input: $ARGUMENTS")

## Team mode

Read `{plugin_root}/runtime/workflows/team-leader.md` from the plugin installation.
Use team `p3-uarch`, phase `p3`, and coordinator `rtl-agent-team:p3-uarch-orchestrator`.
Pass `$ARGUMENTS` through. On Claude Code, the leader session for the spawn manifest is `${CLAUDE_SESSION_ID}`.

## Workflow Notes

- Open Resolution: resolve all OPEN-2-* items from Phase 2 `open-requirements.json`
- Zero-Opens Invariant: no unresolved OPEN-* items may pass to Phase 4
- Compliance Check: verify REQ-U-* uarch requirements against P1+P2 iron requirements
- Exit gate includes `open-resolved`, `zero-remaining-opens`, `compliance-pass`, and `ambiguity-pass`

At handoff, each iron REQ-U-* needs observable `acceptance_criteria` for the
phase gate. Legacy criteria without `ac_id` retain requirement-level traceability.
Report any Critical/High P1 REQ-F-* or P2 REQ-A-* missing a downstream `traces_to`
link as an advisory. Record the rationale for intentional omissions.
