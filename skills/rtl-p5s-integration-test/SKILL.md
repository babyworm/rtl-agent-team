---
name: rtl-p5s-integration-test
description: "Tier 4 integration testing: full system-level verification of cross-module data flow, reset propagation, clock connectivity, and end-to-end scenarios."
---

<Purpose>
Run integration-level tests on the complete RTL system. Verifies that modules work
correctly together: data flows through the pipeline end-to-end, reset propagates
to all sub-modules, clocks are connected correctly, and handshake protocols work
across module boundaries. This is Tier 4 testing — runs after Tier 2 (unit) and
Tier 3 (module regression) pass.

**Testing Tier Context:**
```
Tier 1: Smoke Test     — connectivity, R/W, basic ops (rtl-p4-implement Wave 4)
Tier 2: Unit Test      — reference comparison, uarch features (rtl-p4s-unit-test)
Tier 3: Module Regr.   — cocotb multi-seed (rtl-p5s-func-verify)
Tier 4: Integration    — cross-module, end-to-end (THIS SKILL) ←
```

Outputs: sim/top/integration_results.json + sim/top/ test files.
</Purpose>

<Use_When>
- All modules pass Tier 2 unit tests and Tier 3 module regression
- Need to verify cross-module interactions
- Phase 5 integration verification
- Top-level system-level test before final compliance
- After multi-module RTL changes that may affect interfaces
</Use_When>

<Do_Not_Use_When>
- Individual modules still failing unit tests (fix at Tier 2 first)
- Only need single-module regression (use rtl-p5s-func-verify — Tier 3)
- Performance measurement (use rtl-p5s-perf-verify)
- Standards conformance bitexact testing (use rtl-conformance-test)
</Do_Not_Use_When>

<Why_This_Exists>
Modules that pass individually may fail when connected due to interface mismatches,
protocol violations, or timing assumptions that don't hold across boundaries.
Integration testing catches: width mismatches at module boundaries, reset not propagating
to all sub-modules, backpressure not flowing through the pipeline, and data corruption
at interface handoff points. These bugs are invisible to per-module testing.
</Why_This_Exists>

<Delegation>
Spawn the p5s-integration-orchestrator agent to manage Tier 4 integration testing.
The orchestrator runs static connectivity checks first, then dynamic data flow and
handshake tests, and performs end-to-end reference comparison.

All coding conventions, test ordering, result schema, and escalation rules are defined
in the rtl-p5s-integration-policy skill (loaded via the orchestrator's skills: field).

Agent: p5s-integration-orchestrator
Input: Top-level module, architecture.md, io_definition.json
Output: sim/top/integration_results.json + sim/top/ test files
</Delegation>
