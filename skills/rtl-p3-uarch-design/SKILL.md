---
name: rtl-p3-uarch-design
description: "Phase 3 uArch design. Concretizes P2 modules into sub-blocks with clock domains, protocol assignment, register/SRAM/FSM allocation. Validates via TLM-based BFM with per-block I/O logging."
user-invocable: true
argument-hint: "[--resume | uarch-focus]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion
---

<Purpose>
Execute Phase 3 μArch design pipeline. Concretizes architecture blocks into
implementable microarchitecture specifications with clock domains, protocol
assignments, register/SRAM/FSM allocation, and BFM validation.
</Purpose>

<Use_When>
- Phase 2 architecture is complete and μArch design is needed
- User says "microarchitecture", "uarch", "Phase 3"
- Need detailed module specs before RTL implementation
</Use_When>

<Do_Not_Use_When>
- Phase 2 architecture is not complete (run p2-arch-design first)
- Already have μArch specs and need RTL (use rtl-p4-implement)
- Need architecture-level design (use p2-arch-design)
</Do_Not_Use_When>

## Prerequisites

Phase 2 completion required:
- `docs/phase-2-architecture/architecture.md` must exist

If prerequisite is missing: WARNING — recommend running `/rtl-agent-team:p2-arch-design`.
Proceed with available artifacts — orchestrator will adapt scope.

## Execution

Task(subagent_type="rtl-agent-team:p3-uarch-orchestrator",
     prompt="Execute Phase 3 uArch design. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages domain consultation, parallel uarch design + BFM
development, BFM validation gate, and 5-reviewer 3-round review.
