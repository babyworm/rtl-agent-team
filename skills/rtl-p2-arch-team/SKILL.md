---
name: rtl-p2-arch-team
description: "Phase 2 architecture design using Claude Code native teams for parallel dual-stream architecture + RefC development. Manages HW candidate evaluation, parallel design streams, and 3-round iterative review with tree exploration."
user-invocable: true
argument-hint: "[--resume]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Execute Phase 2 architecture design pipeline using Claude Code native team infrastructure.
Uses TeamCreate + TaskCreate + SendMessage for true parallel architecture design
and reference model development with dependency-aware task scheduling.
</Purpose>

<Use_When>
- Phase 1 research is complete and architecture design is needed
- User says "arch team", "Phase 2 team", "parallel architecture"
- Have multiple algorithm candidates requiring parallel HW evaluation
- Need maximum parallelism for dual-stream arch + RefC development
</Use_When>

<Do_Not_Use_When>
- Phase 1 research not complete (run p1-spec-research first)
- Single candidate only (use p2-arch-design for simpler flow)
- Only need reference model (use ref-model)
</Do_Not_Use_When>

## Prerequisites

Phase 1 completion required:
- `docs/phase-1-research/requirements.json` must exist
- `docs/phase-1-research/io_definition.json` must exist

If prerequisites are missing, inform the user to run `/rtl-agent-team:p1-spec-research` first.

## Execution

```python
# Do NOT pre-write team-config.json here — the orchestrator writes it atomically
# in Step 2 with a valid leader_session_id.

Task(subagent_type="rtl-agent-team:p2-arch-team-orchestrator",
     prompt="Execute Phase 2 architecture design using native teams. User input: $ARGUMENTS")
```

Do not perform any work directly.
The team orchestrator manages TeamCreate, team-config.json creation, dual-stream task graphs,
worker spawning, review round management, and artifact finalization.

## Cleanup

On completion or failure, the orchestrator removes `.rtl-agent-team/state/team-config.json`.
