---
name: rtl-func-verify
description: "Tier 3 module-level regression: cocotb multi-seed regression comparing RTL against reference models. Absorbs rtl-regression-run. Produces Requirement Traceability Matrix."
---

<Purpose>
Run cocotb-based module-level regression tests with multi-seed coverage, comparing RTL simulation
output against the C reference model. This is Tier 3 testing — comprehensive module-level regression
that goes beyond Tier 2 unit tests with randomized stimulus and coverage closure.

**Testing Tier Context:**
```
Tier 1: Smoke Test     — connectivity, R/W, basic ops (rtl-code Wave 4)
Tier 2: Unit Test      — reference comparison, uarch features (rtl-sv-unit-test)
Tier 3: Module Regr.   — cocotb multi-seed (THIS SKILL) ←
Tier 4: Integration    — cross-module, end-to-end (rtl-integration-test)
```

**Note:** This skill absorbs the former `rtl-regression-run` skill. Multi-seed regression,
coverage collection, and failure tracking are now unified here.

Outputs: sim/regression/{test}_result.json per test + sim/coverage/coverage.xml.
On failure: invoke waveform-analyzer for debug.

Leverages the cocotb ecosystem: cocotb-bus (Driver/Monitor), cocotbext-axi (AXI BFMs),
cocotb-coverage (functional coverage). See `references/cocotb-ecosystem.md` for detailed API reference.
</Purpose>

<Use_When>
- RTL passes Tier 2 unit tests and needs multi-seed regression verification
- Adding new test vectors to the regression suite
- Debugging a regression failure
- Full multi-seed regression gate (pre-tapeout, coverage closure)
- Coverage closure requires multi-seed runs
</Use_When>

<Do_Not_Use_When>
- Reference model (refc/) does not exist (run ref-model first)
- Only unit-level SV tests needed (use rtl-sv-unit-test — Tier 2)
- Integration/cross-module testing needed (use rtl-integration-test — Tier 4)
- Performance comparison needed (use rtl-perf-verify instead)
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
- Clock: `dut.clk` (single domain) or `dut.sys_clk` (multiple domains) — NOT `dut.clk_i`
- Reset: `dut.rst_n` (single domain) or `dut.sys_rst_n` (multiple domains) — NOT `dut.rst_ni`
- cocotb clock utility: `cocotb.clock.Clock(dut.sys_clk, 10, units="ns")`
- Reset sequence: drive `dut.sys_rst_n.value = 0`, wait, then `dut.sys_rst_n.value = 1`
</Coding_Convention_Requirements>

