---
name: p1-spec-research
description: "Phase 1 spec research, sequential or team. Triggers: 'research', 'spec analysis', 'Phase 1', 'research team', 'parallel research'."
user-invocable: true
argument-hint: "[spec-file or project-description | team]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate
---

<Purpose>
Execute Phase 1 spec research. Refines the specification, identifies gaps,
surveys candidate algorithms with trade-offs, and produces structured research
artifacts for Phase 2.
</Purpose>

<Use_When>
- Starting a new RTL design from a specification or idea
- User says "research", "spec analysis", "Phase 1"
- User says "research team", "Phase 1 team", "parallel research"
- Specification has ambiguities or missing information
</Use_When>

<Do_Not_Use_When>
- Phase 1 artifacts already exist and are current
- Only need a quick domain question (use domain-consult)
- Need architecture design (use p2-arch-design — requires Phase 1 completion)
</Do_Not_Use_When>

## Mode

Team mode when `$ARGUMENTS` contains the word `team`, or the user asked for a team, parallel workers, or `rtl-p1-research-team`. Otherwise sequential.

<Phase_Workflow>
Sequential mode runs as two stages inside the same Task() invocation:

- **Phase 0 (goal-clarifier)**: when `$ARGUMENTS` is a sparse seed, the
  orchestrator first dispatches `goal-clarifier` for an ambiguity-scored
  interview across 4 RTL dimensions (Functionality / PPA Target / Scope /
  Verification). Phase 0 writes `docs/phase-1-research/goal.md`.
- **Phase 1 (spec-analyst + research)**: spec-analyst consumes `goal.md`
  (plus any user-supplied spec document) and produces the iron/open
  requirements set as before.

When `$ARGUMENTS` points to an existing `.md`/`.txt`/`.rst` spec or is
already a rich seed (≥ 500 chars with PPA/coverage signals), Phase 0
is skipped automatically.
</Phase_Workflow>

<Assets>
| Path | Role |
|------|------|
| `scripts/score_ambiguity.py` | Pure stdlib helper for 4-dimension scoring + ambiguity %. Goal-clarifier calls it once. |
| `templates/goal.md` | Output skeleton for `docs/phase-1-research/goal.md`. |
| `references/goal-dimensions.md` | 4-dimension scoring rubric + question seeds + anti-patterns. |
</Assets>

## Prerequisites

None — this is the first phase entry point.
Specification documents should be available in `specs/` directory.

## Sequential

Task(subagent_type="rtl-agent-team:p1-research-orchestrator",
     prompt="Execute Phase 1 spec research. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages spec refinement, solution tree exploration,
sub-domain expert coordination, and one chief review.

## Team mode

The skill (main session) handles team lifecycle. The coordinator teammate
manages the task graph and directs workers via SendMessage.

```python
# Step 1: Team creation (main session = leader)
TeamCreate(team_name="p1-research", description="Phase 1 research: tree-of-thought parallel candidate exploration")

# Step 2: Write team-config.json for hook consumption
Write(".rat/state/team-config.json", json.dumps({
    "team_mode": true,
    "team_name": "p1-research",
    "leader_session_id": "${CLAUDE_SESSION_ID}",
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
             "Create dynamic tasks (T3a-N deep-dive, T5-T12, then T12b/T12c census+coverage) "
             "as the workflow progresses. A high-confidence spec passes. Do not create a second interpretation pass. "
             "Signal leader ONLY after the Phase 1 Gate (Step 4) passes, including the one confidence check "
             "and the mandatory Codex cross-review (Step 5). "
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

If TeamCreate fails, run the sequential section.

## Output Artifacts

- `docs/phase-1-research/iron-requirements.json` — settled functional/performance requirements (REQ-F-*, REQ-P-*)
- `docs/phase-1-research/open-requirements.json` — research topics deferred to Phase 2 (OPEN-1-*)
- `docs/phase-1-research/io_definition.json` — I/O interface definitions
- Classification verification step confirms each requirement is tagged as either iron (acceptance_criteria defined) or open (research_needed).
