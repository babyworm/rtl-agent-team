---
name: uvm
description: "UVM (Universal Verification Methodology) coding convention and methodology guideline skill. Covers class hierarchy, factory patterns, sequence/sequencer, TLM ports, coverage integration, and naming conventions for UVM testbenches."
---

<Purpose>
UVM coding standards and methodology guidelines.
All agents building or modifying UVM-based verification environments must follow the rules in this skill.
Based on the IEEE 1800.2-2020 UVM Standard.
</Purpose>

<Use_When>
- When writing UVM testbenches, agents, sequences, or scoreboards
- When building UVM environments for the uvm-verify skill
- During Phase 5 (Verification) — UVM-based verification work
- Agents: testbench-dev
</Use_When>

<Do_Not_Use_When>
- When doing cocotb Python-based verification → use `func-verify` skill
- When writing only SVA assertions → use `systemverilog-assertion` skill
- When writing RTL synthesizable code → use `systemverilog` skill
</Do_Not_Use_When>

<Why_This_Exists>
UVM is an industry-standard verification methodology, but its high degree of freedom easily leads to inconsistent code.
Following consistent naming conventions, class structure, and factory usage patterns ensures:
- Maximum environment reusability (agents reusable across multiple projects)
- Ease of debugging (predictable structure)
- Natural coverage integration
</Why_This_Exists>

<Execution_Policy>
- Applies to all agents generating UVM environments
- Use `templates/uvm-env-template.sv` as the starting point for new environments
- Review `examples/uvm-smoke-test-example.sv` for basic smoke test structure
- All UVM components must be registered with the factory (`uvm_component_utils` / `uvm_object_utils`)
- Follow the phase callback order precisely
</Execution_Policy>

<Steps>

## 1. Naming Conventions

### 1.1 Filenames
| Type | Pattern | Example |
|------|---------|---------|
| Agent | `{proto}_agent.sv` | `axi_agent.sv` |
| Driver | `{proto}_driver.sv` | `axi_driver.sv` |
| Monitor | `{proto}_monitor.sv` | `axi_monitor.sv` |
| Sequencer | `{proto}_sequencer.sv` | `axi_sequencer.sv` |
| Sequence Item | `{proto}_seq_item.sv` | `axi_seq_item.sv` |
| Sequence | `{proto}_{name}_seq.sv` | `axi_write_seq.sv` |
| Scoreboard | `{module}_scoreboard.sv` | `cabac_scoreboard.sv` |
| Environment | `{module}_env.sv` | `cabac_env.sv` |
| Test | `{module}_{name}_test.sv` | `cabac_smoke_test.sv` |
| Package | `{module}_tb_pkg.sv` | `cabac_tb_pkg.sv` |
| Top | `tb_{module}_top.sv` | `tb_cabac_top.sv` |

### 1.2 Class Naming
| Target | Pattern | Example |
|--------|---------|---------|
| Agent | `{proto}_agent` | `axi_agent` |
| Driver | `{proto}_driver` | `axi_driver` |
| Monitor | `{proto}_monitor` | `axi_monitor` |
| Sequencer | `{proto}_sequencer` | `axi_sequencer` |
| Sequence Item | `{proto}_seq_item` | `axi_seq_item` |
| Sequence (base) | `{proto}_base_seq` | `axi_base_seq` |
| Sequence (specific) | `{proto}_{name}_seq` | `axi_write_burst_seq` |
| Scoreboard | `{module}_scoreboard` | `cabac_scoreboard` |
| Environment | `{module}_env` | `cabac_env` |
| Test (base) | `{module}_base_test` | `cabac_base_test` |
| Coverage | `{module}_coverage` | `cabac_coverage` |

### 1.3 Instance Naming (create)

> **`m_` prefix 규칙**: UVM 클래스 내부 멤버 핸들은 `m_` prefix를 사용한다 (업계 관행).
> 이는 RTL의 `u_` prefix 규칙과 별개이며, UVM TB에서만 적용된다.

```systemverilog
// Instance name matches the variable name
m_driver  = axi_driver::type_id::create("m_driver", this);
m_monitor = axi_monitor::type_id::create("m_monitor", this);
m_seqr    = axi_sequencer::type_id::create("m_seqr", this);
```

## 2. UVM Class Hierarchy

```
uvm_test
 └── cabac_base_test
      └── cabac_smoke_test
           └── cabac_random_test

uvm_env
 └── cabac_env
      ├── axi_agent (m_axi_agt)
      │    ├── axi_driver (m_driver)
      │    ├── axi_monitor (m_monitor)
      │    └── axi_sequencer (m_seqr)
      ├── cabac_scoreboard (m_scoreboard)
      └── cabac_coverage (m_coverage)
```

## 3. Factory Registration (Mandatory)

All UVM components/objects must be registered with the factory:
```systemverilog
class axi_driver extends uvm_driver #(axi_seq_item);
  `uvm_component_utils(axi_driver)

  function new(string name = "axi_driver", uvm_component parent = null);
    super.new(name, parent);
  endfunction
  // ...
