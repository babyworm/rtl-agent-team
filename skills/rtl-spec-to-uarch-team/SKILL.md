---
name: rtl-spec-to-uarch-team
description: "Phase 1-3 pipeline using native teams for parallel execution within each phase. Sequences P1 research team, P2 architecture team, P3 uArch team with inter-phase quality gates."
user-invocable: true
argument-hint: "[spec-path or --resume]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion, Skill, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate
---

<Purpose>
Execute the Phase 1-3 design pipeline using Claude Code native team infrastructure
within each phase. The skill directly sequences phases, invoking each phase's team skill
for parallel execution. Inter-phase quality gates are enforced between phases.
</Purpose>

<Use_When>
- Starting complete design document pipeline from spec to uArch
- User says "spec to uarch team", "Phase 1-3 team", "parallel design pipeline"
- Want maximum parallelism within each design phase
</Use_When>

<Do_Not_Use_When>
- Only need a single phase (use the phase-specific team skill)
- Want sequential execution (use rtl-spec-to-uarch)
- Want to proceed through Phase 4-5 as well (use rtl-autopilot)
</Do_Not_Use_When>

## Prerequisites

No phase prerequisites (starts from Phase 1).
Specification documents should be available in `specs/` directory.

## Execution

```python
# Initialize or resume state
state = Read(".rtl-agent-team/state/rtl-spec-to-uarch-state.json")  # may not exist

if state and state.current_phase > 1:
    # Resume: skip completed phases
    pass
else:
    # Fresh start
    Write(".rtl-agent-team/state/rtl-spec-to-uarch-state.json",
      { "schema_version": "3.0", "current_phase": 1, "pipeline_scope": "phase-1-to-3",
        "execution_mode": "team",
        "phases": {
          "1": { "status": "pending" },
          "2": { "status": "pending" },
          "3": { "status": "pending" }
        }
      })

# ── Phase 1: Research (team) ──────────────────────────────────
if phases["1"]["status"] != "completed":
    Skill(skill="rtl-agent-team:rtl-p1-research-team", args="$ARGUMENTS")

    # Phase 1→2 artifact gate
    Glob("docs/phase-1-research/requirements.json")
    Glob("docs/phase-1-research/io_definition.json")
    Glob("docs/phase-1-research/timing_constraints.json")
    Glob("docs/phase-1-research/domain-analysis.md")
    # All four must exist. If missing: FAIL.

    # Update state
    # phases["1"]["status"] = "completed"

# ── Phase 2: Architecture + RefC (team) ───────────────────────
if phases["2"]["status"] != "completed":
    Skill(skill="rtl-agent-team:rtl-p2-arch-team", args="Phase 1 artifacts complete")

    # Phase 2→3 artifact gate
    Glob("docs/phase-2-architecture/architecture.md")
    Glob("refc/**/*.c")
    # Must exist. If missing: FAIL.

    # Update state
    # phases["2"]["status"] = "completed"

# ── Phase 3: uArch + BFM (team) ──────────────────────────────
if phases["3"]["status"] != "completed":
    Skill(skill="rtl-agent-team:rtl-p3-uarch-team", args="Phase 2 artifacts complete")

    # Phase 3 artifact gate
    Glob("docs/phase-3-uarch/*.md")
    Glob("bfm/")
    # Must exist. If missing: FAIL.

    # Update state
    # phases["3"]["status"] = "completed"

# ── Completion ────────────────────────────────────────────────
# Report: Phase 1-3 artifacts, reviews, ADR count
# Suggest: "Run /rtl-agent-team:rtl-uarch-to-verify to begin RTL implementation"
# Do NOT proceed to Phase 4
```

Each phase's team skill handles its own TeamCreate/TeamDelete lifecycle.
This skill sequences phases and enforces inter-phase quality gates.
