// Example: AXI4-Lite Protocol Assertions (slave perspective)
// Convention: i_/o_ prefix, sys_clk, sys_rst_n

module axi4_lite_slave_assertions (
  input logic sys_clk,
  input logic sys_rst_n,
  // Write Address Channel
  input logic i_awvalid,
  input logic o_awready,
  input logic [31:0] i_awaddr,
  // Write Data Channel
  input logic i_wvalid,
  input logic o_wready,
  input logic [31:0] i_wdata,
  input logic [3:0]  i_wstrb,
  // Write Response Channel
  input logic o_bvalid,
  input logic i_bready,
  input logic [1:0]  o_bresp,
  // Read Address Channel
  input logic i_arvalid,
  input logic o_arready,
  input logic [31:0] i_araddr,
  // Read Data Channel
  input logic o_rvalid,
  input logic i_rready,
  input logic [31:0] o_rdata,
  input logic [1:0]  o_rresp
);

  // ============================================================
  // Write Address Channel
  // ============================================================

  // AW-1: AWVALID must hold until AWREADY
  aw_valid_hold: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (i_awvalid && !o_awready) |=> i_awvalid
  ) else $error("AXI: i_awvalid dropped before o_awready");

  // AW-2: AWADDR stable while waiting
  aw_addr_stable: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (i_awvalid && !o_awready) |=> $stable(i_awaddr)
  ) else $error("AXI: i_awaddr changed during wait");

  // ============================================================
  // Write Data Channel
  // ============================================================

  // W-1: WVALID must hold until WREADY
  w_valid_hold: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (i_wvalid && !o_wready) |=> i_wvalid
  ) else $error("AXI: i_wvalid dropped before o_wready");

  // W-2: WDATA stable while waiting
  w_data_stable: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (i_wvalid && !o_wready) |=> $stable(i_wdata)
  ) else $error("AXI: i_wdata changed during wait");

  // ============================================================
  // Write Response Channel (slave drives these)
  // ============================================================

  // B-1: BVALID must hold until BREADY
  b_valid_hold: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (o_bvalid && !i_bready) |=> o_bvalid
  ) else $error("AXI: o_bvalid dropped before i_bready");

  // B-2: BRESP stable while waiting
  b_resp_stable: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (o_bvalid && !i_bready) |=> $stable(o_bresp)
  ) else $error("AXI: o_bresp changed during wait");

  // ============================================================
  // Read Address Channel
  // ============================================================

  // AR-1: ARVALID must hold until ARREADY
  ar_valid_hold: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (i_arvalid && !o_arready) |=> i_arvalid
  ) else $error("AXI: i_arvalid dropped before o_arready");

  // ============================================================
  // Read Data Channel (slave drives these)
  // ============================================================

  // R-1: RVALID must hold until RREADY
  r_valid_hold: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (o_rvalid && !i_rready) |=> o_rvalid
  ) else $error("AXI: o_rvalid dropped before i_rready");

  // R-2: RDATA stable while waiting
  r_data_stable: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (o_rvalid && !i_rready) |=> $stable(o_rdata)
  ) else $error("AXI: o_rdata changed during wait");

  // ============================================================
  // No X/Z checks
  // ============================================================

  aw_no_x: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    i_awvalid |-> !$isunknown(i_awaddr)
  );

  w_no_x: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    i_wvalid |-> !$isunknown(i_wdata)
  );

  r_no_x: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    o_rvalid |-> !$isunknown(o_rdata)
  );

endmodule
