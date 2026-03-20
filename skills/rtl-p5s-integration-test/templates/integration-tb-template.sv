// integration_tb_{{TOP_NAME}}.sv — Tier 4 Integration Testbench
// Verifies cross-module connectivity, data flow, and handshake correctness
//
// Conventions:
//   - DUT instance: u_dut (top-level wrapper)
//   - Sub-module instances: u_{module_name}
//   - Clock: {{DOMAIN}}_clk, Reset: {{DOMAIN}}_rst_n
//   - Ports: i_ prefix (input), o_ prefix (output)
//   - Types: logic only

`timescale 1ns / 1ps

module integration_tb_{{TOP_NAME}};

  // ─── Parameters ────────────────────────────────────────────────────────
  localparam int L_CLK_PERIOD = 10;
  localparam int L_TIMEOUT    = 500_000;

  // ─── Signals ───────────────────────────────────────────────────────────
  logic {{DOMAIN}}_clk;
  logic {{DOMAIN}}_rst_n;

  // TODO: Top-level I/O signals
  // logic [DATA_WIDTH-1:0] i_data;
  // logic                  o_result;

  // ─── DUT (top-level wrapper) ───────────────────────────────────────────
  {{TOP_NAME}} u_dut (
    .{{DOMAIN}}_clk   ({{DOMAIN}}_clk),
    .{{DOMAIN}}_rst_n ({{DOMAIN}}_rst_n)
    // TODO: Connect top-level ports
  );

  // ─── Clock + Reset ─────────────────────────────────────────────────────
  initial {{DOMAIN}}_clk = 1'b0;
  always #(L_CLK_PERIOD / 2) {{DOMAIN}}_clk = ~{{DOMAIN}}_clk;

  // ─── Waveform Dump ─────────────────────────────────────────────────────
  initial begin
    `ifdef FSDB_DUMP
      $fsdbDumpfile("sim/top/integration_tb.fsdb");
      $fsdbDumpvars(0, integration_tb_{{TOP_NAME}}, "+all");
    `endif
    `ifdef SHM_DUMP
      $shm_open("sim/top/integration_tb.shm");
      $shm_probe(integration_tb_{{TOP_NAME}}, "ASMC");
    `endif
    `ifdef VCD_DUMP
      $dumpfile("sim/top/integration_tb.vcd");
      $dumpvars(0, integration_tb_{{TOP_NAME}});
    `endif
  end

  // ─── Timeout ───────────────────────────────────────────────────────────
  initial begin
    repeat (L_TIMEOUT) @(posedge {{DOMAIN}}_clk);
    $display("ERROR: Integration test timeout");
    $finish(1);
  end

  // ─── Test Infrastructure ───────────────────────────────────────────────
  int pass_count = 0;
  int fail_count = 0;

  task automatic check(input string name, input logic [63:0] actual, input logic [63:0] expected);
    if (actual === expected) begin
      pass_count++;
      $display("  [PASS] %s", name);
    end else begin
      fail_count++;
      $display("  [FAIL] %s: expected 0x%0h, got 0x%0h", name, expected, actual);
    end
  endtask

  task automatic apply_reset();
    {{DOMAIN}}_rst_n = 1'b0;
    repeat (10) @(posedge {{DOMAIN}}_clk);
    {{DOMAIN}}_rst_n = 1'b1;
    repeat (5) @(posedge {{DOMAIN}}_clk);
  endtask

  // ─── Integration Test Scenarios ────────────────────────────────────────
  initial begin
    $display("=== Integration Test: {{TOP_NAME}} ===");
    apply_reset();

    // ── T1: Static Connectivity ──────────────────────────────────────
    // Verify inter-module signal connections are correct after reset
    $display("--- T1: Static connectivity ---");
    // TODO: check internal signal connections
    // check("moduleA_to_moduleB", u_dut.u_moduleB.i_data, u_dut.u_moduleA.o_data);

    // ── T2: Reset Propagation ────────────────────────────────────────
    // Verify all sub-modules reach known state after reset
    $display("--- T2: Reset propagation ---");
    // TODO: check sub-module reset states
    // check("moduleA_reset_state", u_dut.u_moduleA.o_state, ST_IDLE);

    // ── T3: End-to-End Data Flow ─────────────────────────────────────
    // Drive input, verify output matches reference after pipeline latency
    $display("--- T3: End-to-end data flow ---");
    // TODO: apply stimulus at input, wait pipeline latency, check output
    // i_data = 32'hDEAD_BEEF;
    // repeat (PIPELINE_LATENCY) @(posedge {{DOMAIN}}_clk);
    // check("e2e_data", o_result, expected_from_ref);

    // ── T4: Handshake / Backpressure ─────────────────────────────────
    // Test valid/ready propagation across module boundaries
    $display("--- T4: Handshake propagation ---");
    // TODO: assert backpressure at output, verify it propagates to input

    // ── T5: Clock Domain Crossing (if multi-clock) ───────────────────
    // $display("--- T5: CDC paths ---");
    // TODO: verify data integrity across clock domain boundaries

    // ── Summary ──────────────────────────────────────────────────────
    $display("=== Results: %0d passed, %0d failed ===", pass_count, fail_count);
    if (fail_count == 0) begin
      $display("ALL INTEGRATION TESTS PASSED");
      $finish(0);
    end else begin
      $display("INTEGRATION TESTS FAILED");
      $finish(1);
    end
  end

endmodule
