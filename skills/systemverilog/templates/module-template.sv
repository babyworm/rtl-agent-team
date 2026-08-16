// =============================================================================
// Module: {{MODULE_NAME}}
// Description: {{BRIEF_DESCRIPTION}}
// Author: rtl-coder (generated)
// =============================================================================

// Package import (if needed)
// import {{MODULE_NAME}}_pkg::*;

module {{MODULE_NAME}} #(
  // ---------------------------------------------------------------------------
  // Parameters
  // ---------------------------------------------------------------------------
  parameter int unsigned DATA_WIDTH = 8
) (
  // ---------------------------------------------------------------------------
  // Clock & Reset
  // ---------------------------------------------------------------------------
  input  logic                    sys_clk,
  input  logic                    sys_rst_n,    // active-low async reset

  // ---------------------------------------------------------------------------
  // Input Ports
  // ---------------------------------------------------------------------------
  input  logic [DATA_WIDTH-1:0]   i_data,
  input  logic                    i_valid,
  output logic                    o_ready,      // backpressure to upstream

  // ---------------------------------------------------------------------------
  // Output Ports
  // ---------------------------------------------------------------------------
  output logic [DATA_WIDTH-1:0]   o_data,
  output logic                    o_valid,
  input  logic                    i_ready       // backpressure from downstream
);

  // ===========================================================================
  // Local Parameters
  // ===========================================================================
  // Every localparam must be referenced — Verilator -Wall (which rtl-coder runs
  // after every write) reports an unused one as UNUSEDPARAM and fails the lint.
  localparam int unsigned L_STATE_WIDTH = 2;

  // ===========================================================================
  // Type Definitions (or import from _pkg.sv)
  // ===========================================================================
  typedef enum logic [L_STATE_WIDTH-1:0] {
    ST_IDLE    = 2'b00,
    ST_ACTIVE  = 2'b01,
    ST_DONE    = 2'b10
  } state_t;

  // ===========================================================================
  // Internal Signals
  // ===========================================================================
  state_t                   state_q, state_d;
  logic [DATA_WIDTH-1:0]    data_q;

  // ===========================================================================
  // Sub-module Instances
  // ===========================================================================
  // {{MODULE_NAME}}_sub u_sub (
  //   .sys_clk   (sys_clk),
  //   .sys_rst_n (sys_rst_n),
  //   .i_data    (data_q),
  //   .o_result  (o_data)
  // );

  // ===========================================================================
  // Combinational Logic
  // ===========================================================================
  always_comb begin
    // Defaults (prevent latches)
    state_d = state_q;
    o_ready = 1'b0;
    o_valid = 1'b0;
    o_data  = '0;

    unique case (state_q)
      ST_IDLE: begin
        o_ready = 1'b1;
        if (i_valid) begin
          state_d = ST_ACTIVE;
        end
      end

      ST_ACTIVE: begin
        o_valid = 1'b1;
        o_data  = data_q;
        if (i_ready) begin
          state_d = ST_DONE;
        end
      end

      ST_DONE: begin
        state_d = ST_IDLE;
      end

      default: begin
        state_d = ST_IDLE;
      end
    endcase
  end

  // ===========================================================================
  // Sequential Logic
  // ===========================================================================
  always_ff @(posedge sys_clk or negedge sys_rst_n) begin
    if (!sys_rst_n) begin
      state_q <= ST_IDLE;
      data_q  <= '0;
    end else begin
      state_q <= state_d;
      if (i_valid && o_ready) begin
        data_q <= i_data;
      end
    end
  end

  // ===========================================================================
  // Assertions (synthesis: ignored; simulation: active)
  // ===========================================================================
  // synopsys translate_off
  // synthesis translate_off
  `ifdef SIMULATION
  assert property (@(posedge sys_clk) disable iff (!sys_rst_n)
    i_valid && !o_ready |=> $stable(i_data)
  ) else $error("i_data must be stable when valid && !ready");

  assert property (@(posedge sys_clk) disable iff (!sys_rst_n)
    i_valid && !o_ready |=> i_valid
  ) else $error("i_valid must hold until ready");
  `endif
  // synthesis translate_on
  // synopsys translate_on

endmodule
