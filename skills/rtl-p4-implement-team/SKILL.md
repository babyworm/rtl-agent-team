---
name: rtl-p4-implement-team
description: "Phase 4 RTL implementation using Claude Code native teams for parallel worker execution. Manages 10-wave pipeline with per-module parallelism and inter-wave dependency graphs."
user-invocable: true
argument-hint: "[module-list or --all]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Execute Phase 4 RTL implementation pipeline using Claude Code native team infrastructure.
Uses TeamCreate + TaskCreate + SendMessage for true parallel module implementation
with 10-wave dependency-aware task scheduling.
</Purpose>

<Use_When>
- Phase 3 uArch specs are complete and RTL coding is needed
- User says "implement team", "Phase 4 team", "parallel implement"
- Have 3+ modules that benefit from concurrent RTL coding workers
- Need maximum parallelism for multi-module RTL implementation
</Use_When>

<Do_Not_Use_When>
- Phase 3 uArch specs are not complete (run rtl-p3-uarch-design first)
- Single module only (use rtl-p4-implement for simpler flow)
- Only need a single module bug fix (use rtl-p4s-bugfix)
- Need RTL + verification together from uarch (use rtl-uarch-to-verify)
</Do_Not_Use_When>

## Prerequisites

Phase 3 completion required:
- At least one uArch spec in `docs/phase-3-uarch/` must exist

If prerequisite is missing, inform the user to run `/rtl-agent-team:rtl-p3-uarch-design` first.

## Execution

```python
# Do NOT pre-write team-config.json here — the orchestrator writes it atomically
# in Step 2 with a valid leader_session_id. This avoids race windows where
# Stop hooks see an empty leader_session_id and bypass all gates.

Task(subagent_type="rtl-agent-team:p4-implement-team-orchestrator",
     prompt="Execute Phase 4 RTL implementation using native teams. User input: $ARGUMENTS")
```

Do not perform any work directly.
The team orchestrator manages TeamCreate, team-config.json creation, 10-wave task graphs,
worker spawning, per-module progress tracking, and phase gate verification.

## Cleanup

On completion or failure, the orchestrator removes `.rtl-agent-team/state/team-config.json`.
