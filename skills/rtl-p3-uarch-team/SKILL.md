---
name: rtl-p3-uarch-team
description: "Phase 3 uArch design using Claude Code native teams for parallel dual-stream uArch + BFM development. Manages per-block uarch design, BFM validation gate, and 5-reviewer 3-round iterative review."
user-invocable: true
argument-hint: "[--resume]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate, AskUserQuestion
---

<Purpose>
Execute Phase 3 uArch design pipeline using Claude Code native team infrastructure.
The skill (main session) handles team lifecycle: TeamCreate, coordinator + worker
spawning, task monitoring, and cleanup. The coordinator teammate manages task graphs
and directs workers via SendMessage.
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

If prerequisites are missing: WARNING — recommend running `/rtl-agent-team:p2-arch-design`.
Proceed with available artifacts — orchestrator will adapt scope.

## Execution

```python
# Step 1: Team creation (main session = leader)
TeamCreate(team_name="p3-uarch", description="Phase 3 uArch: dual-stream uArch + BFM development")

# Step 2: Write team-config.json for hook consumption
Write(".rtl-agent-team/state/team-config.json", json.dumps({
    "team_mode": true,
    "team_name": "p3-uarch",
    "leader_session_id": "<current_session_id>",
    "coordinator_name": "coordinator",
    "worker_count": 3,
    "phase": "p3",
    "created_at": "<ISO_TIMESTAMP>"
}))

# Step 3: Prepare directories
Bash("mkdir -p docs/phase-3-uarch reviews/phase-3-uarch .rtl-agent-team/scratch/phase-3")

# Step 4: Create initial task graph (T1 and T2 are independent — no dependencies)
TaskCreate(subject="T1: uArch Design",
           description="Per-block micro-architecture design from architecture spec")
TaskCreate(subject="T2: BFM Development",
           description="Bus Functional Model development from architecture spec")

# Step 5: Spawn coordinator as teammate (orchestrator)
Agent(team_name="p3-uarch", subagent_type="rtl-agent-team:p3-uarch-team-orchestrator",
      name="coordinator", description="P3 uArch coordination",
      prompt="You are the Phase 3 uArch coordinator in team 'p3-uarch'. "
             "Manage the task graph using TaskCreate/TaskList/TaskUpdate. "
             "Direct workers via SendMessage. "
             "Initial tasks T1 (uarch) and T2 (BFM) already created by leader. "
             "Create dynamic tasks (T3 BFM gate, T4-T10 review rounds). "
             "Signal leader when T10 complete. User input: $ARGUMENTS")

# Step 6: Spawn workers as teammates (3 general-purpose)
Agent(team_name="p3-uarch", subagent_type="rtl-agent-team:uarch-designer",
      name="uarch-worker", description="P3 uArch design and review",
      prompt="You are a Phase 3 uArch worker in team 'p3-uarch'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: docs/phase-3-uarch/, reviews/phase-3-uarch/. "
             "Specialty: per-block uArch design, timing review, algorithm consistency. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Examples: timing-advisor for timing review, vcodec-architecture-expert for domain. "
             "Follow Team Worker Protocol in agents/lib/team-worker-preamble.md. "
             "Scratch dir: .rtl-agent-team/scratch/phase-3/ (for write-restricted outputs).")
Agent(team_name="p3-uarch", subagent_type="rtl-agent-team:bfm-dev",
      name="bfm-worker", description="P3 BFM development",
      prompt="You are a Phase 3 BFM worker in team 'p3-uarch'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: bfm/, docs/phase-3-uarch/. "
             "Specialty: BFM development, BFM correctness review, I/O logging. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:ref-model-dev', prompt='...'). "
             "Follow Team Worker Protocol in agents/lib/team-worker-preamble.md.")
Agent(team_name="p3-uarch", subagent_type="rtl-agent-team:rtl-architect",
      name="review-worker", description="P3 review lead",
      prompt="You are a Phase 3 review worker in team 'p3-uarch'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: reviews/phase-3-uarch/. "
             "Specialty: feature preservation review, aggregation, final consolidation. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Follow Team Worker Protocol in agents/lib/team-worker-preamble.md. "
             "Scratch dir: .rtl-agent-team/scratch/phase-3/ (for write-restricted outputs).")

# Step 7: Leader monitoring loop — poll until all tasks complete
while True:
    tasks = TaskList()
    all_done = all(t.status == "completed" for t in tasks)
    if all_done:
        break
    # Continue polling

# Step 8: Cleanup
TeamDelete()
Bash("rm -f .rtl-agent-team/state/team-config.json")
Bash("rm -rf .rtl-agent-team/scratch/phase-3/")
```

## Workflow Notes

- Open Resolution: resolve all OPEN-2-* items from Phase 2 `open-requirements.json`
- Zero-Opens Invariant: no unresolved OPEN-* items may pass to Phase 4
- Exit gate includes `open-resolved`, `zero-remaining-opens`, and `ambiguity-pass`
- Note: `compliance-pass` will be added when team orchestrator is updated to invoke compliance-checker
