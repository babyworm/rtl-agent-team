// Example: Valid/Ready Handshake SVA Assertions
// Convention: i_/o_ port prefix, sys_clk, sys_rst_n

module handshake_props (
  input logic sys_clk,
  input logic sys_rst_n,
  input logic i_valid,
  input logic o_ready,
  input logic [7:0] i_data
);

  logic past_valid;
  always_ff @(posedge sys_clk or negedge sys_rst_n) begin
    if (!sys_rst_n) past_valid <= 1'b0;
    else            past_valid <= 1'b1;
  end

  // VALID must not depend on READY (ARM AMBA rule)
  // Cannot directly prove in SVA — use assume/assert pair:
  // Assume READY can be delayed arbitrarily; assert VALID still asserts

  // VALID must hold until handshake completes
  valid_hold: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (i_valid && !o_ready) |=> i_valid
  ) else $error("FAIL: i_valid dropped before o_ready");

  // Data must be stable while VALID is high and READY is low
  data_stable: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (past_valid && i_valid && !o_ready) |=> $stable(i_data)
  ) else $error("FAIL: i_data changed during wait state");

  // No X/Z on data when valid
  no_unknown_data: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    i_valid |-> !$isunknown(i_data)
  ) else $error("FAIL: i_data contains X/Z while i_valid");

  // Cover: back-to-back handshakes
  back_to_back: cover property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (i_valid && o_ready) ##1 (i_valid && o_ready)
  );

  // Cover: long backpressure (8 cycles)
  long_backpressure: cover property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    i_valid && !o_ready ##8 o_ready
  );

endmodule
