---
name: rtl-p1-research-team
description: "Phase 1 research with parallel team workers for tree-of-thought candidate exploration. Use for 'research team', 'Phase 1 team', 'parallel research'."
user-invocable: true
argument-hint: "[spec-path or --resume]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate, AskUserQuestion
---

<Purpose>
Execute Phase 1 research pipeline using Claude Code native team infrastructure.
The skill (main session) handles team lifecycle: TeamCreate, coordinator + worker
spawning, task monitoring, and cleanup. The coordinator teammate manages task graphs
and directs workers via SendMessage.
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
# Step 1: Team creation (main session = leader)
TeamCreate(team_name="p1-research", description="Phase 1 research: tree-of-thought parallel candidate exploration")

# Step 2: Write team-config.json for hook consumption
Write(".rat/state/team-config.json", json.dumps({
    "team_mode": true,
    "team_name": "p1-research",
    "leader_session_id": "<current_session_id>",
    "coordinator_name": "coordinator",
    "worker_count": 4,
    "phase": "p1",
    "created_at": "<ISO_TIMESTAMP>"
}))

# Step 3: Prepare directories
Bash("mkdir -p docs/phase-1-research reviews/phase-1-research .rat/scratch/phase-1")

# Step 4: Create initial task graph
t1 = TaskCreate(subject="T1: Solution Tree Construction",
                description="Build tree-of-thought solution candidates from spec analysis")
t2 = TaskCreate(subject="T2: Solution Tree Validation",
                description="Validate and rank solution candidates")
TaskUpdate(taskId=t2, addBlockedBy=[t1])
t4b = TaskCreate(subject="T4b: Interconnect Analysis",
                 description="Analyze interconnect topology for top candidates")
TaskUpdate(taskId=t4b, addBlockedBy=[t2])
t4c = TaskCreate(subject="T4c: Power Analysis",
                 description="Analyze power characteristics for top candidates")
TaskUpdate(taskId=t4c, addBlockedBy=[t2])

# Step 5: Spawn coordinator as teammate (orchestrator)
Agent(team_name="p1-research", subagent_type="rtl-agent-team:p1-research-team-orchestrator",
      name="coordinator", description="P1 research coordination",
      prompt="You are the Phase 1 research coordinator in team 'p1-research'. "
             "Manage the task graph using TaskCreate/TaskList/TaskUpdate. "
             "Direct workers via SendMessage. "
             "Initial tasks T1, T2, T4b, T4c already created by leader. "
             "Create dynamic tasks (T3a-N deep-dive, T5-T12, then T12b/T12c census+coverage, "
             "T13a adversarial challenge, T13b re-run+re-bind) as the workflow progresses. "
             "Signal leader ONLY after the Phase 1 Gate (Step 4) passes — i.e., after T13b, "
             "the adversarial gate (Step 3.8), the feature-coverage/ambiguity re-binds, "
             "and the mandatory Codex cross-review (Step 5) are ALL complete. "
             "User input: $ARGUMENTS")

# Step 6: Spawn workers as teammates (3-5 general-purpose)
Agent(team_name="p1-research", subagent_type="rtl-agent-team:spec-analyst",
      name="research-0", description="P1 spec analysis and research",
      prompt="You are a Phase 1 research worker in team 'p1-research'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: docs/phase-1-research/, reviews/phase-1-research/. "
             "Specialty: spec analysis, requirements extraction, solution tree construction. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Follow the Team Worker Protocol section of your agent definition. "
             "Naming: i_/o_ prefixes, snake_case, clk/{domain}_clk, rst_n/{domain}_rst_n. "
             "Scratch dir: .rat/scratch/phase-1/ (for write-restricted outputs).")
Agent(team_name="p1-research", subagent_type="rtl-agent-team:rtl-architect",
      name="research-1", description="P1 architecture review and deep-dive",
      prompt="You are a Phase 1 research worker in team 'p1-research'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: docs/phase-1-research/, reviews/phase-1-research/. "
             "Specialty: architecture review, candidate deep-dive, comparison matrix. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Follow the Team Worker Protocol section of your agent definition. "
             "Naming: i_/o_ prefixes, snake_case, clk/{domain}_clk, rst_n/{domain}_rst_n. "
             "Scratch dir: .rat/scratch/phase-1/ (for write-restricted outputs).")
Agent(team_name="p1-research", subagent_type="rtl-agent-team:rtl-architect",
      name="analysis-0", description="P1 analysis and survey",
      prompt="You are a Phase 1 research worker in team 'p1-research'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: docs/phase-1-research/, reviews/phase-1-research/. "
             "Specialty: cross-cutting surveys (memory, interconnect, power), literature survey. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Follow the Team Worker Protocol section of your agent definition. "
             "Scratch dir: .rat/scratch/phase-1/ (for write-restricted outputs).")
Agent(team_name="p1-research", subagent_type="rtl-agent-team:power-analyzer",
      name="domain-0", description="P1 domain and power analysis",
      prompt="You are a Phase 1 research worker in team 'p1-research'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: docs/phase-1-research/, reviews/phase-1-research/. "
             "Specialty: power analysis, domain-specific expert consultation. "
             "For domain expert work, spawn: Task(subagent_type='rtl-agent-team:vcodec-*-expert', prompt='...'). "
             "Follow the Team Worker Protocol section of your agent definition. "
             "Scratch dir: .rat/scratch/phase-1/ (for write-restricted outputs).")

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
Bash("rm -rf .rat/scratch/phase-1/")
```

## Output Artifacts

- `docs/phase-1-research/iron-requirements.json` — settled functional/performance requirements (REQ-F-*, REQ-P-*)
- `docs/phase-1-research/open-requirements.json` — research topics deferred to Phase 2 (OPEN-1-*)
- `docs/phase-1-research/io_definition.json` — I/O interface definitions
- Classification verification step confirms each requirement is tagged as either iron (acceptance_criteria defined) or open (research_needed).
