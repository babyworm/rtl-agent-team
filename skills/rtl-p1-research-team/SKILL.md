---
name: rtl-p1-research-team
description: "Phase 1 research using Claude Code native teams for parallel tree-of-thought exploration. Manages solution tree construction, parallel candidate deep-dive, sub-domain expert coordination, and 3-round chief review."
user-invocable: true
argument-hint: "[spec-path or --resume]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Execute Phase 1 research pipeline using Claude Code native team infrastructure.
Uses TeamCreate + TaskCreate + SendMessage for true parallel solution tree exploration
with dependency-aware task scheduling across domain experts.
</Purpose>

<Use_When>
- Starting a new RTL design from specification
- User says "research team", "Phase 1 team", "parallel research"
- Have complex spec requiring multi-expert parallel analysis
- Need maximum parallelism for tree-of-thought candidate exploration
</Use_When>

<Do_Not_Use_When>
- Simple single-domain design (use p1-spec-research for simpler flow)
- Already have Phase 1 artifacts complete (proceed to Phase 2)
- Only need domain consultation (use domain-consult)
</Do_Not_Use_When>

## Prerequisites

No phase prerequisites (this is the first phase).
Specification documents should be available in `specs/` directory.

## Execution

```python
# Do NOT pre-write team-config.json here — the orchestrator writes it atomically
# in Step 2 with a valid leader_session_id. This avoids race windows where
# Stop hooks see an empty leader_session_id and bypass all gates.

Task(subagent_type="rtl-agent-team:p1-research-team-orchestrator",
     prompt="Execute Phase 1 research using native teams. User input: $ARGUMENTS")
```

Do not perform any work directly.
The team orchestrator manages TeamCreate, team-config.json creation, solution tree task graphs,
worker spawning, dynamic candidate tasks, chief review rounds, and artifact generation.

## Cleanup

On completion or failure, the orchestrator removes `.rtl-agent-team/state/team-config.json`.
