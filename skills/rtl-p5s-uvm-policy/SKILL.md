---
name: rtl-p5s-uvm-policy
description: "Internal reference: rtl p5s uvm policy (agent-loaded; do not invoke)."
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

## Coverage Targets (Enforced at Regression Report)

| Coverage Type | Target | Tool Flag (VCS) | Notes |
|--------------|--------|-----------------|-------|
| Line | ≥ 90% | `-cm line` | Every executable line exercised |
| Toggle | ≥ 80% | `-cm tgl` | Signal 0→1 and 1→0 transitions |
| FSM | ≥ 70% | `-cm fsm` | State and transition coverage |
| Branch | ≥ 80% | `-cm cond` | if/case branch coverage |
| Functional | ≥ 95% | UVM covergroups | Architect-defined coverpoints |

**Code coverage** is always enabled during regression (`-cm line+cond+fsm+tgl+branch` for VCS,
`-coverage all` for Xcelium, `-coverage` for Questa). Merged from all seeds before evaluation.

**Functional coverage** is collected via `uvm_subscriber`-based coverage collectors in the
testbench. Covergroups must be mapped to requirements (REQ-U-*).

## Coverage-Driven Verification (CDV) Feedback Loop

When merged coverage falls below targets after regression, run a structured 3-round loop:

```
Round N: coverage-analyst → CDTG feedback table (gap analysis)
         test-plan-writer  → systematic test plan (ECP/BVA for config-dependent gaps)
         testbench-dev    → directed UVM sequences per gap row + test plan
         eda-runner       → regression with new tests → re-merge coverage
Round N+1: coverage-analyst re-analyzes → new guidance for remaining gaps
```

1. `coverage-analyst` identifies uncovered bins, states, branches. Produces CDTG feedback table:
   ```
   | Gap ID | Uncovered Bin | REQ | Constraint | Sequence | Expected |
   ```
2. `test-plan-writer` applies ECP/BVA methodology for config-dependent gaps (parameter combinations)
3. `testbench-dev` writes directed UVM sequences per gap row using the systematic test plan
4. Re-run regression with new tests → re-merge → re-analyze
5. Maximum 3 iterations. Convergence detection: 2 consecutive rounds with < 0.5% improvement
6. On convergence: apply Coverage Exclusion Protocol per `rtl-p5s-coverage-policy`
   (classify remaining bins as STIMULUS_GAP/STRUCTURAL_DEAD/INFRA_CODE, generate exclusion artifacts)
7. If post-exclusion targets still not met after 3 rounds → escalate to user

## UVM Stimulus-to-DUT Connectivity Verification

Before running regression, verify stimulus actually reaches the DUT:

1. **Randomization check**: All `rand` fields in test class must be randomized
   - Required: `this.randomize()` called in `build_phase` or `run_phase`
   - Anti-pattern: `rand logic` field declared but never `randomize()`-d
2. **DUT connectivity check**: Every test knob must have a path to DUT port
   - Required: config variable → config_db / virtual_if / backdoor → DUT signal
   - Anti-pattern: `rand cfg_xxx` in test class but DUT port hardcoded in TB top
3. **Effectiveness gate** (after first iteration): verify coverage CHANGED across seeds
   - If coverage delta < 0.1% across all seeds → stimulus is NOT reaching DUT
   - Root cause: missing randomization or disconnected config path
   - Action: HALT regression, debug stimulus connectivity before proceeding

### Enforcement in Orchestrator

p5s-uvm-orchestrator checks coverage delta after first regression iteration (Step 4).
If delta < 0.1% across seeds → invoke uvm-reviewer to diagnose stimulus connectivity
before running additional iterations.

## Regression Runner

Use the UVM regression runner (`{plugin_root}` = plugin root resolved from `.rat/state/spawn-context.json`) for multi-seed regression:
```bash
bash {plugin_root}/skills/rtl-p5s-uvm-verify/scripts/run_regression_uvm.sh --sim vcs --seeds "42 123 456 789 1337" --test base_test --module {module}
```
- Compiles once, runs seeds in parallel with failure halt logic
- Per-seed result JSON + merged coverage + regression report
- Coverage merge: VCS `urg`, Xcelium `imc`, Questa `vcover`

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

Simulator-specific coverage flags — **both compile and run must enable coverage**:

```bash
# VCS — compile + run
vcs -full64 -sverilog -ntb_opts uvm-1.2 \
    -cm line+cond+fsm+tgl+branch \
    -cm_hier sim/uvm/coverage/hier.cfg \
    -timescale=1ns/1ps -f rtl/filelist_top.f \
    sim/uvm/agents/*/*.sv sim/uvm/env/*.sv sim/uvm/seq/*.sv \
    sim/uvm/tests/*.sv sim/uvm/tb/*.sv -o simv
./simv +UVM_TESTNAME={test} +ntb_random_seed={seed} \
    -cm line+cond+fsm+tgl+branch -cm_dir sim/uvm/coverage/seed_{seed}.vdb

# VCS — merge (text + XML for coverage-analyst parsing)
urg -dir sim/uvm/coverage/seed_*.vdb -report sim/uvm/coverage/merged \
    -elfile sim/uvm/coverage/exclusion.el -format both

# Questa — compile (MUST include +cover) + run
vlog -sv +cover=bcestf +incdir+sim/uvm \
    -f rtl/filelist_top.f sim/uvm/agents/*/*.sv sim/uvm/env/*.sv \
    sim/uvm/seq/*.sv sim/uvm/tests/*.sv sim/uvm/tb/*.sv
vsim -c -coverage tb_top +UVM_TESTNAME={test} -sv_seed {seed} \
    -do "coverage save -onexit sim/uvm/coverage/seed_{seed}.ucdb; run -all; quit -f"

# Questa — merge
vcover merge sim/uvm/coverage/merged.ucdb sim/uvm/coverage/seed_*.ucdb
vcover report -details sim/uvm/coverage/merged.ucdb

# Xcelium — compile + run (separate phases)
xrun -sv -uvm -compile -coverage all -timescale 1ns/1ps \
    -f rtl/filelist_top.f sim/uvm/agents/*/*.sv sim/uvm/env/*.sv \
    sim/uvm/seq/*.sv sim/uvm/tests/*.sv sim/uvm/tb/*.sv \
    -xmlibdirpath build/xcelium
xrun -R +UVM_TESTNAME={test} -seed {seed} \
    -coverage all -covworkdir sim/uvm/coverage/seed_{seed}/cov_work -covscope tb_top \
    -xmlibdirpath build/xcelium

# Xcelium — merge (via imc TCL script)
imc -exec merge_script.tcl   # merge -run seed_*/cov_work → report
```

**Common mistakes to avoid:**
- Questa: omitting `+cover=bcestf` at `vlog` compile → runtime `-coverage` collects nothing
- VCS: omitting `-cm` at runtime → compile instrumentation wasted
- Xcelium: using `-R` without matching `-xmlibdirpath` → snapshot not found
- All tools: merging before all seeds complete → partial coverage report

See `references/uvm-architecture.md` for complete UVM class hierarchy, phase order,
and common UVM mistakes to avoid.
