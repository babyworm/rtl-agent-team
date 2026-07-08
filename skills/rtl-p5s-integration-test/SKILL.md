---
name: rtl-p5s-integration-test
description: "P5 Tier 4 integration tests: cross-module data flow, reset propagation, boundary handshakes. Triggers 'integration test', 'end-to-end system verification'."
user-invocable: true
argument-hint: "[top-module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Run Tier 4 integration-level tests on the complete RTL system. Verifies cross-module interactions: data flows end-to-end with correct values, reset propagates to all sub-modules, clocks are connected correctly, and handshake protocols are observed across module boundaries. Outputs: `sim/top/integration_results.json` (per-test PASS/FAIL) and `reviews/phase-5-verify/integration-test-report.md`.
</Purpose>

<Use_When>
- All modules pass Tier 2 unit tests and Tier 3 module regression (PASS or PARTIAL_PASS).
- Cross-module interactions need verification (interface mismatches, protocol handshakes).
- Phase 5 integration verification step is required.
- Multi-module RTL changes may have affected interface compatibility.
</Use_When>

<Do_Not_Use_When>
- Individual modules still fail Tier 2 unit tests — fix at Tier 2 first.
- Only single-module regression is needed — use `rtl-p5s-func-verify` (Tier 3).
- Performance measurement is the goal — use `rtl-p5s-perf-verify`.
- Standards conformance bitexact testing is needed — use `rtl-conformance-test`.
</Do_Not_Use_When>

<Why_This_Exists>
Modules that pass individually may fail when connected due to interface mismatches, protocol violations, or timing assumptions that do not hold across boundaries. Integration testing catches: port width mismatches, reset not propagating to all sub-modules, backpressure not flowing through the pipeline, and data corruption at handoff points. These bugs are invisible to per-module testing.
</Why_This_Exists>

## Prerequisites

- All modules pass Tier 2 (`rtl-p4s-unit-test`) and Tier 3 (`rtl-p5s-func-verify`) — PASS or PARTIAL_PASS.
- RTL source files exist under `rtl/**/*.sv`.
- Phase 2 refC model output available as end-to-end reference oracle.

If prerequisites are missing: WARNING — recommend completing Tier 2 and Tier 3 first. Orchestrator adapts scope with available artifacts.

<Assets>
| Path | Role |
|------|------|
| `templates/integration-tb-template.sv` | Top-level integration TB scaffold: multi-module DUT instantiation, clock/reset generation, connectivity checker, data flow monitors. |
| `scripts/check_connectivity.py` | Stub: static port width/direction checker across module boundaries. (deep-fill in follow-up PR) |
| `references/integration-test-conventions.md` | Tier ordering, test categories, JSON schema, report structure, anti-patterns. |
| `examples/` | (placeholder — deep-fill in follow-up PR) |
</Assets>

<Responsibility_Boundary>
- **Scripts** handle deterministic checks: static connectivity analysis (port width/direction mismatches at module boundaries) before dynamic simulation is run.
- **LLM** handles interpretive analysis: handshake protocol observation, reset propagation verification narrative, and end-to-end reference comparison result interpretation.
- Contract surface: `integration_results.json` schema and test categories documented in `references/integration-test-conventions.md`.
</Responsibility_Boundary>

<Execution>
1. Read `skills/rtl-p5s-integration-test/references/integration-test-conventions.md` for Tier 4 context, test categories, JSON schema, and report structure.
2. Spawn `p5s-integration-orchestrator` (see Tool_Usage) to run the full integration test suite.
3. The orchestrator runs static connectivity checks first (port width/direction mismatches), then dynamic tests: data flow, reset propagation, handshake protocol, and end-to-end reference comparison using the Phase 2 refC model output as oracle.
4. The orchestrator writes `sim/top/integration_results.json` with one entry per test case (category, verdict, failure detail).
5. The orchestrator writes `reviews/phase-5-verify/integration-test-report.md` with the test results table, failure details (module boundary, signal path, first failure cycle), and a recommendation.
6. Report the overall verdict and both output paths to the user.

Apply steps 1-6 to every requested top-level module — do not stop after the first.
</Execution>

<Tool_Usage>
Integration test orchestration:
```
Task(subagent_type="rtl-agent-team:p5s-integration-orchestrator",
     prompt="Execute Tier 4 integration testing. User input: $ARGUMENTS")
```

Do not perform simulation work directly — the orchestrator manages connectivity checks, data flow tests, reset propagation tests, handshake verification, and end-to-end reference comparison.
</Tool_Usage>

<Examples>
<example index="1">
<scenario>Video codec top-level after all per-module Tier 2 and Tier 3 tests pass; verifying the full encode pipeline end-to-end.</scenario>
<reference>skills/rtl-p5s-integration-test/examples/</reference>
<expected_output>Static connectivity check passes; all 5 data flow tests PASS; reset propagation PASS; end-to-end output matches refC oracle — overall PASS. Report recommends proceeding to final compliance and `rtl-p6-design-review`.</expected_output>
</example>

<example index="2">
<scenario>AXI-Stream handshake fails at the boundary between the entropy coder and the bitstream packer due to a width mismatch.</scenario>
<reference>skills/rtl-p5s-integration-test/examples/</reference>
<expected_output>Static connectivity check reports `o_bin_val[7:0]` (cabac_encoder) connected to `i_data[15:0]` (bitstream_packer) — width mismatch. Dynamic simulation skipped. Report flags the boundary with signal paths; recommends Tier 2 re-run for both modules after RTL fix.</expected_output>
</example>

<example index="3">
<scenario>Reset de-assertion reaches the top module but one sub-module never exits its reset state.</scenario>
<reference>skills/rtl-p5s-integration-test/examples/</reference>
<expected_output>Reset propagation test FAIL: `u_range_coder` remains in reset state 5 cycles after `sys_rst_n` de-asserts. `integration_results.json` records the failure with the first divergence cycle. Report identifies the missing reset connection in the instantiation.</expected_output>
</example>
</Examples>

<Escalation_And_Stop_Conditions>
- Static connectivity check fails → report all width/direction mismatches; do not proceed to dynamic simulation.
- Individual modules still fail Tier 2 or Tier 3 → emit WARNING; integration results from pre-passing modules are not reliable.
- End-to-end reference comparison requires refC model output that is absent → note the missing oracle; mark `end_to_end` tests as `"verdict": "SKIP"` rather than fabricating comparison values.
- All dynamic tests pass but `end_to_end` fails → report FAIL; do not override with PARTIAL_PASS.
</Escalation_And_Stop_Conditions>

## Output

- `sim/top/integration_results.json` — per-test PASS/FAIL with category and failure details.
- `reviews/phase-5-verify/integration-test-report.md` — cross-module test results, failure signal paths, and recommendation.

<Final_Checklist>
- [ ] Static connectivity check run before any dynamic simulation.
- [ ] All five test categories attempted: connectivity, data_flow, reset_propagation, handshake, end_to_end.
- [ ] `sim/top/integration_results.json` written with one entry per test.
- [ ] `reviews/phase-5-verify/integration-test-report.md` written with failure details and recommendation.
- [ ] End-to-end comparison uses Phase 2 refC model output as oracle — no fabricated reference values.
- [ ] RTL source not modified.
</Final_Checklist>
