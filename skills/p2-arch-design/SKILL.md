---
name: p2-arch-design
description: "Phase 2 architecture, sequential or team. Use for 'architecture design', 'Phase 2', 'block design', 'arch team', 'parallel architecture'."
user-invocable: true
argument-hint: "[--resume | architecture-focus | team]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate
---

<Purpose>
Execute Phase 2 architecture design. Reviews Phase 1 algorithm candidates
for HW feasibility, designs block-level architecture with data paths, builds
a reference C model, then one architecture review. A further pass runs only when the user asks.
</Purpose>

<Use_When>
- Phase 1 research is complete and architecture design is needed
- User says "architecture design", "Phase 2", "block design"
- User says "arch team", "Phase 2 team", "parallel architecture"
- Need HW feasibility evaluation of algorithm candidates
</Use_When>

<Do_Not_Use_When>
- Phase 1 research is not complete (run p1-spec-research first)
- Only need architecture review of existing docs (use arch-review)
- Need DSE with multiple architecture candidates (use rat-dse)
- Only need a reference model (use ref-model)
</Do_Not_Use_When>

## Mode

Team mode when `$ARGUMENTS` contains the word `team`, or the user asked for a team, parallel workers, or `rtl-p2-arch-team`. Otherwise sequential. `--resume` stays sequential unless team mode also applies.

## Prerequisites

Phase 1 completion required:
- `docs/phase-1-research/iron-requirements.json` must exist
- `docs/phase-1-research/open-requirements.json` (optional — absent if P1 had no open items)
- `docs/phase-1-research/io_definition.json` must exist

If prerequisites are missing: WARNING — recommend running `/rtl-agent-team:p1-spec-research`.
Proceed with available artifacts — orchestrator will adapt scope.

## Sequential

If $ARGUMENTS contains "--resume":

Task(subagent_type="rtl-agent-team:p2-arch-orchestrator",
     prompt="Resume Phase 2 architecture design from existing artifacts in
     docs/phase-2-architecture/ and reviews/phase-2-architecture/. $ARGUMENTS")

Else:

Task(subagent_type="rtl-agent-team:p2-arch-orchestrator",
     prompt="Execute Phase 2 architecture design. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages P1 candidate HW review, parallel architecture
design + ref model, and artifact finalization.

## Team mode

The skill (main session) handles team lifecycle. The coordinator teammate
manages the task graph and directs workers via SendMessage.

```python
# Step 1: Team creation (main session = leader)
TeamCreate(team_name="p2-arch", description="Phase 2 architecture: dual-stream arch + RefC development")

# Step 2: Write team-config.json for hook consumption
Write(".rat/state/team-config.json", json.dumps({
    "team_mode": true,
    "team_name": "p2-arch",
    "leader_session_id": "${CLAUDE_SESSION_ID}",
    "coordinator_name": "coordinator",
    "worker_count": 3,
    "phase": "p2",
    "created_at": "<ISO_TIMESTAMP>"
}))

# Step 3: Prepare directories
Bash("mkdir -p docs/phase-2-architecture reviews/phase-2-architecture .rat/scratch/phase-2")

# Step 4: No initial tasks from skill — coordinator creates T1a-N after reading P1 artifacts

# Step 5: Spawn coordinator as teammate (orchestrator)
Agent(team_name="p2-arch", subagent_type="rtl-agent-team:p2-arch-orchestrator",
      name="coordinator", description="P2 architecture coordination",
      prompt="You are the Phase 2 architecture coordinator in team 'p2-arch'. "
             "Manage the task graph using TaskCreate/TaskList/TaskUpdate. "
             "Direct workers via SendMessage. "
             "Create all tasks (T1a-N HW eval through T13 final consolidation), then perform "
             "Step 3.7/3.8 iron/open artifact production (REQ-A-* from resolved OPEN-1-*) + open "
             "resolution + ambiguity gate, then T14 compliance. "
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

If TeamCreate fails, run the sequential section.

## Workflow Notes

- Open Resolution: resolve all OPEN-1-* items from Phase 1 `open-requirements.json`
- Compliance Check: verify REQ-A-* architecture requirements against P1 iron requirements
- Exit gate includes `open-resolved`, `compliance-pass`, and `ambiguity-pass`
