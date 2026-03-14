---
name: rtl-p4-implement-team
description: "Phase 4 RTL implementation using Claude Code native teams for parallel worker execution. Manages 10-wave pipeline with per-module parallelism and inter-wave dependency graphs."
user-invocable: true
argument-hint: "[module-list or --all]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate, AskUserQuestion
---

<Purpose>
Execute Phase 4 RTL implementation pipeline using Claude Code native team infrastructure.
The skill (main session) handles team lifecycle: TeamCreate, coordinator + worker
spawning, task monitoring, and cleanup. The coordinator teammate manages the 10-wave
task graph and directs workers via SendMessage.
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
- Need RTL + verification together from uarch (use rat-p4p5-impl-verify)
</Do_Not_Use_When>

## Prerequisites

Phase 3 completion required:
- At least one uArch spec in `docs/phase-3-uarch/` must exist

If prerequisite is missing: WARNING — recommend running `/rtl-agent-team:rtl-p3-uarch-design`.
Proceed with available artifacts — orchestrator will adapt scope.

## Execution

```python
# Step 1: Team creation (main session = leader)
TeamCreate(team_name="p4-implement", description="Phase 4 RTL implementation: 10-wave parallel module coding")

# Step 2: Write team-config.json for hook consumption
Write(".rtl-agent-team/state/team-config.json", json.dumps({
    "team_mode": true,
    "team_name": "p4-implement",
    "leader_session_id": "<current_session_id>",
    "coordinator_name": "coordinator",
    "worker_count": 4,
    "phase": "p4",
    "created_at": "<ISO_TIMESTAMP>"
}))

# Step 3: Prepare directories
Bash("mkdir -p reviews/phase-4-rtl docs/phase-4-rtl .rtl-agent-team/scratch/phase-4")

# Step 4: No initial tasks from skill — coordinator creates per-module W1-W10 after reading uarch specs

# Step 5: Spawn coordinator as teammate (orchestrator)
Agent(team_name="p4-implement", subagent_type="rtl-agent-team:p4-implement-team-orchestrator",
      name="coordinator", description="P4 implementation coordination",
      prompt="You are the Phase 4 RTL implementation coordinator in team 'p4-implement'. "
             "Manage the 10-wave task graph using TaskCreate/TaskList/TaskUpdate. "
             "Direct workers via SendMessage. "
             "Create per-module 10-wave task graph after reading uarch specs. "
             "Signal leader when integration gate passes. User input: $ARGUMENTS")

# Step 6: Spawn workers as teammates (4 general-purpose)
Agent(team_name="p4-implement", subagent_type="rtl-agent-team:rtl-coder",
      name="coder-0", description="P4 RTL coding and lint",
      prompt="You are a Phase 4 coding worker in team 'p4-implement'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: rtl/{module}/{module}.sv, reviews/phase-4-rtl/. "
             "Specialty: RTL module implementation (W1), lint (W2), lint fix (W3). "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Examples: lint-checker for lint, eda-runner for simulation. "
             "Follow Team Worker Protocol in agents/lib/team-worker-preamble.md. "
             "Naming: i_/o_ prefixes, snake_case, clk/{domain}_clk, rst_n/{domain}_rst_n.")
Agent(team_name="p4-implement", subagent_type="rtl-agent-team:rtl-coder",
      name="coder-1", description="P4 RTL coding and lint",
      prompt="You are a Phase 4 coding worker in team 'p4-implement'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: rtl/{module}/{module}.sv, reviews/phase-4-rtl/. "
             "Specialty: RTL module implementation (W1), lint (W2), lint fix (W3). "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Follow Team Worker Protocol in agents/lib/team-worker-preamble.md. "
             "Naming: i_/o_ prefixes, snake_case, clk/{domain}_clk, rst_n/{domain}_rst_n.")
Agent(team_name="p4-implement", subagent_type="rtl-agent-team:testbench-dev",
      name="verify-worker", description="P4 unit test and verification",
      prompt="You are a Phase 4 verification worker in team 'p4-implement'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: sim/{module}/, reviews/phase-4-rtl/. "
             "Specialty: unit test (W6), CDC analysis (W7), protocol check (W8). "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Examples: eda-runner for sim, cdc-checker for CDC, protocol-checker for W8. "
             "Follow Team Worker Protocol in agents/lib/team-worker-preamble.md.")
Agent(team_name="p4-implement", subagent_type="rtl-agent-team:rtl-critic",
      name="review-worker", description="P4 code review and refactor",
      prompt="You are a Phase 4 review worker in team 'p4-implement'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: reviews/phase-4-rtl/. "
             "Specialty: code review (W4), bugfix (W5), refactor (W9), integration (W10). "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Follow Team Worker Protocol in agents/lib/team-worker-preamble.md.")

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
Bash("rm -rf .rtl-agent-team/scratch/phase-4/")
```

## Compliance Notes

- After each implementation wave completes (lint + unit test), invoke compliance-checker against P1+P2+P3 iron requirements
- RTL implementation must comply with all upstream iron requirements
- Per-wave compliance ensures regressions are caught before the integration gate (W10)