<Execution_Policy>
- testbench-dev writes cocotb test cases (Python) — pipelined with execution
- As each module TB completes → immediately launch eda-runner for that module (don't wait for all TBs)
- Module-level parallelism: each module's TB + sim runs as an independent parallel task
- Multi-seed regression: each module runs with 5 seeds (default: 1, 42, 123, 1337, 65536), configurable
- On any failure: waveform-analyzer diagnoses before reporting
- Coverage report generated regardless of pass/fail
- Incremental coverage: coverage-analyst can start partial analysis on completed modules
- Early termination: >5% failure rate across seeds → halt and report immediately
</Execution_Policy>

<Steps>
1. `mkdir -p reviews/phase-5-verify`
2. **Pipelined TB Generation + Execution (per-module parallel)**:
   For each module, launch TB generation and immediately follow with simulation — do NOT wait for all TBs:
   - testbench-dev writes sim/{module}/test_{module}.py
     - Use `templates/cocotb-test-template.py` as the test file scaffold
     - Signal access uses `i_`/`o_` prefixes matching RTL ports
     - Clock driven as `dut.sys_clk`, reset as `dut.sys_rst_n`
   - As EACH module's TB completes → immediately launch eda-runner for that module:
     ```bash
     # Icarus Verilog (default — good SV support, fast compile)
     make -C sim/{module} SIM=icarus TOPLEVEL={module} MODULE=test_{module}
     ```
   - Use `run_in_background: true` for each module sim to maximize parallelism
   - Use `COCOTB_RESOLVE_X=RANDOM` for X-state handling and `RANDOM_SEED=42` for reproducibility

3. **Multi-Seed Parallel Regression (per-module, absorbed from rtl-regression-run)**:
   After initial single-seed sim passes for a module, launch full multi-seed regression:
   ```
   # Option A: Automated regression script (preferred)
   bash skills/rtl-regression-run/scripts/run_regression.sh \
     --seeds "1 42 123 1337 65536" --sim icarus --parallel 4

   # Option B: Manual per-seed launch
   For each module:
     Task(eda-runner, seed=1,     module=A, run_in_background=true)
     Task(eda-runner, seed=42,    module=A, run_in_background=true)
     Task(eda-runner, seed=123,   module=A, run_in_background=true)
     Task(eda-runner, seed=1337,  module=A, run_in_background=true)
     Task(eda-runner, seed=65536, module=A, run_in_background=true)
   → 5 seeds × N modules = up to 5N parallel sim tasks
   ```
   - Default 5 seeds: 1, 42, 123, 1337, 65536 (configurable via seed_list.txt)
   - Each seed tests different random stimulus ordering
   - A module passes multi-seed regression only when ALL seeds pass
   - **Early termination**: >5% failure rate → halt, report immediately
   - On any seed failure: capture waveform, waveform-analyzer identifies divergence point
   - Seed-specific results: sim/regression/seed_{seed}_results.json

3.5. **Incremental Coverage Analysis**:
   - As modules complete their multi-seed regression, coverage-analyst begins partial analysis
   - Don't wait for ALL modules to finish — analyze completed modules incrementally
   - Early coverage gaps inform testbench-dev to generate additional tests for remaining modules
   - This overlaps coverage analysis with ongoing simulation for maximum throughput

3.7. **Coverage Merge (absorbed from rtl-regression-run)**:
   - Merge multi-seed coverage data:
     ```bash
     bash skills/rtl-regression-run/scripts/merge_coverage.sh --format verilator --output sim/coverage/merged.info
     ```
   - coverage-analyst checks targets: line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%
   - Below target: testbench-dev generates additional tests → re-run regression
   - Generate HTML report: `genhtml sim/coverage/merged.info -o sim/coverage/html/`

4. For each test: compare RTL output with ref_model output byte-by-byte
5. On mismatch: waveform-analyzer reads .vcd, identifies divergence point
6. Write sim/regression/{test}_result.json: {status, vectors_run, mismatches, divergence_cycle}
7. Generate sim/coverage/coverage.xml via cocotb coverage plugin
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
# ============================================================
# Pipelined per-module TB + Sim (each module is independent)
# ============================================================
# Module A: TB → Sim (immediate, don't wait for other modules)
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Write cocotb test sim/cabac_encoder/test_cabac_encoder.py. Use dut.sys_clk, dut.sys_rst_n, dut.i_*/dut.o_* signal naming per CLAUDE.md conventions. Drive RTL, compare output with ref model binary on 100 random vectors.")
# → As soon as TB is ready, launch sim:
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb regression via Bash CLI: make -C sim/cabac_encoder SIM=icarus TOPLEVEL=cabac_encoder MODULE=test_cabac_encoder RANDOM_SEED=42. Report pass/fail per test and overall coverage.",
     run_in_background=true)

# Module B: TB → Sim (parallel with Module A)
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Write cocotb test sim/transform/test_transform.py. [same conventions]")
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb regression: make -C sim/transform SIM=icarus TOPLEVEL=transform MODULE=test_transform RANDOM_SEED=42.",
     run_in_background=true)
# ... one pair per module, all running in parallel

# ============================================================
# Multi-Seed Full Regression (absorbed from rtl-regression-run)
# ============================================================
# Option A: Automated script (preferred for 5+ seeds)
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run full multi-seed regression via Bash CLI: bash skills/rtl-regression-run/scripts/run_regression.sh --seeds '1 42 123 1337 65536' --sim icarus --parallel 4. Report per-seed pass/fail, capture .vcd on failure. Save results to sim/regression/seed_{seed}_results.json.",
     run_in_background=true)

# Option B: Manual per-seed launch (for fine-grained control)
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb regression: make -C sim/cabac_encoder SIM=icarus TOPLEVEL=cabac_encoder MODULE=test_cabac_encoder RANDOM_SEED=123.",
     run_in_background=true)
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb regression: make -C sim/cabac_encoder SIM=icarus TOPLEVEL=cabac_encoder MODULE=test_cabac_encoder RANDOM_SEED=1337.",
     run_in_background=true)
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb regression: make -C sim/cabac_encoder SIM=icarus TOPLEVEL=cabac_encoder MODULE=test_cabac_encoder RANDOM_SEED=65536.",
     run_in_background=true)
# → 5 seeds × N modules = up to 5N parallel sim tasks

# ============================================================
# Coverage Merge (absorbed from rtl-regression-run)
# ============================================================
Task(subagent_type="rtl-agent-team:coverage-analyst",
     prompt="Merge coverage from multi-seed regression: bash skills/rtl-regression-run/scripts/merge_coverage.sh --format verilator --output sim/coverage/merged.info. Check targets: line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%. Report gaps and suggest additional test vectors.")

# ============================================================
# Incremental Coverage Analysis (starts as modules complete)
# ============================================================
Task(subagent_type="rtl-agent-team:coverage-analyst",
     prompt="Analyze coverage from completed module sims. Don't wait for all modules — analyze incrementally. Report early coverage gaps to guide additional test generation.")

