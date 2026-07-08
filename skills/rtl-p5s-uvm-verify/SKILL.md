---
name: rtl-p5s-uvm-verify
description: "P5 UVM verification on commercial simulators (VCS/Questa/Xcelium). Use when UVM methodology or constrained-random sequences/scoreboards are mandated."
user-invocable: true
argument-hint: "[module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Run a UVM-based verification environment on the target RTL using a commercial simulator
(VCS, Questa, or Xcelium). Outputs: sim/uvm/results/run_summary.log + sim/uvm/coverage/uvm_coverage.xml.

See `references/uvm-architecture.md` for UVM component hierarchy, phase order,
simulator compile commands, and agent template with project naming conventions.
</Purpose>

<Use_When>
- Project mandates UVM methodology
- Commercial simulator is available and licensed
- Complex protocol verification requiring UVM sequences and scoreboards
- Constrained-random verification with UVM agents is required
</Use_When>

<Do_Not_Use_When>
- Commercial simulator not available (use rtl-p4s-unit-test or rtl-p5s-func-verify instead)
- Simple directed tests sufficient (UVM overhead not justified)
- Open-source-only tool constraint (use cocotb via rtl-p5s-func-verify)
</Do_Not_Use_When>

<Why_This_Exists>
UVM provides reusable, scalable verification infrastructure for complex designs.
When a commercial simulator is available, UVM delivers constrained-random coverage
closure that directed testing cannot match for large state spaces.
</Why_This_Exists>

## Prerequisites

Commercial simulator required:
- One of VCS, Questa (vsim), or Xcelium (xrun) must be available

If prerequisite is missing: WARNING — commercial simulator not found.
Use `/rtl-agent-team:rtl-p5s-func-verify` (cocotb/Verilator) instead.

## Execution

Task(subagent_type="rtl-agent-team:p5s-uvm-orchestrator",
     prompt="Execute UVM verification. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages simulator availability checking, UVM environment
generation, compilation, test execution, and coverage collection.

## Output

- `sim/uvm/results/run_summary.log` — test pass/fail summary across all UVM sequences
- `sim/uvm/coverage/` — merged functional and code coverage data
- `reviews/phase-5-verify/{module}-uvm-review.md` — UVM verification review with coverage analysis
