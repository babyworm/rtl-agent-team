---
name: rtl-p3-uarch-team
description: "Phase 3 uArch design using Claude Code native teams for parallel dual-stream uArch + BFM development. Manages per-block uarch design, BFM validation gate, and 5-reviewer 3-round iterative review."
user-invocable: true
argument-hint: "[--resume]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Execute Phase 3 uArch design pipeline using Claude Code native team infrastructure.
Uses TeamCreate + TaskCreate + SendMessage for true parallel uArch design
and BFM development with dependency-aware task scheduling.
</Purpose>

<Use_When>
- Phase 2 architecture is complete and uArch design is needed
- User says "uarch team", "Phase 3 team", "parallel uarch"
- Have multiple modules requiring parallel uarch design
- Need maximum parallelism for dual-stream uArch + BFM development
</Use_When>

<Do_Not_Use_When>
- Phase 2 architecture not complete (run p2-arch-design first)
- Single module only (use rtl-p3-uarch-design for simpler flow)
- Only need BFM (use bfm-develop)
</Do_Not_Use_When>

## Prerequisites

Phase 2 completion required:
- `docs/phase-2-architecture/architecture.md` must exist
- `refc/` directory with C reference model must exist

If prerequisites are missing, inform the user to run `/rtl-agent-team:p2-arch-design` first.

## Execution

```python
# Do NOT pre-write team-config.json here — the orchestrator writes it atomically
# in Step 2 with a valid leader_session_id.

Task(subagent_type="rtl-agent-team:p3-uarch-team-orchestrator",
     prompt="Execute Phase 3 uArch design using native teams. User input: $ARGUMENTS")
```

Do not perform any work directly.
The team orchestrator manages TeamCreate, team-config.json creation, dual-stream task graphs,
BFM validation gate, 5-reviewer review rounds, and artifact finalization.

## Cleanup

On completion or failure, the orchestrator removes `.rtl-agent-team/state/team-config.json`.
