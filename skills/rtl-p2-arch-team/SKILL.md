---
name: rtl-p2-arch-team
description: "Phase 2 architecture design using Claude Code native teams for parallel dual-stream architecture + RefC development. Manages HW candidate evaluation, parallel design streams, and 3-round iterative review with tree exploration."
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
             "Create all tasks (T1a-N HW eval through T13 final consolidation). "
             "Signal leader when T13 complete. User input: $ARGUMENTS")

# Step 6: Spawn workers as teammates (3 general-purpose)
Agent(team_name="p2-arch", subagent_type="rtl-agent-team:arch-designer",
      name="arch-worker", description="P2 architecture design and review",
      prompt="You are a Phase 2 architecture worker in team 'p2-arch'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: docs/phase-2-architecture/, reviews/phase-2-architecture/. "
             "Specialty: architecture design, HW evaluation, bandwidth integration. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Examples: vcodec-architecture-expert for HW eval, rtl-architect for review. "
             "Follow Team Worker Protocol in agents/lib/team-worker-preamble.md. "
             "Scratch dir: .rat/scratch/phase-2/ (for write-restricted outputs).")
Agent(team_name="p2-arch", subagent_type="rtl-agent-team:ref-model-dev",
      name="refmodel-worker", description="P2 reference model development",
      prompt="You are a Phase 2 ref-model worker in team 'p2-arch'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: refc/, docs/phase-2-architecture/. "
             "Specialty: C reference model development, model consistency review. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:ref-model-reviewer', prompt='...'). "
             "Follow Team Worker Protocol in agents/lib/team-worker-preamble.md.")
Agent(team_name="p2-arch", subagent_type="rtl-agent-team:rtl-architect",
      name="review-worker", description="P2 architecture review lead",
      prompt="You are a Phase 2 review worker in team 'p2-arch'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: reviews/phase-2-architecture/. "
             "Specialty: spec compliance review, architecture review aggregation. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Follow Team Worker Protocol in agents/lib/team-worker-preamble.md. "
             "Scratch dir: .rat/scratch/phase-2/ (for write-restricted outputs).")

# Step 7: Leader monitoring loop — poll until all tasks complete
while True:
    tasks = TaskList()
    all_done = all(t.status == "completed" for t in tasks)
    if all_done:
        break
    # Continue polling

# Step 8: Cleanup
TeamDelete()
Bash("rm -f .rat/state/team-config.json")
Bash("rm -rf .rat/scratch/phase-2/")
```

## Workflow Notes

- Open Resolution: resolve all OPEN-1-* items from Phase 1 `open-requirements.json`
- Exit gate includes `open-resolved` and `ambiguity-pass`
- Note: `compliance-pass` will be added when team orchestrator is updated to invoke compliance-checker
