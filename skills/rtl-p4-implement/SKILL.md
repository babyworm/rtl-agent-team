---
name: rtl-p4-implement
description: "Phase 4 RTL from uarch with lint, review, and unit tests. Sequential or team. Use for 'implement RTL', 'write RTL', 'Phase 4 team'."
user-invocable: true
argument-hint: "[module-list or --all | team]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate
---

<Purpose>
Execute Phase 4 RTL implementation. Implements SystemVerilog modules from
μArch specs through a 10-Wave pipeline: Write → Lint → Fix → Review → Bugfix →
UnitTest → CDC → Protocol → Refactor → IntegrationGate.
</Purpose>

<Use_When>
- Phase 3 μArch specs are complete and RTL coding is needed
- User says "implement RTL", "write RTL", "Phase 4", "code modules"
- User says "implement team", "Phase 4 team", "parallel implement"
- Need lint-clean, unit-tested SystemVerilog modules
- Need the full 10-Wave implementation pipeline with comprehensive review/fix/refactor
- Have 3+ modules that benefit from concurrent RTL coding workers
</Use_When>

<Do_Not_Use_When>
- Phase 3 μArch specs are not complete (run rtl-p3-uarch-design first)
- Only need a single module bug fix (use rtl-p4s-bugfix)
- Need RTL + verification together from uarch (use rat-p4p5-impl-verify)
- Need a faster minimal Phase-4 sanity loop first (use rtl-p4-rapid-impl)
- A single module does not need parallel workers (omit `team`)
</Do_Not_Use_When>

## Mode

Team mode when `$ARGUMENTS` contains the word `team`, or the user asked for a team, parallel workers, or `rtl-p4-implement-team`. Otherwise sequential.

## Prerequisites

Phase 3 completion required:
- At least one μArch spec in `docs/phase-3-uarch/` must exist

If prerequisite is missing: WARNING — recommend running `/rtl-agent-team:rtl-p3-uarch-design`.
Proceed with available artifacts — orchestrator will adapt scope.

## Sequential

Task(subagent_type="rtl-agent-team:p4-implement-orchestrator",
     prompt="Execute Phase 4 RTL implementation. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages module enumeration, 10-Wave sequencing,
parallel task dispatch, and phase gate verification.

## Team mode

The skill (main session) handles team lifecycle. The coordinator teammate
manages the 10-wave task graph and directs workers via SendMessage.

```python
# Step 1: Team creation (main session = leader)
TeamCreate(team_name="p4-implement", description="Phase 4 RTL implementation: 10-wave parallel module coding")

# Step 2: Write team-config.json for hook consumption
Write(".rat/state/team-config.json", json.dumps({
    "team_mode": true,
    "team_name": "p4-implement",
    "leader_session_id": "${CLAUDE_SESSION_ID}",
    "coordinator_name": "coordinator",
    "worker_count": 4,
    "phase": "p4",
    "created_at": "<ISO_TIMESTAMP>"
}))

# Step 3: Prepare directories
Bash("mkdir -p reviews/phase-4-rtl docs/phase-4-rtl .rat/scratch/phase-4")

# Step 4: No initial tasks from skill — coordinator creates per-module W1-W10 after reading uarch specs

# Step 5: Spawn coordinator as teammate (orchestrator)
Agent(team_name="p4-implement", subagent_type="rtl-agent-team:p4-implement-team-orchestrator",
      name="coordinator", description="P4 implementation coordination",
      prompt="You are the Phase 4 RTL implementation coordinator in team 'p4-implement'. "
             "Manage the 10-wave task graph using TaskCreate/TaskList/TaskUpdate. "
             "Direct workers via SendMessage. "
             "Create per-module 10-wave task graph after reading uarch specs. "
             "Signal leader ONLY after the Phase 4 Gate (Step 4 — all required checks "
             "and artifacts, not merely the W10 integration gate) passes, including the "
             "mandatory Codex cross-review. User input: $ARGUMENTS")

# Step 6: Spawn workers as teammates (4 general-purpose)
Agent(team_name="p4-implement", subagent_type="rtl-agent-team:rtl-coder",
      name="coder-0", description="P4 RTL coding and lint",
      prompt="You are a Phase 4 coding worker in team 'p4-implement'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: rtl/{module}/{module}.sv, reviews/phase-4-rtl/. "
             "Specialty: RTL module implementation (W1), lint (W2), lint fix (W3). "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Examples: lint-checker for lint, eda-runner for simulation. "
             "Follow the Team Worker Protocol section of your agent definition. "
             "Naming: i_/o_ prefixes, snake_case, clk/{domain}_clk, rst_n/{domain}_rst_n.")
Agent(team_name="p4-implement", subagent_type="rtl-agent-team:rtl-coder",
      name="coder-1", description="P4 RTL coding and lint",
      prompt="You are a Phase 4 coding worker in team 'p4-implement'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: rtl/{module}/{module}.sv, reviews/phase-4-rtl/. "
             "Specialty: RTL module implementation (W1), lint (W2), lint fix (W3). "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Follow the Team Worker Protocol section of your agent definition. "
             "Naming: i_/o_ prefixes, snake_case, clk/{domain}_clk, rst_n/{domain}_rst_n.")
Agent(team_name="p4-implement", subagent_type="rtl-agent-team:testbench-dev",
      name="verify-worker", description="P4 unit test and verification",
      prompt="You are a Phase 4 verification worker in team 'p4-implement'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: sim/{module}/, reviews/phase-4-rtl/. "
             "Specialty: unit test (W6), CDC analysis (W7), protocol check (W8). "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Examples: eda-runner for sim, cdc-checker for CDC, protocol-checker for W8. "
             "Follow the Team Worker Protocol section of your agent definition.")
Agent(team_name="p4-implement", subagent_type="rtl-agent-team:rtl-critic",
      name="review-worker", description="P4 code review and refactor",
      prompt="You are a Phase 4 review worker in team 'p4-implement'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: reviews/phase-4-rtl/. "
             "Specialty: code review (W4), bugfix (W5), refactor (W9), integration (W10). "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Follow the Team Worker Protocol section of your agent definition.")

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
Bash("rm -rf .rat/scratch/phase-4/")
```

If TeamCreate fails, run the sequential section.

## Compliance Notes

- After each implementation wave completes (lint + unit test), invoke compliance-checker against P1+P2+P3 iron requirements
- RTL implementation must comply with all upstream iron requirements
- Per-wave compliance ensures regressions are caught before the integration gate (W10)
- Wave 0 includes test plan generation (Step 0b) — test scenarios are derived from
  uarch spec before RTL implementation begins, following TDD principles.

## Output

- `rtl/*/*.sv` — lint-clean SystemVerilog modules
- `sim/*/tb_*.sv` — per-module unit test testbenches
- `docs/phase-4-rtl/` — Stream B design documents and implementation summary
- `reviews/phase-4-rtl/` — lint reports, code review reports, and wave completion records