# ============================================================
# Waveform Analysis (on failure)
# ============================================================
Task(subagent_type="rtl-agent-team:waveform-analyzer",
     prompt="Analyze sim/waveforms/cabac_encoder_fail.vcd. Find first divergence between RTL o_data and expected output.")

# ============================================================
# Requirement Traceability Matrix (after ALL regression completes)
# ============================================================
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
Using `dut.clk_i` or `dut.data_i` in cocotb — signal name mismatch causes AttributeError at runtime.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- cocotb not installed → halt, provide install command (`pip install cocotb`)
- Failure persists after 2 RTL fix rounds → escalate to rtl-architect with waveform analysis
- Coverage below 80% after full regression → invoke rtl-coverage-analyze skill
- cocotb signal name mismatch error → testbench-dev must fix to use `i_`/`o_` convention
- **Requirements with NO TEST COVERAGE after additional test generation** → escalate to user with list of untestable requirements
- **Requirement traceability verdict FAIL with persistent test failures** → escalate to rtl-code for RTL fix before re-verification
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All cocotb tests use correct signal names (`dut.i_*`, `dut.o_*`, `dut.sys_clk`, `dut.sys_rst_n`)
- [ ] All test vectors run to completion
- [ ] RTL vs ref model comparison done per vector
- [ ] Waveform analysis done for all failures
- [ ] sim/coverage/coverage.xml generated
- [ ] sim/regression/*_result.json written per test
- [ ] **Requirement Traceability Matrix produced with per-REQ-NNN mapping**
- [ ] **Every REQ-NNN in requirements.json covered by at least one test**
- [ ] **All covered requirements pass their tests (or failures are escalated)**
- [ ] **Traceability verdict is PASS**
- [ ] **reviews/phase-5-verify/requirement-traceability.md saved with Requirement Traceability Matrix**
- [ ] Multi-seed regression passed (5 seeds per module: 1, 42, 123, 1337, 65536)
- [ ] Per-module pipelined execution used (TB → sim without waiting for all TBs)
- [ ] Coverage merged across seeds (sim/coverage/merged.info or sim/coverage/coverage.xml)
- [ ] Coverage targets met: line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%
- [ ] sim/regression/seed_{seed}_results.json written per seed
- [ ] Early termination applied if failure rate >5%
</Final_Checklist>

<Advanced>
Multi-seed regression is now mandatory: default seeds 1, 42, 123, 1337, 65536 per module.
For even broader coverage, add random seeds or use `sim/regression/seed_list.txt`.
Coverage targets: ≥90% line, ≥80% toggle, ≥70% FSM state.
Use `COCOTB_RESOLVE_X=RANDOM` to handle X propagation in simulation.

**Full regression via script (absorbed from rtl-regression-run):**
```bash
# Automated multi-seed regression
bash skills/rtl-regression-run/scripts/run_regression.sh \
  --seeds "1 42 123 1337 65536" --sim icarus --parallel 4

# Coverage merge
bash skills/rtl-regression-run/scripts/merge_coverage.sh \
  --format verilator --output sim/coverage/merged.info

# Coverage HTML report
genhtml sim/coverage/merged.info -o sim/coverage/html/ --title "Regression Coverage"
```

**Verilator coverage collection:**
```bash
# Compile with coverage
make -C sim/{module} SIM=verilator EXTRA_ARGS="--coverage --trace-fst" TOPLEVEL=dut MODULE=test_dut

# Merge multi-seed coverage data
verilator_coverage --write-info merged.info seed_*/coverage.dat
```

**Early termination:** When failure rate exceeds 5% across seeds, halt immediately and report.
This prevents wasting compute on a fundamentally broken module.

See `examples/cocotb-axi-lite-test.py` for a complete AXI-Lite register test using cocotbext-axi.

**cocotb ecosystem quick reference:**
- AXI-Lite register access: `AxiLiteMaster(AxiLiteBus.from_prefix(dut, "s_axi"), dut.sys_clk, dut.sys_rst_n, reset_active_level=False)`
- AXI-Stream data flow: `AxiStreamSource(AxiStreamBus.from_prefix(dut, "s_axis"), dut.sys_clk, dut.sys_rst_n)`
- Functional coverage: `@CoverPoint("top.data", bins=[range(0,64), range(64,256)])`
- Parameterized tests: `TestFactory(run_test).add_option("width", [8,16,32]).generate_tests()`

See `references/cocotb-ecosystem.md` for complete API reference with code examples.

**Tier transition rules:**
- Tier 2 PASS (rtl-sv-unit-test) → Tier 3 eligible
- Tier 3 PASS (this skill) → Tier 4 eligible (rtl-integration-test)
- Tier 3 FAIL → fix via rtl-bugfix, re-run Tier 2 then Tier 3
</Advanced>
