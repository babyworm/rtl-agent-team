// tb_{{MODULE_NAME}}.sv — Unit Testbench for {{MODULE_NAME}}
// Auto-generated scaffold from sv-testbench-template.sv
// Tier 2: uarch feature verification with reference model comparison
//
// Conventions (CLAUDE.md):
//   - DUT instance: u_dut
//   - Clock: {{DOMAIN}}_clk, Reset: {{DOMAIN}}_rst_n (active-low async)
//   - Ports: i_ prefix (input), o_ prefix (output)
//   - Types: logic only (no reg/wire)

`timescale 1ns / 1ps

module tb_{{MODULE_NAME}};

  // ─── Parameters ────────────────────────────────────────────────────────
  localparam int L_CLK_PERIOD = 10;  // ns
  localparam int L_TIMEOUT    = 100_000;  // cycles

  // ─── Signals ───────────────────────────────────────────────────────────
  logic {{DOMAIN}}_clk;
  logic {{DOMAIN}}_rst_n;

  // TODO: Add DUT port signals here
  // logic [DATA_WIDTH-1:0] i_data;
  // logic                  i_valid;
  // logic [DATA_WIDTH-1:0] o_result;
  // logic                  o_ready;

  // ─── DUT Instantiation ─────────────────────────────────────────────────
  {{MODULE_NAME}} u_dut (
    .{{DOMAIN}}_clk   ({{DOMAIN}}_clk),
    .{{DOMAIN}}_rst_n ({{DOMAIN}}_rst_n)
    // TODO: Connect DUT ports
    // .i_data   (i_data),
    // .i_valid  (i_valid),
    // .o_result (o_result),
    // .o_ready  (o_ready)
  );

  // ─── Clock Generation ──────────────────────────────────────────────────
  initial {{DOMAIN}}_clk = 1'b0;
  always #(L_CLK_PERIOD / 2) {{DOMAIN}}_clk = ~{{DOMAIN}}_clk;

  // ─── Waveform Dump ─────────────────────────────────────────────────────
  initial begin
    $dumpfile($sformatf("sim/{{MODULE_NAME}}/tb_{{MODULE_NAME}}.vcd"));
    $dumpvars(0, tb_{{MODULE_NAME}});
  end

  // ─── Timeout Watchdog ──────────────────────────────────────────────────
  initial begin
    repeat (L_TIMEOUT) @(posedge {{DOMAIN}}_clk);
    $display("ERROR: Simulation timeout after %0d cycles", L_TIMEOUT);
    $finish(1);
  end

  // ─── Test Infrastructure ───────────────────────────────────────────────
  int pass_count = 0;
  int fail_count = 0;
  int test_count = 0;

  task automatic apply_reset();
    {{DOMAIN}}_rst_n = 1'b0;
    repeat (5) @(posedge {{DOMAIN}}_clk);
    {{DOMAIN}}_rst_n = 1'b1;
    repeat (2) @(posedge {{DOMAIN}}_clk);
  endtask

  task automatic check(
    input string test_name,
    input logic [63:0] actual,
    input logic [63:0] expected
  );
    test_count++;
    if (actual === expected) begin
      pass_count++;
      $display("  [PASS] %s: got 0x%0h", test_name, actual);
    end else begin
      fail_count++;
      $display("  [FAIL] %s: expected 0x%0h, got 0x%0h", test_name, expected, actual);
    end
  endtask

  // ─── Test Sequence ─────────────────────────────────────────────────────
  initial begin
    $display("=== Unit Test: {{MODULE_NAME}} ===");

    // Reset
    apply_reset();

    // ─── Test Case Design (derive from uarch spec + io_definition.json) ───
    //
    // Boundary Value Analysis (for each input of width W):
    //   Unsigned: 0, 1, 2**(W-1)-1, 2**(W-1), 2**W-2, 2**W-1
    //   Signed:   -(2**(W-1)), -(2**(W-1))+1, -1, 0, +1, 2**(W-1)-1
    //   Address:  base, base+1, top-1, top (alignment boundaries)
    //   Counter:  0, 1, depth-1, depth (empty/full conditions)
    //
    // FSM State Transitions:
    //   Test all valid transitions from uarch state diagram
    //   At least one illegal transition attempt per state
    //   Reset recovery from every reachable state
    //
    // Interface (valid/ready):
    //   Backpressure: valid high, ready low for >N cycles
    //   Zero-gap: back-to-back transfers with no idle
    //   Single-beat and max-burst transfers
    //
    // Error Injection:
    //   Reset during active operation
    //   Invalid input encodings (reserved/illegal per spec)
    //   Overflow/underflow at arithmetic boundaries

    // TODO: Replace examples below with spec-derived test vectors
    //
    // Test 1: FSM state transitions
    // $display("--- Test 1: FSM state transitions ---");
    // check("idle_to_active", o_state, ST_ACTIVE);
    //
    // Test 2: Boundary values
    // $display("--- Test 2: Boundary values ---");
    // i_data = '0; @(posedge sys_clk); check("bva_zero", o_result, expected_zero);
    // i_data = '1; @(posedge sys_clk); check("bva_max", o_result, expected_max);
    //
    // Test 3: Reference model comparison
    // $display("--- Test 3: Ref model compare ---");
    // check("transform_result", o_result, expected_from_ref);

    // ─── Summary ─────────────────────────────────────────────────────────
    $display("=== Results: %0d/%0d passed ===", pass_count, test_count);

    if (fail_count == 0) begin
      $display("ALL TESTS PASSED");
      $finish(0);
    end else begin
      $display("TESTS FAILED: %0d failures", fail_count);
      $finish(1);
    end
  end

endmodule
