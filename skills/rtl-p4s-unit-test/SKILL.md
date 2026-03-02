---
name: rtl-p4s-unit-test
description: "Tier 2 unit testing: verify each RTL module against its uarch specification and C reference model. Goes beyond Tier 1 smoke to exercise FSM transitions, pipeline behavior, and data transformations."
user-invocable: true
---

<Purpose>
Write and run unit tests that verify each RTL module implements its microarchitecture
specification correctly. Compares RTL output against the C reference model for functional
correctness. Goes beyond Tier 1 smoke testing (rtl-p4-implement Wave 4) to exercise key features
at uarch level: FSM state transitions, pipeline stage behavior, data transformation accuracy.

**Testing Tier Context:**
```
Tier 1: Smoke Test     — connectivity, R/W, basic ops (rtl-p4-implement Wave 4)
Tier 2: Unit Test      — reference comparison, uarch features (THIS SKILL) ←
Tier 3: Module Regr.   — cocotb multi-seed (rtl-p5s-func-verify)
Tier 4: Integration    — cross-module, end-to-end (rtl-p5s-integration-test)
```

Outputs: sim/{module}/tb_{module}.sv testbench files + sim/{module}/{module}_unit_results.json.
</Purpose>

<Use_When>
- Phase 4 RTL is lint-clean AND Tier 1 smoke test passed (rtl-p4-implement Wave 4)
- Each module needs uarch-level functional verification with reference comparison
- A new module's key features need targeted testing beyond connectivity
- A bug fix needs regression test verifying the fix against reference model
</Use_When>

<Do_Not_Use_When>
- Only basic connectivity/R/W verification needed (covered by rtl-p4-implement Wave 4 smoke — Tier 1)
- Full multi-seed regression needed (use rtl-p5s-func-verify — Tier 3)
- Integration/cross-module testing (use rtl-p5s-integration-test — Tier 4)
- Formal verification preferred (use rtl-p5s-sva-check instead)
</Do_Not_Use_When>

<Why_This_Exists>
Tier 1 (smoke) only verifies connectivity and basic I/O. Tier 2 unit tests verify that each
module implements its uarch spec — FSM states, pipeline stages, data transformations — using
the C reference model as the golden oracle. This catches behavioral bugs that smoke tests miss,
while remaining faster and more targeted than full regression (Tier 3).
</Why_This_Exists>

<Delegation>
The orchestrator writes testbenches per module (parallel via testbench-dev), selects
reference comparison mode (DPI-C or file-based), runs simulations, and handles
failure triage with waveform analysis.

All coding conventions, reference mode rules, escalation criteria, and result schemas
are defined in the rtl-p4s-unit-test-policy skill (loaded via the orchestrator's skills: field).

## Execution

Task(subagent_type="rtl-agent-team:p4s-unit-test-orchestrator",
     prompt="Execute Tier 2 unit testing. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages testbench generation, simulation, and failure triage.
</Delegation>
