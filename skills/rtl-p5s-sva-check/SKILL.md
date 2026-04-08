---
name: rtl-p5s-sva-check
description: "This skill should be used when proving or disproving formal properties on RTL using SymbiYosys BMC and induction. Triggers on 'formal verification', 'prove property', 'SVA'."
user-invocable: true
argument-hint: "[module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Extract SystemVerilog Assertions from RTL and run formal verification.
Outputs: formal/*.sv assertion files + formal_verify.json with prove/fail status per property.

See `references/sva-patterns.md` for SVA temporal operator reference, common assertion patterns,
and SymbiYosys engine selection guide.
</Purpose>

<Use_When>
- RTL is lint-clean and protocol or safety properties need formal proof
- Exhaustive corner-case coverage is required (not achievable by simulation)
- A specific property needs to be proved or disproved
</Use_When>

<Do_Not_Use_When>
- Design is too large for formal (state explosion) — use rtl-p5s-func-verify with coverage instead
- Only simulation-based testing needed
</Do_Not_Use_When>

<Why_This_Exists>
Simulation cannot exhaustively cover all corner cases. Formal verification proves properties
hold for all possible inputs, catching bugs that would take millions of simulation cycles to find.
SymbiYosys is open-source and integrates cleanly with Yosys-based flows.
</Why_This_Exists>

## Prerequisites

RTL modules required:
- `rtl/**/*.sv` files must exist

If prerequisite is missing: WARNING — recommend running `/rtl-agent-team:rtl-p4-implement`.
Proceed with available artifacts — orchestrator will adapt scope.

## Execution

Task(subagent_type="rtl-agent-team:p5s-sva-orchestrator",
     prompt="Execute SVA formal verification. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages 3-round SVA refinement, sv2v conversion,
SymbiYosys BMC/induction execution, and counterexample diagnosis.
