---
name: rtl-p5-verify
description: "Phase 5 verification orchestrator: three-stage (module→top→final) parallel verification pipeline covering lint, SVA/formal, CDC, protocol, functional regression, coverage, performance, synthesizability estimation, and code review."
user-invocable: true
argument-hint: "[--module=name | --stage=N | --resume]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Execute Phase 5 verification pipeline. Runs three-stage verification
(module → top → final) covering 9 verification categories with module
graduation gates and compliance review.
</Purpose>

<Use_When>
- Phase 4 RTL implementation is complete with lint passing
- User says "verify", "verification", "Phase 5", "run all checks"
- Need comprehensive verification: lint, formal, CDC, functional, coverage, synthesis
</Use_When>

<Do_Not_Use_When>
- RTL modules don't exist yet (run rtl-p4-implement first)
- Only need functional regression (use rtl-p5s-func-verify)
- Only need a specific verification category (use the category-specific skill)
</Do_Not_Use_When>

## Prerequisites

Phase 4 completion required:
- `rtl/**/*.sv` files must exist
- `reviews/phase-4-rtl/lint-report.md` must exist (lint PASS)

If prerequisites are missing, inform the user to run `/rtl-agent-team:rtl-p4-implement` first.

## Execution

Task(subagent_type="rtl-agent-team:p5-verify-orchestrator",
     prompt="Execute Phase 5 verification. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages all stages, module graduation,
parallel agent spawning, and compliance review.
