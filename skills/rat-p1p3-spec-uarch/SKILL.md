---
name: rat-p1p3-spec-uarch
description: "Phase 1-3 to uArch, sequential or team; stops before RTL. Use for 'spec to uarch', 'design only', 'Phase 1-3 team'."
user-invocable: true
argument-hint: "[spec-file or project-description | --resume | team]"
allowed-tools: Read, Write, Edit, Task, Grep, Glob, AskUserQuestion, Skill, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate
---

Delegate using the current host as described in `{plugin_root}/runtime/model-selection.md`.

<Purpose>
Execute the Phase 1→3 pipeline (Research → Architecture → μArch) with enforced
dual-layer phase gates, then STOP for human review before RTL implementation.
Produces all design documents needed for RTL coding.
</Purpose>

<Use_When>
- Need complete design documents before RTL implementation
- Want human review checkpoint between design and implementation
- User says "spec to uarch", "design only", "Phase 1 to 3"
- User says "spec to uarch team", "Phase 1-3 team", "parallel design pipeline"
- Starting from scratch and want to stop before RTL coding
</Use_When>

<Do_Not_Use_When>
- Already have uarch docs and need RTL implementation (use rat-p4p5-impl-verify)
- Need the full pipeline including RTL (use rat-auto-design)
- Only need a single phase (use the phase-specific skill; pass `team` on that skill for parallel workers)
</Do_Not_Use_When>

Forward the run-scoped Codex review choice (`review_scope`) to each phase, including on resume, as specified in `{plugin_root}/runtime/phase-dispatch.md`.

## Mode

Team mode when `$ARGUMENTS` contains the word `team`, or the user asked for a team, parallel workers, or `rat-p1p3-spec-uarch-team`. Otherwise sequential. `--resume` stays sequential unless team mode also applies.

## Prerequisites

None — this pipeline starts from Phase 1.
Specification documents should be available in `specs/` directory.

## Sequential

Task(subagent_type="rtl-agent-team:spec-to-uarch-orchestrator",
     prompt="Execute Phase 1→3 spec-to-uarch pipeline. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages phase sequencing, one review per phase,
quality gates, ADR recording, and state management.

## Team mode

This skill sequences the three phase skills in team mode. Each phase skill
handles its own TeamCreate/TeamDelete lifecycle. This skill enforces the
inter-phase artifact gates and does not create a team of its own.

```python
# Legacy migration: rename pre-0.6.10 state file ONLY if new file does not exist
legacy = Read(".rat/state/rtl-spec-to-uarch-state.json")  # may not exist
if legacy:
    new_exists = Read(".rat/state/rat-p1p3-spec-uarch-state.json")  # check new file
    if not new_exists:
        Bash("mv .rat/state/rtl-spec-to-uarch-state.json .rat/state/rat-p1p3-spec-uarch-state.json")

# Initialize or resume state
state = Read(".rat/state/rat-p1p3-spec-uarch-state.json")  # may not exist

if state:
    # Keep partial P1 and completed phases. Use the saved choice unless the user changes it.
    review_scope = current_request_choice or state.get("review_scope") or "project"
else:
    # Fresh start
    review_scope = current_request_choice or "project"
    Write(".rat/state/rat-p1p3-spec-uarch-state.json",
      { "schema_version": "3.0", "current_phase": 1, "pipeline_scope": "phase-1-to-3",
        "execution_mode": "team", "review_scope": review_scope,
        "phases": {
          "1": { "status": "pending" },
          "2": { "status": "pending" },
          "3": { "status": "pending" }
        }
      })

# Persist review_scope in the pipeline state before dispatch.

# ── Phase 1: Research (team) ──────────────────────────────────
if phases["1"]["status"] != "completed":
    Skill(skill="rtl-agent-team:p1-spec-research", args="team $ARGUMENTS {review_scope}")

    # Phase 1→2 artifact gate (iron-requirements is the settled SSOT;
    # open-requirements is optional — absent if Phase 1 had no deferred research)
    Glob("docs/phase-1-research/iron-requirements.json")
    Glob("docs/phase-1-research/io_definition.json")
    Glob("docs/phase-1-research/timing_constraints.json")
    Glob("docs/phase-1-research/domain-analysis.md")
    # All four required artifacts must exist. If missing: FAIL.

    # Update state
    # phases["1"]["status"] = "completed"

# ── Phase 2: Architecture + RefC (team) ───────────────────────
if phases["2"]["status"] != "completed":
    Skill(skill="rtl-agent-team:p2-arch-design", args="team Phase 1 artifacts complete {review_scope}")

    # Phase 2→3 artifact gate
    Glob("docs/phase-2-architecture/architecture.md")
    Glob("refc/**/*.c")
    # Must exist. If missing: FAIL.

    # Update state
    # phases["2"]["status"] = "completed"

# ── Phase 3: uArch + BFM (team) ──────────────────────────────
if phases["3"]["status"] != "completed":
    Skill(skill="rtl-agent-team:rtl-p3-uarch-design", args="team Phase 2 artifacts complete {review_scope}")

    # Phase 3 artifact gate
    Glob("docs/phase-3-uarch/*.md")
    Glob("bfm/")
    # Must exist. If missing: FAIL.

    # Update state
    # phases["3"]["status"] = "completed"

# ── Completion ────────────────────────────────────────────────
# Report: Phase 1-3 artifacts, reviews, ADR count
# Suggest: "Run /rtl-agent-team:rat-p4p5-impl-verify to begin RTL implementation"
# Do NOT proceed to Phase 4
```

If a phase skill's TeamCreate fails, that skill runs its sequential section.
Do NOT proceed to Phase 4. Suggest `/rtl-agent-team:rat-p4p5-impl-verify`.
