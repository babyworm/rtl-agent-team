// UVM Test Template for {{MODULE}}
// Convention: m_ UVM member prefix, u_ RTL instance prefix, {domain}_clk/{domain}_rst_n

// ============================================================
// Environment
// ============================================================
class {{MODULE}}_env extends uvm_env;
  `uvm_component_utils({{MODULE}}_env)

  {{MODULE}}_agent m_agent;
  // {{MODULE}}_scoreboard m_scoreboard;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_agent = {{MODULE}}_agent::type_id::create("m_agent", this);
    // m_scoreboard = {{MODULE}}_scoreboard::type_id::create("m_scoreboard", this);
  endfunction

  function void connect_phase(uvm_phase phase);
    // m_agent.m_monitor.ap.connect(m_scoreboard.analysis_export);
  endfunction
endclass

// ============================================================
// Base Test
// ============================================================
class {{MODULE}}_base_test extends uvm_test;
  `uvm_component_utils({{MODULE}}_base_test)

  {{MODULE}}_env m_env;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_env = {{MODULE}}_env::type_id::create("m_env", this);
  endfunction

  function void end_of_elaboration_phase(uvm_phase phase);
    uvm_top.print_topology();
  endfunction
endclass

// ============================================================
// Base Sequence
// ============================================================
class {{MODULE}}_base_seq extends uvm_sequence #({{MODULE}}_seq_item);
  `uvm_object_utils({{MODULE}}_base_seq)

  function new(string name = "{{MODULE}}_base_seq");
    super.new(name);
  endfunction

  task body();
    {{MODULE}}_seq_item item;
    repeat(100) begin
      item = {{MODULE}}_seq_item::type_id::create("item");
      start_item(item);
      assert(item.randomize());
      finish_item(item);
    end
  endtask
endclass

// ============================================================
// Directed Test
// ============================================================
class {{MODULE}}_directed_test extends {{MODULE}}_base_test;
  `uvm_component_utils({{MODULE}}_directed_test)

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  task run_phase(uvm_phase phase);
    {{MODULE}}_base_seq seq;
    phase.raise_objection(this);

    seq = {{MODULE}}_base_seq::type_id::create("seq");
    seq.start(m_env.m_agent.m_seqr);

    phase.drop_objection(this);
  endtask
endclass

// ============================================================
// Top-Level Testbench Module
// ============================================================
module tb_top;
  logic {{DOMAIN}}_clk;
  logic {{DOMAIN}}_rst_n;

  // Clock generation
  initial begin
    {{DOMAIN}}_clk = 0;
    forever #5 {{DOMAIN}}_clk = ~{{DOMAIN}}_clk;
  end

  // Reset
  initial begin
    {{DOMAIN}}_rst_n = 0;
    #100;
    {{DOMAIN}}_rst_n = 1;
  end

  // Interface
  {{MODULE}}_if u_if(.{{DOMAIN}}_clk({{DOMAIN}}_clk), .{{DOMAIN}}_rst_n({{DOMAIN}}_rst_n));

  // DUT instantiation (u_ prefix)
  {{MODULE}} u_dut (
    .{{DOMAIN}}_clk  ({{DOMAIN}}_clk),
    .{{DOMAIN}}_rst_n({{DOMAIN}}_rst_n),
    .i_valid         (u_if.i_valid),
    .o_ready         (u_if.o_ready),
    .i_data          (u_if.i_data),
    .o_data          (u_if.o_data),
    .o_valid         (u_if.o_valid)
  );

  // UVM config and run
  initial begin
    uvm_config_db#(virtual {{MODULE}}_if.DRV)::set(null, "*", "vif", u_if);
    uvm_config_db#(virtual {{MODULE}}_if.MON)::set(null, "*", "vif", u_if);
    run_test();
  end
endmodule
