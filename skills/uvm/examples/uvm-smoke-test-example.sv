// =============================================================================
// Example: UVM Smoke Test with Sequence and Factory Override
// Demonstrates: test structure, sequence, factory override, coverage
// =============================================================================

// --- Base Sequence ---
class axi_base_seq extends uvm_sequence #(axi_seq_item);
  `uvm_object_utils(axi_base_seq)

  function new(string name = "axi_base_seq");
    super.new(name);
  endfunction
endclass

// --- Write Sequence ---
class axi_write_seq extends axi_base_seq;
  `uvm_object_utils(axi_write_seq)

  rand int unsigned num_txns;
  constraint c_num { num_txns inside {[10:100]}; }

  function new(string name = "axi_write_seq");
    super.new(name);
  endfunction

  task body();
    axi_seq_item txn;
    repeat (num_txns) begin
      txn = axi_seq_item::type_id::create("txn");
      start_item(txn);
      if (!txn.randomize() with { wr_en == 1'b1; })
        `uvm_error("SEQ", "Randomization failed")
      finish_item(txn);
    end
  endtask
endclass

// --- Read-After-Write Sequence ---
class axi_raw_seq extends axi_base_seq;
  `uvm_object_utils(axi_raw_seq)

  function new(string name = "axi_raw_seq");
    super.new(name);
  endfunction

  task body();
    axi_seq_item wr_txn, rd_txn;

    // Write
    wr_txn = axi_seq_item::type_id::create("wr_txn");
    start_item(wr_txn);
    if (!wr_txn.randomize() with { wr_en == 1'b1; })
      `uvm_error("SEQ", "Write randomization failed")
    finish_item(wr_txn);

    // Read same address
    rd_txn = axi_seq_item::type_id::create("rd_txn");
    start_item(rd_txn);
    if (!rd_txn.randomize() with {
      wr_en == 1'b0;
      addr  == wr_txn.addr;
    }) `uvm_error("SEQ", "Read randomization failed")
    finish_item(rd_txn);
  endtask
endclass

// --- Smoke Test ---
class cabac_smoke_test extends cabac_base_test;
  `uvm_component_utils(cabac_smoke_test)

  function new(string name = "cabac_smoke_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    // Factory override example: replace base sequence with specific one
    // axi_base_seq::type_id::set_type_override(axi_write_seq::get_type());
  endfunction

  task run_phase(uvm_phase phase);
    axi_write_seq wr_seq;
    axi_raw_seq   raw_seq;

    phase.raise_objection(this, "Smoke test started");

    // Phase 1: Write burst
    wr_seq = axi_write_seq::type_id::create("wr_seq");
    wr_seq.num_txns = 20;
    wr_seq.start(m_env.m_agt.m_seqr);
    `uvm_info("TEST", "Write burst complete", UVM_MEDIUM)

    // Phase 2: Read-after-write
    repeat (10) begin
      raw_seq = axi_raw_seq::type_id::create("raw_seq");
      raw_seq.start(m_env.m_agt.m_seqr);
    end
    `uvm_info("TEST", "Read-after-write complete", UVM_MEDIUM)

    // Drain time
    #100ns;

    phase.drop_objection(this, "Smoke test completed");
  endtask
endclass

// --- Random Stress Test ---
class cabac_random_test extends cabac_base_test;
  `uvm_component_utils(cabac_random_test)

  function new(string name = "cabac_random_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  task run_phase(uvm_phase phase);
    axi_write_seq seq;

    phase.raise_objection(this, "Random test started");

    seq = axi_write_seq::type_id::create("seq");
    seq.num_txns = 1000;  // Stress with many transactions
    seq.start(m_env.m_agt.m_seqr);

    #500ns;
    phase.drop_objection(this, "Random test completed");
  endtask
endclass

// =============================================================================
// Testbench Top (tb_cabac_top.sv)
// =============================================================================
// module tb_cabac_top;
//   import uvm_pkg::*;
//   `include "uvm_macros.svh"
//   import cabac_tb_pkg::*;
//
//   // Clock/Reset generation
//   logic sys_clk, sys_rst_n;
//   initial sys_clk = 0;
//   always #5ns sys_clk = ~sys_clk;
//   initial begin
//     sys_rst_n = 0;
//     #20ns;
//     sys_rst_n = 1;
//   end
//
//   // Interface
//   axi_if u_axi_if(.sys_clk(sys_clk), .sys_rst_n(sys_rst_n));
//
//   // DUT
//   cabac_encoder u_dut (
//     .sys_clk   (sys_clk),
//     .sys_rst_n (sys_rst_n),
//     .i_data    (u_axi_if.i_data),
//     .i_valid   (u_axi_if.i_valid),
//     .o_ready   (u_axi_if.o_ready),
//     .o_data    (u_axi_if.o_data),
//     .o_valid   (u_axi_if.o_valid)
//   );
//
//   initial begin
//     uvm_config_db #(virtual axi_if)::set(null, "uvm_test_top.m_env.m_agt*", "vif", u_axi_if);
//     run_test();  // Test name from +UVM_TESTNAME=cabac_smoke_test
//   end
// endmodule
