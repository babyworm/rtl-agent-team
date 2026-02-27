# UVM Architecture Reference

> This document is the detailed reference for the `rtl-uvm-verify` skill.
> For core rules, see `<Steps>` in `skills/rtl-uvm-verify/SKILL.md`.
> For coding conventions, see `skills/uvm/SKILL.md`.

## 1. UVM Component Hierarchy

```
uvm_top (implicit root)
 └── uvm_test
      └── {module}_base_test
           └── {module}_env
                ├── {proto}_agent (per interface)
                │    ├── {proto}_driver
                │    ├── {proto}_monitor
                │    └── {proto}_sequencer
                ├── {module}_scoreboard
                ├── {module}_coverage
                └── {module}_virtual_sequencer (optional)
```

## 2. Phase Order (IEEE 1800.2-2020)

### 2.1 Build Phases (top-down)

| Phase | Direction | Purpose |
|-------|-----------|---------|
| `build_phase` | Top → Down | create components, config_db get |
| `connect_phase` | Bottom → Up | TLM port connections |
| `end_of_elaboration_phase` | Bottom → Up | final topology check |

### 2.2 Run Phases (parallel)

| Phase | Execution | Purpose |
|-------|-----------|---------|
| `start_of_simulation_phase` | — | print topology |
| `run_phase` | **parallel** | main test body (sequences) |
| `pre_reset_phase` ~ `post_shutdown_phase` | parallel (12 sub-phases) | optional fine-grained control |

### 2.3 Cleanup Phases (bottom-up)

| Phase | Direction | Purpose |
|-------|-----------|---------|
| `extract_phase` | Bottom → Up | collect results |
| `check_phase` | Bottom → Up | compare, pass/fail |
| `report_phase` | Bottom → Up | print summary |
| `final_phase` | Top → Down | cleanup |

## 3. Factory Pattern

### 3.1 Registration

```systemverilog
// Component (has parent)
class my_driver extends uvm_driver #(my_seq_item);
  `uvm_component_utils(my_driver)
  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction
endclass

// Object (no parent)
class my_seq_item extends uvm_sequence_item;
  `uvm_object_utils(my_seq_item)
  function new(string name = "my_seq_item");
    super.new(name);
  endfunction
endclass
```

### 3.2 Creation

```systemverilog
// Always use factory create (NEVER new for UVM components)
m_driver = my_driver::type_id::create("m_driver", this);
```

### 3.3 Override

```systemverilog
// Type override (global)
set_type_override_by_type(my_driver::get_type(), my_custom_driver::get_type());

// Instance override (specific path)
set_inst_override_by_type("*.m_env.m_agent.m_driver",
                           my_driver::get_type(), my_custom_driver::get_type());
```

## 4. TLM Port Architecture

### 4.1 Port Types

| Port | Direction | Connection | Purpose |
|------|-----------|------------|---------|
| `uvm_analysis_port` | Transmit (1:N) | → `uvm_analysis_imp` | Monitor → Scoreboard, Coverage |
| `uvm_seq_item_pull_port` | Driver ↔ Sequencer | Auto-connected | Sequence item delivery |
| `uvm_blocking_put_port` | 1:1 blocking | → `uvm_blocking_put_imp` | Synchronous delivery |
| `uvm_tlm_analysis_fifo` | FIFO buffer | analysis_port → FIFO → get | Order-preserving |

### 4.2 Analysis Port Connection Pattern

```systemverilog
// Environment connect_phase
function void connect_phase(uvm_phase phase);
  super.connect_phase(phase);

  // Monitor → Scoreboard (1:N broadcast)
  m_agent.m_monitor.m_ap.connect(m_scoreboard.m_input_imp);
  m_agent.m_monitor.m_ap.connect(m_coverage.analysis_export);

  // Driver ↔ Sequencer (automatic via agent)
  m_agent.m_driver.seq_item_port.connect(m_agent.m_seqr.seq_item_export);
endfunction
```

### 4.3 Multiple Analysis Imports

```systemverilog
// Scoreboard with multiple input streams
`uvm_analysis_imp_decl(_expected)
`uvm_analysis_imp_decl(_actual)

class my_scoreboard extends uvm_scoreboard;
  uvm_analysis_imp_expected #(my_txn, my_scoreboard) m_exp_imp;
  uvm_analysis_imp_actual   #(my_txn, my_scoreboard) m_act_imp;

  function void write_expected(my_txn t);
    m_expected_q.push_back(t);
  endfunction

  function void write_actual(my_txn t);
    my_txn exp = m_expected_q.pop_front();
    if (!t.compare(exp))
      `uvm_error("MISMATCH", $sformatf("Expected: %s Got: %s", exp.sprint(), t.sprint()))
  endfunction
endclass
```

## 5. Sequence Architecture

### 5.1 Sequence Hierarchy

```
uvm_sequence #(seq_item)
 └── {proto}_base_seq          ← Common methods
      ├── {proto}_single_seq   ← Single transfer
      ├── {proto}_burst_seq    ← Burst transfer
      └── {proto}_random_seq   ← Random scenario
```

### 5.2 Sequence Body Pattern

```systemverilog
class axi_write_seq extends axi_base_seq;
  `uvm_object_utils(axi_write_seq)

  rand logic [31:0] addr;
  rand logic [31:0] data;

  task body();
    axi_seq_item req;
    req = axi_seq_item::type_id::create("req");

    start_item(req);
    if (!req.randomize() with {
      req.addr == local::addr;
      req.data == local::data;
      req.cmd  == AXI_WRITE;
    }) `uvm_fatal("RAND", "Randomization failed")
    finish_item(req);

    // Optional: get response
    // get_response(rsp);
  endtask
endclass
```

### 5.3 Virtual Sequence (Multi-Agent)

```systemverilog
class my_virtual_seq extends uvm_sequence;
  `uvm_object_utils(my_virtual_seq)

  // Sub-sequencers (set via config_db or p_sequencer)
  axi_sequencer m_axi_seqr;
  apb_sequencer m_apb_seqr;

  task body();
    axi_write_seq wr_seq = axi_write_seq::type_id::create("wr_seq");
    apb_read_seq  rd_seq = apb_read_seq::type_id::create("rd_seq");

    // Parallel: AXI write + APB read
    fork
      wr_seq.start(m_axi_seqr);
      rd_seq.start(m_apb_seqr);
    join
  endtask
endclass
```

## 6. config_db Best Practices

| Pattern | Purpose | Example |
|---------|---------|---------|
| Test → Agent | virtual interface | `set(this, "m_env.m_agt*", "vif", vif)` |
| Test → Env | configuration | `set(this, "m_env", "cfg", cfg)` |
| Wildcard `*` | All within hierarchy | `"m_env.m_agt*"` matches all agents |
| Get + Fatal | Mandatory config check | `if (!get(...)) uvm_fatal(...)` |

**Rule**: `config_db::get()` failure must always result in `uvm_fatal` -- silent failure is prohibited.

## 7. Objection Rules

| Rule | Description |
|------|-------------|
| raise/drop only in Test | Prohibited in Driver, Sequence |
| raise → body → drop order | raise before body starts, drop after completion |
| Set drain_time | `set_drain_time(this, 100ns)` -- wait for last response |

```systemverilog
task my_test::run_phase(uvm_phase phase);
  phase.raise_objection(this, "Test started");

  // Start sequences
  my_seq seq = my_seq::type_id::create("seq");
  seq.start(m_env.m_agent.m_seqr);

  // Wait for completion
  #100ns;  // drain time

  phase.drop_objection(this, "Test done");
endtask
```
