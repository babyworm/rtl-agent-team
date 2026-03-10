---
name: rtl-uarch-to-verify
description: "This skill should be used when implementing RTL and running verification from existing microarchitecture documents (Phase 4→5). Requires completed Phase 1-3 artifacts as prerequisites. Produces RTL code, unit tests, and full verification with Phase 5→4 feedback loops — stopping before Design Note phase."
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
- Phase 3 μArch specs are not complete (run rtl-spec-to-uarch first)
- Only need RTL implementation without verification (use rtl-p4-implement)
- Need the full pipeline from spec (use rat-auto-design)
</Do_Not_Use_When>

## Prerequisites

Phase 3 completion with review required:
- `docs/phase-3-uarch/` must contain at least one μArch spec
- `reviews/phase-3-uarch/uarch-review.md` must exist

If prerequisites are missing: WARNING — recommend completing Phase 1-3
(via `/rtl-agent-team:rtl-spec-to-uarch`). Proceed with available artifacts — orchestrator will adapt scope.

## Execution

Task(subagent_type="rtl-agent-team:uarch-to-verify-orchestrator",
     prompt="Execute Phase 4→5 RTL implementation and verification pipeline. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages prerequisite verification, dual-stream Phase 4,
sub-phase Phase 5, feedback loops, and state management.
