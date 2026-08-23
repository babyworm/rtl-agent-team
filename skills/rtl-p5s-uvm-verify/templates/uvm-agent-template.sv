// UVM Agent Template for {{MODULE}}
// Convention: i_/o_ port prefix, {domain}_clk/{domain}_rst_n, m_ UVM member prefix, u_ RTL instance prefix, logic only

// ============================================================
// Interface (connects to DUT ports)
// ============================================================
interface {{MODULE}}_if (
  input logic {{DOMAIN}}_clk,
  input logic {{DOMAIN}}_rst_n
);
  logic        i_valid;
  logic        o_ready;
  logic [7:0]  i_data;
  logic [7:0]  o_data;
  logic        o_valid;

  // Clocking blocks for driver and monitor
  clocking drv_cb @(posedge {{DOMAIN}}_clk);
    output i_valid, i_data;
    input  o_ready;
  endclocking

  clocking mon_cb @(posedge {{DOMAIN}}_clk);
    input i_valid, i_data, o_ready, o_data, o_valid;
  endclocking

  modport DRV (clocking drv_cb, input {{DOMAIN}}_rst_n);
  modport MON (clocking mon_cb, input {{DOMAIN}}_rst_n);
endinterface

// ============================================================
// Sequence Item
// ============================================================
class {{MODULE}}_seq_item extends uvm_sequence_item;
  `uvm_object_utils({{MODULE}}_seq_item)

  rand logic [7:0] data;

  constraint c_data_range { data inside {[0:255]}; }

  function new(string name = "{{MODULE}}_seq_item");
    super.new(name);
  endfunction
endclass

// ============================================================
// Driver
// ============================================================
class {{MODULE}}_driver extends uvm_driver #({{MODULE}}_seq_item);
  `uvm_component_utils({{MODULE}}_driver)

  virtual {{MODULE}}_if.DRV vif;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db#(virtual {{MODULE}}_if.DRV)::get(this, "", "vif", vif))
      `uvm_fatal("NOVIF", "Virtual interface not set for driver")
  endfunction

  task run_phase(uvm_phase phase);
    forever begin
      seq_item_port.get_next_item(req);
      drive_item(req);
      seq_item_port.item_done();
    end
  endtask

  task drive_item({{MODULE}}_seq_item item);
    @(vif.drv_cb);
    vif.drv_cb.i_valid <= 1'b1;
    vif.drv_cb.i_data  <= item.data;
    do begin
      @(vif.drv_cb);
    end while (!vif.drv_cb.o_ready);
    vif.drv_cb.i_valid <= 1'b0;
  endtask
endclass

// ============================================================
// Monitor
// ============================================================
class {{MODULE}}_monitor extends uvm_monitor;
  `uvm_component_utils({{MODULE}}_monitor)

  virtual {{MODULE}}_if.MON vif;
  uvm_analysis_port #({{MODULE}}_seq_item) ap;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    ap = new("ap", this);
    if (!uvm_config_db#(virtual {{MODULE}}_if.MON)::get(this, "", "vif", vif))
      `uvm_fatal("NOVIF", "Virtual interface not set for monitor")
  endfunction

  task run_phase(uvm_phase phase);
    forever begin
      do begin
        @(vif.mon_cb);
      end while (!vif.mon_cb.o_valid);
      begin
        {{MODULE}}_seq_item item = {{MODULE}}_seq_item::type_id::create("item");
        item.data = vif.mon_cb.o_data;
        ap.write(item);
      end
    end
  endtask
endclass

// ============================================================
// Agent
// ============================================================
class {{MODULE}}_agent extends uvm_agent;
  `uvm_component_utils({{MODULE}}_agent)

  {{MODULE}}_driver  m_driver;
  {{MODULE}}_monitor m_monitor;
  uvm_sequencer #({{MODULE}}_seq_item) m_seqr;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_driver    = {{MODULE}}_driver::type_id::create("m_driver", this);
    m_monitor   = {{MODULE}}_monitor::type_id::create("m_monitor", this);
    m_seqr = uvm_sequencer#({{MODULE}}_seq_item)::type_id::create("m_seqr", this);
  endfunction

  function void connect_phase(uvm_phase phase);
    m_driver.seq_item_port.connect(m_seqr.seq_item_export);
  endfunction
endclass
