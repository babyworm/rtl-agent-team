---
name: rtl-p3-uarch-design
description: "Phase 3 uArch, sequential or team: clock domains, FSM/SRAM, BFM. Use for 'uarch', 'microarchitecture', 'Phase 3', 'uarch team'."
user-invocable: true
argument-hint: "[--resume | uarch-focus | team]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate
---

<Purpose>
Execute Phase 3 μArch design. Concretizes architecture blocks into
implementable microarchitecture specifications with clock domains, protocol
assignments, register/SRAM/FSM allocation, and BFM validation.
</Purpose>

<Use_When>
- Phase 2 architecture is complete and μArch design is needed
- User says "microarchitecture", "uarch", "Phase 3"
- User says "uarch team", "Phase 3 team", "parallel uarch"
- Need detailed module specs before RTL implementation
</Use_When>

<Do_Not_Use_When>
- Phase 2 architecture is not complete (run p2-arch-design first)
- Already have μArch specs and need RTL (use rtl-p4-implement)
- Need architecture-level design (use p2-arch-design)
- Only need a BFM (use bfm-develop)
</Do_Not_Use_When>

## Mode

Team mode when `$ARGUMENTS` contains the word `team`, or the user asked for a team, parallel workers, or `rtl-p3-uarch-team`. Otherwise sequential.

## Prerequisites

Phase 2 completion required:
- `docs/phase-2-architecture/architecture.md` must exist
- `refc/` directory with C reference model must exist

If prerequisites are missing: WARNING — recommend running `/rtl-agent-team:p2-arch-design`.
Proceed with available artifacts — orchestrator will adapt scope.

## Sequential

