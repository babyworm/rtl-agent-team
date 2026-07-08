---
name: uvm
description: "uvm project conventions (loaded by writer agents; do not invoke)."
user-invocable: false
---

<Purpose>
UVM project conventions (naming + RTL boundary rules) for UVM testbench work.
Base: IEEE 1800.2-2020 UVM standard — standard UVM mechanics (factory registration, phasing,
TLM ports, config_db, sequences, objections) are assumed known and are not restated here.
</Purpose>

<Use_When>
- Writing UVM testbenches, agents, sequences, or scoreboards (Phase 5, `rtl-p5s-uvm-verify`)
- Agents: testbench-dev
</Use_When>

<Do_Not_Use_When>
- cocotb Python verification → `rtl-p5s-func-verify` skill; SVA-only work → `systemverilog-assertion` skill; synthesizable RTL → `systemverilog` skill
</Do_Not_Use_When>

<Execution_Policy>
- Environment scaffold: `templates/uvm-env-template.sv`; smoke test structure: `examples/uvm-smoke-test-example.sv`
- All UVM classes registered with the factory; objections raised/dropped only in the test
</Execution_Policy>

<Steps>

## 1. Naming Conventions

Class name = file name (one class per file). Protocol-level components use `{proto}_`, DUT-level
components use `{module}_`:

| Component | Class / File Pattern | Example |
|-----------|---------------------|---------|
| Agent / Driver / Monitor / Sequencer | `{proto}_agent` etc. | `axi_agent`, `axi_driver`, `axi_monitor`, `axi_sequencer` |
| Sequence Item | `{proto}_seq_item` | `axi_seq_item` |
| Sequence (base / specific) | `{proto}_base_seq` / `{proto}_{name}_seq` | `axi_base_seq`, `axi_write_burst_seq` |
| Scoreboard / Environment / Coverage | `{module}_scoreboard` / `{module}_env` / `{module}_coverage` | `cabac_scoreboard`, `cabac_env` |
| Test (base / specific) | `{module}_base_test` / `{module}_{name}_test` | `cabac_base_test`, `cabac_smoke_test` |
| Package | `{module}_tb_pkg.sv` | `cabac_tb_pkg.sv` |
| Top | `tb_{module}_top.sv` | `tb_cabac_top.sv` |

## 2. m_/u_ Prefix Boundary

- UVM class member handles use `m_` prefix (industry convention); the `create()` instance name
  matches the variable name: `m_driver = axi_driver::type_id::create("m_driver", this);`
- `u_` prefix is for RTL module instances ONLY — including the DUT instance in the TB top (`u_dut`)

## 3. RTL Port-Name Matching

TB interfaces/signals connect to DUT ports using the RTL names verbatim: `i_`/`o_`/`io_` prefixes,
`clk`/`{domain}_clk`, `rst_n`/`{domain}_rst_n` (e.g., `@(posedge vif.sys_clk)`). Never invent
TB-side port aliases.

## 4. Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| Not registered with factory | Cannot override/reuse | Add `uvm_*_utils` to all classes |
| Objection in driver | Phase control confusion | Only raise/drop in test |
| Ignoring config_db get failure | Null pointer crash | Handle with `uvm_fatal` |
| Direct DUT access from sequence | Destroys reusability | Use sequencer→driver path only |
| Hard-coded hierarchy path | Destroys portability | Use config_db wildcard |
| `#delay` in run_phase | Destroys portability | Use `@(posedge vif.sys_clk)` |

</Steps>

<Tool_Usage>
This skill is not executed directly. It is referenced by agents that generate UVM environments
(e.g., testbench-dev). Agents should follow the conventions defined here.
</Tool_Usage>

<Examples>
Environment structure with factory/naming/config_db patterns: `templates/uvm-env-template.sv`.
Smoke test structure: `examples/uvm-smoke-test-example.sv`.
</Examples>

<Escalation_And_Stop_Conditions>
- UVM environment compilation error → request fix from testbench-dev
- Coverage target not met → write additional sequences or request analysis from coverage-analyst
- Scoreboard mismatch → request RTL vs Ref Model comparison from func-verifier
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All UVM classes registered with factory (`uvm_component_utils` / `uvm_object_utils`)
- [ ] Objection raised/dropped only in test
- [ ] `uvm_fatal` on config_db get failure
- [ ] TLM analysis port connects monitor→scoreboard
- [ ] Virtual interface passed via config_db
- [ ] Naming convention: `{proto}_agent`, `{proto}_driver`, `m_` prefix instances
- [ ] Coverage collector subscribes to analysis port
- [ ] Port names match RTL (sys_clk, sys_rst_n, i_/o_)
</Final_Checklist>
