---
name: rat-auto-design
description: "Full 6-phase RTL pipeline from spec to verified design (P1 research through P6 design note). Triggers: 'design a chip', 'full pipeline', 'autopilot'."
user-invocable: true
argument-hint: "[spec-file or project-description]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion, Skill, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate
---

Delegate using the current host as described in `{plugin_root}/runtime/model-selection.md`.

Run P1 through P6 from the supplied specification. Team mode is the default
when team tools are available. For `--no-team` or a host without teams,
use the host's sequential delegation:

```
Task(subagent_type="rtl-agent-team:autopilot-orchestrator",
     prompt="Run the full pipeline sequentially. User input and review scope: $ARGUMENTS.")
```

Follow `{plugin_root}/runtime/phase-dispatch.md`. Capture the user's Codex
review choice as `review_scope` (including any phases named); preserve it on
resume and forward it to each phase owner. A run override is local to this run.

## Team mode

Initialize or resume `.rat/state/rat-auto-design-state.json` (schema 3.0).
Persist `review_scope`, execution mode, current phase, evidence and cross-review
results. On resume, keep the saved scope unless explicitly changed. Dispatch
pending phases in order after the preceding gate passes. For a completed
phase, rerun only work invalidated by changed inputs or a newly requested
review. Reuse its current evidence.

```
Skill(skill="rtl-agent-team:p1-spec-research", args="team $ARGUMENTS {review_scope}")
Skill(skill="rtl-agent-team:p2-arch-design", args="team Phase 1 complete {review_scope}")
Skill(skill="rtl-agent-team:rtl-p3-uarch-design", args="team Phase 2 complete {review_scope}")
Skill(skill="rtl-agent-team:rtl-p4-implement", args="team Phase 3 complete {review_scope}")
Skill(skill="rtl-agent-team:rtl-p5-verify", args="team Phase 4 complete {review_scope}")
Task(subagent_type="rtl-agent-team:p6-review-orchestrator",
     prompt="Run the Phase 6 design review after Phase 5 PASS. Review scope: {review_scope}.")
```

Each phase owns its workers, review and gate results. Carry failed measured
repairs into the active gate's counters on resume. At two failed repairs,
set `orchestration_control.needs_user_decision=true` and report the result.
Set top-level status to
`completed` after P6 succeeds, before the normal state-file cleanup. Preserve
interrupted state for resume.

## Output

- Design artifacts: `docs/phase-1-research/` through `docs/phase-5-verify/`
- Phase 6 design note and review verdicts: `reviews/phase-6-review/`
  (Phase 6 is the design review + documentation phase; its outputs live under `reviews/`, not `docs/`)
- `rtl/*/*.sv` — lint-clean, unit-tested RTL modules
- `sim/` — testbenches, regression results, and coverage data
- `reviews/` — per-phase review reports with final compliance verdict
