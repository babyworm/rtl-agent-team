// repro_tb.sv — Minimal reproduction testbench for {{BUG_ID}}
// Target module: {{MODULE_NAME}}
// Symptom: {{SYMPTOM}}
// First failure cycle: {{FAIL_CYCLE}}
//
// Conventions:
//   - DUT instance: u_dut
//   - Clock: {{DOMAIN}}_clk, Reset: {{DOMAIN}}_rst_n (active-low async)
//   - Ports: i_ prefix (input), o_ prefix (output)
//   - Types: logic only (no reg/wire)

`timescale 1ns / 1ps

module repro_tb;

  // ─── Parameters ────────────────────────────────────────────────────────
  localparam int L_CLK_PERIOD = 10;  // ns
  localparam int L_FAIL_CYCLE = {{FAIL_CYCLE}};
  localparam int L_MARGIN     = 50;  // extra cycles after expected failure

  // ─── Signals ───────────────────────────────────────────────────────────
  logic {{DOMAIN}}_clk;
  logic {{DOMAIN}}_rst_n;

  // TODO: Add only the signals needed to reproduce this bug
  // logic [DATA_WIDTH-1:0] i_data;
  // logic                  o_result;

  // ─── DUT Instantiation ─────────────────────────────────────────────────
  {{MODULE_NAME}} u_dut (
    .{{DOMAIN}}_clk   ({{DOMAIN}}_clk),
    .{{DOMAIN}}_rst_n ({{DOMAIN}}_rst_n)
    // TODO: Connect only ports relevant to reproduction
  );

  // ─── Clock Generation ──────────────────────────────────────────────────
  initial {{DOMAIN}}_clk = 1'b0;
  always #(L_CLK_PERIOD / 2) {{DOMAIN}}_clk = ~{{DOMAIN}}_clk;

  // ─── Waveform Dump ─────────────────────────────────────────────────────
  initial begin
    `ifdef FSDB_DUMP
      $fsdbDumpfile($sformatf("sim/bugs/{{BUG_ID}}/repro_tb.fsdb"));
      $fsdbDumpvars(0, repro_tb, "+all");
    `endif
    `ifdef SHM_DUMP
      $shm_open($sformatf("sim/bugs/{{BUG_ID}}/repro_tb.shm"));
      $shm_probe(repro_tb, "ASMC");
    `endif
    `ifdef VCD_DUMP
      $dumpfile($sformatf("sim/bugs/{{BUG_ID}}/repro_tb.vcd"));
      $dumpvars(0, repro_tb);
    `endif
  end

  // ─── Timeout (fail_cycle + margin) ─────────────────────────────────────
  initial begin
    repeat (L_FAIL_CYCLE + L_MARGIN) @(posedge {{DOMAIN}}_clk);
    $display("ERROR: Timeout — bug did NOT reproduce within %0d cycles", L_FAIL_CYCLE + L_MARGIN);
    $finish(1);
  end

  // ─── Reset + Minimal Stimulus ──────────────────────────────────────────
  initial begin
    $display("=== Bug Repro: {{BUG_ID}} ===");
    $display("Target: {{MODULE_NAME}}, expected failure at cycle ~%0d", L_FAIL_CYCLE);

    // Reset
    {{DOMAIN}}_rst_n = 1'b0;
    repeat (5) @(posedge {{DOMAIN}}_clk);
    {{DOMAIN}}_rst_n = 1'b1;
    repeat (2) @(posedge {{DOMAIN}}_clk);

    // TODO: Apply minimal stimulus sequence that triggers the bug
    // ──────────────────────────────────────────────────────────
    // Cycle N: ...
    // Cycle N+1: ...
    // ──────────────────────────────────────────────────────────

    // Wait for expected failure cycle
    repeat (L_FAIL_CYCLE) @(posedge {{DOMAIN}}_clk);

    // TODO: Check for the failure condition
    // if (u_dut.o_signal !== expected_value) begin
    //   $display("BUG REPRODUCED at cycle %0d: expected 0x%0h, got 0x%0h",
    //            L_FAIL_CYCLE, expected_value, u_dut.o_signal);
    //   $finish(0);  // success: bug reproduced
    // end

    $display("Bug NOT reproduced — stimulus may need adjustment");
    $finish(1);
  end

endmodule
