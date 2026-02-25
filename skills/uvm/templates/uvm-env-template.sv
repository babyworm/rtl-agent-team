// =============================================================================
// UVM Environment Template
// Module: {{MODULE_NAME}}
// Description: UVM verification environment scaffold
// Author: testbench-dev (generated)
// Convention: uvm skill
// =============================================================================

`ifndef {{MODULE_NAME_UPPER}}_ENV_SV
`define {{MODULE_NAME_UPPER}}_ENV_SV

// =============================================================================
// Sequence Item
// =============================================================================
class {{PROTO}}_seq_item extends uvm_sequence_item;
  `uvm_object_utils({{PROTO}}_seq_item)

  // Transaction fields
  rand logic [31:0] addr;
  rand logic [31:0] data;
  rand logic        wr_en;

  // Constraints
  constraint c_addr_aligned { addr % 4 == 0; }
  constraint c_addr_range   { addr inside {[32'h0000_0000:32'h0000_FFFF]}; }

  function new(string name = "{{PROTO}}_seq_item");
    super.new(name);
  endfunction

  function string convert2string();
    return $sformatf("addr=0x%08h data=0x%08h wr=%0b", addr, data, wr_en);
  endfunction
endclass

// =============================================================================
// Driver
// =============================================================================
class {{PROTO}}_driver extends uvm_driver #({{PROTO}}_seq_item);
  `uvm_component_utils({{PROTO}}_driver)

  virtual {{PROTO}}_if m_vif;

  function new(string name = "{{PROTO}}_driver", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db #(virtual {{PROTO}}_if)::get(this, "", "vif", m_vif))
      `uvm_fatal("NO_VIF", "Virtual interface not set for driver")
  endfunction

  task run_phase(uvm_phase phase);
    {{PROTO}}_seq_item txn;
    forever begin
      seq_item_port.get_next_item(txn);
      drive_transaction(txn);
      seq_item_port.item_done();
    end
  endtask

  task drive_transaction({{PROTO}}_seq_item txn);
    @(posedge m_vif.sys_clk);
    m_vif.i_valid <= 1'b1;
    m_vif.i_addr  <= txn.addr;
    m_vif.i_data  <= txn.data;
    m_vif.i_wr_en <= txn.wr_en;
    @(posedge m_vif.sys_clk);
    while (!m_vif.o_ready) @(posedge m_vif.sys_clk);
    m_vif.i_valid <= 1'b0;
  endtask
endclass

// =============================================================================
// Monitor
// =============================================================================
class {{PROTO}}_monitor extends uvm_monitor;
  `uvm_component_utils({{PROTO}}_monitor)

  uvm_analysis_port #({{PROTO}}_seq_item) m_ap;
  virtual {{PROTO}}_if m_vif;

  function new(string name = "{{PROTO}}_monitor", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_ap = new("m_ap", this);
    if (!uvm_config_db #(virtual {{PROTO}}_if)::get(this, "", "vif", m_vif))
      `uvm_fatal("NO_VIF", "Virtual interface not set for monitor")
  endfunction

  task run_phase(uvm_phase phase);
    forever begin
      {{PROTO}}_seq_item txn;
      @(posedge m_vif.sys_clk);
      if (m_vif.i_valid && m_vif.o_ready) begin
        txn = {{PROTO}}_seq_item::type_id::create("txn");
        txn.addr  = m_vif.i_addr;
        txn.data  = m_vif.i_data;
        txn.wr_en = m_vif.i_wr_en;
        m_ap.write(txn);
      end
    end
  endtask
endclass

// =============================================================================
// Agent
// =============================================================================
class {{PROTO}}_agent extends uvm_agent;
  `uvm_component_utils({{PROTO}}_agent)

  {{PROTO}}_driver    m_driver;
  {{PROTO}}_monitor   m_monitor;
  uvm_sequencer #({{PROTO}}_seq_item) m_seqr;

  function new(string name = "{{PROTO}}_agent", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_monitor = {{PROTO}}_monitor::type_id::create("m_monitor", this);
    if (get_is_active() == UVM_ACTIVE) begin
      m_driver = {{PROTO}}_driver::type_id::create("m_driver", this);
      m_seqr   = uvm_sequencer #({{PROTO}}_seq_item)::type_id::create("m_seqr", this);
    end
  endfunction

  function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);
    if (get_is_active() == UVM_ACTIVE) begin
      m_driver.seq_item_port.connect(m_seqr.seq_item_export);
    end
  endfunction
endclass

// =============================================================================
// Scoreboard
// =============================================================================
class {{MODULE_NAME}}_scoreboard extends uvm_scoreboard;
  `uvm_component_utils({{MODULE_NAME}}_scoreboard)

  uvm_analysis_imp #({{PROTO}}_seq_item, {{MODULE_NAME}}_scoreboard) m_imp;

  int unsigned m_matches;
  int unsigned m_mismatches;

  // Expected queue (populated by reference model or predictor)
  {{PROTO}}_seq_item m_expected_q[$];

  function new(string name = "{{MODULE_NAME}}_scoreboard", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_imp = new("m_imp", this);
    m_matches = 0;
    m_mismatches = 0;
  endfunction

  function void write({{PROTO}}_seq_item txn);
    if (m_expected_q.size() == 0) begin
      `uvm_error("SB", $sformatf("Unexpected transaction: %s", txn.convert2string()))
      m_mismatches++;
      return;
    end
    begin
      {{PROTO}}_seq_item expected = m_expected_q.pop_front();
      if (txn.data !== expected.data) begin
        `uvm_error("SB", $sformatf("MISMATCH: exp=%s act=%s",
          expected.convert2string(), txn.convert2string()))
        m_mismatches++;
      end else begin
        m_matches++;
      end
    end
  endfunction

  function void report_phase(uvm_phase phase);
    `uvm_info("SB", $sformatf("Scoreboard: %0d matches, %0d mismatches",
      m_matches, m_mismatches), UVM_LOW)
    if (m_mismatches > 0)
      `uvm_error("SB", "TEST FAILED: mismatches detected")
    else
      `uvm_info("SB", "TEST PASSED: all transactions matched", UVM_LOW)
  endfunction
endclass

// =============================================================================
// Environment
// =============================================================================
class {{MODULE_NAME}}_env extends uvm_env;
  `uvm_component_utils({{MODULE_NAME}}_env)

  {{PROTO}}_agent             m_agt;
  {{MODULE_NAME}}_scoreboard  m_scoreboard;

  function new(string name = "{{MODULE_NAME}}_env", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_agt        = {{PROTO}}_agent::type_id::create("m_agt", this);
    m_scoreboard = {{MODULE_NAME}}_scoreboard::type_id::create("m_scoreboard", this);
  endfunction

  function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);
    m_agt.m_monitor.m_ap.connect(m_scoreboard.m_imp);
  endfunction
endclass

// =============================================================================
// Base Test
// =============================================================================
class {{MODULE_NAME}}_base_test extends uvm_test;
  `uvm_component_utils({{MODULE_NAME}}_base_test)

  {{MODULE_NAME}}_env m_env;

  function new(string name = "{{MODULE_NAME}}_base_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_env = {{MODULE_NAME}}_env::type_id::create("m_env", this);
  endfunction

  task run_phase(uvm_phase phase);
    phase.raise_objection(this, "Test started");
    // Override in derived tests to run sequences
    phase.drop_objection(this, "Test completed");
  endtask
endclass

`endif // {{MODULE_NAME_UPPER}}_ENV_SV
