---
name: rtl-p5-verify-team
description: "Phase 5 verification using Claude Code native teams for parallel worker execution. Manages 9 verification categories with dependency-aware task graphs and module graduation gates."
user-invocable: true
argument-hint: "[--module=name | --resume]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Execute Phase 5 verification pipeline using Claude Code native team infrastructure.
Uses TeamCreate + TaskCreate + SendMessage for true parallel verification
across modules and categories, with dependency-aware task scheduling.
</Purpose>

<Use_When>
- Phase 4 RTL implementation is complete with lint passing
- User says "verify team", "Phase 5 team", "parallel verify"
- Need maximum parallelism for multi-module verification
- Have 3+ modules that benefit from concurrent verification workers
</Use_When>

<Do_Not_Use_When>
- RTL modules don't exist yet (run rtl-p4-implement first)
- Single module only (use rtl-p5-verify for simpler flow)
- Want sequential verification (use rtl-p5-verify)
- Only need a specific verification category (use the category-specific skill)
</Do_Not_Use_When>

## Prerequisites

Phase 4 completion required:
- `rtl/**/*.sv` files must exist
- `reviews/phase-4-rtl/lint-report.md` must exist (lint PASS)

If prerequisites are missing, inform the user to run `/rtl-agent-team:rtl-p4-implement` first.

## Execution

```python
# Do NOT pre-write team-config.json here — the orchestrator writes it atomically
# in Step 2 with a valid leader_session_id. This avoids race windows where
# Stop hooks see an empty leader_session_id and bypass all gates.

Task(subagent_type="rtl-agent-team:p5-verify-team-orchestrator",
     prompt="Execute Phase 5 verification using native teams. User input: $ARGUMENTS")
```

Do not perform any work directly.
The team orchestrator manages TeamCreate, team-config.json creation, task graphs,
worker spawning, module graduation, and compliance review.

## Cleanup

On completion or failure, the orchestrator removes `.rtl-agent-team/state/team-config.json`.
If the session exits abnormally, the team-config.json staleness (>2h) will prevent
it from blocking future sessions.
