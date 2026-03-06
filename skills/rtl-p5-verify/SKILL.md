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
This is a legacy bundled bridge while teams transition to split P5A/P5B.
</Purpose>

<Use_When>
- Phase 4 RTL implementation is complete with lint passing
- User says "verify", "verification", "Phase 5", "run all checks"
- Need comprehensive verification: lint, formal, CDC, functional, coverage, synthesis
- Need one legacy-style Phase-5 command that bundles functional + silicon-oriented checks
- Need migration bridge while adopting split flows (`rtl-p5a-functional-closure` + `rtl-p5b-silicon-validation`)
- Team workflow intentionally keeps the combined legacy Phase-5 interface
</Use_When>

<Do_Not_Use_When>
- RTL modules don't exist yet (run `rtl-p4-rapid-impl` or `rtl-p4-implement` first)
- Only need functional regression (use rtl-p5s-func-verify)
- Only need a specific verification category (use the category-specific skill)
- Want strict separation of functional closure and silicon validation
  (use `rtl-p5a-functional-closure` first, then `rtl-p5b-silicon-validation`)
- Starting a new verification flow with explicit two-stage closure
  (default to split `rtl-p5a-functional-closure` + `rtl-p5b-silicon-validation`)
</Do_Not_Use_When>

## Prerequisites

Phase 4 completion required:
- `rtl/**/*.sv` files must exist
- One of the following completion proofs must exist:
  - `reviews/phase-4-rtl/lint-report.md` (full `rtl-p4-implement` path)
  - `.rtl-agent-team/state/p4-state.json` with `gates.p4_exit.verdict` = `pass` (rapid `rtl-p4-rapid-impl` path)

If prerequisites are missing: WARNING — recommend running `/rtl-agent-team:rtl-p4-rapid-impl`
or `/rtl-agent-team:rtl-p4-implement`. Proceed with available artifacts — orchestrator will adapt scope.

## Execution

Task(subagent_type="rtl-agent-team:p5-verify-orchestrator",
     prompt="Execute Phase 5 verification. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages all stages, module graduation,
parallel agent spawning, and compliance review.
