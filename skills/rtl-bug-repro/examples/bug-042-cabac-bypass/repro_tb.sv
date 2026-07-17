// repro_tb.sv — Minimal reproduction testbench for BUG-042
// Target module: cabac_encoder
// Symptom: o_bin_val stuck at previous context value in bypass mode
// First failure cycle: 247
//
// Conventions (see references/bug-repro-conventions.md):
//   - DUT instance: u_dut
//   - Clock: sys_clk, Reset: sys_rst_n (active-low async)
//   - Ports: i_ prefix (input), o_ prefix (output)
//   - Types: logic only (no reg/wire)

`timescale 1ns / 1ps

module repro_tb;

  // ─── Parameters ────────────────────────────────────────────────────────
  localparam int L_CLK_PERIOD = 10;   // ns
  localparam int L_FAIL_CYCLE = 247;
  localparam int L_MARGIN     = 50;   // extra cycles after expected failure

  // ─── Signals ───────────────────────────────────────────────────────────
  logic       sys_clk;
  logic       sys_rst_n;
  logic       i_bin_valid;
  logic       i_bin;
  logic       i_bypass_en;
  logic       o_bit_valid;
  logic       o_bin_val;

  // ─── DUT Instantiation ─────────────────────────────────────────────────
  cabac_encoder u_dut (
    .sys_clk     (sys_clk),
    .sys_rst_n   (sys_rst_n),
    .i_bin_valid (i_bin_valid),
    .i_bin       (i_bin),
    .i_bypass_en (i_bypass_en),
    .o_bit_valid (o_bit_valid),
    .o_bin_val   (o_bin_val)
  );

  // ─── Clock Generation ──────────────────────────────────────────────────
  initial sys_clk = 1'b0;
  always #(L_CLK_PERIOD / 2) sys_clk = ~sys_clk;

  // ─── Waveform Dump ─────────────────────────────────────────────────────
  initial begin
    $dumpfile("sim/bugs/BUG-042/repro_tb.vcd");
    $dumpvars(0, repro_tb);
  end

  // ─── Timeout (fail_cycle + margin) ─────────────────────────────────────
  initial begin
    repeat (L_FAIL_CYCLE + L_MARGIN) @(posedge sys_clk);
    $display("ERROR: Timeout — bug did NOT reproduce within %0d cycles",
             L_FAIL_CYCLE + L_MARGIN);
    $finish(1);
  end

  // ─── Reset + Minimal Stimulus ──────────────────────────────────────────
  initial begin
    $display("=== Bug Repro: BUG-042 ===");
    $display("Target: cabac_encoder, expected failure at cycle ~%0d", L_FAIL_CYCLE);

    i_bin_valid = 1'b0;
    i_bin       = 1'b0;
    i_bypass_en = 1'b0;

    // Reset
    sys_rst_n = 1'b0;
    repeat (5) @(posedge sys_clk);
    sys_rst_n = 1'b1;
    repeat (2) @(posedge sys_clk);

    // Minimal stimulus: one regular-mode bin loads bypass_ctx, then the
    // first bypass-mode bin exposes the missing bypass_ctx reset.
    @(posedge sys_clk);
    i_bin_valid <= 1'b1;      // regular-mode bin: primes bypass_ctx
    i_bin       <= 1'b1;
    i_bypass_en <= 1'b0;
    @(posedge sys_clk);
    i_bin_valid <= 1'b0;
    repeat (238) @(posedge sys_clk);  // drain interval matching failing test
    i_bin_valid <= 1'b1;      // bypass-mode bin: must NOT reuse bypass_ctx
    i_bin       <= 1'b0;
    i_bypass_en <= 1'b1;
    @(posedge sys_clk);
    i_bin_valid <= 1'b0;

    // Check at the expected failure cycle: bypass output must equal i_bin (0)
    wait (o_bit_valid);
    @(negedge sys_clk);
    if (o_bin_val !== 1'b0) begin
      $display("BUG REPRODUCED at cycle %0d: expected o_bin_val=0, got %b",
               L_FAIL_CYCLE, o_bin_val);
      $finish(0);  // success: bug reproduced
    end

    $display("Bug NOT reproduced — stimulus may need adjustment");
    $finish(1);
  end

endmodule
