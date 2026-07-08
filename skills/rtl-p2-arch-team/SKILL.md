---
name: rtl-p2-arch-team
description: "Phase 2 architecture with parallel team workers: dual-stream arch + RefC development. Use for 'arch team', 'Phase 2 team', 'parallel architecture'."
user-invocable: true
argument-hint: "[--resume]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate, AskUserQuestion
---

<Purpose>
Execute Phase 2 architecture design pipeline using Claude Code native team infrastructure.
The skill (main session) handles team lifecycle: TeamCreate, coordinator + worker
spawning, task monitoring, and cleanup. The coordinator teammate manages task graphs
and directs workers via SendMessage.
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
- `docs/phase-1-research/iron-requirements.json` must exist
- `docs/phase-1-research/open-requirements.json` (optional — absent if P1 had no open items)
- `docs/phase-1-research/io_definition.json` must exist

If prerequisites are missing: WARNING — recommend running `/rtl-agent-team:p1-spec-research`.
Proceed with available artifacts — orchestrator will adapt scope.

## Execution

```python
# Step 1: Team creation (main session = leader)
TeamCreate(team_name="p2-arch", description="Phase 2 architecture: dual-stream arch + RefC development")

# Step 2: Write team-config.json for hook consumption
Write(".rat/state/team-config.json", json.dumps({
    "team_mode": true,
    "team_name": "p2-arch",
    "leader_session_id": "<current_session_id>",
    "coordinator_name": "coordinator",
    "worker_count": 3,
    "phase": "p2",
    "created_at": "<ISO_TIMESTAMP>"
}))

# Step 3: Prepare directories
Bash("mkdir -p docs/phase-2-architecture reviews/phase-2-architecture .rat/scratch/phase-2")

# Step 4: No initial tasks from skill — coordinator creates T1a-N after reading P1 artifacts

# Step 5: Spawn coordinator as teammate (orchestrator)
Agent(team_name="p2-arch", subagent_type="rtl-agent-team:p2-arch-team-orchestrator",
      name="coordinator", description="P2 architecture coordination",
      prompt="You are the Phase 2 architecture coordinator in team 'p2-arch'. "
             "Manage the task graph using TaskCreate/TaskList/TaskUpdate. "
             "Direct workers via SendMessage. "
             "Create all tasks (T1a-N HW eval through T13 final consolidation, then T14 compliance). "
             "Signal leader ONLY after the Phase 2 Gate (Step 4) passes — including the "
             "Step 3.9 compliance check, ADR generation, and the mandatory Codex cross-review. "
             "User input: $ARGUMENTS")

# Step 6: Spawn workers as teammates (3 general-purpose)
Agent(team_name="p2-arch", subagent_type="rtl-agent-team:arch-designer",
      name="arch-worker", description="P2 architecture design and review",
      prompt="You are a Phase 2 architecture worker in team 'p2-arch'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: docs/phase-2-architecture/, reviews/phase-2-architecture/. "
             "Specialty: architecture design, HW evaluation, bandwidth integration. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Examples: vcodec-architecture-expert for HW eval, rtl-architect for review. "
             "Follow the Team Worker Protocol section of your agent definition. "
             "Scratch dir: .rat/scratch/phase-2/ (for write-restricted outputs).")
Agent(team_name="p2-arch", subagent_type="rtl-agent-team:ref-model-dev",
      name="refmodel-worker", description="P2 reference model development",
      prompt="You are a Phase 2 ref-model worker in team 'p2-arch'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: refc/, docs/phase-2-architecture/. "
             "Specialty: C reference model development, model consistency review. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:ref-model-reviewer', prompt='...'). "
             "Follow the Team Worker Protocol section of your agent definition.")
Agent(team_name="p2-arch", subagent_type="rtl-agent-team:rtl-architect",
      name="review-worker", description="P2 architecture review lead",
      prompt="You are a Phase 2 review worker in team 'p2-arch'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: reviews/phase-2-architecture/. "
             "Specialty: spec compliance review, architecture review aggregation. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Follow the Team Worker Protocol section of your agent definition. "
             "Scratch dir: .rat/scratch/phase-2/ (for write-restricted outputs).")

# Step 7: Leader wait — teardown is gated on the COORDINATOR SIGNAL, not on TaskList.
# "All tasks completed" is necessary but NOT sufficient: the coordinator's post-gate
# work (compliance check, ADR generation, phase summary, Codex cross-review) runs via
# direct Task() calls that never appear in the shared task graph.
while True:
    if coordinator_signaled_phase_complete:
        # SendMessage from 'coordinator' — sent only after the phase gate
        # AND all post-gate mandatory steps pass (see coordinator prompt above)
        break
    tasks = TaskList()
    if all(t.status == "completed" for t in tasks):
        # Task graph drained but no coordinator signal yet → the coordinator is
        # still running gate/post-gate steps. KEEP WAITING — do NOT TeamDelete.
        pass
    # Continue polling

# Step 8: Cleanup
TeamDelete()
Bash("rm -f .rat/state/team-config.json")
Bash("rm -rf .rat/scratch/phase-2/")
```

## Workflow Notes

- Open Resolution: resolve all OPEN-1-* items from Phase 1 `open-requirements.json`
- Exit gate includes `open-resolved`, `compliance-pass` (compliance-checker vs P1 iron, orchestrator Step 3.9), and `ambiguity-pass`
