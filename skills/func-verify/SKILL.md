---
name: func-verify
description: Phase 5 cocotb regression. RTL vs reference C model comparison.
---

<Purpose>
Run cocotb-based regression tests comparing RTL simulation output against the C reference model.
Outputs: sim/regression/{test}_result.json per test + coverage/coverage.xml.
On failure: invoke waveform-analyzer for debug.
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
1. testbench-dev writes tb/cocotb/test_{module}.py for each module
   - Signal access uses `i_`/`o_` prefixes matching RTL ports
   - Clock driven as `dut.sys_clk`, reset as `dut.sys_rst_n`
2. eda-runner compiles RTL and runs cocotb regression via Bash CLI:
   `make -C tb/cocotb SIM=icarus TOPLEVEL={module} MODULE=test_{module}`
3. For each test: compare RTL output with ref_model output byte-by-byte
4. On mismatch: waveform-analyzer reads .vcd, identifies divergence point
5. Write sim/regression/{test}_result.json: {status, vectors_run, mismatches, divergence_cycle}
6. Generate coverage/coverage.xml via cocotb coverage plugin
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Write cocotb test tb/cocotb/test_cabac_encoder.py. Use dut.sys_clk, dut.sys_rst_n, dut.i_*/dut.o_* signal naming per CLAUDE.md conventions. Drive RTL, compare output with ref_model binary on 100 random vectors.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb regression via Bash CLI: make -C tb/cocotb SIM=icarus TOPLEVEL=cabac_encoder MODULE=test_cabac_encoder. Report pass/fail per test and overall coverage.")

Task(subagent_type="rtl-agent-team:waveform-analyzer",
     prompt="Analyze sim/waveforms/cabac_encoder_fail.vcd. Find first divergence between RTL o_data and expected output.")
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
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All cocotb tests use correct signal names (`dut.i_*`, `dut.o_*`, `dut.sys_clk`, `dut.sys_rst_n`)
- [ ] All test vectors run to completion
- [ ] RTL vs ref model comparison done per vector
- [ ] Waveform analysis done for all failures
- [ ] coverage/coverage.xml generated
- [ ] sim/regression/*_result.json written per test
</Final_Checklist>

<Advanced>
Run with multiple seeds: `make SEED=42 SIM=icarus` for broader randomization coverage.
Coverage target: 90% line, 80% toggle, 70% FSM state.
Use `COCOTB_RESOLVE_X=RANDOM` to handle X propagation in simulation.
</Advanced>
