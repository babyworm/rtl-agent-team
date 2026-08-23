---
name: rtl-p5s-sva-check
description: "P5 formal verification: SVA proof via SymbiYosys BMC/induction on lint-clean RTL. Triggers 'formal verification', 'prove property', 'SVA'."
user-invocable: true
argument-hint: "[module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Extract formal properties from RTL and run formal verification.
Outputs:
- `formal/*_props.sv` commercial/full-SVA assets for bind-file flows
- `formal/*_formal_harness.sv` OSS SymbiYosys harness tops with procedural immediate `assert`/`assume`/`cover`
- `formal/formal_verify_{module}.json` with aggregate task-level formal results

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
The orchestrator agent manages 3-round SVA refinement, explicit DUT-only sv2v
conversion, OSS harness generation, SymbiYosys BMC/prove/cover execution, and
counterexample diagnosis. Full concurrent SVA assets are not routed through sv2v;
sv2v can drop formal semantics.
