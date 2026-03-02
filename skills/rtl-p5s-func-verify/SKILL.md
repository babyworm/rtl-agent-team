---
name: rtl-p5s-func-verify
description: "Tier 3 module-level regression: cocotb multi-seed regression comparing RTL against reference models. Absorbs rtl-regression-run. Produces Requirement Traceability Matrix."
user-invocable: true
argument-hint: "[module-name --seeds=N]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Execute functional verification with cocotb-based multi-seed regression.
Compares RTL simulation outputs against C/Python reference models for
bitexact agreement. Produces regression results and Requirement Traceability Matrix.
</Purpose>

<Use_When>
- RTL modules exist and need functional regression testing
- User says "functional verification", "regression", "cocotb test", "multi-seed"
- Need to compare RTL against reference model
- Need Requirement Traceability Matrix
</Use_When>

<Do_Not_Use_When>
- RTL modules don't exist yet (run rtl-p4-implement first)
- Need full Phase 5 verification (use rtl-p5-verify)
- Only need a single unit test (use rtl-p4s-unit-test)
</Do_Not_Use_When>

## Prerequisites

RTL modules required:
- `rtl/**/*.sv` files must exist

If prerequisite is missing, inform the user to run `/rtl-agent-team:rtl-p4-implement` first.

## Execution

Task(subagent_type="rtl-agent-team:p5s-func-verify-orchestrator",
     prompt="Execute functional verification. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages pipelined TB generation, multi-seed parallel
regression, coverage analysis, and requirement traceability.
