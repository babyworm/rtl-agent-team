---
name: rtl-p5-verify
description: "Phase 5 legacy bundled verification, sequential or team. Triggers 'verify', 'Phase 5', 'verify team'. New flows: prefer split P5A/P5B."
user-invocable: true
argument-hint: "[--module=name | --stage=N | --resume | team]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate
---

<Purpose>
Execute Phase 5 verification. Runs three-stage verification
(module → top → final) covering 9 verification categories with module
graduation gates and compliance review.
This is a legacy bundled bridge while teams transition to split P5A/P5B.
</Purpose>

<Use_When>
- Phase 4 RTL implementation is complete with lint passing
- User says "verify", "verification", "Phase 5", "run all checks"
- User says "verify team", "Phase 5 team", "parallel verify"
- Need comprehensive verification: lint, formal, CDC, functional, coverage, synthesis
- Need one legacy-style Phase-5 command that bundles functional + silicon-oriented checks
- Need migration bridge while adopting split flows (`rtl-p5a-functional-closure` + `rtl-p5b-silicon-validation`)
- Have 3+ modules that benefit from concurrent verification workers
</Use_When>

<Do_Not_Use_When>
- RTL modules don't exist yet (run `rtl-p4-rapid-impl` or `rtl-p4-implement` first)
- Only need functional regression (use rtl-p5s-func-verify)
- Only need a specific verification category (use the category-specific skill)
- Want strict separation of functional closure and silicon validation
  (use `rtl-p5a-functional-closure` first, then `rtl-p5b-silicon-validation`)
- Starting a new verification flow with explicit two-stage closure
  (default to split `rtl-p5a-functional-closure` + `rtl-p5b-silicon-validation`)
- A single module does not need parallel workers (omit `team`)
</Do_Not_Use_When>

## Mode

Team mode when `$ARGUMENTS` contains the word `team`, or the user asked for a team, parallel workers, or `rtl-p5-verify-team`. Otherwise sequential.

## Prerequisites

Phase 4 completion required:
- `rtl/**/*.sv` files must exist
- One of the following completion proofs must exist:
  - `reviews/phase-4-rtl/lint-report.md` (full `rtl-p4-implement` path)
  - `.rat/state/p4-state.json` with `gates.p4_exit.verdict` = `pass` (rapid `rtl-p4-rapid-impl` path)

If prerequisites are missing: WARNING — recommend running `/rtl-agent-team:rtl-p4-rapid-impl`
or `/rtl-agent-team:rtl-p4-implement`. Proceed with available artifacts — orchestrator will adapt scope.

## Sequential

Task(subagent_type="rtl-agent-team:p5-verify-orchestrator",
     prompt="Execute Phase 5 verification. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages all stages, module graduation,
parallel agent spawning, and compliance review.

## Team mode

The skill (main session) handles team lifecycle. The coordinator teammate
manages the 9-category verification task graph and directs workers via SendMessage.

```python
# Step 1: Team creation (main session = leader)
TeamCreate(team_name="p5-verify", description="Phase 5 verification: 9-category parallel verification")

# Step 2: Write team-config.json for hook consumption
Write(".rat/state/team-config.json", json.dumps({
    "team_mode": true,
    "team_name": "p5-verify",
    "leader_session_id": "${CLAUDE_SESSION_ID}",
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
             "Signal leader ONLY after final compliance, the Phase 5 summary task (S3.5), "
             "and the mandatory Codex cross-review (Step 6) are ALL complete. "
             "User input: $ARGUMENTS")

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
Bash("rm -rf .rat/scratch/phase-5/")
```

If TeamCreate fails, run the sequential section.

## Compliance Notes

- Verification must confirm all iron requirement `acceptance_criteria` are met.
  When structured acceptance_criteria (with ac_id) exist from P3, verification
  tracks compliance at the individual criterion level (ac_id granularity).
  When acceptance_criteria is in string-array format (P1/P2), verification
  operates at REQ level.
- Final compliance check compares test results against P1+P2+P3 `acceptance_criteria`
- Phase 5 PASS requires zero unmet iron requirements across all verification categories

## Output

- `reviews/phase-5-verify/` — 9 category verification reports (lint, formal, CDC, protocol, functional, coverage, performance, synthesis, code review)
- `reviews/phase-5-verify/final-compliance.md` — overall PASS/FAIL verdict with requirement traceability
