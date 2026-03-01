// Example: FIFO Safety SVA Assertions
// Convention: i_/o_ port prefix, sys_clk, sys_rst_n

module fifo_props #(
  parameter DEPTH = 16
)(
  input logic sys_clk,
  input logic sys_rst_n,
  input logic i_push,
  input logic i_pop,
  input logic o_full,
  input logic o_empty,
  input logic [$clog2(DEPTH):0] o_count
);

  // No overflow: push when full is forbidden
  no_overflow: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    o_full |-> !i_push
  ) else $error("FAIL: push attempted while FIFO full");

  // No underflow: pop when empty is forbidden
  no_underflow: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    o_empty |-> !i_pop
  ) else $error("FAIL: pop attempted while FIFO empty");

  // Count consistency: full when count == DEPTH
  full_at_depth: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (o_count == DEPTH) |-> o_full
  );

  // Count consistency: empty when count == 0
  empty_at_zero: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (o_count == 0) |-> o_empty
  );

  // Count bounded: never exceeds DEPTH
  count_bounded: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    o_count <= DEPTH
  );

  // After reset: FIFO must be empty
  reset_empty: assert property (
    @(posedge sys_clk)
    !sys_rst_n |=> (o_empty && !o_full && o_count == 0)
  );

  // Cover: fill to full then drain to empty
  fill_and_drain: cover property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    o_empty ##[1:$] o_full ##[1:$] o_empty
  );

endmodule
