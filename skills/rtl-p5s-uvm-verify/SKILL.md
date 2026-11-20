---
name: rtl-p5s-uvm-verify
description: "P5 UVM verification on commercial simulators (VCS/Questa/Xcelium). Use when UVM methodology or constrained-random sequences/scoreboards are mandated."
user-invocable: true
argument-hint: "[module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

Delegate using the current host as described in `{plugin_root}/runtime/model-selection.md`.

<Purpose>
Run a UVM-based verification environment on the target RTL using a commercial simulator
(VCS, Questa, or Xcelium). Outputs are timestamped under `sim/uvm/regression/`
with coverage artifacts under `sim/uvm/coverage/`.

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

- `sim/uvm/regression/run_{timestamp}/seed_{seed}_results.json` — per-seed pass/fail result and log path for this run only
- `sim/uvm/regression/regression_{module}_{timestamp}.json` — aggregate regression report and verdict
- `sim/uvm/coverage/` — merged vendor artifacts or `functional_{timestamp}.json`
- `reviews/phase-5-verify/{module}-uvm-review.md` — UVM verification review with coverage analysis

## Coverage and license waits

The runner defaults to `--coverage-mode auto`. It skips native coverage capture if
IMC, URG, or vcover is unavailable. If a native merge fails or times out, it uses
the functional bin records from the same passing seeds. The full coverage verdict
is `INCONCLUSIVE` (exit 3) when only functional bin coverage is collected.

Use `--coverage-mode functional-log` to run with bin logs and without vendor
coverage flags. `--coverage-mode native` requires a successful vendor merge.
`--coverage-timeout` defaults to 60 seconds per vendor coverage command.
`--sim-timeout` bounds each compile, elaboration, or seed run. It defaults to the
configured `execution.timeout_seconds` (1800 seconds without configuration).
The simulator itself still requires a license.

See [functional bin logging](references/functional-coverage-log.md) for the
testbench changes and report format. The coverage-analysis gate evaluates targets.
