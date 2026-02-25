// =============================================================================
// Example: Complete FIFO SVA Checker (bind file pattern)
// Demonstrates: safety, liveness, coverage, formal-friendly patterns
// =============================================================================

module sva_sync_fifo_checker #(
  parameter int unsigned DEPTH = 16,
  parameter int unsigned WIDTH = 8
) (
  input logic                    sys_clk,
  input logic                    sys_rst_n,
  input logic                    i_push,
  input logic                    i_pop,
  input logic [WIDTH-1:0]        i_wdata,
  input logic [WIDTH-1:0]        o_rdata,
  input logic                    o_full,
  input logic                    o_empty,
  input logic [$clog2(DEPTH):0]  o_count
);

  default clocking cb @(posedge sys_clk); endclocking
  default disable iff (!sys_rst_n);

  logic past_valid;
  always_ff @(posedge sys_clk or negedge sys_rst_n) begin
    if (!sys_rst_n) past_valid <= 1'b0;
    else            past_valid <= 1'b1;
  end

  // ===========================================================================
  // Input Assumptions (formal)
  // ===========================================================================
  m_no_push_when_full: assume property (
    o_full |-> !i_push
  );

  m_no_pop_when_empty: assume property (
    o_empty |-> !i_pop
  );

  // ===========================================================================
  // Safety Assertions
  // ===========================================================================

  // Count never exceeds depth
  a_count_bounded: assert property (
    o_count <= DEPTH
  ) else $error("[%m] Count %0d exceeds DEPTH %0d", o_count, DEPTH);

  // Full flag consistency
  a_full_consistent: assert property (
    o_full == (o_count == DEPTH)
  ) else $error("[%m] Full flag inconsistent with count");

  // Empty flag consistency
  a_empty_consistent: assert property (
    o_empty == (o_count == 0)
  ) else $error("[%m] Empty flag inconsistent with count");

  // Count increments on push-only
  a_push_increment: assert property (
    past_valid && i_push && !i_pop && !o_full
    |=> o_count == $past(o_count) + 1
  ) else $error("[%m] Count did not increment on push");

  // Count decrements on pop-only
  a_pop_decrement: assert property (
    past_valid && i_pop && !i_push && !o_empty
    |=> o_count == $past(o_count) - 1
  ) else $error("[%m] Count did not decrement on pop");

  // Count unchanged on simultaneous push+pop
  a_push_pop_stable: assert property (
    past_valid && i_push && i_pop && !o_empty
    |=> o_count == $past(o_count)
  ) else $error("[%m] Count changed on simultaneous push+pop");

  // No overflow: push when full is illegal
  a_no_overflow: assert property (
    !(i_push && o_full && !i_pop)
  ) else $error("[%m] FIFO overflow: push while full");

  // No underflow: pop when empty is illegal
  a_no_underflow: assert property (
    !(i_pop && o_empty && !i_push)
  ) else $error("[%m] FIFO underflow: pop while empty");

  // ===========================================================================
  // Reset Assertions
  // ===========================================================================
  a_reset_empty: assert property (
    !sys_rst_n |=> o_empty && !o_full && (o_count == 0)
  ) else $error("[%m] FIFO not empty after reset");

  // ===========================================================================
  // Unknown Checks
  // ===========================================================================
  a_count_no_x: assert property (
    !$isunknown(o_count)
  ) else $error("[%m] o_count is X/Z");

  a_flags_no_x: assert property (
    !$isunknown(o_full) && !$isunknown(o_empty)
  ) else $error("[%m] Full/empty flags contain X/Z");

  a_rdata_no_x: assert property (
    !o_empty && i_pop |-> !$isunknown(o_rdata)
  ) else $error("[%m] o_rdata is X/Z during valid pop");

  // ===========================================================================
  // Cover Properties
  // ===========================================================================

  // Fill to full
  c_fill_to_full: cover property (
    o_empty ##[1:$] o_full
  );

  // Drain to empty
  c_drain_to_empty: cover property (
    o_full ##[1:$] o_empty
  );

  // Simultaneous push and pop
  c_push_pop_same_cycle: cover property (
    i_push && i_pop && !o_empty && !o_full
  );

  // Nearly full then pop
  c_almost_full_pop: cover property (
    (o_count == DEPTH - 1) && i_pop && !i_push
  );

  // Rapid fill: consecutive pushes without pop
  c_consecutive_push: cover property (
    (i_push && !i_pop)[*4]
  );

endmodule

// Bind
bind sync_fifo sva_sync_fifo_checker #(
  .DEPTH(DEPTH),
  .WIDTH(WIDTH)
) u_sva_checker (.*);