endclass

class axi_seq_item extends uvm_sequence_item;
  `uvm_object_utils(axi_seq_item)

  function new(string name = "axi_seq_item");
    super.new(name);
  endfunction
  // ...
endclass
```

## 4. Phase Callback Order

| Phase | Purpose | Notes |
|-------|---------|-------|
| `build_phase` | Component create, config_db get | Only create here |
| `connect_phase` | TLM port connections | After build completes |
| `end_of_elaboration_phase` | Final structure check | Optional |
| `run_phase` | Simulation execution | raise/drop objection required |
| `extract_phase` | Collect results | Optional |
| `check_phase` | pass/fail determination | Optional |
| `report_phase` | Report results | Scoreboard summary |

### Objection Rules
```systemverilog
task cabac_base_test::run_phase(uvm_phase phase);
  phase.raise_objection(this, "Test started");
  // ... test body (start sequences)
  phase.drop_objection(this, "Test completed");
endtask
```
- **Only test raises/drops objection** — forbidden in sequences or drivers
- Without objection, simulation terminates immediately

## 5. TLM Port Usage

| Port Type | Direction | Purpose |
|-----------|-----------|---------|
| `uvm_analysis_port` | Monitor → Scoreboard/Coverage | Broadcast (1:N) |
| `uvm_seq_item_pull_port` | Driver ↔ Sequencer | Auto-connected |
| `uvm_analysis_imp` | Scoreboard receiver | Must implement write() |

```systemverilog
// Monitor: analysis port declaration and usage
class axi_monitor extends uvm_monitor;
  uvm_analysis_port #(axi_seq_item) m_ap;

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_ap = new("m_ap", this);
  endfunction

  task run_phase(uvm_phase phase);
    // ... capture transaction
    m_ap.write(txn);  // broadcast to all subscribers
  endtask
endclass

// Scoreboard: analysis imp declaration
class cabac_scoreboard extends uvm_scoreboard;
  `uvm_analysis_imp_decl(_input)
  `uvm_analysis_imp_decl(_output)

  uvm_analysis_imp_input  #(axi_seq_item, cabac_scoreboard) m_input_imp;
  uvm_analysis_imp_output #(axi_seq_item, cabac_scoreboard) m_output_imp;

  function void write_input(axi_seq_item txn);
    // enqueue expected
  endfunction

  function void write_output(axi_seq_item txn);
    // compare with expected
  endfunction
endclass
```

## 6. config_db Usage

```systemverilog
// Test → Agent: pass virtual interface (build_phase)
uvm_config_db #(virtual axi_if)::set(this, "m_env.m_axi_agt*", "vif", m_vif);

// Agent: retrieve virtual interface (build_phase)
if (!uvm_config_db #(virtual axi_if)::get(this, "", "vif", m_vif))
  `uvm_fatal("NO_VIF", "Virtual interface not set for agent")
```
- set/get paths are hierarchy-based (wildcard `*` supported)
- On get failure, `uvm_fatal` is mandatory

## 7. Coverage Integration

```systemverilog
class cabac_coverage extends uvm_subscriber #(axi_seq_item);
  `uvm_component_utils(cabac_coverage)

  covergroup cg_transaction;
    cp_cmd:    coverpoint m_txn.cmd    { bins read = {0}; bins write = {1}; }
    cp_size:   coverpoint m_txn.size   { bins sizes[] = {1, 2, 4, 8}; }
    cross cp_cmd, cp_size;
  endgroup

  function new(string name, uvm_component parent);
    super.new(name, parent);
    cg_transaction = new();
  endfunction

  function void write(axi_seq_item t);
    m_txn = t;
    cg_transaction.sample();
  endfunction
endclass
```

## 8. Anti-Patterns

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
This skill is not executed directly. It is referenced by agents that generate UVM environments:
```
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="... Follow uvm skill conventions. Use factory registration for all components.")
```
</Tool_Usage>

<Examples>
<Good>
Factory registration, correct naming, config_db usage, analysis port:
```systemverilog
class axi_agent extends uvm_agent;
  `uvm_component_utils(axi_agent)
  axi_driver    m_driver;
  axi_monitor   m_monitor;
  axi_sequencer m_seqr;

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_driver  = axi_driver::type_id::create("m_driver", this);
    m_monitor = axi_monitor::type_id::create("m_monitor", this);
    m_seqr    = axi_sequencer::type_id::create("m_seqr", this);
  endfunction
endclass
```
</Good>
<Bad>
No factory usage, hard-coded, direct new:
```systemverilog
class my_agent extends uvm_agent;
  // WRONG: no uvm_component_utils
  my_driver drv;
  function void build_phase(uvm_phase phase);
    drv = new("drv", this);  // WRONG: bypasses factory
  endfunction
endclass
```
</Bad>
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
