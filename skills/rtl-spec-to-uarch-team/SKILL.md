---
name: rtl-spec-to-uarch-team
description: "Phase 1-3 pipeline using native teams for parallel execution within each phase. Sequences P1 research team, P2 architecture team, P3 uArch team with inter-phase quality gates."
user-invocable: true
argument-hint: "[spec-path or --resume]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Execute the Phase 1-3 design pipeline using Claude Code native team infrastructure
within each phase. Sequences through research, architecture, and uArch phases,
using team orchestrators for maximum parallelism within each phase.
</Purpose>

<Use_When>
- Starting complete design document pipeline from spec to uArch
- User says "spec to uarch team", "Phase 1-3 team", "parallel design pipeline"
- Want maximum parallelism within each design phase
</Use_When>

<Do_Not_Use_When>
- Only need a single phase (use the phase-specific team skill)
- Want sequential execution (use rtl-spec-to-uarch)
- Want to proceed through Phase 4-5 as well (use rtl-autopilot)
</Do_Not_Use_When>

## Prerequisites

No phase prerequisites (starts from Phase 1).
Specification documents should be available in `specs/` directory.

## Execution

```python
Task(subagent_type="rtl-agent-team:spec-to-uarch-team-orchestrator",
     prompt="Execute Phase 1-3 pipeline using native teams within each phase. User input: $ARGUMENTS")
```

Do not perform any work directly.
The pipeline orchestrator sequences P1-P2-P3 team orchestrators with inter-phase quality gates.
This is NOT a team itself — it spawns team orchestrators sequentially.

## Cleanup

Each phase team orchestrator handles its own team-config.json cleanup.
