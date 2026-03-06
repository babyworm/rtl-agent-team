---
name: rtl-p6-design-review
description: "Phase 6: Design Review & Documentation with 2-round consistency checks, detailed design notes with decision rationale, and PDF generation support."
user-invocable: true
argument-hint: "[options]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Execute Phase 6 design review and documentation pipeline. Produces comprehensive
design notes with decision rationale, 2-round consistency checks (CC1, CC2),
code quality and design quality reviews, and optional PDF generation.
</Purpose>

<Use_When>
- Phase 5 verification has passed (verdict=PASS)
- User says "design review", "design note", "Phase 6", "documentation"
- Need comprehensive design documentation with quality assessment
</Use_When>

<Do_Not_Use_When>
- Phase 5 verification has not passed (run rtl-p5-verify first)
- Only need RTL documentation without review (use rtl-document)
- Only need a code review (use arch-review or specific reviewer agent)
</Do_Not_Use_When>

## Prerequisites

Phase 5 completion required:
- `reviews/phase-5-verify/final-compliance.md` must exist with verdict=PASS

If prerequisite is missing: WARNING — recommend running `/rtl-agent-team:rtl-p5-verify`.
Proceed with available artifacts — orchestrator will adapt scope.

## Execution

Task(subagent_type="rtl-agent-team:p6-review-orchestrator",
     prompt="Execute Phase 6 design review and documentation pipeline. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages Phase 5→6 gate check, 2-wave parallel execution,
2-round consistency checks (CC1, CC2), completion quality gate,
and optional PDF generation.
