---
name: sv-unit-test
description: Phase 5 first-pass verification. SV testbench-based unit tests per RTL module.
---

<Purpose>
Write and run SystemVerilog testbenches for each RTL module.
Provides first-pass functional coverage before regression.
Outputs: tb/unit/tb_{module}.sv testbench files + sim/unit/{module}_results.txt.
</Purpose>

<Use_When>
- Phase 4 RTL is lint-clean and ready for first verification pass
- A new module needs targeted unit testing
- A bug fix needs a focused regression test added
</Use_When>

<Do_Not_Use_When>
- Full regression with many seeds needed (use regression-run instead)
- Formal verification preferred (use sva-check instead)
- cocotb-based tests required (use func-verify instead)
</Do_Not_Use_When>

<Why_This_Exists>
Unit tests catch obvious bugs early and cheaply before running expensive full-chip simulations.
SV testbenches are close to the RTL and easy to debug with waveforms.
First-pass verification separates trivial bugs from systemic issues.
</Why_This_Exists>

<Coding_Convention_Requirements>
Testbenches MUST follow the project coding conventions (CLAUDE.md):
- Port connections: `i_` prefix for inputs, `o_` prefix for outputs, `io_` for bidirectional
- Clock: `{domain}_clk` (e.g., `sys_clk`), NOT `clk`, `clk_i`
- Reset: `{domain}_rst_n` (e.g., `sys_rst_n`), NOT `rst_ni`, `rst_n`
- Use `logic` only (NOT `reg`/`wire`)
- DUT instance: `u_` prefix (e.g., `u_dut`)
- Testbench filename: `tb_{module}.sv` (e.g., `tb_cabac_encoder.sv`)
</Coding_Convention_Requirements>

<Execution_Policy>
- testbench-dev writes SV testbenches per module (parallel)
- func-verifier runs simulations via Bash CLI (iverilog/verilator) and reports results
- Failing tests trigger waveform analysis before reporting
- Gate: all unit tests pass
</Execution_Policy>

<Steps>
1. Read rtl/src/*.sv to enumerate modules and their port lists
2. testbench-dev writes tb/unit/tb_{module}.sv for each module (parallel)
   - DUT instantiated as `u_dut` with correct `i_`/`o_` port connections
   - Clock generated as `sys_clk` (or appropriate domain clock)
   - Reset generated as `sys_rst_n` (active-low)
3. eda-runner compiles and simulates each testbench via Bash CLI:
   - `iverilog -g2012 -o sim/unit/{module}_sim rtl/src/{module}.sv tb/unit/tb_{module}.sv`
   - `vvp sim/unit/{module}_sim`
4. Collect results in sim/unit/{module}_results.txt
5. For failures: waveform-analyzer reviews .vcd, identifies bug location
6. Report pass/fail summary with failure details
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Write SV unit testbench tb/unit/tb_cabac_encoder.sv for rtl/src/cabac_encoder.sv. Use sys_clk/sys_rst_n, i_/o_ port prefixes, u_dut instance name. Cover reset, normal operation, edge cases.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Compile and simulate tb/unit/tb_cabac_encoder.sv with Icarus Verilog via Bash CLI: iverilog -g2012 -o sim/unit/cabac_encoder_sim rtl/src/cabac_encoder.sv tb/unit/tb_cabac_encoder.sv && vvp sim/unit/cabac_encoder_sim. Report pass/fail and any assertion failures.")

Task(subagent_type="rtl-agent-team:waveform-analyzer",
     prompt="Analyze sim/unit/cabac_encoder.vcd. Identify root cause of unit test failure at failing assertion.")
```
</Tool_Usage>

<Examples>
<Good>
6 modules, 6 testbenches written in parallel; all use `sys_clk`/`sys_rst_n` and `i_`/`o_` port naming;
5 pass immediately; 1 fails on reset edge case; waveform shows missing reset synchronizer;
RTL fix applied; retest passes.
</Good>
<Bad>
Writing a single monolithic testbench for the entire design — hard to isolate failures and debug.
Using `clk`, `rst_n`, `data_i` instead of `sys_clk`, `sys_rst_n`, `i_data` — violates project conventions.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Module fails unit test and waveform analysis cannot identify root cause → escalate to rtl-architect
- Simulator not available → report to user, suggest Icarus Verilog or Verilator installation
- Testbench uses wrong naming convention → testbench-dev must rewrite before simulation
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] tb/unit/tb_{module}.sv exists for every module
- [ ] All testbenches use `i_`/`o_` port prefixes, `sys_clk`/`sys_rst_n`, `u_dut`
- [ ] All simulations compile and complete without crashes
- [ ] All unit tests pass
- [ ] Failure analysis done for any initial failures
</Final_Checklist>

<Advanced>
Testbenches should use $dumpvars for waveform capture even on passing tests (for coverage).
Randomize input sequences with $urandom for broader coverage within unit test time budget.
Use `always_ff`, `always_comb` in testbench helper modules (never `always @*`).
</Advanced>