Task(subagent_type="rtl-agent-team:p3-uarch-orchestrator",
     prompt="Execute Phase 3 uArch design. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages domain consultation, parallel uarch design + BFM
development, BFM validation gate, and one μArch review. A further pass runs only when the user asks.

## Team mode

The skill (main session) handles team lifecycle. The coordinator teammate
manages the task graph and directs workers via SendMessage.

```python
# Step 1: Team creation (main session = leader)
TeamCreate(team_name="p3-uarch", description="Phase 3 uArch: dual-stream uArch + BFM development")

# Step 2: Write team-config.json for hook consumption
Write(".rat/state/team-config.json", json.dumps({
    "team_mode": true,
    "team_name": "p3-uarch",
    "leader_session_id": "${CLAUDE_SESSION_ID}",
    "coordinator_name": "coordinator",
    "worker_count": 3,
    "phase": "p3",
    "created_at": "<ISO_TIMESTAMP>"
}))

# Step 3: Prepare directories
Bash("mkdir -p docs/phase-3-uarch reviews/phase-3-uarch .rat/scratch/phase-3")

# Step 4: Create initial task graph (T1 and T2 are independent — no dependencies)
TaskCreate(subject="T1: uArch Design",
           description="Per-block micro-architecture design from architecture spec")
TaskCreate(subject="T2: BFM Development",
           description="Bus Functional Model development from architecture spec")

# Step 5: Spawn coordinator as teammate (orchestrator)
Agent(team_name="p3-uarch", subagent_type="rtl-agent-team:p3-uarch-orchestrator",
      name="coordinator", description="P3 uArch coordination",
      prompt="You are the Phase 3 uArch coordinator in team 'p3-uarch'. "
             "Manage the task graph using TaskCreate/TaskList/TaskUpdate. "
             "Direct workers via SendMessage. "
             "Initial tasks T1 (uarch) and T2 (BFM) already created by leader. "
             "Create dynamic tasks (T3 BFM gate, one review T4a-T4e, then T5). Do not create T6-T10. Then perform Step 3.7/3.8 "
             "iron artifact production (REQ-U-* from resolved OPEN-2-*) + open resolution + "
             "zero-opens + ambiguity gate, then Step 3.9 compliance. "
             "Signal leader ONLY after the Phase 3 Gate (Step 4) passes — including the "
             "Step 3.9 compliance check, ADR generation, and the mandatory Codex cross-review. "
             "User input: $ARGUMENTS")

# Step 6: Spawn workers as teammates (3 general-purpose)
Agent(team_name="p3-uarch", subagent_type="rtl-agent-team:uarch-designer",
      name="uarch-worker", description="P3 uArch design and review",
      prompt="You are a Phase 3 uArch worker in team 'p3-uarch'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: docs/phase-3-uarch/, reviews/phase-3-uarch/. "
             "Specialty: per-block uArch design, timing review, algorithm consistency. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Examples: timing-advisor for timing review, vcodec-architecture-expert for domain. "
             "Follow the Team Worker Protocol section of your agent definition. "
             "Scratch dir: .rat/scratch/phase-3/ (for write-restricted outputs).")
Agent(team_name="p3-uarch", subagent_type="rtl-agent-team:bfm-dev",
      name="bfm-worker", description="P3 BFM development",
      prompt="You are a Phase 3 BFM worker in team 'p3-uarch'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: bfm/, docs/phase-3-uarch/. "
             "Specialty: BFM development, BFM correctness review, I/O logging. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:ref-model-dev', prompt='...'). "
             "Follow the Team Worker Protocol section of your agent definition.")
Agent(team_name="p3-uarch", subagent_type="rtl-agent-team:rtl-architect",
      name="review-worker", description="P3 review lead",
      prompt="You are a Phase 3 review worker in team 'p3-uarch'. "
             "Coordinator: 'coordinator' (send results via SendMessage). "
             "Phase artifacts: reviews/phase-3-uarch/. "
             "Specialty: feature preservation review, aggregation, final consolidation. "
             "For specialist work, spawn: Task(subagent_type='rtl-agent-team:<specialist>', prompt='...'). "
             "Follow the Team Worker Protocol section of your agent definition. "
             "Scratch dir: .rat/scratch/phase-3/ (for write-restricted outputs).")

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
Bash("rm -rf .rat/scratch/phase-3/")
```

If TeamCreate fails, run the sequential section.

## Workflow Notes

- Open Resolution: resolve all OPEN-2-* items from Phase 2 `open-requirements.json`
- Zero-Opens Invariant: no unresolved OPEN-* items may pass to Phase 4
- Compliance Check: verify REQ-U-* uarch requirements against P1+P2 iron requirements
- Exit gate includes `open-resolved`, `zero-remaining-opens`, `compliance-pass`, and `ambiguity-pass`

## P3 Exit Gate: Acceptance Criteria Advisory

Every REQ-U-* in `docs/phase-3-uarch/iron-requirements.json` should have ≥1 `acceptance_criteria` entry.
This is an advisory check (WARNING, not hard-block):
- If any REQ-U-* has no `acceptance_criteria` (absent or empty array `[]`): emit WARNING listing
  the affected REQ IDs
- Prompt uarch-designer to add missing criteria before P3 exit
- Proceed even if some REQ-U-* lack AC — downstream verification will operate at req_ids level
  (backward compatible)

## P3 Exit Gate: Decomposition Completeness Advisory

After iron-requirements.json is finalized, verify decomposition completeness:
1. Read docs/phase-1-research/iron-requirements.json — collect all Critical/High REQ-F-*
2. Read docs/phase-2-architecture/iron-requirements.json — collect all Critical/High REQ-A-*
3. For each Critical/High REQ-F-*: check if at least one REQ-U-* has it in `traces_to`
4. For each Critical/High REQ-A-*: check if at least one REQ-U-* has it in `traces_to`
5. Report:
   - COVERED: upstream REQ has ≥1 REQ-U-* tracing to it
   - UNCOVERED: no REQ-U-* traces to this upstream REQ → WARNING

This is advisory (WARNING, not hard-block). UNCOVERED Critical requirements
should be investigated — they may indicate a decomposition gap or an intentional
architecture decision (document rationale if intentional).
