---
name: rtl-p5-verify-team
description: "Phase 5 verification with native team parallel workers across modules. Triggers 'verify team', 'parallel verify', 'Phase 5 team'; best for 3+ modules."
user-invocable: true
argument-hint: "[--module=name | --resume]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate, AskUserQuestion
---

<Purpose>
Execute Phase 5 verification pipeline using Claude Code native team infrastructure.
The skill (main session) handles team lifecycle: TeamCreate, coordinator + worker
spawning, task monitoring, and cleanup. The coordinator teammate manages the 9-category
verification task graph and directs workers via SendMessage.
</Purpose>

<Use_When>
- Phase 4 RTL implementation is complete with lint passing
- User says "verify team", "Phase 5 team", "parallel verify"
- Need maximum parallelism for multi-module verification
- Have 3+ modules that benefit from concurrent verification workers
</Use_When>

<Do_Not_Use_When>
- RTL modules don't exist yet (run rtl-p4-implement first)
- Single module only (use rtl-p5-verify for simpler flow)
- Want sequential verification (use rtl-p5-verify)
- Only need a specific verification category (use the category-specific skill)
</Do_Not_Use_When>

## Prerequisites

Phase 4 completion required:
- `rtl/**/*.sv` files must exist
- One of the following completion proofs must exist:
  - `reviews/phase-4-rtl/lint-report.md` (full `rtl-p4-implement` path)
  - `.rat/state/p4-state.json` with `gates.p4_exit.verdict` = `pass` (rapid `rtl-p4-rapid-impl` path)

If prerequisites are missing: WARNING — recommend running `/rtl-agent-team:rtl-p4-implement`.
Proceed with available artifacts — orchestrator will adapt scope.

## Execution

```python
# Step 1: Team creation (main session = leader)
TeamCreate(team_name="p5-verify", description="Phase 5 verification: 9-category parallel verification")

# Step 2: Write team-config.json for hook consumption
Write(".rat/state/team-config.json", json.dumps({
    "team_mode": true,
    "team_name": "p5-verify",
    "leader_session_id": "<current_session_id>",
    "coordinator_name": "coordinator",
    "worker_count": 4,
    "phase": "p5",
    "created_at": "<ISO_TIMESTAMP>"
}))

# Step 3: Prepare directories
Bash("mkdir -p docs/phase-5-verify reviews/phase-5-verify sim/coverage formal lint/cdc .rat/scratch/phase-5")

# Step 4: No initial tasks from skill — coordinator creates per-module V1-V9 after discovering modules

# Step 5: Spawn coordinator as teammate (orchestrator)
Agent(team_name="p5-verify", subagent_type="rtl-agent-team:p5-verify-team-orchestrator",
      name="coordinator", description="P5 verification coordination",
      prompt="You are the Phase 5 verification coordinator in team 'p5-verify'. "
             "Manage the 9-category task graph using TaskCreate/TaskList/TaskUpdate. "
             "Direct workers via SendMessage. "
             "Create per-module V1-V9 task graph after discovering modules. "
             "Signal leader when final compliance review complete. User input: $ARGUMENTS")

# Step 6: Spawn workers as teammates (4 general-purpose)
Agent(team_name="p5-verify", subagent_type="rtl-agent-team:func-verifier",
      name="verify-0", description="P5 functional verification",
      prompt="You are a Phase 5 verification worker in team 'p5-verify'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: reviews/phase-5-verify/, sim/. "
             "Specialty: lint (V1), functional regression (V5), coverage (V6). "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Examples: lint-checker for V1, testbench-dev for TB, eda-runner for sim, coverage-analyst for V6. "
             "Follow the Team Worker Protocol section of your agent definition.")
Agent(team_name="p5-verify", subagent_type="rtl-agent-team:sva-extractor",
      name="verify-1", description="P5 formal and CDC verification",
      prompt="You are a Phase 5 verification worker in team 'p5-verify'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: formal/, lint/cdc/, reviews/phase-5-verify/. "
             "Specialty: SVA/formal (V2), CDC (V3), protocol (V4). "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Examples: cdc-checker for V3, protocol-checker for V4, constraint-writer for SDC. "
             "Follow the Team Worker Protocol section of your agent definition.")
Agent(team_name="p5-verify", subagent_type="rtl-agent-team:eda-runner",
      name="analysis-worker", description="P5 performance and synthesis",
      prompt="You are a Phase 5 analysis worker in team 'p5-verify'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: reviews/phase-5-verify/. "
             "Specialty: performance (V7), synthesis estimation (V8). "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Examples: perf-verifier for V7, synthesis-reporter for V8. "
             "Follow the Team Worker Protocol section of your agent definition.")
Agent(team_name="p5-verify", subagent_type="rtl-agent-team:rtl-critic",
      name="review-worker", description="P5 code review and compliance",
      prompt="You are a Phase 5 review worker in team 'p5-verify'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: reviews/phase-5-verify/. "
             "Specialty: code review (V9), requirement traceability, final compliance. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Examples: requirement-tracer for REQ mapping, rtl-critic for review. "
             "Follow the Team Worker Protocol section of your agent definition.")

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
Bash("rm -rf .rat/scratch/phase-5/")
```

## Compliance Notes

- Verification must confirm all iron requirement `acceptance_criteria` are met.
  When structured acceptance_criteria (with ac_id) exist from P3, verification
  tracks compliance at the individual criterion level (ac_id granularity).
  When acceptance_criteria is in string-array format (P1/P2), verification
  operates at REQ level.
- Final compliance check compares test results against P1+P2+P3 `acceptance_criteria`
- Phase 5 PASS requires zero unmet iron requirements across all verification categories
