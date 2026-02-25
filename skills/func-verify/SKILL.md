---
name: func-verify
description: "This skill should be used when running cocotb regression tests comparing RTL against reference models in Phase 5. Produces Requirement Traceability Matrix."
---

<Purpose>
Run cocotb-based regression tests comparing RTL simulation output against the C reference model.
Outputs: sim/regression/{test}_result.json per test + coverage/coverage.xml.
On failure: invoke waveform-analyzer for debug.

Leverages the cocotb ecosystem: cocotb-bus (Driver/Monitor), cocotbext-axi (AXI BFMs),
cocotb-coverage (functional coverage). See `references/cocotb-ecosystem.md` for detailed API reference.
</Purpose>

<Use_When>
- RTL passes unit tests and needs regression verification against reference model
- Adding new test vectors to the regression suite
- Debugging a regression failure
</Use_When>

<Do_Not_Use_When>
- Reference model (ref_model/) does not exist (run ref-model first)
- Only unit-level SV tests needed (use sv-unit-test instead)
- Performance comparison needed (use perf-verify instead)
</Do_Not_Use_When>

<Why_This_Exists>
cocotb allows Python-driven test control with access to the full test infrastructure.
RTL vs C comparison catches numerical and behavioral divergences that unit tests miss.
Automated regression with coverage reporting drives verification closure.

The cocotb ecosystem provides reusable bus functional models:
- **cocotb-bus**: Base classes for Driver, Monitor, and Scoreboard
- **cocotbext-axi**: Ready-to-use AXI4/AXI4-Lite/AXI4-Stream masters and slaves
- **cocotb-coverage**: Functional coverage with `@CoverPoint` and `@CoverCross` decorators
- **TestFactory**: Parameterized test generation for combinatorial test sweeps
</Why_This_Exists>

<Coding_Convention_Requirements>
cocotb test files MUST use correct signal names matching RTL port conventions (CLAUDE.md):
- Signal access: `dut.i_data` (NOT `dut.data_i`), `dut.o_valid` (NOT `dut.valid_o`)
- Clock: `dut.sys_clk` (NOT `dut.clk`, `dut.clk_i`)
- Reset: `dut.sys_rst_n` (NOT `dut.rst_ni`, `dut.rst_n`)
- cocotb clock utility: `cocotb.clock.Clock(dut.sys_clk, 10, units="ns")`
- Reset sequence: drive `dut.sys_rst_n.value = 0`, wait, then `dut.sys_rst_n.value = 1`
</Coding_Convention_Requirements>

<Execution_Policy>
- testbench-dev writes cocotb test cases (Python)
- eda-runner runs the regression via Bash CLI
- On any failure: waveform-analyzer diagnoses before reporting
- Coverage report generated regardless of pass/fail
</Execution_Policy>

<Steps>
1. `mkdir -p reviews/phase-5-verify`
2. testbench-dev writes tb/cocotb/test_{module}.py for each module
   - Use `templates/cocotb-test-template.py` as the test file scaffold
   - Signal access uses `i_`/`o_` prefixes matching RTL ports
   - Clock driven as `dut.sys_clk`, reset as `dut.sys_rst_n`
3. eda-runner compiles RTL and runs cocotb regression via Bash CLI:
   ```bash
   # Icarus Verilog (default — good SV support, fast compile)
   make -C tb/cocotb SIM=icarus TOPLEVEL={module} MODULE=test_{module}
   # Verilator (fastest simulation, FST traces)
   make -C tb/cocotb SIM=verilator TOPLEVEL={module} MODULE=test_{module} \
     EXTRA_ARGS="--trace-fst --timing"
   ```
   Use `COCOTB_RESOLVE_X=RANDOM` for X-state handling and `RANDOM_SEED=42` for reproducibility.
4. For each test: compare RTL output with ref_model output byte-by-byte
5. On mismatch: waveform-analyzer reads .vcd, identifies divergence point
6. Write sim/regression/{test}_result.json: {status, vectors_run, mismatches, divergence_cycle}
7. Generate coverage/coverage.xml via cocotb coverage plugin
8. **Requirement Traceability Matrix** (use `templates/requirement-traceability.md` as format template) **— verify all REQ items have test coverage:**
   - Read requirements.json and all test results
   - Map each REQ-NNN to the test(s) that exercise it
   - Output a Requirement Traceability Matrix:
     ```
     REQ-001: verified by test_cabac_encoder (PASS)
     REQ-002: verified by test_input_buffer (PASS)
     REQ-005: NO TEST COVERAGE — must add test
     REQ-008: verified by test_transform (FAIL — regression failure)
     ```
   - Summary:
     ```
     Traceability: [X]/[N] requirements have test coverage
     All-pass: [Y]/[X] covered requirements pass their tests
     ```
   - **Save the Requirement Traceability Matrix to `reviews/phase-5-verify/requirement-traceability.md`** in standard review Markdown format:
     ```markdown
     # Phase 5 Review: Requirement Traceability
     - Date: YYYY-MM-DD
     - Reviewer: func-verifier
     - Upper Spec: requirements.json
     - Verdict: PASS | FAIL

     ## Feature Coverage Checklist
     | REQ ID | Test Name | Result | Status |
     |--------|-----------|--------|--------|

     ## Findings
     ### [severity] Finding-N: ...

     ## Verdict
     PASS | FAIL: [reason]
     ```
   - If any REQ has NO TEST COVERAGE: testbench-dev must generate additional tests targeting the uncovered requirements
   - Re-run regression for newly added tests
   - Final verdict:
     ```
     VERDICT: PASS — all [N] requirements verified with passing tests
     ```
     or:
     ```
     VERDICT: FAIL — [M] requirements without test coverage, [K] requirements with failing tests
     ```
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Write cocotb test tb/cocotb/test_cabac_encoder.py. Use dut.sys_clk, dut.sys_rst_n, dut.i_*/dut.o_* signal naming per CLAUDE.md conventions. Drive RTL, compare output with ref_model binary on 100 random vectors.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb regression via Bash CLI: make -C tb/cocotb SIM=icarus TOPLEVEL=cabac_encoder MODULE=test_cabac_encoder. Report pass/fail per test and overall coverage.")

