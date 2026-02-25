// =============================================================================
// SVA Bind File Template
// Target Module: {{MODULE_NAME}}
// Description: Assertion checker for {{MODULE_NAME}}
// Author: sva-extractor (generated)
// Convention: systemverilog-assertion skill
// =============================================================================

module sva_{{MODULE_NAME}}_checker #(
  parameter int unsigned DATA_WIDTH = 8
) (
  // ---------------------------------------------------------------------------
  // Clock & Reset (must match RTL ports)
  // ---------------------------------------------------------------------------
  input logic                    sys_clk,
  input logic                    sys_rst_n,

  // ---------------------------------------------------------------------------
  // Observed Signals (match RTL port/internal names)
  // ---------------------------------------------------------------------------
  input logic [DATA_WIDTH-1:0]   i_data,
  input logic                    i_valid,
  input logic                    o_ready,
  input logic [DATA_WIDTH-1:0]   o_data,
  input logic                    o_valid,
  input logic                    i_ready
);

  // ===========================================================================
  // Default Clocking & Reset
  // ===========================================================================
  default clocking cb @(posedge sys_clk); endclocking
  default disable iff (!sys_rst_n);

  // ===========================================================================
  // Past-Valid Guard (for $past usage)
  // ===========================================================================
  logic past_valid;
  always_ff @(posedge sys_clk or negedge sys_rst_n) begin
    if (!sys_rst_n) past_valid <= 1'b0;
    else            past_valid <= 1'b1;
  end

  // ===========================================================================
  // Input Assumptions (for formal verification only)
  // ===========================================================================
  // Valid must not be unknown
  m_valid_no_x: assume property (
    !$isunknown(i_valid)
  );

  // Data must not be unknown when valid
  m_data_no_x: assume property (
    i_valid |-> !$isunknown(i_data)
  );

  // ===========================================================================
  // Output Assertions
  // ===========================================================================

  // --- Handshake: valid hold until ready ---
  a_valid_hold: assert property (
    i_valid && !o_ready |=> i_valid
  ) else $error("[%m] i_valid dropped before o_ready at %0t", $time);

  // --- Handshake: data stable while valid ---
  a_data_stable: assert property (
    i_valid && !o_ready |=> $stable(i_data)
  ) else $error("[%m] i_data changed while valid && !ready at %0t", $time);

  // --- Output valid must not be unknown ---
  a_o_valid_no_x: assert property (
    !$isunknown(o_valid)
  ) else $error("[%m] o_valid is X/Z at %0t", $time);

  // --- Output data must not be unknown when valid ---
  a_o_data_no_x: assert property (
    o_valid |-> !$isunknown(o_data)
  ) else $error("[%m] o_data is X/Z while o_valid at %0t", $time);

  // ===========================================================================
  // TODO: Module-Specific Assertions
  // ===========================================================================
  // Add assertions specific to {{MODULE_NAME}} behavior:
  // - State machine transitions
  // - Timing constraints (latency bounds)
  // - Data integrity (CRC, parity)
  // - Protocol compliance

  // ===========================================================================
  // Cover Properties (reachability)
  // ===========================================================================

  // --- Basic operation cover ---
  c_single_transfer: cover property (
    i_valid && o_ready ##1 o_valid && i_ready
  );

  // --- Back-to-back transfer ---
  c_back_to_back: cover property (
    (i_valid && o_ready)[*2]
  );

  // --- Backpressure scenario ---
  c_backpressure: cover property (
    i_valid && !o_ready ##[1:10] i_valid && o_ready
  );

endmodule

// =============================================================================
// Bind Statement
// =============================================================================
bind {{MODULE_NAME}} sva_{{MODULE_NAME}}_checker #(
  .DATA_WIDTH(DATA_WIDTH)
) u_sva_checker (
  .sys_clk   (sys_clk),
  .sys_rst_n (sys_rst_n),
  .i_data    (i_data),
  .i_valid   (i_valid),
  .o_ready   (o_ready),
  .o_data    (o_data),
  .o_valid   (o_valid),
  .i_ready   (i_ready)
);
