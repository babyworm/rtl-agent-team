---
name: rat-p4p5-impl-verify
description: "Phase 4-to-5 pipeline: implement RTL then verify from existing P1-3 docs, with P5-to-P4 feedback; stops before Phase 6. Trigger: 'implement and verify'."
user-invocable: true
argument-hint: "[resume or module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Execute the Phase 4→5 pipeline (RTL Implementation → Verification) from existing
Phase 1-3 design documents. Produces RTL code, unit tests, and full verification
with feedback loops, stopping before Phase 6 Design Note.
</Purpose>

<Use_When>
- Phase 1-3 design documents exist and RTL implementation is needed
- User says "implement and verify", "uarch to verify", "Phase 4 and 5"
- Need RTL + verification but not design review (Phase 6)
</Use_When>

<Do_Not_Use_When>
- Phase 3 μArch specs are not complete (run rat-p1p3-spec-uarch first)
- Only need RTL implementation without verification (use rtl-p4-implement)
- Need the full pipeline from spec (use rat-auto-design)
</Do_Not_Use_When>

## Prerequisites

Phase 3 completion with review required:
- `docs/phase-3-uarch/` must contain at least one μArch spec
- `reviews/phase-3-uarch/uarch-review.md` must exist

If prerequisites are missing: WARNING — recommend completing Phase 1-3
(via `/rtl-agent-team:rat-p1p3-spec-uarch`). Proceed with available artifacts — orchestrator will adapt scope.

## Execution

Task(subagent_type="rtl-agent-team:uarch-to-verify-orchestrator",
     prompt="Execute Phase 4→5 RTL implementation and verification pipeline. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages prerequisite verification, dual-stream Phase 4,
sub-phase Phase 5, feedback loops, and state management.
