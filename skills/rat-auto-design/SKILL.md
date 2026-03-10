---
name: rat-auto-design
description: "This skill should be used when starting a full RTL design pipeline from spec to verification. Orchestrates 6-phase flow (Research → Architecture → μArch → RTL → Verify → Design Note) with dual-layer phase gates and hierarchical spec compliance."
user-invocable: true
argument-hint: "[spec-file or project-description]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion, Skill, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate
---

<Purpose>
Execute the full RTL design pipeline from specification to verified silicon.
In team mode (default), the skill directly sequences phases using phase-specific team skills
for parallel execution. In sequential mode (--no-team), delegates to autopilot-orchestrator.
</Purpose>

<Use_When>
- Starting a complete RTL design from a specification document
- User says "design a chip", "full pipeline", "RTL design", "autopilot"
- Need end-to-end flow: Research → Architecture → μArch → RTL → Verify → Design Note
</Use_When>

<Do_Not_Use_When>
- Only need a specific phase (use the phase-specific skill instead)
- Only need design space exploration (use rtl-dse)
- Only need design documents without RTL (use rtl-spec-to-uarch)
</Do_Not_Use_When>

## Prerequisites

None — this is the full pipeline entry point. Setup is handled automatically.

## Execution

```python
# Parse mode
TEAM_MODE = "--no-team" not in ARGUMENTS

if TEAM_MODE:
    # ═══ TEAM MODE: Skill sequences phases directly ═══

    # State management
    Write(".rtl-agent-team/state/rat-auto-design-state.json",
      { "schema_version": "3.0", "status": "running",
        "current_phase": 1, "execution_mode": "team",
        "phases": { "1": {"status":"pending"}, "2": {"status":"pending"},
                    "3": {"status":"pending"}, "4": {"status":"pending"},
                    "5": {"status":"pending"}, "6": {"status":"pending"} } })

    # Phase 1: Research (team)
    Skill(skill="rtl-agent-team:rtl-p1-research-team", args="$ARGUMENTS")
    # Gate check + state update

    # Phase 2: Architecture + RefC (team)
    Skill(skill="rtl-agent-team:rtl-p2-arch-team", args="Phase 1 complete")
    # Gate check + state update

    # Phase 3: uArch + BFM (team)
    Skill(skill="rtl-agent-team:rtl-p3-uarch-team", args="Phase 2 complete")
    # Gate check + state update

    # Phase 4: RTL Implementation (team)
    Skill(skill="rtl-agent-team:rtl-p4-implement-team", args="Phase 3 complete")
    # Gate check + state update

    # Phase 5: Verification (team)
    Skill(skill="rtl-agent-team:rtl-p5-verify-team", args="Phase 4 complete")
    # Gate check + state update

    # Phase 6: Design Review (no team — sequential only)
    Bash("mkdir -p reviews/phase-6-review")
    Task(subagent_type="rtl-agent-team:p6-review-orchestrator",
         prompt="Execute Phase 6 design review. Context: Phase 5 PASS.")

    # Mark completed (stop-gate.sh reads top-level "status" to allow exit)
    # Write completed status BEFORE cleanup so stop hook sees it
    Bash("sed -i 's/\"status\": \"running\"/\"status\": \"completed\"/' .rtl-agent-team/state/rat-auto-design-state.json")
    # Cleanup state
    Bash("rm -f .rtl-agent-team/state/rat-auto-design-state.json")

else:
    # ═══ SEQUENTIAL MODE: Delegate to autopilot-orchestrator ═══
    Task(subagent_type="rtl-agent-team:autopilot-orchestrator",
         prompt="Execute full RTL autopilot pipeline. --no-team. User input: $ARGUMENTS")
```

Team mode uses native teams within each phase for parallel execution (Orchestrator as Teammate pattern).
Each phase team skill handles its own TeamCreate/TeamDelete lifecycle with a coordinator teammate + 3-5 workers.
Sequential mode delegates everything to the autopilot-orchestrator.
