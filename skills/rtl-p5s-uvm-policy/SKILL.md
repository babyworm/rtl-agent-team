---
name: rtl-p5s-uvm-policy
description: "Policy rules, UVM naming conventions (m_ prefix, u_dut instance), commercial simulator requirements, coverage collection rules, and checklists. Pure reference — no orchestration."
user-invocable: false
---

# UVM Verification Policy

## UVM Naming Conventions

UVM environment code MUST follow the project coding conventions (CLAUDE.md):
- DUT port connections in driver/monitor: `i_` prefix for inputs, `o_` prefix for outputs
- Clock: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
- Reset: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
- DUT instance in top-level wrapper: `u_dut` with `u_` prefix
- UVM class member handles: `m_` prefix (e.g., `m_agent`, `m_scoreboard`, `m_driver`, `m_monitor`)
- Use `logic` in all SV declarations (NOT `reg`/`wire`)
- Interface signal names must match RTL ports exactly (e.g., `i_data`, `o_valid`)

## Escalation & Stop Conditions

- No commercial simulator found → HALT immediately, report which simulators are supported
- UVM compilation errors → report exact errors to user, do not attempt workarounds
- Scoreboard mismatch → capture waveform, invoke waveform-analyzer for root cause
- UVM env uses wrong naming convention → testbench-dev must rewrite before compilation

## Final Checklist

- [ ] Commercial simulator availability verified via Bash CLI before any work
- [ ] UVM environment uses correct naming (`i_`/`o_` prefix, `sys_clk`/`sys_rst_n`, `m_` UVM member prefix, `u_` RTL instance prefix)
- [ ] UVM environment compiles without errors
- [ ] All tests run to completion (no crashes)
- [ ] sim/uvm/results/run_summary.log written
- [ ] sim/uvm/coverage/uvm_coverage.xml generated
- [ ] Pass/fail reported per test

## UVM Component Naming and Simulator-Specific Flags

UVM component naming conventions (aligned with project style):
- Agent member handles: `m_agent`, `m_axi_agent`, `m_apb_agent` (m_ prefix for UVM class members)
- Driver/monitor inside agent: `m_driver`, `m_monitor` (m_ prefix for UVM class members)
- DUT wrapper instance: `u_dut` (u_ prefix for RTL instances only)
- All SV code uses `logic` (never `reg`/`wire`)

Simulator-specific flags:
```bash
# VCS with coverage
vcs -full64 -sverilog -ntb_opts uvm-1.2 -cm line+cond+fsm+tgl rtl/*/*.sv sim/uvm/*.sv -o simv
./simv +UVM_TESTNAME={test} +ntb_random_seed={seed} -cm line+cond+fsm+tgl

# Questa with coverage
vlog -sv +incdir+sim/uvm rtl/*/*.sv sim/uvm/*.sv
vsim -c -coverage opt_tb +UVM_TESTNAME={test} -do "coverage save -onexit cov.ucdb; run -all"

# Xcelium with coverage
xrun -sv -uvm -coverage all rtl/*/*.sv sim/uvm/*.sv +UVM_TESTNAME={test} -seed {seed}
```

See `references/uvm-architecture.md` for complete UVM class hierarchy, phase order,
and common UVM mistakes to avoid.
