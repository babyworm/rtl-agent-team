// SVA Property Template for {{MODULE}}
// Convention: i_ prefix inputs, o_ prefix outputs, {domain}_clk, {domain}_rst_n
// Principle: assume inputs, assert outputs

module {{MODULE}}_props #(
  // Mirror the DUT's parameters so the bind passes them straight through.
  parameter int unsigned DATA_WIDTH = 8
) (
  input logic {{DOMAIN}}_clk,
  input logic {{DOMAIN}}_rst_n,
  // Add DUT ports here with i_/o_ prefix
  input logic i_valid,
  input logic o_ready,
  input logic [DATA_WIDTH-1:0] i_data,
  input logic [DATA_WIDTH-1:0] o_data
);

  // ============================================================
  // Helper: guard $past() against undefined first-cycle behavior
  // ============================================================
  logic past_valid;
  always_ff @(posedge {{DOMAIN}}_clk or negedge {{DOMAIN}}_rst_n) begin
    if (!{{DOMAIN}}_rst_n)
      past_valid <= 1'b0;
    else
      past_valid <= 1'b1;
  end

  // ============================================================
  // Input Assumptions (constrain inputs to legal ranges)
  // ============================================================
  // assume property (@(posedge {{DOMAIN}}_clk) disable iff (!{{DOMAIN}}_rst_n)
  //   i_data inside {[0:MAX_VALUE]});

  // ============================================================
  // Output Assertions (verify DUT behavior)
  // ============================================================

  // A1: No X/Z on valid output
  no_x_on_output: assert property (
    @(posedge {{DOMAIN}}_clk) disable iff (!{{DOMAIN}}_rst_n)
    !$isunknown(o_data)
  );

  // A2: Handshake stability — valid must hold until ready
  valid_hold_until_ready: assert property (
    @(posedge {{DOMAIN}}_clk) disable iff (!{{DOMAIN}}_rst_n)
    (i_valid && !o_ready) |=> i_valid
  );

  // A3: Data stability during handshake wait
  data_stable_during_wait: assert property (
    @(posedge {{DOMAIN}}_clk) disable iff (!{{DOMAIN}}_rst_n)
    (past_valid && i_valid && !o_ready) |=> $stable(i_data)
  );

  // ============================================================
  // Cover Properties (verify reachability)
  // ============================================================

  // C1: Normal handshake completes
  handshake_complete: cover property (
    @(posedge {{DOMAIN}}_clk) disable iff (!{{DOMAIN}}_rst_n)
    i_valid && o_ready
  );

  // C2: Backpressure scenario exercised
  backpressure_scenario: cover property (
    @(posedge {{DOMAIN}}_clk) disable iff (!{{DOMAIN}}_rst_n)
    i_valid && !o_ready ##[1:5] i_valid && o_ready
  );

endmodule
