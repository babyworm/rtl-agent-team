---
name: rtl-p4-rapid-impl
description: "Phase 4 rapid RTL implementation and sanity integration. Focuses on module design correctness, fast feedback loops, and block-level integration sanity before deep verification."
user-invocable: true
argument-hint: "[module-list or --all]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Run Phase 4 rapid loop for RTL module implementation and block-level sanity integration.
This phase optimizes for fast detection of functional breakage and interface mismatches.
</Purpose>

<Use_When>
- Microarchitecture is complete and RTL coding must begin
- User wants quick but structured implementation validation before deep closure
- Need module + block sanity with lint/cdc/functional minimum gates
- Need a fast Phase-4 loop before full 10-Wave implementation flow
- Need early risk reduction, then plan to continue into P5A/P5B
</Use_When>

<Do_Not_Use_When>
- Requirements/architecture are not stable yet
- Need full functional closure or top exactness verification (use rtl-p5a-functional-closure / rtl-p5b-silicon-validation)
- Need full 10-Wave Phase-4 pipeline with detailed review/refactor/integration artifacts (use rtl-p4-implement)
- Need full 10-Wave pipeline with code review, protocol checks, refactoring, and Stream B artifacts (use rtl-p4-implement instead)
</Do_Not_Use_When>

## Execution

Task(subagent_type="rtl-agent-team:p4-rtl-sanity-orchestrator",
     prompt="Execute Phase 4 rapid RTL implementation and sanity integration. User input: $ARGUMENTS")

Do not perform work directly.
The orchestrator controls sequencing and gate checks.
