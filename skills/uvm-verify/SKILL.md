---
name: uvm-verify
description: "This skill should be used when running UVM-based verification requiring commercial simulators (VCS/Questa/Xcelium)."
---

<Purpose>
Run a UVM-based verification environment on the target RTL using a commercial simulator
(VCS, Questa, or Xcelium). Outputs: uvm/results/run_summary.log + coverage/uvm_coverage.xml.

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
- Commercial simulator not available (use sv-unit-test or func-verify instead)
- Simple directed tests sufficient (UVM overhead not justified)
- Open-source-only tool constraint (use cocotb via func-verify)
</Do_Not_Use_When>

<Why_This_Exists>
UVM provides reusable, scalable verification infrastructure for complex designs.
When a commercial simulator is available, UVM delivers constrained-random coverage
closure that directed testing cannot match for large state spaces.
</Why_This_Exists>

<Coding_Convention_Requirements>
UVM environment code MUST follow the project coding conventions (CLAUDE.md):
- DUT port connections in driver/monitor: `i_` prefix for inputs, `o_` prefix for outputs
- Clock: `{domain}_clk` (e.g., `sys_clk`) — NOT `clk`, `clk_i`
- Reset: `{domain}_rst_n` (e.g., `sys_rst_n`) — NOT `rst_ni`
- DUT instance in top-level wrapper: `u_dut` with `u_` prefix
- UVM agent instances: `u_` prefix (e.g., `u_axi_agent`, `u_scoreboard`)
- Use `logic` in all SV declarations (NOT `reg`/`wire`)
- Interface signal names must match RTL ports exactly (e.g., `i_data`, `o_valid`)
</Coding_Convention_Requirements>

<Execution_Policy>
- testbench-dev writes UVM environment (agent, sequencer, driver, monitor, scoreboard)
- eda-runner compiles and runs with commercial simulator via Bash CLI
- Coverage collected via simulator's native UVM coverage
- If simulator not found, halt immediately with clear error
</Execution_Policy>

<Steps>
1. eda-runner checks simulator availability via Bash CLI: `which vcs || which vsim || which xrun`
2. If not found: halt with error message listing required simulator
3. testbench-dev writes uvm/{module}_env.sv (agent, sequences, scoreboard)
   - Use `templates/uvm-agent-template.sv` for agent/driver/monitor scaffold
   - Use `templates/uvm-test-template.sv` for test/env/top-level scaffold
   - See `examples/uvm-scoreboard-example.sv` for scoreboard with reference model comparison
   - Driver uses `i_`/`o_` port prefixes, `sys_clk`/`sys_rst_n`
   - DUT wrapped with `u_dut` instance name
   - Interface signals match RTL port names exactly
4. eda-runner compiles via Bash CLI:
   `vcs -full64 -sverilog -ntb_opts uvm rtl/src/*.sv uvm/*.sv -o simv`
5. eda-runner runs via Bash CLI:
   `./simv +UVM_TESTNAME={test} +ntb_random_seed={seed}`
6. Capture results to uvm/results/run_summary.log
7. Extract coverage to coverage/uvm_coverage.xml
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Check commercial simulator availability via Bash CLI: which vcs || which vsim || which xrun. Report which simulator is available or HALT if none found.")

Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Write UVM verification environment for dma_controller in uvm/. Use i_/o_ port prefixes, sys_clk/sys_rst_n, u_dut instance name per CLAUDE.md conventions. Include: UVM agent with driver/monitor, scoreboard comparing DMA transfers, base_test and directed_test sequences.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Compile and run UVM environment via Bash CLI with VCS: vcs -full64 -sverilog -ntb_opts uvm rtl/src/*.sv uvm/*.sv -o simv && ./simv +UVM_TESTNAME=directed_test. Report pass/fail and capture results to uvm/results/run_summary.log.")

Task(subagent_type="rtl-agent-team:waveform-analyzer",
     prompt="Analyze UVM scoreboard mismatch waveform. Identify divergence between DUT o_data and expected value from reference model.")
```
</Tool_Usage>

<Examples>
<Good>
Questa available; testbench-dev writes 200-line UVM env with scoreboard using `sys_clk`, `sys_rst_n`,
`i_`/`o_` port naming; func-verifier runs 10 constrained-random tests; 9 pass; 1 fails scoreboard check;
waveform captured for analysis.
</Good>
<Bad>
Attempting to run UVM with Icarus Verilog — UVM is not supported by Icarus.
Must check for commercial simulator first.
Using `clk_i`, `data_o` in UVM driver — violates project conventions and causes port binding errors.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- No commercial simulator found → HALT immediately, report which simulators are supported
- UVM compilation errors → report exact errors to user, do not attempt workarounds
- Scoreboard mismatch → capture waveform, invoke waveform-analyzer for root cause
- UVM env uses wrong naming convention → testbench-dev must rewrite before compilation
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Commercial simulator availability verified via Bash CLI before any work
- [ ] UVM environment uses correct naming (`i_`/`o_` prefix, `sys_clk`/`sys_rst_n`, `u_` instance prefix)
- [ ] UVM environment compiles without errors
- [ ] All tests run to completion (no crashes)
- [ ] uvm/results/run_summary.log written
- [ ] coverage/uvm_coverage.xml generated
- [ ] Pass/fail reported per test
</Final_Checklist>

<Advanced>
UVM component naming conventions (aligned with project style):
- Agent instances: `u_axi_agent`, `u_apb_agent` (u_ prefix)
- Driver/monitor inside agent: `u_driver`, `u_monitor` (u_ prefix)
- DUT wrapper instance: `u_dut`
- All SV code uses `logic` (never `reg`/`wire`)

Simulator-specific flags:
```bash
# VCS with coverage
vcs -full64 -sverilog -ntb_opts uvm-1.2 -cm line+cond+fsm+tgl rtl/src/*.sv uvm/*.sv -o simv
./simv +UVM_TESTNAME={test} +ntb_random_seed={seed} -cm line+cond+fsm+tgl

# Questa with coverage
vlog -sv +incdir+uvm rtl/src/*.sv uvm/*.sv
vsim -c -coverage opt_tb +UVM_TESTNAME={test} -do "coverage save -onexit cov.ucdb; run -all"

# Xcelium with coverage
xrun -sv -uvm -coverage all rtl/src/*.sv uvm/*.sv +UVM_TESTNAME={test} -seed {seed}
```

See `references/uvm-architecture.md` for complete UVM class hierarchy, phase order,
and common UVM mistakes to avoid.
</Advanced>