Task(subagent_type="rtl-agent-team:waveform-analyzer",
     prompt="Analyze sim/waveforms/cabac_encoder_fail.vcd. Find first divergence between RTL o_data and expected output.")

# Requirement Traceability Matrix (after regression completes)
Bash("mkdir -p reviews/phase-5-verify")

Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Read requirements.json and all sim/regression/*_result.json. Map each REQ-NNN to the test(s) that verify it. Output a Requirement Traceability Matrix showing per-REQ coverage status (PASS/FAIL/NO TEST COVERAGE). Save the Requirement Traceability Matrix to reviews/phase-5-verify/requirement-traceability.md in standard review Markdown format with Date, Reviewer (func-verifier), Upper Spec (requirements.json), Verdict, coverage table (REQ ID, Test Name, Result, Status), Findings, and Verdict sections. For any REQ with NO TEST COVERAGE, write additional cocotb tests targeting those requirements. Use dut.sys_clk, dut.sys_rst_n, dut.i_*/dut.o_* signal naming.")
```
</Tool_Usage>

<Examples>
<Good>
200 test vectors; cocotb uses `dut.sys_clk` and `dut.i_data`/`dut.o_valid` correctly;
198 pass; 2 fail on CABAC bypass mode; waveform-analyzer pinpoints wrong state transition
at cycle 47; RTL fix applied; rerun shows all 200 pass.
</Good>
<Bad>
Comparing only checksums instead of per-output comparison — misses byte-level misalignment bugs.
Using `dut.clk` or `dut.data_i` in cocotb — signal name mismatch causes AttributeError at runtime.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- cocotb not installed → halt, provide install command (`pip install cocotb`)
- Failure persists after 2 RTL fix rounds → escalate to rtl-architect with waveform analysis
- Coverage below 80% after full regression → invoke coverage-analyze skill
- cocotb signal name mismatch error → testbench-dev must fix to use `i_`/`o_` convention
- **Requirements with NO TEST COVERAGE after additional test generation** → escalate to user with list of untestable requirements
- **Requirement traceability verdict FAIL with persistent test failures** → escalate to rtl-code for RTL fix before re-verification
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All cocotb tests use correct signal names (`dut.i_*`, `dut.o_*`, `dut.sys_clk`, `dut.sys_rst_n`)
- [ ] All test vectors run to completion
- [ ] RTL vs ref model comparison done per vector
- [ ] Waveform analysis done for all failures
- [ ] coverage/coverage.xml generated
- [ ] sim/regression/*_result.json written per test
- [ ] **Requirement Traceability Matrix produced with per-REQ-NNN mapping**
- [ ] **Every REQ-NNN in requirements.json covered by at least one test**
- [ ] **All covered requirements pass their tests (or failures are escalated)**
- [ ] **Traceability verdict is PASS**
- [ ] **reviews/phase-5-verify/requirement-traceability.md saved with Requirement Traceability Matrix**
</Final_Checklist>

<Advanced>
Run with multiple seeds: `make SEED=42 SIM=icarus` for broader randomization coverage.
Coverage target: 90% line, 80% toggle, 70% FSM state.
Use `COCOTB_RESOLVE_X=RANDOM` to handle X propagation in simulation.

See `examples/cocotb-axi-lite-test.py` for a complete AXI-Lite register test using cocotbext-axi.

**cocotb ecosystem quick reference:**
- AXI-Lite register access: `AxiLiteMaster(AxiLiteBus.from_prefix(dut, "s_axi"), dut.sys_clk, dut.sys_rst_n, reset_active_level=False)`
- AXI-Stream data flow: `AxiStreamSource(AxiStreamBus.from_prefix(dut, "s_axis"), dut.sys_clk, dut.sys_rst_n)`
- Functional coverage: `@CoverPoint("top.data", bins=[range(0,64), range(64,256)])`
- Parameterized tests: `TestFactory(run_test).add_option("width", [8,16,32]).generate_tests()`

See `references/cocotb-ecosystem.md` for complete API reference with code examples.
</Advanced>
